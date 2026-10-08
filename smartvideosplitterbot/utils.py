import os
import asyncio
import zipfile
import subprocess
import glob
import time
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

# --- HELPER: ZIP SPLITTER ---
def create_split_zips(files, base_name, max_size=1.9 * 1024 * 1024 * 1024):
    """Agrupa archivos en ZIPs que no superen max_size."""
    archives = []
    current_batch = []
    current_size = 0
    part_num = 1
    
    for f_path in files:
        f_size = os.path.getsize(f_path)
        if current_size + f_size > max_size and current_batch:
            zip_name = f"{base_name}_part{part_num}.zip"
            with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:
                for tf in current_batch:
                    zf.write(tf, os.path.basename(tf))
            archives.append(zip_name)
            
            current_batch = []
            current_size = 0
            part_num += 1
            
        current_batch.append(f_path)
        current_size += f_size
        
    if current_batch:
        zip_name = f"{base_name}_part{part_num}.zip" if part_num > 1 else f"{base_name}.zip"
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:
            for tf in current_batch:
                zf.write(tf, os.path.basename(tf))
        archives.append(zip_name)
        
    return archives

def format_bytes(size):
    if not size or size <= 0: return "0 B"
    power = 2**10
    n = 0
    power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB'}
    while size > power and n < 3:
        size /= power
        n += 1
    return f"{size:.1f} {power_labels[n]}"

def render_bar(current, total, length=10):
    if total == 0: return "░" * length
    pct = current / total
    filled = int(length * pct)
    return "█" * filled + "░" * (length - filled)

def split_video_generic(input_path, mode, value, precise=False):
    """Divide video por: 'parts', 'min', 'sec'."""
    if not os.path.exists(input_path): return []
    try:
        cmd_dur = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", input_path
        ]
        duration = float(subprocess.check_output(cmd_dur).decode().strip())
    except Exception as e:
        print(f"Error duration: {e}")
        return []

    if duration < 1: return []

    segment_time = 0
    if mode == 'parts':
        segment_time = duration / int(value)
    elif mode == 'min':
        segment_time = float(value) * 60
    elif mode == 'sec':
        segment_time = float(value)
        
    if segment_time <= 0: return []
    
    base_dir = os.path.dirname(input_path) if input_path else "downloads"
    base_name, ext = os.path.splitext(os.path.basename(input_path)) if input_path else ("video", ".mp4")
    try:
        print(f"[DEBUG] split_video_generic join - base_dir: {base_dir}")
        output_pattern = safe_join(base_dir or "downloads", f"{base_name}_part%03d{ext}")
        
        cmd_split = ["ffmpeg", "-y", "-i", input_path]
        is_audio = ext.lower() in [".mp3", ".ogg", ".wav", ".flac", ".m4a", ".aac", ".wma", ".mka"]
        
        if is_audio:
            cmd_split.extend(["-c", "copy", "-map", "0:a"])
        else:
            if precise:
                # Modo Preciso: Re-codificar con GOP pequeño (1 keyframe por seg) para cortes exactos
                cmd_split.extend(["-c:v", "libx264", "-preset", "superfast", "-crf", "22", "-g", "24", "-sc_threshold", "0", "-c:a", "aac"])
            else:
                # Modo Rápido (OFF): Siempre copia directa, sin importar la duración
                cmd_split.extend(["-c", "copy"])
            cmd_split.extend(["-map", "0:v", "-map", "0:a?"])

        cmd_split.extend(["-f", "segment", "-segment_time", str(segment_time), "-reset_timestamps", "1", output_pattern])
        
        print(f"[FFMPEG SPLIT] Executing: {' '.join(cmd_split)}")
        subprocess.run(cmd_split, check=True) 
        
        print(f"[DEBUG] glob join - base_dir: {base_dir}")
        base_folder = base_dir or "downloads"
        parts = []
        if os.path.exists(base_folder):
            for f in sorted(os.listdir(base_folder)):
                if f.startswith(f"{base_name}_part") and f.endswith(ext):
                    parts.append(os.path.join(base_folder, f))
        return parts
    except Exception as e:
        print(f"❌ ERROR EN split_video_generic:")
        traceback.print_exc()
        return []

def cut_video_range(input_path, start, end, precise=False):
    """Corta un rango específico."""
    if not os.path.exists(input_path): return None
    import uuid
    base_dir = os.path.dirname(input_path) if input_path else "downloads"
    base_name, ext = os.path.splitext(os.path.basename(input_path)) if input_path else ("video", ".mp4")
    print(f"[DEBUG] cut_video_range join - base_dir: {base_dir}, base_name: {base_name}")
    out_path = safe_join(base_dir or "downloads", f"{base_name}_cut_{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}")
    
    print(f"[DEBUG] cut_video_range: start={start}, end={end}, precise={precise}")
    cmd = ["ffmpeg", "-y", "-ss", str(start), "-to", str(end), "-i", input_path]
    is_audio = ext.lower() in [".mp3", ".ogg", ".wav", ".flac", ".m4a", ".aac", ".wma", ".mka"]
    
    if is_audio:
        cmd.extend(["-c", "copy", "-map", "0:a", out_path])
    else:
        if precise:
            cmd.extend(["-c:v", "libx264", "-preset", "superfast", "-crf", "22", "-c:a", "aac"])
        else:
            cmd.extend(["-c", "copy"])
        cmd.extend(["-map", "0:v", "-map", "0:a?", out_path])
        

    print(f"[FFMPEG CUT] Executing: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        if os.path.exists(out_path): return out_path
    except: pass
    return None

def extract_all_audios(input_path, audio_count):
    """Extrae todas las pistas de audio como archivos independientes."""
    if not os.path.exists(input_path) or audio_count <= 0: return []
    
    base_dir = os.path.dirname(input_path) if input_path else "downloads"
    base_name, _ = os.path.splitext(os.path.basename(input_path)) if input_path else ("audio", "")
    
    extracted_files = []
    for i in range(audio_count):
        # Intentaremos extraer en AAC por ser compatible, o MP3 como fallback
        print(f"[DEBUG] extract_all_audios join - base_dir: {base_dir}, base_name: {base_name}")
        out_audio = safe_join(base_dir or "downloads", f"{base_name}_audio_{i+1}.mp3")
        # Comando: mapear pista de audio i, convertir a mp3 320k
        cmd = ["ffmpeg", "-y", "-i", input_path, "-map", f"0:a:{i}", "-c:a", "libmp3lame", "-q:a", "2", out_audio]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(out_audio):
                extracted_files.append(out_audio)
        except:
            pass
    return extracted_files
