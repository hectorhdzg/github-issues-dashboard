// GitHub Issues Dashboard - Main Bicep Template
// This template creates the infrastructure for the Flask-based GitHub Issues Dashboard
targetScope = 'resourceGroup'

@description('The environment name (e.g., dev, staging, prod)')
param environmentName string

@description('The Azure location where resources will be deployed')
param location string = resourceGroup().location

@description('The name of the resource group')
param resourceGroupName string

@description('Flask environment setting')
param flaskEnv string = 'production'

@description('Flask debug setting')
param flaskDebug string = 'false'

@description('GitHub API token for syncing issues (optional)')
@secure()
param githubToken string = ''

// Generate a unique token for resource naming (required format)
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location, environmentName)
var resourcePrefix = 'ghd' // GitHub Dashboard prefix (≤ 3 characters)

// Resource names using the required format
var appServicePlanName = 'az-${resourcePrefix}-plan-${resourceToken}'
var appServiceName = 'az-${resourcePrefix}-app-${resourceToken}'
var applicationInsightsName = 'az-${resourcePrefix}-ai-${resourceToken}'
var logAnalyticsWorkspaceName = 'az-${resourcePrefix}-logs-${resourceToken}'
var managedIdentityName = 'az-${resourcePrefix}-id-${resourceToken}'

// Create User-Assigned Managed Identity (required by AZD platform, not used for auth)
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: managedIdentityName
  location: location
  tags: {
    'azd-env-name': environmentName
  }
}

// Create Log Analytics Workspace for monitoring
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  tags: {
    'azd-env-name': environmentName
  }
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      searchVersion: 1
      legacy: 0
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

// Create Application Insights for application monitoring
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  kind: 'web'
  tags: {
    'azd-env-name': environmentName
  }
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// Create App Service Plan for hosting the Flask application
resource appServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: appServicePlanName
  location: location
  tags: {
    'azd-env-name': environmentName
  }
  sku: {
    name: 'B1' // Basic tier for cost-effective hosting
    tier: 'Basic'
    size: 'B1'
    family: 'B'
    capacity: 1
  }
  kind: 'linux'
  properties: {
    perSiteScaling: false
    elasticScaleEnabled: false
    maximumElasticWorkerCount: 1
    isSpot: false
    reserved: true // Required for Linux plans
    isXenon: false
    hyperV: false
    targetWorkerCount: 0
    targetWorkerSizeId: 0
    zoneRedundant: false
  }
}

// Create the App Service for the Flask application
resource appService 'Microsoft.Web/sites@2024-04-01' = {
  name: appServiceName
  location: location
  kind: 'app,linux'
  tags: {
    'azd-env-name': environmentName
    'azd-service-name': 'dashboard-app'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    serverFarmId: appServicePlan.id
    reserved: true // Required for Linux apps
    httpsOnly: true
    clientAffinityEnabled: false
    publicNetworkAccess: 'Enabled'
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11' // Use Python 3.11 runtime
      appCommandLine: 'bash startup.sh'
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      cors: {
        allowedOrigins: ['*'] // Enable CORS for all origins
        supportCredentials: false
      }
      appSettings: [
        {
          name: 'FLASK_ENV'
          value: flaskEnv
        }
        {
          name: 'FLASK_DEBUG'
          value: flaskDebug
        }
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'true'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: applicationInsights.properties.ConnectionString
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: applicationInsights.properties.InstrumentationKey
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'WEBSITES_PORT'
          value: '5000'
        }
        // OpenTelemetry Configuration
        {
          name: 'OTEL_SERVICE_NAME'
          value: 'github-issues-dashboard'
        }
        {
          name: 'OTEL_SERVICE_VERSION'
          value: '1.0.0'
        }
        {
          name: 'OTEL_RESOURCE_ATTRIBUTES'
          value: 'service.name=github-issues-dashboard,service.version=1.0.0,deployment.environment=${environmentName}'
        }
        {
          name: 'AZURE_MONITOR_DISABLE_OFFLINE_STORAGE'
          value: 'false'
        }
        // GitHub API Configuration
        {
          name: 'GITHUB_TOKEN'
          value: githubToken
        }
        // Database Configuration
        {
          name: 'DATABASE_PATH'
          value: '/home/site/wwwroot/data/github_issues.db'
        }
        // Flask Configuration for Azure
        {
          name: 'FLASK_HOST'
          value: '0.0.0.0'
        }
        {
          name: 'FLASK_DEBUG'
          value: flaskDebug
        }
        {
          name: 'FLASK_ENV'
          value: flaskEnv
        }
        // Auto-initialization Configuration
        {
          name: 'AUTO_INIT_REPOS'
          value: 'true'
        }
        {
          name: 'AUTO_START_SYNC'
          value: 'false'
        }
        // Authentication is disabled - open access
        {
          name: 'ENABLE_USER_AUTHENTICATION'
          value: 'false'
        }
        {
          name: 'FLASK_SECRET_KEY'
          value: base64(uniqueString(subscription().id, resourceGroup().id, 'flask-secret'))
        }
      ]
    }
  }
}

// Create Storage Account for deployment scripts
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'azghd${take(resourceToken, 8)}st'
  location: location
  tags: {
    'azd-env-name': environmentName
  }
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// Create deployment script to initialize repositories
resource repositorySetupScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: '${appServiceName}-repo-setup'
  location: location
  tags: {
    'azd-env-name': environmentName
  }
  kind: 'AzurePowerShell'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    azPowerShellVersion: '9.0'
    retentionInterval: 'PT4H' // Keep for 4 hours
    timeout: 'PT30M' // 30 minute timeout
    cleanupPreference: 'OnSuccess'
    storageAccountSettings: {
      storageAccountName: storageAccount.name
      storageAccountKey: storageAccount.listKeys().keys[0].value
    }
    scriptContent: '''
      # Repository Setup Script for GitHub Issues Dashboard
      Write-Output "Starting repository setup for GitHub Issues Dashboard..."
      
      # Wait for App Service deployment to complete
      Start-Sleep -Seconds 60
      
      $appServiceName = "${appServiceName}"
      $resourceGroupName = "${resourceGroupName}"
      
      Write-Output "App Service: $appServiceName"
      Write-Output "Resource Group: $resourceGroupName"
      
      try {
        # Trigger the repository setup via the App Service
        $appUrl = "https://${appServiceName}.azurewebsites.net"
        Write-Output "App URL: $appUrl"
        
        # Wait for app to be ready
        $maxAttempts = 10
        $attempt = 0
        $appReady = $false
        
        while ($attempt -lt $maxAttempts -and -not $appReady) {
          try {
            $response = Invoke-WebRequest -Uri "$appUrl/health" -TimeoutSec 30 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
              $appReady = $true
              Write-Output "App is ready!"
            }
          } catch {
            Write-Output "App not ready yet, attempt $($attempt + 1)/$maxAttempts"
            Start-Sleep -Seconds 30
          }
          $attempt++
        }
        
        if ($appReady) {
          Write-Output "Triggering repository initialization..."
          # The app will auto-initialize repositories on startup via AUTO_INIT_REPOS environment variable
          # Just need to make a request to wake it up
          $initResponse = Invoke-WebRequest -Uri "$appUrl/api/data/repositories" -TimeoutSec 60 -ErrorAction SilentlyContinue
          Write-Output "Repository initialization triggered. Status: $($initResponse.StatusCode)"
        } else {
          Write-Output "App did not become ready within timeout period"
          exit 1
        }
        
        Write-Output "Repository setup completed successfully!"
      } catch {
        Write-Output "Error during setup: $($_.Exception.Message)"
        exit 1
      }
    '''
    environmentVariables: [
      {
        name: 'appServiceName'
        value: appServiceName
      }
      {
        name: 'resourceGroupName'
        value: resourceGroupName
      }
    ]
  }
  dependsOn: [
    appService
    appServiceDiagnosticSettings
  ]
}

// Create diagnostic settings for the App Service
resource appServiceDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${appServiceName}-diagnostics'
  scope: appService
  properties: {
    workspaceId: logAnalyticsWorkspace.id
    logs: [
      {
        category: 'AppServiceHTTPLogs'
        enabled: true
      }
      {
        category: 'AppServiceConsoleLogs'
        enabled: true
      }
      {
        category: 'AppServiceAppLogs'
        enabled: true
      }
      {
        category: 'AppServiceAuditLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// Required outputs for AZD deployment
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output REACT_APP_API_BASE_URL string = 'https://${appService.properties.defaultHostName}'
output REACT_APP_WEB_BASE_URL string = 'https://${appService.properties.defaultHostName}'
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output SERVICE_DASHBOARD_APP_ENDPOINT_URL string = 'https://${appService.properties.defaultHostName}'
output SERVICE_DASHBOARD_APP_NAME string = appService.name
output SERVICE_DASHBOARD_APP_RESOURCE_EXISTS bool = true

// Additional helpful outputs
output RESOURCE_GROUP_ID string = resourceGroup().id
output AZURE_APP_SERVICE_NAME string = appService.name
output AZURE_APP_SERVICE_URL string = 'https://${appService.properties.defaultHostName}'
output APPLICATIONINSIGHTS_CONNECTION_STRING string = applicationInsights.properties.ConnectionString
