import re

import os

import asyncio

import requests

import zipfile

from deep_translator import GoogleTranslator

from config import COOKIE_MAP, TOOLS_DIR



# --- HELPER: ZIP SPLITTER ---

def create_split_zips(files, base_name, max_size=1.9 * 1024 * 1024 * 1024):

    """Agrupa archivos en ZIPs que no superen max_size."""

    archives = []

    

    current_batch = []

    current_size = 0

    part_num = 1

    

    for f_path in files:

        f_size = os.path.getsize(f_path)

        # Si un solo archivo es mayor al límite, va solo en su propio ZIP (Telegram limitará igual, pero bueno)

        if current_size + f_size > max_size and current_batch:

            # Cerrar batch actual

            zip_name = f"{base_name}_part{part_num}.zip"

            with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:

                for tf in current_batch:

                    zf.write(tf, os.path.basename(tf))

            archives.append(zip_name)

            

            # Reset

            current_batch = []

            current_size = 0

            part_num += 1

            

        current_batch.append(f_path)

        current_size += f_size

        

    # Último batch

    if current_batch:

        zip_name = f"{base_name}_part{part_num}.zip" if part_num > 1 else f"{base_name}.zip"

        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:

            for tf in current_batch:

                zf.write(tf, os.path.basename(tf))

        archives.append(zip_name)

        

    return archives



def format_bytes(size):

    if not size or size <= 0: return "N/A"

    power = 2**10

    n = 0

    power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB'}

    while size > power and n < 3:

        size /= power

        n += 1

    return f"{size:.1f} {power_labels[n]}"



def render_bar(current, total, length=10):

    """Genera una barra de progreso visual [██░░]."""

    if total == 0: return "░" * length

    pct = current / total

    filled = int(length * pct)

    return "█" * filled + "░" * (length - filled)



def limpiar_url(url):

    url = url.strip()

    if "youtube.com" in url or "youtu.be" in url:

        match = re.search(r'(?:v=|\/|shorts\/)([0-9A-Za-z_-]{11})', url)

        if match: return f"https://www.youtube.com/watch?v={match.group(1)}"

    if "eporner" in url:

        url = re.sub(r'https?://(es|de|fr|it)\.eporner\.com', 'https://www.eporner.com', url)

    if "?" in url and not any(d in url for d in ['facebook', 'instagram', 'pornhub', 'dropbox']):

        url = url.split("?")[0]

    return url



async def resolver_url_facebook(url):

    """

    Normaliza enlaces de Facebook.

    Intenta extraer el ID numérico o alfanumérico y devuelve un formato estándar.

    """

    # 1. Expandir redirecciones (fb.watch, etc)

    if "fb.watch" in url or "goo.gl" in url or "bit.ly" in url:

        try:

            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

            loop = asyncio.get_running_loop()

            url = await loop.run_in_executor(None, lambda: requests.head(url, allow_redirects=True, headers=headers).url)

        except: pass



    # 2. Extraer ID y formatear según tipo

    # Reels

    match = re.search(r'/reel/([0-9A-Za-z_-]+)', url)

    if match: return f"https://www.facebook.com/reel/{match.group(1)}"



    # Videos con ID numérico (watch?v= o /videos/)

    match = re.search(r'/(?:videos|watch\?v)=([0-9]+)', url)

    if match: return f"https://www.facebook.com/video.php?v={match.group(1)}"

    

    # Share links (/share/r/..., /share/v/...) -> Dejar tal cual para que yt-dlp resuelva

    if "/share/" in url:

        return url



    return url



def sel_cookie(url):

    for k, v in COOKIE_MAP.items():

        if k in url and os.path.exists(v): return v

    return None



def load_cookies_dict(filename):

    """Carga cookies de Netscape y las devuelve como diccionario para aiohttp."""

    cookies = {}

    if filename and os.path.exists(filename):

        try:

            with open(filename, 'r') as f:

                for line in f:

                    if line.startswith('#') or not line.strip(): continue

                    parts = line.split('\t')

                    if len(parts) >= 7:

                        cookies[parts[5]] = parts[6].strip()

        except: pass

    return cookies



async def traducir_texto(texto):

    if not texto: return ""

    try:
        # Modo 'Calmado': Espera aleatoria de 1.5 a 3 segundos
        await asyncio.sleep(1.5 + (0.1 * (id(texto) % 10))) 
        
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: GoogleTranslator(source='auto', target='es').translate(texto))

    except Exception as e:

        print(f"Translation error: {e}")

        return texto



# Ruta a gallery-dl

# Prioridad: 1. Pip Install (Latest) | 2. Tools Local (Portable) | 3. System Path

PIP_GALLERY_PATH = r"C:\Users\Gonzalo\AppData\Roaming\Python\Python311\Scripts\gallery-dl.exe"

TOOLS_GALLERY_PATH = os.path.join(TOOLS_DIR, "gallery-dl.exe")



if os.path.exists(PIP_GALLERY_PATH):

    GALLERY_DL_EXEC = PIP_GALLERY_PATH

elif os.path.exists(TOOLS_GALLERY_PATH):

    GALLERY_DL_EXEC = TOOLS_GALLERY_PATH

else:

    GALLERY_DL_EXEC = "gallery-dl"



def descargar_galeria(url, cookie_file=None):

    """

    Descarga imágenes de X/Twitter/Facebook usando gallery-dl.

    Retorna una lista de rutas de archivos descargados y el directorio temporal.

    """

    import subprocess

    import glob

    import shutil

    

    # Directorio temporal único
    # Usamos time.time_ns() + Random para evitar colisiones si se lanzan multiples hilos
    import time
    import random
    tmp_dir = f"tmp_gallery_{time.time_ns()}_{random.randint(1000, 9999)}"

    if not os.path.exists(tmp_dir):

        os.makedirs(tmp_dir)

    

    # Construir comando

    # gallery-dl guarda por defecto en ./gallery-dl/twitter/...

    # Usamos -d para forzar una carpeta base

    cmd = [

        GALLERY_DL_EXEC,

        "--config", "gallery-dl.conf",

        "--destination", tmp_dir,
        "--write-metadata",

        "--no-mtime",

        "-q",

    ]

    

    if cookie_file:

        cmd.extend(["--cookies", cookie_file])

        

    cmd.append(url)

    

    print(f"📸 Ejecutando Gallery-DL ({cookie_file}): {' '.join(cmd)}")

    

    try:

        # Check=True lanza excepción si falla (exit code != 0)

        subprocess.run(cmd, check=True, timeout=45)

        

        # Buscar archivos descargados (solo imágenes)

        files = []

        exts = ['jpg', 'jpeg', 'png', 'webp'] # Solo imágenes, videos van por yt-dlp

        for ext in exts:

            files.extend(glob.glob(f"{tmp_dir}/**/*.{ext}", recursive=True))

        # Metadata Extraction
        metadata_text = ""
        try:
            import json
            import glob # ensure glob is available
            json_files = glob.glob(f"{tmp_dir}/**/*.json", recursive=True)
            for jf in json_files:
                try:
                    with open(jf, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Try to find content/text
                        text_found = data.get('content') or data.get('description') or data.get('title') or data.get('full_text') or ""
                        if text_found:
                            metadata_text = str(text_found).strip()
                            break
                except: continue
        except: pass

            

        print(f"✅ Gallery-DL finalizado. Encontradas {len(files)} imágenes.")

        return files, tmp_dir, metadata_text

        

    except Exception as e:

        print(f"❌ Error Gallery-DL: {e}")

        # Limpiar si hubo error grave

        try: shutil.rmtree(tmp_dir)

        except: pass

        return [], None, None



async def scan_channel_history(client, chat_id, limit=None):

    """

    Escanea el historial del canal para indexar hashtags.

    Retorna el número de mensajes indexados.

    """

    from database import hashtag_db, save_tags

    import time

    

    print(f"🔄 Iniciando escaneo de chat: {chat_id}")

    count = 0

    msgs_indexed = 0

    msgs_with_text = 0

    

    try:

        async for msg in client.get_chat_history(chat_id, limit=limit):

            count += 1

            if count % 100 == 0: print(f"⏳ Escaneados {count} mensajes...")

            

            text = msg.text or msg.caption

            if not text:

                continue

                

            msgs_with_text += 1

            if msgs_with_text <= 3:  # Debug: mostrar primeros 3 textos

                print(f"📝 Debug texto encontrado: {text[:100]}")

            

            # Buscar Hashtags

            tags = re.findall(r"#(\w+)", text)

            if tags:

                if msgs_indexed == 0:  # Debug: mostrar el primer tag encontrado

                    print(f"✅ Primer hashtag detectado: {tags}")

                    

                for tag in tags:

                    tag_clean = tag.lower()

                    if tag_clean not in hashtag_db: hashtag_db[tag_clean] = []

                    

                    # Evitar duplicados exactos (mismo mensaje)

                    exists = any(item['id'] == msg.id and item['chat'] == msg.chat.id for item in hashtag_db[tag_clean])

                    if not exists:

                        # Guardamos ID mensaje y Chat ID

                        hashtag_db[tag_clean].append({

                            'id': msg.id,

                            'chat': msg.chat.id

                        })

                msgs_indexed += 1

                

        save_tags()

        print(f"✅ Escaneo completado. Total mensajes: {count}, Con texto: {msgs_with_text}, Con tags: {msgs_indexed}")

        return msgs_indexed

        

    except Exception as e:

        print(f"❌ Error escaneando: {e}")

        import traceback

        traceback.print_exc()

        return 0



def split_video_generic(input_path, mode, value):

    """

    Divide video por: 'parts', 'min', 'sec'.

    mode: 'parts' (value=num), 'min' (value=minutos), 'sec' (value=segundos)

    """

    import subprocess

    import glob

    import os

    

    if not os.path.exists(input_path): return []

    

    try:

        # 1. Obtener duración

        cmd_dur = [

            "ffprobe", "-v", "error", "-show_entries", "format=duration",

            "-of", "default=noprint_wrappers=1:nokey=1", input_path

        ]

        duration = float(subprocess.check_output(cmd_dur).decode().strip())

    except Exception as e:

        print(f"Error duration: {e}")

        return []



    if duration < 1: return []



    # 2. Calcular segment_time

    segment_time = 0

    if mode == 'parts':

        segment_time = duration / int(value)

    elif mode == 'min':

        segment_time = float(value) * 60

    elif mode == 'sec':

        segment_time = float(value)

        

    if segment_time <= 0: return []

    

    # 3. Directorio salida

    base_dir = os.path.dirname(input_path)

    base_name, ext = os.path.splitext(os.path.basename(input_path))

    output_pattern = os.path.join(base_dir, f"{base_name}_part%03d{ext}")

    # 4. Dividir (ADAPTIVE: Precision vs Speed)
    # If segment is small (< 20s), use re-encode for precision (Keyframe independent).
    # If segment is large (>= 20s), use copy for speed.
    
    cmd_split = ["ffmpeg", "-y", "-i", input_path]
    
    if segment_time < 20:
        # Precision Mode (Ultrafast Re-encode)
        print(f"🎬 [DEBUG] Precision Mode (<20s): Re-encoding for perfect cuts.")
        cmd_split.extend([
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "copy" 
        ])
    else:
        # Speed Mode (Stream Copy)
        print(f"⚡ [DEBUG] Speed Mode (>=20s): Stream Copy.")
        cmd_split.extend([
            "-c", "copy"
        ])

    cmd_split.extend([
        "-map", "0",
        "-f", "segment", "-segment_time", str(segment_time),
        "-reset_timestamps", "1", output_pattern
    ])

    

    print(f"✂️ [DEBUG] Starting Split: {mode}={value} (seg_time={segment_time:.2f})")

    print(f"✂️ [DEBUG] Command: {' '.join(cmd_split)}")

    

    try:

        # Habilitar salida a consola para ver errores

        subprocess.run(cmd_split, check=True) 

        print(f"✅ [DEBUG] Split finished successfully.")

    except Exception as e:

        print(f"❌ [DEBUG] Error during FFmpeg split: {e}")

        return []

    

    # 5. Listar resultados

    parts = sorted(glob.glob(os.path.join(base_dir, f"{base_name}_part*{ext}")))

    print(f"📦 [DEBUG] Created {len(parts)} parts.")

    return parts



def get_video_metadata(path):

    """Retorna (width, height) del video."""

    import subprocess

    import json

    try:

        cmd = [

            "ffprobe", "-v", "error", "-select_streams", "v:0",

            "-show_entries", "stream=width,height", "-of", "json", path

        ]

        # Si no hay json en imports globales... importarlo dentro.

        out = subprocess.check_output(cmd).decode()

        data = json.loads(out)

        w = data['streams'][0]['width']

        h = data['streams'][0]['height']

        return w, h

    except Exception as e:

        print(f"Meta Error: {e}")

        return 0, 0



def compress_video_ffmpeg(input_path, crf=28, preset="fast"):

    """

    Comprime video usando FFmpeg + libx264.

    crf: 0-51 (23=default, 28=whatsapp, 35=potato).

    Retorna ruta del archivo comprimido o None si falla.

    """

    import subprocess

    import os

    

    if not os.path.exists(input_path): return None

    

    base_dir = os.path.dirname(input_path)

    base_name = os.path.splitext(os.path.basename(input_path))[0]

    output_path = os.path.join(base_dir, f"compressed_{base_name}.mp4")

    

    try:

        # Comando FFmpeg simple

        # -v error: menos spam

        # -c:v libx264: codec video

        # -crf: factor calidad

        # -preset: velocidad

        # -c:a copy: copiar audio sin tocar (más rápido)

        cmd = [

            "ffmpeg", "-y", "-i", input_path,

            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,

            "-c:a", "copy",

            output_path

        ]

        

        print(f"🗜 Iniciando compresión (CRF={crf}): {input_path}")

        subprocess.run(cmd, check=True) # Check lanza error si falla

        

        if os.path.exists(output_path):

            return output_path

        return None

        

    except Exception as e:

        print(f"❌ Error compresión: {e}")

        return None



def cut_video_range(input_path, start, end):

    """

    Corta un rango específico.

    start/end: strings formato HH:MM:SS o MM:SS o segundos.

    """

    import subprocess

    import os

    

    if not os.path.exists(input_path): return None

    

    base_dir = os.path.dirname(input_path)

    base_name, ext = os.path.splitext(os.path.basename(input_path))

    if not ext: ext = ".mp4"

    

    # Limpiar caracteres raros en tiempos para nombre archivo

    s_safe = str(start).replace(":", "-")

    e_safe = str(end).replace(":", "-")

    output_path = os.path.join(base_dir, f"cut_{base_name}_{s_safe}_to_{e_safe}{ext}")

    

    try:

        # Usamos -ss antes de -i para fast seek

        # -to especifica el punto final (no duración)

        # -c copy para velocidad máxima

        cmd = [

            "ffmpeg", "-y", 

            "-ss", str(start),

            "-to", str(end),

            "-i", input_path,

            "-c", "copy",

            "-avoid_negative_ts", "make_zero",

            output_path

        ]

        

        print(f"✂️ Cutting range {start} -> {end}")

        subprocess.run(cmd, check=True)

        

        if os.path.exists(output_path):

            return output_path

        return None

    except Exception as e:

        print(f"❌ Cut Error: {e}")

        return None



def create_split_archive(input_path, part_size_mb=1500):

    """

    Crea un archivo comprimido dividido en volúmenes.

    Prioridad: 

    1. WinRAR (Rar.exe) -> Crea .part1.rar (Ideal para el usuario)

    2. 7-Zip (7zr.exe) -> Crea .7z.001 (Open source)

    """

    import subprocess

    import glob

    import shutil

    

    if not os.path.exists(input_path): return []

    

    # Definir rutas de herramientas

    tools_dir = os.path.join(os.getcwd(), 'tools')

    rar_exe = os.path.join(tools_dir, 'Rar.exe')

    seven_z_exe = os.path.join(tools_dir, '7zr.exe')

    

    # Fallback a system path

    if not os.path.exists(rar_exe) and shutil.which("rar"): rar_exe = "rar"

    if not os.path.exists(seven_z_exe) and shutil.which("7za"): seven_z_exe = "7za"

    

    base_dir = os.path.dirname(input_path)

    base_name = os.path.splitext(os.path.basename(input_path))[0]

    

    # MODO 1: WINRAR (Prioridad usuario)

    if os.path.exists(rar_exe) or rar_exe == "rar":

        archive_name = os.path.join(base_dir, f"{base_name}.rar")

        # rar a -v1500m -m0 -ep1 archivo.rar input

        # -v: volumen size

        # -m0: store (sin comprimir, rápido para videos que ya están comprimidos)

        # -ep1: excluir ruta base, solo guardar nombre archivo

        cmd = [

            rar_exe, "a", 

            f"-v{part_size_mb}m", 

            "-m0", 

            "-ep1",

            "-y", # Yes to all

            archive_name, 

            input_path

        ]

        print(f"📦 [RAR] Iniciando compresión en volúmenes de {part_size_mb}MB...")

        try:

            subprocess.run(cmd, check=True)

            # Buscar partes creadas

            parts = sorted(glob.glob(os.path.join(base_dir, f"{base_name}.part*.rar")))

            if not parts: # A veces crea solo .rar si cabe en uno

                 parts = sorted(glob.glob(os.path.join(base_dir, f"{base_name}.rar")))

            return parts

        except Exception as e:

            print(f"❌ RAR Error: {e}")

            # Fallback a 7z si falla RAR

            

    # MODO 2: 7-ZIP

    if os.path.exists(seven_z_exe) or seven_z_exe == "7za":

        archive_name = os.path.join(base_dir, f"{base_name}.7z")

        # 7zr a -v1500m -mx0 archivo.7z input

        cmd = [

            seven_z_exe, "a", 

            f"-v{part_size_mb}m", 

            "-mx0", 

            "-y",

            archive_name, 

            input_path

        ]

        print(f"📦 [7Z] Iniciando compresión en volúmenes de {part_size_mb}MB...")

        try:

            subprocess.run(cmd, check=True)

            # Buscar partes (.7z.001, .7z.002 ...)

            parts = sorted(glob.glob(os.path.join(base_dir, f"{base_name}.7z.*")))

            if not parts:

                parts = sorted(glob.glob(os.path.join(base_dir, f"{base_name}.7z")))

            return parts

        except Exception as e:

            print(f"❌ 7Z Error: {e}")



    print("❌ No se encontró compresor (Rar.exe o 7zr.exe).")

    return []



# --- PARALLEL DOWNLOADER (TURBO) ---

async def download_parallel(client, message, file_path, concurrency=8, progress=None, progress_args=None):

    """

    Descarga un archivo de Telegram en paralelo (Turbo).

    Alineado a 1MB para evitar OFFSET_INVALID.

    """

    file_size = 0

    try:

        media = message.video or message.document or message.audio

        if not media: return None



        file_size = media.file_size

        if file_size == 0: return None

        

        # Si es pequeño (<10MB), descarga normal

        if file_size < 10 * 1024 * 1024:

            return await client.download_media(message, file_name=file_path, progress=progress, progress_args=progress_args)



        print(f"🚀 [TURBO] Iniciando descarga paralela: {file_path} ({format_bytes(file_size)})")

        

        # Pre-alocar archivo

        with open(file_path, "wb") as f:

            f.truncate(file_size)



        # Usar alineación de 1MB (1,048,576 bytes) para seguridad total

        # Telegram API prefiere potencias de 2 grandes para paralelos.

        CHUNK_ALIGN = 1024 * 1024 

        

        # Calcular tamaño de parte basado en la alineación

        # Si el archivo es menor a lo que daría la concurrencia x ALIGN, reducimos tareas

        target_part_size = (file_size // concurrency)

        target_part_size = max(CHUNK_ALIGN, (target_part_size // CHUNK_ALIGN) * CHUNK_ALIGN)

        

        tasks = []

        file_lock = asyncio.Lock()

        

        # Shared progress counter

        downloaded_bytes = 0

        progress_lock = asyncio.Lock()



        async def download_chunk(worker_id, start_byte, length):

            nonlocal downloaded_bytes

            try:

                # Debug print for developers to see in logs

                # print(f"DEBUG: Worker {worker_id} offset={start_byte} len={length}")

                

                async for chunk in client.stream_media(message, offset=start_byte, limit=length):

                    if not chunk: break

                    

                    chunk_len = len(chunk)

                    

                    async with file_lock:

                        with open(file_path, "r+b") as f:

                            f.seek(start_byte)

                            f.write(chunk)

                            start_byte += chunk_len

                            

                    # Update Progress

                    async with progress_lock:

                        downloaded_bytes += chunk_len

                        if progress:

                            try:

                                await progress(downloaded_bytes, file_size, *progress_args)

                            except: pass



            except Exception as e:

                print(f"⚠️ Worker {worker_id} Error: {e}")

                raise e



        # Repartir el trabajo

        current_offset = 0

        w_id = 0

        while current_offset < file_size:

            # El último worker se lleva el resto (que puede no estar alineado al final, pero GetFile lo permite)

            # Solo los OFFSETS de inicio deben estar alineados.

            remaining = file_size - current_offset

            length = min(target_part_size, remaining)

            

            # Si es el último tramo y es muy pequeño, unirlo al anterior si es posible? 

            # No, simplemente añadirlo.

            tasks.append(download_chunk(w_id, current_offset, length))

            current_offset += length

            w_id += 1



        # Ejecutar con protección

        await asyncio.gather(*tasks)

        

        # Verificación básica: Usamos downloaded_bytes porque el truncate engaña al os.path.getsize

        if os.path.exists(file_path) and downloaded_bytes == file_size:

            print(f"✅ [TURBO] Descarga exitosa: {file_path}")

            return file_path

        else:

            raise Exception(f"Tamaño incompleto: {downloaded_bytes}/{file_size}")



    except Exception as e:

        print(f"❌ Error en Turbo: {e}")

        print("🔄 Aplicando Fallback a descarga normal...")

        try:

            if os.path.exists(file_path): os.remove(file_path)

            # El fallback debe ser síncrono/controlado para evitar bucles

            return await client.download_media(message, file_name=file_path, progress=progress, progress_args=progress_args)

        except Exception as e2:

            print(f"❌ Fallback falló: {e2}")

            return None





def merge_videos_ffmpeg(video_paths, output_path):

    """

    Une varios videos usando el protocolo concat de FFmpeg.

    Para mayor compatibilidad, se re-codifica ligeramente o se usa filter_complex if needed.

    Aquí usaremos el método simple de concat demuxer si son del mismo formato, 

    o filter complex para mayor robustez.

    """

    import subprocess

    import os

    

    if not video_paths:

        return None

        

    # Crear archivo de lista para concat demuxer

    list_file = output_path + ".txt"

    try:

        with open(list_file, "w", encoding="utf-8") as f:

            for path in video_paths:

                # FFmpeg necesita escapar comillas y usar rutas absolutas preferiblemente

                abs_path = os.path.abspath(path).replace("\\", "/")

                f.write(f"file '{abs_path}'\n")

        

        # Ejecutar FFmpeg

        # Usamos -c copy para que sea instantáneo si son compatibles. 

        # Si fallara, habría que re-codificar.

        cmd = [

            "ffmpeg", "-y", "-f", "concat", "-safe", "0",

            "-i", list_file, "-c", "copy", output_path

        ]

        

        result = subprocess.run(cmd, capture_output=True, text=True)

        

        if result.returncode != 0:

            print(f"⚠️ Merge simple falló, re-intentando con re-codificación: {result.stderr}")

            # Fallback: Re-codificar para asegurar unión aunque sean de distintos fps/resolución

            # Esto es lento pero seguro.

            cmd_slow = ["ffmpeg", "-y"]

            for p in video_paths:

                cmd_slow.extend(["-i", p])

            

            filter_str = ""

            for i in range(len(video_paths)):

                filter_str += f"[{i}:v] [{i}:a] "

            filter_str += f"concat=n={len(video_paths)}:v=1:a=1 [v] [a]"

            

            cmd_slow.extend([

                "-filter_complex", filter_str,

                "-map", "[v]", "-map", "[a]",

                "-c:v", "libx264", "-preset", "fast", "-crf", "23",

                "-c:a", "aac", "-b:a", "128k",

                output_path

            ])

            result_slow = subprocess.run(cmd_slow, capture_output=True, text=True)

            if result_slow.returncode != 0:

                print(f"❌ Error crítico uniendo videos: {result_slow.stderr}")

                return None

        

        return output_path

    except Exception as e:

        print(f"❌ Error en merge_videos_ffmpeg: {e}")

        return None

    finally:

        if os.path.exists(list_file):

            try: os.remove(list_file)

            except: pass





def split_video_by_size(input_path, max_size_bytes=1.9 * 1024 * 1024 * 1024):

    """

    Divide un video en partes de máximo max_size_bytes usando ffmpeg.

    Calcula la duración estimada de cada parte basándose en el bitrate.

    """

    import subprocess

    import os

    import math

    from tools_media import get_meta

    

    w, h, duration = asyncio.run(get_meta(input_path))

    file_size = os.path.getsize(input_path)

    

    if file_size <= max_size_bytes:

        return [input_path]

        

    # Safety margin for Variable Bit Rate (VBR) to avoid parts exceeding max size

    safe_max_size = max_size_bytes * 0.90

    num_parts = math.ceil(file_size / safe_max_size)

    part_duration = duration / num_parts

    

    parts = []

    base, ext = os.path.splitext(input_path)

    

    for i in range(num_parts):

        start_time = i * part_duration

        output_part = f"{base}_part{i+1}.mp4"

        

        # -ss antes de -i para mayor velocidad (fast seek) con +faststart

        cmd = [

            "ffmpeg", "-y", "-ss", str(start_time), "-t", str(part_duration),

            "-i", input_path, "-c", "copy", "-movflags", "+faststart", "-map", "0:v:0?", "-map", "0:a:0?", output_part

        ]

        

        subprocess.run(cmd, capture_output=True)

        if os.path.exists(output_part):

            parts.append(output_part)

            

    return parts





def split_file_into_volumes(input_path, max_size_bytes=1.9 * 1024 * 1024 * 1024):

    """

    Divide un archivo cualquiera en partes binarias (volúmenes) evitando OOM.

    """

    import os

    file_size = os.path.getsize(input_path)

    if file_size <= max_size_bytes:

        return [input_path]

        

    parts = []

    part_num = 1

    

    # Buffer de 10MB para lectura eficiente

    BUFFER_SIZE = 10 * 1024 * 1024 

    

    try:

        with open(input_path, 'rb') as f:

            while True:

                # Verificar si queda algo por leer

                start_pos = f.tell()

                if start_pos >= file_size: break

                

                # Definir nombre parte

                part_path = f"{input_path}.{part_num:03d}"

                current_part_size = 0

                

                with open(part_path, 'wb') as pf:

                    while current_part_size < max_size_bytes:

                        # Cuánto falta para llenar esta parte

                        remaining = max_size_bytes - current_part_size

                        to_read = min(BUFFER_SIZE, remaining)

                        

                        chunk = f.read(int(to_read))

                        if not chunk: break

                        

                        pf.write(chunk)

                        current_part_size += len(chunk)

                

                parts.append(part_path)

                part_num += 1

                

        return parts

    except Exception as e:

        print(f"❌ Error en split_file_into_volumes: {e}")

        return []





def extract_images_ffmpeg(video_path, interval, mode='sec'):

    """

    Extrae fotogramas de un video cada X tiempo o un frame exacto.

    interval: número (segundos o minutos) o string 'HH:MM:SS' / 'SS'

    mode: 'sec', 'min' o 'exact'

    """

    import subprocess

    import os

    import math

    

    base = video_path.rsplit('.', 1)[0]

    out_dir = f"{base}_frames"

    if not os.path.exists(out_dir): os.makedirs(out_dir)

    

    outputs = []

    

    if mode == 'exact':

        out_f = os.path.join(out_dir, f"frame_{str(interval).replace(':', '_')}.jpg")

        cmd = [

            "ffmpeg", "-y", "-ss", str(interval), "-i", video_path,

            "-frames:v", "1", "-q:v", "2", out_f

        ]

        subprocess.run(cmd, capture_output=True)

        if os.path.exists(out_f): outputs.append(out_f)

    else:

        # Convertir a segundos

        try:

            val = float(interval)

            interval_sec = val * 60 if mode == 'min' else val

        except:

            return [], None, None



        # FPS = 1 / interval

        cmd = [

            "ffmpeg", "-y", "-i", video_path,

            "-vf", f"fps=1/{interval_sec}", "-q:v", "2",

            os.path.join(out_dir, "img_%03d.jpg")

        ]

        subprocess.run(cmd, capture_output=True)

        for f in sorted(os.listdir(out_dir)):

            if f.endswith(".jpg"):

                outputs.append(os.path.join(out_dir, f))

                

    return outputs, out_dir





def video_to_gif_ffmpeg(video_path):

    """Convierte un video a GIF optimizado usando filtros de paleta para alta calidad."""

    import subprocess

    import os

    import time

    

    out_gif = video_path.rsplit('.', 1)[0] + ".gif"

    

    # Nombre único para la paleta para evitar conflictos

    palette = os.path.join(os.path.dirname(video_path), f"palette_{int(time.time())}.png")

    

    try:

        # 1. Generar paleta de 256 colores optimizada

        # bajamos a 12 FPS y 360p para que el GIF no pese demasiado y Telegram lo reproduzca bien

        subprocess.run([

            "ffmpeg", "-y", "-i", video_path, 

            "-vf", "fps=12,scale=360:-1:flags=lanczos,palettegen", palette

        ], capture_output=True)

        

        # 2. Generar el GIF aplicando la paleta

        subprocess.run([

            "ffmpeg", "-y", "-i", video_path, "-i", palette,

            "-filter_complex", "fps=12,scale=360:-1:flags=lanczos[x];[x][1:v]paletteuse",

            out_gif

        ], capture_output=True)

        

        if os.path.exists(palette): os.remove(palette)

        

        if os.path.exists(out_gif):

             return out_gif

             

        return None

    except Exception as e:

        print(f"Error en video_to_gif: {e}")

        return None





def create_telegram_sticker(input_path, is_emoji=False):

    """

    Crea un Sticker compatible con Telegram.

    - Detecta automáticamente si es Video o Imagen usando FFprobe.

    - Video -> WebM (VP9)

    - Imagen -> WebP (Static)

    """

    import subprocess

    import os

    import json

    

    base_name = os.path.splitext(input_path)[0]

    

    # 1. Detectar tipo real con FFprobe

    is_video = False

    try:

        cmd_probe = [

            "ffprobe", "-v", "error", 

            "-select_streams", "v:0", 

            "-show_entries", "stream=codec_type,duration,nb_frames", 

            "-of", "json", 

            input_path

        ]

        out_probe = subprocess.check_output(cmd_probe).decode()

        data = json.loads(out_probe)

        stream = data.get('streams', [{}])[0]

        

        # Criterio: Si tiene duración > 0 o más de 1 frame, es video/animación

        duration = float(stream.get('duration', 0))

        nb_frames = int(stream.get('nb_frames', 0))

        

        if duration > 0.1 or nb_frames > 1:

            is_video = True

            

        # Refuerzo: Si extensión es mp4/mov/webm, forzar video

        ext = os.path.splitext(input_path)[1].lower()

        if ext in ['.mp4', '.mov', '.webm', '.gif', '.mkv']:

            is_video = True

            

    except Exception as e:

        print(f"⚠️ Error Probe: {e}. Usando extensión...")

        ext = os.path.splitext(input_path)[1].lower()

        is_video = ext in ['.mp4', '.mov', '.webm', '.gif']



    if not is_video:

        # --- MODO IMAGEN (WEBP ESTÁTICO) ---

        out_file = f"{base_name}.webp"

        try:

            cmd = [

                "ffmpeg", "-y", "-i", input_path,

                "-vf", "scale=512:512:force_original_aspect_ratio=decrease,format=rgba",

                "-c:v", "libwebp", "-lossless", "0", "-q:v", "80", 

                "-vframes", "1", # IMPORTANTE: Solo 1 frame para evitar WebP animado gigante

                "-an",

                out_file

            ]

            print(f"🖼 Creando Sticker Estático: {input_path}")

            subprocess.run(cmd, check=True)

            return out_file if os.path.exists(out_file) else None

        except Exception as e:

            print(f"❌ Error Sticker Imagen: {e}")

            return None



    else:

        # --- MODO VIDEO (WEBM VP9) ---

        out_file = f"{base_name}.webm"

        try:

            # Configuración de Escala

            scale = "100:100" if is_emoji else "512:512"

            

            # Filtro complejo para garantizar transparencia y tamaño

            if is_emoji:

                vf = f"scale={scale}:force_original_aspect_ratio=decrease,pad={scale}:(ow-iw)/2:(oh-ih)/2:color=0x00000000"

            else:

                vf = f"scale={scale}:force_original_aspect_ratio=decrease"



            # Comando FFmpeg VP9 Optimizado

            cmd = [

                "ffmpeg", "-y",

                "-i", input_path,

                "-ss", "00:00:00", "-t", "00:00:02.900",  # Máx 2.9s para asegurar <3s

                "-vf", f"{vf},fps=30,format=yuva420p", 

                "-c:v", "libvpx-vp9",

                "-b:v", "300k",        # Bajamos bitrate para asegurar <256KB

                "-minrate", "150k",

                "-maxrate", "400k",

                "-crf", "35",          # Aumentar CRF para bajar peso

                "-deadline", "realtime", "-cpu-used", "5", 

                "-row-mt", "1",

                "-an", "-map", "0:v:0", "-loop", "0",

                out_file

            ]

            

            print(f"🎥 Creando Sticker Video: {input_path}")

            subprocess.run(cmd, check=True)

            

            # Gestión de tamaño (Si pasa de 256KB, re-comprimir agresivamente)

            if os.path.exists(out_file):

                size = os.path.getsize(out_file)

                if size > 256 * 1024:

                    print(f"⚠️ Sticker grande ({size/1024:.1f}KB). Reintentando Ultra-Compress...")

                    cmd_retry = [

                        "ffmpeg", "-y", "-i", input_path, "-t", "2.9",

                        "-vf", f"{vf},fps=24,scale=trunc(iw/2)*2:trunc(ih/2)*2", # Bajar FPS

                        "-c:v", "libvpx-vp9", "-b:v", "150k", "-crf", "50",

                        "-deadline", "realtime", "-cpu-used", "8",

                        "-an", "-map", "0:v:0",

                        out_file

                    ]

                    subprocess.run(cmd_retry, check=False)

            

            return out_file if os.path.exists(out_file) else None

            

        except Exception as e:

            print(f"❌ Error Sticker Video: {e}")

            return None





# --- SAUCENAO API SERVICE ---

def search_saucenao(image_path, api_key="fcb68d6b88094c2cf65e4f69cd6f3ab3cc7a199e"):

    """

    Realiza una búsqueda inversa en SauceNAO usando el archivo local.

    Retorna una lista de resultados o None si falla.

    """

    import requests

    import json

    

    url = "https://saucenao.com/search.php"

    

    try:

        with open(image_path, 'rb') as f:

            files = {'file': f}

            params = {

                'db': 999,

                'output_type': 2,

                'numres': 3,

                'api_key': api_key,

                'testmode': 1

            }

            

            print(f"🔍 [SauceNAO] Searching for: {image_path}")

            r = requests.post(url, files=files, params=params, timeout=30)

            

            if r.status_code != 200:

                print(f"❌ SauceNAO Error Status: {r.status_code}")

                return None

                

            results = r.json()

            # Validar respuesta

            if results['header']['status'] > 0:

                print(f"❌ SauceNAO Server Error: {results['header']['message']}")

                return None

                

            return results.get('results', [])

            

    except Exception as e:

        print(f"❌ SauceNAO Exception: {e}")

        return None



def format_saucenao_results(results):

    """Formatea los resultados de SauceNAO para enviar al usuario con más detalle."""

    if not results:

        return "🤷‍♂️ **No se encontraron coincidencias.**"

        

    msg = "📁 SauceNAO resultados\n"

    

    count = 0

    for res in results:

        header = res['header']

        data = res['data']

        

        similarity = header.get('similarity', '0')

        if float(similarity) < 55.0: continue # Filtrar baja confianza

        

        count += 1

        if count > 3: break # Máximo 3 resultados

        

        # --- Extracción de Datos Específicos ---

        title = data.get('title', data.get('eng_name', data.get('jp_name', data.get('material', ''))))

        if not title and 'source' in data: title = data['source']

        

        # Line 2 components

        line2_parts = []

        if 'part' in data: line2_parts.append(f"Part: {data['part']}")

        if 'episode' in data: line2_parts.append(f"Ep: {data['episode']}")

        if 'est_time' in data: line2_parts.append(f"Time: {data['est_time']}")

        

        line2 = " | ".join(line2_parts)

        if line2: line2 = f"📁 {line2}"

        

        # --- Construcción del Mensaje ---

        msg += f"📁 Similitud: {similarity}%\n\n"

        

        if title: msg += f"📁 Título: `{title}`\n"

        if line2: msg += f"{line2}\n"

            

    if count == 0:

        return "🤷‍♂️ **SauceNAO: Sin coincidencias relevantes.**"

        

    return msg



# ... (omitted get_anilist_info) ...



# --- TRACE.MOE API SERVICE ---

def get_anilist_info(anilist_id):

    """Obtiene metadatos AVANZADOS de Anilist dado un ID."""

    import requests

    

    query = '''

    query ($id: Int) {

      Media (id: $id, type: ANIME) {

        title {

          romaji

          english

          native

        }

        synonyms

        isAdult

        genres

        format

        episodes

        duration

        startDate { year month day }

        endDate { year month day }

        studios(isMain: true) {

          nodes {

            name

          }

        }

        siteUrl

      }

    }

    '''

    variables = {'id': anilist_id}

    url = 'https://graphql.anilist.co'

    

    try:

        response = requests.post(url, json={'query': query, 'variables': variables}, timeout=10)

        if response.status_code == 200:

            return response.json().get('data', {}).get('Media', {})

    except Exception as e:

        print(f"❌ Anilist Error: {e}")

        

    return None



def search_tracemoe(image_path):

    """

    Busca en trace.moe usando el archivo local.

    """

    import requests

    

    url = "https://api.trace.moe/search?cutBorders"

    

    try:

        print(f"🔍 [Trace.moe] Searching: {image_path}")

        with open(image_path, 'rb') as f:

            files = {'image': f}

            r = requests.post(url, files=files, timeout=30)

            

            if r.status_code == 200:

                return r.json()

            elif r.status_code == 429:

                print("❌ Trace.moe Rate Limit Exceeded")

                return "limit"

            else:

                print(f"❌ Trace.moe Error: {r.status_code} - {r.text}")

                return None

                

    except Exception as e:

        print(f"❌ Trace.moe Exception: {e}")

        return None



def format_tracemoe_results(data):

    """Formatea resultados de trace.moe + anilist info EXTENDIDO."""

    if not data or isinstance(data, str) or 'result' not in data:

        return "🤷‍♂️ **Trace.moe: Sin resultados.**", None, False

        

    results = data['result']

    if not results:

        return "🤷‍♂️ **Trace.moe: Sin coincidencias.**", None, False

        

    # Filtrar y tomar el mejor

    best = results[0]

    similarity = float(best.get('similarity', 0)) * 100

    

    if similarity < 85.0: 

        return "🤷‍♂️ **Trace.moe: Sin coincidencias sólidas (<85%).**", None, False

        

    # Obtener info extra de Anilist

    anilist_id = best.get('anilist', None)

    meta = {}

    if anilist_id:

        from utils import get_anilist_info # Ensure import if needed, or rely on global

        meta = get_anilist_info(anilist_id) or {}

        

    # --- PROCESAR DATOS DE ANILIST ---

    

    # 1. Títulos

    titles = meta.get('title', {})

    title_romaji = titles.get('romaji', 'Desconocido')

    title_native = titles.get('native')

    

    # 2. Info

    episodes = meta.get('episodes', '?')

    duration = meta.get('duration', '?')

    fmt = meta.get('format', 'TV')

    

    desc_type = f"{episodes} ep. ({duration} min) {fmt} anime."

    

    start = meta.get('startDate', {})

    end = meta.get('endDate', {})

    s_date = f"{start.get('year', '?')}-{start.get('month', '?')}-{start.get('day', '?')}"

    e_date = f"{end.get('year', '?')}-{end.get('month', '?')}-{end.get('day', '?')}"

    aired = f"Airing from {s_date} to {e_date}."



    # 3. Alias

    aliases = meta.get('synonyms', [])

    alias_str = aliases[0] if aliases else "None"



    # 4. Géneros

    genres = meta.get('genres', [])

    genre_str = ", ".join(genres[:3]) if genres else "Unknown"



    # 5. Studios

    studios_node = meta.get('studios', {}).get('nodes', [])

    studios_str = "Unknown"

    if studios_node:

        studios_str = ", ".join([s['name'] for s in studios_node])



    # 6. Clip Match

    match_episode = best.get('episode', '?')

    time_pos = best.get('from', 0)

    m, s = divmod(int(time_pos), 60)

    time_str = f"{m}:{s:02d}"



    # NSFW Check

    is_adult = meta.get('isAdult', False)

    video_preview = best.get('video', '')

    

    # --- CONSTRUIR EL MENSAJE FINAL (EXACTO) ---

    msg = f"""

📁 Trace moe resultados

📁 Similitud: {similarity:.2f}%



📁 Title: `{title_romaji}`

📁 `{title_native if title_native else ''}`

📁 Info: {desc_type}

{aired}

📁 Alias: `{alias_str}`

📁 Genre: {genre_str}

📁 Studio: {studios_str}

📁 Clip Match: Episode: {match_episode} (Time: {time_str})

"""

        

    return msg, video_preview, is_adult





def get_random_pack_image(category="general"):

    """

    Selecciona una imagen aleatoria de la carpeta 'pack'.

    category: 'tetas', 'culos', 'cuerpo', 'general'.

    """

    import random

    import glob

    

    base_dir = "pack"

    if not os.path.exists(base_dir):

        try:

            os.makedirs(base_dir)

            os.makedirs(os.path.join(base_dir, "tetas"))

            os.makedirs(os.path.join(base_dir, "culos"))

            os.makedirs(os.path.join(base_dir, "cuerpo"))

        except: pass

        return None

        

    target_dir = base_dir

    if category and category != "general":

        target_dir = os.path.join(base_dir, category)

        

    files = []

    

    if category == "general":

        files.extend(glob.glob(os.path.join(base_dir, "**", "*.jpg"), recursive=True))

        files.extend(glob.glob(os.path.join(base_dir, "**", "*.png"), recursive=True))

        files.extend(glob.glob(os.path.join(base_dir, "**", "*.webp"), recursive=True))

    else:

        files.extend(glob.glob(os.path.join(target_dir, "*.jpg")))

        files.extend(glob.glob(os.path.join(target_dir, "*.png")))

        files.extend(glob.glob(os.path.join(target_dir, "*.webp")))

        

    if not files: return None

    

    return random.choice(files)






# --- WAIFU2X INTEGRATION ---
# --- WAIFU2X INTEGRATION ---
WAIFU2X_PATH_WIN = r"bin\waifu2x\waifu2x-ncnn-vulkan.exe" 
WAIFU2X_PATH_LINUX = "bin/waifu2x/waifu2x-ncnn-vulkan" # Estructura mirror en Linux

def waifu2x_upscale(input_path, scale=2, noise=2):
    """
    Ejecuta Waifu2x-ncnn-vulkan para mejorar una imagen.
    Soporta Windows (binario local) y Linux (PATH o bin local).
    """
    import subprocess
    import os
    import platform
    import shutil
    
    # 1. Determinar el binario según SO
    system = platform.system()
    waifu2x_bin = None
    
    if system == "Windows":
        if os.path.exists(WAIFU2X_PATH_WIN):
            waifu2x_bin = WAIFU2X_PATH_WIN
    else:
        # Linux: Prioridad 1 -> PATH global
        if shutil.which("waifu2x-ncnn-vulkan"):
            waifu2x_bin = "waifu2x-ncnn-vulkan"
        
        # Prioridad 2 -> Carpeta bin local (usuario lo subió ahí)
        elif os.path.exists(WAIFU2X_PATH_LINUX):
             waifu2x_bin = WAIFU2X_PATH_LINUX
             # Dar permisos de ejecución si no tiene
             try: os.chmod(waifu2x_bin, 0o755)
             except: pass
        
        # Prioridad 3 -> Carpeta bin local pero con .exe (Si lo subió tal cual de windows)
        elif os.path.exists(WAIFU2X_PATH_WIN.replace("\\", "/")):
             waifu2x_bin = WAIFU2X_PATH_WIN.replace("\\", "/")
             try: os.chmod(waifu2x_bin, 0o755) 
             except: pass

    if not waifu2x_bin:
        print(f"⚠️ Waifu2x bin not found (System: {system}). Checked PATH and {WAIFU2X_PATH_LINUX}")
        return None
        
    base, ext = os.path.splitext(input_path)
    if not ext: ext = ".png"
    
    # Waifu2x output format
    output_path = f"{base}_waifu2x{ext}"
    
    # Command Construction
    cmd = [
        waifu2x_bin,
        "-i", input_path,
        "-o", output_path,
        "-s", str(scale),
        "-n", str(noise),
        "-x" # TTA Mode
    ]
    
    print(f"✨ [Waifu2x] Upscaling ({system}): {input_path} -> {output_path}")
    
    try:
        # Run blocking
        subprocess.run(cmd, check=True)
        
        if os.path.exists(output_path):
            return output_path
        else:
            print("⚠️ Waifu2x did not produce output.")
            return None
            
    except Exception as e:
        print(f"Error in waifu2x: {e}")
        return None

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- HELPER: PAGINATION GRID ---
def generate_grid_keyboard(current_idx, total_items, prefix_sel, prefix_nav, prefix_jump, prefix_back='menu|tools', extra_rows=None):
    '''
    Genera un teclado de cuadrícula (5x2) para selección paginada.
    - current_idx: índice actual (0-based) para resaltar (opcional).
    - total_items: total de elementos.
    - prefix_sel: callback base para selección (ej: 'tiktok|sel|'). Appends index.
    - prefix_nav: callback base para nav (ej: 'tiktok|nav|'). Appends '{cur}|prev' or '{cur}|next'.
    - prefix_jump: callback para input manual (ej: 'tiktok|jump').
    - prefix_back: callback para volver.
    '''
    page_size = 10
    current_page = current_idx // page_size
    start_idx = current_page * page_size
    end_idx = min(start_idx + page_size, total_items)
    
    buttons = []
    
    # Grid 5x2
    # Row 1: 1-5
    row1 = []
    for i in range(start_idx, min(start_idx + 5, end_idx)):
        # Display is 1-based (i+1)
        # Highlight current? Maybe simply numbers.
        lbl = f'✅ {i+1}' if i == current_idx else f'{i+1}'
        row1.append(InlineKeyboardButton(lbl, callback_data=f'{prefix_sel}{i}'))
    buttons.append(row1)
    
    # Row 2: 6-10
    if end_idx > start_idx + 5:
        row2 = []
        for i in range(start_idx + 5, end_idx):
             lbl = f'✅ {i+1}' if i == current_idx else f'{i+1}'
             row2.append(InlineKeyboardButton(lbl, callback_data=f'{prefix_sel}{i}'))
        buttons.append(row2)

    # Nav Row: [< Prev] [Jump] [Next >]
    nav_row = []
    
    # Prev (If not first page)
    if start_idx > 0:
        # Jump back 10
        target = max(0, start_idx - 10)
        nav_row.append(InlineKeyboardButton('⬅️ Anterior', callback_data=f'{prefix_nav}{current_idx}|prev'))
    else:
        nav_row.append(InlineKeyboardButton('☁️ Inicio', callback_data='ignore'))
        
    # Jump Button
    nav_row.append(InlineKeyboardButton('🔢 Ir a...', callback_data=f'{prefix_jump}'))
    
    # Next (If not last page)
    if end_idx < total_items:
        # Jump forward 10
        # target = start_idx + 10 (handled by logic)
        nav_row.append(InlineKeyboardButton('Siguiente ➡️', callback_data=f'{prefix_nav}{current_idx}|next'))
    else:
        nav_row.append(InlineKeyboardButton('☁️ Fin', callback_data='ignore'))
        
    buttons.append(nav_row)
    
    # Extra Rows (Control buttons like 'Add', 'Random', 'Delete')
    if extra_rows:
        for r in extra_rows:
            buttons.append(r)
            
    # Back Row defaults
    # buttons.append([InlineKeyboardButton('🔙 Volver', callback_data=prefix_back)])
    
    return InlineKeyboardMarkup(buttons)
