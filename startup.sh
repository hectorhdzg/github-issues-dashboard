#!/bin/bash
# Azure App Service startup script for GitHub Issues Dashboard

echo "=== GitHub Issues Dashboard - Azure Deployment Startup ==="
echo "Timestamp: $(date)"

# Ensure data directory exists
echo "Setting up data directory..."
mkdir -p /home/site/wwwroot/data
chmod 755 /home/site/wwwroot/data

# Set environment variables for the database
export DATABASE_PATH="/home/site/wwwroot/data/github_issues.db"

# Check if auto-initialization is enabled
AUTO_INIT=${AUTO_INIT_REPOS:-true}
echo "Auto-initialization enabled: $AUTO_INIT"

# Initialize repositories if needed
if [ "$AUTO_INIT" = "true" ] || [ ! -f "$DATABASE_PATH" ]; then
    echo "Initializing repository database..."
    cd /home/site/wwwroot
    
    # Install dependencies if needed
    if [ ! -d "__pycache__" ]; then
        echo "Installing Python dependencies..."
        pip install -r requirements.txt
    fi
    
    # Run repository setup
    python scripts/setup_deployment_repos.py --action setup --db-path "$DATABASE_PATH" --force-update
    
    if [ $? -eq 0 ]; then
        echo "Repository initialization completed successfully"
        
        # Show summary
        python scripts/setup_deployment_repos.py --action summary --db-path "$DATABASE_PATH"
    else
        echo "Warning: Repository initialization failed, but continuing startup"
    fi
else
    echo "Database exists and auto-init disabled, skipping initialization"
fi

# Verify database exists
if [ -f "$DATABASE_PATH" ]; then
    echo "Database verified at: $DATABASE_PATH"
    ls -la "$DATABASE_PATH"
else
    echo "Warning: Database file not found"
fi

# Set production environment
export FLASK_ENV=production
export FLASK_DEBUG=false

# Start the Flask application with gunicorn for production
echo "Starting Flask application with gunicorn..."
cd /home/site/wwwroot

# Use gunicorn for production deployment
exec gunicorn --bind=0.0.0.0:${PORT:-8000} \
    --workers=2 \
    --timeout=600 \
    --access-logfile=- \
    --error-logfile=- \
    --log-level=info \
    --preload \
    --chdir=/home/site/wwwroot/src \
    app:app
