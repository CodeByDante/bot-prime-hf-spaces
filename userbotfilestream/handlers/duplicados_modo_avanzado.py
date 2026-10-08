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
import core.proxy as proxy
from utils.helpers import safe_edit_status, get_message_title

def shorten_title(title, max_len=20):
    if not title:
        return ""
    return title[:max_len]

def calcular_hash_frame(frame):
    """
    Calcula el hash promedio (aHash) de un frame,
    recortando los márgenes para eliminar marcas de agua y logos.
    """
    if frame is None:
        return None
    try:
        # Convertir a escala de grises
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Evitar frames de color sólido
        if gray.std() < 3.0:
            return None
            
        # Recortar márgenes (eliminar marcas de agua y bordes)
        # Mantener del 15% al 80% de la altura, y del 5% al 95% de la anchura
        h, w = gray.shape
        y1, y2 = int(h * 0.15), int(h * 0.80)
        x1, x2 = int(w * 0.05), int(w * 0.95)
        gray_cropped = gray[y1:y2, x1:x2]
        
        if gray_cropped.size == 0:
            gray_cropped = gray
            
        # Redimensionar a 8x8
        resized = cv2.resize(gray_cropped, (8, 8), interpolation=cv2.INTER_AREA)
        avg = resized.mean()
        hash_bits = "".join(['1' if val > avg else '0' for val in resized.flatten()])
        return int(hash_bits, 2)
    except Exception as e:
        print(f"[Hash Frame Error] {e}")
        return None

def extraer_frame_streaming(stream_url, ts):
    """
    Extrae un frame de forma síncrona en el timestamp especificado.
    """
    try:
        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            return None
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
        ret, frame = cap.read()
        cap.release()
        if ret:
            return frame
    except Exception as e:
        print(f"[Extract Frame Error] ts={ts}s: {e}")
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

async def procesar_comando_duplicados_modo_avanzado(event):
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
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Escaneando videos en {limit_desc}...")
    
    proxy_runner = None
    try:
        videos = []
        last_update = time.time()
        
        # 1. Escanear todo el historial para recolectar metadatos de los videos
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
                duration = 0
                for attr in m.document.attributes:
                    if isinstance(attr, DocumentAttributeVideo):
                        duration = attr.duration
                        break
                if not duration and m.file.duration:
                    duration = m.file.duration
                
                size = m.document.size or 0
                file_name = m.file.name or f"video_{m.id}"
                
                # Omitir videos extremadamente cortos
                if duration >= 5:
                    videos.append({
                        'msg': m,
                        'name': file_name,
                        'duration': duration,
                        'size': size,
                        'hash1': None,
                        'hash2': None
                    })
                
            # Throttling
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

        # 2. Pre-filtrar candidatos sospechosos por duración flexible (duración +- 20 segundos)
        # Esto reduce drásticamente el número de streams a abrir
        candidates = []
        for i, v1 in enumerate(videos):
            has_partner = False
            for j, v2 in enumerate(videos):
                if i != j and abs(v1['duration'] - v2['duration']) <= 20:
                    has_partner = True
                    break
            if has_partner:
                candidates.append(v1)

        if not candidates:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron videos con duraciones similares (no hay duplicados).")
            await asyncio.sleep(6)
            await status_msg.delete()
            try:
                await event.delete()
            except Exception:
                pass
            return

        await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Iniciando streaming para extraer fotogramas de {len(candidates)} videos sospechosos...")

        # 3. Registrar documentos en el proxy local y arrancar el servidor
        proxy.active_client = client
        for c in candidates:
            proxy.active_documents[c['msg'].document.id] = c['msg'].document

        proxy_runner = await proxy.start_proxy_server(port=8080)
        
        # 4. Extraer fotogramas al 30% y al 70% de la duración de cada video
        last_update = time.time()
        loop = asyncio.get_event_loop()
        
        sem = asyncio.Semaphore(4)  # Límite de 4 descargas/extracciones simultáneas
        processed_count = 0
        
        async def procesar_candidato(c):
            nonlocal processed_count, last_update
            dur = c['duration']
            ts1 = dur * 0.3
            ts2 = dur * 0.7
            
            stream_url = f"http://127.0.0.1:8080/stream?id={c['msg'].document.id}"
            
            async with sem:
                # Extraer frame 1 en segundo plano
                frame1 = await loop.run_in_executor(None, extraer_frame_streaming, stream_url, ts1)
                c['hash1'] = calcular_hash_frame(frame1)
                
                # Extraer frame 2 en segundo plano
                frame2 = await loop.run_in_executor(None, extraer_frame_streaming, stream_url, ts2)
                c['hash2'] = calcular_hash_frame(frame2)
            
            # Quitar de active_documents para liberar memoria
            proxy.active_documents.pop(c['msg'].document.id, None)
            
            processed_count += 1
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Analizando fotogramas... ({processed_count}/{len(candidates)} procesados)")
                last_update = now

        tasks = [procesar_candidato(c) for c in candidates]
        await asyncio.gather(*tasks)

        # Apagar servidor proxy
        await proxy_runner.cleanup()
        proxy_runner = None

        # 5. Agrupar duplicados avanzados
        visited = set()
        duplicate_groups = []
        
        for i in range(len(candidates)):
            if i in visited:
                continue
                
            v1 = candidates[i]
            if v1['hash1'] is None or v1['hash2'] is None:
                continue
                
            group = [v1]
            for j in range(i + 1, len(candidates)):
                if j in visited:
                    continue
                    
                v2 = candidates[j]
                if v2['hash1'] is None or v2['hash2'] is None:
                    continue
                    
                # Comparar duración
                dur_diff = abs(v1['duration'] - v2['duration'])
                if dur_diff <= 20:
                    # Distancia de Hamming para el primer frame (30%)
                    dist1 = bin(v1['hash1'] ^ v2['hash1']).count('1')
                    # Distancia de Hamming para el segundo frame (70%)
                    dist2 = bin(v1['hash2'] ^ v2['hash2']).count('1')
                    
                    if dist1 <= 4 and dist2 <= 4:
                        group.append(v2)
                        visited.add(j)
                        
            if len(group) > 1:
                duplicate_groups.append(group)
                visited.add(i)

        await status_msg.delete()

        # 6. Reportar resultados
        chat = await event.get_chat()
        channel_id_str = str(chat.id).replace("-100", "")
        is_public = bool(getattr(chat, 'username', None))

        if duplicate_groups:
            dup_lines = []
            duplicate_groups.sort(key=lambda g: g[0]['size'])
            
            for group_idx, group in enumerate(duplicate_groups, 1):
                group_lines = []
                group_lines.append(f"<b>Coincidencia avanzada {group_idx}:</b>")
                group.sort(key=lambda x: x['msg'].id)
                
                for idx, v in enumerate(group, 1):
                    msg = v['msg']
                    formatted_size = format_size(v['size'])
                    formatted_duration = format_duration(v['duration'])
                    short_name = shorten_title(v['name'])
                    escaped_name = html.escape(short_name)
                    
                    if is_public:
                        link = f"https://t.me/{chat.username}/{msg.id}"
                    else:
                        link = f"https://t.me/c/{channel_id_str}/{msg.id}"
                        
                    tag = "original" if idx == 1 else "duplicado"
                    group_lines.append(f"  └─ {idx}. <a href=\"{link}\">{escaped_name}</a> <code>({formatted_size}) | ({formatted_duration}) {tag}</code>")
                
                dup_lines.append("\n".join(group_lines))

            # Segmentar chunks
            dup_chunks = []
            curr_chunk = "⚠️ **Videos Duplicados Encontrados (Modo Avanzado - Comparación de Frames):**\n\n"
            
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
                
                await event.respond(chunk + "\u200b", parse_mode='html', link_preview=False)
                await asyncio.sleep(1)
                
            last_chunk = dup_chunks[-1]
            text_with_clean_link = (
                last_chunk + 
                "\n\n🧹 **Para limpiar este reporte:** <code>/limpiar</code> | <b>Para borrar los videos duplicados (conservando el de mayor calidad/peso):</b> <code>/elimina_duplicados_modo_avanzado</code>"
            )
            await event.respond(text_with_clean_link + "\u200b", parse_mode='html', link_preview=False)
        else:
            text_no_duplicates = (
                "✅ **No se encontraron videos duplicados en el modo avanzado.**\n\n"
                "🧹 **Para limpiar este reporte:** <code>/limpiar</code>"
            )
            await event.respond(text_no_duplicates + "\u200b", parse_mode='html', link_preview=False)
            
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error en análisis avanzado: {e}")
            await asyncio.sleep(10)
            await status_msg.delete()
        except Exception:
            pass
    finally:
        # Asegurar apagado del proxy en cualquier caso de error/salida
        if proxy_runner:
            try:
                await proxy_runner.cleanup()
            except Exception:
                pass
        # Limpiar active_documents
        for c in proxy.active_documents.copy().keys():
            proxy.active_documents.pop(c, None)

async def procesar_comando_elimina_duplicados_modo_avanzado(event):
    chat_id = event.chat_id
    status_msg = await event.reply("⚙️ **[Bot Prime]** Escaneando y analizando fotogramas para borrar copias livianas...")
    
    proxy_runner = None
    try:
        videos = []
        last_update = time.time()
        
        # 1. Escanear todo el historial para recolectar metadatos de los videos
        async for m in client.iter_messages(chat_id):
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
                duration = 0
                for attr in m.document.attributes:
                    if isinstance(attr, DocumentAttributeVideo):
                        duration = attr.duration
                        break
                if not duration and m.file.duration:
                    duration = m.file.duration
                
                size = m.document.size or 0
                file_name = m.file.name or f"video_{m.id}"
                
                if duration >= 5:
                    videos.append({
                        'msg': m,
                        'name': file_name,
                        'duration': duration,
                        'size': size,
                        'hash1': None,
                        'hash2': None
                    })
                
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Buscando videos... ({len(videos)} encontrados)")
                last_update = now

        if not videos:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontraron videos en el canal.")
            await asyncio.sleep(5)
            await status_msg.delete()
            try:
                await event.delete()
            except Exception:
                pass
            return

        # 2. Pre-filtrar candidatos sospechosos por duración flexible
        candidates = []
        for i, v1 in enumerate(videos):
            has_partner = False
            for j, v2 in enumerate(videos):
                if i != j and abs(v1['duration'] - v2['duration']) <= 20:
                    has_partner = True
                    break
            if has_partner:
                candidates.append(v1)

        if not candidates:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron videos con duraciones similares (no hay duplicados).")
            await asyncio.sleep(6)
            await status_msg.delete()
            try:
                await event.delete()
            except Exception:
                pass
            return

        await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Iniciando streaming para extraer fotogramas de {len(candidates)} videos sospechosos...")

        # 3. Registrar documentos en el proxy local y arrancar el servidor
        proxy.active_client = client
        for c in candidates:
            proxy.active_documents[c['msg'].document.id] = c['msg'].document

        proxy_runner = await proxy.start_proxy_server(port=8080)
        
        # 4. Extraer fotogramas al 30% y al 70% de la duración de cada video
        last_update = time.time()
        loop = asyncio.get_event_loop()
        
        sem = asyncio.Semaphore(4)  # Límite de 4 descargas/extracciones simultáneas
        processed_count = 0
        
        async def procesar_candidato_elimina(c):
            nonlocal processed_count, last_update
            dur = c['duration']
            ts1 = dur * 0.3
            ts2 = dur * 0.7
            
            stream_url = f"http://127.0.0.1:8080/stream?id={c['msg'].document.id}"
            
            async with sem:
                frame1 = await loop.run_in_executor(None, extraer_frame_streaming, stream_url, ts1)
                c['hash1'] = calcular_hash_frame(frame1)
                
                frame2 = await loop.run_in_executor(None, extraer_frame_streaming, stream_url, ts2)
                c['hash2'] = calcular_hash_frame(frame2)
            
            proxy.active_documents.pop(c['msg'].document.id, None)
            
            processed_count += 1
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Analizando fotogramas... ({processed_count}/{len(candidates)} procesados)")
                last_update = now

        tasks = [procesar_candidato_elimina(c) for c in candidates]
        await asyncio.gather(*tasks)

        # Apagar servidor proxy
        await proxy_runner.cleanup()
        proxy_runner = None

        # 5. Agrupar duplicados avanzados
        visited = set()
        duplicate_groups = []
        
        for i in range(len(candidates)):
            if i in visited:
                continue
                
            v1 = candidates[i]
            if v1['hash1'] is None or v1['hash2'] is None:
                continue
                
            group = [v1]
            for j in range(i + 1, len(candidates)):
                if j in visited:
                    continue
                    
                v2 = candidates[j]
                if v2['hash1'] is None or v2['hash2'] is None:
                    continue
                    
                dur_diff = abs(v1['duration'] - v2['duration'])
                if dur_diff <= 20:
                    dist1 = bin(v1['hash1'] ^ v2['hash1']).count('1')
                    dist2 = bin(v1['hash2'] ^ v2['hash2']).count('1')
                    
                    if dist1 <= 4 and dist2 <= 4:
                        group.append(v2)
                        visited.add(j)
                        
            if len(group) > 1:
                duplicate_groups.append(group)
                visited.add(i)

        # 6. Identificar cuáles borrar (los de menor peso/tamaño en cada grupo)
        ids_to_delete = []
        details_deleted = []
        
        for group in duplicate_groups:
            # Ordenar por tamaño descendente (el más pesado / mejor calidad primero)
            group.sort(key=lambda x: x['size'], reverse=True)
            
            conserved = group[0]
            for item in group[1:]:
                ids_to_delete.append(item['msg'].id)
                details_deleted.append(f"• `{item['name']}` ({format_size(item['size'])}) -> Conservado: `{conserved['name']}` ({format_size(conserved['size'])})")

        if ids_to_delete:
            await safe_edit_status(status_msg, f"🗑️ **[Bot Prime]** Eliminando {len(ids_to_delete)} videos duplicados de menor tamaño...")
            await client.delete_messages(chat_id, ids_to_delete)
            
            summary = f"✅ **[Bot Prime]** Se eliminaron {len(ids_to_delete)} copias duplicadas de menor peso (Modo Avanzado):\n\n" + "\n".join(details_deleted[:40])
            if len(details_deleted) > 40:
                summary += f"\n... y {len(details_deleted) - 40} videos más."
            await safe_edit_status(status_msg, summary)
        else:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron videos duplicados para eliminar.")
            
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
    finally:
        if proxy_runner:
            try:
                await proxy_runner.cleanup()
            except Exception:
                pass
        for c in proxy.active_documents.copy().keys():
            proxy.active_documents.pop(c, None)
