@echo off
title CodeByDante - Sistema Completo

echo ==========================================
echo    INICIANDO SISTEMA CODEBYDANTE
echo ==========================================

:: 1. Iniciar la página web (React/Vite)
echo [1/2] Iniciando Web App...
start cmd /k "npm run dev"

:: 2. Iniciar el Bot de Telegram (Python)
echo [2/2] Iniciando Bot de Telegram...
cd bot_telegram
start cmd /k "python bot.py"

echo.
echo ==========================================
echo    ¡SISTEMA EN LINEA! 
echo    Web en: http://localhost:5173 (o similar)
echo    Bot API en: http://localhost:8080
echo ==========================================
pause
