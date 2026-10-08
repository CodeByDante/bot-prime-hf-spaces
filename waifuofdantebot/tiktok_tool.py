import os
import json
import asyncio
import subprocess
import time
import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaVideo
from config import DATA_DIR
from firebase_service import save_user_config_fb, load_all_viral_items_fb
from utils_modes import set_exclusive_mode

# --- CONSTANTS ---
VIRAL_JSON = os.path.join(DATA_DIR, "viral_music.json")

# --- CONFIG STORE ---
SESSION_AUDIO_CONFIG = {} # {chat_id: {'user': Bool, 'viral': Bool}}

async def get_audio_config(chat_id):
    if chat_id not in SESSION_AUDIO_CONFIG:
        SESSION_AUDIO_CONFIG[chat_id] = {'user': False, 'viral': True} # Default: User OFF, Viral ON
    return SESSION_AUDIO_CONFIG[chat_id]

# --- UTILS ---
# --- CATALOG CACHE ---
VIRAL_CATALOG = []
LAST_LOAD_TIME = 0

async def refresh_viral_catalog():
    """Load viral music from JSON and Firebase."""
    global VIRAL_CATALOG, LAST_LOAD_TIME
    
    new_catalog = []
    
    # 1. Load Local JSON (Base/Static)
    try:
        if os.path.exists(VIRAL_JSON):
            with open(VIRAL_JSON, 'r', encoding='utf-8') as f:
                local_items = json.load(f)
                new_catalog.extend(local_items)
    except Exception as e:
        print(f"❌ Error loading Viral JSON: {e}")

    # 2. Load Firebase (Dynamic/User Saved)
    try:
        fb_items = await load_all_viral_items_fb()
        # Sort by date descending (newest first)
        fb_items.sort(key=lambda x: x.get('date', 0), reverse=True)
        new_catalog.extend(fb_items)
    except Exception as e:
        print(f"❌ Error loading Firebase Viral Items: {e}")
        
    # Filter broken items (No path, No file_id, or Path doesn't exist)
    valid_catalog = []
    for item in new_catalog:
        has_file = 'file_id' in item and item['file_id']
        has_path = 'path' in item and item['path'] and os.path.exists(item['path'])
        
        if has_file or has_path:
            valid_catalog.append(item)
            
    VIRAL_CATALOG = valid_catalog
    LAST_LOAD_TIME = time.time()
    print(f"🎵 Viral Catalog Loaded: {len(VIRAL_CATALOG)} items (Filtered from {len(new_catalog)})")

async def get_viral_item(index):
    global VIRAL_CATALOG
    # Refresh if empty or old (every 5 mins)
    if not VIRAL_CATALOG or (time.time() - LAST_LOAD_TIME > 300):
        await refresh_viral_catalog()
    
    if not VIRAL_CATALOG: return None, 0
    
    # Wrap index
    idx = index % len(VIRAL_CATALOG)
    return VIRAL_CATALOG[idx], idx

async def apply_audio_ffmpeg(video_path, audio_input, output_path, mix_user=False, mix_viral=True):
    """
    Apply audio logic:
    - mix_user=T, mix_viral=T -> Mix both (duration=video)
    - mix_user=F, mix_viral=T -> Replace (Viral only, duration=video)
    - mix_user=T, mix_viral=F -> Keep Original (User only)
    - mix_user=F, mix_viral=F -> Mute all
    """
    
    cmd = ["ffmpeg", "-y", "-i", video_path]
    
    if mix_viral:
        cmd.extend(["-i", audio_input])
        
    # LOGIC
    # We use 'apad' filter to pad the audio with infinite silence.
    # Combined with '-shortest', this ensures the output matches the Video stream length,
    # regardless of whether the audio is shorter or longer.
    
    if mix_user and mix_viral:
        # COMPLEX MIX
        # duration=longest insures we don't cut to the shortest audio input inside amix
        # then apad ensures we have infinite tail
        # finally -shortest cuts to video length
        cmd.extend([
            "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=longest[mix];[mix]apad[aout]",
            "-map", "0:v:0",
            "-map", "[aout]"
        ])
    elif mix_viral and not mix_user:
        # REPLACE (Viral Only)
        # Pad viral audio to avoid cutting video if song is short
        cmd.extend([
            "-filter_complex", "[1:a]apad[aout]",
            "-map", "0:v:0",
            "-map", "[aout]"
        ])
    elif mix_user and not mix_viral:
        # ORIGINAL (User Only)
        cmd.extend([
            "-map", "0:v:0",
            "-map", "0:a:0"
        ])
    else:
        # SILENT
        cmd.extend([
            "-map", "0:v:0"
            # No audio map
        ])

    # -shortest signals to stop writing when the shortest stream ends.
    # Since we apad-ed the audio (making it distinctively infinite conceptually or just very long),
    # the video stream becomes the shortest, so output duration == video duration.
    cmd.extend(["-c:v", "copy", "-c:a", "aac", "-shortest", output_path])
    
    print(f"🎵 FFmpeg Mixing: User={mix_user}, Viral={mix_viral}")
    
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        err_msg = stderr.decode()
        print(f"❌ FFmpeg Error: {err_msg}")
        return False
    return True

# --- HANDLERS ---

async def init_tiktok_fast(client, chat_id, config):
    """Muestra el menú principal de Tiktok Fast."""
    is_on = config.get('tiktok_fast_mode', False)
    
    status_icon = "🟢" if is_on else "🔴"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Modo: {status_icon}", callback_data="toggle|tiktok_fast_mode")],
        [InlineKeyboardButton("🔙 Volver", callback_data="menu|tools")]
    ])
    
    await client.send_message(
        chat_id,
        "🎵 **Tiktok Fast Tool**\n\n"
        "Activa este modo para reemplazar automáticamente el audio de tus videos con música viral.\n"
        "1. Activa el modo.\n"
        "2. Envía un video.\n"
        "3. Selecciona la canción del catálogo (Virales/Shorts).\n"
        "4. Usa el mezclador para ajustar volumenes.",
        reply_markup=kb
    )

async def process_tiktok_video(client, msg, file_path):
    """
    Called when a video is received and 'tiktok_fast_mode' is active.
    file_path: Local path of the downloaded video.
    """
    # Fix: Store video path clearly
    from database import url_storage
    storage_key = f"tk_{msg.chat.id}_vid"
    url_storage[storage_key] = file_path
    
    await show_catalog(client, msg.chat.id, 0, video_path=file_path)

async def show_catalog(client, chat_id, index, video_path=None, msg_to_edit=None):
    """Display the catalog item."""
    item, idx = await get_viral_item(index)
    
    from database import url_storage
    storage_key = f"tk_{chat_id}_vid"
    
    # Refresh Video Path
    if video_path: url_storage[storage_key] = video_path
    saved_path = url_storage.get(storage_key)
    if not saved_path and not video_path: return # Should not happen

    if not item: return

    # Load Config
    ac = await get_audio_config(chat_id)
    user_icon = "🔊" if ac['user'] else "🔇"
    viral_icon = "🔊" if ac['viral'] else "🔇"
    
    total = len(VIRAL_CATALOG)
    
    # Info Text
    name = item.get('name', 'Viral')
    if 'caption' in item and item['caption']: name = item['caption'][:50]
    elif 'file_id' in item: name = f"Viral #{item.get('id', 'Unknown')}"
    type_lbl = item.get('type', 'audio').upper()

    text = (
        f"🎵 **Selector** ({idx + 1}/{total})\n"
        f"🎼 {name}\n"
        f"📂 {type_lbl}\n\n"
        f"🎚 **Mezclador:**\n"
        f"👤 Tu Video: {user_icon}\n"
        f"🎵 Viral: {viral_icon}"
    )
    
    # --- NEW NUMBERED KEYBOARD ---
    from utils import generate_grid_keyboard
    from pyrogram.types import InlineKeyboardButton
    
    # Extra Control Rows (Mixer + Action)
    extra_rows = [
        [
            InlineKeyboardButton(f"👤 Voz {user_icon}", callback_data=f"tiktok|t_user|{idx}"),
            InlineKeyboardButton(f"🎵 Viral {viral_icon}", callback_data=f"tiktok|t_viral|{idx}")
        ],
        [
            InlineKeyboardButton("✅ AGREGAR", callback_data=f"tiktok|add|{idx}"),
            InlineKeyboardButton("🎲 Aleatorio", callback_data=f"tiktok|random|{idx}")
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="delete_msg")]
    ]
    
    kb = generate_grid_keyboard(
        current_idx=idx,
        total_items=total,
        prefix_sel="tiktok|sel|", # Select this index
        prefix_nav="tiktok|nav|", # Page nav
        prefix_jump="tiktok|jump",
        extra_rows=extra_rows
    )
    
    # ... (Media Send/Edit Logic - Keep original)
    media_id = item.get('file_id')
    local_path = item.get('path')
    from pyrogram.types import InputMediaVideo, InputMediaAudio
    media_obj = None
    
    if media_id:
        if type_lbl == 'VIDEO': media_obj = InputMediaVideo(media_id, caption=text)
        else: media_obj = InputMediaAudio(media_id, caption=text)
    elif local_path and os.path.exists(local_path):
         if local_path.endswith('.mp4'): media_obj = InputMediaVideo(local_path, caption=text)
         else: media_obj = InputMediaAudio(local_path, caption=text)

    # --- SEND / EDIT ---
    try:
        if msg_to_edit and (msg_to_edit.video or msg_to_edit.audio or msg_to_edit.document):
             if media_obj:
                 await msg_to_edit.edit_media(media=media_obj, reply_markup=kb)
             else:
                 await msg_to_edit.edit_caption(caption=text + "\n\n⚠️ (Vista previa no disponible)", reply_markup=kb)
        else:
             if msg_to_edit: 
                 try: await msg_to_edit.delete()
                 except: pass
             
             if media_obj:
                if isinstance(media_obj, InputMediaVideo):
                    await client.send_video(chat_id, media_obj.media, caption=text, reply_markup=kb)
                else:
                    await client.send_audio(chat_id, media_obj.media, caption=text, reply_markup=kb)
             else:
                await client.send_message(chat_id, text, reply_markup=kb)
    except Exception as e:
        print(f"Display Error: {e}")
        try: await client.send_message(chat_id, text, reply_markup=kb)
        except: pass

# --- CALLBACK ---
async def tiktok_callback(client, callback_query, config):
    # ... (Init logic remains)
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    msg = callback_query.message
    
    if data == "menu|tiktok_fast_init":
        await init_tiktok_fast(client, chat_id, config)
        await callback_query.answer()
        return

    if data == "toggle|tiktok_fast_mode":
        val, disabled = await set_exclusive_mode(chat_id, 'tiktok_fast_mode', is_toggle=True)
        if disabled: await msg.reply(f"🛑 **Se desactivó el modo/herramienta:** {disabled}")
        
        # Refresh Config locally just in case
        if val: config['tiktok_fast_mode'] = True
        else: config['tiktok_fast_mode'] = False
        
        await init_tiktok_fast(client, chat_id, config)
        await msg.delete()
        
        await callback_query.answer(f"Modo {'Activado' if val else 'Desactivado'}")
        return

    if data.startswith("tiktok|"):
        parts = data.split("|")
        action = parts[1]
        
        # HANDLE NAV
        if action == "nav":
            try: 
                current_idx = int(parts[2])
                direction = parts[3] # prev/next
                
                # Jump 10 pages
                if direction == 'next':
                    new_idx = (current_idx + 10) % len(VIRAL_CATALOG)
                    # Align to start of that page? Or just jump 10?
                    # User said: "cambia a 11 hasta 20". So we should land on the first item of next page?
                    # Or just keep relative position?
                    # Let's align to page start.
                    # Current page = cur // 10. Next page = page + 1.
                    page = current_idx // 10
                    next_page = page + 1
                    # Wrap around if needed? Or clamp?
                    # Logic: If I am at 5 (Page 0), Next -> 15 (Page 1) ?
                    # Ensure we don't go out of bounds.
                    new_idx = min(current_idx + 10, len(VIRAL_CATALOG) - 1)
                    if new_idx == current_idx: new_idx = 0 # Loop back to start
                    
                else: # prev
                    new_idx = max(0, current_idx - 10)
                    if new_idx == 0 and current_idx == 0: new_idx = len(VIRAL_CATALOG) - 1 # Loop to end?
                
                await show_catalog(client, chat_id, new_idx, msg_to_edit=msg)
            except: pass
            return
            
        # HANDLE SEL (Direct Click on Number)
        if action == "sel":
            try:
                target_idx = int(parts[2])
                await show_catalog(client, chat_id, target_idx, msg_to_edit=msg)
            except: pass
            return
            
        # HANDLE JUMP (Input)
        if action == "jump":
            # Ask for input
            from database import url_storage
            url_storage[chat_id] = {'tiktok_step': 'wait_jump'}
            await msg.reply("🔢 **Escribe el número** de la canción a la que quieres ir (1 - " + str(len(VIRAL_CATALOG)) + "):", quote=True)
            await callback_query.answer()
            return

        try: current_idx = int(parts[2])
        except: current_idx = 0
        
        # TOGGLES
        if action == "t_user":
            ac = await get_audio_config(chat_id)
            ac['user'] = not ac['user']
            await show_catalog(client, chat_id, current_idx, msg_to_edit=msg)
            await callback_query.answer(f"Voz Usuario: {'ON' if ac['user'] else 'OFF'}")
            return
            
        elif action == "t_viral":
            ac = await get_audio_config(chat_id)
            ac['viral'] = not ac['viral']
            await show_catalog(client, chat_id, current_idx, msg_to_edit=msg)
            await callback_query.answer(f"Audio Viral: {'ON' if ac['viral'] else 'OFF'}")
            return
            
        # NAV
        if action == "next":
            await show_catalog(client, chat_id, current_idx + 1, msg_to_edit=msg)
            await callback_query.answer()
        elif action == "prev":
            await show_catalog(client, chat_id, current_idx - 1, msg_to_edit=msg)
            await callback_query.answer()
        elif action == "random":
            total = len(VIRAL_CATALOG)
            if total > 1:
                # Pick random not equal to current
                choices = [i for i in range(total) if i != current_idx]
                new_idx = random.choice(choices)
            else:
                new_idx = 0
            
            await show_catalog(client, chat_id, new_idx, msg_to_edit=msg)
            await callback_query.answer("🎲 random")

        elif action == "add":
            # ... (Add logic)
            from database import url_storage
            storage_key = f"tk_{chat_id}_vid"
            video_path = url_storage.get(storage_key)
            
            if not video_path or not os.path.exists(video_path):
                await callback_query.answer("❌ Video expiró.", show_alert=True)
                return
            
            item, _ = await get_viral_item(current_idx)
            audio_source = item.get('path')
            
            # Download file_id if needed
            dl_path = None
            if not audio_source and 'file_id' in item:
                await msg.edit_caption("⬇️ **Descargando audio viral...**")
                try:
                    ts = int(time.time())
                    rnd = random.randint(100, 999)
                    dl_path = os.path.join("downloads", f"viral_src_{ts}_{rnd}")
                    dl_path = await client.download_media(item['file_id'], file_name=dl_path)
                    audio_source = dl_path
                except Exception as e:
                    await msg.edit_caption(f"❌ Error descarga: {e}")
                    return

            if not audio_source or not os.path.exists(audio_source):
                 await callback_query.answer("❌ Audio no hallado.", show_alert=True)
                 return
            
            ac = await get_audio_config(chat_id)
            await msg.edit_caption(f"⏳ **Fusionando...**\n(User: {ac['user']} | Viral: {ac['viral']})")
            
            output_path = video_path.rsplit('.', 1)[0] + f"_tikfast_{int(time.time())}.mp4"
            print(f"🎬 Merging: {video_path} + {audio_source} -> {output_path}")
            
            # PASS CONFIG FLAGS
            success = await apply_audio_ffmpeg(
                video_path, audio_source, output_path, 
                mix_user=ac['user'], mix_viral=ac['viral']
            )
            
            if success and os.path.exists(output_path):
                await msg.edit_caption("📤 **Subiendo...**")
                
                # --- THUMBNAIL GENERATION ---
                thumb_path = output_path.rsplit('.', 1)[0] + ".jpg"
                try:
                    # Extract thumbnail at 1s or 0s
                    cmd_thumb = [
                        "ffmpeg", "-y", "-i", output_path, 
                        "-ss", "00:00:01", "-vframes", "1", 
                        "-q:v", "2", thumb_path
                    ]
                    # If video is < 1s, try 0s
                    proc_thumb = await asyncio.create_subprocess_exec(
                        *cmd_thumb, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
                    )
                    await proc_thumb.wait()
                    
                    if not os.path.exists(thumb_path):
                        # Retry at 0s
                        cmd_thumb[5] = "00:00:00"
                        proc_thumb = await asyncio.create_subprocess_exec(
                           *cmd_thumb, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
                        )
                        await proc_thumb.wait()
                except Exception as e:
                    print(f"⚠️ Thumbnail Error: {e}")
                    thumb_path = None

                try:
                    await client.send_video(
                        chat_id, output_path,
                        caption=f"🎵 **Tiktok Fast**\nTrack: {item.get('name', 'Viral')}",
                        thumb=thumb_path if (thumb_path and os.path.exists(thumb_path)) else None
                    )
                    await msg.delete()
                except Exception as ex_send:
                    await msg.edit_caption(f"❌ Error envío: {ex_send}")
                
                # Cleanup
                try: os.remove(output_path)
                except: pass
                
                if thumb_path and os.path.exists(thumb_path):
                    try: os.remove(thumb_path)
                    except: pass
            else:
                await msg.edit_caption("❌ Error FFmpeg.")
            
            if dl_path and os.path.exists(dl_path):
                try: os.remove(dl_path)
                except: pass
            
            await callback_query.answer()
