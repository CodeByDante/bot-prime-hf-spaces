@echo off
chcp 65001 > nul
title MangaFlow Engine - Local System
cls
echo.
echo    [1m[ MANGAFLOW ENGINE ] [0m  [90m- SISTEMA DE DESARROLLO LOCAL [0m
echo    [90m------------------------------------------------------- [0m
echo.
call npx -y concurrently --raw -k "npm run server --silent" "npm run dev --silent"
pause
