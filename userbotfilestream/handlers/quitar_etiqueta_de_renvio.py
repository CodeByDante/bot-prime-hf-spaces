import asyncio
import time
from telethon.errors import FloodWaitError
from core.client import client
from utils.helpers import safe_edit_status


async def procesar_quitar_etiqueta_de_renvio(event):
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
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando videos e imágenes reenviados en {limit_desc}...")
    
    try:
        media_messages = []
        last_update = time.time()
        
        # 1. Escanear mensajes del canal con límite
        async for m in client.iter_messages(chat_id, limit=limit):
            # Solo procesar mensajes que tengan la etiqueta de reenviado
            if m.fwd_from is not None:
                is_media = False
                
                # Verificar si es foto o video
                if m.photo or m.video:
                    is_media = True
                elif m.document:
                    mime = m.document.mime_type or ""
                    if mime.startswith(('video/', 'image/')):
                        is_media = True
                    else:
                        file_name = ""
                        for attr in m.document.attributes:
                            if hasattr(attr, 'file_name') and attr.file_name:
                                file_name = attr.file_name
                                break
                        if file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff')):
                            is_media = True
                
                if is_media:
                    media_messages.append(m)
            
            # Throttling de actualizaciones de estado para evitar FloodWait
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando canal... (encontrados {len(media_messages)} elementos reenviados)")
                last_update = now
                
        if not media_messages:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron videos ni imágenes con etiqueta de reenviado en este canal.")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        # 2. Ordenar cronológicamente por ID ascendente (del más antiguo al más nuevo)
        media_messages.sort(key=lambda x: x.id)
        
        # Group messages by grouped_id to preserve albums
        groups = []
        grouped_messages = {}
        
        for msg in media_messages:
            if msg.grouped_id is None:
                groups.append([msg])
            else:
                if msg.grouped_id not in grouped_messages:
                    group = [msg]
                    grouped_messages[msg.grouped_id] = group
                    groups.append(group)
                else:
                    grouped_messages[msg.grouped_id].append(msg)
                    
        total_groups = len(groups)
        await safe_edit_status(status_msg, f"📦 **[Bot Prime]** Detectados {total_groups} grupos/álbumes reenviados. Iniciando procesamiento...")
        await asyncio.sleep(2)
        
        exitos = 0
        fallidos = 0
        
        # 3. Procesar grupo por grupo (enviar nuevo y borrar antiguo)
        for idx, group in enumerate(groups, 1):
            await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Procesando grupo {idx} de {total_groups}... (Exitosos: {exitos}, Fallidos: {fallidos})")
            
            new_media = None
            envio_exitoso = False
            
            # Si el grupo tiene 1 elemento
            if len(group) == 1:
                msg = group[0]
                retries = 3
                while retries > 0:
                    try:
                        new_media = await client.send_file(
                            chat_id,
                            file=msg.media,
                            caption=msg.text
                        )
                        envio_exitoso = True
                        break
                    except FloodWaitError as e:
                        print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos para enviar...")
                        await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} segundos...")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"❌ Error al enviar elemento: {e}")
                        retries -= 1
                        if retries == 0:
                            print(f"❌ No se pudo enviar el elemento {msg.id} después de 3 intentos.")
                            break
                        await asyncio.sleep(2)
            else:
                # El grupo tiene más de 1 elemento (es un álbum)
                retries = 3
                while retries > 0:
                    try:
                        new_media = await client.send_file(
                            chat_id,
                            file=[m.media for m in group],
                            caption=[m.text for m in group]
                        )
                        envio_exitoso = True
                        break
                    except FloodWaitError as e:
                        print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos para enviar album...")
                        await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} segundos...")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"❌ Error al enviar album: {e}")
                        retries -= 1
                        if retries == 0:
                            print(f"❌ No se pudo enviar el álbum {[m.id for m in group]} después de 3 intentos.")
                            break
                        await asyncio.sleep(2)
                        
            # Si se envió correctamente, borrar el/los mensaje(s) original(es)
            if envio_exitoso and new_media:
                retries = 3
                old_ids = [m.id for m in group]
                while retries > 0:
                    try:
                        await client.delete_messages(chat_id, old_ids)
                        exitos += 1
                        break
                    except FloodWaitError as e:
                        print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos para borrar...")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"❌ Error al borrar elemento antiguo: {e}")
                        retries -= 1
                        if retries == 0:
                            # Aunque no se borre el antiguo, consideramos el envío como exitoso para avanzar
                            exitos += 1
                            break
                        await asyncio.sleep(2)
            else:
                fallidos += 1
            
            # Esperar un breve instante para cumplir los límites de velocidad de Telegram
            await asyncio.sleep(1.5)
            
        # 4. Finalizar y limpiar
        if fallidos > 0:
            await safe_edit_status(status_msg, f"⚠️ **[Bot Prime]** Proceso completado. Se quitaron etiquetas de reenviado: **{exitos}** exitosos, **{fallidos}** fallidos (revisa la consola/logs).")
            await asyncio.sleep(20)
        else:
            await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Proceso completado con éxito. Se eliminó la etiqueta de reenviado en los {total_groups} grupos/álbumes.")
            await asyncio.sleep(10)
            
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error durante el proceso: {e}")
            await asyncio.sleep(15)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
