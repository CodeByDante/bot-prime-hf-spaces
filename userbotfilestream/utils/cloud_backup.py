import os
import asyncio
import json
from telethon.tl.types import DocumentAttributeFilename

def get_backup_channel():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('backup_channel_id', 'me')
    except Exception:
        return 'me'


async def download_database_from_telegram(client, local_db_path):
    print("[CloudDB] Buscando última copia de seguridad en Mensajes Guardados...")
    try:
        target_channel = get_backup_channel()
        # Buscar el último archivo enviado por el propio bot con el hashtag #DB_BACKUP_VIDEOS
        async for msg in client.iter_messages(target_channel, search='#DB_BACKUP_VIDEOS', limit=1):
            if msg.document:
                for attr in msg.document.attributes:
                    if isinstance(attr, DocumentAttributeFilename) and attr.file_name == os.path.basename(local_db_path):
                        print(f"[CloudDB] Copia de seguridad encontrada. Descargando a {local_db_path}...")
                        await client.download_media(msg.document, file=local_db_path)
                        print("[CloudDB] Descarga completada. Memoria restaurada con éxito.")
                        return True
        print("[CloudDB] No se encontró ninguna copia de seguridad previa. Iniciando con base de datos en blanco.")
    except Exception as e:
        print(f"[CloudDB] Error al buscar/descargar la base de datos de Telegram: {e}")
    return False

async def force_database_backup(client, local_db_path, trigger_reason="Automática"):
    try:
        if os.path.exists(local_db_path):
            if os.path.getsize(local_db_path) > 10:
                target_channel = get_backup_channel()
                print(f"[CloudDB] Subiendo copia de seguridad ({trigger_reason}) al canal de backup...")
                await client.send_file(
                    target_channel, 
                    local_db_path, 
                    caption=f"📦 **Copia de Seguridad {trigger_reason}**\n\nEste archivo contiene la memoria del bot (videos y canales indexados).\n\n#DB_BACKUP_VIDEOS"
                )
                print("[CloudDB] Copia de seguridad subida con éxito.")
                return True
    except Exception as e:
        print(f"[CloudDB] Error al subir el backup a Telegram: {e}")
    return False

async def periodic_database_backup(client, local_db_path, interval_seconds=7200):
    await asyncio.sleep(60) # Esperar un poco antes del primer backup
    print(f"[CloudDB] Tarea de backup en segundo plano iniciada (cada {interval_seconds} segundos).")
    while True:
        await force_database_backup(client, local_db_path, trigger_reason="Automática")
        await asyncio.sleep(interval_seconds)
