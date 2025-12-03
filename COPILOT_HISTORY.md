# Copilot Session Notes

## Environment & Services
- Sync service: run from `githubSync/src/app.py` using `python` on port 8000.
- Dashboard UI: run from `githubDashboard/src/app.py` using `python` on port 8001.
- Local SQLite database resides at `githubSync/data/github_issues.db` (ignored by git).

## Recent Engineering Work
- Implemented incremental GitHub sync with conditional requests and sync metadata tracking.
- Rebuilt the dashboard SPA navigation to group repositories by language/type and keep counts in sync.
- Restored Node.js vs Web/Browser language buckets in the navbar and intro stats.
- Cleaned up unused artifacts (`spa.js.broken_backup`, `github_issues_backup.db`) and removed tracked databases.

## Helpful Commands
- Full sync trigger: `Invoke-RestMethod -Uri "http://localhost:8000/api/sync/full" -Method Post`.
- Launch sync API: `python githubSync/src/app.py` (or use `.venv` interpreter).
- Launch dashboard: `python githubDashboard/src/app.py` from activated virtualenv.

## Outstanding Questions / Follow Ups
- Verify PR counts now populate after incremental sync change.
- Confirm Azure deployment scripts still align with updated project layout.
- Consider adding automated tests around new language grouping logic in `githubDashboard/static/js/spa.js`.
