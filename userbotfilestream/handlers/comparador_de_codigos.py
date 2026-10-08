import os
import re
import time
import asyncio
import datetime
from telethon import events
from core.client import client
from utils.channel_resolver import is_jav_channel
from utils.helpers import safe_edit_status


# ReportLab imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

# Expresión regular para códigos JAV (ej: PRED-769, DVDMS-149, GVG-707, etc.)
JAV_REGEX = re.compile(r'\b([a-zA-Z0-9]{2,10}-\d{2,7})\b')

# Prefijos excluidos comunes para evitar falsos positivos
EXCLUDED_PREFIXES = {
    'ep', 'pt', 'part', 'cap', 'vol', 'v', 'ed', 'id', 'p',
    'dvd', 'cd', 'mp4', 'mkv', 'avi', 'gif', 'png', 'jpg'
}

def determine_censorship(text):
    text_lower = text.lower()
    # Buscar "sin censura", "uncensored" o el indicador rápido "s/c"
    if "sin censura" in text_lower or "uncensored" in text_lower or re.search(r'\b(?:s/c|sin_censura)\b', text_lower):
        return "sin censura"
    # Buscar "con censura", "tiene censura", "censored" o el indicador rápido "c/c"
    if "con censura" in text_lower or "tiene censura" in text_lower or "censored" in text_lower or re.search(r'\b(?:c/c|con_censura)\b', text_lower):
        return "con censura"
    return None

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#718096"))
        
        # En páginas > 1, dibujar línea superior de cabecera
        if self._pageNumber > 1:
            self.drawString(54, 750, "Bot Prime - Comparador de Códigos JAV")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)
        
        # Dibujar pie de página
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(558, 40, page_text)
        
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.drawString(54, 40, f"Generado el {now_str}")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 52, 558, 52)
        
        self.restoreState()

async def procesar_comando_comparador_de_codigos(event):
    chat_id = event.chat_id
    
    # Obtener información del chat
    chat = await event.get_chat()
    chat_title = getattr(chat, 'title', '') or ''
    is_private = event.is_private
    
    # Restringir a canales JAV o chats privados del propio userbot
    if not is_private and not is_jav_channel(chat_id, chat_title):
        error_msg = await event.reply("❌ **[Bot Prime]** Este comando es exclusivo para canales **JAV**.")
        await asyncio.sleep(5)
        await client.delete_messages(chat_id, [event.id, error_msg.id])
        return

    # Parsear límite opcional de mensajes a escanear (ej: /comparador_de_codigos 150)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Analizando portadas en {limit_desc} para generar el PDF comparativo...")
    
    try:
        messages = []
        last_update = time.time()
        
        # 1. Escanear mensajes
        async for m in client.iter_messages(chat_id, limit=limit):
            messages.append(m)
            
            # Throttling de la actualización de estado para evitar FloodWait
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Escaneando portadas... ({len(messages)} analizados)")
                last_update = now
                
        # 2. Extraer y agrupar por base_code -> censorship -> lista de mensajes
        codes_groups = {}
        
        for msg in messages:
            # Procesar únicamente portadas/imágenes
            is_image = False
            if msg.photo:
                is_image = True
            elif msg.document:
                mime = msg.document.mime_type or ""
                if mime.startswith('image/'):
                    is_image = True
            
            if not is_image:
                continue
                    
            text_sources = []
            if msg.message:
                text_sources.append(msg.message)
            if msg.file and msg.file.name:
                text_sources.append(msg.file.name)
                
            full_text = " ".join(text_sources)
            if not full_text:
                continue
                
            matches = JAV_REGEX.findall(full_text)
            if not matches:
                continue
                
            censorship = determine_censorship(full_text)
            if censorship is None:
                censorship = ""  # Sin etiqueta
                
            seen_in_msg = set()
            for raw_code in matches:
                code_upper = raw_code.upper()
                prefix = code_upper.split('-')[0]
                
                # Omitir prefijos si están en la lista de excluidos o si ya se procesaron en este mensaje
                if prefix.lower() in EXCLUDED_PREFIXES or code_upper in seen_in_msg:
                    continue
                    
                seen_in_msg.add(code_upper)
                
                if code_upper not in codes_groups:
                    codes_groups[code_upper] = {"sin censura": [], "con censura": [], "": []}
                
                codes_groups[code_upper][censorship].append(msg)

        if not codes_groups:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontraron portadas con códigos JAV en los mensajes analizados.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return

        # 3. Preparar los datos del reporte para el PDF
        channel_id_str = str(chat.id).replace("-100", "")
        is_public = bool(getattr(chat, 'username', None))
        
        sorted_keys = sorted(codes_groups.keys())
        
        # Estilos de ReportLab
        styles = getSampleStyleSheet()
        normal_style = styles['Normal']
        
        # Crear estilos personalizados para las celdas
        cell_style = ParagraphStyle(
            'Cell',
            parent=normal_style,
            fontName='Helvetica',
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#2D3748")
        )
        
        header_style = ParagraphStyle(
            'HeaderCell',
            parent=normal_style,
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=12,
            textColor=colors.white
        )
        
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Title'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1A365D"),
            alignment=0  # Alinear a la izquierda
        )
        
        desc_style = ParagraphStyle(
            'DocDesc',
            parent=normal_style,
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#4A5568")
        )
        
        table_data = [
            [Paragraph("<b>Sin Censura / Sin Etiqueta</b>", header_style), Paragraph("<b>Con Censura</b>", header_style)]
        ]
        
        for code in sorted_keys:
            left_list = codes_groups[code]["sin censura"] + codes_groups[code][""]
            left_list.sort(key=lambda x: x.id)
            
            right_list = codes_groups[code]["con censura"]
            right_list.sort(key=lambda x: x.id)
            
            if not left_list and not right_list:
                continue
                
            max_len = max(len(left_list), len(right_list))
            for i in range(max_len):
                left_msg = left_list[i] if i < len(left_list) else None
                right_msg = right_list[i] if i < len(right_list) else None
                
                # Construir celda izquierda
                if left_msg:
                    left_cens = determine_censorship(left_msg.message or "")
                    left_label = f"{code} (sin censura)" if left_cens == "sin censura" else code
                    left_link = f"https://t.me/{chat.username}/{left_msg.id}" if is_public else f"https://t.me/c/{channel_id_str}/{left_msg.id}"
                    left_html = f'<font color="#2B6CB0"><u><a href="{left_link}">{left_label}</a></u></font>'
                    left_p = Paragraph(left_html, cell_style)
                else:
                    left_p = Paragraph("—", cell_style)
                    
                # Construir celda derecha
                if right_msg:
                    right_label = f"{code} (con censura)"
                    right_link = f"https://t.me/{chat.username}/{right_msg.id}" if is_public else f"https://t.me/c/{channel_id_str}/{right_msg.id}"
                    right_html = f'<font color="#2B6CB0"><u><a href="{right_link}">{right_label}</a></u></font>'
                    right_p = Paragraph(right_html, cell_style)
                else:
                    right_p = Paragraph("", cell_style)
                    
                table_data.append([left_p, right_p])

        # 4. Generar el archivo PDF
        pdf_filename = f"Comparativo_Codigos_{chat.id}.pdf"
        doc = SimpleDocTemplate(
            pdf_filename,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=70,
            bottomMargin=70
        )
        
        # Construir y aplicar estilos a la tabla
        # Ancho disponible: 612 (letter width) - 108 (margins) = 504. Cada columna 252.
        t = Table(table_data, colWidths=[252, 252])
        t_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A365D")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ])
        
        # Alternar colores de fila
        for idx in range(1, len(table_data)):
            if idx % 2 == 0:
                t_style.add('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#F7FAFC"))
                
        t.setStyle(t_style)
        
        elements = [
            Paragraph("Cuadro Comparativo de Códigos JAV", title_style),
            Spacer(1, 6),
            Paragraph(f"Canal: <b>{chat_title}</b> | Rango escaneado: {limit_desc}", desc_style),
            Spacer(1, 15),
            t
        ]
        
        # Compilar PDF en hilo secundario para evitar bloquear Telethon
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: doc.build(elements, canvasmaker=NumberedCanvas))
        
        # 5. Enviar el PDF por Telegram
        await client.send_file(
            chat_id,
            file=pdf_filename,
            caption=(
                f"📊 **[Bot Prime]** Cuadro comparativo de códigos JAV generado correctamente en formato PDF.\n\n"
                f"🧹 **Para limpiar este reporte:** `/limpiar`"
            ),
            reply_to=event.id
        )
        
        # Eliminar el archivo del disco inmediatamente
        if os.path.exists(pdf_filename):
            os.remove(pdf_filename)
            
        await status_msg.delete()
        
    except Exception as e:
        try:
            if 'pdf_filename' in locals() and os.path.exists(pdf_filename):
                os.remove(pdf_filename)
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error al generar PDF: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
