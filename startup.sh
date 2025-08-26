#!/bin/bash
# Azure App Service startup script for GitHub Issues Dashboard

echo "=== GitHub Issues Dashboard - Azure Deployment Startup ==="
echo "Timestamp: $(date)"

# Detect app root (Oryx runs user startup in the extracted app directory like /tmp/XXXX)
APP_ROOT="$(pwd -P)"
echo "App root detected: $APP_ROOT"

# Ensure persistent data directory exists under /home
# Note: When WEBSITE_RUN_FROM_PACKAGE=1, /home/site/wwwroot is read-only.
# Use /home/site/data for writable persistent storage.
PERSISTENT_DATA_DIR="/home/site/data"
echo "Setting up data directory at $PERSISTENT_DATA_DIR..."
mkdir -p "$PERSISTENT_DATA_DIR"
chmod 755 "$PERSISTENT_DATA_DIR"

# Set environment variables for the database
export DATABASE_PATH="$PERSISTENT_DATA_DIR/github_issues.db"

# Check if auto-initialization is enabled
AUTO_INIT=${AUTO_INIT_REPOS:-true}
echo "Auto-initialization enabled: $AUTO_INIT"

# Skip repository initialization here; deployment script will warm endpoints post-provision
if [ "$AUTO_INIT" = "true" ]; then
    echo "AUTO_INIT_REPOS is enabled; repository init will be triggered by deployment script after app is ready."
fi

# Verify database exists
if [ -f "$DATABASE_PATH" ]; then
    echo "Database verified at: $DATABASE_PATH"
    ls -la "$DATABASE_PATH"
else
    echo "Warning: Database file not found"
fi

# Set production environment
export FLASK_ENV=${FLASK_ENV:-production}
export FLASK_DEBUG=${FLASK_DEBUG:-false}

# Normalize port: prefer WEBSITES_PORT if provided by App Service, else 8000
export PORT=${WEBSITES_PORT:-${PORT:-8000}}

# Start the Flask application with gunicorn for production
echo "Starting Flask application with gunicorn on port $PORT..."

# Ensure Python packages are available when running from package
PACKAGE_DIR="/home/site/packages"
export PYTHONPATH="$PACKAGE_DIR:${PYTHONPATH}"
echo "Using PYTHONPATH: $PYTHONPATH"

# Install a minimal set of packages required to boot the app quickly
mkdir -p "$PACKAGE_DIR"
if command -v python3 >/dev/null 2>&1; then
    PYBIN="python3"
else
    PYBIN="python"
fi

# Determine which minimal modules are missing
"$PYBIN" - <<'PY'
import importlib, json
mods = ["flask", "gunicorn", "requests"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
print(json.dumps(missing))
PY
MISSING=$(tail -n 1 | tr -d '\r')
if [ -n "$MISSING" ] && [ "$MISSING" != "[]" ]; then
    echo "Installing missing Python packages into $PACKAGE_DIR: $MISSING"
    # shellcheck disable=SC2001
    PKGS=$(echo "$MISSING" | sed 's/\[\|\]\|\"//g' | sed 's/,/ /g')
    "$PYBIN" -m pip install --no-cache-dir --upgrade $PKGS --target "$PACKAGE_DIR" || {
        echo "Error: minimal pip install failed for $PKGS" >&2
    }
else
    echo "Minimal Python packages already available."
fi

# Determine working directory containing src
WORKDIR="$APP_ROOT"
if [ -d "$APP_ROOT/src" ]; then
    WORKDIR="$APP_ROOT/src"
elif [ -d "/home/site/wwwroot/src" ]; then
    WORKDIR="/home/site/wwwroot/src"
fi
echo "Using working directory: $WORKDIR"

# Use gunicorn for production deployment
exec gunicorn --bind=0.0.0.0:${PORT} \
    --workers=2 \
    --timeout=600 \
    --access-logfile=- \
    --error-logfile=- \
    --log-level=info \
    --preload \
    --chdir="$WORKDIR" \
    app:app
