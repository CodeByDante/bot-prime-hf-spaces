@echo off
title Lanzador Convertidor QH
echo --------------------------------------------------
echo      🚀 INICIANDO CONVERTIDOR QH
echo --------------------------------------------------

:: Intentar activar entorno virtual si existe
if exist .venv\Scripts\activate (
    echo 🛠 Activando entorno virtual...
    call .venv\Scripts\activate
) else if exist venv\Scripts\activate (
    echo 🛠 Activando entorno virtual venv ...
    call venv\Scripts\activate
) else (
    echo ⚠️ Aviso: No se detecto entorno virtual, usando Python global.
)

echo 🤖 Iniciando bot en main.py...
python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ ERROR: El bot se detuvo inesperadamente.
    echo 👉 Asegurate de haber ejecutado start.bat primero.
)

echo --------------------------------------------------
echo ⚠️ Bot detenido.
echo --------------------------------------------------
pause
