# 1. Usar Node 20
FROM node:20-slim

# 2. Instalar Python, pip y dependencias de sistema para PDF/Imágenes
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-full \
    build-essential \
    libvips-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. Copiar archivos de dependencias primero (para cache)
COPY package.json package-lock.json* ./
COPY requirements.txt ./

# 4. Instalar dependencias de Node (incluyendo devDeps para el build)
RUN npm install

# 5. Instalar dependencias de Python
# Usamos --break-system-packages porque en imágenes nuevas de Debian/Ubuntu es necesario
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# 6. Copiar todo el código
COPY . .

# 7. IMPORTANTE: Construir el Frontend
# Si tienes errores de TypeScript, podrías usar: RUN npm run build || true (solo para debug)
RUN npm run build

# 8. Permisos para carpetas de descargas
RUN mkdir -p downloads && chmod 777 downloads

# 9. Hugging Face usa el puerto 7860 por defecto
ENV PORT=7860
EXPOSE 7860

# 10. Comando para arrancar el servidor de Node
# Asegúrate de que tu server.js escuche en el puerto process.env.PORT
CMD ["node", "server.js"]
