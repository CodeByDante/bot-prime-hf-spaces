import json
import os
from config import DB_FILE, DATA_DIR

DB_CACHE = os.path.join(DATA_DIR, "manga_cache.json")
DB_CACHE = os.path.join(DATA_DIR, "manga_cache.json")
DB_TAGS = os.path.join(DATA_DIR, "hashtags.json")
DB_VIRAL = os.path.join(DATA_DIR, "viral_shorts.json")

# --- VARIABLES GLOBALES (NO BORRAR) ---
url_storage = {}    # <-- Esta es la variable que te faltaba
user_config = {}    
downloads_db = {}   
downloads_db = {}   
hashtag_db = {}     # <-- Base de datos de hashtags
viral_music_db = [] # <-- Base de datos de Shorts/Music Viral (Lista de Dicts)
active_downloads = {} # {chat_id: {msg_id: future/task}}
user_cooldowns = {}   # {chat_id: timestamp}
task_progress = {}    # {chat_id: {msg_id: {percent, speed, status, name, url}}}

# --- FUNCIONES ---

def cargar_db():
    global downloads_db
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                downloads_db.update(json.load(f))
        except:
            downloads_db = {}

def guardar_db():
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(downloads_db, f, indent=4)
    except:
        pass

def load_tags():
    global hashtag_db
    if os.path.exists(DB_TAGS):
        try:
            with open(DB_TAGS, 'r', encoding='utf-8') as f:
                hashtag_db.update(json.load(f))
        except:
            hashtag_db = {}

def save_tags():
    try:
        with open(DB_TAGS, 'w', encoding='utf-8') as f:
            json.dump(hashtag_db, f, indent=4, ensure_ascii=False)
    except:
        pass

def load_viral():
    global viral_music_db
    if os.path.exists(DB_VIRAL):
        try:
            with open(DB_VIRAL, 'r', encoding='utf-8') as f:
                viral_music_db.extend(json.load(f))
        except:
            viral_music_db = []

def save_viral():
    try:
        with open(DB_VIRAL, 'w', encoding='utf-8') as f:
            json.dump(viral_music_db, f, indent=4, ensure_ascii=False)
    except:
        pass

def get_config(chat_id):
    if chat_id not in user_config:
        user_config[chat_id] = {
            'lang': 'es', 
            'fmt': 'mp4',
            'q_fixed': None, 
            'q_auto': None, 
            'meta': True,
            'fast_enabled': True,
            'html_mode': False,
            'doc_mode': False,
            'replay_enabled': False, # <--- Nuevo modo replay
            'party_mode': False,
            'join_party_mode': False,
            'extract_mode': False,
            'ai_mode': False, # Modo Party
            'auto_join_party': False,
            'auto_extract': False,
            'gif_mode': False,
            'sticker_mode': False,
            'join_party_zip': False,
            'extract_party_zip': True,
            'collage_mode': False,      # <-- Nuevo Modo Collage
            'collage_auto_mode': False, # <-- DEPRECATED (Migration might be needed or just ignore)
            'collage_grid': '3x3',      # '3x3', '2x2', '2x1'
            'collage_auto_3x3': False,
            'collage_auto_2x2': False,
            'collage_auto_2x1': False,
            'sub_mode': False,          # Nuevo modo subtitulado (Manual/One-Shot)
            'sub_auto_mode': False,     # Nuevo modo subtitulado (Auto/Persistent)
            'viral_mode': False,        # <-- Modo Short Virales Music (Recoleccion)
            'smart_cut_mode': False,    # <-- Smart Cut (Detector Intro)
            'collage_type': 'png',      # 'png' o 'thumb'
            'bot_link_mode': False,     # <-- Modo Enlace Directo (Servidor Local)
            'txt_mode': False,          # <-- Modo TXT (Descargas desde archivo)
            'max_downloads': 'default',
        }

    return user_config[chat_id]

# --- LISTA DE MODOS PARA EXCLUSIVIDAD ---
ALL_MODES_KEYS = [
    'party_mode', 'join_party_mode', 'extract_mode', 'gif_mode', 
    'sticker_mode', 'saucenao_mode', 'mp3_mode', 'cut_init_mode', 
    'cut_auto_mode', 'auto_party', 'resize_mode', 'resize_auto_mode', 
    'thumb_mode', 'convert_qh_mode', 'convert_h264_mode', 
    'smart_cut_mode', 'collage_mode', 'sub_mode', 'sub_auto_mode', 
    'viral_mode', 'research_mode', 'tagger_mode', 'translate_manga_mode',
    'renviado_directo', 'renviado_agrupado',
    'auto_join_party', 'auto_extract', 'smart_cut_auto_mode',
    'waifux2_mode', 'video_mixer_mode', 'tiktok_fast_mode', 'fusion_mode',
    'parallel_thumb_mode', 'bot_link_mode', 'fusion_auto_mode',
    'txt_mode'
]

ALL_ZIP_KEYS = [
    'party_zip', 'join_party_zip', 'extract_party_zip', 'join_party_zip'
]

# Friendly Names Mapping
MODE_NAMES = {
    'party_mode': 'Modo Party',
    'join_party_mode': 'Modo Unir Party', 
    'extract_mode': 'Modo Extractor',
    'gif_mode': 'Modo GIF',
    'sticker_mode': 'Modo Sticker',
    'saucenao_mode': 'Modo SauceNAO',
    'mp3_mode': 'Modo Extractor MP3',
    'cut_init_mode': 'Modo Corte Inicial',
    'cut_auto_mode': 'Modo Auto Corte',
    'auto_party': 'Auto Party',
    'resize_mode': 'Modo Dimensionador',
    'resize_auto_mode': 'Auto Dimensionador',
    'thumb_mode': 'Modo Miniatura',
    'convert_qh_mode': 'Convertidor QH',
    'convert_h264_mode': 'Convertidor H.264',
    'smart_cut_mode': 'Smart Cut',
    'collage_mode': 'Modo Collage',
    'sub_mode': 'Modo Subtitulado',
    'sub_auto_mode': 'Auto Subtitulado',
    'viral_mode': 'Modo Virales',
    'research_mode': 'Investigación Profunda',
    'tagger_mode': 'Etiquetadora',
    'translate_manga_mode': 'Traductor Manga',
    'custom_thumb_mode': 'Miniatura Personalizada',
    'renviado_directo': 'Reenviado Directo',
    'renviado_agrupado': 'Reenviado Agrupado',
    'auto_join_party': 'Auto Unir Party',
    'auto_extract': 'Auto Extractor',
    'smart_cut_auto_mode': 'Auto Smart Cut',
    'waifux2_mode': 'Modo Waifu2x',
    'tiktok_fast_mode': 'Tiktok Fast',
    'fusion_mode': 'Modo Fusión',
    'parallel_thumb_mode': 'Miniatura Personalizada',
    'bot_link_mode': 'Enlace Directo',
    'txt_mode': 'Modo TXT'
}

async def set_exclusive_mode(chat_id, target_mode=None, is_toggle=False):
    """
    Activa un modo y desactiva TODOS los demas.
    Retorna: (new_state, disabled_mode_name)
    disabled_mode_name es el nombre legible del modo que se apagó (si hubo uno).
    """
    conf = get_config(chat_id)
    
    # 1. Identificar qué modo estaba activo antes de limpiar (para el mensaje)
    disabled_name = None
    for k in ALL_MODES_KEYS:
        if conf.get(k, False):
            # Ignoramos si es el mismo que vamos a togglear (eso no es "conflicto", es toggle)
            if k != target_mode:
                disabled_name = MODE_NAMES.get(k, k)
                break # Asumimos solo uno activo por las reglas previas
    
    # 2. Determinar nuevo estado deseado
    new_state = True
    if target_mode:
        if is_toggle:
            new_state = not conf.get(target_mode, False)
        else:
            new_state = True
            
    # 3. Limpiar TODO siempre (Regla de Oro)
    # Incluso si apagamos (new_state False), limpiamos para asegurar consistencia
    for k in ALL_MODES_KEYS:
        conf[k] = False
    # Reset Zips (Clean Slate Rule)
    for k in ALL_ZIP_KEYS:
        conf[k] = False
            
    # 4. Aplicar nuevo estado SOLO si es True
    if target_mode and new_state:
        conf[target_mode] = True
        
    # 5. Guardar
    from firebase_service import save_user_config_fb
    await save_user_config_fb(chat_id, conf)
    
    return new_state, disabled_name

def can_download(chat_id, max_concurrent=3, cooldown_sec=2):
    # Restricciones deshabilitadas a petición del usuario (Modo Ilimitado)
    return True, None

def add_active(chat_id, msg_id, task=None, pid=None):
    if chat_id not in active_downloads:
        active_downloads[chat_id] = {}
    # Guardamos diccionario con task y pid opcional
    active_downloads[chat_id][msg_id] = {'task': task, 'pid': pid}

def remove_active(chat_id, msg_id):
    if chat_id in active_downloads and msg_id in active_downloads[chat_id]:
        del active_downloads[chat_id][msg_id]
        if not active_downloads[chat_id]:
            del active_downloads[chat_id]
    # También limpiar progreso
    remove_progress(chat_id, msg_id)

# --- FUNCIONES DE PROGRESO (TRACKING EN VIVO) ---

def update_progress(chat_id, msg_id, percent=None, speed=None, status=None, name=None, url=None):
    if chat_id not in task_progress:
        task_progress[chat_id] = {}
    if msg_id not in task_progress[chat_id]:
        task_progress[chat_id][msg_id] = {'percent': 0, 'speed': 'N/A', 'status': 'Esperando', 'name': 'Archivo', 'url': 'N/A'}
    
    if percent is not None: task_progress[chat_id][msg_id]['percent'] = percent
    if speed is not None: task_progress[chat_id][msg_id]['speed'] = speed
    if status is not None: task_progress[chat_id][msg_id]['status'] = status
    if name is not None: task_progress[chat_id][msg_id]['name'] = name
    if url is not None: task_progress[chat_id][msg_id]['url'] = url

def get_all_progress():
    return task_progress

def remove_progress(chat_id, msg_id):
    if chat_id in task_progress and msg_id in task_progress[chat_id]:
        del task_progress[chat_id][msg_id]
        if not task_progress[chat_id]:
            del task_progress[chat_id]

async def cancel_all(chat_id):
    cancelled_items = []
    if chat_id in active_downloads:
        tasks_map = active_downloads[chat_id]
        
        for mid, info in tasks_map.items():
            # Soportar formato antiguo (solo task) o nuevo (dict)
            if isinstance(info, dict):
                task = info.get('task')
                pid = info.get('pid')
            else:
                task = info
                pid = None
            
            # --- COLLECT INFO FOR REPORT ---
            # Try to get URL/Name from task_progress
            url = "Enlace desconocido"
            if chat_id in task_progress and mid in task_progress[chat_id]:
                url = task_progress[chat_id][mid].get('url', 'Enlace desconocido')
            
            cancelled_items.append({'url': url, 'msg_id': mid})

            # 1. Cancelar Task de Python
            if task and not task.done():
                task.cancel()
            
            # 2. Matar proceso del sistema (FFmpeg / Aria2 / 7z)
            if pid:
                try:
                    import signal
                    # En Windows, os.kill con SIGTERM suele funcionar, o taskkill forzado
                    os.kill(pid, signal.SIGTERM)
                    print(f"🔪 Process Killed: PID {pid}")
                except Exception as e:
                    print(f"⚠️ Kill Error {pid}: {e}")
                    # Intento Force Windows
                    try:
                        import subprocess
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except: pass

        active_downloads.pop(chat_id, None)
        # Clean progress entirely for this chat
        task_progress.pop(chat_id, None) 
        
    return cancelled_items

# Cargar base de datos al iniciar
cargar_db()
load_tags()