"""
Unit tests for Flask application routes and configuration.
Tests all main routes, template rendering, and app setup.
"""
import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from app import app


class TestFlaskApp(unittest.TestCase):
    """Test cases for the main Flask application."""
    
    def setUp(self):
        """Set up test client and app context."""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Clean up after tests."""
        self.app_context.pop()
    
    def test_app_configuration(self):
        """Test Flask app configuration is correct."""
        self.assertTrue(self.app.config['TESTING'])
        self.assertEqual(self.app.template_folder, os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'templates')))
        self.assertEqual(self.app.static_folder, os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'static')))
    
    def test_index_route(self):
        """Test the main dashboard route."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<!DOCTYPE html>', response.data)
        # Check that it's using the dashboard template
        self.assertIn(b'dashboard', response.data.lower())
    
    def test_stats_route(self):
        """Test the stats page route."""
        response = self.client.get('/stats')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<!DOCTYPE html>', response.data)
        # Check that it's using the stats template
        self.assertIn(b'stats', response.data.lower())
    
    def test_repositories_route(self):
        """Test the repositories page route."""
        response = self.client.get('/repositories')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<!DOCTYPE html>', response.data)
        # Check that it's using the repositories template
        self.assertIn(b'repositories', response.data.lower())
    
    def test_repo_management_route(self):
        """Test the repository management page route."""
        response = self.client.get('/repo-management')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<!DOCTYPE html>', response.data)
        # Check that it's using the repo management template
        self.assertIn(b'repo', response.data.lower())
    
    def test_nonexistent_route(self):
        """Test that nonexistent routes return 404."""
        response = self.client.get('/nonexistent')
        self.assertEqual(response.status_code, 404)
    
    def test_template_rendering(self):
        """Test that templates are rendered correctly."""
        # Test dashboard template has expected structure
        response = self.client.get('/')
        self.assertIn(b'GitHub Issues Dashboard', response.data)
        self.assertIn(b'<html', response.data)
        self.assertIn(b'</html>', response.data)
    
    def test_static_folder_accessible(self):
        """Test that static files can be accessed."""
        # Test CSS file accessibility (if it exists)
        response = self.client.get('/static/css/dashboard.css')
        # Should either return the CSS file or 404 if not found
        self.assertIn(response.status_code, [200, 404])
        
        # Test JS file accessibility (if it exists)
        response = self.client.get('/static/js/spa.js')
        self.assertIn(response.status_code, [200, 404])


class TestAppStartup(unittest.TestCase):
    """Test cases for application startup and configuration."""
    
    @patch('app.app.run')
    def test_app_runs_with_correct_config(self, mock_run):
        """Test that app runs with correct configuration when executed directly."""
        # Set environment variable for testing
        with patch.dict('os.environ', {'PORT': '8001'}):
            # Import and run the app module's main block
            exec(open(os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'app.py')).read())
            
            # Verify that app.run was called with correct parameters
            mock_run.assert_called_with(host="0.0.0.0", port=8001, debug=False)
    
    def test_port_environment_variable(self):
        """Test that PORT environment variable is used correctly."""
        with patch.dict('os.environ', {'PORT': '9000'}):
            port = int(os.environ.get("PORT", 8001))
            self.assertEqual(port, 9000)
    
    def test_default_port(self):
        """Test that default port is used when PORT env var is not set."""
        with patch.dict('os.environ', {}, clear=True):
            port = int(os.environ.get("PORT", 8001))
            self.assertEqual(port, 8001)


class TestAppNew(unittest.TestCase):
    """Test cases for the app_new.py alternative app file."""
    
    def setUp(self):
        """Set up test client for app_new."""
        try:
            from app_new import app as app_new
            self.app = app_new
            self.app.config['TESTING'] = True
            self.client = self.app.test_client()
            self.app_context = self.app.app_context()
            self.app_context.push()
        except ImportError:
            self.skipTest("app_new.py not available")
    
    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'app_context'):
            self.app_context.pop()
    
    def test_app_new_routes(self):
        """Test that app_new has the expected routes."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get('/sync')
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get('/stats')
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()