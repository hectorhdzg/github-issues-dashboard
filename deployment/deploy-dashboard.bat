@echo off
REM Quick deployment batch file for GitHub Dashboard
REM Usage: deploy-dashboard.bat [optional-github-token]

echo.
echo ============================================
echo   GitHub Dashboard - Quick Deploy
echo ============================================
echo.
echo Deploying to: az-ghd-app-amzehuchpezkm.azurewebsites.net
echo App Type: Dashboard
echo.

if "%1"=="" (
    echo Deploying without GitHub token (can be configured later)
    powershell -ExecutionPolicy Bypass -File "%~dp0scripts\quick-deploy.ps1" -AppType "dashboard"
) else (
    echo Using provided GitHub token
    powershell -ExecutionPolicy Bypass -File "%~dp0scripts\quick-deploy.ps1" -GitHubToken "%1" -AppType "dashboard"
)

echo.
pause