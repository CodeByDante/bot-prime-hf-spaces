import aiohttp
import asyncio
import os
import shutil
import json
import zipfile
import img2pdf
from PIL import Image
from io import BytesIO
from config import DATA_DIR
from pyrogram.types import InputMediaPhoto, InputMediaDocument
from tools_media import progreso
from firebase_service import get_cached_file, save_cached_file, get_cached_data
from database import add_active, remove_active, update_progress

import time

FIREBASE_BASE_URL = "https://firestore.googleapis.com/v1/projects/twistedbrody-9d163/databases/(default)/documents"

# --- GLOBAL CACHE ---
MANGA_CACHE = {
    'data': [],
    'last_updated': 0,
    'ttl': 300  # 5 minutos
}

# --- TRACKING LAST SENT MANGAS (Para no repetir seguido) ---
LAST_SENT_MANGAS = {} # {chat_id: deque([id1, id2, id3], maxlen=10)}
from collections import deque

async def download_image(session, url, path):
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(path, 'wb') as f:
                    f.write(await resp.read())
                return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
    return False


async def get_manga_metadata(manga_id):
    """Obtiene título, autor y portada del manga desde Firebase."""
    url = f"{FIREBASE_BASE_URL}/mangas/{manga_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    print(f"❌ Error Metadata ({resp.status}): {await resp.text()}")
                    return None
                data = await resp.json()
                
                fields = data.get('fields', {})
                title = fields.get('title', {}).get('stringValue', 'Desconocido')
                author = fields.get('author', {}).get('stringValue', 'Desconocido')
                # La portada suele estar en 'cover' o 'image'
                cover = fields.get('cover', {}).get('stringValue') or fields.get('image', {}).get('stringValue')
                
                return {
                    'id': manga_id,
                    'title': title,
                    'author': author,
                    'cover': cover
                }
    except Exception as e:
        print(f"❌ Excepción Metadata: {e}")
        return None

async def get_or_cache_cover(client, chat_id, manga_id, cover_url):
    """
    Obtiene el FILE_ID de la portada.
    1. Si está en cache, lo devuelve.
    2. Si no, descarga la imagen, la envía, obtiene el ID y lo guarda.
    """
    if not cover_url: return None
    
    # 1. Check Cache
    cached_id = await get_cached_file(f"manga_{manga_id}", "cover_id")
    if cached_id: return cached_id
    
    # 2. Download & Cache
    try:
        # Temp file
        import time
        ts = int(time.time())
        tmp_path = os.path.join(DATA_DIR, f"cover_{manga_id}_{ts}.jpg")
        
        async with aiohttp.ClientSession() as session:
            if await download_image(session, cover_url, tmp_path):
                # Enviar mensaje temporal para sacar ID
                # Usamos send_photo con file=tmp_path
                msg = await client.send_photo(chat_id, tmp_path)
                if msg and msg.photo:
                    fid = msg.photo.file_id
                    await save_cached_file(f"manga_{manga_id}", "cover_id", fid)
                    await msg.delete()
                    try: os.remove(tmp_path)
                    except: pass
                    return fid
                
                # Si falla obtener ID, pero descargó, devolvemos PATH
                # No borramos tmp_path aqui, dejamos que main.py lo use
                await msg.delete()
                return tmp_path

    except Exception as e:
        print(f"❌ Error Cache Cover: {e}")
    
    return cover_url # Fallback a URL original (baja probabilidad de éxito si es img protegida)


async def get_manga_chapters(manga_id):
    """Obtiene los capítulos (imágenes) usando una Query a Firebase."""
    url = f"{FIREBASE_BASE_URL}:runQuery"
    
    # Query Body exacto proporcionado por el usuario
    payload = {
        "structuredQuery": {
            "from": [{ "collectionId": "chapters" }],
            "where": {
                "fieldFilter": {
                    "field": { "fieldPath": "manga_id" },
                    "op": "EQUAL",
                    "value": { "stringValue": manga_id }
                }
            }
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    print(f"❌ Error Chapters ({resp.status}): {await resp.text()}")
                    return []
                
                data = await resp.json()
                # data es una lista de documentos wrapper
                
                chapters = []
                for item in data:
                    doc = item.get('document', {})
                    if not doc: continue
                    
                    fields = doc.get('fields', {})
                    
                    # Extraer páginas originales
                    orig_pages = []
                    vals = fields.get('original_pages', {}).get('arrayValue', {}).get('values', [])
                    for v in vals:
                        if 'stringValue' in v: orig_pages.append(v['stringValue'])
                        
                    # Extraer páginas webp
                    webp_pages = []
                    vals = fields.get('pages', {}).get('arrayValue', {}).get('values', [])
                    for v in vals:
                        if 'stringValue' in v: webp_pages.append(v['stringValue'])
                        
                    ch_num = fields.get('number', {}).get('integerValue', '0')
                    ch_title = fields.get('title', {}).get('stringValue', f"Capítulo {ch_num}")
                    
                    chapters.append({
                        'title': ch_title,
                        'number': int(ch_num),
                        'original': orig_pages,
                        'webp': webp_pages
                    })
                
                # Ordenar por número
                chapters.sort(key=lambda x: x['number'])
                return chapters
                
    except Exception as e:
        print(f"❌ Excepción Chapters: {e}")
        return []

    except: pass
    return None

async def get_all_mangas_paginated():
    """Obtiene una lista ligera de TODOS los mangas (Title, ID, Cover) para el catálogo."""
    
    # 1. Global Cache Check
    now = time.time()
    if MANGA_CACHE['data'] and (now - MANGA_CACHE['last_updated'] < MANGA_CACHE['ttl']):
        return MANGA_CACHE['data']

    url = f"{FIREBASE_BASE_URL}:runQuery"
    # Query para traer solo campos necesarios y ordenar (simulado)
    # Firebase REST es limitado, traemos todo y filtramos en RAM (Para ~50 mangas está bien)
    payload = {
        "structuredQuery": {
            "from": [{ "collectionId": "mangas" }],
            "limit": 100 # Safety limit
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200: return []
                data = await resp.json()
                
                mangas = []
                for item in data:
                    doc = item.get('document', {})
                    if not doc: continue
                    
                    # ID está en name: .../documents/mangas/ID
                    full_name = doc.get('name', '')
                    mid = full_name.split('/')[-1]
                    
                    fields = doc.get('fields', {})
                    title = fields.get('title', {}).get('stringValue', 'Sin Título')
                    author = fields.get('author', {}).get('stringValue', 'Desconocido')
                    cover = fields.get('cover', {}).get('stringValue') or fields.get('image', {}).get('stringValue')
                    
                    # FALLBACK: Si no hay 'cover' ni 'image' en metadata general, buscar en el capitulo 1 (si existiese en la DB plana)
                    # Pero get_all_mangas solo mira la coleccion "mangas", no "chapters".
                    # Intentamos buscar clean_url o similar
                    if not cover:
                         # Intento desesperado: buscar cualquier campo que parezca url
                         for k, v in fields.items():
                             val = v.get('stringValue', '')
                             if 'http' in val and ('jpg' in val or 'png' in val or 'webp' in val):
                                 cover = val
                                 break

                    if not cover:
                        print(f"⚠️ Manga sin portada: {title} ({mid})")

                    mangas.append({
                        'id': mid,
                        'title': title, # Strip para limpieza
                        'author': author,
                        'cover': cover
                    })
                
                # Ordenar alfabéticamente
                mangas.sort(key=lambda x: x['title'])
                
                # Update Cache
                MANGA_CACHE['data'] = mangas
                MANGA_CACHE['last_updated'] = time.time()
                
                return mangas
    except Exception as e:
        print(f"Error Manga Pagination: {e}")
        return []

async def get_random_cached_image(chat_id):
    """
    Busca un manga aleatorio que tenga imágenes cacheadas en Firebase y devuelve un file_id aleatorio
    junto con los datos del manga para la interfaz.
    """
    import random
    from firebase_service import db, CACHE_COLLECTION
    
    # Obtener historial reciente del chat
    if chat_id not in LAST_SENT_MANGAS:
        LAST_SENT_MANGAS[chat_id] = deque(maxlen=20)
    recent_history = LAST_SENT_MANGAS[chat_id]
    
    # 1. Traer todos los documentos de la colección de caché de una sola vez (es rápido y tiene los IDs)
    if not db: return None, None
    try:
        loop = asyncio.get_running_loop()
        # Traemos solo los documentos de la colección de caché
        docs = await loop.run_in_executor(None, lambda: db.collection(CACHE_COLLECTION).get())
        
        valid_cached_manga_ids = []
        cache_data_map = {}
        
        # Filtrar los que son de mangas (empiezan con manga_) y tienen arrays de imagenes
        for doc in docs:
            doc_id = doc.id
            if doc_id.startswith("manga_"):
                data = doc.to_dict()
                
                # Buscar si este documento tiene algún array con imágenes guardadas
                valid_images = []
                for key in ["img_original", "img_webp", "img_original_doc", "img_webp_doc"]:
                    val = data.get(key)
                    if val and isinstance(val, list) and len(val) > 0:
                        valid_images.extend(val)
                
                if valid_images:
                    manga_id_clean = doc_id.replace("manga_", "")
                    valid_cached_manga_ids.append(manga_id_clean)
                    cache_data_map[manga_id_clean] = valid_images
                    
        if not valid_cached_manga_ids:
            return None, None
            
        # Filtrar mangas disponibles basados en el historial
        available_ids = [mid for mid in valid_cached_manga_ids if mid not in recent_history]
        
        # Si ya mostramos todos, reiniciar
        if not available_ids:
            available_ids = valid_cached_manga_ids
            
        # Elegir un manga_id al azar de los disponibles
        chosen_manga_id = random.choice(available_ids)
        
        # Elegir una imagen al azar de ese manga, pero con 20% de probabilidad de forzar la primera imagen (portada)
        cache_array = cache_data_map[chosen_manga_id]
        if random.random() < 0.20 and len(cache_array) > 0:
            chosen_file_id = cache_array[0]
        else:
            chosen_file_id = random.choice(cache_array)
        
        # Guardar en historial
        recent_history.append(chosen_manga_id)
        
        # Por último, necesitamos los datos (título/portada) de ese manga
        # Como solo necesitamos LOS DATOS DE UNO, podemos buscarlo en la lista paginada en RAM
        mangas = await get_all_mangas_paginated()
        chosen_manga_data = next((m for m in mangas if m['id'] == chosen_manga_id), None)
        
        # Si no está en la lista general paginada, hacemos un metadata fetch rápido final
        if not chosen_manga_data:
             chosen_manga_data = await get_manga_metadata(chosen_manga_id)
             
        return chosen_manga_data, chosen_file_id
        
    except Exception as e:
        print(f"Error optimizando Random Cache Fetch: {e}")
        return None, None

from pyrogram.types import InputMediaPhoto, InputMediaDocument
from pyrogram.errors import FloodWait

async def download_image(session, url, file_path, retries=3):
    """Descarga e una imagen Directamente al Disco (Streaming) para ahorrar RAM."""
    # Headers para evitar bloqueos (403/401)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://codebydrody-twistedbrodymangaflow.hf.space/"
    }
    
    for i in range(retries):
        try:
            async with session.get(url, headers=headers, timeout=30) as resp:
                if resp.status == 200:
                    with open(file_path, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(1024):
                            f.write(chunk)
                    return True
                else:
                    print(f"⚠️ HTTP {resp.status} for {url}")
        except Exception as e:
            # Imprimir error detallado y URL completa
            print(f"⚠️ DL Error ({i+1}/{retries}) {url}: {repr(e)}")
            await asyncio.sleep(2)
    return False

async def repair_image(path):
    """Comprime y redimensiona una imagen si es demasiado pesada para Telegram."""
    try:
        if not os.path.exists(path): return False
        
        size_mb = os.path.getsize(path) / (1024 * 1024)
        
        def _do_repair():
            with Image.open(path) as im:
                # 1. Redimensionar si es excesiva (max 2560px)
                max_dim = 2560
                if im.width > max_dim or im.height > max_dim:
                    im.thumbnail((max_dim, max_dim), Image.LANCZOS)
                
                # 2. Guardar con compresión y optimización
                rgb_im = im.convert('RGB')
                rgb_im.save(path, "JPEG", quality=80, optimize=True)
        
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _do_repair)
        
        new_size = os.path.getsize(path) / (1024 * 1024)
        print(f"🛠 [Repair] {os.path.basename(path)}: {size_mb:.1f}MB -> {new_size:.1f}MB")
        return True
    except Exception as e:
        print(f"❌ Error reparando {path}: {e}")
        return False

async def process_manga_download(client, chat_id, manga_data, container, quality, status_msg, doc_mode=False, group_mode=True):
    """
    Descarga, procesa y envía el manga.
    container: 'zip', 'pdf' o 'img' (alias 'images')
    quality: 'original', 'webp', 'png', 'jpg'
    """
    # Alias
    if container == 'images': container = 'img'
    
    manga_id = manga_data['id']
    title = manga_data['title']
    
    # Crear directorio temporal único
    import time
    timestamp = int(time.time())
    base_tmp = os.path.join(DATA_DIR, f"manga_{manga_id}_{timestamp}")
    os.makedirs(base_tmp, exist_ok=True)
    
    # Register Active Task
    curr_task = asyncio.current_task()
    add_active(chat_id, status_msg.id, curr_task)
    
    try:
        # 0. KEY GENERATION & CACHE CHECK
        # FETCH EARLY para validar si el orden / contenido cambió
        chapters = await get_manga_chapters(manga_id)
        if not chapters:
            await status_msg.edit("❌ No se encontraron capítulos o imágenes.")
            return
            
        use_src = 'webp' if quality == 'webp' else 'original'
        src_urls = []
        for ch in chapters:
             sl = ch[use_src]
             if not sl and use_src == 'original': sl = ch['webp']
             src_urls.extend(sl)
             
        import hashlib
        hash_input = title + "".join(src_urls)
        urls_hash = hashlib.md5(hash_input.encode()).hexdigest()[:10]

        # Key format: manga_{id} // Field: {container}_{quality}_{hash}
        cache_key = f"{container}_{quality}_{urls_hash}"
        if doc_mode: cache_key += "_doc"
        
        print(f"🔍 [Cache Check] Key: {cache_key} for Manga: {manga_id}")
        cached_data = await get_cached_file(f"manga_{manga_id}", cache_key)
        
        # SMART CACHE VALIDATION 
        valid_cache = False
        if cached_data:
             if isinstance(cached_data, list):
                 if len(cached_data) == len(src_urls):
                     valid_cache = True
                     cached_data_to_use = cached_data
                 else:
                     valid_cache = False
             else:
                 valid_cache = True
                 cached_data_to_use = cached_data

        if valid_cache:
            await status_msg.edit(f"✨ **{title}**\n⚡ Enviando desde memoria (instantáneo)...")
            try:
                if isinstance(cached_data_to_use, list):
                    # ALBUM CACHE (Images)
                    if group_mode:
                        # Enviar la primera imagen sola con el título (portada)
                        if cached_data_to_use:
                            cap = f"📖 **{title}**"
                            try:
                                # SIEMPRE enviar la portada como foto, incluso en modo documento
                                await client.send_photo(chat_id, cached_data_to_use[0], caption=cap)
                                await asyncio.sleep(1)
                            except Exception as e:
                                print(f"⚠️ Error enviando portada inicial cache: {e}")

                        for i in range(0, len(cached_data_to_use), 10):
                            chunk = cached_data_to_use[i:i+10]
                            media = []
                            for fid in chunk:
                                if not fid: continue # Skip invalid IDs
                                if doc_mode: media.append(InputMediaDocument(fid))
                                else: media.append(InputMediaPhoto(fid))
                            
                            if not media: continue
                            
                            try:
                                await client.send_media_group(chat_id, media)
                                await asyncio.sleep(1)
                            except FloodWait as fw: await asyncio.sleep(fw.value + 1)
                            except Exception as e: 
                                print(f"⚠️ Error SendGroup Cache: {e}")
                    else:
                        for fid in cached_data_to_use:
                            if not fid: continue
                            try:
                                if doc_mode: await client.send_document(chat_id, fid)
                                else: await client.send_photo(chat_id, fid)
                                await asyncio.sleep(0.3)
                            except FloodWait as fw: await asyncio.sleep(fw.value + 1)
                            except Exception as e:
                                print(f"⚠️ Error SendItem Cache: {e}")
                else:
                    # SINGLE FILE CACHE (ZIP/PDF)
                    cap = f"🎬 **{title}**\n👤 {manga_data.get('author','?')}\n✨ (Desde Memoria)"
                    await client.send_document(chat_id, cached_data_to_use, caption=cap)
                
                await status_msg.delete()
                print(f"✅ Cache Hit Success: {title}")
                
                if isinstance(cached_data_to_use, list) and container == 'img':
                    total_cached = len(cached_data_to_use)
                    summary_text = f"✅ **{title}**\n\nSe enviaron `{total_cached}/{total_cached}` páginas correctamente (desde memoria)."
                    await client.send_message(chat_id, summary_text)
                    
                return # EXIT SUCCESS
            except Exception as e:
                print(f"⚠️ Cache read/send failed: {e}. Fallback to download.")
                await status_msg.edit(f"⚠️ **Error en memoria.**\nDescargando de nuevo...")
                # Fallback to download (continue execution below)

        if not valid_cache: # Solo editar si no acabamos de fallar cache silenciosamente
             await status_msg.edit(f"⏳ **{title}**\n🔍 Obteniendo lista de capítulos...")
        
        # --- ZIP MASTER STRATEGY ---
        # Si NO hay cache específico (ej: pdf_original), preguntamos por el ZIP Maestro.
        zip_master_fid = await get_cached_file(f"manga_{manga_id}", "zip_master")
        
        using_master_zip = False
        
        if zip_master_fid:
            await status_msg.edit(f"⚡ **{title}**\n📥 Descargando desde Respaldo (ZIP Maestro)...")
            try:
                # Descargar ZIP Maestro
                zip_path = os.path.join(base_tmp, "master_download.zip")
                await client.download_media(zip_master_fid, file_name=zip_path)
                
                if os.path.exists(zip_path):
                    await status_msg.edit(f"⚡ **{title}**\n📦 Extrayendo Respaldo...")
                    
                    # Extraer
                    loop = asyncio.get_running_loop()
                    def unzip_master():
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            zip_ref.extractall(base_tmp)
                    await loop.run_in_executor(None, unzip_master)
                    
                    # Cleanup zip
                    try: os.remove(zip_path)
                    except: pass
                    
                    using_master_zip = True
                    print(f"✅ ZIP Maestro usado para: {title}")
                    
            except Exception as e:
                print(f"⚠️ Error usando ZIP Maestro: {e}. Fallback a descarga web.")
        
        if not using_master_zip:
             # METODO ANTIGUO (Solo si falló el maestro o no existe)
             # "chapters" ya se descargó arriba para calcular el hash.
             if not chapters:
                 await status_msg.edit("❌ No se encontraron capítulos o imágenes.")
                 return

             # Seleccionar fuente inicial
             use_source = 'webp' if quality == 'webp' else 'original'
        
             img_queue = []
             for ch in chapters:
                 ch_safe = "".join([c for c in ch['title'] if c.isalnum() or c in " -_"]).strip()
                 ch_dir = os.path.join(base_tmp, ch_safe)
                 os.makedirs(ch_dir, exist_ok=True)
            
                 src_list = ch[use_source]
                 if not src_list and use_source == 'original': src_list = ch['webp'] # Fallback
            
                 for idx, url in enumerate(src_list):
                     ext = url.split('?')[0].split('.')[-1].lower()
                     if len(ext) > 4: ext = 'jpg'
                 
                     fname = f"{idx+1:03d}.{ext}"
                     dest_path = os.path.join(ch_dir, fname)
                     img_queue.append((url, dest_path))
        
             total = len(img_queue)
             await status_msg.edit(f"⏳ **{title}**\n⬇️ Descargando {total} imágenes ({quality.upper()})...")

             # 2. Descarga Concurrente (OPTIMIZADO)
             batch_size = 15 # Reducido a 15 para evitar saturar sockets en requests a ImgBB
             downloaded_count = 0
             failed_count = 0
             
             async with aiohttp.ClientSession() as session:
                 for i in range(0, total, batch_size):
                     batch = img_queue[i:i+batch_size]
                     tasks = [download_image(session, url, path) for url, path in batch]
                     
                     results = await asyncio.gather(*tasks)
                     
                     for res in results:
                         if res: downloaded_count += 1
                         else: failed_count += 1
                     
                     # Calculate and Show Percentage
                     pct = int((downloaded_count / total) * 100)
                     msg_text = f"⏳ **{title}**\n⬇️ Descargando...\n✅ {downloaded_count}/{total} imágenes (`{pct}%`)"
                     if failed_count > 0:
                         msg_text += f"\n❌ Fallaron: {failed_count}"
                         
                     try:
                         if i % 2 == 0 or i + batch_size >= total: # Update less frequently to avoid floodwait
                             await status_msg.edit(msg_text)
                             update_progress(chat_id, status_msg.id, percent=pct, status="Descargando Manga", name=title)
                     except FloodWait as fw:
                         await asyncio.sleep(fw.value)
                     except: pass
        
        # 3. Conversión de Formato (si aplica)
        # Fix: img2pdf no soporta WebP. Telegram send_photo no soporta WebP con Alpha (a veces).
        # Si es PDF o IMG (Photo Mode) con WebP, forzamos conversión a JPG.
        # 3. Conversión de Formato (si aplica)
        # Fix: img2pdf no soporta WebP. Telegram send_photo no soporta WebP con Alpha.
        
        # Logic Revamp: Only convert if strictly necessary to preserve quality.
        convert_count = 0
        
        for root, _, files in os.walk(base_tmp):
            for file in files:
                safe_path = os.path.join(root, file)
                fname, cur_ext = os.path.splitext(file)
                cur_ext = cur_ext.lower()
                
                start_convert = False
                target_ext = ".jpg"

                # A. PDF Mode: Convert WebP -> JPG (img2pdf limitation). Keep PNG/JPG as is.
                if container == 'pdf':
                    if cur_ext == '.webp':
                        start_convert = True
                        target_ext = ".jpg"
                
                # B. Img Mode (Photo): Convert WebP -> JPG (Telegram compatibility)
                elif container == 'img' and not doc_mode:
                    if cur_ext == '.webp': # or quality == 'webp' implicit
                         start_convert = True
                         target_ext = ".jpg"
                
                # C. Explicit Format Request (PNG/JPG) vs Original
                elif quality in ['png', 'jpg']:
                    if cur_ext != f".{quality}":
                        start_convert = True
                        target_ext = f".{quality}"

                if start_convert:
                    if convert_count == 0:
                        await status_msg.edit(f"⏳ **{title}**\n⚙️ Procesando imágenes para compatibilidad...")
                    
                    convert_count += 1
                    new_path = os.path.join(root, fname + target_ext)

                    try:
                        # Offload CPU-heavy image conversion
                        def convert_img():
                            with Image.open(safe_path) as im:
                                rgb_im = im.convert('RGB')
                                rgb_im.save(new_path, quality=95)
                        
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, convert_img)
                        
                        # Remove original if different extension
                        if cur_ext != target_ext and os.path.exists(safe_path):
                            os.remove(safe_path)

                    except Exception as e:
                        print(f"⚠️ Error converting {file}: {e}")
                        
                        if new_path != safe_path and os.path.exists(new_path):
                             try: os.remove(new_path)
                             except: pass

        # 4. Empaquetado o Envío
        
        if container == 'img':
            await status_msg.edit(f"📤 **{title}**\nEnviando {total} imágenes...")
            
            # Recolectar todos los archivos finales ordenados
            all_files = []
            for ch in chapters:
                ch_safe = "".join([c for c in ch['title'] if c.isalnum() or c in " -_"]).strip()
                ch_dir = os.path.join(base_tmp, ch_safe)
                if not os.path.exists(ch_dir): continue
                imgs = sorted(os.listdir(ch_dir))
                for im in imgs:
                    all_files.append(os.path.join(ch_dir, im))

            if not all_files:
                return await status_msg.edit("❌ Error: No se descargaron imágenes.")
            
            # --- ENVIAR AL USUARIO Y CAPTURAR FILE IDs ---
            sent_file_ids = []
            
            if group_mode:
                # Album Fotos/Docs
                # Enviar la primera imagen sola con el título
                first_image = all_files[0]
                cover_file_id = None
                try:
                    cap = f"📖 **{title}**"
                    # SIEMPRE enviar la primera imagen (portada) como foto
                    cover_msg = await client.send_photo(chat_id, first_image, caption=cap)
                    if cover_msg and cover_msg.photo:
                        cover_file_id = cover_msg.photo.file_id
                        
                    if cover_file_id:
                        await save_cached_file(f"manga_{manga_id}", "cover_id", cover_file_id)

                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"⚠️ Error enviando portada inicial: {e}")

                for i in range(0, len(all_files), 10):
                    chunk = all_files[i:i+10]
                    media = []
                    for chunk_idx, f in enumerate(chunk):
                        is_first_image = (i == 0 and chunk_idx == 0)
                        
                        if not is_first_image or not cover_file_id:
                            # --- FIX: REPAIR IMAGE SI PESA MUCHO ---
                            size_mb = os.path.getsize(f) / (1024 * 1024)
                            if size_mb > 9.0 and doc_mode == False:
                                await repair_image(f)
                                
                        media_src = cover_file_id if (is_first_image and cover_file_id) else f
                            
                        if doc_mode: media.append(InputMediaDocument(media_src))
                        else: media.append(InputMediaPhoto(media_src))
                    
                    try:
                        # Capturar resultado
                        sent_msgs = await client.send_media_group(chat_id, media)
                        if sent_msgs:
                            for m in sent_msgs:
                                if m.photo: sent_file_ids.append(m.photo.file_id)
                                elif m.document: sent_file_ids.append(m.document.file_id)
                        await asyncio.sleep(1.5)
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value + 1)
                        # Reintento simple
                        try:
                            sent_msgs = await client.send_media_group(chat_id, media)
                            if sent_msgs:
                                for m in sent_msgs:
                                    if m.photo: sent_file_ids.append(m.photo.file_id)
                                    elif m.document: sent_file_ids.append(m.document.file_id)
                        except: pass
                    except Exception as e:
                        err_str = str(e).upper()
                        # Expandimos errores para incluir PHOTO_SAVE_FILE_INVALID
                        if "FILE_TOO_BIG" in err_str or "MEDIA_INVALID" in err_str or "PHOTO_INVALID_DIMENSIONS" in err_str or "PHOTO_SAVE_FILE_INVALID" in err_str:
                            print(f"⚠️ [Manga] Fallo de envío en lote ({e}). Intentando reparación...")
                            for m_item in media:
                                await repair_image(m_item.media)
                            
                            try:
                                await asyncio.sleep(2)
                                sent_msgs = await client.send_media_group(chat_id, media)
                                if sent_msgs:
                                    for m in sent_msgs:
                                        if m.photo: sent_file_ids.append(m.photo.file_id)
                                        elif m.document: sent_file_ids.append(m.document.file_id)
                                print(f"✅ [Manga] Lote enviado con éxito tras reparación.")
                            except Exception as re_e:
                                print(f"❌ [Manga] Falló reenvío tras reparación: {re_e}")
                        else:
                            print(f"❌ [Manga] Error enviando lote {i}: {e}")
            else:
                # 1 a 1 Fotos/Docs
                for f in all_files:
                    try:
                        m = None
                        if doc_mode: m = await client.send_document(chat_id, f)
                        else: m = await client.send_photo(chat_id, f)
                        
                        if m:
                             if m.photo: sent_file_ids.append(m.photo.file_id)
                             elif m.document: sent_file_ids.append(m.document.file_id)
                             
                        await asyncio.sleep(0.3)
                    except FloodWait as e: await asyncio.sleep(e.value + 1)
                    except Exception as e:
                        err_str = str(e).upper()
                        # Expandimos errores para incluir PHOTO_SAVE_FILE_INVALID
                        if "FILE_TOO_BIG" in err_str or "MEDIA_INVALID" in err_str or "PHOTO_INVALID_DIMENSIONS" in err_str or "PHOTO_SAVE_FILE_INVALID" in err_str:
                             print(f"⚠️ [Manga] Fallo de envío individual: {os.path.basename(f)} ({e}). Reparando...")
                             await repair_image(f)
                             try:
                                 await asyncio.sleep(1)
                                 if doc_mode: m = await client.send_document(chat_id, f)
                                 else: m = await client.send_photo(chat_id, f)
                                 if m:
                                     if m.photo: sent_file_ids.append(m.photo.file_id)
                                     elif m.document: sent_file_ids.append(m.document.file_id)
                                 print(f"✅ [Manga] Imagen enviada con éxito tras reparación.")
                             except Exception as re_e:
                                 print(f"❌ [Manga] Falló reenvío individual tras reparación: {re_e}")
                        else:
                             print(f"❌ [Manga] Error enviando imagen {os.path.basename(f)}: {e}")

            # SAVE TO CACHE (List of IDs)
            if sent_file_ids:
                print(f"🔥 [Cache Save] Key: {cache_key} | IDs: {len(sent_file_ids)}")
                await save_cached_file(f"manga_{manga_id}", cache_key, sent_file_ids, meta={'title': title})

            await status_msg.delete()
            
            # --- SUMMARY MESSAGE ---
            total_expected = len(all_files)
            sent_count = len(sent_file_ids)

            if sent_count >= total_expected:
                summary_text = f"✅ **{title}**\n\nSe enviaron `{total_expected}/{total_expected}` páginas correctamente."
            else:
                summary_text = f"❌ **{title}**\n\nSe enviaron `{sent_count}/{total_expected}` páginas.\n⚠️ Hubo un error procesando algunas páginas."
                
            await client.send_message(chat_id, summary_text)
            return
        
        # ZIP o PDF
        await status_msg.edit(f"⏳ **{title}**\n📦 Creando archivo {container.upper()}...")
        final_file = None
        
        if container == 'pdf':
            all_imgs_paths = []
            for ch in chapters:
                ch_safe = "".join([c for c in ch['title'] if c.isalnum() or c in " -_"]).strip()
                ch_dir = os.path.join(base_tmp, ch_safe)
                if not os.path.exists(ch_dir): continue
                imgs = sorted(os.listdir(ch_dir))
                for im in imgs:
                    all_imgs_paths.append(os.path.join(ch_dir, im))
            
            if all_imgs_paths:
                # Sanitize Title for Filename (Windows)
                safe_title = "".join([c for c in title if c.isalnum() or c in " -_().[]"])
                pdf_path = os.path.join(DATA_DIR, f"{safe_title} [{quality.upper()}].pdf")
                # Offload PDF creation (Blocking I/O + CPU)
                loop = asyncio.get_running_loop()
                def create_pdf():
                    with open(pdf_path, "wb") as f:
                        f.write(img2pdf.convert(all_imgs_paths))
                
                await loop.run_in_executor(None, create_pdf)
                final_file = pdf_path
                
        else:
            # ZIP
            # Offload ZIP creation (Blocking I/O)
            safe_title = "".join([c for c in title if c.isalnum() or c in " -_().[]"])
            zip_path = os.path.join(DATA_DIR, f"{safe_title} [{quality.upper()}].zip")
            
            loop = asyncio.get_running_loop()
            def create_zip():
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(base_tmp):
                        for file in files:
                            abs_path = os.path.join(root, file)
                            arc_name = os.path.relpath(abs_path, base_tmp)
                            zipf.write(abs_path, arc_name)
            
            await loop.run_in_executor(None, create_zip)
            final_file = zip_path

        # Enviar Archivo Final
        if final_file and os.path.exists(final_file):
            await status_msg.edit(f"📤 **{title}**\nSubiendo archivo ({os.path.getsize(final_file)/1024/1024:.1f} MB)...")
            
            cap = f"📚 **{title}**\n👤 {manga_data['author']}\n🆔 `{manga_id}`\n📦 {container.upper()} | 🎨 {quality.upper()}"
            
            try:
                msg = await client.send_document(chat_id, final_file, caption=cap, progress=progreso, progress_args=(status_msg, [time.time(),0], "Subiendo..."))
                
                # SAVE CACHE (Single File ID)
                if msg and msg.document:
                     print(f"🔥 [Cache Save] Key: {cache_key} | ID: {msg.document.file_id}")
                     await save_cached_file(f"manga_{manga_id}", cache_key, msg.document.file_id, meta={'title': title})
                     
                # Eliminar el mensaje de estatus ya que la subida ha finalizado
                try: await status_msg.delete()
                except: pass
            
            except Exception as e:
                print(f"Error sending doc: {e}")
                try: await status_msg.edit(f"❌ Error al subir: {e}")
                except: pass
            
            try: os.remove(final_file)
            except: pass
        else:
            await status_msg.edit("❌ Error al crear el archivo final.")

    except asyncio.CancelledError:
        print(f"🛑 Descarga Cancelada: {title}")
        await status_msg.edit("🛑 **Descarga Cancelada.**")
        raise 

    except Exception as e:
        print(f"❌ Error Critical Process Manga: {e}")
        if status_msg: await status_msg.edit(f"❌ Error Crítico: {e}")
    
    finally:
        # Cleanup
        if 'base_tmp' in locals() and base_tmp and os.path.exists(base_tmp):
            try: shutil.rmtree(base_tmp)
            except: pass
        
        # Unregister Task
        if 'chat_id' in locals() and 'status_msg' in locals():
             remove_active(chat_id, status_msg.id)


# --- BACKGROUND WARMER ---
async def warm_covers_background(app, dump_chat_id, single_run=False):
    """
    Proceso de fondo (o manual) que revisa todos los mangas.
    Si falta la portada en caché (file_id), la descarga y la guarda.
    Requiere DUMP_CHANNEL para generar file_id sin molestar al usuario.
    """
    print(f"🔥 Iniciando Warmer de Portadas... (Manual: {single_run})")
    if not dump_chat_id:
        print("⚠️ Warmer: No DUMP_CHAT_ID. Solo validará URLs.")
    
    total_processed = 0

    while True:
        try:
            mangas = await get_all_mangas_paginated()
            if not mangas:
                if single_run: return 0
                await asyncio.sleep(60)
                continue
            
            processed = 0
            for m in mangas:
                mid = m['id']
                title = m['title']
                
                # Check cache
                cached = await get_cached_file(f"manga_{mid}", "cover_id")
                if cached: continue # Ya tenemos portada lista
                
                # Falta cachear.
                print(f"🔥 Warmer: Procesando portada para {title}")
                
                # Obtener URL (con fallback si hace falta)
                cover_url = m.get('cover')
                if not cover_url or not "http" in cover_url:
                     # Intentar deep search (chapter 1)
                     try:
                        chaps = await get_manga_chapters(mid)
                        if chaps and chaps[0].get('original'):
                            cover_url = chaps[0]['original'][0]
                     except: pass
                
                if cover_url and "http" in cover_url:
                    # Descargar y cachear
                    try:
                        async with aiohttp.ClientSession() as session:
                             async with session.get(cover_url) as resp:
                                 if resp.status == 200:
                                     data = await resp.read()
                                     photo = BytesIO(data)
                                     photo.name = "cover.jpg"
                                     
                                     if dump_chat_id:
                                         # Enviar a canal dump para generar ID permanente
                                         msg = await app.send_photo(dump_chat_id, photo, caption=f"Cover: {title}\nID: {mid}")
                                         if msg.photo:
                                             await save_cached_file(f"manga_{mid}", "cover_id", msg.photo.file_id)
                                             print(f"✅ Warmer: Cacheado {title}")
                                         processed += 1
                                         total_processed += 1
                                         await asyncio.sleep(5) # Delay anti-flood
                    except Exception as e:
                        print(f"❌ Warmer Error {title}: {e}")
                
                await asyncio.sleep(1) # Pequeño respiro entre chequeos
            
            if single_run:
                # Si es manual, terminamos tras una ronda completa
                return total_processed

            if processed == 0:
                # Si no hubo nada nuevo, dormir largo
                await asyncio.sleep(3600) # 1 hora
            else:
                await asyncio.sleep(60) # 1 minuto tras ronda activa
                
        except Exception as e:
            print(f"⚠️ Warmer Crash loop: {e}")
            if single_run: return total_processed
            await asyncio.sleep(60)
# --- BACKUP LOGIC (ZIP MASTER) ---


async def download_images_parallel(chapters, base_tmp, quality='original'):
    """Helper interno para descargar todas las imágenes de un manga."""
    img_queue = []
    use_source = 'webp' if quality == 'webp' else 'original'
    
    for ch in chapters:
        ch_safe = "".join([c for c in ch['title'] if c.isalnum() or c in " -_"]).strip()
        ch_dir = os.path.join(base_tmp, ch_safe)
        os.makedirs(ch_dir, exist_ok=True)
        
        src_list = ch[use_source]
        if not src_list and use_source == 'original': src_list = ch['webp']
        
        for idx, url in enumerate(src_list):
            ext = url.split('?')[0].split('.')[-1].lower()
            if len(ext) > 4: ext = 'jpg'
            fname = f"{idx+1:03d}.{ext}"
            dest_path = os.path.join(ch_dir, fname)
            img_queue.append((url, dest_path))
            
    if not img_queue: return False
    
    # Download Optimized
    async with aiohttp.ClientSession() as session:
        total = len(img_queue)
        # Backup puede ser un poco más agresivo que usuario normal, pero mantenemos cautela
        batch_size = 10 
        
        for i in range(0, total, batch_size):
            batch = img_queue[i:i+batch_size]
            tasks = []
            for url, path in batch:
                 # Reusamos la función optimizada
                 tasks.append(download_image(session, url, path))
            
            await asyncio.gather(*tasks)
            await asyncio.sleep(0.5) 
            
    return True

async def create_zip_from_folder(base_tmp, output_path):
    """Crea un ZIP de la carpeta dada."""
    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(base_tmp):
                for file in files:
                    abs_path = os.path.join(root, file)
                    arc_name = os.path.relpath(abs_path, base_tmp)
                    zipf.write(abs_path, arc_name)
        return True
    except: return False

async def ensure_backup_exists(client, manga_id, backup_id, status_callback=None):
    """
    Verifica si existe el ZIP Maestro en cache. Si no, lo crea y sube.
    Retorna: (file_id, was_new)
    """
    # 1. Check Cache
    cached_zip = await get_cached_file(f"manga_{manga_id}", "zip_master")
    if cached_zip:
        if status_callback: await status_callback("✅ Ya existe en respaldo.")
        return cached_zip, False

    if status_callback: await status_callback("⬇️ Descargando imágenes...")
    
    # 2. Download
    meta = await get_manga_metadata(manga_id)
    if not meta: return None, False
    
    chapters = await get_manga_chapters(manga_id)
    if not chapters: return None, False
    
    import time
    timestamp = int(time.time())
    base_tmp = os.path.join(DATA_DIR, f"bkp_{manga_id}_{timestamp}")
    os.makedirs(base_tmp, exist_ok=True)
    
    try:
        success = await download_images_parallel(chapters, base_tmp)
        if not success: return None, False
        
        if status_callback: await status_callback("📦 Comprimiendo ZIP Maestro...")
        
        # 3. Zip
        zip_path = os.path.join(DATA_DIR, f"MASTER_{meta['title']}.zip")
        if await create_zip_from_folder(base_tmp, zip_path):
            
            if status_callback: await status_callback("📤 Subiendo a Respaldo...")
            # 4. Upload
            cap = f"📦 **BACKUP MASTER**\n📚 {meta['title']}\n🆔 `{manga_id}`"
            msg = await client.send_document(backup_id, zip_path, caption=cap)
            
            fid = msg.document.file_id
            
            # 5. Save Cache
            await save_cached_file(f"manga_{manga_id}", "zip_master", fid, meta={'title': meta['title']})
            
            try: os.remove(zip_path)
            except: pass
            
            return fid, True
            
    except Exception as e:
        print(f"Backup Error: {e}")
        return None, False
    finally:
        try: shutil.rmtree(base_tmp)
        except: pass
    
    return None, False
