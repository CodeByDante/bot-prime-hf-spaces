import asyncio
from telethon import events

async def procesar_comando_p(event):
    if not event.is_reply:
        await event.edit("Debes responder a un video con el comando /p.")
        await asyncio.sleep(3)
        await event.delete()
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg:
        await event.edit("No se pudo obtener el mensaje al que respondiste.")
        await asyncio.sleep(3)
        await event.delete()
        return

    chat = event.chat_id
    
    # Check if the initial message is a video
    if not reply_msg.video:
        await event.edit("El mensaje al que respondiste no es un video.")
        await asyncio.sleep(3)
        await event.delete()
        return

    # Delete the command immediately
    try:
        await event.delete()
    except Exception:
        pass
    
    # Collect all videos starting from the replied message going upwards
    videos_to_edit = [reply_msg]
    next_video = None
    
    state = 0
    # max_id gives messages older than that ID
    async for msg in event.client.iter_messages(chat, max_id=reply_msg.id):
        if state == 0:
            if msg.photo:
                state = 1
                continue
            if msg.video:
                videos_to_edit.append(msg)
                
        if state == 1:
            if msg.video:
                next_video = msg
                break
            
    # Now we have videos from bottom to top. 
    # Reverse them so we can number them from top to bottom
    videos_to_edit.reverse()
    
    # Edit them all
    part_count = 1
    for video_msg in videos_to_edit:
        new_caption = f"Parte {part_count}"
                
        try:
            await event.client.edit_message(chat, video_msg.id, new_caption)
        except Exception as e:
            print(f"Error editing message {video_msg.id}: {e}")
            
        part_count += 1
        
    if next_video:
        await event.client.send_message(chat, ".", reply_to=next_video.id)
