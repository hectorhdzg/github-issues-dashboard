@description('The name of the App Service')
param appName string

@description('The resource ID of the App Service Plan')
param appServicePlanId string

@description('The location for the App Service')
param location string

@description('The environment name')
param environment string

@description('The project name')
param projectName string

@description('The type of application (sync-service or dashboard)')
@allowed(['sync-service', 'dashboard'])
param applicationType string

@description('Storage account connection string')
param storageConnectionString string

@description('Key Vault URI')
param keyVaultUri string = ''

@description('Application Insights instrumentation key')
param applicationInsightsKey string = ''

@description('URL of the sync service (for dashboard)')
param syncServiceUrl string = ''

@description('Enable Key Vault integration')
param enableKeyVault bool = true

@description('Enable Application Insights integration')
param enableApplicationInsights bool = true

// App Service
resource appService 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  tags: {
    Environment: environment
    Project: projectName
    ApplicationType: applicationType
  }
  identity: enableKeyVault ? {
    type: 'SystemAssigned'
  } : null
  properties: {
    serverFarmId: appServicePlanId
    httpsOnly: true
    siteConfig: {
      pythonVersion: '3.11'
      scmType: 'None'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      alwaysOn: environment == 'prod' ? true : false
      appSettings: union(
        [
          {
            name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
            value: 'true'
          }
          {
            name: 'ENVIRONMENT'
            value: environment
          }
          {
            name: 'STORAGE_CONNECTION_STRING'
            value: storageConnectionString
          }
          {
            name: 'PORT'
            value: applicationType == 'sync-service' ? '8000' : '8001'
          }
        ],
        enableApplicationInsights && !empty(applicationInsightsKey) ? [
          {
            name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
            value: applicationInsightsKey
          }
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: 'InstrumentationKey=${applicationInsightsKey}'
          }
        ] : [],
        enableKeyVault && !empty(keyVaultUri) ? [
          {
            name: 'KEY_VAULT_URI'
            value: keyVaultUri
          }
        ] : [],
        applicationType == 'sync-service' ? [
          {
            name: 'FLASK_APP'
            value: 'src/app.py'
          }
          {
            name: 'DATABASE_PATH'
            value: '/home/site/wwwroot/data/github_issues.db'
          }
        ] : [
          {
            name: 'FLASK_APP'
            value: 'src/app.py'
          }
          {
            name: 'SYNC_SERVICE_URL'
            value: syncServiceUrl
          }
        ]
      )
      connectionStrings: [
        {
          name: 'DefaultConnection'
          connectionString: storageConnectionString
          type: 'Custom'
        }
      ]
    }
  }
}

// Key Vault access policy for the App Service (if Key Vault is enabled)
resource keyVaultAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2023-07-01' = if (enableKeyVault && !empty(keyVaultUri)) {
  name: '${last(split(keyVaultUri, '/'))}/add'
  properties: {
    accessPolicies: [
      {
        tenantId: subscription().tenantId
        objectId: appService.identity.principalId
        permissions: {
          secrets: ['get', 'list']
        }
      }
    ]
  }
}

// App Service staging slot for blue-green deployments (production only)
resource stagingSlot 'Microsoft.Web/sites/slots@2023-12-01' = if (environment == 'prod') {
  parent: appService
  name: 'staging'
  location: location
  tags: {
    Environment: '${environment}-staging'
    Project: projectName
    ApplicationType: applicationType
  }
  identity: enableKeyVault ? {
    type: 'SystemAssigned'
  } : null
  properties: {
    serverFarmId: appServicePlanId
    httpsOnly: true
    siteConfig: {
      pythonVersion: '3.11'
      scmType: 'None'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      alwaysOn: true
    }
  }
}

@description('The name of the created App Service')
output appServiceName string = appService.name

@description('The URL of the App Service')
output appServiceUrl string = 'https://${appService.properties.defaultHostName}'

@description('The principal ID of the App Service managed identity')
output principalId string = enableKeyVault ? appService.identity.principalId : ''

@description('The staging slot URL (production only)')
output stagingSlotUrl string = environment == 'prod' ? 'https://${appService.name}-staging.azurewebsites.net' : ''