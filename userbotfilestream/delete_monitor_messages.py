import json
import asyncio
import os
from telethon import TelegramClient

async def main():
    base_dir = r"c:\Users\Gonzalo\Desktop\userbotFileStream"
    config_path = os.path.join(base_dir, "config.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    api_id = int(config["api_id"])
    api_hash = config["api_hash"]
    session_path = os.path.join(base_dir, "telethon_cuenta")

    print("Iniciando cliente de Telegram...")
    client = TelegramClient(session_path, api_id, api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        print("Error: La sesión de Telegram no está iniciada o es inválida.")
        await client.disconnect()
        return

    print("Buscando notificaciones de diagnóstico en Mensajes Guardados ('me')...")
    
    messages_to_delete = []
    
    # Buscamos en los últimos 2000 mensajes
    async for message in client.iter_messages("me", limit=2000):
        if message.message and (
            "📂 Control y Ayuda" in message.message or 
            "🌐 Guía interactiva detallada:" in message.message
        ):
            messages_to_delete.append(message.id)
            print(f"Encontrado mensaje a borrar: ID {message.id}")
            
    if messages_to_delete:
        print(f"\nBorrando {len(messages_to_delete)} mensajes de notificación...")
        await client.delete_messages("me", messages_to_delete)
        print("¡Todos los mensajes han sido eliminados con éxito!")
    else:
        print("No se encontraron notificaciones recientes para eliminar.")
        
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
