import os
import time
import logging
import asyncio
import requests
import base64
from dotenv import load_dotenv
from telethon import TelegramClient, events, Button
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# Cargar variables de entorno
load_dotenv()

# --- SERVIDOR WEB FANTASMA (Para Hugging Face) ---
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        html_content = b"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Twisted Streaming Brody</title>
    <style>
        body { margin: 0; padding: 0; background-color: #0a0a0a; display: flex; justify-content: center; align-items: center; height: 100vh; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .btn { background-color: #2481cc; color: white; padding: 15px 35px; border-radius: 30px; text-decoration: none; font-size: 20px; font-weight: bold; box-shadow: 0 5px 15px rgba(36,129,204,0.4); transition: 0.3s; }
        .btn:hover { transform: translateY(-3px); background-color: #1a629c; box-shadow: 0 8px 20px rgba(36,129,204,0.6); }
    </style>
</head>
<body>
    <a href="https://t.me/TwistedStreamingBrodybot" target="_blank" class="btn">\xF0\x9F\x9A\x80 Abrir Twisted Streaming Brody</a>
</body>
</html>"""
        self.wfile.write(html_content)
    def log_message(self, format, *args):
        pass # Silenciar logs del servidor

def run_server():
    try:
        server = HTTPServer(('0.0.0.0', 7860), DummyHandler)
        server.serve_forever()
    except Exception as e:
        print("Error en servidor web:", e)

Thread(target=run_server, daemon=True).start()

API_ID = int(os.getenv('TELEGRAM_API_ID'))
API_HASH = os.getenv('TELEGRAM_API_HASH')
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = int(os.getenv('TELEGRAM_CHANNEL_ID'))
IMGBB_KEY = os.getenv('IMGBB_API_KEY')

# Nombre del archivo de sesión
SESSION_NAME = 'TwistedStreamingBrodybot'

# --- CONFIGURACIÓN DE FIREBASE ---
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase-credentials.json")
        app = firebase_admin.initialize_app(cred)
        print(f"📁 Firebase conectado correctamente. Proyecto: {app.project_id}")
    db = firestore.client()
except Exception as e:
    print(f"📁 Error al conectar con Firebase: {e}")

# Logs
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Inicializar Cliente de Telethon
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# --- FUNCIONES AUXILIARES ---

async def upload_to_imgbb(photo_source):
    """Sube una imagen a ImgBB y devuelve la URL"""
    try:
        # Descargar la foto en memoria
        path = await client.download_media(photo_source, file=bytes)
        image_base64 = base64.b64encode(path)
        
        url = "https://api.imgbb.com/1/upload"
        payload = {"key": IMGBB_KEY, "image": image_base64}
        
        response = requests.post(url, payload)
        res_json = response.json()
        if res_json['success']:
            return res_json['data']['url']
    except Exception as e:
        print(f"Error ImgBB: {e}")
    return None

import re

def extract_categories_from_title(title):
    """Extrae categorías de un título como [Accion] El Guerrero (2024)"""
    found = re.findall(r'\[(.*?)\]|\((.*?)\)|\{(.*?)\}|\|(.*?)\|', title)
    categories = []
    for match in found:
        for item in match:
            if item and len(item.strip()) > 1:
                categories.append(item.strip())
    return list(set(categories))

def get_or_create_categories(names):
    """Busca o crea categorías por nombre y devuelve sus IDs"""
    ids = []
    for name in names:
        try:
            # Buscar si ya existe
            cats = db.collection('categories').where(filter=FieldFilter('name', '==', name)).get()
            if cats:
                ids.append(cats[0].id)
            else:
                # Crear si no existe
                _, doc_ref = db.collection('categories').add({
                    "name": name,
                    "type": "genre"
                })
                ids.append(doc_ref.id)
                print(f"🆕 Categoría creada: {name}")
        except Exception as e:
            print(f"Error gestionando categoría {name}: {e}")
    return ids

def get_all_categories():
    try:
        cats = db.collection('categories').get()
        return [{"id": c.id, "name": c.to_dict().get('name', 'Sin nombre')} for c in cats]
    except Exception:
        return []

import uuid

class CancelUploadException(Exception):
    pass

class EditorJumpException(Exception):
    def __init__(self, jump_id):
        self.jump_id = jump_id

async def wait_for_message_or_callback(conv, timeout=300):
    client = conv._client
    chat_id = conv.chat_id
    future = asyncio.Future()

    async def msg_handler(e):
        if not future.done():
            future.set_result(e)

    async def cb_handler(e):
        if not future.done():
            future.set_result(e)

    client.add_event_handler(msg_handler, events.NewMessage(chats=chat_id, incoming=True))
    client.add_event_handler(cb_handler, events.CallbackQuery(chats=chat_id))

    try:
        event = await asyncio.wait_for(future, timeout=timeout)
        txt = getattr(event, 'raw_text', getattr(event, 'text', '')).strip()
        
        if txt == '/cancelar':
            await client.send_message(chat_id, "📁 **Proceso cancelado.**")
            raise CancelUploadException()
            
        # Global intercept for editor mode jumps
        if editor_mode_active.get(chat_id, False):
            if txt.startswith('/start '):
                extracted = txt.replace('/start ', '').replace('folder_', '').strip()
                raise EditorJumpException(extracted)
            elif len(txt) == 20 and txt.isalnum() and not txt.startswith('/'):
                # Heuristic for Firebase ID jump
                raise EditorJumpException(txt)
                
        return event
    finally:
        client.remove_event_handler(msg_handler)
        client.remove_event_handler(cb_handler)

async def get_input_or_skip(conv, text, can_skip=True):
    """Espera un mensaje o un botón de omitir con IDs únicos para evitar bugs"""
    uid = str(uuid.uuid4()).encode()
    buttons = [Button.inline("📁 Omitir", uid)] if can_skip else None
    msg = await conv.send_message(text, buttons=buttons)
    
    try:
        while True:
            event = await wait_for_message_or_callback(conv, timeout=300)
            if isinstance(event, events.CallbackQuery.Event):
                if event.data == uid:
                    await event.answer("Omitido")
                    await msg.edit(text + " (Omitido)", buttons=None)
                    return None
                else:
                    await event.answer("Este botón ya no es válido", alert=True)
            else:
                if buttons:
                    await msg.edit(text, buttons=None)
                return event
    except asyncio.TimeoutError:
        await conv.send_message("📁 Tiempo de espera agotado. Proceso cancelado.")
        return None
    except Exception as e:
        print(f"Error en get_input_or_skip: {e}")
        return None

# --- MANEJADORES ---

# --- MODO BUSCADOR ---
@client.on(events.NewMessage(pattern='^/buscador_on$'))
async def enable_search_mode(event):
    chat_id = event.chat_id
    
    # Desactivar editor y cancelar subidas
    editor_mode_active[chat_id] = False
    if chat_id in active_tasks:
        for t in active_tasks[chat_id]:
            t.cancel()
        del active_tasks[chat_id]
        
    search_mode_active[chat_id] = True
    await event.respond("🔍 **Modo Buscador Activado**\n\nAhora puedes buscar enviando el título de una película, serie o capítulo. También puedes pegar enlaces directos o IDs.\n\nEnvía /buscador_off para salir.")

@client.on(events.NewMessage(pattern='^/buscador_off$'))
async def disable_search_mode(event):
    chat_id = event.chat_id
    search_mode_active[chat_id] = False
    await event.respond("❌ **Modo Buscador Desactivado**.")

@client.on(events.NewMessage(func=lambda e: not e.text.startswith('/') and len(e.text) != 20))
async def handle_text_search(event):
    chat_id = event.chat_id
    if not search_mode_active.get(chat_id, False):
        return
    if editor_mode_active.get(chat_id, False):
        return
        
    query = event.raw_text.strip().lower()
    if not query: return
    
    msg = await event.respond("🔍 Buscando...")
    
    # Buscar en Firestore (limitado en memoria por diseño simple de Firebase)
    docs = db.collection('videos').get()
    
    matched_docs = []
    for d in docs:
        data = d.to_dict()
        title = data.get('title', '').lower()
        if query in title:
            matched_docs.append((d.id, data))
            
    if not matched_docs:
        await msg.edit("❌ No se encontraron resultados para tu búsqueda.")
        return

    # Buscar si hay alguna coincidencia EXACTA (para evitar que "Capítulo 1" muestre el "10", "11", etc.)
    exact_matches = [m for m in matched_docs if m[1].get('title', '').lower() == query]
    if len(exact_matches) == 1:
        matched_docs = exact_matches

    # Si hay exactamente 1 resultado, lo enviamos directamente
    if len(matched_docs) == 1:
        doc_id, data = matched_docs[0]
        class DummyEvent:
            def __init__(self, chat_id, raw_text):
                self.chat_id = chat_id
                self.raw_text = raw_text
            async def respond(self, *args, **kwargs):
                return await client.send_message(self.chat_id, *args, **kwargs)
                
        dummy = DummyEvent(event.chat_id, doc_id)
        await msg.delete()
        await handle_document_id(dummy)
        return

    # Si hay múltiples, filtramos para dar prioridad a las Carpetas (Series) y Películas
    # Esto evita mostrar una lista gigante de subcapítulos
    folders_and_movies = []
    chapters = []
    
    for r_id, data in matched_docs:
        if data.get('section') == 'peliculas' or data.get('is_folder'):
            folders_and_movies.append((r_id, data))
        else:
            chapters.append((r_id, data))
            
    # Mostrar carpetas/pelis si hay, sino mostrar capítulos sueltos
    results = folders_and_movies if folders_and_movies else chapters

    # Mostrar resultados en botones
    results = results[:20] # Limitar a 20 resultados para no exceder limite de botones
    buttons = []
    for r_id, data in results:
        t = data.get('title', 'Sin titulo')[:40]
        icon = "🎬" if data.get('section') == 'peliculas' else ("📺" if data.get('is_folder') else "🎞️")
        buttons.append([Button.inline(f"{icon} {t}", f"get_vid_{r_id}".encode('utf-8'))])
        
    await msg.edit(f"📌 **Resultados para:** `{query}`", buttons=buttons)

@client.on(events.CallbackQuery(pattern=b'^get_vid_'))
async def handle_search_result_click(event):
    if not search_mode_active.get(event.chat_id, False):
        await event.answer("El modo buscador está desactivado.", alert=True)
        return
        
    doc_id = event.data.decode('utf-8').replace('get_vid_', '')
    await event.answer()
    
    # Simulamos como si el usuario hubiera enviado el ID directamente
    class DummyEvent:
        def __init__(self, chat_id, raw_text):
            self.chat_id = chat_id
            self.raw_text = raw_text
        async def respond(self, *args, **kwargs):
            return await client.send_message(self.chat_id, *args, **kwargs)
            
    dummy = DummyEvent(event.chat_id, doc_id)
    await handle_document_id(dummy)

# --------------------------


active_tasks = {}
editor_mode_active = {}
search_mode_active = {}

@client.on(events.NewMessage(pattern='/(start|subir|subir_pelicula|subir_serie)$'))
async def start_subir_handler(event):
    chat_id = event.chat_id
    if editor_mode_active.get(chat_id, False):
        await event.respond("🛠️ **Estás en Modo Editor.**\nPor favor, usa `/desactivar_modo_editor` para salir del editor y usar los comandos normales.")
        return
    
    if chat_id not in active_tasks:
        active_tasks[chat_id] = []
        
    current_task = asyncio.current_task()
    current_task.is_uploading = False
    
    remaining_tasks = []
    for old_task in active_tasks[chat_id]:
        if not old_task.done():
            if getattr(old_task, 'is_uploading', False):
                remaining_tasks.append(old_task)
            else:
                old_task.cancel()
                try:
                    await asyncio.sleep(0.1)
                except: pass
                
    active_tasks[chat_id] = remaining_tasks
    active_tasks[chat_id].append(current_task)
    
    try:
        async with client.conversation(chat_id, timeout=600, exclusive=False) as conv:
            try:
                cmd = event.text.strip().lower()
                
                if cmd == '/subir_pelicula':
                    await handle_movie_upload(conv)
                    return
                elif cmd == '/subir_serie':
                    await handle_series_upload(conv)
                    return

                msg_text = "📁 Bienvenido a **Twisted Streaming Brody**.\nElige una opción:"
                botones = [
                    [Button.inline("📁 Subir Película", b"type_movie"), Button.inline("📁 Subir Serie", b"type_series")]
                ]
                
                if cmd == '/start':
                    photos = await client.get_profile_photos('me', limit=1)
                    if photos:
                        msg = await conv.send_message(msg_text, file=photos[0], buttons=botones)
                    else:
                        msg = await conv.send_message(msg_text, buttons=botones)
                else:
                    msg = await conv.send_message(msg_text, buttons=botones)
                    
                while True:
                    press = await wait_for_message_or_callback(conv, timeout=3600)
                    if isinstance(press, events.CallbackQuery.Event):
                        if press.data in [b"type_movie", b"type_series"]:
                            await press.answer()
                            try:
                                await msg.edit(buttons=None)
                            except: pass
                            
                            if press.data == b"type_movie":
                                await handle_movie_upload(conv)
                            elif press.data == b"type_series":
                                await handle_series_upload(conv)
                            break
                        else:
                            await press.answer("Botón expirado", alert=True)
                    elif getattr(press, 'text', '') in ['/start', '/subir', '/subir_pelicula', '/subir_serie']:
                        # El usuario envió otro comando, dejamos que el nuevo handler lo tome
                        break
            except CancelUploadException:
                pass
            except asyncio.CancelledError:
                pass
    finally:
        if current_task in active_tasks.get(chat_id, []):
            active_tasks[chat_id].remove(current_task)
            if not active_tasks[chat_id]:
                del active_tasks[chat_id]

async def handle_movie_upload(conv):
    # 1. Video
    await conv.send_message("📁 **Paso 1:** Envía el **video** (o el archivo) de la película:")
    msg_video = await conv.get_response()
    
    is_video = False
    if msg_video and getattr(msg_video, 'media', None):
        if getattr(msg_video, 'video', None):
            is_video = True
        elif getattr(msg_video, 'document', None):
            mime = getattr(msg_video.file, 'mime_type', '') if hasattr(msg_video, 'file') else ''
            if mime.startswith('video/'):
                is_video = True
            else:
                for attr in msg_video.document.attributes:
                    if hasattr(attr, 'file_name'):
                        import os
                        ext = os.path.splitext(attr.file_name)[1].lower()
                        if ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.ts', '.m4v']:
                            is_video = True
                        break

    if not is_video:
        await conv.send_message("📁 No enviaste un video válido. Debes enviar un video normal o un archivo de video (documento). Las imágenes no son aceptadas. Abortando proceso.")
        print("📁 Intento de subida fallido: No se recibió un video o documento válido.")
        return

    doc_name = ""
    video_caption = msg_video.raw_text if getattr(msg_video, 'raw_text', None) else ""
    if hasattr(msg_video.media, 'document'):
        for attr in msg_video.media.document.attributes:
            if hasattr(attr, 'file_name'):
                import os
                doc_name = os.path.splitext(attr.file_name)[0]
                break

    # 2. Título
    uid_title = str(uuid.uuid4()).encode()
    buttons_title = []
    if doc_name:
        buttons_title.append([Button.inline(f"📁 Usar nombre del archivo: {doc_name[:30]}", uid_title)])
    
    msg_t = await conv.send_message("📁 **Paso 2:** Escribe el **Título** de la película:", buttons=buttons_title if buttons_title else None)
    title = ""
    while True:
        event = await wait_for_message_or_callback(conv, timeout=300)
        if isinstance(event, events.CallbackQuery.Event):
            if doc_name and event.data == uid_title:
                await event.answer("Título seleccionado")
                title = doc_name
                await msg_t.edit(f"📁 Título: **{title}**", buttons=None)
                break
            else:
                await event.answer("Botón expirado", alert=True)
        else:
            title = event.raw_text
            if buttons_title:
                await msg_t.edit(buttons=None)
            break

    print(f"📁 Iniciando carga de película: {title}")

    # 3. Descripción
    uid_desc = str(uuid.uuid4()).encode()
    uid_skip = str(uuid.uuid4()).encode()
    buttons_desc = []
    if video_caption:
        buttons_desc.append([Button.inline("📁 Usar descripción del video", uid_desc)])
    buttons_desc.append([Button.inline("📁 Omitir", uid_skip)])

    msg_d = await conv.send_message("📁 **Paso 3:** Escribe la **Descripción**:", buttons=buttons_desc)
    description = ""
    while True:
        event = await wait_for_message_or_callback(conv, timeout=300)
        if isinstance(event, events.CallbackQuery.Event):
            if video_caption and event.data == uid_desc:
                await event.answer("Descripción seleccionada")
                description = video_caption
                await msg_d.edit("📁 Descripción obtenida del video.", buttons=None)
                break
            elif event.data == uid_skip:
                await event.answer("Omitido")
                description = ""
                await msg_d.edit("📁 Descripción: (Omitida)", buttons=None)
                break
            else:
                await event.answer("Botón expirado", alert=True)
        else:
            description = event.raw_text
            await msg_d.edit(buttons=None)
            break

    # 4. Portada
    cover_url = ""
    while True:
        resp_cover = await get_input_or_skip(conv, "📁 **Paso 4:** Envía la **Portada** (solo como imagen):")
        if not resp_cover:
            break
        if resp_cover.photo:
            cover_url = await upload_to_imgbb(resp_cover.photo)
            break
        else:
            await conv.send_message("📁 Por favor, envía una IMAGEN, no un texto ni un link.")

    async def progress_callback(current, total):
        porcentaje = (current / total) * 100
        print(f"  ⬆️ Subiendo: {porcentaje:.1f}% ({current}/{total} bytes)")

    print(f"📦 Video recibido. Tamaño estimado: {getattr(msg_video.file, 'size', 'desconocido')} bytes")
    status_msg = await conv.send_message("📁 **Subiendo video al canal...** (Mira la consola para ver el progreso)")
    
    try:
        asyncio.current_task().is_uploading = True
        # Formatear el mensaje para el canal
        caption = f"**Twisted Streaming Brody Data**\n\n📁 **Película:** {title}\n📁 {description}"
        
        print(f"📤 Enviando al canal {CHANNEL_ID}...")
        
        if resp_cover and getattr(resp_cover, 'photo', None):
            try:
                await client.send_file(CHANNEL_ID, resp_cover.photo, caption=f"📁 **Portada Película:** {title}")
            except Exception as e:
                print(f"Error enviando portada de película al canal: {e}")
                
        sent_to_channel = await client.send_file(
            CHANNEL_ID, 
            msg_video.media, 
            caption=caption,
            progress_callback=progress_callback
        )
        
        print(f"📁 Enviado al canal. ID: {sent_to_channel.id}")
        clean_channel_id = str(CHANNEL_ID).replace("-100", "")
        file_url = f"https://t.me/c/{clean_channel_id}/{sent_to_channel.id}"

        print("🗄️ Guardando en Firebase...")
        # Guardar en Firestore con todos los campos observados en tu consola
        db.collection('videos').add({
            "title": title, 
            "description": description, 
            "section": "peliculas",
            "is_folder": False, 
            "folder_id": "", # Sin nulls para evitar errores en React
            "video_url": file_url, 
            "telegram_file_id": str(sent_to_channel.id),
            "thumbnail_url": "", 
            "cover_url": cover_url, 
            "thumbnail_position": "50% center",
            "episode": 0,
            "views": 0,
            "rating": 0,
            "categories": [], 
            "servers": [file_url],
            "status": "active",
            "is_public": True,
            "created_at": firestore.SERVER_TIMESTAMP, 
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        print("🎉 Guardado en Firebase exitoso.")
        await status_msg.edit("📁 **¡Película registrada y enviada correctamente!**")
    except Exception as e:
        print(f"📁 ERROR CRÍTICO: {e}")
        await status_msg.edit(f"📁 **Error al procesar:** {e}")

async def handle_series_upload(conv):
    series_title = ""
    videos = []
    naming_strategy = "title"
    manual_prefix = ""
    desc_strategy = "manual"
    desc_text = ""
    cover_url = ""
    resp_cover = None

    step = 1
    while step <= 4:
        if step == 1:
            await conv.send_message("📁 **Paso 1:** Escribe el título general de la Serie (`Ej: The Last of Us, Breaking Bad, Invencible, etc.`):")
            while True:
                title_msg = await wait_for_message_or_callback(conv, timeout=300)
                if isinstance(title_msg, events.CallbackQuery.Event):
                    await title_msg.answer("Por favor, escribe un texto.", alert=True)
                elif getattr(title_msg, 'raw_text', getattr(title_msg, 'text', None)):
                    series_title = getattr(title_msg, 'raw_text', title_msg.text)
                    step = 2
                    break
                    
        elif step == 2:
            uid_done = str(uuid.uuid4()).encode()
            uid_back = str(uuid.uuid4()).encode()
            msg_v = await conv.send_message(
                f"📁 **Paso 2:** Envía los videos de los capítulos. Puedes enviar varios de una vez.\n\n"
                f"Esperando a más videos... ({len(videos)} recibidos)",
                buttons=[
                    [Button.inline("📁 Terminar y confirmar", uid_done)],
                    [Button.inline("⬅️ Atrás (Editar Título)", uid_back)]
                ]
            )
            
            debounce_task = None
            async def update_button():
                await asyncio.sleep(0.8)
                nonlocal msg_v
                try:
                    await msg_v.delete()
                except Exception:
                    pass
                msg_v = await conv.send_message(
                    f"📁 **Paso 2:** Envía los videos de los capítulos.\n\n"
                    f"Esperando a más videos... ({len(videos)} recibidos)",
                    buttons=[
                        [Button.inline("📁 Terminar y confirmar", uid_done)],
                        [Button.inline("⬅️ Atrás (Editar Título)", uid_back)]
                    ]
                )

            async def video_receiver(e):
                is_video = False
                if getattr(e, 'media', None):
                    if getattr(e, 'video', None):
                        is_video = True
                    elif getattr(e, 'document', None):
                        mime = getattr(e.file, 'mime_type', '') if hasattr(e, 'file') else ''
                        if mime.startswith('video/'):
                            is_video = True
                        else:
                            for attr in e.document.attributes:
                                if hasattr(attr, 'file_name'):
                                    import os
                                    ext = os.path.splitext(attr.file_name)[1].lower()
                                    if ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.ts', '.m4v']:
                                        is_video = True
                                    break
                                    
                if is_video:
                    videos.append(e)
                    nonlocal debounce_task
                    if debounce_task:
                        debounce_task.cancel()
                    debounce_task = asyncio.create_task(update_button())

            client.add_event_handler(video_receiver, events.NewMessage(chats=conv.chat_id, incoming=True))
            
            try:
                while True:
                    event = await wait_for_message_or_callback(conv, timeout=3600)
                    if isinstance(event, events.CallbackQuery.Event):
                        if event.data == uid_done:
                            if not videos:
                                await event.answer("No has enviado ningún video aún.", alert=True)
                            else:
                                await event.answer("Videos confirmados")
                                if debounce_task:
                                    debounce_task.cancel()
                                await msg_v.edit(f"📁 Se registraron {len(videos)} videos en total.", buttons=None)
                                step = 3
                                break
                        elif event.data == uid_back:
                            await event.answer("Volviendo atrás")
                            if debounce_task:
                                debounce_task.cancel()
                            await msg_v.edit("📁 Volviendo al Paso 1...", buttons=None)
                            step = 1
                            break
            finally:
                client.remove_event_handler(video_receiver, events.NewMessage(chats=conv.chat_id, incoming=True))
                
        elif step == 3:
            uid_title = str(uuid.uuid4()).encode()
            uid_file = str(uuid.uuid4()).encode()
            uid_back = str(uuid.uuid4()).encode()
            
            sample_names = ""
            for v in videos[:2]:
                doc_name = "Video_desconocido.mp4"
                if hasattr(v.media, 'document'):
                    for attr in v.media.document.attributes:
                        if hasattr(attr, 'file_name'):
                            doc_name = attr.file_name
                            break
                sample_names += f"- {doc_name}\n"
                
            msg_n = await conv.send_message(
                "📁 **Paso 3:** ¿Qué nombre llevarán los capítulos?\n\n"
                "Escribe un nombre base y se enumerarán automáticamente.\n\n"
                f"Por ejemplo, si escribes un nombre o usas el botón **Usar nombre del título general** (`{series_title}`), se nombrarán así:\n"
                f"- {series_title} - Capítulo 1\n"
                f"- {series_title} - Capítulo 2\n"
                f"- {series_title} - Capítulo 3\n\n"
                "Si usas el botón **Usar nombres originales de los archivos**, se usarán los nombres reales que acabas de subir:\n"
                f"{sample_names}\n"
                "Elige un atajo rápido o escribe tu propio nombre base:",
                buttons=[
                    [Button.inline("📁 Usar nombre del título general", uid_title)],
                    [Button.inline("📁 Usar nombres originales de los archivos", uid_file)],
                    [Button.inline("⬅️ Atrás (Añadir más videos)", uid_back)]
                ]
            )
            
            while True:
                event = await wait_for_message_or_callback(conv, timeout=300)
                if isinstance(event, events.CallbackQuery.Event):
                    if event.data == uid_title:
                        naming_strategy = "title"
                        await msg_n.edit(f"📁 Formato: **{series_title} - Capítulo X**", buttons=None)
                        step = 3.5
                        break
                    elif event.data == uid_file:
                        naming_strategy = "file"
                        await msg_n.edit("📁 Formato: **Nombres originales de los archivos**", buttons=None)
                        step = 3.5
                        break
                    elif event.data == uid_back:
                        await event.answer("Volviendo atrás")
                        await msg_n.edit("📁 Volviendo al Paso 2...", buttons=None)
                        step = 2
                        break
                    else:
                        await event.answer("Botón expirado", alert=True)
                else:
                    naming_strategy = "manual"
                    manual_prefix = event.raw_text.strip()
                    await msg_n.edit(f"📁 Formato Manual: **{manual_prefix} - Capítulo 1, ...**", buttons=None)
                    step = 3.5
                    break
                    
        elif step == 3.5:
            uid_desc_video = str(uuid.uuid4()).encode()
            uid_skip = str(uuid.uuid4()).encode()
            uid_back = str(uuid.uuid4()).encode()
            msg_d = await conv.send_message(
                "📁 **Paso 3.5:** Escribe una **Descripción** (se usará la misma para todos los capítulos).\n\n"
                "Opcional: puedes extraer la descripción original de cada video, o simplemente omitir este paso.",
                buttons=[
                    [Button.inline("📁 Usar descripción de cada video", uid_desc_video)],
                    [Button.inline("📁 Omitir", uid_skip)],
                    [Button.inline("⬅️ Atrás (Editar Nombre Capítulos)", uid_back)]
                ]
            )
            
            while True:
                event = await wait_for_message_or_callback(conv, timeout=300)
                if isinstance(event, events.CallbackQuery.Event):
                    if event.data == uid_desc_video:
                        desc_strategy = "video"
                        await msg_d.edit("📁 Descripción: **Se usará la de cada video**", buttons=None)
                        step = 4
                        break
                    elif event.data == uid_skip:
                        desc_strategy = "skip"
                        await msg_d.edit("📁 Descripción: **(Omitida)**", buttons=None)
                        step = 4
                        break
                    elif event.data == uid_back:
                        await event.answer("Volviendo atrás")
                        await msg_d.edit("📁 Volviendo al Paso 3...", buttons=None)
                        step = 3
                        break
                    else:
                        await event.answer("Botón expirado", alert=True)
                else:
                    desc_strategy = "manual"
                    desc_text = event.raw_text
                    await msg_d.edit(f"📁 Descripción: **{desc_text[:30]}...**", buttons=None)
                    step = 4
                    break

        elif step == 4:
            uid_skip = str(uuid.uuid4()).encode()
            uid_back = str(uuid.uuid4()).encode()
            msg_c = await conv.send_message(
                "📁 **Paso 4:** Envía la **Portada** de la serie (solo como imagen):",
                buttons=[
                    [Button.inline("📁 Omitir", uid_skip)],
                    [Button.inline("⬅️ Atrás (Editar Descripción)", uid_back)]
                ]
            )
            
            while True:
                event = await wait_for_message_or_callback(conv, timeout=300)
                if isinstance(event, events.CallbackQuery.Event):
                    if event.data == uid_skip:
                        await event.answer("Omitido")
                        await msg_c.edit("📁 Portada: **(Omitida)**", buttons=None)
                        resp_cover = None
                        cover_url = ""
                        step = 5
                        break
                    elif event.data == uid_back:
                        await event.answer("Volviendo atrás")
                        await msg_c.edit("📁 Volviendo al Paso 3.5...", buttons=None)
                        step = 3.5
                        break
                    else:
                        await event.answer("Botón expirado", alert=True)
                elif getattr(event, 'photo', None):
                    await msg_c.edit("📁 Subiendo portada...", buttons=None)
                    cover_url = await upload_to_imgbb(event.photo)
                    resp_cover = event
                    step = 5
                    break
                else:
                    await conv.send_message("📁 Por favor, envía una IMAGEN, o presiona Omitir/Atrás.")

    # 5. Guardado en Firebase y reenvío
    status_msg = await conv.send_message("📁 **Procesando y subiendo los capítulos...**")
    try:
        asyncio.current_task().is_uploading = True
        if resp_cover and getattr(resp_cover, 'photo', None):
            try:
                await client.send_file(CHANNEL_ID, resp_cover.photo, caption=f"📁 **Portada Serie:** {series_title}")
            except Exception as e:
                print(f"Error enviando portada de serie al canal: {e}")

        # Buscar serie existente para asegurar nombre único
        original_title = series_title
        counter = 1
        
        while True:
            series_query = db.collection('videos').where(filter=FieldFilter('is_folder', '==', True)).where(filter=FieldFilter('title', '==', series_title)).get()
            if series_query:
                counter += 1
                series_title = f"{original_title} {counter}"
            else:
                break

        _, doc_ref = db.collection('videos').add({
            "title": series_title, 
            "section": "series", 
            "is_folder": True,
            "thumbnail_url": cover_url, 
            "categories": [],
            "created_at": firestore.SERVER_TIMESTAMP, 
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        series_id = doc_ref.id

        for i, video_msg in enumerate(videos):
            current_num = i + 1
            
            # Nombre
            if naming_strategy == "title":
                ep_title = f"{series_title} - Capítulo {i+1}"
            elif naming_strategy == "manual":
                ep_title = f"{manual_prefix} - Capítulo {i+1}"
            else:
                doc_name = "Episodio"
                if hasattr(video_msg.media, 'document'):
                    for attr in video_msg.media.document.attributes:
                        if hasattr(attr, 'file_name'):
                            import os
                            doc_name = os.path.splitext(attr.file_name)[0]
                            break
                ep_title = doc_name

            # Descripción
            if desc_strategy == "video":
                ep_desc = video_msg.raw_text if getattr(video_msg, 'raw_text', None) else ""
            elif desc_strategy == "skip":
                ep_desc = ""
            else:
                ep_desc = desc_text

            await status_msg.edit(f"📁 Subiendo: **{ep_title}** ({i+1}/{len(videos)})")

            caption = f"**Twisted Streaming Brody Data**\n\n📁 **Serie:** {series_title}\n📁 **Episodio:** {ep_title}"
            if ep_desc:
                caption += f"\n📁 {ep_desc}"
            
            sent_to_channel = await client.send_file(CHANNEL_ID, video_msg.media, caption=caption)
            clean_channel_id = str(CHANNEL_ID).replace("-100", "")
            file_url = f"https://t.me/c/{clean_channel_id}/{sent_to_channel.id}"

            db.collection('videos').add({
                "title": ep_title, 
                "section": "series",
                "is_folder": False, 
                "folder_id": series_id,
                "episode": current_num,
                "season": 1,
                "video_url": file_url, 
                "telegram_file_id": str(sent_to_channel.id),
                "description": ep_desc,
                "thumbnail_url": "",
                "cover_url": "",
                "views": 0,
                "rating": 0,
                "status": "active",
                "is_public": True,
                "categories": [],
                "servers": [file_url],
                "created_at": firestore.SERVER_TIMESTAMP, 
                "updated_at": firestore.SERVER_TIMESTAMP
            })

        await status_msg.edit(f"📁 **¡Completado! {len(videos)} capítulos de '{series_title}' se han subido con éxito.**")

    except Exception as e:
        print(f"📁 Error al procesar serie: {e}")
        await status_msg.edit(f"📁 **Error al subir los capítulos:** {e}")



# --- CONFIGURACIÓN Y FUNCIONES DE BÚSQUEDA POR ID ---

bot_settings = {
    "send_title": True,
    "send_description": True,
    "ask_series": True
}

try:
    doc_settings = db.collection('settings').document('delivery').get()
    if doc_settings.exists:
        s_data = doc_settings.to_dict()
        bot_settings['send_title'] = s_data.get('send_title', True)
        bot_settings['send_description'] = s_data.get('send_description', True)
        bot_settings['ask_series'] = s_data.get('ask_series', True)
except Exception as e:
    print(f"📁 Error cargando settings: {e}")

@client.on(events.NewMessage(pattern='/(settings|setting|config)$'))
async def settings_handler(event):
    await show_settings_menu(event)

async def show_settings_menu(event_or_query):
    title_status = "✅ PRENDIDO" if bot_settings['send_title'] else "❌ APAGADO"
    desc_status = "✅ PRENDIDO" if bot_settings['send_description'] else "❌ APAGADO"
    ask_status = "✅ PRENDIDO" if bot_settings['ask_series'] else "❌ APAGADO"
    
    botones = [
        [Button.inline(f"Título: {title_status}", b"toggle_title")],
        [Button.inline(f"Descripción: {desc_status}", b"toggle_desc")],
        [Button.inline(f"Preguntar Temporada/Capítulo: {ask_status}", b"toggle_ask")]
    ]
    
    text = "⚙️ **Configuración de Envío de Videos**\n\nElige cómo quieres que el bot entregue los videos:"
    
    if isinstance(event_or_query, events.CallbackQuery.Event):
        await event_or_query.edit(text, buttons=botones)
    else:
        await event_or_query.respond(text, buttons=botones)

from telethon.tl.types import KeyboardButtonWebView

@client.on(events.NewMessage(pattern='/(twistedstreamingbrodybot|app)$'))
async def miniapp_handler(event):
    # Usamos KeyboardButtonWebView para forzar a Telegram a abrirlo como Mini App
    botones = [[KeyboardButtonWebView(text="🍿 Abrir Catálogo", url="https://codebybrody-twistedstreamingbrody.hf.space")]]
        
    await event.respond(
        "🍿 **¡Twisted Streaming Brody!**\n\nToca el botón abajo para abrir nuestra Mini App y navegar por todas las películas y series directamente desde Telegram.",
        buttons=botones
    )

button_cooldowns = {}

@client.on(events.CallbackQuery(pattern=b'^toggle_(title|desc|ask)$'))
async def toggle_settings_handler(event):
    chat_id = event.chat_id
    now = time.time()
    if now - button_cooldowns.get(chat_id, 0) < 0.5:
        await event.answer()
        return
    button_cooldowns[chat_id] = now
    
    action = event.pattern_match.group(1).decode()
    if action == 'title':
        bot_settings['send_title'] = not bot_settings['send_title']
    elif action == 'desc':
        bot_settings['send_description'] = not bot_settings['send_description']
    elif action == 'ask':
        bot_settings['ask_series'] = not bot_settings['ask_series']
        
    try:
        db.collection('settings').document('delivery').set(bot_settings)
    except: pass
    
    await event.answer()
    await show_settings_menu(event)

async def send_movie(chat_id, file_id, data):
    cover = data.get('cover_url') or data.get('thumbnail_url')
    caption_parts = []
    if bot_settings['send_title'] and data.get('title'):
        caption_parts.append(f"📁 **{data.get('title')}**")
    if bot_settings['send_description'] and data.get('description'):
        caption_parts.append(f"{data.get('description')}")
    
    custom_caption = "\n\n".join(caption_parts)
    
    if cover:
        try:
            await client.send_file(chat_id, cover, caption=custom_caption)
        except Exception:
            if custom_caption: await client.send_message(chat_id, custom_caption)
    elif custom_caption:
        await client.send_message(chat_id, custom_caption)
    
    try:
        msg = await client.get_messages(CHANNEL_ID, ids=int(file_id))
        if msg and getattr(msg, 'media', None):
            await client.send_file(chat_id, msg.media, caption="")
        else:
            await client.send_message(chat_id, "📁 Video no encontrado en el canal.")
    except Exception as e:
        print("Error enviando película:", e)

async def send_series_cover(chat_id, folder_id):
    if not folder_id: return
    try:
        s_doc = db.collection('videos').document(folder_id).get()
        if s_doc.exists:
            s_data = s_doc.to_dict()
            cover = s_data.get('thumbnail_url') or s_data.get('cover_url')
            
            caption = ""
            if bot_settings['send_title'] and s_data.get('title'):
                caption = f"📁 **{s_data.get('title')}**"
                
            if cover:
                try:
                    await client.send_file(chat_id, cover, caption=caption)
                except Exception:
                    if caption: await client.send_message(chat_id, caption)
            elif caption:
                await client.send_message(chat_id, caption)
    except Exception as e:
        print("Error al enviar portada de serie:", e)

async def send_episode_video(chat_id, file_id, ep_data):
    try:
        msg = await client.get_messages(CHANNEL_ID, ids=int(file_id))
        if not msg or not getattr(msg, 'media', None):
            await client.send_message(chat_id, "📁 Capítulo no encontrado en el canal.")
            return

        caption_parts = []
        if bot_settings['send_title'] and ep_data.get('title'):
            caption_parts.append(f"📁 **{ep_data.get('title')}**")
        if bot_settings['send_description'] and ep_data.get('description'):
            caption_parts.append(f"{ep_data.get('description')}")
            
        custom_caption = "\n\n".join(caption_parts)
        await client.send_file(chat_id, msg.media, caption=custom_caption)
    except Exception as e:
        print("Error enviando capítulo:", e)

async def send_full_season(chat_id, folder_id, status_msg=None):
    if not status_msg:
        status_msg = await client.send_message(chat_id, "📁 Preparando los capítulos...")
    else:
        try:
            await status_msg.edit("📁 Preparando los capítulos...", buttons=None)
        except Exception:
            pass

    episodes = db.collection('videos').where(filter=FieldFilter('folder_id', '==', folder_id)).get()
    if not episodes:
        await status_msg.edit("📁 No se encontraron capítulos.")
        return
        
    await send_series_cover(chat_id, folder_id)
    
    episodes_sorted = sorted(episodes, key=lambda x: x.to_dict().get('episode', 0))
    for ep in episodes_sorted:
        data = ep.to_dict()
        file_id = data.get('telegram_file_id')
        if file_id:
            await send_episode_video(chat_id, file_id, data)
            await asyncio.sleep(0.5)
    await status_msg.edit("📁 **¡Temporada enviada!**")

@client.on(events.NewMessage(pattern=r'^/start (folder_)?[a-zA-Z0-9_-]{20}$'))
@client.on(events.NewMessage(pattern=r'^(folder/|folder_)?[a-zA-Z0-9_-]{20}$'))
async def handle_document_id(event):
    if editor_mode_active.get(event.chat_id, False):
        return
        
    if not search_mode_active.get(event.chat_id, False):
        return # Ignore links/IDs if search mode is OFF
        
    text = event.raw_text.strip()
    is_folder_request = False
    
    if text.startswith('/start '):
        payload = text.split(' ')[1]
        if payload.startswith('folder_'):
            is_folder_request = True
            doc_id = payload.replace('folder_', '', 1)
        else:
            doc_id = payload
    else:
        if text.startswith('folder/') or text.startswith('folder_'):
            is_folder_request = True
            doc_id = text.replace('folder/', '', 1).replace('folder_', '', 1)
        else:
            doc_id = text
    
    try:
        doc = db.collection('videos').document(doc_id).get()
        if not doc.exists:
            return
            
        data = doc.to_dict()
        section = data.get('section')
        is_folder = data.get('is_folder')
        
        if section == 'peliculas':
            file_id = data.get('telegram_file_id')
            if file_id:
                await send_movie(event.chat_id, file_id, data)
            else:
                await event.respond("📁 No se encontró el archivo en Telegram para esta película.")
                
        elif section == 'series':
            folder_id = doc_id if is_folder else data.get('folder_id')
            
            if is_folder_request:
                await send_full_season(event.chat_id, folder_id)
                return
            
            if not bot_settings.get('ask_series', True):
                if is_folder:
                    await send_full_season(event.chat_id, folder_id)
                else:
                    file_id = data.get('telegram_file_id')
                    if file_id:
                        await send_series_cover(event.chat_id, folder_id)
                        await send_episode_video(event.chat_id, file_id, data)
                    else:
                        await event.respond("📁 Archivo no encontrado.")
                return
            
            if is_folder:
                episodes = db.collection('videos').where(filter=FieldFilter('folder_id', '==', doc_id)).get()
                episodes_sorted = sorted(episodes, key=lambda x: x.to_dict().get('episode', 0))
                
                botones = []
                row = []
                for ep in episodes_sorted:
                    ep_data = ep.to_dict()
                    ep_num = ep_data.get('episode', '?')
                    ep_id = ep.id
                    row.append(Button.inline(f"Cap {ep_num}", f"this_cap_{ep_id}".encode()))
                    if len(row) == 3:
                        botones.append(row)
                        row = []
                if row:
                    botones.append(row)
                    
                botones.append([Button.inline("📁 Enviar Temporada Completa", f"all_caps_{doc_id}".encode())])
                
                await event.respond(f"📁 **Serie:** {data.get('title')}\nSelecciona un capítulo o envía la temporada completa:", buttons=botones)
            else:
                botones = [
                    [Button.inline("📁 Enviar solo este video", f"this_cap_{doc_id}".encode())],
                    [Button.inline("📁 Enviar Temporada Completa", f"all_caps_{folder_id}".encode())]
                ]
                await event.respond(f"📁 **Capítulo:** {data.get('title')}\n¿Qué deseas hacer?", buttons=botones)
                
    except Exception as e:
        print(f"Error buscando documento {doc_id}: {e}")

@client.on(events.CallbackQuery(pattern=b'^(this_cap_|all_caps_|choose_cap_)(.*)'))
async def handle_series_delivery(event):
    chat_id = event.chat_id
    now = time.time()
    if now - button_cooldowns.get(chat_id, 0) < 1.0:
        await event.answer("Procesando...", alert=False)
        return
    button_cooldowns[chat_id] = now
    
    action = event.pattern_match.group(1).decode()
    target_id = event.pattern_match.group(2).decode()
    
    try:
        if action == "this_cap_":
            await event.answer("📁 Enviando capítulo...", alert=False)
            doc = db.collection('videos').document(target_id).get()
            if doc.exists:
                data = doc.to_dict()
                file_id = data.get('telegram_file_id')
                folder_id = data.get('folder_id')
                if file_id:
                    await send_series_cover(event.chat_id, folder_id)
                    await send_episode_video(event.chat_id, file_id, data)
                else:
                    await event.respond("📁 Archivo no encontrado.")
                    
        elif action == "all_caps_":
            await event.answer("📁 Preparando temporada...", alert=False)
            await send_full_season(chat_id, target_id, status_msg=event)
            
        elif action == "choose_cap_":
            await event.answer("📁 Cargando capítulos...", alert=False)
            episodes = db.collection('videos').where(filter=FieldFilter('folder_id', '==', target_id)).get()
            if not episodes:
                await event.answer("No se encontraron capítulos.", alert=True)
                return
                
            episodes_sorted = sorted(episodes, key=lambda x: x.to_dict().get('episode', 0))
            
            botones = []
            row = []
            for ep in episodes_sorted:
                data = ep.to_dict()
                ep_num = data.get('episode', '?')
                ep_id = ep.id
                row.append(Button.inline(f"Cap {ep_num}", f"this_cap_{ep_id}".encode()))
                if len(row) == 3:
                    botones.append(row)
                    row = []
            if row:
                botones.append(row)
                
            await event.edit("📁 **Selecciona el capítulo:**", buttons=botones)
            
    except Exception as e:
        print(f"Error en delivery: {e}")
        await event.respond("📁 Hubo un error procesando la solicitud.")


# --- MODO EDITOR ---
@client.on(events.NewMessage(pattern='/(activar_modo_editor)$'))
async def enable_editor(event):
    import asyncio
    chat_id = event.chat_id
    
    # Cancel previous tasks to prevent "Botón expirado" background overlap
    if chat_id in active_tasks:
        for old_task in active_tasks[chat_id]:
            if not old_task.done():
                if not getattr(old_task, 'is_uploading', False):
                    old_task.cancel()
        try: await asyncio.sleep(0.1)
        except: pass
        
    current_task = asyncio.current_task()
    current_task.is_uploading = False
    
    if chat_id not in active_tasks:
        active_tasks[chat_id] = []
    active_tasks[chat_id].append(current_task)

    editor_mode_active[chat_id] = True
    try:
        await handle_editor_mode(event)
    finally:
        if current_task in active_tasks.get(chat_id, []):
            active_tasks[chat_id].remove(current_task)
            if not active_tasks[chat_id]:
                del active_tasks[chat_id]


@client.on(events.NewMessage(pattern='/(desactivar_modo_editor)$'))
async def disable_editor(event):
    chat_id = event.chat_id
    editor_mode_active[chat_id] = False
    await event.respond("✅ **Modo editor desactivado.** Ya puedes usar los comandos normales.")

async def process_editor_id(conv, txt):
    doc = db.collection('videos').document(txt).get()
    if doc.exists:
        data = doc.to_dict()
        if data.get('section') == 'peliculas':
            await handle_editor_movie_action(conv, txt)
        elif data.get('is_folder', False):
            await handle_editor_series_action(conv, txt)
        elif data.get('section') == 'series' and not data.get('is_folder', False):
            await handle_editor_single_chapter(conv, txt)
        else:
            await conv.send_message("❌ Tipo de documento no reconocido.")
    else:
        await conv.send_message(f"❌ El ID proporcionado (`{txt}`) no fue encontrado en la base de datos.")

async def handle_editor_mode(event):
    chat_id = event.chat_id
    async with client.conversation(chat_id, timeout=3600, exclusive=False) as conv:
        current_jump_id = None
        last_msg = None
        
        while editor_mode_active.get(chat_id, False):
            try:
                if current_jump_id:
                    jump = current_jump_id
                    current_jump_id = None
                    if last_msg:
                        try: await last_msg.delete()
                        except: pass
                    await process_editor_id(conv, jump)
                    continue # Go back to start of loop

                last_msg = await conv.send_message(
                    "🛠️ **Modo Editor Activado**\n\n¿Qué deseas gestionar?",
                    buttons=[
                        [Button.inline("🎬 Gestionar Películas", b"ed_mov")],
                        [Button.inline("📺 Gestionar Series", b"ed_ser")],
                        [Button.inline("❌ Salir del Editor", b"ed_exit")]
                    ]
                )
                
                resp = await wait_for_message_or_callback(conv, timeout=3600)
                if getattr(resp, 'raw_text', '') == '/desactivar_modo_editor':
                    break

                if isinstance(resp, events.CallbackQuery.Event):
                    await resp.answer()
                    try: await last_msg.delete()
                    except: pass
                    
                    if resp.data == b"ed_exit":
                        editor_mode_active[chat_id] = False
                        await conv.send_message("✅ **Modo editor desactivado.**")
                        break
                    elif resp.data == b"ed_mov":
                        await handle_editor_movie_search(conv)
                    elif resp.data == b"ed_ser":
                        await handle_editor_series_search(conv)
                        
                elif getattr(resp, 'raw_text', ''):
                    txt = resp.raw_text.strip()
                    if txt.startswith('/start '):
                        txt = txt.replace('/start ', '').replace('folder_', '').strip()
                        
                    if txt.startswith('/'):
                        if txt == '/desactivar_modo_editor':
                            break
                        continue
                        
                    try: await last_msg.delete()
                    except: pass
                    
                    await process_editor_id(conv, txt)

            except EditorJumpException as e:
                # A jump occurred from anywhere (main menu or submenu)! Loop back and handle it.
                current_jump_id = e.jump_id
            except Exception as e:
                print("Editor error:", e)
                break

async def handle_editor_movie_search(conv):
    from telethon.tl.types import KeyboardButtonSimpleWebView
    uid_back = str(uuid.uuid4()).encode()
    btn_webapp = KeyboardButtonSimpleWebView(text="🍿 Buscar ID en Catálogo", url="https://codebybrody-twistedstreamingbrody.hf.space")
    msg = await conv.send_message("🔍 Escribe el **nombre o el ID** de la película que deseas buscar:", buttons=[
        [btn_webapp],
        [Button.inline("⬅️ Cancelar", uid_back)]
    ])
    
    resp = await wait_for_message_or_callback(conv, timeout=300)
    if isinstance(resp, events.CallbackQuery.Event) and resp.data == uid_back:
        await resp.answer("Cancelado")
        await msg.edit("Búsqueda cancelada.", buttons=None)
        return
        
    query = resp.raw_text.strip()
    await msg.delete()
    
    movies_ref = db.collection('videos').where(filter=FieldFilter('section', '==', 'peliculas')).get()
    results = [m for m in movies_ref if query.lower() in m.to_dict().get('title', '').lower() or query == m.id]
    
    if not results:
        await conv.send_message("❌ No se encontraron películas con ese nombre.")
        return
        
    results = results[:10]
    buttons = []
    for r in results:
        data = r.to_dict()
        buttons.append([Button.inline(f"🎬 {data.get('title')[:30]}", f"ed_m_{r.id}".encode('utf-8'))])
    
    buttons.append([Button.inline("⬅️ Volver", b"ed_back")])
    
    msg_res = await conv.send_message("📌 **Resultados (Películas):**", buttons=buttons)
    resp_res = await wait_for_message_or_callback(conv, timeout=300)
    
    if isinstance(resp_res, events.CallbackQuery.Event):
        await resp_res.answer()
        await msg_res.edit(buttons=None)
        if resp_res.data == b"ed_back": return
        
        movie_id = resp_res.data.decode().replace('ed_m_', '')
        await handle_editor_movie_action(conv, movie_id)

async def handle_editor_movie_action(conv, movie_id):
    doc = db.collection('videos').document(movie_id).get()
    if not doc.exists: return
    data = doc.to_dict()
    
    msg = await conv.send_message(
        f"🎬 **Editando Película:**\n`{data.get('title')}`",
        buttons=[
            [Button.inline("✏️ Renombrar Título", b"renombrar")],
            [Button.inline("📝 Editar Descripción", b"edit_desc")],
            [Button.inline("🗑️ Eliminar Película", b"eliminar")],
            [Button.inline("⬅️ Volver", b"volver")]
        ]
    )
    resp = await wait_for_message_or_callback(conv, timeout=300)
    if isinstance(resp, events.CallbackQuery.Event):
        await resp.answer()
        await msg.edit(buttons=None)
        if resp.data == b"volver": return
        elif resp.data == b"renombrar":
            await conv.send_message("Escribe el **nuevo título** para la película:")
            new_title = await conv.get_response()
            db.collection('videos').document(movie_id).update({"title": new_title.raw_text})
            await conv.send_message(f"✅ Título actualizado a: **{new_title.raw_text}**")
        elif resp.data == b"edit_desc":
            uid_del = str(uuid.uuid4()).encode()
            msg_d = await conv.send_message("Escribe la **nueva descripción** para la película:", buttons=[[Button.inline("❌ Eliminar Descripción", uid_del)]])
            resp_d = await wait_for_message_or_callback(conv, timeout=300)
            if isinstance(resp_d, events.CallbackQuery.Event):
                await resp_d.answer("Eliminando...")
                db.collection('videos').document(movie_id).update({"description": ""})
                await msg_d.edit("✅ Descripción eliminada.", buttons=None)
            else:
                db.collection('videos').document(movie_id).update({"description": resp_d.raw_text})
                await msg_d.edit("✅ Descripción actualizada.", buttons=None)
        elif resp.data == b"eliminar":
            msg_conf = await conv.send_message(
                f"⚠️ ¿Estás seguro de que deseas eliminar la película **{data.get('title')}**?\nEsta acción no se puede deshacer.",
                buttons=[
                    [Button.inline("⚠️ Sí, eliminar definitivamente", b"confirm_del")],
                    [Button.inline("❌ Cancelar", b"cancel_del")]
                ]
            )
            resp_conf = await wait_for_message_or_callback(conv, timeout=120)
            if isinstance(resp_conf, events.CallbackQuery.Event):
                await resp_conf.answer()
                await msg_conf.edit(buttons=None)
                if resp_conf.data == b"confirm_del":
                    db.collection('videos').document(movie_id).delete()
                    await conv.send_message("✅ Película eliminada exitosamente.")
                else:
                    await conv.send_message("✅ Eliminación cancelada.")

async def handle_editor_series_search(conv):
    from telethon.tl.types import KeyboardButtonSimpleWebView
    uid_back = str(uuid.uuid4()).encode()
    btn_webapp = KeyboardButtonSimpleWebView(text="🍿 Buscar ID en Catálogo", url="https://codebybrody-twistedstreamingbrody.hf.space")
    msg = await conv.send_message("🔍 Escribe el **nombre o el ID** de la serie que deseas buscar:", buttons=[
        [btn_webapp],
        [Button.inline("⬅️ Cancelar", uid_back)]
    ])
    
    resp = await wait_for_message_or_callback(conv, timeout=300)
    if isinstance(resp, events.CallbackQuery.Event) and resp.data == uid_back:
        await resp.answer()
        await msg.edit("Búsqueda cancelada.", buttons=None)
        return
        
    query = resp.raw_text.strip()
    await msg.delete()
    
    series_ref = db.collection('videos').where(filter=FieldFilter('is_folder', '==', True)).get()
    results = [s for s in series_ref if query.lower() in s.to_dict().get('title', '').lower() or query == s.id]
    
    if not results:
        await conv.send_message("❌ No se encontraron series con ese nombre.")
        return
        
    results = results[:10]
    buttons = []
    for r in results:
        buttons.append([Button.inline(f"📺 {r.to_dict().get('title')[:30]}", f"ed_s_{r.id}".encode('utf-8'))])
    
    buttons.append([Button.inline("⬅️ Volver", b"ed_back")])
    
    msg_res = await conv.send_message("📌 **Resultados (Series):**", buttons=buttons)
    resp_res = await wait_for_message_or_callback(conv, timeout=300)
    
    if isinstance(resp_res, events.CallbackQuery.Event):
        await resp_res.answer()
        await msg_res.edit(buttons=None)
        if resp_res.data == b"ed_back": return
        
        series_id = resp_res.data.decode().replace('ed_s_', '')
        await handle_editor_series_action(conv, series_id)

async def handle_editor_series_action(conv, series_id):
    while editor_mode_active.get(conv.chat_id, False):
        doc = db.collection('videos').document(series_id).get()
        if not doc.exists: return
        data = doc.to_dict()
        title = data.get('title')
        
        msg = await conv.send_message(
            f"📺 **Editando Serie:**\n`{title}`",
            buttons=[
                [Button.inline("✏️ Renombrar Serie", b"renombrar")],
                [Button.inline("📝 Edición Masiva de Descripciones", b"edit_desc_masiva")],
                [Button.inline("📑 Ver y Editar Capítulos", b"ver_caps")],
                [Button.inline("📝 Edición Masiva de Capítulos", b"editar_lista")],
                [Button.inline("➕ Agregar Nuevos Capítulos", b"add_caps")],
                [Button.inline("🗑️ Eliminar Serie Completa", b"eliminar")],
                [Button.inline("⬅️ Volver al menú principal", b"volver")]
            ]
        )
        resp = await wait_for_message_or_callback(conv, timeout=3600)
        if getattr(resp, 'raw_text', '').startswith('/'): return
        
        if isinstance(resp, events.CallbackQuery.Event):
            await resp.answer()
            await msg.edit(buttons=None)
            
            if resp.data == b"volver": return
            elif resp.data == b"renombrar":
                await conv.send_message("Escribe el **nuevo título general** para la serie:")
                new_title = await conv.get_response()
                db.collection('videos').document(series_id).update({"title": new_title.raw_text})
                await conv.send_message(f"✅ Título general actualizado a: **{new_title.raw_text}**")
            elif resp.data == b"edit_desc_masiva":
                uid_del = str(uuid.uuid4()).encode()
                msg_d = await conv.send_message("Escribe la **nueva descripción** para aplicarla a TODOS los capítulos de esta serie:", buttons=[[Button.inline("❌ Eliminar Todas las Descripciones", uid_del)]])
                resp_d = await wait_for_message_or_callback(conv, timeout=300)
                caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
                updated_count = 0
                
                if isinstance(resp_d, events.CallbackQuery.Event):
                    await resp_d.answer("Eliminando...")
                    for c in caps:
                        db.collection('videos').document(c.id).update({"description": ""})
                        updated_count += 1
                    await msg_d.edit(f"✅ Descripciones eliminadas masivamente en {updated_count} capítulos.", buttons=None)
                else:
                    for c in caps:
                        db.collection('videos').document(c.id).update({"description": resp_d.raw_text})
                        updated_count += 1
                    await msg_d.edit(f"✅ Descripción aplicada masivamente a {updated_count} capítulos.", buttons=None)
            elif resp.data == b"eliminar":
                msg_conf = await conv.send_message(
                    f"⚠️ ¿Estás seguro de que deseas eliminar la serie completa **{title}** y **TODOS** sus capítulos?\nEsta acción no se puede deshacer.",
                    buttons=[
                        [Button.inline("⚠️ Sí, eliminar serie y capítulos", b"confirm_del")],
                        [Button.inline("❌ Cancelar", b"cancel_del")]
                    ]
                )
                resp_conf = await wait_for_message_or_callback(conv, timeout=120)
                if isinstance(resp_conf, events.CallbackQuery.Event):
                    await resp_conf.answer()
                    await msg_conf.edit(buttons=None)
                    if resp_conf.data == b"confirm_del":
                        caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
                        for c in caps: db.collection('videos').document(c.id).delete()
                        db.collection('videos').document(series_id).delete()
                        await conv.send_message("✅ Serie y todos sus capítulos eliminados exitosamente.")
                        return
                    else:
                        await conv.send_message("✅ Eliminación cancelada.")
            elif resp.data == b"ver_caps":
                await handle_editor_series_chapters(conv, series_id, title)
            elif resp.data == b"editar_lista":
                caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
                caps = sorted(caps, key=lambda x: x.to_dict().get('episode', 0))
                if not caps:
                    await conv.send_message("❌ Esta serie no tiene capítulos.")
                    continue
                
                template = f"{{TITULO_GENERAL}} {title}\n\n"
                for c in caps:
                    template += f"{{{c.id}}} {c.to_dict().get('title')}\n"
                
                await conv.send_message(
                    "📝 **EDICIÓN MASIVA**\n\n"
                    "1. Toca el siguiente mensaje para copiarlo.\n"
                    "2. Pégalo en el chat y edita el nombre de la serie o de los capítulos como desees.\n"
                    "3. Envíamelo.\n\n"
                    "⚠️ **MUY IMPORTANTE:** ¡NO borres ni modifiques los códigos entre llaves `{ }`!"
                )
                await conv.send_message(f"```{template}```")
                
                await conv.send_message("⏳ Esperando tu mensaje con la plantilla editada... (O envía `/cancelar` para abortar)")
                
                resp_text = await wait_for_message_or_callback(conv, timeout=3600)
                if isinstance(resp_text, events.CallbackQuery.Event):
                    await resp_text.answer("Operación cancelada")
                    continue
                if resp_text.raw_text.strip().lower() == '/cancelar':
                    await conv.send_message("✅ Edición masiva cancelada.")
                    continue
                if getattr(resp_text, 'raw_text', '').startswith('/'): return
                    
                new_text = resp_text.raw_text
                import re
                matches = re.findall(r'\{(.*?)\}\s*(.*)', new_text)
                
                if not matches:
                    await conv.send_message("❌ No se detectó el formato correcto. Recuerda no borrar las llaves { }.")
                    continue
                    
                status_m = await conv.send_message("⚙️ Guardando cambios...")
                updated_count = 0
                for doc_id, new_title in matches:
                    doc_id = doc_id.strip()
                    new_title = new_title.strip()
                    if new_title:
                        if doc_id == "TITULO_GENERAL":
                            try:
                                db.collection('videos').document(series_id).update({"title": new_title})
                                title = new_title # update variable
                            except: pass
                        else:
                            try:
                                db.collection('videos').document(doc_id).update({"title": new_title})
                                updated_count += 1
                            except: pass
                        
                await status_m.edit(f"✅ **¡Listo!** Se actualizó el título general y {updated_count} capítulos correctamente.")
            elif resp.data == b"add_caps":
                await handle_editor_add_chapters(conv, series_id, title)

async def handle_editor_series_chapters(conv, series_id, series_title):
    caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
    caps = sorted(caps, key=lambda x: x.to_dict().get('episode', 0))
    if not caps:
        await conv.send_message("❌ Esta serie no tiene capítulos.")
        return
        
    buttons = []
    for c in caps[:90]:
        c_data = c.to_dict()
        buttons.append([Button.inline(f"Cap {c_data.get('episode', 0)}: {c_data.get('title')[:20]}", f"ed_c_{c.id}".encode('utf-8'))])
        
    buttons.append([Button.inline("⬅️ Volver", b"volver_caps")])
    
    msg = await conv.send_message(f"📑 **Capítulos de {series_title}**\nSelecciona uno para editar:", buttons=buttons)
    resp = await wait_for_message_or_callback(conv, timeout=300)
    
    if isinstance(resp, events.CallbackQuery.Event):
        await resp.answer()
        await msg.edit(buttons=None)
        if resp.data == b"volver_caps": return
        cap_id = resp.data.decode().replace('ed_c_', '')
        await handle_editor_single_chapter(conv, cap_id)

async def handle_editor_single_chapter(conv, cap_id):
    doc = db.collection('videos').document(cap_id).get()
    if not doc.exists: return
    data = doc.to_dict()
    
    msg = await conv.send_message(
        f"🎞️ **Editando Capítulo:**\n`{data.get('title')}`",
        buttons=[
            [Button.inline("✏️ Renombrar", b"renombrar")],
            [Button.inline("📝 Editar Descripción", b"edit_desc")],
            [Button.inline("🗑️ Eliminar", b"eliminar")],
            [Button.inline("⬅️ Volver", b"volver")]
        ]
    )
    resp = await wait_for_message_or_callback(conv, timeout=300)
    if isinstance(resp, events.CallbackQuery.Event):
        await resp.answer()
        await msg.edit(buttons=None)
        if resp.data == b"volver": return
        if resp.data == b"renombrar":
            await conv.send_message("Escribe el **nuevo nombre** del capítulo:")
            new_title = await conv.get_response()
            db.collection('videos').document(cap_id).update({"title": new_title.raw_text})
            await conv.send_message(f"✅ Capítulo renombrado a: **{new_title.raw_text}**")
        if resp.data == b"edit_desc":
            uid_del = str(uuid.uuid4()).encode()
            msg_d = await conv.send_message("Escribe la **nueva descripción** del capítulo:", buttons=[[Button.inline("❌ Eliminar Descripción", uid_del)]])
            resp_d = await wait_for_message_or_callback(conv, timeout=300)
            if isinstance(resp_d, events.CallbackQuery.Event):
                await resp_d.answer("Eliminando...")
                db.collection('videos').document(cap_id).update({"description": ""})
                await msg_d.edit("✅ Descripción eliminada.", buttons=None)
            else:
                db.collection('videos').document(cap_id).update({"description": resp_d.raw_text})
                await msg_d.edit("✅ Descripción actualizada.", buttons=None)
        if resp.data == b"eliminar":
            msg_conf = await conv.send_message(
                f"⚠️ ¿Estás seguro de que deseas eliminar el capítulo **{data.get('title')}**?\nEsta acción no se puede deshacer.",
                buttons=[
                    [Button.inline("⚠️ Sí, eliminar capítulo", b"confirm_del")],
                    [Button.inline("❌ Cancelar", b"cancel_del")]
                ]
            )
            resp_conf = await wait_for_message_or_callback(conv, timeout=120)
            if isinstance(resp_conf, events.CallbackQuery.Event):
                await resp_conf.answer()
                await msg_conf.edit(buttons=None)
                if resp_conf.data == b"confirm_del":
                    db.collection('videos').document(cap_id).delete()
                    await conv.send_message("✅ Capítulo eliminado exitosamente.")
                else:
                    await conv.send_message("✅ Eliminación cancelada.")

async def handle_editor_add_chapters(conv, series_id, series_title):
    uid_done = str(uuid.uuid4()).encode()
    videos = []
    
    msg_v = await conv.send_message(
        f"➕ **Añadiendo capítulos a: {series_title}**\n\nEnvía los videos. Cuando termines presiona el botón.",
        buttons=[[Button.inline("📁 Terminar y Guardar", uid_done)]]
    )
    
    debounce_task = None
    async def update_button():
        await asyncio.sleep(0.8)
        nonlocal msg_v
        try: await msg_v.delete()
        except: pass
        msg_v = await conv.send_message(
            f"➕ **Añadiendo capítulos a: {series_title}**\n\n({len(videos)} recibidos). Envía más o termina.",
            buttons=[[Button.inline("📁 Terminar y Guardar", uid_done)]]
        )

    async def video_receiver(e):
        is_video = False
        if getattr(e, 'media', None):
            if getattr(e, 'video', None):
                is_video = True
            elif getattr(e, 'document', None):
                mime = getattr(e.file, 'mime_type', '') if hasattr(e, 'file') else ''
                if mime.startswith('video/'):
                    is_video = True
                else:
                    for attr in e.document.attributes:
                        if hasattr(attr, 'file_name'):
                            import os
                            ext = os.path.splitext(attr.file_name)[1].lower()
                            if ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.ts', '.m4v']:
                                is_video = True
                            break
        if is_video:
            videos.append(e)
            nonlocal debounce_task
            if debounce_task: debounce_task.cancel()
            debounce_task = asyncio.create_task(update_button())

    client.add_event_handler(video_receiver, events.NewMessage(chats=conv.chat_id, incoming=True))
    try:
        while True:
            event = await wait_for_message_or_callback(conv, timeout=3600)
            if isinstance(event, events.CallbackQuery.Event):
                if event.data == uid_done:
                    if not videos:
                        await event.answer("No has enviado videos.", alert=True)
                        return
                    await event.answer("Guardando...")
                    if debounce_task: debounce_task.cancel()
                    await msg_v.edit(f"✅ Se recibieron {len(videos)} capítulos.", buttons=None)
                    break
    finally:
        client.remove_event_handler(video_receiver, events.NewMessage(chats=conv.chat_id, incoming=True))

    if not videos: return

    uid_title = str(uuid.uuid4()).encode()
    uid_file = str(uuid.uuid4()).encode()
    
    sample_names = ""
    for v in videos[:2]:
        doc_name = "Video_desconocido.mp4"
        if hasattr(v.media, 'document'):
            for attr in v.media.document.attributes:
                if hasattr(attr, 'file_name'):
                    doc_name = attr.file_name
                    break
        sample_names += f"- {doc_name}\n"
        
    msg_n = await conv.send_message(
        "📁 ¿Cómo nombrar estos capítulos extra?\n\n"
        "Si usas nombres originales, se verán así:\n"
        f"{sample_names}",
        buttons=[
            [Button.inline("📁 Continuar enumeración general", uid_title)],
            [Button.inline("📁 Usar nombres de archivos originales", uid_file)]
        ]
    )
    
    naming_strategy = "title"
    while True:
        event = await wait_for_message_or_callback(conv, timeout=300)
        if isinstance(event, events.CallbackQuery.Event):
            if event.data == uid_title:
                naming_strategy = "title"
                await msg_n.edit("Formato: Serie - Capítulo X", buttons=None)
                break
            elif event.data == uid_file:
                naming_strategy = "file"
                await msg_n.edit("Formato: Archivo original", buttons=None)
                break
        else:
            naming_strategy = "manual"
            manual_prefix = event.raw_text
            await msg_n.edit(f"Formato: {manual_prefix}...", buttons=None)
            break

    status_msg = await conv.send_message("📁 **Procesando capítulos extra...**")
    
    caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
    max_ep = 0
    for c in caps:
        ep = c.to_dict().get('episode', 0)
        if ep > max_ep: max_ep = ep

    for i, video_msg in enumerate(videos):
        max_ep += 1
        
        if naming_strategy == "title":
            ep_title = f"{series_title} - Capítulo {max_ep}"
        elif naming_strategy == "manual":
            ep_title = f"{manual_prefix} - Capítulo {max_ep}"
        else:
            doc_name = "Episodio"
            if hasattr(video_msg.media, 'document'):
                for attr in video_msg.media.document.attributes:
                    if hasattr(attr, 'file_name'):
                        import os
                        doc_name = os.path.splitext(attr.file_name)[0]
                        break
            ep_title = doc_name

        await status_msg.edit(f"📁 Subiendo extra: **{ep_title}** ({i+1}/{len(videos)})")
        caption = f"**Twisted Streaming Brody Data**\n\n📁 **Serie:** {series_title}\n📁 **Episodio:** {ep_title}"
        sent_to_channel = await client.send_file(CHANNEL_ID, video_msg.media, caption=caption)
        clean_channel_id = str(CHANNEL_ID).replace("-100", "")
        file_url = f"https://t.me/c/{clean_channel_id}/{sent_to_channel.id}"

        db.collection('videos').add({
            "title": ep_title, 
            "section": "series",
            "is_folder": False, 
            "folder_id": series_id,
            "episode": max_ep,
            "season": 1,
            "video_url": file_url, 
            "telegram_file_id": str(sent_to_channel.id),
            "description": "",
            "thumbnail_url": "",
            "cover_url": "",
            "views": 0,
            "rating": 0,
            "status": "active",
            "is_public": True,
            "categories": [],
            "servers": [file_url],
            "created_at": firestore.SERVER_TIMESTAMP, 
            "updated_at": firestore.SERVER_TIMESTAMP
        })
    await status_msg.edit(f"✅ **¡{len(videos)} capítulos extra añadidos con éxito!**")

if __name__ == '__main__':

    print("================================")
    print(f"   BOT @TwistedStreamingBrodybot INICIADO")
    print("================================")
    client.start(bot_token=TOKEN)
    
    # Limpiar el menú nativo de comandos de Telegram
    async def set_commands():
        from telethon.tl.functions.bots import SetBotCommandsRequest
        from telethon.tl.types import BotCommand, BotCommandScopeDefault
        try:
            await client(SetBotCommandsRequest(
                scope=BotCommandScopeDefault(),
                lang_code='',
                commands=[
                    BotCommand(command="start", description="Iniciar el bot / Ver instrucciones"),
                    BotCommand(command="subir", description="Men\xC3\xBA principal de subida"),
                    BotCommand(command="subir_pelicula", description="Atajo: Subir Pel\xC3\xADcula"),
                    BotCommand(command="subir_serie", description="Atajo: Subir Serie"),
                    BotCommand(command="app", description="Abrir la Mini App de Cat\xC3\xA1logo"),
                    BotCommand(command="setting", description="Configurar env\xC3\xADo de videos"),
                    BotCommand(command="cancelar", description="Cancelar proceso de subida"),
                    BotCommand(command="activar_modo_editor", description="Activar Modo Editor"),
                    BotCommand(command="desactivar_modo_editor", description="Desactivar Modo Editor"),
                    BotCommand(command="buscador_on", description="Activar Modo Buscador"),
                    BotCommand(command="buscador_off", description="Desactivar Modo Buscador")
                ]
            ))
            print("📁 Menú nativo de comandos (/) actualizado.")
        except Exception as e:
            pass
            
    client.loop.run_until_complete(set_commands())
    client.run_until_disconnected()
