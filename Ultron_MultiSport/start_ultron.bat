@echo off
REM ULTRON Bot Launcher for Windows

cd /d "C:\Users\jeffc\OneDrive - Collège Ahuntsic\Documents\SLot Machin Program"

:restart
echo ===============================================
echo ULTRON - Sports Betting Bot (Auto-Restart)
echo ===============================================
echo Launching bot...
echo.

python.exe ultron_bot_windows.py

if errorlevel 1 (
    echo Bot crashed, restarting in 5 seconds...
    timeout /t 5 /nobreak
    goto restart
) else (
    echo Bot stopped normally
    pause
)
