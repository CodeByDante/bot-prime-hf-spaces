@echo off
echo.
echo ==============================================
echo Instalando dependencias del Bot...
echo ==============================================
echo.

echo [1/2] Descargando modulos de Go...
go mod download
go mod tidy

echo.
echo [2/2] Iniciando Telegram File Stream Bot...
echo ==============================================
echo.
go run ./cmd/fsb run
pause
