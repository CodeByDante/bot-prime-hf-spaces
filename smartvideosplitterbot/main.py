import asyncio
import os
import sys
import time
import logging
import traceback

def safe_join(*args):
    """Junta rutas de forma segura convirtiendo None a string."""
    try:
        # Filtrar None y asegurar que todo sea string
        safe_args = [str(a) if a is not None else "unknown" for a in args]
        return os.path.join(*safe_args)
    except Exception as e:
        print(f"⚠️ [SafeJoin Error] {e}")
        return "downloads" # Fallback universal
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message,
    InputMediaDocument, InputMediaVideo, InputMediaAudio
)
from pyrogram.errors import MessageNotModified, FloodWait
from tools_media import progreso

# Configuraciones y DB
from config import API_ID, API_HASH, BOT_TOKEN, DOWNLOAD_DIR
from database import get_config, user_config
from firebase_service import save_user_config_fb, load_all_user_configs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- WEB SERVER (Salud y Base) ---
async def handle_health(request):
    img = "https://codebydante-brodyfilestreambot.hf.space/stream/88882?hash=9800aa"
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Smart Splitter | Stealth</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;900&display=swap" rel="stylesheet">
        <style>
            body {{
                margin: 0; padding: 0;
                background: #000000;
                font-family: 'Outfit', sans-serif;
                height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
                perspective: 1000px;
            }}
            .bg-subtle {{
                position: fixed;
                top: 0; left: 0; width: 100%; height: 100%;
                background: url('{img}') no-repeat center center;
                background-size: cover;
                filter: blur(120px) grayscale(1) brightness(0.12);
                z-index: -1;
            }}
            .container {{
                text-align: center;
                animation: float 6s ease-in-out infinite;
            }}
            @keyframes float {{
                0%, 100% {{ transform: translateY(0); }}
                50% {{ transform: translateY(-15px); }}
            }}
            .img-wrapper {{
                width: 320px;
                height: 320px;
                margin: 0 auto 4rem;
                padding: 2px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 2.5rem;
                box-shadow: 0 40px 100px -20px rgba(0,0,0,1);
                position: relative;
                transition: all 0.6s cubic-bezier(0.23, 1, 0.32, 1);
                transform-style: preserve-3d;
            }}
            .img-wrapper::after {{
                content: '';
                position: absolute;
                inset: -20px;
                background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%);
                opacity: 0;
                transition: opacity 0.6s;
                z-index: -1;
                border-radius: 4rem;
            }}
            .img-wrapper:hover {{
                transform: rotateX(10deg) rotateY(10deg) scale(1.05);
                background: rgba(255, 255, 255, 0.3);
                box-shadow: 0 60px 120px -20px rgba(255,255,255,0.1);
            }}
            .img-wrapper:hover::after {{ opacity: 1; }}
            .img-wrapper img {{
                width: 100%;
                height: 100%;
                object-fit: cover;
                border-radius: 2.4rem;
                filter: contrast(1.1) brightness(0.9);
                transition: filter 0.6s;
            }}
            .img-wrapper:hover img {{ filter: contrast(1.2) brightness(1.1); }}
            .btn {{
                background: #000000;
                color: #ffffff;
                padding: 1.5rem 4.5rem;
                border-radius: 1.2rem;
                text-decoration: none;
                font-weight: 900;
                font-size: 1rem;
                letter-spacing: 0.2em;
                display: inline-block;
                text-transform: uppercase;
                transition: all 0.5s cubic-bezier(0.165, 0.84, 0.44, 1);
                border: 2px solid white;
                position: relative;
                overflow: hidden;
            }}
            .btn:hover {{
                background: #ffffff;
                color: #000000;
                box-shadow: 0 20px 50px rgba(255,255,255,0.3);
                transform: translateY(-5px);
            }}
            .btn::before {{
                content: '';
                position: absolute;
                top: 0; left: -100%;
                width: 100%; height: 100%;
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
                transition: 0.5s;
            }}
            .btn:hover::before {{ left: 100%; }}
        </style>
    </head>
    <body>
        <div class="bg-subtle"></div>
        <div class="container">
            <div class="img-wrapper">
                <img src="{img}" alt="Smart Video Splitter">
            </div>
            <a href="https://t.me/SmartVideoSplitterBot" class="btn">
                BOT DE TELEGRAM
            </a>
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
    print("🌍 Servidor Base activo en puerto 7860")

# --- FIX WINDOWS ---
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- PYROGRAM CLIENT ---
WORKDIR = "sessions"
if not os.path.exists(WORKDIR):
    os.makedirs(WORKDIR)

app = Client(
    "brody_base_bot_v2", 
    api_id=int(API_ID),
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN, 
    workers=100,
    workdir=WORKDIR,
    ipv6=False,
    sleep_threshold=60,
    max_concurrent_transmissions=16
)

# Limitadores (No eliminar)
PARTY_SEND_LOCKS = {}
USER_PROCESSING_LOCKS = {}
USER_QUEUE_COUNTS = {}
SEM_PARTY = asyncio.Semaphore(8)
PARTY_STATE = {} # Para configurar cortes
WAITING_FOR_CONFIG = {} # {chat_id: {message_id: Message}} - Mensajes esperando configuración antes de descargar
ACTIVE_TASKS = {} # {chat_id: set(asyncio.Task)} - Tareas en ejecución por usuario
BOT_ICON_CACHE = {'file_id': None, 'last_check': 0}

async def get_bot_icon(client):
    """Obtiene el file_id de la foto de perfil del bot con cache de 1 hora."""
    now = time.time()
    if BOT_ICON_CACHE['file_id'] and (now - BOT_ICON_CACHE['last_check'] < 3600):
        return BOT_ICON_CACHE['file_id']
    
    try:
        async for photo in client.get_chat_photos("me", limit=1):
            BOT_ICON_CACHE['file_id'] = photo.file_id
            BOT_ICON_CACHE['last_check'] = now
            return photo.file_id
    except Exception as e:
        print(f"⚠️ Error al obtener foto del bot: {e}")
    return None

# --- MODO PARTY LÓGICA (Extraída pura) ---
async def run_party_logic(client, chat_id, file_path, mode, val, msg_to_edit=None, original_msg=None, context_config=None):
    from utils import split_video_generic, cut_video_range
    from tools_media import get_meta, get_thumb
    
    if context_config is None:
        context_config = get_config(chat_id)

    def get_precise_val():
        val = context_config.get('party_precise', False)
        return str(val).lower() == 'true' if isinstance(val, str) else bool(val)

    def get_ultra_val():
        v = context_config.get('party_ultra', False)
        return str(v).lower() == 'true' if isinstance(v, str) else bool(v)

    is_ultra = get_ultra_val()
    is_precise_initial = get_precise_val()
    p_mode_str = "🚀 Ultra" if is_ultra else ("🎯 Preciso" if is_precise_initial else "⚡️ Rápido")
    
    if msg_to_edit:
        await msg_to_edit.edit(f"⏳ Procesando Party ({mode}={val})\nModo: **{p_mode_str}**")
    else:
        msg_to_edit = await client.send_message(chat_id, f"⏳ Procesando Party ({mode}={val})\nModo: **{p_mode_str}**")

    print(f"[PARTY LOGIC] Starting process for user {chat_id}. Mode: {mode}, Val: {val}, Precise: {is_precise_initial}")

    try:
        # Re-enviar video original y ANCLARLO (Nueva petición del usuario)
        if original_msg:
            try:
                pinned_msg = await original_msg.copy(chat_id, caption="🎬 **Video Original**")
                await pinned_msg.pin(both_sides=True)
            except Exception as e:
                print(f"⚠️ Error al anclar original: {e}")

        from tools_media import get_meta
        _, _, duration, a_count = await get_meta(file_path)
        
        # --- NUEVO: SOPORTE MULTI-AUDIO (Extracción automática) ---
        if a_count > 1:
            try:
                await msg_to_edit.edit(f"🎧 **Detección Multi-Audio ({a_count} pistas)**\nExtrayendo audios por separado...")
                from utils import extract_all_audios
                audio_files = await asyncio.get_running_loop().run_in_executor(None, lambda: extract_all_audios(file_path, a_count))
                
                for i, audio in enumerate(audio_files):
                    try:
                        await client.send_audio(
                            chat_id, 
                            audio, 
                            caption=f"🎵 **Pista de Audio {i+1}** (Extraída automáticamente)",
                            title=f"Audio Track {i+1}",
                            performer="Smart Splitter"
                        )
                    except: pass
                    finally:
                        if os.path.exists(audio): os.remove(audio)
                
                await msg_to_edit.edit(f"✅ **{len(audio_files)} audios extraídos.**\nContinuando con el video...")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Error en extraccion multi-audio: {e}")
        
        segments = []
        if mode in ['parts', 'sec', 'min']:
            if mode == 'parts':
                num_parts = int(val)
                seg_time = duration / num_parts
                for i in range(num_parts):
                    segments.append((i * seg_time, (i+1) * seg_time, f"Parte {i+1}/{num_parts}"))
            elif mode == 'sec' or mode == 'min':
                seg_time = float(val) if mode == 'sec' else float(val) * 60
                cur = 0
                idx = 1
                while cur < duration:
                    end_t = min(cur + seg_time, duration)
                    if (end_t - cur) < 0.5: break # Ignorar trozos demasiado pequeños al final
                    segments.append((cur, end_t, f"Parte {idx}"))
                    cur += seg_time
                    idx += 1
        elif mode == 'range':
            pts = str(val).split()
            if len(pts) < 2 or len(pts) % 2 != 0:
                await msg_to_edit.edit("❌ Formato de rango inválido. Deben ser pares (Ej: '10 20').")
                return False
            for i in range(0, len(pts), 2):
                segments.append((pts[i], pts[i+1], f"Corte {i//2 + 1}"))

        if not segments:
            await msg_to_edit.edit("❌ No hay segmentos para procesar. Quizá el video es muy corto.")
            return False

        is_zip_mode = context_config.get('party_zip', False)
        is_doc_mode = context_config.get('party_doc', False)
        use_group_mode = context_config.get('party_group', False) and len(segments) > 1 and not is_zip_mode
        
        # Nota: ZIP mode sigue necesitando procesar todo antes de enviar
        if is_zip_mode:
            all_parts = []
            await msg_to_edit.edit("⏳ Procesando todas las partes para ZIP...")
            if is_ultra and mode != 'range':
                all_parts = await asyncio.get_running_loop().run_in_executor(None, lambda: split_video_generic(file_path, mode, val))
            else:
                for s, e, lbl in segments:
                    current_precise = get_precise_val()
                    p_path = await asyncio.get_running_loop().run_in_executor(None, lambda: cut_video_range(file_path, s, e, precise=current_precise))
                    if p_path: all_parts.append(p_path)
            
            await msg_to_edit.edit(f"📦 Comprimiendo {len(all_parts)} partes...")
            from utils import create_split_zips
            
            # DEBUG: Logging arguments for os.path.join
            base_dir_val = os.path.dirname(file_path) if file_path else "downloads"
            print(f"[DEBUG] zip_target join - base_dir: {base_dir_val}")
            
            zip_target_base = safe_join(base_dir_val or "downloads", f"party_{int(time.time())}")
            zip_files = await asyncio.get_running_loop().run_in_executor(None, lambda: create_split_zips(all_parts, zip_target_base))
            
            # Enviar ZIPs
            for p in all_parts: 
                try: os.remove(p)
                except: pass
            
            for i, z in enumerate(zip_files):
                await client.send_document(chat_id, z, caption=f"📦 Pack ZIP {i+1}/{len(zip_files)}", progress=progreso, progress_args=(msg_to_edit, [0.0, 0], "Subiendo ZIP"))
            return True

        # FLUJO DE PROCESAMIENTO MULTIPLE (PIPELINE: Cortar en paralelo mientras se sube)
        if chat_id not in PARTY_SEND_LOCKS:
             PARTY_SEND_LOCKS[chat_id] = asyncio.Lock()
             
        async with PARTY_SEND_LOCKS[chat_id]:
            queue = asyncio.Queue(maxsize=3) # Buffer pequeño para no saturar disco
            total_segments = len(segments)
            ts_base = int(time.time())

            # TAREA PRODUCTORA: Se encarga de cortar los videos en segundo plano (paralelismo límite 3)
            async def producer():
                try:
                    if is_ultra and mode != 'range':
                        await msg_to_edit.edit(f"🚀 **Modo Ultra Rápido** ({mode}={val})\nCortando todo en una sola pasada...")
                        u_paths = await asyncio.get_running_loop().run_in_executor(None, lambda: split_video_generic(file_path, mode, val))
                        for i, upath in enumerate(u_paths):
                            await queue.put((upath, f"Parte {i+1}", i+1))
                        return

                    sem = asyncio.Semaphore(3)
                    async def process_part(idx_inner, s_inner, e_inner, lbl_inner):
                        async with sem:
                            current_precise = get_precise_val()
                            p = await asyncio.get_running_loop().run_in_executor(None, lambda: cut_video_range(file_path, s_inner, e_inner, precise=current_precise))
                            return p, lbl_inner, idx_inner + 1

                    pending = {}
                    nxt = 0
                    
                    for i, (s, e, lbl) in enumerate(segments):
                        pending[i] = asyncio.create_task(process_part(i, s, e, lbl))
                        
                        while nxt in pending and (pending[nxt].done() or len(pending) >= 3):
                            res = await pending.pop(nxt)
                            if res[0]:
                                await queue.put(res)
                            nxt += 1
                            
                    while nxt < len(segments):
                        if nxt in pending:
                            res = await pending.pop(nxt)
                            if res[0]:
                                await queue.put(res)
                        nxt += 1

                except asyncio.CancelledError:
                    return # Salir si se cancela
                except Exception as e:
                    print(f"Error cortando parte: {e}")
                finally:
                    await queue.put(None) # Señal de fin

            producer_task = asyncio.create_task(producer())
            processed_count = 0

            # TAREA CONSUMIDORA: Subida secuencial (1 a la vez) para orden perfecto
            while True:
                item = await queue.get()
                if item is None: break
                
                # Si es ALBUM, lo manejamos como bloque
                if use_group_mode:
                    pending_group = [item]
                    for _ in range(9):
                        if queue.empty(): break
                        nxt = await queue.get(); 
                        if nxt is None: await queue.put(None); break
                        pending_group.append(nxt)
                    
                    media_group = []; temp_thumbs = []
                    for gp_path, gp_lbl, gp_idx in pending_group:
                        gp_is_audio = gp_path.lower().endswith(('.mp3', '.ogg', '.wav', '.flac', '.m4a', '.aac'))
                        w, h, dur, _ = await get_meta(gp_path)
                        
                        t_path = None
                        if not gp_is_audio and not is_doc_mode:
                            t_path = await get_thumb(gp_path, chat_id, f"{ts_base}_{gp_idx}")
                            if t_path:
                                temp_thumbs.append(t_path)
                                
                        cap = f"🎉 Party: {gp_lbl.split()[0]} {gp_idx}/{total_segments}"
                        if is_doc_mode: media_group.append(InputMediaDocument(media=gp_path, thumb=t_path, caption=cap))
                        elif gp_is_audio: media_group.append(InputMediaAudio(media=gp_path, duration=dur, caption=cap))
                        else: media_group.append(InputMediaVideo(media=gp_path, thumb=t_path, width=w, height=h, duration=dur, caption=cap))
                    
                    try: 
                        p_mode_label = "🚀 Ultra" if is_ultra else ("🎯 Preciso" if get_precise_val() else "⚡️ Rápido")
                        await msg_to_edit.edit(f"📤 Enviando bloque ({pending_group[-1][2]}/{total_segments})...\nModo: **{p_mode_label}**")
                    except: pass
                    
                    for att in range(4):
                        try:
                            await client.send_media_group(chat_id, media_group)
                            break
                        except FloodWait as e:
                            print(f"⚠️ FloodWait ({e.value}s) durante Album")
                            await asyncio.sleep(e.value + 2)
                        except Exception as e:
                            print(f"Album Error: {e}")
                            break
                    
                    for t in temp_thumbs: 
                        if t and os.path.exists(t): os.remove(t)
                    for gp_p, _, _ in pending_group:
                        if os.path.exists(gp_p): os.remove(gp_p)
                    await asyncio.sleep(1.2)
                else:
                    # ENVÍO INDIVIDUAL SECUENCIAL
                    p_path, lbl, idx = item
                    is_doc_mode = context_config.get('party_doc', False)
                    is_audio_file = p_path.lower().endswith(('.mp3', '.ogg', '.wav', '.flac', '.m4a', '.aac', '.wma', '.mka'))
                    
                    lbl_type = "Documento" if is_doc_mode else ("Audio" if is_audio_file else "Video")
                    cap_lbl = f"🎉 Party: {lbl.split()[0]} {idx}/{total_segments}"
                    
                    try:
                        p_mode_icon = "🚀" if is_ultra else ("🎯" if context_config.get('party_precise', False) else "⚡️")
                        lbl_act = f"{p_mode_icon} Subiendo {lbl_type} ({idx}/{total_segments})"
                        
                        w, h, dur, _ = await get_meta(p_path)
                        t_path = await get_thumb(p_path, chat_id, f"{ts_base}_{idx}", duration=dur) if not is_doc_mode and not is_audio_file else None
                        
                        for att in range(4):
                            try:
                                if is_doc_mode:
                                     await client.send_document(chat_id, p_path, caption=cap_lbl, force_document=True, progress=progreso, progress_args=(msg_to_edit, [0.0, 0], lbl_act))
                                elif is_audio_file:
                                     await client.send_audio(chat_id, p_path, duration=dur, caption=cap_lbl, progress=progreso, progress_args=(msg_to_edit, [0.0, 0], lbl_act))
                                else:
                                    await client.send_video(chat_id, p_path, width=w, height=h, duration=dur, thumb=t_path, caption=cap_lbl, progress=progreso, progress_args=(msg_to_edit, [0.0, 0], lbl_act))
                                break
                            except FloodWait as e:
                                print(f"⚠️ FloodWait ({e.value}s) en individual")
                                await asyncio.sleep(e.value + 2)
                            except Exception as e:
                                print(f"Error interno pyrogram: {e}")
                                break
                    except Exception as e:
                        print(f"Error subiendo {idx}: {e}")
                    finally:
                        if 't_path' in locals() and t_path and os.path.exists(t_path):
                            try: os.remove(t_path)
                            except: pass
                    
                    if os.path.exists(p_path): os.remove(p_path)
                    await asyncio.sleep(1) # Pausa suave para orden garantizado

            producer_task.cancel() # Asegurar cierre de productora
            await producer_task
        
        # 3. Limpieza y Reseteo de Estado
        try: await msg_to_edit.delete()
        except: pass

        import shutil
        job_dir = os.path.dirname(file_path)
        if job_dir and 'job_' in os.path.basename(job_dir) and os.path.exists(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)

        is_auto = context_config.get('party_auto', False)
        if not is_auto:
            context_config['party_mode'] = False
            # Guardamos el reseteo en Firebase para que la próxima vez pregunte
            asyncio.create_task(save_user_config_fb(chat_id, context_config.copy()))
            await client.send_message(chat_id, "✅ **Proceso terminado.** (Envía otro video cuando quieras)")
        else:
            await client.send_message(chat_id, "✅ **Proceso terminado.**\n*(Modo AUTO activo: enviando siguiente automáticamente)*")
            
        return True
    except Exception as e:
        print(f"❌ ERROR CRÍTICO EN run_party_logic:")
        traceback.print_exc()
        if msg_to_edit: 
            try: await msg_to_edit.edit(f"❌ Error General en Party: {e}")
            except: pass
        return False

# --- MENÚS (INTERACTIVOS) ---
async def send_panel(client, chat_id, message_id=None):
    conf = get_config(chat_id)
    party_on = conf.get('party_mode')
    s_auto = "🟢" if conf.get('party_auto') else "🔴"
    s_zip = "🟢" if conf.get('party_zip') else "🔴"
    s_doc = "🟢" if conf.get('party_doc') else "🔴"
    s_group = "🟢" if conf.get('party_group', False) else "🔴"
    s_precise = "🟢" if conf.get('party_precise', False) else "🔴"
    s_ultra = "🟢" if conf.get('party_ultra', False) else "🔴"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥳 Modo Party", callback_data="menu|party_init")],
        [InlineKeyboardButton(f"📄 Doc: {s_doc}", callback_data="toggle|party_doc"),
         InlineKeyboardButton(f"📚 Agrup: {s_group}", callback_data="toggle|party_group")],
        [InlineKeyboardButton(f"🔄 Auto: {s_auto}", callback_data="menu|auto_init"),
         InlineKeyboardButton(f"📦 ZIP: {s_zip}", callback_data="toggle|party_zip")],
        [InlineKeyboardButton(f"🎯 Preciso: {s_precise}", callback_data="toggle|party_precise"),
         InlineKeyboardButton(f"🚀 Ultra: {s_ultra}", callback_data="toggle|party_ultra")]
    ])
    txt = "⚡️ **Smart Video Splitter PRO**\n\nEl sistema más avanzado para procesar, recortar y dividir todos tus videos con la máxima velocidad y calidad."
    
    photo = await get_bot_icon(client)
    
    try:
        if message_id:
            if photo:
                try:
                    await client.edit_message_caption(chat_id, message_id, caption=txt, reply_markup=kb)
                except:
                    # Si falla (tal vez no era un mensaje con foto), enviamos uno nuevo
                    await client.send_photo(chat_id, photo, caption=txt, reply_markup=kb)
            else:
                await client.edit_message_text(chat_id, message_id, txt, reply_markup=kb)
        else:
            if photo:
                await client.send_photo(chat_id, photo, caption=txt, reply_markup=kb)
            else:
                await client.send_message(chat_id, txt, reply_markup=kb)
    except MessageNotModified:
        pass
    except Exception as e:
        print(f"Error send_panel: {e}")

# --- COMANDO START ---
@app.on_message(filters.command(["start", "party"]) & filters.private)
async def start_cmd(client: Client, message: Message):
    cmd = message.command[0]
    chat_id = message.chat.id
    conf = get_config(chat_id)

    if cmd == "party":
        conf['party_mode'] = True
        asyncio.create_task(save_user_config_fb(chat_id, conf))
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧩 Partes", callback_data="party_view|parts"),
             InlineKeyboardButton("⏱ Tiempo", callback_data="party_view|sec")],
            [InlineKeyboardButton("✂️ Rango", callback_data="party_view|range")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu|main")]
        ])
        await message.reply("🎉 **Modo Party Activo**\n\n1️⃣ Configura abajo 👇\n2️⃣ O envía video directo.", reply_markup=kb)
    else:
        await send_panel(client, chat_id)

@app.on_message(filters.command("cancelar") & filters.private)
async def cancel_cmd_logic(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in ACTIVE_TASKS and ACTIVE_TASKS[chat_id]:
        for task in list(ACTIVE_TASKS[chat_id]):
            try: task.cancel()
            except: pass
        ACTIVE_TASKS[chat_id].clear()
        await message.reply("🛑 **Proceso(s) cancelado(s) manualmente con comando.**")
    else:
        await message.reply("⚠️ No tienes ningún proceso activo para cancelar.")

# --- HANDLER BOTONES ---
@app.on_callback_query()
async def menu_callback(c: Client, q: CallbackQuery):
    chat_id = q.message.chat.id
    conf = get_config(chat_id)
    data = q.data

    # --- Pre-respuesta para evitar el "spinning" del botón ---
    # Solo evitamos responder aquí si el handler de abajo va a dar una respuesta con texto (Toast)
    if not (data.startswith("party_val|") or data.startswith("party_ask|")):
        try: await q.answer()
        except: pass

    if data == "menu|main":
        await send_panel(c, chat_id, q.message.id)
        return

    if data == "menu|auto_init":
        s_auto = "🟢 ENCENDIDO" if conf.get('party_auto') else "🔴 APAGADO"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Estado: {s_auto}", callback_data="toggle|party_auto")],
            [InlineKeyboardButton("⚙️ Personalizado", callback_data="menu|auto_custom")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu|main")]
        ])
        await q.message.edit_text("🔄 **Menu Auto Party**\n\nSi activas esto, el Modo Party NO se desactivará al terminar un video.\nTodos los videos que envíes serán procesados.", reply_markup=kb)
        return

    if data == "menu|auto_custom":
        mode = conf.get('party_cut_mode', 'sec')
        val = conf.get('party_val', 30)
        # Mapping labels
        labels = {'sec': 'Tiempo', 'parts': 'Partes', 'range': 'Rango'}
        mode_label = labels.get(mode, mode)
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔧 Config: {mode_label}={val}", callback_data="party_view|parts|auto")], 
            [InlineKeyboardButton("🧩 Partes", callback_data="party_view|parts|auto"),
             InlineKeyboardButton("⏱ Tiempo", callback_data="party_view|sec|auto")],
            [InlineKeyboardButton("✂️ Rango", callback_data="party_view|range|auto")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu|auto_init")]
        ])
        await q.message.edit_text("⚙️ **Auto Party Personalizado**\n\nConfiguración global para cuando el Modo Auto está activo.", reply_markup=kb)
        return
    if data == "menu|party_init":
        conf['party_mode'] = True
        asyncio.create_task(save_user_config_fb(chat_id, conf))
        
        mode = conf.get('party_cut_mode', 'sec')
        val = conf.get('party_val', 30)
        labels = {'sec': 'Tiempo', 'parts': 'Partes', 'range': 'Rango'}
        mode_label = labels.get(mode, mode)

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧩 Partes", callback_data="party_view|parts|main"),
             InlineKeyboardButton("⏱ Tiempo", callback_data="party_view|sec|main")],
            [InlineKeyboardButton("✂️ Rango", callback_data="party_view|range|main")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu|main")]
        ])
        
        await q.message.edit_text("🎉 **Configuración Modo Party**\n\n¿Cómo quieres dividir tus videos? Selecciona una opción abajo 👇", reply_markup=kb)
        return

    # Sub-Vistas detalladas
    if data.startswith("party_view|"):
        args = data.split("|")
        mode = args[1]
        context = args[2] if len(args) > 1 else 'main'
        
        # Corregir navegación: Volver debe ir al origen correcto
        if context == 'main': back_target = "menu|party_init"
        elif context == 'auto': back_target = "menu|auto_custom"
        elif context.startswith('direct_'): back_target = f"menu|direct_back_{context.split('_')[1]}"
        else: back_target = "menu|direct_back" # Para cuando se envía un video directo

        if mode == "parts":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("2", callback_data=f"party_val|parts|2|{context}"), InlineKeyboardButton("3", callback_data=f"party_val|parts|3|{context}"), InlineKeyboardButton("4", callback_data=f"party_val|parts|4|{context}")],
                [InlineKeyboardButton("5", callback_data=f"party_val|parts|5|{context}"), InlineKeyboardButton("10", callback_data=f"party_val|parts|10|{context}")],
                [InlineKeyboardButton("✏️ Manual", callback_data=f"party_ask|parts|{context}")],
                [InlineKeyboardButton("🔙 Volver", callback_data=back_target)]
            ])
            await q.message.edit_text("🧩 **Dividir en Partes**\n¿En cuántas partes cortarlo?", reply_markup=kb)
            return

        if mode == "sec":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("10s", callback_data=f"party_val|sec|10|{context}"), InlineKeyboardButton("30s", callback_data=f"party_val|sec|30|{context}"), InlineKeyboardButton("1m", callback_data=f"party_val|sec|60|{context}")],
                [InlineKeyboardButton("5m", callback_data=f"party_val|sec|300|{context}"), InlineKeyboardButton("10m", callback_data=f"party_val|sec|600|{context}")],
                [InlineKeyboardButton("✏️ Manual (seg)", callback_data=f"party_ask|sec|{context}"), InlineKeyboardButton("✏️ Manual (min)", callback_data=f"party_ask|min|{context}")],
                [InlineKeyboardButton("🔙 Volver", callback_data=back_target)]
            ])
            await q.message.edit_text("⏱ **Dividir por Duración**\n¿De cuánto cada parte?", reply_markup=kb)
            return

        if mode == "range":
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data=back_target)]])
            PARTY_STATE[chat_id] = f'range|{context}'
            await q.message.edit_text("✂️ **Cortar Rango(s)**\n\nEnvía pares de inicio y fin.\nEjemplo: `00:10 01:30` (Un corte)\nEjemplo Múltiple: `00:10 00:20 01:00 01:30` (Dos cortes)", reply_markup=kb)
            return

    # Handlers de Valor Rápido
    if data.startswith("party_val|"):
        args = data.split("|")
        mode, val = args[1], args[2]
        context = args[3] if len(args) > 3 else 'main'
        conf['party_cut_mode'] = mode
        conf['party_val'] = val
        asyncio.create_task(save_user_config_fb(chat_id, conf))
        await c.answer_callback_query(q.id, f"✅ Configurado: {mode}={val}")
        
        # Comprobar si hay un video esperando para procesar (Solo si viene de configuración directa)
        if chat_id in WAITING_FOR_CONFIG and context.startswith('direct_'):
            target_id_str = context.split('_')[1]
            if target_id_str.isdigit():
                target_id = int(target_id_str)
                if target_id in WAITING_FOR_CONFIG[chat_id]:
                    original_msg = WAITING_FOR_CONFIG[chat_id].pop(target_id)
                    try:
                        await q.message.delete()
                    except:
                        pass
                    # Lanzar la tarea de descarga y proceso
                    asyncio.create_task(process_video_flow(c, original_msg, conf, mode, val))
                    return

        # Vista simplificada tras configurar
        if context == 'main':
             labels = {'sec': 'Tiempo', 'parts': 'Partes', 'range': 'Rango'}
             mode_label = labels.get(mode, mode)
             kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver al Inicio", callback_data="menu|main")]])
             txt = (f"✅ Configurado: **{mode_label}={val}**\n\n"
                    "🎉 **Modo Party Activo**\n"
                    "🎬 **Ahora envíame el video para procesarlo.**")
             await q.message.edit_text(txt, reply_markup=kb)
        elif context == 'auto':
             # Volver al menú de Auto Custom
             mode_ac = conf.get('party_cut_mode', 'sec')
             val_ac = conf.get('party_val', 30)
             labels = {'sec': 'Tiempo', 'parts': 'Partes', 'range': 'Rango'}
             mode_label = labels.get(mode_ac, mode_ac)
             kb = InlineKeyboardMarkup([
                 [InlineKeyboardButton(f"🔧 Config: {mode_label}={val_ac}", callback_data="party_view|parts|auto")], 
                 [InlineKeyboardButton("🧩 Partes", callback_data="party_view|parts|auto"),
                  InlineKeyboardButton("⏱ Tiempo", callback_data="party_view|sec|auto")],
                 [InlineKeyboardButton("✂️ Rango", callback_data="party_view|range|auto")],
                 [InlineKeyboardButton("🔙 Volver", callback_data="menu|auto_init")]
             ])
             await q.message.edit_text("⚙️ **Auto Party Personalizado**\n\nConfiguración global para cuando el Modo Auto está activo.", reply_markup=kb)
        return

    if data.startswith("menu|direct_back"):
        target_id = ""
        if len(data.split("_")) > 2:
            target_id = "_" + data.split("_")[2]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧩 Partes", callback_data=f"party_view|parts|direct{target_id}"),
             InlineKeyboardButton("⏱ Tiempo", callback_data=f"party_view|sec|direct{target_id}")],
            [InlineKeyboardButton("✂️ Rango", callback_data=f"party_view|range|direct{target_id}")]
        ])
        await q.message.edit_text("🎬 **¡Video recibido!**\n\n¿Cómo deseas dividirlo? Selecciona una opción abajo:", reply_markup=kb)
        return

    if data.startswith("party_ask|"):
        args = data.split("|")
        mode = args[1]
        context = args[2] if len(args) > 2 else 'main'
        PARTY_STATE[chat_id] = f'{mode}|{context}'
        await c.answer_callback_query(q.id, "✏️ Esperando valor...")
        await q.message.reply(f"⚙️ Envíame el valor para `{mode}`:")
        return

    if data.startswith("toggle|"):
        key = data.split("|")[1]
        
        # Redirecciones para menús específicos
        if key == "party_auto":
            new_val = not conf.get('party_auto', False)
            conf['party_auto'] = new_val
            if not new_val:
                conf['party_mode'] = False
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            await menu_callback(c, type('obj', (object,), {'message': q.message, 'data': 'menu|auto_init', 'id': q.id})())
            return
            
        # Limpiar prefijos si ya los tiene
        clean_key = key.replace("party_", "")
        if clean_key in ['doc', 'group', 'auto', 'zip', 'precise', 'ultra']:
            key = "party_" + clean_key
            
        conf[key] = not conf.get(key, False)
        
        # Aseguramos exclusividad mutua entre Preciso y Ultra Rápido
        if key == "party_precise" and conf[key]:
            conf["party_ultra"] = False
        elif key == "party_ultra" and conf[key]:
            conf["party_precise"] = False
            
        print(f"[DEBUG] Toggle {key} -> {conf[key]}")
        asyncio.create_task(save_user_config_fb(chat_id, conf))
        await send_panel(c, chat_id, q.message.id)
        return

    if data.startswith("cancel|"):
        target_id = int(data.split("|")[1])
        if target_id in ACTIVE_TASKS and ACTIVE_TASKS[target_id]:
            for task in list(ACTIVE_TASKS[target_id]):
                try: task.cancel()
                except: pass
            ACTIVE_TASKS[target_id].clear()
            await c.answer_callback_query(q.id, "🛑 Proceso(s) cancelado(s).")
            try: await q.message.edit_text("❌ **Proceso cancelado por el usuario.**")
            except: pass
        else:
            await c.answer_callback_query(q.id, "⚠️ No hay procesos activos.")
        return
    
    # Asegurar que se responde al final si no se hizo antes (Fallback)
    try: await q.answer()
    except: pass

@app.on_message(filters.text & filters.private)
async def handle_text(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in PARTY_STATE:
        state_data = PARTY_STATE[chat_id].split("|")
        mode = state_data[0]
        context = state_data[1] if len(state_data) > 1 else 'main'
        
        val = message.text.strip()
        conf = get_config(chat_id)
        if mode == 'min':
            try: val = str(float(val) * 60); mode = 'sec'
            except: pass
        conf['party_cut_mode'] = mode
        conf['party_val'] = val
        asyncio.create_task(save_user_config_fb(chat_id, conf))
        del PARTY_STATE[chat_id]
        
        await message.reply(f"✅ Configurado corte por `{mode}`: `{val}`.")
        
        await message.reply(f"✅ Configurado corte por `{mode}`: `{val}`.")
        
        # Comprobar si hay un video esperando (Solo si viene de configuración directa)
        if chat_id in WAITING_FOR_CONFIG and context.startswith('direct_'):
            target_id_str = context.split('_')[1]
            if target_id_str.isdigit():
                target_id = int(target_id_str)
                if target_id in WAITING_FOR_CONFIG[chat_id]:
                    original_msg = WAITING_FOR_CONFIG[chat_id].pop(target_id)
                    asyncio.create_task(process_video_flow(client, original_msg, conf, mode, val))
                    return

        # Re-enviar menú según contexto
        await send_panel(client, chat_id)


@app.on_message((filters.video | filters.document | filters.video_note | filters.audio | filters.voice) & filters.private)
async def handle_media(client: Client, message: Message):
    if message.document:
        mime = getattr(message.document, "mime_type", "") or ""
        fname = getattr(message.document, "file_name", "") or ""
        is_video = mime.startswith("video/") or fname.lower().endswith((".mp4", ".ts", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv"))
        is_audio = mime.startswith("audio/") or fname.lower().endswith((".mp3", ".ogg", ".wav", ".flac", ".m4a", ".aac"))
        if not is_video and not is_audio:
            await message.reply("⚠️ **El documento enviado no es multimedia válido.**\nSube un archivo de video o audio para continuar.", quote=True)
            return

    chat_id = message.chat.id
    conf = get_config(chat_id)
    
    # Soporte para Video Note (mensaje circular) y notas de voz
    if message.video_note or getattr(message, "voice", None):
        # Los Video Note o Voces no suelen tener modo AUTO configurado de la misma forma, 
        # pero forzamos que se reconozcan como media para el resto del flujo.
        pass
    
    is_auto = conf.get('party_auto', False)
    is_manual = conf.get('party_mode', False)

    # LÓGICA DE DECISIÓN: Descarga directa si es AUTO o si viene de configuración MANUAL reciente
    if is_auto or is_manual:
        # APAGAR INSTANTÁNEO: si es manual, consumimos el estado para que no quede pegado.
        if is_manual and not is_auto:
            conf['party_mode'] = False
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            
        asyncio.create_task(process_video_flow(client, message, conf, conf.get('party_cut_mode', 'sec'), conf.get('party_val', 30)))
    else:
        # Enviar el formulario y esperar selección antes de descargar
        if chat_id not in WAITING_FOR_CONFIG:
            WAITING_FOR_CONFIG[chat_id] = {}
        WAITING_FOR_CONFIG[chat_id][message.id] = message
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧩 Partes", callback_data=f"party_view|parts|direct_{message.id}"),
             InlineKeyboardButton("⏱ Tiempo", callback_data=f"party_view|sec|direct_{message.id}")],
            [InlineKeyboardButton("✂️ Rango", callback_data=f"party_view|range|direct_{message.id}")]
        ])
        label_msg = "🎬 **¡Video recibido!**"
        if getattr(message, "video_note", None): label_msg = "🎬 **¡Video Mensaje recibido!**"
        elif getattr(message, "audio", None) or getattr(message, "voice", None) or (message.document and getattr(message.document, "mime_type", "").startswith("audio/")): label_msg = "🎵 **¡Audio recibido!**"

        try:
            await message.reply(f"{label_msg}\n\n¿Cómo deseas dividirlo? Selecciona una opción abajo para configurar el bot y comenzar el proceso:", reply_markup=kb, quote=True)
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            await message.reply(f"{label_msg}\n\n¿Cómo deseas dividirlo? Selecciona una opción abajo para configurar el bot y comenzar el proceso:", reply_markup=kb, quote=True)

@app.on_message(filters.private & ~filters.command(["start", "ayuda", "cancelar", "party", "auto"]) & ~filters.video & ~filters.document & ~filters.video_note & ~filters.audio & ~filters.voice)
async def reject_invalid_media(client: Client, message: Message):
    try:
        await message.reply("⚠️ **Formato no válido.**\n\nPor favor, envíame directamente un archivo de Video (.mp4, .mkv) o Audio (.mp3, .ogg) para procesarlo.", quote=True)
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        await message.reply("⚠️ **Formato no válido.**\n\nPor favor, envíame directamente un archivo de Video (.mp4, .mkv) o Audio (.mp3, .ogg) para procesarlo.", quote=True)

async def process_video_flow(client: Client, message: Message, conf, mode, val):
    """Encargado de gestionar el lock, descarga y ejecución de lógica."""
    chat_id = message.chat.id

    async def run_flow():
        if chat_id not in USER_PROCESSING_LOCKS:
            USER_PROCESSING_LOCKS[chat_id] = asyncio.Lock()
            
        if chat_id not in USER_QUEUE_COUNTS:
            USER_QUEUE_COUNTS[chat_id] = 0
            
        # Ya no anclamos el mensaje del usuario directamente, 
        # se anclará el re-envío dentro de run_party_logic
        pass
            
        status_msg = None
        is_queued = False
        if USER_PROCESSING_LOCKS[chat_id].locked():
            is_queued = True
            USER_QUEUE_COUNTS[chat_id] += 1
            queue_pos = USER_QUEUE_COUNTS[chat_id]
            try:
                status_msg = await message.reply(f"⏳ **Video en cola #{queue_pos}...**\nEsperando turno para procesar.", quote=True)
            except:
                pass

        job_dir = None
        async with USER_PROCESSING_LOCKS[chat_id]:
            try:
                if is_queued:
                    USER_QUEUE_COUNTS[chat_id] -= 1
                    if USER_QUEUE_COUNTS[chat_id] < 0:
                        USER_QUEUE_COUNTS[chat_id] = 0
                # Pre-calcular tamaño para el progreso instantáneo
                media = message.video or message.document or message.video_note
                size_mb = (media.file_size / 1048576) if media else 0
                
                txt_status = f"⬇️ **Descargando** 📁 `0.0/{size_mb:.1f} MB (0.0%)`"
                if status_msg:
                    try:
                        await status_msg.edit_text(txt_status)
                        msg_status = status_msg
                    except:
                        msg_status = await message.reply(txt_status, quote=True)
                else:
                    msg_status = await message.reply(txt_status, quote=True)
                
                # Fallback de seguridad para DOWNLOAD_DIR
                from config import DOWNLOAD_DIR
                base_download = DOWNLOAD_DIR if DOWNLOAD_DIR else "downloads"
                
                job_ts = int(time.time())
                job_id_val = message.id
                job_name = f"job_{chat_id}_{job_id_val}_{job_ts}"
                
                print(f"[DEBUG] process_video_flow join - base: {base_download}, name: {job_name}")
                job_dir = safe_join(base_download, job_name)
                os.makedirs(job_dir, exist_ok=True)
                
                media_obj = getattr(message, "document", None) or getattr(message, "video", None) or getattr(message, "video_note", None) or getattr(message, "audio", None) or getattr(message, "voice", None)
                if not media_obj:
                    await msg_status.edit("❌ No se encontró contenido multimedia para procesar.")
                    return

                # Garantizar que file_name nunca sea None para evitar TypeError en os.path.join
                file_name = getattr(media_obj, "file_name", None)
                if not file_name:
                    ext = ".mp4" # Default
                    if getattr(message, "video_note", None): ext = ".mp4"
                    elif getattr(message, "voice", None): ext = ".ogg"
                    elif getattr(message, "audio", None): ext = ".mp3"
                    file_name = f"media_{message.id}{ext}"
                
                # out_target con seguridad adicional
                print(f"[DEBUG] out_target join - job_dir: {job_dir}, file_name: {file_name}")
                ext_fallback = "" if "." in file_name else ext
                out_target = safe_join(job_dir or "downloads", file_name or f"media_{message.id}{ext_fallback}")
                
                from tools_media import fast_download
                file_path = await fast_download(client, message, out_target, msg_status, "Descargando")
                
                if file_path:
                    # En run_party_logic también pasamos el teclado de cancelar
                    await run_party_logic(client, chat_id, file_path, mode, val, msg_status, original_msg=message, context_config=conf)
                else:
                    try: await msg_status.edit("❌ No se pudo descargar el archivo.")
                    except: pass
            except asyncio.CancelledError:
                # Si se cancela, avisar y limpiar
                print(f"🛑 Tarea cancelada para el usuario {chat_id}")
            except Exception as e:
                print(f"❌ ERROR CRÍTICO EN process_video_flow:")
                traceback.print_exc()
                print(f"Error process_video_flow: {e}")
            finally:
                if job_dir and os.path.exists(job_dir):
                    import shutil; shutil.rmtree(job_dir, ignore_errors=True)
                
                curr_task = asyncio.current_task()
                if chat_id in ACTIVE_TASKS and curr_task in ACTIVE_TASKS[chat_id]:
                    ACTIVE_TASKS[chat_id].discard(curr_task)

    task = asyncio.create_task(run_flow())
    if chat_id not in ACTIVE_TASKS:
        ACTIVE_TASKS[chat_id] = set()
    ACTIVE_TASKS[chat_id].add(task)

async def main():
    await start_web_server()
    
    print("🔥 Cargando configuraciones desde Firebase...")
    try:
        remote_configs = await load_all_user_configs()
        if remote_configs:
            # RESET DE SEGURIDAD: Al iniciar el servidor, apagamos el Modo Party manual de todos
            # para evitar que descarguen solos por accidente tras un reset
            for uid in remote_configs:
                remote_configs[uid]['party_mode'] = False
                
            user_config.update(remote_configs)
            print(f"✅ {len(remote_configs)} configuraciones cargadas (con reset de seguridad).")
    except Exception as e:
        print(f"⚠️ Error cargando configs: {e}")

    await app.start()
    
    # Configurar Comandos Rápidos en el Botón [Menú] de Telegram
    try:
        from pyrogram.types import BotCommand
        await app.set_bot_commands([
            BotCommand("start", "⚙️ Menú Principal"),
            BotCommand("party", "✂️ Cortar Video"),
            BotCommand("cancelar", "🛑 Cancelar Proceso")
        ])
        print("✅ Comandos de acceso rápido configurados")
    except Exception as e:
        print(f"⚠️ No se pudieron configurar los comandos: {e}")

    print("✅ Bot Online"); await idle(); await app.stop()

if __name__ == "__main__":
    app.run(main())