import re
import time
import asyncio
from telethon import events
from telethon.errors import FloodWaitError
from core.client import client
from utils.helpers import safe_edit_status


# Keywords that commonly start description fields to avoid false positive actress names
EXCLUDED_KEYWORDS = {
    'titulo', 'título', 'sinopsis', 'duracion', 'duración', 'resolucion', 
    'resolución', 'peso', 'canal', 'grupo', 'parte', 'part', 'capitulo', 
    'capítulo', 'episodio', 'genero', 'género', 'tags', 'enlace', 'link'
}

def name_to_hashtag(name):
    # Replace spaces and hyphens with underscores
    tag = re.sub(r'[\s\-]+', '_', name)
    # Remove characters that are not allowed in Telegram hashtags (keep letters, numbers, underscores)
    tag = re.sub(r'[^\w_]', '', tag)
    return f"#{tag}"

def extract_actress_names(caption):
    if not caption:
        return []
    
    names = []
    for line in caption.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Check if line starts with an excluded keyword followed by a colon
        has_excluded_keyword = False
        for keyword in EXCLUDED_KEYWORDS:
            if re.match(rf'^\b{keyword}\b\s*:', line, re.IGNORECASE):
                has_excluded_keyword = True
                break
        if has_excluded_keyword:
            continue
            
        # 1. Search for explicit "actriz:" or "actress:" prefix
        match = re.search(r'\bactri[zs]:\s*([^-\n#]+)', line, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name and name not in names:
                names.append(name)
            continue
            
        # 2. No prefix: split on separators and clean up
        clean = line.split('-')[0].split('#')[0].strip()
        clean = re.sub(r'[\r\n]+', ' ', clean).strip()
        
        # If the remaining clean string is short, treat it as the actress name
        if clean and len(clean) < 40:
            if clean.lower() in EXCLUDED_KEYWORDS:
                continue
            if clean not in names:
                names.append(clean)
                
    return names

async def procesar_comando_etiquetado_actriz(event):
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
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Analizando etiquetado de actrices en {limit_desc}...")
    
    try:
        messages = []
        last_update = time.time()
        
        # 1. Fetch messages
        async for m in client.iter_messages(chat_id, limit=limit):
            messages.append(m)
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando mensajes... ({len(messages)} leídos)")
                last_update = now
                
        # 2. Sort chronologically (oldest first) so "below" means index + 1
        messages.sort(key=lambda x: x.id)
        
        edited_video_ids = set()
        count_case_a = 0
        count_case_b = 0
        
        # 3. Process messages
        for idx, msg in enumerate(messages):
            # Case A: Image followed by a video
            if msg.photo and msg.message and msg.message.strip():
                actress_names = extract_actress_names(msg.message)
                if actress_names:
                    # Look ahead up to 3 messages to find a video without description
                    for next_idx in range(idx + 1, min(idx + 4, len(messages))):
                        next_msg = messages[next_idx]
                        if next_msg.video:
                            has_desc = bool(next_msg.message and next_msg.message.strip())
                            if not has_desc:
                                # Found the video! Update caption
                                formatted_caption = "\n".join(f"actriz: {name} - {name_to_hashtag(name)}" for name in actress_names)
                                try:
                                    await client.edit_message(chat_id, next_msg.id, text=formatted_caption)
                                    edited_video_ids.add(next_msg.id)
                                    count_case_a += 1
                                    await asyncio.sleep(1.0)  # Avoid rate limit
                                except FloodWaitError as e:
                                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} seg...")
                                    await asyncio.sleep(e.seconds)
                                    await client.edit_message(chat_id, next_msg.id, text=formatted_caption)
                                    edited_video_ids.add(next_msg.id)
                                    count_case_a += 1
                                except Exception as e:
                                    print(f"Error editing message {next_msg.id}: {e}")
                                break  # Stop looking for videos for this image
                                
            # Case B: Standalone Video with name but no prefix (or not fully matching the format)
            elif msg.video and msg.id not in edited_video_ids:
                if msg.message and msg.message.strip():
                    caption = msg.message.strip()
                    
                    actress_names = extract_actress_names(caption)
                    if actress_names:
                        formatted_caption = "\n".join(f"actriz: {name} - {name_to_hashtag(name)}" for name in actress_names)
                        # If the caption is already exactly in the formatted state, skip
                        if caption == formatted_caption:
                            continue
                            
                        try:
                            await client.edit_message(chat_id, msg.id, text=formatted_caption)
                            count_case_b += 1
                            await asyncio.sleep(1.0)
                        except FloodWaitError as e:
                            await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} seg...")
                            await asyncio.sleep(e.seconds)
                            await client.edit_message(chat_id, msg.id, text=formatted_caption)
                            count_case_b += 1
                        except Exception as e:
                            print(f"Error editing video {msg.id}: {e}")
                            
        # 4. Summary report
        total_edits = count_case_a + count_case_b
        if total_edits > 0:
            await safe_edit_status(status_msg, 
                f"✅ **[Bot Prime]** Proceso completado:\n"
                f"• Imagen + Video (Caso A): {count_case_a} videos actualizados\n"
                f"• Video propio (Caso B): {count_case_b} videos actualizados"
            )
        else:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron videos que requirieran etiquetado de actriz.")
            
        await asyncio.sleep(8)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
