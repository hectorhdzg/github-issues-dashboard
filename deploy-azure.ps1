# Azure deployment script for GitHub Issues Dashboard (PowerShell)
Write-Host "🚀 Deploying GitHub Issues Dashboard to Azure..." -ForegroundColor Green

# Configuration variables (update these with your values)
$RESOURCE_GROUP = "github-issues-rg"
$APP_SERVICE_PLAN = "github-issues-plan"
$WEB_APP_NAME = "github-issues-dashboard"
$LOCATION = "East US"

Write-Host "📋 Configuration:" -ForegroundColor Yellow
Write-Host "  Resource Group: $RESOURCE_GROUP"
Write-Host "  App Service Plan: $APP_SERVICE_PLAN"
Write-Host "  Web App Name: $WEB_APP_NAME"
Write-Host "  Location: $LOCATION"
Write-Host ""

# Check if Azure CLI is installed
if (!(Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Azure CLI is not installed. Please install it first:" -ForegroundColor Red
    Write-Host "   https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
}

# Login check
Write-Host "🔐 Checking Azure login status..." -ForegroundColor Blue
try {
    az account show | Out-Null
} catch {
    Write-Host "Please login to Azure:"
    az login
}

# Create resource group
Write-Host "📦 Creating resource group..." -ForegroundColor Blue
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create App Service plan (Linux, Free tier)
Write-Host "⚙️ Creating App Service plan..." -ForegroundColor Blue
az appservice plan create `
    --name $APP_SERVICE_PLAN `
    --resource-group $RESOURCE_GROUP `
    --sku F1 `
    --is-linux

# Create Web App
Write-Host "🌐 Creating Web App..." -ForegroundColor Blue
az webapp create `
    --resource-group $RESOURCE_GROUP `
    --plan $APP_SERVICE_PLAN `
    --name $WEB_APP_NAME `
    --runtime "PYTHON|3.11" `
    --deployment-local-git

# Configure startup command
Write-Host "⚙️ Configuring startup command..." -ForegroundColor Blue
az webapp config set `
    --resource-group $RESOURCE_GROUP `
    --name $WEB_APP_NAME `
    --startup-file "gunicorn --bind 0.0.0.0:`$PORT --workers 1 --timeout 300 app:app"

# Set environment variables
Write-Host "🔧 Setting environment variables..." -ForegroundColor Blue
az webapp config appsettings set `
    --resource-group $RESOURCE_GROUP `
    --name $WEB_APP_NAME `
    --settings `
        FLASK_ENV=production `
        SCM_DO_BUILD_DURING_DEPLOYMENT=true

# Deploy code
Write-Host "📤 Deploying application code..." -ForegroundColor Blue

# Get deployment URL
$DEPLOY_URL = az webapp deployment source config-local-git `
    --resource-group $RESOURCE_GROUP `
    --name $WEB_APP_NAME `
    --query url -o tsv

# Add Azure remote
try {
    git remote add azure $DEPLOY_URL 2>$null
} catch {
    git remote set-url azure $DEPLOY_URL
}

# Deploy
git add .
git commit -m "Deploy to Azure"
git push azure main

# Get the app URL
$APP_URL = az webapp show `
    --resource-group $RESOURCE_GROUP `
    --name $WEB_APP_NAME `
    --query defaultHostName -o tsv

Write-Host ""
Write-Host "🎉 Deployment completed!" -ForegroundColor Green
Write-Host "📊 Your dashboard is available at: https://$APP_URL" -ForegroundColor Cyan
Write-Host "🔧 Azure Portal: https://portal.azure.com" -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 Useful commands:" -ForegroundColor Yellow
Write-Host "  View logs: az webapp log tail --resource-group $RESOURCE_GROUP --name $WEB_APP_NAME"
Write-Host "  Stop app:  az webapp stop --resource-group $RESOURCE_GROUP --name $WEB_APP_NAME"
Write-Host "  Start app: az webapp start --resource-group $RESOURCE_GROUP --name $WEB_APP_NAME"
Write-Host ""
