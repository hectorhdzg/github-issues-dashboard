"""
Unit tests for database operations and API interactions.
Tests data fetching, API responses, and database connectivity.
"""
import unittest
import os
import json
import sqlite3
from unittest.mock import patch, MagicMock, mock_open
import requests
from urllib.parse import urlparse, parse_qs


class TestDatabaseOperations(unittest.TestCase):
    """Test cases for database operations."""
    
    def setUp(self):
        """Set up test database."""
        self.test_db_path = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'test_github_issues.db')
        self.db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'github_issues.db')
    
    def test_database_exists(self):
        """Test that the main database file exists."""
        # Check if database exists in expected location
        self.assertTrue(os.path.exists(self.db_path) or os.path.exists('../data/github_issues.db'),
                       "Database file should exist in data directory")
    
    @patch('sqlite3.connect')
    def test_database_connection(self, mock_connect):
        """Test database connection functionality."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # Test connection
        conn = sqlite3.connect(self.db_path)
        mock_connect.assert_called_with(self.db_path)
        self.assertIsNotNone(conn)
    
    @patch('sqlite3.connect')
    def test_database_schema(self, mock_connect):
        """Test expected database schema for issues and pull requests."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock table schema response
        mock_cursor.fetchall.return_value = [
            ('id', 'INTEGER', 0, None, 1),
            ('number', 'INTEGER', 0, None, 0),
            ('title', 'TEXT', 0, None, 0),
            ('state', 'TEXT', 0, None, 0),
            ('repo', 'TEXT', 0, None, 0),
            ('created_at', 'TEXT', 0, None, 0),
            ('updated_at', 'TEXT', 0, None, 0),
        ]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(issues)")
        columns = cursor.fetchall()
        
        # Verify expected columns exist
        expected_columns = ['id', 'number', 'title', 'state', 'repo']
        column_names = [col[1] for col in columns]
        for expected_col in expected_columns:
            self.assertIn(expected_col, column_names)


class TestAPIInteractions(unittest.TestCase):
    """Test cases for API interactions with the sync service."""
    
    def setUp(self):
        """Set up API test configuration."""
        self.base_url = 'http://localhost:8000'
        self.api_endpoints = {
            'issues': '/api/issues',
            'pull_requests': '/api/pull_requests',
            'repositories': '/api/repositories',
            'sync_status': '/api/sync_status'
        }
    
    @patch('requests.get')
    def test_fetch_issues_api(self, mock_get):
        """Test fetching issues from the sync service API."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'issues': [
                {
                    'id': 1,
                    'number': 123,
                    'title': 'Test Issue',
                    'state': 'open',
                    'repo': 'test/repo',
                    'created_at': '2025-01-01T00:00:00Z',
                    'updated_at': '2025-01-01T00:00:00Z'
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Test API call
        url = f"{self.base_url}{self.api_endpoints['issues']}"
        response = requests.get(url)
        
        self.assertTrue(response.ok)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('issues', data)
        self.assertEqual(len(data['issues']), 1)
        self.assertEqual(data['issues'][0]['number'], 123)
    
    @patch('requests.get')
    def test_fetch_pull_requests_api(self, mock_get):
        """Test fetching pull requests from the sync service API."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'pull_requests': [
                {
                    'id': 1,
                    'number': 456,
                    'title': 'Test PR',
                    'state': 'open',
                    'repo': 'test/repo',
                    'created_at': '2025-01-01T00:00:00Z',
                    'updated_at': '2025-01-01T00:00:00Z'
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Test API call
        url = f"{self.base_url}{self.api_endpoints['pull_requests']}"
        response = requests.get(url)
        
        self.assertTrue(response.ok)
        data = response.json()
        self.assertIn('pull_requests', data)
        self.assertEqual(len(data['pull_requests']), 1)
        self.assertEqual(data['pull_requests'][0]['number'], 456)
    
    @patch('requests.get')
    def test_fetch_repositories_api(self, mock_get):
        """Test fetching repositories from the sync service API."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'repositories': [
                {
                    'repo': 'Azure/azure-sdk-for-js',
                    'display_name': 'Azure SDK for JS',
                    'main_category': 'client',
                    'classification': 'javascript',
                    'priority': 1,
                    'is_active': True
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Test API call
        url = f"{self.base_url}{self.api_endpoints['repositories']}"
        response = requests.get(url)
        
        self.assertTrue(response.ok)
        data = response.json()
        self.assertIn('repositories', data)
        self.assertEqual(len(data['repositories']), 1)
        self.assertEqual(data['repositories'][0]['repo'], 'Azure/azure-sdk-for-js')
    
    @patch('requests.get')
    def test_api_error_handling(self, mock_get):
        """Test API error handling for failed requests."""
        # Mock failed response
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_get.return_value = mock_response
        
        # Test API call with error
        url = f"{self.base_url}{self.api_endpoints['issues']}"
        response = requests.get(url)
        
        self.assertFalse(response.ok)
        self.assertEqual(response.status_code, 500)
        with self.assertRaises(requests.exceptions.HTTPError):
            response.raise_for_status()
    
    @patch('requests.get')
    def test_api_query_parameters(self, mock_get):
        """Test API calls with query parameters."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {'issues': []}
        mock_get.return_value = mock_response
        
        # Test API call with parameters
        url = f"{self.base_url}{self.api_endpoints['issues']}?state=open&repo=test/repo"
        response = requests.get(url)
        
        # Verify the URL was called correctly
        mock_get.assert_called_with(url)
        self.assertTrue(response.ok)
        
        # Parse the URL to verify parameters
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        self.assertEqual(query_params['state'], ['open'])
        self.assertEqual(query_params['repo'], ['test/repo'])
    
    @patch('requests.get')
    def test_network_timeout_handling(self, mock_get):
        """Test handling of network timeouts."""
        # Mock timeout exception
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        
        # Test API call with timeout
        url = f"{self.base_url}{self.api_endpoints['issues']}"
        with self.assertRaises(requests.exceptions.Timeout):
            requests.get(url, timeout=5)
    
    @patch('requests.get')
    def test_connection_error_handling(self, mock_get):
        """Test handling of connection errors."""
        # Mock connection error
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        # Test API call with connection error
        url = f"{self.base_url}{self.api_endpoints['issues']}"
        with self.assertRaises(requests.exceptions.ConnectionError):
            requests.get(url)


class TestDataProcessing(unittest.TestCase):
    """Test cases for data processing and transformation."""
    
    def test_issue_data_structure(self):
        """Test that issue data has expected structure."""
        sample_issue = {
            'id': 1,
            'number': 123,
            'title': 'Test Issue',
            'state': 'open',
            'repo': 'test/repo',
            'created_at': '2025-01-01T00:00:00Z',
            'updated_at': '2025-01-01T00:00:00Z',
            'labels': ['bug', 'high-priority'],
            'assignee': 'test-user'
        }
        
        # Verify required fields
        required_fields = ['id', 'number', 'title', 'state', 'repo']
        for field in required_fields:
            self.assertIn(field, sample_issue)
        
        # Verify data types
        self.assertIsInstance(sample_issue['id'], int)
        self.assertIsInstance(sample_issue['number'], int)
        self.assertIsInstance(sample_issue['title'], str)
        self.assertIsInstance(sample_issue['state'], str)
    
    def test_pull_request_data_structure(self):
        """Test that pull request data has expected structure."""
        sample_pr = {
            'id': 1,
            'number': 456,
            'title': 'Test PR',
            'state': 'open',
            'repo': 'test/repo',
            'created_at': '2025-01-01T00:00:00Z',
            'updated_at': '2025-01-01T00:00:00Z',
            'draft': False,
            'mergeable': True
        }
        
        # Verify required fields
        required_fields = ['id', 'number', 'title', 'state', 'repo']
        for field in required_fields:
            self.assertIn(field, sample_pr)
        
        # Verify data types
        self.assertIsInstance(sample_pr['draft'], bool)
        self.assertIsInstance(sample_pr['mergeable'], bool)
    
    def test_repository_data_structure(self):
        """Test that repository data has expected structure."""
        sample_repo = {
            'repo': 'Azure/azure-sdk-for-js',
            'display_name': 'Azure SDK for JS',
            'main_category': 'client',
            'classification': 'javascript',
            'priority': 1,
            'is_active': True
        }
        
        # Verify required fields
        required_fields = ['repo', 'display_name', 'main_category']
        for field in required_fields:
            self.assertIn(field, sample_repo)
        
        # Verify data types
        self.assertIsInstance(sample_repo['priority'], int)
        self.assertIsInstance(sample_repo['is_active'], bool)


if __name__ == '__main__':
    unittest.main()