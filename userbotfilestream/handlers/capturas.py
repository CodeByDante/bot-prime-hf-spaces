import os
import re
import cv2
import asyncio
from telethon.tl.types import DocumentAttributeVideo
from telethon.errors import FloodWaitError

from core.client import client
import core.proxy as proxy
from utils.helpers import (
    extract_title_from_caption,
    clean_comparison_string,
    get_message_title,
    extract_series_name,
    parse_episode_number,
    calculate_distribution,
    safe_edit_status
)
from utils.image import capture_frames_from_stream
from utils.channel_resolver import matches_channel

def is_video_message(msg):
    if not msg:
        return False
    if msg.video:
        return True
    if msg.document:
        mime = msg.document.mime_type or ""
        if mime.startswith('video/'):
            return True
        for attr in msg.document.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                if attr.file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts')):
                    return True
    return False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "capturas")
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def procesar_comando_capturas(event):
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
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Analizando videos en {limit_desc}...")
    
    try:
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', '') or ''
        is_hentaila = matches_channel(chat_id, chat_title, "hentaila_vip") or "hentaila" in chat_title.lower()

        messages = []
        async for m in client.iter_messages(chat_id, limit=limit):
            messages.append(m)
            
        # Agrupar videos: por series en Hentaila, o individualmente en otros canales
        groups = {}
        current_part_group_key = None
        
        for msg in messages:
            if is_video_message(msg):
                title = ""
                if msg.message:
                    title = extract_title_from_caption(msg.message)
                if not title:
                    title = get_message_title(msg)
                if not title or not title.strip():
                    title = f"Video {msg.id}"
                
                if is_hentaila:
                    s_name = extract_series_name(title)
                    series_key = clean_comparison_string(s_name)
                    if not series_key:
                        series_key = f"video_{msg.id}"
                    display_name = s_name or title
                    ep_num = parse_episode_number(title)
                else:
                    match = re.search(r'(parte|versión|version|verción|vercion)\s*\d+', title, re.IGNORECASE)
                    if match:
                        if current_part_group_key is None:
                            current_part_group_key = f"group_{msg.id}"
                        series_key = current_part_group_key
                        display_name = ""
                        ep_num = 1
                    else:
                        current_part_group_key = None
                        series_key = f"video_{msg.id}"
                        display_name = title
                        ep_num = 1
                
                ep_data = {
                    'msg': msg,
                    'title': title,
                    'ep_num': ep_num,
                    'video': msg.video or msg.document
                }
                
                if series_key not in groups:
                    groups[series_key] = {
                        'search_name': display_name,
                        'display_name': display_name,
                        'episodes': []
                    }
                groups[series_key]['episodes'].append(ep_data)
            else:
                if msg.photo:
                    current_part_group_key = None
                        
        if not groups:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontró ningún video para procesar.")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        # Definir la cola para procesamiento en fila
        queue = asyncio.Queue()
        processed_series_names = []

        async def scan_task():
            try:
                # Sort group keys by the message ID of their oldest episode in ascending order (oldest first)
                sorted_group_keys = sorted(
                    groups.keys(),
                    key=lambda k: min(groups[k]['episodes'], key=lambda x: x['msg'].id)['msg'].id
                )
                for group_key in sorted_group_keys:
                    group_data = groups[group_key]
                    search_name = group_data['search_name']
                    display_name = group_data['display_name']
                    eps = group_data['episodes']
                    
                    print(f"🔍 Verificando si '{display_name}' ya tiene capturas...")
                    
                    # Detección por proximidad: contamos las fotos que hay arriba (más antiguos) del episodio más antiguo
                    unprocessed_eps = []
                    oldest_ep = min(eps, key=lambda x: x['msg'].id)
                    video_ya_tiene = False
                    try:
                        video_idx = next(i for i, m in enumerate(messages) if m.id == oldest_ep['msg'].id)
                        
                        # Buscar hacia atrás/arriba (mensajes más antiguos, mayor índice en la lista messages)
                        photo_count = 0
                        for j in range(video_idx + 1, min(video_idx + 18, len(messages))):
                            msg_check = messages[j]
                            if is_video_message(msg_check):
                                # Si es un video de otro grupo, paramos de contar
                                is_same_group = False
                                for group_ep in eps:
                                    if group_ep['msg'].id == msg_check.id:
                                        is_same_group = True
                                        break
                                if not is_same_group:
                                    break
                            if msg_check.photo:
                                photo_count += 1
                        
                        required_photos = 10 if is_hentaila else 4
                        if photo_count >= required_photos:
                            video_ya_tiene = True
                    except StopIteration:
                        pass
                        
                    if not video_ya_tiene:
                        unprocessed_eps = eps
                    else:
                        print(f"  • Serie/Video '{display_name}' ya tiene sus {required_photos} capturas arriba. Saltando.")
                    
                    if unprocessed_eps:
                        print(f"❌ La serie/video '{display_name}' no tiene capturas. Se procesará(n) {len(unprocessed_eps)} video(s).")
                        await queue.put((display_name, unprocessed_eps))
                    else:
                        print(f"✅ '{display_name}' ya tiene capturas. Saltando.")
            except Exception as e:
                print(f"[Scan Task Error] Error al comprobar videos: {e}")
            finally:
                # Poner None en la cola para finalizar al consumidor
                await queue.put(None)

        async def process_task():
            proxy.active_client = client
            proxy_runner = None
            
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        queue.task_done()
                        break
                        
                    s_name, episodes = item
                    
                    # Lazy start of proxy server
                    if proxy_runner is None:
                        proxy_runner = await proxy.start_proxy_server(port=8080)
                        
                    print("\n\033[95m" + "="*50)
                    print(f" PROCESANDO VIDEO: {s_name}")
                    print("="*50 + "\033[0m")
                    await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Capturando fotogramas de: '{s_name}'...")
                    
                    episodes.sort(key=lambda x: x['ep_num'])
                    for ep in episodes:
                        print(f"  • Encontrado: {ep['title']} (Episodio {ep['ep_num']})")
                        
                    total_screenshots = 10 if is_hentaila else 4
                    distribution = calculate_distribution(len(episodes), total_screenshots=total_screenshots)
                    print(f"\033[94m[Distribución] Reparto equitativo de fotos: {list(reversed(distribution))}\033[0m")
                    
                    # Registrar todos los videos en active_documents del proxy
                    for ep in episodes:
                        proxy.active_documents[ep['video'].id] = ep['video']
                    
                    saved_files = []
                    semaphore = asyncio.Semaphore(3)  # Limitar a 3 descargas concurrentes
                    
                    async def procesar_episodio(idx, ep):
                        count = distribution[idx]
                        if count == 0:
                            return []
                            
                        video_doc = ep['video']
                        duration = 0
                        for attr in video_doc.attributes:
                            if isinstance(attr, DocumentAttributeVideo):
                                duration = attr.duration
                                break
                        if duration == 0:
                            duration = 300
                            
                        timestamps = [(j + 0.5) * (duration / count) for j in range(count)]
                        print(f"\n[Streaming] {ep['title']} -> Extrayendo {count} capturas...")
                        
                        async with semaphore:
                            loop = asyncio.get_event_loop()
                            stream_url = f"http://127.0.0.1:8080/stream?id={video_doc.id}"
                            capturas = await loop.run_in_executor(
                                None,
                                capture_frames_from_stream,
                                stream_url,
                                timestamps
                            )
                        
                        saved_episode_files = []
                        start_photo_idx = sum(distribution[:idx]) + 1
                        
                        for f_idx, (ts, frame) in enumerate(capturas):
                            clean_filename = re.sub(r'[\\/*?:"<>|]', "", s_name)
                            img_name = f"captura_{clean_filename.replace(' ', '_')}_cap_{start_photo_idx + f_idx:02d}.jpg"
                            full_path = os.path.join(OUTPUT_DIR, img_name)
                            cv2.imwrite(full_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                            saved_episode_files.append((start_photo_idx + f_idx, full_path))
                            print(f"   ✓ Foto guardada: {img_name}")
                            
                        return saved_episode_files

                    tasks = [procesar_episodio(idx, ep) for idx, ep in enumerate(episodes)]
                    results = await asyncio.gather(*tasks)
                    
                    # Desregistrar del proxy
                    for ep in episodes:
                        proxy.active_documents.pop(ep['video'].id, None)
                    
                    # Reconstruir lista ordenada de archivos guardados
                    saved_files_with_idx = []
                    for res in results:
                        saved_files_with_idx.extend(res)
                    saved_files_with_idx.sort(key=lambda x: x[0])
                    saved_files = [path for _, path in saved_files_with_idx]
                    
                    if not saved_files:
                        print(f"\033[91m[Error] No se pudo tomar ninguna captura para '{s_name}'.\033[0m")
                        queue.task_done()
                        continue
                        
                    # 1. Enviar álbum de fotos
                    print(f"\n[Destino] Enviando álbum de capturas...")
                    album_sent = False
                    while True:
                        try:
                            await client.send_file(chat_id, saved_files, caption=f"🉐Titulo: {s_name}")
                            print(f"   ✓ Álbum de fotos enviado con éxito!")
                            album_sent = True
                            break
                        except FloodWaitError as e:
                            print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos para enviar álbum...")
                            await asyncio.sleep(e.seconds)
                        except Exception as e:
                            print(f"   ✗ Error al enviar el álbum: {e}")
                            break
                    
                    # 2. Reenviar videos y borrar antiguos
                    if album_sent:
                        print(f"\n[Destino] Reenviando el video...")
                        for ep in episodes:
                            while True:
                                try:
                                    await client.send_file(
                                        chat_id,
                                        file=ep['msg'].media,
                                        caption=ep['msg'].message,
                                        formatting_entities=ep['msg'].entities
                                    )
                                    print(f"   ✓ Video '{ep['title']}' reenviado con éxito!")
                                    break
                                except FloodWaitError as e:
                                    print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos para reenviar video...")
                                    await asyncio.sleep(e.seconds)
                                except Exception as e:
                                    print(f"   ✗ Error al reenviar el video '{ep['title']}': {e}")
                                    break
                                    
                            while True:
                                try:
                                    await client.delete_messages(chat_id, ep['msg'].id)
                                    break
                                except FloodWaitError as e:
                                    print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos para borrar video antiguo...")
                                    await asyncio.sleep(e.seconds)
                                except Exception as e:
                                    print(f"   ✗ Error al borrar video antiguo: {e}")
                                    break
                        processed_series_names.append(s_name)
                        
                    # Eliminar archivos locales
                    for file_path in saved_files:
                        try:
                            os.remove(file_path)
                        except Exception:
                            pass
                            
                    queue.task_done()
            except Exception as e:
                print(f"[Process Task Error] {e}")
            finally:
                pass

        # Iniciar las tareas concurrentemente
        process_worker = asyncio.create_task(process_task())
        await scan_task()
        await process_worker

        if not processed_series_names:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** Todos los videos cuentan con sus capturas.")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        num_processed = len(processed_series_names)
        names_list = "\n".join([f"`{name}`" for name in processed_series_names])
        if num_processed == 1:
            summary_text = f"✅ **[Bot Prime]** Se procesó 1 video:\n\n{names_list}"
        else:
            summary_text = f"✅ **[Bot Prime]** Se procesaron {num_processed} videos:\n\n{names_list}"
            
        await safe_edit_status(status_msg, summary_text)
        await asyncio.sleep(20)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
        await asyncio.sleep(10)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
