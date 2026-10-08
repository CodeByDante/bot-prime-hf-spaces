import os
import sys
import json
import shutil
import tempfile
import asyncio
import subprocess
import logging
from collections import defaultdict
from telethon import TelegramClient, events

# Silenciar las advertencias de conexión de Telethon para evitar ruido en la consola
logging.basicConfig(level=logging.ERROR)
logging.getLogger('telethon').setLevel(logging.ERROR)

# Resolver la ruta del directorio base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# Intentar cargar credenciales desde variables de entorno primero
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
bot_token = os.environ.get("BOT_TOKEN")

# Si no están en el entorno, buscar en config.json
if not API_ID or not API_HASH:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
            API_ID = API_ID or config.get("api_id")
            API_HASH = API_HASH or config.get("api_hash")
            bot_token = bot_token or config.get("bot_token")
        except Exception as e:
            print(f"[Advertencia] No se pudo leer config.json: {e}")
    else:
        print(f"[Info] config.json no encontrado en {CONFIG_PATH}. Esperando variables de entorno.")

if not API_ID or not API_HASH:
    print("\033[91m[Error] API_ID y API_HASH no configurados en variables de entorno ni en config.json.\033[0m")
    sys.exit(1)

# Asegurar tipos correctos
API_ID = int(API_ID)

# Crear cliente con la sesión llamada "sesion"
client = TelegramClient(os.path.join(BASE_DIR, "sesion"), API_ID, API_HASH)

# Importar las funciones rápidas de descarga/subida
from fast_telethon import download_file, upload_file

# Estructuras de datos para control de descargas y colas
video_queues = defaultdict(list)
processing_chats = set()
queue_status_msgs = {}
chat_locks = defaultdict(asyncio.Lock)

# Rastrear tareas activas y carpetas temporales para posibilitar la cancelación
active_tasks = {}
active_temp_dirs = set()

# Semáforo global: máximo 2 descargas simultáneas en paralelo para evitar desconexiones de Telegram
# (2 descargas simultáneas * 8 conexiones por archivo = 16 conexiones totales, límite estable de la API)
global_download_semaphore = asyncio.Semaphore(2)

# Semáforo global para normalización con FFmpeg: máximo 2 conversiones simultáneas para evitar saturación de CPU y OOM
global_normalize_semaphore = asyncio.Semaphore(2)


def get_video_metadata(file_path):
    """Obtiene la anchura, altura y duración de un video usando ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-show_entries', 'format=duration',
            '-of', 'json',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            width = data['streams'][0].get('width', 0) if data.get('streams') else 0
            height = data['streams'][0].get('height', 0) if data.get('streams') else 0
            duration = int(float(data['format'].get('duration', 0))) if data.get('format') else 0
            return width, height, duration
    except Exception as e:
        print(f"[Advertencia] No se pudo obtener metadatos con ffprobe: {e}")
    return 0, 0, 0


def has_audio_stream(file_path):
    """Retorna True si el video tiene pista de audio."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'a',
            '-show_entries', 'stream=codec_type',
            '-of', 'json',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return len(data.get('streams', [])) > 0
    except Exception as e:
        print(f"[Advertencia] Error al verificar audio en ffprobe: {e}")
    return False


def extract_thumbnail(video_path, duration, temp_dir):
    """Extrae una miniatura del video en el segundo/minuto especificado (minuto 5 si es posible)."""
    thumb_path = os.path.join(temp_dir, "thumb.jpg")
    # Si dura más de 5 minutos (300s), extraer del minuto 5 (300s)
    # De lo contrario, si dura más de 5s, extraer del segundo 5 (5s)
    # Si no, de la mitad del video
    if duration > 300:
        ss = 300
    elif duration > 5:
        ss = 5
    else:
        ss = duration / 2
        
    try:
        cmd = [
            'ffmpeg', '-y', 
            '-ss', str(ss), 
            '-i', video_path, 
            '-vframes', '1', 
            '-q:v', '2', 
            thumb_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(thumb_path):
            return thumb_path
    except Exception as e:
        print(f"[Advertencia] No se pudo extraer la miniatura: {e}")
    return None


async def check_permissions(event) -> bool:
    """Retorna True si el mensaje viene del propio usuario o si el cliente corre como Bot."""
    is_bot = await client.is_bot()
    if is_bot:
        return True
    
    # Userbot: solo responder a mensajes salientes de nosotros mismos
    if not event.out:
        me = await event.client.get_me()
        sender = await event.get_sender()
        if not sender or sender.id != me.id:
            return False
    return True


async def process_merge(chat_id, event, queue):
    """Ejecuta el proceso de descarga, mezcla y subida de la lista de videos dada."""
    # Rastrear la tarea para permitir su cancelación
    active_tasks[chat_id] = asyncio.current_task()
    
    processing_chats.add(chat_id)
    
    print(f"\n\033[94m[Proceso] Iniciando proceso de unión para el chat {chat_id}. Total: {len(queue)} videos.\033[0m")
    status_msg = await event.reply(
        f"⏳ **[1/4] Reconocidos {len(queue)} videos en cola.**\n"
        "Iniciando descargas en paralelo... (8 hilos por video)"
    )
    temp_dir = tempfile.mkdtemp(prefix=f"merge_{chat_id}_")
    active_temp_dirs.add(temp_dir)
    print(f"[Proceso] Directorio temporal creado: {temp_dir}")

    try:
        tasks = []
        download_progress = {}
        last_edit_time = 0
        edit_lock = asyncio.Lock()

        async def update_status_text():
            nonlocal last_edit_time
            now = asyncio.get_event_loop().time()
            if now - last_edit_time < 2.0:
                return
            
            async with edit_lock:
                now = asyncio.get_event_loop().time()
                if now - last_edit_time < 2.0:
                    return
                last_edit_time = now
                
                lines = []
                for i in range(len(queue)):
                    pct = download_progress.get(i, 0)
                    lines.append(f"📥 **Video {i+1}:** `{pct}%`" if pct < 100 else f"✅ **Video {i+1}:** `Completado`")
                
                status_text = (
                    f"⏳ **[1/4] Descargando {len(queue)} videos en paralelo...**\n\n"
                    + "\n".join(lines)
                )
                try:
                    await status_msg.edit(status_text)
                except Exception:
                    pass

        async def download_task(msg, idx):
            file_name = msg.file.name or f"video_{idx}.mp4"
            file_size_mb = msg.file.size / (1024 * 1024)
            temp_file_name = f"part_{idx:03d}_{file_name}"
            out_path = os.path.join(temp_dir, temp_file_name)

            print(f"\033[93m[Descarga] Video {idx + 1}/{len(queue)}: '{file_name}' ({file_size_mb:.2f} MB) en espera...\033[0m")
            download_progress[idx] = 0

            last_percent = -1
            async def progress_callback(current, total):
                nonlocal last_percent
                if not total:
                    return
                percent = int(current * 100 / total)
                if percent != last_percent and percent % 10 == 0:
                    last_percent = percent
                    download_progress[idx] = percent
                    await update_status_text()
                    print(f" -> [Progreso] Video {idx + 1}/{len(queue)}: {percent}% descargado ({current}/{total} bytes)")

            # Adquirir semáforo (máximo 5 descargas simultáneas en paralelo)
            async with global_download_semaphore:
                print(f"\033[92m[Descarga] Iniciando descarga activa de Video {idx + 1}/{len(queue)}: '{file_name}'\033[0m")
                with open(out_path, "wb") as out_file:
                    # Descargar usando 8 hilos/conexiones por video
                    await download_file(
                        client,
                        msg,
                        out_file,
                        progress_callback=progress_callback,
                        connection_count=8
                    )

            print(f"\033[92m[Descarga] Video {idx + 1}/{len(queue)} completado: '{file_name}'\033[0m")
            download_progress[idx] = 100
            
            # Forzar actualización al terminar este archivo
            try:
                async with edit_lock:
                    lines = []
                    for i in range(len(queue)):
                        pct = download_progress.get(i, 0)
                        lines.append(f"📥 **Video {i+1}:** `{pct}%`" if pct < 100 else f"✅ **Video {i+1}:** `Completado`")
                    status_text = (
                        f"⏳ **[1/4] Descargando {len(queue)} videos en paralelo...**\n\n"
                        + "\n".join(lines)
                    )
                    await status_msg.edit(status_text)
            except Exception:
                pass

            return out_path

        # Inicializar el progreso de todos los videos en 0%
        for i in range(len(queue)):
            download_progress[i] = 0

        # Forzar el primer dibujo de la lista en Telegram de inmediato para que no se quede congelado
        lines = []
        for i in range(len(queue)):
            lines.append(f"📥 **Video {i+1}:** `0%`")
        status_text = (
            f"⏳ **[1/4] Descargando {len(queue)} videos en paralelo...**\n\n"
            + "\n".join(lines)
        )
        try:
            await status_msg.edit(status_text)
        except Exception:
            pass

        # Crear tareas en el orden en que fueron recibidos
        for idx, msg in enumerate(queue):
            tasks.append(download_task(msg, idx))

        # Descargar concurrentemente los videos
        downloaded_paths = await asyncio.gather(*tasks)
        print("[Proceso] Todas las descargas concurrentes han finalizado con éxito.")

        # Iniciar normalización y unión con FFmpeg
        await status_msg.edit(f"⚙️ **[2/4] Normalizando {len(queue)} videos en paralelo...**")
        print(f"\033[96m[Proceso] Iniciando normalización concurrente de {len(queue)} videos (ultrafast preset) para acelerar el procesamiento...\033[0m")

        async def normalize_task(p, idx):
            async with global_normalize_semaphore:
                norm_name = f"norm_{idx:03d}_{os.path.basename(p)}"
                norm_path = os.path.join(temp_dir, norm_name)
                
                print(f"[FFmpeg] Normalizando Video {idx+1}/{len(queue)}: {os.path.basename(p)}...")
                
                def check_audio():
                    return has_audio_stream(p)
                has_audio = await asyncio.to_thread(check_audio)
                
                def run_normalize():
                    # Forzar preset ultrafast para máxima velocidad de procesamiento en múltiples hilos
                    if has_audio:
                        cmd = [
                            'ffmpeg', '-y', '-i', p,
                            '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p',
                            '-r', '30',
                            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
                            '-c:a', 'aac', '-ar', '44100', '-ac', '2',
                            norm_path
                        ]
                    else:
                        cmd = [
                            'ffmpeg', '-y', '-i', p,
                            '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
                            '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p',
                            '-r', '30',
                            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
                            '-c:a', 'aac', '-ar', '44100', '-ac', '2',
                            '-shortest',
                            norm_path
                        ]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    return res.returncode, res.stderr
                
                retcode, stderr_output = await asyncio.to_thread(run_normalize)
                if retcode != 0:
                    print(f"\033[91m[FFmpeg Error] Error al normalizar {os.path.basename(p)}. Usando fallback de copia simple. Código: {retcode}. Detalles:\n{stderr_output}\033[0m")
                    shutil.copy(p, norm_path)
                else:
                    print(f"[FFmpeg] Video {idx+1}/{len(queue)} normalizado correctamente.")
                return norm_path

        # Crear y ejecutar tareas de normalización en paralelo
        normalize_tasks = [normalize_task(p, idx) for idx, p in enumerate(downloaded_paths)]
        normalized_paths = await asyncio.gather(*normalize_tasks)

        await status_msg.edit(f"⚙️ **[2/4] Mezclando {len(queue)} videos normalizados...**")
        print("\033[96m[FFmpeg] Escribiendo list.txt de concatenación para los videos normalizados...\033[0m")

        # Escribir list.txt para FFmpeg (nombres de archivos relativos en orden exacto)
        list_file_path = os.path.join(temp_dir, "list.txt")
        with open(list_file_path, "w", encoding="utf-8") as f:
            for p in normalized_paths:
                f.write(f"file '{os.path.basename(p)}'\n")

        output_name = "video_unido.mp4"
        output_path = os.path.join(temp_dir, output_name)

        # Función síncrona para ejecutar FFmpeg en un hilo y evitar NotImplementedError en Windows
        def run_ffmpeg():
            cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'list.txt', '-c', 'copy', output_name]
            result = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True)
            return result.returncode, result.stdout, result.stderr

        # Ejecutar FFmpeg de forma asíncrona mediante un hilo de fondo
        print("\033[96m[FFmpeg] Ejecutando concatenación en segundo plano...\033[0m")
        returncode, stdout, stderr = await asyncio.to_thread(run_ffmpeg)

        if returncode != 0:
            print(f"\033[91m[FFmpeg Error] FFmpeg falló. Código: {returncode}. Detalles:\n{stderr}\033[0m")
            await status_msg.edit(f"❌ **Error al unir videos:** FFmpeg falló.\n\nDetalles:\n`{stderr[:200]}`")
            return

        print("\033[92m[FFmpeg] Fusión completada con éxito. Archivo de salida creado.\033[0m")

        # Subir archivo final a Telegram
        await status_msg.edit("📤 **[3/4] Subiendo video final acelerado a Telegram...**")
        upload_progress_msg = await event.reply("📤 **Subiendo archivo final... 0%**")

        last_up_percent = -1
        async def upload_progress_callback(current, total):
            nonlocal last_up_percent
            if not total:
                return
            percent = int(current * 100 / total)
            if percent != last_up_percent and percent % 10 == 0:
                last_up_percent = percent
                try:
                    await upload_progress_msg.edit(f"📤 **Subiendo archivo final... {percent}%**")
                except Exception:
                    pass
                print(f" -> [Subida] Progreso de subida del video final: {percent}%")

        merged_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"\033[93m[Subida] Iniciando subida de video unido ({merged_size_mb:.2f} MB)...\033[0m")
        with open(output_path, "rb") as out_file:
            input_file = await upload_file(client, out_file, progress_callback=upload_progress_callback)

        print("\033[92m[Subida] Video subido con éxito a los servidores de Telegram.\033[0m")
        try:
            await upload_progress_msg.delete()
        except Exception:
            pass

        # Obtener metadatos del video final con ffprobe
        def get_meta():
            return get_video_metadata(output_path)
        
        print("[Proceso] Extrayendo metadatos del video unido con ffprobe...")
        width, height, duration = await asyncio.to_thread(get_meta)
        print(f"[Proceso] Metadatos obtenidos: ancho={width}, alto={height}, duración={duration}s")

        # Extraer miniatura del video (minuto 5 si es posible)
        def get_thumb():
            return extract_thumbnail(output_path, duration, temp_dir)
            
        print("[Proceso] Generando miniatura personalizada (minuto 5 o fallback)...")
        thumb_path = await asyncio.to_thread(get_thumb)
        if thumb_path:
            print(f"[Proceso] Miniatura generada con éxito: {thumb_path}")
        else:
            print("[Advertencia] No se pudo generar la miniatura, se enviará sin ella.")

        from telethon.tl.types import DocumentAttributeVideo
        video_attr = DocumentAttributeVideo(
            duration=duration,
            w=width,
            h=height,
            supports_streaming=True
        )

        # Enviar el mensaje final con el video unido, metadatos y miniatura
        await status_msg.edit("🎉 **[4/4] Enviando video final de forma optimizada...**")

        await client.send_file(
            chat_id,
            input_file,
            caption=f"🎬 **¡{len(queue)} videos unidos con éxito!**\n\n_Procesado usando Bot Unidor (8 hilos/descarga y mezcla directa)._",
            supports_streaming=True,
            thumb=thumb_path,
            attributes=[video_attr],
            reply_to=queue[0].id
        )

        await status_msg.delete()
        print(f"\033[92m[Proceso] ¡Unión completada y enviada al chat {chat_id}!\033[0m\n")

    except asyncio.CancelledError:
        print(f"\033[91m[Proceso] Proceso de unión en chat {chat_id} cancelado.\033[0m")
        try:
            await status_msg.edit("❌ **Unión cancelada y bot restablecido.**")
        except Exception:
            pass
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\033[91m[Error] Error crítico en process_merge: {e}\033[0m")
        try:
            await status_msg.edit(f"❌ **Ha ocurrido un error inesperado:**\n`{str(e)[:200]}`")
        except Exception:
            pass
    finally:
        print(f"[Proceso] Limpiando archivos temporales en {temp_dir}...")
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            print("[Proceso] Carpeta temporal eliminada.")
        except Exception as e:
            print(f"[Advertencia Error de Limpieza] No se pudo borrar el directorio temporal: {e}")
        active_temp_dirs.discard(temp_dir)
        if chat_id in processing_chats:
            processing_chats.remove(chat_id)
        active_tasks.pop(chat_id, None)


# Comando .sesion o /sesion o /start para comprobar estado del bot
@client.on(events.NewMessage(pattern=r'(?i)^[\./](sesio?n|start)'))
async def handle_sesion(event):
    if not await check_permissions(event):
        return

    chat_id = event.chat_id
    print(f"[Comando] Chat {chat_id}: Recibido comando de estado/sesión.")
    queue_len = len(video_queues[chat_id])
    is_bot = await client.is_bot()
    cmd_prefix = "/" if is_bot else "."
    
    msg_text = (
        "🟢 **[Bot Unidor] Sesión Activa**\n\n"
        "El bot de unión está funcionando y listo.\n"
        f"• **Videos actualmente en cola:** `{queue_len}`\n\n"
        "**Instrucciones:**\n"
        "1. Envía o reenvía los videos que quieras unir a este chat (en el orden que desees).\n"
        "2. Se descargarán simultáneamente (hasta 5 a la vez, con 8 hilos cada uno).\n"
        f"3. Escribe `{cmd_prefix}unir` para iniciar la descarga y unión de todos los videos.\n\n"
        f"• Usa `{cmd_prefix}limpiar` para vaciar la cola actual.\n"
        f"• Usa `{cmd_prefix}cancelar` para abortar cualquier unión activa y reiniciar el bot."
    )
    await event.reply(msg_text)


# Comando .limpiar o /limpiar para vaciar la cola de videos
@client.on(events.NewMessage(pattern=r'(?i)^[\./]limpiar'))
async def handle_limpiar(event):
    if not await check_permissions(event):
        return

    chat_id = event.chat_id
    print(f"[Comando] Chat {chat_id}: Vaciando cola de videos.")
    video_queues[chat_id] = []
    
    # Eliminar mensaje de estado de cola previo si existe
    status_msg = queue_status_msgs.pop(chat_id, None)
    if status_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass
            
    await event.reply("🗑️ **Cola de videos limpiada para este chat.**")


# Comando .unir o /unir para iniciar manualmente la unión
@client.on(events.NewMessage(pattern=r'(?i)^[\./]unir'))
async def handle_unir(event):
    if not await check_permissions(event):
        return

    chat_id = event.chat_id
    print(f"[Comando] Chat {chat_id}: Recibido comando para unir videos.")
    if chat_id in processing_chats:
        await event.reply("⚠️ Ya hay una unión en proceso para este chat. Por favor espera a que termine.")
        return

    queue = video_queues[chat_id]
    if len(queue) < 2:
        print(f"[Advertencia] Chat {chat_id}: Intento de unión fallido. Cola insuficiente ({len(queue)} videos).")
        await event.reply(f"⚠️ Se necesitan al menos 2 videos en la cola para unir. Cola actual: `{len(queue)}` video(s)")
        return

    # Eliminar mensaje de estado de cola previo si existe antes de iniciar la mezcla
    status_msg = queue_status_msgs.pop(chat_id, None)
    if status_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass

    # Extraer snapshot de los videos en la cola y limpiarla INMEDIATAMENTE.
    queue_snapshot = list(queue)
    video_queues[chat_id] = []
    print(f"[Comando] Chat {chat_id}: Cola copiada y reseteada. Lanzando proceso para {len(queue_snapshot)} videos.")

    asyncio.create_task(process_merge(chat_id, event, queue_snapshot))


async def cancel_all_processing():
    """Cancela todos los procesos de descarga, normalización, fusión y subida activos."""
    print(f"\033[91m[Cancelación] Cancelando todas las tareas de unión activas ({len(active_tasks)})...\033[0m")
    
    # Cancelar las tareas de procesamiento
    for chat_id, task in list(active_tasks.items()):
        try:
            task.cancel()
            print(f"[Cancelación] Tarea de chat {chat_id} cancelada.")
        except Exception as e:
            print(f"[Error Cancelación] No se pudo cancelar la tarea del chat {chat_id}: {e}")
            
    active_tasks.clear()
    processing_chats.clear()
    video_queues.clear()
    
    # Eliminar los mensajes de estado anteriores de Telegram
    for chat_id, msg in list(queue_status_msgs.items()):
        try:
            await msg.delete()
        except Exception:
            pass
    queue_status_msgs.clear()
    
    # Borrar los directorios temporales de unión activos
    print(f"[Cancelación] Borrando {len(active_temp_dirs)} directorios temporales...")
    for temp_dir in list(active_temp_dirs):
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"[Cancelación] Carpeta temporal eliminada: {temp_dir}")
        except Exception as e:
            print(f"[Error Cancelación] No se pudo borrar {temp_dir}: {e}")
    active_temp_dirs.clear()


# Comando .cancelar o /cancelar para detener unión y reiniciar el bot
@client.on(events.NewMessage(pattern=r'(?i)^[\./]cancelar'))
async def handle_cancelar(event):
    if not await check_permissions(event):
        return

    chat_id = event.chat_id
    print(f"[Comando] Chat {chat_id}: Recibido comando para cancelar y reiniciar bot.")
    
    # Responder de inmediato en Telegram
    await event.reply("⏳ **Cancelando uniones activas y reiniciando el bot...**")
    
    # Detener las tareas y borrar archivos
    await cancel_all_processing()
    
    # Programar el reinicio del proceso en un segundo
    async def restart_process():
        await asyncio.sleep(1)
        try:
            await client.disconnect()
        except Exception:
            pass
        print("\033[95m[Reinicio] Re-ejecutando script de bot...\033[0m")
        os.execv(sys.executable, [sys.executable] + sys.argv)
        
    asyncio.create_task(restart_process())


# Listener general para capturar los videos enviados
@client.on(events.NewMessage)
async def handle_new_message(event):
    # Ignorar mensajes que son comandos
    if event.text and event.text.startswith(('.', '/')):
        return

    if not await check_permissions(event):
        return

    # Comprobar si el mensaje tiene un archivo de video
    if event.message.file and event.message.file.mime_type and event.message.file.mime_type.startswith('video/'):
        chat_id = event.chat_id
        file_name = event.message.file.name or "sin_nombre.mp4"
        size_mb = event.message.file.size / (1024 * 1024)

        # Adquirir el candado de este chat para serializar la recepción y evitar condiciones de carrera (envíos múltiples)
        async with chat_locks[chat_id]:
            if chat_id in processing_chats:
                await event.reply("⚠️ Ya hay una unión en proceso. Espera a que finalice antes de enviar más videos.")
                return

            queue = video_queues[chat_id]
            queue.append(event.message)
            print(f"\033[94m[Cola] Chat {chat_id}: Video '{file_name}' ({size_mb:.2f} MB) añadido. Total en cola: {len(queue)}\033[0m")

            is_bot = await client.is_bot()
            cmd_prefix = "/" if is_bot else "."

            # Construir resumen de la cola
            lines = []
            total_size = 0.0
            for i, msg in enumerate(queue):
                name = msg.file.name or f"video_{i+1}.mp4"
                sz = msg.file.size / (1024 * 1024)
                total_size += sz
                lines.append(f"• **Video {i+1}:** `{name}` ({sz:.2f} MB)")

            text = (
                f"📥 **Cola de videos en este chat: {len(queue)}**\n\n"
                + "\n".join(lines) + "\n\n"
                f"• **Tamaño total:** `{total_size:.2f} MB`\n"
                f"• Escribe `{cmd_prefix}unir` para iniciar la unión en orden."
            )

            # Si ya existe un mensaje de cola en el chat, lo editamos para no hacer spam
            old_msg = queue_status_msgs.get(chat_id)
            if old_msg:
                try:
                    await old_msg.edit(text)
                    return
                except Exception:
                    pass

            # Si no existe, enviamos uno nuevo y guardamos la referencia
            new_msg = await event.reply(text)
            queue_status_msgs[chat_id] = new_msg



async def main():
    print("\033[95m" + "=" * 60)
    print("            BOT UNIDOR DE VIDEOS: INICIADO")
    print("=" * 60 + "\033[0m")

    # Iniciar usando bot_token si está presente, de lo contrario iniciar como userbot
    if bot_token:
        print("\033[94m[Iniciando] Conectando como Bot de Telegram usando token...\033[0m")
        await client.start(bot_token=bot_token)
    else:
        print("\033[94m[Iniciando] Conectando como Userbot (requiere autenticación telefónica)...\033[0m")
        await client.start()

    is_bot = await client.is_bot()
    if is_bot:
        print("\033[92m[Bot] Conectado como Bot de Telegram.")
        # Configurar los comandos de acceso rápido en Telegram para el bot
        print("[Bot] Configurando comandos de acceso rápido en el menú de Telegram...")
        try:
            from telethon.tl.functions.bots import SetBotCommandsRequest
            from telethon.tl.types import BotCommand, BotCommandScopeDefault
            # Configuración para idioma español
            await client(SetBotCommandsRequest(
                scope=BotCommandScopeDefault(),
                lang_code="es",
                commands=[
                    BotCommand(command="start", description="Iniciar bot y ver instrucciones"),
                    BotCommand(command="sesion", description="Ver estado de la sesión y cola de videos"),
                    BotCommand(command="unir", description="Forzar unión de videos en cola"),
                    BotCommand(command="limpiar", description="Vaciar la cola de videos de este chat"),
                    BotCommand(command="cancelar", description="Detener unión y reiniciar el bot")
                ]
            ))
            # Configuración por defecto
            await client(SetBotCommandsRequest(
                scope=BotCommandScopeDefault(),
                lang_code="",
                commands=[
                    BotCommand(command="start", description="Iniciar bot y ver instrucciones"),
                    BotCommand(command="sesion", description="Ver estado de la sesión y cola de videos"),
                    BotCommand(command="unir", description="Forzar unión de videos en cola"),
                    BotCommand(command="limpiar", description="Vaciar la cola de videos de este chat"),
                    BotCommand(command="cancelar", description="Detener unión y reiniciar el bot")
                ]
            ))
            print("[Bot] Comandos de acceso rápido registrados correctamente.")
        except Exception as e:
            print(f"[Advertencia] No se pudieron configurar los comandos rápidos: {e}")

        print("[Bot] Esperando comandos (/sesion, /unir, /limpiar) o videos...\033[0m\n")
    else:
        print("\033[92m[Userbot] Conectado como Userbot con sesión 'sesion'.")
        print("[Userbot] Esperando comandos (.sesion, .unir, .limpiar) o videos...\033[0m\n")

    await client.run_until_disconnected()


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
