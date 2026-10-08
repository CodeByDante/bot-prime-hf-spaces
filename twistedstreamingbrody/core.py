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
            await client.send_message(chat_id, "📁 **Proceso cancelado.**\nEscribe /start para volver al menú principal.")
            raise CancelUploadException()
            
        # Global intercept for editor mode jumps
        if user_modes.get(chat_id) == 'editor':
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


user_modes = {}
active_tasks = {}
button_cooldowns = {}
bot_settings = {'send_title': True, 'send_description': True, 'ask_series': True}
editor_mode_active = {}
search_mode_active = {}
