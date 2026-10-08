import os
import re
import json
import time
import asyncio
import hashlib
from telethon import events
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeFilename
from telethon.errors import FloodWaitError
from core.client import client, config
from utils.helpers import safe_edit_status, get_message_title
from utils.database import DB

# Rutas de archivo
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(BASE_DIR, "videos_cache.json")

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {"channels": {}}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Cache Error] No se pudo leer {CACHE_FILE}: {e}")
        return {"channels": {}}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[Cache Error] No se pudo guardar {CACHE_FILE}: {e}")

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
    return duration, size

def get_web_url():
    space_id = os.environ.get("SPACE_ID")
    if space_id:
        parts = space_id.split('/')
        if len(parts) == 2:
            user, space = parts
            user_clean = user.lower().replace('_', '-').replace('.', '-')
            space_clean = space.lower().replace('_', '-').replace('.', '-')
            return f"https://{user_clean}-{space_clean}.hf.space"
    return "http://127.0.0.1:7860"

def get_message_file_properties(msg):
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


async def get_stream_link_for_video(video_msg):
    BACKUP_CHANNEL_ID = config.get("backup_channel_id")
    if not BACKUP_CHANNEL_ID:
        print("[Stream Error] No se ha configurado backup_channel_id en config.json")
        return None
        
    try:
        # Reenviar al canal de respaldo con soporte para FloodWait
        try:
            forwarded = await client.forward_messages(BACKUP_CHANNEL_ID, video_msg)
        except FloodWaitError as e:
            print(f"[Stream Error] FloodWait detectado al reenviar video, esperando {e.seconds}s...")
            await asyncio.sleep(e.seconds + 2)
            forwarded = await client.forward_messages(BACKUP_CHANNEL_ID, video_msg)
            
        if not forwarded:
            return None
            
        file_name, file_size, mime_type, file_id = get_message_file_properties(video_msg)
        hash = calculate_go_hash(file_name, file_size, mime_type, file_id)
        
        # Guardar la relación en base de datos para no tener que reenviarlo en el futuro
        if video_msg.chat_id:
            chat_id_str = str(video_msg.chat_id)
            if not chat_id_str.startswith("-100") and chat_id_str.lstrip("-").isdigit():
                chat_id_int = int(f"-100{chat_id_str.lstrip('-')}")
            else:
                chat_id_int = int(chat_id_str) if chat_id_str.lstrip("-").isdigit() else chat_id_str
            video_key = f"video_{chat_id_int}_{video_msg.id}"
            await DB.save_backup_msg_id(video_key, forwarded.id)
            
        return f"{get_stream_base_url()}/stream/{forwarded.id}?hash={hash}"
    except Exception as e:
        print(f"[Stream Error] Error en get_stream_link_for_video: {e}")
        return None

async def respaldar_canal_en_segundo_plano(chat_id):
    # Ya no se requiere en segundo plano porque indexamos síncronamente con parches,
    # pero se mantiene por compatibilidad.
    pass

async def procesar_comando_prime_video(event):
    await _procesar_indexacion_comun(event, mode="video")

async def procesar_comando_prime_imagenes(event):
    await _procesar_indexacion_comun(event, mode="imagenes")

async def _procesar_indexacion_comun(event, mode="video"):
    chat = await event.get_chat()
    chat_id = str(event.chat_id)
    channel_title = getattr(chat, 'title', 'Canal Privado')
    
    # Solo permitir en canales o grupos
    if event.is_private:
        await event.reply("❌ **[Bot Prime]** Este comando solo puede ser ejecutado dentro de un canal o grupo.")
        return
        
    status_msg = await event.reply(
        "⚡ **[Bot Prime] Indexando canal...**\n\n"
        "🔄 **Paso 1/4**: Escaneando historial en busca de videos...\n"
        "⏳ **Paso 2/4**: Clasificando videos y comprobando base de datos...\n"
        "⏳ **Paso 3/4**: Reenviando al canal de respaldo...\n"
        "⏳ **Paso 4/4**: Generando enlaces del catálogo..."
    )
    
    try:
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
        
        # 1. Escanear mensajes de video del canal
        video_messages = []
        async for m in client.iter_messages(event.chat_id):
            if is_video_message(m):
                video_messages.append(m)
                
        if not video_messages:
            await safe_edit_status(
                status_msg, 
                "❌ **[Bot Prime]** No se encontró ningún video en este canal."
            )
            return
            
        await safe_edit_status(
            status_msg,
            f"⚡ **[Bot Prime] Indexando canal...**\n\n"
            f"✅ **Paso 1/4**: Escaneo completado ({len(video_messages)} videos encontrados).\n"
            f"🔄 **Paso 2/4**: Clasificando videos y comprobando base de datos...\n"
            f"⏳ **Paso 3/4**: Reenviando al canal de respaldo...\n"
            f"⏳ **Paso 4/4**: Generando enlaces del catálogo..."
        )
        
        existing_videos = {str(v["id"]): v for v in channel_data["videos"]}
        
        # Clasificar videos
        to_backup = []     # Lista de (m, video_data)
        to_hash = []       # Lista de (m, video_data, backup_id)
        new_videos_list = []
        
        # Soportar usernames o enteros puros con o sin -100
        chat_id_str = str(chat_id)
        if not chat_id_str.startswith("-100") and chat_id_str.lstrip("-").isdigit():
            chat_id_int = int(f"-100{chat_id_str.lstrip('-')}")
        else:
            chat_id_int = int(chat_id_str) if chat_id_str.lstrip("-").isdigit() else chat_id_str
            
        for m in video_messages:
            title = get_message_title(m)
            if not title or not title.strip():
                title = f"Video #{m.id}"
                
            v_duration, v_size = get_video_info(m)
            dur_str = format_duration(v_duration)
            sz_str = format_size(v_size)
            
            link = f"https://t.me/{chat.username}/{m.id}" if is_public else f"https://t.me/c/{channel_id_str}/{m.id}"
            
            # Comprobar si existe en la caché y tiene una URL de stream válida
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
                "indexed_at": int(time.time())
            }
            
            if has_valid_url:
                # Mantener el existente pero actualizar metadatos y reescribir host a actual
                cached_data = existing_videos[msg_id_str]
                base_url = get_stream_base_url()
                match = re.search(r'/stream/\d+\?hash=[a-f0-9]+', cached_data["stream_url"])
                if match:
                    video_data["stream_url"] = f"{base_url}{match.group(0)}"
                else:
                    video_data["stream_url"] = cached_data["stream_url"]
                new_videos_list.append(video_data)
            else:
                # Verificar si ya está respaldado
                video_key = f"video_{chat_id_int}_{m.id}"
                backup_id = await DB.get_backup_msg_id(video_key)
                if backup_id:
                    to_hash.append((m, video_data, backup_id))
                else:
                    to_backup.append((m, video_data))
                    
        total_a_respaldar = len(to_backup)
        total_a_generar = len(to_hash)
        
        # 2. Reenviar videos no respaldados en lotes de 100 con control de FloodWait
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
                    f"⚡ **[Bot Prime] Indexando canal...**\n\n"
                    f"✅ **Paso 1/4**: Escaneo completado ({len(video_messages)} videos).\n"
                    f"✅ **Paso 2/4**: Clasificación completa (Nuevos a respaldar: {total_a_respaldar}).\n"
                    f"🔄 **Paso 3/4**: Reenviando lote {lote_num} de {total_lotes} al canal de respaldo...\n"
                    f"⏳ **Paso 4/4**: Generando enlaces del catálogo..."
                )
                
                # Intentar reenviar el lote con reintentos para FloodWait
                retry = True
                forwarded_msgs = []
                while retry:
                    try:
                        forwarded_msgs = await client.forward_messages(BACKUP_CHANNEL_ID, batch_msgs)
                        retry = False
                    except FloodWaitError as e:
                        # Si Telegram nos limita, dormimos el tiempo sugerido + 2 segundos de colchón
                        await safe_edit_status(
                            status_msg,
                            f"⚡ **[Bot Prime] Indexando canal...**\n\n"
                            f"✅ **Paso 1/4**: Escaneo completado.\n"
                            f"✅ **Paso 2/4**: Clasificación completa.\n"
                            f"⏳ **Paso 3/4**: Límite de Telegram alcanzado. Durmiendo por {e.seconds}s para continuar lote {lote_num} de {total_lotes}...\n"
                            f"⏳ **Paso 4/4**: Generando enlaces del catálogo..."
                        )
                        await asyncio.sleep(e.seconds + 2)
                    except Exception as e:
                        print(f"[Backup Error] Error reenviando lote: {e}")
                        retry = False
                        forwarded_msgs = [None] * len(batch_msgs)
                
                # Guardar IDs de respaldo
                for item, f_msg in zip(batch_tuples, forwarded_msgs):
                    m, v_data = item
                    if f_msg:
                        video_key = f"video_{chat_id_int}_{m.id}"
                        await DB.save_backup_msg_id(video_key, f_msg.id)
                        # Agregar a la lista para calcular hash
                        to_hash.append((m, v_data, f_msg.id))
                        
                # Pequeña pausa entre lotes exitosos para no saturar
                await asyncio.sleep(3.0)
            paso3_final = f"✅ **Paso 3/4**: Reenvío finalizado ({total_a_respaldar} videos respaldados)."
            
        # 3. Generar enlaces de streaming usando hash offline
        procesados = 0
        fallidos = 0
        total_hash = len(to_hash)
        
        await safe_edit_status(
            status_msg,
            f"⚡ **[Bot Prime] Indexando canal...**\n\n"
            f"✅ **Paso 1/4**: Escaneo completado ({len(video_messages)} videos).\n"
            f"✅ **Paso 2/4**: Clasificación completa.\n"
            f"{paso3_final}\n"
            f"🔄 **Paso 4/4**: Generando hashes y enlaces del catálogo para {total_hash} videos..."
        )
        
        if total_hash > 0:
            for m, v_data, backup_id in to_hash:
                try:
                    file_name, file_size, mime_type, file_id = get_message_file_properties(m)
                    hash_val = calculate_go_hash(file_name, file_size, mime_type, file_id)
                    
                    base_url = get_stream_base_url()
                    v_data["stream_url"] = f"{base_url}/stream/{backup_id}?hash={hash_val}"
                    new_videos_list.append(v_data)
                    procesados += 1
                except Exception as e:
                    print(f"[Hash Error] Error al procesar hash del video {m.id}: {e}")
                    fallidos += 1
                    
        # 4. Guardar catálogo ordenado
        channel_data["videos"] = sorted(new_videos_list, key=lambda x: x["id"])
        await DB.save_channel_data(chat_id, channel_data)
        
        # Iniciar la pre-generación de escenas en segundo plano si es modo imagenes
        if mode == "imagenes":
            try:
                from app import add_to_pregeneration_queue
                for v in new_videos_list:
                    v_id = v.get("id")
                    stream_url = v.get("stream_url")
                    dur_str = v.get("duration", "0:00")
                    try:
                        parts = list(map(int, dur_str.split(':')))
                        if len(parts) == 2:
                            duration_sec = parts[0] * 60 + parts[1]
                        elif len(parts) == 3:
                            duration_sec = parts[0] * 3600 + parts[1] * 60 + parts[2]
                        else:
                            duration_sec = 120
                    except Exception:
                        duration_sec = 120
                    
                    if stream_url:
                        await add_to_pregeneration_queue(chat_id, v_id, stream_url, duration_sec)
            except Exception as e:
                print(f"[Pregen Trigger Error] {e}")
        
        web_url = get_web_url()
        if mode == "video":
            catalog_link = f"🎬 **Total en catálogo**: {len(new_videos_list)} videos.\n" \
                           f"📥 **Nuevos indexados**: {procesados} (Fallidos: {fallidos}).\n\n" \
                           f"🌐 **Ver Catálogo**: {web_url}/catalog/{chat_id}"
        else:
            catalog_link = f"🖼️ **Total en catálogo**: {len(new_videos_list)} galerías de escenas.\n" \
                           f"📥 **Nuevos indexados**: {procesados} (Fallidos: {fallidos}).\n\n" \
                           f"🌐 **Ver Catálogo de Escenas**: {web_url}/catalog_images/{chat_id}"
                           
        await safe_edit_status(
            status_msg,
            f"✅ **[Bot Prime] ¡Indexación exitosa y catálogo actualizado!**\n\n"
            f"✅ **Paso 1/4**: Escaneo completado ({len(video_messages)} videos).\n"
            f"✅ **Paso 2/4**: Clasificación completa.\n"
            f"{paso3_final}\n"
            f"✅ **Paso 4/4**: Catálogo web generado exitosamente.\n\n"
            f"{catalog_link}"
        )
        
        # NUEVO: Forzar un backup a la nube tras cada indexación
        try:
            from utils.cloud_backup import force_database_backup
            from utils.database import LOCAL_CACHE_FILE
            asyncio.create_task(force_database_backup(client, LOCAL_CACHE_FILE, trigger_reason="Post-Indexación"))
        except Exception as e:
            print(f"[Backup Error] {e}")
            
    except Exception as e:
        print(f"[Error Prime Video] {e}")
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Ocurrió un error inesperado al indexar: {e}")
        except Exception:
            pass

async def procesar_comando_limpiar_catalogo(event):
    chat_id = str(event.chat_id)
    status_msg = await event.reply("🧹 **[Bot Prime]** Limpiando base de datos y catálogo del canal...")
    
    try:
        # Vaciar el canal en la base de datos
        await DB.save_channel_data(chat_id, {
            "channel_title": getattr(await event.get_chat(), 'title', 'Canal Privado'),
            "username": getattr(await event.get_chat(), 'username', None),
            "videos": []
        })
        
        await safe_edit_status(
            status_msg,
            "✅ **[Bot Prime]** Se ha vaciado la base de datos y el catálogo de este canal en Firebase / local.\n\n"
            "🔄 Ya puedes enviar `/prime_video` para reindexar todo de forma limpia desde cero."
        )
    except Exception as e:
        print(f"[Error Limpiar Catálogo] {e}")
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** No se pudo limpiar el catálogo: {e}")
        except Exception:
            pass
