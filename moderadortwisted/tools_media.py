import os
import json
import time
import asyncio
import subprocess
import math
import logging
from pyrogram import Client
from pyrogram.errors import FloodWait
from pyrogram.raw.functions.auth import ExportAuthorization
from pyrogram.raw.functions.upload import SaveBigFilePart, SaveFilePart
from pyrogram.raw.types import InputFileBig, InputFile
from pyrogram.file_id import FileId

from config import HAS_FFMPEG

# --- FUNCIONES DE MEDIA (FFMPEG) ---

async def get_thumb(path, cid, ts, duration=0, seek_override=None, count=1):
    out_paths = []
    if not HAS_FFMPEG: return []

    try:
        if count <= 1:
            out = f"t_{cid}_{ts}.jpg"
            seek_time = "00:00:02"
            if seek_override: seek_time = seek_override
            elif duration > 0:
                s_sec = duration * 0.15 
                if duration < 5: s_sec = duration / 2
                elif s_sec < 2: s_sec = 2
                m, s = divmod(s_sec, 60)
                h, m = divmod(m, 60)
                seek_time = f"{int(h):02d}:{int(m):02d}:{s:06.3f}"

            commands_to_try = [
                ["ffmpeg", "-ss", seek_time, "-i", path, "-vf", "thumbnail", "-vframes", "1", "-q:v", "2", out, "-y"],
                ["ffmpeg", "-ss", "00:00:00", "-i", path, "-vf", "thumbnail", "-vframes", "1", "-q:v", "2", out, "-y"],
                ["ffmpeg", "-i", path, "-vf", "thumbnail", "-vframes", "1", "-q:v", "2", out, "-y"]
            ]
            for idx, cmd in enumerate(commands_to_try):
                process = await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                if os.path.exists(out): 
                    out_paths.append(out)
                    break
                else:
                    print(f"Fallback {idx} falló. FFMPEG ERROR: {process.stderr.decode('utf-8', errors='ignore')}")
        else:
            # Primero extraer la miniatura PRINCIPAL usando el segundo configurado
            out_main = f"t_{cid}_{ts}_main.jpg"
            seek_time_main = "00:00:02"
            if seek_override: seek_time_main = seek_override
            elif duration > 0:
                s_sec = duration * 0.15 
                if duration < 5: s_sec = duration / 2
                elif s_sec < 2: s_sec = 2
                m, s = divmod(s_sec, 60)
                h, m = divmod(m, 60)
                seek_time_main = f"{int(h):02d}:{int(m):02d}:{s:06.3f}"
            
            commands_to_try = [
                ["ffmpeg", "-ss", seek_time_main, "-i", path, "-vf", "thumbnail", "-vframes", "1", "-q:v", "2", out_main, "-y"],
                ["ffmpeg", "-ss", "00:00:00", "-i", path, "-vf", "thumbnail", "-vframes", "1", "-q:v", "2", out_main, "-y"],
                ["ffmpeg", "-i", path, "-vf", "thumbnail", "-vframes", "1", "-q:v", "2", out_main, "-y"]
            ]
            for cmd in commands_to_try:
                await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                if os.path.exists(out_main): 
                    out_paths.append(out_main)
                    break

            # Luego extraer las escenas adicionales (ahora generamos exactamente 'count' escenas)
            if duration <= 0: duration = 20
            
            # Generaremos la candidad pedida de escenas, aparte de la miniatura principal
            total_extra = count
            if total_extra > 0:
                step = duration / (total_extra + 1)
                for i in range(1, total_extra + 1):
                    s_sec = step * i
                    m, s = divmod(s_sec, 60)
                    h, m = divmod(m, 60)
                    seek_time = f"{int(h):02d}:{int(m):02d}:{float(s):06.3f}"
                    out_i = f"t_{cid}_{ts}_{i}.jpg"
                    
                    cmd = ["ffmpeg", "-ss", seek_time, "-i", path, "-vf", "thumbnail", "-vframes", "1", "-q:v", "2", out_i, "-y"]
                    await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    if os.path.exists(out_i): out_paths.append(out_i)
                    else:
                        cmd2 = ["ffmpeg", "-i", path, "-vf", "thumbnail", "-vframes", "1", "-q:v", "2", out_i, "-y"]
                        await asyncio.to_thread(subprocess.run, cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                        if os.path.exists(out_i): out_paths.append(out_i)

    except Exception as e:
        import traceback
        print(f"Error FFMPEG thumb traceback: {repr(e)}")
        traceback.print_exc()
        
    return out_paths

async def get_meta(path):
    if not HAS_FFMPEG: return 0, 0, 0
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0", 
            "-show_entries", "stream=width,height,duration,sample_aspect_ratio:stream_tags=rotate", 
            "-of", "json", path
        ]
        process = await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        d = json.loads(process.stdout)
        s = d['streams'][0]
        w = int(s.get('width', 0))
        h = int(s.get('height', 0))
        dur = int(float(s.get('duration', 0)))
        
        sar = s.get('sample_aspect_ratio', '1:1')
        if sar != '1:1' and sar != '0:1' and ':' in sar:
            try:
                num, den = map(int, sar.split(':'))
                if den > 0: w = int(w * (num / den))
            except: pass
        
        tags = s.get('tags', {})
        rot = tags.get('rotate')
        if rot:
            rot = int(rot)
            if abs(rot) in [90, 270]: w, h = h, w
        return w, h, dur
    except: return 0, 0, 0

async def progreso(cur, tot, msg, times, act, kb=None):
    if not msg: return
    safe_cur = int(cur) if cur else 0
    safe_tot = int(tot) if tot else 0
    
    if safe_tot == 0 or safe_cur == 0: return
    
    now = time.time()
    per = safe_cur * 100 / safe_tot
    
    if not isinstance(times, list) or len(times) != 2:
        times.clear()
        times.extend([now, safe_cur])
        return

    # Intervalo de actualización (Aumentado a 8 segundos para evitar FloodWait por spam de ediciones a Telegram al tener múltiples tareas)
    interval = 8.0
    
    if (now - times[0]) > interval or safe_cur == safe_tot:
        time_elapsed = now - times[0]
        bytes_diff = safe_cur - times[1]
        speed_bps = bytes_diff / time_elapsed if time_elapsed > 0 else 0
        speed_mbps = speed_bps / 1048576
        
        times[0], times[1] = now, safe_cur
        
        emoji = "⬇️" if "Descargando" in act else "📤"
        mb_cur, mb_tot = safe_cur / 1048576, safe_tot / 1048576
        
        txt = f"{emoji} {act} 📁 `{mb_cur:.1f}/{mb_tot:.1f} MB ({per:.1f}%) {speed_mbps:.1f} MB/s`"
            
        try: await msg.edit_text(txt, reply_markup=kb)
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except: pass

async def fast_download(client: Client, message, file_path, msg_status, act="Descargando", kb=None):
    """Descarga nativa de Pyrogram (estable)."""
    media = message.video or message.document or message.audio or message.voice
    if not media: 
        return await client.download_media(message, file_name=file_path)
    
    t_data = [time.time() - 8.0, 0]
    async def pyrogram_progress(current, total):
        await progreso(current, total, msg_status, t_data, act, kb)
        
    try:
        return await client.download_media(message, file_name=file_path, progress=pyrogram_progress)
    except Exception as e:
        print(f"Error descargando natively: {e}")
        return None

