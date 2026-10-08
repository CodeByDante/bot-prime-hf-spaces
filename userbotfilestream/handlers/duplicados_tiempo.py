import time
import html
import asyncio
from telethon import events
from telethon.tl.types import DocumentAttributeVideo
from core.client import client
from utils.helpers import safe_edit_status

def format_duration(seconds):
    if seconds is None:
        return "Desconocido"
    seconds_int = int(seconds)
    hours = seconds_int // 3600
    minutes = (seconds_int % 3600) // 60
    secs = seconds_int % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def format_size(size_bytes):
    if not size_bytes:
        return "0 B"
    size_bytes = int(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def shorten_title(title, max_len=25):
    if not title:
        return ""
    return title[:max_len]

async def procesar_comando_duplicados_tiempo(event):
    chat_id = event.chat_id
    message_text = event.message.message
    parts = message_text.split()
    cmd = parts[0].lower()
    
    # Resolver si es una solicitud de tiempo/duración y extraer el límite
    is_time_dup = False
    limit = None
    
    if "tiempo" in cmd or "tempo" in cmd:
        is_time_dup = True
        if len(parts) > 1:
            try:
                limit = int(parts[1])
            except ValueError:
                pass
    elif len(parts) > 1 and parts[1].lower() in ["tempo", "tiempo"]:
        is_time_dup = True
        if len(parts) > 2:
            try:
                limit = int(parts[2])
            except ValueError:
                pass
                
    if not is_time_dup:
        # Si por alguna razón llegó aquí y no coincide, avisar
        await event.reply(
            "❌ **[Bot Prime]** Formato incorrecto.\n\n"
            "Use `/duplicacion_tiempo [límite]` o `/duplicacion tempo [límite]`."
        )
        return

    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Escaneando videos en busca de duplicados por duración en {limit_desc}...")
    
    try:
        videos = []
        last_update = time.time()
        
        async for m in client.iter_messages(chat_id, limit=limit):
            is_video = False
            file_name = ""
            
            if m.document:
                for attr in m.document.attributes:
                    if isinstance(attr, DocumentAttributeVideo):
                        is_video = True
                    elif hasattr(attr, 'file_name') and attr.file_name:
                        file_name = attr.file_name
                        
                mime = m.document.mime_type or ""
                if mime.startswith('video/') or file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts')):
                    is_video = True
                    
            if is_video:
                duration = None
                for attr in m.document.attributes:
                    if isinstance(attr, DocumentAttributeVideo):
                        duration = attr.duration
                        break
                if not duration and m.file.duration:
                    duration = m.file.duration
                
                size = m.document.size or 0
                file_name = m.file.name or f"video_{m.id}"
                
                # Excluir videos extremadamente cortos (menos de 3 segundos)
                if duration and duration >= 3:
                    videos.append({
                        'msg': m,
                        'name': file_name,
                        'duration': int(duration),
                        'size': size
                    })
                    
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Escaneando videos... ({len(videos)} encontrados)")
                last_update = now

        if not videos:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** No se encontraron videos en {limit_desc}.")
            await asyncio.sleep(5)
            await status_msg.delete()
            try:
                await event.delete()
            except Exception:
                pass
            return

        # Agrupar por duración exacta (en segundos)
        duration_groups = {}
        for v in videos:
            dur = v['duration']
            if dur not in duration_groups:
                duration_groups[dur] = []
            duration_groups[dur].append(v)
            
        duplicate_groups = {dur: group for dur, group in duration_groups.items() if len(group) > 1}
        
        await status_msg.delete()
        
        chat = await event.get_chat()
        channel_id_str = str(chat.id).replace("-100", "")
        is_public = bool(getattr(chat, 'username', None))
        
        if duplicate_groups:
            dup_lines = []
            sorted_durations = sorted(duplicate_groups.keys())
            
            for group_idx, dur in enumerate(sorted_durations, 1):
                group = duplicate_groups[dur]
                # El más antiguo primero
                group.sort(key=lambda x: x['msg'].id)
                
                formatted_duration = format_duration(dur)
                group_lines = []
                group_lines.append(f"<b>Coincidencia {group_idx} - Duración: {formatted_duration}</b>")
                
                for idx, v in enumerate(group, 1):
                    msg = v['msg']
                    formatted_size = format_size(v['size'])
                    short_name = shorten_title(v['name'])
                    escaped_name = html.escape(short_name)
                    
                    if is_public:
                        link = f"https://t.me/{chat.username}/{msg.id}"
                    else:
                        link = f"https://t.me/c/{channel_id_str}/{msg.id}"
                        
                    if idx == 1:
                        group_lines.append(f"  ├─ 1. [Original] <a href=\"{link}\">{escaped_name}</a> <code>({formatted_size})</code>")
                    else:
                        group_lines.append(
                            f"  ├─ {idx}. [Copia] <a href=\"{link}\">{escaped_name}</a> <code>({formatted_size})</code>\n"
                            f"  │   └─ Eliminar copia: <code>/eliminar_copia_{msg.id}</code>"
                        )
                dup_lines.append("\n".join(group_lines))

            # Segmentar los reportes para cumplir los límites de Telegram
            dup_chunks = []
            curr_chunk = f"⚠️ **Videos duplicados por duración encontrados ({limit_desc}):**\n\n"
            
            for block in dup_lines:
                if len(curr_chunk) + len(block) + 4 > 3500:
                    dup_chunks.append(curr_chunk)
                    curr_chunk = ""
                curr_chunk += block + "\n\n"
                
            if curr_chunk:
                dup_chunks.append(curr_chunk.strip())
                
            for chunk in dup_chunks[:-1]:
                await event.respond(chunk + "\u200b", parse_mode='html', link_preview=False)
                await asyncio.sleep(1)
                
            last_chunk = dup_chunks[-1]
            text_with_clean_link = (
                last_chunk + 
                f"\n\n🧹 **Para limpiar este reporte:** <code>/limpiar</code>\n"
                f"🗑️ **Para eliminar las copias conservando el de mayor tamaño/calidad:**\n"
                f"<code>/elimina_duplicados_tiempo {limit or ''}</code>"
            )
            await event.respond(text_with_clean_link + "\u200b", parse_mode='html', link_preview=False)
            
        else:
            text_no_duplicates = (
                f"✅ **No se encontraron videos duplicados por duración en {limit_desc}.**\n\n"
                "🧹 **Para limpiar este reporte:** <code>/limpiar</code>"
            )
            await event.respond(text_no_duplicates + "\u200b", parse_mode='html', link_preview=False)
            
    except Exception as e:
        try:
            await event.respond(f"❌ **[Bot Prime]** Error al buscar duplicados por duración: {e}")
        except Exception:
            pass

async def procesar_comando_elimina_duplicados_tiempo(event):
    chat_id = event.chat_id
    message_text = event.message.message
    parts = message_text.split()
    
    limit = None
    if len(parts) > 1:
        try:
            limit = int(parts[1])
        except ValueError:
            pass
            
    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"🗑️ **[Bot Prime]** Escaneando y eliminando duplicados por duración en {limit_desc}...")
    
    try:
        videos = []
        last_update = time.time()
        
        async for m in client.iter_messages(chat_id, limit=limit):
            is_video = False
            file_name = ""
            
            if m.document:
                for attr in m.document.attributes:
                    if isinstance(attr, DocumentAttributeVideo):
                        is_video = True
                    elif hasattr(attr, 'file_name') and attr.file_name:
                        file_name = attr.file_name
                        
                mime = m.document.mime_type or ""
                if mime.startswith('video/') or file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts')):
                    is_video = True
                    
            if is_video:
                duration = None
                for attr in m.document.attributes:
                    if isinstance(attr, DocumentAttributeVideo):
                        duration = attr.duration
                        break
                if not duration and m.file.duration:
                    duration = m.file.duration
                
                size = m.document.size or 0
                file_name = m.file.name or f"video_{m.id}"
                
                if duration and duration >= 3:
                    videos.append({
                        'msg': m,
                        'name': file_name,
                        'duration': int(duration),
                        'size': size
                    })
                    
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🗑️ **[Bot Prime]** Escaneando videos... ({len(videos)} encontrados)")
                last_update = now

        if not videos:
            await safe_edit_status(status_msg, f"✅ **[Bot Prime]** No se encontraron videos para eliminar en {limit_desc}.")
            await asyncio.sleep(5)
            await status_msg.delete()
            try:
                await event.delete()
            except Exception:
                pass
            return

        # Agrupar por duración
        duration_groups = {}
        for v in videos:
            dur = v['duration']
            if dur not in duration_groups:
                duration_groups[dur] = []
            duration_groups[dur].append(v)
            
        duplicate_groups = {dur: group for dur, group in duration_groups.items() if len(group) > 1}
        
        if not duplicate_groups:
            await safe_edit_status(status_msg, f"✅ **[Bot Prime]** No se encontraron videos duplicados por duración para eliminar.")
            await asyncio.sleep(6)
            await status_msg.delete()
            try:
                await event.delete()
            except Exception:
                pass
            return
            
        ids_to_delete = []
        details_deleted = []
        
        for dur, group in duplicate_groups.items():
            # Ordenar por tamaño descendente (el más pesado / mejor calidad se conserva)
            # A igual tamaño, conserva el ID más antiguo (orden ascendente de ID)
            group.sort(key=lambda x: (-x['size'], x['msg'].id))
            
            conserved = group[0]
            for item in group[1:]:
                ids_to_delete.append(item['msg'].id)
                details_deleted.append(f"• `{item['name']}` ({format_size(item['size'])}) -> Conservado: `{conserved['name']}` ({format_size(conserved['size'])})")

        if ids_to_delete:
            await safe_edit_status(status_msg, f"🗑️ **[Bot Prime]** Eliminando {len(ids_to_delete)} videos duplicados de menor tamaño...")
            await client.delete_messages(chat_id, ids_to_delete)
            
            summary = f"✅ **[Bot Prime]** Se eliminaron {len(ids_to_delete)} copias duplicadas por duración:\n\n" + "\n".join(details_deleted[:40])
            if len(details_deleted) > 40:
                summary += f"\n... y {len(details_deleted) - 40} videos más."
            await safe_edit_status(status_msg, summary)
        else:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se eliminó ningún video.")
            
        await asyncio.sleep(15)
        await status_msg.delete()
        try:
            await event.delete()
        except Exception:
            pass
            
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error al eliminar: {e}")
            await asyncio.sleep(10)
            await status_msg.delete()
        except Exception:
            pass
