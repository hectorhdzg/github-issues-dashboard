@description('The name of the Key Vault')
param keyVaultName string

@description('The location for the Key Vault')
param location string

@description('The environment name')
param environment string

@description('The project name')
param projectName string

@description('GitHub personal access token')
@secure()
param githubToken string

@description('Key Vault SKU')
@allowed(['standard', 'premium'])
param keyVaultSku string = 'standard'

// Key Vault for secure secrets management
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: {
    Environment: environment
    Project: projectName
  }
  properties: {
    sku: {
      family: 'A'
      name: keyVaultSku
    }
    tenantId: subscription().tenantId
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enableRbacAuthorization: false
    accessPolicies: [] // Access policies will be added by the App Service module
    networkAcls: {
      defaultAction: 'Allow' // Change to 'Deny' for production with private endpoints
      bypass: 'AzureServices'
    }
  }
}

// Store GitHub token as a secret
resource githubTokenSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'github-token'
  properties: {
    value: githubToken
    attributes: {
      enabled: true
    }
  }
}

// Secret for database encryption key (auto-generated)
resource databaseKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'database-encryption-key'
  properties: {
    value: base64(substring(uniqueString(resourceGroup().id, keyVaultName), 0, 13))
    attributes: {
      enabled: true
    }
  }
}

// Secret for application JWT signing key (auto-generated)
resource jwtSigningKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'jwt-signing-key'
  properties: {
    value: base64(substring(uniqueString(resourceGroup().id, keyVaultName, 'jwt'), 0, 13))
    attributes: {
      enabled: true
    }
  }
}

@description('The name of the Key Vault')
output keyVaultName string = keyVault.name

@description('The URI of the Key Vault')
output keyVaultUri string = keyVault.properties.vaultUri

@description('The resource ID of the Key Vault')
output keyVaultId string = keyVault.id

@description('The name of the GitHub token secret')
output githubTokenSecretName string = githubTokenSecret.name

@description('The name of the database encryption key secret')
output databaseKeySecretName string = databaseKeySecret.name

@description('The name of the JWT signing key secret')
output jwtSigningKeySecretName string = jwtSigningKeySecret.name