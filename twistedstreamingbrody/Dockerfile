# Usa una imagen oficial de Python ligera
FROM python:3.11-slim

# Evita que Python escriba archivos .pyc y fuerza salida de consola en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Crea un usuario no root (Requisito estricto de Hugging Face Spaces)
RUN useradd -m -u 1000 user

# Cambia al usuario 'user'
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Directorio de trabajo
WORKDIR /app

# Copia los archivos del bot asegurando que el propietario sea 'user'
COPY --chown=user . /app

# Instala las dependencias necesarias
RUN pip install --no-cache-dir -r requirements.txt

# Expone el puerto 7860 para la página fantasma de Hugging Face
EXPOSE 7860

# Ejecuta el bot de Telegram
CMD ["python", "main.py"]
