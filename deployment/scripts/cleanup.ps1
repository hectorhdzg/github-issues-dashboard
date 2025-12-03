#Requires -Version 7.0
<#
.SYNOPSIS
    Cleans up Azure resources for the GitHub Dashboard project.

.DESCRIPTION
    This script removes all Azure resources associated with the GitHub Dashboard
    deployment. Use with caution as this action is irreversible.

.PARAMETER Environment
    The target environment (dev, staging, prod)

.PARAMETER ResourceGroupName
    The name of the resource group to delete (optional, will be derived if not provided)

.PARAMETER Force
    Skip confirmation prompts

.PARAMETER WhatIf
    Preview what would be deleted without actually deleting

.PARAMETER KeepResourceGroup
    Delete only the resources within the resource group, not the group itself

.EXAMPLE
    .\cleanup.ps1 -Environment "dev" -WhatIf

.EXAMPLE
    .\cleanup.ps1 -Environment "dev" -Force

.EXAMPLE
    .\cleanup.ps1 -Environment "staging" -ResourceGroupName "rg-github-dashboard-staging" -KeepResourceGroup
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment,

    [Parameter(Mandatory = $false)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory = $false)]
    [switch]$Force,

    [Parameter(Mandatory = $false)]
    [switch]$WhatIf,

    [Parameter(Mandatory = $false)]
    [switch]$KeepResourceGroup
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

# Function to list resources in resource group
function Get-ResourceGroupResources {
    param([string]$ResourceGroupName)
    
    try {
        $resources = az resource list --resource-group $ResourceGroupName --output json | ConvertFrom-Json
        return $resources
    }
    catch {
        Write-ColorOutput "Warning: Could not list resources in $ResourceGroupName" "Yellow"
        return @()
    }
}

# Function to show what will be deleted
function Show-DeletionPreview {
    param([string]$ResourceGroupName, [array]$Resources, [bool]$DeleteGroup)
    
    Write-ColorOutput "`n=== Deletion Preview ===" "Yellow"
    Write-ColorOutput "Environment: $Environment" "Cyan"
    Write-ColorOutput "Resource Group: $ResourceGroupName" "Cyan"
    
    if ($DeleteGroup) {
        Write-ColorOutput "`n🗑️  The following resource group and ALL its contents will be DELETED:" "Red"
        Write-ColorOutput "  - Resource Group: $ResourceGroupName" "Red"
    } else {
        Write-ColorOutput "`n🗑️  The following resources will be DELETED:" "Red"
    }
    
    if ($Resources.Count -gt 0) {
        Write-ColorOutput "`nResources to be deleted:" "Yellow"
        foreach ($resource in $Resources) {
            $resourceType = $resource.type -replace "Microsoft\.", ""
            Write-ColorOutput "  - $($resource.name) ($resourceType)" "Red"
        }
    } else {
        Write-ColorOutput "  No resources found in the resource group." "Yellow"
    }
    
    Write-ColorOutput "`n⚠️  WARNING: This action cannot be undone!" "Red"
}

# Function to confirm deletion
function Confirm-Deletion {
    param([string]$ResourceGroupName, [bool]$DeleteGroup)
    
    if ($Force) {
        Write-ColorOutput "Force flag specified, skipping confirmation..." "Yellow"
        return $true
    }
    
    $action = if ($DeleteGroup) { "DELETE the entire resource group" } else { "DELETE all resources in the resource group" }
    
    Write-ColorOutput "`nAre you sure you want to $action '$ResourceGroupName'?" "Yellow"
    Write-ColorOutput "Type 'yes' to confirm, or anything else to cancel:" "Yellow"
    
    $confirmation = Read-Host
    
    return $confirmation.ToLower() -eq "yes"
}

# Function to delete individual resources
function Remove-Resources {
    param([string]$ResourceGroupName, [array]$Resources)
    
    Write-ColorOutput "`n=== Deleting Resources ===" "Yellow"
    
    $deletionErrors = @()
    
    # Group resources by type for optimal deletion order
    $resourceGroups = $Resources | Group-Object type
    
    # Define deletion order (dependencies last)
    $deletionOrder = @(
        "Microsoft.Web/sites",
        "Microsoft.Web/serverfarms",
        "Microsoft.Insights/components",
        "Microsoft.OperationalInsights/workspaces",
        "Microsoft.KeyVault/vaults",
        "Microsoft.Storage/storageAccounts"
    )
    
    foreach ($resourceType in $deletionOrder) {
        $resourcesOfType = $resourceGroups | Where-Object { $_.Name -eq $resourceType }
        if ($resourcesOfType) {
            foreach ($resource in $resourcesOfType.Group) {
                try {
                    Write-ColorOutput "Deleting $($resource.name) ($($resource.type))..." "Cyan"
                    
                    # Special handling for Key Vault (needs purge protection disabled)
                    if ($resource.type -eq "Microsoft.KeyVault/vaults") {
                        az keyvault delete --name $resource.name --resource-group $ResourceGroupName
                        if ($LASTEXITCODE -eq 0) {
                            # Purge the Key Vault to completely remove it
                            az keyvault purge --name $resource.name --no-wait
                        }
                    } else {
                        az resource delete --ids $resource.id --no-wait
                    }
                    
                    if ($LASTEXITCODE -eq 0) {
                        Write-ColorOutput "✓ $($resource.name) deletion initiated" "Green"
                    } else {
                        Write-ColorOutput "✗ Failed to delete $($resource.name)" "Red"
                        $deletionErrors += $resource.name
                    }
                }
                catch {
                    Write-ColorOutput "✗ Error deleting $($resource.name): $($_.Exception.Message)" "Red"
                    $deletionErrors += $resource.name
                }
            }
        }
    }
    
    # Delete any remaining resources not in the predefined order
    $remainingResources = $Resources | Where-Object { $_.type -notin $deletionOrder }
    foreach ($resource in $remainingResources) {
        try {
            Write-ColorOutput "Deleting $($resource.name) ($($resource.type))..." "Cyan"
            az resource delete --ids $resource.id --no-wait
            
            if ($LASTEXITCODE -eq 0) {
                Write-ColorOutput "✓ $($resource.name) deletion initiated" "Green"
            } else {
                Write-ColorOutput "✗ Failed to delete $($resource.name)" "Red"
                $deletionErrors += $resource.name
            }
        }
        catch {
            Write-ColorOutput "✗ Error deleting $($resource.name): $($_.Exception.Message)" "Red"
            $deletionErrors += $resource.name
        }
    }
    
    if ($deletionErrors.Count -gt 0) {
        Write-ColorOutput "`n⚠️  Some resources failed to delete:" "Yellow"
        foreach ($errorItem in $deletionErrors) {
            Write-ColorOutput "  - $errorItem" "Red"
        }
    }
    
    return $deletionErrors.Count -eq 0
}

# Function to delete resource group
function Remove-ResourceGroup {
    param([string]$ResourceGroupName)
    
    Write-ColorOutput "`n=== Deleting Resource Group ===" "Yellow"
    Write-ColorOutput "Deleting resource group: $ResourceGroupName" "Cyan"
    
    try {
        az group delete --name $ResourceGroupName --yes --no-wait
        
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "✓ Resource group deletion initiated" "Green"
            return $true
        } else {
            Write-ColorOutput "✗ Failed to delete resource group" "Red"
            return $false
        }
    }
    catch {
        Write-ColorOutput "✗ Error deleting resource group: $($_.Exception.Message)" "Red"
        return $false
    }
}

# Function to wait for deletion completion
function Wait-ForDeletion {
    param([string]$ResourceGroupName, [bool]$DeletedGroup)
    
    if ($DeletedGroup) {
        Write-ColorOutput "`nWaiting for resource group deletion to complete..." "Cyan"
        $maxWaitTime = 300 # 5 minutes
        $waitTime = 0
        
        while ($waitTime -lt $maxWaitTime) {
            try {
                $rg = az group show --name $ResourceGroupName --output json 2>$null | ConvertFrom-Json
                if (-not $rg) {
                    Write-ColorOutput "✓ Resource group deleted successfully" "Green"
                    return
                }
            }
            catch {
                Write-ColorOutput "✓ Resource group deleted successfully" "Green"
                return
            }
            
            Start-Sleep -Seconds 10
            $waitTime += 10
            Write-ColorOutput "  Still waiting... ($waitTime seconds)" "Gray"
        }
        
        Write-ColorOutput "⚠️  Deletion is taking longer than expected. Check Azure portal for status." "Yellow"
    } else {
        Write-ColorOutput "`nNote: Resource deletions are running asynchronously. Check Azure portal for completion status." "Gray"
    }
}

# Main execution
try {
    Write-ColorOutput "=== GitHub Dashboard - Resource Cleanup ===" "Magenta"
    Write-ColorOutput "Environment: $Environment" "Cyan"
    
    # Discover resource group
    $rgName = Get-ResourceGroup -Environment $Environment
    Write-ColorOutput "Resource Group: $rgName" "Cyan"
    
    # Check if resource group exists
    try {
        $rg = az group show --name $rgName --output json | ConvertFrom-Json
        if (-not $rg) {
            Write-ColorOutput "Resource group '$rgName' not found. Nothing to clean up." "Yellow"
            exit 0
        }
    }
    catch {
        Write-ColorOutput "Resource group '$rgName' not found. Nothing to clean up." "Yellow"
        exit 0
    }
    
    # Get resources in the resource group
    $resources = Get-ResourceGroupResources -ResourceGroupName $rgName
    
    # Show what will be deleted
    Show-DeletionPreview -ResourceGroupName $rgName -Resources $resources -DeleteGroup (-not $KeepResourceGroup)
    
    # Preview mode
    if ($WhatIf) {
        Write-ColorOutput "`nPreview completed. Use -WhatIf:$false to proceed with actual deletion." "Yellow"
        exit 0
    }
    
    # Confirm deletion
    $confirmed = Confirm-Deletion -ResourceGroupName $rgName -DeleteGroup (-not $KeepResourceGroup)
    if (-not $confirmed) {
        Write-ColorOutput "Cleanup cancelled by user." "Yellow"
        exit 0
    }
    
    # Perform deletion
    if ($KeepResourceGroup) {
        # Delete individual resources
        $success = Remove-Resources -ResourceGroupName $rgName -Resources $resources
        if ($success) {
            Write-ColorOutput "`n✅ Resource cleanup completed successfully!" "Green"
            Write-ColorOutput "Resource group '$rgName' has been preserved." "Gray"
        } else {
            Write-ColorOutput "`n⚠️  Resource cleanup completed with errors. Check the output above." "Yellow"
        }
    } else {
        # Delete entire resource group
        $success = Remove-ResourceGroup -ResourceGroupName $rgName
        if ($success) {
            Wait-ForDeletion -ResourceGroupName $rgName -DeletedGroup $true
            Write-ColorOutput "`n✅ Resource group cleanup completed successfully!" "Green"
        } else {
            Write-ColorOutput "`n❌ Failed to delete resource group." "Red"
            exit 1
        }
    }
    
}
catch {
    Write-ColorOutput "`n❌ Cleanup failed: $($_.Exception.Message)" "Red"
    exit 1
}