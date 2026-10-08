@echo off
title Registro de Cuentas Esclavas - Brody Prime
chcp 65001 > nul

:loop
cls
python login_accounts.py
echo.
echo =======================================================
echo ¿Deseas registrar otra cuenta?
echo - Presiona cualquier tecla para añadir otra.
echo - Cierra esta ventana para finalizar.
echo =======================================================
pause > nul
goto loop
