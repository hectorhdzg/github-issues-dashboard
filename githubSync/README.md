## GitHub Issues Sync Service

A dedicated service for synchronizing GitHub issues and pull requests data from multiple repositories into a local SQLite database. This project provides REST APIs for data synchronization and status monitoring, making it easy to build dashboards or analytics tools on top of GitHub data.

### Features
- Synchronizes issues and pull requests from specified GitHub repositories
- Stores data in a local SQLite database (`data/github_issues.db`)
- Provides REST API endpoints for triggering syncs and retrieving status
- Sample repositories are pre-configured for quick start
- Designed for local use or deployment to Azure App Service

### Main Components
- **`src/app.py`**: Main Flask application providing API endpoints and sync logic
- **`data/github_issues.db`**: SQLite database storing issues, pull requests, and repository metadata
- **`requirements.txt`**: Python dependencies
- **`startup.sh`**: Startup script for Azure App Service deployment

### API Endpoints

#### Sync Operations
- `POST /api/sync/all` — Sync all configured repositories (issues and PRs)
- `POST /api/sync/issues` — Sync issues for a specific repository
- `POST /api/sync/prs` — Sync pull requests for a specific repository
- `GET /api/sync/status` — Get the latest sync status
- `POST /api/sync/test` — Test sync with a sample repository

#### Repository Management
- `GET /api/repositories` — Get all configured repositories
- `POST /api/repositories` — Add a new repository
- `PUT /api/repositories/{id}` — Update an existing repository
- `DELETE /api/repositories/{id}` — Remove a repository

#### Data Retrieval
- `GET /api/issues` — Get issues with optional filtering
  - Query parameters:
    - `repository` (optional): Filter by repository (format: `owner/repo`)
    - `state` (optional): Filter by state (`open`, `closed`)
    - `limit` (optional): Maximum results (default: 100)
- `GET /api/pull_requests` — Get pull requests with optional filtering
  - Query parameters:
    - `repository` (optional): Filter by repository (format: `owner/repo`)
    - `state` (optional): Filter by state (`open`, `closed`, `merged`)
    - `limit` (optional): Maximum results (default: 100)
- `GET /api/stats` — Get database statistics

#### Examples
```bash
# Get all issues
curl http://localhost:8000/api/issues

# Get open issues for a specific repository
curl "http://localhost:8000/api/issues?repository=microsoft/vscode&state=open"

# Get recent pull requests with limit
curl "http://localhost:8000/api/pull_requests?limit=50"
```

### Quick Start (Local)
1. **Install dependencies:**
	```sh
	pip install -r requirements.txt
	```
2. **Run the service:**
	```sh
	python src/app.py
	```
3. **Access the API:**
	- Default: http://localhost:8000

### 🚀 App Startup & Verification Checklist

**ALWAYS RUN THESE STEPS BEFORE WORKING ON THE PROJECT:**

#### Step 1: Start the Service
```powershell
# Navigate to project directory
cd C:\Scripts\GitHub-Issues-Dashboard\githubSync

# Stop any existing Python processes
Stop-Process -Name python -Force

# Wait for processes to stop
Start-Sleep 2

# Verify port 8000 is free (should return nothing)
netstat -an | findstr 8000

# Start the service
C:/Scripts/GitHub-Issues-Dashboard/githubSync/.venv/Scripts/python.exe src/app.py
```

#### Step 2: Verify Service is Running
```powershell
# Check if port 8000 is listening (should show LISTENING)
netstat -an | findstr 8000

# Test health endpoint (should return "OK")
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET

# Test API stats (should return JSON with database stats)
Invoke-RestMethod -Uri "http://localhost:8000/api/stats" -Method GET
```

#### Step 3: Verify Web Interface
1. **Open browser:** http://localhost:8000
2. **Check interface loads:** Should see GitHub Issues Dashboard
3. **Verify data loads:** Should see repository list, stats, and data freshness
4. **Check Recent Sync Activity:** Should show recent sync operations

#### Step 4: Service Status Indicators
**✅ Service Running Correctly:**
- Terminal shows: `* Running on http://127.0.0.1:8000`
- `netstat` shows: `TCP 0.0.0.0:8000 LISTENING`
- Health check returns: `"OK"`
- Web interface loads without errors

**❌ Service Issues:**
- `netstat` returns nothing (service not running)
- Connection refused errors
- Empty/broken web interface
- API endpoints return errors

#### Step 5: Common Fixes
```powershell
# If service won't start (port in use):
Stop-Process -Name python -Force
Start-Sleep 3
# Then restart service

# If web interface is empty:
# Check browser console for API errors
# Refresh the page (Ctrl+F5)

# If Recent Sync Activity is empty:
# Trigger a new sync from the web interface
# Or check if sync_history data exists in database
```

### Service Management

#### Starting the Service
```powershell
# Activate virtual environment (if using one)
& .venv/Scripts/Activate.ps1

# Start the service (runs in foreground)
C:/Scripts/GitHub-Issues-Dashboard/githubSync/.venv/Scripts/python.exe src/app.py
```

#### Stopping the Service
```powershell
# Kill all Python processes (be careful if you have other Python apps running)
Stop-Process -Name python -Force

# Or use Ctrl+C in the terminal where the service is running
```

#### Restarting the Service
```powershell
# Step 1: Stop any existing service
Stop-Process -Name python -Force

# Step 2: Wait a moment and verify port is free
Start-Sleep 2
netstat -an | findstr 8000

# Step 3: Start the service again
C:/Scripts/GitHub-Issues-Dashboard/githubSync/.venv/Scripts/python.exe src/app.py
```

#### Checking Service Status
```powershell
# Check if port 8000 is in use
netstat -an | findstr 8000

# Test API health endpoint
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET

# Check service logs (view terminal output where service is running)
```

#### Troubleshooting
- **"Connection Refused" error:** Service is not running, use the restart steps above
- **"Port already in use" error:** Another service is using port 8000, stop it first
- **Import errors:** Make sure virtual environment is activated and dependencies are installed
- **Database errors:** Check that `data/github_issues.db` exists and has proper permissions

### 📋 Daily Workflow Checklist

**Before Any Development Work:**
1. ✅ Run startup checklist above
2. ✅ Verify service is responding: `http://localhost:8000/health`
3. ✅ Check web interface loads: `http://localhost:8000`
4. ✅ Confirm Recent Sync Activity shows data

**During Development:**
- Monitor terminal output for errors
- Test API endpoints after code changes
- Restart service after modifying `src/app.py`

**After Making Changes:**
1. ✅ Restart service with latest code
2. ✅ Verify all endpoints still work
3. ✅ Test web interface functionality
4. ✅ Run a test sync to verify sync operations

### Environment Variables
- `GITHUB_TOKEN` (optional): GitHub personal access token for higher rate limits
- `DATABASE_PATH` (optional): Path to the SQLite database file

### Deployment
For Azure App Service, use the provided `startup.sh` for initialization and package installation.

---
**Author:** [Your Name or Organization]
**License:** MIT
