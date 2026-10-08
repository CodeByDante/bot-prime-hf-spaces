import sys
import os
import asyncio
import json
import urllib.request
import firebase_admin
import socket
from firebase_admin import credentials, firestore
from telethon.tl.functions.channels import EditAdminRequest
from telethon.tl.types import ChatAdminRights

# Forzar IPv4 para evitar timeouts de TLS/handshake en Hugging Face (causados por IPv6 no ruteado)
orig_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = getaddrinfo_ipv4

# Silenciar logs molestos de FFmpeg y OpenCV en la consola
os.environ["AV_LOG_LEVEL"] = "quiet"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"

# Añadir el directorio actual al path para resolver las importaciones
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.client import client, client_pool
import handlers.main_handler
# Importar main_handler para registrar los eventos del despachador
def _fetch_bot_username(token):
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode())
            if res_data.get("ok"):
                return res_data["result"]["username"]
    except Exception:
        pass
    return None

async def auto_promote_workers_on_startup():
    await asyncio.sleep(3) # Esperar a que la conexión esté estable
    print("[Userbot] Iniciando verificación automática de workers en el canal de respaldo...")
    try:
        # 1. Leer config.json
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if not os.path.exists(config_path):
            print("[Userbot] No se encontró config.json, omitiendo verificación de workers.")
            return
            
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        backup_channel_id = int(config_data.get("backup_channel_id", 0))
        if not backup_channel_id:
            print("[Userbot] backup_channel_id no configurado, omitiendo verificación.")
            return

        # 2. Conectar a Firebase para leer los tokens
        firebase_key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "firebase_key.json")
        if not os.path.exists(firebase_key_path):
            print("[Userbot] firebase_key.json no encontrado, omitiendo verificación.")
            return


        # NOTA: Desactivado temporalmente el uso de Firebase para evitar límites de cuota.
        # En su lugar, el bot usará los tokens locales u omitirá los workers.
        db = None

        def get_tokens_sync():
            try:
                # Usar timeout para que no se quede congelado reintentando si no hay cuota
                return list(db.collection("brody_tokens").stream(timeout=5))
            except Exception as e:
                print(f"[Firebase Warning] No se pudieron obtener los tokens (Posible Cuota Excedida): {e}")
                return []

        # Simulamos que no hay Firebase
        tokens = []

        if not tokens:
            print("[Userbot] Firebase desactivado por el usuario. Omitiendo cargar tokens desde la nube.")
            return

        print(f"[Userbot] Se encontraron {len(tokens)} tokens de workers. Comprobando canal...")
        
        # Obtener entidad del canal de respaldo
        try:
            channel = await client.get_entity(backup_channel_id)
            # Cargar participantes del canal para meterlos en el caché de Telethon
            try:
                await client.get_participants(channel)
            except Exception:
                pass
        except Exception as e:
            print(f"[Userbot Error] No se pudo obtener el canal de respaldo {backup_channel_id}: {e}")
            return

        # Permisos administrativos completos para los workers
        rights = ChatAdminRights(
            change_info=True,
            post_messages=True,
            edit_messages=True,
            delete_messages=True,
            invite_users=True,
            manage_call=True,
            add_admins=True,
            ban_users=True,
            pin_messages=True,
            anonymous=True,
            manage_topics=True,
            post_stories=True,
            edit_stories=True,
            delete_stories=True,
            manage_direct_messages=True
        )

        for token in tokens:
            # Obtener username del bot llamando a Telegram Bot API getMe (no bloqueante en un hilo de fondo)
            bot_username = None
            try:
                bot_username = await asyncio.to_thread(_fetch_bot_username, token)
            except Exception as e:
                print(f"[Userbot Warning] Error al consultar Bot API para {token[:15]}...: {e}")

            if not bot_username:
                try:
                    bot_id = int(token.split(":")[0])
                    bot_entity = await client.get_entity(bot_id)
                except Exception as e:
                    print(f"[Userbot Error] No se pudo resolver el bot para el token {token[:15]}...: {e}")
                    continue
            else:
                try:
                    bot_entity = await client.get_entity(bot_username)
                except Exception as e:
                    print(f"[Userbot Error] No se pudo resolver la entidad de @{bot_username}: {e}")
                    continue

            # Promover/Asegurar administrador en el canal de respaldo
            try:
                await client(EditAdminRequest(
                    channel=channel,
                    user_id=bot_entity,
                    admin_rights=rights,
                    rank="Worker"
                ))
                name = bot_username if bot_username else token.split(":")[0]
                print(f"[Userbot OK] Bot @{name} verificado y promovido a admin en canal de respaldo.")
            except Exception as e:
                name = bot_username if bot_username else token.split(":")[0]
                print(f"[Userbot Error] No se pudo promover al bot @{name} en el canal: {e}")

    except Exception as e:
        print(f"[Userbot Error] Error general en verificación de workers: {e}")

async def main():
    print("\033[95m" + "="*60)
    print("      TWISTED BRODY PRIME USER BOT: INICIADO")
    print("="*60 + "\033[0m")
    
    # Inicializar el pool de clientes (inicia master y esclavos)
    await client_pool.initialize()
    print("\033[92m[Userbot] Conexión y escucha activa en Telegram. Esperando comandos...\033[0m\n")
    
    # Vincular cliente de Telethon con el monitor de Spaces
    try:
        from utils.space_monitor import space_monitor
        space_monitor.set_telegram_client(client)
    except Exception as monitor_err:
        print(f"[Userbot Warning] No se pudo vincular cliente de Telegram con SpaceMonitor: {monitor_err}")

    # Programar la verificación automática de workers al iniciar
    asyncio.create_task(auto_promote_workers_on_startup())
    
    # NUEVO: Lógica de Cloud DB usando Mensajes Guardados
    try:
        from utils.cloud_backup import download_database_from_telegram, periodic_database_backup
        from utils.database import LOCAL_CACHE_FILE
        # 1. Descargar la memoria al iniciar
        await download_database_from_telegram(client, LOCAL_CACHE_FILE)
        # 2. Programar el guardado automático cada 2 horas (7200 segundos)
        asyncio.create_task(periodic_database_backup(client, LOCAL_CACHE_FILE, 7200))
    except Exception as e:
        print(f"[CloudDB Warning] No se pudo inicializar la memoria en la nube: {e}")
    
    await client.run_until_disconnected()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

