---
title: MiniaturasProBot
emoji: 🥳
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
---

# SmartVideoSplitterBot 🥳✂️

**SmartVideoSplitterBot** es una solución minimalista y de alto rendimiento para la gestión, división y procesamiento de videos de forma automatizada a través de Telegram. Diseñado para ser ligero, rápido y extremadamente intuitivo.

## 🚀 Funciones Principales

### 🥳 Modo Party (División de Video)
El núcleo del bot. Permite fragmentar videos pesados en trozos más pequeños según tres criterios:
- 🧩 **Por Partes**: Divide el video en un número exacto de fragmentos (ej: 3 partes iguales).
- ⏱ **Por Tiempo**: Corta el video cada X segundos o minutos (ej: cada 30 segundos).
- ✂️ **Por Rango**: Permite realizar cortes quirúrgicos indicando el inicio y el fin (ej: `00:10 00:50`).

### 🤖 Automatización Inteligente
- 🔄 **Modo Auto**: Procesa múltiples videos de forma consecutiva sin tener que reactivar el bot cada vez.
- 🟢 **Modo Fijo**: Permite establecer una configuración predeterminada para que el bot no pregunte nada y trabaje de forma 100% autónoma.
- 🚀 **Sistema de Colas**: Procesa los videos uno por uno (FIFO), gestionando las descargas y subidas de forma ordenada para no saturar el sistema.

### 📦 Gestión de Salida
- 📄 **Modo Doc**: Envía los resultados como archivos (Documentos) para evitar la compresión de Telegram.
- 📚 **Modo Agrup**: Envía los fragmentos en álbumes de hasta 10 elementos.
- 📦 **Modo ZIP**: Comprime todos los fragmentos en archivos .zip de máximo 1.9GB (con división automática en volúmenes para archivos gigantes).

## 🛠 Instalación y Uso Local

### Requisitos
1. Python 3.10+
2. FFmpeg (debe estar en el PATH del sistema).
3. Token de Bot de Telegram (@BotFather).

### Inicio Rápido
Simplemente ejecuta el archivo:
```bash
run.bat
```
El script detectará automáticamente tu entorno y lanzará el bot.

## ⚙️ Configuración
El bot utiliza Firebase para la persistencia de datos, lo que permite que cada usuario guarde sus preferencias de forma individual y privada.

---
**Desarrollado con ❤️ para un flujo de trabajo ultra-rápido.**
