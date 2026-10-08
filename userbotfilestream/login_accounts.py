import os
import asyncio
import json
from telethon import TelegramClient

# Resolver la ruta del directorio base del proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

if not os.path.exists(CONFIG_PATH):
    print(f"[Error] No se encontró config.json en {CONFIG_PATH}.")
    exit(1)

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

API_ID = int(config["api_id"])
API_HASH = config["api_hash"]

async def main():
    print("========================================")
    print("   REGISTRO DE CUENTAS ESCLAVAS / POOL  ")
    print("========================================")
    print("Este script te permite iniciar sesión en una de tus cuentas")
    print("secundarias de Telegram y guardarla en la carpeta 'sessions/'.")
    print()
    
    phone = input("Introduce el número de teléfono (con prefijo internacional, ej. +5411652132): ").strip()
    if not phone:
        print("[Error] El número de teléfono no puede estar vacío.")
        return
        
    sessions_dir = os.path.join(BASE_DIR, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    
    # Limpiar el número de teléfono para usarlo como nombre de sesión
    session_name = phone.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    session_path = os.path.join(sessions_dir, session_name)
    
    client = TelegramClient(session_path, API_ID, API_HASH)
    
    print(f"\nConectando a Telegram para el número {phone}...")
    await client.connect()
    
    try:
        if not await client.is_user_authorized():
            print(f"Enviando código de verificación a {phone}...")
            await client.send_code_request(phone)
            code = input("Introduce el código enviado por Telegram: ").strip()
            
            try:
                await client.sign_in(phone, code)
            except Exception as e:
                # Si requiere contraseña de verificación de 2 pasos
                if "two-step" in str(e).lower() or "verification" in str(e).lower() or "password" in str(e).lower():
                    pw = input("La cuenta tiene verificación en dos pasos (2FA). Introduce la contraseña: ").strip()
                    await client.sign_in(password=pw)
                else:
                    raise e
                    
        me = await client.get_me()
        if me:
            print(f"\n[ÉXITO] Sesión iniciada con éxito.")
            print(f"Cuenta: {me.first_name} {me.last_name or ''} (@{me.username or 'sin username'})")
            print(f"Sesión guardada en: sessions/{session_name}.session")
        else:
            print("\n[Error] No se pudo verificar la información del usuario.")
            
    except Exception as e:
        print(f"\n[ERROR] No se pudo iniciar sesión: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nRegistro cancelado.")
