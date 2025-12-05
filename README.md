# GitHub Issues Dashboard (migrated)

This project has been migrated and split into two repositories:

- Data sync service: https://github.com/hectorhdzg/GithubDataSyncService
- Dashboard UI: https://github.com/hectorhdzg/GithubDashboard

No further development happens here. Please use the repositories above for all source code, issues, and updates.

### Issues Table
```sql
CREATE TABLE issues (
    id INTEGER PRIMARY KEY,
    number INTEGER,
    title TEXT,
    state TEXT,
    repo TEXT,
    assignee TEXT,
    created_at TEXT,
    updated_at TEXT,
    body TEXT,
    labels TEXT,
    html_url TEXT,
    fetched_at TEXT
);
```

### Pull Requests Table
```sql
CREATE TABLE pull_requests (
    id INTEGER PRIMARY KEY,
    number INTEGER,
    title TEXT,
    state TEXT,
    repo TEXT,
    user TEXT,
    created_at TEXT,
    updated_at TEXT,
    merged BOOLEAN,
    html_url TEXT,
    fetched_at TEXT
);
```

### Repositories Table
```sql
CREATE TABLE repositories (
    repo TEXT PRIMARY KEY,
    display_name TEXT,
    main_category TEXT,
    classification TEXT,
    priority INTEGER,
    is_active BOOLEAN,
    created_at TEXT,
    updated_at TEXT
);
```

## 🔧 Configuration

### Environment Variables
```bash
# GitHub API
GITHUB_TOKEN=your_github_token_here

# Service URLs
SYNC_SERVICE_URL=http://127.0.0.1:5001
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False

# Database
DATABASE_PATH=github_issues.db

# Monitoring
USE_MOCK_SYNC=False
SECRET_KEY=your-secret-key-here
```

### Repository Configuration
Repositories can be configured through the web interface at `/repo-management` or via API calls to `/api/repositories/manage`.

**Categories:**
- nodejs, python, dotnet, java, browser, react, angular, react-native, javascript, other

**Classifications:**
- azure, opentelemetry, microsoft, other

## 🧪 Testing

Run the test suite:
```bash
python -m pytest tests/
```

Individual test files:
```bash
python test_sync_manager.py
python test_app_routes.py
python test_repo_api.py
```

## 📊 Monitoring & Observability

- **Health Checks**: Available at `/health` endpoints
- **Sync Status**: Real-time sync progress monitoring
- **Queue Management**: Background job processing with retry logic
- **Error Handling**: Comprehensive error logging and reporting
- **Telemetry**: Built-in Azure Monitor support (disabled by default)

## 🔒 Security Considerations

- **GitHub Token**: Store in `.env` file, never in code
- **Rate Limiting**: Automatic handling of GitHub API rate limits
- **CORS**: Enabled for cross-origin requests
- **Input Validation**: All API inputs are validated
- **Error Handling**: No sensitive information in error responses

## 🚀 Deployment

### Azure Deployment (Automated)
Deploy to Azure with a single command:

```bash
# Deploy everything automatically
azd up
```

This includes:
- Infrastructure provisioning (App Service, Storage, Monitoring)
- Database initialization with 20+ repositories
- Application deployment with production configuration
- Repository setup (Azure SDK, OpenTelemetry, Application Insights)

### Local Development
Use the startup scripts for local development as described in Quick Start.

## 🐛 Troubleshooting

### Common Issues

**1. Connection Refused Errors**
```bash
# Ensure sync service is running
python sync_service.py

# Check if port 5001 is available
netstat -an | grep 5001
```

**2. Repository Management API Issues**
- Verify sync service is running on port 5001
- Check CORS headers are properly configured
- Ensure database is accessible

**3. Sync Failures**
- Check GitHub token validity
- Verify internet connectivity
- Review error logs in sync service output

**4. Database Lock Issues**
```bash
# Check for database locks
python check_db.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

For issues, questions, or contributions, please use the GitHub Issues tab or contact the maintainers.

### 2. Web Application (`app.py`) - Port 5000
- **Purpose**: Serves the dashboard UI and handles user interactions
- **Responsibilities**:
  - Renders HTML templates for dashboard, sync, and stats pages
  - Communicates with sync service via REST APIs
  - Provides web API endpoints for frontend JavaScript
- **Data Source**: Gets all data from sync service (no direct database access)

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

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd GitHub-Issues-Dashboard
   ```

2. **Set up environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

3. **Configure environment variables** (optional)
   ```bash
   # Create .env file
   GITHUB_TOKEN=your_github_token_here
   FLASK_DEBUG=true
   ```

4. **Start services**
   ```bash
   # Terminal 1: Start sync service
   python sync_service.py
   
   # Terminal 2: Start web app
   python start_app.py
   ```

5. **Access the dashboard**
   - Main Dashboard: http://127.0.0.1:5000
   - Repository Management: http://127.0.0.1:5000/repo-management
   - Sync Service API: http://127.0.0.1:5001

## 🌐 API Documentation

### Base URLs
- **Sync Service**: `http://127.0.0.1:5001`
- **Web App**: `http://127.0.0.1:5000`

### Authentication
- **Currently runs unauthenticated** (60 requests/hour limit)
- GitHub token support available but not required

---

## 🔗 Sync Service API Endpoints

### Health Check
```http
GET /health
```
**Response:**
```json
{
  "service": "GitHub Issues Sync Service",
  "status": "healthy",
  "timestamp": "2025-08-06T09:52:00.000Z"
}
```

### Sync Management

#### Get Sync Status
```http
GET /api/sync/status
```
**Response:**
```json
{
  "success": true,
  "sync_in_progress": false,
  "last_sync": "2025-08-06T09:00:00.000Z",
  "totals": {
    "open_issues": 120,
    "closed_issues": 80,
    "open_prs": 45,
    "closed_prs": 35,
    "merged_prs": 25
  },
  "by_repo": {
    "issues": {
      "repo-name": {"open": 10, "closed": 5}
    },
    "prs": {
      "repo-name": {"open": 3, "closed": 2, "merged": 1}
    }
  }
}
```

#### Start Sync
```http
POST /api/sync/start
```
**Response:**
```json
{
  "success": true,
  "message": "Sync started successfully"
}
```

#### Get Queue Status
```http
GET /api/queue/status
```
**Response:**
```json
{
  "success": true,
  "queue_size": 5,
  "processing": false,
  "next_retry": "2025-08-06T10:15:00.000Z"
}
```

### Data Access

#### Get Issues
```http
GET /api/data/issues?repo=<repo>&state=<state>&limit=<limit>&offset=<offset>
```
**Parameters:**
- `repo` (optional): Repository name (e.g., "microsoft/ApplicationInsights-dotnet")
- `state` (optional): "open", "closed", or "all" (default: "all")
- `limit` (optional): Number of items to return (default: 100, max: 1000)
- `offset` (optional): Number of items to skip (default: 0)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 123,
      "number": 4856,
      "title": "Memory leak in trace exports",
      "body": "We are experiencing memory leaks...",
      "state": "open",
      "author": "username",
      "assignees": "[\"user1\", \"user2\"]",
      "labels": "[\"bug\", \"memory-leak\"]",
      "created_at": "2025-08-06T08:00:00.000Z",
      "updated_at": "2025-08-06T09:00:00.000Z",
      "html_url": "https://github.com/repo/issues/4856",
      "repository_name": "open-telemetry/opentelemetry-js"
    }
  ],
  "pagination": {
    "count": 1,
    "total": 156,
    "offset": 0,
    "limit": 100
  }
}
```

#### Get Pull Requests
```http
GET /api/data/prs?repo=<repo>&state=<state>&limit=<limit>&offset=<offset>
```
**Parameters:** Same as issues endpoint

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 456,
      "number": 789,
      "title": "Fix memory leak in trace exports",
      "body": "Fixes #4856...",
      "state": "open",
      "author": "username",
      "assignees": "[]",
      "labels": "[\"fix\"]",
      "created_at": "2025-08-06T08:30:00.000Z",
      "updated_at": "2025-08-06T09:30:00.000Z",
      "html_url": "https://github.com/repo/pull/789",
      "repository_name": "open-telemetry/opentelemetry-js",
      "merged": false,
      "draft": false
    }
  ]
}
```

#### Get Repositories
```http
GET /api/data/repositories
```
**Response:**
```json
{
  "success": true,
  "repositories": [
    "microsoft/ApplicationInsights-dotnet",
    "open-telemetry/opentelemetry-js"
  ]
}
```

### Repository Management

#### List Repositories with Metadata
```http
GET /api/repositories/manage
```
**Response:**
```json
{
  "success": true,
  "repositories": [
    {
      "repo": "microsoft/ApplicationInsights-dotnet",
      "display_name": "ApplicationInsights .NET SDK",
      "main_category": "dotnet",
      "classification": "azure",
      "priority": 1,
      "is_active": true,
      "created_at": "2025-08-06T08:00:00.000Z",
      "updated_at": "2025-08-06T09:00:00.000Z"
    }
  ]
}
```

#### Add Repository
```http
POST /api/repositories/manage
Content-Type: application/json

{
  "repo": "microsoft/ApplicationInsights-Java",
  "display_name": "ApplicationInsights Java SDK",
  "main_category": "java",
  "classification": "azure",
  "priority": 2,
  "is_active": true
}
```

#### Update Repository
```http
PUT /api/repositories/manage/<repo_name>
Content-Type: application/json

{
  "display_name": "ApplicationInsights Java SDK (Updated)",
  "main_category": "java",
  "classification": "azure",
  "priority": 1,
  "is_active": true
}
```

#### Delete Repository
```http
DELETE /api/repositories/manage/<repo_name>
```

---

## 🎯 Web Application API Endpoints

### Dashboard Data
```http
GET /api/dashboard/data?type=<type>&state=<state>&repo=<repo>
```
**Parameters:**
- `type`: "all", "issues", "prs" (default: "all")
- `state`: "open", "closed", "all" (default: "open")
- `repo`: Repository name or "all" (default: "all")

### Sync Operations
```http
GET /api/sync_status
POST /api/sync_now
```

### Health Check
```http
GET /api/health
```

## 🗂️ Project Structure

```
GitHub-Issues-Dashboard/
├── app.py                 # Main web application
├── sync_service.py        # GitHub sync service
├── start_app.py          # Application launcher
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   ├── dashboard.html
│   ├── sync.html
│   ├── stats.html
│   └── repo_management.html
├── static/              # Static assets
│   ├── css/
│   └── js/
├── infra/              # Azure infrastructure
│   ├── main.bicep
│   └── main.parameters.json
└── azure.yaml          # Azure Developer CLI config
```

## 🚀 Deployment

### Azure App Service (Automated)
Deploy with a single command - everything is automated:

```bash
azd up
```

This automatically:
- Creates Azure infrastructure (App Service, Storage, Monitoring)
- Initializes database with 20+ pre-configured repositories
- Deploys application with production settings
- Sets up monitoring and health checks

Optional: Set GitHub token for better rate limits:
```bash
azd env set GITHUB_TOKEN "your_github_token_here"
azd up
```

## 🛠️ Development

### Adding New Repositories
1. Use the Repository Management interface at `/repo-management`
2. Or use the API endpoints directly
3. Configure repository metadata (display name, category, classification, priority)

### Customizing the Dashboard
1. **Templates**: Modify files in `templates/` directory
2. **Styling**: Update CSS in `static/css/dashboard.css`
3. **JavaScript**: Enhance functionality in `static/js/`

### Database Schema
The application uses SQLite with the following main tables:
- `issues`: GitHub issues data
- `pull_requests`: GitHub pull requests data
- `repositories`: Repository metadata and configuration

## 📋 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub personal access token | None (unauthenticated) |
| `FLASK_DEBUG` | Enable Flask debug mode | False |
| `FLASK_HOST` | Flask host address | 0.0.0.0 |
| `FLASK_PORT` | Flask port number | 5000 |
| `SYNC_SERVICE_URL` | Sync service URL | http://127.0.0.1:5001 |

## 🔧 Troubleshooting

### Common Issues

**1. Repository Management Not Loading Data**
- Ensure sync service is running on port 5001
- Check that repository metadata endpoints are accessible
- Verify database contains repository records

**2. GitHub Rate Limiting**
- Add GitHub token to increase rate limit from 60 to 5000 requests/hour
- Monitor queue status for rate-limited requests

**3. Sync Service Connection Issues**
- Verify sync service is running: `http://127.0.0.1:5001/health`
- Check firewall settings
- Ensure ports 5000 and 5001 are available

### Debug Commands
```bash
# Test sync service health
curl http://127.0.0.1:5001/health

# Test web app health  
curl http://127.0.0.1:5000/api/health

# Check repository management API
curl http://127.0.0.1:5001/api/repositories/manage
```

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

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

3. **Set environment variables** (optional):
   ```bash
   # Windows (PowerShell) - Optional for better performance
   $env:GITHUB_TOKEN="your_github_token_here"
   
   # Linux/Mac - Optional for better performance  
   export GITHUB_TOKEN="your_github_token_here"
   ```
   
   **Note**: GitHub token is optional. The app works in unauthenticated mode but with lower rate limits.

4. **Run the application**:
   ```bash
   python app.py
   ```

5. **Access the dashboard**:
   - **Main Dashboard**: `http://localhost:5000`
   - **Sync Management**: `http://localhost:5000/sync`
   - **Health Check**: `http://localhost:5000/health`

### GitHub Token Setup (Optional but Recommended)

**Note**: The dashboard can run without a GitHub token in unauthenticated mode, but adding a token provides better performance and data coverage.

**Benefits of GitHub Token**:
- **Higher Rate Limits**: 5,000 vs 60 requests per hour
- **More Data**: Fetch up to 500 issues per repository vs 200
- **Better Reliability**: Reduced chance of rate limit errors

**Setup Steps**:
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token with these permissions:
   - `repo` (Full control of private repositories) - *for private repos only*
   - `public_repo` (Access public repositories) - *sufficient for public repos*
   - `read:org` (Read org and team membership) - *optional*
3. Copy the token and set it as the `GITHUB_TOKEN` environment variable

**Token Permissions Explained**:
- **Public repositories only**: Use `public_repo` scope
- **Private repositories**: Use full `repo` scope
- **Organization repositories**: Add `read:org` for better access

## ☁️ Azure Deployment

### Automated Azure Deployment

**One-command deployment** - everything is automated:

```bash
# Install Azure Developer CLI if needed
winget install microsoft.azd  # Windows
# brew tap azure/azd && brew install azd  # macOS
# curl -fsSL https://aka.ms/install-azd.sh | bash  # Linux

# Login and deploy
azd auth login
azd up
```

**That's it!** The deployment automatically:
- ✅ Creates all Azure infrastructure
- ✅ Initializes database with 20+ repositories
- ✅ Configures production environment
- ✅ Sets up monitoring and health checks

**Optional**: Set GitHub token for better rate limits:
```bash
azd env set GITHUB_TOKEN "your_github_token_here"
azd up
```

### What Gets Deployed
- **Repositories**: 20+ pre-configured (Azure SDK, OpenTelemetry, App Insights)
- **Infrastructure**: App Service, Storage, Application Insights, Log Analytics
- **Configuration**: Production-ready settings with monitoring
- **Database**: SQLite with schema and repository metadata

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

The dashboard includes a comprehensive sync management interface at `/sync` for monitoring and controlling data synchronization:

#### Accessing Sync Management
- **URL**: `http://localhost:5000/sync` (local) or `https://your-app.azurewebsites.net/sync` (production)
- **Auto-refresh**: Page automatically refreshes every 30 seconds

#### Sync Modes

**🔑 Authenticated Mode** (with GITHUB_TOKEN):
- **Rate Limit**: 5,000 requests per hour
- **Data Coverage**: Up to 5 pages per repository (~500 issues each)
- **Recommended**: For comprehensive data collection

**📡 Unauthenticated Mode** (without GITHUB_TOKEN):
- **Rate Limit**: 60 requests per hour
- **Data Coverage**: Up to 2 pages per repository (~200 issues each)
- **Safe for Daily Sync**: 28 total requests across 14 repositories

#### Sync Controls

1. **🚀 Trigger Manual Sync**: Start immediate synchronization
2. **🔄 Refresh**: Reload sync status
3. **🏠 Back to Dashboard**: Return to main dashboard

#### Sync Status Information

- **Authentication Status**: Shows current API access mode and rate limits
- **Last Sync**: Timestamp of most recent successful sync
- **Next Scheduled Sync**: Automatic sync occurs daily at 2:00 AM UTC
- **Total Issues Synced**: Count of issues processed in last sync
- **Recent Errors**: List of any sync failures with detailed messages
- **Repository Status**: Shows all configured repositories

#### Understanding Sync Results

- **✅ Success**: All repositories synced successfully
- **⚠️ Partial**: Some repositories failed (check error list)
- **❌ Failed**: Sync encountered critical errors
- **🔄 In Progress**: Sync currently running (button disabled)

#### Troubleshooting Sync Issues

**Rate Limit Exceeded**:
```
❌ Rate limit exceeded for owner/repo. Try again later or add GITHUB_TOKEN.
```
- **Solution**: Wait for rate limit reset or add GitHub token

**Network Errors**:
```
❌ Network error fetching owner/repo: Connection timeout
```
- **Solution**: Check internet connectivity and GitHub status

**Authentication Issues**:
```
❌ Forbidden error for owner/repo: Bad credentials
```
- **Solution**: Verify GitHub token is valid and has required permissions

#### Automatic Scheduling

- **Frequency**: Every 24 hours
- **Time**: 2:00 AM UTC (avoids peak hours)
- **Background**: Runs automatically without user intervention
- **Smart Delays**: Built-in delays between repositories to respect rate limits

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