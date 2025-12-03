#Requires -Version 7.0
<#
.SYNOPSIS
    Deploys the GitHub Dashboard applications to Azure.

.DESCRIPTION
    This script deploys both the GitHub Sync Service and GitHub Dashboard 
    applications to Azure using Bicep templates and Azure CLI.

.PARAMETER Environment
    The target environment (dev, staging, prod)

.PARAMETER ResourceGroupName
    The name of the existing resource group

.PARAMETER Location
    The Azure region for deployment (optional, uses resource group location)

.PARAMETER GitHubToken
    GitHub personal access token (optional, can be set in parameters file)

.PARAMETER SkipBuild
    Skip building the applications before deployment

.PARAMETER WhatIf
    Preview the deployment without making changes

.EXAMPLE
    .\deploy.ps1 -Environment "dev" -ResourceGroupName "rg-github-dashboard-dev"

.EXAMPLE
    .\deploy.ps1 -Environment "prod" -ResourceGroupName "rg-github-dashboard-prod" -GitHubToken "ghp_xxx" -WhatIf
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory = $false)]
    [string]$Location,

    [Parameter(Mandatory = $false)]
    [string]$GitHubToken,

    [Parameter(Mandatory = $false)]
    [switch]$SkipBuild,

    [Parameter(Mandatory = $false)]
    [switch]$WhatIf
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Script variables
$ScriptRoot = Split-Path -Parent $PSScriptRoot
$InfraPath = Join-Path $ScriptRoot "infra"
$MainBicepFile = Join-Path $InfraPath "main.bicep"
$ParametersFile = Join-Path $InfraPath "parameters" "$Environment.parameters.json"
$DeploymentName = "github-dashboard-$Environment-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

# Function to write colored output
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

# Function to validate prerequisites
function Test-DeploymentPrerequisites {
    Write-ColorOutput "`n=== Validating Prerequisites ===" "Yellow"
    
    # Check if files exist
    if (-not (Test-Path $MainBicepFile)) {
        throw "Main Bicep file not found: $MainBicepFile"
    }
    Write-ColorOutput "✓ Main Bicep file found" "Green"
    
    if (-not (Test-Path $ParametersFile)) {
        throw "Parameters file not found: $ParametersFile"
    }
    Write-ColorOutput "✓ Parameters file found" "Green"
    
    # Check Azure CLI
    try {
        $account = az account show --output json | ConvertFrom-Json
        Write-ColorOutput "✓ Azure CLI authenticated as: $($account.user.name)" "Green"
    }
    catch {
        throw "Azure CLI not authenticated. Run 'az login' first."
    }
    
    # Check resource group
    try {
        $rg = az group show --name $ResourceGroupName --output json | ConvertFrom-Json
        Write-ColorOutput "✓ Resource group found: $($rg.name)" "Green"
        return $rg
    }
    catch {
        throw "Resource group not found: $ResourceGroupName"
    }
}

# Function to update parameters file with GitHub token
function Update-ParametersFile {
    param([string]$Token)
    
    if (-not $Token) {
        Write-ColorOutput "⚠ No GitHub token provided. Make sure to update the parameters file manually." "Yellow"
        return
    }
    
    Write-ColorOutput "Updating parameters file with GitHub token..." "Cyan"
    
    try {
        $parametersContent = Get-Content $ParametersFile -Raw | ConvertFrom-Json
        $parametersContent.parameters.githubToken.value = $Token
        $parametersContent | ConvertTo-Json -Depth 10 | Set-Content $ParametersFile
        Write-ColorOutput "✓ Parameters file updated" "Green"
    }
    catch {
        Write-ColorOutput "✗ Failed to update parameters file: $($_.Exception.Message)" "Red"
        throw
    }
}

# Function to build applications
function Build-Applications {
    if ($SkipBuild) {
        Write-ColorOutput "Skipping application build..." "Yellow"
        return
    }
    
    Write-ColorOutput "`n=== Building Applications ===" "Yellow"
    
    # Navigate to project root
    $ProjectRoot = Split-Path -Parent $ScriptRoot
    
    # Build sync service
    Write-ColorOutput "Building GitHub Sync Service..." "Cyan"
    $SyncPath = Join-Path $ProjectRoot "githubSync"
    Push-Location $SyncPath
    try {
        # Create requirements file if it doesn't exist
        if (-not (Test-Path "requirements.txt")) {
            Write-ColorOutput "Creating requirements.txt for sync service..." "Gray"
            @"
Flask==3.0.3
Flask-CORS==5.0.0
requests==2.31.0
gunicorn==23.0.0
APScheduler==3.10.4
"@ | Set-Content "requirements.txt"
        }
        Write-ColorOutput "✓ Sync service build prepared" "Green"
    }
    finally {
        Pop-Location
    }
    
    # Build dashboard
    Write-ColorOutput "Building GitHub Dashboard..." "Cyan"
    $DashboardPath = Join-Path $ProjectRoot "githubDashboard"
    Push-Location $DashboardPath
    try {
        # Create requirements file if it doesn't exist
        if (-not (Test-Path "requirements.txt")) {
            Write-ColorOutput "Creating requirements.txt for dashboard..." "Gray"
            @"
Flask==3.0.3
requests==2.31.0
gunicorn==23.0.0
"@ | Set-Content "requirements.txt"
        }
        Write-ColorOutput "✓ Dashboard build prepared" "Green"
    }
    finally {
        Pop-Location
    }
}

# Function to validate Bicep template
function Test-BicepTemplate {
    Write-ColorOutput "`n=== Validating Bicep Template ===" "Yellow"
    
    Write-ColorOutput "Running Bicep validation..." "Cyan"
    az deployment group validate `
        --resource-group $ResourceGroupName `
        --template-file $MainBicepFile `
        --parameters "@$ParametersFile" `
        --output none
    
    if ($LASTEXITCODE -ne 0) {
        throw "Bicep template validation failed"
    }
    Write-ColorOutput "✓ Bicep template validation passed" "Green"
}

# Function to preview deployment
function Show-DeploymentPreview {
    Write-ColorOutput "`n=== Deployment Preview ===" "Yellow"
    
    Write-ColorOutput "Generating deployment preview..." "Cyan"
    $whatIfResult = az deployment group what-if `
        --resource-group $ResourceGroupName `
        --template-file $MainBicepFile `
        --parameters "@$ParametersFile" `
        --result-format "FullResourcePayloads"
    
    Write-ColorOutput $whatIfResult "Gray"
    Write-ColorOutput "✓ Deployment preview generated" "Green"
}

# Function to deploy infrastructure
function Deploy-Infrastructure {
    Write-ColorOutput "`n=== Deploying Infrastructure ===" "Yellow"
    
    Write-ColorOutput "Starting deployment: $DeploymentName" "Cyan"
    Write-ColorOutput "Resource Group: $ResourceGroupName" "Gray"
    Write-ColorOutput "Environment: $Environment" "Gray"
    
    # Start deployment
    $deploymentResult = az deployment group create `
        --resource-group $ResourceGroupName `
        --template-file $MainBicepFile `
        --parameters "@$ParametersFile" `
        --name $DeploymentName `
        --output json | ConvertFrom-Json
    
    if ($LASTEXITCODE -ne 0 -or -not $deploymentResult) {
        throw "Infrastructure deployment failed"
    }
    
    Write-ColorOutput "✓ Infrastructure deployment completed" "Green"
    return $deploymentResult
}

# Function to deploy applications
function Deploy-Applications {
    param($DeploymentOutputs)
    
    Write-ColorOutput "`n=== Deploying Applications ===" "Yellow"
    
    $ProjectRoot = Split-Path -Parent $ScriptRoot
    
    # Deploy sync service
    Write-ColorOutput "Deploying GitHub Sync Service..." "Cyan"
    $syncServiceUrl = $DeploymentOutputs.syncServiceUrl.value
    
    # Create deployment package for sync service
    $SyncPath = Join-Path $ProjectRoot "githubSync"
    Push-Location $SyncPath
    try {
        # Deploy using zip deployment
        Compress-Archive -Path "src", "data", "setup", "requirements.txt" -DestinationPath "sync-deployment.zip" -Force
        
        # Get sync service name from URL
        $syncServiceName = ($syncServiceUrl -replace "https://", "" -replace ".azurewebsites.net", "")
        
        az webapp deployment source config-zip `
            --resource-group $ResourceGroupName `
            --name $syncServiceName `
            --src "sync-deployment.zip"
            
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "✓ Sync service deployed successfully" "Green"
        }
    }
    finally {
        Pop-Location
    }
    
    # Deploy dashboard
    Write-ColorOutput "Deploying GitHub Dashboard..." "Cyan"
    $dashboardUrl = $DeploymentOutputs.dashboardUrl.value
    
    $DashboardPath = Join-Path $ProjectRoot "githubDashboard"
    Push-Location $DashboardPath
    try {
        # Create deployment package for dashboard
        Compress-Archive -Path "src", "templates", "static", "requirements.txt" -DestinationPath "dashboard-deployment.zip" -Force
        
        # Get dashboard service name from URL
        $dashboardServiceName = ($dashboardUrl -replace "https://", "" -replace ".azurewebsites.net", "")
        
        az webapp deployment source config-zip `
            --resource-group $ResourceGroupName `
            --name $dashboardServiceName `
            --src "dashboard-deployment.zip"
            
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "✓ Dashboard deployed successfully" "Green"
        }
    }
    finally {
        Pop-Location
    }
}

# Function to show deployment results
function Show-DeploymentResults {
    param($DeploymentResult)
    
    Write-ColorOutput "`n=== Deployment Results ===" "Green"
    
    $outputs = $DeploymentResult.properties.outputs
    
    Write-ColorOutput "🚀 GitHub Dashboard Applications Deployed Successfully!" "Green"
    Write-ColorOutput "" "White"
    Write-ColorOutput "📊 Dashboard URL: $($outputs.dashboardUrl.value)" "Cyan"
    Write-ColorOutput "🔄 Sync Service URL: $($outputs.syncServiceUrl.value)" "Cyan"
    
    if ($outputs.keyVaultName.value) {
        Write-ColorOutput "🔐 Key Vault: $($outputs.keyVaultName.value)" "Gray"
    }
    if ($outputs.storageAccountName.value) {
        Write-ColorOutput "💾 Storage Account: $($outputs.storageAccountName.value)" "Gray"
    }
    
    Write-ColorOutput "" "White"
    Write-ColorOutput "Next Steps:" "Yellow"
    Write-ColorOutput "1. Verify applications are running at the URLs above" "Gray"
    Write-ColorOutput "2. Configure GitHub repositories in the sync service" "Gray"
    Write-ColorOutput "3. Run initial data synchronization" "Gray"
    Write-ColorOutput "4. Set up monitoring and alerts" "Gray"
}

# Main execution
try {
    Write-ColorOutput "=== GitHub Dashboard - Azure Deployment ===" "Magenta"
    Write-ColorOutput "Environment: $Environment" "Cyan"
    Write-ColorOutput "Resource Group: $ResourceGroupName" "Cyan"
    Write-ColorOutput "Deployment: $DeploymentName" "Cyan"
    
    # Validate prerequisites
    $resourceGroup = Test-DeploymentPrerequisites
    
    # Update parameters if GitHub token provided
    if ($GitHubToken) {
        Update-ParametersFile -Token $GitHubToken
    }
    
    # Build applications
    Build-Applications
    
    # Validate Bicep template
    Test-BicepTemplate
    
    # Show preview if requested
    if ($WhatIf) {
        Show-DeploymentPreview
        Write-ColorOutput "`nPreview completed. Use -WhatIf:$false to proceed with actual deployment." "Yellow"
        return
    }
    
    # Deploy infrastructure
    $deploymentResult = Deploy-Infrastructure
    
    # Deploy applications
    Deploy-Applications -DeploymentOutputs $deploymentResult.properties.outputs
    
    # Show results
    Show-DeploymentResults -DeploymentResult $deploymentResult
    
    Write-ColorOutput "`n✅ Deployment completed successfully!" "Green"
    
}
catch {
    Write-ColorOutput "`n❌ Deployment failed: $($_.Exception.Message)" "Red"
    Write-ColorOutput "Check the Azure portal for detailed error information." "Yellow"
    exit 1
}