@echo off
title Bot Party Mode
color 0A

echo Verificando entorno...

:: Intentar activar el entorno virtual si existe
if exist ".venv\Scripts\activate.bat" (
    echo [+] Entorno virtual detectado. Activando...
    call ".venv\Scripts\activate.bat"
) else (
    echo [!] Aviso: No se encontro el archivo de activacion en .venv.
    echo [!] Se intentara ejecutar con el Python del sistema directamente.
)

echo.
echo [+] Lanzando Bot...
echo.

python main.py

if errorlevel 1 (
    echo.
    echo [X] Error: El bot se ha detenido inesperadamente.
    echo [?] Asegurate de tener instaladas las dependencias: pip install -r requirements.txt
    echo.
    pause
) else (
    echo.
    echo [+] Bot finalizado correctamente.
    pause
)
