#!/usr/bin/env python3
"""
Simple startup script for the repository management page
"""

print("🚀 Starting Repository Management Tool...")
print("📋 Make sure sync service is running on port 5001")

try:
    from app import app
    print("✅ Flask app imported successfully")
    
    print("🌐 Starting web server...")
    print("📝 Repository Management URL: http://127.0.0.1:5000/repo-management")
    print("📝 Main Dashboard URL: http://127.0.0.1:5000/")
    print("⏹️  Press Ctrl+C to stop the server")
    print("-" * 50)
    
    app.run(host='127.0.0.1', port=5000, debug=True)
    
except Exception as e:
    print(f"❌ Error starting Flask app: {e}")
    input("Press Enter to exit...")
