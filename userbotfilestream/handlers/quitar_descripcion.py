import asyncio
import time
from telethon import events
from telethon.errors import FloodWaitError
from core.client import client
from utils.helpers import safe_edit_status


def es_video(m):
    if m.video:
        return True
    if m.document:
        mime = m.document.mime_type or ""
        if mime.startswith('video/'):
            return True
        file_name = ""
        for attr in m.document.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                file_name = attr.file_name
                break
        if file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts')):
            return True
    return False

def es_imagen(m):
    if m.photo:
        return True
    if m.document:
        mime = m.document.mime_type or ""
        if mime.startswith('image/'):
            return True
        file_name = ""
        for attr in m.document.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                file_name = attr.file_name
                break
        if file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff')):
            return True
    return False

async def procesar_quitar_descripcion_video(event):
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
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando videos con descripción en {limit_desc}...")
    
    try:
        matching_messages = []
        last_update = time.time()
        
        async for m in client.iter_messages(chat_id, limit=limit):
            if es_video(m) and m.message and m.message.strip():
                matching_messages.append(m)
            
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando canal... (encontrados {len(matching_messages)} videos con descripción)")
                last_update = now
                
        if not matching_messages:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron videos con descripción en este canal.")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        total = len(matching_messages)
        await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Encontrados {total} videos con descripción. Iniciando remoción...")
        await asyncio.sleep(2)
        
        edited_count = 0
        consecutive_perm_errors = 0
        for idx, msg in enumerate(matching_messages, 1):
            retries = 3
            while retries > 0:
                try:
                    await client.edit_message(chat_id, msg.id, text="")
                    edited_count += 1
                    consecutive_perm_errors = 0
                    break
                except FloodWaitError as e:
                    print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos para editar...")
                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} segundos...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"❌ Error al editar mensaje {msg.id}: {e}")
                    err_msg = str(e).lower()
                    if "message id is invalid" in err_msg or "you can't do that operation" in err_msg or "chat_admin_required" in err_msg or "message_author_required" in err_msg:
                        consecutive_perm_errors += 1
                        if consecutive_perm_errors >= 3:
                            raise Exception("Falta de permisos para editar mensajes en este canal.")
                        break # No reintentar este mensaje
                    retries -= 1
                    if retries == 0:
                        break
                    await asyncio.sleep(2)
            
            if idx % 5 == 0 or idx == total:
                await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Removiendo descripciones: {idx}/{total} videos procesados...")
                
            await asyncio.sleep(1.0)
            
        await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Proceso completado. Se removió la descripción de {edited_count} videos.")
        await asyncio.sleep(8)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error durante el proceso: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass

async def procesar_quitar_descripcion_imagen(event):
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
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando imágenes con descripción en {limit_desc}...")
    
    try:
        matching_messages = []
        last_update = time.time()
        
        async for m in client.iter_messages(chat_id, limit=limit):
            if es_imagen(m) and m.message and m.message.strip():
                matching_messages.append(m)
            
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando canal... (encontrados {len(matching_messages)} imágenes con descripción)")
                last_update = now
                
        if not matching_messages:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron imágenes con descripción en este canal.")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        total = len(matching_messages)
        await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Encontradas {total} imágenes con descripción. Iniciando remoción...")
        await asyncio.sleep(2)
        
        edited_count = 0
        consecutive_perm_errors = 0
        for idx, msg in enumerate(matching_messages, 1):
            retries = 3
            while retries > 0:
                try:
                    await client.edit_message(chat_id, msg.id, text="")
                    edited_count += 1
                    consecutive_perm_errors = 0
                    break
                except FloodWaitError as e:
                    print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos para editar...")
                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} segundos...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"❌ Error al editar mensaje {msg.id}: {e}")
                    err_msg = str(e).lower()
                    if "message id is invalid" in err_msg or "you can't do that operation" in err_msg or "chat_admin_required" in err_msg or "message_author_required" in err_msg:
                        consecutive_perm_errors += 1
                        if consecutive_perm_errors >= 3:
                            raise Exception("Falta de permisos para editar mensajes en este canal.")
                        break
                    retries -= 1
                    if retries == 0:
                        break
                    await asyncio.sleep(2)
            
            if idx % 5 == 0 or idx == total:
                await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Removiendo descripciones: {idx}/{total} imágenes procesadas...")
                
            await asyncio.sleep(1.0)
            
        await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Proceso completado. Se removió la descripción de {edited_count} imágenes.")
        await asyncio.sleep(8)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error durante el proceso: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass

async def procesar_quitar_descripcion(event):
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
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando fotos y videos con descripción en {limit_desc}...")
    
    try:
        matching_messages = []
        last_update = time.time()
        
        async for m in client.iter_messages(chat_id, limit=limit):
            if (es_video(m) or es_imagen(m)) and m.message and m.message.strip():
                matching_messages.append(m)
            
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando canal... (encontrados {len(matching_messages)} archivos con descripción)")
                last_update = now
                
        if not matching_messages:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron fotos o videos con descripción en este canal.")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        total = len(matching_messages)
        await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Encontrados {total} archivos con descripción. Iniciando remoción...")
        await asyncio.sleep(2)
        
        edited_count = 0
        consecutive_perm_errors = 0
        for idx, msg in enumerate(matching_messages, 1):
            retries = 3
            while retries > 0:
                try:
                    await client.edit_message(chat_id, msg.id, text="")
                    edited_count += 1
                    consecutive_perm_errors = 0
                    break
                except FloodWaitError as e:
                    print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos para editar...")
                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} segundos...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"❌ Error al editar mensaje {msg.id}: {e}")
                    err_msg = str(e).lower()
                    if "message id is invalid" in err_msg or "you can't do that operation" in err_msg or "chat_admin_required" in err_msg or "message_author_required" in err_msg:
                        consecutive_perm_errors += 1
                        if consecutive_perm_errors >= 3:
                            raise Exception("Falta de permisos para editar mensajes en este canal.")
                        break
                    retries -= 1
                    if retries == 0:
                        break
                    await asyncio.sleep(2)
            
            if idx % 5 == 0 or idx == total:
                await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Removiendo descripciones: {idx}/{total} archivos procesados...")
                
            await asyncio.sleep(1.0)
            
        await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Proceso completado. Se removió la descripción de {edited_count} archivos.")
        await asyncio.sleep(8)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error durante el proceso: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
