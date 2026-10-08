import asyncio
import time
from telethon import events
from telethon.errors import FloodWaitError
from core.client import client
from utils.helpers import safe_edit_status


async def procesar_comando_album_directo_video(event):
    chat_id = event.chat_id
    
    # Parse scan limit (default None to scan everything)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass
            
    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando videos agrupados en {limit_desc}...")
    
    try:
        messages = []
        last_update = time.time()
        
        # 1. Fetch messages
        async for m in client.iter_messages(chat_id, limit=limit):
            # Only process videos that are grouped (grouped_id is NOT None)
            if m.video and m.grouped_id is not None:
                messages.append(m)
            elif m.document:
                # Check document mime or extensions for videos
                mime = m.document.mime_type or ""
                is_video_doc = False
                if mime.startswith('video/'):
                    is_video_doc = True
                else:
                    file_name = ""
                    for attr in m.document.attributes:
                        if hasattr(attr, 'file_name') and attr.file_name:
                            file_name = attr.file_name
                            break
                    if file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts')):
                        is_video_doc = True
                if is_video_doc and m.grouped_id is not None:
                    messages.append(m)
                
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando mensajes... ({len(messages)} videos agrupados encontrados)")
                last_update = now
                
        if not messages:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron videos agrupados en este rango.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        # 2. Sort chronologically (oldest first)
        messages.sort(key=lambda x: x.id)
        total = len(messages)
        
        await safe_edit_status(status_msg, f"📦 **[Bot Prime]** Encontrados {total} videos agrupados. Iniciando desagrupamiento...")
        await asyncio.sleep(2)
        
        # 3. Re-send each video individually and delete the original
        for idx, msg in enumerate(messages, 1):
            await safe_edit_status(status_msg, f"🎥 **[Bot Prime]** Reenviando video individual {idx} de {total}...")
            
            new_msg = None
            retries = 3
            while retries > 0:
                try:
                    new_msg = await client.send_file(
                        chat_id,
                        file=msg.media,
                        caption=msg.text
                    )
                    break
                except FloodWaitError as e:
                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} seg...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"Error sending individual video: {e}")
                    retries -= 1
                    if retries == 0:
                        raise e
                    await asyncio.sleep(2)
                    
            if new_msg:
                # Delete original
                retries = 3
                while retries > 0:
                    try:
                        await client.delete_messages(chat_id, msg.id)
                        break
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"Error deleting original video message: {e}")
                        retries -= 1
                        if retries == 0:
                            break
                        await asyncio.sleep(2)
                        
            await asyncio.sleep(1.5) # Avoid telegram rate limits
            
        await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Desagrupamiento completado. Se separaron {total} videos con éxito.")
        await asyncio.sleep(8)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass

async def procesar_comando_album_directo_imagenes(event):
    chat_id = event.chat_id
    
    # Parse scan limit (default None to scan everything)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass
            
    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando imágenes agrupadas en {limit_desc}...")
    
    try:
        messages = []
        last_update = time.time()
        
        # 1. Fetch messages
        async for m in client.iter_messages(chat_id, limit=limit):
            # Only process images that are grouped (grouped_id is NOT None)
            if m.photo and m.grouped_id is not None:
                messages.append(m)
            elif m.document:
                # Check document mime or extensions for images
                mime = m.document.mime_type or ""
                is_image_doc = False
                if mime.startswith('image/'):
                    is_image_doc = True
                else:
                    file_name = ""
                    for attr in m.document.attributes:
                        if hasattr(attr, 'file_name') and attr.file_name:
                            file_name = attr.file_name
                            break
                    if file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff')):
                        is_image_doc = True
                if is_image_doc and m.grouped_id is not None:
                    messages.append(m)
                            
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando mensajes... ({len(messages)} imágenes agrupadas encontradas)")
                last_update = now
                
        if not messages:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron imágenes agrupadas en este rango.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        # 2. Sort chronologically (oldest first)
        messages.sort(key=lambda x: x.id)
        total = len(messages)
        
        await safe_edit_status(status_msg, f"📦 **[Bot Prime]** Encontradas {total} imágenes agrupadas. Iniciando desagrupamiento...")
        await asyncio.sleep(2)
        
        # 3. Re-send each image individually and delete the original
        for idx, msg in enumerate(messages, 1):
            await safe_edit_status(status_msg, f"📸 **[Bot Prime]** Reenviando imagen individual {idx} de {total}...")
            
            new_msg = None
            retries = 3
            while retries > 0:
                try:
                    new_msg = await client.send_file(
                        chat_id,
                        file=msg.media,
                        caption=msg.text
                    )
                    break
                except FloodWaitError as e:
                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} seg...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"Error sending individual image: {e}")
                    retries -= 1
                    if retries == 0:
                        raise e
                    await asyncio.sleep(2)
                    
            if new_msg:
                # Delete original
                retries = 3
                while retries > 0:
                    try:
                        await client.delete_messages(chat_id, msg.id)
                        break
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"Error deleting original image message: {e}")
                        retries -= 1
                        if retries == 0:
                            break
                        await asyncio.sleep(2)
                        
            await asyncio.sleep(1.5) # Avoid telegram rate limits
            
        await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Desagrupamiento completado. Se separaron {total} imágenes con éxito.")
        await asyncio.sleep(8)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
