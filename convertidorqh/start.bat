@echo off
title Instalador Convertidor QH
echo --------------------------------------------------
echo      🚀 INSTALADOR DE DEPENDENCIAS (QH)
echo --------------------------------------------------

:: Verificar si python esta en el PATH
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ ERROR: No se encontro 'python' en tu sistema.
    echo 👉 Por favor, instala Python y marcala la opcion "Add to PATH".
    pause
    exit
)

:: Crear venv si no existe
if not exist .venv (
    echo 📦 Creando entorno virtual .venv ...
    python -m venv .venv
)

:: Intentar activar
if exist .venv\Scripts\activate (
    echo 🛠 Activando entorno...
    call .venv\Scripts\activate
    echo 📥 Instalando librerias...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    echo ⚠️ No se pudo activar el entorno, instalando en Python global...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
)

echo --------------------------------------------------
echo ✅ LISTO: Ya puedes cerrar esta ventana y usar run.bat
echo --------------------------------------------------
pause
