import asyncio
import os
import sys
import time
import logging
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message,
    InputMediaDocument, InputMediaVideo, InputMediaAudio
)
from pyrogram.errors import MessageNotModified

# Configuraciones y DB
from config import API_ID, API_HASH, BOT_TOKEN
from database import get_config
from firebase_service import save_user_config_fb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- WEB SERVER (Página Fantasma - Minimalista) ---
async def handle_health(request):
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Smart Forwarder | Stealth</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;900&display=swap" rel="stylesheet">
        <style>
            body { 
                margin: 0; padding: 0; background: #000; color: #fff; 
                font-family: 'Outfit', sans-serif; height: 100vh; 
                display: flex; align-items: center; justify-content: center; 
                overflow: hidden; 
            }
            .glow {
                position: absolute; width: 400px; height: 400px;
                background: radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%);
                animation: pulse 4s infinite alternate;
            }
            @keyframes pulse { from { transform: scale(1); opacity: 0.3; } to { transform: scale(1.5); opacity: 0.1; } }
            .content { text-align: center; z-index: 10; cursor: pointer; }
            h1 { font-size: 3rem; font-weight: 900; letter-spacing: -0.05em; margin-bottom: 0.5rem; }
            p { font-size: 0.9rem; letter-spacing: 0.4em; text-transform: uppercase; opacity: 0.4; }
        </style>
    </head>
    <body onclick="location.href='https://t.me/SmartVideoSplitterBot'">
        <div class="glow"></div>
        <div class="content">
            <h1>SMART FORWARDER</h1>
            <p>System Status: Active</p>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def start_web_server():
    app_web = web.Application()
    app_web.router.add_get('/', handle_health)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 7860)
    await site.start()

# --- PYROGRAM CLIENT ---
WORKDIR = "sessions"
if not os.path.exists(WORKDIR): os.makedirs(WORKDIR)
import glob
for f in glob.glob(os.path.join(WORKDIR, "*.session*")):
    try: os.remove(f)
    except: pass

app = Client("brody_base_bot_v2", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN, workers=100, workdir=WORKDIR)

# --- REENVIADO LÓGICA ---
REENVIADO_BUFFER = {} # {chat_id: {"task": task, "msgs": [msg_ids]}}

async def process_forward_queue(client, chat_id):
    await asyncio.sleep(5)
    if chat_id in REENVIADO_BUFFER:
        data = REENVIADO_BUFFER.pop(chat_id)
        msg_ids = data["msgs"]
        if not msg_ids: return
        
        try:
            # Ordenar IDs cronológicamente para asegurar consistencia
            msg_ids = sorted(list(set(msg_ids)))
            
            if len(msg_ids) == 1:
                await client.copy_message(chat_id, chat_id, msg_ids[0])
            else:
                conf = get_config(chat_id)
                organizador = conf.get('organizador_mode', False)
                
                photo_group = []
                video_group = []
                visual_group = []
                doc_group = []
                
                for mid in msg_ids:
                    m = await client.get_messages(chat_id, mid)
                    if not m:
                        continue
                    
                    if m.photo:
                        from pyrogram.types import InputMediaPhoto
                        media_item = InputMediaPhoto(m.photo.file_id, caption=m.caption)
                        if organizador:
                            photo_group.append(media_item)
                        else:
                            visual_group.append(media_item)
                    elif m.video:
                        media_item = InputMediaVideo(m.video.file_id, caption=m.caption)
                        if organizador:
                            video_group.append(media_item)
                        else:
                            visual_group.append(media_item)
                    elif m.document:
                        doc_group.append(InputMediaDocument(m.document.file_id, caption=m.caption))
                    elif m.audio:
                        doc_group.append(InputMediaAudio(m.audio.file_id, caption=m.caption))
                    elif m.animation:
                        # GIFs no se pueden agrupar en Telegram nativo
                        await client.send_message(chat_id, "⚠️ **GIF/Animación detectada**: No se puede agrupar, reenviado por separado.")
                        await m.copy(chat_id)

                async def safe_send_media_group(media_list):
                    if not media_list:
                        return
                    for i in range(0, len(media_list), 10):
                        chunk = media_list[i:i+10]
                        if len(chunk) == 1:
                            item = chunk[0]
                            from pyrogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
                            if isinstance(item, InputMediaPhoto):
                                await client.send_photo(chat_id, item.media, caption=item.caption)
                            elif isinstance(item, InputMediaVideo):
                                await client.send_video(chat_id, item.media, caption=item.caption)
                            elif isinstance(item, InputMediaDocument):
                                await client.send_document(chat_id, item.media, caption=item.caption)
                            elif isinstance(item, InputMediaAudio):
                                await client.send_audio(chat_id, item.media, caption=item.caption)
                            else:
                                await client.send_media_group(chat_id, chunk)
                        else:
                            await client.send_media_group(chat_id, chunk)

                # Enviar grupos ordenadamente
                if organizador:
                    if video_group:
                        await safe_send_media_group(video_group)
                    if photo_group:
                        await safe_send_media_group(photo_group)
                else:
                    if visual_group:
                        await safe_send_media_group(visual_group)
                
                if doc_group:
                    await safe_send_media_group(doc_group)
        except Exception as e: 
            print(f"Error reenviado agrupado: {e}")

# --- MENÚS ---
async def send_panel(client, chat_id, message_id=None):
    conf = get_config(chat_id)
    s_re = "🟢" if conf.get('reenviado_mode') else "🔴"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"🔄 Reenviado: {s_re}", callback_data="menu|re_init")]])
    txt = "🛠 **SmartVideoSplitterBot**\n\nHerramientas de reenvío inteligente activas."
    if message_id: await client.edit_message_text(chat_id, message_id, txt, reply_markup=kb)
    else: await client.send_message(chat_id, txt, reply_markup=kb)

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m): await send_panel(c, m.chat.id)

@app.on_message(filters.command("directo") & filters.private)
async def cmd_directo(c, m):
    chat_id = m.chat.id
    conf = get_config(chat_id)
    conf['reenviado_type'] = 'direct'
    conf['reenviado_mode'] = True
    asyncio.create_task(save_user_config_fb(chat_id, conf))
    await m.reply("🚀 **Modo Directo Activado**\nLos archivos se reenviarán inmediatamente (desagrupados).")

@app.on_message(filters.command("agrupado") & filters.private)
async def cmd_agrupado(c, m):
    chat_id = m.chat.id
    conf = get_config(chat_id)
    conf['reenviado_type'] = 'group'
    conf['reenviado_mode'] = True
    asyncio.create_task(save_user_config_fb(chat_id, conf))
    await m.reply("📦 **Modo Agrupados Activado**\nLos archivos se enviarán en álbumes (espera de 5s).")

@app.on_callback_query()
async def cb_handler(c, q):
    chat_id = q.message.chat.id
    conf = get_config(chat_id)
    data = q.data

    if data == "menu|main": await send_panel(c, chat_id, q.message.id)
    elif data == "menu|re_init":
        s_d = "🟢" if conf.get('reenviado_type') == 'direct' else "🔴"
        s_g = "🟢" if conf.get('reenviado_type') == 'group' else "🔴"
        s_o = "🟢" if conf.get('organizador_mode') else "🔴"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Directo: {s_d}", callback_data="set_re|direct"),
             InlineKeyboardButton(f"Agrupados: {s_g}", callback_data="set_re|group")],
            [InlineKeyboardButton(f"Organizador: {s_o}", callback_data="toggle_re|organizador")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu|main")]
        ])
        txt = (
            "🔄 **Herramienta: REENVIADO**\n\n"
            "🔶 **Directo**: Reenvía inmediatamente.\n"
            "🔶 **Agrupados**: Espera 5s y agrupa.\n\n"
            "🗂 **Organizador**: Si está activo, separa imágenes y videos en reenvíos agrupados, "
            "enviando primero los videos (de 10 en 10) y luego las imágenes (de 10 en 10)."
        )
        await q.message.edit_text(txt, reply_markup=kb)
    elif data.startswith("set_re|"):
        mode = data.split("|")[1]
        conf['reenviado_type'] = mode
        conf['reenviado_mode'] = True
        asyncio.create_task(save_user_config_fb(chat_id, conf))
        await cb_handler(c, type('obj', (object,), {'message': q.message, 'data': 'menu|re_init', 'id': q.id})())
    elif data == "toggle_re|organizador":
        conf['organizador_mode'] = not conf.get('organizador_mode', False)
        asyncio.create_task(save_user_config_fb(chat_id, conf))
        await cb_handler(c, type('obj', (object,), {'message': q.message, 'data': 'menu|re_init', 'id': q.id})())

@app.on_message((filters.video | filters.document | filters.audio | filters.photo | filters.animation) & filters.private)
async def media_handler(c, m):
    chat_id = m.chat.id
    conf = get_config(chat_id)
    if not conf.get('reenviado_mode'): return
    
    if conf.get('reenviado_type') == 'direct':
        await m.copy(chat_id)
    else:
        if chat_id not in REENVIADO_BUFFER: REENVIADO_BUFFER[chat_id] = {"msgs": []}
        if "task" in REENVIADO_BUFFER[chat_id]: REENVIADO_BUFFER[chat_id]["task"].cancel()
        REENVIADO_BUFFER[chat_id]["msgs"].append(m.id)
        REENVIADO_BUFFER[chat_id]["task"] = asyncio.create_task(process_forward_queue(c, chat_id))

async def main():
    await start_web_server(); await app.start()
    try:
        from pyrogram.types import BotCommand
        await app.set_bot_commands([
            BotCommand("start", "⚙️ Menú Principal"),
            BotCommand("directo", "🚀 Reenvío Inmediato"),
            BotCommand("agrupado", "📦 Reenvío en Álbumes")
        ])
    except: pass
    await idle(); await app.stop()

if __name__ == "__main__": app.run(main())