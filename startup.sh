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

    # Fallback: if core modules are still missing, install minimal packages into /home/site/packages
    PY_FALLBACK_DIR="/home/site/packages"
    python3 - <<'PY' || true
    import importlib, sys
    mods = ["flask", "requests", "gunicorn"]
    missing = [m for m in mods if importlib.util.find_spec(m) is None]
    sys.exit(1 if missing else 0)
    PY
    if [ $? -ne 0 ]; then
        echo "Installing minimal packages into $PY_FALLBACK_DIR..."
        mkdir -p "$PY_FALLBACK_DIR"
        python3 -m pip install --no-cache-dir --upgrade flask requests gunicorn --target "$PY_FALLBACK_DIR" || echo "Warning: fallback pip install failed"
        export PYTHONPATH="$PY_FALLBACK_DIR:$PYTHONPATH"
        echo "Added to PYTHONPATH: $PY_FALLBACK_DIR"
    fi

# Determine working directory containing src
WORKDIR="$APP_ROOT"
if [ -d "$APP_ROOT/src" ]; then
    WORKDIR="$APP_ROOT/src"
elif [ -d "/home/site/wwwroot/src" ]; then
    WORKDIR="/home/site/wwwroot/src"
fi
echo "Using working directory: $WORKDIR"

# Diagnostics: print python info and module availability
if command -v python3 >/dev/null 2>&1; then PYBIN=python3; else PYBIN=python; fi
echo "Python binary: $(command -v $PYBIN || echo 'not found')"
echo "Python version: $($PYBIN --version 2>&1 || echo 'n/a')"
$PYBIN - <<'PY'
import sys
print('sys.executable:', sys.executable)
print('sys.path:')
for p in sys.path:
    print(' -', p)
def check(name):
    try:
        __import__(name)
        print(f'MODULE OK: {name}')
    except Exception as e:
        print(f'MODULE MISSING: {name} -> {e}')
for m in ('flask','requests','gunicorn'):
    check(m)
PY

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
