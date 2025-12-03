"""
Unit tests for GitHub Sync Service
"""

import unittest
import sys
import os
import tempfile
import sqlite3

# Add src to path so we can import app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class TestGitHubSyncService(unittest.TestCase):
    """Test cases for GitHubSyncService"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Import here to avoid circular imports during test discovery
        from app import app, GitHubSyncService
        
        self.app = app
        self.client = app.test_client()
        app.config['TESTING'] = True
        
        # Create a temporary database for testing
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db_path = self.test_db.name
        self.test_db.close()
        
        # Initialize test database with basic schema
        self._setup_test_database()
    
    def tearDown(self):
        """Clean up test fixtures"""
        try:
            os.unlink(self.test_db_path)
        except:
            pass
    
    def _setup_test_database(self):
        """Set up test database with basic schema"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # Create basic tables for testing
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                repository TEXT NOT NULL,
                sync_type TEXT NOT NULL,
                status TEXT NOT NULL,
                total_processed INTEGER DEFAULT 0,
                new_records INTEGER DEFAULT 0,
                updated_records INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                owner TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def test_health_check(self):
        """Test that the service endpoints respond"""
        # Test statistics endpoint (should work even with empty DB)
        response = self.client.get('/api/statistics')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('total_issues', data)
        self.assertIn('total_prs', data)
    
    def test_scheduler_status(self):
        """Test scheduler status endpoint"""
        response = self.client.get('/api/scheduler/status')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('running', data)
        self.assertIn('enabled', data)
        # The actual API returns 'interval' not 'interval_hours'
        self.assertTrue('interval' in data or 'interval_hours' in data)
    
    def test_sync_history_endpoint(self):
        """Test sync history endpoint"""
        response = self.client.get('/api/sync/history')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        # API returns object with 'sync_history' key containing the list
        if 'sync_history' in data:
            self.assertIsInstance(data['sync_history'], list)
        else:
            self.assertIsInstance(data, list)
    
    def test_repositories_endpoint(self):
        """Test repositories endpoint"""
        response = self.client.get('/api/repositories')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        # API returns object with 'repositories' key containing the list
        if 'repositories' in data:
            self.assertIsInstance(data['repositories'], list)
        else:
            self.assertIsInstance(data, list)

if __name__ == '__main__':
    unittest.main()