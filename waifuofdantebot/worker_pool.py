import os
import asyncio
from pyrogram import Client
from config import API_ID, API_HASH, DATABASE_CHANNEL

# Archivo que guarda los tokens (un token por línea)
WORKERS_FILE = "workers.txt"

_workers = []
_current_index = 0

async def start_workers():
    """Lee workers.txt y enciende las sesiones en paralelo."""
    if not os.path.exists(WORKERS_FILE):
        with open(WORKERS_FILE, "w") as f:
            f.write("# Pega los tokens de tus bots obreros aquí (uno por línea)\n")
        print("⚠️ Archivo workers.txt creado. Pon tokens ahí para usar el clúster multi-bot.")
        return

    with open(WORKERS_FILE, "r") as f:
        tokens = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not tokens:
        print("⚠️ No hay tokens en workers.txt. Se usará el bot principal.")
        return

    print(f"🚀 Iniciando clúster de {len(tokens)} bots obreros...")
    
    for i, token in enumerate(tokens):
        session_name = f"worker_{i}"
        client = Client(
            session_name,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=token,
            in_memory=True # Para no crear miles de archivos .session
        )
        try:
            await client.start()
            _workers.append(client)
            print(f"✅ Obrero {i} conectado.")
        except Exception as e:
            print(f"❌ Error conectando obrero {i}: {e}")

def get_worker(main_client):
    """Devuelve el siguiente bot (incluyendo el principal) (Round Robin)."""
    global _current_index
    if not _workers:
        return main_client
    
    total_bots = len(_workers) + 1 # El maestro + los obreros
    
    if _current_index == 0:
        worker = main_client
    else:
        worker = _workers[_current_index - 1]
        
    _current_index = (_current_index + 1) % total_bots
    return worker

def is_enabled():
    """Verifica si el clúster está activo y configurado."""
    return len(_workers) > 0 and DATABASE_CHANNEL is not None

# --- Wrappers para subida ---

async def _delegated_upload(main_client, upload_func_name, chat_id, f_path, delayed_copy=False, **kwargs):
    worker = get_worker(main_client)
    original_reply_to = kwargs.pop("reply_to_message_id", None)
    
    if not is_enabled():
        # Si no hay clúster ni canal, sube directo al chat
        print(f"👑 Bot Maestro subiendo archivo directamente sin base de datos...")
        func = getattr(main_client, upload_func_name)
        if original_reply_to: kwargs["reply_to_message_id"] = original_reply_to
        return await func(chat_id, f_path, **kwargs)

    # El obrero (o el maestro si es delayed_copy) sube al canal de base de datos
    worker_func = getattr(worker, upload_func_name)
    
    print(f"{'👑 Maestro' if worker==main_client else '👷 Obrero'} subiendo a la base de datos...")
    dump_msg = await worker_func(DATABASE_CHANNEL, f_path, **kwargs)
    
    if delayed_copy:
        # Guardar reply original como un atributo temporal y retornar el dump_msg
        dump_msg.original_reply_to = original_reply_to
        return dump_msg
    
    # El maestro lo copia instantáneamente al chat del usuario
    sent_msg = await main_client.copy_message(
        chat_id=chat_id,
        from_chat_id=DATABASE_CHANNEL,
        message_id=dump_msg.id,
        reply_to_message_id=original_reply_to
    )
    
    # copy_message devuelve un objeto Message simplificado. 
    # Le inyectamos la metadata del media para que el resto del código no falle al buscar file_id
    if hasattr(dump_msg, 'video'): sent_msg.video = dump_msg.video
    if hasattr(dump_msg, 'document'): sent_msg.document = dump_msg.document
    if hasattr(dump_msg, 'audio'): sent_msg.audio = dump_msg.audio
    if hasattr(dump_msg, 'photo'): sent_msg.photo = dump_msg.photo
    
    return sent_msg

async def send_video(main_client, chat_id, f_path, delayed_copy=False, **kwargs):
    return await _delegated_upload(main_client, "send_video", chat_id, f_path, delayed_copy=delayed_copy, **kwargs)

async def send_document(main_client, chat_id, f_path, delayed_copy=False, **kwargs):
    return await _delegated_upload(main_client, "send_document", chat_id, f_path, delayed_copy=delayed_copy, **kwargs)

async def send_audio(main_client, chat_id, f_path, delayed_copy=False, **kwargs):
    return await _delegated_upload(main_client, "send_audio", chat_id, f_path, delayed_copy=delayed_copy, **kwargs)

async def send_photo(main_client, chat_id, f_path, delayed_copy=False, **kwargs):
    return await _delegated_upload(main_client, "send_photo", chat_id, f_path, delayed_copy=delayed_copy, **kwargs)
