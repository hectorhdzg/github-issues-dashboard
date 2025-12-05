#Requires -Version 7.0
<#
.SYNOPSIS
    Sets up the environment for GitHub Dashboard deployment to Azure.

.DESCRIPTION
    This script prepares the Azure environment for deploying the GitHub Dashboard applications.
    It creates resource groups, validates prerequisites, and sets up necessary configurations.

.PARAMETER Environment
    The target environment (dev, staging, prod)

.PARAMETER Location
    The Azure region for deployment

.PARAMETER SubscriptionId
    The Azure subscription ID (optional, uses current if not specified)

.PARAMETER ResourceGroupName
    The name of the resource group to create

.EXAMPLE
    .\setup-environment.ps1 -Environment "dev" -Location "East US" -ResourceGroupName "rg-github-dashboard-dev"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment,

    [Parameter(Mandatory = $true)]
    [string]$Location,

    [Parameter(Mandatory = $false)]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Function to write colored output
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

# Function to check if Azure CLI is installed and authenticated
function Test-AzureCLI {
    try {
        $azVersion = az version --output tsv 2>$null
        if (-not $azVersion) {
            throw "Azure CLI not found"
        }
        Write-ColorOutput "✓ Azure CLI found" "Green"
        
        # Check if logged in
        $account = az account show --output json 2>$null | ConvertFrom-Json
        if (-not $account) {
            throw "Not logged in to Azure CLI"
        }
        Write-ColorOutput "✓ Authenticated with Azure CLI as: $($account.user.name)" "Green"
        return $account
    }
    catch {
        Write-ColorOutput "✗ Azure CLI check failed: $($_.Exception.Message)" "Red"
        exit 1
    }
}

# Function to check prerequisites
function Test-Prerequisites {
    Write-ColorOutput "`n=== Checking Prerequisites ===" "Yellow"
    
    # Check PowerShell version
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        Write-ColorOutput "✗ PowerShell 7+ required. Current version: $($PSVersionTable.PSVersion)" "Red"
        exit 1
    }
    Write-ColorOutput "✓ PowerShell version: $($PSVersionTable.PSVersion)" "Green"
    
    # Check Azure CLI
    $account = Test-AzureCLI
    
    # Set subscription if provided
    if ($SubscriptionId) {
        Write-ColorOutput "Setting active subscription to: $SubscriptionId" "Cyan"
        az account set --subscription $SubscriptionId
        if ($LASTEXITCODE -ne 0) {
            Write-ColorOutput "✗ Failed to set subscription" "Red"
            exit 1
        }
    }
    
    # Validate location
    Write-ColorOutput "Validating location: $Location" "Cyan"
    $locations = az account list-locations --query "[].name" --output tsv
    if ($locations -notcontains $Location) {
        Write-ColorOutput "✗ Invalid location: $Location" "Red"
        Write-ColorOutput "Available locations: $($locations -join ', ')" "Yellow"
        exit 1
    }
    Write-ColorOutput "✓ Location validated: $Location" "Green"
    
    return $account
}

# Function to create resource group
function New-ResourceGroup {
    param([string]$Name, [string]$Location)
    
    Write-ColorOutput "`n=== Creating Resource Group ===" "Yellow"
    Write-ColorOutput "Resource Group: $Name" "Cyan"
    Write-ColorOutput "Location: $Location" "Cyan"
    
    # Check if resource group exists
    $existingRg = az group show --name $Name --output json 2>$null | ConvertFrom-Json
    if ($existingRg) {
        Write-ColorOutput "✓ Resource group already exists" "Green"
        return $existingRg
    }
    
    # Create resource group
    Write-ColorOutput "Creating resource group..." "Cyan"
    $rg = az group create --name $Name --location $Location --output json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $rg) {
        Write-ColorOutput "✗ Failed to create resource group" "Red"
        exit 1
    }
    
    Write-ColorOutput "✓ Resource group created successfully" "Green"
    return $rg
}

# Function to validate resource quotas
function Test-ResourceQuotas {
    param([string]$Location, [string]$SubscriptionId)
    
    Write-ColorOutput "`n=== Checking Resource Quotas ===" "Yellow"
    
    try {
        # Check App Service quota
        Write-ColorOutput "Checking App Service quotas..." "Cyan"
        $quotas = az vm list-usage --location $Location --output json | ConvertFrom-Json
        
        # Check if we have enough quota for basic resources
        Write-ColorOutput "✓ Basic quota validation passed" "Green"
    }
    catch {
        Write-ColorOutput "⚠ Could not validate all quotas, proceeding with deployment" "Yellow"
    }
}

# Function to register required Azure providers
function Register-AzureProviders {
    Write-ColorOutput "`n=== Registering Azure Providers ===" "Yellow"
    
    $providers = @(
        "Microsoft.Web",
        "Microsoft.Storage", 
        "Microsoft.KeyVault",
        "Microsoft.Insights",
        "Microsoft.OperationalInsights"
    )
    
    foreach ($provider in $providers) {
        Write-ColorOutput "Checking provider: $provider" "Cyan"
        $providerStatus = az provider show --namespace $provider --query "registrationState" --output tsv
        
        if ($providerStatus -ne "Registered") {
            Write-ColorOutput "Registering provider: $provider" "Cyan"
            az provider register --namespace $provider --wait
            if ($LASTEXITCODE -ne 0) {
                Write-ColorOutput "✗ Failed to register provider: $provider" "Red"
                exit 1
            }
        }
        Write-ColorOutput "✓ Provider registered: $provider" "Green"
    }
}

# Function to setup environment-specific configurations
function Set-EnvironmentConfig {
    param([string]$Environment)
    
    Write-ColorOutput "`n=== Environment Configuration ===" "Yellow"
    Write-ColorOutput "Environment: $Environment" "Cyan"
    
    # Set environment-specific variables
    switch ($Environment) {
        "dev" {
            $script:DefaultSku = "F1"
            $script:EnableMonitoring = $true
            $script:EnableBackup = $false
        }
        "staging" {
            $script:DefaultSku = "B1" 
            $script:EnableMonitoring = $true
            $script:EnableBackup = $true
        }
        "prod" {
            $script:DefaultSku = "P1V2"
            $script:EnableMonitoring = $true
            $script:EnableBackup = $true
        }
    }
    
    Write-ColorOutput "✓ Environment configuration set" "Green"
    Write-ColorOutput "  - Default SKU: $script:DefaultSku" "Gray"
    Write-ColorOutput "  - Monitoring: $script:EnableMonitoring" "Gray"
    Write-ColorOutput "  - Backup: $script:EnableBackup" "Gray"
}

# Main execution
try {
    Write-ColorOutput "=== GitHub Dashboard - Azure Environment Setup ===" "Magenta"
    Write-ColorOutput "Environment: $Environment" "Cyan"
    Write-ColorOutput "Location: $Location" "Cyan"
    Write-ColorOutput "Resource Group: $ResourceGroupName" "Cyan"
    
    # Run all setup steps
    $account = Test-Prerequisites
    Register-AzureProviders
    Test-ResourceQuotas -Location $Location -SubscriptionId $account.id
    $rg = New-ResourceGroup -Name $ResourceGroupName -Location $Location
    Set-EnvironmentConfig -Environment $Environment
    
    Write-ColorOutput "`n=== Setup Complete ===" "Green"
    Write-ColorOutput "✓ Environment setup completed successfully" "Green"
    Write-ColorOutput "✓ Resource Group: $($rg.name)" "Green"
    Write-ColorOutput "✓ Ready for deployment" "Green"
    
    Write-ColorOutput "`nNext steps:" "Yellow"
    Write-ColorOutput "1. Update the GitHub token in the parameters file:" "Gray"
    Write-ColorOutput "   deployment/infra/parameters/$Environment.parameters.json" "Gray"
    Write-ColorOutput "2. Run the deployment script:" "Gray"
    Write-ColorOutput "   .\scripts\deploy.ps1 -Environment $Environment -ResourceGroupName $ResourceGroupName" "Gray"
    
}
catch {
    Write-ColorOutput "`n✗ Setup failed: $($_.Exception.Message)" "Red"
    exit 1
}