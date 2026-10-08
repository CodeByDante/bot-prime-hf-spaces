import asyncio
import time
from telethon import events
from telethon.tl.types import DocumentAttributeVideo
from telethon.errors import FloodWaitError
from core.client import client
from utils.helpers import safe_edit_status


async def procesar_comando_renvio_ordenador(event):
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
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Iniciando escaneo de videos e imágenes en {limit_desc}...")
    
    try:
        media_messages = []
        last_update = time.time()
        
        # 1. Escanear mensajes del canal
        async for m in client.iter_messages(chat_id, limit=limit):
            is_media = False
            
            # Verificar si es foto o video
            if m.photo or m.video:
                is_media = True
            elif m.document:
                mime = m.document.mime_type or ""
                if mime.startswith(('video/', 'image/')):
                    is_media = True
                else:
                    # Verificar por extensión de archivo por si acaso
                    file_name = ""
                    for attr in m.document.attributes:
                        if hasattr(attr, 'file_name') and attr.file_name:
                            file_name = attr.file_name
                            break
                    if file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff')):
                        is_media = True
            
            if is_media:
                media_messages.append(m)
                
            # Actualizar estado de forma controlada (throttling) para evitar FloodWait
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando canal... (encontrados {len(media_messages)} videos/imágenes)")
                last_update = now
                
        if not media_messages:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontraron videos ni imágenes en este canal.")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        # 2. Ordenar cronológicamente (ID de menor a mayor / del más antiguo al más nuevo)
        media_messages.sort(key=lambda x: x.id)
        
        # 3. Agrupar en lotes de 100
        message_ids = [m.id for m in media_messages]
        chunks = [message_ids[i:i + 100] for i in range(0, len(message_ids), 100)]
        
        await safe_edit_status(status_msg, f"📦 **[Bot Prime]** Se encontraron {len(media_messages)} elementos. Preparando el reenvío ordenado en {len(chunks)} lotes al bot @VideoAlbumMakerBot...")
        await asyncio.sleep(2)
        
        # 4. Enviar los lotes
        for idx, chunk in enumerate(chunks, 1):
            await safe_edit_status(status_msg, f"📤 **[Bot Prime]** Reenviando lote {idx} de {len(chunks)} ({len(chunk)} elementos)...")
            retries = 3
            while retries > 0:
                try:
                    await client.forward_messages('@VideoAlbumMakerBot', chunk, from_peer=chat_id)
                    break
                except FloodWaitError as e:
                    print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos...")
                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} segundos...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"❌ Error al reenviar lote: {e}")
                    retries -= 1
                    if retries == 0:
                        raise e
                    await asyncio.sleep(2)
            # Pequeña espera entre lotes para evitar saturación de Telegram
            await asyncio.sleep(3)
            
        # 5. Notificación final y limpieza
        await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Reenvío completado con éxito. Se enviaron {len(media_messages)} elementos en {len(chunks)} lotes al bot @VideoAlbumMakerBot.")
        await asyncio.sleep(10)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error durante el proceso: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
