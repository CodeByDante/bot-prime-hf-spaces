import asyncio
import time
from telethon import events
from telethon.errors import FloodWaitError
from telethon.tl.types import PeerChannel
from core.client import client
from utils.helpers import get_message_title, safe_edit_status

from utils.channel_resolver import get_registered_id


async def procesar_eliminador_definitivo(event):
    chat_id = event.chat_id
    
    # Parse scan limit (default None to scan everything)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    limit_desc = f"en los últimos {limit} mensajes del canal" if limit else "en todo el historial del canal"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Iniciando /eliminador_definitivo {limit_desc}...")
    
    try:
        # 1. Buscar el canal de origen "Twisted Short cuckold bbc"
        await safe_edit_status(status_msg, "🔍 **[Bot Prime]** Buscando el canal de origen 'Twisted Short cuckold bbc'...")
        target_channel = None
        reg_id = get_registered_id("twisted_short")
        if reg_id:
            try:
                target_channel = await client.get_entity(PeerChannel(channel_id=int(str(reg_id).replace("-100", ""))))
            except Exception:
                pass
                
        if not target_channel:
            # Fallback a buscar por nombre
            async for dialog in client.iter_dialogs():
                if dialog.is_channel and dialog.name and dialog.name.lower() == "twisted short cuckold bbc":
                    target_channel = dialog.entity
                    break

                
        if not target_channel:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontró el canal de origen 'Twisted Short cuckold bbc' en tus chats. Asegúrate de estar unido a él.")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return

        # 2. Escanear mensajes en el canal actual para identificar los reenviados del canal origen
        await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Escaneando mensajes en este canal para identificar reenviados de '{target_channel.title}'...")
        
        matching_messages = []
        last_update = time.time()
        
        async for m in client.iter_messages(chat_id, limit=limit):
            if m.fwd_from and m.fwd_from.from_id:
                # Comprobar si proviene de un PeerChannel y coincide con el ID
                from_peer = m.fwd_from.from_id
                if isinstance(from_peer, PeerChannel):
                    if from_peer.channel_id == target_channel.id:
                        if m.fwd_from.channel_post:
                            matching_messages.append(m)
                            
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando canal... (encontrados {len(matching_messages)} elementos de '{target_channel.title}')")
                last_update = now

        if not matching_messages:
            await safe_edit_status(status_msg, f"✅ **[Bot Prime]** No se encontraron mensajes reenviados de '{target_channel.title}' en este canal.")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return

        # Obtener los títulos de los videos y eliminar duplicados de IDs
        deleted_titles = []
        seen_ids = set()
        for m in matching_messages:
            post_id = m.fwd_from.channel_post
            if post_id not in seen_ids:
                seen_ids.add(post_id)
                title = get_message_title(m) or f"Mensaje ID {post_id}"
                deleted_titles.append(title)

        original_ids = list(seen_ids)
        total_to_delete = len(original_ids)
        
        await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Encontrados {total_to_delete} mensajes únicos para eliminar en el origen. Iniciando borrado por lotes...")
        await asyncio.sleep(2)

        # 3. Eliminar los mensajes originales en el canal de origen de 100 en 100
        total_deleted = 0
        batch_size = 100
        
        for i in range(0, total_to_delete, batch_size):
            chunk = original_ids[i:i + batch_size]
            retries = 3
            while retries > 0:
                try:
                    await client.delete_messages(target_channel, chunk)
                    total_deleted += len(chunk)
                    break
                except FloodWaitError as e:
                    print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos para eliminar en origen...")
                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} segundos...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"❌ Error al borrar mensajes en canal origen: {e}")
                    retries -= 1
                    if retries == 0:
                        break
                    await asyncio.sleep(2)

            await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Eliminando en origen: {total_deleted}/{total_to_delete} completados...")
            await asyncio.sleep(1.0)

        # Generar reporte final con los títulos eliminados
        report = f"✅ **[Bot Prime]** Proceso completado. Se eliminaron {total_deleted} videos originales de '{target_channel.title}':\n\n"
        for title in deleted_titles[:30]:
            report += f"• {title}\n"
        if len(deleted_titles) > 30:
            report += f"• ... y {len(deleted_titles) - 30} videos más.\n"

        await safe_edit_status(status_msg, report)
        await asyncio.sleep(15)
        await client.delete_messages(chat_id, [event.id, status_msg.id])

    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error durante el proceso: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass

async def procesar_eliminador_definitivo_prime(event):
    chat_id = event.chat_id
    
    # Parse scan limit (default None to scan everything)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    limit_desc = f"en los últimos {limit} mensajes del canal" if limit else "en todo el historial del canal"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Iniciando /eliminador_definitivo_prime {limit_desc}...")
    
    try:
        await safe_edit_status(status_msg, "🔍 **[Bot Prime]** Escaneando el canal para identificar todos los mensajes reenviados...")
        
        matching_messages = []
        deletions_by_channel = {}
        deleted_titles_by_channel = {}
        last_update = time.time()
        
        async for m in client.iter_messages(chat_id, limit=limit):
            if m.fwd_from and m.fwd_from.from_id:
                from_peer = m.fwd_from.from_id
                if isinstance(from_peer, PeerChannel):
                    src_channel_id = from_peer.channel_id
                    original_msg_id = m.fwd_from.channel_post
                    if original_msg_id:
                        if src_channel_id not in deletions_by_channel:
                            deletions_by_channel[src_channel_id] = set()
                            deleted_titles_by_channel[src_channel_id] = []
                        
                        if original_msg_id not in deletions_by_channel[src_channel_id]:
                            deletions_by_channel[src_channel_id].add(original_msg_id)
                            title = get_message_title(m) or f"Mensaje ID {original_msg_id}"
                            deleted_titles_by_channel[src_channel_id].append(title)
                            matching_messages.append(m)
                            
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando canal... (encontrados {len(matching_messages)} elementos reenviados de otros canales)")
                last_update = now

        if not matching_messages:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron mensajes reenviados en este canal.")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return

        total_to_delete = sum(len(ids) for ids in deletions_by_channel.values())
        await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Encontrados {total_to_delete} mensajes reenviados. Iniciando borrado por lotes en sus respectivos canales...")
        await asyncio.sleep(2)

        total_deleted = 0
        for src_channel_id, msg_ids in deletions_by_channel.items():
            msg_ids_list = list(msg_ids)
            try:
                channel_entity = await client.get_entity(PeerChannel(channel_id=src_channel_id))
                channel_name = channel_entity.title
            except Exception:
                channel_name = f"Canal ID {src_channel_id}"

            await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Eliminando {len(msg_ids_list)} mensajes originales en '{channel_name}'...")
            
            # Borrar en lotes de 100
            for i in range(0, len(msg_ids_list), 100):
                chunk = msg_ids_list[i:i + 100]
                retries = 3
                while retries > 0:
                    try:
                        await client.delete_messages(PeerChannel(channel_id=src_channel_id), chunk)
                        total_deleted += len(chunk)
                        break
                    except FloodWaitError as e:
                        print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos para eliminar en origen...")
                        await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} segundos...")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"❌ Error al borrar en origen {src_channel_id}: {e}")
                        retries -= 1
                        if retries == 0:
                            break
                        await asyncio.sleep(2)
                await asyncio.sleep(1.0)

        # Generar reporte final con los títulos y canales correspondientes
        report = f"✅ **[Bot Prime]** Proceso completado. Se eliminaron {total_deleted} mensajes en total en sus canales de origen:\n\n"
        flat_deleted_titles = []
        
        for src_channel_id, titles in deleted_titles_by_channel.items():
            try:
                channel_entity = await client.get_entity(PeerChannel(channel_id=src_channel_id))
                channel_name = channel_entity.title
            except Exception:
                channel_name = f"Canal ID {src_channel_id}"
                
            for t in titles:
                flat_deleted_titles.append(f"• {t} (de '{channel_name}')")

        for item in flat_deleted_titles[:30]:
            report += f"{item}\n"
        if len(flat_deleted_titles) > 30:
            report += f"• ... y {len(flat_deleted_titles) - 30} mensajes más.\n"

        await safe_edit_status(status_msg, report)
        await asyncio.sleep(15)
        await client.delete_messages(chat_id, [event.id, status_msg.id])

    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error durante el proceso: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
