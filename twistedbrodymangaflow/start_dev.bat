@echo off
chcp 65001 > nul
title MangaFlow - Development Server
cls
echo.
echo    [1m[ MANGAFLOW FRONTEND ] [0m  [90m- ENTORNO DESARROLLO VITE [0m
echo    [90m------------------------------------------------------- [0m
echo.
npm run dev
pause
