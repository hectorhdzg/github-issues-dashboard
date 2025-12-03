#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy minimal GitHub Issues Dashboard to Azure App Service
.DESCRIPTION
    Deploys a simplified combined application with both dashboard and basic API
#>

param(
    [string]$ResourceGroup = "hectorh",
    [string]$AppName = "az-ghd-app-amzehuchpezkm"
)

Write-Host "🚀 Deploying Minimal GitHub Issues Dashboard" -ForegroundColor Green
Write-Host "App: $AppName" -ForegroundColor Cyan

try {
    # Ensure we're in the right directory
    Set-Location "c:\Scripts\GitHub-Issues-Dashboard"

    # Create temporary deployment directory
    $deployDir = "temp_deploy"
    if (Test-Path $deployDir) {
        Remove-Item $deployDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $deployDir | Out-Null

    Write-Host "`n📦 Creating deployment package..." -ForegroundColor Yellow

    # Copy minimal app as main app
    Copy-Item "minimal_app.py" "$deployDir/app.py"

    # Copy dashboard templates and static files
    Copy-Item "githubDashboard/templates" "$deployDir/templates" -Recurse
    Copy-Item "githubDashboard/static" "$deployDir/static" -Recurse

    # Create requirements.txt
    @"
Flask>=2.0.0
Flask-CORS>=4.0.0
"@ | Out-File "$deployDir/requirements.txt" -Encoding utf8

    # Create startup.txt for Azure
    @"
python app.py
"@ | Out-File "$deployDir/startup.txt" -Encoding utf8

    Write-Host "✅ Package created" -ForegroundColor Green

    Write-Host "`n⚙️ Configuring Azure App Service..." -ForegroundColor Yellow

    # Set startup command
    az webapp config set --resource-group $ResourceGroup --name $AppName --startup-file "startup.txt"

    # Set Python version
    az webapp config set --resource-group $ResourceGroup --name $AppName --python-version "3.11"

    Write-Host "`n🚀 Deploying to Azure..." -ForegroundColor Yellow

    # Deploy using zip
    Compress-Archive -Path "$deployDir/*" -DestinationPath "deploy.zip" -Force
    az webapp deploy --resource-group $ResourceGroup --name $AppName --src-path "deploy.zip" --type zip

    Write-Host "`n✅ Deployment completed!" -ForegroundColor Green
    Write-Host "🌐 Your app is available at: https://$AppName.azurewebsites.net" -ForegroundColor Cyan

    # Cleanup
    Remove-Item $deployDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item "deploy.zip" -Force -ErrorAction SilentlyContinue

} catch {
    Write-Host "`n❌ Deployment failed: $_" -ForegroundColor Red
    exit 1
}