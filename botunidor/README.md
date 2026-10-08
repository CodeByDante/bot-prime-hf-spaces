---
title: Bot Unidor de Videos
emoji: 🎬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7080
pinned: false
---

# Bot Unidor de Videos

Bot de Telegram que descarga videos en cola de forma paralela (8 conexiones/hilos por video) y los une secuencialmente usando FFmpeg de forma rápida y normalizada.

## Despliegue en Hugging Face Spaces
Esta aplicación se ejecuta dentro de un contenedor Docker.
La página web fantasma de estado y monitoreo está expuesta en el puerto **7080**.

### Variables de Entorno (Secrets)
Para que el bot funcione de manera segura, debes configurar las siguientes claves en la pestaña **Settings -> Variables and secrets** de tu Space en Hugging Face:

1. **`API_ID`**: Tu ID de API de Telegram (obtenido de [my.telegram.org](https://my.telegram.org)).
2. **`API_HASH`**: Tu Hash de API de Telegram (obtenido de [my.telegram.org](https://my.telegram.org)).
3. **`BOT_TOKEN`**: El Token de tu Bot de Telegram (obtenido al crear el bot con [@BotFather](https://t.me/BotFather)).

---

## Estructura del Proyecto

- **`app.py`**: Punto de entrada de la aplicación. Levanta el servidor web en el puerto `7080` (o `$PORT` en producción) y arranca el bot de Telegram en segundo plano.
- **`bot.py`**: Lógica principal del bot (comandos de Telegram `/start`, `/unir`, `/limpiar`, control de cola, procesamiento de video y normalización/mezcla).
- **`fast_telethon.py`**: Motor de transferencia paralela optimizado para realizar descargas concurrentes de alta velocidad.
- **`Dockerfile`**: Configuración del contenedor Docker (instalación automática de `ffmpeg` y `ffprobe`, y privilegios de usuario UID `1000`).
