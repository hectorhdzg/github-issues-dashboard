# 🐛 GitHub Issues Dashboard

A comprehensive web dashboard for monitoring and managing GitHub issues across multiple repositories, specifically designed for Azure Monitor Scripting SDKs but extensible to any GitHub repositories.

## 🚀 Features

- **Multi-Repository Support**: Monitor issues across 14+ repositories simultaneously
- **Smart PR/Issue Detection**: Automatically extracts and links related PRs and issues from issue descriptions
- **24-Hour Auto Sync**: Keeps data fresh with automated GitHub API synchronization
- **Triage Management**: Track and manage issue triage status with checkboxes
- **Priority System**: Assign and manage priority levels (High, Medium, Low, None)
- **Advanced Filtering**: Search and filter issues by title, assignee, or status
- **Responsive Design**: Clean, modern interface that works on desktop and mobile
- **Real-time Status**: Monitor sync status and view last update times

## 📊 Supported Repositories

The dashboard currently monitors these Azure Monitor and OpenTelemetry repositories:

- Azure/azure-sdk-for-python
- Azure/azure-sdk-for-js  
- Azure/azure-sdk-for-net
- Azure/azure-sdk-for-java
- microsoft/ApplicationInsights-Python
- microsoft/ApplicationInsights-node.js
- microsoft/ApplicationInsights-dotnet
- microsoft/ApplicationInsights-Java
- microsoft/node-diagnostic-channel
- open-telemetry/opentelemetry-js
- open-telemetry/opentelemetry-js-contrib
- open-telemetry/opentelemetry-python
- open-telemetry/opentelemetry-python-contrib

## 🛠️ Technology Stack

- **Backend**: Python Flask
- **Database**: SQLite with automatic schema management
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **APIs**: GitHub REST API v3
- **Deployment**: Azure App Service
- **Infrastructure**: Azure Bicep templates
- **Monitoring**: Azure Application Insights integration

## 🔧 Local Development

### Prerequisites

- Python 3.8+
- GitHub Personal Access Token (for API access)

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/hectorhdzg/github-issues-dashboard.git
   cd github-issues-dashboard
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**:
   ```bash
   # Windows (PowerShell)
   $env:GITHUB_TOKEN="your_github_token_here"
   
   # Linux/Mac
   export GITHUB_TOKEN="your_github_token_here"
   ```

4. **Run the application**:
   ```bash
   python app.py
   ```

5. **Access the dashboard**:
   Open `http://localhost:5000` in your browser

### GitHub Token Setup

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token with these permissions:
   - `repo` (Full control of private repositories)
   - `read:org` (Read org and team membership)
3. Copy the token and set it as the `GITHUB_TOKEN` environment variable

## ☁️ Azure Deployment

### Option 1: Azure Developer CLI (Recommended)

1. **Install AZD**:
   ```bash
   # Windows
   winget install microsoft.azd
   
   # macOS
   brew tap azure/azd && brew install azd
   
   # Linux
   curl -fsSL https://aka.ms/install-azd.sh | bash
   ```

2. **Login to Azure**:
   ```bash
   azd auth login
   ```

3. **Initialize and deploy**:
   ```bash
   azd up
   ```

4. **Configure GitHub token** (in Azure portal):
   - Go to your App Service → Configuration → Application settings
   - Add `GITHUB_TOKEN` with your GitHub personal access token
   - Restart the app service

### Option 2: Manual Azure Deployment

1. **Deploy infrastructure** using Azure CLI:
   ```bash
   az login
   az group create --name rg-github-dashboard --location eastus
   az deployment group create \
     --resource-group rg-github-dashboard \
     --template-file infra/main.bicep \
     --parameters githubToken="your_token_here"
   ```

2. **Deploy application code**:
   - Use Azure App Service deployment center
   - Connect to your GitHub repository
   - Configure automatic deployments

### Environment Variables

The following environment variables are required for production:

- `GITHUB_TOKEN`: GitHub Personal Access Token for API access
- `APPLICATIONINSIGHTS_CONNECTION_STRING`: (Optional) Azure Application Insights connection string

## 📱 Usage

### Dashboard Navigation

1. **Repository Selection**: Click on any repository name in the navigation bar to view its issues
2. **Search**: Use the search box to filter issues by title, assignee, or keywords
3. **Pagination**: Navigate through issues using the pagination controls
4. **Sorting**: Issues are sorted by creation date (newest first)

### Issue Management

- **Triage**: Check/uncheck the triage checkbox to mark issues as triaged
- **Priority**: Use the dropdown to assign priority levels (High, Medium, Low, None)
- **Related PRs/Issues**: View automatically detected related PRs and issues
- **External Links**: Click issue numbers or titles to open the GitHub issue

### Sync Management

- **Automatic Sync**: Runs every 24 hours at 2:00 AM UTC
- **Manual Sync**: Access `/sync` endpoint to trigger manual synchronization
- **Sync Status**: View real-time sync status at `/sync/status`

## 🔍 PR/Issue Detection

The dashboard automatically detects related PRs and issues using multiple patterns:

1. **Full URLs**: `https://github.com/owner/repo/pull/1234`
2. **Short References**: `#1234` (assumes same repository)
3. **Text References**: `PR 1234`, `pull request #1234`

**Indicators**:
- `T` = Text-based reference
- `E` = External repository reference

## 📈 Monitoring and Observability

- **Health Check**: `/health` endpoint for monitoring
- **Sync Status**: Real-time sync monitoring with error tracking
- **Application Insights**: Automatic telemetry and performance monitoring
- **Database Metrics**: Track sync success rates and data freshness

## 🛡️ Security

- GitHub tokens are stored securely in Azure App Service configuration
- No sensitive data in code or version control
- HTTPS enforcement in production
- CORS policies configured for security

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make your changes and add tests
4. Commit your changes: `git commit -am 'Add new feature'`
5. Push to the branch: `git push origin feature/new-feature`
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🐛 Issues and Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/hectorhdzg/github-issues-dashboard/issues) page
2. Create a new issue with detailed information
3. Include logs from Azure Application Insights if available

## 🔄 Changelog

### Latest Updates
- ✅ Smart PR/Issue detection with false positive prevention
- ✅ 24-hour automatic synchronization
- ✅ Improved UI with "Related PRs/Issues" column
- ✅ Clean `#number` format for references
- ✅ Background sync with daemon threads
- ✅ Azure Bicep infrastructure templates

---

Made with ❤️ for the Azure Monitor team