@echo off
echo ========================================
echo Iniciando Servidor Web y Bot de Telegram...
echo ========================================

start /b python dummy_server.py
python main.py

pause
