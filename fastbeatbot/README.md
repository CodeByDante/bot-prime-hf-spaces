---
title: FastBeat Bot
emoji: 🎵
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# 🎵 FastBeat Bot

Un bot de Telegram premium especializado en la **creación y edición de contenido viral (Shorts, Reels y TikToks)** con mezcla de audios y videos de forma instantánea. Diseñado para ser 100% estable, rápido y compatible con hosting gratuito como **Hugging Face Spaces** a través de Docker.

---

## ✨ Características Principales

1. **🎵 Short Virales Music**: Combina automáticamente videos con las pistas musicales más virales guardadas en tu base de datos de Telegram.
2. **🎵 Tiktok Fast**: Mezcla videos enviados directamente por el chat con un catálogo musical dinámico de forma ultra veloz.
3. **🎵 Fusión**: Mezcla de forma inteligente un video y un audio o nota de voz enviados por el usuario en tiempo real.
4. **☁️ Optimizado para Hosting**: 
   * **Sin links externos**: Los archivos se envían y procesan directamente a través de Telegram.
   * **Cero bloqueos**: No utiliza descargadores externos (como `yt-dlp`), lo que evita baneos de IP o captchas.
   * **Sin cookies**: 100% libre de mantenimiento de cookies o captchas.

---

## 🛠️ Configuración de Variables de Entorno

Para desplegar el bot, configura las siguientes **Variables Secretas (Secrets)** en la pestaña `Settings` de tu Hugging Face Space:

| Variable | Descripción |
| :--- | :--- |
| `API_ID` | Tu API ID de Telegram (obtener en [my.telegram.org](https://my.telegram.org)). |
| `API_HASH` | Tu API Hash de Telegram. |
| `BOT_TOKEN` | El token de tu bot de Telegram proporcionado por [@BotFather](https://t.me/BotFather). |
| `FIREBASE_KEY` | El contenido completo en JSON de tus credenciales de Firebase. |
| `OWNER_ID` | Tu ID de usuario de Telegram (para el Panel de Control Modo Dios). |
| `GEMINI_API_KEY` | (Opcional) Tu API key de Google Gemini si utilizas funciones de IA. |

---

## 🚀 Despliegue

El archivo `Dockerfile` ya está preconfigurado para instalar todas las dependencias necesarias (`ffmpeg`, `python`, etc.) y arrancar el archivo `main.py` de forma automática. ¡Simplemente sube los archivos de este repositorio a tu Space y disfruta!
