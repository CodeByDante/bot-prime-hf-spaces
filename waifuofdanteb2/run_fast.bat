@echo off
title Twisted Brody Bot Pro (Fast)
cls
echo 🚀 Iniciando sin verificar dependencias...
:loop
python main.py
echo.
echo ⚠️ El bot se ha detenido o ha ocurrido un error.
echo 🔄 Reiniciando en 5 segundos...
timeout /t 5
goto loop
