import asyncio
import os
import sys
import logging
from pyrogram import Client, filters, idle, enums
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, Message,
    BotCommand, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
)
import aiohttp
from aiohttp import web

# --- IMPORTACIONES DEL PROYECTO ---
from config import API_ID, API_HASH, BOT_TOKEN, DATA_DIR
from database import get_config
from manga_service import get_manga_metadata, process_manga_download
from collage_service import create_and_send_collage

WORKDIR = "sessions"
COLLAGE_SESSIONS = {}
BATCH_SESSIONS = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- WEB SERVER SETUP (AIOHTTP STREAMING / PORT BIND PARA HUGGINGFACE) ---
async def handle_health(request):
    return web.Response(text="OK - Running phantom page for HuggingFace")

async def start_web_server():
    app_web = web.Application()
    app_web.router.add_get('/', handle_health)
    app_web.router.add_get('/health', handle_health)
    
    runner = web.AppRunner(app_web)
    await runner.setup()
    # Usa el puerto 7860 obligatorio de HuggingFace Spaces
    site = web.TCPSite(runner, '0.0.0.0', 7860)
    await site.start()
    print("🌍 Servidor Fantasma Aiohttp activo en puerto 7860")

# --- 1. FIX WINDOWS LOOP ---
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if not os.path.exists(WORKDIR):
    os.makedirs(WORKDIR)

app = Client(
    "brody_final_v2", 
    api_id=int(API_ID),
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN, 
    workers=50,
    workdir=WORKDIR,
    ipv6=False
)

# --- COMANDOS ---
@app.on_message(filters.command(["start", "manga"]) | filters.regex(r"^🎲 Manga Aleatorio$"))
async def start_command(client: Client, message: Message):
    chat_id = message.chat.id
    
    # Activar menú rápido si es primera vez (o enviar el manga directamente si es un botón inline)
    # Telegram no permite ReplyKeyboard y InlineKeyboard en un solo mensaje.
    # Así que el ReplyKeyboard (el del menú de abajo) se envía con el texto inicial, 
    # y el Manga se envía en un mensaje separado con el InlineKeyboard.
    if message.text and (message.text.startswith("/start") or message.text.startswith("/manga")):
        try:
              await message.reply_text(
                 "📂 **Twisted Brody Manga Flow**",
                 reply_markup=ReplyKeyboardMarkup([
                     [KeyboardButton("🎲 Manga Aleatorio"), KeyboardButton("🖼 Creador de Collage")]
                 ], resize_keyboard=True)
             )
        except Exception as e:
             logger.error(f"Error enviando teclado: {e}")
    
    # 1. Start a loading/typing action
    await client.send_chat_action(chat_id, enums.ChatAction.TYPING)
    
    config = get_config(chat_id)
    doc_mode = config.get('manga_doc_mode', False)
    group_mode = config.get('manga_group_mode', True)
    hd_mode = config.get('manga_hd_mode', True)
    
    doc_btn = "🟢 Doc" if doc_mode else "🔴 Doc"
    grp_btn = "🟢 Álbum" if group_mode else "🔴 Álbum"
    hd_btn = "🟢 HD" if hd_mode else "🔴 Comprimido"

    # 2. Get a random manga cover
    try:
        from manga_service import get_random_cached_image
        
        random_manga, random_file_id = await get_random_cached_image(chat_id)
        
        buttons = [
            [
                InlineKeyboardButton(
                    "📖 Abrir MangaApp Web", 
                    web_app=WebAppInfo(url="https://codebybrody-twistedbrodymangaflow.hf.space/")
                )
            ],
            [
                InlineKeyboardButton(f"📄 Archivos: {doc_btn}", callback_data="cfgmanga:toggle_doc"),
                InlineKeyboardButton(f"📚 Agrupar: {grp_btn}", callback_data="cfgmanga:toggle_grp")
            ],
            [
                InlineKeyboardButton(f"🖼 Calidad: {hd_btn}", callback_data="cfgmanga:toggle_hd")
            ]
        ]
        
        if random_manga and random_manga.get('id'):
            buttons.insert(1, [InlineKeyboardButton("📤 Enviar Manga de la Portada", callback_data=f"showmanga:{random_manga['id']}")])
            
        keyboard = InlineKeyboardMarkup(buttons)
        caption = "👋 **¡Hola! Bienvenido a manga flow**"
        
        if random_file_id:
            try:
                # Enviar archivo desde FileID caché (Instantáneo y alta calidad)
                await message.reply_photo(
                    photo=random_file_id,
                    caption=caption,
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Error enviando random cache: {e}")
                await message.reply_text(caption, reply_markup=keyboard)
        else:
            # Fallback a texto si no hay imagenes cacheadas
            await message.reply_text(caption, reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Error sending random cover: {e}")
        buttons = [
            [
                InlineKeyboardButton(
                    "📖 Abrir MangaApp Web", 
                    web_app=WebAppInfo(url="https://codebybrody-twistedbrodymangaflowbot.hf.space")
                )
            ],
            [
                InlineKeyboardButton(f"📄 Archivos: {doc_btn}", callback_data="cfgmanga:toggle_doc"),
                InlineKeyboardButton(f"📚 Agrupar: {grp_btn}", callback_data="cfgmanga:toggle_grp")
            ],
            [
                InlineKeyboardButton(f"🖼 Calidad: {hd_btn}", callback_data="cfgmanga:toggle_hd")
            ]
        ]
        await message.reply_text(
            "👋 **¡Hola! Bienvenido a manga flow**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

@app.on_message(filters.command(["mangaflow"]))
async def mangaflow_command(client: Client, message: Message):
    buttons = [
        [
            InlineKeyboardButton(
                "📱 Abrir Twisted Brody Manga Flow", 
                web_app=WebAppInfo(url="https://codebybrody-twistedbrodymangaflowbot.hf.space")
            )
        ]
    ]
    await message.reply_text(
        "✨ **Twisted Brody Manga Flow**\n\nHaz clic en el botón inferior para abrir la aplicación Web:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r"^cfgmanga:"))
async def handle_manga_config(client: Client, callback_query):
    action = callback_query.data.split(":")[1]
    chat_id = callback_query.message.chat.id
    config = get_config(chat_id)
    
    if action == "toggle_doc":
        config['manga_doc_mode'] = not config.get('manga_doc_mode', False)
    elif action == "toggle_grp":
        config['manga_group_mode'] = not config.get('manga_group_mode', True)
    elif action == "toggle_hd":
        config['manga_hd_mode'] = not config.get('manga_hd_mode', True)
        
    doc_btn = "🟢 Doc" if config.get('manga_doc_mode', False) else "🔴 Doc"
    grp_btn = "🟢 Álbum" if config.get('manga_group_mode', True) else "🔴 Álbum"
    hd_btn = "🟢 HD" if config.get('manga_hd_mode', True) else "🔴 Comprimido"
    
    existing_markup = callback_query.message.reply_markup
    showmanga_btn = None
    if existing_markup and existing_markup.inline_keyboard:
        for row in existing_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data and str(btn.callback_data).startswith("showmanga:"):
                    showmanga_btn = btn

    buttons = [
        [
            InlineKeyboardButton(
                "📖 Abrir MangaApp Web", 
                web_app=WebAppInfo(url="https://codebybrody-twistedbrodymangaflow.hf.space/")
            )
        ],
        [
            InlineKeyboardButton(f"📄 Archivos: {doc_btn}", callback_data="cfgmanga:toggle_doc"),
            InlineKeyboardButton(f"📚 Agrupar: {grp_btn}", callback_data="cfgmanga:toggle_grp")
        ],
        [
            InlineKeyboardButton(f"🖼 Calidad: {hd_btn}", callback_data="cfgmanga:toggle_hd")
        ]
    ]
    
    if showmanga_btn:
        buttons.insert(1, [showmanga_btn])
        
    keyboard = InlineKeyboardMarkup(buttons)
    
    try:
        await callback_query.message.edit_reply_markup(reply_markup=keyboard)
    except:
        pass
    await callback_query.answer("Configuración actualizada.")

@app.on_message(filters.regex(r"^🖼 Creador de Collage$"))
async def start_collage_session(client: Client, message: Message):
    chat_id = message.chat.id
    COLLAGE_SESSIONS[chat_id] = {
        'images': [],
        'task': None,
        'status_msg': None,
        'creating_status': False,
        'status_created': False
    }
    await message.reply_text(
        "🖼 **Modo Collage Activado**\n\n"
        "Envíame o reenvíame todas las imágenes que quieras unir (fotos o documentos de imagen).\n"
        "El bot esperará 3 segundos desde la última imagen recibida para procesarlas todas juntas. ¡Puedes reenviar varias de golpe!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="cancel_collage")]])
    )

@app.on_callback_query(filters.regex(r"^cancel_collage$"))
async def cancel_collage(client: Client, callback_query):
    chat_id = callback_query.message.chat.id
    if chat_id in COLLAGE_SESSIONS:
        task = COLLAGE_SESSIONS[chat_id].get('task')
        if task and not task.done():
            task.cancel()
        del COLLAGE_SESSIONS[chat_id]
        await callback_query.message.edit_text("❌ Modo Collage cancelado.")
    else:
        await callback_query.message.delete()
        
async def process_collage_timeout(client: Client, chat_id: int):
    # Wait 3.5 seconds to see if more images arrive
    await asyncio.sleep(3.5)
    
    # If we get here, no new images arrived in the last 3.5 seconds. Process them!
    session = COLLAGE_SESSIONS.pop(chat_id, None)
    if session and session['images']:
        try:
             await create_and_send_collage(client, chat_id, session['status_msg'], session['images'])
        except Exception as e:
             logger.error(f"Error firing collage timer: {e}")
             await session['status_msg'].edit_text("❌ Ocurrió un error inesperado al armar el collage.")

@app.on_message((filters.photo | filters.document) & filters.private)
async def handle_collage_images(client: Client, message: Message):
    chat_id = message.chat.id
    
    if chat_id in COLLAGE_SESSIONS:
        session = COLLAGE_SESSIONS[chat_id]
        
        # User is in collage mode. Capture the file_id
        file_id = None
        if message.photo:
            file_id = message.photo.file_id
        elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
            file_id = message.document.file_id
            
        if file_id:
            session['images'].append(file_id)
            
            # Cancel the previous timeout task if it exists
            if session.get('task') and not session['task'].done():
                session['task'].cancel()
                
            count = len(session['images'])
            
            if not session.get('status_created') and not session.get('creating_status'):
                session['creating_status'] = True
                async def create_first_status():
                    try:
                        session['status_msg'] = await message.reply_text("📸 Recibiendo imágenes...")
                        session['status_created'] = True
                    except: pass
                asyncio.create_task(create_first_status())
            elif session.get('status_created') and count % 3 == 0:
                async def update_txt(c):
                    try: await session['status_msg'].edit_text(f"📸 Recibidas {c} imágenes. Esperando si hay más...")
                    except: pass
                asyncio.create_task(update_txt(count))
                    
            # Start a new timeout task
            session['task'] = asyncio.create_task(process_collage_timeout(client, chat_id))
        return

@app.on_message(filters.text & filters.private)
async def handle_manga_code(client: Client, message: Message):
    text = message.text.strip()
    
    import re
    words = re.split(r'[\s\n,]+', text)
    codes = [w.strip() for w in words if 10 < len(w.strip()) < 40 and w.strip().isalnum()]
    
    if len(codes) == 1:
        text = codes[0]
        chat_id = message.chat.id
        status_msg = await message.reply_text(f"🔍 Buscando manga `{text}` en la base de datos...")
        
        manga_data = await get_manga_metadata(text)
        
        if manga_data:
            title = manga_data.get('title', 'Desconocido')
            
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("📦 ZIP", callback_data=f"dlmanga:{text}:zip"),
                        InlineKeyboardButton("📄 PDF", callback_data=f"dlmanga:{text}:pdf")
                    ],
                    [
                        InlineKeyboardButton("🖼 Ver Imágenes", callback_data=f"dlmanga:{text}:img")
                    ],
                    [
                        InlineKeyboardButton("🔙 Cancelar", callback_data="dlmanga:cancel")
                    ]
                ]
            )
            
            await status_msg.edit_text(
                f"📚 **{title}**\n\n⬇️ Selecciona formato:",
                reply_markup=keyboard
            )
        else:
            await status_msg.edit_text("❌ Código de manga no encontrado o inválido.")
            
    elif len(codes) > 1:
        chat_id = message.chat.id
        session_id = str(message.id)
        BATCH_SESSIONS[session_id] = codes
        
        status_msg = await message.reply_text(f"🔍 Detectados {len(codes)} códigos de manga. Verificando...")
        
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📦 ZIP (Todos)", callback_data=f"dlbatch:{session_id}:zip"),
                    InlineKeyboardButton("📄 PDF (Todos)", callback_data=f"dlbatch:{session_id}:pdf")
                ],
                [
                    InlineKeyboardButton("🖼 Ver Imágenes (Todos)", callback_data=f"dlbatch:{session_id}:img")
                ],
                [
                    InlineKeyboardButton("🔙 Cancelar", callback_data="dlbatch:cancel")
                ]
            ]
        )
        
        await status_msg.edit_text(
            f"📚 **Lote Detectado ({len(codes)} mangas)**\n\n⬇️ Selecciona el formato para descargarlos/enviarlos todos juntos:",
            reply_markup=keyboard
        )

@app.on_callback_query(filters.regex(r"^dlbatch:"))
async def handle_batch_selection(client: Client, callback_query):
    data = callback_query.data.split(":")
    
    if len(data) == 2 and data[1] == "cancel":
        await callback_query.message.edit_text("❌ Descarga por lotes cancelada.")
        return
        
    if len(data) == 3:
        _, session_id, container = data
        chat_id = callback_query.message.chat.id
        
        codes = BATCH_SESSIONS.get(session_id)
        if not codes:
            await callback_query.message.edit_text("❌ Sesión por lotes caducada o inválida.")
            return
            
        await callback_query.message.edit_text(f"⏳ Iniciando envío de {len(codes)} mangas en lote...")
        
        config = get_config(chat_id)
        hd_mode = config.get('manga_hd_mode', True)
        quality_str = "original" if hd_mode else "webp"
        
        for i, manga_id in enumerate(codes):
            manga_status_msg = await callback_query.message.reply_text(f"🔄 **[{i+1}/{len(codes)}]** Buscando manga `{manga_id}`...")
            
            manga_data = await get_manga_metadata(manga_id)
            if manga_data:
                title = manga_data.get('title', 'Desconocido')
                await manga_status_msg.edit_text(f"✅ **[{i+1}/{len(codes)}]** **{title}**\nPreparando ({container.upper()})...")
                
                try:
                    await process_manga_download(
                        client=client, 
                        chat_id=chat_id, 
                        manga_data=manga_data, 
                        container=container, 
                        quality=quality_str, 
                        status_msg=manga_status_msg, 
                        doc_mode=config.get('manga_doc_mode', False), 
                        group_mode=config.get('manga_group_mode', True)
                    )
                except Exception as e:
                    logger.error(f"Error en batch manga {manga_id}: {e}")
                    try: await manga_status_msg.edit_text(f"❌ Error al procesar {title}: {e}")
                    except: pass
            else:
                 await manga_status_msg.edit_text(f"❌ **[{i+1}/{len(codes)}]** Código de manga no encontrado: `{manga_id}`")
                 
            if i < len(codes) - 1:
                await asyncio.sleep(3)
                
        try:
            await callback_query.message.edit_text(f"✅ **Lote Completado**\nSe enviaron todos los {len(codes)} mangas solicitados.")
        except:
            pass
            
        if session_id in BATCH_SESSIONS:
            del BATCH_SESSIONS[session_id]

@app.on_callback_query(filters.regex(r"^showmanga:"))
async def handle_showmanga(client: Client, callback_query):
    manga_id = callback_query.data.split(":")[1]
    
    manga_data = await get_manga_metadata(manga_id)
        
    if manga_data:
        title = manga_data.get('title', 'Desconocido')
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📦 ZIP", callback_data=f"dlmanga:{manga_id}:zip"),
                    InlineKeyboardButton("📄 PDF", callback_data=f"dlmanga:{manga_id}:pdf")
                ],
                [
                    InlineKeyboardButton("🖼 Ver Imágenes", callback_data=f"dlmanga:{manga_id}:img")
                ],
                [
                    InlineKeyboardButton("🔙 Cancelar", callback_data="dlmanga:cancel")
                ]
            ]
        )
        
        await callback_query.message.reply_text(
            f"📚 **{title}**\n\n⬇️ Selecciona formato para descargar:",
            reply_markup=keyboard
        )
        await callback_query.answer()
    else:
        await callback_query.answer("❌ Código de manga no encontrado.", show_alert=True)

@app.on_callback_query(filters.regex(r"^dlmanga:"))
async def handle_format_selection(client: Client, callback_query):
    data = callback_query.data.split(":")
    
    if len(data) == 2 and data[1] == "cancel":
        await callback_query.message.edit_text("❌ Descarga cancelada.")
        return
        
    if len(data) == 3:
        _, manga_id, container = data
        chat_id = callback_query.message.chat.id
        
        await callback_query.message.edit_text(f"🔍 Recuperando manga...")
        manga_data = await get_manga_metadata(manga_id)
        
        if manga_data:
            title = manga_data.get('title', 'Desconocido')
            await callback_query.message.edit_text(f"✅ Manga encontrado: **{title}**\nPreparando descarga ({container.upper()})...")
            
            try:
                config = get_config(chat_id)
                hd_mode = config.get('manga_hd_mode', True)
                quality_str = "original" if hd_mode else "webp"
                
                await process_manga_download(
                    client=client, 
                    chat_id=chat_id, 
                    manga_data=manga_data, 
                    container=container, 
                    quality=quality_str, 
                    status_msg=callback_query.message, 
                    doc_mode=config.get('manga_doc_mode', False), 
                    group_mode=config.get('manga_group_mode', True)
                )
            except Exception as e:
                logger.error(f"Error descargando manga: {e}")
                try: await callback_query.message.edit_text(f"❌ Error al procesar: {e}")
                except: pass
        else:
            await callback_query.message.edit_text("❌ Código de manga no encontrado o inválido.")

# --- ARRANQUE ---
async def boot_services():
    print("🚀 Bot Iniciando (Versión Limpia - Solo Manga)...")
    
    try:
        if not os.path.exists("downloads"):
            os.makedirs("downloads")
    except: pass
    
    # Inicializar cliente Telegram
    max_retries = 10
    connected = False
    
    for i in range(max_retries):
        try:
            if i > 0: print(f"🔄 Intento de conexión {i+1}/{max_retries}...")
            await app.start()
            connected = True
            break
        except Exception as e:
            err_str = str(e)
            if "406" in err_str or "AUTH_KEY" in err_str or "Unauthorized" in err_str:
                print(f"⚠️ Error de Sesión. Eliminando archivo corrupto...")
                s_path = os.path.join(WORKDIR, "brody_final_v2.session")
                if os.path.exists(s_path):
                    try: os.remove(s_path)
                    except: pass
                continue
            print(f"⚠️ Error de Red ({e}). Reintentando en {(i+1)*3}s...")
            await asyncio.sleep((i+1)*3)

    if not connected:
        print("❌ Error Crítico: No se pudo conectar a Telegram.")
        sys.exit(1)
        
    await app.set_bot_commands([
        BotCommand("start", "📖 Abrir Manga App"),
        BotCommand("mangaflow", "📱 Abrir Mini App directamente")
    ])
    
    # Firebase sync basico si es necesario por el database.py local
    try:
        from firebase_service import load_all_user_configs
        import database
        cfs = await load_all_user_configs()
        if cfs: database.user_config.update(cfs)
    except: pass
    
    print("✅ Bot Conectado y Listo.")
    
    # Iniciar Aiohttp Server (Ghost Page para HuggingFace)
    await start_web_server()
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        print('🚀 Iniciando Loop Principal del Bot (Clean Version)...')
        loop = asyncio.get_event_loop()
        loop.run_until_complete(boot_services())
    except KeyboardInterrupt:
        print("🛑 Bot detenido manualmente.")
    except Exception as e:
        print(f"❌ CRITICAL BOT CRASH: {e}")