@echo off
title Bot Unidor - Telegram
color 0a

echo ========================================================
echo             INICIANDO BOT UNIDOR DE VIDEOS
echo ========================================================
echo.

:: Instalar dependencias
pip install -r requirements.txt --quiet

:loop
echo [Ejecutando] Iniciando bot con sesion "sesion"...
python app.py
echo.
echo ========================================================
echo El bot se ha detenido/reiniciado. Reiniciando en 3 segundos...
echo ========================================================
timeout /t 3
goto loop
