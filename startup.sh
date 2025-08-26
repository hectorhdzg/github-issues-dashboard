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

# Configure PYTHONPATH to include Oryx-installed packages if present
ORYX_VENV_SITEPACKAGES="/home/site/wwwroot/antenv/lib/python3.11/site-packages"
ORYX_VENDOR_SITEPACKAGES="/home/site/wwwroot/.python_packages/lib/site-packages"
if [ -d "$ORYX_VENV_SITEPACKAGES" ]; then
    export PYTHONPATH="$ORYX_VENV_SITEPACKAGES:$PYTHONPATH"
    echo "Added to PYTHONPATH: $ORYX_VENV_SITEPACKAGES"
fi
if [ -d "$ORYX_VENDOR_SITEPACKAGES" ]; then
    export PYTHONPATH="$ORYX_VENDOR_SITEPACKAGES:$PYTHONPATH"
    echo "Added to PYTHONPATH: $ORYX_VENDOR_SITEPACKAGES"
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
