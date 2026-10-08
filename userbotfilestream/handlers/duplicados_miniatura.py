import os
import re
import cv2
import html
import time
import asyncio
from telethon import events
from telethon.tl.types import DocumentAttributeVideo
from telethon.errors import FloodWaitError
from core.client import client
from utils.helpers import safe_edit_status, get_message_title

def shorten_title(title, max_len=20):
    if not title:
        return ""
    return title[:max_len]

# Carpeta temporal para guardar las miniaturas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(BASE_DIR, "capturas")
os.makedirs(TEMP_DIR, exist_ok=True)

def calcular_hash_imagen(image_path):
    """
    Calcula el hash promedio (aHash) de una imagen usando OpenCV,
    recortando los márgenes para eliminar marcas de agua y logos.
    """
    try:
        # Cargar en escala de grises
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
            
        # Evitar imágenes lisas / pantallas en negro
        if img.std() < 3.0:
            return None
            
        # Recortar márgenes (eliminar marcas de agua y bordes)
        # Mantener del 15% al 80% de la altura, y del 5% al 95% de la anchura
        h, w = img.shape
        y1, y2 = int(h * 0.15), int(h * 0.80)
        x1, x2 = int(w * 0.05), int(w * 0.95)
        img_cropped = img[y1:y2, x1:x2]
        
        if img_cropped.size == 0:
            img_cropped = img
            
        # Redimensionar a 8x8 píxeles
        resized = cv2.resize(img_cropped, (8, 8), interpolation=cv2.INTER_AREA)
        
        # Calcular el valor promedio
        avg = resized.mean()
        
        # Construir el hash binario comparando cada píxel con la media
        hash_bits = "".join(['1' if val > avg else '0' for val in resized.flatten()])
        return int(hash_bits, 2)
    except Exception as e:
        print(f"[Hash Error] No se pudo calcular el hash de {image_path}: {e}")
        return None

def format_duration(seconds):
    if not seconds:
        return "00:00"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
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

async def escanear_y_calcular_hashes(chat_id, status_msg, limit):
    """
    Escanea los mensajes y calcula los hashes de miniaturas.
    """
    all_messages = []
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
            all_messages.append(m)
            
        now = time.time()
        if now - last_update > 4.0:
            await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Buscando videos... ({len(all_messages)} encontrados)")
            last_update = now

    if not all_messages:
        return []

    await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Analizando visualmente {len(all_messages)} videos...")
    last_update = time.time()
    
    sem = asyncio.Semaphore(3)  # Límite de 3 descargas simultáneas (más confiable para Telethon)
    processed_count = 0
    
    async def procesar_video_individual(m):
        nonlocal processed_count, last_update
        duration = 0
        for attr in m.document.attributes:
            if isinstance(attr, DocumentAttributeVideo):
                duration = attr.duration
                break
        if not duration and m.file.duration:
            duration = m.file.duration
            
        size = m.document.size or 0
        file_name = m.file.name or f"video_{m.id}"
        
        hash_val = None
        has_thumb = bool(getattr(m.document, 'thumbs', []))
        
        if has_thumb:
            temp_filename = f"thumb_temp_{m.id}.jpg"
            temp_path = os.path.join(TEMP_DIR, temp_filename)
            
            async with sem:
                try:
                    path = await client.download_media(m, file=temp_path, thumb=-1)
                    if path and os.path.exists(path):
                        loop = asyncio.get_event_loop()
                        hash_val = await loop.run_in_executor(None, calcular_hash_imagen, path)
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"Error descargando miniatura para ID {m.id}: {e}")
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass

        processed_count += 1
        now = time.time()
        if now - last_update > 4.0:
            await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Analizando miniaturas... ({processed_count}/{len(all_messages)} procesados)")
            last_update = now
            
        return {
            'msg': m,
            'name': file_name,
            'duration': duration,
            'size': size,
            'hash': hash_val
        }

    tasks = [procesar_video_individual(m) for m in all_messages]
    analyzed_videos = await asyncio.gather(*tasks)
    return analyzed_videos

def es_grupo_especial(group):
    """
    Un grupo es especial si existe al menos un par de videos en donde
    uno de ellos es más largo (> 20 segundos) pero pesa menos que otro.
    """
    n = len(group)
    for i in range(n):
        for j in range(i + 1, n):
            v1 = group[i]
            v2 = group[j]
            if abs(v1['duration'] - v2['duration']) > 20:
                # Caso especial: el más largo pesa menos que el más corto
                if (v1['duration'] > v2['duration'] and v1['size'] < v2['size']) or \
                   (v2['duration'] > v1['duration'] and v2['size'] < v1['size']):
                    return True
    return False
 
def agrupar_duplicados_miniatura(analyzed_videos):
    """
    1. Agrupa los videos por similitud visual de miniaturas (distancia Hamming <= 4)
       y que además tengan una duración similar (<= 20s de diferencia) o que correspondan
       a un duplicado especial (duración diferente, pero el de menor peso es más largo).
    2. Clasifica cada grupo como Estándar o Especial según es_grupo_especial.
    """
    visited = set()
    all_groups = []
    
    # Agrupar por miniatura
    for i in range(len(analyzed_videos)):
        if i in visited:
            continue
        v1 = analyzed_videos[i]
        if v1['hash'] is None:
            continue
            
        group = [v1]
        for j in range(i + 1, len(analyzed_videos)):
            if j in visited:
                continue
            v2 = analyzed_videos[j]
            if v2['hash'] is None:
                continue
                
            dist = bin(v1['hash'] ^ v2['hash']).count('1')
            if dist <= 4:
                # Filtrar falsos positivos usando la duración y peso
                dur_diff = abs(v1['duration'] - v2['duration'])
                es_dup = False
                if dur_diff <= 20:
                    es_dup = True
                else:
                    # Caso Especial: el de mayor duración pesa menos que el de menor duración
                    if (v1['duration'] > v2['duration'] and v1['size'] < v2['size']) or \
                       (v2['duration'] > v1['duration'] and v2['size'] < v1['size']):
                        es_dup = True
                        
                if es_dup:
                    group.append(v2)
                    visited.add(j)
                    
        if len(group) > 1:
            all_groups.append(group)
            visited.add(i)
            
    # Clasificar en Estándar y Especiales
    std_groups = []
    spec_groups = []
    for group in all_groups:
        if es_grupo_especial(group):
            spec_groups.append(group)
        else:
            std_groups.append(group)
            
    return std_groups, spec_groups

async def procesar_comando_duplicados_miniatura(event):
    chat_id = event.chat_id
    
    # Parsear límite de mensajes opcional
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Escaneando videos y descargando miniaturas en {limit_desc}...")
    
    try:
        analyzed_videos = await escanear_y_calcular_hashes(chat_id, status_msg, limit)
        if not analyzed_videos:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** No se encontraron videos en {limit_desc}.")
            await asyncio.sleep(5)
            await status_msg.delete()
            try:
                await event.delete()
            except Exception:
                pass
            return

        std_groups, spec_groups = agrupar_duplicados_miniatura(analyzed_videos)

        await status_msg.delete()

        # Generar reporte
        chat = await event.get_chat()
        channel_id_str = str(chat.id).replace("-100", "")
        is_public = bool(getattr(chat, 'username', None))

        if not std_groups and not spec_groups:
            text_no_duplicates = (
                "✅ **No se encontraron videos duplicados visualmente.**\n\n"
                "🧹 **Para limpiar este reporte:** <code>/limpiar</code>"
            )
            await event.respond(text_no_duplicates + "\u200b", parse_mode='html', link_preview=False)
            return

        # 1. Reportar Duplicados Estándar
        if std_groups:
            dup_lines = []
            std_groups.sort(key=lambda g: g[0]['size'])
            
            for group_idx, group in enumerate(std_groups, 1):
                group_lines = []
                group_lines.append(f"<b>Coincidencia visual {group_idx}:</b>")
                group.sort(key=lambda x: x['msg'].id)
                
                for idx, v in enumerate(group, 1):
                    msg = v['msg']
                    formatted_size = format_size(v['size'])
                    formatted_duration = format_duration(v['duration'])
                    short_name = shorten_title(v['name'])
                    escaped_name = html.escape(short_name)
                    
                    link = f"https://t.me/{chat.username}/{msg.id}" if is_public else f"https://t.me/c/{channel_id_str}/{msg.id}"
                    tag = "original" if idx == 1 else "duplicado"
                    group_lines.append(f"  └─ {idx}. <a href=\"{link}\">{escaped_name}</a> <code>({formatted_size}) | ({formatted_duration}) {tag}</code>")
                
                dup_lines.append("\n".join(group_lines))

            dup_chunks = []
            curr_chunk = "⚠️ **Videos Duplicados Encontrados (Comparación Visual de Miniaturas):**\n\n"
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
            text_with_clean = (
                last_chunk + 
                "\n\n🧹 **Para limpiar este reporte:** <code>/limpiar</code> | <b>Para borrar estos duplicados (menor peso):</b> <code>/elimina_duplicados_miniatura</code>"
            )
            await event.respond(text_with_clean + "\u200b", parse_mode='html', link_preview=False)
            await asyncio.sleep(1)

        # 2. Reportar Duplicados Especiales
        if spec_groups:
            spec_lines = []
            spec_groups.sort(key=lambda g: g[0]['size'])
            
            for group_idx, group in enumerate(spec_groups, 1):
                group_lines = []
                group_lines.append(f"<b>Coincidencia especial {group_idx} (Conflicto Peso vs Duración):</b>")
                group.sort(key=lambda x: x['msg'].id)
                
                for idx, v in enumerate(group, 1):
                    msg = v['msg']
                    formatted_size = format_size(v['size'])
                    formatted_duration = format_duration(v['duration'])
                    short_name = shorten_title(v['name'])
                    escaped_name = html.escape(short_name)
                    
                    link = f"https://t.me/{chat.username}/{msg.id}" if is_public else f"https://t.me/c/{channel_id_str}/{msg.id}"
                    tag = "original" if idx == 1 else "duplicado especial"
                    group_lines.append(f"  └─ {idx}. <a href=\"{link}\">{escaped_name}</a> <code>({formatted_size}) | ({formatted_duration}) {tag}</code>")
                
                spec_lines.append("\n".join(group_lines))

            spec_chunks = []
            curr_chunk = "⚠️ **Videos Duplicados Especiales (El video con menor peso es más largo):**\n\n"
            for block in spec_lines:
                if len(curr_chunk) + len(block) + 4 > 3500:
                    spec_chunks.append(curr_chunk)
                    curr_chunk = ""
                curr_chunk += block + "\n\n"
            if curr_chunk:
                spec_chunks.append(curr_chunk.strip())
                
            for chunk in spec_chunks[:-1]:
                await event.respond(chunk + "\u200b", parse_mode='html', link_preview=False)
                await asyncio.sleep(1)
                
            last_chunk = spec_chunks[-1]
            text_with_clean = (
                last_chunk + 
                "\n\n🧹 **Para limpiar este reporte:** <code>/limpiar</code> | <b>Para borrar estos duplicados especiales (menor peso):</b> <code>/elimina_duplicados_especial_miniatura</code>"
            )
            await event.respond(text_with_clean + "\u200b", parse_mode='html', link_preview=False)

    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(10)
            await status_msg.delete()
        except Exception:
            pass

async def procesar_comando_elimina_duplicados_miniatura(event):
    chat_id = event.chat_id
    status_msg = await event.reply("⚙️ **[Bot Prime]** Escaneando y analizando miniaturas para borrar copias estándar livianas...")
    
    try:
        analyzed_videos = await escanear_y_calcular_hashes(chat_id, status_msg, limit=None)
        if not analyzed_videos:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontraron videos en el canal.")
            await asyncio.sleep(5)
            await status_msg.delete()
            try:
                await event.delete()
            except Exception:
                pass
            return

        std_groups, _ = agrupar_duplicados_miniatura(analyzed_videos)

        ids_to_delete = []
        details_deleted = []
        
        for group in std_groups:
            # Ordenar por tamaño de forma descendente (conservar el más pesado)
            group.sort(key=lambda x: x['size'], reverse=True)
            conserved = group[0]
            for item in group[1:]:
                ids_to_delete.append(item['msg'].id)
                details_deleted.append(f"• `{item['name']}` ({format_size(item['size'])}) -> Conservado: `{conserved['name']}` ({format_size(conserved['size'])})")

        if ids_to_delete:
            await safe_edit_status(status_msg, f"🗑️ **[Bot Prime]** Eliminando {len(ids_to_delete)} videos duplicados estándar de menor tamaño...")
            await client.delete_messages(chat_id, ids_to_delete)
            
            summary = f"✅ **[Bot Prime]** Se eliminaron {len(ids_to_delete)} copias duplicadas estándar de menor peso:\n\n" + "\n".join(details_deleted[:40])
            if len(details_deleted) > 40:
                summary += f"\n... y {len(details_deleted) - 40} videos más."
            await safe_edit_status(status_msg, summary)
        else:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron videos duplicados estándar para eliminar.")
            
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

async def procesar_comando_elimina_duplicados_especial_miniatura(event):
    chat_id = event.chat_id
    status_msg = await event.reply("⚙️ **[Bot Prime]** Escaneando y analizando miniaturas para borrar duplicados especiales (diferente duración) livianos...")
    
    try:
        analyzed_videos = await escanear_y_calcular_hashes(chat_id, status_msg, limit=None)
        if not analyzed_videos:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontraron videos en el canal.")
            await asyncio.sleep(5)
            await status_msg.delete()
            try:
                await event.delete()
            except Exception:
                pass
            return

        _, spec_groups = agrupar_duplicados_miniatura(analyzed_videos)

        ids_to_delete = []
        details_deleted = []
        
        for group in spec_groups:
            # Ordenar por tamaño de forma descendente (conservar el más pesado)
            group.sort(key=lambda x: x['size'], reverse=True)
            conserved = group[0]
            for item in group[1:]:
                ids_to_delete.append(item['msg'].id)
                details_deleted.append(f"• `{item['name']}` ({format_duration(item['duration'])}) ({format_size(item['size'])}) -> Conservado: `{conserved['name']}` ({format_duration(conserved['duration'])}) ({format_size(conserved['size'])})")

        if ids_to_delete:
            await safe_edit_status(status_msg, f"🗑️ **[Bot Prime]** Eliminando {len(ids_to_delete)} videos duplicados especiales de menor tamaño...")
            await client.delete_messages(chat_id, ids_to_delete)
            
            summary = f"✅ **[Bot Prime]** Se eliminaron {len(ids_to_delete)} copias duplicadas especiales de menor peso:\n\n" + "\n".join(details_deleted[:40])
            if len(details_deleted) > 40:
                summary += f"\n... y {len(details_deleted) - 40} videos más."
            await safe_edit_status(status_msg, summary)
        else:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron videos duplicados especiales para eliminar.")
            
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
