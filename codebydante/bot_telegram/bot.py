import os
import asyncio
from contextlib import asynccontextmanager
from telethon import TelegramClient, events
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
from dotenv import load_dotenv

# 1. Configuración
load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = int(os.getenv("TELEGRAM_CHANNEL_ID", "0"))

# FORZAMOS el puerto 7860 para Hugging Face (NO CAMBIAR)
PORT = 7860

if not os.path.exists("sessions"):
    os.makedirs("sessions")

# 2. Inicializar Cliente de Telethon
client = TelegramClient('sessions/bot_session', API_ID, API_HASH)

# --- CICLO DE VIDA (LIFESPAN) ---
# Esto asegura que el bot arranque sin importar cómo se inicie el servidor
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- INICIANDO SISTEMA HÍBRIDO ---")
    print(f"Puerto detectado: {PORT}")
    try:
        print("Iniciando Bot de Telegram...")
        await client.start(bot_token=BOT_TOKEN)
        print("¡Bot en línea y escuchando!")
    except Exception as e:
        print(f"ERROR AL INICIAR BOT: {e}")
    
    yield
    
    print("Apagando sistema...")
    await client.disconnect()

# 3. Servidor API con FastAPI
app_api = FastAPI(lifespan=lifespan)

app_api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- COMANDOS DEL BOT ---

@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    parts = event.raw_text.split()
    if len(parts) > 1:
        try:
            msg_id = int(parts[1])
            await client.forward_messages(event.chat_id, msg_id, CHANNEL_ID)
            return
        except:
            pass
    await event.respond('¡Hola! Soy el bot de CodeByDante. Usa la web para descargar tus archivos.')

# --- ENDPOINTS DE LA API ---

@app_api.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_path = f"temp_{file.filename}"
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        print(f"Subiendo '{file.filename}' a Telegram...")
        sent_msg = await client.send_file(CHANNEL_ID, file_path)
        os.remove(file_path)
        
        return {
            "status": "success", 
            "message_id": sent_msg.id,
            "channel_id": CHANNEL_ID
        }
    except Exception as e:
        print(f"Error en upload: {e}")
        return {"status": "error", "message": str(e)}

# --- SERVIR FRONTEND ---

dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dist"))

if os.path.exists(dist_path):
    print(f"Sirviendo frontend desde: {dist_path}")
    app_api.mount("/assets", StaticFiles(directory=os.path.join(dist_path, "assets")), name="assets")

    @app_api.get("/")
    async def serve_index():
        return FileResponse(os.path.join(dist_path, "index.html"))

    @app_api.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        local_file = os.path.join(dist_path, full_path)
        if os.path.exists(local_file) and os.path.isfile(local_file):
            return FileResponse(local_file)
        return FileResponse(os.path.join(dist_path, "index.html"))
else:
    @app_api.get("/")
    async def hello():
        return {"message": "Servidor activo. Carpeta 'dist' no encontrada."}

if __name__ == '__main__':
    uvicorn.run(app_api, host="0.0.0.0", port=PORT)
