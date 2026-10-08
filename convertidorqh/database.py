import os

# --- VARIABLES GLOBALES MINIMAS ---
url_storage = {}
task_progress = {}

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

def remove_progress(chat_id, msg_id):
    if chat_id in task_progress and msg_id in task_progress[chat_id]:
        del task_progress[chat_id][msg_id]
        if not task_progress[chat_id]:
            del task_progress[chat_id]

# Mocks para evitar errores en otros archivos si se importan
def get_config(chat_id):
    return {'convert_qh_mode': True}

async def save_user_config_fb(chat_id, config):
    pass