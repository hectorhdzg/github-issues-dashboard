@echo off
REM Quick deployment batch file for GitHub Sync Service
REM Usage: deploy-sync.bat [your-github-token]

if "%1"=="" (
    echo Usage: deploy-sync.bat [your-github-token]
    echo Example: deploy-sync.bat ghp_xxxxxxxxxxxxx
    pause
    exit /b 1
)

echo.
echo ============================================
echo   GitHub Sync Service - Quick Deploy
echo ============================================
echo.
echo Deploying to: az-ghd-app-amzehuchpezkm.azurewebsites.net
echo App Type: Sync Service
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0scripts\quick-deploy.ps1" -GitHubToken "%1" -AppType "sync"

echo.
pause