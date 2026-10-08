import asyncio
import time
import re
from telethon import events
from telethon.errors import FloodWaitError
from core.client import client, config
from utils.helpers import safe_edit_status
from utils.database import DB

def es_titulo_por_defecto(text):
    if not text or not text.strip():
        return True
    text = text.strip()
    if text.startswith("Video #") or text.startswith("Imagen #"):
        return True
    # Coincide con patrones como "v 5565051026 1781829318 7459"
    if re.match(r'^v\s+\d+\s+\d+\s+\d+$', text):
        return True
    if re.match(r'^photo_\d+$', text):
        return True
    return False

async def procesar_comando_restaurar_actriz(event):
    chat_id = str(event.chat_id)
    
    # Solo permitir en canales o grupos
    if event.is_private:
        await event.reply("❌ **[Bot Prime]** Este comando solo puede ser ejecutado dentro de un canal o grupo.")
        return

    # Parse scanning limit (optional)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    BACKUP_CHANNEL_ID = config.get("backup_channel_id")
    if not BACKUP_CHANNEL_ID:
        await event.reply("❌ **[Bot Prime]** No se encuentra configurado 'backup_channel_id' en config.json")
        return

    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Iniciando restauración de actrices desde el canal de respaldo en {limit_desc}...")
    
    try:
        # 1. Obtener datos actuales del canal en la base de datos
        channel_data = await DB.get_channel_data(chat_id)
        if not channel_data or "videos" not in channel_data:
            alt_chat_id = chat_id.replace("-100", "") if chat_id.startswith("-100") else f"-100{chat_id}"
            channel_data = await DB.get_channel_data(alt_chat_id)

        if not channel_data:
            channel_data = {
                "channel_title": getattr(await event.get_chat(), 'title', 'Canal Privado'),
                "username": getattr(await event.get_chat(), 'username', None),
                "videos": []
            }

        videos = channel_data.get("videos", [])
        video_by_id = {v["id"]: v for v in videos}

        # Soportar usernames o enteros puros con o sin -100
        chat_id_str = str(chat_id)
        if not chat_id_str.startswith("-100") and chat_id_str.lstrip("-").isdigit():
            chat_id_int = int(f"-100{chat_id_str.lstrip('-')}")
        else:
            chat_id_int = int(chat_id_str) if chat_id_str.lstrip("-").isdigit() else chat_id_str

        # 2. Escanear mensajes en Telegram
        restored_count = 0
        total_analyzed = 0
        db_updated = False
        
        await safe_edit_status(status_msg, "⚙️ **[Bot Prime]** Escaneando mensajes y comparando con el canal de respaldo...")
        await asyncio.sleep(1)

        async for m in client.iter_messages(event.chat_id, limit=limit):
            total_analyzed += 1
            
            # Obtener el ID del mensaje respaldado
            video_key = f"video_{chat_id_int}_{m.id}"
            backup_id = await DB.get_backup_msg_id(video_key)
            
            if backup_id:
                current_text = m.message or ""
                
                # Si el mensaje actual tiene un título por defecto o está vacío, intentamos restaurar
                if es_titulo_por_defecto(current_text):
                    # Obtener el mensaje original del canal de respaldo
                    try:
                        backup_msg = await client.get_messages(BACKUP_CHANNEL_ID, ids=backup_id)
                        if backup_msg and backup_msg.message and backup_msg.message.strip():
                            original_caption = backup_msg.message.strip()
                            
                            # Editar mensaje en el canal origen para restaurar la descripción
                            retries = 3
                            while retries > 0:
                                try:
                                    await client.edit_message(event.chat_id, m.id, text=original_caption)
                                    restored_count += 1
                                    
                                    # Actualizar también la base de datos local/Firebase
                                    if m.id in video_by_id:
                                        video_by_id[m.id]["title"] = original_caption
                                        db_updated = True
                                    break
                                except FloodWaitError as e:
                                    print(f"[FloodWait] Esperando {e.seconds}s en restauración...")
                                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite de velocidad. Esperando {e.seconds}s...")
                                    await asyncio.sleep(e.seconds + 2)
                                except Exception as e:
                                    print(f"[Restore Error] Error al editar mensaje {m.id}: {e}")
                                    retries -= 1
                                    if retries == 0:
                                        break
                                    await asyncio.sleep(2)
                                    
                            await asyncio.sleep(1.0) # Retardo seguro para no saturar
                    except Exception as e:
                        print(f"[Restore Error] Error al leer el mensaje de respaldo {backup_id}: {e}")
                        
            if total_analyzed % 20 == 0:
                await safe_edit_status(
                    status_msg, 
                    f"⚙️ **[Bot Prime]** Progreso: {total_analyzed} analizados. Restaurados: {restored_count} descripciones..."
                )

        # 3. Guardar cambios en la base de datos si hubo actualizaciones de títulos
        if db_updated:
            channel_data["videos"] = list(video_by_id.values())
            await DB.save_channel_data(chat_id, channel_data)
            print("[Restore DB] Catálogo y base de datos actualizados con los títulos restaurados.")

        await safe_edit_status(
            status_msg, 
            f"✅ **[Bot Prime] Restauración completa.**\n\n"
            f"• Mensajes analizados: {total_analyzed}\n"
            f"• Descripciones restauradas desde respaldo: {restored_count}"
        )
        await asyncio.sleep(8)
        await client.delete_messages(event.chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        print(f"[Restore Error] {e}")
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error durante la restauración: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(event.chat_id, [event.id, status_msg.id])
        except Exception:
            pass
