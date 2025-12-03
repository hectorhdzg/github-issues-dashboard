<#
.SYNOPSIS
    Deploy BOTH Dashboard and Sync Service as a combined application.

.DESCRIPTION
    This deploys both the frontend dashboard and backend sync service to a single Azure App Service.

.PARAMETER GitHubToken
    Your GitHub personal access token (optional)

.EXAMPLE
    .\deploy-combined.ps1 -GitHubToken "ghp_xxxxx"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$GitHubToken = ""
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
    Write-ColorOutput "🚀 Deploying COMBINED GitHub Dashboard + Sync Service" "Magenta"
    Write-ColorOutput "App: $AppName" "Cyan"
    
    # Set subscription
    Write-ColorOutput "`nSetting Azure subscription..." "Yellow"
    az account set --subscription $SubscriptionId
    
    # Find project paths
    $ScriptDir = Split-Path -Parent $PSScriptRoot
    $ProjectRoot = Split-Path -Parent $ScriptDir
    $DashboardPath = Join-Path $ProjectRoot "githubDashboard"
    $SyncPath = Join-Path $ProjectRoot "githubSync"
    
    if (-not (Test-Path $DashboardPath)) {
        throw "Dashboard path not found: $DashboardPath"
    }
    if (-not (Test-Path $SyncPath)) {
        throw "Sync service path not found: $SyncPath"
    }
    
    # Configure app settings for combined app
    Write-ColorOutput "`nConfiguring app settings..." "Yellow"
    $settings = @(
        "ENVIRONMENT=production",
        "PORT=8001",
        "FLASK_APP=src/combined_app.py",
        "PYTHONDONTWRITEBYTECODE=1",
        "DATABASE_PATH=/home/site/wwwroot/data/github_issues.db"
    )
    
    # Add GitHub token if provided
    if ($GitHubToken -and $GitHubToken -ne "") {
        $settings += "GITHUB_TOKEN=$GitHubToken"
    }
    
    az webapp config appsettings set --resource-group $ResourceGroup --name $AppName --settings $settings --output none
    
    # Set startup command
    $startupCmd = "gunicorn --bind 0.0.0.0:8001 --chdir src combined_app:app"
    az webapp config set --resource-group $ResourceGroup --name $AppName --startup-file $startupCmd --output none
    
    # Create deployment package
    Write-ColorOutput "`nCreating combined deployment package..." "Yellow"
    $TempDir = Join-Path $env:TEMP "github-dashboard-combined-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
    
    # Copy dashboard files
    Write-ColorOutput "Copying dashboard files..." "Gray"
    Copy-Item -Path (Join-Path $DashboardPath "src") -Destination $TempDir -Recurse
    Copy-Item -Path (Join-Path $DashboardPath "templates") -Destination $TempDir -Recurse -ErrorAction SilentlyContinue
    Copy-Item -Path (Join-Path $DashboardPath "static") -Destination $TempDir -Recurse -ErrorAction SilentlyContinue
    
    # Copy sync service files
    Write-ColorOutput "Copying sync service files..." "Gray"
    $SyncDestDir = Join-Path $TempDir "sync"
    New-Item -ItemType Directory -Path $SyncDestDir -Force | Out-Null
    Copy-Item -Path (Join-Path $SyncPath "src") -Destination $SyncDestDir -Recurse
    Copy-Item -Path (Join-Path $SyncPath "data") -Destination $SyncDestDir -Recurse -ErrorAction SilentlyContinue
    Copy-Item -Path (Join-Path $SyncPath "setup") -Destination $SyncDestDir -Recurse -ErrorAction SilentlyContinue
    
    # Update the combined app to reference sync files correctly
    $CombinedAppContent = @"
import os
import sys
from flask import Flask, render_template

# Add sync service to path
sync_path = os.path.join(os.path.dirname(__file__), 'sync', 'src')
sys.path.insert(0, sync_path)

# Import sync service
try:
    from app import app as sync_app
    print("Successfully imported sync service")
    sync_available = True
except ImportError as e:
    print(f"Failed to import sync service: {e}")
    sync_app = None
    sync_available = False

# Create combined app
app = Flask(__name__, 
           template_folder="../templates",
           static_folder="../static")

# Add sync routes if available
if sync_available and sync_app:
    for rule in sync_app.url_map.iter_rules():
        endpoint = rule.endpoint
        if endpoint != 'static' and not endpoint.startswith('dashboard'):
            try:
                view_func = sync_app.view_functions[endpoint]
                app.add_url_rule(rule.rule, endpoint, view_func, methods=list(rule.methods))
            except Exception as e:
                print(f"Failed to add route {rule.rule}: {e}")

# Dashboard routes
@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/dashboard")
def dashboard_alt():
    return render_template("dashboard.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    print(f"Starting combined GitHub Dashboard + Sync Service on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
"@
    
    $CombinedAppContent | Set-Content (Join-Path $TempDir "src" "combined_app.py")
    
    # Create combined requirements.txt
    Write-ColorOutput "Creating combined requirements.txt..." "Gray"
    $RequirementsContent = @"
Flask==3.0.3
Flask-CORS==5.0.0
requests==2.31.0
gunicorn==23.0.0
APScheduler==3.10.4
"@
    $RequirementsContent | Set-Content (Join-Path $TempDir "requirements.txt")
    
    # Create data directory
    $DataDir = Join-Path $TempDir "data"
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    
    # Create zip
    $ZipPath = "$TempDir.zip"
    Compress-Archive -Path "$TempDir\*" -DestinationPath $ZipPath -Force
    
    # Deploy
    Write-ColorOutput "`nDeploying combined app to Azure..." "Yellow"
    az webapp deployment source config-zip --resource-group $ResourceGroup --name $AppName --src $ZipPath --output none
    
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "`n✅ Combined deployment successful!" "Green"
        $AppUrl = "https://$AppName.azurewebsites.net"
        Write-ColorOutput "🌐 Your app: $AppUrl" "Cyan"
        
        Write-ColorOutput "`nAvailable endpoints:" "Yellow"
        Write-ColorOutput "📊 Dashboard: $AppUrl/" "Gray"
        Write-ColorOutput "🔧 Management: $AppUrl/management" "Gray"
        Write-ColorOutput "📡 API: $AppUrl/api/repositories" "Gray"
        Write-ColorOutput "📈 Stats: $AppUrl/api/stats" "Gray"
        
        # Test the deployment
        Write-ColorOutput "`nTesting deployment..." "Yellow"
        Start-Sleep -Seconds 15  # Give the app time to start
        
        try {
            $response = Invoke-WebRequest -Uri $AppUrl -Method Get -TimeoutSec 30
            if ($response.StatusCode -eq 200) {
                Write-ColorOutput "✅ Dashboard is responding!" "Green"
            }
        }
        catch {
            Write-ColorOutput "⚠️  App may still be starting up. Check: $AppUrl" "Yellow"
        }
        
        try {
            $apiResponse = Invoke-WebRequest -Uri "$AppUrl/api/repositories" -Method Get -TimeoutSec 30
            if ($apiResponse.StatusCode -eq 200) {
                Write-ColorOutput "✅ API is responding!" "Green"
            }
        }
        catch {
            Write-ColorOutput "⚠️  API may still be starting up. Check: $AppUrl/api/repositories" "Yellow"
        }
        
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