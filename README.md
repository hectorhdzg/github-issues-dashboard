# GitHub Issues Dashboard Project

This project consists of two complementary applications designed to work together for managing and visualizing GitHub issues and pull requests across multiple repositories.

## 📊 Project Overview

The project is split into two main applications:

1. **`githubSync/`** - Backend synchronization service
2. **`githubDashboard/`** - Frontend web dashboard

## 🔄 Application 1: GitHub Sync Service (`githubSync/`)

A dedicated REST API service for synchronizing GitHub issues and pull requests data from multiple repositories into a local SQLite database.

### Key Features
- **Data Synchronization**: Automatically syncs issues and pull requests from configured GitHub repositories
- **Local Database**: Stores all data in SQLite (`data/github_issues.db`) for fast local access
- **REST API**: Provides comprehensive API endpoints for sync operations and data retrieval
- **Repository Management**: Add, update, and manage multiple GitHub repositories
- **Scheduled Sync**: Built-in scheduler for automatic periodic synchronization
- **CORS Support**: Cross-origin requests enabled for frontend integration

### Main Components
- **`src/app.py`**: Main Flask application with sync logic and API endpoints
- **`setup/setup_database.py`**: Database initialization and schema setup
- **`setup/populate_repositories.py`**: Script to add sample repositories
- **`data/github_issues.db`**: SQLite database for storing synchronized data
- **`src/ui/`**: Optional web interface for repository management

### API Endpoints
```
POST /api/sync/all          # Sync all configured repositories
POST /api/sync/issues       # Sync issues for specific repository
POST /api/sync/prs          # Sync pull requests for specific repository
GET  /api/sync/status       # Get latest sync status
GET  /api/repositories      # List all configured repositories
POST /api/repositories      # Add new repository
GET  /api/issues           # Retrieve issues with filtering
GET  /api/pull_requests    # Retrieve pull requests with filtering
GET  /api/stats            # Database statistics
```

### Running the Sync Service
```bash
cd githubSync
pip install -r requirements.txt
python src/app.py
# Service runs on http://localhost:8000
```

## 📈 Application 2: GitHub Dashboard (`githubDashboard/`)

A modern Flask-based web dashboard that provides an interactive interface for viewing and managing GitHub issues and pull requests data.

### Key Features
- **Interactive Dashboard**: Modern single-page application (SPA) interface
- **Data Visualization**: Comprehensive view of issues and pull requests
- **Real-time Updates**: Dynamic content loading without page refreshes
- **Responsive Design**: Works on desktop and mobile devices
- **Issue Management**: View, filter, and interact with GitHub issues
- **Pull Request Tracking**: Monitor PR status and changes

### Main Components
- **`src/app.py`**: Flask web server serving the dashboard interface
- **`templates/dashboard.html`**: Main dashboard page template
- **`templates/base.html`**: Base template with common layout
- **`static/js/spa.js`**: Single-page application JavaScript logic
- **`static/js/navigation.js`**: Navigation and routing functionality
- **`static/css/dashboard.css`**: Dashboard styling and responsive design
- **`templates/components/`**: Reusable UI components (navbar, modals)

### Dashboard Features
- Issue and PR listing with filtering capabilities
- Detailed issue/PR modal views
- Repository statistics and summaries
- Search and sorting functionality
- Responsive navigation

### Running the Dashboard
```bash
cd githubDashboard
pip install -r requirements.txt
python src/app.py
# Dashboard runs on http://localhost:8001
```

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher
- GitHub personal access token (for API access)

### Quick Setup

1. **Start the Sync Service** (Backend)
   ```bash
   cd githubSync
   pip install -r requirements.txt
   python setup/setup_database.py
   python setup/populate_repositories.py  # Optional: add sample repos
   python src/app.py
   ```

2. **Start the Dashboard** (Frontend)
   ```bash
   cd githubDashboard
   pip install -r requirements.txt
   python src/app.py
   ```

3. **Access the Applications**
   - Dashboard: http://localhost:8001
   - Sync API: http://localhost:8000

### Environment Variables
- `GITHUB_TOKEN`: Your GitHub personal access token (required for sync service)
- `PORT`: Custom port for each service (default: 8000 for sync, 8001 for dashboard)

## 🧪 Testing

Both applications include comprehensive test suites:

### Dashboard Tests (`githubDashboard/tests/`)
- Unit tests for Flask application
- Database and API tests
- Frontend JavaScript functionality tests
- Integration tests

```bash
cd githubDashboard
python tests/run_tests.py --all
```

### Sync Service Tests (`githubSync/tests/`)
- Service functionality tests
- API endpoint tests

```bash
cd githubSync
python tests/run_tests.py
```

## 📁 Project Structure

```
GitHub-Issues-Dashboard/
├── README.md                    # This file
├── githubSync/                  # Backend sync service
│   ├── src/app.py              # Main sync service
│   ├── setup/                  # Database setup scripts
│   ├── data/                   # SQLite database storage
│   ├── tests/                  # Service tests
│   └── requirements.txt        # Python dependencies
└── githubDashboard/            # Frontend dashboard
    ├── src/app.py              # Main dashboard app
    ├── templates/              # HTML templates
    ├── static/                 # CSS and JavaScript
    ├── tests/                  # Dashboard tests
    └── requirements.txt        # Python dependencies
```

## 🔧 Configuration

### Adding Repositories
Use the sync service API to add repositories:
```bash
curl -X POST http://localhost:8000/api/repositories \
  -H "Content-Type: application/json" \
  -d '{"owner": "username", "repo": "repository-name"}'
```

### Scheduling Sync
The sync service includes automatic scheduling. Configure sync intervals in the application settings.

## 📝 License

This project is designed for monitoring GitHub repositories and can be adapted for various use cases including DevOps monitoring, project management, and issue tracking across multiple repositories.