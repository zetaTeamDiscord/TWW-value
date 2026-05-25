@echo off
title ValueListBot - Discord Bot
color 0A
echo.
echo ================================================
echo        VALUELIST BOT - DEMARRAGE
echo ================================================
echo.

REM Va dans le dossier du bot
cd /d "C:\Users\liam\Downloads\TESTREPO"

REM Lance le bot
echo Demarrage du bot...
python Main.py

REM Si le bot s'arrete, affiche un message
echo.
echo ================================================
echo    Le bot s'est arrete
echo    Appuie sur une touche pour fermer
echo ================================================
pause