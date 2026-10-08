import os
import json
import asyncio
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# Directorio base y configuración
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_CACHE_FILE = os.path.join(BASE_DIR, "videos_cache.json")
FIREBASE_KEY_PATH = os.path.join(BASE_DIR, "firebase_key.json")

# Inicializar Firebase Firestore (DESACTIVADO POR EL USUARIO PARA AHORRAR CUOTA)
db_firestore = None
# if os.path.exists(FIREBASE_KEY_PATH):
#     try:
#         cred = credentials.Certificate(FIREBASE_KEY_PATH)
#         if not firebase_admin._apps:
#             firebase_admin.initialize_app(cred)
#         db_firestore = firestore.client()
#         print("[DB] Firebase Firestore inicializado con éxito usando firebase_key.json.")
#     except Exception as e:
#         print(f"[DB Error] No se pudo inicializar Firebase Firestore: {e}")

class DB:
    _active_channels_cache = None
    _active_channels_cache_time = 0

    @staticmethod
    def is_firebase():
        return db_firestore is not None

    @staticmethod
    async def get_all_data():
        if DB.is_firebase():
            try:
                loop = asyncio.get_event_loop()
                def run():
                    docs = db_firestore.collection("channels").stream()
                    channels = {}
                    for doc in docs:
                        channels[doc.id] = doc.to_dict()
                    return {"channels": channels}
                return await loop.run_in_executor(None, run)
            except Exception as e:
                print(f"[Firebase Error] No se pudieron obtener todos los datos de Firestore: {e}")
                return {"channels": {}}
        else:
            if not os.path.exists(LOCAL_CACHE_FILE):
                return {"channels": {}}
            try:
                with open(LOCAL_CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[DB Error] No se pudo leer {LOCAL_CACHE_FILE}: {e}")
                return {"channels": {}}

    @staticmethod
    async def get_channel_data(chat_id: str):
        chat_id = str(chat_id)
        if DB.is_firebase():
            try:
                loop = asyncio.get_event_loop()
                def run():
                    doc_ref = db_firestore.collection("channels").document(chat_id)
                    doc = doc_ref.get()
                    if doc.exists:
                        return doc.to_dict()
                    return None
                return await loop.run_in_executor(None, run)
            except Exception as e:
                print(f"[Firebase Error] Error leyendo canal {chat_id} en Firestore: {e}")
                return None
        else:
            data = await DB.get_all_data()
            return data.get("channels", {}).get(chat_id)

    @staticmethod
    def _merge_custom_fields(old_video: dict, new_video: dict):
        if not old_video or not new_video:
            return
        custom_keys = ["duplicate", "is_duplicate", "dup_order", "custom_title", "actress", "custom_thumb_time", "custom_thumb_url"]
        for key in custom_keys:
            if key in old_video and key not in new_video:
                new_video[key] = old_video[key]

    @staticmethod
    async def save_channel_data(chat_id: str, channel_data: dict, preserve_custom_metadata: bool = True):
        chat_id = str(chat_id)
        # Invalidar caché para que se actualice la próxima vez
        DB._active_channels_cache = None
        
        if preserve_custom_metadata and isinstance(channel_data, dict) and "videos" in channel_data:
            try:
                old_data = await DB.get_channel_data(chat_id)
                if old_data and isinstance(old_data, dict) and "videos" in old_data:
                    old_map = {v.get("id"): v for v in old_data["videos"] if isinstance(v, dict) and "id" in v}
                    for new_v in channel_data["videos"]:
                        if isinstance(new_v, dict) and "id" in new_v:
                            old_v = old_map.get(new_v["id"])
                            if old_v:
                                DB._merge_custom_fields(old_v, new_v)
            except Exception as e:
                print(f"[DB Warning] No se pudo fusionar metadatos al guardar canal {chat_id}: {e}")

        if DB.is_firebase():
            try:
                loop = asyncio.get_event_loop()
                def run():
                    doc_ref = db_firestore.collection("channels").document(chat_id)
                    doc_ref.set(channel_data)
                    return True
                return await loop.run_in_executor(None, run)
            except Exception as e:
                print(f"[Firebase Error] Error guardando canal {chat_id} en Firestore: {e}")
                return False
        else:
            data = await DB.get_all_data()
            if "channels" not in data:
                data["channels"] = {}
            data["channels"][chat_id] = channel_data
            try:
                loop = asyncio.get_event_loop()
                def run_local():
                    with open(LOCAL_CACHE_FILE, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                    return True
                return await loop.run_in_executor(None, run_local)
            except Exception as e:
                print(f"[DB Error] Error guardando cache local: {e}")
                return False

    @staticmethod
    async def add_video(chat_id: str, video_data: dict, channel_title="Canal Privado", username=None):
        chat_id = str(chat_id)
        ch_data = await DB.get_channel_data(chat_id)
        
        if not ch_data:
            ch_data = {
                "channel_title": channel_title,
                "username": username,
                "videos": []
            }
        else:
            ch_data["channel_title"] = channel_title
            ch_data["username"] = username
            if "videos" not in ch_data:
                ch_data["videos"] = []
                
        # Evitar duplicados del ID de mensaje y fusionar metadatos previa si existía
        video_id = video_data["id"]
        existing_video = next((v for v in ch_data["videos"] if isinstance(v, dict) and v.get("id") == video_id), None)
        if existing_video:
            DB._merge_custom_fields(existing_video, video_data)

        videos = [v for v in ch_data["videos"] if v.get("id") != video_id]
        videos.append(video_data)
        
        # Ordenar cronológicamente descendente
        ch_data["videos"] = sorted(videos, key=lambda x: x["id"], reverse=True)
        
        return await DB.save_channel_data(chat_id, ch_data, preserve_custom_metadata=False)

    @staticmethod
    async def remove_videos(chat_id: str, video_ids: list):
        chat_id = str(chat_id)
        ch_data = await DB.get_channel_data(chat_id)
        if not ch_data or "videos" not in ch_data:
            return False
            
        videos_antes = len(ch_data["videos"])
        ch_data["videos"] = [v for v in ch_data["videos"] if v["id"] not in video_ids]
        videos_despues = len(ch_data["videos"])
        
        if videos_antes != videos_despues:
            return await DB.save_channel_data(chat_id, ch_data)
        return False

    @staticmethod
    async def get_active_channels():
        import time
        current_time = time.time()
        # Usar caché si tiene menos de 10 minutos (600 segundos)
        if DB._active_channels_cache is not None and (current_time - DB._active_channels_cache_time < 600):
            return DB._active_channels_cache

        if DB.is_firebase():
            try:
                loop = asyncio.get_event_loop()
                def run():
                    docs = db_firestore.collection("channels").list_documents()
                    return [doc.id for doc in docs]
                result = await loop.run_in_executor(None, run)
                DB._active_channels_cache = result
                DB._active_channels_cache_time = current_time
                return result
            except Exception as e:
                print(f"[Firebase Error] Error listando canales de Firestore: {e}")
                return DB._active_channels_cache or []
        else:
            data = await DB.get_all_data()
            result = list(data.get("channels", {}).keys())
            DB._active_channels_cache = result
            DB._active_channels_cache_time = current_time
            return result

    @staticmethod
    async def get_backup_msg_id(media_key: str):
        if DB.is_firebase():
            try:
                loop = asyncio.get_event_loop()
                def run():
                    doc_ref = db_firestore.collection("backup_media").document(media_key)
                    doc = doc_ref.get()
                    if doc.exists:
                        return doc.to_dict().get("msg_id")
                    return None
                return await loop.run_in_executor(None, run)
            except Exception:
                return None
        else:
            backup_path = os.path.join(BASE_DIR, "backup_cache.json")
            if not os.path.exists(backup_path):
                return None
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get(media_key)
            except Exception:
                return None

    @staticmethod
    async def save_backup_msg_id(media_key: str, msg_id: int):
        if DB.is_firebase():
            try:
                loop = asyncio.get_event_loop()
                def run():
                    doc_ref = db_firestore.collection("backup_media").document(media_key)
                    doc_ref.set({"msg_id": msg_id})
                await loop.run_in_executor(None, run)
            except Exception as e:
                print(f"[DB Error] Fallo al guardar backup reference: {e}")
        else:
            backup_path = os.path.join(BASE_DIR, "backup_cache.json")
            data = {}
            if os.path.exists(backup_path):
                try:
                    with open(backup_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    pass
            data[media_key] = msg_id
            try:
                loop = asyncio.get_event_loop()
                def run_local():
                    with open(backup_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4)
                await loop.run_in_executor(None, run_local)
            except Exception as e:
                print(f"[DB Error] Fallo al guardar backup cache local: {e}")
