# GitHub Issues Dashboard

A Flask-based web application designed to track and manage GitHub issues and pull requests across Azure Monitor TelReach SDK repositories. This dashboard provides a centralized view for monitoring issues across m## 🧪 Testing

### Test Structure
The application includes comprehensive tests organized in the `tests/` directory:

```
tests/
├── __init__.py              # Tests package
├── conftest.py              # Test configuration and utilities
├── run_tests.py             # Test runner script
├── pytest.ini              # Pytest configuration
├── fixtures/
│   └── test_data.json       # Test data fixtures
├── unit/
│   ├── test_flask_app.py    # Flask application tests
│   ├── test_database_api.py # Database and API tests
│   └── test_spa_functionality.py # JavaScript SPA tests
└── integration/
    └── test_integration.py  # End-to-end integration tests
```

### Running Tests

#### Install Test Dependencies
```bash
pip install -r requirements.txt
```

#### Run All Tests
```bash
python tests/run_tests.py --all
```

#### Run Specific Test Types
```bash
# Unit tests only
python tests/run_tests.py --unit

# Integration tests only (requires services running)
python tests/run_tests.py --integration

# Specific test module
python tests/run_tests.py --test tests.unit.test_flask_app
```

#### Using Pytest Directly
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test files
pytest tests/unit/test_flask_app.py
pytest tests/integration/test_integration.py -v
```

### Test Types

#### Unit Tests
- **Flask App Tests**: Route testing, template rendering, configuration
- **Database/API Tests**: Data fetching, API interactions, error handling
- **SPA Functionality Tests**: State management, data processing, pagination

#### Integration Tests
- **End-to-End Workflow**: Complete application workflow testing
- **Template Integration**: Template rendering with real data
- **API Data Flow**: Service communication and data consistency

### Test Configuration

#### Environment Variables
```bash
# Enable integration tests (requires running services)
export INTEGRATION_TESTS=1

# Enable API connectivity tests
export API_TESTS=1
```

#### Test Dependencies
- `pytest` - Test framework
- `pytest-mock` - Mocking utilities
- `coverage` - Code coverage reporting
- `unittest-xml-reporting` - XML test reports

### Mock Data
Test fixtures include realistic mock data for:
- GitHub repositories
- Issues and pull requests
- Sync service responses
- API error scenarios

### Continuous Integration
Tests are designed to run in CI environments with:
- Isolated test database (in-memory SQLite)
- Mock API responses
- Environment-specific configuration

## 📝 Notes

- The application expects a separate sync service running on port 8000
- SQLite database should be initialized by the sync service before starting the dashboard
- Static files are served directly by Flask in development; consider a reverse proxy for production
- The application is optimized for Azure Monitor SDK repository structures
- **Always run the dashboard in a dedicated terminal to avoid accidentally killing the process**

---

*Built for Azure Monitor TelReach SDK Issue Management*gramming language SDKs.

## 🎯 Purpose

This application was specifically built to help manage GitHub issues across Azure Monitor TelReach SDKs for different programming languages:
- **Node.js SDK**
- **Python SDK**
- **Browser JavaScript SDK**
- **.NET SDK**
- **Java SDK**

## ✨ Features

### Core Functionality
- **Dashboard View**: Unified view of issues and pull requests across all monitored repositories
- **Data Type Toggle**: Switch between viewing Issues and Pull Requests
- **Repository Management**: Add, remove, and manage GitHub repositories
- **Statistics Page**: Comprehensive overview with repository statistics
- **Sync Status**: Monitor GitHub data synchronization status and performance

### Single Page Application (SPA)
- Client-side routing and state management
- Real-time data updates without page refreshes
- Responsive design with Bootstrap 5
- Interactive modals for detailed issue/PR information

### Data Management
- SQLite database (`github_issues.db`) for local data storage
- Sync service integration for GitHub API data fetching
- Caching mechanisms for improved performance

## 🏗️ Architecture

### Backend (Flask)
- **Main Application**: [`src/app.py`](src/app.py) - Core Flask application with route definitions
- **Startup Script**: [`src/start_dashboard.py`](src/start_dashboard.py) - Dashboard service launcher
- **Templates**: Jinja2 templates in [`templates/`](templates/) directory
- **Static Assets**: CSS and JavaScript files in [`static/`](static/) directory

### Frontend
- **SPA Controller**: [`static/js/spa.js`](static/js/spa.js) - Single-page application logic
- **Navigation**: [`static/js/navigation.js`](static/js/navigation.js) - Navigation management
- **Styling**: [`static/css/dashboard.css`](static/css/dashboard.css) - Custom dashboard styles

### Database
- **SQLite Database**: [`data/github_issues.db`](data/github_issues.db) - Local data storage
- Stores GitHub issues, pull requests, and synchronization metadata

## 📋 Application Routes

| Route | Purpose | Template |
|-------|---------|----------|
| `/` | Main dashboard | [`dashboard.html`](templates/dashboard.html) |
| `/stats` | Repository statistics | [`stats.html`](templates/stats.html) |
| `/repositories` | Repository listing | [`repositories.html`](templates/repositories.html) |
| `/repo-management` | Repository management interface | [`repo_management.html`](templates/repo_management.html) |

## ⚙️ Configuration

### Environment Variables
- `PORT`: Server port (default: 8001)
- `SYNC_SERVICE_URL`: URL for the sync service (default: http://localhost:8000)
- `DATABASE_PATH`: Path to SQLite database (default: ../data/github_issues.db)

### Dependencies
See [`requirements.txt`](requirements.txt):
- **Flask 3.0.3**: Web framework
- **requests 2.31.0**: HTTP client for API calls
- **gunicorn 23.0.0**: WSGI HTTP Server for production deployment

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- pip package manager

### Installation

1. **Clone the repository** (if not already done)
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the application**:
   ```bash
   # Using the startup script (recommended)
   python src/start_dashboard.py
   
   # Or directly
   python src/app.py
   ```

4. **Access the dashboard**: Open http://localhost:8001 in your browser

### Development Setup
For development, you can run the Flask app in debug mode by modifying [`src/app.py`](src/app.py) and setting `debug=True`.

## 🔧 IMPORTANT: App Status Verification Protocol

### ⚡ ALWAYS Follow This Checklist Before Any Work:

1. **Check Dashboard Status**: 
   ```bash
   netstat -an | findstr ":8001"
   ```
   - Should show `LISTENING` on port 8001
   - If not listening, start the dashboard

2. **Check Sync Service Status**:
   ```bash
   netstat -an | findstr ":8000"
   ```
   - Should show `LISTENING` on port 8000
   - This is the data source for the dashboard

3. **Test Dashboard API Access**:
   ```bash
   curl http://localhost:8001
   ```
   - Should return HTML content
   - If connection refused, restart dashboard

4. **Test Sync Service API**:
   ```bash
   curl http://localhost:8000/api/repositories
   ```
   - Should return JSON with repository data
   - If this fails, the dashboard will have no data

5. **Start Dashboard if Needed**:
   ```bash
   cd "c:\Scripts\GitHub-Issues-Dashboard\githubDashboard"
   python src/start_dashboard.py
   ```

### 🚨 Critical Rules for Every Session:

- **ALWAYS verify both services are running before making any changes**
- **NEVER run additional commands in the terminal running the dashboard**
- **Use a separate terminal for testing/debugging**
- **Check `http://localhost:8001` in browser to confirm dashboard is accessible**
- **If dashboard shows no data, verify sync service is running and returning data**

## 🐳 Deployment

### Azure App Service
The application includes Azure App Service deployment configuration:
- **Startup Script**: [`startup.sh`](startup.sh) - Azure App Service initialization
- Automatic virtual environment detection and package installation
- Production-ready configuration with gunicorn

### Manual Deployment
For other platforms, use gunicorn:
```bash
gunicorn --bind 0.0.0.0:8001 src.app:app
```

## 📊 Data Flow

1. **External Sync Service** (port 8000) fetches data from GitHub API
2. **Dashboard Application** (port 8001) reads data from SQLite database
3. **SPA Frontend** dynamically updates the UI based on user interactions
4. **Real-time Updates** through periodic data refresh

## 🔧 Key Components

### Templates
- **Base Template**: [`templates/base.html`](templates/base.html) - Common layout and navigation
- **Component Templates**: [`templates/components/`](templates/components/) - Reusable UI components
  - [`navbar.html`](templates/components/navbar.html) - Navigation bar
  - [`issue_modal.html`](templates/components/issue_modal.html) - Issue detail modal
  - [`pr_modal.html`](templates/components/pr_modal.html) - Pull request detail modal

### JavaScript Architecture
- **SPA Pattern**: Single-page application with client-side routing
- **State Management**: Centralized state management for data type, filters, and selected repositories
- **Caching**: Client-side caching for improved performance

## 🎨 UI Features

- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Dark/Light Theme Support**: Consistent with Azure design patterns
- **Interactive Charts**: Statistics visualization
- **Real-time Status Indicators**: Sync status and data freshness indicators
- **Modal Dialogs**: Detailed views for issues and pull requests

## 🔍 Monitoring Features

- **Sync Statistics**: Track synchronization performance and errors
- **Repository Health**: Monitor issue counts and trends across SDKs
- **Data Freshness**: Visual indicators for last sync times
- **Error Tracking**: Identification and reporting of sync issues

## 🤝 Contributing

This dashboard is specifically designed for Azure Monitor TelReach SDK management. When making changes:

1. Ensure compatibility with the existing sync service architecture
2. Maintain the SPA pattern for frontend interactions
3. Follow the established Flask route structure
4. Update this README when adding new features

## � Troubleshooting

### Dashboard Server Management

**⚠️ CRITICAL: Process Management Issue**

When running the dashboard, be careful not to accidentally kill the server process by running additional commands in the same terminal or starting new processes. This is a common issue that causes the dashboard to become unreachable.

**Symptoms:**
- Browser shows "ERR_CONNECTION_REFUSED" 
- `localhost:8001` refuses to connect
- Dashboard was working but suddenly stops

**Solutions:**
1. **Use separate terminals**: Always run the dashboard in a dedicated terminal window
2. **Check if process is still running**: Use `netstat -an | findstr ":8001"` to verify the dashboard is listening
3. **Restart the dashboard**: If killed accidentally, restart with:
   ```bash
   python src/start_dashboard.py
   ```

### Common Issues

1. **No Data Displayed**
   - Ensure sync service is running on port 8000: `netstat -an | findstr ":8000"`
   - Test sync service API: `curl http://localhost:8000/api/repositories`
   - Check browser developer console for JavaScript errors

2. **CORS/API Connection Issues**
   - The dashboard now includes API proxy endpoints to avoid CORS issues
   - Frontend should call `/api/repositories` not `http://localhost:8000/api/repositories`

3. **Database Issues**
   - Ensure `data/github_issues.db` exists and is populated by sync service
   - Check sync service logs for database initialization errors

## �📝 Notes

- The application expects a separate sync service running on port 8000
- SQLite database should be initialized by the sync service before starting the dashboard
- Static files are served directly by Flask in development; consider a reverse proxy for production
- The application is optimized for Azure Monitor SDK repository structures
- **Always run the dashboard in a dedicated terminal to avoid accidentally killing the process**

---

*Built for Azure Monitor TelReach SDK Issue Management*
