import os
import sys
import json
import glob
from telethon import TelegramClient

# Resolver la ruta del directorio base del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

if not os.path.exists(CONFIG_PATH):
    print(f"\033[91m[Error] No se encontró config.json en {CONFIG_PATH}.\033[0m")
    sys.exit(1)

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

API_ID = int(config["api_id"])
API_HASH = config["api_hash"]

# Crear cliente master con la ruta absoluta del archivo de sesión
client = TelegramClient(os.path.join(BASE_DIR, "telethon_cuenta"), API_ID, API_HASH)
client.max_concurrent_media_downloads = 16

class TelegramClientPool:
    def __init__(self, master_client):
        self.master = master_client
        self.clients = [master_client]
        self.current_idx = 0

    async def initialize(self):
        # 1. Asegurar que el master está iniciado
        invite_hash = None
        try:
            if not self.master.is_connected():
                await self.master.start()
            # Cargar diálogos del master para registrar entidades localmente
            await self.master.get_dialogs()
            
            # Intentar generar el invite link del canal de respaldo para los esclavos
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    val = cfg.get("backup_channel_id")
                    if val:
                        backup_id = int(val) if str(val).lstrip("-").isdigit() else val
                        try:
                            from telethon.tl.functions.messages import ExportChatInviteRequest
                            import re
                            invite = await self.master(ExportChatInviteRequest(peer=backup_id))
                            invite_link = invite.link
                            match = re.search(r'(?:\+|joinchat/)([\w\-]+)', invite_link)
                            if match:
                                invite_hash = match.group(1)
                                print(f"[Client Pool] Enlace de invitación de respaldo obtenido automáticamente: {invite_link}")
                        except Exception as export_err:
                            print(f"[Client Pool Warning] No se pudo exportar el enlace de invitación para el canal de respaldo: {export_err}")
        except Exception as e:
            print(f"[Client Pool Error] No se pudo iniciar el cliente principal: {e}")
            
        # 2. Cargar clientes secundarios desde la carpeta sessions/
        sessions_dir = os.path.join(BASE_DIR, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        session_files = glob.glob(os.path.join(sessions_dir, "*.session"))
        
        for sf in session_files:
            session_name = os.path.basename(sf).replace(".session", "")
            # Evitar duplicar el master
            if session_name == "telethon_cuenta":
                continue
            
            client_path = os.path.join(sessions_dir, session_name)
            try:
                cl = TelegramClient(client_path, API_ID, API_HASH)
                cl.max_concurrent_media_downloads = 16
                await cl.start()
                
                # Intentar unir al esclavo al canal de respaldo si tenemos el invite_hash
                if invite_hash:
                    try:
                        from telethon.tl.functions.messages import ImportChatInviteRequest
                        await cl(ImportChatInviteRequest(invite_hash))
                        print(f"[Client Pool] Esclavo {session_name} unido automáticamente al canal de respaldo.")
                    except Exception as join_err:
                        if "USER_ALREADY_PARTICIPANT" in str(join_err):
                            pass  # Ya está unido, no hay problema
                        else:
                            print(f"[Client Pool Warning] Esclavo {session_name} no pudo unirse al canal de respaldo: {join_err}")
                
                # Cargar diálogos del esclavo para guardar la caché de canales (entities) en su base de datos local
                print(f"[Client Pool] Sincronizando diálogos del esclavo {session_name} para registrar entidades...")
                await cl.get_dialogs()
                self.clients.append(cl)
                print(f"[Client Pool] Cliente esclavo cargado con éxito: {session_name}")
            except Exception as e:
                print(f"[Client Pool Error] No se pudo inicializar sesión esclava {session_name}: {e}")
                
        print(f"[Client Pool] Total de clientes activos en el pool: {len(self.clients)}")

    def get_client(self):
        """Devuelve un cliente rotando de manera equitativa (Round-Robin)"""
        if not self.clients:
            return self.master
        cl = self.clients[self.current_idx]
        self.current_idx = (self.current_idx + 1) % len(self.clients)
        return cl

    def get_master(self):
        return self.master

    def get_all(self):
        return self.clients

client_pool = TelegramClientPool(client)
