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

    interval = 1.5 if "Descargando" in act else 3
    
    if (now - times[0]) > interval or safe_cur == safe_tot:
        time_elapsed = now - times[0]
        bytes_diff = safe_cur - times[1]
        speed_bps = bytes_diff / time_elapsed if time_elapsed > 0 else 0
        speed_mbps = speed_bps / 1048576
        
        times[0], times[1] = now, safe_cur
        
        emoji = "⬇️" if "Descargando" in act else "📤"
        mb_cur, mb_tot = safe_cur / 1048576, safe_tot / 1048576
        
        if "Descargando" in act:
            txt = f"{emoji} {act} 📁 `{mb_cur:.1f}/{mb_tot:.1f} MB`\n🚀 **Velocidad:** `{speed_mbps:.1f} MB/s`\n📊 **Progreso:** `{per:.1f}%`"
        else:
            txt = f"{emoji} {act} 📁 `{mb_cur:.1f}/{mb_tot:.1f} MB`\n📊 **Progreso:** `{per:.1f}%`"
            
        try: await msg.edit_text(txt, reply_markup=kb)
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except: pass

async def fast_download(client: Client, message, file_path, msg_status, act="Descargando", kb=None):
    """Descarga de 16 hilos concurrentes por archivo."""
    media = message.video or message.document
    if not media: return None
    
    file_id_obj = FileId.decode(media.file_id)
    file_size = media.file_size
    
    # 16 hilos de descarga
    num_threads = 16
    # Tamaño de cada parte
    part_size = math.ceil(file_size / num_threads)
    
    # Pre-reservar archivo (Importante para acceso directo a offsets)
    with open(file_path, "wb") as f:
        f.truncate(file_size)

    total_downloaded = 0
    t_data = [time.time(), 0]
    
    # Semáforo para no saturar si hubiera archivos minúsculos (pero usaremos 16 tareas fijas)
    
    async def download_part(part_idx):
        nonlocal total_downloaded
        start = part_idx * part_size
        end = min(start + part_size, file_size)
        
        if start >= file_size: return
        
        # En Windows/Selector o Linux esto vuela con 16 tareas
        current_pos = start
        async for chunk in client.get_file(file_id_obj, offset=start, limit=end-start):
            with open(file_path, "rb+") as f:
                f.seek(current_pos)
                f.write(chunk)
            current_pos += len(chunk)
            total_downloaded += len(chunk)
            # Actualizar progreso
            await progreso(total_downloaded, file_size, msg_status, t_data, act, kb)

    # Lanzar los 16 hilos
    tasks = [download_part(i) for i in range(num_threads)]
    await asyncio.gather(*tasks)
    
    return file_path

# Función auxiliar para subida paralela (16 hilos)
async def fast_upload(client: Client, file_path, msg_status, act="Subiendo"):
    """Subida paralela de 16 hilos."""
    file_size = os.path.getsize(file_path)
    # Part size para archivos grandes es 512KB
    part_size = 512 * 1024
    total_parts = math.ceil(file_size / part_size)
    is_big = file_size > 10 * 1024 * 1024
    
    file_id = int(time.time() * 1000)
    
    t_data = [time.time(), 0]
    uploaded_parts = 0
    
    semaphore = asyncio.Semaphore(16) # 16 hilos de subida

    async def upload_part(part_index):
        nonlocal uploaded_parts
        async with semaphore:
            offset = part_index * part_size
            with open(file_path, "rb") as f:
                f.seek(offset)
                chunk = f.read(part_size)
            
            for _ in range(3): # Reintentos
                try:
                    if is_big:
                        await client.invoke(
                            SaveBigFilePart(
                                file_id=file_id,
                                file_part=part_index,
                                file_total_parts=total_parts,
                                bytes=chunk
                            )
                        )
                    else:
                        await client.invoke(
                            SaveFilePart(
                                file_id=file_id,
                                file_part=part_index,
                                bytes=chunk
                            )
                        )
                    break
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                except Exception:
                    await asyncio.sleep(1)

            uploaded_parts += 1
            cur_bytes = uploaded_parts * part_size
            if cur_bytes > file_size: cur_bytes = file_size
            await progreso(cur_bytes, file_size, msg_status, t_data, act)

    tasks = [upload_part(i) for i in range(total_parts)]
    await asyncio.gather(*tasks)
    
    # Retornar objeto InputFile para usar en send_video/document
    if is_big:
        return InputFileBig(id=file_id, parts=total_parts, name=os.path.basename(file_path))
    else:
        return InputFile(id=file_id, parts=total_parts, name=os.path.basename(file_path), md5_checksum="")
