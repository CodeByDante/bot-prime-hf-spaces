import asyncio
import os
import sys
import yt_dlp
import time
import re
import shutil
import logging
import psutil
import pyrogram
from pyrogram import Client, filters, idle
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    InputMediaPhoto, InputMediaDocument, InputMediaVideo, InputMediaAnimation, Message,
    BotCommand, WebAppInfo
)
from pyrogram.errors import FloodWait
from io import BytesIO
import aiohttp
import threading
import random
# import uvicorn # Removed but kept for safety if referenced elsewhere, actually removing it is better.
# import uvicorn
# from fastapi import FastAPI
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- WEB SERVER SETUP (AIOHTTP STREAMING) ---
from aiohttp import web

async def handle_health(request):
    return web.Response(text="OK")

async def web_download_handler(request):
    chat_id = request.match_info.get('chat_id')
    msg_id = request.match_info.get('msg_id')
    
    if not chat_id or not msg_id: return web.Response(status=400, text="Bad Request")
    try:
        chat_id, msg_id = int(chat_id), int(msg_id)
    except: return web.Response(status=400, text="Invalid IDs")
    
    try:
        msg = await app.get_messages(chat_id, msg_id)
        if not msg or getattr(msg, 'empty', True): return web.Response(status=404, text="Message not found")
        
        media = msg.video or msg.document or msg.audio or msg.animation or msg.photo
        if not media: return web.Response(status=404, text="No media found")
        
        file_size = getattr(media, 'file_size', 0)
        file_name = getattr(media, 'file_name', 'downloaded_file')
        mime_type = getattr(media, 'mime_type', 'application/octet-stream')
        
        response = web.StreamResponse(
            status=200, reason='OK',
            headers={
                'Content-Type': mime_type,
                'Content-Disposition': f'attachment; filename="{file_name}"',
                'Content-Length': str(file_size)
            }
        )
        await response.prepare(request)
        async for chunk in app.stream_media(msg):
            await response.write(chunk)
        await response.write_eof()
        return response
    except Exception as e:
        print(f"Streaming Error: {e}")
        return web.Response(status=500, text="Internal Server Error")

async def start_web_server():
    app_web = web.Application()
    app_web.router.add_get('/', handle_health)
    app_web.router.add_get('/dl/{chat_id}/{msg_id}', web_download_handler)
    app_web.router.add_get('/dl/{chat_id}/{msg_id}/', web_download_handler)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 7860)
    await site.start()
    print("🌍 Servidor Aiohttp (Direct Link) activo en puerto 7860")

# --- IMPORTACIONES DEL PROYECTO ---
from config import API_ID, API_HASH, BOT_TOKEN, DATA_DIR, COOKIE_MAP, DATABASE_CHANNEL, BASE_DIR, OWNER_ID, GEMINI_API_KEY
from database import get_config, url_storage, hashtag_db, can_download, cancel_all, add_active, remove_active, load_viral, save_viral, viral_music_db, set_exclusive_mode
from utils import format_bytes, limpiar_url, sel_cookie, resolver_url_facebook, descargar_galeria, scan_channel_history, search_saucenao, format_saucenao_results, search_tracemoe, format_tracemoe_results
from utils_chat_actions import chat_action_loop
from jav_extractor import extraer_jav_directo
from downloader import procesar_descarga, SEM_DOWNLOAD, get_user_semaphore
from manga_service import (
    get_all_mangas_paginated, get_manga_metadata, 
    process_manga_download, get_or_cache_cover,
    get_manga_chapters
)
from firebase_service import (
    save_bot_config, get_cached_file, save_cached_file, 
    get_cached_data, register_user, get_user_rules_fb, 
    save_user_rule_fb, save_global_persona, 
    get_all_global_personas, delete_global_persona_fb,
    save_persona_image, get_persona_images,
    save_viral_item_fb, delete_viral_item_fb, load_all_viral_items_fb # New imports
)
from ai_service import init_ai, ask_gemini, clear_chat_memory, generate_hashtags_ai
from tts_service import generate_tts_audio
from tagger_tool import run_tagger_logic

# Cache for Avatar Categories (Lazy Loaded)
# Structure: {persona_id: set([cat1, cat2, ...])}
AVATAR_KEYS_CACHE = {}

# --- SEMAPHORE FOR AUTO CORTE (Max 5 concurrent) ---
SEM_AUTO_CORTE = asyncio.Semaphore(5)
# --- SEMAPHORE FOR CONVERTIDOR QH (Max 5 concurrent) ---
SEM_CONVERT_QH = asyncio.Semaphore(5)
# --- SEMAPHORE FOR CONVERTIDOR MP4 H264 (Max 5 concurrent) ---
SEM_CONVERT_H264 = asyncio.Semaphore(5)
# --- SEMAPHORE FOR COLLAGE (Max 5 concurrent) ---
SEM_COLLAGE = asyncio.Semaphore(5)
# --- SEMAPHORES ---
# Limit downloads to 5 concurrent
SEM_DOWNLOAD = asyncio.Semaphore(5)
# Limit analysis (initial message/extraction) to 3 concurrent to prevent FloodWait
SEM_ANALYSIS = asyncio.Semaphore(3)
# --- SEMAPHORE FOR SUBTITLES (Max 5 concurrent) ---
SEM_SUB = asyncio.Semaphore(5)
# --- SEMAPHORE FOR SMART CUT (Max 3 concurrent) ---
SEM_SMART_CUT = asyncio.Semaphore(3)
# --- SEMAPHORE FOR PARTY MODE (Max 5 concurrent) ---
SEM_PARTY = asyncio.Semaphore(5)
# --- LOCKS FOR PARTY SENDING (Serial sending per Chat) ---
PARTY_SEND_LOCKS = {}

# --- VIDEO MIXER BUFFER & LOCKS ---
# Buffer: {chat_id: [(msg_id, path), ...]}
VIDEO_MIXER_BUFFERS = {}
VIDEO_MIXER_LOCKS = {} # {chat_id: asyncio.Lock()}
from video_mixer import mix_videos_side_by_side

# --- NANO BANANA BATCH BUFFER (Multi-Image Support) ---
# Format: {chat_id: {'images': [path1, path2], 'text': "last caption", 'task': asyncio.Task}}
NANO_BATCH_BUFFER = {}

# --- NANO PENDING CONTEXT (Waiting for Text Prompt) ---
# Format: {chat_id: [img_path1, img_path2]}
NANO_PENDING_CONTEXT = {}

# --- QUEUE SEMAPHORE (Anti-Crash) ---
SEM_EXCLUSIVE_VIDEO = asyncio.Semaphore(3)

# --- COLLAGE BATCH BUFFER ---
COLLAGE_BATCH_BUFFER = {}

async def run_collage_batch(chat_id, client):
    """Waits for multiple media files and processes them as a collage."""
    try:
        await asyncio.sleep(4.0) # Wait for album/more files (4s is safer for big albums)
        
        if chat_id not in COLLAGE_BATCH_BUFFER: return
        data = COLLAGE_BATCH_BUFFER.pop(chat_id)
        
        files = data['files']
        wm = data['wm']
        
        if not files: return
        
        # Determine Grid
        count = len(files)
        conf = get_config(chat_id)
        grid = conf.get('collage_grid', None) # If None, auto-calc in tools_media.py
        
        # Feedback
        try: await wm.edit(f"🧩 **Procesando Collage ({count} archivos)...**")
        except: pass
        
        from tools_media import create_mixed_media_collage, get_meta, progreso
        
        # Process
        out_path = await create_mixed_media_collage(files, grid=grid)
        
        if out_path and os.path.exists(out_path):
             # Upload
             try: await wm.edit("📤 **Subiendo Collage...**")
             except: pass
             
             async with chat_action_loop(client, chat_id, pyrogram.enums.ChatAction.UPLOAD_PHOTO):
                 await client.send_photo(
                     chat_id, out_path, 
                     caption=f"🧩 **Collage Generado** ({count} elementos)"
                 )
             
             # Cleanup
             os.remove(out_path)
        else:
             try: await wm.edit("❌ Error creando collage.")
             except: pass
             
        # Cleanup inputs
        for f in files:
            if os.path.exists(f): 
                try: os.remove(f)
                except: pass
        
        # Cleanup Job Dir
        try:
             job_dir = os.path.dirname(files[0]) if files else None
             if job_dir and "job_" in os.path.basename(job_dir) and os.path.exists(job_dir):
                  import shutil
                  shutil.rmtree(job_dir, ignore_errors=True)
        except: pass

        # Auto-OFF Check
        from firebase_service import save_user_config_fb
        conf['collage_mode'] = False
        asyncio.create_task(save_user_config_fb(chat_id, conf))
        
        await client.send_message(chat_id, "✅ **Proceso Finalizado.** (Modo Apagado)")
        try: await wm.delete()
        except: pass
        
    except Exception as e:
        print(f"Collage Batch Error: {e}")
        if chat_id in COLLAGE_BATCH_BUFFER: COLLAGE_BATCH_BUFFER.pop(chat_id, None)


async def run_nano_batch(chat_id, client):
    """Espera un momento para agrupar imágenes (album) y luego PIDE EL PROMPT."""
    try:
        # Esperar a que lleguen más fotos (simulando álbum)
        await asyncio.sleep(2.5) 
        
        # Recuperar datos del buffer
        if chat_id not in NANO_BATCH_BUFFER: return
        data = NANO_BATCH_BUFFER.pop(chat_id)
        
        image_paths = data['images']
        wm_msg = data.get('wm')
        
        if not image_paths: return

        # --- AUTO TRIGGER IF CAPTION PRESENT ---
        user_prompt = data.get('text')
        if user_prompt and len(user_prompt.strip()) > 0:
            print(f"🍌 [NanoBanana] Caption detected: '{user_prompt}'. Triggering immediately.")
            
            # Delete "Viendo..." message
            if wm_msg:
                try: await wm_msg.delete()
                except: pass

            # Move images to global pending context (so ai_chat_handler finds them)
            NANO_PENDING_CONTEXT[chat_id] = image_paths
            
            # Create MOCK Message to trigger ai_chat_handler
            # We need to simulate a Text Message
            from types import SimpleNamespace
            
            mock_msg = SimpleNamespace(
                chat=SimpleNamespace(id=chat_id),
                from_user=data['msg'].from_user,
                text=user_prompt,
                caption=None,
                photo=None,
                document=None,
                reply_to_message=None,
                video=None,
                id=data['msg'].id # Keep original ID or new? Original is fine.
            )
            
            # Inject methods that might be called
            async def mock_reply(text, **kwargs):
                return await client.send_message(chat_id, text, **kwargs)
            
            async def mock_reply_document(document, **kwargs):
                return await client.send_document(chat_id, document, **kwargs)

            async def mock_reply_photo(photo, **kwargs):
                return await client.send_photo(chat_id, photo, **kwargs)
            
            mock_msg.reply = mock_reply
            mock_msg.reply_document = mock_reply_document
            mock_msg.reply_photo = mock_reply_photo
            
            # Manual Call to Handler
            await ai_chat_handler(client, mock_msg)
            return

        print(f"🍌 [NanoBanana] Album Collected: {len(image_paths)} images. Waiting for User Prompt.")
        
        # MOVE TO PENDING CONTEXT (Waiting for text)
        existing = NANO_PENDING_CONTEXT.get(chat_id, [])
        # Avoid duplicates just in case? No, paths are unique by timestamp.
        combined = existing + image_paths
        NANO_PENDING_CONTEXT[chat_id] = combined
        
        # Update existing "Recibido" message or send new one
        msg_sent = False
        if wm_msg:
            try: 
                await wm_msg.edit_text(
                    f"✅ **Recibido. Total imágenes: {len(combined)}**\n✍️ **Escribe tu prompt cuando estés listo.**",
                    reply_markup=wm_msg.reply_markup
                )
                msg_sent = True
            except: 
                pass
        
        if not msg_sent:
            await client.send_message(
                chat_id, 
                f"✅ **Recibido. Total imágenes: {len(combined)}**\n✍️ **Escribe tu prompt cuando estés listo.**"
            )
            
    except Exception as e:
        print(f"❌ Nano Batch Error: {e}")
        if chat_id in NANO_BATCH_BUFFER: NANO_BATCH_BUFFER.pop(chat_id, None)

# SPANISH TRANSLATIONS (GLOBAL)
TRANS = {
    # Social
    'greeting': 'Saludo', 'bienvenida': 'Bienvenida', 'welcome': 'Bienvenida', 'happy': 'Feliz', 'laugh': 'Risa', 'angry': 'Enojada', 'pouting': 'Puchero',
    'sad': 'Triste', 'shock': 'Sorpresa', 'confused': 'Confundida', 'scared': 'Asustada', 'disgusted': 'Asco',
    'thinking': 'Pensando', 'wink': 'Guiño', 'bored': 'Aburrida', 'tired': 'Cansada', 'drunk': 'Borracha',
    'crazy': 'Loca', 'pleading': 'Suplicando', 'smug': 'Presumida', 'shy': 'Tímida',
    # Romance
    'love': 'Enamorada', 'kiss': 'Beso', 'deep_kiss': 'Beso Lengua', 'blow_kiss': 'Beso Aire',
    'hug': 'Abrazo', 'holding': 'Manos', 'lap_pillow': 'Regazo (Almohada)', 'lap_sit': 'Sentada en Ti',
    'feeding': 'Dando Comer', 'headpat': 'Caricias', 'cuddle': 'Acurrucados', 'lean': 'Apoyada',
    'cheek': 'Beso Mejilla', 'forehead': 'Beso Frente', 'ring': 'Anillo', 'date': 'Cita', 'heart': 'Corazón',
    'stare': 'Mirada Fija',
    # Outfits
    'casual': 'Casual', 'dress': 'Vestido', 'sundress': 'Vestido Verano', 'wedding': 'Novia',
    'bikini': 'Bikini', 'micro': 'Micro Bikini', 'gym': 'Gimnasio', 'school': 'Colegiala',
    'bloomer': 'Bloomers', 'maid': 'Maid', 'nurse': 'Enfermera', 'police': 'Policía',
    'bunny': 'Conejita', 'cheongsam': 'China', 'kimono': 'Kimono', 'goth': 'Gótica',
    'ol': 'Oficina', 'sweater': 'Suéter', 'pajamas': 'Pijama', 'towel': 'Toalla', 'apron': 'Delantal',
    # Soft
    'horny': 'Caliente', 'lingerie': 'Lencería', 'bra': 'Sostén', 'panties': 'Bragas',
    'nude': 'Desnudo Frontal', 'nude_back': 'Desnudo Espalda', 'ass': 'Culo', 'boobs': 'Pechos',
    'nipples': 'Pezones', 'feet': 'Pies', 'legs': 'Piernas', 'armpits': 'Axilas',
    'sweat': 'Sudor', 'oil': 'Aceite', 'bondage': 'Atada', 'collar': 'Collar',
    # Hard
    'masturb': 'Dedo/Mast', 'toy_play': 'Juguete', 'blowjob': 'Oral', 'deepthroat': 'Garganta Profunda',
    'cum_mouth': 'Semen Boca', 'facesit': 'Sentada Cara', 'paizuri': 'Cubana', 'handjob': 'Paja',
    'doggy': 'Perrito', 'mission': 'Misionero', 'cowgirl': 'Cabalgando', 'standing': 'De Pie',
    'anal': 'Anal', 'gangbang': 'Grupo', 'double': 'Doble Pen', 'lesbian': 'Lesbico', '69': '69',
    # Climax
    'cum_face': 'Semen Cara', 'cum_body': 'Semen Cuerpo', 'creampie': 'Creampie', 'anal_pie': 'Anal Pie',
    'bukkake': 'Bukkake', 'ahegao': 'Ahegao', 'after': 'Post-Sexo', 'mess': 'Sucia',
    # Life (and Vulgar)
    'sleep': 'Durmiendo', 'eat': 'Comiendo', 'bath': 'Bañera', 'toilet': 'Baño', 'selfie': 'Selfie',
    'pussy': 'Vagina', 'dick': 'Pene', 'anus': 'Ano', 'spread': 'Abriendo',
    'orgy': 'Orgía', 'cuckold': 'Cornudo', 'sex': 'Sexo', 'slut': 'Puta', 'milk': 'Leche', 'cum': 'Semen', 'threesome': 'Trío',
    'rimjob': 'Beso Negro', 'spit': 'Saliva', 'choking': 'Ahorcando', 'spank': 'Nalgadas', 'fisting': 'Fisting', 'squirt': 'Squirt',
    # Cosplay / Extra
    'cat_girl': 'Gatita', 'dog_girl': 'Perrita', 'cow_girl': 'Vaquita', 'fox_girl': 'Zorrita',
    'doctor': 'Doctora', 'teacher': 'Maestra', 'nun': 'Monja', 'witch': 'Bruja',
    'vampire': 'Vampiresa', 'succubus': 'Súcubo', 'elf': 'Elfa', 'goblin': 'Duende',
    # Packs
    'pack_boobs': 'Pack Tetas', 'pack_ass': 'Pack Culo', 'pack_pussy': 'Pack Vagina',
    'pack_nude': 'Pack Cuerpo', 'pack_feet': 'Pack Pies', 'pack_dildo': 'Pack Juguetes',
    'pack_underwear': 'Pack Ropa Interior', 'pack_cam': 'Pack Cam/Selfie'
}

# --- VARIABLES GLOBALES ---
logging.basicConfig(level=logging.INFO)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- GLOBAL CACHE ---
global_personas = {}

async def refresh_globals():
    """Recarga las personalidades globales desde Firebase."""
    global global_personas, viral_music_db
    try:
        global_personas = await get_all_global_personas()
        print(f"🌍 [Main] Global Personas Loaded: {len(global_personas)}")
        
        # ALSO LOAD VIRAL MUSIC DB HERE
        viral_music_db = await load_all_viral_items_fb()
        print(f"🎵 [Main] Global Viral Items Loaded: {len(viral_music_db)}")
        
    except Exception as e:
        print(f"⚠️ Global Refresh Error: {e}")

# --- 1. FIX WINDOWS LOOP ---
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- 2. CONFIGURACIÓN CLIENTE ---
WORKDIR = "sessions"
if not os.path.exists(WORKDIR):
    os.makedirs(WORKDIR)

app = Client(
    "brody_final_v2", 
    api_id=int(API_ID),
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN, 
    workers=100,
    workdir=WORKDIR,
    ipv6=False,
    sleep_threshold=60,
    max_concurrent_transmissions=8
)

BOT_USERNAME = None

# --- HELPER: LOGICA PARTY ---
async def run_extract_logic(client, chat_id, file_path, mode, val, msg_to_edit=None):
    from utils import extract_images_ffmpeg, create_split_zips
    
    if msg_to_edit: await msg_to_edit.edit(f"🖼 **Extrayendo imágenes ({mode}={val})...**")
    else: msg_to_edit = await client.send_message(chat_id, f"🖼 **Extrayendo imágenes ({mode}={val})...**")

    try:
        imgs, out_dir = await asyncio.get_running_loop().run_in_executor(None, lambda: extract_images_ffmpeg(file_path, val, mode))
        
        if not imgs:
            await msg_to_edit.edit("❌ No se pudieron extraer imágenes. Verifica el tiempo/intervalo.")
            return False

        conf = get_config(chat_id)
        is_zip = conf.get('extract_party_zip', True)
        is_doc = conf.get('doc_mode_tools', False)
        is_group = conf.get('group_mode_tools', False)

        if is_zip:
            await msg_to_edit.edit(f"📦 **Comprimiendo {len(imgs)} imágenes...**")
            base_name = f"Extracted_{chat_id}_{int(time.time())}"
            zip_files = await asyncio.get_running_loop().run_in_executor(None, lambda: create_split_zips(imgs, base_name))
            
            for zp in zip_files:
                async with chat_action_loop(client, chat_id, pyrogram.enums.ChatAction.UPLOAD_DOCUMENT):
                    await client.send_document(chat_id, zp, caption=f"🖼 **Extractor**: {len(imgs)} fotogramas ({mode}={val})")
                if os.path.exists(zp): os.remove(zp)
        else:
            await msg_to_edit.edit(f"📤 **Enviando {len(imgs)} imágenes...**")
            if is_group and len(imgs) > 1:
                # Enviar como Media Group (max 10 cada uno)
                chunks = [imgs[i:i + 10] for i in range(0, len(imgs), 10)]
                for chunk in chunks:
                    media = []
                    for img in chunk:
                        if is_doc: media.append(InputMediaDocument(media=img))
                        else: media.append(InputMediaPhoto(media=img))
                    async with chat_action_loop(client, chat_id, pyrogram.enums.ChatAction.UPLOAD_PHOTO):
                        await client.send_media_group(chat_id, media)
            else:
                # Individual
                for img in imgs:
                    if is_doc:
                        async with chat_action_loop(client, chat_id, pyrogram.enums.ChatAction.UPLOAD_DOCUMENT):
                            await client.send_document(chat_id, img)
                    else:
                        async with chat_action_loop(client, chat_id, pyrogram.enums.ChatAction.UPLOAD_PHOTO):
                            await client.send_photo(chat_id, img)

        await msg_to_edit.delete()
        
        # Cleanup Job Dir
        import shutil
        job_dir = os.path.dirname(file_path)
        if 'job_' in os.path.basename(job_dir) and os.path.exists(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)
        elif os.path.exists(out_dir): 
            shutil.rmtree(out_dir)
        
        # Auto-OFF logic
        conf = get_config(chat_id)
        if not conf.get('auto_extract', False):
            conf['extract_mode'] = False
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            
        return True
    except Exception as e:
        await msg_to_edit.edit(f"❌ Error en Extractor: {e}")
        return False


async def run_gif_logic(client, chat_id, file_path, msg_to_edit=None):
    from utils import video_to_gif_ffmpeg
    if msg_to_edit: await msg_to_edit.edit("🎞 **Convirtiendo a GIF...**")
    else: msg_to_edit = await client.send_message(chat_id, "🎞 **Convirtiendo a GIF...**")

    try:
        gif_file = await asyncio.get_running_loop().run_in_executor(None, lambda: video_to_gif_ffmpeg(file_path))
        if gif_file:
            async with chat_action_loop(client, chat_id, pyrogram.enums.ChatAction.UPLOAD_VIDEO):
                await client.send_animation(chat_id, gif_file, caption="🎬 **GIF Creado**")
            
            # Smart Cleanup
            import shutil
            job_dir = os.path.dirname(file_path)
            if 'job_' in os.path.basename(job_dir) and os.path.exists(job_dir):
                shutil.rmtree(job_dir, ignore_errors=True)
            elif os.path.exists(gif_file): os.remove(gif_file)
            
            await msg_to_edit.delete()
        else:
            await msg_to_edit.edit("❌ Error al convertir a GIF.")
    except Exception as e:
        await msg_to_edit.edit(f"❌ Error: {e}")
    finally:
        # Auto-OFF
        conf = get_config(chat_id)
        conf['gif_mode'] = False
        from firebase_service import save_user_config_fb
        asyncio.create_task(save_user_config_fb(chat_id, conf))


async def run_sticker_logic(client, chat_id, file_path, msg_to_handle=None):
    from utils import create_telegram_sticker
    
    # Mensaje de espera
    wm = await client.send_message(chat_id, "🎭 **Creando Video Sticker (VP9)...**")
    
    try:
        # Generamos el sticker optimizado
        sticker_file = await asyncio.get_running_loop().run_in_executor(None, lambda: create_telegram_sticker(file_path, is_emoji=False))
        
        if sticker_file:
            # Enviamos el sticker
            # Nota: Al ser .webm y formato correcto, Telegram debería mostrarlo como sticker.
            async with chat_action_loop(client, chat_id, pyrogram.enums.ChatAction.UPLOAD_VIDEO):
                await client.send_sticker(chat_id, sticker_file)
            
            # Mensaje de éxito
            await wm.edit("✅ **Sticker Generado.**\n(Añádelo a tus favoritos o reenvíalo)")
            
            if os.path.exists(sticker_file): os.remove(sticker_file)
        else:
            await wm.edit("❌ Error al crear sticker (FFmpeg).")
            
    except Exception as e:
        await wm.edit(f"❌ Error General: {e}")
    finally:
        conf = get_config(chat_id)
        conf['sticker_mode'] = False
        from firebase_service import save_user_config_fb
        asyncio.create_task(save_user_config_fb(chat_id, conf))


async def run_saucenao_logic(client, chat_id, file_path, msg_to_edit=None):
    from utils import search_saucenao, format_saucenao_results, search_tracemoe, format_tracemoe_results
    
    if msg_to_edit: await msg_to_edit.edit("🔍 **Buscando información...**")
    else: msg_to_edit = await client.send_message(chat_id, "🔍 **Buscando información...**")
    
    try:
        # 1. SauceNAO
        results_sauce = await asyncio.get_running_loop().run_in_executor(None, lambda: search_saucenao(file_path))
        msg_sauce = format_saucenao_results(results_sauce)
        
        # 2. Trace.moe
        results_trace = await asyncio.get_running_loop().run_in_executor(None, lambda: search_tracemoe(file_path))
        msg_trace, video_preview, is_adult = format_tracemoe_results(results_trace)
        
        # Combine Results
        final_msg = f"{msg_sauce}\n\n━━━━━━━━━━━━━━━━━━━━\n\n{msg_trace}"
        
        # Enviar resultados
        # Intentamos enviar como reply a la imagen si es posible, sino editamos el mensaje de espera
        await msg_to_edit.edit(final_msg, disable_web_page_preview=True)
        
        # Opcional: Si trace.moe dio preview, podríamos enviarlo.
        # Por ahora lo dejamos solo en texto para no spammear.
        
    except Exception as e:
        await msg_to_edit.edit(f"❌ Error en Búsqueda: {e}")
    finally:
        # Cleanup file
        if os.path.exists(file_path): 
            try: os.remove(file_path)
            except: pass
            
        # Auto-OFF
        conf = get_config(chat_id)
        conf['saucenao_mode'] = False
        from firebase_service import save_user_config_fb
        asyncio.create_task(save_user_config_fb(chat_id, conf))


async def run_tagger_text_logic(client, chat_id, text, msg):
    from ai_service import generate_hashtags_ai
    try:
        tags = await asyncio.get_running_loop().run_in_executor(None, lambda: generate_hashtags_ai(text))
        await msg.reply(tags)
    except Exception as e:
        print(f"Error Tagger: {e}")
        await msg.reply(f"❌ Error al generar tags: {e}")

async def run_research_logic(client, chat_id, text=None, image_path=None, msg=None):
    from ai_service import research_character_ai
    try:
        # Feedback visual
        status = await msg.reply("🕵️‍♀️ **Investigando a fondo...**")
        
        tags = await asyncio.get_running_loop().run_in_executor(None, lambda: research_character_ai(text, image_path))
        
        await status.edit(tags)
    except Exception as e:
        print(f"Error Research: {e}")
        await msg.reply(f"❌ Error investigando: {e}")


async def run_party_logic(client, chat_id, file_path, mode, val, msg_to_edit=None, original_msg=None, context_config=None):
    from utils import split_video_generic, cut_video_range
    from tools_media import get_meta, get_thumb
    
    # --- LOAD CONFIG FROM CONTEXT OR DB ---
    # Si context_config es None, cargamos la actual (comportamiento legacy/fallback)
    # Pero si viene del handler, usaremos la "congelada" al momento de iniciar la tarea.
    if context_config is None:
        context_config = get_config(chat_id)

    if msg_to_edit:
        await msg_to_edit.edit(f"⏳ Procesando Party ({mode}={val})...")
    else:
         sm = await client.send_message(chat_id, f"⏳ Procesando Party ({mode}={val})...")
         msg_to_edit = sm

    try:
        if mode == 'parts':
            parts = await asyncio.get_running_loop().run_in_executor(None, lambda: split_video_generic(file_path, mode, float(val)))
        elif mode in ['sec', 'min']:
            parts = await asyncio.get_running_loop().run_in_executor(None, lambda: split_video_generic(file_path, mode, float(val)))
        elif mode == 'range':
            pts = str(val).split()
            if len(pts) < 2 or len(pts) % 2 != 0:
                await msg_to_edit.edit("❌ Formato de rango inválido. Deben ser pares (Ej: '10 20 30 40').")
                return False
            
            parts = []
            for i in range(0, len(pts), 2):
                s, e = pts[i], pts[i+1]
                p_path = await asyncio.get_running_loop().run_in_executor(None, lambda: cut_video_range(file_path, s, e))
                if p_path: parts.append(p_path)
        else:
            parts = []

        if not parts:
            await msg_to_edit.edit("❌ Error al procesar el video.")
            return False

        # --- LOGICA ZIP MODE ---
        # Usamos context_config congelada
        is_zip_mode = context_config.get('party_zip', False)
        
        if is_zip_mode:
            await msg_to_edit.edit(f"📦 Comprimiendo {len(parts)} partes en ZIP...")
            # Calcular nombre base
            base_zip = file_path.rsplit('.', 1)[0] + "_party"
            from utils import create_split_zips
            
            # Crear zips (run in executor for blocking I/O)
            zip_files = await asyncio.get_running_loop().run_in_executor(None, lambda: create_split_zips(parts, base_zip))
            
            # Limpiar partes originales ya que están en el zip
            for p in parts:
                try: os.remove(p)
                except: pass
                
            parts = zip_files # Reemplazamos la lista de partes con los ZIPs
            
        # --- LOGICA ENVIO (Agrupado o Individual) ---
        # Usamos context_config congelada
        
        # FIX: Si es DOC MODE, forzamos thumb=None para que se vea como archivo genérico (icono azul)
        send_as_doc_mode = context_config.get('doc_mode_tools', False)
        use_group_mode = context_config.get('group_mode_tools', False) and len(parts) > 1
        
        # --- LOCK SENDING PHASE PER CHAT ---
        # Garantiza que no se mezclen los mensajes si hay varios videos procesándose a la vez en el mismo chat.
        if chat_id not in PARTY_SEND_LOCKS:
             PARTY_SEND_LOCKS[chat_id] = asyncio.Lock()
             
        async with PARTY_SEND_LOCKS[chat_id]:
            # --- SEND ORIGINAL VIDEO FIRST (User Request) ---
            if original_msg:
                try:
                    await msg_to_edit.edit(f"📤 Enviando video original...")
                    await original_msg.copy(chat_id, caption="🎬 **Video Original**")
                except Exception as e:
                    print(f"Error copying original: {e}")

            if use_group_mode:
                await msg_to_edit.edit(f"📤 Enviando {len(parts)} parte(s) en álbum...")
                
                # Dividir en chunks de 10 (Límite Telegram)
                chunks = [parts[i:i + 10] for i in range(0, len(parts), 10)]
                ts = int(time.time())
                
                for i, chunk in enumerate(chunks):
                    media_group = []
                    temp_thumbs = []
                    
                    for j, p in enumerate(chunk):
                        try:
                            thumb = None
                            width, height, duration = None, None, None
                            
                            if not is_zip_mode and not send_as_doc_mode:
                                w, h, dur = await get_meta(p)
                                t_path = await get_thumb(p, chat_id, f"{ts}_{i}_{j}")
                                thumb = t_path
                                temp_thumbs.append(t_path)
                                width, height, duration = w, h, dur
                            
                            # Caption solo en el primer elemento del grupo para no ensuciar
                            # Opcional: Poner caption en todos, pero "Party Video" x10 ensucia.
                            # Dejaremos caption vacía o mínima.
                            cap = "" 
                            if i == 0 and j == 0:
                                cap = "🎉 **Party Video** (Álbum)"
    
                            if is_zip_mode or send_as_doc_mode:
                                # Restoring thumb as downloader.py does.
                                media_group.append(InputMediaDocument(media=p, thumb=thumb, caption=cap))
                            elif p.lower().endswith(('.mp3', '.m4a', '.flac', '.wav', '.ogg')):
                                media_group.append(InputMediaAudio(media=p, thumb=thumb, caption=cap, duration=duration))
                            else:
                                media_group.append(InputMediaVideo(
                                    media=p, 
                                    thumb=thumb, 
                                    width=width, 
                                    height=height, 
                                    duration=duration, 
                                    caption=cap
                                ))
                        except Exception as e:
                            print(f"Error preparando media group item {j}: {e}")
                    
                    if media_group:
                        try:
                            async with chat_action_loop(client, chat_id, pyrogram.enums.ChatAction.UPLOAD_VIDEO):
                                await client.send_media_group(chat_id, media_group)
                        except Exception as e:
                            print(f"Error enviando Media Group: {e}")
                            # Fallback a envios individuales si falla el grupo
                            for item in media_group:
                                try:
                                    if isinstance(item, InputMediaDocument):
                                        await client.send_document(chat_id, item.media, thumb=item.thumb, caption=item.caption)
                                    elif isinstance(item, InputMediaAudio):
                                        await client.send_audio(chat_id, item.media, thumb=item.thumb, caption=item.caption, duration=item.duration)
                                    else:
                                        await client.send_video(chat_id, item.media, thumb=item.thumb, caption=item.caption)
                                except: pass
    
                    # Cleanup thumbs del chunk
                    for t in temp_thumbs:
                        if os.path.exists(t): os.remove(t)
    
            else:
                # --- ENVIO INDIVIDUAL (Legacy Logic) ---
                await msg_to_edit.edit(f"📤 Enviando {len(parts)} {'ZIPs' if is_zip_mode else 'partes'}...")
                ts = int(time.time())
                for i, p in enumerate(parts):
                    try:
                        thumb = None
                        width, height, duration = None, None, None
                        
                        # Si es video normal, extraemos meta. Si es ZIP, nada.
                        if not is_zip_mode:
                            # Extraer meta para cada parte
                            w, h, dur = await get_meta(p)
                            thumb = await get_thumb(p, chat_id, f"{ts}_{i}")
                            width, height, duration = w, h, dur
    
                        # if send_as_doc_mode: thumb = None # COMENTADO: Restauramos thumb
    
                        if is_zip_mode or send_as_doc_mode:
                             cap_lbl = "🎉 Party ZIP" if is_zip_mode else "🎉 Party Video (Doc)"
                             if len(parts) > 1: cap_lbl += f" - Parte {i+1}"
                             
                             async with chat_action_loop(client, chat_id, pyrogram.enums.ChatAction.UPLOAD_DOCUMENT):
                                 await client.send_document(
                                    chat_id, p,
                                    thumb=thumb,
                                    caption=cap_lbl,
                                    force_document=True
                                 )
                        else:
                            if p.lower().endswith(('.mp3', '.m4a', '.flac', '.wav', '.ogg')):
                                 async with chat_action_loop(client, chat_id, pyrogram.enums.ChatAction.UPLOAD_AUDIO):
                                     await client.send_audio(
                                        chat_id, p,
                                        duration=duration if duration else None,
                                        thumb=thumb,
                                        caption=f"🎉 Party: Parte {i+1}" if len(parts) > 1 else "🎉 Party Audio"
                                     )
                            else:
                                async with chat_action_loop(client, chat_id, pyrogram.enums.ChatAction.UPLOAD_VIDEO):
                                    await client.send_video(
                                        chat_id, p,
                                        width=width if width else None,
                                        height=height if height else None,
                                        duration=duration if duration else None,
                                        thumb=thumb,
                                        caption=f"🎉 Party: Parte {i+1}" if len(parts) > 1 else "🎉 Party Video"
                                    )
                        if thumb and os.path.exists(thumb): os.remove(thumb)
                    except Exception as e:
                        print(f"Error enviando parte {i}: {e}")
                        try: await client.send_document(chat_id, p)
                        except: pass
        
        # Cleanup final (Full Job Folder)
        import shutil
        job_dir = os.path.dirname(file_path)
        # Ensure we are deleting a 'job_' folder to avoid accidents
        if 'job_' in os.path.basename(job_dir) and os.path.exists(job_dir):
             try: shutil.rmtree(job_dir, ignore_errors=True)
             except: pass
        else:
             # Fallback cleanup
             try: 
                 if os.path.exists(file_path): os.remove(file_path)
                 for p in parts: 
                    if os.path.exists(p): os.remove(p)
             except: pass
        
        await msg_to_edit.delete()
        
        # --- AUTO-DISABLE PARTY MODE ---
        conf = get_config(chat_id)
        # Solo desactivar si NO está en modo Auto-Party (Persistent)
        if conf.get('party_mode') and not conf.get('auto_party', False):
            conf['party_mode'] = False
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            # Avisar y mostrar menú principal
            await client.send_message(chat_id, "✅ **Finalizado.**\nModo Party desactivado.", reply_markup=gen_kb(conf, chat_id))
            
        return True
    except Exception as e:
        await msg_to_edit.edit(f"❌ Error en Party: {e}")
        return False



# --- 3. DISEÑO DE MENÚ (DISEÑO REFINADO) ---
def gen_kb(conf, user_id=None):
    c_on, c_off = "🟢", "🔴"
    
    # 1. Metadatos (Full width)
    s_meta = c_on if conf.get('meta', True) else c_off
    btn_meta = InlineKeyboardButton(f"📝 Metadatos: {s_meta}", callback_data="toggle|meta")
    

    # 2. Turbo & Doc (Split)
    s_turbo = c_on if conf.get('fast_enabled', True) else c_off
    btn_turbo = InlineKeyboardButton(f"🚀 Turbo: {s_turbo}", callback_data="toggle|fast")
    s_doc = c_on if conf.get('doc_mode', False) else c_off
    btn_doc = InlineKeyboardButton(f"📄 Doc: {s_doc}", callback_data="toggle|doc")
    
    # 3. Agrup (Full width)
    s_group = c_on if conf.get('group_mode', True) else c_off
    btn_group = InlineKeyboardButton(f"📚 Agrup: {s_group}", callback_data="toggle|group")
    
    # 3.5 TXT Mode
    s_txt = c_on if conf.get('txt_mode', False) else c_off
    btn_txt = InlineKeyboardButton(f"📄 TXT: {s_txt}", callback_data="toggle|txt_mode")
    
    # 4. Auto (Full width)
    q_auto_val = conf.get('q_auto')
    txt_auto = "Desact."
    if q_auto_val == 'max': txt_auto = "Máx"
    elif q_auto_val == 'min': txt_auto = "Mín"
    elif q_auto_val in ['4320', '2160', '1440', '1080', '720', '480', '360', '240', '144']: txt_auto = f"{q_auto_val}p"
    btn_auto = InlineKeyboardButton(f"⚙️ Auto: {txt_auto}", callback_data="menu|auto")
    
    # 5. Idioma (Full width)
    lang = conf.get('lang', 'es')
    flag = "🇪🇸" if lang == 'es' else "🇺🇸"
    btn_lang = InlineKeyboardButton(f"🌐 Idioma: {flag}", callback_data="toggle|lang")
    
    # 6. Formato (Full width)
    fmt = conf.get('fmt', 'mp4')
    btn_fmt = InlineKeyboardButton(f"📦 Formato: 📹 {fmt.upper()}", callback_data="toggle|fmt")

    # 6.5 Pregunta descarga directa
    s_ask = c_on if conf.get('ask_direct', True) else c_off
    btn_ask_direct = InlineKeyboardButton(f"❓ Pregunta Descarga Directa: {s_ask}", callback_data="toggle|ask_direct")
    
    # 7. Modo Party (Split with Auto Party)
    btn_party = InlineKeyboardButton("🎉 Modo Party", callback_data="menu|party_init")
    
    # Auto Party Button (Status indicator)
    s_auto_p = "🟢" if conf.get('auto_party', False) else "🔴"
    btn_auto_party = InlineKeyboardButton(f"🔁 Auto: {s_auto_p}", callback_data="menu|autoparty_menu")

    # ZIP Party Button
    s_zip = "🟢" if conf.get('party_zip', False) else "🔴"
    btn_zip = InlineKeyboardButton(f"📦 ZIP: {s_zip}", callback_data="toggle|party_zip")

    # NUEVO: Mini App Web Button
    btn_webapp = InlineKeyboardButton(
        text="Twisted Brody Manga Flow",
        web_app=WebAppInfo(url="https://codebydrody-twistedbrodymangaflow.hf.space/")
    )
    
    # 8. Preview Mode (Full width)
    s_prev = "🟢" if conf.get('preview_mode', True) else "🔴"
    btn_prev = InlineKeyboardButton(f"👁️ Preview: {s_prev}", callback_data="toggle|preview")

    # Concurrent downloads configuration button
    max_dl = conf.get('max_downloads', 'default')
    if max_dl == 'default':
        lbl_dl = "Predeterminado"
    elif max_dl == 5:
        lbl_dl = "5 a la vez"
    elif max_dl == 10:
        lbl_dl = "10 a la vez"
    else:
        lbl_dl = str(max_dl)
    btn_max_dl = InlineKeyboardButton(f"⚡ Hilos: {lbl_dl}", callback_data="toggle|max_downloads")

    kb = [
        [btn_webapp], # 0. Mini App (Top Priority)
        [btn_meta],
        [btn_turbo, btn_doc],
        [btn_group, btn_txt],
        [btn_auto],
        [btn_lang],
        [btn_fmt],
        [btn_ask_direct],
        [btn_max_dl], # Dynamic concurrency limit button
        [btn_prev], # Preview Mode
        [InlineKeyboardButton("🛠 Herramientas", callback_data="menu|tools")]
    ]

    # Admin Panel (Sigue existiendo para el owner como botón extra)
    if user_id == OWNER_ID:
        kb.append([InlineKeyboardButton("👮‍♂️ Panel Admin (Stats)", callback_data="menu|admin")])

    return InlineKeyboardMarkup(kb)

# --- 4. HANDLERS DE MENSAJES ---

@app.on_message(group=-1)
async def log_message(c, m):
    try:
        uid = m.from_user.id if m.from_user else "Unknown"
        text = m.text if m.text else "[Media/Emoji]"
        print(f"📩 [MSG] From: {uid} | Text: {text[:50]}")
    except: pass
    m.continue_propagation()

@app.on_message(filters.command("ping"))
async def ping_cmd(c, m):
    import socket
    import sys
    msg = [f"🏓 **Pong!**", f"🐍 Py: {sys.version.split()[0]}"]
    
    targets = [("google.com", "Google"), ("www.youtube.com", "YouTube")]
    
    for host, label in targets:
        try:
            ip = socket.gethostbyname(host)
            msg.append(f"✅ {label}: `{ip}`")
        except Exception as e:
            msg.append(f"❌ {label}: `{e}`")
            
    await m.reply("\n".join(msg))

@app.on_message(filters.command("start"))
async def start_handler(c, m):
    uid = m.from_user.id
    cid = m.chat.id
    
    # 0. Check if finishing an upload session
    st = url_storage.get(cid)
    if st:
        # Clear AutoClass Mode
        if st.get('autoclass_mode'):
            url_storage.pop(cid, None)
            await m.reply("🛑 **Modo Auto-Clasificación DESACTIVADO.**")
            
        elif st.get('ai_config_step') == 'wait_image':
            count = st.get('count', 0)
            cat = st.get('category', 'Unknown')
            await m.reply(f"✅ **Carga Finalizada.**\nSe guardaron total {count} imágenes en `{cat}`.")
            url_storage.pop(cid, None)

    try:
        from firebase_service import register_user
        await register_user(uid, m.from_user.first_name, m.from_user.username)
    except: pass
    
    caption = (
        f"👋 **¡Hola {m.from_user.mention}!**\n\n"
        f"🚀 **Twisted Brody Bot Pro** está listo.\n"
        f"Configura tus preferencias abajo o envíame un link."
    )
    
    menu_caption = caption

    if uid == OWNER_ID: menu_caption = "⚙️ **Panel de Control (Modo Dios)**"

    # --- AI WAIFU WELCOME IMAGE ---
    # REVERTIDO: El usuario quiere que /start sea SIEMPRE el icono del bot.
    # La imagen de bienvenida IA solo se usará si se pide explícitamente a la IA.
    
    try:
        global START_ICON_FILE_ID
        if 'START_ICON_FILE_ID' not in globals() or not START_ICON_FILE_ID:
            from firebase_service import db
            me = c.me or await c.get_me()
            current_unique = getattr(me.photo, 'big_photo_unique_id', None) if me and getattr(me, 'photo', None) else None
            
            cached_unique = None
            cached_file_id = None
            doc_ref = None
            try:
                doc_ref = db.collection('bot_data').document('config')
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    cached_unique = data.get('bot_photo_unique_id')
                    cached_file_id = data.get('bot_photo_file_id')
            except Exception as e: 
                print(f"Error accessing firebase for photo: {e}")

            if current_unique and current_unique == cached_unique and cached_file_id:
                START_ICON_FILE_ID = cached_file_id
            elif current_unique:
                # La foto se actualizó en BotFather o no está en caché
                try:
                    photo_path = await c.download_media(me.photo.big_file_id)
                    if photo_path:
                        sent_msg = await m.reply_photo(photo=photo_path, caption=menu_caption, reply_markup=gen_kb(get_config(m.chat.id), uid))
                        import os
                        if os.path.exists(photo_path): os.remove(photo_path)
                        
                        if sent_msg and sent_msg.photo:
                            START_ICON_FILE_ID = sent_msg.photo.file_id
                            try:
                                if doc_ref: 
                                    doc_ref.set({
                                        'bot_photo_unique_id': current_unique,
                                        'bot_photo_file_id': START_ICON_FILE_ID
                                    }, merge=True)
                            except: pass
                        return
                except Exception as e:
                    print(f"Error downloading/sending new profile photo: {e}")

        if START_ICON_FILE_ID:
            try:
                await m.reply_photo(photo=START_ICON_FILE_ID, caption=menu_caption, reply_markup=gen_kb(get_config(m.chat.id), uid))
                return
            except Exception as e:
                print(f"Error using cached START_ICON_FILE_ID: {e}")
                START_ICON_FILE_ID = None
                
        # Send without photo if it doesn't have one
        await m.reply(menu_caption, reply_markup=gen_kb(get_config(m.chat.id), uid))
    except Exception as e:
        await m.reply(f"❌ Error CRITICO: {e}", reply_markup=gen_kb(get_config(m.chat.id), uid))

@app.on_message(filters.command("autoclass"))
async def autoclass_handler(c, m):
    """Activa el modo de auto-clasificación de imágenes para reacciones."""
    cid = m.chat.id
    
    # Check Active Persona
    conf = get_config(cid)
    active_p = conf.get('active_persona', 'nsfw')
    
    # Store Mode
    url_storage[cid] = url_storage.get(cid, {})
    url_storage[cid]['autoclass_mode'] = True
    url_storage[cid]['persona_id'] = active_p
    
    await m.reply(
        f"🧠 **Modo Auto-Clasificación ACTIVADO** ({active_p})\n\n"
        "📸 **Instrucciones:**\n"
        "1. Envía todas las fotos que quieras.\n"
        "2. La IA las analizará y las guardará en la categoría correcta (feliz, triste, nsfw, etc).\n"
        "3. Usa `/cancel` o toca 'Detener' cuando termines.\n\n"
        "👇 _¡Empieza a enviar fotos ahora!_"
    )

@app.on_message(filters.text & filters.private, group=2)
async def parallel_seek_input_handler(c, m):
    cid = m.chat.id
    st = url_storage.get(cid)
    
    if st and st.get('set_parallel_seek_mode'):
        try:
            val = int(m.text.strip())
            if val < 0: raise ValueError
            
            conf = get_config(cid)
            conf['parallel_thumb_seek'] = val
            
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            
            url_storage[cid].pop('set_parallel_seek_mode', None)
            
            await m.reply(
                f"✅ **Segundo de Miniatura Guardado:** `{val}s`\nAhora usaré este segundo para todas las miniaturas paralelas.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu|parallel_thumb_init")]])
            )
            m.stop_propagation()
            
        except ValueError:
            await m.reply("❌ **Error:** Envía solo un número válido (ej: `5`).")
            m.stop_propagation() # Stop to prevent download logic execution


@app.on_message(filters.command(["party", "unir_party", "extractor", "gif", "sticker", "sauce", "saucenao", "tagger", "mp3"]))
async def tool_shortcuts(c, m):
    """Atajos rápidos para activar herramientas."""
    cid = m.chat.id
    cmd = m.command[0].lower()
    
    msg_text = ""
    reply_markup = None # Add support for buttons
    
    mode_key = None
    
    # Map command to mode key
    if cmd == "party": mode_key = 'party_mode'
    elif cmd == "unir_party": mode_key = 'join_party_mode'
    elif cmd == "extractor": mode_key = 'extract_mode'
    elif cmd == "gif": mode_key = 'gif_mode'
    elif cmd == "sticker": mode_key = 'sticker_mode'
    elif cmd in ["sauce", "saucenao"]: mode_key = 'saucenao_mode'
    elif cmd == "tagger": mode_key = 'tagger_mode'
    elif cmd == "mp3": mode_key = 'mp3_mode'
    
    # Execute Exclusivity
    if mode_key:
        val, disabled = await set_exclusive_mode(cid, mode_key)
        if disabled:
            await m.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            
    # Set Specific Messages/Actions
    if cmd == "party":
        msg_text = "🎉 **Modo Party Activo**\n\n1️⃣ **Configura** abajo 👇\n2️⃣ O **envía video** directo."
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧩 Partes", callback_data="party_sel|parts"), InlineKeyboardButton("⏱ Tiempo", callback_data="party_sel|time")],
            [InlineKeyboardButton("✂️ Rango", callback_data="party_sel|range")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
        ])
        
    elif cmd == "unir_party":
        url_storage.pop(cid, None) # Limpiar clips previos
        msg_text = "🔗 **Modo Unir Party Activo**\n\n🎬 Envíame los clips que quieras fusionar uno por uno."
    elif cmd == "extractor":
        msg_text = "🖼 **Modo Extractor Activo**\n\n🎬 Envíame un video para empezar a sacar fotogramas."
    elif cmd == "gif":
        msg_text = "🎬 **Creador de GIF Activo**\n\n🎬 Envíame el video que quieras convertir a GIF."
    elif cmd == "sticker":
        msg_text = "🎭 **Creador de Stickers Activo**\n\n🖼 Envíame una imagen para convertirla en Sticker."
    elif cmd in ["sauce", "saucenao"]:
        msg_text = "🔍 **Buscador SauceNAO Activo**\n\n🖼 Envíame una imagen (Anime/Art) para buscar su fuente."
    elif cmd == "tagger":
        msg_text = "🏷️ **Etiquetadora Activa**\n\n📝 Escribe cualquier texto y lo convertiré en hashtags corregidos."
    elif cmd == "mp3":
        msg_text = "🎵 **Extractor MP3 Activo**\n\n🎬 Envíame un video y extraeré el audio en MP3."

    if msg_text:
        await m.reply(msg_text, reply_markup=reply_markup)

@app.on_message(filters.command("menu") | filters.command("settings") | filters.regex("⚙️ Configuración") | filters.regex("Menu"))
async def cmd_menu(c, m):
    uid = m.from_user.id
    
    # Texto Explicativo Profesional y Extenso
    txt = (
        "👑 **Twisted Brody Bot Pro - Guía de Usuario**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "¡Bienvenido! Aquí tienes todo lo que necesitas saber para dominar el bot.\n\n"
        "🔹 **HERRAMIENTAS DE VIDEO**\n"
        "• 🎉 **Party**: Corta videos, extrae clips o divide en partes iguales.\n"
        "• 🧩 **Unir Party**: Fusiona múltiples videos en uno solo.\n"
        "• 🖼 **Extractor**: Saca fotos de un video (frames exactos o intervalos).\n"
        "• 🎬 **GIF**: Crea GIFs animados de alta calidad desde videos.\n"
        "• 🎵 **MP3**: Extrae el audio de cualquier video a formato MP3.\n\n"
        "🔹 **OTRAS HERRAMIENTAS**\n"
        "• 🎭 **Sticker**: Convierte imágenes en stickers para Telegram.\n"
        "• 🔍 **SauceNAO**: Encuentra el artista o fuente original de una imagen.\n"
        "• 🏷️ **Tagger**: Convierte texto normal en hashtags formateados.\n\n"
        "🔹 **ATAJOS RÁPIDOS (COMANDOS)**\n"
        "• `/party` - Activar Cortar Video.\n"
        "• `/unir_party` - Activar Unir Videos.\n"
        "• `/extractor` - Activar Extractor de Fotos.\n"
        "• `/gif` - Activar Creador de GIFs.\n"
        "• `/mp3` - Activar Extractor de Audio.\n"
        "• `/sticker` - Activar Creador de Stickers.\n"
        "• `/sauce` - Activar Buscador de Fuentes.\n"
        "• `/tagger` - Activar Generador de Hashtags.\n\n"
        "🔹 **SISTEMA**\n"
        "• `/start` - Reinicio y Panel Principal.\n"
        "• `/menu` - Esta guía de ayuda.\n"
        "• `/cancel` - Detener todos los procesos.\n"
        "• `/ping` - Ver estado y latencia del bot.\n"
        "• `/id` - Ver tu ID y el del chat.\n\n"
        "💡 **TIP**: ¡Solo envíame un link de **YouTube, X, Pornhub, Eporner o Mediafire** para descargar!"
    )
    
    await m.reply(txt, reply_markup=gen_kb(get_config(m.chat.id), uid))

# --- HELPER: RESET TOTOAL ---
async def full_reset(c, cid, m=None):
    """Detiene todo y resetea modos."""
    # 1. Cancelar tareas y procesos
    n = await cancel_all(cid)
    
    # 2. Resetear Configuración (Modos)
    conf = get_config(cid)
    keys_to_reset = [
        'party_mode', 'join_party_mode', 'extract_mode', 'gif_mode', 
        'sticker_mode', 'saucenao_mode', 'mp3_mode', 'cut_init_mode', 
        'cut_auto_mode', 'auto_party', 'resize_mode', 'resize_auto_mode', 
        'thumb_mode', 'convert_qh_mode', 'convert_h264_mode', 
        'smart_cut_mode', 'collage_mode', 'sub_mode', 'sub_auto_mode', 
        'viral_mode', 'research_mode', 'tagger_mode', 'waifux2_mode',
        'parallel_thumb_mode'
    ]
    for k in keys_to_reset:
        conf[k] = False
        
    from firebase_service import save_user_config_fb
    asyncio.create_task(save_user_config_fb(cid, conf))
    
    # 3. Limpiar Storage
    url_storage.pop(cid, None)
    
    msg_txt = f"🛑 **CANCELADO TOTAL**\n\n✅ Procesos detenidos: {n}\n✅ Modos desactivados\n✅ Memoria limpia"
    
    if m:
        await m.reply(msg_txt, reply_markup=gen_kb(conf, cid))
    else:
        await c.send_message(cid, msg_txt, reply_markup=gen_kb(conf, cid))    

@app.on_message(filters.command("cancel"))
async def cancel_cmd(c, m):
    await full_reset(c, m.chat.id, m)

@app.on_callback_query()
async def cb(c, q):
    cid = q.message.chat.id
    uid = q.from_user.id
    data = q.data
    conf = get_config(cid)
    msg = q.message

    # 0. Answer query IMMEDIATELY to stop the loading icon
    try: await q.answer()
    except: pass

    # 1. Anti-Spam (Mejorado para evitar bugs de edición rápida)
    now = time.time()
    if not hasattr(app, 'click_locks'): app.click_locks = {}
    
    # Bypass lock for internal calls (mock objects don't have certain real attributes or we can flag them)
    is_internal = hasattr(q, 'internal')
    if not is_internal and now - app.click_locks.get(uid, 0) < 0.5: 
        return
    
    if not is_internal:
        app.click_locks[uid] = now

    try:
        if data == "cancel": 
            await full_reset(c, cid, None)
            try: await msg.delete()
            except: pass
            return

        if data == "delete_msg":
            await msg.delete()
            return

        # --- WAIFU2X HANDLER ---
        if data.startswith("waifu2x|"):
            file_path = data.split("|")[1]
            try:
                raw_val = data.split('|')[1]
                file_path = raw_val
                
                # Resolve Short ID
                if raw_val.startswith("w2x_"):
                     if raw_val in url_storage:
                         val = url_storage[raw_val]
                         if isinstance(val, dict): file_path = val.get('path')
                         else: file_path = val
                     else:
                         await q.answer("❌ Imagen expirada o no encontrada.", show_alert=True)
                         return

                if not os.path.exists(file_path):
                    await q.answer("❌ El archivo ya no existe (expirado).", show_alert=True)
                    return

                await msg.edit_text("✨ **Mejorando calidad (Waifu2x)...**")
                
                # Run in Executor to avoid blocking
                from utils import waifu2x_upscale
                upscaled_path = await asyncio.get_running_loop().run_in_executor(
                    None, 
                    lambda: waifu2x_upscale(file_path, scale=2, noise=2)
                )
                
                if upscaled_path:
                    # Check Tool Config
                    if conf.get('doc_mode_tools'):
                         await c.send_document(
                             cid, 
                             upscaled_path, 
                             caption="✨ **Imagen Mejorada (Waifu2x)**\n2x Upscale + Denoise Level 2"
                         )
                    else:
                         # Default behavior (Photo as Doc usually, but if user wants doc_mode off, maybe stick to current)
                         # Waifu2x usually best as Doc/Png. But if user untoggles Doc?
                         # Original code sent as document regardless.
                         # Let's keep send_document as default but allow send_photo if they REALLY want compressed?
                         # No, Waifu2x users probably want quality.
                         # But let's respect the "Doc" toggle if they want it as... photo?
                         # If doc_mode_tools is OFF -> send_photo (compressed).
                         await c.send_photo(
                             cid, 
                             upscaled_path, 
                             caption="✨ **Imagen Mejorada (Waifu2x)**\n2x Upscale + Denoise Level 2"
                         )
                    await msg.delete()
                    
                    try: os.remove(upscaled_path)
                    except: pass
                    
                else:
                    await msg.edit("❌ Error: Waifu2x falló (¿Faltan binarios o error de memoria?).")
                    
            except Exception as e:
                print(f"Waifu2x Callback Error: {e}")
                await msg.edit(f"❌ Error crítico: {e}")
            return




        # --- RENVIADO SUBMENU ---
        if data == "menu|renviado":
             s_dir = "🟢" if conf.get('renviado_directo', False) else "🔴"
             s_grp = "🟢" if conf.get('renviado_agrupado', False) else "🔴"
             
             kb_ren = InlineKeyboardMarkup([
                 [InlineKeyboardButton(f"Directo: {s_dir}", callback_data="toggle|renviado_directo"),
                  InlineKeyboardButton(f"Agrupados: {s_grp}", callback_data="toggle|renviado_agrupado")],
                 [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
             ])
             
             await msg.edit_text(
                 "🔄 **Herramienta: REENVIADO**\n\n"
                 "🔸 **Directo**: Reenvía videos inmediatamente (desagrupa álbumes).\n"
                 "🔸 **Agrupados**: Espera 5s y agrupa videos sueltos en un álbum.",
                 reply_markup=kb_ren
             )
             return

        if data == "toggle|preview":
             conf['preview_mode'] = not conf.get('preview_mode', True)
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             
             # Refresh Menu
             await msg.edit_reply_markup(reply_markup=gen_kb(conf, uid))
             return

        if data == "toggle|renviado_directo":
             # Exclusive Mode (Toggle)
             val, disabled = await set_exclusive_mode(cid, 'renviado_directo', is_toggle=True)
             
             if disabled:
                 await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
             
             conf = get_config(cid) 
             # Explicitly disable grouped (already done by set_exclusive_mode based on new keys)
             # But just in case logic:
             if val: 
                 conf['renviado_agrupado'] = False
                 # await msg.reply("🛑 **Otros modos desactivados.** (Prioridad Reenviado)") # replaced by generic msg
             
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             
             # Refresh Menu
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|renviado', 'answer': q.answer, 'internal': True})())
             return

        if data == "toggle|renviado_agrupado":
             # Exclusive Mode (Toggle)
             val, disabled = await set_exclusive_mode(cid, 'renviado_agrupado', is_toggle=True)
             
             if disabled:
                 await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
             
             conf = get_config(cid)
             if val: 
                 conf['renviado_directo'] = False
                 # await msg.reply("🛑 **Otros modos desactivados.** (Prioridad Reenviado)")
             
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             
             # Refresh Menu
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|renviado', 'answer': q.answer, 'internal': True})())
             return

        if data == "edit|parallel_thumb_seek":
             # Set State
             url_storage[cid] = url_storage.get(cid, {})
             url_storage[cid]['set_parallel_seek_mode'] = True
             
             await msg.reply("✏️ **Configurar Segundo de Miniatura**\n\nEnvía el número del segundo que quieres usar para todas las miniaturas (ej: `5`, `10`).")
             return

        if data == "toggle|parallel_thumb":
             # Exclusive Mode (Toggle)
             val, disabled = await set_exclusive_mode(cid, 'parallel_thumb_mode', is_toggle=True)
             
             if disabled:
                 await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
             
             # Refresh Submenu
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|parallel_thumb_init', 'answer': q.answer, 'internal': True})())
             return

        if data == "toggle|fusion":
             # Exclusive Mode (Toggle)
             val, disabled = await set_exclusive_mode(cid, 'fusion_mode', is_toggle=True)
             
             if disabled:
                 await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
             
             conf = get_config(cid) # Refresh config after set_exclusive_mode
             
             # Update Button
             is_on = conf.get('fusion_mode', False)
             status_icon = "🟢" if is_on else "🔴"
             
             is_auto_on = conf.get('fusion_auto_mode', False)
             auto_icon = "🟢" if is_auto_on else "🔴"
             
             kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Modo: {status_icon}", callback_data="toggle|fusion")],
                [InlineKeyboardButton(f"🤖 Modo Automático {auto_icon}", callback_data="fus_auto|menu")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
             ])
             
             try: await msg.edit_reply_markup(reply_markup=kb)
             except: pass
             return


        # --- AI DOWNLOAD CALLBACK ---
        if data.startswith("ai_dl|"):
            link_id = data.split("|")[1]
            # Recuperar info del link_id
            found_key = None
            found_url = None
            
            # Buscar en url_storage alguna key que termine en this link_id (o sea exactamente ese ID)
            # Pero url_storage keys son "chatid_linkid" o just "chatid" sometimes.
            # Nuestro link_id generado abajo es único.
            # Vamos a buscar en todas las llaves del chat
            
            # OPTIMIZACION: Construimos key esperada
            key_attempt = f"{cid}_{link_id}"
            if key_attempt in url_storage:
                found_key = key_attempt
                found_url = url_storage[key_attempt].get('url')
            
            if not found_url:
                 await q.answer("❌ El enlace ha expirado.", show_alert=True)
                 return

            await q.answer("⬇️ Iniciando análisis...")
            
            # SIMULAR MENSAJE PARA REUTILIZAR 'analyze'
            # Creamos un objeto dummy que tenga .text, .chat.id, .from_user ...
            # O mejor, llamamos analyze con el mensaje original SI lo editamos, pero analyze usa m.text.
            # Vamos a modificar el m.text del mensaje actual a la URL para que analyze lo tome.
            
            # Hack: Modificar el mensaje objeto en memoria (no en Telegram) y pasarlo.
            msg.text = found_url
            
            # Llamamos analyze. 
            # Analyze hace: matches regex, checks can_download...
            # OJO: analyze usa `m.reply(...)`. Si pasamos `msg` (que es el mensaje del bot con el botón), 
            # `m.reply` responderá a ese mensaje del bot. Correcto.
            
            await analyze(c, msg)
            return



        # --- AI SAUCENAO CALLBACK ---
        if data.startswith("ai_sauce|"):
            sauce_key = data.split("|")[1]
            stored_path = url_storage.get(sauce_key)
            if not stored_path or not os.path.exists(stored_path):
                await q.answer("❌ La imagen ya expiró o no existe.", show_alert=True)
                return
            
            await q.answer("🔍 Buscando en SauceNAO...", show_alert=False)
            
            # Ejecutar lógica SauceNAO existente
            await run_saucenao_logic(c, cid, stored_path, msg_to_edit=msg)
            return

        # --- AI EXTEND CALLBACK ---
        if data.startswith("ai_extend|"):
            ext_id = data.split("|")[1]
            data_stored = url_storage.get(ext_id)
            
            if not data_stored or 'full_text' not in data_stored:
                await q.answer("❌ El mensaje ha expirado.", show_alert=True)
                return
            
            full_txt = data_stored['full_text']
            sauce_id_stored = data_stored.get('sauce_id')
            
            # Restore ONLY SauceNAO button as requested
            btns = []
            if sauce_id_stored:
                 btns.append([InlineKeyboardButton("🔍 Buscar con SauceNAO", callback_data=f"ai_sauce|{sauce_id_stored}")])
            
            # We remove "Extender" and "Listo". Just the search button remains.
            kb = InlineKeyboardMarkup(btns) if btns else None
            
            await msg.edit_text(full_txt, reply_markup=kb)
            await q.answer("📜 Mensaje extendido.")
            return

        # --- SUBMENÚ HERRAMIENTAS ---
        if data == "menu|tools":
            # Configuración visual basada en el mockup del usuario
            s_auto_p = "🟢" if conf.get('auto_party', False) else "🔴"
            s_zip_p = "🟢" if conf.get('party_zip', False) else "🔴"
            
            s_auto_j = "🟢" if conf.get('auto_join_party', False) else "🔴"
            s_zip_j = "🟢" if conf.get('join_party_zip', False) else "🔴"
            s_auto_e = "🟢" if conf.get('auto_extract', False) else "🔴"
            s_zip_e = "🟢" if conf.get('extract_party_zip', True) else "🔴"
            
            # Renviado Status
            s_ren = "🔴"
            if conf.get('renviado_directo'): s_ren = "🟢 (Dir)"
            elif conf.get('renviado_agrupado'): s_ren = "🟢 (Agr)"
            s_tagger = "🟢" if conf.get('tagger_mode', False) else "🔴"
            
            kb_tools = [
                [
                    InlineKeyboardButton("🖼 Extractor", callback_data="menu|extract_init"),
                    InlineKeyboardButton(f"🔁 Auto: {s_auto_e}", callback_data="menu|auto_e_set"),
                    InlineKeyboardButton(f"📦 ZIP: {s_zip_e}", callback_data="toggle|extract_party_zip")
                ],
                [
                    InlineKeyboardButton("🎬 GIF", callback_data="menu|gif_init"),
                    InlineKeyboardButton("🎭 Sticker", callback_data="menu|sticker_init")
                ],
                [
                    InlineKeyboardButton("🔍 SauceNAO", callback_data="menu|saucenao_init")
                ],
                [
                    InlineKeyboardButton(f"🏷️ Smart Tagger: {s_tagger}", callback_data="toggle|tagger"),
                    InlineKeyboardButton(f"🕵️‍♀️ Inv. Profunda: {'🟢' if conf.get('research_mode') else '🔴'}", callback_data="toggle|research")
                ],
                [
                    InlineKeyboardButton("✂️ Corte Inicial", callback_data="menu|cut_init_menu"),
                    InlineKeyboardButton(f"⚙️ Auto Corte: {'🟢' if conf.get('cut_auto_mode') else '🔴'}", callback_data="menu|cut_auto_menu")
                ],
                [
                    InlineKeyboardButton(f"📥 Convertidor QH: {'🟢' if conf.get('convert_qh_mode') else '🔴'}", callback_data="toggle|convert_qh")
                ],
                [
                    InlineKeyboardButton(f"🎞 Convertidor H.264: {'🟢' if conf.get('convert_h264_mode') else '🔴'}", callback_data="toggle|convert_h264")
                ],

            ]
             
            # --- Dimensionador (Bottom) ---
            # --- Dimensionador (Bottom) ---
            kb_tools.append([
                InlineKeyboardButton("📐 Dimensionador", callback_data="resize_init"),
                InlineKeyboardButton(f"⚙️ Auto: {'🟢' if conf.get('resize_auto_mode') else '🔴'}", callback_data="menu|resize_auto_menu")
            ])
            kb_tools.append([
                InlineKeyboardButton("🧩 Menú Collage", callback_data="menu|collage_menu")
            ])
            # Smart Cut Row with Auto Toggle
            s_smart = "🟢" if conf.get('smart_cut_auto_mode', False) else "🔴"
            toggle_cb = "toggle_smart_cut_auto|off|tools" if conf.get('smart_cut_auto_mode', False) else "toggle_smart_cut_auto|on|tools"
            
            kb_tools.append([
                InlineKeyboardButton("✂️ Smart Cut (Beta)", callback_data="menu|smart_cut_init"),
                InlineKeyboardButton(f"🔁 Auto: {s_smart}", callback_data=toggle_cb)
            ])
            kb_tools.append([
                InlineKeyboardButton(f"📝 Subtitulado {'(⏳)' if conf.get('sub_mode') and not conf.get('sub_auto_mode') else ''}", callback_data="menu|sub_init"),
                InlineKeyboardButton(f"⚙️ Auto: {'🟢' if conf.get('sub_auto_mode') else '🔴'}", callback_data="toggle|sub_auto")
            ])
            # VIDEO MIXER BUTTON
            mixer_on = "🟢" if conf.get('video_mixer_mode') else "🔴"
            kb_tools.append([
                InlineKeyboardButton(f"🎞 Collage Creator: {mixer_on}", callback_data="menu|video_mixer_menu")
            ])
            kb_tools.append([
                InlineKeyboardButton("🎵 Short Virales Music", callback_data="menu|viral_init")
            ])
            kb_tools.append([
                InlineKeyboardButton(f"🈚 Traductor Manga: {'🟢' if conf.get('translate_manga_mode') else '🔴'}", callback_data="toggle|translate_manga")
            ])


            kb_tools.append([
                InlineKeyboardButton(f"✨ Waifu2x: {'🟢' if conf.get('waifux2_mode') else '🔴'}", callback_data="toggle|waifux2")
            ])

            kb_tools.append([
                InlineKeyboardButton(f"🎵 Tiktok Fast: {'🟢' if conf.get('tiktok_fast_mode') else '🔴'}", callback_data="menu|tiktok_fast_init")
            ])
            
            # --- FUSION BUTTON ---
            f_active = conf.get('fusion_mode') or conf.get('fusion_auto_mode')
            kb_tools.append([
                InlineKeyboardButton(f"🎵 Fusión: {'🟢' if f_active else '🔴'}", callback_data="menu|fusion_init")
            ])

            # --- ENLACE DIRECTO BUTTON ---
            kb_tools.append([
                InlineKeyboardButton(f"🌐 Enlace Bot: {'🟢' if conf.get('bot_link_mode') else '🔴'}", callback_data="toggle|bot_link_mode")
            ])

            # --- DOC / AGRUP (TOOLS MODE SPECIFIC) ---
            s_doc_t = "🟢" if conf.get('doc_mode_tools') else "🔴"
            s_grp_t = "🟢" if conf.get('group_mode_tools') else "🔴"
            
            kb_tools.append([
                InlineKeyboardButton(f"📄 Doc: {s_doc_t}", callback_data="toggle|doc_tools"),
                InlineKeyboardButton(f"📚 Agrup: {s_grp_t}", callback_data="toggle|group_tools")
            ])
            
            kb_tools.append([InlineKeyboardButton("🔙 Volver", callback_data="menu|main")])

            try:
                await msg.edit_text(
                    "🛠 **Herramientas Avanzadas**\n\n"
                    "Selecciona una herramienta para configurar (o activa los modos globales):",
                    reply_markup=InlineKeyboardMarkup(kb_tools)
                )
            except Exception as e:
                # Ignore "Message Not Modified" errors during menu refresh
                if "MESSAGE_NOT_MODIFIED" in str(e):
                    pass 
                else:
                    print(f"⚠️ Error Menu Tools: {e}")
            return

        # --- GLOBAL MODES HANDLERS ---
        if data == "toggle|bot_link_mode":
            val, disabled = await set_exclusive_mode(cid, 'bot_link_mode', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return

        if data == "toggle|doc_mode":
            conf['doc_mode'] = not conf.get('doc_mode', False)
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return

        if data == "menu|parallel_thumb_init":
            s_par = "🟢" if conf.get('parallel_thumb_mode') else "🔴"
            s_seek = conf.get('parallel_thumb_seek', 2)
            
            txt = (
                "📸 **Miniatura Personalizada**\n\n"
                "Activa este modo para forzar que la miniatura de tus descargas sea siempre un segundo específico.\n\n"
                f"⏱ **Segundo Configurado:** `{s_seek}s`\n"
                "1. Configura el segundo deseado.\n"
                "2. Activa el modo.\n"
                "3. Descarga tus videos."
            )
            
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Modo: {s_par}", callback_data="toggle|parallel_thumb")],
                [InlineKeyboardButton(f"✏️ Configurar Segundo ({s_seek}s)", callback_data="edit|parallel_thumb_seek")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            
            try:
                await msg.edit_text(txt, reply_markup=kb)
            except Exception as e:
                if "MESSAGE_NOT_MODIFIED" not in str(e):
                    print(f"Error Thumb Menu: {e}")
            return

        if data == "menu|video_mixer_menu":
            is_on = conf.get('video_mixer_mode', False)
            audio_mode = conf.get('vm_audio_mode', 'mix')
            is_persist = conf.get('vm_persist', False)
            
            # Decouple state
            v1_on = audio_mode in ['mix', 'v1']
            v2_on = audio_mode in ['mix', 'v2']
            
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Estado: {'🟢 ENCENDIDO' if is_on else '🔴 APAGADO'}", callback_data="toggle|video_mixer_mode")],
                [
                    InlineKeyboardButton(f"1️⃣ Video 1: {'🔊' if v1_on else '🔇'}", callback_data="toggle|vm_v1"),
                    InlineKeyboardButton(f"2️⃣ Video 2: {'🔊' if v2_on else '🔇'}", callback_data="toggle|vm_v2")
                ],
                [InlineKeyboardButton(f"📄 Modo Papel: {'🟢 ON' if conf.get('vm_paper_mode') else '🔴 OFF'}", callback_data="toggle|vm_paper")],
                [InlineKeyboardButton(f"🔁 Persistente: {'🟢 SI' if is_persist else '🔴 NO'}", callback_data="toggle|vm_persist")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            await msg.edit_text(
                "🎞 **Collage Video Creator**\n\n"
                "Une dos videos lado a lado.\n"
                " **Modo Papel**: Añade borde blanco y texto estilo meme arriba.",
                reply_markup=kb
            )
            return

        if data == "toggle|video_mixer_mode":
            val, disabled = await set_exclusive_mode(cid, 'video_mixer_mode', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            # Clear Buffer on toggle
            VIDEO_MIXER_BUFFERS.pop(cid, None)
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|video_mixer_menu', 'answer': q.answer, 'internal': True})())
            return

        if data == "toggle|vm_v1":
            curr = conf.get('vm_audio_mode', 'mix')
            is_v1 = curr in ['mix', 'v1']
            is_v2 = curr in ['mix', 'v2']
            
            # Toggle V1
            is_v1 = not is_v1
            
            # Calculate new mode
            if is_v1 and is_v2: new_mode = 'mix'
            elif is_v1 and not is_v2: new_mode = 'v1'
            elif not is_v1 and is_v2: new_mode = 'v2'
            else: new_mode = 'none'
            
            conf['vm_audio_mode'] = new_mode
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|video_mixer_menu', 'answer': q.answer, 'internal': True})())
            return

        if data == "toggle|vm_v2":
            curr = conf.get('vm_audio_mode', 'mix')
            is_v1 = curr in ['mix', 'v1']
            is_v2 = curr in ['mix', 'v2']
            
            # Toggle V2
            is_v2 = not is_v2
            
            # Calculate new mode
            if is_v1 and is_v2: new_mode = 'mix'
            elif is_v1 and not is_v2: new_mode = 'v1'
            elif not is_v1 and is_v2: new_mode = 'v2'
            else: new_mode = 'none'
            
            conf['vm_audio_mode'] = new_mode
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|video_mixer_menu', 'answer': q.answer, 'internal': True})())
            return
            
        if data == "toggle|vm_persist":
            conf['vm_persist'] = not conf.get('vm_persist', False)
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|video_mixer_menu', 'answer': q.answer, 'internal': True})())
            return

        if data == "toggle|vm_paper":
            conf['vm_paper_mode'] = not conf.get('vm_paper_mode', False)
            # If Paper Mode ON, we might want to disable Persist or specific things? Not necessarily.
            # But we might want to warn about "Text Input" requirement.
            
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|video_mixer_menu', 'answer': q.answer, 'internal': True})())
            return

        # --- MISSING TOGGLE FIXES ---
        if data == "toggle|convert_h264":
            val, disabled = await set_exclusive_mode(cid, 'convert_h264_mode', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            # Refresh
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return

        if data == "toggle|convert_qh":
            val, disabled = await set_exclusive_mode(cid, 'convert_qh_mode', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            # Refresh
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return


        if data == "toggle|group_mode":
            conf['group_mode'] = not conf.get('group_mode', False)
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return

        # --- AUTO JOIN SET HANDLER (FIX) ---
        if data == "menu|auto_j_set":
            val, disabled = await set_exclusive_mode(cid, 'auto_join_party', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            # Refresh Tools Menu
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return
            
        # --- AUTO EXTRACT SET HANDLER (FIX) ---
        if data == "menu|auto_e_set":
             val, disabled = await set_exclusive_mode(cid, 'auto_extract', is_toggle=True)
             if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
             # Refresh Tools Menu
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
             return

        # --- DIMENSIONADOR LOGIC ---
        if data == "resize_init":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Verticales (9:16)", callback_data="resize_cat|vert")],
                [InlineKeyboardButton("🟦 Cuadrados (1:1)", callback_data="resize_cat|sq")],
                [InlineKeyboardButton("🎬 Horizontales (16:9)", callback_data="resize_cat|hor")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            await msg.edit_text("📐 **Dimensionador de Video**\n\nElige el tipo de formato que buscas:", reply_markup=kb)
            return

        if data.startswith("resize_cat|"):
            cat = data.split("|")[1]
            rows = []
            if cat == "vert":
                rows = [
                    [InlineKeyboardButton("📱 9:16 (TikTok/Reels)", callback_data="resize_set|9:16")],
                    [InlineKeyboardButton("📸 3:4 (Insta Feed)", callback_data="resize_set|3:4")],
                    [InlineKeyboardButton("📱 9:19.5 (Full Mobile)", callback_data="resize_set|9:19.5")]
                ]
            elif cat == "sq":
                rows = [
                    [InlineKeyboardButton("🟦 1:1 (Cuadrado)", callback_data="resize_set|1:1")],
                    [InlineKeyboardButton("📺 4:3 (iPad/Retro)", callback_data="resize_set|4:3")]
                ]
            elif cat == "hor":
                rows = [
                    [InlineKeyboardButton("💻 16:9 (YouTube)", callback_data="resize_set|16:9")],
                    [InlineKeyboardButton("🎬 2.35:1 (Cinema)", callback_data="resize_set|2.35:1")],
                    [InlineKeyboardButton("🎞 1.85:1 (Wide)", callback_data="resize_set|1.85:1")]
                ]
            rows.append([InlineKeyboardButton("🔙 Volver", callback_data="resize_init")])
            
            await msg.edit_text(f"📐 **Selecciona el Ratio ({cat.upper()})**:", reply_markup=InlineKeyboardMarkup(rows))
            return

        # --- WAIFUX2 TOGGLE HANDLER ---
        if data == "toggle|waifux2":
            val, disabled = await set_exclusive_mode(cid, 'waifux2_mode', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            
            # Refresh Menu
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return

        if data.startswith("resize_set|"):
            ratio = data.split("|")[1]
            
            val, disabled = await set_exclusive_mode(cid, 'resize_mode')
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            
            conf = get_config(cid) # Refresh
            conf['resize_target'] = ratio
            
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await msg.edit_text(f"📐 **Modo Dimensionador Activo**\n\nTarget: `{ratio}`\n\n🎬 **Envíame el video ahora** y lo adaptaré a ese formato (Zoom + Crop).")
            return

        if data == "menu|fusion_init":
            from tools_fusion import init_fusion_menu
            await init_fusion_menu(c, cid, conf, edit_msg=q.message)
            await q.answer()
            return


        if data == "toggle|fusion":
            val, disabled = await set_exclusive_mode(cid, 'fusion_mode', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            
            # Refresh Config & UI (Manual Edit to keep it smooth)
            conf = get_config(cid)
            is_on = conf.get('fusion_mode', False)
            status_icon = "🟢" if is_on else "🔴"
            
            is_auto_on = conf.get('fusion_auto_mode', False)
            auto_icon = "🟢" if is_auto_on else "🔴"
            
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Modo: {status_icon}", callback_data="toggle|fusion")],
                [InlineKeyboardButton(f"🤖 Modo Automático {auto_icon}", callback_data="fus_auto|menu")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            
            text = (
                "🎵 **Herramienta de Fusión**\n\n"
                "Mezcla audio y video fácilmente.\n"
                "1. Activa el modo.\n"
                "2. Envía un **Video Base**.\n"
                "3. Envía un **Audio** (o video para extraer audio).\n"
                "4. Configura la mezcla final."
            )
            
            try: await msg.edit_text(text, reply_markup=kb)
            except: pass
            return

        if data.startswith("fus|") or data.startswith("fus_auto|"):
            from tools_fusion import fusion_callback
            await fusion_callback(c, q)
            return

        # --- TIKTOK FAST CALLBACK ---
        if data.startswith("menu|tiktok") or data.startswith("toggle|tiktok") or data.startswith("tiktok|"):
            from tiktok_tool import tiktok_callback
            await tiktok_callback(c, q, conf)
            return

        # --- COLLAGE SUBMENU ---
        if data == "menu|collage_menu":
            # Grid Toggles
            c_3x3 = conf.get('collage_auto_3x3', False)
            c_2x2 = conf.get('collage_auto_2x2', False)
            c_2x1 = conf.get('collage_auto_2x1', False)
            
            # Type Status
            c_type = conf.get('collage_type', 'png')
            s_png = "🟢" if c_type == 'png' else "⚪"
            s_thumb = "🟢" if c_type == 'thumb' else "⚪"
            
            kb = InlineKeyboardMarkup([
                # Row 3x3
                [
                    InlineKeyboardButton("🧩 Collage 3x3", callback_data="pre_collage_select|3x3"),
                    InlineKeyboardButton(f"Auto: {'🟢' if c_3x3 else '🔴'}", callback_data="toggle|collage_auto_3x3")
                ],
                # Row 2x2
                [
                    InlineKeyboardButton("🧩 Collage 2x2", callback_data="pre_collage_select|2x2"),
                    InlineKeyboardButton(f"Auto: {'🟢' if c_2x2 else '🔴'}", callback_data="toggle|collage_auto_2x2")
                ],
                # Row 2x1
                [
                    InlineKeyboardButton("🧩 Collage 2x1 (2 Fotos)", callback_data="pre_collage_select|2x1"),
                    InlineKeyboardButton(f"Auto: {'🟢' if c_2x1 else '🔴'}", callback_data="toggle|collage_auto_2x1")
                ],
                # Type Selector
                [
                    InlineKeyboardButton(f"🖼 PNG {s_png}", callback_data="set_collage_type_menu|png"),
                    InlineKeyboardButton(f"🎞 Miniatura {s_thumb}", callback_data="set_collage_type_menu|thumb")
                ],
                # Personalizado Row
                [
                    InlineKeyboardButton("✏️ Personalizado", callback_data="toggle|custom_thumb_mode"),
                    InlineKeyboardButton(f"Auto: {'🟢' if conf.get('custom_thumb_auto') else '🔴'}", callback_data="toggle|custom_thumb_auto")
                ],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            await msg.edit_text("🧩 **Menú Collage**\n\n1. Elige una distribución (3x3, 2x2...).\n2. Configura los botones de abajo para decirle al **Auto** qué formato enviar.", reply_markup=kb)
            return
            
        # --- TYPE SETTER (Main Menu) ---
        if data.startswith("set_collage_type_menu|"):
            new_type = data.split("|")[1]
            conf['collage_type'] = new_type
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            # Refresh
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|collage_menu', 'answer': q.answer, 'internal': True})())
            return

        # --- PRE COLLAGE SELECTION (Grid -> Type) ---
        if data.startswith("pre_collage_select|"):
            grid = data.split("|")[1]
            
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🖼 Imagen (PNG)", callback_data=f"set_collage_final|{grid}|png"),
                    InlineKeyboardButton("🎞 Video (Miniatura)", callback_data=f"set_collage_final|{grid}|thumb")
                ],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|collage_menu")]
            ])
            await msg.edit_text(f"🧩 **Collage {grid}**\n\n¿Cómo quieres el resultado?", reply_markup=kb)
            return

        # --- COLLAGE FINAL SET ---
        if data.startswith("set_collage_final|"):
            parts = data.split("|")
            grid = parts[1]
            ctype = parts[2]
            
            val, disabled = await set_exclusive_mode(cid, 'collage_mode')
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            
            conf = get_config(cid)
            conf['collage_grid'] = grid
            conf['collage_type'] = ctype
            
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            
            # Check if Auto is ON for this grid
            is_auto = conf.get(f'collage_auto_{grid}', False)
            auto_txt = " (AUTO ON)" if is_auto else " (1 Uso)"
            type_txt = "PNG" if ctype == 'png' else "Miniatura"
            
            await msg.edit_text(f"🧩 **Modo Collage Activo**\nGrid: `{grid}` | Tipo: `{type_txt}`{auto_txt}\n\n🎬 **Envíame un video** ahora.")
            return

        if data.startswith("toggle_smart_cut_auto|"):
            # Format: toggle_smart_cut_auto|{state}|{source}
            parts = data.split("|")
            # We ignore state hardcoding, we just toggle safely using exclusive logic
            
            val, disabled = await set_exclusive_mode(cid, 'smart_cut_auto_mode', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            
            # Refresh Tools
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return

        if data == "toggle|custom_thumb_mode":
            # is_toggle=True logic in set_exclusive_mode handles toggle
            new_val, disabled = await set_exclusive_mode(cid, 'custom_thumb_mode', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            
            conf = get_config(cid)
            if new_val:
                url_storage[cid] = {'custom_thumb_step': 'wait_video'}
                await msg.edit_text("✏️ **Modo Personalizado Activo**\n\n1️⃣ Envíame el **VIDEO** primero.\n2️⃣ Luego te pediré la miniatura.")
            else:
                url_storage.pop(cid, None)
                await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|collage_menu', 'answer': q.answer, 'internal': True})())
            return

        if data == "toggle|custom_thumb_auto":
            conf['custom_thumb_auto'] = not conf.get('custom_thumb_auto', False)
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|collage_menu', 'answer': q.answer, 'internal': True})())
            return

        # --- CUSTOM THUMB CATALOG NAVIGATION ---
        if data == "custom|show_catalog":
             st = url_storage.get(cid, {})
             thumbs = st.get('custom_thumbs_list', [])
             
             if not thumbs:
                 await q.answer("⚠️ Catálogo vacío o expirado.", show_alert=True)
                 return
             
             # Show first thumb
             initial_thumb = thumbs[0]
             kb = InlineKeyboardMarkup([
                 [
                     InlineKeyboardButton("⬅️", callback_data="custom|cat|nav|0"),
                     InlineKeyboardButton("✅ Usar (0s)", callback_data="custom|cat|sel|0"),
                     InlineKeyboardButton("➡️", callback_data="custom|cat|nav|1")
                 ],
                 [InlineKeyboardButton(f"📄 1 / {len(thumbs)}", callback_data="ignore")],
                 [InlineKeyboardButton("🔙 Volver a Subir", callback_data="custom|back_upload")]
             ])
             # Edit to Media - NO, Delete and Send New for reliability (Text -> Photo)
             await msg.delete()
             caption = f"🎞 **Catálogo: 0s**\nFrame 1 de {len(thumbs)}"
             await c.send_photo(cid, initial_thumb, caption=caption, reply_markup=kb)
             return

        if data == "custom|back_upload":
             # Return to "Send Image" prompt
             kb = InlineKeyboardMarkup([
                 [InlineKeyboardButton("🎞 Ver Catálogo Generado", callback_data="custom|show_catalog")],
                 [InlineKeyboardButton("❌ Cancelar", callback_data="menu|tools")]
             ])
             # We cannot "edit_media" back to text easily if it was a photo.
             # Easier to delete and send new text, or edit text if it was text (it wasn't).
             # It was a media message.
             # We will try to edit caption if it's media, or just send new message.
             await msg.delete()
             await c.send_message(cid, "🖼 **Muy bien.**\nEnvíame una **Imagen** de tu galería para usarla como portada.", reply_markup=kb)
             return

        if data.startswith("custom|cat|"):
             action = data.split("|")[2]
             
             st = url_storage.get(cid, {})
             thumbs = st.get('custom_thumbs_list', [])
             v_path = st.get('video_path')
             
             if not thumbs or not v_path:
                 await q.answer("❌ Sesión expirada.", show_alert=True)
                 return
                 
             if action == "nav":
                 idx = int(data.split("|")[3])
                 if idx < 0: idx = len(thumbs) - 1
                 if idx >= len(thumbs): idx = 0
                 
                 curr_thumb = thumbs[idx]
                 ts_label = f"{idx * 10}s" # Aprox label
                 
                 kb = InlineKeyboardMarkup([
                     [
                         InlineKeyboardButton("⬅️", callback_data=f"custom|cat|nav|{idx-1}"),
                         InlineKeyboardButton(f"✅ Usar ({ts_label})", callback_data=f"custom|cat|sel|{idx}"),
                         InlineKeyboardButton("➡️", callback_data=f"custom|cat|nav|{idx+1}")
                     ],
                     [InlineKeyboardButton(f"📄 {idx+1} / {len(thumbs)}", callback_data="ignore")],
                     [InlineKeyboardButton("❌ Cancelar", callback_data="menu|tools")]
                 ])
                 
                 try:
                     # Force caption update to ensure UI refresh visibility
                     caption = f"🎞 **Catálogo: {ts_label}**\nFrame {idx+1} de {len(thumbs)}"
                     await msg.edit_media(InputMediaPhoto(curr_thumb, caption=caption), reply_markup=kb)
                 except Exception as e:
                     print(f"Nav Error: {e}") 
                 return
                 
             elif action == "sel":
                 idx = int(data.split("|")[3])
                 t_path = thumbs[idx]
                 
                 await msg.delete()
                 wait = await c.send_message(cid, "⚙️ **Aplicando Miniatura...**")
                 
                 # Logic Duplicate from image_handler but clean
                 from tools_media import embed_thumbnail, get_meta
                 
                 out_path = await embed_thumbnail(v_path, t_path)
                 if out_path:
                     await wait.edit("📤 **Enviando Resultado...**")
                     w, h, dur = await get_meta(out_path)
                     
                     try:
                         await c.send_video(cid, out_path, thumb=t_path, width=w, height=h, duration=dur, caption="✏️ **Video Personalizado**")
                     except:
                         await c.send_document(cid, out_path, thumb=t_path, caption="✏️ **Video Personalizado**")
                     
                     # Cleanup Job Dir
                     import shutil
                     job_dir = os.path.dirname(v_path) # Assuming v_path is in a job dir
                     if 'job_' in os.path.basename(job_dir) and os.path.exists(job_dir):
                         shutil.rmtree(job_dir, ignore_errors=True)
                     else:
                         if os.path.exists(out_path): os.remove(out_path)
                         if os.path.exists(v_path): os.remove(v_path)
                         # Clean all thumbs
                         for t in thumbs:
                             if os.path.exists(t): os.remove(t)
                     await wait.delete()
                     
                     # Auto Check
                     if conf.get('custom_thumb_auto', False):
                         url_storage[cid] = {'custom_thumb_step': 'wait_video'}
                         # Mini reminder
                         kb_auto = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Detener Auto", callback_data="toggle|custom_thumb_mode")]])
                         await c.send_message(cid, "✅ **Listo.**\nEnvíame el siguiente **VIDEO**.", reply_markup=kb_auto)
                     else:
                         conf['custom_thumb_mode'] = False
                         from firebase_service import save_user_config_fb
                         asyncio.create_task(save_user_config_fb(cid, conf))
                         url_storage.pop(cid, None)
                         await c.send_message(cid, "✅ **Proceso Finalizado.**")
                 else:
                     await wait.edit("❌ Error Embed.")
                 return

        # --- AUTO RESIZE MENU ---
        if data == "menu|resize_auto_menu":
            is_on = conf.get('resize_auto_mode', False)
            curr_val = conf.get('resize_auto_val', '9:16') # Default
            
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Estado: {'🟢 ACTIVO' if is_on else '🔴 APAGADO'}", callback_data="toggle|resize_auto")],
                [InlineKeyboardButton(f"📐 Valor: {curr_val}", callback_data="ignore")],
                [
                    InlineKeyboardButton("9:16 (Tik)", callback_data="resize_auto_set|9:16"),
                    InlineKeyboardButton("3:4 (Insta)", callback_data="resize_auto_set|3:4"),
                    InlineKeyboardButton("1:1 (Sq)", callback_data="resize_auto_set|1:1")
                ],
                [
                    InlineKeyboardButton("16:9 (YT)", callback_data="resize_auto_set|16:9"),
                    InlineKeyboardButton("4:3 (Retro)", callback_data="resize_auto_set|4:3"),
                    InlineKeyboardButton("2.35:1 (Cine)", callback_data="resize_auto_set|2.35:1")
                ],
                [
                    InlineKeyboardButton("9:19.5 (Full)", callback_data="resize_auto_set|9:19.5")
                ],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            await msg.edit_text("⚙️ **Configuración Auto Dimensionador**\n\nSi está ACTIVO, todos los videos se redimensionarán automáticamente a este formato (Crop/Fill).", reply_markup=kb)
            return

        # --- AUTO RESIZE ACTIONS ---
        if data == "toggle|resize_auto":
            new_state = await set_exclusive_mode(cid, 'resize_auto_mode', is_toggle=True)
            
            # Refresh
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|resize_auto_menu', 'answer': q.answer, 'internal': True})())
            return

        if data.startswith("resize_auto_set|"):
            val = data.split("|")[1]
            conf['resize_auto_val'] = val
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            asyncio.create_task(q.answer(f"✅ Valor guardado: {val}"))
            
            # Refresh
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|resize_auto_menu', 'answer': q.answer, 'internal': True})())
            return

        # --- SMART CUT INIT ---
        if data == "menu|smart_cut_init":
            val, disabled = await set_exclusive_mode(cid, 'smart_cut_mode')
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            conf = get_config(cid) # Refresh
            
            # Check Auto State
            is_auto = conf.get('smart_cut_auto_mode', False)
            auto_txt = "🟢 Auto: ON" if is_auto else "🔴 Auto: OFF"
            auto_cb = "toggle_smart_cut_auto|off" if is_auto else "toggle_smart_cut_auto|on"
            
            await msg.edit_text(
                "🧠 **Smart Cut (Detector de Intro)**\n\n"
                "🎬 **Envíame un video** y detectaré automáticamente el final de la intro (cambio de escena) para cortarla.\n"
                "⚠️ _Beta: Puede fallar si la intro no tiene cortes claros._",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
                ])
            )
            return

        if data.startswith("toggle_smart_cut_auto|"):
            parts = data.split("|")
            val = parts[1] == "on"
            
            # If enabling Auto, we might want exclusivity or not?
            # User wants "Modo Automático" to be exclusive.
            # So if ON, call exclusive mode.
            if val:
                val_x, disabled = await set_exclusive_mode(cid, 'smart_cut_mode') # Active mode is smart cut
                if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
                conf = get_config(cid)
                conf['smart_cut_auto_mode'] = True # Set auto flag
                from firebase_service import save_user_config_fb
                asyncio.create_task(save_user_config_fb(cid, conf))
            else:
                conf['smart_cut_auto_mode'] = False
                from firebase_service import save_user_config_fb
                asyncio.create_task(save_user_config_fb(cid, conf))
            
            # Refresh menu
            target_menu = "menu|smart_cut_init"
            if len(parts) > 2 and parts[2] == "tools":
                target_menu = "menu|tools"
            
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': target_menu, 'answer': q.answer, 'internal': True})())
            return

        if data == "menu|sub_init":
            val, disabled = await set_exclusive_mode(cid, 'sub_mode')
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            await msg.edit_text("📝 **Modo Subtitulado Activo (1 Uso)**\n\n🎬 **Envíame un video** y le generaré subtítulos.\n_(Si deseas que quede fijo, activa el botón 'Auto' en el menú)_")
            return
            
        if data == "toggle|sub_auto":
            new_val = not conf.get('sub_auto_mode', False)
            
            # Exclusivity: If Auto ON, active sub_mode
            if new_val:
                val, disabled = await set_exclusive_mode(cid, 'sub_mode')
                if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
                conf = get_config(cid)
                conf['sub_auto_mode'] = True
                msg_txt = "✅ **Auto Subtitulado: ENCENDIDO** (Prioridad Alta)"
            else:
                conf['sub_auto_mode'] = False
                # Optionally disable sub_mode if relying on auto
                # But manual mode might persist.
                # Just saving usage.
                msg_txt = "❌ **Auto Subtitulado: APAGADO**"
                
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            
            # Refresh Menu
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            # Notify state
            try: await c.answer_callback_query(q.id, msg_txt)
            except: pass
            return

        # --- VIRAL MUSIC TOOL ---
        if data == "menu|viral_init":
             is_on = conf.get('viral_mode', False)
             count = len(viral_music_db)
             
             kb = InlineKeyboardMarkup([
                 [InlineKeyboardButton(f"⚙️ Estado Recolección: {'🟢 ACTIVO' if is_on else '🔴 APAGADO'}", callback_data="toggle|viral_mode")],
                 [InlineKeyboardButton(f"📚 Ver Catálogo ({count})", callback_data="menu|viral_catalog")],
                 [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
             ])
             await msg.edit_text(
                 f"🎵 **Short Virales Music**\n\n"
                 f"📦 **Items en catálogo:** {count}\n\n"
                 f"Activa la **Recolección** y envíame videos/audios para guardarlos. "
                 f"Luego usa el **Catálogo** para verlos aleatoriamente.",
                 reply_markup=kb
             )
             return



        if data == "toggle|viral_mode":
             val, disabled = await set_exclusive_mode(cid, 'viral_mode', is_toggle=True)
             if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
             
             # Refresh
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|viral_init', 'answer': q.answer, 'internal': True})())
             return

        if data == "menu|viral_catalog" or data == "viral_next" or data.startswith("viral_nav|") or data.startswith("viral_sel|") or data.startswith("viral_send_all|"):
             if not viral_music_db:
                 await c.answer_callback_query(q.id, "❌ El catálogo está vacío.", show_alert=True)
                 return
                 
             # --- VIRAL CATALOG LOGIC START ---
             target_idx = -1
             send_batch = False
             
             # Intercept explicit "send batch" action
             if data.startswith("viral_send_all|"):
                 target_idx = int(data.split("|")[1])
                 send_batch = True
             
             # Case A: Random / Init
             elif data == "viral_next" or data == "menu|viral_catalog":
                 import random
                 if viral_music_db:
                     if data == "menu|viral_catalog":
                         target_idx = 0
                     else:
                         item = random.choice(viral_music_db)
                         try: target_idx = viral_music_db.index(item)
                         except: target_idx = 0
             
             # Case B: Navigation (Paging)
             elif data.startswith("viral_nav|"):
                 parts = data.split("|")
                 current_idx = int(parts[1])
                 direction = parts[2]
                 
                 if direction == 'next':
                     target_idx = min(current_idx + 10, len(viral_music_db) - 1)
                     if target_idx == current_idx: target_idx = 0
                 elif direction == 'prev':
                     target_idx = max(0, current_idx - 10)
                 else:
                     target_idx = current_idx # Fallback
             
             # Case C: Direct Selection / Jump (Calculated previously or passed)
             elif data.startswith("viral_sel|"):
                 target_idx = int(data.split("|")[1])
                 
             # --- UNIFIED DISPLAY BLOCK ---
             if target_idx != -1 and viral_music_db:
                 # Ensure bounds
                 if target_idx < 0: target_idx = len(viral_music_db) - 1
                 if target_idx >= len(viral_music_db): target_idx = 0
                 
                 item = viral_music_db[target_idx]
                 iid = item['id']
                 
                 from utils import generate_grid_keyboard
                 
                 page_size = 10
                 current_page = target_idx // page_size
                 start_idx = current_page * page_size
                 end_idx = min(start_idx + page_size, len(viral_music_db))
                 batch_count = end_idx - start_idx
                 
                 extra_rows = [
                     [
                         InlineKeyboardButton("🗑️ Eliminar", callback_data=f"viral_del|{iid}"),
                         InlineKeyboardButton("🎲 Aleatorio 10", callback_data="viral_next")
                     ],
                     [InlineKeyboardButton(f"🚀 Enviar Todo el Lote ({batch_count})", callback_data=f"viral_send_all|{target_idx}")],
                     [InlineKeyboardButton("🔙 Menú Viral", callback_data="menu|viral_init")]
                 ]
                 
                 kb = generate_grid_keyboard(
                    current_idx=target_idx,
                    total_items=len(viral_music_db),
                    prefix_sel="viral_sel|", 
                    prefix_nav="viral_nav|", 
                    prefix_jump="viral_jump",
                    extra_rows=extra_rows
                 )
                 
                 try:
                     try: await msg.delete()
                     except: pass
                     
                     if send_batch:
                         wm = await c.send_message(cid, f"⏳ **Enviando lote de {batch_count} items...**")
                         
                         for i in range(start_idx, end_idx):
                             m_item = viral_music_db[i]
                             fid = m_item['file_id']
                             itype = m_item['type']
                             cap = f"🎵 Item {i+1} | ID: `{m_item['id']}`"
                             try:
                                 if itype == 'video': await c.send_video(cid, fid, caption=cap)
                                 elif itype == 'audio': await c.send_audio(cid, fid, caption=cap)
                                 elif itype == 'voice': await c.send_voice(cid, fid, caption=cap)
                             except Exception as e:
                                 print(f"Error enviando item {i}: {e}")
                                 
                         await wm.delete()
                         
                     if not send_batch:
                         m_item = viral_music_db[target_idx]
                         fid = m_item['file_id']
                         itype = m_item['type']
                         cap = f"🎵 Seleccionado: {target_idx+1}\nID: `{m_item['id']}`"
                         try:
                             if itype == 'video': await c.send_video(cid, fid, caption=cap)
                             elif itype == 'audio': await c.send_audio(cid, fid, caption=cap)
                             elif itype == 'voice': await c.send_voice(cid, fid, caption=cap)
                         except: pass
                     
                     menu_text = f"🎵 **Catálogo Viral** [{target_idx+1}/{len(viral_music_db)}]\n🏷️ Seleccionado: **{target_idx+1}**"
                     await c.send_message(cid, menu_text, reply_markup=kb)
                     
                 except Exception as e:
                     await c.send_message(cid, f"❌ Error al mostrar catálogo: {e}")
                 return

        if data == "viral_jump":
             url_storage[cid] = {'viral_step': 'wait_jump'}
             await msg.reply("🔢 **Escribe el número** al que quieres ir (1 - " + str(len(viral_music_db)) + "):", quote=True)
             await q.answer()
             return

        if data.startswith("viral_del|"):
             iid = data.split("|")[1]
             # Find and remove
             found = False
             for i, item in enumerate(viral_music_db):
                 if item['id'] == iid:
                     viral_music_db.pop(i)
                     # save_viral() -> Firebase
                     asyncio.create_task(delete_viral_item_fb(iid))
                     found = True
                     break
             
             if found:
                 await c.answer_callback_query(q.id, "✅ Eliminado.")
                 # Trigger next
                 await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'viral_next', 'answer': q.answer, 'internal': True})())
             else:
                 await c.answer_callback_query(q.id, "⚠️ Ya no existe.", show_alert=True)
             return

        if data == "menu|cut_init_menu":
            val, disabled = await set_exclusive_mode(cid, 'cut_init_mode', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            
            txt = "✂️ **Corte Inicial Activo**\n\n🎬 **Envíame el video** que quieres recortar al inicio."
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]])
            
            if not val: # If toggled off
                await msg.edit_text("⚙️ Modo Corte Desactivado.", reply_markup=kb)
                return

            if msg.photo or msg.caption:
                await msg.delete()
                await c.send_message(cid, txt, reply_markup=kb)
            else:
                await msg.edit_text(txt, reply_markup=kb)
            return

        # --- CONVERTIDOR QH TOGGLE ---
        if data == "toggle|convert_qh":
            val, disabled = await set_exclusive_mode(cid, 'convert_qh_mode', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            
            # Refresh Menu
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return

        # --- CONVERTIDOR MP4 H264 TOGGLE ---
        if data == "toggle|convert_h264":
            val, disabled = await set_exclusive_mode(cid, 'convert_h264_mode', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            
            # Refresh Menu (Internal to bypass Anti-Spam)
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return

        # --- TRADUCTOR MANGA TOGGLE ---
        if data == "toggle|translate_manga":
            val, disabled = await set_exclusive_mode(cid, 'translate_manga_mode', is_toggle=True)
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            
            # Refresh Menu
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return



        # --- TOGGLE AUTO RANDOM ---



        # --- THUMB RANDOM FRAME ---


        if data == "menu|ai_advanced":
            # Usamos una sola variable 'ai_model_mode' para garantizar exclusividad
            # Valores: 'gemini_2' (default), 'gemini_3', 'nano_banana'
            mode = conf.get('ai_model_mode', 'gemini_2')
            
            # Estados visuales
            st_g2 = "🟢 ACTIVO" if mode == 'gemini_2' else "🔴"
            st_g3 = "🟢 ACTIVO" if mode == 'gemini_3' else "🔴"
            st_nb = "🟢 ACTIVO" if mode == 'nano_banana' else "🔴"
            
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"⚡ Gemini 2 Flash: {st_g2}", callback_data="ai_set_mode|gemini_2")],
                [
                    InlineKeyboardButton(f"💎 Gemini 3 Pro: {st_g3}", callback_data="ai_set_mode|gemini_3"),
                    InlineKeyboardButton("⚙️", callback_data="menu|ai_tools_config")
                ],
                [
                    InlineKeyboardButton(f"🍌 Nano Banana Pro: {st_nb}", callback_data="ai_set_mode|nano_banana"),
                    InlineKeyboardButton("⚙️ Config", callback_data="menu|ai_advanced_conf")
                ],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|main")]
            ])
            
            desc = "**✨ Configuración de Cerebro IA**\n\n"
            if mode == 'gemini_2':
                desc += "✅ **Modo Actual:** Gemini 2 Flash (Rápido, Gratis).\n_Comportamiento estándar._"
            elif mode == 'gemini_3':
                desc += "✅ **Modo Actual:** Gemini 3 (Premium).\n_Máxima inteligencia. Usa tus cookies._"
            elif mode == 'nano_banana':
                desc += "✅ **Modo Actual:** Nano Banana Pro (Solo Imágenes).\n_El bot solo dibujará, no chatea._"
            
            await msg.edit_text(desc, reply_markup=kb)
            return

        if data.startswith("ai_set_mode|"):
            new_mode = data.split("|")[1]
            conf['ai_model_mode'] = new_mode
            
            # Limpiar flags antiguos por si acaso
            conf['gemini_3_mode'] = (new_mode == 'gemini_3')
            conf['nano_banana_mode'] = (new_mode == 'nano_banana')
            
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            
            # Refresh
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': "menu|ai_advanced", 'answer': q.answer, 'internal': True})())
            return

        # --- AI TOOLS CONFIG (NEW MENU) ---
        if data == "menu|ai_tools_config":
             is_search = conf.get('google_search_mode', True)
             
             kb = InlineKeyboardMarkup([
                 [InlineKeyboardButton(f"🔎 Google Search: {'🟢 ON' if is_search else '🔴 OFF'}", callback_data="toggle|google_search")],
                 [InlineKeyboardButton("🔙 Volver", callback_data="menu|ai_advanced")]
             ])
             
             await msg.edit_text(
                  "⚙️ **Herramientas de IA**\n\n"
                  "Activa o desactiva herramientas específicas que usa Gemini 3 Pro.",
                  reply_markup=kb
             )
             return

        # --- CONFIGURACIÓN AVANZADA IMAGEN (NANO/GEMINI) ---
        if data == "menu|ai_advanced_conf":
             # Leer valores actuales (defaults)
             curr_ratio = conf.get('ai_img_ratio', '1:1')
             is_doc = conf.get('ai_img_as_doc', False)
             curr_temp = conf.get('ai_temp', 1.0)
             curr_batch = conf.get('ai_img_batch', 1)
             
             # Status Icons
             st_doc = "🟢 ON" if is_doc else "🔴 OFF"
             
             kb = InlineKeyboardMarkup([
                 [
                     InlineKeyboardButton(f"📐 Ratio: {curr_ratio}", callback_data="menu|ai_conf_ratio")
                 ],
                 
                 # Batch Size (Toggle)
                 [InlineKeyboardButton(f"🔢 Batch: {curr_batch}", callback_data="toggle|ai_img_batch")],

                 # Nano Banana Config (Menu)
                 [InlineKeyboardButton("🍌 Config Nano Banana", callback_data="menu|ai_nano_config")],
                 
                 [InlineKeyboardButton("🔙 Volver", callback_data="menu|ai_advanced")]
             ])
             
             await msg.edit_text(
                 "🛠️ **Configuración Avanzada de Imagen**\n\n"
                 "Ajusta los parámetros de generación para **Nano Banana** y **Gemini**.",
                 reply_markup=kb
             )
             return

        # --- SUBMENU: AI NANO BANANA CONFIG (NEW) ---
        if data == "menu|ai_nano_config":
             # Toggle Status
             s_doc = "🟢" if conf.get('ai_img_as_doc', False) else "🔴"
             s_w2x = "🟢" if conf.get('waifu2x_auto', False) else "🔴"
             curr_res = conf.get('ai_img_res', '1K')
             
             # Explanation about Doc Mode Exception
             # Logic is: If ai_img_as_doc is explicitly set (True/False), it overrides Global. 
             # Wait, the requirement says: "Nano Banana Pro must still send content as a document... if its internal mode is active."
             # So we need an explicit toggle for THIS tool.
             
             kb = InlineKeyboardMarkup([
                 [InlineKeyboardButton(f"📄 Enviar como Doc: {s_doc}", callback_data="toggle|ai_img_as_doc_nano")],
                 [InlineKeyboardButton(f"✨ Auto Waifu2x: {s_w2x}", callback_data="toggle|waifu2x_auto")],
                 [InlineKeyboardButton(f"🖥 Res: {curr_res}", callback_data="menu|ai_conf_res")],
                 [InlineKeyboardButton("🔙 Volver", callback_data="menu|ai_advanced_conf")]
             ])
             
             await msg.edit_text(
                 "🍌 **Configuración Nano Banana Pro**\n\n"
                 "🔸 **Enviar como Doc**: Si está activo, enviarimagenes generadas como archivo (Sin compresión), IGNORANDO el modo global.\n"
                 "🔸 **Auto Waifu2x**: Mejora automáticamente la resolución (Crea 2 imágenes: Original + HD) sin preguntar.\n"
                 "🔸 **Res (Waifu2x)**: Define el nivel de escalado (1K=x2, 4K=x4, 8K=x8).",
                 reply_markup=kb
             )
             return

        if data == "toggle|ai_img_as_doc_nano":
             conf['ai_img_as_doc'] = not conf.get('ai_img_as_doc', False)
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|ai_nano_config', 'answer': q.answer, 'internal': True})())
             return

        if data == "toggle|waifu2x_auto":
             conf['waifu2x_auto'] = not conf.get('waifu2x_auto', False)
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|ai_nano_config', 'answer': q.answer, 'internal': True})())
             return

        # --- SUBMENU: RATIO ---
        if data == "menu|ai_conf_ratio":
             ratios = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9"]
             curr = conf.get('ai_img_ratio', '1:1')
             
             buttons = []
             row = []
             for r in ratios:
                 lbl = f"✅ {r}" if r == curr else r
                 buttons.append(InlineKeyboardButton(lbl, callback_data=f"ai_set_val|ratio|{r}"))
                 if len(row) == 3:
                     buttons.append(row)
                     row = []
             if row: buttons.append(row)
             
             buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="menu|ai_advanced_conf")])
             
             await msg.edit_text("📐 **Selecciona Relación de Aspecto:**", reply_markup=InlineKeyboardMarkup(buttons))
             return

        # --- SUBMENU: RES ---
        if data == "menu|ai_conf_res":
             res_opts = ["1K", "2K", "4K", "8K"]
             curr = conf.get('ai_img_res', '1K')
             
             buttons = []
             for r in res_opts:
                 lbl = f"✅ {r}" if r == curr else r
                 buttons.append([InlineKeyboardButton(lbl, callback_data=f"ai_set_val|res|{r}")])
                 
             buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="menu|ai_nano_config")])
             
             await msg.edit_text("🖥 **Selecciona Resolución (Upscale):**\n_(Afecta detalles y nitidez)_", reply_markup=InlineKeyboardMarkup(buttons))
             return

        # --- SET VALUE GENERIC ---
        if data.startswith("ai_set_val|"):
             parts = data.split("|")
             setting = parts[1] # ratio, res
             val = parts[2]
             
             if setting == "ratio": conf['ai_img_ratio'] = val
             if setting == "res": conf['ai_img_res'] = val
             
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             
             # Return to Main Config
             ret_menu = "menu|ai_advanced_conf"
             if setting == "res": ret_menu = "menu|ai_nano_config"

             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': ret_menu, 'answer': q.answer, 'internal': True})())
             return

        # --- TOGGLE DOC MODE ---
        if data == "toggle|ai_img_as_doc":
             conf['ai_img_as_doc'] = not conf.get('ai_img_as_doc', False)
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|ai_advanced_conf', 'answer': q.answer, 'internal': True})())
             return

        # --- TOGGLE BATCH SIZE ---
        if data == "toggle|ai_img_batch":
             curr = conf.get('ai_img_batch', 1)
             nxt = curr + 1
             if nxt > 4: nxt = 1
             conf['ai_img_batch'] = nxt
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|ai_advanced_conf', 'answer': q.answer, 'internal': True})())
             return

        # --- TOGGLE GOOGLE SEARCH ---
        if data == "toggle|google_search":
             conf['google_search_mode'] = not conf.get('google_search_mode', True)
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|ai_tools_config', 'answer': q.answer, 'internal': True})())
             return

        # --- MISSING HANDLERS (PARTY, JOIN, EXTRACT, ETC) ---


        if data == "toggle|tagger":
             val, disabled = await set_exclusive_mode(cid, 'tagger_mode', is_toggle=True)
             if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
             # Refresh
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
             return

        if data == "toggle|research":
             val, disabled = await set_exclusive_mode(cid, 'research_mode', is_toggle=True)
             if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
             # Refresh
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
             return

        if data == "menu|cut_auto_menu":
            is_on = conf.get('cut_auto_mode', False)
            curr_val = conf.get('cut_auto_val', '15') # Default 15s
            
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Estado: {'🟢 ACTIVO' if is_on else '🔴 APAGADO'}", callback_data="toggle|cut_auto")],
                [InlineKeyboardButton(f"⏱ Valor: {curr_val}s", callback_data="ignore")],
                [InlineKeyboardButton("🚫 Intro PH (3s)", callback_data="cut_auto_set|3")],
                [
                    InlineKeyboardButton("5s", callback_data="cut_auto_set|5"),
                    InlineKeyboardButton("10s", callback_data="cut_auto_set|10"),
                    InlineKeyboardButton("15s", callback_data="cut_auto_set|15"),
                    InlineKeyboardButton("30s", callback_data="cut_auto_set|30")
                ],
                [InlineKeyboardButton("✏️ Personalizado", callback_data="cut_auto_set|custom")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            await msg.edit_text("⚙️ **Configuración Auto Corte**\n\nSi está ACTIVO, todos los videos que envíes en el modo 'Corte Inicial' se cortarán automáticamente con este valor.", reply_markup=kb)
            return

        # --- AUTO CORTE ACTIONS ---
        if data == "toggle|cut_auto":
            conf['cut_auto_mode'] = not conf.get('cut_auto_mode', False)
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            
            # REFRESH MENU IN-PLACE
            is_on = conf.get('cut_auto_mode', False)
            curr_val = conf.get('cut_auto_val', '15')
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Estado: {'🟢 ACTIVO' if is_on else '🔴 APAGADO'}", callback_data="toggle|cut_auto")],
                [InlineKeyboardButton(f"⏱ Valor: {curr_val}s", callback_data="ignore")],
                [InlineKeyboardButton("🚫 Intro PH (3s)", callback_data="cut_auto_set|3")],
                [
                    InlineKeyboardButton("5s", callback_data="cut_auto_set|5"),
                    InlineKeyboardButton("10s", callback_data="cut_auto_set|10"),
                    InlineKeyboardButton("15s", callback_data="cut_auto_set|15"),
                    InlineKeyboardButton("30s", callback_data="cut_auto_set|30")
                ],
                [InlineKeyboardButton("✏️ Personalizado", callback_data="cut_auto_set|custom")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            await msg.edit_text("⚙️ **Configuración Auto Corte**\n\nSi está ACTIVO, todos los videos que envíes en el modo 'Corte Inicial' se cortarán automáticamente con este valor.", reply_markup=kb)
            return

        if data == "cut_auto_set|custom":
            url_storage[cid] = url_storage.get(cid, {})
            url_storage[cid]['cut_auto_step'] = 'val_wait'
            await msg.edit_text("✍️ **Ingresa el valor personalizado**\n\nEjemplos: `10` (segundos), `01:05` (1 min 5 seg).", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="menu|cut_auto_menu")]]))
            return

        if data.startswith("cut_auto_set|"):
            val = data.split("|")[1]
            conf['cut_auto_val'] = val
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await q.answer(f"✅ Valor guardado: {val}s")
            
            # REFRESH MENU IN-PLACE
            is_on = conf.get('cut_auto_mode', False)
            curr_val = conf.get('cut_auto_val', '15')
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Estado: {'🟢 ACTIVO' if is_on else '🔴 APAGADO'}", callback_data="toggle|cut_auto")],
                [InlineKeyboardButton(f"⏱ Valor: {curr_val}s", callback_data="ignore")],
                [InlineKeyboardButton("🚫 Intro PH (3s)", callback_data="cut_auto_set|3")],
                [
                    InlineKeyboardButton("5s", callback_data="cut_auto_set|5"),
                    InlineKeyboardButton("10s", callback_data="cut_auto_set|10"),
                    InlineKeyboardButton("15s", callback_data="cut_auto_set|15"),
                    InlineKeyboardButton("30s", callback_data="cut_auto_set|30")
                ],
                [InlineKeyboardButton("✏️ Personalizado", callback_data="cut_auto_set|custom")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            try:
                await msg.edit_text("⚙️ **Configuración Auto Corte**\n\nSi está ACTIVO, todos los videos que envíes en el modo 'Corte Inicial' se cortarán automáticamente con este valor.", reply_markup=kb)
            except: pass # In case content is identical (Telegram error)
            return

        # --- SECCION: CONFIGURACION IA (Personalidades) ---
        if data == "menu|ai_config":
            # 1. DATA MIGRATION CHECK
            # We want 'ai_images' to be dict of personas: {'nsfw': {cat: ...}, 'custom1': {cat: ...}}
            # Old format: 'ai_images': { 'welcome': ... } (Directly categories)
            # Detect old format by checking if 'welcome'/'greeting' is a key at top level of ai_images
            if 'ai_images' not in conf: conf['ai_images'] = {}
            current_imgs = conf['ai_images']
            
            # Check if it looks like old schema (has category keys directly)
            is_legacy = any(key in current_imgs for key in ['welcome', 'greeting', 'admire'])
            if is_legacy:
                # MIGRATE
                legacy_data = current_imgs.copy()
                conf['ai_images'] = {
                    'nsfw': legacy_data
                }
                # Set default persona if not set
                if 'active_persona' not in conf: conf['active_persona'] = 'formal'
                
                # Save immediately
                from firebase_service import save_user_config_fb
                asyncio.create_task(save_user_config_fb(cid, conf))
            
            if 'active_persona' not in conf: conf['active_persona'] = 'formal'
            active_p = conf['active_persona']

            # Standard Personas
            standards = [
                ('formal', "🎩 Formal"),
                ('pasiva', "🧘‍♀️ Pasiva"),
                ('profesional', "👔 Profesional"),
                ('agresiva', "💢 Agresiva"),
                ('timida', "😳 Tímida")
            ]
            
            kb_rows = []
            
            # 1. Standards
            for pid, pname in standards:
                status = "🟢" if active_p == pid else "⚪"
                kb_rows.append([InlineKeyboardButton(f"{pname} {status}", callback_data=f"ai_set_p|{pid}")])
                
            # 2. NSFW (Special Visual)
            status_nsfw = "🟢" if active_p == 'nsfw' else "⚪"
            row_nsfw = [InlineKeyboardButton(f"🔞 Waifu NSFW {status_nsfw}", callback_data="ai_set_p|nsfw")]
            # Only show Body Config if this acts as Visual (it does)
            # But the user wants "Cuerpo" button next to it or accessible.
            # Plan: Toggle button, and IF active (or separate button), show Config.
            # User req: "todos cambiara con un botó ocion de verde y rojo... solo esas tienen decho a tener sus cuerpo"
            # Let's add a "⚙️" button next to it.
            row_nsfw.append(InlineKeyboardButton("⚙️ Config", callback_data="ai_conf|body|nsfw"))
            kb_rows.append(row_nsfw)
            
            # 3. Customs (Local + Global)
            local_customs = conf.get('custom_personas', {})
            # Merge: Global overrides local if same ID
            all_customs = {**local_customs, **global_personas}
            
            for cid_key, cdata in all_customs.items():
                cname = cdata.get('name', 'Custom')
                status_c = "🟢" if active_p == cid_key else "⚪"
                kb_rows.append([
                    InlineKeyboardButton(f"👤 {cname} {status_c}", callback_data=f"ai_set_p|{cid_key}"),

                    InlineKeyboardButton("✏️", callback_data=f"ai_conf|edit_ask|{cid_key}"),
                    InlineKeyboardButton("🗑", callback_data=f"ai_conf|del_p_ask|{cid_key}")
                ])

            # 4. Expressions & Focus Mode (REMOVED)
            # kb_rows.append([
            #     InlineKeyboardButton(f"Expresiones: {green}", callback_data="toggle|ai_green_mode"),
            #     InlineKeyboardButton(f"Boto f: {focus}", callback_data="toggle|ai_focus_mode")
            # ])

            # 5. Add & Back
            # kb_rows.append([InlineKeyboardButton("➕ Agregar Personalidad", callback_data="ai_add_persona")])
            # 5. Add Voice & Back
            v_status = "🟢" if conf.get('voice_mode') else "🔴"
            kb_rows.append([InlineKeyboardButton(f"🎙️ Voz: {v_status}", callback_data="toggle|voice_mode")])
            kb_rows.append([InlineKeyboardButton("🔙 Volver", callback_data="menu|main")])
            
            # Calculate Display Title
            current_display = active_p.title()
            # 1. Standard?
            for pid, pname in standards:
                if pid == active_p: current_display = pname
            # 2. NSFW?
            if active_p == 'nsfw': current_display = "🔞 Waifu NSFW"
            # 3. Custom?
            if active_p in all_customs:
                current_display = all_customs[active_p].get('name', active_p.title())

            kb = InlineKeyboardMarkup(kb_rows)
            txt = (f"🧠 **Personalidad Actual:** {current_display}\n\n"
                   "Selecciona el comportamiento de la IA.")
            
            # Fix persistent media
            if msg.photo or msg.video or msg.animation or msg.sticker or msg.document:
                await msg.delete()
                await c.send_message(cid, txt, reply_markup=kb)
            else:
                 await msg.edit_text(txt, reply_markup=kb)
            return

        # --- SET ACTIVE PERSONA ---
        if data.startswith("ai_set_p|"):
            new_p = data.split("|")[1]
            conf['active_persona'] = new_p
            # Clear memory to ensure fresh start with new persona
            clear_chat_memory(cid)
            
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            # Refresh Menu
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': "menu|ai_config", 'answer': q.answer, 'internal': True})())
            return

        # --- AUTO COLLAGE TOGGLE ---
        if data == "toggle|collage_auto":
            conf['collage_auto_mode'] = not conf.get('collage_auto_mode', False)
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return

        # --- VOICE MODE TOGGLE ---
        if data == "toggle|voice_mode":
            conf['voice_mode'] = not conf.get('voice_mode', False)
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            # Refresh Menu (Internal to bypass Anti-Spam)
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|ai_config', 'answer': q.answer, 'internal': True})())
            return

        # --- BODY CONFIG (HIERARCHICAL) ---
        if data.startswith("ai_conf|body"):
            parts = data.split("|")
            persona_id = parts[2] if len(parts) > 2 else 'nsfw' 
            
            p_name = "Waifu NSFW"
            is_nsfw = (persona_id == 'nsfw')
            if is_nsfw: p_name = "Waifu NSFW 🔞"
            
            # Name Lookup (Local -> Global)
            if not is_nsfw:
                if persona_id in conf.get('custom_personas', {}):
                    p_name = conf['custom_personas'][persona_id].get('name', 'Custom')
                elif persona_id in global_personas:
                    p_name = global_personas[persona_id].get('name', 'Global Custom')

            # DEFINICIÓN DE GRUPOS
            groups = [
                ('social', '📂 Emociones & Social'),
                ('romance', '📂 Romance & Cariño'),
                ('outfits', '📂 Cosplay & Outfits'),
                ('nsfw_soft', '📂 NSFW Soft & Tease'),
                ('nsfw_hard', '📂 NSFW Actos'),
                ('nsfw_climax', '📂 NSFW Clímax'),
                ('vulgar', '📂 Vulgar & Anatomía'),
                ('life', '📂 Contexto / Vida'),
                ('pack', '📂 Packs (Colección)')
            ]
            
            buttons = []
            for gid, gname in groups:
                buttons.append([InlineKeyboardButton(gname, callback_data=f"ai_conf|group|{gid}|{persona_id}")])
            
            buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="menu|ai_config")])

            kb = InlineKeyboardMarkup(buttons)
            txt = f"💃 **Cuerpo: {p_name}**\n\nSelecciona una categoría para gestionar las imágenes de reacción."
            
            if msg.photo or msg.video or msg.animation or msg.sticker or msg.document:
                await msg.delete()
                await c.send_message(cid, txt, reply_markup=kb)
            else:
                await msg.edit_text(txt, reply_markup=kb)
            return

        # --- GROUP VIEW (Folders) ---
        if data.startswith("ai_conf|group|"):
            parts = data.split("|")
            gid, pid = parts[2], parts[3]
            
            # DATA DEFINITION (Hardcoded Map)
            
            # CLEAR STATE (Safety: Going back always turns off upload)
            url_storage.pop(cid, None)
            
            AVATAR_DATA = {
                'social': ['welcome', 'greeting', 'happy', 'laugh', 'angry', 'pouting', 'sad', 'shock', 'confused', 'scared', 'disgusted', 'thinking', 'wink', 'bored', 'tired', 'drunk', 'crazy', 'pleading', 'smug', 'shy'],
                'romance': ['love', 'kiss', 'deep_kiss', 'blow_kiss', 'hug', 'holding', 'lap_pillow', 'lap_sit', 'feeding', 'headpat', 'cuddle', 'lean', 'cheek', 'forehead', 'ring', 'date', 'heart', 'stare'],
                'outfits': ['casual', 'dress', 'sundress', 'wedding', 'bikini', 'micro', 'gym', 'school', 'bloomer', 'maid', 'nurse', 'doctor', 'police', 'bunny', 'cat_girl', 'dog_girl', 'cow_girl', 'fox_girl', 'cheongsam', 'kimono', 'goth', 'ol', 'sweater', 'pajamas', 'towel', 'apron', 'teacher', 'nun', 'witch', 'vampire', 'succubus', 'elf'],
                'nsfw_soft': ['horny', 'lingerie', 'bra', 'panties', 'nude', 'nude_back', 'ass', 'boobs', 'nipples', 'feet', 'legs', 'armpits', 'sweat', 'oil', 'bondage', 'collar'],
                'nsfw_hard': ['masturb', 'toy_play', 'blowjob', 'deepthroat', 'cum_mouth', 'facesit', 'paizuri', 'handjob', 'doggy', 'mission', 'cowgirl', 'standing', 'anal', 'gangbang', 'double', 'lesbian', '69'],
                'nsfw_climax': ['cum_face', 'cum_body', 'creampie', 'anal_pie', 'bukkake', 'ahegao', 'after', 'mess'],
                'vulgar': ['pussy', 'dick', 'anus', 'spread', 'orgy', 'cuckold', 'sex', 'slut', 'milk', 'cum', 'threesome', 'rimjob', 'spit', 'choking', 'spank', 'fisting', 'squirt'],
                'life': ['sleep', 'eat', 'bath', 'toilet', 'selfie'],
                'pack': ['pack_boobs', 'pack_ass', 'pack_pussy', 'pack_nude', 'pack_feet', 'pack_dildo', 'pack_underwear', 'pack_cam']
            }
            
            # SPANISH TRANSLATIONS -> Moved to Global Scope


            cat_list = AVATAR_DATA.get(gid, [])
            
            # --- FETCH COUNTS (New) ---
            from firebase_service import get_all_avatars
            # This returns {outfit: {emotion: [file_ids]}}
            # We want total across all outfits? Or just default? 
            # Usually users just use 'default' outfit for now. 
            # Let's count TOTAL unique if possible or just use 'default' as primary.
            # Simple approach: Get 'default' outfit counts.
            av_counts = {}
            try:
                full_data = await get_all_avatars(pid) or {}
                # Merge checks: if outfit not specified, check all?
                # User flow: Uploads go to 'default'.
                # Let's verify 'default' key exists.
                def_data = full_data.get('default', {})
                for c_k, c_v in def_data.items():
                    if isinstance(c_v, list): av_counts[c_k] = len(c_v)
            except Exception as e:
                print(f"Error fetching counts: {e}")

            # Generate Buttons Matrix (2 columns)
            buttons = []
            row = []
            for cat in cat_list:
                # Icono de carpeta siempre 📂 y nombre traducido
                display_name = TRANS.get(cat, cat.replace('_', ' ').title())
                
                # Count
                c_num = av_counts.get(cat, 0)
                
                label = f"📂 {display_name} ({c_num})"
                
                row.append(InlineKeyboardButton(label, callback_data=f"ai_conf|cat|{cat}|{pid}|{gid}")) # Pass GID for back button
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row: buttons.append(row)
            
            buttons.append([InlineKeyboardButton("🔙 Volver", callback_data=f"ai_conf|body|{pid}")])
            
            kb = InlineKeyboardMarkup(buttons)
            g_name = gid.replace('_', ' ').title()
            await msg.edit_text(f"📂 **Carpeta: {g_name}**\nSelecciona una sub-carpeta para subir fotos.", reply_markup=kb)
            return

        # --- ADD CATEGORY FLOW ---
        if data.startswith("ai_conf|add_cat|"):
             parts = data.split("|")
             pid = parts[2]
             
             # Ask for name
             # State storage
             url_storage[cid] = {'action': 'ai_add_cat_wait', 'pid': pid}
             
             await msg.edit_text(f"✍️ **Nueva Característica para {pid}:**\n\nEscribe el nombre de la emoción o rasgo (ej: `Enojada`, `Sonrojada`, `Llorando`).\n\n_Esto creará un nuevo grupo de imágenes._", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data=f"ai_conf|body|{pid}")]]))
             return

        if data.startswith("ai_conf|cat|"):
            parts = data.split("|")
            cat = parts[2]
            pid = parts[3] if len(parts) > 3 else 'nsfw'
            gid = parts[4] if len(parts) > 4 else 'social' 

            # DIRECT UPLOAD FLOW
            
            # Mapas de texto
            c_name = TRANS.get(cat, cat.replace('_', ' ').title())

            # Trigger Upload Mode Directly


            # Count Logic Logic
            # Only show "Catálogo" if count > 0
            
            # Fetch local count or use what we fetched
            # av_counts was fetched in group view? No, this is cat view.
            # Rerun fetch or pass it? Usually safer to fetch again or assume 0 if not passed.
            # Let's fetch quickly.
            from firebase_service import get_persona_images
            existing_imgs = await get_persona_images(pid, 'default', cat)
            e_count = len(existing_imgs)
            
            # Retrieve current upload state
            st = url_storage.get(cid, {})
            is_upload_active = st.get('ai_config_step') == 'wait_image' and st.get('category') == cat
            
            # Message
            status_txt = "🟢 **ENCENDIDO** (Envía fotos ahora)" if is_upload_active else "🔴 **APAGADO** (Subida bloqueada)"
            
            txt = (
                f"📂 **Carpeta: {c_name}**\n"
                f"📊 **Imágenes:** {e_count}\n"
                f"📡 **Estado Subida:** {status_txt}\n\n"
                f"Controla si el bot debe recibir nuevas imágenes o no."
            )
            
            # Buttons
            rows = []
            
            # Toggle Button
            if is_upload_active:
                rows.append([InlineKeyboardButton("🛑 PAUSAR SUBIDA", callback_data=f"ai_conf|toggle_up|{cat}|off|{pid}|{gid}")])
            else:
                rows.append([InlineKeyboardButton("🟢 ACTIVAR SUBIDA", callback_data=f"ai_conf|toggle_up|{cat}|on|{pid}|{gid}")])
            
            if e_count > 0:
                 rows.append([InlineKeyboardButton(f"🖼 Ver Catálogo ({e_count})", callback_data=f"ai_conf|catnav|{cat}|0|view|{pid}|{gid}")])
            
            rows.append([InlineKeyboardButton("🔙 Volver", callback_data=f"ai_conf|group|{gid}|{pid}")])
            
            kb = InlineKeyboardMarkup(rows)
            
            # If user sent media? The handler below handles uploads. This is just Text menu.
            if msg.photo: # If reused
                await msg.delete()
                await c.send_message(cid, txt, reply_markup=kb)
            else:
                await msg.edit_text(txt, reply_markup=kb)
            return

        # --- TOGGLE UPLOAD HANDLER ---
        if data.startswith("ai_conf|toggle_up|"):
             parts = data.split("|")
             cat = parts[2]
             mode = parts[3]
             pid = parts[4]
             gid = parts[5]
             
             if mode == "on":
                 # Activate
                 url_storage[cid] = {'ai_config_step': 'wait_image', 'category': cat, 'persona_id': pid, 'count': 0, 'gid': gid}
                 await q.answer("🟢 Subida ACTIVADA. Envía fotos.", show_alert=False)
             else:
                 # Deactivate
                 url_storage.pop(cid, None)
                 await q.answer("🔴 Subida PAUSADA.", show_alert=False)
             
             # Recalculate UI State for Refresh
             is_upload_active = (mode == "on")
             
             # Fetch needed data again for display
             c_name = TRANS.get(cat, cat.replace('_', ' ').title())
             from firebase_service import get_persona_images
             existing_imgs = await get_persona_images(pid, 'default', cat)
             e_count = len(existing_imgs)
             
             status_txt = "🟢 **ENCENDIDO** (Envía fotos ahora)" if is_upload_active else "🔴 **APAGADO** (Subida bloqueada)"
             
             txt = (
                 f"📂 **Carpeta: {c_name}**\n"
                 f"📊 **Imágenes:** {e_count}\n"
                 f"📡 **Estado Subida:** {status_txt}\n\n"
                 f"Controla si el bot debe recibir nuevas imágenes o no."
             )
             
             # Buttons
             rows = []
             if is_upload_active:
                 rows.append([InlineKeyboardButton("🛑 PAUSAR SUBIDA", callback_data=f"ai_conf|toggle_up|{cat}|off|{pid}|{gid}")])
             else:
                 rows.append([InlineKeyboardButton("🟢 ACTIVAR SUBIDA", callback_data=f"ai_conf|toggle_up|{cat}|on|{pid}|{gid}")])
             
             if e_count > 0:
                  rows.append([InlineKeyboardButton(f"🖼 Ver Catálogo ({e_count})", callback_data=f"ai_conf|catnav|{cat}|0|view|{pid}|{gid}")])
             
             rows.append([InlineKeyboardButton("🔙 Volver", callback_data=f"ai_conf|group|{gid}|{pid}")])
             
             try:
                 await msg.edit_text(txt, reply_markup=InlineKeyboardMarkup(rows))
             except Exception as e:
                 print(f"Error editing text: {e}")
             return

        # --- CATALOG VIEWER ---
        if data.startswith("ai_conf|catnav|"):
             # ai_conf|catnav|{cat}|{idx}|{action}|{pid}|{gid}
             parts = data.split("|")
             cat = parts[2]
             idx = int(parts[3])
             action = parts[4]
             pid = parts[5]
             gid = parts[6]
             
             from firebase_service import get_persona_images, delete_persona_image
             imgs = await get_persona_images(pid, 'default', cat)
             
             if not imgs:
                 await q.answer("⚠️ Carpeta vacía.", show_alert=True)
                 # Go back to upload view
                 return await cb(c, type('obj', (object,), {'message': msg, 'data': f"ai_conf|cat|{cat}|{pid}|{gid}", 'answer': q.answer})())

             # Navigation Logic
             if idx < 0: idx = len(imgs) - 1
             if idx >= len(imgs): idx = 0
             
             curr = imgs[idx]
             fid = curr if isinstance(curr, str) else curr.get('id')
             ftype = 'photo' if isinstance(curr, str) else curr.get('type', 'photo')
             
             # Buttons: < > Delete Back
             row_nav = [
                 InlineKeyboardButton("⬅️", callback_data=f"ai_conf|catnav|{cat}|{idx-1}|view|{pid}|{gid}"),
                 InlineKeyboardButton(f"{idx+1}/{len(imgs)}", callback_data="ignore"),
                 InlineKeyboardButton("➡️", callback_data=f"ai_conf|catnav|{cat}|{idx+1}|view|{pid}|{gid}")
             ]
             row_act = [
                 InlineKeyboardButton("🗑 Borrar", callback_data=f"ai_conf|catdel|{cat}|{idx}|{pid}|{gid}"),
                 InlineKeyboardButton("🔙 Volver", callback_data=f"ai_conf|cat|{cat}|{pid}|{gid}")
             ]
             kb = InlineKeyboardMarkup([row_nav, row_act])
             
             # Caption
             c_name = TRANS.get(cat, cat.replace('_', ' ').title())
             txt = f"📂 **{c_name}** ({idx+1}/{len(imgs)})"
             
             media = None
             if ftype == 'photo': media = InputMediaPhoto(fid, caption=txt)
             elif ftype == 'video': media = InputMediaVideo(fid, caption=txt)
             elif ftype == 'animation': media = InputMediaAnimation(fid, caption=txt)
             elif ftype == 'document': media = InputMediaDocument(fid, caption=txt)
             elif ftype == 'sticker': media = None # Stickers cannot be InputMedia for edit
             
             # Fallback if unknown type strictly to avoid error if possible, but if it is sticker we must be careful
             if not media and ftype != 'sticker': media = InputMediaPhoto(fid, caption=txt)
             
             try:
                 if action == 'view':
                     # If we have media object AND current message is editable media (not sticker)
                     can_edit = (msg.photo or msg.video or msg.animation or msg.document) and media
                     
                     if can_edit:
                        await msg.edit_media(media, reply_markup=kb)
                     else:
                        # Must delete and resend (Sticker -> Photo, Photo -> Sticker, etc)
                        await msg.delete()
                        if ftype == 'sticker':
                            await c.send_sticker(msg.chat.id, fid, reply_markup=kb)
                        elif ftype == 'video':
                             await c.send_video(msg.chat.id, fid, caption=txt, reply_markup=kb)
                        elif ftype == 'animation':
                             await c.send_animation(msg.chat.id, fid, caption=txt, reply_markup=kb)
                        elif ftype == 'document':
                             await c.send_document(msg.chat.id, fid, caption=txt, reply_markup=kb)
                        else:
                             await c.send_photo(msg.chat.id, fid, caption=txt, reply_markup=kb)
             except Exception as e:
                 print(f"⚠️ Catalog Edit Error: {e}")
                 # If edit fails (e.g. type change), delete and send
                 try: await msg.delete()
                 except: pass
                 
                 if ftype == 'sticker': await c.send_sticker(msg.chat.id, fid, reply_markup=kb)
                 elif ftype == 'video': await c.send_video(msg.chat.id, fid, caption=txt, reply_markup=kb)
                 elif ftype == 'animation': await c.send_animation(msg.chat.id, fid, caption=txt, reply_markup=kb)
                 elif ftype == 'document': await c.send_document(msg.chat.id, fid, caption=txt, reply_markup=kb)
                 else: await c.send_photo(msg.chat.id, fid, caption=txt, reply_markup=kb)
             return

        # --- CATALOG DELETE ---
        if data.startswith("ai_conf|catdel|"):
             parts = data.split("|")
             cat = parts[2]
             idx = int(parts[3])
             pid = parts[4]
             gid = parts[5]
             
             from firebase_service import get_persona_images, delete_persona_image
             imgs = await get_persona_images(pid, 'default', cat)
             if 0 <= idx < len(imgs):
                 target = imgs[idx]
                 # Delete
                 await delete_persona_image(pid, 'default', cat, target)
                 await q.answer("🗑 Imagen borrada.")
                 
                 # Refresh at same index (or prev if last)
                 new_len = len(imgs) - 1
                 if new_len == 0:
                     # Empty -> Go back
                     return await cb(c, type('obj', (object,), {'message': msg, 'data': f"ai_conf|cat|{cat}|{pid}|{gid}", 'answer': q.answer})())
                 
                 if idx >= new_len: idx = new_len - 1
                 
                 # Redirect to view
                 return await cb(c, type('obj', (object,), {'message': msg, 'data': f"ai_conf|catnav|{cat}|{idx}|view|{pid}|{gid}", 'answer': q.answer})())
             return

        # --- DELETE CATEGORY FLOW ---
        if data.startswith("ai_conf|del_cat_ask|"):
            parts = data.split("|")
            cat, pid = parts[2], parts[3]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Sí, Borrar", callback_data=f"ai_conf|del_cat_do|{cat}|{pid}"),
                 InlineKeyboardButton("❌ Cancelar", callback_data=f"ai_conf|cat|{cat}|{pid}")]
            ])
            await msg.edit_text(f"🗑️ **¿Borrar categoría '{cat}'?**\n\nSe perderán todas las imágenes configuradas para esta reacción.", reply_markup=kb)
            return

        if data.startswith("ai_conf|del_cat_do|"):
            parts = data.split("|")
            cat, pid = parts[2], parts[3]
            
            # Global
            if pid in global_personas and 'images' in global_personas[pid] and cat in global_personas[pid]['images']:
                 del global_personas[pid]['images'][cat]
                 await save_global_persona(pid, global_personas[pid])
            
            # Local
            if pid in conf.get('ai_images', {}) and cat in conf['ai_images'][pid]:
                del conf['ai_images'][pid][cat]
            
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            
            # Back to menu
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': f"ai_conf|body|{pid}", 'answer': q.answer, 'internal': True})())
            return
        
        # --- EDIT PERSONA FLOW ---
        if data.startswith("ai_conf|edit_ask|"):
            pid = data.split("|")[2]
            # Ask what to edit
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Nombre", callback_data=f"ai_conf|edit_field|name|{pid}"),
                 InlineKeyboardButton("🧠 Prompt", callback_data=f"ai_conf|edit_field|prompt|{pid}")],
                [InlineKeyboardButton("🔙 Cancelar", callback_data="menu|ai_config")]
            ])
            await msg.edit_text(f"✏️ **Editar Personalidad:**\n¿Qué deseas cambiar?", reply_markup=kb)
            return

        if data.startswith("ai_conf|edit_field|"):
            parts = data.split("|")
            field, pid = parts[2], parts[3]
            
            url_storage[cid] = {'action': 'ai_edit_p_wait', 'pid': pid, 'field': field}
            
            f_label = "Nombre" if field == 'name' else "Prompt"
            await msg.edit_text(f"✍️ **Editando {f_label}:**\n\nEnvía ahora el nuevo valor.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data="menu|ai_config")]]))
            return

        # --- DELETE PERSONA FLOW ---
        if data.startswith("ai_conf|del_p_ask|"):
            pid = data.split("|")[2]
            cname = conf.get('custom_personas', {}).get(pid, {}).get('name', 'Custom')
            
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 SÍ, ELIMINAR", callback_data=f"ai_conf|del_p_do|{pid}")],
                [InlineKeyboardButton("🔙 Cancelar", callback_data="menu|ai_config")]
            ])
            await msg.edit_text(f"⚠️ **¿Estás seguro de eliminar a '{cname}'?**\n\nEsta acción no se puede deshacer.", reply_markup=kb)
            return

        if data.startswith("ai_conf|del_p_do|"):
            pid = data.split("|")[2]
            
            # 1. Try Delete Global
            await delete_global_persona_fb(pid)
            await asyncio.sleep(0.5) # Wait for propagation
            await refresh_globals()

            # 2. Try Delete Local (Legacy)
            if 'custom_personas' in conf and pid in conf['custom_personas']:
                del conf['custom_personas'][pid]
                
            # If was active, reset to nsfw
            if conf.get('active_persona') == pid:
                conf['active_persona'] = 'nsfw'

            # Clean images (Optional, can keep or delete)
            # For global, images are in the document, so deleting doc deletes images.
            # For local legacy images:
            if 'ai_images' in conf and pid in conf['ai_images']:
                del conf['ai_images'][pid]

            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            
            await q.answer("🗑 Personalidad eliminada.")
            
            # Go back to menu (Refresh)
            # We call the menu handler directly.
            # IMPORTANT: To ensure UI updates, we pass a dummy 'random' data or ensure menu rebuilds.
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': "menu|ai_config", 'answer': q.answer, 'internal': True})())
            return

        # --- MODE SETTER ---
        if data.startswith("ai_conf|setmode|"):
            parts = data.split("|")
            cat, new_mode = parts[2], parts[3]
            pid = parts[4] if len(parts) > 4 else 'nsfw'
            
            # Init structure
            if 'ai_images' not in conf: conf['ai_images'] = {}
            if pid not in conf['ai_images']: conf['ai_images'][pid] = {}
            if cat not in conf['ai_images'][pid]: conf['ai_images'][pid][cat] = {'images': []}
            
            img_count = len(conf['ai_images'][pid][cat].get('images', []))

            # Special Logic for Modes
            if new_mode == 'single':
                # Go to Catalog to Select
                 if img_count == 0:
                     await q.answer("⚠️ No hay imágenes. Sube alguna primero.", show_alert=True)
                     return
                 # Open Catalog in SELECT mode
                 await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': f"ai_conf|nav|{cat}|0|select|{pid}", 'answer': q.answer, 'internal': True})())
                 return

            elif new_mode == 'subset':
                # Ask for numbers
                if img_count == 0:
                     await q.answer("⚠️ No hay imágenes.", show_alert=True)
                     return
                
                # Store PID in storage for input handler
                url_storage[cid] = {'ai_config_step': 'wait_subset', 'category': cat, 'persona_id': pid}
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data=f"ai_conf|cat|{cat}|{pid}")]])
                txt = (f"🔢 **Modo Personalizado ({cat.upper()})**\n\n"
                       f"Tienes **{img_count}** imágenes.\n"
                       f"Escribe los números que quieres usar, separados por espacio.\n"
                       f"Ejemplo: `1 3 5`")
                if msg.photo or msg.video or msg.animation or msg.sticker or msg.document:
                     await msg.delete()
                     await c.send_message(cid, txt, reply_markup=kb)
                else: 
                     await msg.edit_text(txt, reply_markup=kb)
                return

            # For Random, just set and refresh
            conf['ai_images'][pid][cat]['mode'] = new_mode
            
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': f"ai_conf|cat|{cat}|{pid}", 'answer': q.answer, 'internal': True})())
            return

        if data.startswith("ai_conf|nav|"):
            parts = data.split("|")
            # format: ai_conf|nav|cat|idx|mode|pid
            cat, idx, mode = parts[2], int(parts[3]), parts[4]
            pid = parts[5] if len(parts) > 5 else 'nsfw'
            
            ai_imgs = conf.get('ai_images', {}).get(pid, {}).get(cat, {'images': []})
            imgs = ai_imgs.get('images', [])
            
            if not imgs:
                await q.answer("⚠️ No hay imágenes.", show_alert=True)
                # Go back
                await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': f"ai_conf|cat|{cat}|{pid}", 'answer': q.answer, 'internal': True})())
                return

            # Wrap index
            n = len(imgs)
            if idx < 0: idx = n - 1
            if idx >= n: idx = 0
            
            # Wrapper for legacy string items
            item = imgs[idx]
            if isinstance(item, str): item = {'id': item, 'type': 'photo'}
            
            file_id = item['id']
            ftype = item.get('type', 'photo')
            
            # Buttons
            # Row 1: Nav
            btn_prev = InlineKeyboardButton("⬅️", callback_data=f"ai_conf|nav|{cat}|{idx-1}|{mode}|{pid}")
            btn_next = InlineKeyboardButton("➡️", callback_data=f"ai_conf|nav|{cat}|{idx+1}|{mode}|{pid}")
            btn_count = InlineKeyboardButton(f"{idx+1}/{n}", callback_data="ignore")
            
            # Row 2: Action
            if mode == 'select':
                btn_action = InlineKeyboardButton("✅ Seleccionar", callback_data=f"ai_conf|act|{cat}|{idx}|select|{pid}")
            else: # view
                btn_action = InlineKeyboardButton("🗑 Borrar", callback_data=f"ai_conf|act|{cat}|{idx}|delete|{pid}")
            
            # Row 3: Back
            btn_back = InlineKeyboardButton("🔙 Volver", callback_data=f"ai_conf|cat|{cat}|{pid}")
            
            kb = InlineKeyboardMarkup([
                [btn_prev, btn_count, btn_next],
                [btn_action],
                [btn_back]
            ])
            
            txt = f"🖼 **Catálogo ({cat.upper()})**\nItem {idx+1} de {n}\nTipo: {ftype.upper()}"
            if mode == 'select': txt += "\n\n👇 Pulsa 'Seleccionar' para usar este."
            
            try:
                # Media Switching logic (same as before)
                if ftype == 'sticker':
                    await msg.delete()
                    await c.send_sticker(cid, file_id, reply_markup=kb)
                elif ftype == 'video':
                     await msg.edit_media(InputMediaVideo(file_id, caption=txt), reply_markup=kb)
                elif ftype == 'animation':
                     await msg.edit_media(InputMediaAnimation(file_id, caption=txt), reply_markup=kb)
                else: 
                     await msg.edit_media(InputMediaPhoto(file_id, caption=txt), reply_markup=kb)
                     
            except Exception as e:
                try: await msg.delete()
                except: pass
                if ftype == 'video': await c.send_video(cid, file_id, caption=txt, reply_markup=kb)
                elif ftype == 'animation': await c.send_animation(cid, file_id, caption=txt, reply_markup=kb)
                elif ftype == 'sticker': await c.send_sticker(cid, file_id, reply_markup=kb)
                else: await c.send_photo(cid, file_id, caption=txt, reply_markup=kb)
            return

        # --- ACTIONS (Select / Delete) ---
        if data.startswith("ai_conf|act|"):
            parts = data.split("|")
            cat, idx, action = parts[2], int(parts[3]), parts[4]
            pid = parts[5] if len(parts) > 5 else 'nsfw'
            
            if action == 'select':
                # Set Config
                if 'ai_images' not in conf: conf['ai_images'] = {}
                if pid not in conf['ai_images']: conf['ai_images'][pid] = {}
                if cat not in conf['ai_images'][pid]: conf['ai_images'][pid][cat] = {}
                
                # Get ID
                imgs = conf['ai_images'][pid][cat].get('images', [])
                if idx < len(imgs):
                    conf['ai_images'][pid][cat]['active'] = imgs[idx]
                    conf['ai_images'][pid][cat]['mode'] = 'single'
                    
                    from firebase_service import save_user_config_fb
                    asyncio.create_task(save_user_config_fb(cid, conf))
                    
                    await q.answer("✅ Imagen seleccionada.")
                    # Go back to menu
                    await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': f"ai_conf|cat|{cat}|{pid}", 'answer': q.answer, 'internal': True})())
                return

            elif action == 'delete':
                if 'ai_images' in conf and pid in conf['ai_images'] and cat in conf['ai_images'][pid]:
                     imgs = conf['ai_images'][pid][cat].get('images', [])
                     if idx < len(imgs):
                         # Delete
                         popped = imgs.pop(idx)
                         # Clean active if was this one
                         if conf['ai_images'][pid][cat].get('active') == popped:
                             conf['ai_images'][pid][cat]['active'] = None
                         
                         from firebase_service import save_user_config_fb
                         asyncio.create_task(save_user_config_fb(cid, conf))
                         
                         await q.answer("🗑 Borrada.")
                         
                         # Refresh nav (idx may change)
                         if not imgs:
                             # Empty -> Back to menu
                             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': f"ai_conf|cat|{cat}|{pid}", 'answer': q.answer, 'internal': True})())
                             return
                         
                         # Show next (or prev if was last)
                         new_idx = idx if idx < len(imgs) else len(imgs) - 1
                         await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': f"ai_conf|nav|{cat}|{new_idx}|view|{pid}", 'answer': q.answer, 'internal': True})())
                return
        
        # --- UPLOAD TRIGGER ---
        if data.startswith("ai_conf|upload|"):
            parts = data.split("|")
            cat = parts[2]
            pid = parts[3] if len(parts) > 3 else 'nsfw'

            # Set user state
            url_storage[cid] = {'ai_config_step': 'wait_image', 'category': cat, 'persona_id': pid}
            
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data=f"ai_conf|cat|{cat}|{pid}")]])
            txt = (f"📤 **Subir Archivos a {cat.upper()}**\n\n"
                   f"Envía ahora tus fotos, videos, gifs o stickers.\n"
                   f"Se agregarán automáticamente a la personalidad: **{pid.upper()}**.")
            
            if msg.photo or msg.video or msg.animation or msg.sticker or msg.document:
                 await msg.delete()
                 await c.send_message(cid, txt, reply_markup=kb)
            else: 
                 await msg.edit_text(txt, reply_markup=kb)
            return

        # --- ADD CUSTOM PERSONA TRIGGER ---
        if data == "ai_add_persona":
            # Set state
            url_storage[cid] = {'ai_add_step': 'wait_name'}
            
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data="menu|ai_config")]])
            txt = ("👤 **Nueva Personalidad**\n\n"
                   "Escribe el **NOMBRE** de tu nueva waifu/personalidad.\n"
                   "Ejemplo: `Goth Girl`, `Tsundere`, `Mi Novia`.")
            
            if msg.photo or msg.video or msg.animation or msg.sticker or msg.document:
                 await msg.delete()
                 await c.send_message(cid, txt, reply_markup=kb)
            else: 
                 await msg.edit_text(txt, reply_markup=kb)
            return

        if data.startswith("ai_conf|upload|"):
            cat = data.split("|")[2]
            url_storage[cid] = {'ai_config_step': 'wait_image', 'category': cat}
            
            txt = f"📤 **Subir Imagen para {cat.upper()}**\n\nEnvíame la imagen (o varias si quieres armar pack)."
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data=f"ai_conf|cat|{cat}")]])
            
            if msg.photo or msg.caption: await msg.edit_caption(txt, reply_markup=kb)
            else: await msg.edit_text(txt, reply_markup=kb)
            return

        if data.startswith("ai_conf|clear|"):
            cat = data.split("|")[2]
            if 'ai_images' in conf and cat in conf['ai_images']:
                # conf['ai_images'][cat]['images'] = [] # Clear list
                # conf['ai_images'][cat]['active'] = None
                # Better: Reset structure
                conf['ai_images'][cat] = {'mode': 'single', 'images': [], 'active': None}
                
                from firebase_service import save_user_config_fb
                asyncio.create_task(save_user_config_fb(cid, conf))
                
            await q.answer("🗑 Pack eliminado.", show_alert=True)
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': f"ai_conf|cat|{cat}", 'answer': q.answer, 'internal': True})())
            return
            if msg.photo or msg.caption:
                await msg.edit_caption(txt, reply_markup=kb_tools)
            else:
                await msg.edit_text(txt, reply_markup=kb_tools)
            return

        # 1. Iniciadores de Herramientas (Modos Exclusivos)
        if data == "menu|join_init":
            val, disabled = await set_exclusive_mode(cid, 'join_party_mode')
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            url_storage.pop(cid, None) # Limpiar clips previos
            
            await msg.edit_text(
                "🔗 **Modo Unir Party Activo**\n\n🎬 **¡Envíame los clips ahora!**\nLos iré registrando uno por uno.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]])
            )
            return

        if data == "menu|party_init":
            val, disabled = await set_exclusive_mode(cid, 'party_mode')
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🧩 Partes", callback_data="party_sel|parts"), InlineKeyboardButton("⏱ Tiempo", callback_data="party_sel|time")],
                [InlineKeyboardButton("✂️ Rango", callback_data="party_sel|range")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            await msg.edit_text("🎉 **Modo Party Activo**\n\n1️⃣ **Configura** abajo 👇\n2️⃣ O **envía video** directo.", reply_markup=kb)
            return

        if data == "menu|extract_init":
            val, disabled = await set_exclusive_mode(cid, 'extract_mode')
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            await msg.edit_text("🖼 **Modo Extractor Activo**\n\n🎬 Envíame un video para empezar a sacar fotogramas.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]]))
            return

        if data == "menu|gif_init":
            val, disabled = await set_exclusive_mode(cid, 'gif_mode')
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            await msg.edit_text("🎬 **Creador de GIF Activo**\n\n🎬 Envíame el video que quieras convertir a GIF.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]]))
            return

        if data == "menu|sticker_init":
            val, disabled = await set_exclusive_mode(cid, 'sticker_mode')
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            await msg.edit_text("🎭 **Creador de Stickers Activo**\n\n🖼 Envíame una imagen para convertirla en Sticker.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]]))
            return

        if data == "menu|mp3_init":
            val, disabled = await set_exclusive_mode(cid, 'mp3_mode')
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            await msg.edit_text("🎵 **Extractor MP3 Activo**\n\n🎬 Envíame un video y extraeré el audio en MP3.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]]))
            return

        if data == "menu|saucenao_init":
            val, disabled = await set_exclusive_mode(cid, 'saucenao_mode')
            if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            await msg.edit_text("🔍 **Buscador SauceNAO Activo**\n\n🖼 Envíame una imagen (Anime/Art) para buscar su fuente.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]]))
            return

        # 2. Menús de Configuración AUTO (Mockup del usuario)


        if data.startswith("set_aj|"):
            val = data.split("|")[1] == "on"
            conf['auto_join_party'] = val
            if val:
                conf['auto_party'] = False
                conf['auto_extract'] = False
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            # Volver a Herramientas (Bypass anti-spam)
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return

        if data == "menu|auto_e_set":
            s = "🟢 Activado (Siempre ON)" if conf.get('auto_extract') else "🔴 Desactivado (Auto-OFF)"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🟢 Siempre Activo", callback_data="set_ae|on")],
                [InlineKeyboardButton("🔴 Desactivar (Auto-OFF)", callback_data="set_ae|off")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            txt = f"🔁 **Auto Extractor**\n\nEstado Actual: {s}\n\nSi activas esto, el Extractor NO se desactivará tras procesar un video."
            if msg.photo or msg.caption: await msg.edit_caption(txt, reply_markup=kb)
            else: await msg.edit_text(txt, reply_markup=kb)
            return









        # --- SECCION: EXTRACTOR DE IMAGENES ---
        
        if data == "extract_menu":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏱ Segundos", callback_data="extract_sel|sec"), InlineKeyboardButton("🕒 Minutos", callback_data="extract_sel|min")],
                [InlineKeyboardButton("🎯 Frame Exacto", callback_data="extract_sel|exact")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            txt = "🖼 **Opciones de Extracción**\n¿Cómo quieres extraer las imágenes?"
            if msg.photo or msg.caption: await msg.edit_caption(txt, reply_markup=kb)
            else: await msg.edit_text(txt, reply_markup=kb)
            return

        if data.startswith("extract_sel|"):
            mode = data.split("|")[1]
            if mode == "sec":
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("5s", callback_data="extract_val|sec|5"), InlineKeyboardButton("10s", callback_data="extract_val|sec|10")],
                    [InlineKeyboardButton("15s", callback_data="extract_val|sec|15"), InlineKeyboardButton("20s", callback_data="extract_val|sec|20")],
                    [InlineKeyboardButton("25s", callback_data="extract_val|sec|25"), InlineKeyboardButton("30s", callback_data="extract_val|sec|30")],
                    [InlineKeyboardButton("45s", callback_data="extract_val|sec|45"), InlineKeyboardButton("60s", callback_data="extract_val|sec|60")],
                    [InlineKeyboardButton("✏ Personalizado", callback_data="extract_val|sec|custom")],
                    [InlineKeyboardButton("🔙 Volver", callback_data="extract_menu")]
                ])
                await msg.edit_text("⏱ **Extraer cada X Segundos**\nSelecciona el intervalo:", reply_markup=kb)
            elif mode == "min":
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("5m", callback_data="extract_val|min|5"), InlineKeyboardButton("10m", callback_data="extract_val|min|10")],
                    [InlineKeyboardButton("15m", callback_data="extract_val|min|15"), InlineKeyboardButton("20m", callback_data="extract_val|min|20")],
                    [InlineKeyboardButton("25m", callback_data="extract_val|min|25"), InlineKeyboardButton("30m", callback_data="extract_val|min|30")],
                    [InlineKeyboardButton("✏ Personalizado", callback_data="extract_val|min|custom")],
                    [InlineKeyboardButton("🔙 Volver", callback_data="extract_menu")]
                ])
                await msg.edit_text("🕒 **Extraer cada X Minutos**\nSelecciona el intervalo:", reply_markup=kb)
            elif mode == "exact":
                await msg.edit_text("🎯 **Frame Exacto**\nEnvíame el tiempo exacto (ej: `01:23` o `45`) para extraer ese fotograma:", 
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="extract_menu")]]))
                url_storage[cid] = {'extract_step': 'wait_exact', 'file': url_storage.get(cid, {}).get('file')}
            return
            
        if data.startswith("extract_val|"):
            pts = data.split("|")
            mode, val = pts[1], pts[2]
            st = url_storage.get(cid, {})
            f_p = st.get('file')
            
            # 1. Custom Check FIRST (Avoid DL)
            if val == "custom":
                await msg.edit_text(f"✏ **Intervalo Personalizado ({mode})**\nEnvíame el número de {mode} deseado:", 
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data=f"extract_sel|{mode}")]]))
                # Preserve ST (keep extract_msg)
                st['extract_step'] = f'wait_custom_{mode}'
                url_storage[cid] = st
                return

            # 2. Deferred Download (Only if NOT custom)
            if not f_p or not os.path.exists(f_p):
                 extract_msg = st.get('extract_msg') 
                 if extract_msg:
                     # Confirmacion Visual
                     await msg.edit(f"✅ **Configurado: {val} ({mode})**")
                     wait = await msg.reply(f"⬇️ **Descargando para extraer...**\n🚀 Velocidad Máxima Activada")
                     
                     from utils import download_parallel
                     from tools_media import progreso
                     import random
                     import config
                     
                     # Create Temp Dir
                     tool_folder = os.path.join(config.DATA_DIR, "extract_temp")
                     if not os.path.exists(tool_folder): os.makedirs(tool_folder)
                     job_dir = os.path.join(tool_folder, f"job_{cid}_{time.time_ns()}_{random.randint(1000, 9999)}")
                     if not os.path.exists(job_dir): os.makedirs(job_dir)
                     
                     # Ext guess
                     ext = ".mp4"
                     if extract_msg.video and extract_msg.video.file_name: _, ext = os.path.splitext(extract_msg.video.file_name)
                     elif extract_msg.document and extract_msg.document.file_name: _, ext = os.path.splitext(extract_msg.document.file_name)
                     
                     f_p = await download_parallel(c, extract_msg, os.path.join(job_dir, f"extract_{cid}{ext}"), progress=progreso, progress_args=(wait, [0,0], "Descargando"))
                     if not f_p: f_p = await c.download_media(extract_msg, file_name=os.path.join(job_dir, f"extract_{cid}{ext}"))
                     
                     if not f_p: 
                         await wait.edit("❌ Error descargando video.")
                         return
                     
                     # Update storage
                     st['file'] = f_p
                     url_storage[cid] = st
                 else:
                     return await q.answer("❌ Video expiró.", show_alert=True)

            # Ejecutar lógica
            await run_extract_logic(c, cid, f_p, mode, val, msg)
            return


        if data.startswith("set_ae|"):
            val = data.split("|")[1] == "on"
            conf['auto_extract'] = val
            if val:
                conf['auto_party'] = False
                conf['auto_join_party'] = False
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            return



        # --- SECCION: PARTY MODE REFACTORED ---
        
        # --- AUTO PARTY MENU & CUSTOM ---
        if data == "menu|autoparty_menu":
            is_on = conf.get('auto_party', False)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Estado: {'🟢 ACTIVO' if is_on else '🔴 APAGADO'}", callback_data="toggle|auto_party")],
                [InlineKeyboardButton("⚙️ Personalizado", callback_data="menu|auto_party_custom")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            await msg.edit_text("🔁 **Menu Auto Party**\n\nSi activas esto, el Modo Party NO se desactivará al terminar un video.\nTodos los videos que envíes serán procesados.", reply_markup=kb)
            return

        if data == "menu|auto_party_custom":
            cust_on = conf.get('auto_party_custom', False)
            cust_cfg = conf.get('auto_party_cfg') 
            
            txt_cfg = "Sin Config"
            if cust_cfg:
                 m, v = cust_cfg
                 txt_cfg = f"{m}={v}"

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Fijo: {'🟢 SI' if cust_on else '🔴 NO'}", callback_data="auto_party_toggle|custom")],
                [InlineKeyboardButton(f"🔧 Config: {txt_cfg}", callback_data="ignore")],
                [InlineKeyboardButton("🧩 Partes", callback_data="auto_party_set_mode|parts"), InlineKeyboardButton("⏱ Tiempo", callback_data="auto_party_set_mode|time")],
                 [InlineKeyboardButton("✂️ Rango", callback_data="auto_party_set_mode|range")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|autoparty_menu")]
            ])
            await msg.edit_text("⚙️ **Auto Party Personalizado**\n\nSi 'Fijo' está ON, usaré siempre esta configuración sin preguntar por cada video.", reply_markup=kb)
            return

        if data == "auto_party_toggle|custom":
             conf['auto_party_custom'] = not conf.get('auto_party_custom', False)
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|auto_party_custom', 'answer': q.answer, 'internal': True})())
             return

        if data.startswith("auto_party_set_mode|"):
             mode = data.split("|")[1]
             if mode == "parts":
                 bts = [
                    [InlineKeyboardButton("2", callback_data="auto_party_save|parts|2"), InlineKeyboardButton("3", callback_data="auto_party_save|parts|3"), InlineKeyboardButton("4", callback_data="auto_party_save|parts|4")],
                    [InlineKeyboardButton("5", callback_data="auto_party_save|parts|5"), InlineKeyboardButton("10", callback_data="auto_party_save|parts|10")],
                    [InlineKeyboardButton("✏️ Manual", callback_data="auto_party_input|parts")],
                    [InlineKeyboardButton("🔙 Volver", callback_data="menu|auto_party_custom")]
                 ]
                 await msg.edit("🧩 **(Auto) Dividir en Partes**\nConfiguración por defecto:", reply_markup=InlineKeyboardMarkup(bts))
             elif mode == "time":
                  bts = [
                    [InlineKeyboardButton("10s", callback_data="auto_party_save|sec|10"), InlineKeyboardButton("30s", callback_data="auto_party_save|sec|30"), InlineKeyboardButton("1m", callback_data="auto_party_save|min|1")],
                    [InlineKeyboardButton("5m", callback_data="auto_party_save|min|5"), InlineKeyboardButton("10m", callback_data="auto_party_save|min|10")],
                    [InlineKeyboardButton("✏️ Manual", callback_data="auto_party_input|sec")],
                     [InlineKeyboardButton("🔙 Volver", callback_data="menu|auto_party_custom")]
                  ]
                  await msg.edit("⏱ **(Auto) Por Duración**\nConfiguración por defecto:", reply_markup=InlineKeyboardMarkup(bts))
             elif mode == "range":
                  url_storage[cid] = {'auto_party_input_mode': 'range'}
                  await msg.edit("✂️ **(Auto) Rango Fijo**\nEnvía el rango (ej: `00:00 00:10`).\nSe aplicará a TODOS los videos (cuidado si duran menos).", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="menu|auto_party_custom")]]))
             return

        if data.startswith("auto_party_save|"):
             pts = data.split("|")
             mode, val = pts[1], pts[2]
             conf['auto_party_cfg'] = (mode, val)
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|auto_party_custom', 'answer': q.answer, 'internal': True})())
             return

        if data.startswith("auto_party_input|"):
             mode = data.split("|")[1]
             url_storage[cid] = {'auto_party_input_mode': mode}
             await msg.edit(f"✍️ **Ingresa el valor Auto ({mode}):**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="menu|auto_party_custom")]]))
             return

        # --- JOIN PARTY EXECUTE ---
        if data == "party_join_now":
            # Usamos la lógica compartida (inyección de dependencias si hiciera falta, pero es global)
            await run_join_party_logic(c, cid, msg)
            return

        # 1. Menu Principal Party (Opciones o Iniciador)
        if data == "party_menu":
            # Usar set_exclusive_mode para asegurar limpieza
            await set_exclusive_mode(cid, 'party_mode')
            
            # Recargar config actualizada
            conf = get_config(cid)

            # MOSTRAR MENU SIEMPRE (Refactor: Pre-Config or Post-Config)
            # Opciones de configuración
            kb_p = InlineKeyboardMarkup([
                [InlineKeyboardButton("🧩 Partes", callback_data="party_sel|parts"), InlineKeyboardButton("⏱ Tiempo", callback_data="party_sel|time")],
                [InlineKeyboardButton("✂️ Rango", callback_data="party_sel|range")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
            ])
            
            st = url_storage.get(cid)
            if st and 'file' in st and os.path.exists(st['file']):
                # YA tenemos video -> Mostrar Video Options
                await msg.edit("✂️ **Modo Party (Video Cargado)**\nSelecciona una opción para procesar:", reply_markup=kb_p)
            else:
                # NO tenemos video -> Mostrar Opciones de Pre-Configuración
                await msg.edit_text("✂️ **Modo Party Activo**\n\n1️⃣ **Configura** el corte abajo 👇\n2️⃣ O **envía el video** directo (te preguntaré después).", reply_markup=kb_p)
            return

        # 2. Selección de Herramienta Party
        if data.startswith("party_sel|"):
            mode = data.split("|")[1]
            if mode == "parts":
                bts = [
                    [InlineKeyboardButton("2", callback_data="party_exec|parts|2"), InlineKeyboardButton("3", callback_data="party_exec|parts|3"), InlineKeyboardButton("4", callback_data="party_exec|parts|4")],
                    [InlineKeyboardButton("5", callback_data="party_exec|parts|5"), InlineKeyboardButton("10", callback_data="party_exec|parts|10")],
                    [InlineKeyboardButton("✏️ Manual", callback_data="party_input|parts")],
                    [InlineKeyboardButton("🔙 Volver", callback_data="party_menu")] # Volver a Opciones
                ]
                await msg.edit("🧩 **Dividir en Partes**\n¿En cuántas partes cortarlo?", reply_markup=InlineKeyboardMarkup(bts))
            elif mode == "time":
                bts = [
                    [InlineKeyboardButton("10s", callback_data="party_exec|sec|10"), InlineKeyboardButton("30s", callback_data="party_exec|sec|30"), InlineKeyboardButton("1m", callback_data="party_exec|min|1")],
                    [InlineKeyboardButton("5m", callback_data="party_exec|min|5"), InlineKeyboardButton("10m", callback_data="party_exec|min|10")],
                    [InlineKeyboardButton("✏️ Manual (seg)", callback_data="party_input|sec"), InlineKeyboardButton("✏️ Manual (min)", callback_data="party_input|min")],
                    [InlineKeyboardButton("🔙 Volver", callback_data="party_menu")] # Volver a Opciones
                ]
                await msg.edit("⏱ **Dividir por Duración**\n¿De cuánto cada parte?", reply_markup=InlineKeyboardMarkup(bts))
            elif mode == "range":
                 url_storage[cid] = url_storage.get(cid, {})
                 url_storage[cid]['party_input_mode'] = 'range'
                 await msg.edit("✂️ **Cortar Rango(s)**\n\nEnvía pares de inicio y fin.\nEjemplo: `00:10 01:30` (Un corte)\nEjemplo Múltiple: `00:10 00:20 01:00 01:30` (Dos cortes)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="party_menu")]]))
            return

        if data.startswith("party_input|"):
             mode = data.split("|")[1]
             url_storage[cid] = url_storage.get(cid, {})
             url_storage[cid]['party_input_mode'] = mode
             await msg.edit(f"✍️ **Ingresa el valor** para dividir ({mode}):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="party_sel|"+mode if mode in ['parts'] else "party_menu")]]))
             return

        if data.startswith("party_exec|"):
            pts = data.split("|")
            mode, val = pts[1], pts[2]
            st = url_storage.get(cid, {})
            
            # Si se lanzó sin archivo (por config previa rara?), pedir video
            if 'file' not in st:
                # --- DEFERRED DOWNLOAD LOGIC ---
                if 'party_msg' in st or msg.reply_to_message:
                    # Tarea Asíncrona (Queue System)
                    
                    async def party_worker(client, chat_id, message_vid, mode_w, val_w, wait_msg):
                        # Check Queue Status
                        if SEM_PARTY.locked():
                            try:
                                await wait_msg.edit(f"⏳ **En Cola (Posición {len(SEM_PARTY._waiters) if hasattr(SEM_PARTY, '_waiters') else '?'})...**\nEsperando turno.")
                            except: pass

                        async with SEM_PARTY:
                            try:
                                await wait_msg.edit(f"⬇️ **Bajando video para {mode_w}={val_w}...**\n(Descarga Diferida)")
                                
                                from utils import download_parallel
                                from tools_media import progreso
                                
                                # Determinar extensión
                                ext = ".mp4"
                                if message_vid.audio: ext = ".mp3"
                                if message_vid.document and message_vid.document.file_name: _, ext = os.path.splitext(message_vid.document.file_name)
                                elif message_vid.video and message_vid.video.file_name: _, ext = os.path.splitext(message_vid.video.file_name)
                                elif message_vid.audio and message_vid.audio.file_name: _, ext = os.path.splitext(message_vid.audio.file_name)
                                
                                f_p = await download_parallel(client, message_vid, os.path.join(DATA_DIR, f"party_{chat_id}_{message_vid.id}{ext}"), concurrency=8, progress=progreso, progress_args=(wait_msg, [0,0], "Descargando"))
                                if not f_p: f_p = await client.download_media(message_vid, file_name=os.path.join(DATA_DIR, f"party_{chat_id}_{message_vid.id}{ext}"))
                                
                                if f_p and os.path.exists(f_p):
                                    # Proceed with Logic
                                    await run_party_logic(client, chat_id, f_p, mode_w, val_w, wait_msg)
                                else:
                                    await wait_msg.edit("❌ Error en descarga diferida.")
                            except Exception as e:
                                print(f"Party Worker Error: {e}")
                                try: await wait_msg.edit(f"❌ Error interno: {e}")
                                except: pass

                    # Detectar mensaje origen (Reply o Storage)
                    m_target = msg.reply_to_message if msg.reply_to_message else st.get('party_msg')
                    
                    if m_target:
                        # Lanzar Worker
                        wait = await msg.edit(f"⏳ **Añadido a la cola**...")
                        asyncio.create_task(party_worker(c, cid, m_target, mode, val, wait))
                        url_storage.pop(cid, None)
                        return
                    else:
                         await msg.edit("❌ Error: No se encontró el video original.")
                         return

                else:
                    url_storage[cid] = st
                    url_storage[cid]['party_pending'] = (mode, val)
                    await msg.edit(f"✅ **Configurado:** `{mode}={val}`\n\n🎬 **Ahora envíame el video** para procesarlo.")
                    return
            
            # EJECUTAR DIRECTAMENTE
            await msg.delete()
            await run_party_logic(c, cid, st['file'], mode, val)
            url_storage.pop(cid, None)
            return

        # --- CUT INIT LOGIC ---
        if data.startswith("cut_input|"):
             mode = data.split("|")[1]
             url_storage[cid] = url_storage.get(cid, {})
             url_storage[cid]['cut_input_mode'] = mode
             await msg.edit(f"✍️ **Ingresa el tiempo a eliminar del inicio**\n\nEjemplos: `10` (segundos), `01:20` (min:seg).\nEl video empezará desde ese punto.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]]))
             return

        if data.startswith("cut_exec|"):
            val = data.split("|")[1]
            st = url_storage.get(cid, {})
            f_path = st.get('file')
            
            if not f_path or not os.path.exists(f_path):
                await q.answer("❌ El archivo expiró.", show_alert=True)
                return

            await msg.edit(f"✂️ **Cortando inicio ({val})...**\nProcesando...")
            
            from tools_media import cut_video_start, get_meta, get_thumb
            
            # FIX: Call async directly (now re-encoding)
            out = await cut_video_start(f_path, val)
            
            if out:
                await msg.edit("📤 **Enviando video cortado...**")
                w, h, dur = await get_meta(out)
                t_path = await get_thumb(out, cid, int(time.time()))
                
                from tools_media import progreso
                try:
                    await c.send_video(cid, out, width=w, height=h, duration=dur, thumb=t_path, caption=f"✂️ **Corte Inicial ({val})**", progress=progreso, progress_args=(msg, [0,0], None))
                except Exception as e:
                     await c.send_document(cid, out, caption=f"✂️ **Corte Inicial ({val})**", progress=progreso, progress_args=(msg, [0,0], None))

                if t_path and os.path.exists(t_path): os.remove(t_path)
                if os.path.exists(out): os.remove(out)
                await msg.delete()
                
                # Auto-OFF
                conf['cut_init_mode'] = False
                from firebase_service import save_user_config_fb
                asyncio.create_task(save_user_config_fb(cid, conf))
                
            else:
                await msg.edit("❌ Error al cortar el video.")
            
            # Cleanup original
            if os.path.exists(f_path): os.remove(f_path)
            url_storage.pop(cid, None)
            return

        # --- SECCION: DESCARGAS ---
        if data.startswith("dl|"):
            raw_val = data.split("|")[1]
            quality, l_key = None, cid # Fallback legacy
            
            if "_" in raw_val:
                quality, lid = raw_val.rsplit("_", 1)
                l_key = f"{cid}_{lid}"
                d_st = url_storage.get(l_key)
                
                # Falback / Debug
                if not d_st:
                     print(f"❌ [DEBUG] Key Missing: {l_key}. Available Keys in keys(): {[k for k in url_storage.keys() if str(cid) in str(k)]}")
            else:
                quality = raw_val
                d_st = url_storage.get(cid)
            
            if not d_st: return await q.answer("⚠️ Link expiró o es muy antiguo.", show_alert=True)
            
            await msg.delete()
            # url_storage.pop(l_key, None) # PERSISTENCE FIX: Do not delete immediately to allow re-clicks or queue checks
            
            d_st['fast_enabled'] = conf.get('fast_enabled', True)
            target_msg = msg.reply_to_message if msg.reply_to_message else msg
            asyncio.create_task(procesar_descarga(c, cid, d_st['url'], quality, d_st, target_msg))
            return

        # --- SECCION: CONFIGURACION ---
        if data.startswith("toggle|"):
            k = data.split("|")[1]
            
            # --- MODIFIERS (NON-EXCLUSIVE) ---
            if k == "meta": conf['meta'] = not conf.get('meta', True)
            elif k == "fast": conf['fast_enabled'] = not conf.get('fast_enabled', True)
            elif k == "doc": conf['doc_mode'] = not conf.get('doc_mode', False)
            elif k == "group": conf['group_mode'] = not conf.get('group_mode', True)
            elif k == "ask_direct": conf['ask_direct'] = not conf.get('ask_direct', True)
            elif k == "lang": conf['lang'] = 'es' if conf.get('lang', 'es') == 'orig' else 'orig'
            elif k == "fmt": conf['fmt'] = 'mp3' if conf.get('fmt', 'mp4') == 'mp4' else 'mp4'
            elif k == "party_zip": conf['party_zip'] = not conf.get('party_zip', False)
            elif k == "join_party_zip": conf['join_party_zip'] = not conf.get('join_party_zip', False)
            elif k == "extract_party_zip": conf['extract_party_zip'] = not conf.get('extract_party_zip', True)
            elif k == "ai_green_mode": conf['ai_green_mode'] = not conf.get('ai_green_mode', False)
            elif k == "ai_focus_mode": conf['ai_focus_mode'] = not conf.get('ai_focus_mode', False)
            elif k == "max_downloads":
                curr = conf.get('max_downloads', 'default')
                if curr == 'default':
                    conf['max_downloads'] = 5
                elif curr == 5:
                    conf['max_downloads'] = 10
                else:
                    conf['max_downloads'] = 'default'
            
            # --- TOOLS SPECIFIC MODES ---
            elif k == "doc_tools": conf['doc_mode_tools'] = not conf.get('doc_mode_tools', False)
            elif k == "group_tools": conf['group_mode_tools'] = not conf.get('group_mode_tools', False)
            
            # --- FUSION MODE (Exclusive) ---
            elif k == "fusion":
                new_val, disabled = await set_exclusive_mode(cid, 'fusion_mode', is_toggle=True)
                # Refresh Menu
                from tools_fusion import init_fusion_menu
                
                # Delete old message to avoid spam if it was a menu
                try: await msg.delete()
                except: pass
                
                await init_fusion_menu(c, cid, conf)
                
                txt = "🟢 ACTIVADO" if new_val else "🔴 DESACTIVADO"
                if disabled: txt += f"\n(🛑 Se desactivó: {disabled})"
                await q.answer(txt)
                return

            # --- EXCLUSIVE MODES ---
            elif k == "tagger": 
                val, disabled = await set_exclusive_mode(cid, 'tagger_mode', is_toggle=True)
                if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            elif k == "research":
                val, disabled = await set_exclusive_mode(cid, 'research_mode', is_toggle=True)
                if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            elif k == "translate_manga":
                val, disabled = await set_exclusive_mode(cid, 'translate_manga_mode', is_toggle=True)
                if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            elif k == "sub_auto":
                val, disabled = await set_exclusive_mode(cid, 'sub_auto_mode', is_toggle=True)
                if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            elif k == "auto_party":
                 val, disabled = await set_exclusive_mode(cid, 'auto_party', is_toggle=True)
                 if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
                 
                 from firebase_service import save_user_config_fb
                 asyncio.create_task(save_user_config_fb(cid, conf))
                 await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|autoparty_menu', 'answer': q.answer, 'internal': True})())
                 return
            elif k == "auto_join_party":
                 val, disabled = await set_exclusive_mode(cid, 'auto_join_party', is_toggle=True)
                 if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            elif k == "txt_mode":
                 val, disabled = await set_exclusive_mode(cid, 'txt_mode', is_toggle=True)
                 if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
            
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            
            # MENU REFRESH LOGIC
            # If from tools or known tool toggle
            if k in ["party_zip", "join_party_zip", "extract_party_zip", "auto_join_party", "tagger", "research", "translate_manga", "sub_auto", "doc_tools", "group_tools"]:
                await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|tools', 'answer': q.answer, 'internal': True})())
            elif k in ["ai_green_mode", "ai_focus_mode"]:
                 await cb(c, type('obj', (object,), {'message': msg, 'from_user': q.from_user, 'data': 'menu|ai_config', 'answer': q.answer, 'internal': True})())
            else:
                await msg.edit_reply_markup(gen_kb(conf, uid))
            return

        # --- LOGICA: EJECUTAR UNIÓN ---
        if data == "party_join_now":
            st = url_storage.get(cid)
            if not st or 'join_clips' not in st or not st['join_clips']:
                return await q.answer("❌ No hay clips registrados.", show_alert=True)
            
            clips = st['join_clips']
            url_storage.pop(cid, None) # Limpiar inmediatamente
            
            await msg.edit_text(f"⏳ **Descargando {len(clips)} clips...**\nEsto puede tardar según el tamaño.")
            
            from utils import merge_videos_ffmpeg, download_parallel
            paths = []
            try:
                # 1. Descargar todos (Modo TURBO x16)
                for i, m_clip in enumerate(clips):
                    await msg.edit_text(f"🚀 **Bajando CLIP {i+1}/{len(clips)} (TURBO x16)...**")
                    p = await download_parallel(c, m_clip, os.path.join(DATA_DIR, f"join_{cid}_{i}.mp4"))
                    if p: paths.append(p)
                
                if len(paths) < 2:
                    await msg.edit_text("❌ Error: Se necesitan al menos 2 clips válidos.")
                    return
                
                # 2. Unir
                await msg.edit_text(f"🎬 **Fucionando {len(paths)} clips...**\nEspere un momento.")
                out_p = os.path.join(DATA_DIR, f"joined_{cid}_{int(time.time())}.mp4")
                final_v = await asyncio.get_running_loop().run_in_executor(None, lambda: merge_videos_ffmpeg(paths, out_p))
                
                if not final_v or not os.path.exists(final_v):
                    await msg.edit_text("❌ Error al unir los videos.")
                    return
                
                # 3. Enviar
                await msg.edit_text("📤 **Enviando video unido...**")
                
                limit_bytes = 1.9 * 1024 * 1024 * 1024
                
                # --- LOGICA: ZIP (Modo Unir) ---
                if conf.get('join_party_zip', False):
                    await msg.edit_text("📦 **Comprimiendo en ZIP...**")
                    from utils import create_split_zips, split_file_into_volumes
                    # Crear zip inicial
                    zip_files = await asyncio.get_running_loop().run_in_executor(None, lambda: create_split_zips([final_v], f"Joined_Party_{cid}"))
                    
                    if zip_files:
                        for zp in zip_files:
                            # Si el ZIP resultante es > 1.9GB (raro para un solo video pero posible), dividir en volúmenes
                            if os.path.getsize(zp) > limit_bytes:
                                await msg.edit_text("📦 **Archivo masivo detectado, dividiendo en volúmenes...**")
                                volumes = await asyncio.get_running_loop().run_in_executor(None, lambda: split_file_into_volumes(zp, limit_bytes))
                                for vol in volumes:
                                    await c.send_document(cid, vol, caption=f"📦 **ZIP Volumen**: `{os.path.basename(vol)}`")
                                    if os.path.exists(vol) and vol != zp: os.remove(vol)
                            else:
                                await c.send_document(cid, zp, caption="📦 **Join Party ZIP**")
                            
                            if os.path.exists(zp): os.remove(zp)
                    else:
                        await msg.edit_text("❌ Error al comprimir el video.")
                else:
                    from tools_media import get_meta, get_thumb
                    from utils import split_video_by_size
                    
                    # Chequeo de tamaño para video directo
                    final_size = os.path.getsize(final_v)
                    v_to_send = [final_v]
                    
                    if final_size > limit_bytes:
                        await msg.edit_text("🎬 **Video muy grande detectado, dividiendo en partes jugables...**")
                        v_to_send = await asyncio.get_running_loop().run_in_executor(None, lambda: split_video_by_size(final_v, limit_bytes))

                    # Enviar partes
                    for i, v_part in enumerate(v_to_send):
                        w, h, dur = await get_meta(v_part)
                        thm = await get_thumb(v_part, cid, f"join_{int(time.time())}_{i}")
                        
                        # Respetar Doc Mode
                        is_doc = conf.get('doc_mode', False)
                        cap = f"🔗 **Video Unido Part {i+1}**" if len(v_to_send) > 1 else "🔗 **Video Unido (Party Join)**"
                        
                        if is_doc:
                            await c.send_document(cid, v_part, thumb=thm, caption=cap)
                        else:
                            await c.send_video(cid, v_part, width=w, height=h, duration=dur, thumb=thm, caption=cap)
                        
                        if thm and os.path.exists(thm): os.remove(thm)
                        if v_part != final_v and os.path.exists(v_part): os.remove(v_part)
                    
                if os.path.exists(final_v): os.remove(final_v)
                for p in paths:
                    if os.path.exists(p): os.remove(p)
                
                await msg.delete()
                
                # Auto Disable Logic (Igual que Party Mode)
                if not conf.get('auto_join_party', False):
                    conf['join_party_mode'] = False
                    from firebase_service import save_user_config_fb
                    asyncio.create_task(save_user_config_fb(cid, conf))
                    await c.send_message(cid, "✅ **Unión finalizada.**\nModo Unir Party desactivado.", reply_markup=gen_kb(conf, cid))

            except Exception as e:
                await msg.edit_text(f"❌ Error crítico en Join: {e}")
            return

        if data == "menu|auto":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🌟 Máxima Calidad", callback_data="set_auto|max")],
                [InlineKeyboardButton("📉 Mínimo Peso", callback_data="set_auto|min")],
                [InlineKeyboardButton("🎯 Calidad Predefinida", callback_data="menu|fixed_quality")],
                [InlineKeyboardButton("🔴 Desactivar", callback_data="set_auto|off")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|main")]
            ])
            await msg.edit_text("⚙️ **Auto-Descarga**", reply_markup=kb)
            return

        if data == "menu|fixed_quality":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("4320p (8K UHD)", callback_data="set_auto|4320"), InlineKeyboardButton("2160p (4K UHD)", callback_data="set_auto|2160")],
                [InlineKeyboardButton("1440p (2K / QHD)", callback_data="set_auto|1440"), InlineKeyboardButton("1080p (Full HD)", callback_data="set_auto|1080")],
                [InlineKeyboardButton("720p (HD)", callback_data="set_auto|720"), InlineKeyboardButton("480p (SD)", callback_data="set_auto|480")],
                [InlineKeyboardButton("360p", callback_data="set_auto|360"), InlineKeyboardButton("240p", callback_data="set_auto|240")],
                [InlineKeyboardButton("144p", callback_data="set_auto|144")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|auto")]
            ])
            await msg.edit_text("🎯 **Selecciona Calidad Predefinida**", reply_markup=kb)
            return

        if data.startswith("set_auto|"):
            v = data.split("|")[1]
            conf['q_auto'] = None if v == "off" else v
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await msg.edit_text("⚙️ **Configuración Actualizada**", reply_markup=gen_kb(conf, uid))
            return

        if data == "menu|party_off":
            conf['party_mode'] = False
            url_storage.pop(cid, None)
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await msg.edit_text("⚙️ **Panel de Configuración**\n🛑 Se desactivó el modo/herramienta: Modo Party", reply_markup=gen_kb(conf, uid))
            return

        if data == "menu|main":
            await msg.edit_text("⚙️ **Panel de Configuración**", reply_markup=gen_kb(conf, uid))
            return

        if data == "menu|admin" or data == "admin|refresh":
            if uid != OWNER_ID: return await q.answer("🔒", show_alert=True)
            
            # --- Estadísticas del Sistema ---
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            
            # Red (MB enviados desde arranque)
            net = psutil.net_io_counters()
            sent = net.bytes_sent / (1024*1024)
            recv = net.bytes_recv / (1024*1024)
            
            # --- Estadísticas de Tareas Detalladas ---
            from database import get_all_progress
            all_prog = get_all_progress()
            
            active_tasks_count = 0
            tasks_detail = []
            
            # Usuarios únicos interactuando
            active_users_interact = len(url_storage)

            for cid_task, msg_map in all_prog.items():
                try:
                    u_info = await c.get_users(cid_task)
                    u_name = u_info.first_name
                except: u_name = f"ID:{cid_task}"
                
                for mid, info in msg_map.items():
                    active_tasks_count += 1
                    p = info.get('percent', 0)
                    s = info.get('status', 'Procesando')
                    sp = info.get('speed', 'N/A')
                    nm = info.get('name', 'Archivo')[:20]
                    u = info.get('url', 'N/A')
                    # Formato: 👤 Nombre: [Descargando] 45% (12MB/s) - Video - Link
                    tasks_detail.append(f"👤 **{u_name}**: [{s}] `{int(p)}%` ({sp})\n📝 _{nm}_ | 🔗 {u}")

            from firebase_service import db
            st_doc = db.collection('bot_settings').document('stats').get()
            u_count = st_doc.to_dict().get('user_count', 0) if st_doc.exists else 0
            
            txt = (
                f"👮‍♂️ **Panel de Control Total**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 **SISTEMA**\n"
                f"🖥 **CPU:** `{cpu}%` | 🧠 **RAM:** `{ram}%`\n"
                f"⬆️ **Subido:** `{sent:.1f} MB` | ⬇️ **Bajado:** `{recv:.1f} MB`\n\n"
                f"👥 **ESTADÍSTICAS**\n"
                f"✨ **Usuarios Totales:** `{u_count}`\n"
                f"🖱 **Interactuando:** `{active_users_interact}`\n"
                f"🔥 **Tareas en Vivo:** `{active_tasks_count}`\n\n"
                + ("\n".join(tasks_detail[:15]) if tasks_detail else "_Sin tareas activas_") +
                (f"\n_... y {len(tasks_detail)-15} más_" if len(tasks_detail) > 15 else "") +
                f"\n\n🆔 **Tu ID:** `{uid}`"
            )
            
            kb_admin = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Actualizar", callback_data="admin|refresh")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|main")]
            ])
            
            if data == "admin|refresh":
                try: await msg.edit_text(txt, reply_markup=kb_admin)
                except: pass 
            else:
                await msg.edit_text(txt, reply_markup=kb_admin)
            return

        # --- SECCION: FUSION TOOL ---
        if data.startswith("fus_opt|"):
            opt = data.split("|")[1] # v_on, v_off, a_on, a_off
            st = url_storage.get(cid)
            if not st: return await q.answer("❌ Sesión expirada.", show_alert=True)
            
            # Logic
            if opt == "v_on": st['keep_v'] = True
            elif opt == "v_off": st['keep_v'] = False
            elif opt == "a_on": st['keep_a'] = True
            elif opt == "a_off": st['keep_a'] = False
            
            url_storage[cid] = st
            
            # Re-render KB
            kv = st.get('keep_v', False)
            ka = st.get('keep_a', True)
            
            t_v = "🔊 Video: ON" if kv else "🔇 Video: OFF"
            t_a = "🔊 Audio: ON" if ka else "🔇 Audio: OFF"
            
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(t_v, callback_data=f"fus_opt|{'v_off' if kv else 'v_on'}"), 
                 InlineKeyboardButton(t_a, callback_data=f"fus_opt|{'a_off' if ka else 'a_on'}")],
                [InlineKeyboardButton("✅ FUSIONAR", callback_data="fus_exec")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
            ])
            await msg.edit_reply_markup(kb)
            return

        if data == "fus_exec":
            st = url_storage.get(cid)
            if not st or 'video_path' not in st or 'audio_path' not in st:
                return await q.answer("❌ Falta información.", show_alert=True)
            
            v_path = st['video_path']
            a_path = st['audio_path']
            keep_v = st.get('keep_v', False)
            keep_a = st.get('keep_a', True)
            
            url_storage.pop(cid, None) # Clear immediately
            
            await msg.edit_text("🧬 **Fusionando Streams...**\n(Cortando audio al tamaño del video...)")
            
            from tools_fusion import process_fusion, get_thumb
            from tools_media import get_meta
            from utils import DATA_DIR
            
            out_path = os.path.join(DATA_DIR, f"fusion_{cid}_{int(time.time())}.mp4")
            
            success, err = await process_fusion(v_path, a_path, out_path, keep_video_audio=keep_v, keep_added_audio=keep_a)
            
            if success:
                await msg.edit_text("📤 **Enviando Fusión...**")
                w, h, dur = await get_meta(out_path)
                t_path = await get_thumb(out_path, cid, int(time.time()), duration=dur)
                
                try:
                    await c.send_video(
                        cid, out_path,
                        width=w, height=h, duration=dur, thumb=t_path,
                        caption=f"🧬 **Video Fusionado**\n🔊 V:{'ON' if keep_v else 'OFF'} | 🎵 A:{'ON' if keep_a else 'OFF'}"
                    )
                except Exception as e:
                    await c.send_document(cid, out_path, thumb=t_path, caption="🧬 **Video Fusionado**")
                
                # Cleanup
                if t_path and os.path.exists(t_path): os.remove(t_path)
                if os.path.exists(out_path): os.remove(out_path)
                await msg.delete()
            else:
                await msg.edit_text(f"❌ Error en Fusión:\n`{err}`")
            
            # Cleanup Inputs
            if os.path.exists(v_path): os.remove(v_path)
            if os.path.exists(a_path): os.remove(a_path)
            return

        # --- SECCION: MANGA FLOW ---
        if data == "menu|mflow":
            await q.answer("🔄 Cargando catálogo...")
            mgs = await get_all_mangas_paginated()
            if not mgs: return await q.answer("⚠️ Catálogo vacío.", show_alert=True)
            url_storage[cid] = {'catalog_list': mgs}
            curr = mgs[0]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️", callback_data=f"catalog|nav|{len(mgs)-1}"), InlineKeyboardButton(f"1/{len(mgs)}", callback_data="ignore"), InlineKeyboardButton("➡️", callback_data=f"catalog|nav|1")],
                [InlineKeyboardButton("📥 VER MANGA", callback_data=f"catalog|sel|{curr['id']}")],
                [InlineKeyboardButton("🔙 Salir", callback_data="menu|main")]
            ])
            txt = f"📚 **Manga Flow**\n\n📌 **{curr['title']}**\n👤 {curr['author']}"
            if curr.get('cover'):
                await msg.delete()
                await c.send_photo(cid, curr['cover'], caption=txt, reply_markup=kb)
            else:
                await msg.edit(txt, reply_markup=kb)
            return

        if data.startswith("catalog|"):
            m_m = data.split("|")[1]
            if m_m == "nav":
                px = int(data.split("|")[2])
                lst = url_storage.get(cid, {}).get('catalog_list', [])
                if not lst: return
                if px < 0: px = len(lst)-1
                if px >= len(lst): px = 0
                cur = lst[px]
                kb_n = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data=f"catalog|nav|{px-1}"), InlineKeyboardButton(f"{px+1}/{len(lst)}", callback_data="ignore"), InlineKeyboardButton("➡️", callback_data=f"catalog|nav|{px+1}")], [InlineKeyboardButton("📥 VER", callback_data=f"catalog|sel|{cur['id']}")], [InlineKeyboardButton("🔙 Salir", callback_data="menu|main")]])
                await msg.edit_media(InputMediaPhoto(cur['cover'], caption=f"📚 **Manga Flow**\n📌 **{cur['title']}**"), reply_markup=kb_n)
            elif m_m == "sel":
                mi = data.split("|")[2]
                t = next((m for m in url_storage[cid]['catalog_list'] if m['id'] == mi), None)
                url_storage[cid]['manga_data'] = t
                # AÑADIDO BOTÓN IMAGENES
                kb_d = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📦 ZIP", callback_data="manga_sel|zip"), InlineKeyboardButton("📄 PDF", callback_data="manga_sel|pdf")],
                    [InlineKeyboardButton("🖼 Ver Imágenes", callback_data="manga_sel|images")],
                    [InlineKeyboardButton("🔙 Volver", callback_data="catalog|nav|0")]
                ])
                await msg.edit_caption(f"📚 **{t['title']}**\nDescargar:", reply_markup=kb_d)
            return

        if data.startswith("manga_sel|"):
            pts = data.split("|")
            mg = url_storage.get(cid, {}).get('manga_data')
            
            # Si eligió formato, preguntar calidad (si es ZIP/PDF) o enviar directo (Imagenes)
            if len(pts) == 2:
                fmt = pts[1]
                if fmt == "images":
                     await msg.delete()
                     sm = await c.send_message(cid, f"⏳ Obteniendo imágenes...")
                     
                     # FIX: Respetar configuración de Doc y Grupo
                     conf = get_config(cid)
                     doc_m = conf.get('doc_mode', False)
                     grp_m = conf.get('group_mode', True)
                     
                     asyncio.create_task(process_manga_download(c, cid, mg, "images", "original", sm, doc_mode=doc_m, group_mode=grp_m))
                else:
                    kb_q = InlineKeyboardMarkup([[InlineKeyboardButton("💎 Original", callback_data=f"manga_sel|{fmt}|original")], [InlineKeyboardButton("⚡ WebP", callback_data=f"manga_sel|{fmt}|webp")], [InlineKeyboardButton("🔙 Atrás", callback_data=f"menu|main")]])
                    await msg.edit_text(f"Calidad:", reply_markup=kb_q)
            elif len(pts) == 3:
                await msg.delete()
                sm = await c.send_message(cid, f"⏳ Descargando {pts[1].upper()}...")
                asyncio.create_task(process_manga_download(c, cid, mg, pts[1], pts[2], sm))
            return


    except Exception as e:
        print(f"Callback Error: {e}")
        try: await q.answer("❌ Error en el botón.", show_alert=True)
        except: pass



# --- HELPER: RENVIADO QUEUE ---
async def process_renviado_queue(chat_id, client):
    """Espera 5s y envía lo que haya en la cola agrupado (Smart Batching + GIF fix)."""
    await asyncio.sleep(5)
    
    st = url_storage.get(chat_id)
    if not st or 'renviado_queue' not in st: return
    
    queue = st['renviado_queue']
    if not queue: return
    
    # Consumir cola
    msgs_to_send = list(queue)
    # Limpiar cola inmediatamente
    st['renviado_queue'] = []
    url_storage[chat_id] = st
    
    # --- SMART BATCHING LOGIC ---
    current_batch = []
    current_type = None # 'visual' (photo/video/gif) or 'doc'
    
    # List to track temp files for cleanup
    files_to_clean = []
    
    async def flush():
        nonlocal current_batch, current_type
        if not current_batch: return
        
        try:
            if len(current_batch) == 1:
                # Single item -> Send Individually (Group requires 2+)
                item = current_batch[0]
                # Check type based on InputMedia class or current_type
                if isinstance(item, InputMediaPhoto):
                    await client.send_photo(chat_id, item.media, caption=item.caption)
                elif isinstance(item, InputMediaVideo):
                    # Works for both file_id and local path (GIF fix)
                     await client.send_video(chat_id, item.media, caption=item.caption)
                elif isinstance(item, InputMediaDocument):
                     await client.send_document(chat_id, item.media, caption=item.caption)
            else:
                 # 2+ items -> Send Group
                 await client.send_media_group(chat_id, current_batch)
        except Exception as e:
             print(f"Error flushing batch ({len(current_batch)} items): {e}")
             # Fallback logic could go here
             pass
        current_batch = []
        current_type = None

    try:
        for m in msgs_to_send:
            # 1. Identify Media Type & Create Input Object
            m_type = None
            media_obj = None
            
            try:
                if m.sticker:
                    m_type = 'sticker'
                elif m.photo: 
                    m_type = 'visual'
                    media_obj = InputMediaPhoto(m.photo.file_id, caption=m.caption)
                elif m.video:
                    m_type = 'visual'
                    media_obj = InputMediaVideo(m.video.file_id, caption=m.caption)
                elif m.animation: 
                    m_type = 'visual'
                    # FIX: GIF (Animation) must be DOWNLOADED AND CONVERTED to be grouped as video
                    # 1. Download as temp file (preserve original nature or just .mp4 logic)
                    f_name = f"gif_r_{chat_id}_{m.id}_{int(time.time())}.mp4"
                    d_path = os.path.join(DATA_DIR, f_name)
                    
                    # Download sync
                    path = await client.download_media(m, file_name=d_path)
                    
                    if path:
                        # 2. TRANSCODE (Convert) to real H.264 MP4 to fix Headers/Container
                        # Needed 'convert_to_h264' from tools_media
                        try:
                            from tools_media import convert_to_h264
                            converted_path = await convert_to_h264(path)
                            
                            if converted_path and os.path.exists(converted_path):
                                # Success conversion
                                files_to_clean.append(path) # Delete original download later
                                path = converted_path
                            else:
                                # Conversion failed? Use original download as fallback
                                pass
                        except Exception as e:
                            print(f"GIF Convert Error: {e}")
                        
                        media_obj = InputMediaVideo(path, caption=m.caption)
                        files_to_clean.append(path)
                    else:
                        continue # Skip if failed
                        
                elif m.document:
                    m_type = 'doc'
                    media_obj = InputMediaDocument(m.document.file_id, caption=m.caption)
            except Exception as e: 
                print(f"Error prepping media: {e}")
                continue
            
            if not m_type: continue

            # 2. Check Logic
            if m_type == 'sticker':
                await flush()
                try: await m.copy(chat_id)
                except: pass
                continue
                
            # Type Mismatch
            if current_type and current_type != m_type:
                await flush()
                
            # 3. Add to Batch
            current_type = m_type
            current_batch.append(media_obj)
            
            # 4. Max Size Check (10)
            if len(current_batch) >= 10:
                await flush()

        # Final Flush
        await flush()
        
    finally:
        # Cleanup Temps
        for f in files_to_clean:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass



# --- HELPER: AUTO THUMB QUEUE ---
async def process_single_thumb_auto(client, chat_id, message):
    try:
        from tools_media import get_meta, embed_thumbnail, progreso
        from utils import download_parallel
        import random
        import subprocess
        
        # 1. Download (Turbo 32)
        # We create a message for progress tracking
        dl_msg = await message.reply("⬇️ **Iniciando...**", quote=True)
        
        v_path = os.path.join(DATA_DIR, f"thumb_auto_v_{chat_id}_{message.id}_{int(time.time())}.mp4")
        
        # Use existing 'progreso' callback
        v_path = await download_parallel(client, message, v_path, concurrency=8, progress=progreso, progress_args=(dl_msg, [0,0], "Descargando"))
        
        if not v_path:
            await dl_msg.edit("❌ Error Descarga")
            return

        # 2. Random Frame logic
        await dl_msg.edit("🎲 **Generando portada aleatoria...**")
        w, h, dur = await get_meta(v_path)
        if dur <= 0: dur = 5
        rand_time = random.uniform(0, dur)
        
        thumb_path = f"tmp_auto_thumb_{chat_id}_{message.id}.jpg"
        cmd = ["ffmpeg", "-ss", str(rand_time), "-i", v_path, "-vframes", "1", "-q:v", "2", thumb_path, "-y"]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await process.wait()
        
        if os.path.exists(thumb_path):
            # 3. Embed Thumbnail
            await dl_msg.edit("📤 **Procesando y Subiendo...**")
            out_path = await embed_thumbnail(v_path, thumb_path)
            
            if out_path:
                try:
                    # Upload with Progress
                    await client.send_video(
                        chat_id, 
                        out_path, 
                        caption=f"🎲 **Portada Aleatoria** (`{int(rand_time)}s`)", 
                        thumb=thumb_path, 
                        width=w, height=h, duration=dur,
                        progress=progreso, progress_args=(dl_msg, [0,0], "Enviando")
                    )
                except:
                     await client.send_document(chat_id, out_path, caption=f"🎲 **Portada Aleatoria** (`{int(rand_time)}s`)", thumb=thumb_path, progress=progreso, progress_args=(dl_msg, [0,0], "Enviando"))
                
                # Cleanup
                try:
                    os.remove(out_path)
                    os.remove(thumb_path)
                    os.remove(v_path)
                except: pass
                await dl_msg.delete()
                
            else:
                 await dl_msg.edit("❌ Error Embed")
        else:
             await dl_msg.edit("❌ Error Frame Extract")
             
    except Exception as e:
        print(f"Auto Thumb Error: {e}")
        try: await dl_msg.edit(f"❌ Error: {e}")
        except: pass

async def check_thumb_queue(chat_id, client):
    """
    Gestiona la cola con semáforo manual (Max 5 concurrentes).
    Se llama cada vez que se añade un video o termina uno.
    """
    st = url_storage.get(chat_id, {})
    
    # Init vars
    if 'thumb_active_count' not in st: st['thumb_active_count'] = 0
    if 'thumb_auto_queue' not in st: st['thumb_auto_queue'] = []
    
    MAX_CONCURRENT = 5
    
    # LOOP: Launch tasks while slots available and queue not empty
    while st['thumb_active_count'] < MAX_CONCURRENT and st['thumb_auto_queue']:
        # Pop next message
        next_msg = st['thumb_auto_queue'].pop(0)
        
        # Increment active
        st['thumb_active_count'] += 1
        url_storage[chat_id] = st
        
        # Launch Task
        asyncio.create_task(run_thumb_task_wrapper(client, chat_id, next_msg))
        
        # Update state ref
        st = url_storage.get(chat_id, {})

async def run_thumb_task_wrapper(client, chat_id, message):
    """Wrapper para ejecutar la tarea y luego liberar el slot."""
    try:
        await process_single_thumb_auto(client, chat_id, message)
    except Exception as e:
        print(f"Task Wrapper Error: {e}")
    finally:
        # Decrement Active
        st = url_storage.get(chat_id, {})
        if 'thumb_active_count' in st and st['thumb_active_count'] > 0:
            st['thumb_active_count'] -= 1
        url_storage[chat_id] = st
        
        # Trigger Check Queue (Recursion via Task)
        asyncio.create_task(check_thumb_queue(chat_id, client))

@app.on_message(filters.photo | filters.document | filters.video | filters.animation | filters.sticker, group=-1)
async def image_handler(c, m):
    cid = m.chat.id
    conf = get_config(cid)
    
    # --- BOT LINK MODE (Top Priority) ---
    if conf.get('bot_link_mode') and (getattr(m, 'video', None) or getattr(m, 'document', None) or getattr(m, 'animation', None) or getattr(m, 'audio', None)):
        
        # 1. Enlace Local (Pruebas PC)
        link_local = f"http://127.0.0.1:7860/dl/{cid}/{m.id}"
        
        # 2. Enlace Público (HuggingFace / VPS)
        # HuggingFace Spaces usa la variable de entorno SPACE_HOST
        hf_host = os.environ.get('SPACE_HOST')
        
        if hf_host:
            # Si estamos en HuggingFace, el puerto interno 7860 mapea directo al dominio principal con HTTPS
            link_vps = f"https://{hf_host}/dl/{cid}/{m.id}"
            vps_label = "🚀 **Para Hugging Face (Público):**"
            vps_note = "_Nota: Este enlace usa los servidores de Hugging Face y ya tiene HTTPS._"
        else:
            # Si no es HuggingFace, intentamos sacar la IP pública (VPS Tradicional)
            public_ip = "127.0.0.1"
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get('https://api.ipify.org') as resp:
                        if resp.status == 200:
                            public_ip = await resp.text()
            except Exception as e:
                print(f"Error fetching public IP: {e}")
            
            link_vps = f"http://{public_ip}:7860/dl/{cid}/{m.id}"
            vps_label = "🌍 **Para el VPS (Público):**"
            vps_note = "_Nota: El enlace público requiere que el puerto 7860 esté abierto en el firewall del VPS._"
        
        msg_text = (
            f"🔗 **Enlaces Directos Generados:**\n\n"
            f"🖥 **Para tu PC Local (Pruebas):**\n{link_local}\n\n"
            f"{vps_label}\n{link_vps}\n\n"
            f"{vps_note}"
        )
        
        await m.reply(msg_text, disable_web_page_preview=True)
        m.stop_propagation()
        return

    # --- RENVIADO TOOL LOGIC (Top Priority) ---
    if conf.get('renviado_directo'):
        # Directo: Reenviar copia limpia (esto desagrupa álbumes naturalmente)
        await m.copy(cid)
        m.stop_propagation()
        return

    if conf.get('renviado_agrupado'):
        # Agrupado: Cola de 5s
        st = url_storage.get(cid, {})
        if 'renviado_queue' not in st: st['renviado_queue'] = []
        
        st['renviado_queue'].append(m)
        
        # Cancelar tarea previa si existe (debounce)
        if 'renviado_task' in st and not st['renviado_task'].done():
            st['renviado_task'].cancel()
            
        # Nueva tarea
        st['renviado_task'] = asyncio.create_task(process_renviado_queue(cid, c))
        url_storage[cid] = st
        
        m.stop_propagation()
        return

    # --- RESEARCH MODE (HIGH PRIORITY) ---
    if conf.get('research_mode'):
        wm = await m.reply("🕵️‍♀️ **Analizando imagen...**")
        f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"research_{cid}_{int(time.time())}.jpg"))
        
        if f_p:
            await wm.delete()
            # Call Research Logic
            await run_research_logic(c, cid, text=None, image_path=f_p, msg=m)
            # Cleanup
            try: os.remove(f_p)
            except: pass
        else:
            await wm.edit("❌ Error al descargar imagen.")
        
        m.stop_propagation()
        return

    # --- CUSTOM THUMBNAIL MODE (Image Step) ---
    st = url_storage.get(cid, {})
    if conf.get('custom_thumb_mode') and st.get('custom_thumb_step') == 'wait_thumb':
        # Received Thumb
        wait = await m.reply("⬇️ **Bajando Miniatura...**")
        
        # Use parallel download with progress
        from utils import download_parallel
        from tools_media import progreso
        
        t_path = await download_parallel(c, m, os.path.join(DATA_DIR, f"custom_thumb_{cid}_{m.id}.jpg"), concurrency=8, progress=progreso, progress_args=(wait, [0,0], "Bajando Miniatura (x16)"))
        if not t_path: t_path = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"custom_thumb_{cid}_{m.id}.jpg"), progress=progreso, progress_args=(wait, [0,0], "Bajando Miniatura"))
        
        v_path = st.get('video_path')
        if t_path and v_path and os.path.exists(v_path):
             await wait.edit("⚙️ **Aplicando Miniatura...**")
             from tools_media import embed_thumbnail, get_meta
             
             out_path = await embed_thumbnail(v_path, t_path)
             if out_path:
                 await wait.edit("📤 **Enviando Resultado...**")
                 w, h, dur = await get_meta(out_path)
                 
                 try:
                     await c.send_video(
                         cid, out_path, 
                         thumb=t_path, width=w, height=h, duration=dur, 
                         caption="✏️ **Video Personalizado**",
                         progress=progreso, progress_args=(wait, [0,0], "Subiendo")
                     )
                 except:
                     await c.send_document(cid, out_path, thumb=t_path, caption="✏️ **Video Personalizado**", progress=progreso, progress_args=(wait, [0,0], "Subiendo"))
                 
                 # Cleanup
                 if os.path.exists(out_path): os.remove(out_path)
                 if os.path.exists(v_path): os.remove(v_path)
                 if os.path.exists(t_path): os.remove(t_path)
                 await wait.delete()
                 
                 # Auto Check
                 if conf.get('custom_thumb_auto', False):
                     url_storage[cid] = {'custom_thumb_step': 'wait_video'}
                     await m.reply("✅ **Listo.**\nEnvíame el siguiente **VIDEO**.")
                 else:
                     conf['custom_thumb_mode'] = False
                     from firebase_service import save_user_config_fb
                     asyncio.create_task(save_user_config_fb(cid, conf))
                     url_storage.pop(cid, None)
                     await m.reply("✅ **Proceso Finalizado.**")
             else:
                 await wait.edit("❌ Error Embed.")
        else:
             await wait.edit("❌ Error: Falta video o miniatura.")
        
        m.stop_propagation()
        return

    # --- THUMBNAIL MODE (High Priority) ---


    # 0. AI Config Upload (High Priority)
    st = url_storage.get(cid)
    # conf = get_config(cid) # Already loaded above
    # print(f"[DEBUG] Image Handler | CID: {cid} | State: {st} | Config Step: {st.get('ai_config_step') if st else 'None'}")

    # --- AUTO-CLASS MODE ---
    if st and st.get('autoclass_mode'):
        pid = st.get('persona_id', 'nsfw')
        
        # 1. Download
        dl_msg = await m.reply("🧠 **Analizando...**", quote=True)
        # Unique paths
        f_name = f"autoclass_{cid}_{int(time.time())}.jpg"
        f_path = os.path.join(DATA_DIR, f_name)
        
        try:
             path = await m.download(file_name=f_path)
        except Exception as e:
             await dl_msg.edit(f"❌ Error descarga: {e}")
             return

        if not path:
             await dl_msg.edit("❌ Error: No se pudo descargar.")
             return
             
        # 2. Get Categories
        # Default cats
        cats = ['bienvenida', 'greeting', 'admire', 'happy', 'sad', 'angry', 'surprised', 'love', 'shy']
        
        # Add Global Cats
        if pid in global_personas and 'images' in global_personas[pid]:
             cats.extend(list(global_personas[pid]['images'].keys()))
             
        # Add Local Cats
        if 'ai_images' in conf and pid in conf['ai_images']:
             cats.extend(list(conf['ai_images'][pid].keys()))
             
        # Add NSFW cats explicitely to ensure they are available even if empty
        cats.extend(['nsfw', 'sex', 'boobs', 'ass', 'cum', 'ahegao'])
        
        # Deduplicate
        cats = list(set(cats))
        
        # 3. Classify
        from ai_service import classify_image
        predicted_cat = await asyncio.get_running_loop().run_in_executor(None, lambda: classify_image(path, cats))
        
        # 4. Save
        # Get fid/type
        fid = m.photo.file_id if m.photo else (m.sticker.file_id if m.sticker else None)
        ftype = 'photo' if m.photo else 'sticker'
        
        if not fid and m.document:
             fid = m.document.file_id
             # guess type
             if 'video' in m.document.mime_type: ftype = 'video'
        
        if fid:
             # Save to Firebase/Local Config
             asyncio.create_task(save_persona_image(pid, 'default', predicted_cat, {'id': fid, 'type': ftype}))
             
             # Cache update
             if pid not in AVATAR_KEYS_CACHE: AVATAR_KEYS_CACHE[pid] = set()
             AVATAR_KEYS_CACHE[pid].add(predicted_cat)
             
             # Translate Category
             cat_display = TRANS.get(predicted_cat, predicted_cat.replace('_', ' ').title())
             
             # 5. Reply
             kb_stop = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Detener / Cancelar", callback_data="cancel_all")]])
             await dl_msg.edit(
                 f"✅ **Imagen Guardada**\n"
                 f"👤 **Cuerpo:** `{pid}`\n"
                 f"📂 **Categoría:** `{cat_display}`",
                 reply_markup=kb_stop
             )
        else:
             await dl_msg.edit("❌ No pude obtener ID del archivo.")
             
        # 4. Clean up (Job Dir)
        try:
            import shutil
            job_dir = os.path.dirname(f_path)
            if 'job_' in os.path.basename(job_dir) and os.path.exists(job_dir):
                shutil.rmtree(job_dir, ignore_errors=True)
            elif os.path.exists(f_path):
                os.remove(f_path)
        except Exception as e:
            print(f"Autoclass cleanup error: {e}")
        
        m.stop_propagation()
        return

    if st and st.get('ai_config_step') == 'wait_image':
        cat = st.get('category')
        pid = st.get('persona_id', 'nsfw')
        
        # Get File ID & Type
        fid = None
        ftype = 'photo'
        
        if m.photo: 
            fid = m.photo.file_id
            ftype = 'photo'
        elif m.sticker:
            fid = m.sticker.file_id
            ftype = 'sticker'
        elif m.animation:
            fid = m.animation.file_id
            ftype = 'animation'
        elif m.video:
            fid = m.video.file_id
            ftype = 'video'
        elif m.document:
            # Check mime type
            mime = m.document.mime_type
            fid = m.document.file_id
            if mime and 'image' in mime: ftype = 'photo'
            elif mime and 'video' in mime: ftype = 'video'
            else: ftype = 'document' # Fallback
        
        if fid:
            # NEW CLOUD BODY LOGIC
            # Save to 'avatars' collection via save_persona_image
            # Default outfit for now: 'default'
            
            # Increment session count
            st['count'] = st.get('count', 0) + 1
            url_storage[cid] = st
            
            # Fire and forget save
            # We save the WHOLE item {'id': ..., 'type': ...} so we know how to send it back
            asyncio.create_task(save_persona_image(pid, 'default', cat, {'id': fid, 'type': ftype}))
            
            # Update Cache Immediate
            if pid not in AVATAR_KEYS_CACHE: AVATAR_KEYS_CACHE[pid] = set()
            AVATAR_KEYS_CACHE[pid].add(cat)
            
            # Reply confirmation
            gid = st.get('gid', 'social') # get GID for back button
            
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Terminado", callback_data=f"ai_conf|group|{gid}|{pid}")]])
            
            await m.reply(f"✅ **Foto #{st['count']} guardada** en `{cat}`.\nSigue enviando...", reply_markup=kb)
            m.stop_propagation()
            return

    # 0.5 AI Config Subset Input
    if st and st.get('ai_config_step') == 'wait_subset':
        cat = st.get('category')
        pid = st.get('persona_id', 'nsfw')
        txt = m.text.strip()
        
        # Cancel logic
        if txt.lower() == "/cancel":
             url_storage.pop(cid, None)
             await m.reply("❌ Cancelado.")
             return
             
        try:
             # Parse numbers
             nums = [int(x) for x in txt.split()]
             if not nums: raise ValueError("Empty")
             
             # Validate against real count
             ai_imgs = conf.get('ai_images', {}).get(pid, {}).get(cat, {'images': []})
             count = len(ai_imgs.get('images', []))
             
             # Convert to 0-indexed indices
             final_subset = []
             for n in nums:
                 if 1 <= n <= count:
                     final_subset.append(n-1) # 0-indexed
             
             if not final_subset:
                 await m.reply("⚠️ Ningún número válido. Usa índices del 1 al " + str(count))
                 return
                 
             # Save
             if 'ai_images' not in conf: conf['ai_images'] = {}
             if pid not in conf['ai_images']: conf['ai_images'][pid] = {}
             if cat not in conf['ai_images'][pid]: conf['ai_images'][pid][cat] = {}
             
             conf['ai_images'][pid][cat]['mode'] = 'subset'
             conf['ai_images'][pid][cat]['subset'] = final_subset
             
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             
             # Success msg with Menu
             # Success msg with Menu
             # from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton (GLOBAL ALREADY)
             kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver a Configurar", callback_data=f"ai_conf|cat|{cat}|{pid}")]])
             await m.reply(f"✅ **Modo Personalizado Activado**\nUsando {len(final_subset)} imágenes seleccionadas.", reply_markup=kb)
             
             url_storage.pop(cid, None)
             return
             
        except Exception as e:
             await m.reply("❌ Error leyendo números. Asegúrate de enviarlos separados por espacio (Ej: `1 3 5`).")
             return

    # 1. Sticker Mode
    if conf.get('sticker_mode'):
        wm = await m.reply("⬇️ **Bajando Imagen para Sticker...**")
        f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"sticker_{cid}.jpg"))
        if f_p:
            await wm.delete()
            await run_sticker_logic(c, cid, f_p)
        else:
            await wm.edit("❌ Error al descargar imagen.")
        m.stop_propagation()
        return

    # 2. SauceNAO Mode
    if conf.get('saucenao_mode'):
        wm = await m.reply("⬇️ **Bajando para SauceNAO...**")
        f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"sauce_{cid}.jpg"))
        if f_p:
            await wm.delete()
            await run_saucenao_logic(c, cid, f_p, None) # msg_to_edit=None, function creates one
        else:
            await wm.edit("❌ Error al descargar imagen.")
        m.stop_propagation()
        return

    m.continue_propagation()


async def run_mp3_logic(c, cid, f_path, msg_to_edit=None):
    from tools_media import extract_audio, get_audio_dur
    
    if msg_to_edit: await msg_to_edit.edit("🎵 **Extrayendo Audio MP3...**")
    else: msg_to_edit = await c.send_message(cid, "🎵 **Extrayendo Audio MP3...**")
    
    mp3_path = await extract_audio(f_path)
    if mp3_path:
        await msg_to_edit.edit("📤 **Subiendo Audio...**")
        dur = await get_audio_dur(mp3_path)
        try:
            await c.send_audio(cid, mp3_path, title=os.path.basename(mp3_path), duration=dur, caption="🎵 **Audio Extraído**")
            await msg_to_edit.delete()
        except Exception as e:
            await msg_to_edit.edit(f"❌ Error al subir: {e}")
        
        # Cleanup
        # Cleanup (Job Dir)
        import shutil
        job_dir = os.path.dirname(f_path)
        if 'job_' in os.path.basename(job_dir) and os.path.exists(job_dir):
             shutil.rmtree(job_dir, ignore_errors=True)
        elif os.path.exists(mp3_path): os.remove(mp3_path)
    else:
        await msg_to_edit.edit("❌ Error: No se pudo extraer el audio (quizás no tiene pista de audio).")
    
    # Smart Cleanup
    import shutil
    job_dir = os.path.dirname(f_path)
    if 'job_' in os.path.basename(job_dir) and os.path.exists(job_dir):
        shutil.rmtree(job_dir, ignore_errors=True)
    elif os.path.exists(f_path): os.remove(f_path)
    
    # Auto Disable
    conf = get_config(cid)
    conf['mp3_mode'] = False
    from firebase_service import save_user_config_fb
    asyncio.create_task(save_user_config_fb(cid, conf))
    try: await msg_to_edit.edit(msg_to_edit.text + "\n🛑 Se desactivó el modo/herramienta: Audio MP3")
    except: pass

# --- AUTO JOIN TASKS (Debounce) ---
AUTO_JOIN_TASKS = {}

async def run_join_party_logic(client, chat_id, msg_to_edit=None):
    """
    Lógica compartida para unir clips. 
    Se llama desde el botón 'Unir ahora' O automáticamente tras X segundos.
    """
    st = url_storage.get(chat_id, {})
    clips = st.get('join_clips', [])
    
    # Si no hay mensaje para editar, enviamos uno nuevo o usamos el último clip
    if not msg_to_edit:
        if clips:
             last_m = clips[-1]
             msg_to_edit = await client.send_message(chat_id, "⏳ **Iniciando Unión Automática...**")
        else:
             return

    if not clips:
        try: await msg_to_edit.edit("❌ No hay clips registrados para unir.")
        except: pass
        return

    try:
        if len(clips) < 2:
            try: await msg_to_edit.edit("⚠️ Se necesitan al menos 2 clips para unir.\nEnvíame más.")
            except: pass
            return

        await msg_to_edit.edit(f"🔗 **Uniendo {len(clips)} clips...**\n⬇️ Bajando videos...")
        
        from utils import download_parallel, merge_videos_ffmpeg
        from tools_media import get_meta, get_thumb, progreso
        
        downloaded_files = []
        
        # 1. Crear carpeta de trabajo única para el Join (Nested)
        tool_folder = os.path.join(DATA_DIR, "join_temp")
        if not os.path.exists(tool_folder): os.makedirs(tool_folder)

        job_dir = os.path.join(tool_folder, f"job_join_{chat_id}_{time.time_ns()}_{random.randint(1000, 9999)}")
        if not os.path.exists(job_dir): os.makedirs(job_dir)
        
        # 1. Descargar todos
        for i, m_clip in enumerate(clips):
            await msg_to_edit.edit(f"⬇️ **Bajando clip {i+1}/{len(clips)}...**")
            
            # Nombre temporal seguro
            ext = ".mp4"
            if m_clip.video and m_clip.video.file_name: _, ext = os.path.splitext(m_clip.video.file_name)
            elif m_clip.document and m_clip.document.file_name: _, ext = os.path.splitext(m_clip.document.file_name)
            
            fname = os.path.join(job_dir, f"clip_{i}_{m_clip.id}{ext}")
            
            # Descarga
            f_p = await download_parallel(client, m_clip, fname, concurrency=4)
            if not f_p: f_p = await client.download_media(m_clip, file_name=fname)
            
            if f_p and os.path.exists(f_p):
                downloaded_files.append(f_p)
            else:
                await msg_to_edit.edit(f"❌ Error bajando clip {i+1}. Abortando.")
                # Cleanup parcial
                for f in downloaded_files: 
                    if os.path.exists(f): os.remove(f)
                return
        
        # 2. Unir
        await msg_to_edit.edit("🔗 **Procesando unión (FFmpeg)...**")
        output_join = os.path.join(job_dir, f"merged_{chat_id}_{int(time.time())}.mp4")
        
        final_path = await asyncio.get_running_loop().run_in_executor(None, lambda: merge_videos_ffmpeg(downloaded_files, output_join))
        
        # 3. Enviar
        if final_path and os.path.exists(final_path):
            await msg_to_edit.edit("📤 **Enviando video unido...**")
            w, h, dur = await get_meta(final_path)
            t_path = await get_thumb(final_path, chat_id, int(time.time()))
            
            try:
                await client.send_video(
                    chat_id, final_path,
                    width=w, height=h, duration=dur, thumb=t_path,
                    caption=f"🔗 **Party Unida ({len(clips)} clips)**",
                    progress=progreso, progress_args=(msg_to_edit, [0,0], "Enviando")
                )
            except Exception as e:
                    await client.send_document(chat_id, final_path, caption=f"🔗 Party Unida ({len(clips)} clips)")

            if t_path and os.path.exists(t_path): os.remove(t_path)
            # os.remove(final_path) # No needed, rmtree handles it
            
            # Reset
            url_storage.pop(chat_id, None)
            AUTO_JOIN_TASKS.pop(chat_id, None)
            
            try: await msg_to_edit.delete()
            except: pass
            
            await client.send_message(chat_id, "✅ **Unión Completada.**")
            
            # Auto-OFF
            conf = get_config(chat_id)
            conf['join_party_mode'] = False
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            await client.send_message(chat_id, "🛑 Se desactivó el modo/herramienta: Unir Party")
            
        else:
                await msg_to_edit.edit("❌ Error al unir los videos.")
                
    except Exception as e:
        print(f"Join Error: {e}")
        try: await msg_to_edit.edit(f"❌ Error crítico: {e}")
        except: pass
    
    # Cleanup Job Dir (All files)
    import shutil
    try: shutil.rmtree(job_dir, ignore_errors=True)
    except: pass

async def party_worker(client, chat_id, message_vid, mode_w, val_w, wait_msg, context_config=None):
    # Check Queue Status
    if SEM_PARTY.locked():
        try:
            await wait_msg.edit(f"⏳ **En Cola (Posición {len(SEM_PARTY._waiters) if hasattr(SEM_PARTY, '_waiters') else '?'})...**\nEsperando turno.")
        except: pass

    async with SEM_PARTY:
        try:
            await wait_msg.edit(f"⬇️ **Bajando video para {mode_w}={val_w}...**\n(Descarga Diferida)")
            
            from utils import download_parallel
            from tools_media import progreso
            
            # Determinar extensión
            ext = ".mp4"
            if message_vid.audio: ext = ".mp3"
            if message_vid.document and message_vid.document.file_name: _, ext = os.path.splitext(message_vid.document.file_name)
            elif message_vid.video and message_vid.video.file_name: _, ext = os.path.splitext(message_vid.video.file_name)
            elif message_vid.audio and message_vid.audio.file_name: _, ext = os.path.splitext(message_vid.audio.file_name)
            
            # Create Job Directory (Nested for Tool Isolation)
            # Structure: downloads/party_temp/job_{id}_{ts}/
            tool_folder = os.path.join(DATA_DIR, "party_temp")
            if not os.path.exists(tool_folder): os.makedirs(tool_folder)
            
            job_dir = os.path.join(tool_folder, f"job_{chat_id}_{time.time_ns()}_{random.randint(1000, 9999)}")
            if not os.path.exists(job_dir): os.makedirs(job_dir)
            
            f_p = await download_parallel(client, message_vid, os.path.join(job_dir, f"party_{chat_id}_{message_vid.id}{ext}"), concurrency=8, progress=progreso, progress_args=(wait_msg, [0,0], "Descargando"))
            if not f_p: f_p = await client.download_media(message_vid, file_name=os.path.join(job_dir, f"party_{chat_id}_{message_vid.id}{ext}"))
            
            if f_p and os.path.exists(f_p):
                # Proceed with Logic
                await run_party_logic(client, chat_id, f_p, mode_w, val_w, wait_msg, original_msg=message_vid, context_config=context_config)
            else:
                await wait_msg.edit("❌ Error en descarga diferida.")
        except Exception as e:
            print(f"Party Worker Error: {e}")
            try: await wait_msg.edit(f"❌ Error interno: {e}")
            except: pass

@app.on_message(filters.video | filters.document | filters.audio | filters.animation)
async def party_video_handler(c, m):
    cid = m.chat.id
    conf = get_config(cid)

    # --- NANO BANANA EXCLUSION CHECK (Images as Documents) ---
    # If Nano Banana is active, it handles its own images (even files).
    # Party Mode shouldn't steal them.
    if conf.get('ai_model_mode') == 'nano_banana':
        is_pos_image = False
        if m.photo: is_pos_image = True
        elif m.document and m.document.mime_type and m.document.mime_type.startswith('image/'): is_pos_image = True
        elif m.document and m.document.file_name:
             _, ext = os.path.splitext(m.document.file_name)
             if ext.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.heic']:
                 is_pos_image = True
        
        if is_pos_image:
            # Let ai_chat_handler handle it
            return await m.continue_propagation()
    
    # --- LOGICA: UNIR PARTY (COLECCIÓN) ---
    # --- LOGICA: UNIR PARTY (COLECCIÓN) ---
    if conf.get('join_party_mode'):
        st = url_storage.get(cid, {})
        if 'join_clips' not in st: st['join_clips'] = []
        
        # Registrar clip
        st['join_clips'].append(m) 
        
        # Borrar mensaje de confirmación anterior si existe
        last_msg_id = st.get('join_confirm_msg_id')
        if last_msg_id:
            try:
                await c.delete_messages(cid, last_msg_id)
            except: pass
            
        url_storage[cid] = st # Guardar clips
        
        count = len(st['join_clips'])
        
        # Generar nuevo mensaje de confirmación
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Sí, Unir ahora", callback_data="party_join_now")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="menu|party_init")]
        ])
        
        if count == 1:
            sent_m = await m.reply("✅ **Clip registrado (1).**\nEnvíame otro clip...", quote=True)
            st['join_confirm_msg_id'] = sent_m.id
        else:
            sent_m = await m.reply(
                f"📹 **He recibido {count} clips.**\n¿Comienzo a descargarlos y unirlos?", 
                reply_markup=kb,
                quote=True
            )
            st['join_confirm_msg_id'] = sent_m.id
            
        url_storage[cid] = st
        return

    # --- SMART CUT LOGIC (Top Priority within Tools) ---
    if conf.get('smart_cut_mode'):
        if SEM_SMART_CUT.locked():
             wait = await m.reply("⏳ **En Cola de Procesamiento (Smart Cut)...**\n_Esperando turno_")
        else:
             wait = await m.reply("🧠 **Analizando Intro...**\n⬇️ Bajando video...")

        async with SEM_SMART_CUT:
             if wait.text.startswith("⏳"): await wait.edit("🧠 **Analizando Intro...**\n⬇️ Bajando video...")
             
             from utils import download_parallel
             from tools_media import smart_cut_video, get_meta, get_thumb
             from tools_media import progreso as prog_callback
             
             f_p = await download_parallel(c, m, os.path.join(DATA_DIR, f"smart_{cid}_{m.id}.mp4"), progress=prog_callback, progress_args=(wait, [0,0], "Descargando"))
             if not f_p: f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"smart_{cid}_{m.id}.mp4"))
             
             if f_p and os.path.exists(f_p):
                 res_tuple = await smart_cut_video(f_p)
                 
                 if res_tuple:
                     out_path, cut_time = res_tuple
                     await wait.edit(f"✂️ **Intro Detectada ({cut_time}s)**\nEnviando video cortado...")
                     
                     w, h, dur = await get_meta(out_path)
                     t_path = await get_thumb(out_path, cid, int(time.time()))
                     
                     try:
                         await c.send_video(
                             cid, out_path, 
                             width=w, height=h, duration=dur, thumb=t_path,
                             caption=f"🧠 **Smart Cut** (Intro: {cut_time}s)",
                             progress=prog_callback, progress_args=(wait, [0,0], "Enviando")
                         )
                     except:
                         await c.send_document(cid, out_path, caption=f"🧠 **Smart Cut** (Intro: {cut_time}s)")
                     
                     if t_path and os.path.exists(t_path): os.remove(t_path)
                     if os.path.exists(out_path): os.remove(out_path)
                 else:
                    await wait.edit("⚠️ **No se detectó intro.**\nEnviando original (Directo)...")
                    
                    # Try to use file_id from message to avoid re-upload
                    sent_ok = False
                    try:
                        target_file_id = None
                        if m.video: target_file_id = m.video.file_id
                        elif m.document: target_file_id = m.document.file_id
                        elif m.animation: target_file_id = m.animation.file_id

                        if target_file_id:
                            await c.send_video(
                                cid, target_file_id, 
                                caption="video original sin cambios (smart cut no encontrado)"
                            )
                            sent_ok = True
                    except Exception as e:
                        print(f"Smart Cut Direct Send Error: {e}")
                    
                    if not sent_ok:
                        w, h, dur = await get_meta(f_p)
                        t_path = await get_thumb(f_p, cid, int(time.time()))
                        
                        try:
                            await c.send_video(
                                cid, f_p, 
                                width=w, height=h, duration=dur, thumb=t_path,
                                caption="video original sin cambios (smart cut no encontrado)",
                                progress=prog_callback, progress_args=(wait, [0,0], "Enviando")
                            )
                        except:
                            await c.send_document(cid, f_p, caption="video original sin cambios (smart cut no encontrado)")
                        
                        if t_path and os.path.exists(t_path): os.remove(t_path)
                 
                 if os.path.exists(f_p): os.remove(f_p)
             else:
                 await wait.edit("❌ Error descragando video.")
             
             # Auto Logic
             if not conf.get('smart_cut_auto_mode', False):
                 conf['smart_cut_mode'] = False
                 from firebase_service import save_user_config_fb
                 asyncio.create_task(save_user_config_fb(cid, conf))
                 try: await wait.delete()
                 except: pass
                 await c.send_message(cid, "✅ **Proceso Finalizado.**\n🛑 Se desactivó el modo/herramienta: Smart Cut")
             else:
                 try: await wait.delete()
                 except: pass

        return

    if not conf.get('party_mode') and not conf.get('auto_party') and not conf.get('join_party_mode') and not conf.get('extract_mode') and not conf.get('gif_mode') and not conf.get('mp3_mode') and not conf.get('cut_init_mode') and not conf.get('cut_auto_mode') and not conf.get('convert_qh_mode') and not conf.get('convert_h264_mode') and not conf.get('resize_mode') and not conf.get('resize_auto_mode') and not conf.get('custom_thumb_mode') and not conf.get('fusion_mode') and not conf.get('fusion_auto_mode') and not conf.get('fusion_auto_audio_capture'):
        return m.continue_propagation()
    
    st = url_storage.get(cid, {})

    # --- FUSION AUTO MODE (Wait Audio Step) ---
    if conf.get('fusion_auto_audio_capture', False):
        wait = await m.reply("⬇️ **Guardando referencia del Audio Predeterminado...**")
        
        file_id = None
        if m.audio: file_id = m.audio.file_id
        elif m.voice: file_id = m.voice.file_id
        elif m.document: file_id = m.document.file_id
        elif m.video: file_id = m.video.file_id
        
        if not file_id:
            await wait.edit("❌ Por favor envía un archivo válido (Audio, Nota de voz, Video o Documento).")
            return
            
        conf['fusion_default_audio'] = file_id
        conf['fusion_auto_audio_capture'] = False # Auto OFF after capturing
        
        from firebase_service import save_user_config_fb
        import asyncio
        asyncio.create_task(save_user_config_fb(cid, conf))
        
        from tools_fusion import show_fusion_auto_menu
        await wait.edit("✅ **Audio Predeterminado Guardado correctamente (ID de Telegram vinculado).**")
        await show_fusion_auto_menu(c, cid, conf)
        return

    # --- FUSION AUTO MODE FLOW ---
    
    # Global semaphore to prevent FFmpeg CPU/RAM death on mass uploads
    if 'fusion_auto_sem' not in globals():
        global fusion_auto_sem
        import asyncio
        fusion_auto_sem = asyncio.Semaphore(5)

    if conf.get('fusion_auto_mode', False):
        from tools_fusion import get_fusion_session, show_fusion_panel
        
        if conf.get('fusion_default_audio'):
            if m.video or m.document or m.animation:
                wait = await m.reply("🤖 **Fusión Automática:** En cola... ⏳")
                
                async with fusion_auto_sem:
                    await wait.edit("🤖 **Fusión Automática:** Inicializando...")
                    
                    file_id = conf['fusion_default_audio']
                    
                    # Create a reliable unique hash for this specific file_id so it downloads the new one if changed
                    import hashlib
                    clean_id = hashlib.md5(file_id.encode()).hexdigest()[:15]
                    a_path = os.path.join(DATA_DIR, f"fus_auto_a_{cid}_{clean_id}.mp3")
                    
                    if not os.path.exists(a_path):
                        await wait.edit("🤖 **Fusión Automática:** Recuperando audio predeterminado de la nube...")
                        try:
                            a_path = await c.download_media(file_id, file_name=a_path)
                        except Exception as e:
                            await wait.edit("❌ El audio predeterminado ya no es accesible. Por favor guárdalo de nuevo.")
                            return
                            
                    if not a_path or not os.path.exists(a_path):
                        await wait.edit("❌ Fallo obteniendo el audio predeterminado.")
                        return
                    
                    await wait.edit("🤖 **Fusión Automática:** Descargando video objetivo...")
                    from utils import download_parallel
                    from tools_media import progreso
                    
                    filename = getattr(m.video, 'file_name', None) or getattr(m.document, 'file_name', None) or getattr(m.animation, 'file_name', None) or ".mp4"
                    _, ext = os.path.splitext(filename)
                    ts = int(time.time())
                    # Ensure unique filename by appending m.id (Message ID) for concurrent batches
                    v_path = os.path.join(DATA_DIR, f"fus_auto_v_{ts}_{m.id}_{cid}{ext}")
                    
                    f_p = await download_parallel(c, m, v_path, concurrency=16, progress=progreso, progress_args=(wait, [0,0], "Bajando Video"))
                    if not f_p: f_p = await c.download_media(m, file_name=v_path)
                    
                    if not f_p:
                        await wait.edit("❌ Error bajando video.")
                        return
                    
                    await wait.edit("⚙️ **Fusión Automática:** Mezclando y renderizando...")
                    
                    sess = await get_fusion_session(cid)
                    out_path = os.path.join(DATA_DIR, f"fusion_auto_final_{ts}_{m.id}_{cid}.mp4")
                    
                    from tools_fusion import process_fusion
                    ok, err = await process_fusion(
                        f_p, a_path, out_path, 
                        keep_video_audio=conf.get('fusion_auto_cfg_v', True), 
                        keep_added_audio=conf.get('fusion_auto_cfg_a', True), 
                        safe_mode=sess.get('safe_mode', False),
                        vol_v=conf.get('fusion_auto_vol_v', 100),
                        vol_a=conf.get('fusion_auto_vol_a', 100)
                    )
                    
                    if ok:
                        await wait.edit("📤 **Fusión Automática:** Subiendo...")
                        from tools_media import get_meta, get_thumb
                        w, h, dur = await get_meta(out_path)
                        thumb = await get_thumb(out_path, cid, ts)
                    
                    
                        try:
                            await c.send_video(
                                cid, out_path,
                                caption="🤖 **Fusión Automática Terminada**",
                                width=w, height=h, duration=dur, thumb=thumb,
                                progress=progreso, progress_args=(wait, [0,0], "Enviando")
                            )
                        except Exception as e:
                            try: await c.send_document(cid, out_path, caption="🤖 **Fusión Automática** (Fallback Doc)", thumb=thumb)
                            except: pass
                            
                        if thumb and os.path.exists(thumb): os.remove(thumb)
                        if os.path.exists(out_path): os.remove(out_path)
                        await wait.delete()
                    else:
                        await wait.edit(f"❌ Error Fusión Automática:\n`{err}`")
                    
                    if os.path.exists(f_p): os.remove(f_p)
                    return
            else:
                return # Ignore messages that aren't videos in auto mode
                
        else:
            await m.reply("⚠️ El Modo Automático está activado, pero falta el Audio Predeterminado. Ve al submenú para establecerlo.")
            return

    # --- FUSION MANUAL MODE FLOW ---
    if conf.get('fusion_mode', False):
        from tools_fusion import get_fusion_session, show_fusion_panel
        sess = await get_fusion_session(cid)
        
        if not sess['video']:
            # STEP 1: Register Video Base
            sess['video'] = m
            sess['step'] = 1
            await m.reply("🎥 **Video Registrado (1).**\n\nAhora envíame el **AUDIO** (o video).")
            return
            
        else:
            # STEP 2: Register Audio
            sess['audio'] = m
            sess['step'] = 2
            
            # Show Panel
            await show_fusion_panel(c, cid)
            return



    # --- CUSTOM THUMB MODE (Video Step + Catalog Gen) ---
    if conf.get('custom_thumb_mode', False) and st.get('custom_thumb_step') == 'wait_video':
        wait = await m.reply("⬇️ **Bajando Video Base...**")
        
        # Download with Progress
        from utils import download_parallel
        from tools_media import progreso
        
        f_p = await download_parallel(c, m, os.path.join(DATA_DIR, f"custom_base_{cid}_{m.id}.mp4"), concurrency=16, progress=progreso, progress_args=(wait, [0,0], "Bajando Video (x16)"))
        if not f_p: f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"custom_base_{cid}_{m.id}.mp4"), progress=progreso, progress_args=(wait, [0,0], "Bajando Video"))
        
        if f_p:
            await wait.edit("🎞 **Generando Catálogo de Miniaturas...**\n(Cada 5s)")
            from tools_media import generate_catalog_thumbs
            
            thumbs = await generate_catalog_thumbs(f_p, interval=5)
            
            url_storage[cid] = {
                'custom_thumb_step': 'wait_thumb', 
                'video_path': f_p,
                'custom_thumbs_list': thumbs
            }
            
            if thumbs:
                # Ask for custom image FIRST, with option for Catalog
                kb = InlineKeyboardMarkup([
                     [InlineKeyboardButton("🎞 Ver Catálogo Automático", callback_data="custom|show_catalog")],
                     [InlineKeyboardButton("❌ Cancelar", callback_data="menu|tools")]
                 ])
                
                await wait.delete()
                await c.send_message(cid, "✅ **Video Recibido.**\n\n1️⃣ Envíame una **IMAGEN** para usar de portada.\n2️⃣ O abre el cátalogo de frames del video.", reply_markup=kb)
            else:
                await wait.edit("⚠️ No pude generar miniaturas del video.\n**Envía una imagen manual** para usarla.")
                
        else:
            await wait.edit("❌ Error descarga video.")
        return

    # --- CONVERTIDOR QH FLOW (QUEUE + TURBO x32) ---
    if conf.get('convert_qh_mode', False):
        # 1. Detectar si es Imagen (para no convertirla a video)
        is_image = False
        original_ext = ""
        
        if m.photo:
            is_image = True
            original_ext = ".jpg"
        elif m.document:
            if m.document.mime_type and m.document.mime_type.startswith("image/"):
                is_image = True
            if m.document.file_name:
                _, original_ext = os.path.splitext(m.document.file_name)
                if original_ext.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.bmp']:
                    is_image = True
        
        # Si es imagen, procesamos como imagen (pass-through o conversión simple si hiciera falta)
        if is_image:
            wait = await m.reply("⬇️ **Bajando Imagen...**")
            # Descargar con nombre original/extensión correcta
            # Usamos download_media de pyrogram directo para imágenes, es rápido.
            dl_path = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"qh_img_{cid}_{m.id}{original_ext}"))
            
            if dl_path and os.path.exists(dl_path):
                await wait.edit("📤 **Enviando Imagen...**")
                try:
                    # Enviar como FOTO (Normal) como pidió el usuario
                    await c.send_photo(cid, dl_path, caption="📦 **Imagen (QH)**")
                except Exception as e:
                    # Fallback a documento solo si falla
                    await c.send_document(cid, dl_path, caption="📦 **Imagen (QH)**")
                
                os.remove(dl_path)
                await wait.delete()
            else:
                 await wait.edit("❌ Error descargando imagen.")
            return

        # 2. Si NO es imagen (Video/Audio), flujo normal de Video
        if SEM_CONVERT_QH.locked():
             wait = await m.reply("⏳ **En Cola de Procesamiento...**\n_Esperando turno (Máx 5 simultáneos)_")
        else:
             wait = await m.reply("⬇️ **Bajando TURBO (x32)...**\n🚀 Convertidor QH Activo")

        async with SEM_CONVERT_QH:
             if wait.text.startswith("⏳"): await wait.edit("⬇️ **Bajando TURBO (x32)...**\n🚀 Convertidor QH Activo")
             
             from utils import download_parallel
             from tools_media import progreso
             
             # Force MP4 for Videos
             f_p = await download_parallel(c, m, os.path.join(DATA_DIR, f"conv_qh_{cid}_{m.id}.mp4"), concurrency=32, progress=progreso, progress_args=(wait, [0,0], "Descargando"))
             
             if not f_p:
                 # Fallback
                 f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"conv_qh_{cid}_{m.id}.mp4"))

             if f_p:
                 await wait.edit("📤 **Enviando Video Convertido...**")
                 from tools_media import get_meta, get_thumb
                 w, h, dur = await get_meta(f_p)
                 t_path = await get_thumb(f_p, cid, int(time.time()))
                 
                 try:
                     await c.send_video(cid, f_p, width=w, height=h, duration=dur, thumb=t_path, caption=f"📦 **Convertido QH**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                 except Exception as e:
                     await c.send_document(cid, f_p, caption=f"📦 **Convertido QH** (Doc Fallback)", progress=progreso, progress_args=(wait, [0,0], "Enviando"))

                 if t_path and os.path.exists(t_path): os.remove(t_path)
                 if os.path.exists(f_p): os.remove(f_p)
                 await wait.delete()
             else:
                 await wait.edit("❌ Error en descarga.")
        return

    # --- DIMENSIONADOR FLOW ---
    if conf.get('resize_mode'):
        target = conf.get('resize_target', '9:16')
        wait = await m.reply(f"📐 **Dimensionador Activo**\nTarget: `{target}`\n⬇️ Bajando video...")
        
        from utils import download_parallel
        from tools_media import resize_video, progreso, get_meta, get_thumb
        
        # Download
        f_p = await download_parallel(c, m, os.path.join(DATA_DIR, f"resize_{cid}_{m.id}.mp4"), concurrency=32, progress=progreso, progress_args=(wait, [0,0], "Descargando"))
        if not f_p:
            f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"resize_{cid}_{m.id}.mp4"))
            
        if f_p and os.path.exists(f_p):
            await wait.edit(f"⚙️ **Redimensionando a {target}...**\n(Zoom + Crop al centro)")
            
            # Process
            out_path = await resize_video(f_p, target)
            
            if out_path and os.path.exists(out_path):
                await wait.edit("📤 **Enviando Video Redimensionado...**")
                w, h, dur = await get_meta(out_path)
                t_path = await get_thumb(out_path, cid, int(time.time()))
                
                try:
                    await c.send_video(cid, out_path, width=w, height=h, duration=dur, thumb=t_path, caption=f"📐 **Redimensionado a {target}**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                except:
                    await c.send_document(cid, out_path, caption=f"📐 **Redimensionado a {target}**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                
                # Cleanup
                if t_path and os.path.exists(t_path): os.remove(t_path)
                os.remove(out_path)
                # Auto-OFF
                conf['resize_mode'] = False
                from firebase_service import save_user_config_fb
                asyncio.create_task(save_user_config_fb(cid, conf))
                await c.send_message(cid, "✅ **Proceso Finalizado.**\n🛑 Se desactivó el modo/herramienta: Dimensionador")
            else:
                 await wait.edit("❌ Error al procesar el video.")
            
            if os.path.exists(f_p): os.remove(f_p)
            try: await wait.delete()
            except: pass
        else:
             await wait.edit("❌ Error descragando video.")
        return

    # --- CONVERTIDOR MP4 H264 FLOW (QUEUE + TURBO x32 + FFMPEG) ---
    if conf.get('convert_h264_mode', False):
        if SEM_CONVERT_H264.locked():
             wait = await m.reply("⏳ **En Cola de Procesamiento...**\n_Esperando turno (Máx 5 simultáneos)_")
        else:
             wait = await m.reply("⬇️ **Bajando TURBO (x32)...**\n🚀 Convertidor H.264 Activo")

        async with SEM_CONVERT_H264:
             if wait.text.startswith("⏳"): await wait.edit("⬇️ **Bajando TURBO (x32)...**\n🚀 Convertidor H.264 Activo")
             
             from utils import download_parallel
             from tools_media import progreso, convert_to_h264, get_meta, get_thumb
             
             # Descarga en modo documento (para aceptar MKV, TS, AVI crudos)
             original_path = os.path.join(DATA_DIR, f"tmp_h264_{cid}_{m.id}") # Sin extension para que download_parallel o fallback decidan o usar extension original
             
             # Intentamos adivinar extension del nombre de archivo si es documento
             ext = ""
             if m.document and m.document.file_name:
                 _, ext = os.path.splitext(m.document.file_name)
             elif m.video and m.video.file_name:
                  _, ext = os.path.splitext(m.video.file_name)
             elif m.animation:
                  # Treat Animation/GIF as MP4 source for ffmpeg
                  ext = ".mp4" 
             
             if not ext: ext = ".mp4" # Default
             original_path += ext

             f_p = await download_parallel(c, m, original_path, concurrency=32, progress=progreso, progress_args=(wait, [0,0], "Descargando"))
             
             if not f_p:
                 f_p = await c.download_media(m, file_name=original_path)

             if f_p and os.path.exists(f_p):
                 await wait.edit("⚙️ **Convirtiendo a MP4 H.264...**\nEsto puede tardar según el peso.")
                 
                 # Conversion FFMPEG
                 h264_path = await convert_to_h264(f_p)
                 
                 if h264_path and os.path.exists(h264_path):
                     await wait.edit("📤 **Enviando Video H.264...**")
                     w, h, dur = await get_meta(h264_path)
                     t_path = await get_thumb(h264_path, cid, int(time.time()))
                     
                     try:
                         # Send as Video
                         await c.send_video(cid, h264_path, width=w, height=h, duration=dur, thumb=t_path, caption=f"🎞 **Convertido H.264**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                     except Exception as e:
                         await c.send_document(cid, h264_path, caption=f"🎞 **Convertido H.264** (Doc Fallback)", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                     
                     if t_path and os.path.exists(t_path): os.remove(t_path)
                     os.remove(h264_path)
                 else:
                     await wait.edit("❌ **Error en la conversión.**\nQuizás el archivo está dañado.")
                 
                 if os.path.exists(f_p): os.remove(f_p)
                 try: await wait.delete()
                 except: pass
             else:
                 await wait.edit("❌ Error en descarga.")
        return

    # --- AUTO RESIZE SPECIFIC FLOW ---
    if conf.get('resize_auto_mode', False) and 'party_pending' not in st:
        # Check Semaphore Status (Reusing SEM_AUTO_CORTE for shared resource limit)
        if SEM_AUTO_CORTE.locked():
             wait = await m.reply("⏳ **En Cola de Procesamiento (Resize)...**\n_Esperando turno_")
        else:
             wait = await m.reply("⬇️ **Bajando para Redimensionar...**\n🚀 Velocidad Máxima Activada")

        async with SEM_AUTO_CORTE:
            if wait.text.startswith("⏳"): await wait.edit("⬇️ **Bajando...**")
            
            # 1. Download
            ext = ".mp4"
            if m.document and m.document.file_name: _, ext = os.path.splitext(m.document.file_name)
            elif m.video and m.video.file_name: _, ext = os.path.splitext(m.video.file_name)
            
            from utils import download_parallel
            from tools_media import progreso, resize_video, get_meta, get_thumb
            
            f_p = await download_parallel(c, m, os.path.join(DATA_DIR, f"resize_{cid}_{m.id}{ext}"), progress=progreso, progress_args=(wait, [0,0], "Descargando"))
            
            if not f_p: f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"resize_{cid}_{m.id}{ext}"))

            if f_p and os.path.exists(f_p):
                val = conf.get('resize_auto_val', '9:16')
                await wait.edit(f"📐 **Redimensionando a {val}...**")
                
                # 2. PROCESAR
                out_path = await resize_video(f_p, val)
                
                if out_path:
                    w, h, dur = await get_meta(out_path)
                    t_path = await get_thumb(out_path, cid, int(time.time()))
                    
                    await wait.edit("📤 **Enviando video redimensionado...**")
                    try:
                        await c.send_video(
                            cid, out_path, 
                            width=w, height=h, duration=dur, thumb=t_path,
                            caption=f"✅ **Auto Dimensionador** (`{val}`)",
                            progress=progreso, progress_args=(wait, [0,0], "Enviando")
                        )
                    except Exception as e:
                         await c.send_document(cid, out_path, caption=f"✅ **Auto Dimensionador** (`{val}`)", thumb=t_path)
                    
                    if t_path and os.path.exists(t_path): os.remove(t_path)
                    os.remove(out_path)
                else:
                    await wait.edit("❌ Error al redimensionar.")
                
                if os.path.exists(f_p): os.remove(f_p)
                try: await wait.delete()
                except: pass
            else:
                await wait.edit("❌ Error en descarga.")
        return

    # --- AUTO CORTE SPECIFIC FLOW (QUEUE) ---
    if conf.get('cut_auto_mode', False) and 'party_pending' not in st:
        # Check Semaphore Status
        if SEM_AUTO_CORTE.locked():
             wait = await m.reply("⏳ **En Cola de Procesamiento...**\n_Esperando turno (Máx 5 simultáneos)_")
        else:
             wait = await m.reply("⬇️ **Bajando TURBO (x16)...**\n🚀 Velocidad Máxima Activada")

        async with SEM_AUTO_CORTE:
            if wait.text.startswith("⏳"): await wait.edit("⬇️ **Bajando TURBO (x16)...**\n🚀 Velocidad Máxima Activada")
            
            # Determine Extension
            ext = ".mp4"
            if m.audio: ext = ".mp3"
            if m.document and m.document.file_name: _, ext = os.path.splitext(m.document.file_name)
            elif m.video and m.video.file_name: _, ext = os.path.splitext(m.video.file_name)
            elif m.audio and m.audio.file_name: _, ext = os.path.splitext(m.audio.file_name)
            
            from utils import download_parallel
            from tools_media import progreso
            f_p = await download_parallel(c, m, os.path.join(DATA_DIR, f"party_{cid}_{m.id}{ext}"), progress=progreso, progress_args=(wait, [0,0], "Descargando"))
            
            if not f_p:
                  f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"party_{cid}_{m.id}{ext}"))

            # Logic Auto Cut
            val = conf.get('cut_auto_val', '15')
            await wait.edit(f"✂️ **Auto Corte Activo ({val}s)**\nProcesando...")
            
            from tools_media import cut_video_start, get_meta, get_thumb
            out = await cut_video_start(f_p, val)

            if out:
                await wait.edit("📤 **Enviando video cortado...**")
                w, h, dur = await get_meta(out)
                t_path = await get_thumb(out, cid, int(time.time()))
                
                try:
                    if out.lower().endswith(('.mp3', '.m4a', '.flac', '.wav', '.ogg')):
                         # Send as Audio
                         await c.send_audio(cid, out, caption=f"✂️ **Corte Inicial Auto ({val}s)**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                    else:
                         # Send as Video
                         await c.send_video(cid, out, width=w, height=h, duration=dur, thumb=t_path, caption=f"✂️ **Corte Inicial Auto ({val}s)**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                except Exception as e:
                    await c.send_document(cid, out, caption=f"✂️ **Corte Inicial Auto ({val}s)**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))

                if t_path and os.path.exists(t_path): os.remove(t_path)
                if os.path.exists(out): os.remove(out)
                await wait.delete()
                if os.path.exists(f_p): os.remove(f_p)
            else:
                await wait.edit("❌ Error en Auto Corte.")
        return
        
    # --- STANDARD FLOW (No Queue / One-by-One Manual) ---

    # --- DEFERRED DOWNLOAD CHECK ---
    # Si NO hay configuración pendiente, NO descargar. Preguntar primero.
    if 'party_pending' not in st and not (conf.get('gif_mode') or conf.get('mp3_mode') or conf.get('cut_init_mode') or conf.get('extract_mode')):
         # --- CUSTOM AUTO PARTY CHECK (Priority) ---
         if conf.get('auto_party') and conf.get('auto_party_custom') and conf.get('auto_party_cfg'):
             mode_c, val_c = conf.get('auto_party_cfg')
             # Direct Queue (Using global party_worker)
             wait_msg = await m.reply(f"⏳ **Auto Party ({mode_c}={val_c})**\nEncolando...")
             asyncio.create_task(party_worker(c, cid, m, mode_c, val_c, wait_msg, context_config=conf))
             return

         # Guardar mensaje para después
         url_storage[cid] = {'party_step': 'wait_mode', 'party_msg': m}
         
         # from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
         kb_p = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧩 Partes", callback_data="party_sel|parts"), InlineKeyboardButton("⏱ Tiempo", callback_data="party_sel|time")],
            [InlineKeyboardButton("✂️ Rango", callback_data="party_sel|range")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu|party_off")]
         ])
         await m.reply("✂️ **Modo Party Activo**\n\n1️⃣ **Configura** el corte abajo 👇\n2️⃣ El video se descargará **después** de configurar.", reply_markup=kb_p)
         return

         return

    # --- DEFERRED EXTRACT MODE CHECK ---
    if conf.get('extract_mode') and 'extract_pending' not in st:
         # Ignore if auto_extract is ON (let it download)
         if conf.get('auto_extract', False):
             pass 
         else:
             url_storage[cid] = {'extract_step': 'wait_mode', 'extract_msg': m}
             kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏱ Segundos", callback_data="extract_sel|sec"), InlineKeyboardButton("🕒 Minutos", callback_data="extract_sel|min")],
                [InlineKeyboardButton("🎯 Frame Exacto", callback_data="extract_sel|exact")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
             ])
             # Check if we should delete user message to keep chat clean or just reply? 
             # Party mode replies. We reply.
             await m.reply("🖼 **Modo Extractor Activo**\n\n1️⃣ **Configura** abajo 👇\n2️⃣ El video se descargará **después** de configurar.", reply_markup=kb)
             return

    wait = await m.reply("⬇️ **Bajando TURBO (x16)...**\n🚀 Velocidad Máxima Activada")
    
    from utils import download_parallel
    from tools_media import progreso
    
    # Determine Extension
    ext = ".mp4"
    if m.audio: ext = ".mp3"
    if m.document and m.document.file_name: _, ext = os.path.splitext(m.document.file_name)
    elif m.video and m.video.file_name: _, ext = os.path.splitext(m.video.file_name)
    elif m.audio and m.audio.file_name: _, ext = os.path.splitext(m.audio.file_name)

    # Create Job Directory (Nested)
    tool_folder = os.path.join(DATA_DIR, "general_temp")
    if not os.path.exists(tool_folder): os.makedirs(tool_folder)
    
    job_dir = os.path.join(tool_folder, f"job_{cid}_{time.time_ns()}_{random.randint(1000, 9999)}")
    if not os.path.exists(job_dir): os.makedirs(job_dir)
    
    f_p = await download_parallel(c, m, os.path.join(job_dir, f"party_{cid}{ext}"), progress=progreso, progress_args=(wait, [0,0], "Descargando"))
    
    if not f_p:
         # Fallback manual por si acaso
         f_p = await c.download_media(m, file_name=os.path.join(job_dir, f"party_{cid}{ext}"))
    
    # ¿Hay una acción pendiente?
    if 'party_pending' in st:
        mode, val = st['party_pending']
        await run_party_logic(c, cid, f_p, mode, val, wait, original_msg=m, context_config=conf)
        url_storage.pop(cid, None)
    elif conf.get('gif_mode'):
        # Solo GIF, sin menú de opciones
        await run_gif_logic(c, cid, f_p, wait)
    elif conf.get('mp3_mode'):
        # Solo MP3, sin menú
        await run_mp3_logic(c, cid, f_p, wait)
    elif conf.get('cut_init_mode'):
        # Ir al menú de corte (Manual)
        url_storage[cid] = {'cut_step': 'wait_time', 'file': f_p}
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("5s", callback_data="cut_exec|00:05"), InlineKeyboardButton("10s", callback_data="cut_exec|00:10"), InlineKeyboardButton("30s", callback_data="cut_exec|00:30")],
            [InlineKeyboardButton("1m", callback_data="cut_exec|01:00"), InlineKeyboardButton("✏️ Manual", callback_data="cut_input|manual")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
        ])
        await wait.edit("✂️ **Corte Inicial**\n¿Cuánto tiempo quieres cortar del inicio?\n(El video empezará DESPUÉS de este tiempo)", reply_markup=kb)
    elif conf.get('extract_mode'):
        # Ir al menú de extracción
        url_storage[cid] = {'extract_step': 'wait_mode', 'file': f_p}
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏱ Segundos", callback_data="extract_sel|sec"), InlineKeyboardButton("🕒 Minutos", callback_data="extract_sel|min")],
            [InlineKeyboardButton("🎯 Frame Exacto", callback_data="extract_sel|exact")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
        ])
        await wait.edit("🖼 **Modo Extractor**\n¿Cómo quieres extraer las imágenes?", reply_markup=kb)
    else:
        # Modo clásico: El usuario envió el video y AHORA elige
        url_storage[cid] = {'party_step': 'wait_mode', 'file': f_p}
        kb_p = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧩 Partes", callback_data="party_sel|parts"), InlineKeyboardButton("⏱ Tiempo", callback_data="party_sel|time")],
            [InlineKeyboardButton("✂️ Rango", callback_data="party_sel|range")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu|party_off")]
        ])
        await wait.edit("✂️ **Modo Party**\nSelecciona una opción:", reply_markup=kb_p)


@app.on_message(filters.text & ~filters.command(["start", "help", "id", "menu", "cancel", "user", "setsudo"]), group=1)
async def input_handler(c, m):
    # Fix: Combined logic for ID detection and party mode input
    cid = m.chat.id
    text = m.text.strip()
    
    # 0. Check Party Input Mode first (Existing Logic)
    # 0. Check Party Input Mode first (Existing Logic)
    st = url_storage.get(cid)
    conf = get_config(cid) # FIX: Define conf

    # --- TIKTOK JUMP INPUT ---
    if st and st.get('tiktok_step') == 'wait_jump':
        try:
            val = int(text)
            # Find closest valid index (1-based input -> 0-based idx)
            target = max(0, val - 1)
            
            # Use TikTok Tool Logic
            from tiktok_tool import show_catalog, VIRAL_CATALOG # Import locally
            total = len(VIRAL_CATALOG)
            target = min(target, total - 1)
            
            # Clear state
            url_storage[cid].pop('tiktok_step', None)
            
            await m.reply(f"✅ Saltando a {target + 1}...")
            await show_catalog(c, cid, target)
        except ValueError:
            await m.reply("❌ Introduce un número válido.")
        return

    # --- VIRAL CATALOG JUMP INPUT ---
    if st and st.get('viral_step') == 'wait_jump':
        try:
            val = int(text)
            target = max(0, val - 1)
            target = min(target, len(viral_music_db) - 1)
            
            url_storage[cid].pop('viral_step', None)
            
            await m.reply(f"✅ Saltando a {target + 1}...")
            
            # Show Item (Reuse logic block manually or via callback hack)
            # Manual show
            item = viral_music_db[target]
            iid = item['id']
            itype = item['type']
            fid = item['file_id']
            cap = item.get('caption', "")
            
            from utils import generate_grid_keyboard
            from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            extra_rows = [
                 [
                     InlineKeyboardButton("🗑️ Eliminar", callback_data=f"viral_del|{iid}"),
                     InlineKeyboardButton("🎲 Aleatorio", callback_data="viral_next")
                 ],
                 [InlineKeyboardButton("🔙 Menú Viral", callback_data="menu|viral_init")]
             ]
            kb = generate_grid_keyboard(target, len(viral_music_db), "viral_sel|", "viral_nav|", "viral_jump", extra_rows=extra_rows)
            
            caption_txt = f"🎵 **Catálogo Viral** [{target+1}/{len(viral_music_db)}]\nID: `{iid}`\n{cap}"
            if itype == 'video': await c.send_video(cid, fid, caption=caption_txt, reply_markup=kb)
            elif itype == 'audio': await c.send_audio(cid, fid, caption=caption_txt, reply_markup=kb)
            elif itype == 'voice': await c.send_voice(cid, fid, caption=caption_txt, reply_markup=kb)
            
        except ValueError:
             await m.reply("❌ Introduce un número válido.")
        return

    # --- CUT AUTO CUSTOM VALUE INPUT ---
    if st and st.get('auto_party_input_mode'):
         mode = st.get('auto_party_input_mode')
         val = text
         conf['auto_party_cfg'] = (mode, val)
         from firebase_service import save_user_config_fb
         asyncio.create_task(save_user_config_fb(cid, conf))
         
         await m.reply(f"✅ **Auto Configurado:** {mode}={val}")
         url_storage[cid].pop('auto_party_input_mode', None)
         
         # Show menu again (Trigger callback hack)
         await cb(c, type('obj', (object,), {'message': m, 'from_user': m.from_user, 'data': 'menu|auto_party_custom', 'answer': lambda *args, **kwargs: None, 'internal': True})())
         return

    if st and st.get('cut_auto_step') == 'val_wait':
        val = text
        conf['cut_auto_val'] = val
        from firebase_service import save_user_config_fb
        asyncio.create_task(save_user_config_fb(cid, conf))
        
        url_storage[cid]['cut_auto_step'] = None # Clear step
        
        # Show updated menu
        is_on = conf.get('cut_auto_mode', False)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Estado: {'🟢 ACTIVO' if is_on else '🔴 APAGADO'}", callback_data="toggle|cut_auto")],
            [InlineKeyboardButton(f"⏱ Valor: {val}s", callback_data="ignore")],
            [
                InlineKeyboardButton("5s", callback_data="cut_auto_set|5"),
                InlineKeyboardButton("10s", callback_data="cut_auto_set|10"),
                InlineKeyboardButton("15s", callback_data="cut_auto_set|15"),
                InlineKeyboardButton("30s", callback_data="cut_auto_set|30")
            ],
            [InlineKeyboardButton("✏️ Personalizado", callback_data="cut_auto_set|custom")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
        ])
        
        # User requested specific feedback explaining automation
        await m.reply(f"✅ **Valor guardado:** `{val}`\n\nAhora, si usas el modo **Corte Inicial**, cortará automáticamente **{val}** de cualquier video que mandes.", reply_markup=kb)
        # Check auto-off for cut_auto if needed? The logic seems to be "set value" here, not run logic.
        return

    # --- CUT INIT MANUAL INPUT ---
    if st and st.get('cut_input_mode') == 'manual':
         val = text
         # Feedback moved below after validation of file
         
         f_path = st.get('file')
         f_path = st.get('file')
         if f_path and os.path.exists(f_path):
             # Format feedback
             fb_str = val
             if ":" in val:
                 parts = val.split(":")
                 if len(parts) == 2:
                     fb_str = f"{val} ({parts[0]} min {parts[1]} seg)"
             else:
                 fb_str = f"{val} ({val} segundos)"
             
             await m.reply(f"✅ Recibido: `{fb_str}`. Procesando...")

             from tools_media import cut_video_start, get_meta, get_thumb
             # FIX: Call async directly, do not use run_in_executor
             out = await cut_video_start(f_path, val)
             
             if out:
                w, h, dur = await get_meta(out)
                t_path = await get_thumb(out, cid, int(time.time()))
                from tools_media import progreso
                # Send with progress
                pm = await m.reply("📤 **Iniciando subida...**")
                
                # CHECK DOC MODE TOOLS
                conf = get_config(cid)
                is_doc_tools = conf.get('doc_mode_tools', False)
                
                try:
                    if is_doc_tools:
                         await c.send_document(cid, out, thumb=t_path, caption=f"✂️ **Corte Inicial ({fb_str})**", progress=progreso, progress_args=(pm, [0,0], None))
                    else:
                         await c.send_video(cid, out, width=w, height=h, duration=dur, thumb=t_path, caption=f"✂️ **Corte Inicial ({fb_str})**", progress=progreso, progress_args=(pm, [0,0], None))
                except:
                    await c.send_document(cid, out, caption=f"✂️ **Corte Inicial ({fb_str})**", progress=progreso, progress_args=(pm, [0,0], None))
                
                await pm.delete()
                
                if t_path and os.path.exists(t_path): os.remove(t_path)
                if os.path.exists(out): os.remove(out)
             else:
                await m.reply("❌ Error al cortar.\nFormato posible de tiempo incorrecto (Ej: `00:10`).")
             
             if os.path.exists(f_path): os.remove(f_path)
             url_storage.pop(cid, None)
             
             # Auto-OFF
             conf['cut_init_mode'] = False
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             await c.send_message(cid, "🛑 Se desactivó el modo/herramienta: Corte Inicial")

         else:
             await m.reply("❌ Archivo expiró.")
             url_storage.pop(cid, None)
             
         m.stop_propagation()
         return

    # 0.5 Tagger/Research Mode Support (Top Priority for Text)
    # 0.5 Tagger/Research Mode Support (Top Priority for Text)
    is_tagger = conf.get('tagger_mode')
    is_research = conf.get('research_mode')
    
    if is_tagger and is_research:
        # DUAL SMART MODE
        if not text.startswith("/"):
            # Use research logic but it will handle the smart context because we will update the prompt
            await run_research_logic(c, cid, text=text, msg=m) 
            m.stop_propagation()
            return

    if is_tagger:
        # Ignore commands
        if not text.startswith("/"):
            await run_tagger_text_logic(c, cid, text, m)
            m.stop_propagation()
            return
    elif is_research:
        if not text.startswith("/"):
            await run_research_logic(c, cid, text=text, msg=m)
            m.stop_propagation()
            return
    
    # BLOCK INTERACTIONS IF IN CONFIG MODE
    if st and (st.get('ai_config_step') or st.get('ai_add_step')):
        # Allow only if it matches specific logic below?
        # ai_add_step handles its own logic below.
        # ai_config_step handles subset below? No, subset is in image_handler (weird location but ok)
        
        # Check if it was handled by image_handler (wait_subset)
        # image_handler filters are media. subset is text.
        # So where is wait_subset handled?!?
        # It is handled in image_handler in the file I viewed earlier?
        # Let me re-verify that.
        pass # Placeholder for thought
        
    # Re-reading: subset logic WAS inside image_handler but that function decorator was media only.
    # That means subset text input (e.g. "1 3 5") was NEVER working if image_handler only had media filters.
    # UNLESS image_handler had filters.text too?
    # View showed: @app.on_message(filters.photo | filters.document | filters.video | filters.animation | filters.sticker)
    # It does NOT have text.
    # So line 2221 "if st and st.get('ai_config_step') == 'wait_subset':" inside image_handler is DEAD CODE for text inputs.
    # Fixing this: I should move that logic to input_handler OR add filters.text to image_handler.
    # Adding filters.text to image_handler makes it a "general handler" which is essentially what input_handler is.
    # Better to move it or handle it in input_handler.
    
    # But for now, user request is 'block others'.
    # If I block others here, I might block valid inputs if I don't move the logic.
    # Assuming the user only complained about "other functions" responding.
    
    if st and st.get('ai_config_step') == 'wait_image':
         await m.reply("⚠️ **Modo Subida Activo**\nSolo acepto imágenes.\nPulsa **🛑 PAUSAR SUBIDA** si ya terminaste, o escribe /start.")
         m.stop_propagation()
         return

    
    # --- FLOW: ADD CUSTOM PERSONA ---
    if st and 'ai_add_step' in st:
        step = st['ai_add_step']
        if text.lower() == "/cancel":
             url_storage.pop(cid, None)
             await m.reply("❌ Cancelado.")
             return

        if step == 'wait_name':
            # Save name, ask prompt
            url_storage[cid]['new_persona_name'] = text
            url_storage[cid]['ai_add_step'] = 'wait_prompt'
            
            await m.reply(f"👤 **Nombre:** {text}\n\n🧠 **Ahora define su COMPORTAMIENTO (Prompt).**\nDescribe cómo debe hablar, su actitud, palabras clave, etc.\n\n_Tip: Puedes escribir 'Misma que NSFW' para copiar la base._")
            return

        elif step == 'wait_prompt':
            name = st.get('new_persona_name', 'Custom')
            prompt = text
            
            # Save to Global (Shared)
            # Save to Global (Shared)
            # import time # Removed to avoid shadowing global time
            pid = f"cust_{int(time.time())}"
            
            p_data = {'name': name, 'prompt': prompt, 'images': {}}
            await save_global_persona(pid, p_data)
            await refresh_globals()
            
            # Auto-Activate (Local User Config)
            conf = get_config(cid)
            conf['active_persona'] = pid
            
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            
            url_storage.pop(cid, None)
            
            from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Configurar Cuerpo", callback_data=f"ai_conf|body|{pid}")],
                [InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu|ai_config")]
            ])
            await m.reply(f"✅ **Personalidad Global Creada: {name}**\n\n🧠 Ya está activa y visible para todos. Configura su cuerpo.", reply_markup=kb)
            return

    # --- FLOW: ADD CATEGORY (NEW) ---
    if st and st.get('action') == 'ai_add_cat_wait':
        pid = st.get('pid', 'nsfw')
        if text.lower() == "/cancel":
            url_storage.pop(cid, None)
            await m.reply("❌ Cancelado.")
            return

        # Normalize key
        key_raw = text.strip()
        key_clean = re.sub(r'[^a-zA-Z0-9]', '_', key_raw).lower()
        
        if not key_clean:
            await m.reply("❌ Nombre inválido. Usa letras y números.")
            return
            
        conf = get_config(cid)
        
        # Check Global First
        if pid in global_personas:
             p_data = global_personas[pid]
             if 'images' not in p_data: p_data['images'] = {}
             
             if key_clean not in p_data['images']:
                 p_data['images'][key_clean] = {'mode': 'single', 'images': []}
                 await save_global_persona(pid, p_data)
                 # Don't need refresh_globals() full here, just local update is enough for now, 
                 # but good to stay synced.
                 global_personas[pid] = p_data 
             else:
                 await m.reply(f"⚠️ La reacción `{key_raw}` ya existía (Global).")
                 url_storage.pop(cid, None)
                 return
        else:
            # Local Legacy
            if 'ai_images' not in conf: conf['ai_images'] = {}
            if pid not in conf['ai_images']: conf['ai_images'][pid] = {}
            
            if key_clean not in conf['ai_images'][pid]:
                conf['ai_images'][pid][key_clean] = {'mode': 'single', 'images': []}
                asyncio.create_task(save_user_config_fb(cid, conf))
            else:
                await m.reply(f"⚠️ La reacción `{key_raw}` ya existía.")
                url_storage.pop(cid, None)
                return
        
        url_storage.pop(cid, None)
        
        # Redirect back
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver a configurar", callback_data=f"ai_conf|body|{pid}")]])
        await m.reply(f"✅ **Característica Creada:** `{key_raw}`\n\nAhora aparecerá en el menú.", reply_markup=kb)
        return

    # --- FLOW: SUBSET CONFIG (Moved from Image Handler) ---
    if st and st.get('ai_config_step') == 'wait_subset':
        cat = st.get('category')
        pid = st.get('persona_id', 'nsfw')
        
        if text.lower() == "/cancel":
             url_storage.pop(cid, None)
             await m.reply("❌ Cancelado.")
             return
             
        try:
             # Parse numbers
             nums = [int(x) for x in text.split()]
             if not nums: raise ValueError("Empty")
             
             conf = get_config(cid)
             # Validate against real count
             # Check Global First
             ai_imgs = {}
             is_global = False
             
             if pid in global_personas and 'images' in global_personas[pid] and cat in global_personas[pid]['images']:
                  ai_imgs = global_personas[pid]['images'][cat]
                  is_global = True
             else:
                  # Local
                  ai_imgs = conf.get('ai_images', {}).get(pid, {}).get(cat, {'images': []})
             
             count = len(ai_imgs.get('images', []))
             
             # Convert to 0-indexed indices
             final_subset = []
             for n in nums:
                 if 1 <= n <= count:
                     final_subset.append(n-1) # 0-indexed
             
             if not final_subset:
                 await m.reply("⚠️ Ningún número válido. Usa índices del 1 al " + str(count))
                 return
                 
             # Save
             if is_global:
                 p_data = global_personas[pid]
                 p_data['images'][cat]['mode'] = 'subset'
                 p_data['images'][cat]['subset'] = final_subset
                 await save_global_persona(pid, p_data)
                 global_personas[pid] = p_data
             else:
                 if 'ai_images' not in conf: conf['ai_images'] = {}
                 if pid not in conf['ai_images']: conf['ai_images'][pid] = {}
                 if cat not in conf['ai_images'][pid]: conf['ai_images'][pid][cat] = {}
                 
                 conf['ai_images'][pid][cat]['mode'] = 'subset'
                 conf['ai_images'][pid][cat]['subset'] = final_subset
                 
                 from firebase_service import save_user_config_fb
                 asyncio.create_task(save_user_config_fb(cid, conf))
             
             # Success msg with Menu
             from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
             kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver a Configurar", callback_data=f"ai_conf|cat|{cat}|{pid}")]])
             await m.reply(f"✅ **Modo Personalizado Activado**\nUsando {len(final_subset)} imágenes seleccionadas.", reply_markup=kb)
             
             url_storage.pop(cid, None)
             return
             
        except Exception as e:
             await m.reply(f"❌ Error: {e}")
             return

    # --- FLOW: EDIT PERSONA TEXT HANDLER ---
    if st and st.get('action') == 'ai_edit_p_wait':
        pid = st.get('pid')
        field = st.get('field')
        
        if text.lower() == "/cancel":
             url_storage.pop(cid, None)
             await m.reply("❌ Edición Cancelada.")
             return
        
        # Validate Input
        if len(text) > 1000: # Limit Prompt
            await m.reply("⚠️ Texto muy largo. Intenta algo más corto.")
            return

        conf = get_config(cid)
        
        # 1. Global Persona Check
        if pid in global_personas:
             p_data = global_personas[pid]
             if field == 'name':
                 if len(text) > 30:
                     await m.reply("⚠️ Nombre muy largo (máx 30 chars).")
                     return
                 p_data['name'] = text
                 msg_success = f"✅ **Nombre Global Editado:** {text}"
             else:
                 p_data['prompt'] = text
                 msg_success = f"✅ **Prompt Global Actualizado.**"
                 
             await save_global_persona(pid, p_data)
             # Update local cache
             global_personas[pid] = p_data
        
        else:
            # 2. Local Legacy Check
            if 'custom_personas' not in conf: conf['custom_personas'] = {}
            if pid not in conf['custom_personas']: conf['custom_personas'][pid] = {}
            
            if field == 'name':
                 if len(text) > 30:
                     await m.reply("⚠️ Nombre muy largo (máx 30 chars).")
                     return
                 conf['custom_personas'][pid]['name'] = text
                 msg_success = f"✅ **Nombre cambiado a:** {text}"
            else:
                 conf['custom_personas'][pid]['prompt'] = text
                 msg_success = f"✅ **Prompt actualizado.**"
            
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
        
        url_storage.pop(cid, None)
        
        # Return to Menu
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu|ai_config")]])
        await m.reply(msg_success, reply_markup=kb)
        return

        # Return to Menu
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu|ai_config")]])
        await m.reply(msg_success, reply_markup=kb)
        return

    # --- INPUT: PAPER MODE (VIDEO MIXER) ---
    if st and 'vm_paper_pending' in st:
        pending = st['vm_paper_pending']
        if not text: return
        
        # We have text and pending videos
        wm = pending['wm']
        msgs = pending['msgs'] # List of [m1, m2] (Pyrogram Message Objects)
        text_input = text
        
        # Clear state
        url_storage[cid].pop('vm_paper_pending')
        
        try: await wm.edit("⬇️ **Descargando videos (Modo Papel)...**")
        except: pass
        
        # Download
        # We need client 'c' to download.
        from utils import download_parallel
        
        paths = []
        for i, msg_v in enumerate(msgs):
            try:
                # Determine Ext
                ext = ".mp4"
                if msg_v.photo: ext = ".jpg"
                elif msg_v.document:
                     if msg_v.document.mime_type and msg_v.document.mime_type.startswith('image/'): ext = ".jpg"
                     elif msg_v.document.file_name: _, ext = os.path.splitext(msg_v.document.file_name)
                elif msg_v.video and msg_v.video.file_name: _, ext = os.path.splitext(msg_v.video.file_name)
                
                # Name unique
                f_path = os.path.join(DATA_DIR, f"paper_in_{cid}_{int(time.time())}_{i}{ext}")
                dl_path = await download_parallel(c, msg_v, f_path)
                if not dl_path: dl_path = await c.download_media(msg_v, file_name=f_path)
                
                if dl_path and os.path.exists(dl_path):
                    paths.append(dl_path)
            except Exception as e:
                print(f"DL Error: {e}")
                
        if len(paths) < 2:
            await wm.edit("❌ Error descargando videos.")
            return
            
        # Process
        await wm.edit(f"🎨 **Generando Meme...**\nTexto: `{text_input}`")
        
        from video_mixer import mix_videos_paper
        conf = get_config(cid)
        audio_mode = conf.get('vm_audio_mode', 'mix')
        
        out_path = await mix_videos_paper(paths[0], paths[1], text_input, audio_mode=audio_mode)
        
        if out_path:
            await wm.edit("📤 **Subiendo...**")
            
            # Detect Type
            is_img_out = out_path.endswith(".jpg")
            
            try:
                if is_img_out:
                    await c.send_photo(
                        cid, out_path, 
                        caption=f"📝 **Modo Papel**\nTexto: {text_input}"
                    )
                else:
                    # Video
                    from tools_media import get_meta
                    w, h, dur = await get_meta(out_path)
                    await c.send_video(
                        cid, out_path, 
                        caption=f"📝 **Modo Papel**\nTexto: {text_input}",
                        width=w, height=h, duration=dur
                    )
            except Exception as e:
                # Fallback
                await c.send_document(cid, out_path, caption="📝 **Modo Papel**")
                
            await wm.delete()
            
            # Cleanup
            try:
                os.remove(out_path)
                for p in paths: os.remove(p)
            except: pass
            
            # Persist Check
            if conf.get('vm_persist', False) and conf.get('video_mixer_mode', False):
                 # Stay in mode... but buffers are cleared.
                 await m.reply("✅ **Listo.**\nEnvíame otros 2 videos para otro meme.", 
                               reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="menu|video_mixer_menu")]]))
            else:
                 # Auto OFF
                 conf['video_mixer_mode'] = False
                 conf['vm_paper_mode'] = False # Disable sub-mode too? Usually safer.
                 from firebase_service import save_user_config_fb
                 asyncio.create_task(save_user_config_fb(cid, conf))
                 await m.reply("✅ **Proceso Finalizado.**")
                 
        else:
            await wm.edit("❌ Error Generando Video.")
            
        m.stop_propagation()
        return

    if st and 'party_input_mode' in st:
        mode = st['party_input_mode']
        url_storage[cid].pop('party_input_mode', None)

        if 'file' not in st:
            url_storage[cid]['party_pending'] = (mode, text)
            await m.reply(f"✅ **Configurado (Split):** `{mode}={text}`\n\n🎬 **Envía el video** ahora.")
            return
        
        await run_party_logic(c, cid, st['file'], mode, text, original_msg=st.get('party_msg'))
        url_storage.pop(cid, None)
        return

    if st and 'extract_step' in st:
        step = st['extract_step']
        f_p = st.get('file')
        
        # --- DEFERRED DOWNLOAD (INPUT HANDLER) ---
        if not f_p or not os.path.exists(f_p):
             extract_msg = st.get('extract_msg')
             if extract_msg:
                 # Confirmacion Visual
                 await m.reply(f"✅ **Configurado: {text}**")
                 wait = await m.reply(f"⬇️ **Descargando para extraer...**\n🚀 Velocidad Máxima Activada")
                 
                 from utils import download_parallel
                 from tools_media import progreso
                 import random
                 import config
                 
                 # Create Temp Dir
                 tool_folder = os.path.join(config.DATA_DIR, "extract_temp")
                 if not os.path.exists(tool_folder): os.makedirs(tool_folder)
                 job_dir = os.path.join(tool_folder, f"job_{cid}_{time.time_ns()}_{random.randint(1000, 9999)}")
                 if not os.path.exists(job_dir): os.makedirs(job_dir)
                 
                 # Ext guess
                 ext = ".mp4"
                 if extract_msg.video and extract_msg.video.file_name: _, ext = os.path.splitext(extract_msg.video.file_name)
                 elif extract_msg.document and extract_msg.document.file_name: _, ext = os.path.splitext(extract_msg.document.file_name)
                 
                 f_p = await download_parallel(c, extract_msg, os.path.join(job_dir, f"extract_{cid}{ext}"), progress=progreso, progress_args=(wait, [0,0], "Descargando"))
                 if not f_p: f_p = await c.download_media(extract_msg, file_name=os.path.join(job_dir, f"extract_{cid}{ext}"))
                 
                 if not f_p: 
                     await wait.edit("❌ Error descargando video.")
                     return
                 
                 # clean wait msg
                 try: await wait.delete()
                 except: pass
             else:
                 await m.reply("❌ Video expiró.")
                 url_storage.pop(cid, None)
                 return

        url_storage.pop(cid, None)

        if step.startswith('wait_custom_'):
            mode = step.split('_')[-1]
            await run_extract_logic(c, cid, f_p, mode, text)
        elif step == 'wait_exact':
            await run_extract_logic(c, cid, f_p, 'exact', text)
        return

    # 1. RAW MANGA ID CHECK (AlphaNumeric ~20 chars)
    # Ejemplo: sX2wxwVUjoJzWmN0W2cG
    if re.match(r'^[a-zA-Z0-9]{20}$', text):
        wm = await m.reply("⬇️ **Analizando ID de Manga...**")
        await show_manga_menu(c, m, text, wait_msg=wm)
        return

    m.continue_propagation()


# --- COLLAGE TOOL HANDLER ---
@app.on_message((filters.video | filters.document | filters.photo) & filters.private)
async def collage_video_handler(c, m):
    cid = m.chat.id
    conf = get_config(cid)
    
    # Priority Auto Check:
    # If explicit 'collage_mode' is True, use it (manual or previously set).
    # IF NOT, check if any AUTO is True. If so, ACTIVATE it on the fly.
    active_auto = None
    if conf.get('collage_auto_3x3'): active_auto = '3x3'
    elif conf.get('collage_auto_2x2'): active_auto = '2x2'
    elif conf.get('collage_auto_2x1'): active_auto = '2x1'
    
    # If Auto is detected, override/activate mode
    if active_auto:
        conf['collage_mode'] = True
        conf['collage_grid'] = active_auto
        # We don't save to DB here to avoid spamming writes, passed in memory or just used.
        # But 'run_collage_logic' reads from 'conf', which is a dict. This update affects the local dict.
    
    # Check if Collage Mode is active
    if conf.get('collage_mode'):
        # --- BATCH BUFFER LOGIC ---
        if cid not in COLLAGE_BATCH_BUFFER:
             # First item in batch
             wm = await m.reply("🧩 **Collage: Recibido 1/N...**\n(Envía más o espera a que se procese)")
             COLLAGE_BATCH_BUFFER[cid] = {'files': [], 'wm': wm}
             # Start Batch Timer
             asyncio.create_task(run_collage_batch(cid, c))
        
        # Download Media to Temp
        wm = COLLAGE_BATCH_BUFFER[cid]['wm']
        try: await wm.edit("⬇️ ...")
        except: pass
        
        # Determine Ext
        ext = ".jpg" # Default if photo
        if m.video: ext = ".mp4"
        elif m.document: _, ext = os.path.splitext(m.document.file_name or "file.mp4")
        
        # Create Temp Path
        ts = int(time.time())
        rnd = random.randint(1000, 9999)
        # Unique Job Folder per Chat/Batch? Or shared temp? Shared temp but unique files.
        tool_folder = os.path.join(DATA_DIR, "collage_temp")
        if not os.path.exists(tool_folder): os.makedirs(tool_folder)
        
        f_path = os.path.join(tool_folder, f"col_in_{cid}_{ts}_{rnd}{ext}")
        
        # Download
        # Assuming photos are small, video/doc normal download
        if m.photo:
            await c.download_media(m, file_name=f_path)
        else:
            from utils import download_parallel
            from tools_media import progreso
            p = await download_parallel(c, m, f_path, progress=progreso, progress_args=(wm, [0,0], "Agregando..."))
            if not p: await c.download_media(m, file_name=f_path)
            
        if os.path.exists(f_path):
             COLLAGE_BATCH_BUFFER[cid]['files'].append(f_path)
             cnt = len(COLLAGE_BATCH_BUFFER[cid]['files'])
             try: await wm.edit(f"🧩 **Collage: Recibido {cnt}/N...**\n(Espera 4s para procesar)")
             except: pass
        
        m.stop_propagation()
        return

    # If not active, propagate to standard handlers (Party, Tools, etc.)
    m.continue_propagation()

# --- LINK REFACTOR MODE HANDLER ---
@app.on_message(filters.command(["refactorización_de_enlaces", "refactor_on", "refactor_off"]) & filters.private)
async def refactor_mode_command(c, m):
    cid = m.chat.id
    try:
        current_st = get_config(cid).get('refactor_mode', False)
        cmd = m.command[0].lower()

        # Logic for determining new state based on command name or argument
        if cmd == "refactor_on":
            new_st = True
        elif cmd == "refactor_off":
            new_st = False
        else:
            # Generic command: /refactorización_de_enlaces
            if len(m.command) < 2:
                state = "ON 🟢" if current_st else "OFF 🔴"
                await m.reply(f"ℹ️ **Modo Refactorización:** {state}\nUso: `/refactor_on`, `/refactor_off` o `/refactorización_de_enlaces on/off`")
                return
            
            arg = m.command[1].lower()
            new_st = True if arg == 'on' else False
        
        conf = get_config(cid)
        conf['refactor_mode'] = new_st
        
        from firebase_service import save_user_config_fb
        asyncio.create_task(save_user_config_fb(cid, conf))
        
        state_txt = "ACTIVADO 🟢" if new_st else "DESACTIVADO 🔴"
        await m.reply(f"✅ **Refactorización de Enlaces:** {state_txt}")
        
    except Exception as e:
        await m.reply(f"❌ Error: {e}")

# --- REFACTOR INTERCEPTOR (High Priority) ---
@app.on_message(filters.regex(r"https?://(www\.)?facebook\.com/share/r/") & filters.private, group=-5)
async def refactor_link_interceptor(c, m):
    cid = m.chat.id
    conf = get_config(cid)
    
    # Only if enabled
    if not conf.get('refactor_mode', False):
        m.continue_propagation()
        return
        
    url = m.text.strip()
    
    # Check if handleable
    if 'share/r/' in url:
        await m.reply("🔄 **Analizando enlace (puede tardar unos segundos)...**")
        try:
            # Use yt-dlp to resolve the redirect and get ID
            import yt_dlp
            
            # Run in executor to avoid blocking
            def get_fb_id(u):
                opts = {
                    'quiet': True,
                    'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(u, download=False)
                    return info.get('id')
            
            real_id = await asyncio.get_running_loop().run_in_executor(None, get_fb_id, url)
            
            if real_id:
                new_url = f"https://www.facebook.com/reel/{real_id}"
                await m.reply(f"🔄 **Link Refactorizado:**\n{new_url}", disable_web_page_preview=True)
            else:
                 await m.reply("⚠️ No se pudo extraer el ID del enlace.")

        except Exception as e:
            print(f"Refactor Error: {e}")
            m.continue_propagation()
            return
    else:
        m.continue_propagation()


# --- VIDEO MIXER HANDLER ---
@app.on_message((filters.video | filters.document | filters.photo) & filters.private, group=-2)
async def video_mixer_handler(c, m):
    cid = m.chat.id
    conf = get_config(cid)
    
    if conf.get('video_mixer_mode'):
        await run_video_mixer_logic(c, cid, m)
        m.stop_propagation()
        return
    
    m.continue_propagation()

async def run_video_mixer_logic(c, cid, m):
    # 1. Init Buffer & Lock (Thread-Safeish)
    if cid not in VIDEO_MIXER_BUFFERS:
        VIDEO_MIXER_BUFFERS[cid] = []
    if cid not in VIDEO_MIXER_LOCKS:
        VIDEO_MIXER_LOCKS[cid] = asyncio.Lock()
        
    buff = VIDEO_MIXER_BUFFERS[cid]
    
    # 2. Add to Buffer (Store Message, Don't Download Yet)
    # We reply to acknowledge receipt
    wm = await m.reply("⬇️ ...") 
    
    process_pair = None
    
    async with VIDEO_MIXER_LOCKS[cid]:
        # Append tuple: (msg_id, message_object, reply_msg_object)
        buff.append((m.id, m, wm))
        buff.sort(key=lambda x: x[0])
        
        needed = 2
        if len(buff) >= needed:
            process_pair = [buff.pop(0) for _ in range(needed)]

    # 3. Feedback Loop (Wait or Start)
    if not process_pair:
        try:
            await wm.edit(f"✅ **Recibí 1 Archivo.**\n🎥 **Envíame el siguiente** (Video o Foto) para mezclar.")
        except: pass
        return
        
    # Continue with processing
    try:
        # Check Paper Mode
        conf = get_config(cid)
        if conf.get('vm_paper_mode', False):
            # PAPER MODE: Don't mix yet. Ask for Text.
            # Store the pair in a specific wait state.
            
            # Clean UI first
            m1, wm1 = process_pair[0][1], process_pair[0][2]
            m2, wm2 = process_pair[1][1], process_pair[1][2]
            
            try: await wm1.delete()
            except: pass
            
            # We use the second wm to ask
            target_wm = wm2 
            
            # Save pending pair
            if cid not in url_storage: url_storage[cid] = {}
            
            url_storage[cid]['vm_paper_pending'] = {
                'wm': target_wm,
                'msgs': [m1, m2]
            }
            
            await target_wm.edit("✍️ **Modo Papel: Falta Texto**\n\nEscribe el texto que irá en la parte superior (Meme).")
            return

        # 4. START PROCESS (Standard Mix)

        v1_data = process_pair[0] # (id, msg, wm)
        v2_data = process_pair[1]
        
        m1, wm1 = v1_data[1], v1_data[2]
        m2, wm2 = v2_data[1], v2_data[2]
        
        # UI Cleanup: Delete first waiting message, keep second for progress
        try: await wm1.delete()
        except: pass
        
        target_wm = wm2 
        try: await target_wm.edit("⬇️ **Recibidos 2 Clips. Comenzando descarga...**")
        except: pass
        
        from utils import download_parallel
        from tools_media import progreso
        
        # Helper Download function
        async def dl_clip(msg, index):
            # Determine Ext
            ext = ".mp4"
            is_static_img = False
            
            if msg.photo: 
                ext = ".jpg"
                is_static_img = True
            elif msg.video and msg.video.file_name: _, ext = os.path.splitext(msg.video.file_name)
            elif msg.document:
                 if msg.document.mime_type and msg.document.mime_type.startswith('image/'):
                     ext = ".jpg"
                     is_static_img = True
                 elif msg.document.file_name: 
                     _, ext = os.path.splitext(msg.document.file_name)
            
            f_path = os.path.join(DATA_DIR, f"vmix_{cid}_{msg.id}_{int(time.time())}{ext}")
            
            # Download
            if is_static_img:
                 # Direct download for images (faster/simpler)
                 path = await c.download_media(msg, file_name=f_path)
            else:
                 path = await download_parallel(c, msg, f_path, progress=progreso, progress_args=(target_wm, [0,0], f"Descargando Clip {index}/2"))
                 if not path: path = await c.download_media(msg, file_name=f_path)
                 
            return path

        # Sequential Download (safer for progress bar updates)
        v1_path = await dl_clip(m1, 1)
        if not v1_path:
             await target_wm.edit("❌ Error descargando Archivo 1")
             return
             
        v2_path = await dl_clip(m2, 2)
        if not v2_path:
             await target_wm.edit("❌ Error descargando Archivo 2")
             return

        # 5. MIXING
        try: 
             await target_wm.edit("✅ **Descargas Completas.**\n🎬 **Comenzando a mezclar...**")
        except: pass
        
        # (Continue to mixing logic below...)

        # Variables are already set above: v1_path, v2_path
        
        conf = get_config(cid)
        a_mode = conf.get('vm_audio_mode', 'mix')
            
        # RUN MIXER
        from video_mixer import mix_videos_side_by_side
        from tools_media import get_meta, get_thumb
        
        out_path = await mix_videos_side_by_side(v1_path, v2_path, audio_mode=a_mode)
        
        if out_path:
            await target_wm.edit("📤 **Subiendo...**")
            
            is_img_out = out_path.endswith(".jpg")
            
            try:
                if is_img_out:
                     await c.send_photo(
                        cid, out_path, 
                        caption="🎞 **Collage Video Creator (Mixer)**"
                    )
                else:
                    w, h, dur = await get_meta(out_path)
                    t_path = await get_thumb(out_path, cid, int(time.time()))
                    
                    await c.send_video(
                        cid, out_path, 
                        width=w, height=h, duration=dur, thumb=t_path,
                        caption="🎞 **Collage Video Creator (Mixer)**",
                        progress=progreso, progress_args=(target_wm, [0,0], "Subiendo")
                    )
                    
                    if t_path and os.path.exists(t_path): os.remove(t_path)
            except Exception as e:
                 await c.send_document(cid, out_path, caption="🎞 **Collage Video Creator (Mixer)**")
            
            # Cleanup Progress Msg
            try: await target_wm.delete()
            except: pass
            
            # Cleanup Output and Thumb
            if t_path and os.path.exists(t_path): os.remove(t_path)
            os.remove(out_path)
        else:
            await target_wm.edit("❌ Error al mezclar videos.")
            
        # Cleanup Inputs
        if os.path.exists(v1_path): os.remove(v1_path)
        if os.path.exists(v2_path): os.remove(v2_path)
        
        # Persistence Check
        if not conf.get('vm_persist', False):
            # Only Auto-Off if buffer is empty? 
            # Smart Check:
            remaining = 0
            async with VIDEO_MIXER_LOCKS[cid]:
                remaining = len(buff)
            
            if remaining == 0:
                conf['video_mixer_mode'] = False
                from firebase_service import save_user_config_fb
                asyncio.create_task(save_user_config_fb(cid, conf))
                await c.send_message(cid, "✅ **Proceso Finalizado.** (Modo Apagado)")
        else:
             # Persist ON -> Just confirm
             pass
                 
    except Exception as e:
        import traceback
        print(f"❌ Video Mixer Error: {e} | Type: {type(e)}")
        traceback.print_exc()
        try: await wm.edit(f"❌ Error CRÍTICO Video Mixer:\n`{e}`\nType: `{type(e)}`")
        except: pass
        # Clean specific file if failed to add
        # (Only if variable 'path' exists and not in buffer)

# --- SMART CUT HANDLER ---
@app.on_message((filters.video | filters.document) & filters.private, group=1) # Group 1 to avoid fighting with Collage? Or same group. 
# Defaults are group 0. If multiple match, multiple run? Pyrogram stops on stop_propagation.
# I'll check Collage Mode. If active, it takes over.
# If Smart Cut Mode is active, it takes over.
async def smart_cut_handler(c, m):
    cid = m.chat.id
    conf = get_config(cid)
    
    if conf.get('smart_cut_mode'):
        # Check Exclusivity (Collage vs Smart Cut) happens at Activation Time.
        await run_smart_cut_logic(c, cid, m)
        m.stop_propagation()
        return
        
    m.continue_propagation()

async def run_smart_cut_logic(c, cid, m):
    wm = await m.reply("⬇️ **Descargando para Smart Cut...**")
    dl_path = None
    out_path = None
    
    try:
        timestamp = int(time.time())
        dl_path = os.path.join("downloads", f"smart_in_{cid}_{timestamp}.mp4")
        
        # Download with Progress
        # Download with Progress
        from tools_media import smart_cut_video, get_meta, progreso, get_thumb
        times = [0, 0]
        await m.download(file_name=dl_path, progress=progreso, progress_args=(wm, times, "Descargando para Smart Cut"))
        
        await wm.edit("🧠 **Analizando intro...**\n_Buscando cambios de escena..._")
        
        # Run detection and cut
        res = await smart_cut_video(dl_path)
        
        if res and res[0]:
            out_path, cut_time = res
            await wm.edit(f"✂️ **Intro detectada: {cut_time:.2f}s**\n📤 Enviando video cortado...")
            
            # Generate Thumbnail from the NEW video
            t_path = await get_thumb(out_path, cid, int(time.time()))
            
            # Send video with Progress
            w, h, dur = await get_meta(out_path)
            times = [0, 0]
            await c.send_video(
                cid, out_path, 
                width=w, height=h, duration=dur,
                thumb=t_path, # Attach new thumbnail
                caption=f"🧠 **Smart Cut Aplicado**\n\n✂️ Se eliminaron los primeros **{cut_time:.2f}s**.",
                progress=progreso, progress_args=(wm, times, "Subiendo Smart Cut")
            )
            
            # Cleanup Thumb
            if t_path and os.path.exists(t_path): 
                try: os.remove(t_path)
                except: pass
        else:
            await wm.edit("⚠️ **No se detectó una intro clara.**\nEl video empieza directo o el cambio es muy sutil.")
            
    except Exception as e:
        print(f"Smart Cut Error: {e}")
        await wm.edit(f"❌ Error: {e}")
        
    finally:
        # Cleanup
        if dl_path and os.path.exists(dl_path): 
            try: os.remove(dl_path)
            except: pass
        if out_path and os.path.exists(out_path):
            try: os.remove(out_path)
            except: pass
            
        # Robust Auto-OFF
        conf = get_config(cid)
        conf['smart_cut_mode'] = False
        from firebase_service import save_user_config_fb
        asyncio.create_task(save_user_config_fb(cid, conf))
        
        try: await c.send_message(cid, "✅ **Smart Cut Finalizado (Auto-OFF)**")
        except: pass
        try: await wm.delete()
        except: pass


async def run_collage_logic(c, cid, m):
    """
    Handles the collage creation process.
    """
    conf = get_config(cid)
    ctype = conf.get('collage_type', 'png')
    grid = conf.get('collage_grid', '3x3')
    
    # 1. Download Video
    wm = await m.reply("⬇️ **Descargando para Collage...**")
    
    try:
        # Determine path
        timestamp = int(time.time())
        # Create Job Directory
        # Create Job Directory (Nested)
        tool_folder = os.path.join(DATA_DIR, "collage_temp")
        if not os.path.exists(tool_folder): os.makedirs(tool_folder)

        job_dir = os.path.join(tool_folder, f"job_{cid}_{timestamp}_{random.randint(1000, 9999)}")
        if not os.path.exists(job_dir): os.makedirs(job_dir)

        dl_path = os.path.join(job_dir, f"collage_in_{cid}_{timestamp}.mp4")
        
        from tools_media import create_video_collage, get_meta, progreso
        times = [0, 0]
        await m.download(file_name=dl_path, progress=progreso, progress_args=(wm, times, "Descargando para Collage"))
        
        await wm.edit(f"🧩 **Generando Collage {grid} (esto puede tardar)...**")
        
        # 2. Generate Collage Image
        collage_path = await create_video_collage(dl_path, grid=grid)
        
        if not collage_path or not os.path.exists(collage_path):
            await wm.edit("❌ Error: No se pudo crear el collage.")
            return

        # 3. Send Result
        await wm.edit("📤 **Subiendo resultado...**")
        times = [0, 0]
        
        if ctype == 'png':
             # Send as Photo
             await c.send_photo(
                 cid, collage_path, 
                 caption=f"🧩 **Collage {grid} Generado**",
                 progress=progreso, progress_args=(wm, times, "Subiendo Collage (IMG)")
             )
        else:
             # Send as Video Thumbnail
             w, h, dur = await get_meta(dl_path)
             if dur == 0: dur = 10
             
             await c.send_video(
                 cid, 
                 dl_path, 
                 thumb=collage_path, 
                 width=w, 
                 height=h, 
                 duration=dur, 
                 caption=f"🧩 **Video con Portada Collage ({grid})**",
                 progress=progreso, progress_args=(wm, times, "Subiendo Collage (Ovid)")
             )
        
        # 4. Clean up
        try:
            if 'job_' in os.path.basename(job_dir) and os.path.exists(job_dir):
                import shutil
                shutil.rmtree(job_dir, ignore_errors=True)
            else:
                 if os.path.exists(collage_path): os.remove(collage_path)
                 if os.path.exists(dl_path): os.remove(dl_path)
        except: pass
        
        await wm.delete()
        
        # 5. Auto-OFF (Check Specific AUTO)
        is_auto = conf.get(f'collage_auto_{grid}', False)
        
        if not is_auto:
            conf['collage_mode'] = False
            from firebase_service import save_user_config_fb
            asyncio.create_task(save_user_config_fb(cid, conf))
            await c.send_message(cid, f"✅ **Modo Collage ({grid}) Finalizado**")
            pass

    except Exception as e:
        print(f"Collage Logic Error: {e}")
        await wm.edit(f"❌ Error crítico: {e}")


async def run_subtitle_logic(c, cid, m):
    wm = await m.reply("⬇️ **Descargando para Subtitular...**")
    dl_path = None
    out_path = None
    
    try:
        timestamp = int(time.time())
        # Create Job Directory
        # Create Job Directory (Nested)
        tool_folder = os.path.join(DATA_DIR, "subtitle_temp")
        if not os.path.exists(tool_folder): os.makedirs(tool_folder)

        job_dir = os.path.join(tool_folder, f"job_{cid}_{timestamp}_{random.randint(1000, 9999)}")
        if not os.path.exists(job_dir): os.makedirs(job_dir)
        
        dl_path = os.path.join(job_dir, f"sub_in_{cid}_{timestamp}.mp4")
        
        # Download
        from tools_media import generate_subtitles_video, get_meta, get_thumb, progreso
        times = [0, 0]
        await m.download(file_name=dl_path, progress=progreso, progress_args=(wm, times, "Descargando para Subtítulos"))
        
        await wm.edit("📝 **Generando Subtítulos (Whisper AI)...**\n_Esto puede tardar unos minutos..._")
        
        # Subtitle Generation
        out_path = await generate_subtitles_video(dl_path, cid)
        
        if out_path and os.path.exists(out_path):
            await wm.edit("📤 **Subiendo video subtitulado...**")
            
            w, h, dur = await get_meta(out_path)
            t_path = await get_thumb(out_path, cid, int(time.time()))
            times = [0, 0]
            
            await c.send_video(
                cid, out_path,
                width=w, height=h, duration=dur,
                thumb=t_path,
                caption="📝 **Video Subtitulado (Automático)**\n_Generado con Whisper AI_",
                progress=progreso, progress_args=(wm, times, "Subiendo Subtitulado")
            )
            
            if t_path and os.path.exists(t_path): 
                try: os.remove(t_path)
                except: pass
        else:
            await wm.edit("❌ Error: No se pudieron generar los subtítulos.")
            
    except Exception as e:
        print(f"Sub Error: {e}")
        await wm.edit(f"❌ Error: {e}")
        
    finally:
        # Cleanup Job Dir
        import shutil
        job_dir = os.path.dirname(dl_path) if dl_path else None
        
        if job_dir and 'job_' in os.path.basename(job_dir) and os.path.exists(job_dir):
             shutil.rmtree(job_dir, ignore_errors=True)
        else:
            if dl_path and os.path.exists(dl_path): 
                try: os.remove(dl_path)
                except: pass
            if out_path and os.path.exists(out_path):
                try: os.remove(out_path)
                except: pass
            
        # Auto-OFF Check
        conf = get_config(cid)
        if not conf.get('sub_auto_mode'):
             conf['sub_mode'] = False
             from firebase_service import save_user_config_fb
             asyncio.create_task(save_user_config_fb(cid, conf))
             try: await c.send_message(cid, "✅ **Subtitulado Finalizado**")
             except: pass
        else:
             # Auto Mode: Stay ON.
             pass
             
        try: await wm.delete()
        except: pass

@app.on_message((filters.video | filters.document) & filters.private, group=2)
async def sub_video_handler(c, m):
    cid = m.chat.id
    conf = get_config(cid)
    
    # Check Auto Mode or Manual Mode
    active = conf.get('sub_mode')
    
    # Priority Auto Check: If auto is set, ensure active is True (runtime check)
    if conf.get('sub_auto_mode'): 
        active = True
        conf['sub_mode'] = True # Ensure consistency
    
    if active:
        # Use SEM_SUB (5 max)
        
        if SEM_SUB.locked():
            msg = await m.reply("⏳ En cola de subtitulado...", quote=True)
        else:
            msg = None
            
        async with SEM_SUB:
            if msg: 
                try: await msg.delete()
                except: pass
            await run_subtitle_logic(c, cid, m)
            
        m.stop_propagation()
        return



# --- TIKTOK FAST VIDEO HANDLER ---
# Usamos group=-1 para tener PRIORIDAD sobre otros handlers (que suelen ser group=0 o 1)
# Así evitamos que la IA o el downloader genérico capturen el video primero.
@app.on_message((filters.video | filters.animation | filters.document) & filters.private, group=-1)
async def exclusive_video_handler(c, m):
    cid = m.chat.id
    conf = get_config(cid)
    
    # Priority Check: Fusion Mode receives video first (Group 0)
    if conf.get('fusion_mode'):
        m.continue_propagation()
        return
    
    # Check if we need to handle this video
    is_tiktok = conf.get('tiktok_fast_mode')
    is_thumb = conf.get('parallel_thumb_mode')
    
    if not is_tiktok and not is_thumb:
        m.continue_propagation()
        return

    # Check validity (Video/Anim/DocVideo)
    is_vid = m.video or m.animation or (m.document and m.document.mime_type and m.document.mime_type.startswith('video'))
    if not is_vid:
        m.continue_propagation()
        return

    # --- QUEUE LOGIC ---
    if SEM_EXCLUSIVE_VIDEO.locked():
        await m.reply("⏳ **En cola...** (Servidor ocupado, espere un momento)", quote=True)
    
    async with SEM_EXCLUSIVE_VIDEO:
        # 1. TIKTOK FAST MODE
        if is_tiktok:
            wm = await m.reply("⬇️ **Descargando para Tiktok Fast...**")
            try:
                import time
                import random
                ts = int(time.time())
                rnd = random.randint(1000, 9999)
                path = os.path.join("downloads", f"tk_in_{cid}_{ts}_{rnd}.mp4")
                
                await m.download(file_name=path)
                
                from tiktok_tool import process_tiktok_video
                await process_tiktok_video(c, m, path)
                
                try: await wm.delete()
                except: pass
                
            except Exception as e:
                try: await wm.edit(f"❌ Error Tiktok Fast: {e}")
                except: pass
            
            m.stop_propagation()
            return

        # 2. PARALLEL THUMB MODE (Miniatura Personalizada)
        if is_thumb:
            wm = await m.reply("⬇️ **Descargando para Miniatura...**")
            try:
                import time
                import random
                ts = int(time.time())
                rnd = random.randint(1000, 9999)
                # Determine extension
                ext = ".mp4"
                if m.video and m.video.file_name: _, ext = os.path.splitext(m.video.file_name)
                elif m.document and m.document.file_name: _, ext = os.path.splitext(m.document.file_name)
                
                dl_path = os.path.join("downloads", f"thumb_in_{cid}_{ts}_{rnd}{ext}")
                await m.download(file_name=dl_path)
                
                await wm.edit("📸 **Generando Miniatura...**")
                
                # Get Configured Second
                seek_time = conf.get('parallel_thumb_seek', 2)
                thumb_path = os.path.join("downloads", f"thumb_out_{cid}_{ts}_{rnd}.jpg")
                
                # Extract Thumb
                cmd = [
                    "ffmpeg", "-y", "-ss", str(seek_time),
                    "-i", dl_path, "-vframes", "1", "-q:v", "2", 
                    thumb_path
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
                )
                await process.wait()
                
                if os.path.exists(thumb_path):
                    await wm.edit("📤 **Enviando...**")
                    from tools_media import get_meta
                    w, h, dur = await get_meta(dl_path)
                    
                    caption = f"📸 **Miniatura Personalizada**\n⏱ Frame: `{seek_time}s`"
                    
                    try:
                        await c.send_video(
                            cid, dl_path, thumb=thumb_path, 
                            caption=caption, width=w, height=h, duration=dur
                        )
                    except:
                        await c.send_document(
                            cid, dl_path, thumb=thumb_path, caption=caption
                        )
                    
                    try: os.remove(thumb_path)
                    except: pass
                    
                else:
                    await wm.edit(f"⚠️ **Error:** No se pudo extraer miniatura en el segundo {seek_time}.")
                
                # Cleanup Input
                if os.path.exists(dl_path): os.remove(dl_path)
                try: await wm.delete()
                except: pass

            except Exception as e:
                print(f"Parallel Thumb Error: {e}")
                try: await wm.edit(f"❌ Error Miniatura: {e}")
                except: pass
            
            m.stop_propagation()
            return
                
# --- VIRAL SHORTS MUSIC HANDLER ---
@app.on_message((filters.video | filters.audio | filters.voice) & filters.private, group=3)
async def viral_handler(c, m):
    cid = m.chat.id
    conf = get_config(cid)
    
    # Intercept ONLY if mode is ON
    if conf.get('viral_mode'):
        # Save to DB
        ftype = 'video'
        fid = None
        
        if m.video:
            fid = m.video.file_id
            ftype = 'video'
        elif m.audio:
            fid = m.audio.file_id
            ftype = 'audio'
        elif m.voice:
             fid = m.voice.file_id
             ftype = 'voice'
        
        if fid:
            import random
            # Add random suffix to prevent exact millisecond collisions during mass-forwards
            item_id = f"{int(time.time()*1000)}_{random.randint(1000, 9999)}"
            
            item = {
                'id': item_id,
                'type': ftype,
                'file_id': fid,
                'date': int(time.time()),
                'user': cid,
                'caption': m.caption or ""
            }
            viral_music_db.append(item)
            # save_viral() -> Firebase
            asyncio.create_task(save_viral_item_fb(item))
            
            # Avoid sending a reply for EVERY item in a media group to prevent FloodWait crashes
            if not m.media_group_id:
                try:
                    await m.reply(f"✅ **Guardado en Catálogo Short/Music**\nID: `{item['id']}`", quote=True)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
            else:
                # Optionally, notify the console for media group items silently
                print(f"📦 Media group item '{item_id}' added to catalog silently.")
                
        m.stop_propagation()

# --- SMART TAGGER (NEW) ---
@app.on_message(filters.command(["fixwaifu"]) & filters.private)
async def fix_waifu_server_handler(c, m):
    """Comando de rescate para arreglar la instalación de Waifu2x en el servidor."""
    await m.reply("🛠 **Iniciando Auto-Reparación de Waifu2x...**\nBuscando el archivo perdido...")
    
    import os
    import shutil
    import stat
    
    target_dir = "bin/waifu2x"
    target_bin = os.path.join(target_dir, "waifu2x-ncnn-vulkan")
    found_path = None
    
    # 1. Buscar recursivamente en bin/
    for root, dirs, files in os.walk("bin"):
        if "waifu2x-ncnn-vulkan" in files:
            found_path = os.path.join(root, "waifu2x-ncnn-vulkan")
            break
            
    if not found_path:
        await m.reply("❌ Error: No encontré el archivo `waifu2x-ncnn-vulkan` en ninguna parte de la carpeta `bin/`.\n¿Seguro que subiste el ZIP descomprimido?")
        return

    # 2. Moverlo al lugar correcto (si no está ahí ya)
    try:
        if os.path.abspath(found_path) != os.path.abspath(target_bin):
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            
            # Mover archivo
            shutil.move(found_path, target_bin)
            await m.reply(f"📦 Archivo movido de:\n`{found_path}`\na:\n`{target_bin}`")
        else:
            await m.reply("✅ El archivo ya estaba en el lugar correcto.")

        # 3. Dar Permisos de Ejecución (+x)
        st = os.stat(target_bin)
        os.chmod(target_bin, st.st_mode | stat.S_IEXEC)
        await m.reply("🔑 **Permisos de ejecución concedidos.**\n\n✨ **¡Waifu2x debería funcionar ahora!** Pruébalo con una foto.")

    except Exception as e:
        await m.reply(f"❌ Error crítico moviendo/permisos: {e}")

# --- TAG HANDLERS ---
@app.on_message(filters.command(["tag", "rename"]) & filters.private)
async def tag_command_handler(c, m):
    """
    Comando /tag o /rename para analizar videos con IA
    sin descargar todo el archivo (Chunk Start).
    """
    if not m.reply_to_message or (not m.reply_to_message.video and not m.reply_to_message.document and not m.reply_to_message.photo):
        await m.reply("❌ **Uso:** Responde a un video/foto/archivo con `/tag`")
        return
    
    # Delegate to tool logic
    await run_tagger_logic(c, m)
    m.stop_propagation()
    return



# --- TAGGER VIDEO HANDLER ---
@app.on_message((filters.video | filters.document) & filters.private, group=4)
async def tagger_video_handler(c, m):
    """Intercepta videos cuando el modo Tagger está activo para Smart Tagging."""
    conf = get_config(m.chat.id)
    if conf.get('tagger_mode'):
        # Delegar a Smart Tagger (Logic)
        await run_tagger_logic(c, m)
        m.stop_propagation()
    else:
        m.continue_propagation()

# --- AI IMAGE ANALYZER (PHOTO HANDLER) ---
@app.on_message(filters.photo)
async def photo_analysis_handler(c, m):
    """Analiza fotos usando Gemini Vision (Auto) o SauceNAO (Manual)."""
    # Check if this is a reply to a specific command or if it's just a general image
    if m.reply_to_message:
         # If replying to a bot message that asked for something specific?
         pass
         
    conf = get_config(m.chat.id)
    cid = m.chat.id

    # --- EXCLUSIVE MODES CHECK (Mixer, Tagger, etc) ---
    if conf.get('video_mixer_mode') or conf.get('tagger_mode'):
        m.continue_propagation() # Let specific handlers (even if expecting video) deal with it or ignore
        return

    # --- WAIFUX2 MODE (Priority) ---
    if conf.get('waifux2_mode'):
        wm = await m.reply("✨ **Mejorando con Waifu2x...**\n_Esto puede tardar unos segundos..._")
        try:
             # Download
             dl_path = os.path.join("downloads", f"w2x_in_{cid}_{int(time.time())}.jpg")
             await m.download(file_name=dl_path)
             
             # Upscale
             from utils import waifu2x_upscale
             out_path = await asyncio.get_running_loop().run_in_executor(None, lambda: waifu2x_upscale(dl_path))
             
             if out_path and os.path.exists(out_path):
                 await m.reply_document(document=out_path, caption="✨ **Waifu2x Completo (x2)**")
                 try: os.remove(out_path)
                 except: pass
             else:
                 await wm.edit("❌ Error: Waifu2x falló.")
             
             if os.path.exists(dl_path): os.remove(dl_path)
             await wm.delete()
        except Exception as e:
             await wm.edit(f"❌ Error Waifu2x: {e}")
        
        m.stop_propagation()
        return

    # --- REDIRECT TO NANO BANANA ---
    if conf.get('ai_model_mode') == 'nano_banana':
        return await ai_chat_handler(c, m) # Hand off to drawing logic make sure ai_chat_handler is visible or imported

    cid = m.chat.id
    # Check rate limit (simpler for now)
    
    # Check if "Modo Portada" is active (SPECIAL FLOW)
    # This takes precedence over general AI analysis
    
    # Check simple state to avoid conflict with other specific flows if needed
    st = url_storage.get(cid)
    print(f"[DEBUG] Photo Analysis | CID: {cid} | State: {st}")

    # --- TAGGER MODE INTERCEPT ---
    if conf.get('tagger_mode'):
        # Delegar a Smart Tagger (Imagen/Video)
        await run_tagger_logic(c, m)
        m.stop_propagation()
        return
    
    # BLOCK IF IN CONFIG MODE
    if st and (st.get('ai_config_step') == 'wait_image' or st.get('ai_add_step')):
         m.stop_propagation()
         return

    if st and ('extract_step' in st or 'party_input_mode' in st or 'saucenao_mode' in st.get('config', {})):
         m.continue_propagation()
         return

    # Si hay caption, puede ser un comando, dejar pasar
    if m.caption and m.caption.startswith("/"):
        m.continue_propagation()
        return

    wm = await m.reply("🔍 **Analizando imagen...**")
    try:
        # Download photo
        dl_path = os.path.join("downloads", f"ai_img_{cid}_{int(time.time())}.jpg")
        await m.download(file_name=dl_path)
        
        # Ask AI with image
        # Get Config & Persona
        conf = get_config(cid)
        active_p = conf.get('active_persona', 'nsfw')
        
        # --- MANGA TRANSLATOR MODE ---
        if conf.get('translate_manga_mode'):
            try:
                # 1. Ask Gemini for Translation
                prompt = (
                    "ACT AS A PROFESSIONAL MANGA TRANSLATOR.\n"
                    "Translate ALL text in this image to SPANISH.\n"
                    "Format the output clearly by panels (e.g., 'Panel 1: ...', 'Panel 2: ...').\n"
                    "If there is SFX (Sound Effects), translate them in brackets [Boom].\n"
                    "Return ONLY the translated text. Do not add introductory conversational filler."
                )
                
                response = await asyncio.get_running_loop().run_in_executor(None, lambda: ask_gemini(
                    prompt, cid, dl_path, 
                    active_persona='formal', # Force formal/neutral for translation
                    user_rules=[], 
                    green_mode=False, 
                    focus_mode=False
                ))
                
                # 2. Extract Text
                txt = response if isinstance(response, str) else response.get('text', 'Error en traducción.')
                
                # 3. Send Result
                await wm.delete()
                await m.reply(f"🈚 **Traducción Manga:**\n\n{txt}", quote=True)
                
                # 4. Cleanup
                try: os.remove(dl_path)
                except: pass
                
                return # Stop here

            except Exception as e_trans:
                print(f"Manga Trans Error: {e_trans}")
                await wm.edit(f"❌ Error traduciendo: {e_trans}")
                return

        
        # Get Rules
        user_rules = await get_user_rules_fb(cid, persona_id=active_p)
        
        if not m.caption:
             # --- DUAL LENS MODE (Google + Yandex) ---
             await wm.edit("🕵️‍♂️ **Buscando en Google y Yandex...**\n_Abriendo navegadores..._")
             
             from google_lens import google_lens_screenshot
             from yandex_lens import yandex_lens_screenshot
             
             # Paths
             ts = int(time.time())
             out_google = os.path.join("downloads", f"lens_g_{cid}_{ts}.png")
             out_yandex = os.path.join("downloads", f"lens_y_{cid}_{ts}.png")
             
             # Run PARALLEL
             # We use return_exceptions=True to ensure one failure doesn't stop the other
             results = await asyncio.gather(
                 google_lens_screenshot(dl_path, out_google),
                 yandex_lens_screenshot(dl_path, out_yandex),
                 return_exceptions=True
             )
             
             # Process Results
             res_google = results[0] if isinstance(results[0], bool) else False
             res_yandex = results[1] if isinstance(results[1], bool) else False
             
             media_group = []
             
             # Google Result
             if res_google and os.path.exists(out_google):
                 from pyrogram.types import InputMediaPhoto
                 media_group.append(InputMediaPhoto(out_google, caption="🇺🇸 **Google Lens**"))
             
             # Yandex Result
             if res_yandex and os.path.exists(out_yandex):
                 from pyrogram.types import InputMediaPhoto
                 media_group.append(InputMediaPhoto(out_yandex, caption="🇷🇺 **Yandex Images** (Mejor NSFW)"))
             
             # Send
             if media_group:
                 await wm.delete()
                 if len(media_group) == 1:
                    # Single photo (reply_photo) because reply_media_group requires 2+ usually, 
                    # but pyrogram handles list of 1 ok? No, usually list of 1 acts as single.
                    # Safety check:
                    p = media_group[0].media
                    cpt = media_group[0].caption
                    await m.reply_photo(p, caption=cpt)
                 else:
                    await m.reply_media_group(media_group)
             else:
                 await wm.edit("❌ Fallaron ambas búsquedas (Timeouts o Captchas).")
             
             # Cleanup
             try:
                 if os.path.exists(out_google): os.remove(out_google)
                 if os.path.exists(out_yandex): os.remove(out_yandex)
                 if os.path.exists(dl_path): os.remove(dl_path)
             except: pass
             
             return

        # Ask AI with image (If caption exists)
        user_text = m.caption 
        
        response = await asyncio.get_running_loop().run_in_executor(None, lambda: ask_gemini(
            user_text, cid, 
            image_paths=[dl_path], # Pass as list to new arg
            active_persona=active_p, 
            user_rules=user_rules, 
            green_mode=conf.get('ai_green_mode', False), 
            focus_mode=conf.get('ai_focus_mode', False)
        ))
        
        # Store for SauceNAO button
        sauce_id = f"sauce_{cid}_{int(time.time())}"
        url_storage[sauce_id] = dl_path
        
        # Prepare Button
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Buscar con SauceNAO", callback_data=f"ai_sauce|{sauce_id}")]])
        
        if isinstance(response, dict) and response.get('action') == 'TRIGGER_TOOL' and response.get('tool') == 'sauce':
             # AI wants to use SauceNAO. Execute it automatically.
             txt = response.get('text')
             # Append status
             if txt: txt += "\n\n🔍 **Ejecutando búsqueda automática (SauceNAO)...**"
             else: txt = "🔍 **La IA sugiere buscar la fuente. Ejecutando SauceNAO...**"
             
             await wm.edit(txt)
             
             # Execute SauceNAO Logic (from utils)
             try:
                 results = await search_saucenao(dl_path, limit=3)
                 s_txt = format_saucenao_results(results)
                 
                 final_txt = f"{txt}\n\n{s_txt}"
                 # Limit length
                 if len(final_txt) > 4000: final_txt = final_txt[:4000] + "..."
                 
                 await wm.delete()
                 await m.reply(final_txt, reply_markup=kb, quote=True, disable_web_page_preview=True)
                 return
                 
             except Exception as e_sauce:
                 print(f"❌ Auto-Sauce Error: {e_sauce}")
                 await wm.delete()
                 await m.reply(f"{txt}\n\n❌ Error en búsqueda automática: {e_sauce}", reply_markup=kb)
                 return

        # --- SAVE REACTION TRIGGER (NEW) ---
        if isinstance(response, dict) and response.get('action') == 'TRIGGER_TOOL' and response.get('tool') == 'save_reaction':
             target_cat = response.get('category')
             
             # Get File ID
             fid = m.photo.file_id if m.photo else (m.document.file_id if m.document else None)
             ftype = 'photo' if m.photo else 'document'
             
             if fid and target_cat:
                 # Save (AWAIT to ensure it is written before we verify or user checks)
                 await save_persona_image(active_p, 'default', target_cat, {'id': fid, 'type': ftype})
                 
                 # Cache update
                 if active_p not in AVATAR_KEYS_CACHE: AVATAR_KEYS_CACHE[active_p] = set()
                 AVATAR_KEYS_CACHE[active_p].add(target_cat)
                 
                 # Fetch actual count for confirmation
                 from firebase_service import get_persona_images
                 curr_imgs = await get_persona_images(active_p, 'default', target_cat)
                 c_count = len(curr_imgs)
                 
                 # Translate
                 cat_disp = TRANS.get(target_cat, target_cat.replace('_', ' ').title())
                 
                 response_txt = response.get('text', "Entendido.")
                 
                 await wm.delete()
                 await m.reply(
                     f"{response_txt}\n\n✅ **Imagen Guardada**\n👤 **Cuerpo:** `{active_p}`\n📂 **Categoría:** `{cat_disp} ({c_count})`",
                     reply_markup=kb,
                     quote=True
                 )
                 return
             else:
                 await m.reply("❌ No pude guardar la imagen (Falta ID o Categoría).")
        
        # Normal Text Response
        txt = response if isinstance(response, str) else response.get('text', 'Imagen analizada.')
        
        # --- LOGICA EXTENDER (SPLIT) ---
        delimiter = "===EXTENDED==="
        if delimiter in txt:
            parts = txt.split(delimiter)
            summary = parts[0].strip()
            # Reconstruct clean full text with exactly one blank line
            full_text = f"{summary}\n\n{parts[1].strip()}"
            
            # Store full text AND sauce_id
            ext_id = f"ext_{cid}_{int(time.time())}"
            url_storage[ext_id] = {'full_text': full_text, 'sauce_id': sauce_id}
            
            # Button
            kb_ext = InlineKeyboardMarkup([
                [InlineKeyboardButton("📜 Extender Mensaje", callback_data=f"ai_extend|{ext_id}")],
                [InlineKeyboardButton("🔍 Buscar con SauceNAO", callback_data=f"ai_sauce|{sauce_id}")]
            ])
            
            await wm.delete()
            await m.reply(summary, reply_markup=kb_ext, quote=True)
            return

        if conf.get('voice_mode'):
            try:
                audio_f = await generate_tts_audio(txt, active_p)
                if audio_f:
                    await m.reply_voice(audio_f)
                    os.remove(audio_f)
            except Exception as e_tts:
                print(f"TTS Error: {e_tts}")

        # Fix: Append to inline_keyboard list, not the object
        # Fix: Use 'dl_path' instead of undefined 'path'
        # Note: dl_path is local file, waifu2x needs reply or file. 
        # But callback 'waifu2x' usually expects a message reply. 
        # The button logic in callback_handler uses 'download_media' on the message, so we just need a trigger.
        # However, passing path string in callback_data might be too long and invalid if it's a file path.
        # Actually, standard 'waifu2x' callback handles message reply.
        # Let's just pass "auto" or empty.
        
        kb.inline_keyboard.append([InlineKeyboardButton("✨ Mejorar (Waifu2x)", callback_data="w2x_manual")])
        await wm.delete()
        await m.reply(txt, reply_markup=InlineKeyboardMarkup(kb), quote=True)
        
    except Exception as e:
        # Solo mostrar error si preview_mode está ON (o sea wm existe)
        # Si no, fallar silenciosamente o loggear en consola.
        if wm:
             await wm.edit(f"❌ Error al analizar: {e}")
        else:
             print(f"❌ Error silencioso (Preview OFF): {e}")


@app.on_message(filters.text & (filters.regex("http") | filters.regex("www") | filters.regex("twisted-brody-manga-flow")))
async def analyze(c, m):
    cid = m.chat.id
    import re # FIX: Ensure re is available locally since it's used/imported later in this function
    
    # --- CONFLICT FIX: AI vs AUTO-DL ---
    # Si el mensaje tiene más de 3 palabras, asumimos que es una conversación para la IA.
    # Excepción: Si es un link de Manga Flow (usualmente largo pero sin espacios)
    msg_words = m.text.strip().split()
    # FIX: Allow massive link lists
    # If len > 3, check if it's mostly URLs
    urls_found = re.findall(r"(https?://\S+)", m.text)
    
    if len(msg_words) > 3:
        # If we have many URLs (e.g. almost as many as words), it is a link list, NOT chat.
        # Let's say if we have at least 2 URLs and they make up > 30% of words?
        # Or simpler: if we have URLs, we process them.
        # But we don't want to break "Can you download this http://video.com?" (7 words, 1 link) -> Chat ID detection usually handles this?
        # Actually, analyze IS the download handler.
        # Original logic: > 3 words -> Chat.
        # New logic: If > 3 words BUT we have found multiple URLs (>= 2), we assume it's a batch request.
        if len(urls_found) < 2: 
             m.continue_propagation()
             return

    if not can_download(cid)[0]: return await m.reply("⚠️ Espera a que terminen tus descargas.")
    # url_storage.pop(cid, None) # Removido para permitir múltiples links concurrentes
    match = re.search(r"(https?://\S+)", m.text)
    if not match: return
    l_u = limpiar_url(match.group(1))
    
    # Generar ID único BASE para este grupo de links (microsegundos + random para evitar colisiones en reenvíos masivos)
    base_link_id = int(time.time_ns() // 1000) + random.randint(10000, 99999)
    
    # Extract ALL URLs
    urls = re.findall(r"(https?://\S+)", m.text)
    unique_urls = list(set(urls)) # Deduplicate
    
    # --- AUTO-EXPAND HENTAILA PLAYLISTS ---
    expanded_urls = []
    from downloader import get_all_hentaila_episodes
    for u in unique_urls:
        if "hentaila.com/media/" in u:
            # Buscar automáticamente si hay más episodios en la página
            eps = await get_all_hentaila_episodes(u)
            expanded_urls.extend(eps)
        else:
            expanded_urls.append(u)
            
    # Mantener orden y eliminar duplicados (por si envió un link que el extractor ya sacó)
    seen = set()
    unique_urls = [x for x in expanded_urls if not (x in seen or seen.add(x))]
    
    # Security Limit (increased to 1000 as requested)
    if len(unique_urls) > 1000:
        await m.reply(f"⚠️ **Demasiados enlaces.** procesando los primeros 1000...")
        unique_urls = unique_urls[:1000]

    multi_url_count = len(unique_urls)
    if multi_url_count > 1:
        await m.reply(f"🔗 **Hay {multi_url_count} enlaces detectados.** Procesando todos en lote...", quote=True)

    # Process each URL concurrently
    tasks = []
    for i, raw_url in enumerate(unique_urls):
        clean_url = limpiar_url(raw_url)
        # Unique ID for EACH link: Base + Index
        link_id_suffix = f"{base_link_id}_{i}"
        
        # Launch Task
        tasks.append(asyncio.create_task(process_url_flow(c, m, clean_url, link_id_suffix, multi_url_count)))
        
        # Pequeno delay para no saturar inmediatamente el loop o API rates si son muchos
        if i > 0: await asyncio.sleep(1.5)

    if multi_url_count > 1:
        results = await asyncio.gather(*tasks)
        
        # Mapear cada URL a sus mensajes resultantes
        url_to_msgs = {}
        all_sent_msgs = []
        for url, r in zip(unique_urls, results):
            if r:
                msgs_list = r if isinstance(r, list) else [r]
                url_to_msgs[url] = msgs_list
                all_sent_msgs.extend(msgs_list)
                
        # Organizar y reenviar en el orden original de los links (agrupando parejas JAV)
        if len(all_sent_msgs) > 1:
            org_msg = await m.reply("✅ **Descargas completas.** Organizando capítulos en orden...", quote=True)
            
            def extract_jav_code(url):
                u = url.lower()
                u = re.sub(r'https?://[^/]+/', '', u)
                match = re.search(r'([a-z0-9]+(?:-[a-z0-9]+)*-\d+)', u)
                if match:
                    return match.group(1)
                match_nodash = re.search(r'([a-z]+)(\d+)', u)
                if match_nodash:
                    return f"{match_nodash.group(1)}-{match_nodash.group(2)}"
                return None

            groups = {}
            group_order = []
            for url in unique_urls:
                code = extract_jav_code(url)
                if code:
                    if code not in groups:
                        groups[code] = []
                        group_order.append(code)
                    groups[code].append(url)
                else:
                    groups[url] = [url]
                    group_order.append(url)

            sorted_urls = []
            for key in group_order:
                if key in groups:
                    sorted_urls.extend(groups.pop(key))

            # Borrar los desordenados
            msg_ids_to_delete = [msg.id for msg in all_sent_msgs]
            try: await c.delete_messages(m.chat.id, msg_ids_to_delete)
            except: pass
            
            # Reenviar en el orden agrupado
            for url in sorted_urls:
                msgs = url_to_msgs.get(url, [])
                for msg in msgs:
                    try:
                        await msg.copy(m.chat.id, reply_to_message_id=m.id)
                        await asyncio.sleep(1.5)
                    except Exception as e:
                        print(f"Error copiando mensaje ordenado para {url}: {e}")
                        
            try: await org_msg.delete()
            except: pass

async def process_url_flow(c, m, l_u, link_id_suffix, multi_url_count=1):
    """
    Procesa un enlace individual (Audio, Video, Galeria, Manga, etc).
    Encapsulado para soportar Multi-Link.
    """
    cid = m.chat.id
    import re
    from pyrogram.errors import FloodWait
    
    # Throttle Analysis to prevent FloodWait loop
    async with SEM_ANALYSIS:
        # Generar ID único para este link
        # Usamos el suffix pasado o uno nuevo si no hay
        if link_id_suffix:
            link_id = hex(int(link_id_suffix.split('_')[0]) + int(link_id_suffix.split('_')[1]))[2:]
        else:
            link_id = hex(int(time.time_ns() // 1000) + random.randint(10000, 99999))[2:]

        storage_key = f"{cid}_{link_id}"

    # --- AUTO-MP3 CHECK ---
    conf = get_config(cid)
    if conf.get('fmt') == 'mp3':
        wm = None # Silent Analysis
        # wm = await m.reply(f"🎵 **Analizando MP3...**\n`{l_u}`", quote=True)
        url_info = {'url': l_u, 'titulo': "Audio Auto-MP3", 'fast_enabled': conf.get('fast_enabled', True)}
        res = await procesar_descarga(c, cid, l_u, "mp3", url_info, m, context_config=conf)
        try: await wm.delete()
        except: pass
        return res

    # 1. MANGA FLOW CHECK
    if "twisted-brody-manga-flow" in l_u:
        wm = None
        if conf.get('preview_mode', True):
             wm = None # Silent Analysis for Manga
             # wm = await m.reply("⬇️ **Analizando Manga...**", quote=True)
        try:
            if "#manga/" in l_u: raw_id = l_u.split("#manga/")[1]
            elif "/manga/" in l_u: raw_id = l_u.split("/manga/")[1]
            else:
                 await wm.edit("❌ Error: ID no encontrado en el link.")
                 return
            
            match_id = re.match(r'^([a-zA-Z0-9]+)', raw_id)
            mi_l = match_id.group(1) if match_id else raw_id.split("?")[0].strip()

            await show_manga_menu(c, m, mi_l, wait_msg=wm)
        except Exception as e:
            if wm: await wm.edit(f"❌ Error Manga: {e}")
        return

    # 2. GALLERY CHECK (X, Pinterest, Instagram)
    gallery_sent = False
    if any(x in l_u for x in ['twitter.com', 'x.com', 'pinterest.com', 'instagram.com', 'facebook.com']):
        wm_gal = None
        try:
            c_file = sel_cookie(l_u)
            async with get_user_semaphore(cid, False, get_config(cid).get('max_downloads', 'default')):
                res_gal = await asyncio.get_running_loop().run_in_executor(None, lambda: descargar_galeria(l_u, c_file))
            
            if len(res_gal) == 3: paths, tmp, metadata_text = res_gal
            else: paths, tmp = res_gal; metadata_text = ""
            
            if paths:
                conf = get_config(cid)
                is_doc = conf.get('doc_mode', False)
                is_group = conf.get('group_mode', False)
                
                if conf.get('preview_mode', True):
                    cnt = len(paths)
                    txt_n = "imagen" if cnt == 1 else "imágenes"
                    wm_gal = await m.reply(f"📁 Encontré un álbum de {cnt} {txt_n}", quote=True)
                    # Small delay to let user read
                    await asyncio.sleep(2)
                    try: await wm_gal.edit(f"📁 Enviando {txt_n}... `{cnt}/{cnt}` 📤")
                    except: pass
                
                if is_doc:
                    for p in paths:
                        try: await c.send_document(cid, p, reply_to_message_id=m.id)
                        except: pass
                else:
                    if is_group and len(paths) > 1:
                        # ALBUM LOGIC (Chunked)
                        album_caption = ""
                        try:
                             # Silent analysis (no edit)
                             if not metadata_text or len(metadata_text) < 2:
                                 album_caption = "" 
                             else:
                                 from ai_service import translate_text_pure
                                 tags_found = re.findall(r"#[^\s]+", metadata_text)
                                 tags_str = " ".join(tags_found)
                                 text_only = re.sub(r"#[^\s]+", "", metadata_text).strip()
                                 final_title = ""
                                 raw_desc = ""
                                 if text_only:
                                     lines = text_only.split('\n')
                                     raw_title = lines[0].strip()[:100]
                                     if len(lines) > 1: raw_desc = "\n".join(lines[1:]).strip()[:800]
                                     trans_title = await asyncio.get_running_loop().run_in_executor(None, lambda: translate_text_pure(raw_title, "es"))
                                     final_title = f"**{trans_title if trans_title else raw_title}**"
                                 
                                 caption_parts = []
                                 if final_title: caption_parts.append(final_title)
                                 if raw_desc: caption_parts.append(raw_desc)
                                 if tags_str: caption_parts.append(tags_str)
                                 album_caption = "\n\n".join(caption_parts)
                        except Exception as e_ai:
                            print(f"AI Album Fail: {e_ai}")
                            album_caption = ""

                        from pyrogram.types import InputMediaPhoto
                        
                        # Batching logic 10 items max per album
                        batch_size = 10
                        for i in range(0, len(paths), batch_size):
                            chunk = paths[i:i + batch_size]
                            media = []
                            for j, p in enumerate(chunk):
                                # Put caption only on the VERY first message of the sequence
                                cap = album_caption if (i == 0 and j == 0) else ""
                                media.append(InputMediaPhoto(p, caption=cap))
                            
                            try: await c.send_media_group(cid, media, reply_to_message_id=m.id)
                            except: 
                                 for p in chunk: await c.send_photo(cid, p, reply_to_message_id=m.id)
                            
                            # Small delay to ensure order
                            await asyncio.sleep(1)
                    else:
                        # INDIVIDUAL LOGIC
                        for i, p in enumerate(paths):
                            caption = ""
                            try:
                                # Silent analysis (no edit)
                                if not metadata_text or len(metadata_text) < 2:
                                    caption = ""
                                else:
                                    from ai_service import translate_text_pure
                                    tags_found = re.findall(r"#[^\s]+", metadata_text)
                                    tags_str = " ".join(tags_found)
                                    text_only = re.sub(r"#[^\s]+", "", metadata_text).strip()
                                    final_title = ""
                                    raw_desc = ""
                                    if text_only:
                                        lines = text_only.split('\n')
                                        raw_title = lines[0].strip()[:100]
                                        if len(lines) > 1:
                                            raw_desc = "\n".join(lines[1:]).strip()[:800]
                                            if conf.get('lang') == 'es':
                                                raw_desc = await asyncio.get_running_loop().run_in_executor(None, lambda: translate_text_pure(raw_desc, "es"))
                                        
                                        if conf.get('lang') == 'es':
                                            trans_title = await asyncio.get_running_loop().run_in_executor(None, lambda: translate_text_pure(raw_title, "es"))
                                            final_title = f"**{trans_title if trans_title else raw_title}**"
                                        else: final_title = f"**{raw_title}**"

                                    final_tags = tags_str # Simplified for brevity, logic remains same
                                    caption_parts = []
                                    if final_title: caption_parts.append(final_title)
                                    if raw_desc: caption_parts.append(raw_desc)
                                    if final_tags: caption_parts.append(final_tags)
                                    caption = "\n\n".join(caption_parts)
                            except: caption = ""
                            try: await c.send_photo(cid, p, caption=caption, reply_to_message_id=m.id)
                            except: pass
                
                gallery_sent = True
                import shutil
                try: shutil.rmtree(tmp)
                except: pass
                if wm_gal: await wm_gal.delete()

        except Exception as e:
            # Silent fail for gallery, verify video next
            pass

    # 3. NORMALIZAR FACEBOOK
    if "facebook.com" in l_u or "fb.watch" in l_u:
        l_u = await resolver_url_facebook(l_u)

    wm = None
    wm = None
    if conf.get('preview_mode', True):
        # Silent Analysis Standard
        pass
        # try:
        #     wm = await m.reply(f"⬇️ **Analizando...**\n`{l_u}`", quote=True)
        # except FloodWait as e:
        #     print(f"🌊 FloodWait in Analysis: Sleeping {e.value}s")
        #     await asyncio.sleep(e.value + 2)
        #     wm = await m.reply(f"⬇️ **Analizando...**\n`{l_u}`", quote=True)
        # except Exception as e:
        #     print(f"❌ Msg Error: {e}")
        #     return

    # 4. JAV TURBO SNIFFER
    if any(x in l_u for x in ['jav', 'hpjav', 'missav', 'javtrailers', '7mmtv']):
        try:
            async with SEM_ANALYSIS:
                links_tuple = await asyncio.get_running_loop().run_in_executor(None, lambda: extraer_jav_directo(l_u))
            cover_url = None
            # Manejar compatibilidad
            if isinstance(links_tuple, tuple):
                if len(links_tuple) == 3:
                    links, page_title, cover_url = links_tuple
                else:
                    links, page_title = links_tuple
            else:
                links, page_title = links_tuple, "JAV Video"
                
            if links:
                url_storage[storage_key] = {'url': l_u, 'id': f"jav_{int(time.time())}", 'titulo': page_title, 'html_links_data': links, 'cover_url': cover_url}
                
                # AUTO QUALITY LOGIC PARA JAV
                q_auto = conf.get('q_auto')
                if q_auto in ['max', 'min']:
                    if wm: await wm.edit(f"⚙️ **Auto-Calidad ({q_auto.upper()}):** Extrayendo automáticamente...")
                    d_st = url_storage[storage_key]
                    d_st['fast_enabled'] = conf.get('fast_enabled', True)
                    local_conf = conf.copy()
                    
                    # El mejor enlace (m3u8) siempre está en index 0 gracias a jav_extractor
                    # Para 'min' podríamos usar el último, pero usualmente m3u8 es preferido en ambos, 
                    # así que descargaremos html_0_link_id
                    target_q = f"html_0"
                    
                    res = await procesar_descarga(c, cid, d_st['url'], target_q, d_st, m, context_config=local_conf)
                    if wm:
                        try: await wm.delete()
                        except: pass
                    return res

                # Si NO hay Auto-Quality, mostrar botones
                btns = []
                for i, l in enumerate(links[:8]):
                    btns.append([InlineKeyboardButton(f"🚀 {l['res']}", callback_data=f"dl|html_{i}_{link_id}")])
                btns.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
                
                if wm: await wm.delete()
                await m.reply(f"🎬 **{page_title}**", reply_markup=InlineKeyboardMarkup(btns), quote=True)
                return
        except: pass

    # 4b. EPORNER VIDEO SNIFFER
    if "eporner.com" in l_u and "/video-" in l_u:
        try:
            from downloader import get_eporner_links, find_best_quality_index, find_worst_quality_index, find_fixed_quality_index
            
            async with SEM_ANALYSIS:
                page_title, links = await get_eporner_links(l_u)
            
            if links:
                eporner_id = "video"
                match_id = re.search(r'/video-([a-zA-Z0-9]+)/', l_u)
                if match_id:
                    eporner_id = match_id.group(1)
                
                final_id = f"eporner_{eporner_id}"
                
                url_storage[storage_key] = {
                    'url': l_u,
                    'id': final_id,
                    'titulo': page_title,
                    'html_links_data': links
                }
                
                # AUTO QUALITY LOGIC
                q_auto = conf.get('q_auto')
                if q_auto in ['max', 'min'] or q_auto in ['4320', '2160', '1440', '1080', '720', '480', '360', '240', '144']:
                    lbl_q = q_auto if q_auto in ['max', 'min'] else f"{q_auto}p"
                    if wm: await wm.edit(f"⚙️ **Auto-Calidad ({lbl_q.upper()}):** Extrayendo automáticamente...")
                    d_st = url_storage[storage_key]
                    d_st['fast_enabled'] = conf.get('fast_enabled', True)
                    local_conf = conf.copy()
                    
                    if q_auto == 'max':
                        best_idx = find_best_quality_index(links)
                        target_q = f"html_{best_idx}"
                    elif q_auto == 'min':
                        worst_idx = find_worst_quality_index(links)
                        target_q = f"html_{worst_idx}"
                    else:
                        target_res = int(q_auto)
                        fixed_idx = find_fixed_quality_index(links, target_res)
                        target_q = f"html_{fixed_idx}"
                        
                    res = await procesar_descarga(c, cid, d_st['url'], target_q, d_st, m, context_config=local_conf)
                    if wm:
                        try: await wm.delete()
                        except: pass
                    return res
                
                # Multi-URL handling (auto-download best if in batch)
                if multi_url_count > 1:
                    best_idx = find_best_quality_index(links)
                    target_q = f"html_{best_idx}"
                    d_st = url_storage[storage_key]
                    d_st['fast_enabled'] = conf.get('fast_enabled', True)
                    local_conf = conf.copy()
                    
                    asyncio.create_task(procesar_descarga(c, cid, d_st['url'], target_q, d_st, m, context_config=local_conf))
                    return
                
                # Si NO hay Auto-Quality, mostrar botones (separamos h264 y AV1)
                btns = []
                for i, l in enumerate(links):
                    if l['codec'].lower() == 'h264':
                        btns.append([InlineKeyboardButton(f"🚀 {l['res']}", callback_data=f"dl|html_{i}_{link_id}")])
                
                has_h264 = any(l['codec'].lower() == 'h264' for l in links)
                has_av1 = any(l['codec'].lower() == 'av1' for l in links)
                if has_h264 and has_av1:
                    btns.append([InlineKeyboardButton("─── CÓDEC AV1 (Menor Peso) ───", callback_data="ignore")])
                    
                for i, l in enumerate(links):
                    if l['codec'].lower() == 'av1':
                        btns.append([InlineKeyboardButton(f"🚀 {l['res']}", callback_data=f"dl|html_{i}_{link_id}")])
                btns.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
                
                if wm: await wm.delete()
                await m.reply(f"🎬 **{page_title}**", reply_markup=InlineKeyboardMarkup(btns), quote=True)
                return
        except Exception as e_ep:
            print(f"❌ Eporner Sniffer Error: {e_ep}")

    # 5. DIRECT SITES & EPORNER FIX
    eporner_id = None
    is_direct = any(x in l_u for x in ['hentaila.com', 'fireload.com', 'mediafire.com', 'yourupload.com', 'mp4upload.com', 'rule34video.com/get_file/', 'xhamster.com', 'xhcdn.com'])
    
    if "eporner.com" in l_u and "/dload/" in l_u:
        is_direct = True
        try:
            # URL format: .../dload/VIDEO_ID/...
            parts = l_u.split('/dload/')
            if len(parts) > 1:
                eporner_id = parts[1].split('/')[0]
        except: pass

    # Surrit Direct Check (Fix for ID "video" collision)
    surrit_id = None
    if "surrit.com" in l_u and ".m3u8" in l_u:
        is_direct = True
        try:
            # URL format: https://surrit.com/UUID/quality/video.m3u8
            # Regex for UUID
            match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', l_u)
            if match:
                surrit_id = match.group(1)
        except: pass

    if not is_direct and re.search(r'\.(mp4|mkv|webm|avi|mov)(/|\?|$)', l_u, re.I): is_direct = True

    if is_direct:
        # Use Eporner/Surrit ID if available, otherwise fallback to timestamp + link_id_suffix to avoid collision
        if eporner_id:
            final_id = f"eporner_{eporner_id}"
        elif surrit_id:
            final_id = f"surrit_{surrit_id}"
        else:
            final_id = f"direct_{link_id_suffix}"
            
        print(f"DEBUG: Detect: Ep={eporner_id} Su={surrit_id} | Final: {final_id}")
        
        url_storage[storage_key] = {'url': l_u, 'id': final_id, 'titulo': "Enlace Directo"}
        # KEY FIX: Button must use 'link_id' (HEX) so CallbackHandler can find the storage entry.
        # We pass 'direct' as quality placeholder which matches existing handler logic.
        conf = get_config(m.chat.id)
        if not conf.get('ask_direct', True) or multi_url_count > 1:
            if wm: await wm.delete()
            # Se eliminó la restricción de preview_mode = False para multi_url_count a petición del usuario
            if multi_url_count > 1:
                conf = conf.copy()
            
            dl_msg = m
            return await procesar_descarga(c, m.chat.id, l_u, 'direct', url_storage[storage_key], dl_msg, context_config=conf)

        btns = [[InlineKeyboardButton("⬇️ Descargar Ahora", callback_data=f"dl|direct_{link_id}")], [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]]
        if wm: await wm.delete()
        await m.reply(f"📦 **Archivo Detectado**", reply_markup=InlineKeyboardMarkup(btns), quote=True)
        return

    # 6. YT-DLP STANDARD
    try:
        y_o = {
            'quiet': True, 
            'force_ipv4': False, 
            'nocheckcertificate': True, 
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'
            }
        }
        
        # Agregar Referer e impersonación dinámicos para MissAV / Surrit / xhand / xhamster
        if "surrit.com" in l_u or "missav" in l_u:
            y_o['http_headers']['Referer'] = 'https://missav.ws/'
            y_o['extractor_args'] = {'generic': ['impersonate=chrome']}
        elif "xhand.net" in l_u or "xhamster.com" in l_u:
            y_o['http_headers']['Referer'] = 'https://xhand.net/' if "xhand.net" in l_u else 'https://es.xhamster.com/'
            y_o['http_headers']['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            y_o['extractor_args'] = {'generic': ['impersonate=chrome']}
            
        c_file = sel_cookie(l_u)
        if c_file: 
            y_o['cookiefile'] = c_file

        y_i = None
        last_err = None
        
        # Determinar max_attempts (2 para X/Twitter/Eporner, 30 para otros)
        max_attempts = 2 if any(x in l_u for x in ['twitter.com', 'x.com', 'eporner.com']) else 30
        
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"🔄 [YT-DLP Standard] Intento de análisis {attempt}/{max_attempts} con cookies...")
                async with SEM_ANALYSIS:
                    y_i = await asyncio.get_running_loop().run_in_executor(None, lambda: yt_dlp.YoutubeDL(y_o).extract_info(l_u, download=False))
                if y_i:
                    print(f"✅ [YT-DLP Standard] Intento {attempt} exitoso!")
                    break
            except Exception as ex:
                last_err = ex
                print(f"⚠️ [YT-DLP Standard] Intento {attempt} falló: {ex}")
                if attempt < max_attempts:
                    await asyncio.sleep(2)
                
        if not y_i:
            raise last_err if last_err else Exception("No se pudo extraer información del video tras múltiples intentos.")

        if y_i and 'entries' in y_i:
            # MULTI-VIDEO HANDLING (Twitter/X Albums)
            if any(x in l_u for x in ['twitter.com', 'x.com']):
                entries = y_i['entries']
                count = len(entries)
                if count > 1:
                    if wm: await wm.edit(f"🎬 **Álbum Twitter detectado ({count} videos).**\n⬇️ Descargando todos...")
                    else: await m.reply(f"🎬 **Álbum Twitter detectado ({count} videos).**\n⬇️ Descargando todos...", quote=True)
                    
                    tw_results = []
                    for idx, entry in enumerate(entries):
                        # Construct minimal info for each video
                        # FIX: Prefer 'url' -> 'formats'[best] -> 'webpage_url'
                        target_url = entry.get('url')
                        
                        # Extra check for formats if url is None (Common in some playlist extractions)
                        if not target_url and entry.get('formats'):
                            # Intelligent Format Selection for Twitter
                            # 1. Look for Best Format with BOTH Video and Audio
                            best_merged = None
                            for f in entry['formats']:
                                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                                    best_merged = f
                            
                            # 2. Look for M3U8 (Master Playlist)
                            best_m3u8 = None
                            for f in entry['formats']:
                                if 'm3u8' in f.get('url', '') or f.get('ext') == 'm3u8':
                                    best_m3u8 = f
                            
                            if best_merged:
                                target_url = best_merged.get('url')
                            elif best_m3u8:
                                target_url = best_m3u8.get('url')
                            else:
                                # Fallback to last (highest quality, risk of video-only) if nothing else
                                try:
                                    best_fmt = entry['formats'][-1]
                                    target_url = best_fmt.get('url')
                                except: pass
                            
                        # Debug Log
                        print(f"🔍 [Twitter Debug] Entry {idx}: ID={entry.get('id')} | URL={target_url}")
                        
                        if not target_url: target_url = entry.get('webpage_url', l_u)

                        sub_info = {
                            'url': target_url,
                            'id': entry.get('id'),
                            'titulo': f"{entry.get('title', 'Video')} ({idx+1}/{count})",
                            'uploader': entry.get('uploader'),
                            'uploader_url': entry.get('uploader_url')
                        }
                        
                        # Auto-download BEST quality for albums to avoid menu spam
                        # Using slight delay to avoid floodwait on start
                        res_tw = await procesar_descarga(c, cid, sub_info['url'], "best", sub_info, m, context_config=conf)
                        if res_tw: 
                            if isinstance(res_tw, list): tw_results.extend(res_tw)
                            else: tw_results.append(res_tw)
                        await asyncio.sleep(1.5)
                    
                    if wm:
                        try: await wm.delete()
                        except: pass
                    return tw_results
                else:
                    y_i = entries[0]
            else:
                # Default behavior for other sites (take first)
                y_i = y_i['entries'][0]
        
        y_b, y_f = [], []
        formats = y_i.get('formats', [])
        for fl in formats:
            hv = fl.get('height')
            if hv and hv not in y_f:
                y_f.append(hv)
                label = f"{fl.get('width', '???')}x{hv}" if fl.get('width') else f"{hv}p"
                f_size = fl.get('filesize') or fl.get('filesize_approx')
                if not f_size:
                    tbr = fl.get('tbr') or ((fl.get('vbr') or 0) + (fl.get('abr') or 0))
                    dur = y_i.get('duration') or fl.get('duration')
                    if tbr and dur: f_size = (tbr * 1024 * dur) / 8
                
                if f_size:
                    from utils import format_bytes
                    label += f" ({format_bytes(f_size)})"
                y_b.append([InlineKeyboardButton(f"🎬 {label}", callback_data=f"dl|{hv}_{link_id}")])
        
        if not y_b and formats:
             if next((f for f in reversed(formats) if f.get('vcodec') != 'none'), None):
                 y_b.append([InlineKeyboardButton("🎬 Calidad Única / Best", callback_data=f"dl|best_{link_id}")])

        y_b.append([InlineKeyboardButton("🎵 Audio MP3", callback_data=f"dl|mp3_{link_id}")])
        y_b.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
        
        url_info = {'url': l_u, 'id': y_i.get('id'), 'titulo': y_i.get('title')}
        if 'surrit.com' in l_u and str(y_i.get('id')) in ['playlist', 'video']:
             match_uuid = re.search(r'surrit\.com/([a-zA-Z0-9-]+)', l_u)
             if match_uuid: url_info['id'] = match_uuid.group(1)

        url_storage[storage_key] = url_info

        # AUTO QUALITY LOGIC
        q_auto = conf.get('q_auto')
        if q_auto in ['max', 'min'] or q_auto in ['1080', '720', '480', '360', '240']:
            target_q = None
            if y_f:
                start_l = sorted([int(x) for x in y_f])
                if q_auto == 'max': 
                    target_q = str(start_l[-1])
                elif q_auto == 'min': 
                    target_q = str(start_l[0])
                else:
                    target_res = int(q_auto)
                    below = [x for x in start_l if x <= target_res]
                    if below:
                        target_q = str(below[-1])
                    else:
                        target_q = str(start_l[0])
            else:
                 if q_auto == 'max': target_q = "best"
                 else: target_q = "best"
            
            if target_q:
                lbl_q = q_auto if q_auto in ['max', 'min'] else f"{q_auto}p"
                if wm: await wm.edit(f"⚙️ **Auto-Calidad ({lbl_q.upper()}):** {target_q}p")
                d_st = url_storage[storage_key]
                d_st['fast_enabled'] = conf.get('fast_enabled', True)
                local_conf = conf.copy()
                # Se eliminó local_conf['preview_mode'] = False a petición del usuario
                asyncio.create_task(procesar_descarga(c, cid, d_st['url'], target_q, d_st, m, context_config=local_conf))
                if wm:
                    try: await wm.delete()
                    except: pass
                return

        if multi_url_count > 1:
            if wm:
                try: await wm.delete()
                except: pass
            target_q = str(sorted([int(x) for x in y_f])[-1]) if y_f else "best"
            d_st = url_storage[storage_key]
            d_st['fast_enabled'] = conf.get('fast_enabled', True)
            local_conf = conf.copy()
            # Se eliminó local_conf['preview_mode'] = False a petición del usuario
            asyncio.create_task(procesar_descarga(c, cid, d_st['url'], target_q, d_st, m, context_config=local_conf))
            return

        if wm: await wm.delete()
        await m.reply(f"🎬 **{y_i.get('title', 'Video Detectado')}**", reply_markup=InlineKeyboardMarkup(y_b), quote=True)
    except Exception as e:
        # TIKTOK FALLBACK (Main Process Level)
        # If downloader failed and raised exception, we try here as last resort.
        err_str = str(e)
        err_str_lower = err_str.lower()
        
        # --- CLASIFICACIÓN DE ERRORES ---
        if "404" in err_str_lower or "not found" in err_str_lower:
            friendly_err = "❌ **El video ya no existe o el enlace no es válido (Error 404)**"
        elif "403" in err_str_lower or "forbidden" in err_str_lower:
            friendly_err = "❌ **El sitio web nos ha bloqueado el acceso (Error 403 - Bloqueo)**"
        elif "429" in err_str_lower or "too many requests" in err_str_lower:
            friendly_err = "❌ **Demasiadas peticiones consecutivas (Bloqueo Temporal 429). Por favor, intenta de nuevo en unos minutos.**"
        elif "503" in err_str_lower or "service unavailable" in err_str_lower:
            friendly_err = "❌ **El sitio web está saturado o fuera de servicio temporalmente (Error 503)**"
        elif "timeout" in err_str_lower or "timed out" in err_str_lower or "deadline" in err_str_lower:
            friendly_err = "❌ **Se agotó el tiempo de espera al conectar con el servidor (Timeout)**"
        elif "connection refused" in err_str_lower or "cannot connect" in err_str_lower or "connection reset" in err_str_lower:
            friendly_err = "❌ **Error de conexión con el servidor remoto (Conexión rechazada/caída)**"
        elif "unsupported url" in err_str_lower or "unsupported" in err_str_lower:
            friendly_err = "❌ **Este enlace no está soportado o no tiene un extractor compatible.**"
        else:
            friendly_err = f"❌ **Error al analizar el enlace**:\n`{err_str[:150]}`"

        print(f"❌ Error al procesar {l_u}: {err_str}")

        if "tiktok.com" in l_u and ("Unsupported URL" in err_str or "Video no encontrado" in err_str):
             if wm: await wm.edit("🔄 **Intentando Fallback (TikWM)...**")
             from downloader import get_tikwm_data
             try:
                 tik_data = await get_tikwm_data(l_u)
                 if tik_data:
                      # Determine Type
                      if 'images' in tik_data and tik_data['images']:
                           # It's an image slideshow
                           cnt = len(tik_data['images'])
                           txt_n = "imagen" if cnt == 1 else "imágenes"
                           if wm: await wm.edit(f"📁 Encontré un álbum de {cnt} {txt_n}\n⏳ Descargando...")
                           
                           # Manual Download & Send Logic for Main
                           import aiohttp
                           paths = []
                           async with aiohttp.ClientSession() as session:
                               for idx, img_url in enumerate(tik_data['images']):
                                   async with session.get(img_url) as resp:
                                       if resp.status == 200:
                                           f_p = os.path.join("downloads", f"tk_slide_{cid}_{int(time.time())}_{idx}.jpg")
                                           with open(f_p, 'wb') as f:
                                               f.write(await resp.read())
                                           paths.append(f_p)
                           
                           if paths:
                               # Send
                               if wm: 
                                   try: await wm.edit(f"📁 Enviando {txt_n}... `{len(paths)}/{cnt}` 📤")
                                   except: pass
                               
                               if len(paths) > 1:
                                   # Send as Album
                                   from pyrogram.types import InputMediaPhoto
                                   media = [InputMediaPhoto(p) for p in paths[:10]] # Limit 10 per album
                                   await c.send_media_group(cid, media, reply_to_message_id=m.id)
                               else:
                                   await c.send_photo(cid, paths[0], reply_to_message_id=m.id)
                               
                               # Cleanup
                               for p in paths:
                                   try: os.remove(p)
                                   except: pass
                               return

                      elif 'play' in tik_data:
                           # Video
                           v_url = tik_data['play']
                           if wm: await wm.edit("⬇️ **Descargando Video (TikWM)...**")
                           
                           f_path = os.path.join("downloads", f"tk_vid_{cid}_{int(time.time())}.mp4")
                           async with aiohttp.ClientSession() as session:
                               async with session.get(v_url) as resp:
                                   if resp.status == 200:
                                       with open(f_path, 'wb') as f:
                                           while True:
                                               chunk = await resp.content.read(1024*1024)
                                               if not chunk: break
                                               f.write(chunk)
                           
                           if os.path.exists(f_path):
                               if wm: await wm.delete()
                               await c.send_video(cid, f_path, caption=f"🎬 **{tik_data.get('title','TikTok')}**", reply_to_message_id=m.id)
                               try: os.remove(f_path)
                               except: pass
                               return

             except Exception as e_tik:
                 print(f"❌ TikWM Main Error: {e_tik}")

        # Si gallery_sent es true, probablemente era un post mixto o solo imagenes, no mostrar error de video
        if gallery_sent:
            if wm: await wm.delete()
            return
        
        # Enviar el mensaje descriptivo al usuario
        if wm:
            try: await wm.edit(friendly_err)
            except: pass
        else:
            try: await m.reply(friendly_err, quote=True)
            except: pass

async def show_manga_menu(c, m, manga_id, wait_msg=None):
    cid = m.chat.id
    meta_m = await get_manga_metadata(manga_id)
    
    if not meta_m: 
        if wait_msg: await wait_msg.edit("❌ **Error:** Manga no encontrado (ID inválido o DB vacía).")
        return

    url_storage[cid] = {'manga_data': meta_m}
    
    if wait_msg: await wait_msg.delete()
    
    # BOTONES SOLICITADOS:
    # [ ZIP ] [ PDF ]
    # [ Enviar Imágenes ]
    kb_m_f = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 ZIP", callback_data="manga_sel|zip"), InlineKeyboardButton("📄 PDF", callback_data="manga_sel|pdf")],
        [InlineKeyboardButton("🖼 Ver Imágenes", callback_data="manga_sel|images")],
        [InlineKeyboardButton("🔙 Cancelar", callback_data="cancel")]
    ])
    
    txt = f"📚 **{meta_m['title']}**\n👤 {meta_m.get('author', 'Desconocido')}\n\n⬇️ **Selecciona formato:**"
    
    # OLD: if meta_m.get('cover'): await c.send_photo(cid, meta_m['cover'], ...
    
    # NEW: Cache Logic
    cover_ref = meta_m.get('cover')
    if cover_ref:
        # Intentar obtener ID cacheado o generar uno nuevo
        if wait_msg: 
            try: await wait_msg.edit("🖼 **Procesando portada...**")
            except: pass
            
        final_cover = await get_or_cache_cover(c, cid, manga_id, cover_ref)
        
        try: await wait_msg.delete()
        except: pass
        
        try:
            await c.send_photo(cid, final_cover, caption=txt, reply_markup=kb_m_f)
        except Exception as e:
            print(f"❌ Error enviando Cover: {e}")
            # Fallback: Enviar texto con botones si la foto falla
            await c.send_message(cid, txt, reply_markup=kb_m_f)
    else:
        if wait_msg: await wait_msg.delete()
        await c.send_message(cid, txt, reply_markup=kb_m_f)

# --- COMANDOS ADICIONALES ---

@app.on_message(filters.command("id"))
async def id_command(c, m):
    await m.reply_text(f"🆔 **ID del Chat:** `{m.chat.id}`")

@app.on_message(filters.command("cancel"))
async def cancel_cmd(c, m):
    cid = m.chat.id
    conf = get_config(cid)
    
    # 1. IDENTIFICAR MODO ACTIVO (Para reporte)
    active_mode_name = "Bot"
    # Map keys to readable names
    mode_map = {
        'party_mode': 'Modo Party',
        'join_party_mode': 'Modo Unir Party',
        'extract_mode': 'Modo Extractor',
        'gif_mode': 'Modo GIF',
        'sticker_mode': 'Modo Sticker',
        'saucenao_mode': 'Modo Sauce',
        'mp3_mode': 'Modo MP3',
        'cut_init_mode': 'Modo Corte Inicial',
        'cut_auto_mode': 'Modo Auto Corte',
        'auto_party': 'Modo Auto Party',
        'resize_mode': 'Modo Resize',
        'resize_auto_mode': 'Modo Auto Resize',
        'thumb_mode': 'Modo Maker Thumb',
        'convert_qh_mode': 'Modo Converter QH',
        'convert_h264_mode': 'Modo Converter H264',
        'smart_cut_mode': 'Modo Smart Cut',
        'collage_mode': 'Modo Collage',
        'sub_mode': 'Modo Subtítulos',
        'sub_auto_mode': 'Modo Auto Sub',
        'viral_mode': 'Modo Viral',
        'tagger_mode': 'Modo Tagger',
        'translate_manga_mode': 'Modo Traductor Manga'
    }
    
    found_mode = False
    for k, name in mode_map.items():
        if conf.get(k):
            active_mode_name = name
            found_mode = True
            break
            
    # 2. EJECUTAR CANCELACIÓN (Obtener lista detallada)
    cancelled_items = await cancel_all(cid) # Returns list of dicts {'url':..., 'msg_id':...}
    count = len(cancelled_items)
    
    # 3. LIMPIEZA GLOBAL
    # Reset UI logic keys
    url_storage.pop(cid, None)
    # Reset Modes (Exclusivity)
    await set_exclusive_mode(cid, None) # Clears all ALL_MODES_KEYS
    
    # 4. GENERAR REPORTE
    msg_out = ""
    
    if count > 0:
        if count == 1:
            # Caso Único: "Se canceló la descarga en Modo X."
            # Si enlace disponible, lo mostramos? El usuario pidió mensaje simple Específico para este caso.
            # "Se canceló la descarga en Modo Party."
            msg_out = f"🛑 **Se canceló la descarga en {active_mode_name}.**"
        else:
            # Caso Múltiple: "Se cancelaron 3 descargas." + Lista
            msg_out = f"🛑 **Se cancelaron {count} descargas.**\n"
            for i, item in enumerate(cancelled_items):
                url = item.get('url', 'Desconocido')
                msg_out += f"{i+1}. {url}\n"
    elif found_mode:
        # No descargas, pero modo estaba activo
        msg_out = f"🛑 **Se desactivó el {active_mode_name}.**"
    else:
        # Nada activo
        msg_out = "🛑 **No hay procesos activos para cancelar.**"
        
    await m.reply(msg_out)

@app.on_message(filters.command("reset"))
async def reset_cmd(c, m):
    if m.from_user.id != OWNER_ID: return
    await m.reply("🔴 **Reiniciando Servidor...**\nEl bot volverá en unos segundos.")
    print(f"🔄 RESTART COMMAND RECEIVED FROM {m.from_user.id}. RESTARTING...")
    
    # Reinicio forzado del proceso
    os.execv(sys.executable, [sys.executable] + sys.argv)


@app.on_message(filters.command("user"))
async def user_profile_cmd(c, m):
    uid = m.from_user.id
    txt = f"🆔 **Perfil de Usuario**\n👤 **Nombre:** {m.from_user.first_name}\n🔢 **ID:** `{uid}`"
    await m.reply(txt)

@app.on_message(filters.command("setsudo"))
async def setsudo_cmd(c, m):
    if m.from_user.id != OWNER_ID: return
    if len(m.command) < 2: return
    new_id = int(m.command[1])
    # Lógica de guardado en Firebase...
    await m.reply(f"👮‍♂️ Admin añadido: `{new_id}`")

# --- AI HANDLER (TEXTO GENERAL) ---
# --- AI HANDLER (TEXTO GENERAL + MULTIMEDIA NANO BANANA) ---
@app.on_message(filters.text | filters.photo | filters.document | filters.video)
async def ai_chat_handler(c, m):
    """Maneja mensajes de texto generales y multimedia para Nano Banana usando Gemini AI."""
    # --- AI DISABLED BY USER REQUEST ---
    return
    
    # Ignorar si es parte de un flujo de espera (ej. pyromod)
    
    user_txt = m.text or m.caption or ""
    
    # EXCLUSIVE CHECK FOR NANO BANANA: Allow media messages
    conf = get_config(m.chat.id)
    is_nano_banana = conf.get('ai_model_mode') == 'nano_banana'
    
    # --- VALIDACION DE ENTRADA NANO BANANA ---
    # Si es Nano Banana y envía video, bloquear con mensaje específico.
    if is_nano_banana and (m.video or (m.document and m.document.mime_type and m.document.mime_type.startswith('video/'))):
        await m.reply(
            "⚠️ **Estás en el modo Nano Banana Pro.**\n\n"
            "Acabas de enviar un video y esta herramienta trabaja únicamente con imágenes.\n"
            "Por favor, vuelve a enviar el contenido en formato de imagen o cambia de IA."
        )
        return

    # If not text and not Nano Banana, ignore media messages here (let other handlers take them)
    if not user_txt and not is_nano_banana:
        return


    # EXCLUSIVE FLOW CHECK:
    # If user is in a configuration flow (editing persona, adding category, etc), AI should NOT reply.
    # The input_handler (Group 1) will handle it.
    st = url_storage.get(m.chat.id)
    conf = get_config(m.chat.id) # Load config early to check modes

    if conf.get('tagger_mode') or conf.get('research_mode') or conf.get('cut_init_mode'): return # Exclusivity for Tagger, Research & Cut Init

    if st and (
        'ai_add_step' in st or 
        'ai_config_step' in st or 
        'party_input_mode' in st or
        'extract_step' in st or
        'cut_auto_step' in st or 
        'vm_paper_pending' in st or # Exclusivity for Paper Mode Text
        st.get('action') in ['ai_edit_p_wait', 'ai_add_cat_wait']
    ):
        return

    # FAST PASS: Si es solo link o texto corto con link, ignorar (lo toma input_handler/analyze)
    has_http = "http" in user_txt
    if has_http and len(user_txt.split()) <= 3:
        return
    
    # FIX: Si analyze() lo dejó pasar (porque era largo), nosotros lo tomamos aquí.
    # No necesitamos más lógica extra, el flujo es correcto.
    
    # Manejo de Reply (Contexto)
    # Manejo de Reply (Contexto o Imagen)
    img_path_reply = None
    if m.reply_to_message:
        # Texto
        if m.reply_to_message.text:
            reply_txt = m.reply_to_message.text
            if len(reply_txt) > 200: reply_txt = reply_txt[:200] + "..."
            user_txt = f"[En respuesta a: '{reply_txt}']\nUsuario dice: {user_txt}"
        
        # Imagen
        if m.reply_to_message.photo:
            try:
                wm_r = await m.reply("🔍 Analizando imagen respondida...")
                # Use absolute path to ensure AI service finds it
                filename = f"ai_reply_{m.chat.id}_{int(time.time())}.jpg"
                img_path_reply = os.path.abspath(os.path.join("downloads", filename))
                
                await m.reply_to_message.download(file_name=img_path_reply)
                await wm_r.delete()
                print(f"🖼️ Imagen descargada para análisis: {img_path_reply}")
            except Exception as e_img:
                print(f"❌ Error descargando reply image: {e_img}")

    # --- NANO BANANA BATCHING LOGIC (ALBUMS) ---
    img_path_current = None
    is_media = m.photo or (m.document and m.document.mime_type and m.document.mime_type.startswith('image/'))

    if is_media:
        try:
             # Determine extension
             ext = "jpg"
             if m.document and m.document.file_name:
                 ext_chk = m.document.file_name.split('.')[-1]
                 if len(ext_chk) < 5: ext = ext_chk
             
             import time
             import random
             # Use ns timing + random to avoid collision in same-second batch
             unique_id = f"{int(time.time()*1000)}_{random.randint(100,999)}"
             filename_cur = f"ai_input_{m.chat.id}_{unique_id}.{ext}"
             img_path_current = os.path.abspath(os.path.join("downloads", filename_cur))
             
             await m.download(file_name=img_path_current)
             print(f"🖼️ [NanoBanana] Buffered Image: {img_path_current}")
             
             # NANO BANANA BATCH MODE
             if is_nano_banana:
                 chat_id = m.chat.id
                 
                 # Initialize buffer if empty
                 if chat_id not in NANO_BATCH_BUFFER:
                     # 1. LOCK IMMEDIATELY (Reserve spot to prevent race condition)
                     NANO_BATCH_BUFFER[chat_id] = {
                         'images': [], 
                         'text': user_txt, 
                         'wm': None,
                         'msg': m 
                     }
                     
                     # 2. PERFORM ASYNC OPS (Send Message)
                     wm_msg = None
                     if not user_txt:
                         try:
                             wm_msg = await m.reply(
                                 "✅ **Recibido. Total imágenes: 1**\n✍️ Escribe tu prompt cuando estés listo."
                             )
                         except: pass

                     # 3. UPDATE BUFFER WITH MSG
                     if wm_msg:
                         NANO_BATCH_BUFFER[chat_id]['wm'] = wm_msg
                 
                 # Append Image
                 NANO_BATCH_BUFFER[chat_id]['images'].append(img_path_current)
                 
                 # Update Count in Message (if exists)
                 if NANO_BATCH_BUFFER[chat_id].get('wm'):
                     try:
                         cnt = len(NANO_BATCH_BUFFER[chat_id]['images'])
                         curr_wm = NANO_BATCH_BUFFER[chat_id]['wm']
                         # Solo editar si el contador cambia (evitar errores de API)
                         if f"Total imágenes: {cnt}" not in curr_wm.text:
                             await curr_wm.edit_text(
                                 f"✅ **Recibido. Total imágenes: {cnt}**\n✍️ Escribe tu prompt cuando estés listo.",
                                 reply_markup=curr_wm.reply_markup
                             )
                     except: pass
                 
                 # Update text (append or replace? Let's replace if new text is meaningful)
                 if user_txt:
                     # Si llega texto nuevo en una foto posterior, actualizamos el prompt
                     # Y si había mensaje de espera, deberíamos borrarlo? 
                     # El usuario dice: "NO debe mostrarse mensaje... Proceder directamente".
                     # Si ya mostramos mensaje (porque la primera foto no tenía texto), y la segunda SI tiene:
                     # Deberíamos borrar el mensaje de espera.
                     if NANO_BATCH_BUFFER[chat_id].get('wm'):
                         try:
                             await NANO_BATCH_BUFFER[chat_id]['wm'].delete()
                             NANO_BATCH_BUFFER[chat_id]['wm'] = None
                         except: pass
                     
                     prev_txt = NANO_BATCH_BUFFER[chat_id]['text']
                     if prev_txt != user_txt:
                         NANO_BATCH_BUFFER[chat_id]['text'] = user_txt.strip()
                 
                 # Reset Timer (Debounce)
                 # Cancel previous task
                 if 'task' in NANO_BATCH_BUFFER[chat_id]:
                     NANO_BATCH_BUFFER[chat_id]['task'].cancel()
                 
                 # Start new task
                 NANO_BATCH_BUFFER[chat_id]['task'] = asyncio.create_task(run_nano_batch(chat_id, c))
                 
                 return # EXIT HANDLER HERE, let batch runner handle AI call

             # Standard Logic for non-nano banana (immediate)
             wm_scan = None
             if not m.reply_to_message:
                   wm_scan = await m.reply("👁️ **Viendo tu imagen...**")
             if wm_scan:
                  try: await wm_scan.delete()
                  except: pass

        except Exception as e_curr:
             print(f"❌ Error descargando current image: {e_curr}")

    if user_txt.startswith('/'): return # Ignorar comandos
    
    # If we are here, it's either text-only or non-nano-banana image
    # BUT if nano_banana sent text-only, we should process it immediately? Yes.
    
    if len(user_txt) < 2 and not img_path_current: return 

    # Feedback visual (escribiendo...)
    await c.send_chat_action(m.chat.id, pyrogram.enums.ChatAction.TYPING)
    
    # Consultar AI
    uid = m.from_user.id
    
    # --- LOGIC: WELCOME BACK (TIEMPO SIN VERTE) ---
    sys_hint_welcome = ""
    try:
        from firebase_service import get_user_rules_fb, save_user_rule_fb, save_user_config_fb, db
        import time
        
        # Usamos una coleccion separada o un campo en user_config para 'last_seen'
        # Por simplicidad, leeremos 'last_seen' de user_config
        conf = get_config(m.chat.id)
        last_seen = conf.get('last_seen', 0)
        now_ts = int(time.time())
        
        # 6 Horas = 21600 segundos
        if last_seen > 0 and (now_ts - last_seen) > 21600:
             sys_hint_welcome = "\n\n[SYSTEM NOTICE: El usuario ha vuelto después de mucho tiempo (más de 6h). Si te saluda, intenta usar la reacción 'bienvenida' (si encaja en el contexto).]"
             print(f"👋 [Welcome Back] Triggered for {uid} (Delta: {now_ts - last_seen}s)")
             
        # Actualizar last_seen
        conf['last_seen'] = now_ts
        # Guardar async (fire and forget task)
        asyncio.create_task(save_user_config_fb(m.chat.id, conf))
        
    except Exception as e_wb:
        print(f"⚠️ Welcome Back Logic Error: {e_wb}")

    conf = get_config(m.chat.id) # Reload or use current
    active_p = conf.get('active_persona', 'nsfw')
    
    # Custom Prompt Logic
    custom_p_text = None
    if active_p not in ['formal', 'pasiva', 'profesional', 'agresiva', 'nsfw']:
        # Check Global First
        c_p = global_personas.get(active_p)
        if not c_p:
            # Fallback Local Legacy
             c_p = conf.get('custom_personas', {}).get(active_p)
        
        if c_p: custom_p_text = c_p.get('prompt')

    # 1. Recuperar reglas de este usuario (async desde Firebase)
    user_rules = await get_user_rules_fb(uid, persona_id=active_p)
    
    # Get available categories for AI knowledge
    # Default visual cats
    avail_cats = ['bienvenida', 'greeting', 'admire']
    
    # Global Cats
    if active_p in global_personas and 'images' in global_personas[active_p]:
        avail_cats.extend(list(global_personas[active_p]['images'].keys()))
        
    # Local Cats (Legacy)
    if 'ai_images' in conf and active_p in conf['ai_images']:
        avail_cats.extend(list(conf['ai_images'][active_p].keys()))
        
    # CLOUD BODY CACHE (Lazy Load)
    from firebase_service import get_all_avatars
    if active_p not in AVATAR_KEYS_CACHE:
        # Load from DB
        # Run in background task to not block? No, we need it for this prompt.
        # But get_all_avatars is async.
        try:
             av_data = await get_all_avatars(active_p) # {outfit: {emotion: [ids]}}
             keys = set()
             for o_cnt in av_data.values():
                 if isinstance(o_cnt, dict):
                     keys.update(o_cnt.keys())
             AVATAR_KEYS_CACHE[active_p] = keys
        except Exception as e:
             print(f"⚠️ Cache Load Error: {e}")
             AVATAR_KEYS_CACHE[active_p] = set()
             
    if active_p in AVATAR_KEYS_CACHE:
        avail_cats.extend(list(AVATAR_KEYS_CACHE[active_p]))
        
    # Deduplicate
    avail_cats = list(set(avail_cats))
    
    # 2. Llamar a Gemini (pasando las reglas, personalidad y categorías disponibles)
    ai_mode_val = conf.get('ai_model_mode', 'gemini_2')
    
    # Prepare Image Paths List
    image_paths_list = []
    if img_path_reply: 
        image_paths_list.append(img_path_reply)
    if img_path_current:
        image_paths_list.append(img_path_current)
        
    # NANO BANANA PENDING CONTEXT check
    if is_nano_banana and m.chat.id in NANO_PENDING_CONTEXT:
        pending_imgs = NANO_PENDING_CONTEXT.pop(m.chat.id)
        if pending_imgs:
            image_paths_list.extend(pending_imgs)
            print(f"🍌 [NanoBanana] Attached {len(pending_imgs)} pending images to prompt.")

    # Prepare Image Config
    img_conf = {
        'ratio': conf.get('ai_img_ratio', '1:1'),
        'res': conf.get('ai_img_res', '1K'),
        'temp': conf.get('ai_temp', 1.0),
        'batch_size': conf.get('ai_img_batch', 1)
    }

    # --- STATUS MESSAGE (DYNAMIC) ---
    # "Pensando..." removed by user request
    status_msg = None
    last_status_time = 0
    
    # Capture running loop for thread-safety
    main_loop = asyncio.get_running_loop()

    def status_callback(text):
        # Rate limit updates
        nonlocal last_status_time
        import time
        if time.time() - last_status_time < 2.0: return 
        last_status_time = time.time()
        
        try:
            if status_msg:
                future = asyncio.run_coroutine_threadsafe(status_msg.edit(text), main_loop)
            # Optional: future.result() if we wanted to wait, but we don't.
        except Exception as e:
            logger.error(f"⚠️ Status Update Error: {e}")

    # Generate
    try:
        response = await asyncio.get_running_loop().run_in_executor(
            None, 
            lambda: ask_gemini(
                user_txt + sys_hint_welcome, 
                uid, 
                image_paths=image_paths_list, 
                user_rules=user_rules, 
                active_persona=active_p, 
                custom_prompt=custom_p_text, 
                available_categories=avail_cats, 
                green_mode=conf.get('ai_green_mode', False), 
                focus_mode=conf.get('ai_focus_mode', False), 
                ai_mode=ai_mode_val, 
                image_config=img_conf,
                status_callback=status_callback,
                google_search_mode=conf.get('google_search_mode', True)
            )
        )
    except Exception as e:
        if status_msg: await status_msg.edit(f"❌ Error fatal en Gemini: {e}")
        else: await m.reply(f"❌ Error fatal en Gemini: {e}")
        return

    # Delete Status Message when done
    try: 
        if status_msg: await status_msg.delete()
    except: pass
    
    # Cleanup Input Image
    if img_path_current and os.path.exists(img_path_current):
        try: os.remove(img_path_current)
        except: pass
    
    # Manejar Respuesta
    if isinstance(response, dict) and response.get('action') == 'TRIGGER_TOOL':
        tool = response.get('tool')
        text_response = response.get('text')
        
        # --- TOOL HANDLERS ---
        if tool == 'download':
            # CASO ESPECIAL: Enviamos texto + botón juntos o DESCARGA INMEDIATA
            url = response.get('url')
            immediate = response.get('immediate')

            if url:
                l_u = limpiar_url(url)
                
                if immediate:
                    # --- DESCARGA INMEDIATA (Sin botones) ---
                    await m.reply(text_response or "🚀 **Iniciando descarga inmediata...**")
                    
                    cid = m.chat.id
                    # conf already loaded above
                    
                    # Determinar calidad (Auto o Best)
                    quality = "best"
                    q_auto = conf.get('q_auto')
                    if q_auto == 'min': quality = 'worst'
                    
                    url_info = {'url': l_u, 'titulo': "AI Auto Download", 'fast_enabled': conf.get('fast_enabled', True)}
                    
                    # Llamar al downloader
                    asyncio.create_task(procesar_descarga(c, cid, l_u, quality, url_info, m))
                else:
                    # --- FLUJO NORMAL (Botones) ---
                    # Generamos ID para el botón (microsegundos + random para evitar colisiones)
                    import time
                    link_id = hex(int(time.time_ns() // 1000) + random.randint(10000, 99999))[2:] 
                    storage_key = f"{m.chat.id}_{link_id}"
                    url_storage[storage_key] = {'url': l_u}
                    
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬇️ Empezar descarga", callback_data=f"ai_dl|{link_id}")]])
                    await m.reply(text_response, reply_markup=kb)
                # Fallback sin url
                await m.reply(text_response)

        elif tool == 'SEND_GENERATED_IMAGE':
            # --- NANO BANANA GENERATED IMAGE ---
            raw_path = response.get('path')
            paths = raw_path if isinstance(raw_path, list) else [raw_path]
            caption = response.get('text', "")
            
            sent_any = False
            for i, img_path in enumerate(paths):
                if img_path and os.path.exists(img_path):
                    # Check User Preference for Document (AI Specific OR Global)
                    # EXCEPTION LOGIC: Nano Banana Pro
                    # 1. Check Internal Nano setting (ai_img_as_doc)
                    # 2. If Internal SET (True/False), use it (Overrides Global).
                    # 3. If Internal NOT SET (None), fallback to Global (doc_mode).
                    
                    internal_doc = conf.get('ai_img_as_doc') # Can be True, False, or None
                    global_doc = conf.get('doc_mode', False)
                    
                    use_doc = global_doc # Default to global
                    if internal_doc is not None:
                        use_doc = internal_doc
                    
                    # Caption only on first image? Or all? Let's do first for now to avoid spamming text.
                    cap_final = caption if i == 0 else ""

                    try:
                        if use_doc:
                            await m.reply_document(img_path, caption=cap_final)
                        else:
                            await m.reply_photo(img_path, caption=cap_final)
                        sent_any = True
                    except Exception as e:
                        print(f"❌ Error sending generated image {i}: {e}")
                        
                    # --- AUTO WAIFU2X LOGIC ---
                    if conf.get('waifu2x_auto', False):
                        try:
                            from utils import waifu2x_upscale
                            print(f"✨ [Auto Waifu2x] Processing: {img_path}")
                            
                            # Determine Scale based on Config
                            res_conf = conf.get('ai_img_res', '1K')
                            w2x_scale = 2 # Default (1K/2K make 2x)
                            
                            if res_conf == '4K': w2x_scale = 4
                            elif res_conf == '8K': w2x_scale = 8
                            
                            upscaled_path = await asyncio.get_running_loop().run_in_executor(
                                None, 
                                lambda: waifu2x_upscale(img_path, scale=w2x_scale, noise=2)
                            )
                            
                            if upscaled_path and os.path.exists(upscaled_path):
                                cap_w2x = f"✨ **Versión Waifu2x ({res_conf})**"
                                if use_doc:
                                    await m.reply_document(upscaled_path, caption=cap_w2x)
                                else:
                                    await m.reply_photo(upscaled_path, caption=cap_w2x)
                                
                                try: os.remove(upscaled_path)
                                except: pass
                            else:
                                print("⚠️ [Auto Waifu2x] Failed to generate path.")
                                
                        except Exception as e_w2x:
                            print(f"❌ [Auto Waifu2x] Error: {e_w2x}")

                    # CLEANUP GENERATED IMAGE
                    try: 
                        os.remove(img_path)
                        print(f"🗑️ [Cleanup] Deleted generated file: {img_path}")
                    except Exception as e:
                        print(f"⚠️ Error cleaning up generated file: {e}")

            if not sent_any:
                await m.reply("⚠️ Error: La imagen generada no se encontró.")

        elif tool == 'reaction':
            # --- AI VISUAL REACTION (Waifu Body) ---
            cat = response.get('reaction_category')
            
            # MAPPING FIX: AI uses 'welcome', 'admire' but DB has 'greeting', 'love'
            CAT_MAP = {
                'welcome': 'greeting', # Normal "Hello" -> Saludo
                'bienvenida': 'bienvenida', # Explicit Welcome Back -> Bienvenida
                'admire': 'love',  # Approximate
                'shy': 'shy'
            }
            if cat in CAT_MAP: cat = CAT_MAP[cat]
            
            if cat:
                reaction_item = None
                
                # 1. CLOUD BODY LOOKUP (Priority) - Supports {'id':..., 'type':...}
                cloud_imgs = await get_persona_images(active_p, 'default', cat)
                if cloud_imgs:
                    import random
                    # --- NO REPEAT LOGIC ---
                    last_id = conf.get('last_react_id')
                    
                    # Filter out last sent ID if possible
                    candidates = [img for img in cloud_imgs if img['id'] != last_id]
                    
                    # If nothing left (e.g. only 1 image exists), use original list
                    if not candidates:
                        candidates = cloud_imgs
                        
                    reaction_item = random.choice(candidates)
                    
                    # Save new ID for next time (Fire & forget)
                    conf['last_react_id'] = reaction_item['id']
                    asyncio.create_task(save_user_config_fb(m.chat.id, conf))
                
                # 2. Fallback to Legacy/Global
                if not reaction_item:
                    # Get Config (already have 'conf' and 'active_p')
                    # Access nested images: Global or Local
                    ai_imgs = global_personas.get(active_p, {}).get('images', {}).get(cat, {})
                    
                    if not ai_imgs:
                         ai_imgs = conf.get('ai_images', {}).get(active_p, {}).get(cat, {})
                    
                    mode = ai_imgs.get('mode', 'single')
                    imgs = ai_imgs.get('images', [])
                    
                    # --- SELECTION LOGIC ---
                    if imgs:
                        if mode == 'random':
                            import random
                            reaction_item = random.choice(imgs)
                        elif mode == 'subset':
                            subset = ai_imgs.get('subset', [])
                            valid_subset = [imgs[i] for i in subset if 0 <= i < len(imgs)]
                            if valid_subset:
                                import random
                                reaction_item = random.choice(valid_subset)
                        else:
                            reaction_item = ai_imgs.get('active') or imgs[-1]
                
                # --- SENDING LOGIC ---
                if reaction_item:
                    # Legacy support: if str, wrap it
                    if isinstance(reaction_item, str): reaction_item = {'id': reaction_item, 'type': 'photo'}
                    
                    fid = reaction_item['id']
                    ftype = reaction_item.get('type', 'photo')
                    
                    try:
                        if ftype == 'sticker':
                           # Sticker + Text (Separate messages usually, caption not supported on stickers)
                           await m.reply(text_response)
                           await m.reply_sticker(sticker=fid)
                        elif ftype == 'video':
                           await m.reply_video(video=fid, caption=text_response)
                        elif ftype == 'animation':
                           # User req: Text first, then GIF (like stickers) or caption? 
                           # Animation supports caption usually.
                           # But user logic in legacy code used reply_animation.
                           await m.reply_animation(animation=fid, caption=text_response)
                        else: # Photo
                           await m.reply_photo(photo=fid, caption=text_response)
                        
                        # --- TTS INJECTION FOR REACTION ---
                        # DEBUG TTS
                        is_voice = conf.get('voice_mode')
                        print(f"🎤 [DEBUG] Check TTS: VoiceMode={is_voice}, TextLen={len(text_response) if text_response else 0}")
                        
                        if is_voice and text_response:
                             try:
                                 print(f"🎤 [DEBUG] Generating Audio for: {text_response[:20]}...")
                                 audio_f = await generate_tts_audio(text_response, active_p)
                                 if audio_f:
                                     print(f"🎤 [DEBUG] Sending Audio: {audio_f}")
                                     await m.reply_voice(audio_f)
                                     os.remove(audio_f)
                                 else:
                                     print("🎤 [DEBUG] Audio file returned None")
                             except Exception as e_tts:
                                 print(f"🎤 [DEBUG] TTS Error: {e_tts}")
                             
                        return
                        
                    except Exception as e:
                        print(f"❌ Reaction Error ({ftype}): {e}")
                        # Fallback to text only
                        await m.reply(text_response)
                        return
                
                # --- FALLBACK: NO IMAGE FOUND (EMPTY CATEGORY) ---
                else:
                    if text_response:
                        await m.reply(text_response)
                        
                        # --- TTS INJECTION FOR FALLBACK ---
                        if conf.get('voice_mode'):
                             try:
                                 audio_f = await generate_tts_audio(text_response, active_p)
                                 if audio_f:
                                     await m.reply_voice(audio_f)
                                     os.remove(audio_f)
                             except: pass
                    return

        elif tool == 'create_post':
            # --- POST CREATOR ---
            # Args: text, media_type, url (media_url), buttons
            buttons_data = response.get('buttons', [])
            media_type = response.get('media_type')
            media_url = response.get('url') # Mapped from media_url in ai_service
            
            # Construir Teclado
            kb_post = None
            if buttons_data:
                rows = []
                current_row = []
                for btn_str in buttons_data:
                    parts = btn_str.split('|', 1)
                    if len(parts) == 2:
                        lbl, data = parts
                        # Detectar tipo de botón
                        if data.startswith('http'):
                            current_row.append(InlineKeyboardButton(lbl, url=data))
                        elif data.startswith('callback:'):
                            cb_val = data.split(':', 1)[1]
                            current_row.append(InlineKeyboardButton(lbl, callback_data=cb_val))
                        else:
                            # Default a URL si no es callback explícito, o callback data raw
                            # Asumimos URL si parace url, sino callback
                            if '://' in data:
                                current_row.append(InlineKeyboardButton(lbl, url=data))
                            else:
                                current_row.append(InlineKeyboardButton(lbl, callback_data=data))
                    
                    # Simple grid logic: 2 buttons max per row for aesthetics
                    if len(current_row) >= 2:
                        rows.append(current_row)
                        current_row = []
                
                if current_row: rows.append(current_row)
                kb_post = InlineKeyboardMarkup(rows)

            # Enviar Mensaje Multimedia o Texto
            try:
                if media_url and media_type:
                    if 'photo' in media_type:
                        await m.reply_photo(media_url, caption=text_response, reply_markup=kb_post)
                    elif 'video' in media_type:
                        await m.reply_video(media_url, caption=text_response, reply_markup=kb_post)
                    else:
                        await m.reply(text_response, reply_markup=kb_post, disable_web_page_preview=False)
                else:
                    await m.reply(text_response, reply_markup=kb_post, disable_web_page_preview=False)
            except Exception as e_post:
                await m.reply(f"❌ Error creando post: {e_post}\n\n{text_response}")

        elif tool == 'manage_rules':
            # --- MANAGE RULES (Scoped) ---
            rule_content = response.get('text') 
            action = response.get('action_type')
            
            # Usamos la versión Async de Firebase con Active Persona
            success = await save_user_rule_fb(m.from_user.id, rule_content, action, persona_id=active_p)
            
            if success:
                if action == 'add':
                    await m.reply(f"✅ **Regla Guardada ({active_p}):**\n`{rule_content}`\n\n_La recordaré para siempre en este modo._")
                elif action == 'remove':
                    await m.reply(f"🗑️ **Regla Olvidada ({active_p}):**\n`{rule_content}`")
                elif action == 'clear':
                    await m.reply(f"🧹 **Memoria de reglas ({active_p}) borrada.**")
            else:
                await m.reply("❌ Hubo un error guardando la regla en Firebase.")

        elif tool == 'pack':
            # --- PACK SENDER (CLOUD BODY) ---
            p_cat = response.get('pack_category', 'general')
            
            # Map user intent to Firebase keys (NEW PACK FOLDERS)
            cat_map = {
                'tetas': 'pack_boobs',
                'culos': 'pack_ass',
                'cuerpo': 'pack_nude',
                'vagina': 'pack_pussy',
                'pies': 'pack_feet',
                'general': 'pack_nude' 
            }
            fb_key = cat_map.get(p_cat, 'pack_nude')
            
            # Send text first if explicitly provided by AI
            if text_response: await m.reply(text_response)

            # Retrieve from Firebase
            # from firebase_service import get_persona_images (Already global)
            conf = get_config(m.chat.id)
            pid = conf.get('active_persona', 'nsfw')
            
            # 1. Try Active Persona
            imgs = await get_persona_images(pid, 'default', fb_key)
            
            # 2. Fallback to NSFW if generic and custom persona is empty
            if not imgs and pid != 'nsfw':
                imgs = await get_persona_images('nsfw', 'default', fb_key)
            
            if imgs:
                import random
                selected = random.choice(imgs)
                # Handle dict or str
                fid = selected if isinstance(selected, str) else selected.get('id')
                ftype = 'photo' if isinstance(selected, str) else selected.get('type', 'photo')
                
                try:
                    cap = f"📦 Aquí tienes tu pack de **{p_cat}**."
                    if ftype == 'video':
                         await m.reply_video(fid, caption=cap)
                    elif ftype == 'animation':
                         await m.reply_animation(fid, caption=cap)
                    elif ftype == 'sticker':
                         await m.reply_sticker(fid)
                    elif ftype == 'document':
                         await m.reply_document(fid, caption=cap)
                    else:
                         await m.reply_photo(fid, caption=cap)
                except Exception as e:
                    await m.reply(f"❌ Error enviando pack (ID inválido?): {e}")
            else:
                 # Prompt user to upload
                 clean_key = fb_key.replace('_', ' ').title()
                 await m.reply(
                     f"📂 Ve a **Configuración IA** > **Pack Waifu** para llenarme el álbum."
                 )
            
            # --- TTS INJECTION FOR PACK ---
            if conf.get('voice_mode') and text_response:
                 try:
                     audio_f = await generate_tts_audio(text_response, active_p)
                     if audio_f:
                         await m.reply_voice(audio_f)
                         os.remove(audio_f)
                 except: pass

        else:
            # CASO GENERAL: Enviamos texto primero
            # --- SILENT MODE CHECK (Nano Banana) ---
            is_nano_banana = (conf.get('ai_model_mode') == 'nano_banana')
            
            if text_response and not is_nano_banana:
                await m.reply(text_response)
                
                # TTS (Solo si no es Nano Banana)
                if conf.get('voice_mode'):
                     try:
                         audio_f = await generate_tts_audio(text_response, active_p)
                         if audio_f:
                             await m.reply_voice(audio_f)
                             os.remove(audio_f)
                     except: pass
            
            # Si es Nano Banana y hay texto pero NO herramienta -> Forzar mensaje de "Esperando..." o silencio total
            elif is_nano_banana and text_response:
                 # Opcional: Loguear pero no enviar
                 print(f"🍌 [NanoBanana] Silenced Text: {text_response[:50]}...")

            # Luego ejecutamos la herramienta (Siempre)
            if tool == 'party':
                # Logic for party command (Inline)
                cid = m.chat.id
                conf = get_config(cid)
                conf['party_mode'] = True
                save_bot_config(cid, conf)
                await m.reply("🎉 **Modo Party Activado.**\nEnvíame videos y cuando termines escribe `/join` o `/unir`.")
                
            elif tool == 'auto_party':
                cid = m.chat.id
                conf = get_config(cid)
                conf['party_auto_mode'] = True 
                conf['party_mode'] = True
                save_bot_config(cid, conf)
                await m.reply("🔗 **Modo Auto-Join Activado.** Envíame videos y los uniré automáticamente.")
            elif tool == 'cutter':
                 # Logic for cutter command (Inline)
                await m.reply("✂️ **Herramienta Cutter.**\nResponde a un video con `/cut inicio fin` (ej: `/cut 00:00 00:30`) para cortarlo.")

            elif tool == 'sauce':
                cid = m.chat.id
                conf = get_config(cid)
                conf['saucenao_mode'] = True
                save_bot_config(cid, conf)
                await m.reply("🔍 **Modo Sauce Activado.** La próxima imagen que envíes será analizada.")



    elif response:
        # --- SILENCE NANO BANANA TEXT ---
        if is_nano_banana:
            print(f"🍌 [NanoBanana] Silenced Hallucination: {response[:50]}...")
            return

        await m.reply(response, quote=True)
        
        if conf.get('voice_mode'):
             try:
                 audio_f = await generate_tts_audio(response, active_p)
                 if audio_f:
                     await m.reply_voice(audio_f)
                     os.remove(audio_f)
             except: pass

    # FINAL CLEANUP (Reply Context)
    if img_path_reply and os.path.exists(img_path_reply):
        try: os.remove(img_path_reply)
        except: pass

    if has_http:
        m.stop_propagation()

# --- ARRANQUE ---

# --- ARRANQUE ---

async def boot_services():
    print("🚀 Bot Iniciando (Versión Final)...")

    # --- INIT AI ---
    init_ai(GEMINI_API_KEY)
    
    # --- INIT GLOBAL PERSONAS ---
    await refresh_globals()
    
    # --- CLEANUP STARTUP ---
    try:
        if not os.path.exists("downloads"):
            os.makedirs("downloads")

        import shutil
        cwd = os.getcwd()
        print("🧹 Ejecutando limpieza inicial...")
        for item in os.listdir(cwd):
            if item.startswith("tmp_gallery_") and os.path.isdir(item):
                try: 
                    shutil.rmtree(item)
                    print(f"🗑 Eliminado: {item}")
                except Exception as e:
                    print(f"⚠️ Error borrando {item}: {e}")
    except: pass
    
    
    # --- CLEANUP SESSION & START ---
    # --- CLEANUP SESSION & START ---
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
            # 1. Error de Sesión (Corrupción) -> Borrar y matar proceso para reiniciar limpio
            if "406" in err_str or "AUTH_KEY" in err_str or "Unauthorized" in err_str:
                print(f"⚠️ Error de Sesión detectado ({e}). Eliminando archivo de sesión corrupto y reiniciando app...")
                s_path = os.path.join(WORKDIR, "brody_final_v2.session")
                if os.path.exists(s_path):
                    try: os.remove(s_path)
                    except: pass
                sys.exit(1)

            # 2. Error de Red (Timeout, Connection, etc) -> Esperar y reintentar
            is_net = any(x in err_str for x in ["Connection", "Timeout", "Network", "OSError", "Unreachable"])
            if is_net:
                wait_sec = (i + 1) * 3  # 3s, 6s, 9s...
                print(f"⚠️ Error de Red ({e}). Reintentando en {wait_sec} segundos...")
                await asyncio.sleep(wait_sec)
                continue
            
            # 3. Otros errores -> Crash
            raise e

    if not connected:
        print("❌ Error Crítico: No se pudo conectar a Telegram tras múltiples intentos.")
        sys.exit(1)
    
    # Comandos con atajos de herramientas (Actualizado)
    await app.set_bot_commands([
        BotCommand("start", "⚙️ Menú Principal"),
        BotCommand("refactor_on", "🟢 Activar Refactor Links"),
        BotCommand("refactor_off", "🔴 Desactivar Refactor Links"),
        BotCommand("party", "✂️ Cortar Video"),
        BotCommand("unir_party", "🔗 Unir Videos"),
        BotCommand("extractor", "🖼 Extraer Fotos"),
        BotCommand("gif", "🎬 Crear GIF"),
        BotCommand("sticker", "🎭 Crear Sticker"),
        BotCommand("mp3", "🎵 Extraer Audio MP3"),
        BotCommand("sauce", "🔍 Buscar Fuente (SauceNAO)"),
        BotCommand("tagger", "🏷️ Generar Hashtags"),
        BotCommand("autoclass", "📷 Auto-Clasificación"),
        BotCommand("ping", "🏓 Check Estado"),
        BotCommand("id", "🆔 Ver IDs"),
        BotCommand("cancel", "🛑 Cancelar Todo")
    ])
    
    # Firebase sync
    try:
        from firebase_service import load_all_user_configs, load_all_hashtags
        import database
        cfs = await load_all_user_configs()
        if cfs: database.user_config.update(cfs)
        if cfs: database.user_config.update(cfs)
        tgs = await load_all_hashtags()
        if tgs: database.hashtag_db.update(tgs)
        load_viral() # Load Viral DB locally
    except: pass
    
    print("✅ Bot Conectado y Listo.")
    
    # Iniciar Aiohttp Server
    await start_web_server()
    await idle()
    await app.stop()


# --- INTERCEPTOR DE ARCHIVOS TXT ---
@app.on_message(filters.private, group=-20)
async def txt_mode_interceptor(c, m):
    cid = m.chat.id
    conf = get_config(cid)
    if not conf.get('txt_mode', False):
        m.continue_propagation()
        return
    
    # Permitir que comandos estándar se propaguen
    if m.text and (m.text.startswith('/') or "Configuración" in m.text or "Menu" in m.text):
        m.continue_propagation()
        return
        
    if m.document and m.document.file_name and m.document.file_name.lower().endswith('.txt'):
        # Procesar archivo .txt
        await process_txt_file_download(c, m)
        return
        
    # Bloquear/ignorar todo lo demás si el modo TXT está activo
    return


async def upload_media_group_batch(c, cid, batch_items, conf):
    if not batch_items:
        return
    
    from pyrogram.types import InputMediaVideo, InputMediaDocument, InputMediaPhoto, InputMediaAudio
    from tools_media import get_meta, get_thumb
    from downloader import generate_caption
    from utils_chat_actions import chat_action_loop
    from pyrogram import enums
    import time
    
    media_group = []
    temp_thumbs = []
    job_dirs_to_clean = []
    
    ts = int(time.time())
    is_doc = conf.get('doc_mode', False)
    
    for idx, item in enumerate(batch_items):
        files = item.get('files', [])
        datos = item.get('datos', {})
        vid_id = item.get('vid_id')
        ckey = item.get('ckey')
        job_dir = item.get('job_dir')
        if job_dir:
            job_dirs_to_clean.append(job_dir)
            
        for j, f_path in enumerate(files):
            if not os.path.exists(f_path):
                continue
            
            final_caption = generate_caption(datos, conf)
            
            if f_path.lower().endswith(('.mp4', '.mkv', '.webm', '.ts')):
                width, height, duration = 0, 0, 0
                thumb_path = None
                try:
                    w, h, d = await get_meta(f_path)
                    width, height, duration = w, h, d
                    
                    seek_forced = None
                    if conf.get('parallel_thumb_mode'):
                         p_sec = conf.get('parallel_thumb_seek', 2)
                         m_sec, s = divmod(p_sec, 60)
                         hh, m_sec = divmod(m_sec, 60)
                         seek_forced = f"{int(hh):02d}:{int(m_sec):02d}:{s:02d}"
                         
                    thumb_path = await get_thumb(f_path, cid, f"{ts}_{idx}_{j}", duration, seek_override=seek_forced)
                    if thumb_path:
                        temp_thumbs.append(thumb_path)
                except Exception as e_meta:
                    print(f"Error getting meta/thumb: {e_meta}")
                    
                if is_doc:
                    media_group.append(InputMediaDocument(f_path, thumb=thumb_path, caption=final_caption))
                else:
                    media_group.append(InputMediaVideo(f_path, thumb=thumb_path, width=width, height=height, duration=duration, caption=final_caption, supports_streaming=True))
            elif f_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                media_group.append(InputMediaPhoto(f_path, caption=final_caption))
            elif f_path.lower().endswith(('.mp3', '.m4a', '.flac', '.wav', '.ogg')):
                duration = 0
                try:
                    from downloader import get_audio_dur
                    duration = await get_audio_dur(f_path)
                except: pass
                media_group.append(InputMediaAudio(f_path, caption=final_caption, duration=duration))
            else:
                media_group.append(InputMediaDocument(f_path, caption=final_caption))
                
    if media_group:
        try:
            action = enums.ChatAction.UPLOAD_DOCUMENT if is_doc else enums.ChatAction.UPLOAD_VIDEO
            async with chat_action_loop(c, cid, action):
                sent_msgs = await c.send_media_group(cid, media_group)
                if sent_msgs:
                    for sent_msg, item in zip(sent_msgs, batch_items):
                        fid = None
                        if sent_msg.video: fid = sent_msg.video.file_id
                        elif sent_msg.document: fid = sent_msg.document.file_id
                        elif sent_msg.audio: fid = sent_msg.audio.file_id
                        
                        vid_id = item.get('vid_id')
                        if fid and vid_id:
                            from firebase_service import save_cached_file_strict
                            print(f"✨ Saving Group Download to Cache: {vid_id}")
                            asyncio.create_task(save_cached_file_strict(vid_id, item.get('datos', {}).get('url'), item.get('ckey'), item.get('is_doc_mode'), fid))
        except Exception as e_group:
            print(f"❌ Error sending media group batch: {e_group}")
            for item in batch_items:
                for f_path in item.get('files', []):
                    if not os.path.exists(f_path): continue
                    final_caption = generate_caption(item.get('datos'), conf)
                    try:
                        if is_doc:
                            await c.send_document(cid, f_path, caption=final_caption)
                        else:
                            if f_path.lower().endswith(('.mp4', '.mkv', '.webm', '.ts')):
                                await c.send_video(cid, f_path, caption=final_caption)
                            else:
                                await c.send_document(cid, f_path, caption=final_caption)
                    except Exception as e_indiv:
                        print(f"Fallback send failed: {e_indiv}")
                        
    for t in temp_thumbs:
        if os.path.exists(t):
            try: os.remove(t)
            except: pass
            
    import shutil
    for jd in job_dirs_to_clean:
        if os.path.exists(jd):
            try: shutil.rmtree(jd, ignore_errors=True)
            except: pass


async def process_txt_file_download(c, m):
    cid = m.chat.id
    txt_path = await c.download_media(m)
    if not txt_path or not os.path.exists(txt_path):
        await m.reply("❌ Error al descargar el archivo TXT.")
        return
        
    try:
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        await m.reply(f"❌ Error al leer el archivo TXT: {e}")
        try: os.remove(txt_path)
        except: pass
        return
        
    try: os.remove(txt_path)
    except: pass
    
    urls = re.findall(r"(https?://\S+)", content)
    unique_urls = []
    seen = set()
    for u in urls:
        clean = limpiar_url(u)
        if clean not in seen:
            seen.add(clean)
            unique_urls.append(clean)
            
    if not unique_urls:
        await m.reply("⚠️ No se encontraron enlaces válidos en el archivo TXT.")
        return
        
    total = len(unique_urls)
    conf = get_config(cid)
    is_group = conf.get('group_mode', True)
    
    status_msg = await m.reply(f"📥 **Archivo TXT procesado.**\nEncontrados `{total}` enlaces.\nDescargando de 5 en 5... {'(Modo Agrupado Activo)' if is_group else ''}")
    
    sem = asyncio.Semaphore(5)
    
    if not is_group:
        async def worker(url, idx):
            base_link_id = int(time.time_ns() // 1000) + random.randint(10000, 99999)
            link_id_suffix = f"{base_link_id}_{idx}"
            async with sem:
                try:
                    await process_txt_url_flow(c, m, url, link_id_suffix, return_paths=False)
                except Exception as e:
                    print(f"Error downloading {url}: {e}")
                    
        tasks = [worker(url, idx) for idx, url in enumerate(unique_urls)]
        await asyncio.gather(*tasks)
        await status_msg.edit(f"✅ **Proceso TXT finalizado.** Se procesaron `{total}` enlaces.")
    else:
        downloaded_items = []
        downloaded_lock = asyncio.Lock()
        
        async def group_worker(url, idx):
            base_link_id = int(time.time_ns() // 1000) + random.randint(10000, 99999)
            link_id_suffix = f"{base_link_id}_{idx}"
            async with sem:
                try:
                    res = await process_txt_url_flow(c, m, url, link_id_suffix, return_paths=True)
                    if res and isinstance(res, dict) and res.get('files'):
                        async with downloaded_lock:
                            downloaded_items.append(res)
                            if len(downloaded_items) >= 10:
                                batch = downloaded_items[:10]
                                del downloaded_items[:10]
                                await upload_media_group_batch(c, cid, batch, conf)
                except Exception as e:
                    print(f"Error downloading {url} in group worker: {e}")
                    
        tasks = [group_worker(url, idx) for idx, url in enumerate(unique_urls)]
        await asyncio.gather(*tasks)
        
        if downloaded_items:
            await upload_media_group_batch(c, cid, downloaded_items, conf)
            
        await status_msg.edit(f"✅ **Proceso TXT finalizado.** Se procesaron `{total}` enlaces.")


async def process_txt_url_flow(c, m, l_u, link_id_suffix, return_paths=True):
    """
    Procesa un enlace individual para TXT y retorna las rutas descargadas.
    Asegura que procesar_descarga se ejecute con return_paths=True de forma síncrona/esperable.
    """
    cid = m.chat.id
    import re
    import time
    import random
    from pyrogram.errors import FloodWait
    from downloader import procesar_descarga
    
    if link_id_suffix:
        link_id = hex(int(link_id_suffix.split('_')[0]) + int(link_id_suffix.split('_')[1]))[2:]
    else:
        link_id = hex(int(time.time_ns() // 1000) + random.randint(10000, 99999))[2:]

    storage_key = f"{cid}_{link_id}"
    conf = get_config(cid)

    if conf.get('fmt') == 'mp3':
        url_info = {'url': l_u, 'titulo': "Audio Auto-MP3", 'fast_enabled': conf.get('fast_enabled', True)}
        res = await procesar_descarga(c, cid, l_u, "mp3", url_info, m, context_config=conf, return_paths=return_paths)
        return res

    if "twisted-brody-manga-flow" in l_u:
        try:
            if "#manga/" in l_u: raw_id = l_u.split("#manga/")[1]
            elif "/manga/" in l_u: raw_id = l_u.split("/manga/")[1]
            else: return None
            
            match_id = re.match(r'^([a-zA-Z0-9]+)', raw_id)
            mi_l = match_id.group(1) if match_id else raw_id.split("?")[0].strip()
            await show_manga_menu(c, m, mi_l, wait_msg=None)
        except: pass
        return None

    if any(x in l_u for x in ['twitter.com', 'x.com', 'pinterest.com', 'instagram.com', 'facebook.com']):
        try:
            c_file = sel_cookie(l_u)
            async with get_user_semaphore(cid, False, conf.get('max_downloads', 'default')):
                res_gal = await asyncio.get_running_loop().run_in_executor(None, lambda: descargar_galeria(l_u, c_file))
            if len(res_gal) == 3: paths, tmp, metadata_text = res_gal
            else: paths, tmp = res_gal; metadata_text = ""
            
            if paths:
                is_doc = conf.get('doc_mode', False)
                is_group = conf.get('group_mode', False)
                
                if is_doc:
                    for p in paths:
                        try: await c.send_document(cid, p, reply_to_message_id=m.id)
                        except: pass
                else:
                    if is_group and len(paths) > 1:
                        from pyrogram.types import InputMediaPhoto
                        batch_size = 10
                        for i in range(0, len(paths), batch_size):
                            chunk = paths[i:i + batch_size]
                            media = []
                            for j, p in enumerate(chunk):
                                media.append(InputMediaPhoto(p))
                            try: await c.send_media_group(cid, media, reply_to_message_id=m.id)
                            except: 
                                 for p in chunk: await c.send_photo(cid, p, reply_to_message_id=m.id)
                            await asyncio.sleep(1)
                    else:
                        for p in paths:
                            try: await c.send_photo(cid, p, reply_to_message_id=m.id)
                            except: pass
                import shutil
                try: shutil.rmtree(tmp)
                except: pass
        except: pass
        return None

    if "facebook.com" in l_u or "fb.watch" in l_u:
        l_u = await resolver_url_facebook(l_u)

    if any(x in l_u for x in ['jav', 'hpjav', 'missav', 'javtrailers', '7mmtv']):
        try:
            async with SEM_ANALYSIS:
                links_tuple = await asyncio.get_running_loop().run_in_executor(None, lambda: extraer_jav_directo(l_u))
            cover_url = None
            if isinstance(links_tuple, tuple):
                if len(links_tuple) == 3:
                    links, page_title, cover_url = links_tuple
                else:
                    links, page_title = links_tuple
            else:
                links, page_title = links_tuple, "JAV Video"
                
            if links:
                url_storage[storage_key] = {'url': l_u, 'id': f"jav_{int(time.time())}", 'titulo': page_title, 'html_links_data': links, 'cover_url': cover_url}
                q_auto = conf.get('q_auto', 'max')
                if q_auto not in ['max', 'min']: q_auto = 'max'
                target_q = f"html_0"
                d_st = url_storage[storage_key]
                d_st['fast_enabled'] = conf.get('fast_enabled', True)
                local_conf = conf.copy()
                
                return await procesar_descarga(c, cid, d_st['url'], target_q, d_st, m, context_config=local_conf, return_paths=return_paths)
        except: pass
        return None

    if "eporner.com" in l_u and "/video-" in l_u:
        try:
            from downloader import get_eporner_links, find_best_quality_index, find_worst_quality_index, find_fixed_quality_index
            async with SEM_ANALYSIS:
                page_title, links = await get_eporner_links(l_u)
            if links:
                eporner_id = "video"
                match_id = re.search(r'/video-([a-zA-Z0-9]+)/', l_u)
                if match_id: eporner_id = match_id.group(1)
                final_id = f"eporner_{eporner_id}"
                
                url_storage[storage_key] = {'url': l_u, 'id': final_id, 'titulo': page_title, 'html_links_data': links}
                
                q_auto = conf.get('q_auto', 'max')
                if q_auto not in ['max', 'min'] and q_auto not in ['4320', '2160', '1440', '1080', '720', '480', '360', '240', '144']:
                    q_auto = 'max'
                
                d_st = url_storage[storage_key]
                d_st['fast_enabled'] = conf.get('fast_enabled', True)
                local_conf = conf.copy()
                
                if q_auto == 'max':
                    best_idx = find_best_quality_index(links)
                    target_q = f"html_{best_idx}"
                elif q_auto == 'min':
                    worst_idx = find_worst_quality_index(links)
                    target_q = f"html_{worst_idx}"
                else:
                    target_res = int(q_auto)
                    fixed_idx = find_fixed_quality_index(links, target_res)
                    target_q = f"html_{fixed_idx}"
                
                return await procesar_descarga(c, cid, d_st['url'], target_q, d_st, m, context_config=local_conf, return_paths=return_paths)
        except Exception as e_ep:
            print(f"❌ TXT Mode Eporner Sniffer Error: {e_ep}")

    eporner_id = None
    is_direct = any(x in l_u for x in ['hentaila.com', 'fireload.com', 'mediafire.com', 'yourupload.com', 'mp4upload.com', 'rule34video.com/get_file/', 'xhamster.com', 'xhcdn.com'])
    if "eporner.com" in l_u and "/dload/" in l_u:
        is_direct = True
        try:
            parts = l_u.split('/dload/')
            if len(parts) > 1: eporner_id = parts[1].split('/')[0]
        except: pass

    surrit_id = None
    if "surrit.com" in l_u and ".m3u8" in l_u:
        is_direct = True
        try:
            match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', l_u)
            if match: surrit_id = match.group(1)
        except: pass

    if not is_direct and re.search(r'\.(mp4|mkv|webm|avi|mov)(/|\?|$)', l_u, re.I): is_direct = True

    if is_direct:
        if eporner_id: final_id = f"eporner_{eporner_id}"
        elif surrit_id: final_id = f"surrit_{surrit_id}"
        else: final_id = f"direct_{link_id_suffix}"
        
        url_storage[storage_key] = {'url': l_u, 'id': final_id, 'titulo': "Enlace Directo"}
        local_conf = conf.copy()
        return await procesar_descarga(c, m.chat.id, l_u, 'direct', url_storage[storage_key], m, context_config=local_conf, return_paths=return_paths)

    try:
        y_o = {
            'quiet': True, 
            'force_ipv4': False, 
            'nocheckcertificate': True, 
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'
            }
        }
        if "surrit.com" in l_u or "missav" in l_u:
            y_o['http_headers']['Referer'] = 'https://missav.ws/'
            y_o['extractor_args'] = {'generic': ['impersonate=chrome']}
        elif "xhand.net" in l_u or "xhamster.com" in l_u:
            y_o['http_headers']['Referer'] = 'https://xhand.net/' if "xhand.net" in l_u else 'https://es.xhamster.com/'
            y_o['http_headers']['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            y_o['extractor_args'] = {'generic': ['impersonate=chrome']}
            
        c_file = sel_cookie(l_u)
        if c_file: y_o['cookiefile'] = c_file

        y_i = None
        max_attempts = 2 if any(x in l_u for x in ['twitter.com', 'x.com', 'eporner.com']) else 10
        last_err = None
        for attempt in range(1, max_attempts + 1):
            try:
                async with SEM_ANALYSIS:
                    y_i = await asyncio.get_running_loop().run_in_executor(None, lambda: yt_dlp.YoutubeDL(y_o).extract_info(l_u, download=False))
                if y_i: break
            except Exception as ex:
                last_err = ex
                if attempt < max_attempts: await asyncio.sleep(2)
                
        if not y_i: raise last_err if last_err else Exception("YT-DLP fail")

        if y_i and 'entries' in y_i:
            if any(x in l_u for x in ['twitter.com', 'x.com']):
                entries = y_i['entries']
                count = len(entries)
                tw_results = []
                for idx, entry in enumerate(entries):
                    target_url = entry.get('url')
                    if not target_url and entry.get('formats'):
                        best_merged = next((f for f in entry['formats'] if f.get('vcodec') != 'none' and f.get('acodec') != 'none'), None)
                        best_m3u8 = next((f for f in entry['formats'] if 'm3u8' in f.get('url', '') or f.get('ext') == 'm3u8'), None)
                        target_url = best_merged.get('url') if best_merged else (best_m3u8.get('url') if best_m3u8 else entry['formats'][-1].get('url'))
                    if not target_url: target_url = entry.get('webpage_url', l_u)
                    
                    sub_info = {
                        'url': target_url,
                        'id': entry.get('id'),
                        'titulo': f"{entry.get('title', 'Video')} ({idx+1}/{count})",
                        'uploader': entry.get('uploader'),
                        'uploader_url': entry.get('uploader_url')
                    }
                    res_tw = await procesar_descarga(c, cid, sub_info['url'], "best", sub_info, m, context_config=conf, return_paths=return_paths)
                    if res_tw:
                        if isinstance(res_tw, list): tw_results.extend(res_tw)
                        else: tw_results.append(res_tw)
                    await asyncio.sleep(1)
                return tw_results
            else:
                y_i = y_i['entries'][0]

        formats = y_i.get('formats', [])
        y_f = []
        for fl in formats:
            hv = fl.get('height')
            if hv and hv not in y_f: y_f.append(hv)
            
        url_info = {'url': l_u, 'id': y_i.get('id'), 'titulo': y_i.get('title')}
        if 'surrit.com' in l_u and str(y_i.get('id')) in ['playlist', 'video']:
            match_uuid = re.search(r'surrit\.com/([a-zA-Z0-9-]+)', l_u)
            if match_uuid: url_info['id'] = match_uuid.group(1)

        url_storage[storage_key] = url_info
        
        q_auto = conf.get('q_auto', 'max')
        if q_auto not in ['max', 'min'] and q_auto not in ['1080', '720', '480', '360', '240']:
            q_auto = 'max'
            
        target_q = "best"
        if y_f:
            start_l = sorted([int(x) for x in y_f])
            if q_auto == 'max': target_q = str(start_l[-1])
            elif q_auto == 'min': target_q = str(start_l[0])
            else:
                target_res = int(q_auto)
                below = [x for x in start_l if x <= target_res]
                target_q = str(below[-1]) if below else str(start_l[0])
                
        d_st = url_storage[storage_key]
        d_st['fast_enabled'] = conf.get('fast_enabled', True)
        local_conf = conf.copy()
        
        return await procesar_descarga(c, cid, d_st['url'], target_q, d_st, m, context_config=local_conf, return_paths=return_paths)
    except Exception as e:
        print(f"❌ TXT Mode YT-DLP Sniffer Error: {e}")
        
    return None


if __name__ == "__main__":
    try:
        # Servidor web asíncrono ahora se inicia en boot_services
        print('🚀 Iniciando Loop Principal del Bot...')
        loop = asyncio.get_event_loop()
        loop.run_until_complete(boot_services())

    except Exception as e:
        print(f"❌ CRITICAL BOT CRASH: {e}")
    except KeyboardInterrupt:
        print("🛑 Bot detenido manualmente.")