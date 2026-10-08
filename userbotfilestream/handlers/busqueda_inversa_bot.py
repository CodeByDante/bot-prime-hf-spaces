import asyncio
import time
import re
from telethon import events
from telethon.tl.types import DocumentAttributeVideo, InputMessagesFilterVideo, InputMessagesFilterDocument
from core.client import client
from utils.helpers import safe_edit_status

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

def get_video_info(msg):
    duration = None
    size = None
    
    doc = getattr(msg, 'video', None) or getattr(msg, 'document', None)
    if doc:
        size = doc.size
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeVideo):
                duration = attr.duration
                break
    if not duration and msg.file and msg.file.duration:
        duration = msg.file.duration
    return duration, size

def get_video_filename(msg):
    if not msg:
        return None
    if msg.document:
        for attr in msg.document.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                return attr.file_name
    if msg.file and msg.file.name:
        return msg.file.name
    return None

def clean_filename(name):
    if not name:
        return ""
    # Quitar extensión (.mp4, .mkv, etc.)
    name = re.sub(r'\.[a-zA-Z0-9]+$', '', name)
    # Quitar caracteres especiales
    name = re.sub(r'[^a-zA-Z0-9ñÑáéíóúÁÉÍÓÚ]', ' ', name)
    return name.strip().lower()

async def buscar_en_bot(bot, size, duration, target_filename, progress_dict):
    filters = [InputMessagesFilterVideo, InputMessagesFilterDocument]
    scanned_msgs = 0
    scanned_videos = 0
    
    for filter_type in filters:
        offset_id = 0
        while True:
            try:
                # Obtener lote de 1000 mensajes de una sola vez
                messages = await client.get_messages(bot, limit=1000, offset_id=offset_id, filter=filter_type)
                if not messages:
                    break
                
                scanned_msgs += len(messages)
                
                # Procesar el lote en memoria
                for m in messages:
                    if is_video_message(m):
                        scanned_videos += 1
                        m_duration, m_size = get_video_info(m)
                        m_filename = get_video_filename(m)
                        
                        # Criterio 1: Peso y duración
                        size_dur_match = False
                        if size and m_size == size:
                            if duration is None and m_duration is None:
                                size_dur_match = True
                            elif duration is not None and m_duration is not None:
                                if abs(int(duration) - int(m_duration)) <= 1:
                                    size_dur_match = True
                                    
                        # Criterio 2: Nombre de archivo
                        name_match = False
                        if target_filename and m_filename:
                            t_clean = clean_filename(target_filename)
                            c_clean = clean_filename(m_filename)
                            if len(t_clean) > 4 and t_clean == c_clean:
                                name_match = True
                                
                        if size_dur_match or name_match:
                            progress_dict[bot] = {"msgs": scanned_msgs, "videos": scanned_videos, "status": "Encontrado"}
                            return (bot, m, size_dur_match, name_match)
                
                # Actualizar progreso en el dict
                progress_dict[bot] = {"msgs": scanned_msgs, "videos": scanned_videos, "status": "Buscando..."}
                
                # Establecer offset_id para el siguiente lote
                offset_id = messages[-1].id
                
            except Exception as e:
                print(f"⚠️ [Búsqueda Inversa] Error en {bot} con {filter_type.__name__}: {e}")
                progress_dict[bot] = {"msgs": scanned_msgs, "videos": scanned_videos, "status": f"Error: {e}"}
                break
                
    progress_dict[bot] = {"msgs": scanned_msgs, "videos": scanned_videos, "status": "Completado"}
    return None

async def procesar_comando_busqueda_inversa_bot(event):
    chat_id = event.chat_id
    
    # 1. Determinar el video objetivo (target)
    target_msg = None
    
    # Caso A: Es una respuesta a otro mensaje
    if event.message.is_reply:
        target_msg = await event.get_reply_message()
        
    # Caso B: El comando está en la descripción del propio mensaje
    if not target_msg or not is_video_message(target_msg):
        if is_video_message(event.message):
            target_msg = event.message

    # Si no se encontró un video válido, informar al usuario
    if not target_msg or not is_video_message(target_msg):
        error_msg = await event.reply(
            "❌ **[Bot Prime]** El comando `/busqueda_inversa_bot` debe usarse respondiendo a un video o en la descripción de un video."
        )
        await asyncio.sleep(8)
        try:
            await client.delete_messages(chat_id, [event.id, error_msg.id])
        except Exception:
            pass
        return

    # 2. Obtener peso, duración y nombre del video objetivo
    duration, size = get_video_info(target_msg)
    target_filename = get_video_filename(target_msg)
    
    if not size and not target_filename:
        error_msg = await event.reply("❌ **[Bot Prime]** No se pudo obtener información del video para la búsqueda.")
        await asyncio.sleep(8)
        try:
            await client.delete_messages(chat_id, [event.id, error_msg.id])
        except Exception:
            pass
        return

    # 3. Notificar inicio de la búsqueda
    desc_video = f"Peso: {format_size(size) if size else 'Desconocido'} | Duración: {format_duration(duration) if duration else 'Desconocida'}"
    if target_filename:
        desc_video += f" | Archivo: `{target_filename}`"
        
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Iniciando búsqueda inversa optimizada (Lotes de 1000)...\n({desc_video})")
    
    target_bots = ["@waifuofbrodybot", "@waifuofdanteb2Bot", "@waifuofdanteBot"]
    progress_dict = {bot: {"msgs": 0, "videos": 0, "status": "Conectando..."} for bot in target_bots}
    
    # Tarea en segundo plano para actualizar el mensaje de estado cada 4 segundos
    async def update_status_loop():
        while True:
            await asyncio.sleep(4)
            status_text = f"🔍 **[Bot Prime]** Buscando coincidencia de video en paralelo (Lotes de 1000)...\n"
            status_text += f"({desc_video})\n\n"
            for b in target_bots:
                diag = progress_dict[b]
                status_text += f"• **{b}**: `{diag['msgs']}` leídos, `{diag['videos']}` videos ({diag['status']})\n"
            try:
                await safe_edit_status(status_msg, status_text)
            except Exception:
                pass
                
    updater_task = asyncio.create_task(update_status_loop())
    
    try:
        # 4. Ejecutar las búsquedas en paralelo (concurrentemente)
        search_tasks = [buscar_en_bot(bot, size, duration, target_filename, progress_dict) for bot in target_bots]
        results = await asyncio.gather(*search_tasks)
        
        # Cancelar el actualizador de estado
        updater_task.cancel()
        
        # Filtrar los resultados no nulos (coincidencias encontradas)
        found_matches = [r for r in results if r is not None]
        
        # 5. Procesar los resultados
        if found_matches:
            # Reenviar a Mensajes Guardados ('me') y enviar confirmación
            for bot, match_msg, s_match, n_match in found_matches:
                try:
                    await client.forward_messages('me', match_msg)
                    
                    match_reason = []
                    if s_match:
                        match_reason.append("Coincidencia de peso/tiempo")
                    if n_match:
                        match_reason.append("Coincidencia de nombre de archivo")
                        
                    reason_str = " + ".join(match_reason)
                    m_filename = get_video_filename(match_msg) or "Desconocido"
                    
                    await client.send_message(
                        'me',
                        f"🤖 **[Búsqueda Inversa]** Coincidencia encontrada en {bot}\n"
                        f"• **Razón:** {reason_str}\n"
                        f"• **Archivo:** `{m_filename}`\n"
                        f"• **Peso:** {format_size(match_msg.document.size) if match_msg.document else 'Desconocido'}\n"
                        f"• **ID de Mensaje:** `{match_msg.id}`"
                    )
                except Exception as fe:
                    print(f"⚠️ Error al reenviar a Mensajes Guardados: {fe}")
            
            # Mostrar resumen de éxito en el chat de origen
            summary = f"✅ **[Bot Prime]** ¡Búsqueda completada! Coincidencias encontradas y reenviadas a Mensajes Guardados:\n\n"
            for bot, _, s_m, n_m in found_matches:
                type_m = "peso/tiempo" if s_m and not n_m else ("nombre" if n_m and not s_m else "peso + nombre")
                summary += f"• **{bot}** (Encontrado por {type_m})\n"
            
            # Añadir diagnósticos de escaneo
            summary += "\n📊 **Resumen del escaneo por lotes (1000 msgs):**\n"
            for b in target_bots:
                diag = progress_dict[b]
                summary += f"• {b}: `{diag['msgs']}` leídos, `{diag['videos']}` videos ({diag['status']})\n"
                
            await safe_edit_status(status_msg, summary)
            
        else:
            # Mostrar reporte si no hubo coincidencias
            fail_msg = f"❌ **[Bot Prime]** No se encontró coincidencia para el video ({desc_video}).\n\n📊 **Resumen del escaneo por lotes (1000 msgs):**\n"
            for b in target_bots:
                diag = progress_dict[b]
                fail_msg += f"• {b}: `{diag['msgs']}` leídos, `{diag['videos']}` videos ({diag['status']})\n"
                
            await safe_edit_status(status_msg, fail_msg)
            
        # Limpieza de mensajes del canal después de unos segundos
        await asyncio.sleep(20)
        try:
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
            
    except Exception as e:
        updater_task.cancel()
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error general en la búsqueda: {e}")
            await asyncio.sleep(15)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
