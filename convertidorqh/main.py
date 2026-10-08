import asyncio
import os
import time
import random
import sys
import io
import pyrogram
from aiohttp import web

# Fix for Windows console emoji printing (prevent UnicodeEncodeError)
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except:
        pass

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, Message,
    InputMediaPhoto, InputMediaVideo, InputMediaDocument
)

# --- IMPORTACIONES DEL PROYECTO ---
from config import API_ID, API_HASH, BOT_TOKEN, DATA_DIR, HAS_FFMPEG
from utils import download_parallel
from tools_media import get_meta, get_thumb, progreso, has_audio_track, add_silent_audio

# --- CONFIGURACIÓN CLIENTE ---
WORKDIR = "sessions"
if not os.path.exists(WORKDIR):
    os.makedirs(WORKDIR)

app = Client(
    "qh_converter_bot", 
    api_id=int(API_ID),
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN, 
    workers=100,
    workdir=WORKDIR,
    ipv6=False,
    sleep_threshold=60,
    max_concurrent_transmissions=8
)

# --- SEMAPHORE (Limit concurrency to avoid ban/crash) ---
SEM_CONVERT_QH = asyncio.Semaphore(5)

@app.on_message(filters.command("start"))
async def start_handler(c, m):
    welcome_text = (
        "🚀 **Bienvenido al Convertidor QH**\n\n"
        "Este bot está optimizado para convertir archivos y documentos en videos normales que Telegram puede reproducir directamente a gran velocidad.\n\n"
        "✅ **¿Qué puedes hacer?**\n"
        "1️⃣ Envíame un archivo **como Documento** (video o imagen).\n"
        "2️⃣ Envíame un **GIF** (animación).\n\n"
        "Si me envías un archivo (.mp4, .mkv, .jpg) o un GIF, lo descargaré y lo convertiré a un formato nativo para verlo directamente.\n\n"
        "👇 Usa `/help` para ver más detalles."
    )
    await m.reply(welcome_text)

@app.on_message(filters.command("help"))
async def help_handler(c, m):
    help_text = (
        "❓ **Ayuda del Convertidor QH**\n\n"
        "El **Convertidor QH** es una herramienta de 'Quality & High-performance' diseñada para usuarios que necesitan mover archivos pesados rápidamente en Telegram.\n\n"
        "🔹 **¿Cómo funciona?**\n"
        "1. **Documentos:** Si tienes un video o foto pesado o con formato raro, envíalo usando el botón de 'Archivo' o 'Documento' (Clip 📎 -> Archivo). El bot lo convertirá y lo enviará como video visualizable.\n"
        "2. **GIFs/Animaciones:** Si mandas un GIF, el bot lo transforma automáticamente en un video MP4 nativo con audio vacío.\n\n"
        "⚠️ **Importante:** El bot ignora los videos y fotos de la galería normal para no molestar, solo atiende Documentos y GIFs.\n\n"
        "🚀 _¡Solo envía el archivo para comenzar!_"
    )
    await m.reply(help_text)

@app.on_message(filters.document | filters.animation)
async def qh_handler(c, m: Message):
    cid = m.chat.id
    
    # 1. Detectar si es Imagen
    is_image = False
    original_ext = ""
    
    if m.photo:
        is_image = True
        original_ext = ".jpg"
    elif m.document:
        if m.document.mime_type and m.document.mime_type.startswith("image/"):
            is_image = True
        if m.document.file_name:
            _, ext = os.path.splitext(m.document.file_name)
            if ext.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.bmp']:
                is_image = True
                original_ext = ext

    # --- FLUJO IMAGEN ---
    if is_image:
        wait = await m.reply("⬇️ **Bajando Imagen (QH)...**")
        dl_path = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"qh_img_{cid}_{m.id}{original_ext}"))
        
        if dl_path and os.path.exists(dl_path):
            await wait.edit("📤 **Enviando Imagen...**")
            try:
                # Enviar como FOTO (Normal)
                await c.send_photo(cid, dl_path, caption="📦 **Imagen (QH)**")
            except Exception:
                # Fallback a documento
                await c.send_document(cid, dl_path, caption="📦 **Imagen (QH)**")
            
            if os.path.exists(dl_path): os.remove(dl_path)
            await wait.delete()
        else:
            await wait.edit("❌ Error descargando imagen.")
        return

    # --- FLUJO VIDEO / ANIMACION ---
    # Detectamos si el documento es un video si no capturó filters.video
    is_video = m.video or m.animation
    if not is_video and m.document and m.document.mime_type:
        if m.document.mime_type.startswith("video/"):
            is_video = True

    if is_video:
        if SEM_CONVERT_QH.locked():
             wait = await m.reply("⏳ **En Cola de Procesamiento...**\n_Esperando turno (Máx 5 simultáneos)_")
        else:
             wait = await m.reply("⬇️ **Bajando TURBO (x32)...**\n🚀 Convertidor QH Activo")

        async with SEM_CONVERT_QH:
             if wait.text.startswith("⏳"): 
                 await wait.edit("⬇️ **Bajando TURBO (x32)...**\n🚀 Convertidor QH Activo")
             
             # Prep path
             file_name = f"conv_qh_{cid}_{m.id}.mp4"
             f_p = os.path.join(DATA_DIR, file_name)
             
             # Descarga Paralela (Turbo x32)
             # Nota: download_parallel ya maneja la lógica de x32 internamente si le pasas concurrency=32
             success_path = await download_parallel(c, m, f_p, concurrency=32, progress=progreso, progress_args=(wait, [0,0], "Descargando"))
             
             if not success_path:
                 # Fallback pyrogram download
                 success_path = await c.download_media(m, file_name=f_p)

             if success_path and os.path.exists(success_path):
                 # --- NEW LOGIC FOR NO AUDIO / GIF ---
                 await wait.edit("⚙️ **Adaptando video para Telegram (Audio vacío)...**")
                 has_audio = await has_audio_track(success_path)
                 if not has_audio or m.animation:
                     await wait.edit("🔇 **Añadiendo pista silenciosa para forzar formato de video...**")
                     new_path = await add_silent_audio(success_path)
                     if new_path and os.path.exists(new_path):
                         try: os.remove(success_path)
                         except: pass
                         success_path = new_path

                 await wait.edit("📤 **Enviando Video Convertido...**")
                 
                 # Extraer Meta y Thumb
                 w, h, dur = await get_meta(success_path)
                 t_path = await get_thumb(success_path, cid, int(time.time()), duration=dur)
                 
                 try:
                     await c.send_video(
                         cid, success_path, 
                         width=w, height=h, duration=dur, 
                         thumb=t_path, 
                         caption=f"📦 **Convertido QH**", 
                         progress=progreso, progress_args=(wait, [0,0], "Enviando")
                     )
                 except Exception:
                     # Fallback Document
                     await c.send_document(
                         cid, success_path, 
                         caption=f"📦 **Convertido QH** (Doc Fallback)", 
                         progress=progreso, progress_args=(wait, [0,0], "Enviando")
                     )

                 # Limpieza
                 if t_path and os.path.exists(t_path): os.remove(t_path)
                 if os.path.exists(success_path): os.remove(success_path)
                 
                 try: await wait.delete()
                 except: pass
             else:
                 await wait.edit("❌ Error en la descarga del video.")
        return

async def set_bot_commands(c: Client):
    from pyrogram.types import BotCommand
    commands = [
        BotCommand("start", "🚀 Iniciar el bot"),
        BotCommand("help", "❓ Ayuda y funcionamiento")
    ]
    try:
        await c.set_bot_commands(commands)
        print("✅ Comandos de acceso rápido configurados.")
    except Exception as e:
        print(f"⚠️ No se pudieron configurar los comandos: {e}")

async def handle_web(request):
    return web.Response(text="Bot Funcionando 🚀")

async def start_web_server():
    app_web = web.Application()
    app_web.router.add_get('/', handle_web)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 7860)
    await site.start()
    print("🌍 Servidor Aiohttp (Direct Link) activo en puerto 7860")

if __name__ == "__main__":
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    print("🚀 Iniciando Convertidor QH...")
    
    # Modo de arranque compatible y seguro
    app.start()
    app.loop.run_until_complete(start_web_server())
    app.loop.run_until_complete(set_bot_commands(app))
    print("✅ Bot en línea y listo.")
    pyrogram.idle()
    app.stop()