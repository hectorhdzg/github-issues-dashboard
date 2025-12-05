# Azure Deployment Scripts

This folder contains all the necessary scripts and infrastructure as code (IaC) files to deploy the GitHub Issues Dashboard project to Azure.

## 📁 Structure

```
deployment/
├── README.md                    # This file
├── infra/                       # Infrastructure as Code (Bicep)
│   ├── main.bicep              # Main deployment template
│   ├── modules/                # Reusable Bicep modules
│   │   ├── app-service.bicep   # App Service module
│   │   ├── storage.bicep       # Storage account module
│   │   └── monitoring.bicep    # Application Insights module
│   └── parameters/             # Environment-specific parameters
│       ├── dev.parameters.json
│       ├── staging.parameters.json
│       └── prod.parameters.json
├── scripts/                    # Deployment scripts
│   ├── deploy.ps1              # Main deployment script
│   ├── setup-environment.ps1   # Environment setup
│   ├── validate-deployment.ps1 # Post-deployment validation
│   └── cleanup.ps1             # Resource cleanup
└── azure-pipelines.yml         # Azure DevOps pipeline (optional)
```

## 🚀 Quick Deploy

### Prerequisites
- Azure CLI installed and authenticated
- PowerShell 7+ (for cross-platform support)
- Contributor role on target Azure subscription

### Quick Deploy to Existing Azure App Service

**For immediate deployment to your existing App Service:**

1. **Deploy Dashboard (Recommended)**
   ```cmd
   deploy-dashboard.bat ghp_your_github_token_here
   ```
   
   Or using PowerShell:
   ```powershell
   .\scripts\quick-deploy.ps1 -GitHubToken "ghp_your_token" -AppType "dashboard"
   ```

2. **Deploy Sync Service** 
   ```cmd
   deploy-sync.bat ghp_your_github_token_here
   ```
   
   Or using PowerShell:
   ```powershell
   .\scripts\quick-deploy.ps1 -GitHubToken "ghp_your_token" -AppType "sync"
   ```

**Your app will be deployed to:** https://az-ghd-app-amzehuchpezkm.azurewebsites.net

### Full Infrastructure Deployment

For creating new resources from scratch:

1. **Setup Environment**
   ```powershell
   cd deployment
   .\scripts\setup-environment.ps1 -Environment "dev" -Location "East US"
   ```

2. **Deploy Infrastructure and Applications**
   ```powershell
   .\scripts\deploy.ps1 -Environment "dev" -ResourceGroupName "rg-github-dashboard-dev"
   ```

3. **Validate Deployment**
   ```powershell
   .\scripts\validate-deployment.ps1 -Environment "dev"
   ```

## 🔧 Configuration

### Environment Parameters
Each environment (dev/staging/prod) has its own parameter file in `infra/parameters/`:

- **dev.parameters.json**: Development environment with minimal SKUs
- **staging.parameters.json**: Staging environment for testing
- **prod.parameters.json**: Production environment with high availability

### Application Settings
The deployment scripts automatically configure:
- App Service application settings
- Connection strings
- Environment variables
- Storage account configuration
- Application Insights monitoring

## 📊 Deployed Resources

### For Each Environment:
- **Resource Group**: Container for all resources
- **App Service Plan**: Hosting plan for both applications
- **App Services**: 
  - GitHub Sync Service (backend)
  - GitHub Dashboard (frontend)
- **Storage Account**: For SQLite database persistence
- **Application Insights**: Monitoring and telemetry
- **Key Vault**: Secure storage for secrets (GitHub tokens)

### Resource Naming Convention:
- Resource Group: `rg-github-dashboard-{env}`
- App Service Plan: `asp-github-dashboard-{env}`
- Sync Service: `app-github-sync-{env}-{unique}`
- Dashboard: `app-github-dashboard-{env}-{unique}`
- Storage: `stgithubdashboard{env}{unique}`
- Key Vault: `kv-github-dash-{env}-{unique}`
- App Insights: `ai-github-dashboard-{env}`

## 🔐 Security

### Managed Identity
- Both App Services use system-assigned managed identities
- Managed identities have access to Key Vault for secrets
- No hardcoded credentials in application code

### Key Vault Integration
- GitHub tokens stored securely in Key Vault
- App Services retrieve secrets using managed identity
- Automatic secret rotation support

### Network Security
- HTTPS-only communication
- Storage account with private endpoints (production)
- App Service firewall rules (configurable)

## 📈 Monitoring

### Application Insights
- Performance monitoring for both applications
- Custom metrics and telemetry
- Alerts for critical issues
- Dependency tracking

### Health Checks
- Built-in health check endpoints
- Automated monitoring and alerting
- Integration with Azure Monitor

## 🧹 Cleanup

To remove all deployed resources:
```powershell
.\scripts\cleanup.ps1 -Environment "dev" -Confirm
```

## 🔄 CI/CD Integration

### Azure DevOps
The included `azure-pipelines.yml` provides:
- Automated build and test
- Infrastructure validation
- Multi-environment deployment
- Approval gates for production

### GitHub Actions
Alternative deployment workflow available for GitHub repositories.

## 📝 Troubleshooting

### Common Issues
1. **Authentication**: Ensure Azure CLI is logged in with correct subscription
2. **Permissions**: Verify Contributor role on target subscription
3. **Resource Names**: Check for naming conflicts with existing resources
4. **Quotas**: Ensure sufficient quota for App Service plans and storage

### Logs and Diagnostics
- App Service logs: Available in Azure portal
- Application Insights: Detailed telemetry and errors
- Deployment logs: Check Azure Resource Manager deployment history

## 📞 Support

For deployment issues:
1. Check the troubleshooting section above
2. Review Azure portal deployment history
3. Check Application Insights for runtime issues
4. Validate resource configurations