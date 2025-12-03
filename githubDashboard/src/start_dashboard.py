#!/usr/bin/env python3
"""
Start dashboard service on port 8001
"""
import os
import sys

# Set environment variables
os.environ['PORT'] = '8001'
os.environ['SYNC_SERVICE_URL'] = 'http://localhost:8000'
os.environ['DATABASE_PATH'] = '../data/github_issues.db'

# Change to dashboard app directory
sys.path.insert(0, os.path.dirname(__file__))

try:
    from app import app
    print("✅ Starting Dashboard Service on port 8001")
    print("✅ Sync Service URL: http://localhost:8000")
    app.run(host='0.0.0.0', port=8001, debug=False)
except Exception as e:
    print(f"❌ Error starting dashboard: {e}")
    import traceback
    traceback.print_exc()
