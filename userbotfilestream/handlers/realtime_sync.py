import time
import asyncio
import re
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from telethon import events
from core.client import client
from utils.database import DB
from utils.helpers import get_message_title
from handlers.prime_video import (
    is_video_message,
    get_video_info,
    format_duration,
    format_size,
    get_web_url,
    get_stream_link_for_video
)

@client.on(events.NewMessage)
async def handle_realtime_new_video(event):
    # Ignorar chats privados (como el chat con @BrodyFileStreamBot)
    if event.is_private:
        return
        
    chat_id = str(event.chat_id)
    try:
        active_channels = await DB.get_active_channels()
    except Exception as e:
        print(f"[Realtime Sync Error] No se pudieron obtener los canales activos: {e}")
        return
        
    # Verificar si es un canal indexado
    if chat_id not in active_channels:
        alt_chat_id = chat_id.replace("-100", "") if chat_id.startswith("-100") else f"-100{chat_id}"
        if alt_chat_id in active_channels:
            chat_id = alt_chat_id
        else:
            return
            
    # Validar si el mensaje entrante es de tipo video
    if not is_video_message(event.message):
        return
        
    print(f"[Realtime Sync] 📥 Detectado nuevo video en canal indexado {chat_id} (Msg ID: {event.id})")
    
    try:
        chat = await event.get_chat()
        title = get_message_title(event.message)
        if not title or not title.strip():
            title = f"Video #{event.id}"
            
        v_duration, v_size = get_video_info(event.message)
        dur_str = format_duration(v_duration)
        sz_str = format_size(v_size)
        
        is_public = bool(getattr(chat, 'username', None))
        channel_id_str = chat_id.replace("-100", "")
        link = f"https://t.me/{chat.username}/{event.id}" if is_public else f"https://t.me/c/{channel_id_str}/{event.id}"
        
        # Generar enlace de streaming a través del bot de Go (BrodyFileStreamBot)
        stream_link = await get_stream_link_for_video(event.message)
        
        # Descargar la miniatura de forma nativa a disco en tiempo real
        thumb_dir = os.path.join(BASE_DIR, "static", "thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, f"{chat_id}_{event.id}.jpg")
        if not os.path.exists(thumb_path):
            try:
                await client.download_media(event.message, file=thumb_path, thumb=-1)
            except Exception as th_err:
                print(f"[Realtime Sync Warning] No se pudo obtener miniatura para msg {event.id}: {th_err}")
                
        if stream_link:
            video_data = {
                "id": event.id,
                "title": title,
                "link": link,
                "duration": dur_str,
                "size": sz_str,
                "stream_url": stream_link,
                "indexed_at": int(time.time())
            }
            await DB.add_video(
                chat_id,
                video_data,
                channel_title=getattr(chat, 'title', 'Canal'),
                username=getattr(chat, 'username', None)
            )
            print(f"[Realtime Sync] ✅ Video {event.id} indexado y añadido al catálogo del canal {chat_id}")
        else:
            print(f"[Realtime Sync] ❌ No se pudo obtener enlace de stream para el video {event.id}")
            
    except Exception as e:
        print(f"[Realtime Sync Error] Error procesando nuevo mensaje: {e}")

@client.on(events.MessageDeleted)
async def handle_realtime_deleted_video(event):
    chat_id = None
    if event.chat_id:
        chat_id = str(event.chat_id)
    elif hasattr(event, 'original_update') and hasattr(event.original_update, 'channel_id'):
        chat_id = f"-100{event.original_update.channel_id}"
        
    if not chat_id:
        return
        
    try:
        active_channels = await DB.get_active_channels()
    except Exception as e:
        print(f"[Realtime Sync Error] No se pudieron obtener los canales activos: {e}")
        return
        
    if chat_id not in active_channels:
        alt_chat_id = chat_id.replace("-100", "") if chat_id.startswith("-100") else f"-100{chat_id}"
        if alt_chat_id in active_channels:
            chat_id = alt_chat_id
        else:
            return
            
    deleted_ids = event.deleted_ids
    if not deleted_ids:
        return
        
    print(f"[Realtime Sync] 🗑 Detectada eliminación de mensajes {deleted_ids} en el canal {chat_id}")
    
    try:
        removed = await DB.remove_videos(chat_id, deleted_ids)
        if removed:
            print(f"[Realtime Sync] ✅ Se eliminaron los videos {deleted_ids} del catálogo del canal {chat_id}")
    except Exception as e:
        print(f"[Realtime Sync Error] Error al eliminar videos de la base de datos: {e}")
