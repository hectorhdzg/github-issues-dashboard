# Repository Management UI

A web-based user interface for managing GitHub repositories in the sync service.

## Features

- **Repository Management**
  - View all configured repositories
  - Add new repositories with metadata
  - Remove repositories
  - Sync repositories (issues, PRs, or both)

- **Real-time Statistics**
  - Total repositories count
  - Issues and PRs statistics
  - Service health status

- **User-friendly Interface**
  - Bootstrap-based responsive design
  - Card-based repository layout
  - Priority-based visual indicators
  - Dropdown actions for each repository

## Quick Start

1. **Ensure the sync service is running:**
   ```bash
   cd ../
   python src/app.py
   ```

2. **Open the management UI:**
   - Open `index.html` in your web browser
   - Or serve it with a simple HTTP server:
   ```bash
   python -m http.server 3000
   ```
   - Then visit: http://localhost:3000

## API Integration

The UI connects to the sync service API at `http://localhost:8000/api` and uses these endpoints:

- `GET /api/repositories` - List repositories
- `GET /api/stats` - Get statistics
- `GET /health` - Service health check
- `POST /api/sync/repositories/{repo}/issues` - Sync issues
- `POST /api/sync/repositories/{repo}/prs` - Sync PRs
- `POST /api/sync/repositories/{repo}` - Sync both

## Features to Implement

- **Add Repository Backend**: Need API endpoint to add repositories
- **Remove Repository Backend**: Need API endpoint to remove repositories
- **Toast Notifications**: Replace alerts with proper toast notifications
- **Sync History**: Show detailed sync activity and logs
- **Repository Details**: View detailed info about each repository

## File Structure

```
management-ui/
├── index.html          # Main UI page
├── app.js             # JavaScript application logic
└── README.md          # This file
```
