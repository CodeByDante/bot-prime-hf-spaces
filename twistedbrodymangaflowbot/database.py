import json
import os
from config import DB_FILE, DATA_DIR

DB_CACHE = os.path.join(DATA_DIR, "manga_cache.json")

# --- VARIABLES GLOBALES (NO BORRAR) ---
url_storage = {}    
user_config = {}    
active_downloads = {} # {chat_id: {msg_id: future/task}}
task_progress = {}    # {chat_id: {msg_id: {percent, speed, status, name, url}}}

# --- FUNCIONES ---

def get_config(chat_id):
    if chat_id not in user_config:
        user_config[chat_id] = {
            'lang': 'es', 
            'manga_doc_mode': False,
            'manga_group_mode': True,
            'manga_hd_mode': True
        }
    return user_config[chat_id]

def add_active(chat_id, msg_id, task=None, pid=None):
    if chat_id not in active_downloads:
        active_downloads[chat_id] = {}
    active_downloads[chat_id][msg_id] = {'task': task, 'pid': pid}

def remove_active(chat_id, msg_id):
    if chat_id in active_downloads and msg_id in active_downloads[chat_id]:
        del active_downloads[chat_id][msg_id]
        if not active_downloads[chat_id]:
            del active_downloads[chat_id]
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
            if isinstance(info, dict):
                task = info.get('task')
                pid = info.get('pid')
            else:
                task = info
                pid = None
            
            url = "Enlace desconocido"
            if chat_id in task_progress and mid in task_progress[chat_id]:
                url = task_progress[chat_id][mid].get('url', 'Enlace desconocido')
            
            cancelled_items.append({'url': url, 'msg_id': mid})

            if task and not task.done():
                task.cancel()
            
            if pid:
                try:
                    import signal
                    os.kill(pid, signal.SIGTERM)
                except:
                    pass

        active_downloads.pop(chat_id, None)
        task_progress.pop(chat_id, None) 
        
    return cancelled_items