import os
import json

# Ruta al archivo JSON en el directorio raíz del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(BASE_DIR, "registered_channels.json")

# Nombres por defecto usados en las búsquedas
DEFAULT_NAMES = {
    "twisted_short": "Twisted Short cuckold bbc",
    "hentaila_vip": "Hentaila VIP",
    "jav_premium": "JAV PREMIUM",
    "jav_regular": "JAV REGULAR"
}

def load_channels():
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando registered_channels.json: {e}")
    return {}

def save_channels(data):
    try:
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando registered_channels.json: {e}")

def get_registered_id(key):
    data = load_channels()
    if key in data:
        return data[key].get("id")
    return None

def get_registered_name(key):
    data = load_channels()
    if key in data:
        return data[key].get("name", DEFAULT_NAMES.get(key, ""))
    return DEFAULT_NAMES.get(key, "")

def matches_channel(chat_id, chat_title, key):
    # 1. Comprobar coincidencia por ID
    reg_id = get_registered_id(key)
    if reg_id is not None:
        try:
            normalized_chat_id = int(str(chat_id).replace("-100", ""))
            normalized_reg_id = int(str(reg_id).replace("-100", ""))
            if normalized_chat_id == normalized_reg_id:
                return True
        except ValueError:
            pass

    # 2. Comprobar coincidencia por nombre registrado
    reg_name = get_registered_name(key)
    if chat_title and reg_name:
        if reg_name.lower() in chat_title.lower():
            return True
            
    # 3. Fallback al nombre por defecto
    default_name = DEFAULT_NAMES.get(key, "")
    if chat_title and default_name:
        if default_name.lower() in chat_title.lower():
            return True

    return False

def is_jav_channel(chat_id, chat_title):
    chat_title_lower = (chat_title or "").lower()
    return (
        matches_channel(chat_id, chat_title, "jav_premium") or
        matches_channel(chat_id, chat_title, "jav_regular") or
        "jav" in chat_title_lower or
        "yuria" in chat_title_lower or
        "yoshine" in chat_title_lower or
        "prime" in chat_title_lower
    )
