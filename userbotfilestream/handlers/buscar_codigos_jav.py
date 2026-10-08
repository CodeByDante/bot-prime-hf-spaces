import re
import time
import asyncio
from telethon import events
from core.client import client
from utils.channel_resolver import matches_channel
from utils.helpers import safe_edit_status



# Expresión regular para códigos JAV (ej: PRED-769, DVDMS-149, GVG-707, etc.)
# Coincide con secuencias de letras y números seguidas de un guion y dígitos.
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

def extract_part(text):
    # Buscar formato de parte estilo "1/2", "[1/2]", "(1/2)" o "1 de 2"
    match = re.search(r'\[?(\d+)\s*(?:/|de)\s*(\d+)\]?', text, re.IGNORECASE)
    if match:
        p_num = int(match.group(1))
        p_tot = int(match.group(2))
        return f"[{p_num}/{p_tot}]", (p_num, p_tot)
    
    # Buscar formato "parte 1", "part 2", "pt 3"
    match = re.search(r'\b(?:part|parte|pt)\.?\s*(\d+)\b', text, re.IGNORECASE)
    if match:
        p_num = int(match.group(1))
        return f"[{p_num}]", (p_num, 99)
        
    return "", (0, 0)

async def procesar_comando_buscar_codigos_jav(event):
    chat_id = event.chat_id
    
    # Obtener información del chat
    chat = await event.get_chat()
    chat_title = getattr(chat, 'title', '') or ''
    is_private = event.is_private
    
    # Restringir a "JAV PREMIUM" excepto para chats privados del propio userbot (desarrollo/pruebas)
    if not is_private and not matches_channel(chat_id, chat_title, "jav_premium"):
        error_msg = await event.reply("❌ **[Bot Prime]** Este comando es exclusivo para el canal **JAV PREMIUM**.")
        await asyncio.sleep(5)
        await client.delete_messages(chat_id, [event.id, error_msg.id])
        return

    # Parsear límite opcional de mensajes a escanear (ej: /buscar_codigos_jav 150)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Iniciando escaneo de códigos JAV en {limit_desc}...")
    
    try:
        messages = []
        last_update = time.time()
        
        # 1. Escanear mensajes
        async for m in client.iter_messages(chat_id, limit=limit):
            messages.append(m)
            
            # Throttling de la actualización de estado para evitar FloodWait
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Escaneando mensajes... ({len(messages)} analizados)")
                last_update = now
                
        # 2. Extraer códigos JAV
        extracted_items = []
        
        # Determinar estructura de enlaces
        channel_id_str = str(chat.id).replace("-100", "")
        is_public = bool(getattr(chat, 'username', None))
        
        for msg in messages:
            # Ignorar portadas/imágenes
            if msg.photo:
                continue
            if msg.document:
                mime = msg.document.mime_type or ""
                if mime.startswith('image/'):
                    continue
                    
            # Buscar en el texto/caption y en el nombre del archivo si aplica
            text_sources = []
            if msg.message:
                text_sources.append(msg.message)
            if msg.file and msg.file.name:
                text_sources.append(msg.file.name)
                
            full_text = " ".join(text_sources)
            if not full_text:
                continue
                
            # Buscar todas las coincidencias de códigos en el texto acumulado del mensaje
            matches = JAV_REGEX.findall(full_text)
            if not matches:
                continue
                
            # Determinar censura y partes para el mensaje
            censorship = determine_censorship(full_text)
            part_str, part_tuple = extract_part(full_text)
            
            # Construir enlace al mensaje
            if is_public:
                msg_link = f"https://t.me/{chat.username}/{msg.id}"
            else:
                msg_link = f"https://t.me/c/{channel_id_str}/{msg.id}"
                
            # Procesar códigos encontrados sin duplicados en el mismo mensaje
            seen_in_msg = set()
            for raw_code in matches:
                code_upper = raw_code.upper()
                prefix = code_upper.split('-')[0]
                
                # Omitir si el prefijo está en la lista de excluidos o si ya se procesó en este mensaje
                if prefix.lower() in EXCLUDED_PREFIXES or code_upper in seen_in_msg:
                    continue
                    
                seen_in_msg.add(code_upper)
                
                # Construir el nombre a mostrar (ej: GVG-707 (sin censura) [1/2])
                name_parts = [code_upper]
                if censorship:
                    name_parts.append(f"({censorship})")
                if part_str:
                    name_parts.append(part_str)
                display_name = " ".join(name_parts)
                
                extracted_items.append({
                    'code': code_upper,
                    'censorship': censorship,
                    'part_str': part_str,
                    'part_sort': part_tuple,
                    'display_name': display_name,
                    'link': msg_link
                })
                
        if not extracted_items:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontraron códigos JAV en los mensajes analizados.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return

        # 3. Ordenar alfabéticamente por código y luego por número de parte
        extracted_items.sort(key=lambda x: (x['code'].lower(), x['part_sort'], x['censorship'] or ''))
        
        # 4. Construir las líneas del reporte
        lines = []
        for item in extracted_items:
            lines.append(f"• <a href=\"{item['link']}\">{item['display_name']}</a>")
            
        # 5. Dividir en mensajes (lotes) de tamaño aceptable para Telegram
        messages_to_send = []
        current_chunk = "🤖 **Lista de Códigos JAV:**\n\n"
        
        for line in lines:
            # Límite de 3500 caracteres para asegurar margen
            if len(current_chunk) + len(line) + 2 > 3500:
                messages_to_send.append(current_chunk)
                current_chunk = ""
            current_chunk += line + "\n"
            
        if current_chunk:
            messages_to_send.append(current_chunk)
            
        # Eliminar el mensaje de estado de búsqueda
        await status_msg.delete()
        
        # 6. Enviar reportes (con marca de agua \u200b para limpieza)
        for chunk in messages_to_send:
            await event.respond(chunk + "\u200b", parse_mode='html', link_preview=False)
            await asyncio.sleep(1)
            
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error al escanear códigos: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
