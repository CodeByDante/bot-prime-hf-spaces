import os
import json
import time
import asyncio
import subprocess
from pyrogram import enums
from pyrogram.errors import FloodWait
from config import HAS_FFMPEG
from database import update_progress

# --- FUNCIONES DE MEDIA (FFMPEG) ---

async def get_thumb(path, cid, ts, duration=0, seek_override=None):
    out = f"t_{cid}_{ts}.jpg"
    log_file = "media_debug.log"
    if HAS_FFMPEG:
        try:
            # Smart Seek Calculation
            seek_time = "00:00:02"
            
            if seek_override:
                seek_time = seek_override
                print(f"📸 Forced Thumbnail Seek: {seek_time}")
            elif duration > 0:
                # 15% mark usually avoids intros but captures action
                s_sec = duration * 0.15 
                if duration < 5: s_sec = duration / 2 # Short videos: Middle
                elif s_sec < 2: s_sec = 2 # Min 2s
                
                # Format
                m, s = divmod(s_sec, 60)
                h, m = divmod(m, 60)
                seek_time = f"{int(h):02d}:{int(m):02d}:{s:06.3f}"

            # Thumbnail con corrección de Aspect Ratio (Square Pixels)
            # Primero intenta en Smart Seek
            cmd = ["ffmpeg", "-ss", seek_time, "-i", path, "-vf", "scale=iw*sar:ih", "-vframes", "1", "-q:v", "2", out, "-y"]
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"Thumb Cmd 1 ({seek_time}): {cmd}\n")
            
            process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await process.wait()
            
            # Si falla, intenta al principio (0s)
            if not os.path.exists(out):
                cmd = ["ffmpeg", "-ss", "00:00:00", "-i", path, "-vf", "scale=iw*sar:ih", "-vframes", "1", "-q:v", "2", out, "-y"]
                with open(log_file, "a", encoding="utf-8") as f: f.write(f"Thumb Cmd 2 (Fallback): {cmd}\n")
                process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                await process.wait()

            if os.path.exists(out): 
                with open(log_file, "a", encoding="utf-8") as f: f.write(f"Thumb created: {out} ({os.path.getsize(out)} bytes)\n")
                return out
            else:
                with open(log_file, "a", encoding="utf-8") as f: f.write(f"Thumb FAILED for {path}\n")
        except Exception as e:
            print(f"Error thumb: {e}")
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"Thumb Error: {e}\n")
    return None


async def get_meta(path):
    log_file = "media_debug.log"
    if not HAS_FFMPEG: return 0, 0, 0
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0", 
            "-show_entries", "stream=width,height,duration,sample_aspect_ratio:stream_tags=rotate", 
            "-of", "json", path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        
        d = json.loads(stdout)
        s = d['streams'][0]
        w = int(s.get('width', 0))
        h = int(s.get('height', 0))
        dur = int(float(s.get('duration', 0)))
        
        with open(log_file, "a", encoding="utf-8") as f: f.write(f"Raw Meta: w={w}, h={h}, sar={s.get('sample_aspect_ratio')}\n")

        # Aspect Ratio Correction
        sar = s.get('sample_aspect_ratio', '1:1')
        if sar != '1:1' and sar != '0:1' and ':' in sar:
            try:
                num, den = map(int, sar.split(':'))
                if den > 0:
                     # Calculate Display Width
                     w = int(w * (num / den))
                     with open(log_file, "a", encoding="utf-8") as f: f.write(f"Corrected w={w}\n")
            except: pass
        
        # Check rotation
        tags = s.get('tags', {})
        rot = tags.get('rotate')
        if rot:
            rot = int(rot)
            if abs(rot) in [90, 270]:
                w, h = h, w
        
        with open(log_file, "a", encoding="utf-8") as f: f.write(f"Final Meta: w={w}, h={h}\n")
        return w, h, dur
    except Exception as e:
        with open(log_file, "a", encoding="utf-8") as f: f.write(f"Meta Error: {e}\n")
        return 0, 0, 0

async def get_audio_dur(path):
    try:
        cmd = [
            "ffprobe", "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "json", path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return int(float(json.loads(stdout)['format']['duration']))
    except:
        return 0

# --- GLOBAL THROTTLE (Roulette) ---
GLOBAL_LAST_EDIT_TIME = 0.0
GLOBAL_EDIT_LOCK = asyncio.Lock()

async def progreso(cur, tot, msg, times, act, orig_id=None):
    if not msg: return
    now = time.time()
    if not orig_id: orig_id = msg.id # Fallback
    
    # SAFEGUARD: tot/cur can be None or 0
    safe_cur = int(cur) if cur else 0
    safe_tot = int(tot) if tot else 0
    
    if safe_tot == 0: return

    per = safe_cur * 100 / safe_tot
    
    # THROTTLING INTELIGENTE:
    # Solo actualizar si:
    # 1. Pasaron > 8 segundos (Time-based prevent FloodWait)
    # 2. O si el progreso cambió > 5% (Step-based)
    # 3. O si terminó (100%)
    
    # Safe guard for bad inputs
    if isinstance(times, (int, float)):
         times = [times, 0]
    
    last_time = times[0]
    last_per = times[1]
    
    if (now - last_time) > 8 or (per - last_per) > 5 or safe_cur == safe_tot:
        # --- GLOBAL ROULETTE (Max 1 edit every 5s across entire bot) ---
        global GLOBAL_LAST_EDIT_TIME
        async with GLOBAL_EDIT_LOCK:
            current_time = time.time()
            time_since_last = current_time - GLOBAL_LAST_EDIT_TIME
            
            if time_since_last < 5.0:
                if safe_cur == safe_tot:
                    # Es el final, DEBEMOS actualizar, pero esperamos nuestro turno para evitar FloodWait
                    await asyncio.sleep(5.0 - time_since_last)
                    current_time = time.time()
                else:
                    # Update intermedio, saltamos turno para no bloquear la subida
                    return
            
            GLOBAL_LAST_EDIT_TIME = current_time

        times[0] = now
        times[1] = per
        
        try:
            from utils import render_bar
            
            mb_cur = safe_cur / (1024 * 1024)
            mb_tot = safe_tot / (1024 * 1024)
            # bar = render_bar(safe_cur, safe_tot) # Removed per user request
            
            # Custom Action Text
            action_text = act if act else "Enviando"
            emoji = "⬇️" if "Descargando" in action_text else "📤"
            
            # Update Admin Progress (Keep URL if exists)
            from database import task_progress
            existing_url = task_progress.get(msg.chat.id, {}).get(orig_id, {}).get('url', 'N/A')
            update_progress(msg.chat.id, orig_id, percent=per, status=f"{action_text} {emoji}", speed=f"{mb_cur:.1f}MB", url=existing_url)
            
            # Format: 📤 Subiendo Video 📁25.0/97.7 MB (25.6%)
            txt = f"{emoji} {action_text} 📁 `{mb_cur:.1f}/{mb_tot:.1f} MB` (`{per:.1f}%`)"
            # Console Log (User Request)
            print(f"🔄 Progress: {mb_cur:.1f}/{mb_tot:.1f} MB ({per:.1f}%)")
            await msg.edit_text(txt)
            
        except FloodWait as e:
            # Si Telegram nos dice "espera X segundos", NO crasheamos, solo esperamos y saltamos este update visual.
            # print(f"⏳ FloodWait en barra: {e.value}s")
            await asyncio.sleep(e.value)
        except Exception as e:
            # Error visual ignorado para no romper subida
            pass

async def cut_video_start(path, start_time):
    """Corta el video desde start_time hasta el final usando stream copy."""
    log_file = "media_debug.log"
    base, ext = os.path.splitext(path)
    out_path = f"{base}_cut_{int(time.time())}{ext}"
    
    if HAS_FFMPEG:
        try:
            # OPTIMIZATION: Try Stream Copy first (Instant & No Quality Loss)
            # -ss before -i for fast seek (keyframe snap)
            # -c copy to avoid re-encoding
            cmd_copy = ["ffmpeg", "-ss", str(start_time), "-i", path, "-c", "copy", "-map", "0", out_path, "-y"]
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"Cut Start Cmd (Copy): {cmd_copy}\n")
            
            process = await asyncio.create_subprocess_exec(*cmd_copy, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            _, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(out_path):
                return out_path
            
            # Fallback: Re-encoding if copy fails (e.g. incompatible codecs for container)
            # Use optimized settings to avoid file bloat: -crf 26 (smaller) -preset fast
            with open(log_file, "a", encoding="utf-8") as f: 
                f.write(f"⚠️ Stream Copy Failed (RC={process.returncode}): {stderr.decode() if stderr else 'Unknown'}\nFallback to Encode...\n")

            # Fallback based on extension
            if ext.lower() in ['.mp3', '.m4a', '.flac', '.wav', '.ogg', '.opus']:
                 # Audio Fallback
                 cmd_encode = [
                    "ffmpeg", "-ss", str(start_time), "-i", path,
                    "-c:a", "libmp3lame" if ext == '.mp3' else "aac", 
                    "-b:a", "192k",
                    "-vn", # No video
                    "-map", "0:a", 
                    out_path, "-y"
                 ]
            else:
                 # Video Fallback
                 cmd_encode = [
                    "ffmpeg", "-ss", str(start_time), "-i", path, 
                    "-c:v", "libx264", "-preset", "fast", "-crf", "26", 
                    "-c:a", "aac", "-b:a", "128k", 
                    "-map", "0", out_path, "-y"
                 ]
            
            process = await asyncio.create_subprocess_exec(*cmd_encode, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await process.wait()
            
            if os.path.exists(out_path):
                return out_path
                
        except Exception as e:
            print(f"Error cutting video: {e}")
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"Cut Error: {e}\n")
    return None

async def extract_audio(path):
    """Extrae el audio de un video y lo guarda como MP3."""
    log_file = "media_debug.log"
    out_path = os.path.splitext(path)[0] + ".mp3"
    
    if HAS_FFMPEG:
        try:
            # ffmpeg -i input.mp4 -q:a 0 -map a output.mp3
            cmd = ["ffmpeg", "-i", path, "-vn", "-acodec", "libmp3lame", "-q:a", "2", out_path, "-y"]
            process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await process.wait()
            
            if os.path.exists(out_path):
                return out_path
        except Exception as e:
            print(f"Error extracting audio: {e}")
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"Audio Extract Error: {e}\n")
    return None

async def convert_to_h264(path):
    """Convierte cualquier video a MP4 H.264 compatible con Telegram/Web."""
    log_file = "media_debug.log"
    # Salida con nombre unico
    base, _ = os.path.splitext(path)
    # Evitar conflictos de nombre
    out_path = f"{base}_h264_{int(time.time())}.mp4"
    
    if HAS_FFMPEG:
        try:
            # Comando FFmpeg para estandarizar a H.264 AAC
            # -c:v libx264 -preset fast -crf 23 (buen balance calidad/peso)
            # -c:a aac -b:a 128k
            # -movflags +faststart (para streaming web si hace falta)
            # -pix_fmt yuv420p (máxima compatibilidad)
            # -map 0:v:0 -map 0:a? (Solo primer video y audio si existe, ignora data/subs rotos de .ts)
            cmd = [
                "ffmpeg",
                "-probesize", "10M",
                "-analyzeduration", "10M",
                "-i", path, 
                "-c:v", "libx264", 
                "-preset", "superfast", 
                "-crf", "23", 
                "-c:a", "aac", 
                "-b:a", "128k",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-sn",
                "-dn", 
                out_path, 
                "-y"
            ]
            
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"H264 Convert Cmd: {cmd}\n")
            
            # Ejecutar conversión
            process = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.PIPE 
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                # Error crítico
                err_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Unknown Error"
                with open(log_file, "a", encoding="utf-8") as f: 
                    f.write(f"❌ FFmpeg FAILED (RC={process.returncode}):\n{err_msg}\n")
                
                if os.path.exists(out_path): 
                    try: os.remove(out_path)
                    except: pass
                return None

            # Éxito (con posibles warnings)
            if stderr:
                with open(log_file, "a", encoding="utf-8") as f: 
                    f.write(f"⚠️ FFmpeg Warnings (RC=0): {stderr.decode('utf-8', errors='ignore')}\n")
            
            if os.path.exists(out_path):
                # --- SILENT VIDEO CHECK ---
                # User Request: If H264 conversion yields no audio (e.g. from GIF), 
                # force inject silent audio so it behaves like a video.
                has_audio = await has_audio_track(out_path)
                if not has_audio:
                     print("🔇 H264 Output is silent. Injecting ghost audio...")
                     new_out = await add_silent_audio(out_path)
                     if new_out and os.path.exists(new_out):
                         try: os.remove(out_path)
                         except: pass
                         out_path = new_out

                return out_path
        except Exception as e:
            print(f"Error converting H264: {e}")
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"H264 Error: {e}\n")
            
    return None

async def embed_thumbnail(video_path, image_path):
    """
    Incrusta una imagen como portada (thumbnail) en el archivo de video.
    Usa stream copy para el video, evitando re-encoding.
    """
    log_file = "media_debug.log"
    if not os.path.exists(video_path) or not os.path.exists(image_path):
        return None
        
    base, ext = os.path.splitext(video_path)
    # Nombre temporal para la salida
    out_path = f"{base}_thumb_{int(time.time())}.mp4"
    
    if HAS_FFMPEG:
        try:
            # Comando mágico:
            # -map 0: toma todo del video
            # -map 1: toma la imagen
            # -c copy: copia sin re-encodear video/audio
            # -c:v:1 png: asegura que la imagen sea compatible
            # -disposition:v:1 attached_pic: le dice al metadata "esto es la portada"
            cmd = [
                "ffmpeg", "-y", 
                "-i", video_path, 
                "-i", image_path,
                "-map", "0", "-map", "1",
                "-c", "copy", 
                "-c:v:1", "png",
                "-disposition:v:1", "attached_pic",
                out_path
            ]
            
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"Thumb Embed Cmd: {cmd}\n")
            
            process = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.PIPE
            )
            _, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(out_path):
                return out_path
            else:
                 with open(log_file, "a", encoding="utf-8") as f: 
                    f.write(f"❌ Embed Failed: {stderr.decode() if stderr else 'Unknown'}\n")
                    
        except Exception as e:
             print(f"Error embed thumb: {e}")
             with open(log_file, "a", encoding="utf-8") as f: f.write(f"Embed Error: {e}\n")
             
    return None

async def resize_video(path, target_ratio):
    """
    Redimensiona (Scale to Cover/Fill) un video a un aspect ratio específico.
    Estrategia: Agrandar y Centrar (Crop).
    Base Resolution: 1080p density.
    """
    log_file = "media_debug.log"
    if not os.path.exists(path): return None
    
    base, ext = os.path.splitext(path)
    out_path = f"{base}_resize_{target_ratio.replace(':','-')}_{int(time.time())}.mp4"
    
    # 1. Definir Resoluciones Objetivo (Based on 1080p logic)
    # Vertical (H=1920)
    # Horizontal (W=1920)
    # Square (1080x1080)
    
    w, h = 1920, 1080 # Default 16:9
    
    if target_ratio == "9:16":   w, h = 1080, 1920
    elif target_ratio == "3:4":  w, h = 1080, 1440 # (1080 * 4/3 = 1440)
    elif target_ratio == "9:19.5": w, h = 1080, 2340 # ~iPhone X
    elif target_ratio == "1:1":  w, h = 1080, 1080
    elif target_ratio == "4:3":  w, h = 1440, 1080
    elif target_ratio == "16:9": w, h = 1920, 1080
    elif target_ratio == "2.35:1": w, h = 1920, 816
    elif target_ratio == "1.85:1": w, h = 1920, 1038
    
    if HAS_FFMPEG:
        try:
            # FILTER COMPLEX EXPLAINED:
            # 1. scale=w:h:force_original_aspect_ratio=increase
            #    Escala el video para que CUBRA la caja destino (al menos una dimension encaja, la otra sobra)
            # 2. crop=w:h
            #    Recorta el sobrante para llegar exactamente a w:h, centrado automáticamente.
            # 3. setsar=1
            #    Asegura pixel cuadrado.
            
            vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
            
            cmd = [
                "ffmpeg", "-y", 
                "-i", path,
                "-vf", vf,
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "copy", # Try copy audio first (or aac if needed)
                out_path
            ]
            
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"Resize Cmd: {cmd}\n")
            
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            _, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(out_path):
                return out_path
                
            # If audio copy fails (codecs mismatch handling), retry with aac
            if "Audio" in str(stderr):
                 with open(log_file, "a", encoding="utf-8") as f: f.write(f"⚠️ Audio Copy failed during resize. Retrying with AAC...\n")
                 cmd[12] = "aac" 
                 cmd.insert(13, "-b:a")
                 cmd.insert(14, "128k")
                 
                 process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                 )
                 await process.wait()
                 if os.path.exists(out_path): return out_path
            
            with open(log_file, "a", encoding="utf-8") as f: 
                f.write(f"Resize Error (RC={process.returncode}): {stderr.decode() if stderr else 'Unknown'}\n")
                
        except Exception as e:
            print(f"Error Resizing: {e}")
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"Resize Ex: {e}\n")
            
    return None

async def create_video_collage(video_path, grid='3x3'):
    log_file = "media_debug.log"
    out_path = f"{os.path.splitext(video_path)[0]}_collage.jpg"
    
    if HAS_FFMPEG:
        try:
            # 1. Obtener duración para calcular intervalo
            _, _, dur = await get_meta(video_path)
            if dur <= 0: dur = 10 # Fallback
            
            # Setup Grid
            if grid == '2x2':
                cols, rows, total_frames = 2, 2, 4
            elif grid == '2x1':
                cols, rows, total_frames = 2, 1, 2
            else: # 3x3
                cols, rows, total_frames = 3, 3, 9
                
            grid_str = f"{cols}x{rows}"

            # User Request: Ignorar el primer segundo y el último.
            usable_dur = dur - 2
            if usable_dur < 1: usable_dur = dur 
            
            interval = usable_dur / total_frames
            
            cmd = [
                "ffmpeg", "-y",
                "-ss", "00:00:01", 
                "-i", video_path,
                "-vf", f"select=isnan(prev_selected_t)+gte(t-prev_selected_t\,{interval}),scale=480:-1,tile={grid_str}",
                "-frames:v", "1",
                "-q:v", "2", 
                out_path
            ]
            
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"Collage Cmd ({grid}): {cmd}\n")
            
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            _, stderr = await process.communicate()
            
            if os.path.exists(out_path):
                return out_path
            else:
                 with open(log_file, "a", encoding="utf-8") as f: 
                    f.write(f"Collage Failed: {stderr.decode() if stderr else 'Unknown'}\n")
                    
        except Exception as e:
            print(f"Error Collage: {e}")
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"Collage Ex: {e}\n")
            
    return None

async def detect_intro_cut_time(video_path):
    """
    Detecta el final de una intro analizando cambios de escena en los primeros 20s.
    Retorna el timestamp (float) donde cortar.
    """
    if not HAS_FFMPEG: return 0
    try:
        # --- PHASE 1: STANDARD CUT (Sharp Transitions) ---
        # Analizar 20s, buscar cambios de escena > 0.3 (Hard Cuts)
        cmd_p1 = [
            "ffmpeg", 
            "-ss", "0", "-t", "20",
            "-i", video_path,
            "-vf", "select='gt(scene,0.3)',showinfo",
            "-f", "null", "-"
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd_p1, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        _, stderr = await process.communicate()
        output_p1 = stderr.decode('utf-8', errors='ignore')
        
        import re
        matches = re.findall(r"pts_time:([0-9\.]+)", output_p1)
        
        # Priority 1: Classic Hard Cut (2s - 15s)
        for m in matches:
            t = float(m)
            if t > 2.0 and t < 15.0:
                print(f"🎬 Smart Cut (Hard): {t}s")
                return t

        # --- PHASE 2: SMOOTH / FADE DETECTION (Fallback) ---
        # Si no hubo cortes duros, buscar pantallazos negros (fades) o cambios sutiles
        print("🕵️ Smart Cut: No hard cut found. Trying smooth detection...")
        
        # Usamos blackdetect para encontrar intervalos negros
        # y select con umbral bajo (0.08) para disolvencias
        cmd_p2 = [
            "ffmpeg", 
            "-ss", "0", "-t", "20",
            "-i", video_path,
            "-vf", "blackdetect=d=0.1:pix_th=0.1,select='gt(scene,0.08)',showinfo",
            "-f", "null", "-"
        ]
        
        process_p2 = await asyncio.create_subprocess_exec(
            *cmd_p2, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        _, stderr_p2 = await process_p2.communicate()
        output_p2 = stderr_p2.decode('utf-8', errors='ignore')
        
        # 1. Check for Black Detects: "black_end:3.5"
        # ffmpeg output example: [blackdetect @ ...] black_start:2.1 black_end:3.5 black_duration:1.4
        black_ends = re.findall(r"black_end:([0-9\.]+)", output_p2)
        
        best_black_cut = 0.0
        for b in black_ends:
            t = float(b)
            if t > 1.0 and t < 18.0:
                # Preferimos el último corte negro antes de los 18s (fin de intro)
                best_black_cut = t
        
        if best_black_cut > 0:
            print(f"🎬 Smart Cut (Black Fade): {best_black_cut}s")
            return best_black_cut

        # 2. Check for Soft Scene Changes (> 0.08)
        matches_soft = re.findall(r"pts_time:([0-9\.]+)", output_p2)
        for m in matches_soft:
            t = float(m)
            if t > 2.0 and t < 15.0:
                print(f"🎬 Smart Cut (Soft): {t}s")
                return t
        
        return 0

    except Exception as e:
        print(f"Error Smart Detect: {e}")
        return 0

async def smart_cut_video(input_path):
    # 1. Detectar tiempo
    cut_time = await detect_intro_cut_time(input_path)
    
    if cut_time <= 0: return None # No se detectó intro clara
    
    # 2. Cortar usando cut_video_start (existente)
    # cut_video_start ya maneja re-encode si copy falla.
    # Necesitamos importar cut_video_start o asegurarnos que esté disponible en scope.
    # Está definido arriba en este archivo.
    
    # FIX: cut_video_start retorna solo path, necesitamos path y tiempo?
    # El usuario de esta funcion espera (path, time)
    res = await cut_video_start(input_path, cut_time)
    return res, cut_time
       
    return None

# --- AUTO SUBTITLE LOGIC ---
def format_timestamp(seconds: float):
    # SRT format: 00:00:00,000
    ms = int((seconds % 1) * 1000)
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


        
# --- FASTER WHISPER GLOBAL MODEL ---
GLOBAL_WHISPER = None

def get_whisper_model():
    global GLOBAL_WHISPER
    if GLOBAL_WHISPER is None:
        print("🚀 Loading Faster Whisper Model (Small)...")
        from faster_whisper import WhisperModel
        # Run on CPU with INT8 by default (Most compatible for valid server/PC)
        # If GPU available, user can change device='cuda', compute_type='float16'
        try:
            GLOBAL_WHISPER = WhisperModel("small", device="cpu", compute_type="int8")
        except Exception as e:
            print(f"Error loading Whisper: {e}")
            return None
    return GLOBAL_WHISPER

async def generate_subtitles_video(video_path, cid=None):
    """
    Usa Faster-Whisper para transcribir optimizado.
    Soporta traducción y EMOJIS (via Gemini) si se solicita.
    """
    try:
        # 1. Output Path
        ts = int(time.time())
        srt_path = video_path.replace(".mp4", f"_{ts}.srt")
        out_path = video_path.replace(".mp4", f"_sub_{ts}.mp4")
        
        # 2. Transcribe (Blocking, run in executor)
        def run_transcribe():
            model = get_whisper_model()
            if not model: return None, None
            
            # Segments is a generator in faster-whisper
            segments_gen, info = model.transcribe(video_path, beam_size=5)
            # Convert to list immediately to use in async
            return list(segments_gen), info

        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, run_transcribe)
        if not res: return None
        
        segments, info = res
        detected_lang = info.language
        print(f"Whisper Detected: {detected_lang} (Prob: {info.language_probability:.2f})")
        
        # --- LOGICA EMOJIS / TRADUCCIÓN ---
        # Si NO es español, traducimos.
        # Si ES español (o ya traducido), agregamos emojis si el usuario lo pidió (Implícito en "optimized version")
        
        texts = [s.text.strip() for s in segments]
        
        # --- LÓGICA SIN IA (SOLO TRANSCRIPCIÓN LOCAL) ---
        # El usuario solicitó eliminar la dependencia de la IA externa (Gemini)
        # por lo que simplemente usaremos la transcripción pura obtenida por Whisper.
        
        final_texts = texts
        
        # 3. Create SRT content
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments):
                start = format_timestamp(seg.start)
                end = format_timestamp(seg.end)
                
                # Get Enhanced Text
                text = final_texts[i] if i < len(final_texts) else seg.text.strip()
                
                f.write(f"{i+1}\n{start} --> {end}\n{text}\n\n")
                
        # 4. Burn Subtitles with FFmpeg
        # Verify path escaping for Windows FFmpeg
        # Using forward slashes usually works best in filter chains even on Windows
        srt_path_esc = srt_path.replace("\\", "/").replace(":", "\\:")
        
        # Style: Yellow with Black outline, Arial, Size 12 (Smaller)
        style = "FontName=Arial,FontSize=12,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=15,Alignment=2"
        # Color &H0000FFFF is Yellow in ASS format (BBGGRR) -> 00(Alpha) 00(Blue) FF(Green) FF(Red) = Cyan? No.
        # Yellow is R=255, G=255, B=0 -> Hex FFFF00. In ASS it is 00 + (00) + (FF) + (FF) -> &H0000FFFF (BBGGRR). Correct.
        
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles='{srt_path_esc}':force_style='{style}'",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "copy",
            out_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        _, stderr = await process.communicate()
        
        # Cleanup SRT
        try: os.remove(srt_path)
        except: pass
        
        if os.path.exists(out_path):
            return out_path
        else:
            print(f"FFmpeg Sub Error: {stderr.decode() if stderr else 'Unknown'}")
            
    except Exception as e:
        print(f"Subtitler Error: {e}")
        
    return None

async def generate_catalog_thumbs(video_path, interval=30):
    """
    Genera miniaturas cada N segundos del video usando one-pass.
    Retorna lista de paths.
    """
    log_file = "media_debug.log"
    paths = []
    
    if HAS_FFMPEG:
        try:
            base = os.path.splitext(video_path)[0]
            # Pattern for output: base_cat_001.jpg
            out_pattern = f"{base}_cat_%03d.jpg"
            
            # Use fps filter: 1 frame every 'interval' seconds -> fps=1/interval
            # scale=320:-1 optimize for menu view (fast load)
            vf = f"fps=1/{interval},scale=320:-1"
            
            cmd = [
                "ffmpeg", "-i", video_path, 
                "-vf", vf, 
                "-q:v", "2", 
                out_pattern, "-y"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            await process.wait()
            
            # Find generated files
            dir_name = os.path.dirname(video_path)
            prefix = os.path.basename(base) + "_cat_"
            
            for f in os.listdir(dir_name):
                if "_cat_" in f and f.endswith(".jpg") and base in os.path.join(dir_name, f):
                    paths.append(os.path.join(dir_name, f))
            
            # Sort naturally just in case (001, 002...)
            paths.sort()
            
            # If empty (maybe video < 30s), extract at least 00:00:01
            if not paths:
                 one_out = f"{base}_cat_001.jpg"
                 cmd_one = ["ffmpeg", "-ss", "00:00:01", "-i", video_path, "-vframes", "1", "-q:v", "2", "-vf", "scale=320:-1", one_out, "-y"]
                 process = await asyncio.create_subprocess_exec(*cmd_one, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                 await process.wait()
                 if os.path.exists(one_out): paths.append(one_out)

        except Exception as e:
            print(f"Catalog Error: {e}")
            
    return paths

async def create_mixed_media_collage(media_paths, grid=None):
    """
    Crea un collage imagen (JPG) a partir de multiples inputs (Video o Imagen).
    Si es video, extrae un frame.
    Si es imagen, la usa.
    media_paths: Lista de rutas de archivos.
    """
    log_file = "media_debug.log"
    if not media_paths: return None
    
    # Ensure all paths exist
    valid_paths = [p for p in media_paths if os.path.exists(p)]
    if not valid_paths: return None
    
    out_path = f"downloads/mixed_collage_{int(time.time())}.jpg"
    
    try:
        # 1. Determinar Grid si no se fuerza
        count = len(valid_paths)
        if not grid:
            if count <= 2: grid = f"{count}x1" # 2x1 Horizontal
            elif count <= 4: grid = "2x2"
            elif count <= 6: grid = "3x2"
            elif count <= 9: grid = "3x3"
            else: grid = "4x4"
            
        # 2. Construir inputs y filter complex
        # ffmpeg -i 1 -i 2 ... -filter_complex "[0:v]scale=480:480:force_original_aspect_ratio=increase,crop=480:480[v0];...[v0][v1]...tile=GRID"
        
        cmd_inputs = []
        filter_parts = []
        labels = []
        
        # Tamaño de celda estandarizado
        cw, ch = 480, 480
        
        for i, path in enumerate(valid_paths):
            cmd_inputs.extend(["-i", path])
            # Escalar y recortar para llenar el cuadrado perfecto
            filter_parts.append(f"[{i}:v]scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch}[v{i}]")
            labels.append(f"[v{i}]")
            
        # Unir todo en tile
        # tile=3x3
        filter_join = f"{''.join(labels)}tile={grid}"
        
        full_filter = ";".join(filter_parts) + ";" + filter_join
        
        cmd = ["ffmpeg", "-y"] + cmd_inputs + ["-filter_complex", full_filter, "-q:v", "2", out_path]
        
        with open(log_file, "a", encoding="utf-8") as f: f.write(f"Mixed Collage Cmd ({count} files): {cmd}\n")
        
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        _, stderr = await process.communicate()
        
        if process.returncode == 0 and os.path.exists(out_path):
            return out_path
        else:
             with open(log_file, "a", encoding="utf-8") as f: 
                f.write(f"Mixed Collage Failed: {stderr.decode() if stderr else 'Unknown'}\n")
                
    except Exception as e:
        print(f"Error Mixed Collage: {e}")
        with open(log_file, "a", encoding="utf-8") as f: f.write(f"Mixed Collage Ex: {e}\n")
            
    return None

async def has_audio_track(path):
    """Verifica si el archivo tiene un stream de audio usando ffprobe."""
    if not HAS_FFMPEG: return True # Asumir sí para evitar loop
    try:
        cmd = [
            "ffprobe", "-v", "error", 
            "-select_streams", "a", 
            "-show_entries", "stream=index", 
            "-of", "csv=p=0", path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        stdout, _ = await process.communicate()
        return bool(stdout.strip())
    except:
        return False

async def add_silent_audio(path):
    """
    Agrega un track de audio silencioso al video para forzar formato MP4 en Telegram.
    Usa 'anullsrc' filter.
    """
    if not HAS_FFMPEG: return path
    
    base, ext = os.path.splitext(path)
    # Ensure MP4 extension for final
    out_path = f"{base}_silent_{int(time.time())}.mp4"
    log_file = "media_debug.log"
    
    try:
        # -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -> Genera silencio infinito
        # -shortest -> Corta el audio a la duración del video
        # -c:v copy -> Copia el video (rápido, sin pérdida)
        # -c:a aac -> Encodea el silencio a AAC
        cmd = [
            "ffmpeg", "-y",
            "-i", path,
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            out_path
        ]
        
        with open(log_file, "a", encoding="utf-8") as f: f.write(f"Silent Audio Cmd: {cmd}\n")
        
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        _, stderr = await process.communicate()
        
        if process.returncode == 0 and os.path.exists(out_path):
            return out_path
        else:
             with open(log_file, "a", encoding="utf-8") as f: 
                f.write(f"Add Silent Audio Failed: {stderr.decode() if stderr else 'Unknown'}\n")
                
    except Exception as e:
        print(f"Error Silent Audio: {e}")
        with open(log_file, "a", encoding="utf-8") as f: f.write(f"Silent Audio Ex: {e}\n")
        
    return None