import re
import time
import asyncio
from telethon import events
from core.client import client
from utils.helpers import safe_edit_status


# Expresión regular para códigos JAV (ej: PRED-769, DVDMS-149, GVG-707, etc.)
JAV_REGEX = re.compile(r'\b([a-zA-Z0-9]{2,10}-\d{2,7})\b')

# Prefijos excluidos comunes para evitar falsos positivos
EXCLUDED_PREFIXES = {
    'ep', 'pt', 'part', 'cap', 'vol', 'v', 'ed', 'id', 'p',
    'dvd', 'cd', 'mp4', 'mkv', 'avi', 'gif', 'png', 'jpg'
}

def determine_censorship(text):
    text_lower = text.lower()
    # Buscar "sin censura", "uncensored" o "s/c"
    if "sin censura" in text_lower or "uncensored" in text_lower or re.search(r'\b(?:s/c|sin_censura)\b', text_lower):
        return "sin censura"
    # Buscar "con censura", "tiene censura", "censored" o "c/c"
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

async def procesar_comando_code_duplicado(event):
    chat_id = event.chat_id
    
    # Parsear límite opcional de mensajes a escanear
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Escaneando todos los códigos JAV en {limit_desc}...")
    
    try:
        messages = []
        last_update = time.time()
          # 1. Escanear todos los mensajes del canal
        async for m in client.iter_messages(chat_id, limit=limit):
            messages.append(m)
            
            # Throttling de la actualización de estado para evitar FloodWait
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Escaneando portadas... ({len(messages)} analizados)")
                last_update = now
                
        # 2. Extraer códigos JAV y agrupar por (código, censura) de las portadas (imágenes)
        codes_map = {}
        
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
                
                # Omitir prefijos de la lista de excluidos o si ya se vio en este mensaje
                if prefix.lower() in EXCLUDED_PREFIXES or code_upper in seen_in_msg:
                    continue
                    
                seen_in_msg.add(code_upper)
                
                key = (code_upper, censorship)
                if key not in codes_map:
                    codes_map[key] = []
                codes_map[key].append(msg)

        if not codes_map:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontraron portadas con códigos JAV en los mensajes analizados.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return

        # 3. Procesar y ordenar duplicados
        chat = await event.get_chat()
        channel_id_str = str(chat.id).replace("-100", "")
        is_public = bool(getattr(chat, 'username', None))
        
        duplicate_groups = []
        for (code, censorship), msgs_list in codes_map.items():
            if len(msgs_list) > 1:
                # Ordenar por ID ascendente (más antiguo primero)
                msgs_list.sort(key=lambda x: x.id)
                duplicate_groups.append(((code, censorship), msgs_list))
                
        # Ordenar alfabéticamente por código y censura
        duplicate_groups.sort(key=lambda x: (x[0][0], x[0][1]))

        # Eliminar el mensaje de búsqueda inicial
        await status_msg.delete()

        # 4. Enviar reporte de duplicados
        if duplicate_groups:
            dup_lines = []
            for (code, censorship), msgs_list in duplicate_groups:
                censorship_label = f" ({censorship})" if censorship else ""
                
                group_lines = []
                for msg_idx, msg in enumerate(msgs_list):
                    link = f"https://t.me/{chat.username}/{msg.id}" if is_public else f"https://t.me/c/{channel_id_str}/{msg.id}"
                    status_tag = "original" if msg_idx == 0 else "duplicado"
                    line_text = f"({msg_idx+1}) <a href=\"{link}\">{code}{censorship_label} {status_tag}</a>"
                    group_lines.append(line_text)
                    
                dup_lines.append("\n".join(group_lines))

            # Enviar reporte en partes si supera el límite de Telegram
            dup_report_chunks = []
            curr_dup_chunk = "⚠️ **Códigos Duplicados Detectados en Portadas:**\n\n"
            
            for block in dup_lines:
                if len(curr_dup_chunk) + len(block) + 4 > 3500:
                    dup_report_chunks.append(curr_dup_chunk)
                    curr_dup_chunk = ""
                curr_dup_chunk += block + "\n\n"
                
            if curr_dup_chunk:
                dup_report_chunks.append(curr_dup_chunk.strip())
                
            for chunk in dup_report_chunks:
                await event.respond(chunk + "\u200b", parse_mode='html', link_preview=False)
                await asyncio.sleep(1)
        else:
            await event.respond("✅ **No se encontraron códigos duplicados en las portadas.**\u200b", parse_mode='html', link_preview=False)
            
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(10)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
