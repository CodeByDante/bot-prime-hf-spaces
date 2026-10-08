import os
import asyncio
import time
import zipfile
import shutil
import uuid
import re
import json
from PIL import Image
# Desactivar el límite de píxeles de Pillow para permitir imágenes extremadamente grandes sin error DecompressionBomb
Image.MAX_IMAGE_PIXELS = None

from pyrogram import Client, filters, ContinuePropagation
from pyrogram.types import Message, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiohttp import web

# Intentar importar la configuración desde config.py para mantener consistencia
try:
    import config
    API_ID = getattr(config, "API_ID", 33226415)
    API_HASH = getattr(config, "API_HASH", "01999dae3e5348c7ab0dbcc6f7f4edc5")
    BOT_TOKEN = getattr(config, "BOT_TOKEN", "8517308010:AAFNVBIH5Mo3m8htxZ6JvFkfwI-U0gZJKWg")
    OWNER_ID = getattr(config, "OWNER_ID", 5565051026)
    DEFAULT_CHANNEL = getattr(config, "DATABASE_CHANNEL", -1003824889674)
except ImportError:
    API_ID = 33226415
    API_HASH = "01999dae3e5348c7ab0dbcc6f7f4edc5"
    BOT_TOKEN = "8517308010:AAFNVBIH5Mo3m8htxZ6JvFkfwI-U0gZJKWg"
    OWNER_ID = 5565051026
    DEFAULT_CHANNEL = -1003824889674

SESSION_NAME = "mi_bot_zip"

# Configuración básica
app = Client(
    SESSION_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    max_concurrent_transmissions=10,
    sleep_threshold=1000  # Manejar FloodWaits automáticamente de hasta 1000 segundos
)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DOWNLOADS_DIR = os.path.join(DATA_DIR, "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(DATA_DIR, "bot_config.json")

def load_bot_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_bot_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        print(f"Error guardando configuración: {e}")

def get_database_channel():
    cfg = load_bot_config()
    # 1. Intentar cargar el canal guardado por comando
    channel = cfg.get("database_channel")
    if channel is not None:
        return channel
    
    # 2. Intentar cargar desde variables de entorno
    env_chan = os.getenv("DATABASE_CHANNEL") or os.getenv("DUMP_CHAT_ID")
    if env_chan:
        try:
            if env_chan.strip().startswith("@"):
                return env_chan.strip()
            return int(env_chan.strip())
        except ValueError:
            return env_chan.strip()
            
    # 3. Fallback al valor por defecto
    return DEFAULT_CHANNEL

def get_webp_quality():
    cfg = load_bot_config()
    return cfg.get("webp_quality", 80)

def get_webp_max_size():
    cfg = load_bot_config()
    return cfg.get("webp_max_size", None)

def propagate_peers():
    import sqlite3
    main_db = "mi_bot_zip.session"
    if not os.path.exists(main_db):
        return
            
    sessions_dir = os.path.join(DATA_DIR, "sessions")
    if not os.path.exists(sessions_dir):
        return
        
    try:
        conn_main = sqlite3.connect(main_db)
        cursor_main = conn_main.cursor()
        cursor_main.execute("SELECT id, access_hash, type, username, phone_number, last_update_on FROM peers")
        peers_to_copy = cursor_main.fetchall()
        conn_main.close()
    except Exception as e:
        print(f"Error leyendo peers de la base de datos principal: {e}")
        return
        
    if not peers_to_copy:
        return
        
    # Copiar a cada base de datos de worker
    for filename in os.listdir(sessions_dir):
        if filename.endswith(".session"):
            worker_db = os.path.join(sessions_dir, filename)
            try:
                conn_worker = sqlite3.connect(worker_db)
                cursor_worker = conn_worker.cursor()
                cursor_worker.executemany(
                    "INSERT OR REPLACE INTO peers (id, access_hash, type, username, phone_number, last_update_on) VALUES (?, ?, ?, ?, ?, ?)",
                    peers_to_copy
                )
                conn_worker.commit()
                conn_worker.close()
                print(f"✅ Sincronizados {len(peers_to_copy)} peers a {filename}")
            except Exception as e:
                print(f"Error copiando peers a {filename}: {e}")

# Sistemas de Control de Concurrencia
download_sem = asyncio.Semaphore(4)      # Máximo 4 descargas simultáneas
process_sem = asyncio.Semaphore(1)       # Solo 1 procesamiento de ZIP a la vez
image_processing_sem = asyncio.Semaphore(3)  # Máximo 3 imágenes procesándose/subiéndose en paralelo
conversion_sem = asyncio.Semaphore(1)            # Máximo 1 conversión WebP a la vez (CPU/RAM-heavy)

# Contadores globales para feedback visual
active_downloads = 0
tasks_in_queue = 0

class WorkerBotManager:
    def __init__(self, api_id, api_hash):
        self.api_id = api_id
        self.api_hash = api_hash
        self.clients = []
        self.current_index = 0
        self.tokens_file = os.path.join(DATA_DIR, "bot_tokens.json")

    async def start(self):
        import json
        if not os.path.exists(self.tokens_file):
            with open(self.tokens_file, "w", encoding="utf-8") as f:
                json.dump([], f)
        
        try:
            with open(self.tokens_file, "r", encoding="utf-8") as f:
                tokens = json.load(f)
        except Exception:
            tokens = []
        
        sessions_dir = os.path.join(DATA_DIR, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        
        for i, token in enumerate(tokens):
            if not token.strip(): continue
            session_path = os.path.join(sessions_dir, f"worker_{i}")
            client = Client(
                session_path,
                api_id=self.api_id,
                api_hash=self.api_hash,
                bot_token=token.strip(),
                max_concurrent_transmissions=10,
                sleep_threshold=1000
            )
            try:
                await client.start()
                self.clients.append(client)
                print(f"✅ Worker bot {i} iniciado de forma persistente y listo para enviar.")
            except Exception as e:
                print(f"❌ Error al iniciar worker {i}: {e}")

    async def stop(self):
        for client in self.clients:
            try:
                await client.stop()
            except:
                pass

    def get_next_client(self, fallback_client):
        all_clients = [fallback_client] + self.clients
        if self.current_index >= len(all_clients):
            self.current_index = 0
            
        client = all_clients[self.current_index]
        self.current_index = (self.current_index + 1) % len(all_clients)
        return client

worker_manager = WorkerBotManager(API_ID, API_HASH)


def format_bytes(size):
    # Formatea los bytes a una unidad legible (MB, KB, etc.)
    power = 2**10
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.1f} {power_labels[n]}"

async def safe_edit_text(message: Message, text: str):
    try:
        await asyncio.wait_for(message.edit_text(text), timeout=5)
    except Exception:
        pass

async def safe_delete_message(message: Message):
    try:
        await asyncio.wait_for(message.delete(), timeout=5)
    except Exception:
        pass

async def download_progress(current, total, message: Message, start_time, last_update_time):
    # Actualiza el mensaje cada 3 segundos para evitar FLOOD_WAIT
    now = time.time()
    if now - last_update_time[0] > 3.0 or current == total:
        last_update_time[0] = now
        percent = (current / total) * 100
        curr_str = format_bytes(current)
        total_str = format_bytes(total)
        await safe_edit_text(message, f"⬇️ Descargando 📁 `{curr_str} / {total_str} ({percent:.1f}%)`")

async def handle_task(message: Message, status_msg: Message):
    global active_downloads, tasks_in_queue
    tasks_in_queue += 1
    
    try:
        user_id = message.from_user.id
        file_id = message.document.file_id
        doc = message.document
        doc_name = doc.file_name if doc.file_name else "archivo_desconocido.zip"
        
        await safe_edit_text(status_msg, f"⏳ En cola de descarga... Estás en la posición #{tasks_in_queue} de todas las tareas.")
        
        max_retries = 3
        extraction_successful = False
        extract_path = ""
        download_path = None
        safe_file_name = ""
        
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                await safe_edit_text(status_msg, f"⚠️ Reintentando descarga y extracción... (Intento {attempt}/{max_retries})")
                await asyncio.sleep(2)
                
            # 1. Download with progress (Up to 4 concurrent)
            async with download_sem:
                active_downloads += 1
                start_time = time.time()
                last_update_time = [start_time]
                print(f"[{file_id}] ⬇️ Iniciando descarga... (Intento {attempt}/{max_retries})")
                await safe_edit_text(status_msg, f"⬇️ Iniciando descarga... (Intento {attempt}/{max_retries})")
                
                try:
                    download_path = await asyncio.wait_for(
                        app.download_media(
                            message,
                            file_name=os.path.join(DOWNLOADS_DIR, f"{file_id}.zip"),
                            progress=download_progress,
                            progress_args=(status_msg, start_time, last_update_time)
                        ),
                        timeout=600 # 10 minutos máximo
                    )
                except asyncio.TimeoutError:
                    download_path = None
                    print(f"[{file_id}] ❌ Timeout en descarga.")
                except Exception as e:
                    download_path = None
                    print(f"[{file_id}] ❌ Error en descarga: {e}")
                active_downloads -= 1
                
            if not download_path:
                if attempt == max_retries:
                    await safe_edit_text(status_msg, "❌ Error al descargar el archivo después de 3 intentos.")
                    return
                continue # Retry

            print(f"[{file_id}] ⏳ Descarga completada. En cola para procesamiento...")
            await safe_edit_text(status_msg, f"⏳ Descarga de `{doc_name}` completada. Esperando turno para extraer...")

            # 2. Extract (Sequential 1 by 1)
            async with process_sem:
                print(f"[{file_id}] 📂 Extrayendo archivos ZIP...")
                await safe_edit_text(status_msg, f"📂 Extrayendo archivos del zip `{doc_name}`...")
                
                if doc.file_name:
                    base_name = os.path.splitext(doc.file_name)[0]
                else:
                    base_name = "archivo_desconocido"
                
                # Limpiar caracteres no válidos para carpetas en Windows
                safe_file_name = re.sub(r'[\\/*?:"<>|]', "", base_name).strip()
                if not safe_file_name:
                    safe_file_name = "archivo"

                # Crear ruta super clara: downloads/usuario/idmensaje_nombrezip
                folder_name = f"{message.id}_{safe_file_name}"
                extract_path = os.path.join(DOWNLOADS_DIR, str(user_id), folder_name)
                os.makedirs(extract_path, exist_ok=True)
                
                try:
                    with zipfile.ZipFile(download_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_path)
                    extraction_successful = True
                except (zipfile.BadZipFile, Exception) as e:
                    print(f"[{file_id}] ❌ Error al extraer (Intento {attempt}/{max_retries}): {e}")
                    if os.path.exists(download_path):
                        os.remove(download_path)
                    shutil.rmtree(extract_path, ignore_errors=True)
                    
            if extraction_successful:
                break # Éxito, salir del loop
                
        if not extraction_successful:
            await safe_edit_text(status_msg, "❌ Ocurrió un error al descomprimir el archivo tras 3 intentos. Puede que esté dañado, protegido con contraseña, o no sea un ZIP válido.")
            return

        # 3. Detect images and videos
        async with process_sem:

            # 3. Detect images and videos
            image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".gif"}
            video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv"}
            valid_extensions = image_extensions.union(video_extensions)
            images_found = []
            
            for root, dirs, files in os.walk(extract_path):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in valid_extensions:
                        images_found.append(os.path.join(root, file))
            
            if not images_found:
                await safe_edit_text(status_msg, "❌ No se encontraron imágenes ni videos en el ZIP.")
                os.remove(download_path)
                shutil.rmtree(extract_path, ignore_errors=True)
                return
                
            img_count = len(images_found)
            print(f"[{file_id}] 🚀 Procesando {img_count} archivos (Enviando originales y convirtiendo imágenes al Canal)...")
            # Borrar el mensaje de estado temporal
            await safe_delete_message(status_msg)
            
            # Reenviar primero el ZIP al canal de base de datos
            db_channel = get_database_channel()
            try:
                await asyncio.wait_for(message.forward(chat_id=db_channel), timeout=120)
            except asyncio.TimeoutError:
                print(f"Timeout reenviando zip al canal.")
            except Exception as e:
                print(f"Error reenviando zip al canal: {e}")

            # 4. Prepare Upload Tasks
            sent_original = 0
            sent_webp = 0
            sent_video = 0
            files_data = [] # Lista para almacenar la información de los archivos exportados
            
            # Concurrencia de envío de documentos
            send_sem = asyncio.Semaphore(5)
            upload_tasks = []

            async def upload_doc(path, file_type):
                nonlocal sent_original, sent_webp, sent_video, files_data
                async with send_sem:
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            # Seleccionar un worker bot o el bot principal
                            client_to_use = worker_manager.get_next_client(app)
                            current_db_channel = get_database_channel()
                            
                            if file_type == "VIDEO":
                                sent_msg_channel = await asyncio.wait_for(
                                    client_to_use.send_document(
                                        chat_id=current_db_channel,
                                        document=path,
                                        caption=f"🎞️ Video: {os.path.basename(path)}",
                                        force_document=True
                                    ),
                                    timeout=600
                                )
                                sent_video += 1
                                file_id = sent_msg_channel.document.file_id if (hasattr(sent_msg_channel, "document") and sent_msg_channel.document) else None
                            else:
                                sent_msg_channel = await asyncio.wait_for(
                                    client_to_use.send_document(
                                        chat_id=current_db_channel,
                                        document=path,
                                        caption=f"🟢 WEBP Optimizado: {os.path.basename(path)}" if file_type == "WEBP" else f"📄 Original: {os.path.basename(path)}",
                                        force_document=True
                                    ),
                                    timeout=300
                                )
                                if file_type == "WEBP": sent_webp += 1
                                else: sent_original += 1
                                file_id = sent_msg_channel.document.file_id if (hasattr(sent_msg_channel, "document") and sent_msg_channel.document) else None
                            
                            files_data.append({
                                "name": os.path.basename(path),
                                "type": file_type,
                                "msg_id": sent_msg_channel.id,
                                "file_id": file_id
                            })
                            
                            # Pausa mínima (0.1s); si Telegram pide más tiempo por rate limit, 
                            # Pyrogram lo sumirá automáticamente según el sleep_threshold=1000
                            await asyncio.sleep(0.1)
                            break # Exito, salir del loop
                        except asyncio.TimeoutError:
                            print(f"⏳ Timeout sending doc {path} (Intento {attempt+1}/{max_retries})")
                        except Exception as e:
                            print(f"❌ Error sending doc {path} (Intento {attempt+1}/{max_retries}): {e}")
                            await asyncio.sleep(2)

            def convert_to_webp(img_path, index):
                """ Sync function to be run in a thread """
                try:
                    img = Image.open(img_path)
                    
                    width, height = img.size
                    max_size_conf = get_webp_max_size()
                    max_limit = 16383
                    
                    # 1. Redimensionar si supera el tamaño máximo configurado por el usuario
                    if max_size_conf and (width > max_size_conf or height > max_size_conf):
                        ratio = min(max_size_conf / width, max_size_conf / height)
                        new_width = int(width * ratio)
                        new_height = int(height * ratio)
                        try:
                            resample_filter = Image.Resampling.LANCZOS
                        except AttributeError:
                            resample_filter = Image.LANCZOS
                        img = img.resize((new_width, new_height), resample_filter)
                        print(f"[{file_id}] ⚙️ Imagen redimensionada por límite de usuario de {width}x{height} a {new_width}x{new_height}.")
                    elif width > max_limit or height > max_limit:
                        # 2. Redimensionar por límite físico de WebP (16383px)
                        ratio = min(max_limit / width, max_limit / height)
                        new_width = int(width * ratio)
                        new_height = int(height * ratio)
                        try:
                            resample_filter = Image.Resampling.LANCZOS
                        except AttributeError:
                            resample_filter = Image.LANCZOS
                        img = img.resize((new_width, new_height), resample_filter)
                        print(f"[{file_id}] ⚠️ Imagen redimensionada por límite físico de WebP de {width}x{height} a {new_width}x{new_height}.")
                    
                    is_animated = getattr(img, "is_animated", False)
                    if not is_animated:
                        if img.mode not in ('RGB', 'RGBA'):
                            img = img.convert('RGBA')
                        
                    webp_path = os.path.splitext(img_path)[0] + f"_opt.webp"
                    
                    quality = get_webp_quality()
                    
                    if is_animated:
                        img.info.pop('background', None) 
                        img.save(webp_path, "webp", quality=quality, method=6, save_all=True)
                    else:
                        img.save(webp_path, "webp", quality=quality, method=6)
                        
                    print(f"[{file_id}] ✅ Convertida a WEBP: {os.path.basename(img_path)}")
                    return webp_path
                except Exception as e:
                    print(f"[{file_id}] ❌ Error convirtiendo {img_path}: {e}")
                    return None
                    
            async def process_single_image(img_path, index):
                """ Subtask: Send original immediately, convert in background, send webp """
                async with image_processing_sem:
                    ext = os.path.splitext(img_path)[1].lower()
                    
                    if ext in video_extensions:
                        await upload_doc(img_path, "VIDEO")
                    else:
                        # 1. Start original upload right away
                        task_orig = asyncio.create_task(upload_doc(img_path, "ORIGINAL"))
                        
                        # 2. Run conversion CPU-heavy task under conversion_sem
                        async with conversion_sem:
                            webp_path = await asyncio.to_thread(convert_to_webp, img_path, index)
                        
                        # 3. Wait for original to finish
                        await task_orig
                        
                        # 4. Upload WEBP
                        if webp_path:
                            await upload_doc(webp_path, "WEBP")

            # Build all subtasks
            for index, img_path in enumerate(images_found):
                upload_tasks.append(process_single_image(img_path, index))
            
            # Run everything concurrently (each throttled by image_processing_sem and conversion_sem)
            await asyncio.gather(*upload_tasks)
            
            print(f"[{file_id}] ✅ Proceso terminado en canal. Originales: {sent_original}/{img_count} | WEBP: {sent_webp}/{img_count} | Videos: {sent_video}/{img_count}")
            
            # Crear archivo de texto con los IDs
            txt_filename = f"{safe_file_name}_data.txt"
            txt_path = os.path.join(extract_path, txt_filename)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"=== Datos del ZIP: {doc_name} ===\n\n")
                # Ordenar un poco para legibilidad (opcional)
                for item in sorted(files_data, key=lambda x: x['name']):
                    f.write(f"[{item['type']}] {item['name']}\n")
                    f.write(f"Message ID (Canal): {item['msg_id']}\n")
                    f.write(f"File ID: {item['file_id']}\n")
                    f.write("-" * 40 + "\n")
            
            summary_text = f"✅ Éxito.\nSe enviaron **{sent_webp}** WEBP, **{sent_original}** originales y **{sent_video}** videos silenciosamente al canal.\n\nAquí tienes el reporte de IDs de este ZIP para reenviárselo a tu otro bot."
            
            # Enviar el archivo TXT a la conversacion privada respondiendo al ZIP
            try:
                await asyncio.wait_for(
                    app.send_document(
                        chat_id=message.chat.id,
                        document=txt_path,
                        caption=summary_text,
                        force_document=True,
                        reply_to_message_id=message.id
                    ),
                    timeout=60
                )
            except Exception as e:
                print(f"Error enviando txt final: {e}")

            # Cleanup
            try:
                os.remove(download_path)
                shutil.rmtree(extract_path, ignore_errors=True)
            except Exception as e:
                print(f"Error cleaning up files: {e}")

    except Exception as e:
        try:
            await message.reply(f"❌ Ocurrió un error inesperado al procesar:\n{e}")
        except Exception as inner_e:
            print(f"No se pudo enviar mensaje de error (posible FloodWait): {inner_e}")
        print(f"Error fatal en handle_task: {e}")
    finally:
        tasks_in_queue -= 1

@app.on_message(filters.command("reload_tokens") & filters.private)
async def reload_tokens_cmd(client, message):
    await message.reply("🔄 Recargando tokens de base de datos (`data/bot_tokens.json`)...")
    await worker_manager.stop()
    worker_manager.clients = []
    worker_manager.current_index = 0
    await worker_manager.start()
    await message.reply(f"✅ Tokens recargados exitosamente. {len(worker_manager.clients)} worker bots activos.")

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await message.reply("¡Hola! Envíame un archivo `.zip` para extraer las imágenes y videos. Convertiré las imágenes a formato optimizado (WEBP) y te devolveré tanto el original como el optimizado de super alta velocidad.")

@app.on_message(filters.command("twistedbrody") & filters.private)
async def twistedbrody_cmd(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Waifu Of Brody", url="https://t.me/waifuofbrodybot")],
        [InlineKeyboardButton("Twisted Brody Manga Flow", url="https://t.me/twistedbrodymangaflowbot")],
        [InlineKeyboardButton("Brody File Stream", url="https://t.me/BrodyFileStreamBot")]
    ])
    await message.reply("🤖 Aquí tienes nuestros bots hermanos:", reply_markup=keyboard)

@app.on_message(filters.command("set_channel") & filters.private)
async def set_channel_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        await message.reply("❌ No tienes permisos para usar este comando.")
        return
        
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        current_chan = get_database_channel()
        await message.reply(
            f"ℹ️ Uso: `/set_channel <ID_del_canal_o_Username>`\n\n"
            f"Canal actual: `{current_chan}`\n\n"
            f"💡 **Consejo:** Si es un canal privado, por favor reenvía cualquier mensaje de ese canal a este chat del bot. El bot lo detectará y configurará automáticamente."
        )
        return
        
    channel_input = parts[1].strip()
    
    # Intentar parsear como entero si no empieza por @
    if not channel_input.startswith("@"):
        try:
            channel_id = int(channel_input)
        except ValueError:
            await message.reply("❌ El ID del canal debe ser un número entero (ej. -100123456789) o un username (ej. @mi_canal).")
            return
    else:
        channel_id = channel_input

    # Intentar verificar/resolver el canal para guardarlo en la caché de peers
    try:
        chat = await app.get_chat(channel_id)
        resolved_id = chat.id
        resolved_title = chat.title or chat.first_name or "Canal/Grupo"
    except Exception as e:
        await message.reply(
            f"⚠️ El bot principal no pudo verificar/resolver el canal `{channel_id}` (Error: {e}).\n\n"
            f"📢 **Si es un canal privado, por favor reenvía cualquier mensaje de ese canal a este chat del bot** para registrarlo y sincronizarlo automáticamente."
        )
        return

    cfg = load_bot_config()
    cfg["database_channel"] = resolved_id
    save_bot_config(cfg)
    
    # Propagar peers a los workers de inmediato
    propagate_peers()
    
    await message.reply(f"✅ Canal de base de datos verificado y actualizado a: **{resolved_title}** (`{resolved_id}`)")

@app.on_message(filters.private & filters.forwarded)
async def handle_forwarded_message(client, message):
    # Si contiene un documento (como un ZIP), dejar que continúe al handler de documentos
    if message.document:
        raise ContinuePropagation

    if message.from_user.id != OWNER_ID:
        raise ContinuePropagation
        
    chat = message.forward_from_chat
    if chat:
        chat_type = str(chat.type)
        if "channel" in chat_type or "group" in chat_type or "supergroup" in chat_type:
            # Registrar canal en la configuración
            cfg = load_bot_config()
            cfg["database_channel"] = chat.id
            save_bot_config(cfg)
            
            # Pausa breve para asegurar el guardado de peer en la base de datos principal
            await asyncio.sleep(1)
            propagate_peers()
            
            await message.reply(
                f"✅ **Canal/Grupo detectado y enlazado con éxito**\n\n"
                f"• Nombre: **{chat.title}**\n"
                f"• ID del Canal: `{chat.id}`\n\n"
                f"Los datos de acceso (peer hashes) se han sincronizado con los worker bots. Ya puedes enviar archivos y el bot los procesará correctamente."
            )
            return

    raise ContinuePropagation

@app.on_message(filters.command("calidad") & filters.private)
async def calidad_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        await message.reply("❌ No tienes permisos para usar este comando.")
        return
        
    current_quality = get_webp_quality()
    
    # Mapear calidad numérica a etiqueta legible
    if current_quality <= 60:
        quality_str = "Mínima"
    elif current_quality <= 85:
        quality_str = "Media / Recomendada"
    else:
        quality_str = "Máxima"
        
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Mínima (Menor peso)", callback_data="qual_min")],
        [InlineKeyboardButton("Media / Recomendada", callback_data="qual_med")],
        [InlineKeyboardButton("Máxima (Mejor calidad)", callback_data="qual_max")]
    ])
    
    await message.reply(
        f"⚙️ **Configuración de Calidad WebP**\n\n"
        f"Selecciona la calidad deseada para la compresión de tus imágenes:\n"
        f"• Calidad actual: **{quality_str}** (`{current_quality}`)\n\n"
        f"💡 *Mínima reduce al máximo el peso (ideal para web), Media es el equilibrio estándar, y Máxima conserva casi todo el detalle.*",
        reply_markup=keyboard
    )

@app.on_callback_query(filters.regex(r"^qual_"))
async def handle_quality_callback(client, callback_query: CallbackQuery):
    if callback_query.from_user.id != OWNER_ID:
        await callback_query.answer("❌ No tienes permisos para realizar esta acción.", show_alert=True)
        return
        
    data = callback_query.data
    quality_val = 80
    quality_str = "Media / Recomendada"
    
    if data == "qual_min":
        quality_val = 55 # Calidad mínima (muy compacta)
        quality_str = "Mínima"
    elif data == "qual_med":
        quality_val = 80 # Calidad recomendada
        quality_str = "Media / Recomendada"
    elif data == "qual_max":
        quality_val = 95 # Calidad máxima
        quality_str = "Máxima"
        
    cfg = load_bot_config()
    cfg["webp_quality"] = quality_val
    save_bot_config(cfg)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Mínima (Menor peso)", callback_data="qual_min")],
        [InlineKeyboardButton("Media / Recomendada", callback_data="qual_med")],
        [InlineKeyboardButton("Máxima (Mejor calidad)", callback_data="qual_max")]
    ])
    
    try:
        await callback_query.edit_message_text(
            f"⚙️ **Configuración de Calidad WebP**\n\n"
            f"✅ ¡Calidad actualizada correctamente!\n"
            f"• Calidad actual: **{quality_str}** (`{quality_val}`)\n\n"
            f"💡 *Mínima reduce al máximo el peso (ideal para web), Media es el equilibrio estándar, y Máxima conserva casi todo el detalle.*",
            reply_markup=keyboard
        )
    except Exception:
        pass
        
    await callback_query.answer(f"Calidad configurada en: {quality_str}")

@app.on_message(filters.command("set_max_size") & filters.private)
async def set_max_size_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        await message.reply("❌ No tienes permisos para usar este comando.")
        return
        
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        current_max_size = get_webp_max_size()
        await message.reply(
            f"ℹ️ Uso: `/set_max_size <píxeles | none>`\n\n"
            f"Ejemplo: `/set_max_size 1920` (redimensiona imágenes mayores a 1920px de ancho/alto)\n"
            f"Ejemplo: `/set_max_size none` (desactiva el límite y mantiene resolución original)\n\n"
            f"Tamaño máximo actual: `{current_max_size}`"
        )
        return
        
    val = parts[1].strip().lower()
    if val == "none":
        max_size = None
    else:
        try:
            max_size = int(val)
            if max_size <= 0:
                raise ValueError()
        except ValueError:
            await message.reply("❌ El tamaño debe ser un entero positivo o `none`.")
            return

    cfg = load_bot_config()
    cfg["webp_max_size"] = max_size
    save_bot_config(cfg)
    
    status_str = f"`{max_size}px`" if max_size else "desactivado (mantiene original)"
    await message.reply(f"✅ Límite de tamaño de imagen para WebP actualizado a: {status_str}")

@app.on_message(filters.document & filters.private)
async def handle_document(client, message: Message):
    doc = message.document
    file_name = doc.file_name or ""
    if doc.mime_type in ["application/zip", "application/x-zip-compressed"] or file_name.lower().endswith(".zip"):
        status_msg = await message.reply("📥 Archivo recibido. Comprobando posición en la cola...", quote=True)
        # Create an independent backgrount task for each file
        asyncio.create_task(handle_task(message, status_msg))
    else:
        await message.reply("❌ Por favor, envía un archivo con formato `.zip`.")

async def web_server():
    async def handle_request(request):
        return web.Response(text="Bot is running!")
    
    app_web = web.Application()
    app_web.router.add_get('/', handle_request)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 7860)
    await site.start()
    print("🌍 Servidor Fantasma Aiohttp activo en puerto 7860")

async def start_bot():
    # Iniciar servidor web fantasma
    await web_server()
    
    # Iniciar bot
    await app.start()
    
    # Propagar peers ya conocidos con los workers antes de iniciarlos
    print("🔄 Sincronizando base de datos de canales/grupos (peers) con los workers...")
    propagate_peers()
    
    # Iniciar workers
    await worker_manager.start()
    
    # Resetear comandos antiguos y dejar los nuevos
    print("🔄 Actualizando comandos de menú en Telegram...")
    await app.set_bot_commands([
        BotCommand("start", "Iniciar el bot procesador de ZIPs"),
        BotCommand("twistedbrody", "Ver bots hermanos recomendados"),
        BotCommand("set_channel", "Configurar canal de base de datos (Admin)"),
        BotCommand("calidad", "Configurar calidad WebP por botones (Admin)"),
        BotCommand("set_max_size", "Configurar tamaño máximo WebP (Admin)")
    ])
    
    print("✅ Bot Conectado y Listo.")
    
    # Mantener el bot corriendo
    from pyrogram import idle
    await idle()
    await worker_manager.stop()
    await app.stop()

if __name__ == "__main__":
    app.run(start_bot())