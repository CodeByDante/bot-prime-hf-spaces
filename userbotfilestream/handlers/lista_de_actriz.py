import re
import time
import asyncio
from telethon import events
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

async def procesar_comando_lista_de_actriz(event):
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
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando y contando actrices en {limit_desc}...")
    
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
                
        # Sort chronologically (oldest first)
        messages.sort(key=lambda x: x.id)
        
        # 2. Count videos per actress
        actress_video_counts = {}
        counted_video_ids = set()
        
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
                                # Count this video for all actresses of the image
                                for name in actress_names:
                                    actress_video_counts[name] = actress_video_counts.get(name, 0) + 1
                                counted_video_ids.add(next_msg.id)
                                break
                                
            # Case B: Standalone Video with name
            elif msg.video and msg.id not in counted_video_ids:
                if msg.message and msg.message.strip():
                    actress_names = extract_actress_names(msg.message)
                    for name in actress_names:
                        actress_video_counts[name] = actress_video_counts.get(name, 0) + 1
                        
        if not actress_video_counts:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontró ninguna actriz en los mensajes analizados.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        # 3. Sort alphabetically by name
        sorted_actresses = sorted(actress_video_counts.items(), key=lambda x: x[0])
        
        # 4. Format the list into chunks for Telegram
        lines = []
        for name, count in sorted_actresses:
            lines.append(f"• <code>{name}</code> - {name_to_hashtag(name)} ({count})")
            
        messages_to_send = []
        current_chunk = "🤖 **Lista de Actrices:**\n\n"
        
        for line in lines:
            if len(current_chunk) + len(line) + 2 > 3500:
                messages_to_send.append(current_chunk)
                current_chunk = ""
            current_chunk += line + "\n"
            
        if current_chunk:
            messages_to_send.append(current_chunk)
            
        # Delete the status message
        await status_msg.delete()
        
        # 5. Send chunks
        for chunk in messages_to_send:
            await event.respond(chunk + "\u200b", parse_mode='html', link_preview=False)
            await asyncio.sleep(1)
            
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
