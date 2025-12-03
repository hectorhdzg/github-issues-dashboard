@description('The environment name (e.g., dev, staging, prod)')
param environment string = 'dev'

@description('The location for all resources')
param location string = resourceGroup().location

@description('The base name for all resources')
param projectName string = 'github-dashboard'

@description('The SKU for the App Service Plan')
@allowed(['F1', 'D1', 'B1', 'B2', 'B3', 'S1', 'S2', 'S3', 'P1V2', 'P2V2', 'P3V2'])
param appServicePlanSku string = 'B1'

@description('GitHub personal access token (will be stored in Key Vault)')
@secure()
param githubToken string

@description('Enable Application Insights monitoring')
param enableApplicationInsights bool = true

@description('Enable Key Vault for secrets management')
param enableKeyVault bool = true

// Generate unique suffix for globally unique resources
var uniqueSuffix = substring(uniqueString(resourceGroup().id), 0, 6)
var appServicePlanName = 'asp-${projectName}-${environment}'
var syncServiceName = 'app-github-sync-${environment}-${uniqueSuffix}'
var dashboardName = 'app-github-dashboard-${environment}-${uniqueSuffix}'
var storageAccountName = 'st${replace(projectName, '-', '')}${environment}${uniqueSuffix}'
var keyVaultName = 'kv-github-dash-${environment}-${uniqueSuffix}'
var applicationInsightsName = 'ai-${projectName}-${environment}'

// App Service Plan for hosting both applications
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  tags: {
    Environment: environment
    Project: projectName
  }
  sku: {
    name: appServicePlanSku
  }
  properties: {
    reserved: false // Windows App Service Plan
  }
}

// Storage Account for SQLite database persistence and static files
module storage 'modules/storage.bicep' = {
  name: 'storage-deployment'
  params: {
    storageAccountName: storageAccountName
    location: location
    environment: environment
    projectName: projectName
  }
}

// Key Vault for secure secrets management
module keyVault 'modules/key-vault.bicep' = if (enableKeyVault) {
  name: 'keyvault-deployment'
  params: {
    keyVaultName: keyVaultName
    location: location
    environment: environment
    projectName: projectName
    githubToken: githubToken
  }
}

// Application Insights for monitoring
module applicationInsights 'modules/monitoring.bicep' = if (enableApplicationInsights) {
  name: 'monitoring-deployment'
  params: {
    applicationInsightsName: applicationInsightsName
    location: location
    environment: environment
    projectName: projectName
  }
}

// GitHub Sync Service (Backend API)
module syncService 'modules/app-service.bicep' = {
  name: 'sync-service-deployment'
  params: {
    appName: syncServiceName
    appServicePlanId: appServicePlan.id
    location: location
    environment: environment
    projectName: projectName
    applicationType: 'sync-service'
    storageConnectionString: storage.outputs.connectionString
    keyVaultUri: enableKeyVault ? keyVault.outputs.keyVaultUri : ''
    applicationInsightsKey: enableApplicationInsights ? applicationInsights.outputs.instrumentationKey : ''
    enableKeyVault: enableKeyVault
    enableApplicationInsights: enableApplicationInsights
  }
}

// GitHub Dashboard (Frontend Web App)
module dashboard 'modules/app-service.bicep' = {
  name: 'dashboard-deployment'
  params: {
    appName: dashboardName
    appServicePlanId: appServicePlan.id
    location: location
    environment: environment
    projectName: projectName
    applicationType: 'dashboard'
    storageConnectionString: storage.outputs.connectionString
    keyVaultUri: enableKeyVault ? keyVault.outputs.keyVaultUri : ''
    applicationInsightsKey: enableApplicationInsights ? applicationInsights.outputs.instrumentationKey : ''
    syncServiceUrl: 'https://${syncServiceName}.azurewebsites.net'
    enableKeyVault: enableKeyVault
    enableApplicationInsights: enableApplicationInsights
  }
}

// Outputs for reference and CI/CD integration
@description('The URL of the GitHub Sync Service')
output syncServiceUrl string = 'https://${syncServiceName}.azurewebsites.net'

@description('The URL of the GitHub Dashboard')
output dashboardUrl string = 'https://${dashboardName}.azurewebsites.net'

@description('The name of the storage account')
output storageAccountName string = storageAccountName

@description('The name of the Key Vault')
output keyVaultName string = enableKeyVault ? keyVaultName : ''

@description('The Application Insights instrumentation key')
output applicationInsightsInstrumentationKey string = enableApplicationInsights ? applicationInsights.outputs.instrumentationKey : ''

@description('Resource group information')
output resourceGroup object = {
  name: resourceGroup().name
  location: location
}