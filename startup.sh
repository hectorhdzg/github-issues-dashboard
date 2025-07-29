#!/usr/bin/env bash
# Azure Web App startup script

echo "🚀 Starting GitHub Issues Dashboard on Azure..."

# Install dependencies
pip install -r requirements.txt

# Set environment variables for production
export FLASK_ENV=production
export PYTHONPATH=/home/site/wwwroot

# Create database directory if it doesn't exist
mkdir -p /home/site/data

# Start the application with gunicorn
gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 300 app:app
