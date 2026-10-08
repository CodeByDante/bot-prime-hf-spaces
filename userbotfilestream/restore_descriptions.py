import os
import sys
import json
import asyncio
from telethon import TelegramClient
from telethon.errors import FloodWaitError

# Ensure standard output can print Unicode characters on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_DIR)

from utils.database import DB, db_firestore
from core.client import client

async def main():
    print("🤖 Conectando a la base de datos...")
    
    if db_firestore is None:
        print("⚠️ Firebase no está activo. Leyendo cache local...")
        cache_file = os.path.join(PROJECT_DIR, "videos_cache.json")
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            print("❌ No se encontró videos_cache.json local.")
            return
    else:
        print("🔥 Conectando a Firebase Firestore...")
        try:
            loop = asyncio.get_event_loop()
            def fetch_firebase():
                docs = db_firestore.collection("channels").stream()
                channels = {}
                for doc in docs:
                    channels[doc.id] = doc.to_dict()
                return {"channels": channels}
            data = await asyncio.wait_for(loop.run_in_executor(None, fetch_firebase), timeout=15.0)
        except Exception as e:
            print(f"❌ Error al conectar a Firebase: {e}.")
            return

    channels = data.get("channels", {})
    if not channels:
        print("❌ No hay canales guardados en la base de datos.")
        return

    print("\n========================================================")
    print("📺 CANALES DISPONIBLES EN LA BASE DE DATOS:")
    print("========================================================")
    ch_list = []
    for idx, (chat_id, ch_data) in enumerate(channels.items(), 1):
        title = ch_data.get("channel_title", "Canal Privado")
        videos = ch_data.get("videos", [])
        ch_list.append((chat_id, title, videos))
        print(f"{idx}. {title} (ID: {chat_id}) - {len(videos)} videos en base de datos")
    print("========================================================\n")

    try:
        choice = input("👉 Selecciona el número del canal que deseas restaurar (o pulsa Enter para salir): ")
        if not choice.strip():
            print("Proceso cancelado.")
            return
        idx = int(choice) - 1
        if idx < 0 or idx >= len(ch_list):
            print("❌ Opción inválida.")
            return
    except ValueError:
        print("❌ Entrada inválida.")
        return

    target_chat_id, target_title, target_videos = ch_list[idx]
    
    # Try to convert chat ID to integer for Telethon
    try:
        tg_chat_id = int(target_chat_id)
    except ValueError:
        tg_chat_id = target_chat_id

    print(f"\n🔄 Preparando restauración para: {target_title} ({target_chat_id})")
    print("🔌 Iniciando sesión en Telegram...")
    
    await client.start()
    print("✅ Conectado a Telegram.")

    # Try to get entity to verify accessibility
    try:
        entity = await client.get_entity(tg_chat_id)
        print(f"✅ Canal verificado con éxito: {entity.title}")
    except Exception as e:
        print(f"⚠️ Advertencia al verificar canal: {e}. Intentando continuar con el ID directo...")

    # We will retrieve messages that need restoring
    print("\n🔍 Escaneando mensajes en el canal de Telegram...")
    # Find list of message IDs from target_videos
    video_map = {v["id"]: v["title"] for v in target_videos if v.get("title")}
    if not video_map:
        print("❌ No hay videos con títulos guardados para este canal en la base de datos.")
        return

    print(f"Total de videos guardados en la base de datos para restaurar: {len(video_map)}")
    
    # Fetch target messages from Telegram
    print("📥 Descargando información actual de los mensajes desde Telegram...")
    restore_list = []
    
    try:
        # Fetch only the specific message IDs we have in the database
        msg_ids = list(video_map.keys())
        # Telethon get_messages can fetch in chunks
        chunk_size = 100
        for i in range(0, len(msg_ids), chunk_size):
            chunk = msg_ids[i:i+chunk_size]
            messages = await client.get_messages(tg_chat_id, ids=chunk)
            for m in messages:
                if m:
                    cached_title = video_map.get(m.id)
                    # Check if the message on Telegram is currently empty or doesn't match the cached title
                    current_text = m.message or ""
                    if not current_text.strip() and cached_title:
                        restore_list.append((m.id, cached_title))
    except Exception as e:
        print(f"❌ Error al recuperar mensajes desde Telegram: {e}")
        return

    if not restore_list:
        print("🎉 ¡Genial! Todos los mensajes en Telegram ya tienen descripción. No hay nada que restaurar.")
        return

    print(f"\n⚠️ Se encontraron {len(restore_list)} mensajes que perdieron su descripción en Telegram.")
    confirm = input(f"¿Deseas restaurar la descripción de estos {len(restore_list)} mensajes ahora? (s/n): ")
    if confirm.lower() != 's':
        print("Proceso cancelado.")
        return

    print("\n🚀 Iniciando restauración...")
    restored_count = 0
    for idx, (msg_id, cached_title) in enumerate(restore_list, 1):
        try:
            # Restore the title/actress
            await client.edit_message(tg_chat_id, msg_id, text=cached_title)
            restored_count += 1
            print(f"[{idx}/{len(restore_list)}] ✅ Mensaje {msg_id} restaurado: '{cached_title}'")
            await asyncio.sleep(1.0) # Safe delay to avoid flood wait
        except FloodWaitError as e:
            print(f"⏳ Límite de velocidad de Telegram. Esperando {e.seconds} segundos...")
            await asyncio.sleep(e.seconds + 2)
            await client.edit_message(tg_chat_id, msg_id, text=cached_title)
            restored_count += 1
            print(f"[{idx}/{len(restore_list)}] ✅ Mensaje {msg_id} restaurado (luego de espera): '{cached_title}'")
        except Exception as e:
            print(f"[{idx}/{len(restore_list)}] ❌ Error al restaurar mensaje {msg_id}: {e}")
            await asyncio.sleep(1.0)

    print(f"\n🎉 ¡Restauración completada! Se restauraron con éxito {restored_count} de {len(restore_list)} mensajes.")

if __name__ == "__main__":
    asyncio.run(main())
