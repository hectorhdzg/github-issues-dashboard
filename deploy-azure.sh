#!/usr/bin/env bash

# Azure deployment script for GitHub Issues Dashboard
echo "🚀 Deploying GitHub Issues Dashboard to Azure..."

# Configuration variables (update these with your values)
RESOURCE_GROUP="github-issues-rg"
APP_SERVICE_PLAN="github-issues-plan"
WEB_APP_NAME="github-issues-dashboard"
LOCATION="East US"

echo "📋 Configuration:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  App Service Plan: $APP_SERVICE_PLAN"
echo "  Web App Name: $WEB_APP_NAME"
echo "  Location: $LOCATION"
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI is not installed. Please install it first:"
    echo "   https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Login check
echo "🔐 Checking Azure login status..."
if ! az account show &> /dev/null; then
    echo "Please login to Azure:"
    az login
fi

# Create resource group
echo "📦 Creating resource group..."
az group create --name $RESOURCE_GROUP --location "$LOCATION"

# Create App Service plan (Linux, Free tier)
echo "⚙️ Creating App Service plan..."
az appservice plan create \
    --name $APP_SERVICE_PLAN \
    --resource-group $RESOURCE_GROUP \
    --sku F1 \
    --is-linux

# Create Web App
echo "🌐 Creating Web App..."
az webapp create \
    --resource-group $RESOURCE_GROUP \
    --plan $APP_SERVICE_PLAN \
    --name $WEB_APP_NAME \
    --runtime "PYTHON|3.11" \
    --deployment-local-git

# Configure startup command
echo "⚙️ Configuring startup command..."
az webapp config set \
    --resource-group $RESOURCE_GROUP \
    --name $WEB_APP_NAME \
    --startup-file "gunicorn --bind 0.0.0.0:\$PORT --workers 1 --timeout 300 app:app"

# Set environment variables
echo "🔧 Setting environment variables..."
az webapp config appsettings set \
    --resource-group $RESOURCE_GROUP \
    --name $WEB_APP_NAME \
    --settings \
        FLASK_ENV=production \
        SCM_DO_BUILD_DURING_DEPLOYMENT=true

# Deploy code
echo "📤 Deploying application code..."
# Get deployment URL
DEPLOY_URL=$(az webapp deployment source config-local-git \
    --resource-group $RESOURCE_GROUP \
    --name $WEB_APP_NAME \
    --query url -o tsv)

# Add Azure remote
git remote add azure $DEPLOY_URL 2>/dev/null || git remote set-url azure $DEPLOY_URL

# Deploy
git add .
git commit -m "Deploy to Azure"
git push azure main

# Get the app URL
APP_URL=$(az webapp show \
    --resource-group $RESOURCE_GROUP \
    --name $WEB_APP_NAME \
    --query defaultHostName -o tsv)

echo ""
echo "🎉 Deployment completed!"
echo "📊 Your dashboard is available at: https://$APP_URL"
echo "🔧 Azure Portal: https://portal.azure.com"
echo ""
echo "📝 Useful commands:"
echo "  View logs: az webapp log tail --resource-group $RESOURCE_GROUP --name $WEB_APP_NAME"
echo "  Stop app:  az webapp stop --resource-group $RESOURCE_GROUP --name $WEB_APP_NAME"
echo "  Start app: az webapp start --resource-group $RESOURCE_GROUP --name $WEB_APP_NAME"
echo ""
