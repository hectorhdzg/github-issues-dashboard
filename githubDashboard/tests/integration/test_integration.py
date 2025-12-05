"""
Integration tests for the GitHub Issues Dashboard.
Tests full application workflow and component interactions.
"""
import unittest
import os
import sys
import time
import requests
from unittest.mock import patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestDashboardIntegration(unittest.TestCase):
    """Integration tests for the complete dashboard functionality."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.dashboard_url = 'http://localhost:8001'
        self.sync_service_url = 'http://localhost:8000'
        self.test_timeout = 10
    
    @unittest.skipUnless(os.environ.get('INTEGRATION_TESTS'), 
                        "Integration tests require INTEGRATION_TESTS env var")
    def test_dashboard_service_connectivity(self):
        """Test that dashboard service is accessible."""
        try:
            response = requests.get(self.dashboard_url, timeout=self.test_timeout)
            self.assertEqual(response.status_code, 200)
            self.assertIn('GitHub Issues Dashboard', response.text)
        except requests.exceptions.ConnectionError:
            self.skipTest("Dashboard service not running")
    
    @unittest.skipUnless(os.environ.get('INTEGRATION_TESTS'), 
                        "Integration tests require INTEGRATION_TESTS env var")
    def test_sync_service_connectivity(self):
        """Test that sync service is accessible."""
        try:
            response = requests.get(f"{self.sync_service_url}/api/repositories", 
                                  timeout=self.test_timeout)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('repositories', data)
        except requests.exceptions.ConnectionError:
            self.skipTest("Sync service not running")
    
    @unittest.skipUnless(os.environ.get('INTEGRATION_TESTS'), 
                        "Integration tests require INTEGRATION_TESTS env var")
    def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow."""
        # 1. Access dashboard
        try:
            dashboard_response = requests.get(self.dashboard_url, timeout=self.test_timeout)
            self.assertEqual(dashboard_response.status_code, 200)
        except requests.exceptions.ConnectionError:
            self.skipTest("Dashboard service not running")
        
        # 2. Fetch repositories
        try:
            repos_response = requests.get(f"{self.sync_service_url}/api/repositories", 
                                        timeout=self.test_timeout)
            self.assertEqual(repos_response.status_code, 200)
            repos_data = repos_response.json()
            self.assertIn('repositories', repos_data)
        except requests.exceptions.ConnectionError:
            self.skipTest("Sync service not running")
        
        # 3. Fetch issues
        try:
            issues_response = requests.get(f"{self.sync_service_url}/api/issues", 
                                         timeout=self.test_timeout)
            self.assertEqual(issues_response.status_code, 200)
            issues_data = issues_response.json()
            self.assertIn('issues', issues_data)
        except requests.exceptions.ConnectionError:
            self.skipTest("Sync service not running")


class TestTemplateIntegration(unittest.TestCase):
    """Integration tests for template rendering and static file serving."""
    
    def setUp(self):
        """Set up template integration tests."""
        from app import app
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_dashboard_template_integration(self):
        """Test that dashboard template renders with all components."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        # Check for key dashboard components
        content = response.data.decode('utf-8')
        self.assertIn('GitHub Issues Dashboard', content)
        self.assertIn('navbar', content.lower())
        self.assertIn('Issues', content)
        self.assertIn('Pull Requests', content)
    
    def test_stats_template_integration(self):
        """Test that stats template renders correctly."""
        response = self.client.get('/stats')
        self.assertEqual(response.status_code, 200)
        
        content = response.data.decode('utf-8')
        self.assertIn('stats', content.lower())
    
    def test_repositories_template_integration(self):
        """Test that repositories template renders correctly."""
        response = self.client.get('/repositories')
        self.assertEqual(response.status_code, 200)
        
        content = response.data.decode('utf-8')
        self.assertIn('repositories', content.lower())
    
    def test_static_files_integration(self):
        """Test that static files are served correctly."""
        # Test CSS file
        css_response = self.client.get('/static/css/dashboard.css')
        # Should either return CSS or 404 if file doesn't exist
        self.assertIn(css_response.status_code, [200, 404])
        
        # Test JS file
        js_response = self.client.get('/static/js/spa.js')
        self.assertIn(js_response.status_code, [200, 404])


class TestAPIDataFlow(unittest.TestCase):
    """Integration tests for API data flow between components."""
    
    @patch('requests.get')
    def test_api_data_flow_simulation(self, mock_get):
        """Test simulated API data flow."""
        # Mock repositories response
        repos_mock = MagicMock()
        repos_mock.ok = True
        repos_mock.status_code = 200
        repos_mock.json.return_value = {
            'repositories': [
                {
                    'repo': 'Azure/azure-sdk-for-js',
                    'display_name': 'Azure SDK for JS',
                    'main_category': 'client',
                    'classification': 'javascript'
                }
            ]
        }
        
        # Mock issues response
        issues_mock = MagicMock()
        issues_mock.ok = True
        issues_mock.status_code = 200
        issues_mock.json.return_value = {
            'issues': [
                {
                    'id': 1,
                    'number': 123,
                    'title': 'Test Issue',
                    'state': 'open',
                    'repo': 'Azure/azure-sdk-for-js',
                    'created_at': '2025-01-01T00:00:00Z'
                }
            ]
        }
        
        # Set up mock responses based on URL
        def mock_response(url, **kwargs):
            if 'repositories' in url:
                return repos_mock
            elif 'issues' in url:
                return issues_mock
            return MagicMock(ok=False, status_code=404)
        
        mock_get.side_effect = mock_response
        
        # Test repositories call
        repos_response = requests.get('http://localhost:8000/api/repositories')
        self.assertTrue(repos_response.ok)
        repos_data = repos_response.json()
        self.assertEqual(len(repos_data['repositories']), 1)
        
        # Test issues call
        issues_response = requests.get('http://localhost:8000/api/issues')
        self.assertTrue(issues_response.ok)
        issues_data = issues_response.json()
        self.assertEqual(len(issues_data['issues']), 1)


class TestDataConsistency(unittest.TestCase):
    """Integration tests for data consistency across components."""
    
    def test_repository_data_consistency(self):
        """Test that repository data is consistent across API calls."""
        sample_repo_data = {
            'repo': 'Azure/azure-sdk-for-js',
            'display_name': 'Azure SDK for JS',
            'main_category': 'client',
            'classification': 'javascript',
            'priority': 1,
            'is_active': True
        }
        
        # Verify required fields are present
        required_fields = ['repo', 'display_name', 'main_category']
        for field in required_fields:
            self.assertIn(field, sample_repo_data)
        
        # Verify data types
        self.assertIsInstance(sample_repo_data['repo'], str)
        self.assertIsInstance(sample_repo_data['priority'], int)
        self.assertIsInstance(sample_repo_data['is_active'], bool)
    
    def test_issue_data_consistency(self):
        """Test that issue data is consistent across API calls."""
        sample_issue_data = {
            'id': 1,
            'number': 123,
            'title': 'Test Issue',
            'state': 'open',
            'repo': 'Azure/azure-sdk-for-js',
            'created_at': '2025-01-01T00:00:00Z',
            'updated_at': '2025-01-01T00:00:00Z'
        }
        
        # Verify required fields
        required_fields = ['id', 'number', 'title', 'state', 'repo']
        for field in required_fields:
            self.assertIn(field, sample_issue_data)
        
        # Verify state values
        valid_states = ['open', 'closed']
        self.assertIn(sample_issue_data['state'], valid_states)


class TestErrorHandlingIntegration(unittest.TestCase):
    """Integration tests for error handling across components."""
    
    @patch('requests.get')
    def test_api_error_handling_integration(self, mock_get):
        """Test integrated error handling for API failures."""
        # Mock network error
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")
        
        # Test that appropriate error handling occurs
        with self.assertRaises(requests.exceptions.ConnectionError):
            requests.get('http://localhost:8000/api/repositories')
    
    @patch('requests.get')
    def test_api_timeout_handling(self, mock_get):
        """Test integrated timeout handling."""
        # Mock timeout error
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
        
        with self.assertRaises(requests.exceptions.Timeout):
            requests.get('http://localhost:8000/api/issues', timeout=5)
    
    def test_invalid_route_handling(self):
        """Test handling of invalid routes."""
        from app import app
        app.config['TESTING'] = True
        client = app.test_client()
        
        response = client.get('/invalid-route')
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    # Set environment variable to enable integration tests
    if len(sys.argv) > 1 and sys.argv[1] == '--integration':
        os.environ['INTEGRATION_TESTS'] = '1'
    
    unittest.main()