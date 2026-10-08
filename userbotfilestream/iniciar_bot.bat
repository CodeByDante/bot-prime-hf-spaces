@echo off
title Userbot - Bot Prime
color 0b

echo ========================================================
echo             INICIANDO USERBOT PRIME
echo ========================================================
echo.

:: Instalar dependencias
pip install -r requirements.txt --quiet

echo [Stream Bot] Iniciando BrodyFileStreamBot en ventana separada...
start cmd /k "title Brody File Stream Bot && cd BrodyFileStreamBot && fsb.exe run"

echo [Userbot] Iniciando el userbot y conectando a Telegram...
python app.py

echo.
echo ========================================================
echo Proceso finalizado.
echo ========================================================
pause
