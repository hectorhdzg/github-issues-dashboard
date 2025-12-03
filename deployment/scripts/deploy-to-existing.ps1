#Requires -Version 7.0
<#
.SYNOPSIS
    Deploys GitHub Dashboard to existing Azure App Service.

.DESCRIPTION
    This script deploys the GitHub Dashboard applications to your existing Azure infrastructure
    in resource group 'hectorh' with App Service 'az-ghd-app-amzehuchpezkm'.

.PARAMETER AppType
    Which application to deploy: 'dashboard', 'sync', or 'both'

.PARAMETER GitHubToken
    GitHub personal access token for API access

.PARAMETER CreateSyncService
    Create a second App Service for the sync service

.EXAMPLE
    .\deploy-to-existing.ps1 -AppType "dashboard" -GitHubToken "ghp_xxxxx"

.EXAMPLE
    .\deploy-to-existing.ps1 -AppType "both" -GitHubToken "ghp_xxxxx" -CreateSyncService
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dashboard", "sync", "both")]
    [string]$AppType,

    [Parameter(Mandatory = $true)]
    [string]$GitHubToken,

    [Parameter(Mandatory = $false)]
    [switch]$CreateSyncService
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Your existing Azure resources
$ResourceGroupName = "hectorh"
$ExistingAppName = "az-ghd-app-amzehuchpezkm"
$AppInsightsName = "az-ghd-ai-amzehuchpezkm"
$SubscriptionId = "65b2f83e-7bf1-4be3-bafc-3a4163265a52"

# Function to write colored output
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

# Function to check prerequisites
function Test-Prerequisites {
    Write-ColorOutput "`n=== Checking Prerequisites ===" "Yellow"
    
    # Check Azure CLI
    try {
        $account = az account show --output json | ConvertFrom-Json
        Write-ColorOutput "✓ Azure CLI authenticated as: $($account.user.name)" "Green"
        
        # Set correct subscription
        az account set --subscription $SubscriptionId
        Write-ColorOutput "✓ Using subscription: $SubscriptionId" "Green"
        
    }
    catch {
        throw "Azure CLI not authenticated. Run 'az login' first."
    }

    # Check if project structure exists
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
    $DashboardPath = Join-Path $ProjectRoot "githubDashboard"
    $SyncPath = Join-Path $ProjectRoot "githubSync"
    
    if (-not (Test-Path $DashboardPath)) {
        throw "Dashboard application not found at: $DashboardPath"
    }
    if (-not (Test-Path $SyncPath)) {
        throw "Sync service not found at: $SyncPath"
    }
    
    Write-ColorOutput "✓ Application source code found" "Green"
    
    return @{
        ProjectRoot = $ProjectRoot
        DashboardPath = $DashboardPath
        SyncPath = $SyncPath
    }
}

# Function to get Application Insights connection string
function Get-AppInsightsConnectionString {
    Write-ColorOutput "Getting Application Insights connection string..." "Cyan"
    
    try {
        $appInsights = az monitor app-insights component show --app $AppInsightsName --resource-group $ResourceGroupName --output json | ConvertFrom-Json
        return $appInsights.connectionString
    }
    catch {
        Write-ColorOutput "⚠ Could not get Application Insights connection string: $($_.Exception.Message)" "Yellow"
        return ""
    }
}

# Function to create sync service if requested
function New-SyncService {
    if (-not $CreateSyncService) {
        return $null
    }
    
    Write-ColorOutput "`n=== Creating Sync Service ===" "Yellow"
    
    $syncServiceName = "az-ghd-sync-$(Get-Random -Minimum 1000 -Maximum 9999)"
    
    # Get the App Service Plan from existing app
    $existingApp = az webapp show --resource-group $ResourceGroupName --name $ExistingAppName --output json | ConvertFrom-Json
    $appServicePlanId = $existingApp.serverFarmId
    $appServicePlanName = Split-Path $appServicePlanId -Leaf
    
    Write-ColorOutput "Creating sync service: $syncServiceName" "Cyan"
    Write-ColorOutput "Using App Service Plan: $appServicePlanName" "Gray"
    
    # Create the sync service app
    $syncApp = az webapp create `
        --resource-group $ResourceGroupName `
        --plan $appServicePlanName `
        --name $syncServiceName `
        --runtime "PYTHON:3.11" `
        --output json | ConvertFrom-Json
    
    if ($LASTEXITCODE -ne 0 -or -not $syncApp) {
        throw "Failed to create sync service"
    }
    
    Write-ColorOutput "✓ Sync service created: $syncServiceName" "Green"
    return $syncServiceName
}

# Function to configure app settings
function Set-AppConfiguration {
    param(
        [string]$AppName,
        [string]$AppType,
        [string]$AppInsightsConnectionString,
        [string]$SyncServiceUrl = ""
    )
    
    Write-ColorOutput "Configuring $AppType settings for $AppName..." "Cyan"
    
    # Base settings for all apps
    $settings = @(
        "ENVIRONMENT=production",
        "GITHUB_TOKEN=$GitHubToken",
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTHONUNBUFFERED=1"
    )
    
    # Add Application Insights if available
    if ($AppInsightsConnectionString) {
        $settings += "APPLICATIONINSIGHTS_CONNECTION_STRING=$AppInsightsConnectionString"
    }
    
    # App-specific settings
    if ($AppType -eq "sync") {
        $settings += @(
            "PORT=8000",
            "FLASK_APP=src/app.py",
            "DATABASE_PATH=/home/site/wwwroot/data/github_issues.db"
        )
    }
    elseif ($AppType -eq "dashboard") {
        $settings += @(
            "PORT=8001", 
            "FLASK_APP=src/app.py"
        )
        
        if ($SyncServiceUrl) {
            $settings += "SYNC_SERVICE_URL=$SyncServiceUrl"
        }
    }
    
    # Apply settings
    az webapp config appsettings set --resource-group $ResourceGroupName --name $AppName --settings $settings --output none
    
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "✓ App settings configured for $AppName" "Green"
    } else {
        Write-ColorOutput "✗ Failed to configure app settings for $AppName" "Red"
    }
}

# Function to deploy application
function Deploy-Application {
    param(
        [string]$AppName,
        [string]$AppType,
        [string]$SourcePath
    )
    
    Write-ColorOutput "`n=== Deploying $AppType to $AppName ===" "Yellow"
    
    # Create deployment package
    $tempDir = Join-Path $env:TEMP "github-dashboard-$AppType-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    
    try {
        # Copy application files
        if ($AppType -eq "sync") {
            Copy-Item -Path (Join-Path $SourcePath "src") -Destination $tempDir -Recurse
            Copy-Item -Path (Join-Path $SourcePath "data") -Destination $tempDir -Recurse -ErrorAction SilentlyContinue
            Copy-Item -Path (Join-Path $SourcePath "setup") -Destination $tempDir -Recurse -ErrorAction SilentlyContinue
            Copy-Item -Path (Join-Path $SourcePath "requirements.txt") -Destination $tempDir -ErrorAction SilentlyContinue
        }
        elseif ($AppType -eq "dashboard") {
            Copy-Item -Path (Join-Path $SourcePath "src") -Destination $tempDir -Recurse
            Copy-Item -Path (Join-Path $SourcePath "templates") -Destination $tempDir -Recurse
            Copy-Item -Path (Join-Path $SourcePath "static") -Destination $tempDir -Recurse
            Copy-Item -Path (Join-Path $SourcePath "requirements.txt") -Destination $tempDir -ErrorAction SilentlyContinue
        }
        
        # Create requirements.txt if it doesn't exist
        $requirementsPath = Join-Path $tempDir "requirements.txt"
        if (-not (Test-Path $requirementsPath)) {
            if ($AppType -eq "sync") {
                @"
Flask==3.0.3
Flask-CORS==5.0.0
requests==2.31.0
gunicorn==23.0.0
APScheduler==3.10.4
"@ | Set-Content $requirementsPath
            } else {
                @"
Flask==3.0.3
requests==2.31.0
gunicorn==23.0.0
"@ | Set-Content $requirementsPath
            }
        }
        
        # Create startup script
        $startupScript = if ($AppType -eq "sync") {
            "gunicorn --bind 0.0.0.0:8000 --chdir src app:app"
        } else {
            "gunicorn --bind 0.0.0.0:8001 --chdir src app:app"
        }
        
        # Set startup command
        az webapp config set --resource-group $ResourceGroupName --name $AppName --startup-file $startupScript --output none
        
        # Create zip package
        $zipPath = "$tempDir.zip"
        Compress-Archive -Path "$tempDir\*" -DestinationPath $zipPath -Force
        
        # Deploy via zip
        Write-ColorOutput "Uploading deployment package..." "Cyan"
        az webapp deployment source config-zip --resource-group $ResourceGroupName --name $AppName --src $zipPath --output none
        
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "✓ $AppType deployed successfully to $AppName" "Green"
            $appUrl = "https://$AppName.azurewebsites.net"
            Write-ColorOutput "   URL: $appUrl" "Gray"
            return $appUrl
        } else {
            throw "Deployment failed for $AppName"
        }
    }
    finally {
        # Cleanup
        if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue }
        if (Test-Path $zipPath) { Remove-Item $zipPath -Force -ErrorAction SilentlyContinue }
    }
}

# Function to test deployment
function Test-Deployment {
    param([string]$Url, [string]$AppType)
    
    Write-ColorOutput "Testing $AppType at $Url..." "Cyan"
    
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 30 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-ColorOutput "✓ $AppType is responding (HTTP $($response.StatusCode))" "Green"
            return $true
        }
    }
    catch {
        Write-ColorOutput "✗ $AppType test failed: $($_.Exception.Message)" "Red"
        return $false
    }
    return $false
}

# Main execution
try {
    Write-ColorOutput "=== GitHub Dashboard - Deploy to Existing Azure Resources ===" "Magenta"
    Write-ColorOutput "Resource Group: $ResourceGroupName" "Cyan"
    Write-ColorOutput "Existing App: $ExistingAppName" "Cyan"
    Write-ColorOutput "Deployment Type: $AppType" "Cyan"
    
    # Check prerequisites
    $paths = Test-Prerequisites
    
    # Get Application Insights connection string
    $appInsightsConnectionString = Get-AppInsightsConnectionString
    
    # Create sync service if requested
    $syncServiceName = New-SyncService
    $syncServiceUrl = if ($syncServiceName) { "https://$syncServiceName.azurewebsites.net" } else { "" }
    
    # Deploy applications based on type
    $deployedUrls = @()
    
    if ($AppType -eq "dashboard" -or $AppType -eq "both") {
        # Configure and deploy dashboard to existing app
        Set-AppConfiguration -AppName $ExistingAppName -AppType "dashboard" -AppInsightsConnectionString $appInsightsConnectionString -SyncServiceUrl $syncServiceUrl
        $dashboardUrl = Deploy-Application -AppName $ExistingAppName -AppType "dashboard" -SourcePath $paths.DashboardPath
        $deployedUrls += @{ Type = "Dashboard"; Url = $dashboardUrl; AppName = $ExistingAppName }
    }
    
    if (($AppType -eq "sync" -or $AppType -eq "both") -and $syncServiceName) {
        # Configure and deploy sync service to new app
        Set-AppConfiguration -AppName $syncServiceName -AppType "sync" -AppInsightsConnectionString $appInsightsConnectionString
        $syncUrl = Deploy-Application -AppName $syncServiceName -AppType "sync" -SourcePath $paths.SyncPath
        $deployedUrls += @{ Type = "Sync Service"; Url = $syncUrl; AppName = $syncServiceName }
    }
    elseif ($AppType -eq "sync" -and -not $CreateSyncService) {
        # Deploy sync service to existing app
        Set-AppConfiguration -AppName $ExistingAppName -AppType "sync" -AppInsightsConnectionString $appInsightsConnectionString
        $syncUrl = Deploy-Application -AppName $ExistingAppName -AppType "sync" -SourcePath $paths.SyncPath
        $deployedUrls += @{ Type = "Sync Service"; Url = $syncUrl; AppName = $ExistingAppName }
    }
    
    # Test deployments
    Write-ColorOutput "`n=== Testing Deployments ===" "Yellow"
    foreach ($deployment in $deployedUrls) {
        Test-Deployment -Url $deployment.Url -AppType $deployment.Type
    }
    
    # Show results
    Write-ColorOutput "`n=== Deployment Complete! ===" "Green"
    Write-ColorOutput "🚀 GitHub Dashboard deployed successfully!" "Green"
    Write-ColorOutput "" "White"
    
    foreach ($deployment in $deployedUrls) {
        Write-ColorOutput "📱 $($deployment.Type): $($deployment.Url)" "Cyan"
        Write-ColorOutput "   App Service: $($deployment.AppName)" "Gray"
    }
    
    Write-ColorOutput "" "White"
    Write-ColorOutput "Next Steps:" "Yellow"
    Write-ColorOutput "1. Access your applications at the URLs above" "Gray"
    Write-ColorOutput "2. Configure GitHub repositories in the sync service" "Gray"
    Write-ColorOutput "3. Monitor performance in Application Insights: $AppInsightsName" "Gray"
    
    if ($deployedUrls.Count -gt 1) {
        Write-ColorOutput "4. The dashboard will automatically connect to the sync service" "Gray"
    }
    
}
catch {
    Write-ColorOutput "`n❌ Deployment failed: $($_.Exception.Message)" "Red"
    Write-ColorOutput "Check the Azure portal for detailed error information." "Yellow"
    exit 1
}