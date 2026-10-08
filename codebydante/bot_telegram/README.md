# Telegram Bot (Python) para CodeByDante

Este bot usa **Pyrogram (MTProto)** para gestionar sesiones persistentes y permitir subidas de archivos desde tu página web.

## Estructura
- `bot.py`: Código principal (Bot + API).
- `sessions/`: Aquí se guarda el archivo `.session` generado automáticamente.
- `.env`: Configuración de credenciales.

## Instalación
Si no has instalado las dependencias:
```bash
pip install pyrogram tgcrypto fastapi uvicorn python-dotenv
```

## Configuración
1. Edita el archivo `.env`.
2. Asegúrate de tener los valores correctos de `API_ID`, `API_HASH` y `BOT_TOKEN`.
3. El `CHANNEL_ID` debe ser el ID del canal donde el bot es admin.

## Ejecución
```bash
python bot.py
```

Al iniciar por primera vez, se creará el archivo `bot_session.session` dentro de la carpeta `sessions/`.
