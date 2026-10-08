# --- ETAPA 1: Compilar la aplicación Go (BrodyFileStreamBot) ---
FROM golang:1.25-bookworm AS go-builder
WORKDIR /app
COPY BrodyFileStreamBot/go.mod BrodyFileStreamBot/go.sum ./
RUN go mod download
COPY BrodyFileStreamBot/ .
RUN go mod tidy
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/fsb -ldflags="-w -s" ./cmd/fsb

# --- ETAPA 2: Runtime Python ---
FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para OpenCV y utilidades generales (incluido FFMPEG)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no root con UID 1000 (requerido por Hugging Face)
RUN useradd -m -u 1000 user

# Configurar directorio de trabajo
WORKDIR /home/user/app

# Asegurar que el usuario no root sea propietario del directorio de trabajo
RUN chown -R user:user /home/user/app

# Cambiar al usuario no root para la instalación y ejecución
USER user

# Configurar variables de entorno para que Python encuentre los paquetes instalados en el espacio de usuario
ENV PATH="/home/user/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

# Actualizar pip (en el espacio de usuario)
RUN pip install --no-cache-dir --user --upgrade pip

# Instalar dependencias de Python (en el espacio de usuario)
# Nota: Usamos opencv-python-headless para evitar dependencias GUI innecesarias en servidores
RUN pip install --no-cache-dir --user \
    telethon \
    "opencv-python-headless<5" \
    aiohttp \
    curl_cffi \
    beautifulsoup4 \
    reportlab \
    firebase-admin \
    telegraph

# Copiar archivos del proyecto cambiando el propietario al usuario no root
COPY --chown=user:user . /home/user/app

# Copiar el binario de Go compilado desde el builder
COPY --from=go-builder --chown=user:user /app/fsb /home/user/app/BrodyFileStreamBot/fsb

# Crear carpeta de capturas (funcionará porque el usuario 1000 tiene permisos en su WORKDIR)
RUN mkdir -p capturas

# Exponer el puerto del servidor web
EXPOSE 7860

# Comando para iniciar la aplicación
CMD ["python", "-u", "app.py"]

