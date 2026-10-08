import os
import asyncio
import subprocess
import time
from tools_media import get_meta, has_audio_track

# Re-using existing check from tools_media if possible, but defining here for standalone safety
async def get_thumb(file_path, chat_id, ts, duration=0):
    """
    Genera un thumbnail del video usando FFmpeg.
    """
    thumb_path = f"thumb_{chat_id}_{ts}.jpg"
    
    # Intentar sacar thumb al 10% o al segundo 1
    seek = "00:00:01"
    if duration > 10:
        seek = time.strftime('%H:%M:%S', time.gmtime(duration * 0.1))
        
    cmd = [
        "ffmpeg", "-y",
        "-ss", seek,
        "-i", file_path,
        "-vframes", "1",
        "-q:v", "2",
        thumb_path
    ]
    
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await proc.wait()
    
    if os.path.exists(thumb_path):
        return thumb_path
    return None

async def process_fusion(video_path, audio_path, output_path, keep_video_audio=False, keep_added_audio=True, safe_mode=False, vol_v=100, vol_a=100, loop_audio=True, force_shortest=False):
    """
    Mezcla video y audio usando FFmpeg.
    
    Args:
        keep_video_audio (bool): Si es True, mantiene el audio original del video.
        keep_added_audio (bool): Si es True, usa el audio nuevo.
        (Ambos True = Mezcla)
    """
    if keep_added_audio and loop_audio and not force_shortest:
        cmd = ["ffmpeg", "-y", "-i", video_path, "-stream_loop", "-1", "-i", audio_path]
    else:
        cmd = ["ffmpeg", "-y", "-i", video_path, "-i", audio_path]
    
    # Complex Filter Construction
    filter_complex = []
    map_args = []
    
    # Video map always 0:v:0 (ensures we don't grab extra mjpeg thumbnail streams)
    map_args.extend(["-map", "0:v:0"])
    
    # Check if video actually has audio if we want to keep it
    if keep_video_audio:
        has_audio = await has_audio_track(video_path)
        if not has_audio:
            keep_video_audio = False

    # Check if added audio actually has audio
    if keep_added_audio:
        has_added_audio = await has_audio_track(audio_path)
        if not has_added_audio:
            keep_added_audio = False

    # Audio Volume Factor (e.g. 100% = 1.0, 50% = 0.5)
    v_factor = vol_v / 100.0
    a_factor = vol_a / 100.0

    # Audio Logic
    if keep_video_audio and keep_added_audio:
        # MIX Both
        mix_dur = "shortest" if force_shortest else "first"
        cmd.extend([
            "-filter_complex", 
            f"[0:a]volume={v_factor}[v_aud];[1:a]volume={a_factor}[a_aud];[v_aud][a_aud]amix=inputs=2:duration={mix_dur}:dropout_transition=2[a]",
            "-map", "[a]"
        ])
    elif keep_video_audio and not keep_added_audio:
        # Video Audio Only (External Muted)
        cmd.extend([
            "-filter_complex", f"[0:a]volume={v_factor}[a]",
            "-map", "[a]"
        ])
    elif not keep_video_audio and keep_added_audio:
        # External Audio Only (Video Muted)
        if not loop_audio and not force_shortest:
            # Silence padding (apad) ensures it lasts as long as the video without looping the music
            filter_str = f"[1:a]volume={a_factor},apad[a]"
        else:
            filter_str = f"[1:a]volume={a_factor}[a]"
            
        cmd.extend([
            "-filter_complex", filter_str,
            "-map", "[a]"
        ])
    else:
        # BOTH MUTED (Silent video)
        # We don't map any audio
        pass
        
    cmd.extend(map_args)
    
    # Codecs and Cut
    if safe_mode or force_shortest:
        cmd.extend([
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", # Ensures width/height are divisible by 2 for yuv420p
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", output_path
        ])
    else:
        cmd.extend([
            "-c:v", "copy",   # Copy video stream (Fast) unless re-encoding needed? 
                              # Re-encoding is safer for compatibility but slower. 
                              # Copy is best for "Fusion" speed.
            "-c:a", "aac",    # Re-encode audio to AAC typical for MP4
            "-shortest",      # Cut to shortest stream (usually video)
            output_path
        ])
    
    print(f"🧬 Fusion CMD: {' '.join(cmd)}")
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait
    stdout, stderr = await proc.communicate()
    
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return True, None
    else:
        err_str = stderr.decode('utf-8', errors='ignore')
        print(f"❌ FFmpeg Fusion Error: {err_str}")
        
        # Truncate error to avoid Telegram 400 MESSAGE_TOO_LONG
        if len(err_str) > 2000:
             err_str = "..." + err_str[-2000:]
             
        if os.path.exists(output_path):
             try: os.remove(output_path)
             except: pass
        return False, err_str

# --- UI HANDLERS ---
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def init_fusion_menu(client, chat_id, config, edit_msg=None):
    """Muestra el menú principal de la herramienta Fusión."""
    is_on = config.get('fusion_mode', False)
    status_icon = "🟢" if is_on else "🔴"
    
    is_auto_on = config.get('fusion_auto_mode', False)
    auto_icon = "🟢" if is_auto_on else "🔴"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Modo: {status_icon}", callback_data="toggle|fusion")],
        [InlineKeyboardButton(f"🤖 Modo Automático {auto_icon}", callback_data="fus_auto|menu")],
        [InlineKeyboardButton("🔙 Volver", callback_data="menu|main")]
    ])

    text = (
        "🎵 **Herramienta de Fusión**\n\n"
        "Mezcla audio y video fácilmente.\n"
        "1. Activa el modo.\n"
        "2. Envía un **Video Base**.\n"
        "3. Envía un **Audio** (o video para extraer audio).\n"
        "4. Configura la mezcla final."
    )

    if edit_msg:
        await edit_msg.edit_text(text, reply_markup=kb)
    else:
        await client.send_message(
            chat_id,
            text,
            reply_markup=kb
        )

async def show_fusion_auto_menu(client, chat_id, config, edit_msg=None):
    """Muestra el submenú de Fusión Automática."""
    is_on = config.get('fusion_auto_mode', False)
    status_icon = "🟢 Encendido" if is_on else "🔴 Apagado"
    has_audio = bool(config.get('fusion_default_audio'))
    audio_status_icon = "✅ Guardado" if has_audio else "❌ Faltante"

    icon_v = "🔊" if config.get('fusion_auto_cfg_v', True) else "🔇"
    icon_a = "🔊" if config.get('fusion_auto_cfg_a', True) else "🔇"

    loop_on = config.get('fusion_auto_loop', True)
    loop_icon = "🟢 Activo" if loop_on else "🔴 Inactivo"
    
    shortest_on = config.get('fusion_auto_shortest', False)
    shortest_icon = "🟢 Activo" if shortest_on else "🔴 Inactivo"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Estado de Fusión Automática: {status_icon}", callback_data="fus_auto|toggle")],
        [InlineKeyboardButton(f"🎵 Subir Audio Predeterminado [{audio_status_icon}]", callback_data="fus_auto|set_audio")],
        [
            InlineKeyboardButton(f"🎥 Video {icon_v}", callback_data="fus_auto|toggle_vol|v"),
            InlineKeyboardButton(f"🔊 {config.get('fusion_auto_vol_v', 100)}%", callback_data="fus_auto|vol|v")
        ],
        [
            InlineKeyboardButton(f"🎵 Audio {icon_a}", callback_data="fus_auto|toggle_vol|a"),
            InlineKeyboardButton(f"🔊 {config.get('fusion_auto_vol_a', 100)}%", callback_data="fus_auto|vol|a")
        ],
        [
            InlineKeyboardButton(f"🔁 Bucle: {loop_icon}", callback_data="fus_auto|toggle_loop"),
            InlineKeyboardButton(f"⚡ Corte Fort: {shortest_icon}", callback_data="fus_auto|toggle_shortest")
        ],
        [InlineKeyboardButton("🔙 Volver a Fusión", callback_data="menu|fusion_init")]
    ])

    text = (
        "🤖 **Modo Fusión Automática**\n\n"
        "Al estar encendido, cualquier video que envíes se fusionará instantáneamente con tu audio predeterminado, usando los ajustes de volumen pasados, ¡sin botones!\n\n"
        "*(Requiere tener la herramienta Fusión activada y un audio configurado).*")
    
    if config.get('fusion_auto_audio_capture', False):
        text = "🎵 **Esperando Audio Predeterminado...**\n\nPor favor envíame ahora mismo el **Audio** (o video para extraer su audio). Este será tu nuevo fondo predeterminado.\n\n_(Para cancelar, presiona el botón abajo)_"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancelar Subida", callback_data="fus_auto|cancel_audio")]
        ])

    if edit_msg:
        try:
            await edit_msg.edit_text(text, reply_markup=kb)
        except Exception as e:
            import traceback
            print(f"ERROR UI EDIT: {traceback.format_exc()}")
            # Intentar notificar
            try: await client.send_message(chat_id, f"⚠️ Error visual: {e}")
            except: pass
    else:
        await client.send_message(chat_id, text, reply_markup=kb)

# --- FUSION SESSION & LOGIC ---
FUSION_SESSIONS = {} # {chat_id: {'video': msg/id, 'audio': msg/id, 'cfg_v': T, 'cfg_a': T, 'step': 0}}

async def get_fusion_session(chat_id):
    if chat_id not in FUSION_SESSIONS:
        FUSION_SESSIONS[chat_id] = {'step': 0, 'cfg_v': True, 'cfg_a': True, 'safe_mode': False, 'vol_v': 100, 'vol_a': 100, 'video': None, 'audio': None}
        # Step 0: Idle/Wait Video
        # Step 1: Wait Audio
        # Step 2: Ready/Panel
    return FUSION_SESSIONS[chat_id]

async def show_fusion_panel(client, chat_id, edit_msg=None):
    sess = await get_fusion_session(chat_id)
    
    # Config Icons
    icon_v = "🔊" if sess['cfg_v'] else "🔇"
    icon_a = "🔊" if sess['cfg_a'] else "🔇"
    safe_cb = "✅ Seguro" if sess.get('safe_mode', False) else "⚡️ Rápido"
    
    txt = (
        "🎚 **Panel de Fusión**\n\n"
        "Configura las fuentes de audio antes de procesar:\n\n"
        f"🎥 **Video Base:** {'✅ Listo' if sess['video'] else '❌ Falta'}\n"
        f"🎵 **Audio/Mix:** {'✅ Listo' if sess['audio'] else '❌ Falta'}\n"
        f"⚙️ **Modo Video:** {safe_cb} *(El Seguro evita audios/videos corruptos)*\n"
    )
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🎥 Video {icon_v}", callback_data="fus|toggle|v"),
            InlineKeyboardButton(f"🔊 {sess.get('vol_v', 100)}%", callback_data="fus|vol|v")
        ],
        [
            InlineKeyboardButton(f"🎵 Audio {icon_a}", callback_data="fus|toggle|a"),
            InlineKeyboardButton(f"🔊 {sess.get('vol_a', 100)}%", callback_data="fus|vol|a")
        ],
        [InlineKeyboardButton(f"⚙️ Cambiar Modo: {safe_cb}", callback_data="fus|toggle|safe")],
        [InlineKeyboardButton("✅ ACEPTAR Y FUSIONAR", callback_data="fus|exec")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="fus|cancel")]
    ])
    
    if edit_msg:
        await edit_msg.edit_text(txt, reply_markup=kb)
    else:
        return await client.send_message(chat_id, txt, reply_markup=kb)

async def fusion_callback(client, callback_query):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    
    # --- AUTO MODE CALLBACKS ---
    if data.startswith("fus_auto|"):
        from database import get_config, url_storage
        from firebase_service import save_user_config_fb
        conf = get_config(chat_id)
        
        cmd = data.split("|")[1]
        
        if cmd == "dummy":
            await callback_query.answer("Controles de volumen de mezcla automática.")
            return

        if cmd == "toggle_vol":
            target = data.split("|")[2]
            key = 'fusion_auto_cfg_v' if target == 'v' else 'fusion_auto_cfg_a'
            conf[key] = not conf.get(key, True)
            
            import asyncio
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            await show_fusion_auto_menu(client, chat_id, conf, edit_msg=callback_query.message)
            return

        if cmd == "vol":
            target = data.split("|")[2]
            key = 'fusion_auto_vol_v' if target == 'v' else 'fusion_auto_vol_a'
            vol = conf.get(key, 100) + 10
            if vol > 100: vol = 10
            conf[key] = vol
            
            import asyncio
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            await show_fusion_auto_menu(client, chat_id, conf, edit_msg=callback_query.message)
            await callback_query.answer(f"Volumen Auto {'Video' if target == 'v' else 'Audio'}: {vol}%")
            return
            
        if cmd == "menu":
            try:
                await show_fusion_auto_menu(client, chat_id, conf, edit_msg=callback_query.message)
            except Exception:
                try:
                    await callback_query.message.delete()
                except: pass
                await show_fusion_auto_menu(client, chat_id, conf, edit_msg=None)
            return
            
        if cmd == "toggle":
            from database import set_exclusive_mode
            await set_exclusive_mode(chat_id, 'fusion_auto_mode', is_toggle=True)
            
            conf = get_config(chat_id)
            
            if not conf.get('fusion_auto_mode', False):
                conf['fusion_auto_audio_capture'] = False
                import asyncio
                asyncio.create_task(save_user_config_fb(chat_id, conf))
                
            await show_fusion_auto_menu(client, chat_id, conf, edit_msg=callback_query.message)
            return
            
        if cmd == "set_audio":
            file_id = conf.get('fusion_default_audio')
            if not file_id:
                # No audio saved yet, go straight to wait state
                conf['fusion_auto_audio_capture'] = True
                import asyncio
                asyncio.create_task(save_user_config_fb(chat_id, conf))
                try:
                    await callback_query.answer("Cambiando a Modo Espera...")
                except: pass
                await show_fusion_auto_menu(client, chat_id, conf, edit_msg=callback_query.message)
                return
            
            # They have an audio. Let's send the preview!
            try:
                await callback_query.answer("Cargando vista previa...")
            except: pass
            
            # Delete the menu message
            try:
                await callback_query.message.delete()
            except: pass
            
            caption = "🎵 **Audio/Video Predeterminado Guardado**\n\nEste es tu archivo de fondo actual. ¿Qué deseas hacer?"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Actualizar", callback_data="fus_auto|force_set_audio")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="fus_auto|menu")]
            ])
            
            sent = False
            # Try to send using standard methods
            for send_method in [client.send_audio, client.send_voice, client.send_video, client.send_document]:
                try:
                    await send_method(chat_id, file_id, caption=caption, reply_markup=kb)
                    sent = True
                    break
                except Exception:
                    continue
                    
            if not sent:
                # Try generic cached media send
                try:
                    await client.send_cached_media(chat_id, file_id, caption=caption, reply_markup=kb)
                    sent = True
                except Exception:
                    pass
                    
            if not sent:
                # Plain text fallback
                await client.send_message(chat_id, caption + "\n\n⚠️ No se pudo reproducir la vista previa en Telegram.", reply_markup=kb)
            return

        if cmd == "force_set_audio":
            conf['fusion_auto_audio_capture'] = True
            import asyncio
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            
            try:
                await callback_query.answer("Cambiando a Modo Espera...")
            except: pass
            
            # Delete the preview message and send the waiting message
            try:
                await callback_query.message.delete()
            except: pass
            
            await show_fusion_auto_menu(client, chat_id, conf, edit_msg=None)
            return

        if cmd == "cancel_audio":
            conf['fusion_auto_audio_capture'] = False
            import asyncio
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            
            await show_fusion_auto_menu(client, chat_id, conf, edit_msg=callback_query.message)
            return

        if cmd == "toggle_loop":
            new_val = not conf.get('fusion_auto_loop', True)
            conf['fusion_auto_loop'] = new_val
            if new_val:
                conf['fusion_auto_shortest'] = False
            import asyncio
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            await show_fusion_auto_menu(client, chat_id, conf, edit_msg=callback_query.message)
            return

        if cmd == "toggle_shortest":
            new_val = not conf.get('fusion_auto_shortest', False)
            conf['fusion_auto_shortest'] = new_val
            if new_val:
                conf['fusion_auto_loop'] = False
            import asyncio
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            await show_fusion_auto_menu(client, chat_id, conf, edit_msg=callback_query.message)
            return

    # --- STANDARD MODE CALLBACKS ---
    sess = await get_fusion_session(chat_id)
    
    if data == "fus|cancel":
        FUSION_SESSIONS[chat_id] = {'step': 0, 'cfg_v': True, 'cfg_a': True, 'safe_mode': False, 'video': None, 'audio': None}
        await callback_query.message.edit_text("❌ Fusión cancelada.")
        return

    if data == "fus|toggle|safe":
        sess['safe_mode'] = not sess.get('safe_mode', False)
        await show_fusion_panel(client, chat_id, edit_msg=callback_query.message)
        await callback_query.answer(f"Modo: {'Seguro' if sess['safe_mode'] else 'Rápido'}")
        return

    if data == "fus|vol|v":
        vol = sess.get('vol_v', 100) + 10
        if vol > 100: vol = 10
        sess['vol_v'] = vol
        await show_fusion_panel(client, chat_id, edit_msg=callback_query.message)
        await callback_query.answer(f"Volumen Video: {vol}%")
        return

    if data == "fus|vol|a":
        vol = sess.get('vol_a', 100) + 10
        if vol > 100: vol = 10
        sess['vol_a'] = vol
        await show_fusion_panel(client, chat_id, edit_msg=callback_query.message)
        await callback_query.answer(f"Volumen Audio: {vol}%")
        return

    if data == "fus|toggle|v":
        sess['cfg_v'] = not sess['cfg_v']
        await show_fusion_panel(client, chat_id, edit_msg=callback_query.message)
        await callback_query.answer(f"Audio Video: {'ON' if sess['cfg_v'] else 'OFF'}")
        return

    if data == "fus|toggle|a":
        sess['cfg_a'] = not sess['cfg_a']
        await show_fusion_panel(client, chat_id, edit_msg=callback_query.message)
        await callback_query.answer(f"Audio Externo: {'ON' if sess['cfg_a'] else 'OFF'}")
        return

    if data == "fus|exec":
        # EXECUTION
        if not sess['video'] or not sess['audio']:
            await callback_query.answer("❌ Faltan archivos.", show_alert=True)
            return

        await callback_query.message.edit_text("⏳ **Descargando archivos...**")
        
        # Download logic needs to be here or triggered.
        # Since main.py usually handles downloads, we need access to the downloader or simple download_media method
        # sess['video'] and ['audio'] should be Pyrogram Message objects or IDs
        
        try:
            # Paths
            ts = int(time.time())
            v_path = os.path.join("downloads", f"fus_v_{ts}_{chat_id}.mp4")
            a_path = os.path.join("downloads", f"fus_a_{ts}_{chat_id}") # Ext guesses later
            
            # Download Video
            # Determine if message or file_id
            v_msg = sess['video']
            await client.download_media(v_msg, file_name=v_path)
            
            # Download Audio
            a_msg = sess['audio']
            a_dl = await client.download_media(a_msg, file_name=a_path)
            
            if not os.path.exists(v_path) or not os.path.exists(a_dl):
                await callback_query.message.edit_text("❌ Error en descarga.")
                return
            
            # PROCESS
            await callback_query.message.edit_text("⚙️ **Procesando Fusión...**")
            
            out_path = os.path.join("downloads", f"fusion_final_{ts}_{chat_id}.mp4")
            
            ok, err = await process_fusion(
                v_path, a_dl, out_path, 
                keep_video_audio=sess['cfg_v'], 
                keep_added_audio=sess['cfg_a'], 
                safe_mode=sess.get('safe_mode', False),
                vol_v=sess.get('vol_v', 100),
                vol_a=sess.get('vol_a', 100)
            )
            
            if ok:
                await callback_query.message.edit_text("📤 **Enviando...**")
                # Generate Thumb
                thumb = await get_thumb(out_path, chat_id, ts)
                w, h, dur = await get_meta(out_path)
                
                await client.send_video(
                    chat_id, out_path,
                    caption="🧬 **Fusión Completada**",
                    width=w, height=h, duration=dur, thumb=thumb
                )
                
                # Cleanup
                if thumb and os.path.exists(thumb): os.remove(thumb)
                if os.path.exists(out_path): os.remove(out_path)
                
                # Reset Session Loop (Keep settings? User said 'sale el panel nuevamente y asi')
                # Usually reset files but keep settings?
                # "si le renvio dos videos... sale el panel nuevamente"
                sess['video'] = None
                sess['audio'] = None
                sess['step'] = 0
                
                await callback_query.message.delete()
                # Reprompt? Or just silent wait?
                # User flow: "cuando le de aseptar ... el bot recien comienza ... y asi cuando el boton... este no se apaga"
                
            else:
                 await callback_query.message.edit_text(f"❌ Error Fusión: {err}")
                 
            # Clean Inputs
            if os.path.exists(v_path): os.remove(v_path)
            if os.path.exists(a_dl): os.remove(a_dl)
            
        except Exception as e:
            print(f"Fusion Exec Error: {e}")
            await callback_query.message.edit_text(f"❌ Error Crítico: {e}")

