@echo off
REM Lancer le serveur PowerShell
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "start_server.ps1"
pause
