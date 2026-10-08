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
from config import API_ID, API_HASH, BOT_TOKEN, DOWNLOAD_DIR
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
    "brody_min_bot_v4", 
    api_id=int(API_ID),
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN, 
    workers=100, # Para velocidad en descargas y eventos
    workdir=WORKDIR,
    ipv6=False
)

# Control de Concurrencia (3x3 - 3 descargas simultáneas por usuario)
USER_SEMAPHORES = {}
def get_user_semaphore(chat_id):
    if chat_id not in USER_SEMAPHORES:
        USER_SEMAPHORES[chat_id] = asyncio.Semaphore(3)
    return USER_SEMAPHORES[chat_id]

# Variables de Estado de UI
WAITING_FOR_SECOND = {} # Almacena si un usuario va a escribir el segundo

# --- INTERFAZ UI ---
async def send_panel(client, chat_id, message_id=None):
    conf = get_config(chat_id)
    thumb_mode = conf.get('thumb_auto_mode', False)
    thumb_second = conf.get('thumb_second', 30)

    status_icon = "🟢" if thumb_mode else "🔴"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Modo: {status_icon}", callback_data="toggle_mode")],
        [InlineKeyboardButton(f"✏️ Configurar Segundo ({thumb_second}s)", callback_data="config_sec")],
        [InlineKeyboardButton("🔙 Volver", callback_data="panel_main")]
    ])
    
    txt = (
        "📸 **Miniatura Personalizada**\n\n"
        "Activa este modo para forzar que la miniatura de tus descargas sea siempre un segundo específico.\n\n"
        f"⏱ **Segundo Configurado:** `{thumb_second}s`\n"
        "1. Configura el segundo deseado.\n"
        "2. Activa el modo.\n"
        "3. Descarga tus vídeos."
    )
    
    try:
        if message_id:
            await client.edit_message_text(text=txt, chat_id=chat_id, message_id=message_id, reply_markup=kb)
        else:
            await client.send_message(chat_id, txt, reply_markup=kb)
    except MessageNotModified:
        pass
    except Exception as e:
        print(f"Error enviando panel: {e}")

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
    chat_id = q.message.chat.id
    data = q.data
    conf = get_config(chat_id)

    try:
        await q.answer()
    except:
        pass

    if data == "toggle_mode":
        conf['thumb_auto_mode'] = not conf.get('thumb_auto_mode', False)
        asyncio.create_task(save_user_config_fb(chat_id, conf))
        await send_panel(client, chat_id, q.message.id)
    
    elif data == "config_sec":
        WAITING_FOR_SECOND[chat_id] = True
        await q.message.reply("⏱ **Por favor, envía el segundo que quieres configurar para la miniatura (ejemplo: 30, 45, 120):**")
    
    elif data == "panel_main":
        WAITING_FOR_SECOND.pop(chat_id, None)
        await send_panel(client, chat_id, q.message.id)

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
    
    if not conf.get('thumb_auto_mode', False):
        # Si el modo está apagado, ignoramos
        return
        
    sem = get_user_semaphore(chat_id)
    if sem.locked():
        await message.reply("⏳ **Cola llena (Máximo 3 simultáneos). Esperando turno...**", quote=True)
        
    # Agendar tarea usando el semaforo de concurrencia 3x3
    asyncio.create_task(process_media(client, message, conf, sem))

async def process_media(client: Client, message: Message, conf, sem):
    from tools_media import progreso, fast_download, get_meta, get_thumb
    chat_id = message.chat.id
    
    async with sem:
        msg_status = await message.reply("⚡️ **Preparando descarga...**", quote=True)
        ts_base = int(time.time())
        file_path = os.path.join(DOWNLOAD_DIR, f"v_{chat_id}_{ts_base}_{message.id}.mp4")
        t_path = None
        
        try:
            # 1. Descarga del video (Acelerada internamente por Workers + Selector)
            res = await fast_download(client, message, file_path, msg_status, act="Descargando")
            if not res or not os.path.exists(file_path):
                await msg_status.edit("❌ **Error al descargar el vídeo.**")
                return

            # 2. Extracción de Metadatos y Miniatura
            await msg_status.edit("🎨 **Procesando Miniatura...**")
            w, h, duration = await get_meta(file_path)
            
            thumb_sec_val = conf.get('thumb_second', 30)
            m, s = divmod(thumb_sec_val, 60)
            hh, mm = divmod(m, 60)
            seek_fmt = f"{int(hh):02d}:{int(mm):02d}:{s:02d}"
            
            t_path = await get_thumb(file_path, chat_id, ts_base, duration=duration, seek_override=seek_fmt)
            
            # 3. Subida Acelerada (16 Hilos Manuales)
            from tools_media import fast_upload
            from pyrogram.raw.types import InputMediaUploadedDocument, InputMediaUploadedPhoto
            from pyrogram.raw.functions.messages import SendMedia
            
            await msg_status.edit("📤 **Subiendo vídeo (16 Hilos)...**")
            
            # Subir archivo principal
            input_file = await fast_upload(client, file_path, msg_status, act="Subiendo")
            
            # Subir miniatura si existe
            input_thumb = None
            if t_path and os.path.exists(t_path):
                input_thumb = await fast_upload(client, t_path, msg_status, act="Subiendo Mini")
            
            # 4. Enviar mediante Raw API para usar los hilos completados
            await msg_status.edit("✅ **Finalizando envío...**")
            
            original_caption = message.caption or ""
            is_doc_orig = bool(message.document)
            
            # Atributos para el video
            attributes = []
            if not is_doc_orig:
                from pyrogram.raw.types import DocumentAttributeVideo
                attributes.append(DocumentAttributeVideo(duration=duration, w=w, h=h, supports_streaming=True))
            
            from pyrogram.raw.types import DocumentAttributeFilename
            attributes.append(DocumentAttributeFilename(file_name=os.path.basename(file_path)))

            # Ejecutar Envío Raw
            await client.invoke(
                SendMedia(
                    peer=await client.resolve_peer(chat_id),
                    media=InputMediaUploadedDocument(
                        file=input_file,
                        thumb=input_thumb,
                        mime_type="video/mp4" if not is_doc_orig else "application/x-zip-compressed",
                        attributes=attributes,
                        force_file=is_doc_orig
                    ),
                    message=original_caption,
                    random_id=client.rnd_id(),
                    reply_to_msg_id=message.id
                )
            )
            
            await msg_status.delete()
            
        except Exception as e:
            print(f"Error procesando {message.id}: {e}")
            try: await msg_status.edit(f"❌ **Error:** {e}")
            except: pass
        finally:
            if os.path.exists(file_path):
                try: os.remove(file_path)
                except: pass
            if t_path and os.path.exists(t_path):
                try: os.remove(t_path)
                except: pass

# --- MAIN LOOP ---
async def main_loop():
    await start_web_server()
    print("🚀 Iniciando Pyrogram...")
    await app.start()
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