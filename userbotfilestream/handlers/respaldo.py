import asyncio
import time
import re
import os
import hashlib
from telethon import events
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeFilename
from telethon.errors import FloodWaitError
from core.client import client, config
from utils.helpers import safe_edit_status, get_message_title
from utils.database import DB

def is_media_message(msg):
    if not msg:
        return False
    if msg.video or msg.photo:
        return True
    if msg.document:
        mime = msg.document.mime_type or ""
        if mime.startswith('video/') or mime.startswith('image/'):
            return True
        file_name = ""
        for attr in msg.document.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                file_name = attr.file_name
                break
        if file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff')):
            return True
    return False

def get_media_properties(msg):
    if msg.photo:
        photo = msg.photo
        file_id = photo.id
        file_size = photo.sizes[-1].size if photo.sizes else 0
        file_name = f"photo_{msg.id}.jpg"
        mime_type = "image/jpeg"
        return file_name, file_size, mime_type, file_id
        
    doc = getattr(msg, 'video', None) or getattr(msg, 'document', None)
    if not doc:
        return "", 0, "", 0
        
    file_name = ""
    for attr in doc.attributes:
        if isinstance(attr, DocumentAttributeFilename):
            file_name = attr.file_name
            break
            
    file_size = doc.size
    mime_type = doc.mime_type or ""
    file_id = doc.id
    return file_name, file_size, mime_type, file_id

def calculate_go_hash(file_name, file_size, mime_type, file_id, hash_length=6):
    file_name = file_name or ""
    mime_type = mime_type or ""
    val_str = f"{file_name}{file_size}{mime_type}{file_id}"
    hasher = hashlib.md5()
    hasher.update(val_str.encode('utf-8'))
    full_hash = hasher.hexdigest()
    return full_hash[:hash_length]

def get_stream_base_url():
    env_url = os.environ.get("STREAM_BASE_URL")
    if env_url:
        return env_url.rstrip("/")
    
    space_id = os.environ.get("SPACE_ID")
    if space_id:
        subdomain = space_id.replace("/", "-").lower()
        return f"https://{subdomain}.hf.space"
        
    return "http://localhost:7861"

def format_duration(seconds):
    if seconds is None:
        return "0:00"
    seconds_int = int(seconds)
    m = seconds_int // 60
    s = seconds_int % 60
    h = m // 60
    m = m % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
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
    return duration, size

async def procesar_comando_respaldo(event):
    chat = await event.get_chat()
    chat_id = str(event.chat_id)
    channel_title = getattr(chat, 'title', 'Canal Privado')
    
    # Solo permitir en canales o grupos
    if event.is_private:
        await event.reply("❌ **[Bot Prime]** Este comando solo puede ser ejecutado dentro de un canal o grupo.")
        return

    # Parse scanning limit (optional)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    status_msg = await event.reply(
        "⚡ **[Bot Prime] Iniciando respaldo del canal...**\n\n"
        "🔄 **Paso 1/4**: Escaneando historial en busca de videos y fotos...\n"
        "⏳ **Paso 2/4**: Clasificando archivos y comprobando base de datos...\n"
        "⏳ **Paso 3/4**: Reenviando al canal de respaldo...\n"
        "⏳ **Paso 4/4**: Guardando en base de datos Firebase..."
    )
    
    try:
        # Cargar datos del canal
        channel_data = await DB.get_channel_data(chat_id)
        if not channel_data:
            channel_data = {
                "channel_title": channel_title,
                "username": getattr(chat, 'username', None),
                "videos": []
            }
        else:
            channel_data["channel_title"] = channel_title
            channel_data["username"] = getattr(chat, 'username', None)
            if "videos" not in channel_data:
                channel_data["videos"] = []
                
        channel_id_str = chat_id.replace("-100", "")
        is_public = bool(getattr(chat, 'username', None))

        # 1. Escanear fotos y videos del canal
        media_messages = []
        async for m in client.iter_messages(event.chat_id, limit=limit):
            if is_media_message(m):
                media_messages.append(m)

        if not media_messages:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontró ningún video o foto en este canal.")
            return

        await safe_edit_status(
            status_msg,
            f"⚡ **[Bot Prime] Respaldo en progreso...**\n\n"
            f"✅ **Paso 1/4**: Escaneo completado ({len(media_messages)} archivos encontrados).\n"
            f"🔄 **Paso 2/4**: Clasificando archivos y comprobando base de datos...\n"
            f"⏳ **Paso 3/4**: Reenviando al canal de respaldo...\n"
            f"⏳ **Paso 4/4**: Guardando en base de datos Firebase..."
        )

        existing_videos = {str(v["id"]): v for v in channel_data["videos"]}
        
        # Clasificar
        to_backup = []     # Lista de (m, video_data)
        to_hash = []       # Lista de (m, video_data, backup_id)
        new_videos_list = []
        
        # Soportar usernames o enteros puros con o sin -100
        chat_id_str = str(chat_id)
        if not chat_id_str.startswith("-100") and chat_id_str.lstrip("-").isdigit():
            chat_id_int = int(f"-100{chat_id_str.lstrip('-')}")
        else:
            chat_id_int = int(chat_id_str) if chat_id_str.lstrip("-").isdigit() else chat_id_str

        for m in media_messages:
            title = get_message_title(m)
            if not title or not title.strip():
                prefix = "Video" if (m.video or (m.document and (m.document.mime_type or "").startswith("video/"))) else "Imagen"
                title = f"{prefix} #{m.id}"

            v_duration = None
            v_size = None
            if m.photo:
                # Foto
                v_size = m.photo.sizes[-1].size if m.photo.sizes else 0
                dur_str = "0:00"
            else:
                # Video/Doc
                v_duration, v_size = get_video_info(m)
                dur_str = format_duration(v_duration)
                
            sz_str = format_size(v_size)
            link = f"https://t.me/{chat.username}/{m.id}" if is_public else f"https://t.me/c/{channel_id_str}/{m.id}"

            msg_id_str = str(m.id)
            has_valid_url = False
            if msg_id_str in existing_videos:
                url = existing_videos[msg_id_str].get("stream_url")
                if url and "hash=" in url:
                    has_valid_url = True

            video_data = {
                "id": m.id,
                "title": title,
                "link": link,
                "duration": dur_str,
                "size": sz_str,
                "stream_url": None,
                "indexed_at": int(time.time()),
                "pinned": bool(getattr(m, "pinned", False))
            }

            if has_valid_url:
                cached_data = existing_videos[msg_id_str]
                base_url = get_stream_base_url()
                match = re.search(r'/stream/\d+\?hash=[a-f0-9]+', cached_data["stream_url"])
                if match:
                    video_data["stream_url"] = f"{base_url}{match.group(0)}"
                else:
                    video_data["stream_url"] = cached_data["stream_url"]
                video_data["pinned"] = bool(getattr(m, "pinned", False))
                new_videos_list.append(video_data)
            else:
                video_key = f"video_{chat_id_int}_{m.id}"
                backup_id = await DB.get_backup_msg_id(video_key)
                if backup_id:
                    to_hash.append((m, video_data, backup_id))
                else:
                    to_backup.append((m, video_data))

        total_a_respaldar = len(to_backup)
        total_a_generar = len(to_hash)

        BACKUP_CHANNEL_ID = config.get("backup_channel_id")
        if not BACKUP_CHANNEL_ID:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encuentra configurado 'backup_channel_id' en config.json")
            return

        paso3_final = "✅ **Paso 3/4**: Reenvío de respaldo no requerido (Al día)."
        
        if total_a_respaldar > 0:
            batch_size = 100
            total_lotes = (total_a_respaldar + batch_size - 1) // batch_size
            
            for idx in range(0, total_a_respaldar, batch_size):
                batch_tuples = to_backup[idx:idx+batch_size]
                batch_msgs = [item[0] for item in batch_tuples]
                lote_num = (idx // batch_size) + 1
                
                await safe_edit_status(
                    status_msg,
                    f"⚡ **[Bot Prime] Respaldo en progreso...**\n\n"
                    f"✅ **Paso 1/4**: Escaneo completado.\n"
                    f"✅ **Paso 2/4**: Clasificación completa (Nuevos a respaldar: {total_a_respaldar}).\n"
                    f"🔄 **Paso 3/4**: Reenviando lote {lote_num} de {total_lotes} al canal de respaldo...\n"
                    f"⏳ **Paso 4/4**: Generando hashes de transmisión..."
                )
                
                retry = True
                forwarded_msgs = []
                while retry:
                    try:
                        forwarded_msgs = await client.forward_messages(BACKUP_CHANNEL_ID, batch_msgs)
                        retry = False
                    except FloodWaitError as e:
                        await safe_edit_status(
                            status_msg,
                            f"⚡ **[Bot Prime] Respaldo en progreso...**\n\n"
                            f"✅ **Paso 1/4**: Escaneo completado.\n"
                            f"✅ **Paso 2/4**: Clasificación completa.\n"
                            f"⏳ **Paso 3/4**: Límite de Telegram alcanzado. Esperando {e.seconds}s para lote {lote_num} de {total_lotes}...\n"
                            f"⏳ **Paso 4/4**: Generando hashes..."
                        )
                        await asyncio.sleep(e.seconds + 2)
                    except Exception as e:
                        print(f"[Backup Error] Error reenviando lote: {e}")
                        retry = False
                        forwarded_msgs = [None] * len(batch_msgs)

                for item, f_msg in zip(batch_tuples, forwarded_msgs):
                    m, v_data = item
                    if f_msg:
                        video_key = f"video_{chat_id_int}_{m.id}"
                        await DB.save_backup_msg_id(video_key, f_msg.id)
                        to_hash.append((m, v_data, f_msg.id))

                await asyncio.sleep(3.0)
            paso3_final = f"✅ **Paso 3/4**: Reenvío finalizado ({total_a_respaldar} archivos respaldados)."

        # Generar hashes/enlaces
        procesados = 0
        fallidos = 0
        total_hash = len(to_hash)

        await safe_edit_status(
            status_msg,
            f"⚡ **[Bot Prime] Respaldo en progreso...**\n\n"
            f"✅ **Paso 1/4**: Escaneo completado.\n"
            f"✅ **Paso 2/4**: Clasificación completa.\n"
            f"{paso3_final}\n"
            f"🔄 **Paso 4/4**: Guardando en base de datos Firebase..."
        )

        if total_hash > 0:
            for m, v_data, backup_id in to_hash:
                try:
                    file_name, file_size, mime_type, file_id = get_media_properties(m)
                    hash_val = calculate_go_hash(file_name, file_size, mime_type, file_id)
                    
                    base_url = get_stream_base_url()
                    v_data["stream_url"] = f"{base_url}/stream/{backup_id}?hash={hash_val}"
                    new_videos_list.append(v_data)
                    procesados += 1
                except Exception as e:
                    print(f"[Hash Error] Error al procesar hash para {m.id}: {e}")
                    fallidos += 1

        # Guardar catálogo ordenado
        channel_data["videos"] = sorted(new_videos_list, key=lambda x: x["id"])
        await DB.save_channel_data(chat_id, channel_data)

        await safe_edit_status(
            status_msg,
            f"✅ **[Bot Prime] ¡Respaldo completado con éxito!**\n\n"
            f"✅ **Paso 1/4**: Escaneo completado.\n"
            f"✅ **Paso 2/4**: Clasificación completa.\n"
            f"{paso3_final}\n"
            f"✅ **Paso 4/4**: Base de datos Firebase actualizada.\n\n"
            f"📁 **Total en respaldo**: {len(new_videos_list)} archivos guardados.\n"
            f"📥 **Nuevos respaldados**: {procesados} (Fallidos: {fallidos})."
        )
        
    except Exception as e:
        print(f"[Error Respaldo] {e}")
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Ocurrió un error inesperado al respaldar: {e}")
        except Exception:
            pass
