#!/usr/bin/env python3
"""
Simple Test Runner to verify basic functionality
"""

import os
import sys
import json
import tempfile
import sqlite3

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_flask_import():
    """Test that Flask app can be imported"""
    try:
        from app import app
        print("✅ Flask app imports successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import Flask app: {e}")
        return False

def test_basic_routes():
    """Test basic Flask routes"""
    try:
        from app import app
        app.config['TESTING'] = True
        client = app.test_client()
        
        # Test main route
        response = client.get('/')
        if response.status_code == 200:
            print("✅ Main route (/) works")
        else:
            print(f"❌ Main route failed with status {response.status_code}")
            return False
        
        # Test API route
        response = client.get('/api/sync_status')
        if response.status_code == 200:
            print("✅ Sync status API works")
            data = json.loads(response.data)
            if 'sync_in_progress' in data:
                print("✅ Sync status API returns correct format")
            else:
                print("❌ Sync status API returns incorrect format")
                return False
        else:
            print(f"❌ Sync status API failed with status {response.status_code}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Route testing failed: {e}")
        return False

def test_static_files():
    """Test that static files are accessible"""
    try:
        from app import app
        app.config['TESTING'] = True
        client = app.test_client()
        
        # Test CSS file
        response = client.get('/static/css/dashboard.css')
        if response.status_code == 200:
            print("✅ CSS file accessible")
        else:
            print(f"❌ CSS file not accessible: {response.status_code}")
            return False
        
        # Test JS file
        response = client.get('/static/js/dashboard.js')
        if response.status_code == 200:
            print("✅ JavaScript file accessible")
        else:
            print(f"❌ JavaScript file not accessible: {response.status_code}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Static file testing failed: {e}")
        return False

def test_database_functions():
    """Test database related functions"""
    try:
        from app import get_db_connection, get_repos_with_issues
        
        # Test database connection with temporary database
        test_db_fd, test_db_path = tempfile.mkstemp()
        
        # Create a simple test database
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY,
                repo TEXT NOT NULL,
                number INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                html_url TEXT NOT NULL,
                assignees TEXT DEFAULT '[]',
                labels TEXT DEFAULT '[]',
                mentions TEXT DEFAULT '[]',
                user_login TEXT,
                triage INTEGER DEFAULT 0,
                priority INTEGER DEFAULT -1,
                comments TEXT DEFAULT '',
                UNIQUE(repo, number)
            )
        ''')
        
        # Insert test data
        cursor.execute('''
            INSERT INTO issues (repo, number, title, body, state, created_at, updated_at, html_url, user_login)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('test/repo', 1, 'Test Issue', 'Test body', 'open', 
              '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z',
              'https://github.com/test/repo/issues/1', 'testuser'))
        
        conn.commit()
        conn.close()
        
        # Test database connection function by patching DATABASE_PATH
        import app
        original_db_path = getattr(app, 'DATABASE_PATH', None)
        app.DATABASE_PATH = test_db_path
        
        try:
            conn = get_db_connection()
            if conn:
                print("✅ Database connection function works")
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM issues')
                count = cursor.fetchone()[0]
                if count > 0:
                    print("✅ Can query database")
                else:
                    print("❌ Database query returned no results")
                    return False
                conn.close()
            else:
                print("❌ Database connection function returned None")
                return False
        finally:
            # Restore original database path
            if original_db_path:
                app.DATABASE_PATH = original_db_path
        
        # Clean up
        os.close(test_db_fd)
        os.unlink(test_db_path)
        
        print("✅ Database functions work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Database testing failed: {e}")
        return False

def test_javascript_structure():
    """Test JavaScript file structure"""
    try:
        js_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'js', 'dashboard.js')
        
        # Read with proper encoding
        try:
            with open(js_file, 'r', encoding='utf-8') as f:
                js_content = f.read()
        except UnicodeDecodeError:
            with open(js_file, 'r', encoding='latin-1') as f:
                js_content = f.read()
        
        required_functions = [
            'initializePageFromUrl',
            'setActiveRepo',
            'hideAllContent', 
            'showIntroPage',
            'activateRepoSection',
            'initializeDropdowns'
        ]
        
        missing_functions = []
        for func in required_functions:
            if f'function {func}' not in js_content:
                missing_functions.append(func)
        
        if missing_functions:
            print(f"❌ Missing JavaScript functions: {missing_functions}")
            return False
        else:
            print("✅ All required JavaScript functions present")
            return True
            
    except Exception as e:
        print(f"❌ JavaScript structure test failed: {e}")
        return False

def main():
    """Run all basic tests"""
    print("🧪 Running Basic Functionality Tests")
    print("="*50)
    
    tests = [
        ("Flask Import", test_flask_import),
        ("Basic Routes", test_basic_routes),
        ("Static Files", test_static_files),
        ("Database Functions", test_database_functions),
        ("JavaScript Structure", test_javascript_structure)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            failed += 1
    
    print("\n" + "="*50)
    print(f"📊 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All basic tests passed!")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above.")
        return False

if __name__ == '__main__':
    success = main()
    if success:
        print("\n✅ Application appears to be functioning correctly!")
    else:
        print("\n❌ Application has issues that need to be addressed.")
