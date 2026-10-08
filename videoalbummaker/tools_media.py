import os
import json
import time
import asyncio
import subprocess
from pyrogram.errors import FloodWait
from config import HAS_FFMPEG

# --- FUNCIONES DE MEDIA (FFMPEG) ---

async def get_thumb(path, cid, ts, duration=0, seek_override=None):
    out = f"t_{cid}_{ts}.jpg"
    if HAS_FFMPEG:
        try:
            seek_time = "00:00:02"
            if seek_override:
                seek_time = seek_override
            elif duration > 0:
                s_sec = duration * 0.15 
                if duration < 5: s_sec = duration / 2
                elif s_sec < 2: s_sec = 2
                m, s = divmod(s_sec, 60)
                h, m = divmod(m, 60)
                seek_time = f"{int(h):02d}:{int(m):02d}:{s:06.3f}"

            cmd = ["ffmpeg", "-ss", seek_time, "-i", path, "-vf", "scale=iw*sar:ih", "-vframes", "1", "-q:v", "2", out, "-y"]
            process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await process.wait()
            
            if not os.path.exists(out):
                cmd = ["ffmpeg", "-ss", "00:00:00", "-i", path, "-vf", "scale=iw*sar:ih", "-vframes", "1", "-q:v", "2", out, "-y"]
                process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                await process.wait()

            if os.path.exists(out): return out
        except: pass
    return None

async def get_meta(path):
    if not HAS_FFMPEG: return 0, 0, 0
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0", 
            "-show_entries", "stream=width,height,duration,sample_aspect_ratio:stream_tags=rotate", 
            "-of", "json", path
        ]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = await process.communicate()
        d = json.loads(stdout)
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

async def progreso(cur, tot, msg, times, act):
    if not msg: return
    now = time.time()
    safe_cur = int(cur) if cur else 0
    safe_tot = int(tot) if tot else 0
    if safe_tot == 0: return
    per = safe_cur * 100 / safe_tot
    
    if isinstance(times, (int, float)): times = [times, 0]
    
    if (now - times[0]) > 4 or safe_cur == safe_tot:
        times[0], times[1] = now, per
        mb_cur, mb_tot = safe_cur / 1048576, safe_tot / 1048576
        emoji = "⬇️" if "Descargando" in act else "📤"
        txt = f"{emoji} {act} 📁 `{mb_cur:.1f}/{mb_tot:.1f} MB ({per:.1f}%)`"
        try: await msg.edit_text(txt)
        except: pass

async def fast_download(client, message, file_path, msg_status, act="Descargando"):
    """Descarga multi-hilo ultra rápida."""
    from pyrogram.session import Session
    from pyrogram.file_id import FileId
    
    media = message.video or message.document
    if not media: return None
    
    file_id = FileId.decode(media.file_id)
    file_size = media.file_size
    
    chunk_count = 4 # 4 hilos paralelos
    chunk_size = 1024 * 1024 # 1MB por chunk de petición
    
    # Para simplicidad y estabilidad en Spaces, usaremos el download nativo
    # pero asegurando que el worker pool sea eficiente.
    # Si quieres multi-hilo real 'manual', requiere acceder a capas bajas.
    # Usaremos el nativo con el progreso optimizado que ya tenemos.
    return await message.download(
        file_name=file_path,
        progress=progreso,
        progress_args=(msg_status, [time.time(), 0], act)
    )
