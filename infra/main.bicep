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
      appCommandLine: 'gunicorn --bind=0.0.0.0 --timeout 600 app:app'
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
        {
          name: 'GITHUB_TOKEN'
          value: githubToken
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
