import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import asyncio

# Variable global para el cliente de Firestore
db = None

def init_firebase():
    global db
    if db is not None:
        return db

    try:
        # 1. Intentar cargar desde variable de entorno (JSON RAW)
        firebase_json = os.environ.get("FIREBASE_JSON")
        
        # 2. Si no es JSON raw, intentar ruta de archivo
        if not firebase_json:
            cred_path = os.environ.get("FIREBASE_CREDENTIALS", "firebase_credentials.json")
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
            else:
                print("⚠️ [Firebase] No se encontraron credenciales (FIREBASE_JSON ni archivo).")
                return None
        else:
            # Parsear el JSON del string
            try:
                cred_dict = json.loads(firebase_json)
                cred = credentials.Certificate(cred_dict)
            except Exception as e:
                print(f"❌ [Firebase] Error parseando FIREBASE_JSON: {e}")
                return None

        # Inicializar App
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        print("🔥 [Firebase] Conectado exitosamente a Firestore.")
        return db

    except Exception as e:
        print(f"❌ [Firebase] Error inicializando: {e}")
        return None

# Inicializar al importar (o llamar explícitamente en main)
init_firebase()

from config import BOT_TOKEN

# Segregar cache por Bot ID para evitar conflictos al cambiar de bot
BOT_ID = BOT_TOKEN.split(":")[0] if ":" in BOT_TOKEN else "global"
CACHE_COLLECTION = f"media_cache_{BOT_ID}"

async def get_cached_file(video_id, quality):
    """
    Busca en la colección del bot actual si existe el file_id.
    Retorna el file_id o None.
    """
    if not db: return None

    try:
        # Usamos el video_id como ID del documento para búsqueda rápida O(1)
        doc_ref = db.collection(CACHE_COLLECTION).document(str(video_id))
        
        loop = asyncio.get_running_loop()
        # FIX: Añadir timeout de 5s para evitar hanging si Firebase falla
        try:
            doc = await asyncio.wait_for(loop.run_in_executor(None, doc_ref.get), timeout=5.0)
        except asyncio.TimeoutError:
            print(f"⚠️ [Firebase] Cache Read Timeout ({video_id}) - Saltando cache.")
            return None
        
        if doc.exists:
            data = doc.to_dict()
            # data estructura: {'mp3': 'file_id_1', '720': 'file_id_2', ...}
            return data.get(quality)
        return None
    except Exception as e:
        print(f"⚠️ [Firebase] Error leyendo cache: {e}")
        return None

async def get_cached_data(video_id):
    """
    Retorna el documento completo del cache (incluyendo meta y todos los formatos).
    """
    if not db: return None
    try:
        doc_ref = db.collection(CACHE_COLLECTION).document(str(video_id))
        loop = asyncio.get_running_loop()
        doc = await loop.run_in_executor(None, doc_ref.get)
        
        if doc.exists: return doc.to_dict()
    except Exception as e:
        print(f"⚠️ [Firebase] Error leyendo data cache: {e}")
    return None

async def save_cached_file(video_id, quality, file_id, meta=None):
    """
    Guarda o actualiza el file_id para una calidad dada.
    """
    if not db: return
    
    try:
        doc_ref = db.collection(CACHE_COLLECTION).document(str(video_id))
        
        # Usamos set con merge=True para no borrar otras calidades
        update_data = {
            quality: file_id,
            'last_updated': firestore.SERVER_TIMESTAMP
        }
        
        if meta:
            update_data['meta'] = meta # Título, duración, etc si queremos guardar info extra
            
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: doc_ref.set(update_data, merge=True))
        
        print(f"🔥 [Firebase] Cache guardado: {video_id} [{quality}]")
    except Exception as e:
        print(f"❌ [Firebase] Error guardando cache: {e}")

# --- STRICT CACHE LOGIC (URL + Quality + DocMode) ---
import hashlib

def _compute_variant_key(url, quality, is_doc):
    """Genera un hash único basado en los parámetros estrictos."""
    
    # Eporner Direct Link Normalization:
    # URL style: https://www.eporner.com/dload/VIDEO_ID/QUALITY/TOKEN-filename.mp4
    # We want to key ONLY by VIDEO_ID + QUALITY to allow cache hits even if token changes.
    if "eporner.com/dload/" in url:
        try:
            # Extract ID usually after /dload/
            parts = url.split('/dload/')
            if len(parts) > 1:
                # Part 1 is video_id: 2pBe2ZZDqtG
                vid_id_clean = parts[1].split('/')[0]
                # Use this clean ID as the 'url' for the key
                url = f"eporner_{vid_id_clean}" 
        except: pass

    raw = f"{url}|{quality}|{str(is_doc).lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()

async def get_cached_file_strict(video_id, url, quality, is_doc):
    """
    Busca una variante exacta en el documento del video.
    """
    if not db: return None
    try:
        doc_ref = db.collection(CACHE_COLLECTION).document(str(video_id))
        loop = asyncio.get_running_loop()
        try:
            doc = await asyncio.wait_for(loop.run_in_executor(None, doc_ref.get), timeout=5.0)
        except asyncio.TimeoutError:
            return None
        
        if doc.exists:
            data = doc.to_dict()
            variants = data.get('variants', {})
            v_key = _compute_variant_key(url, quality, is_doc)
            
            # DEBUG
            print(f"🔍 [Firebase Debug] Key: {v_key} | Variants: {list(variants.keys())}")
            
            variant = variants.get(v_key)
            if variant:
                print(f"✨ [Firebase] Cache Estricto ENCONTRADO: {video_id}")
                return variant.get('file_id')
                
        return None
    except Exception as e:
        print(f"⚠️ [Firebase] Error leyendo cache estricto: {e}")
        return None

async def save_cached_file_strict(video_id, url, quality, is_doc, file_id, meta=None):
    """
    Guarda una variante estricta en el documento.
    """
    if not db: return
    try:
        doc_ref = db.collection(CACHE_COLLECTION).document(str(video_id))
        v_key = _compute_variant_key(url, quality, is_doc)
        
        variant_data = {
            'file_id': file_id,
            'url': url,
            'quality': quality,
            'is_doc': is_doc,
            'saved_at': firestore.SERVER_TIMESTAMP
        }
        
        # Validar meta
        if meta and isinstance(meta, dict):
            # Limpiar meta para evitar recursión o datos corruptos
            safe_meta = {k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))}
            variant_data['meta'] = safe_meta

        # Update map inside map: {'variants': {hash: {...}}}
        loop = asyncio.get_running_loop()
        
        # 1. Leer data actual para no sobreescribir otras variantes si set(merge=True) no es suficiente para deep merges de maps
        # Firestore merge de mapas reemplaza todo el mapa si no usas notación de puntos.
        # FIX: Usar diccionario anidado para set(merge=True) en Python para asegurar merge correcto
        
        update_payload = {
            'variants': {
                v_key: variant_data
            },
            'last_updated': firestore.SERVER_TIMESTAMP
        }
        
        if meta:
             update_payload['global_meta'] = meta # Meta general (ej titulo) solo lo último

        await loop.run_in_executor(None, lambda: doc_ref.set(update_payload, merge=True))
        
        print(f"🔥 [Firebase] Cache Estricto Guardado: {video_id} [Q:{quality} D:{is_doc}]")
    except Exception as e:
        print(f"❌ [Firebase] Error guardando cache estricto: {e}")

async def delete_cached_file(video_id):
    """
    Elimina un archivo del cache (útil si el link expira o es inválido).
    """
    if not db: return
    try:
        doc_ref = db.collection(CACHE_COLLECTION).document(str(video_id))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, doc_ref.delete)
        print(f"🗑 [Firebase] Cache eliminado: {video_id}")
    except Exception as e:
        print(f"⚠️ [Firebase] Error eliminando cache: {e}")

async def get_bot_config():
    """
    Obtiene la configuración global del bot (ej: canal de backup).
    Retorna un dict con las keys.
    """
    if not db: return {}
    try:
        doc_ref = db.collection('bot_settings').document('global_config')
        loop = asyncio.get_running_loop()
        doc = await loop.run_in_executor(None, doc_ref.get)
        
        if doc.exists:
            return doc.to_dict()
        return {}
    except Exception as e:
        print(f"⚠️ [Firebase] Error leyendo config global: {e}")
        return {}

async def save_bot_config(key, value):
    """
    Guarda una key especifica en la configuración global.
    """
    if not db: return False
    try:
        doc_ref = db.collection('bot_settings').document('global_config')
        
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: doc_ref.set({key: value}, merge=True))
        
        print(f"🔥 [Firebase] Config guardada: {key} = {value}")
        return True
    except Exception as e:
        print(f"❌ [Firebase] Error guardando config global: {e}")
        return False

async def load_all_user_configs():
    """Carga todas las configs de usuarios desde Firestore."""
    if not db: return {}
    try:
        # Ejecutar en thread pool para no bloquear
        loop = asyncio.get_running_loop()
        docs = await loop.run_in_executor(None, lambda: db.collection('user_configs').stream())
        
        # Stream devuelve un generador, iterarlo puede bloquear si son muchos,
        # pero es necesario para poblar la RAM inicial.
        data = {}
        for doc in docs:
            try:
                data[int(doc.id)] = doc.to_dict()
            except: pass
        print(f"🔥 [Firebase] Configs cargadas: {len(data)} usuarios.")
        return data
    except Exception as e:
        print(f"⚠️ [Firebase] Config Load Error: {e}")
        return {}

async def save_user_config_fb(chat_id, config_data):
    """Guarda/Actualiza la config de un usuario."""
    if not db: return
    try:
        # Fire-and-forget sync wrapper
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: db.collection('user_configs').document(str(chat_id)).set(config_data, merge=True))
    except Exception as e:
         print(f"❌ [Firebase] Save Config Error: {e}")

async def load_all_hashtags():
    """Carga todos los hashtags."""
    if not db: return {}
    try:
        loop = asyncio.get_running_loop()
        docs = await loop.run_in_executor(None, lambda: db.collection('hashtags').stream())
        
        data = {}
        for doc in docs:
            data[doc.id] = doc.to_dict().get('msgs', [])
        print(f"🔥 [Firebase] Hashtags cargados: {len(data)} tags.")
        return data
    except Exception as e:
        print(f"⚠️ [Firebase] Tags Load Error: {e}")
        return {}

async def save_hashtag_fb(tag, msgs_list):
    if not db: return
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: db.collection('hashtags').document(tag).set({'msgs': msgs_list}, merge=True))
    except Exception as e:
        print(f"❌ [Firebase] Save Tag Error: {e}")

async def register_user(user_id, first_name, username):
    """
    Registra al usuario, cuenta el total y detecta cambio de nombre.
    Retorna: (is_new, count, name_changed)
    """
    if not db: return (False, 0, False) # Fallback

    try:
        # Referencias
        user_ref = db.collection('user_configs').document(str(user_id))
        stats_ref = db.collection('bot_settings').document('stats')
        
        # Ejecutar transacción (pseudo-transacción para simplificar en async wrapper)
        # Nota: Firestore async de python no soporta transactions con await facil dentro de lambda
        # Haremos una logica optimista/separada por simplicidad y velocidad
        
        # 1. Obtener User
        loop = asyncio.get_running_loop()
        doc = await loop.run_in_executor(None, user_ref.get)
        
        if not doc.exists:
            # --- NUEVO USUARIO ---
            # 1. Incrementar contador global
            try:
                # Lectura + Escritura (Riesgo bajo de colision en low traffic)
                st_doc = await loop.run_in_executor(None, stats_ref.get)
                current_count = st_doc.to_dict().get('user_count', 0) if st_doc.exists else 0
                new_count = current_count + 1
                await loop.run_in_executor(None, lambda: stats_ref.set({'user_count': new_count}, merge=True))
            except:
                new_count = 1 # Fallback
            
            # 2. Guardar Usuario
            user_data = {
                'first_name': first_name,
                'username': username,
                'joined_at': firestore.SERVER_TIMESTAMP,
                'user_id': user_id
            }
            await loop.run_in_executor(None, lambda: user_ref.set(user_data, merge=True))
            return (True, new_count, False)
            
        else:
            # --- USUARIO EXISTENTE ---
            data = doc.to_dict()
            old_name = data.get('first_name', '')
            
            # Detectar cambio de nombre
            if old_name != first_name:
                await loop.run_in_executor(None, lambda: user_ref.set({'first_name': first_name, 'username': username}, merge=True))
                return (False, 0, True)
            
            return (False, 0, False)

    except Exception as e:
        print(f"⚠️ [Firebase] Register Error: {e}")
        return (False, 0, False)

async def get_global_stats():
    """Retorna el diccionario de stats (ej: user_count)."""
    if not db: return {}
    try:
        doc_ref = db.collection('bot_settings').document('stats')
        loop = asyncio.get_running_loop()
        doc = await loop.run_in_executor(None, doc_ref.get)
        
        if doc.exists: return doc.to_dict()
        return {}
    except: return {}

# --- USER RULES (Memoria a largo plazo) ---
async def get_user_rules_fb(user_id, persona_id="nsfw"):
    """Retorna la lista de reglas de un usuario para una personalidad específica."""
    if not db: return []
    try:
        doc_ref = db.collection('user_rules').document(str(user_id))
        loop = asyncio.get_running_loop()
        doc = await loop.run_in_executor(None, doc_ref.get)
        
        if doc.exists:
            data = doc.to_dict()
            # MIGRATION CHECK: If 'rules' is at top level, it's legacy
            if 'rules' in data and isinstance(data['rules'], list):
               # Assume legacy rules belong to 'nsfw' or default
               legacy = data.pop('rules')
               if 'nsfw' not in data: data['nsfw'] = {'rules': legacy}
               else: data['nsfw']['rules'].extend(legacy)
               
               # Save migration async
               await loop.run_in_executor(None, lambda: doc_ref.set(data, merge=True))
            
            # Retrieve persona rules
            p_data = data.get(persona_id, {})
            return p_data.get('rules', [])
            
        return []
    except Exception as e:
        print(f"⚠️ [Firebase] Error leyendo reglas ({persona_id}): {e}")
        return []

async def save_user_rule_fb(user_id, rule_text, action="add", persona_id="nsfw"):
    """Guarda, elimina o limpia reglas de un usuario (Scoped by Persona)."""
    if not db: return False
    try:
        doc_ref = db.collection('user_rules').document(str(user_id))
        loop = asyncio.get_running_loop()
        
        # Leemos primero para modificar la lista
        doc = await loop.run_in_executor(None, doc_ref.get)
        data = doc.to_dict() if doc.exists else {}
        
        # MIGRATION ON SAVE
        if 'rules' in data and isinstance(data['rules'], list):
             legacy = data.pop('rules')
             if 'nsfw' not in data: data['nsfw'] = {'rules': legacy}
             else: data['nsfw']['rules'].extend(legacy)

        # Get target list
        if persona_id not in data: data[persona_id] = {'rules': []}
        current_rules = data[persona_id].get('rules', [])
        
        changed = False
        if action == "add":
            if rule_text not in current_rules:
                current_rules.append(rule_text)
                changed = True
        elif action == "remove":
            # Loose match or exact? Exact for now
            if rule_text in current_rules:
                current_rules = [r for r in current_rules if r != rule_text]
                changed = True
        elif action == "clear":
            current_rules = []
            changed = True
            
        if changed:
            data[persona_id]['rules'] = current_rules
            await loop.run_in_executor(None, lambda: doc_ref.set(data, merge=True))
            print(f"🔥 [Firebase] Reglas actualizadas user {user_id} [{persona_id}]: {action}")
            return True
        return True 
    except Exception as e:
        print(f"❌ [Firebase] Error guardando regla ({persona_id}): {e}")
        return False

# --- GLOBAL PERSONAS (SHARED) ---
async def save_global_persona(pid, data):
    """Guarda una personalidad global (Nombre, Prompt, Imágenes)."""
    if not db: return
    try:
        # Use a separate collection for scalable global personas
        doc_ref = db.collection('global_personas').document(str(pid))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: doc_ref.set(data, merge=True))
        print(f"🌍 [Firebase] Personalidad Global Guardada: {pid}")
    except Exception as e:
        print(f"❌ [Firebase] Error guardando global persona: {e}")

async def get_all_global_personas():
    """Retorna todas las personalidades globales {pid: data}."""
    if not db: return {}
    try:
        loop = asyncio.get_running_loop()
        docs = await loop.run_in_executor(None, lambda: db.collection('global_personas').stream())
        
        data = {}
        for doc in docs:
            data[doc.id] = doc.to_dict()
        return data
    except Exception as e:
        print(f"⚠️ [Firebase] Global Personas Load Error: {e}")
        return {}

async def delete_global_persona_fb(pid):
    """Elimina una personalidad global."""
    if not db: return
    try:
        doc_ref = db.collection('global_personas').document(str(pid))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, doc_ref.delete)
        print(f"🗑 [Firebase] Personalidad Global Eliminada: {pid}")
    except Exception as e:
        print(f"❌ [Firebase] Error eliminando global persona: {e}")

# --- CLOUD BODY (AVATARS) ---
async def save_persona_image(persona_id, outfit_id, emotion_id, file_id):
    """
    Guarda un File ID de Telegram en la colección de avatares.
    Estructura: avatars/{persona_id} -> {outfit_id}: {emotion_id: [file_ids]}
    """
    if not db: return False
    try:
        doc_ref = db.collection('avatars').document(str(persona_id))
        
        loop = asyncio.get_running_loop()
        doc = await loop.run_in_executor(None, doc_ref.get)
        
        data = doc.to_dict() if doc.exists else {}
        
        # Estructura profunda: data[outfit][emotion] = list
        if outfit_id not in data: data[outfit_id] = {}
        if emotion_id not in data[outfit_id]: data[outfit_id][emotion_id] = []
        
        # Evitar duplicados exactos
        if file_id not in data[outfit_id][emotion_id]:
            data[outfit_id][emotion_id].append(file_id)
            
            # Guardar
            await loop.run_in_executor(None, lambda: doc_ref.set(data, merge=True))
            print(f"🔥 [Firebase] Avatar Saved: {persona_id}/{outfit_id}/{emotion_id}")
            return True
            
        return True # Ya existía
    except Exception as e:
        print(f"❌ [Firebase] Avatar Save Error: {e}")
        return False

async def get_persona_images(persona_id, outfit_id, emotion_id):
    """
    Retorna la lista de File IDs para una combinación específica.
    """
    if not db: return []
    try:
        doc_ref = db.collection('avatars').document(str(persona_id))
        loop = asyncio.get_running_loop()
        doc = await loop.run_in_executor(None, doc_ref.get)
        
        if doc.exists:
            data = doc.to_dict()
            outfit_data = data.get(outfit_id, {})
            images = outfit_data.get(emotion_id, [])
            return images
        return []
    except Exception as e:
        print(f"⚠️ [Firebase] Avatar Read Error: {e}")
        return []

async def get_all_avatars(persona_id):
    """Retorna toda la estructura de avatares de una persona."""
    if not db: return {}
    try:
        doc_ref = db.collection('avatars').document(str(persona_id))
        loop = asyncio.get_running_loop()
        doc = await loop.run_in_executor(None, doc_ref.get)
        return doc.to_dict() if doc.exists else {}
    except: return {}

async def delete_persona_image(persona_id, outfit_id, emotion_id, file_id_target):
    """
    Elimina una imagen específica (por file_id) de la lista.
    file_id_target puede ser string o dict {'id':...}
    """
    if not db: return False
    try:
        doc_ref = db.collection('avatars').document(str(persona_id))
        loop = asyncio.get_running_loop()
        doc = await loop.run_in_executor(None, doc_ref.get)
        
        if not doc.exists: return False
        
        data = doc.to_dict()
        
        if outfit_id not in data or emotion_id not in data[outfit_id]:
            return False
            
        current_list = data[outfit_id][emotion_id]
        
        # Filtrar
        new_list = []
        found = False
        target_str = file_id_target
        if isinstance(file_id_target, dict): target_str = file_id_target.get('id')
        
        for item in current_list:
            item_id = item
            if isinstance(item, dict): item_id = item.get('id')
            
            if item_id == target_str:
                found = True
            else:
                new_list.append(item)
        
        if found:
            data[outfit_id][emotion_id] = new_list
            await loop.run_in_executor(None, lambda: doc_ref.set(data))
            print(f"🗑 [Firebase] Avatar Deleted: {target_str}")
            return True
            
        return False
    except Exception as e:
        print(f"❌ [Firebase] Avatar Delete Error: {e}")
        return False

# --- VIRAL SHORTS PERSISTENCE ---
async def save_viral_item_fb(item):
    """Guarda un item viral en la colección 'viral_shorts'."""
    if not db: return False
    try:
        # Usa el ID del item como ID del documento
        doc_ref = db.collection('viral_shorts').document(str(item['id']))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: doc_ref.set(item, merge=True))
        print(f"🔥 [Firebase] Viral Item Saved: {item['id']}")
        return True
    except Exception as e:
        print(f"❌ [Firebase] Viral Save Error: {e}")
        return False

async def delete_viral_item_fb(item_id):
    """Elimina un item viral de la colección."""
    if not db: return False
    try:
        doc_ref = db.collection('viral_shorts').document(str(item_id))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, doc_ref.delete)
        print(f"🗑 [Firebase] Viral Item Deleted: {item_id}")
        return True
    except Exception as e:
        print(f"❌ [Firebase] Viral Delete Error: {e}")
        return False

async def load_all_viral_items_fb():
    """Carga todos los items virales en una lista."""
    if not db: return []
    try:
        loop = asyncio.get_running_loop()
        docs = await loop.run_in_executor(None, lambda: db.collection('viral_shorts').stream())
        
        items = []
        for doc in docs:
            try:
                items.append(doc.to_dict())
            except: pass
        
        print(f"🔥 [Firebase] Viral Items Loaded: {len(items)}")
        return items
    except Exception as e:
        print(f"⚠️ [Firebase] Viral Load Error: {e}")
        return []
