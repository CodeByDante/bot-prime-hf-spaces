# Usar una imagen base de Python ligera
FROM python:3.11-slim

# Instalar dependencias del sistema (FFmpeg es vital)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Crear un usuario para no correr como root (Requisito de HF)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Establecer directorio de trabajo
WORKDIR $HOME/app

# Copiar archivos de requerimientos e instalar
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY --chown=user . .

# El puerto 7860 es el estándar de HF Spaces
EXPOSE 7860

# Comando para arrancar el bot
CMD ["python", "main.py"]
