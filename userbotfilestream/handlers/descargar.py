import os
import uuid
import time
import asyncio
from telethon import events
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeFilename
from core.client import client
from utils.helpers import safe_edit_status, get_message_title

# Almacenamiento en memoria de los lotes activos para descarga
download_batches = {}

def get_web_url():
    space_id = os.environ.get("SPACE_ID")
    if space_id:
        try:
            parts = space_id.split('/')
            if len(parts) == 2:
                user, space = parts
                user_clean = user.lower().replace('_', '-').replace('.', '-')
                space_clean = space.lower().replace('_', '-').replace('.', '-')
                return f"https://{user_clean}-{space_clean}.hf.space"
        except Exception:
            pass
    return "http://localhost:7860"

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

def is_image_message(msg):
    if not msg:
        return False
    if msg.photo:
        return True
    if msg.document:
        mime = msg.document.mime_type or ""
        if mime.startswith('image/'):
            return True
        for attr in msg.document.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                if attr.file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
                    return True
    return False

def get_media_info(msg):
    size = 0
    name = f"archivo_{msg.id}"
    
    if msg.photo:
        # Obtener el tamaño de la foto más grande
        if msg.photo.sizes:
            size = getattr(msg.photo.sizes[-1], 'size', 0)
        name = f"imagen_{msg.id}.jpg"
    elif msg.document:
        size = msg.document.size or 0
        for attr in msg.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                name = attr.file_name
                break
    return name, size

async def procesar_comando_descargar(event, media_type):
    chat_id = event.chat_id
    chat = await event.get_chat()
    
    # Extraer cantidad (argumento)
    command_text = event.message.message
    parts = command_text.split(maxsplit=1)
    
    limit = 10
    if len(parts) >= 2:
        try:
            limit = int(parts[1].strip())
            if limit <= 0:
                limit = 10
            elif limit > 100:
                limit = 100  # Límite máximo razonable para descargas web simultáneas
        except ValueError:
            pass

    status_msg = await event.reply(f"🔍 **[Bot Prime]** Escaneando el canal en busca de los últimos **{limit}** {'videos' if media_type == 'video' else 'imágenes'}...")
    
    try:
        files = []
        # Buscar en los mensajes del canal
        async for m in client.iter_messages(chat_id):
            if len(files) >= limit:
                break
                
            matched = False
            if media_type == "video" and is_video_message(m):
                matched = True
            elif media_type == "image" and is_image_message(m):
                matched = True
                
            if matched:
                name, size = get_media_info(m)
                files.append({
                    "id": m.id,
                    "name": name,
                    "size": size
                })
        
        if not files:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** No se encontró ningún {'video' if media_type == 'video' else 'imagen'} en este canal.")
            return

        # Registrar lote en memoria
        batch_id = str(uuid.uuid4())[:8]
        download_batches[batch_id] = {
            "chat_id": chat_id,
            "type": media_type,
            "files": files,
            "created_at": int(time.time())
        }
        
        web_url = get_web_url()
        download_link = f"{web_url}/download_batch/{batch_id}"
        
        await safe_edit_status(
            status_msg,
            f"✅ **[Bot Prime]** Lote de descarga listo.\n\n"
            f"📦 Archivos encontrados: **{len(files)}** {'videos' if media_type == 'video' else 'imágenes'}.\n\n"
            f"🌐 **Enlace de descarga:** [Clic aquí para descargar]({download_link})"
        )
        
    except Exception as e:
        print(f"[Error Descargar Lote] {e}")
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Ocurrió un error al procesar el lote: {e}")
        except Exception:
            pass
