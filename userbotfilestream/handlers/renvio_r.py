import asyncio
from telethon import events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

async def procesar_comando_r(event):
    if not event.is_reply:
        await event.edit("Debes responder a un video con el comando /r.")
        await asyncio.sleep(3)
        await event.delete()
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg:
        await event.edit("No se pudo obtener el mensaje al que respondiste.")
        await asyncio.sleep(3)
        await event.delete()
        return

    if not reply_msg.video:
        await event.edit("El mensaje al que respondiste no es un video.")
        await asyncio.sleep(3)
        await event.delete()
        return

    chat = event.chat_id
    
    # Check if replied video is a part or version
    title = reply_msg.message or ""
    import re
    match = re.search(r'(parte|versión|version|verción|vercion)\s*\d+', title, re.IGNORECASE)
    
    videos_to_process = [reply_msg]
    
    if match:
        async for msg in event.client.iter_messages(chat, max_id=reply_msg.id):
            if msg.photo:
                break
            if msg.video or (msg.document and msg.document.mime_type and msg.document.mime_type.startswith('video/')):
                msg_title = msg.message or ""
                if re.search(r'(parte|versión|version|verción|vercion)\s*\d+', msg_title, re.IGNORECASE):
                    videos_to_process.append(msg)
                else:
                    break

    # videos_to_process has newest first, so [reply_msg, older, oldest]. Reverse to get chronological order.
    videos_to_process.reverse()
    
    messages_to_delete = [m.id for m in videos_to_process] + [event.id]
    
    # Buscar si inmediatamente antes del video más antiguo hay un grupo de imágenes
    oldest_video = videos_to_process[0]
    prev_msgs = await event.client.get_messages(chat, limit=10, max_id=oldest_video.id)
    
    album_messages = []
    if prev_msgs and prev_msgs[0].grouped_id and prev_msgs[0].photo:
        target_grouped_id = prev_msgs[0].grouped_id
        for m in prev_msgs:
            if m.grouped_id == target_grouped_id:
                album_messages.append(m)
        
        # Ordenar cronológicamente (por ID)
        album_messages.sort(key=lambda x: x.id)

    # Si hay imágenes arriba, enviarlas primero
    if album_messages:
        await event.client.send_message(chat, file=album_messages)
        messages_to_delete.extend([m.id for m in album_messages])

    # Luego reenviar los videos por separado con su misma descripción
    from telethon.errors import FloodWaitError
    for msg in videos_to_process:
        while True:
            try:
                await event.client.send_message(chat, file=msg.media, message=msg.message, formatting_entities=msg.entities)
                break
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as e:
                print(f"Error reenviando video en /r: {e}")
                break
    
    # Buscar el siguiente video hacia arriba para responderle con un "."
    # Empezamos a buscar por encima del álbum (si lo hubo) o por encima del video más antiguo
    top_msg_id = album_messages[0].id if album_messages else oldest_video.id
    
    async for msg in event.client.iter_messages(chat, max_id=top_msg_id):
        if msg.video or (msg.document and msg.document.mime_type and msg.document.mime_type.startswith('video/')):
            await event.client.send_message(chat, ".", reply_to=msg.id)
            break
            
    # Borrar el comando, los videos originales y las imágenes originales (si las hubo)
    try:
        await event.client.delete_messages(chat, messages_to_delete)
    except Exception:
        pass

