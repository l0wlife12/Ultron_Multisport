@echo off
REM Script de déploiement Railway pour ULTRON
REM Usage: deploy-railway.bat

echo.
echo ============================================================
echo ULTRON - Deployment to Railway
echo ============================================================
echo.

REM Check if git is available
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git n'est pas installé ou n'est pas dans le PATH
    pause
    exit /b 1
)

REM Check if railway CLI is available
cmd /c npx @railway/cli --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: Railway CLI not found. Installing...
    cmd /c npm install -g @railway/cli --force
)

echo.
echo [1/4] Vérification du statut Git...
git status

echo.
echo [2/4] Commit des changements...
set /p commit_msg="Entrez le message de commit (default: 'deploy: Update ULTRON'): "
if "%commit_msg%"=="" set commit_msg=deploy: Update ULTRON

git add .
git commit -m "%commit_msg%"

echo.
echo [3/4] Vérification de la configuration Railway...
cmd /c npx @railway/cli env list

echo.
echo [4/4] Redéploiement sur Railway...
echo.
echo Note: Si vous avez modifié TELEGRAM_TOKEN, assurez-vous qu'il est défini:
echo   railway env set TELEGRAM_TOKEN="votre_token_ici"
echo.
pause

cmd /c npx @railway/cli up

echo.
echo ============================================================
echo Déploiement complété!
echo.
echo Pour voir les logs:
echo   railway logs -f
echo.
echo Pour vérifier le statut:
echo   railway status
echo ============================================================
echo.
pause
