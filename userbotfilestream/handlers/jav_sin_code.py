import re
import time
import asyncio
from telethon import events
from telethon.errors import FloodWaitError
from core.client import client
from utils.channel_resolver import matches_channel
from utils.helpers import safe_edit_status



# Expresión regular para códigos JAV (ej: PRED-769, DVDMS-149, GVG-707, etc.)
JAV_REGEX = re.compile(r'\b([a-zA-Z0-9]{2,10}-\d{2,7})\b')

# Prefijos excluidos comunes para evitar falsos positivos
EXCLUDED_PREFIXES = {
    'ep', 'pt', 'part', 'cap', 'vol', 'v', 'ed', 'id', 'p',
    'dvd', 'cd', 'mp4', 'mkv', 'avi', 'gif', 'png', 'jpg'
}

async def procesar_comando_jav_sin_code(event):
    chat_id = event.chat_id
    
    # Obtener información del chat
    chat = await event.get_chat()
    chat_title = getattr(chat, 'title', '') or ''
    is_private = event.is_private
    
    # Restringir a "JAV REGULAR" excepto para chats privados
    if not is_private and not matches_channel(chat_id, chat_title, "jav_regular"):
        error_msg = await event.reply("❌ **[Bot Prime]** Este comando es exclusivo para el canal **JAV REGULAR**.")
        await asyncio.sleep(5)
        await client.delete_messages(chat_id, [event.id, error_msg.id])
        return

    # Parsear límite opcional de mensajes a escanear (por defecto None para escanear todo)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando videos sin descripción en {limit_desc}...")
    
    try:
        messages = []
        last_update = time.time()
        
        # 1. Escanear mensajes
        async for m in client.iter_messages(chat_id, limit=limit):
            messages.append(m)
            
            # Throttling de la actualización de estado
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando mensajes... ({len(messages)} analizados)")
                last_update = now
                
        # 2. Filtrar videos sin códigos JAV
        videos_sin_code = []
        
        # Determinar estructura de enlaces
        channel_id_str = str(chat.id).replace("-100", "")
        is_public = bool(getattr(chat, 'username', None))
        
        for msg in messages:
            # Solo procesar videos
            if not msg.video:
                continue
                
            # Verificar si el mensaje tiene descripción/caption
            has_description = bool(msg.message and msg.message.strip())
            
            # Si tiene descripción, no lo tocamos (omitir por completo)
            if has_description:
                continue
                
            # Generar nombre descriptivo usando el nombre del archivo si existe, de lo contrario un genérico
            label = ""
            if msg.file and msg.file.name:
                label = msg.file.name
            if not label:
                label = f"Video vacío (Mensaje #{msg.id})"
                
            # Enlace directo al mensaje en Telegram
            link = f"https://t.me/{chat.username}/{msg.id}" if is_public else f"https://t.me/c/{channel_id_str}/{msg.id}"
            
            videos_sin_code.append({
                'label': label,
                'link': link,
                'id': msg.id,
                'msg': msg
            })
                
        if not videos_sin_code:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** Todos los videos analizados tienen una descripción asignada.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return

        # 3. Ordenar cronológicamente (ID de menor a mayor / del más antiguo al más nuevo)
        videos_sin_code.sort(key=lambda x: x['id'])
        
        # 4. Construir las líneas del reporte
        lines = []
        for item in videos_sin_code:
            lines.append(f"• <a href=\"{item['link']}\">{item['label']}</a>")
            
        # 5. Dividir en mensajes (lotes) de tamaño aceptable para Telegram
        messages_to_send = []
        current_chunk = "🤖 **Videos sin código JAV detectados:**\n\n"
        
        for line in lines:
            if len(current_chunk) + len(line) + 2 > 3500:
                messages_to_send.append(current_chunk)
                current_chunk = ""
            current_chunk += line + "\n"
            
        if current_chunk:
            messages_to_send.append(current_chunk)
            
        # Eliminar el mensaje de estado de búsqueda
        await status_msg.delete()
        
        # 6. Enviar reportes (con marca de agua \u200b para limpieza)
        for chunk in messages_to_send:
            await event.respond(chunk + "\u200b", parse_mode='html', link_preview=False)
            await asyncio.sleep(1)
            
        # 7. Reenviar los videos sin código en orden secuencial (sin etiqueta de reenviado)
        total_videos = len(videos_sin_code)
        progress_msg = await event.respond(f"📤 **[Bot Prime]** Iniciando el reenvío de {total_videos} videos sin código (sin etiqueta)...")
        await asyncio.sleep(2)
        
        sent_count = 0
        for idx, item in enumerate(videos_sin_code, 1):
            msg = item['msg']
            await safe_edit_status(progress_msg, f"⚙️ **[Bot Prime]** Reenviando video {idx} de {total_videos}...")
            
            new_msg = None
            retries = 3
            while retries > 0:
                try:
                    new_msg = await client.send_file(
                        chat_id,
                        file=msg.media,
                        caption=msg.message,
                        formatting_entities=msg.entities
                    )
                    break
                except FloodWaitError as e:
                    print(f"[JAV Sin Code] FloodWait al enviar: esperando {e.seconds} seg...")
                    await safe_edit_status(progress_msg, f"⏳ **[Bot Prime]** Límite excedido al enviar. Esperando {e.seconds} seg...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"[JAV Sin Code] Error reenviando video {msg.id}: {e}")
                    retries -= 1
                    if retries > 0:
                        await asyncio.sleep(2)
            
            if new_msg:
                # Borrar el original inmediatamente
                delete_retries = 3
                deleted = False
                while delete_retries > 0:
                    try:
                        await client.delete_messages(chat_id, msg.id)
                        deleted = True
                        break
                    except FloodWaitError as e:
                        print(f"[JAV Sin Code] FloodWait al borrar: esperando {e.seconds} seg...")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"[JAV Sin Code] Error al borrar original {msg.id}: {e}")
                        delete_retries -= 1
                        if delete_retries > 0:
                            await asyncio.sleep(2)
                
                sent_count += 1
            
            # Esperar un breve instante para evitar flood de Telegram
            await asyncio.sleep(2.0)
            
        if sent_count == total_videos:
            await safe_edit_status(progress_msg, f"✅ **[Bot Prime]** Reenvío completado. Se reenviaron {sent_count} videos sin código y se eliminaron los originales.")
        else:
            await safe_edit_status(progress_msg, f"⚠️ **[Bot Prime]** Reenvío finalizado. Se procesaron {sent_count} de {total_videos} videos exitosamente.")
            
        await asyncio.sleep(8)
        await progress_msg.delete()
            
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error al escanear: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
