@description('The name of the storage account')
param storageAccountName string

@description('The location for the storage account')
param location string

@description('The environment name')
param environment string

@description('The project name')
param projectName string

@description('Storage account SKU')
@allowed(['Standard_LRS', 'Standard_GRS', 'Standard_ZRS', 'Premium_LRS'])
param storageAccountSku string = 'Standard_LRS'

// Storage Account for database persistence and file storage
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: {
    Environment: environment
    Project: projectName
  }
  sku: {
    name: storageAccountSku
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    encryption: {
      services: {
        blob: {
          enabled: true
        }
        file: {
          enabled: true
        }
      }
      keySource: 'Microsoft.Storage'
    }
    networkAcls: {
      defaultAction: 'Allow' // Change to 'Deny' for production with private endpoints
      bypass: 'AzureServices'
    }
  }
}

// Blob service configuration
resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    isVersioningEnabled: true
  }
}

// Container for database backups
resource databaseContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobServices
  name: 'database-backups'
  properties: {
    publicAccess: 'None'
  }
}

// Container for application logs
resource logsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobServices
  name: 'application-logs'
  properties: {
    publicAccess: 'None'
  }
}

// File service for shared data
resource fileServices 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    shareDeleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

// File share for SQLite database
resource databaseFileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: fileServices
  name: 'github-database'
  properties: {
    shareQuota: 1024 // 1 GB
    enabledProtocols: 'SMB'
  }
}

@description('The name of the storage account')
output storageAccountName string = storageAccount.name

@description('The primary endpoint of the storage account')
output primaryEndpoint string = storageAccount.properties.primaryEndpoints.blob

@description('The connection string for the storage account')
@secure()
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${az.environment().suffixes.storage}'

@description('The resource ID of the storage account')
output storageAccountId string = storageAccount.id

@description('The file share name for the database')
output databaseFileShareName string = databaseFileShare.name