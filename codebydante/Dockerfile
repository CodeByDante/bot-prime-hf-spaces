# --- STAGE 1: Build the React Frontend ---
FROM node:18 AS build-stage
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# --- STAGE 2: Run the Python Bot + FastAPI Server ---
FROM python:3.11-slim
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requerimientos e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el build del frontend
COPY --from=build-stage /app/dist /app/dist

# Copiar el código del bot
COPY bot_telegram /app/bot_telegram
WORKDIR /app/bot_telegram

# Exponer el puerto de Hugging Face (7860)
EXPOSE 7860

# El comando de inicio será correr el bot
CMD ["python", "bot.py"]
