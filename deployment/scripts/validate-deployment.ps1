#Requires -Version 7.0
<#
.SYNOPSIS
    Validates the deployed GitHub Dashboard applications in Azure.

.DESCRIPTION
    This script performs post-deployment validation to ensure both applications
    are running correctly and all components are properly configured.

.PARAMETER Environment
    The target environment (dev, staging, prod)

.PARAMETER ResourceGroupName
    The name of the resource group (optional, will be derived if not provided)

.PARAMETER SkipHealthChecks
    Skip application health checks

.PARAMETER Detailed
    Show detailed validation results

.EXAMPLE
    .\validate-deployment.ps1 -Environment "dev"

.EXAMPLE
    .\validate-deployment.ps1 -Environment "prod" -ResourceGroupName "rg-github-dashboard-prod" -Detailed
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment,

    [Parameter(Mandatory = $false)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory = $false)]
    [switch]$SkipHealthChecks,

    [Parameter(Mandatory = $false)]
    [switch]$Detailed
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

# Function to test HTTP endpoint
function Test-HttpEndpoint {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30,
        [int]$ExpectedStatusCode = 200
    )
    
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec $TimeoutSeconds
        return @{
            Success = $response.StatusCode -eq $ExpectedStatusCode
            StatusCode = $response.StatusCode
            ResponseTime = $response.Headers["X-Response-Time"]
            Error = $null
        }
    }
    catch {
        return @{
            Success = $false
            StatusCode = $null
            ResponseTime = $null
            Error = $_.Exception.Message
        }
    }
}

# Function to discover resource group if not provided
function Get-ResourceGroup {
    param([string]$Environment)
    
    if ($ResourceGroupName) {
        return $ResourceGroupName
    }
    
    # Try common naming patterns
    $commonNames = @(
        "rg-github-dashboard-$Environment",
        "github-dashboard-$Environment-rg",
        "rg-githubdashboard-$Environment"
    )
    
    foreach ($name in $commonNames) {
        try {
            $rg = az group show --name $name --output json 2>$null | ConvertFrom-Json
            if ($rg) {
                Write-ColorOutput "✓ Found resource group: $name" "Green"
                return $name
            }
        }
        catch {
            # Continue searching
        }
    }
    
    throw "Could not find resource group for environment '$Environment'. Please specify -ResourceGroupName parameter."
}

# Function to get deployment outputs
function Get-DeploymentOutputs {
    param([string]$ResourceGroupName)
    
    Write-ColorOutput "Getting deployment information..." "Cyan"
    
    # Get the latest deployment
    $deployments = az deployment group list --resource-group $ResourceGroupName --query "[?starts_with(name, 'github-dashboard')]" --output json | ConvertFrom-Json
    
    if (-not $deployments -or $deployments.Count -eq 0) {
        throw "No GitHub Dashboard deployments found in resource group: $ResourceGroupName"
    }
    
    # Get the most recent successful deployment
    $latestDeployment = $deployments | Where-Object { $_.properties.provisioningState -eq "Succeeded" } | Sort-Object timestamp -Descending | Select-Object -First 1
    
    if (-not $latestDeployment) {
        throw "No successful deployments found"
    }
    
    Write-ColorOutput "✓ Found deployment: $($latestDeployment.name)" "Green"
    
    # Get deployment outputs
    $outputs = az deployment group show --resource-group $ResourceGroupName --name $latestDeployment.name --query "properties.outputs" --output json | ConvertFrom-Json
    
    return $outputs
}

# Function to validate Azure resources
function Test-AzureResources {
    param([string]$ResourceGroupName, [object]$Outputs)
    
    Write-ColorOutput "`n=== Validating Azure Resources ===" "Yellow"
    
    $validationResults = @()
    
    # Test App Services
    if ($Outputs.syncServiceUrl) {
        $syncServiceName = ($Outputs.syncServiceUrl.value -replace "https://", "" -replace ".azurewebsites.net", "")
        try {
            $syncApp = az webapp show --resource-group $ResourceGroupName --name $syncServiceName --output json | ConvertFrom-Json
            if ($syncApp.state -eq "Running") {
                Write-ColorOutput "✓ Sync Service is running" "Green"
                $validationResults += @{ Service = "Sync Service"; Status = "Running"; Details = $syncApp.defaultHostName }
            } else {
                Write-ColorOutput "✗ Sync Service is not running (State: $($syncApp.state))" "Red"
                $validationResults += @{ Service = "Sync Service"; Status = $syncApp.state; Details = "Not running" }
            }
        }
        catch {
            Write-ColorOutput "✗ Could not validate Sync Service: $($_.Exception.Message)" "Red"
            $validationResults += @{ Service = "Sync Service"; Status = "Error"; Details = $_.Exception.Message }
        }
    }
    
    if ($Outputs.dashboardUrl) {
        $dashboardName = ($Outputs.dashboardUrl.value -replace "https://", "" -replace ".azurewebsites.net", "")
        try {
            $dashboardApp = az webapp show --resource-group $ResourceGroupName --name $dashboardName --output json | ConvertFrom-Json
            if ($dashboardApp.state -eq "Running") {
                Write-ColorOutput "✓ Dashboard is running" "Green"
                $validationResults += @{ Service = "Dashboard"; Status = "Running"; Details = $dashboardApp.defaultHostName }
            } else {
                Write-ColorOutput "✗ Dashboard is not running (State: $($dashboardApp.state))" "Red"
                $validationResults += @{ Service = "Dashboard"; Status = $dashboardApp.state; Details = "Not running" }
            }
        }
        catch {
            Write-ColorOutput "✗ Could not validate Dashboard: $($_.Exception.Message)" "Red"
            $validationResults += @{ Service = "Dashboard"; Status = "Error"; Details = $_.Exception.Message }
        }
    }
    
    # Test Storage Account
    if ($Outputs.storageAccountName) {
        try {
            $storage = az storage account show --resource-group $ResourceGroupName --name $Outputs.storageAccountName.value --output json | ConvertFrom-Json
            if ($storage.provisioningState -eq "Succeeded") {
                Write-ColorOutput "✓ Storage Account is provisioned" "Green"
                $validationResults += @{ Service = "Storage Account"; Status = "Succeeded"; Details = $storage.primaryEndpoints.blob }
            } else {
                Write-ColorOutput "✗ Storage Account provisioning failed" "Red"
                $validationResults += @{ Service = "Storage Account"; Status = $storage.provisioningState; Details = "Provisioning failed" }
            }
        }
        catch {
            Write-ColorOutput "✗ Could not validate Storage Account: $($_.Exception.Message)" "Red"
            $validationResults += @{ Service = "Storage Account"; Status = "Error"; Details = $_.Exception.Message }
        }
    }
    
    # Test Key Vault
    if ($Outputs.keyVaultName -and $Outputs.keyVaultName.value) {
        try {
            $keyVault = az keyvault show --resource-group $ResourceGroupName --name $Outputs.keyVaultName.value --output json | ConvertFrom-Json
            Write-ColorOutput "✓ Key Vault is accessible" "Green"
            $validationResults += @{ Service = "Key Vault"; Status = "Accessible"; Details = $keyVault.properties.vaultUri }
        }
        catch {
            Write-ColorOutput "✗ Could not validate Key Vault: $($_.Exception.Message)" "Red"
            $validationResults += @{ Service = "Key Vault"; Status = "Error"; Details = $_.Exception.Message }
        }
    }
    
    return $validationResults
}

# Function to test application health
function Test-ApplicationHealth {
    param([object]$Outputs)
    
    if ($SkipHealthChecks) {
        Write-ColorOutput "Skipping application health checks..." "Yellow"
        return @()
    }
    
    Write-ColorOutput "`n=== Testing Application Health ===" "Yellow"
    
    $healthResults = @()
    
    # Test Sync Service
    if ($Outputs.syncServiceUrl) {
        Write-ColorOutput "Testing Sync Service health..." "Cyan"
        
        # Test root endpoint
        $rootTest = Test-HttpEndpoint -Url $Outputs.syncServiceUrl.value
        if ($rootTest.Success) {
            Write-ColorOutput "✓ Sync Service root endpoint responding" "Green"
        } else {
            Write-ColorOutput "✗ Sync Service root endpoint failed: $($rootTest.Error)" "Red"
        }
        $healthResults += @{ Service = "Sync Service Root"; Status = $rootTest.Success; Details = $rootTest }
        
        # Test API endpoints
        $apiTest = Test-HttpEndpoint -Url "$($Outputs.syncServiceUrl.value)/api/repositories"
        if ($apiTest.Success) {
            Write-ColorOutput "✓ Sync Service API responding" "Green"
        } else {
            Write-ColorOutput "✗ Sync Service API failed: $($apiTest.Error)" "Red"
        }
        $healthResults += @{ Service = "Sync Service API"; Status = $apiTest.Success; Details = $apiTest }
    }
    
    # Test Dashboard
    if ($Outputs.dashboardUrl) {
        Write-ColorOutput "Testing Dashboard health..." "Cyan"
        
        $dashboardTest = Test-HttpEndpoint -Url $Outputs.dashboardUrl.value
        if ($dashboardTest.Success) {
            Write-ColorOutput "✓ Dashboard responding" "Green"
        } else {
            Write-ColorOutput "✗ Dashboard failed: $($dashboardTest.Error)" "Red"
        }
        $healthResults += @{ Service = "Dashboard"; Status = $dashboardTest.Success; Details = $dashboardTest }
    }
    
    return $healthResults
}

# Function to show detailed results
function Show-DetailedResults {
    param([array]$ValidationResults, [array]$HealthResults, [object]$Outputs)
    
    Write-ColorOutput "`n=== Detailed Validation Results ===" "Yellow"
    
    # Azure Resources
    Write-ColorOutput "`nAzure Resources:" "Cyan"
    foreach ($result in $ValidationResults) {
        $status = if ($result.Status -eq "Running" -or $result.Status -eq "Succeeded" -or $result.Status -eq "Accessible") { "Green" } else { "Red" }
        Write-ColorOutput "  $($result.Service): $($result.Status)" $status
        if ($Detailed) {
            Write-ColorOutput "    Details: $($result.Details)" "Gray"
        }
    }
    
    # Application Health
    if ($HealthResults.Count -gt 0) {
        Write-ColorOutput "`nApplication Health:" "Cyan"
        foreach ($result in $HealthResults) {
            $status = if ($result.Status) { "Green" } else { "Red" }
            $statusText = if ($result.Status) { "Healthy" } else { "Unhealthy" }
            Write-ColorOutput "  $($result.Service): $statusText" $status
            if ($Detailed -and $result.Details) {
                Write-ColorOutput "    Status Code: $($result.Details.StatusCode)" "Gray"
                if ($result.Details.Error) {
                    Write-ColorOutput "    Error: $($result.Details.Error)" "Gray"
                }
            }
        }
    }
    
    # URLs
    Write-ColorOutput "`nApplication URLs:" "Cyan"
    if ($Outputs.dashboardUrl) {
        Write-ColorOutput "  Dashboard: $($Outputs.dashboardUrl.value)" "Gray"
    }
    if ($Outputs.syncServiceUrl) {
        Write-ColorOutput "  Sync Service: $($Outputs.syncServiceUrl.value)" "Gray"
    }
}

# Function to generate validation summary
function Show-ValidationSummary {
    param([array]$ValidationResults, [array]$HealthResults)
    
    $totalTests = $ValidationResults.Count + $HealthResults.Count
    $passedTests = ($ValidationResults | Where-Object { $_.Status -in @("Running", "Succeeded", "Accessible") }).Count + 
                   ($HealthResults | Where-Object { $_.Status -eq $true }).Count
    
    Write-ColorOutput "`n=== Validation Summary ===" "Yellow"
    Write-ColorOutput "Tests Passed: $passedTests / $totalTests" "Cyan"
    
    if ($passedTests -eq $totalTests) {
        Write-ColorOutput "🎉 All validations passed! Deployment is healthy." "Green"
        return $true
    } else {
        $failedTests = $totalTests - $passedTests
        Write-ColorOutput "⚠ $failedTests validation(s) failed. Please review the results above." "Yellow"
        return $false
    }
}

# Main execution
try {
    Write-ColorOutput "=== GitHub Dashboard - Deployment Validation ===" "Magenta"
    Write-ColorOutput "Environment: $Environment" "Cyan"
    
    # Discover resource group
    $rgName = Get-ResourceGroup -Environment $Environment
    Write-ColorOutput "Resource Group: $rgName" "Cyan"
    
    # Get deployment outputs
    $outputs = Get-DeploymentOutputs -ResourceGroupName $rgName
    
    # Validate Azure resources
    $validationResults = Test-AzureResources -ResourceGroupName $rgName -Outputs $outputs
    
    # Test application health
    $healthResults = Test-ApplicationHealth -Outputs $outputs
    
    # Show detailed results if requested
    if ($Detailed) {
        Show-DetailedResults -ValidationResults $validationResults -HealthResults $healthResults -Outputs $outputs
    }
    
    # Show summary
    $allPassed = Show-ValidationSummary -ValidationResults $validationResults -HealthResults $healthResults
    
    if ($allPassed) {
        Write-ColorOutput "`n✅ Validation completed successfully!" "Green"
        exit 0
    } else {
        Write-ColorOutput "`n⚠ Validation completed with warnings. Check the results above." "Yellow"
        exit 1
    }
    
}
catch {
    Write-ColorOutput "`n❌ Validation failed: $($_.Exception.Message)" "Red"
    exit 1
}