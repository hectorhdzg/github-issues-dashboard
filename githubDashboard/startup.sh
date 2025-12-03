#!/bin/bash

# GitHub Dashboard startup script for Azure App Service
set -e

echo "Starting GitHub Dashboard initialization..."

# Ensure data directory exists
mkdir -p /home/site/data

# Enhanced package installation with fallback mechanisms
echo "Checking Python environment..."
echo "Python executable: $(which python3)"
echo "Python version: $(python3 --version)"
echo "Current working directory: $(pwd)"

# Check if we have virtual environment paths available
if [ -d "/home/site/wwwroot/antenv" ]; then
    echo "Using Oryx virtual environment..."
    export PATH="/home/site/wwwroot/antenv/bin:$PATH"
    export PYTHONPATH="/home/site/wwwroot/antenv/lib/python3.11/site-packages:$PYTHONPATH"
fi

# Install packages with multiple fallback mechanisms
echo "Installing Python packages..."
pip3 install --upgrade pip

# Primary installation attempt
if ! pip3 install -r /home/site/wwwroot/requirements.txt; then
    echo "Primary pip install failed, trying with --user flag..."
    pip3 install --user -r /home/site/wwwroot/requirements.txt
    
    if ! pip3 install --user -r /home/site/wwwroot/requirements.txt; then
        echo "Fallback pip install failed, trying manual installation..."
        pip3 install --user Flask==3.0.3
        pip3 install --user requests==2.31.0
        pip3 install --user gunicorn==23.0.0
    fi
fi

# Verify requests module installation
echo "Verifying requests module..."
python3 -c "import requests; print(f'SUCCESS: requests {requests.__version__} available at {requests.__file__}')" || {
    echo "WARNING: requests module verification failed"
    echo "Python path:"
    python3 -c "import sys; print('\n'.join(sys.path))"
}

echo "GitHub Dashboard initialization completed"
