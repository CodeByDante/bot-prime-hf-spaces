"""
Launcher Autónomo del Monitor Diagnóstico para Hugging Face Spaces.
Puede ejecutarse de manera independiente en cualquier servidor o contenedor Docker.
"""
import os
import sys
import asyncio

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from utils.space_monitor import space_monitor

async def main():
    print("=" * 70)
    print(" 🔍 INICIANDO MONITOR DIAGNÓSTICO AUTÓNOMO DE HUGGING FACE SPACES")
    print("=" * 70)

    # Si existe una sesión de Telethon local, intentar conectar para enviar alertas a Telegram
    try:
        from core.client import client
        if not client.is_connected():
            await client.start()
        space_monitor.set_telegram_client(client)
        print("[Standalone Monitor] Cliente de Telegram iniciado correctamente.")
    except Exception as e:
        print(f"[Standalone Monitor Warning] Ejecutando sin cliente de Telegram ({e}). Solo logs y estado local.")

    await space_monitor.start_monitoring()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Standalone Monitor] Monitor detenido por el usuario.")
