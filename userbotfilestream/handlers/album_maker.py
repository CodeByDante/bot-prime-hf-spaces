import asyncio
import time
from telethon import events
from telethon.errors import FloodWaitError
from core.client import client
from utils.helpers import safe_edit_status


async def procesar_comando_album_maker_video(event):
    chat_id = event.chat_id
    
    # Parse scan limit (default None to scan everything)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass
            
    reply_to_msg_id = event.reply_to_msg_id
    
    if reply_to_msg_id:
        status_msg = await event.reply("🔍 **[Bot Prime]** Buscando videos desde el mensaje seleccionado...")
    elif limit is not None:
        status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando videos en los últimos {limit} mensajes...")
    else:
        status_msg = await event.reply("🔍 **[Bot Prime]** Buscando todos los videos del canal...")
    
    try:
        messages = []
        last_update = time.time()
        
        # 1. Fetch messages
        if reply_to_msg_id:
            scan_limit = limit if len(args) > 1 else None
            msg_generator = client.iter_messages(chat_id, min_id=reply_to_msg_id - 1, reverse=True, limit=scan_limit)
        else:
            msg_generator = client.iter_messages(chat_id, limit=limit)
            
        from telethon.tl.types import MessageMediaDocument
        async for m in msg_generator:
            # Only process real media documents (excludes webpage previews, etc.)
            if isinstance(m.media, MessageMediaDocument):
                if m.video:
                    messages.append(m)
                elif m.document:
                    # Check document mime or extensions for videos
                    mime = m.document.mime_type or ""
                    if mime.startswith('video/'):
                        messages.append(m)
                    else:
                        file_name = ""
                        for attr in m.document.attributes:
                            if hasattr(attr, 'file_name') and attr.file_name:
                                file_name = attr.file_name
                                break
                        if file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts')):
                            messages.append(m)
                
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando mensajes... ({len(messages)} videos encontrados)")
                last_update = now
                
        if not messages:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron videos en este rango.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        # 2. Sort chronologically (oldest first)
        messages.sort(key=lambda x: x.id)
        
        # 3. Split into groups of up to 10
        chunks = [messages[i:i + 10] for i in range(0, len(messages), 10)]
        total_chunks = len(chunks)
        
        await safe_edit_status(status_msg, f"📦 **[Bot Prime]** Encontrados {len(messages)} videos. Creando {total_chunks} álbumes de video...")
        await asyncio.sleep(2)
        
        for idx, chunk in enumerate(chunks, 1):
            await safe_edit_status(status_msg, f"🎥 **[Bot Prime]** Enviando álbum de videos {idx} de {total_chunks}...")
            
            new_msgs = None
            retries = 3
            while retries > 0:
                try:
                    new_msgs = await client.send_file(
                        chat_id,
                        file=[m.media for m in chunk],
                        caption=[(m.text or "") for m in chunk]
                    )
                    break
                except FloodWaitError as e:
                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} seg...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"Error sending video album chunk: {e}")
                    retries -= 1
                    if retries == 0:
                        raise e
                    await asyncio.sleep(2)
                    
            if new_msgs:
                # Delete originals
                old_ids = [m.id for m in chunk]
                retries = 3
                while retries > 0:
                    try:
                        await client.delete_messages(chat_id, old_ids)
                        break
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"Error deleting original messages: {e}")
                        retries -= 1
                        if retries == 0:
                            break
                        await asyncio.sleep(2)
                        
            await asyncio.sleep(2.0) # Avoid telegram rate limits
            
        await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Álbumes creados con éxito. Se agruparon {len(messages)} videos en {total_chunks} álbumes.")
        await asyncio.sleep(8)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass

async def procesar_comando_album_maker_imagenes(event):
    chat_id = event.chat_id
    
    # Parse scan limit (default None to scan everything)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass
            
    reply_to_msg_id = event.reply_to_msg_id
    
    if reply_to_msg_id:
        status_msg = await event.reply("🔍 **[Bot Prime]** Buscando imágenes desde el mensaje seleccionado...")
    elif limit is not None:
        status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando imágenes en los últimos {limit} mensajes...")
    else:
        status_msg = await event.reply("🔍 **[Bot Prime]** Buscando todas las imágenes del canal...")
    
    try:
        messages = []
        last_update = time.time()
        
        # 1. Fetch messages
        if reply_to_msg_id:
            scan_limit = limit if len(args) > 1 else None
            msg_generator = client.iter_messages(chat_id, min_id=reply_to_msg_id - 1, reverse=True, limit=scan_limit)
        else:
            msg_generator = client.iter_messages(chat_id, limit=limit)
            
        from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
        async for m in msg_generator:
            # Only process real media (excludes webpage previews, etc.)
            if isinstance(m.media, MessageMediaPhoto):
                messages.append(m)
            elif isinstance(m.media, MessageMediaDocument):
                # Check document mime or extensions for images
                mime = m.document.mime_type or ""
                if mime.startswith('image/'):
                    messages.append(m)
                else:
                    file_name = ""
                    for attr in m.document.attributes:
                        if hasattr(attr, 'file_name') and attr.file_name:
                            file_name = attr.file_name
                            break
                    if file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff')):
                        messages.append(m)
                            
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando mensajes... ({len(messages)} imágenes encontradas)")
                last_update = now
                
        if not messages:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron imágenes en este rango.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        # 2. Sort chronologically (oldest first)
        messages.sort(key=lambda x: x.id)
        
        # 3. Split into groups of up to 10
        chunks = [messages[i:i + 10] for i in range(0, len(messages), 10)]
        total_chunks = len(chunks)
        
        await safe_edit_status(status_msg, f"📦 **[Bot Prime]** Encontradas {len(messages)} imágenes. Creando {total_chunks} álbumes de imágenes...")
        await asyncio.sleep(2)
        
        for idx, chunk in enumerate(chunks, 1):
            await safe_edit_status(status_msg, f"📸 **[Bot Prime]** Enviando álbum de imágenes {idx} de {total_chunks}...")
            
            new_msgs = None
            retries = 3
            while retries > 0:
                try:
                    new_msgs = await client.send_file(
                        chat_id,
                        file=[m.media for m in chunk],
                        caption=[(m.text or "") for m in chunk]
                    )
                    break
                except FloodWaitError as e:
                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} seg...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"Error sending image album chunk: {e}")
                    retries -= 1
                    if retries == 0:
                        raise e
                    await asyncio.sleep(2)
                    
            if new_msgs:
                # Delete originals
                old_ids = [m.id for m in chunk]
                retries = 3
                while retries > 0:
                    try:
                        await client.delete_messages(chat_id, old_ids)
                        break
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"Error deleting original messages: {e}")
                        retries -= 1
                        if retries == 0:
                            break
                        await asyncio.sleep(2)
                        
            await asyncio.sleep(2.0) # Avoid telegram rate limits
            
        await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Álbumes creados con éxito. Se agruparon {len(messages)} imágenes en {total_chunks} álbumes.")
        await asyncio.sleep(8)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass

async def procesar_comando_album_maker(event):
    chat_id = event.chat_id
    
    # Parse scan limit (default None to scan everything)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass
            
    reply_to_msg_id = event.reply_to_msg_id
    
    if reply_to_msg_id:
        status_msg = await event.reply("🔍 **[Bot Prime]** Buscando imágenes y videos desde el mensaje seleccionado...")
    elif limit is not None:
        status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando imágenes y videos en los últimos {limit} mensajes...")
    else:
        status_msg = await event.reply("🔍 **[Bot Prime]** Buscando todas las imágenes y videos del canal...")
        
    try:
        messages = []
        last_update = time.time()
        
        # 1. Fetch messages
        if reply_to_msg_id:
            scan_limit = limit if len(args) > 1 else None
            msg_generator = client.iter_messages(chat_id, min_id=reply_to_msg_id - 1, reverse=True, limit=scan_limit)
        else:
            msg_generator = client.iter_messages(chat_id, limit=limit)
            
        from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
        async for m in msg_generator:
            # Match either photo or video document
            is_valid_media = False
            if isinstance(m.media, MessageMediaPhoto):
                is_valid_media = True
            elif isinstance(m.media, MessageMediaDocument):
                # Check document mime or attributes for video or image
                mime = m.document.mime_type or ""
                if mime.startswith(('video/', 'image/')):
                    is_valid_media = True
                else:
                    file_name = ""
                    for attr in m.document.attributes:
                        if hasattr(attr, 'file_name') and attr.file_name:
                            file_name = attr.file_name
                            break
                    if file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff')):
                        is_valid_media = True
            
            if is_valid_media:
                messages.append(m)
                
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando mensajes... ({len(messages)} archivos encontrados)")
                last_update = now
                
        if not messages:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron imágenes ni videos en este rango.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        # 2. Sort chronologically (oldest first)
        messages.sort(key=lambda x: x.id)
        
        # 3. Split into groups of up to 10
        chunks = [messages[i:i + 10] for i in range(0, len(messages), 10)]
        total_chunks = len(chunks)
        
        await safe_edit_status(status_msg, f"📦 **[Bot Prime]** Encontrados {len(messages)} archivos de medios. Creando {total_chunks} álbumes mixtos...")
        await asyncio.sleep(2)
        
        for idx, chunk in enumerate(chunks, 1):
            await safe_edit_status(status_msg, f"📸🎥 **[Bot Prime]** Enviando álbum mixto {idx} de {total_chunks}...")
            
            new_msgs = None
            retries = 3
            while retries > 0:
                try:
                    new_msgs = await client.send_file(
                        chat_id,
                        file=[m.media for m in chunk],
                        caption=[(m.text or "") for m in chunk]
                    )
                    break
                except FloodWaitError as e:
                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} seg...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"Error sending mixed album chunk: {e}")
                    retries -= 1
                    if retries == 0:
                        raise e
                    await asyncio.sleep(2)
                    
            if new_msgs:
                # Delete originals
                old_ids = [m.id for m in chunk]
                retries = 3
                while retries > 0:
                    try:
                        await client.delete_messages(chat_id, old_ids)
                        break
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"Error deleting original messages: {e}")
                        retries -= 1
                        if retries == 0:
                            break
                        await asyncio.sleep(2)
                        
            await asyncio.sleep(2.0) # Avoid telegram rate limits
            
        await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Álbumes mixtos creados con éxito. Se agruparon {len(messages)} archivos en {total_chunks} álbumes.")
        await asyncio.sleep(8)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
