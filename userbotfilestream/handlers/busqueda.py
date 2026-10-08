import re
import time
import asyncio
from telethon import events
from telethon.tl.types import DocumentAttributeVideo
from core.client import client
from utils.helpers import safe_edit_status, get_message_title

def format_duration(seconds):
    if seconds is None:
        return "Desconocido"
    seconds_int = int(seconds)
    m = seconds_int // 60
    s = seconds_int % 60
    return f"{m}:{s:02d}"

def format_size(size_bytes):
    if size_bytes is None:
        return "Desconocido"
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024*1024*1024):.2f} GB"
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024*1024):.2f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} B"

def is_video_message(msg):
    if not msg:
        return False
    if msg.video:
        return True
    if msg.document:
        mime = msg.document.mime_type or ""
        if mime.startswith('video/'):
            return True
        for attr in msg.document.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                if attr.file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts')):
                    return True
    return False

def get_video_info(msg):
    duration = None
    size = None
    
    doc = getattr(msg, 'video', None) or getattr(msg, 'document', None)
    if doc:
        size = doc.size
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeVideo):
                duration = attr.duration
                break
        if not duration and hasattr(msg, 'file') and msg.file and msg.file.duration:
            duration = msg.file.duration
            
    if duration is not None:
        duration = int(round(duration))
    return duration, size

async def procesar_comando_busqueda(event):
    chat_id = event.chat_id
    
    # Extraer el argumento del comando (todo lo que viene después de /busqueda)
    command_text = event.message.message
    parts = command_text.split(maxsplit=1)
    if len(parts) < 2:
        error_msg = await event.reply(
            "❌ **[Bot Prime]** Formato incorrecto.\n\n"
            "**Ejemplos de uso:**\n"
            "• `/busqueda 26:27` (Busca videos de exactamente 26 minutos y 27 segundos)\n"
            "• `/busqueda 250 mb` (Busca videos de exactamente 250 MB)"
        )
        await asyncio.sleep(8)
        await client.delete_messages(chat_id, [event.id, error_msg.id])
        return

    query = parts[1].strip()
    
    # Intentar parsear como duración (MM:SS)
    duration_match = re.match(r'^(\d+):(\d{2})$', query)
    # Intentar parsear como peso/tamaño (ej: 250 mb, 1.5 gb)
    size_match = re.match(r'^(\d+(?:\.\d+)?)\s*(b|kb|mb|gb)$', query, re.IGNORECASE)
    
    search_type = None
    target_seconds = None
    target_bytes = None
    desc_query = ""
    
    if duration_match:
        minutes = int(duration_match.group(1))
        seconds = int(duration_match.group(2))
        target_seconds = minutes * 60 + seconds
        search_type = "duration"
        desc_query = f"duración exacta de **{query}**"
    elif size_match:
        val = float(size_match.group(1))
        unit = size_match.group(2).lower()
        
        if unit == 'b':
            factor = 1
        elif unit == 'kb':
            factor = 1024
        elif unit == 'mb':
            factor = 1024 * 1024
        elif unit == 'gb':
            factor = 1024 * 1024 * 1024
            
        target_bytes = int(val * factor)
        search_type = "size"
        desc_query = f"peso exacto de **{query.upper()}** ({target_bytes:,} bytes)"
    else:
        error_msg = await event.reply(
            "❌ **[Bot Prime]** Formato de búsqueda no reconocido.\n\n"
            "Use el formato `MM:SS` para duración (ej: `26:27`) o `[número] mb/gb` para peso (ej: `250 mb`)."
        )
        await asyncio.sleep(8)
        await client.delete_messages(chat_id, [event.id, error_msg.id])
        return

    status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando videos con {desc_query}...")
    
    try:
        chat = await event.get_chat()
        channel_id_str = str(chat.id).replace("-100", "")
        is_public = bool(getattr(chat, 'username', None))
        
        coincidencias = []
        messages_scanned = 0
        last_update = time.time()
        
        # Escanear todo el historial del canal
        async for m in client.iter_messages(chat_id):
            messages_scanned += 1
            
            if is_video_message(m):
                v_duration, v_size = get_video_info(m)
                
                matched = False
                if search_type == "duration" and v_duration is not None:
                    if v_duration == target_seconds:
                        matched = True
                elif search_type == "size" and v_size is not None:
                    if v_size == target_bytes:
                        matched = True
                        
                if matched:
                    title = get_message_title(m)
                    if not title or not title.strip():
                        title = f"Video #{m.id}"
                    
                    link = f"https://t.me/{chat.username}/{m.id}" if is_public else f"https://t.me/c/{channel_id_str}/{m.id}"
                    coincidencias.append({
                        'title': title,
                        'link': link,
                        'id': m.id,
                        'duration': v_duration,
                        'size': v_size
                    })
            
            # Throttling de la actualización de estado
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(
                    status_msg, 
                    f"🔍 **[Bot Prime]** Analizando mensajes... ({messages_scanned} analizados, {len(coincidencias)} coincidentes)"
                )
                last_update = now

        if not coincidencias:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** No se encontró ningún video con {desc_query}.")
            await asyncio.sleep(10)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        # Ordenar cronológicamente (ID de menor a mayor / del más antiguo al más nuevo)
        coincidencias.sort(key=lambda x: x['id'])
        
        # Construir el reporte
        lines = []
        for idx, item in enumerate(coincidencias, 1):
            dur_str = format_duration(item['duration'])
            sz_str = format_size(item['size'])
            lines.append(f"{idx}. <a href=\"{item['link']}\">{item['title']}</a> (`{dur_str}` | `{sz_str}`)")
            
        # Dividir el reporte en partes que quepan en el límite de Telegram (4096 caracteres)
        messages_to_send = []
        header = f"🤖 **Resultados de búsqueda ({desc_query}):**\n\n"
        current_chunk = header
        
        for line in lines:
            if len(current_chunk) + len(line) + 2 > 3800:
                messages_to_send.append(current_chunk)
                current_chunk = ""
            current_chunk += line + "\n"
            
        if current_chunk:
            messages_to_send.append(current_chunk)
            
        # Eliminar el mensaje de estado de búsqueda
        await status_msg.delete()
        
        # Enviar reportes
        for chunk in messages_to_send:
            await event.respond(chunk + "\u200b", parse_mode='html', link_preview=False)
            await asyncio.sleep(1)
            
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error en la búsqueda: {e}")
            await asyncio.sleep(10)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
