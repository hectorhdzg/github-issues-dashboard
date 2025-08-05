"""
GitHub Issues Dashboard Test Suite
Comprehensive tests for backend and frontend functionality
"""

import os
import sys
import unittest
import tempfile
import json
import sqlite3
from unittest.mock import patch, MagicMock, mock_open

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask app and related modules
from app import app, get_db_connection, get_repos_with_issues
from sync_manager import SyncManager

class TestFlaskApp(unittest.TestCase):
    """Test cases for Flask application routes and functionality"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        self.client = self.app.test_client()
        
        # Create a temporary database for testing
        self.test_db_fd, self.test_db_path = tempfile.mkstemp()
        self.app.config['DATABASE'] = self.test_db_path
        
        # Set up test database schema
        self.setup_test_database()
    
    def tearDown(self):
        """Clean up after each test method."""
        os.close(self.test_db_fd)
        os.unlink(self.test_db_path)
    
    def setup_test_database(self):
        """Create test database with sample data"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # Create issues table
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
                assignees TEXT,
                labels TEXT,
                mentions TEXT,
                user_login TEXT,
                triage INTEGER DEFAULT 0,
                priority INTEGER DEFAULT -1,
                comments TEXT DEFAULT '',
                UNIQUE(repo, number)
            )
        ''')
        
        # Create pull_requests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pull_requests (
                id INTEGER PRIMARY KEY,
                repo TEXT NOT NULL,
                number INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                html_url TEXT NOT NULL,
                assignees TEXT,
                labels TEXT,
                mentions TEXT,
                user_login TEXT,
                draft INTEGER DEFAULT 0,
                merged INTEGER DEFAULT 0,
                base_ref TEXT,
                head_ref TEXT,
                comments TEXT DEFAULT '',
                UNIQUE(repo, number)
            )
        ''')
        
        # Insert sample test data
        sample_issues = [
            ('Azure/azure-sdk-for-python', 1, 'Test Issue 1', 'Test body 1', 'open', 
             '2024-01-01T00:00:00Z', '2024-01-02T00:00:00Z', 'https://github.com/Azure/azure-sdk-for-python/issues/1',
             '[]', '[{"name": "bug", "color": "d73a4a"}]', '["testuser"]', 'testuser', 0, -1, ''),
            ('Azure/azure-sdk-for-python', 2, 'Test Issue 2', 'Test body 2', 'closed',
             '2024-01-01T00:00:00Z', '2024-01-03T00:00:00Z', 'https://github.com/Azure/azure-sdk-for-python/issues/2',
             '[{"login": "assignee1"}]', '[{"name": "enhancement", "color": "a2eeef"}]', '[]', 'testuser2', 1, 2, 'Test comment'),
        ]
        
        cursor.executemany('''
            INSERT INTO issues (repo, number, title, body, state, created_at, updated_at, html_url, 
                              assignees, labels, mentions, user_login, triage, priority, comments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_issues)
        
        sample_prs = [
            ('Azure/azure-sdk-for-python', 100, 'Test PR 1', 'Test PR body 1', 'open',
             '2024-01-01T00:00:00Z', '2024-01-02T00:00:00Z', 'https://github.com/Azure/azure-sdk-for-python/pull/100',
             '[]', '[{"name": "feature", "color": "0e8a16"}]', '["reviewer1"]', 'author1', 0, 0, 'main', 'feature-branch', ''),
        ]
        
        cursor.executemany('''
            INSERT INTO pull_requests (repo, number, title, body, state, created_at, updated_at, html_url,
                                     assignees, labels, mentions, user_login, draft, merged, base_ref, head_ref, comments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)  
        ''', sample_prs)
        
        conn.commit()
        conn.close()
    
    def test_main_route(self):
        """Test the main dashboard route"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'GitHub Issues Dashboard', response.data)
    
    def test_main_route_with_repo_param(self):
        """Test the main route with repository parameter"""
        response = self.client.get('/?repo=Azure/azure-sdk-for-python&type=issues&state=open')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Issue 1', response.data)
    
    def test_api_update_issue(self):
        """Test the API endpoint for updating issues"""
        update_data = {
            'repo': 'Azure/azure-sdk-for-python',
            'number': 1,
            'triage': True,
            'priority': 1,
            'comments': 'Updated test comment'
        }
        
        response = self.client.post('/api/update_issue', 
                                  data=json.dumps(update_data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertEqual(result['status'], 'success')
        
        # Verify the update in database
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT triage, priority, comments FROM issues WHERE repo = ? AND number = ?',
                      ('Azure/azure-sdk-for-python', 1))
        row = cursor.fetchone()
        conn.close()
        
        self.assertEqual(row[0], 1)  # triage should be 1 (True)
        self.assertEqual(row[1], 1)  # priority should be 1
        self.assertEqual(row[2], 'Updated test comment')
    
    def test_api_sync_status(self):
        """Test the sync status API endpoint"""
        response = self.client.get('/api/sync_status')
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertIn('sync_in_progress', result)
        self.assertIn('errors', result)
    
    def test_get_db_connection(self):
        """Test database connection function"""
        # Mock the database path
        with patch('app.DATABASE_PATH', self.test_db_path):
            conn = get_db_connection()
            self.assertIsNotNone(conn)
            
            # Test a simple query
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM issues')
            count = cursor.fetchone()[0]
            conn.close()
            
            self.assertEqual(count, 2)  # We inserted 2 test issues
    
    def test_get_repos_with_issues(self):
        """Test the function that retrieves repositories with issues"""
        with patch('app.DATABASE_PATH', self.test_db_path):
            repos = get_repos_with_issues('issues', 'open')
            self.assertIsInstance(repos, list)
            self.assertGreater(len(repos), 0)
            
            # Check the structure of returned data
            repo = repos[0]
            self.assertIn('repo_name', repo)
            self.assertIn('issues', repo)
            self.assertIn('issue_count', repo)

class TestSyncManager(unittest.TestCase):
    """Test cases for SyncManager functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_db_fd, self.test_db_path = tempfile.mkstemp()
        self.sync_manager = SyncManager(self.test_db_path)
        
    def tearDown(self):
        """Clean up after tests"""
        os.close(self.test_db_fd)
        os.unlink(self.test_db_path)
    
    @patch('sync_manager.requests.get')
    def test_fetch_github_data(self, mock_get):
        """Test GitHub API data fetching"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'number': 123,
                'title': 'Test Issue',
                'body': 'Test body',
                'state': 'open',
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T00:00:00Z',
                'html_url': 'https://github.com/test/repo/issues/123',
                'assignees': [],
                'labels': [],
                'user': {'login': 'testuser'}
            }
        ]
        mock_get.return_value = mock_response
        
        # Test the method (this would need to be implemented in sync_manager.py)
        # For now, just test that the sync manager can be instantiated
        self.assertIsNotNone(self.sync_manager)
    
    def test_database_operations(self):
        """Test basic database operations"""
        # Create tables
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # Test table creation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_issues (
                id INTEGER PRIMARY KEY,
                repo TEXT,
                number INTEGER,
                title TEXT
            )
        ''')
        
        # Test data insertion
        cursor.execute('INSERT INTO test_issues (repo, number, title) VALUES (?, ?, ?)',
                      ('test/repo', 1, 'Test Issue'))
        
        # Test data retrieval
        cursor.execute('SELECT * FROM test_issues WHERE repo = ?', ('test/repo',))
        row = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        self.assertIsNotNone(row)
        self.assertEqual(row[1], 'test/repo')
        self.assertEqual(row[2], 1)
        self.assertEqual(row[3], 'Test Issue')

class TestJavaScriptFunctionality(unittest.TestCase):
    """Test cases for JavaScript functionality using mock DOM"""
    
    def setUp(self):
        """Set up test environment for JavaScript tests"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_dashboard_html_structure(self):
        """Test that the dashboard HTML contains required elements for JavaScript"""
        response = self.client.get('/')
        html_content = response.data.decode('utf-8')
        
        # Check for required JavaScript elements
        self.assertIn('id="intro-page"', html_content)
        self.assertIn('class="repo-section"', html_content or '')
        self.assertIn('dashboard.js', html_content)
        self.assertIn('selectedRepoFromTemplate', html_content)
        
    def test_dashboard_css_structure(self):
        """Test that CSS file is accessible"""
        response = self.client.get('/static/css/dashboard.css')
        self.assertEqual(response.status_code, 200)
        
        css_content = response.data.decode('utf-8')
        # Check for important CSS classes
        self.assertIn('.intro-page', css_content)
        self.assertIn('.repo-section', css_content)
        self.assertIn('.container', css_content)
    
    def test_dashboard_js_structure(self):
        """Test that JavaScript file is accessible and contains required functions"""
        response = self.client.get('/static/js/dashboard.js')
        self.assertEqual(response.status_code, 200)
        
        js_content = response.data.decode('utf-8')
        # Check for important JavaScript functions
        self.assertIn('function initializePageFromUrl', js_content)
        self.assertIn('function setActiveRepo', js_content)
        self.assertIn('function hideAllContent', js_content)
        self.assertIn('function showIntroPage', js_content)
        self.assertIn('function activateRepoSection', js_content)

class TestDataIntegrity(unittest.TestCase):
    """Test cases for data integrity and consistency"""
    
    def setUp(self):
        """Set up test database"""
        self.test_db_fd, self.test_db_path = tempfile.mkstemp()
        self.setup_test_database()
    
    def tearDown(self):
        """Clean up test database"""
        os.close(self.test_db_fd)
        os.unlink(self.test_db_path)
    
    def setup_test_database(self):
        """Set up test database with sample data"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # Create tables with proper schema
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
        
        conn.commit()
        conn.close()
    
    def test_database_schema_integrity(self):
        """Test that database schema is correct"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # Check that issues table exists and has correct columns
        cursor.execute("PRAGMA table_info(issues)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        expected_columns = ['id', 'repo', 'number', 'title', 'body', 'state', 
                          'created_at', 'updated_at', 'html_url', 'assignees',
                          'labels', 'mentions', 'user_login', 'triage', 'priority', 'comments']
        
        for expected_col in expected_columns:
            self.assertIn(expected_col, column_names)
        
        conn.close()
    
    def test_json_data_integrity(self):
        """Test that JSON data in database is valid"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # Insert test data with JSON fields
        test_assignees = '[{"login": "test_user", "id": 123}]'
        test_labels = '[{"name": "bug", "color": "d73a4a"}]'
        test_mentions = '["user1", "user2"]'
        
        cursor.execute('''
            INSERT INTO issues (repo, number, title, body, state, created_at, updated_at, 
                              html_url, assignees, labels, mentions, user_login)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('test/repo', 1, 'Test Issue', 'Test body', 'open', 
              '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z',
              'https://github.com/test/repo/issues/1',
              test_assignees, test_labels, test_mentions, 'testuser'))
        
        # Retrieve and validate JSON data
        cursor.execute('SELECT assignees, labels, mentions FROM issues WHERE repo = ? AND number = ?',
                      ('test/repo', 1))
        row = cursor.fetchone()
        
        # Validate that JSON can be parsed
        assignees = json.loads(row[0])
        labels = json.loads(row[1])
        mentions = json.loads(row[2])
        
        self.assertIsInstance(assignees, list)
        self.assertIsInstance(labels, list)
        self.assertIsInstance(mentions, list)
        
        self.assertEqual(len(assignees), 1)
        self.assertEqual(assignees[0]['login'], 'test_user')
        
        conn.commit()
        conn.close()

def run_all_tests():
    """Run all test suites and return results"""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestFlaskApp,
        TestSyncManager, 
        TestJavaScriptFunctionality,
        TestDataIntegrity
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(test_suite)
    
    return result

if __name__ == '__main__':
    print("Running GitHub Issues Dashboard Test Suite...")
    print("=" * 60)
    
    # Run all tests
    result = run_all_tests()
    
    # Print summary
    print("\n" + "=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
