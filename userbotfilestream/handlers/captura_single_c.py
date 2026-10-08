import os
import cv2
import asyncio
from telethon.tl.types import DocumentAttributeVideo
from telethon.errors import FloodWaitError
from core.client import client
import core.proxy as proxy
from utils.image import capture_frames_from_stream
from utils.helpers import safe_edit_status, calculate_distribution
from handlers.capturas import is_video_message, OUTPUT_DIR

async def procesar_comando_c(event):
    chat_id = event.chat_id
    
    if not event.is_reply:
        await event.edit("❌ Debes responder a un video válido.")
        await asyncio.sleep(3)
        await event.delete()
        return
        
    reply_msg = await event.get_reply_message()
    if not reply_msg or not is_video_message(reply_msg):
        await event.edit("❌ Debes responder a un video válido.")
        await asyncio.sleep(3)
        await event.delete()
        return

    status_msg = await event.reply("⚙️ **[Bot Prime]** Analizando grupo de videos...")
    
    try:
        proxy.active_client = client
        proxy_runner = await proxy.start_proxy_server(port=8080)
        
        # Extract title of the replied video
        title = reply_msg.message or ""
        import re
        match = re.search(r'(parte|versión|version|verción|vercion)\s*\d+', title, re.IGNORECASE)
        
        videos_to_process = [reply_msg]
        
        if match:
            # It's a part/version. Collect older videos that are also parts/versions.
            async for msg in client.iter_messages(chat_id, max_id=reply_msg.id):
                if msg.photo:
                    break
                if is_video_message(msg):
                    msg_title = msg.message or ""
                    if re.search(r'(parte|versión|version|verción|vercion)\s*\d+', msg_title, re.IGNORECASE):
                        videos_to_process.append(msg)
                    else:
                        break
                        
        videos_to_process.reverse()
        
        if len(videos_to_process) > 1:
            await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Capturando 4 fotogramas repartidos en {len(videos_to_process)} videos...")
            
        for msg in videos_to_process:
            v_doc = msg.video or msg.document
            proxy.active_documents[v_doc.id] = v_doc
            
        distribution = list(reversed(calculate_distribution(len(videos_to_process), total_screenshots=4)))
        
        saved_files = []
        semaphore = asyncio.Semaphore(3)
        
        async def extract_from_video(idx, msg):
            count = distribution[idx]
            if count == 0:
                return []
                
            v_doc = msg.video or msg.document
            duration = 0
            for attr in v_doc.attributes:
                if isinstance(attr, DocumentAttributeVideo):
                    duration = attr.duration
                    break
            if duration == 0:
                duration = 300
                
            timestamps = [(j + 0.5) * (duration / count) for j in range(count)]
            
            loop = asyncio.get_event_loop()
            stream_url = f"http://127.0.0.1:8080/stream?id={v_doc.id}"
            
            async with semaphore:
                capturas = await loop.run_in_executor(
                    None,
                    capture_frames_from_stream,
                    stream_url,
                    timestamps
                )
                
            episode_files = []
            for f_idx, (ts, frame) in enumerate(capturas):
                img_name = f"captura_single_{reply_msg.id}_{idx}_{f_idx}.jpg"
                full_path = os.path.join(OUTPUT_DIR, img_name)
                cv2.imwrite(full_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                episode_files.append((idx * 10 + f_idx, full_path))
            return episode_files

        tasks = [extract_from_video(idx, msg) for idx, msg in enumerate(videos_to_process)]
        results = await asyncio.gather(*tasks)
        
        for msg in videos_to_process:
            v_doc = msg.video or msg.document
            proxy.active_documents.pop(v_doc.id, None)
            
        saved_files_with_idx = []
        for res in results:
            saved_files_with_idx.extend(res)
        saved_files_with_idx.sort(key=lambda x: x[0])
        saved_files = [path for _, path in saved_files_with_idx]
        
        if saved_files:
            # Send album
            await client.send_file(chat_id, saved_files)
            
            # Send videos
            from telethon.errors import FloodWaitError
            for msg in videos_to_process:
                while True:
                    try:
                        await client.send_file(chat_id, file=msg.media, message=msg.message, formatting_entities=msg.entities)
                        break
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"Error reenviando video: {e}")
                        break
                        
            # Delete old videos and command
            msgs_to_delete = [m.id for m in videos_to_process] + [event.id, status_msg.id]
            try:
                await client.delete_messages(chat_id, msgs_to_delete)
            except Exception:
                pass
                
            # Reply dot to next video
            next_video = None
            async for msg in client.iter_messages(chat_id, max_id=videos_to_process[0].id):
                if is_video_message(msg):
                    next_video = msg
                    break
            if next_video:
                await client.send_message(chat_id, ".", reply_to=next_video.id)
                
            # Cleanup
            for f in saved_files:
                try:
                    os.remove(f)
                except:
                    pass
        else:
            await safe_edit_status(status_msg, "❌ No se pudieron tomar capturas.")
            await asyncio.sleep(3)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            
    except Exception as e:
        print(f"Error in single capture: {e}")
        await safe_edit_status(status_msg, f"❌ Error: {e}")
        await asyncio.sleep(3)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    return
