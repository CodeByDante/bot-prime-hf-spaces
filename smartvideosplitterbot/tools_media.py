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
    if not HAS_FFMPEG: return 0, 0, 0, 0
    try:
        w, h, dur = 0, 0, 0
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0", 
            "-show_entries", "stream=width,height,duration,sample_aspect_ratio:stream_tags=rotate", 
            "-of", "json", path
        ]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = await process.communicate()
        d = json.loads(stdout)
        if d.get('streams'):
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
            
        # Contar pistas de audio
        cmd_a = [
            "ffprobe", "-v", "error", "-select_streams", "a", 
            "-show_entries", "stream=index,duration", "-of", "json", path
        ]
        proc_a = await asyncio.create_subprocess_exec(*cmd_a, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_a, _ = await proc_a.communicate()
        d_a = json.loads(stdout_a)
        streams_a = d_a.get('streams', [])
        audio_count = len(streams_a)
        
        if dur == 0 and audio_count > 0:
            dur = int(float(streams_a[0].get('duration', 0) or 0))
        
        # Si todavía no hay duración (puede que esté en format)
        if dur == 0:
            cmd_f = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path]
            proc_f = await asyncio.create_subprocess_exec(*cmd_f, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout_f, _ = await proc_f.communicate()
            d_f = json.loads(stdout_f)
            if 'format' in d_f and 'duration' in d_f['format']:
                try: dur = int(float(d_f['format']['duration']))
                except: pass

        return w, h, dur, audio_count
    except Exception as e:
        print(f"Error get_meta: {e}")
        return 0, 0, 0, 0

async def progreso(cur, tot, msg, times, act, kb=None):
    if not msg: return
    safe_cur = int(cur) if cur else 0
    safe_tot = int(tot) if tot else 0
    
    # DEBUG LINE
    # print(f"[DEBUG PROGRESS] {act} | cur: {safe_cur} | tot: {safe_tot} | times: {times}")

    if safe_tot == 0 or safe_cur == 0: return  # Ignoramos el byte 0 para no atascar Pyrogram en su lectura primaria
    
    now = time.time()
    if safe_tot == 0: return
    per = safe_cur * 100 / safe_tot
    
    if isinstance(times, (int, float)): times = [times, 0]
    
    # Adaptar times a [last_time, last_per, last_bytes, last_time_speed, speed_str]
    if len(times) == 2:
        times.extend([safe_cur, now, "0.0 MB/s"])
    
    # Diferenciar velocidad de actualización: Descarga necesita feedback rápido, Subida necesita evitar bloqueo
    interval = 3 if "Descargando" in act else 8
    
    if (now - times[0]) > interval or safe_cur == safe_tot:
        diff_bytes = safe_cur - times[2]
        diff_time = now - times[3]
        
        if diff_time > 0 and diff_bytes > 0:
            speed_mb = (diff_bytes / diff_time) / 1048576
            times[4] = f"{speed_mb:.1f} MB/s"
            
        times[0], times[1] = now, per
        times[2], times[3] = safe_cur, now
        
        emoji = "⬇️" if "Descargando" in act else "📤"
        
        if "Descargando" in act:
            mb_cur, mb_tot = safe_cur / 1048576, safe_tot / 1048576
            txt = f"{emoji} {act} 📁 `{mb_cur:.1f}/{mb_tot:.1f} MB ({per:.1f}%) {times[4]}`"
        else:
            # Para subidas masivas (ej 60 partes), mensaje ultra-ligero
            txt = f"{emoji} {act} 📁"
            
        try: await msg.edit_text(txt, reply_markup=kb)
        except: pass

async def fast_download(client, message, file_path, msg_status, act="Descargando", kb=None):
    """Descarga multi-hilo ultra rápida."""
    from pyrogram.session import Session
    from pyrogram.file_id import FileId
    
    media = message.video or message.document or message.video_note or message.audio or message.voice
    if not media: return None
    
    file_id = getattr(media, "file_id", None)
    if not file_id: return None
    
    from pyrogram.file_id import FileId
    file_id_decoded = FileId.decode(file_id)
    file_size = media.file_size
    
    chunk_count = 16 # 16 hilos paralelos
    chunk_size = 1024 * 1024 # 1MB por chunk de petición
    
    # Para simplicidad y estabilidad en Spaces, usaremos el download nativo
    # pero asegurando que el worker pool sea eficiente.
    # Si quieres multi-hilo real 'manual', requiere acceder a capas bajas.
    # Usaremos el nativo con el progreso optimizado que ya tenemos.
    print(f"[DEBUG DOWN] Initiating message.download for {file_path}")
    try:
        res = await message.download(
            file_name=file_path,
            progress=progreso,
            progress_args=(msg_status, [0.0, 0], act, kb)
        )
        print(f"[DEBUG DOWN] Download complete, result: {res}")
        return res
    except Exception as e:
        print(f"[DEBUG DOWN EXCEPTION] Exception during message.download: {e}")
        return None
