import asyncio
import os
import time
import logging
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, BotCommand
)
from pyrogram.errors import MessageNotModified, FloodWait

# Configuraciones y DB
# Configuraciones y DB
from config import API_ID, API_HASH, BOT_TOKEN, DOWNLOAD_DIR, DUMP_CHANNEL_ID, WORKER_TOKENS
from database import get_config, user_config
from firebase_service import save_user_config_fb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- WEB SERVER (Salud y Base) ---
async def handle_health(request):
    return web.Response(text="Bot Miniatura Activo", content_type='text/plain')

async def start_web_server():
    app_web = web.Application()
    app_web.router.add_get('/', handle_health)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 7860)
    await site.start()
    print("🌍 Servidor Base activo en puerto 7860")

# --- FIX WINDOWS ---
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- PYROGRAM CLIENT ---
WORKDIR = "sessions"
if not os.path.exists(WORKDIR):
    os.makedirs(WORKDIR)

app = Client(
    "moderador_twisted", 
    api_id=int(API_ID),
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN, 
    workers=100, # Para velocidad en descargas y eventos
    workdir=WORKDIR,
    max_concurrent_transmissions=5,
    ipv6=False
)

# Escuadrón de Workers para subidas simultáneas al Dump Channel
BOT_WORKERS = []
worker_idx = 0

def get_upload_worker():
    global worker_idx
    if not BOT_WORKERS:
        return app # Fallback
    worker = BOT_WORKERS[worker_idx]
    worker_idx = (worker_idx + 1) % len(BOT_WORKERS)
    return worker

# Control de Concurrencia (5 descargas simultáneas solicitadas por el usuario)
USER_SEMAPHORES = {}
def get_user_semaphore(chat_id):
    if chat_id not in USER_SEMAPHORES:
        USER_SEMAPHORES[chat_id] = asyncio.Semaphore(5)
    return USER_SEMAPHORES[chat_id]

# Control de subidas (1 en 1 por usuario)
UPLOAD_LOCKS = {}
def get_upload_lock(chat_id):
    if chat_id not in UPLOAD_LOCKS:
        UPLOAD_LOCKS[chat_id] = asyncio.Lock()
    return UPLOAD_LOCKS[chat_id]

# Variables de Estado de UI
WAITING_FOR_SECOND = {} # Almacena si un usuario va a escribir el segundo
WAITING_FOR_COUNT = {} # Almacena si un usuario va a escribir la cantidad de imágenes
ANTI_SPAM = {} # Control de clics anti-ban para proteger de FloodWait

# --- ESTADO DE LOTES (NUEVO) ---
USER_STATUS = {} 
# { chat_id: { "received": 0, "success_videos": 0, "success_images": 0, "errors": [], "reg_task": None } }

def get_user_status(chat_id):
    if chat_id not in USER_STATUS:
        USER_STATUS[chat_id] = {
            "received": 0, 
            "success_videos": 0, 
            "success_images": 0, 
            "errors": [], 
            "reg_task": None
        }
    return USER_STATUS[chat_id]

async def notify_registration(client, chat_id):
    """Notifica cuántos videos se han recibido tras un breve periodo de inactividad."""
    await asyncio.sleep(4)
    status = USER_STATUS.get(chat_id)
    if status and status["received"] > 0:
        try:
            await client.send_message(chat_id, f"📥 **Se registraron {status['received']} videos en memoria. Procesando ahora...**")
        except: pass
    if status: status["reg_task"] = None

async def check_and_send_summary(client, chat_id):
    """Envía el resumen final cuando todos los videos registrados han sido procesados."""
    status = USER_STATUS.get(chat_id)
    if not status: return
    
    # Verificamos si ya terminamos todo lo recibido
    total_finalizados = status["success_videos"] + len(status["errors"])
    if status["received"] > 0 and total_finalizados >= status["received"]:
        # Un pequeño delay para asegurar que no entren más en el mismo instante
        await asyncio.sleep(2)
        if total_finalizados >= status["received"]:
            v = status["success_videos"]
            img = status["success_images"]
            e_count = len(status["errors"])
            
            msg = f"✅ **Se enviaron {v} videos y {img} imágenes**\n"
            
            if e_count > 0:
                msg += f"\n❌ **Fallaron {e_count} videos:**\n"
                for err in status["errors"]:
                    msg += f"   • {err}\n"
            
            try:
                await client.send_message(chat_id, msg)
            except: pass
            
            # Reiniciar contadores para el siguiente lote
            status["received"] = 0
            status["success_videos"] = 0
            status["success_images"] = 0
            status["errors"] = []

# --- INTERFAZ UI ---
async def send_panel(client, chat_id, message_id=None, q=None):
    conf = get_config(chat_id)
    thumb_mode = conf.get('thumb_auto_mode', True)
    thumb_second = conf.get('thumb_second', 30)
    thumb_count = conf.get('thumb_count', 1)

    status_icon = "🟢" if thumb_mode else "🔴"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Modo: {status_icon}", callback_data="toggle_mode")],
        [InlineKeyboardButton(f"🖼 Cantidad (x{thumb_count})", callback_data="menu_count"),
         InlineKeyboardButton(f"⏱ Segundo ({thumb_second}s)", callback_data="menu_sec")],
        [InlineKeyboardButton("🔙 Volver", callback_data="panel_main")]
    ])
    
    txt = (
        "📸 **Miniaturas & Capturas**\n\n"
        "Configura cuántas capturas quieres y en qué segundo inicia la principal.\n\n"
        f"⏱ **Segundo (para 1 img):** `{thumb_second}s`\n"
        f"🖼 **Cantidad de imágenes:** `{thumb_count}`\n\n"
        "1. Si eliges 1, usará el segundo configurado.\n"
        "2. Si eliges de 2 a 50, extraerá escenas distintas del video automáticamente.\n"
    )
    
    try:
        if message_id:
            await client.edit_message_text(text=txt, chat_id=chat_id, message_id=message_id, reply_markup=kb)
        else:
            await client.send_message(chat_id, txt, reply_markup=kb)
        if q:
            try: await q.answer()
            except: pass
    except MessageNotModified:
        if q:
            try: await q.answer()
            except: pass
    except FloodWait as e:
        if q:
            try: await q.answer(f"⏳ Bot bloqueado temporalmente por {e.value}s debido al exceso. Espera por favor.", show_alert=True)
            except: pass
        try:
            await client.send_message(chat_id, txt, reply_markup=kb)
        except:
            pass
    except Exception as e:
        print(f"Error enviando panel: {e}")
        if q:
            try: await q.answer(f"Error: {e}", show_alert=True)
            except: pass
        try:
            await client.send_message(chat_id, f"Error interno en panel: {e}")
        except:
            pass

# --- COMANDOS ---
@app.on_message(filters.command(["start", "help"]) & filters.private)
async def start_cmd(client: Client, message: Message):
    chat_id = message.chat.id
    WAITING_FOR_SECOND.pop(chat_id, None)
    await send_panel(client, chat_id)

@app.on_message(filters.command(["md"]) & filters.private)
async def md_cmd(client: Client, message: Message):
    explicacion = (
        "🤖 **Acerca del Bot**\n\n"
        "Este bot está diseñado para **asignar miniaturas personalizadas** a tus vídeos de forma automatizada.\n\n"
        "🔹 **¿Para qué sirve?**\n"
        "Sirve para cuando subes un vídeo y quieres que la miniatura sea un fotograma exacto.\n\n"
        "🔹 **¿Cómo funciona?**\n"
        "1. En el panel (`/start`), usas 'Configurar Segundo' y escribes un número (ej. 30).\n"
        "2. Asegúrate de que el Modo esté en 🟢.\n"
        "3. Simplemente envías tus vídeos, y el bot los devolverá velozmente con la miniatura capturada de ese segundo exacto."
    )
    await message.reply(explicacion)

# --- CALLBACKS (BOTONES) ---
@app.on_callback_query()
async def callbacks(client: Client, q: CallbackQuery):
    try:
        chat_id = q.message.chat.id
        
        # Escudo Anti-Spam (0.3 segundos mínimo entre clics para permitir navegación rápida)
        now = time.time()
        if now - ANTI_SPAM.get(chat_id, 0) < 0.3:
            try:
                await q.answer("🛡 Anti-Spam", show_alert=False)
            except:
                pass
            return
        ANTI_SPAM[chat_id] = now
        
        data = q.data
        conf = get_config(chat_id)

        if data == "toggle_mode":
            conf['thumb_auto_mode'] = not conf.get('thumb_auto_mode', True)
            try: asyncio.create_task(save_user_config_fb(chat_id, conf))
            except: pass
            await send_panel(client, chat_id, q.message.id, q)
        
        elif data == "menu_sec":
            buttons = []
            for i in range(5, 101, 25):
                row = [InlineKeyboardButton(f"{j}s", callback_data=f"set_sec_{j}") for j in range(i, i+25, 5) if j <= 100]
                buttons.append(row)
            buttons.append([InlineKeyboardButton("✏️ Manual", callback_data="config_sec_manual"), InlineKeyboardButton("🔙 Volver", callback_data="panel_main")])
            
            try:
                await q.message.edit_text(
                    "⏱ **Elige el segundo para la miniatura principal:**\n\n"
                    "*(Selecciona un número del menú o usa el lápiz para escribirlo manualmente)*",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                try: await q.answer()
                except: pass
            except FloodWait as e:
                await q.answer(f"⏳ Demasiados rápidos clics. Telegram pide esperar {e.value}s", show_alert=True)
            except Exception:
                pass
            
        elif data.startswith("set_sec_"):
            val = int(data.split("_")[2])
            conf['thumb_second'] = val
            try: asyncio.create_task(save_user_config_fb(chat_id, conf))
            except: pass
            await send_panel(client, chat_id, q.message.id, q)

        elif data == "config_sec_manual":
            WAITING_FOR_SECOND[chat_id] = True
            WAITING_FOR_COUNT.pop(chat_id, None)
            try:
                await q.message.reply("✏️ **Por favor, envía el segundo que quieres configurar para la miniatura (ejemplo: 30, 45, 120):**")
                try: await q.answer()
                except: pass
            except FloodWait as e:
                await q.answer(f"⏳ Telegram te limitó. Espera {e.value}s antes de intentar de nuevo.", show_alert=True)
            except:
                pass
            
        elif data == "menu_count":
            buttons = []
            for i in range(1, 21, 5):
                row = [InlineKeyboardButton(str(j), callback_data=f"set_count_{j}") for j in range(i, i+5)]
                buttons.append(row)
            buttons.append([InlineKeyboardButton("✏️ Manual", callback_data="config_count_manual"), InlineKeyboardButton("🔙 Volver", callback_data="panel_main")])
            
            try:
                await q.message.edit_text(
                    "🖼 **Elige la cantidad de capturas que deseas extraer:**\n\n"
                    "*(Selecciona un número del menú o usa el lápiz para escribirlo manualmente)*",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                try: await q.answer()
                except: pass
            except FloodWait as e:
                await q.answer(f"⏳ Demasiados rápidos clics. Telegram pide esperar {e.value}s", show_alert=True)
            except Exception:
                pass
            
        elif data.startswith("set_count_"):
            val = int(data.split("_")[2])
            conf['thumb_count'] = val
            try: asyncio.create_task(save_user_config_fb(chat_id, conf))
            except: pass
            await send_panel(client, chat_id, q.message.id, q)

        elif data == "config_count_manual":
            WAITING_FOR_COUNT[chat_id] = True
            WAITING_FOR_SECOND.pop(chat_id, None)
            try:
                await q.message.reply("✏️ **Envía la cantidad de capturas que deseas extraer (del 1 al 50):**")
                try: await q.answer()
                except: pass
            except FloodWait as e:
                await q.answer(f"⏳ Telegram te limitó. Espera {e.value}s antes de intentar de nuevo.", show_alert=True)
            except:
                pass
        
        elif data == "panel_main":
            WAITING_FOR_SECOND.pop(chat_id, None)
            try:
                await send_panel(client, chat_id, q.message.id, q)
            except Exception as e:
                await client.send_message(chat_id, f"Crash panel_main: {e}")
                
    except Exception as exc:
        print(f"Error fatal en callback: {exc}")
        try:
            await client.send_message(q.message.chat.id, f"⚠️ Error fatal procesando botón: {exc}")
        except:
            pass

# --- CAPTURA DE TEXTO (CONFIG SEGUNDO) ---
@app.on_message(filters.text & filters.private)
async def handle_text(client: Client, message: Message):
    chat_id = message.chat.id
    
    if WAITING_FOR_SECOND.get(chat_id):
        try:
            val = int(message.text.strip())
            if val < 0: val = 0
            
            conf = get_config(chat_id)
            conf['thumb_second'] = val
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            
            WAITING_FOR_SECOND.pop(chat_id, None)
            await message.reply(f"✅ **Segundo configurado exitosamente a:** `{val}s`")
            await send_panel(client, chat_id)
        except ValueError:
            await message.reply("❌ **Por favor, envía un número válido (ejemplo: 10, 30, 60).**")

    elif WAITING_FOR_COUNT.get(chat_id):
        try:
            val = int(message.text.strip())
            if val < 1: val = 1
            if val > 50: val = 50
            
            conf = get_config(chat_id)
            conf['thumb_count'] = val
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            
            WAITING_FOR_COUNT.pop(chat_id, None)
            await message.reply(f"✅ **Cantidad de capturas configurada a:** `{val}`")
            await send_panel(client, chat_id)
        except ValueError:
            await message.reply("❌ **Por favor, envía un número del 1 al 50.**")

# --- FLUJO DE PROCESAMIENTO (LA MAGIA) ---
@app.on_message((filters.video | filters.document) & filters.private)
async def handle_video(client: Client, message: Message):
    chat_id = message.chat.id
    
    if message.document:
        mime = getattr(message.document, "mime_type", "") or ""
        fname = getattr(message.document, "file_name", "") or ""
        is_video = mime.startswith("video/") or fname.lower().endswith((".mp4", ".ts", ".mkv", ".avi", ".mov", ".webm"))
        if not is_video:
            return # Ignorar documentos no-video sin avisar
            
    conf = get_config(chat_id)
    
    if not conf.get('thumb_auto_mode', True):
        # Si el modo está apagado, ignoramos
        return
        
    sem = get_user_semaphore(chat_id)
    if sem.locked():
        try:
            await message.reply("⏳ **Cola llena (Máximo 5 procesos simultáneos). Esperando turno...**", quote=True)
        except FloodWait:
            pass # Ignoramos el flood para la advertencia visual
        except Exception:
            pass
        
    # --- Lógica de Lote ---
    status = get_user_status(chat_id)
    status["received"] += 1
    
    # Cancelar tarea de registro anterior si existe para reiniciar el debounce
    if status["reg_task"]:
        status["reg_task"].cancel()
    status["reg_task"] = asyncio.create_task(notify_registration(client, chat_id))

    # Agendar tarea usando el semaforo de concurrencia de 5
    asyncio.create_task(process_media(client, message, conf, sem))

async def process_media(client: Client, message: Message, conf, sem):
    from tools_media import progreso, fast_download, get_meta, get_thumb
    chat_id = message.chat.id
    
    async with sem:
        # Añadido un pequeño ID visual basado en el ID del mensaje para identificarlo
        msg_status = None
        try:
            msg_status = await message.reply(f"⚡️ [ID:{message.id}] **Preparando descarga en nube...**", quote=True)
        except FloodWait as e:
            pass
        except Exception:
            pass
            
        ts_base = int(time.time())
        file_path = os.path.join(DOWNLOAD_DIR, f"v_{chat_id}_{ts_base}_{message.id}.mp4")
        t_path = None
        t_paths = []
        
        # 0. Seleccionar Worker para ciclo de vida y hacer Backup en Canal Oculto
        worker_cli = get_upload_worker()
        dump_msg_id = None
        worker_msg = None
        
        try:
            # Reenviar el crudo instantáneamente al canal
            dump_msg = await client.copy_message(
                chat_id=DUMP_CHANNEL_ID,
                from_chat_id=chat_id,
                message_id=message.id
            )
            dump_msg_id = dump_msg.id
            # Conseguir el objeto de mensaje desde la vista del Worker
            worker_msg = await worker_cli.get_messages(DUMP_CHANNEL_ID, dump_msg_id)
        except Exception as e:
            print(f"Error copiando a Dump Channel: {e}")
            worker_msg = message # Fallback al principal si hay error
            worker_cli = client # Revertimos al bot padre
        
        try:
            # 1. Descarga del video (completamente absorbido por el Worker Network)
            res = await fast_download(worker_cli, worker_msg, file_path, msg_status, act=f"[ID:{message.id}] Descargando")
            if not res or not os.path.exists(file_path):
                raise Exception("Error al descargar el vídeo de los servidores de Telegram.")

            # 2. Extracción de Metadatos y Miniatura
            if msg_status:
                try: await msg_status.edit(f"🎨 [ID:{message.id}] **Procesando Miniatura...**")
                except: pass
            w, h, duration = await get_meta(file_path)
            
            thumb_sec_val = conf.get('thumb_second', 30)
            m, s = divmod(thumb_sec_val, 60)
            hh, mm = divmod(m, 60)
            seek_fmt = f"{int(hh):02d}:{int(mm):02d}:{s:02d}"
            
            thumb_count = conf.get('thumb_count', 1)
            t_paths = await get_thumb(file_path, chat_id, f"{ts_base}_{message.id}", duration=duration, seek_override=seek_fmt, count=thumb_count)
            t_path = t_paths[0] if t_paths else None
            
            # Bloquear la fase de subida y envío final 1 a 1 para evitar que se mezclen
            # up_lock NO debe bloquear la subida, porque queremos que los workers suban en paralelo.
            
            # 3. Subida Nativa Acelerada (manejada por Pyrogram de forma estable)
            if msg_status:
                try: await msg_status.edit(f"📤 [ID:{message.id}] **Subiendo vídeo (Worker {worker_cli.name})...**")
                except: pass
            
            from tools_media import progreso
            t_data = [time.time() - 8.0, 0]
            async def progress_up(current, total):
                await progreso(current, total, msg_status, t_data, act=f"[ID:{message.id}] Subiendo")
            
            is_doc_orig = bool(message.document)
            msg_text = message.caption if message.caption else ""
            
            sent_msg = None
            for att in range(15):
                try:
                    if not is_doc_orig:
                        sent_msg = await worker_cli.send_video(
                            chat_id=DUMP_CHANNEL_ID,
                            video=file_path,
                            caption=msg_text,
                            thumb=t_path if (t_path and os.path.exists(t_path)) else None,
                            duration=duration,
                            width=w,
                            height=h,
                            supports_streaming=True,
                            progress=progress_up
                        )
                    else:
                        sent_msg = await worker_cli.send_document(
                            chat_id=DUMP_CHANNEL_ID,
                            document=file_path,
                            caption=msg_text,
                            thumb=t_path if (t_path and os.path.exists(t_path)) else None,
                            progress=progress_up
                        )
                    break # Si tiene éxito, salimos del bucle de reintentos
                except FloodWait as e:
                    # Si Telegram nos pide esperar 43 segundos (u otro tiempo), esperamos y reintentamos.
                    await asyncio.sleep(e.value + 1)
                except Exception as e:
                    # Otros errores inesperados que no son FloodWait
                    raise e
            
            
            try: await msg_status.delete()
            except: pass
            
            sent_id = sent_msg.id if sent_msg else None

            # AHORA SÍ: Bloqueamos SOLO el reenvío final al usuario para que las fotos de 2 videos no se mezclen en el chat
            up_lock = get_upload_lock(chat_id)
            async with up_lock:
                if len(t_paths) == 1:
                    try:
                        await client.send_photo(chat_id, photo=t_path, reply_to_message_id=message.id)
                    except Exception as e:
                        await message.reply(f"❌ **Error al enviar la imagen:** {e}")
                elif len(t_paths) > 1:
                    try:
                        from pyrogram.types import InputMediaPhoto
                        # Enviar solo las capturas de escenas al chat (ignoramos la principal [0] que va al video)
                        scenes = t_paths[1:]
                        if scenes:
                            for i in range(0, len(scenes), 10):
                                chunk = [p for p in scenes[i:i + 10] if os.path.exists(p)]
                                if not chunk: continue
                                media_group = [InputMediaPhoto(p) for p in chunk]
                                await client.send_media_group(chat_id, media=media_group, reply_to_message_id=message.id)
                                await asyncio.sleep(0.5)
                    except Exception as e:
                        await message.reply(f"❌ **Error capturas:** {e}")
                
                if sent_id:
                    # Reenviar invisiblemente al usuario
                    new_msg = await client.copy_message(
                        chat_id=chat_id,
                        from_chat_id=DUMP_CHANNEL_ID,
                        message_id=sent_id,
                        reply_to_message_id=message.id
                    )
                    if new_msg:
                        await new_msg.pin(both_sides=True)
                        # Actualizar éxito en el lote
                        status = get_user_status(chat_id)
                        status["success_videos"] += 1
                        status["success_images"] += len(t_paths)
            
        except Exception as e:
            err_msg = f"Video {message.id} falló: {str(e)}"
            print(f"Error procesando {message.id}: {e}")
            
            # Registrar error en el lote
            status = get_user_status(chat_id)
            status["errors"].append(err_msg)
            
            if msg_status:
                try: await msg_status.edit(f"❌ **Error:** {e}")
                except: pass
        finally:
            # Disparar chequeo de resumen final
            asyncio.create_task(check_and_send_summary(client, chat_id))
            
            if os.path.exists(file_path):
                try: os.remove(file_path)
                except: pass
            for p in t_paths:
                if os.path.exists(p):
                    try: os.remove(p)
                    except: pass
            if t_path and os.path.exists(t_path):
                try: os.remove(t_path)
                except: pass

# --- MAIN LOOP ---
async def main_loop():
    await start_web_server()
    print("🚀 Iniciando Pyrogram...")
    await app.start()
    print("🚀 Iniciando cliente único principal...")
    
    print("🚀 Iniciando Escuadrón de Workers...")
    for idx, token in enumerate(WORKER_TOKENS):
        if not token.strip(): continue
        try:
            worker = Client(f"worker_{idx}", api_id=int(API_ID), api_hash=API_HASH, bot_token=token.strip(), workdir=WORKDIR, workers=400, max_concurrent_transmissions=5)
            await worker.start()
            BOT_WORKERS.append(worker)
            print(f"   [+] Worker {worker.name} activado en modo ultra (400 hilos, 5 concurrentes).")
        except Exception as e:
            print(f"   [-] Error iniciando {token[:10]}... : {e}")
            
    try:
        await app.set_bot_commands([
            BotCommand("start", "Abrir el panel principal"),
            BotCommand("md", "Saber para qué sirve el bot")
        ])
        print("✅ Comandos rápidos listos en el menú de Telegram.")
    except Exception as e:
        print(f"Error configurando comandos: {e}")
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_loop())