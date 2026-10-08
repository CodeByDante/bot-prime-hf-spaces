@echo off
echo Iniciando sistema de descargas locales (Modo Una Ventana)...

:: Usamos npx para no obligar a instalar dependencias globales
:: -k mata ambos procesos si uno falla o se cierra
:: --names nos da etiquetas bonitas [BACK] [FRONT]
call npx -y concurrently -k -n "BACK,FRONT" -c "blue,magenta" "npm run server" "npm run dev"

pause
