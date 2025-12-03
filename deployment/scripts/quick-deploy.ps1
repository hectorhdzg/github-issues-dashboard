<#
.SYNOPSIS
    Quick deploy to your existing GitHub Dashboard App Service.

.DESCRIPTION
    Simple one-command deployment to az-ghd-app-amzehuchpezkm.azurewebsites.net

.PARAMETER GitHubToken
    Your GitHub personal access token (optional)

.PARAMETER AppType
    'dashboard' or 'sync' - which app to deploy

.EXAMPLE
    .\quick-deploy.ps1 -AppType "dashboard"

.EXAMPLE
    .\quick-deploy.ps1 -GitHubToken "ghp_xxxxx" -AppType "dashboard"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$GitHubToken = "",
    
    [Parameter(Mandatory = $false)]
    [ValidateSet("dashboard", "sync")]
    [string]$AppType = "dashboard"
)

$ErrorActionPreference = "Stop"

# Your Azure resources
$ResourceGroup = "hectorh"
$AppName = "az-ghd-app-amzehuchpezkm"
$SubscriptionId = "65b2f83e-7bf1-4be3-bafc-3a4163265a52"

function Write-ColorOutput($Message, $Color = "White") {
    Write-Host $Message -ForegroundColor $Color
}

try {
    Write-ColorOutput "🚀 Quick Deploy to Azure App Service" "Magenta"
    Write-ColorOutput "App: $AppName" "Cyan"
    Write-ColorOutput "Type: $AppType" "Cyan"
    
    # Set subscription
    Write-ColorOutput "`nSetting Azure subscription..." "Yellow"
    az account set --subscription $SubscriptionId
    
    # Find project paths
    $ScriptDir = Split-Path -Parent $PSScriptRoot
    $ProjectRoot = Split-Path -Parent $ScriptDir
    
    if ($AppType -eq "dashboard") {
        $SourcePath = Join-Path $ProjectRoot "githubDashboard"
    } else {
        $SourcePath = Join-Path $ProjectRoot "githubSync"
    }
    
    if (-not (Test-Path $SourcePath)) {
        throw "Source path not found: $SourcePath"
    }
    
    # Configure app settings
    Write-ColorOutput "`nConfiguring app settings..." "Yellow"
    $settings = @(
        "ENVIRONMENT=production",
        "PORT=$(if ($AppType -eq 'sync') { '8000' } else { '8001' })",
        "FLASK_APP=src/app.py",
        "PYTHONDONTWRITEBYTECODE=1"
    )
    
    # Add GitHub token only if provided
    if ($GitHubToken -and $GitHubToken -ne "") {
        $settings += "GITHUB_TOKEN=$GitHubToken"
    }
    
    if ($AppType -eq "sync") {
        $settings += "DATABASE_PATH=/home/site/wwwroot/data/github_issues.db"
    }
    
    az webapp config appsettings set --resource-group $ResourceGroup --name $AppName --settings $settings --output none
    
    # Set startup command
    $startupCmd = if ($AppType -eq "sync") {
        "gunicorn --bind 0.0.0.0:8000 --chdir src app:app"
    } else {
        "gunicorn --bind 0.0.0.0:8001 --chdir src app:app"
    }
    
    az webapp config set --resource-group $ResourceGroup --name $AppName --startup-file $startupCmd --output none
    
    # Create deployment package
    Write-ColorOutput "`nCreating deployment package..." "Yellow"
    $TempDir = Join-Path $env:TEMP "github-dashboard-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
    
    # Copy files
    Copy-Item -Path (Join-Path $SourcePath "src") -Destination $TempDir -Recurse
    
    if ($AppType -eq "dashboard") {
        Copy-Item -Path (Join-Path $SourcePath "templates") -Destination $TempDir -Recurse -ErrorAction SilentlyContinue
        Copy-Item -Path (Join-Path $SourcePath "static") -Destination $TempDir -Recurse -ErrorAction SilentlyContinue
    } else {
        Copy-Item -Path (Join-Path $SourcePath "data") -Destination $TempDir -Recurse -ErrorAction SilentlyContinue
        Copy-Item -Path (Join-Path $SourcePath "setup") -Destination $TempDir -Recurse -ErrorAction SilentlyContinue
    }
    
    # Create requirements.txt
    $RequirementsContent = if ($AppType -eq "sync") {
        @"
Flask==3.0.3
Flask-CORS==5.0.0
requests==2.31.0
gunicorn==23.0.0
APScheduler==3.10.4
"@
    } else {
        @"
Flask==3.0.3
requests==2.31.0
gunicorn==23.0.0
"@
    }
    $RequirementsContent | Set-Content (Join-Path $TempDir "requirements.txt")
    
    # Create zip
    $ZipPath = "$TempDir.zip"
    Compress-Archive -Path "$TempDir\*" -DestinationPath $ZipPath -Force
    
    # Deploy
    Write-ColorOutput "`nDeploying to Azure..." "Yellow"
    az webapp deployment source config-zip --resource-group $ResourceGroup --name $AppName --src $ZipPath --output none
    
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "`n✅ Deployment successful!" "Green"
        $AppUrl = "https://$AppName.azurewebsites.net"
        Write-ColorOutput "🌐 Your app: $AppUrl" "Cyan"
        
        # Test the deployment
        Write-ColorOutput "`nTesting deployment..." "Yellow"
        Start-Sleep -Seconds 10  # Give the app time to start
        
        try {
            $response = Invoke-WebRequest -Uri $AppUrl -Method Get -TimeoutSec 30
            if ($response.StatusCode -eq 200) {
                Write-ColorOutput "✅ App is responding!" "Green"
            }
        }
        catch {
            Write-ColorOutput "⚠️  App may still be starting up. Check: $AppUrl" "Yellow"
        }
        
        Write-ColorOutput "`nNext steps:" "Yellow"
        Write-ColorOutput "• Visit your app at: $AppUrl" "Gray"
        if ($AppType -eq "sync") {
            Write-ColorOutput "• API endpoints: $AppUrl/api/repositories" "Gray"
            Write-ColorOutput "• Add repositories: POST to $AppUrl/api/repositories" "Gray"
        }
        Write-ColorOutput "• Monitor logs in Azure portal" "Gray"
    } else {
        throw "Deployment failed"
    }
    
    # Cleanup
    Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $ZipPath -Force -ErrorAction SilentlyContinue
    
}
catch {
    Write-ColorOutput "`n❌ Error: $($_.Exception.Message)" "Red"
    exit 1
}