"""
Test configuration and utilities for GitHub Issues Dashboard tests.
"""
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Test configuration constants
TEST_CONFIG = {
    'DASHBOARD_URL': 'http://localhost:8001',
    'SYNC_SERVICE_URL': 'http://localhost:8000',
    'TEST_TIMEOUT': 10,
    'TEST_DATABASE_PATH': ':memory:',  # Use in-memory database for tests
}

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / 'src'
FIXTURES_DIR = PROJECT_ROOT / 'tests' / 'fixtures'


def load_test_data():
    """Load test data from fixtures."""
    test_data_path = FIXTURES_DIR / 'test_data.json'
    if test_data_path.exists():
        with open(test_data_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def create_mock_response(data, status_code=200, ok=True):
    """Create a mock response object for testing API calls."""
    mock_response = MagicMock()
    mock_response.ok = ok
    mock_response.status_code = status_code
    mock_response.json.return_value = data
    mock_response.text = json.dumps(data) if isinstance(data, dict) else str(data)
    mock_response.content = mock_response.text.encode('utf-8')
    return mock_response


def create_test_app():
    """Create a test Flask application."""
    import sys
    sys.path.insert(0, str(SRC_DIR))
    
    from app import app
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app


class TestDataHelper:
    """Helper class for managing test data."""
    
    def __init__(self):
        self.test_data = load_test_data()
    
    def get_test_repositories(self):
        """Get test repositories data."""
        return self.test_data.get('test_repositories', [])
    
    def get_test_issues(self):
        """Get test issues data."""
        return self.test_data.get('test_issues', [])
    
    def get_test_pull_requests(self):
        """Get test pull requests data."""
        return self.test_data.get('test_pull_requests', [])
    
    def get_test_sync_status(self):
        """Get test sync status data."""
        return self.test_data.get('test_sync_status', {})
    
    def filter_by_repo(self, items, repo_name):
        """Filter items by repository name."""
        return [item for item in items if item.get('repo') == repo_name]
    
    def filter_by_state(self, items, state):
        """Filter items by state."""
        return [item for item in items if item.get('state') == state]


# Environment setup for tests
def setup_test_environment():
    """Set up test environment variables."""
    os.environ.update({
        'FLASK_ENV': 'testing',
        'PORT': '8001',
        'SYNC_SERVICE_URL': TEST_CONFIG['SYNC_SERVICE_URL'],
        'DATABASE_PATH': TEST_CONFIG['TEST_DATABASE_PATH'],
    })


def cleanup_test_environment():
    """Clean up test environment."""
    test_env_vars = ['FLASK_ENV', 'INTEGRATION_TESTS']
    for var in test_env_vars:
        if var in os.environ:
            del os.environ[var]


# Mock API responses
class MockAPIResponses:
    """Collection of mock API responses for testing."""
    
    @staticmethod
    def repositories_success():
        """Mock successful repositories API response."""
        test_helper = TestDataHelper()
        return create_mock_response({
            'repositories': test_helper.get_test_repositories()
        })
    
    @staticmethod
    def issues_success():
        """Mock successful issues API response."""
        test_helper = TestDataHelper()
        return create_mock_response({
            'issues': test_helper.get_test_issues()
        })
    
    @staticmethod
    def pull_requests_success():
        """Mock successful pull requests API response."""
        test_helper = TestDataHelper()
        return create_mock_response({
            'pull_requests': test_helper.get_test_pull_requests()
        })
    
    @staticmethod
    def api_error():
        """Mock API error response."""
        return create_mock_response(
            {'error': 'Internal server error'}, 
            status_code=500, 
            ok=False
        )
    
    @staticmethod
    def api_not_found():
        """Mock API not found response."""
        return create_mock_response(
            {'error': 'Not found'}, 
            status_code=404, 
            ok=False
        )


# Test decorators
def requires_integration():
    """Decorator to mark tests that require integration environment."""
    import unittest
    return unittest.skipUnless(
        os.environ.get('INTEGRATION_TESTS'), 
        "Integration tests require INTEGRATION_TESTS env var"
    )


def requires_api():
    """Decorator to mark tests that require API connectivity."""
    import unittest
    return unittest.skipUnless(
        os.environ.get('API_TESTS'), 
        "API tests require API_TESTS env var"
    )


# Test utilities
def assert_valid_html(html_content):
    """Assert that HTML content is valid."""
    assert '<!DOCTYPE html>' in html_content or '<html' in html_content
    assert '</html>' in html_content


def assert_valid_json_response(response_data):
    """Assert that response data is valid JSON structure."""
    assert isinstance(response_data, dict)
    # Add more JSON structure validation as needed


def get_test_file_path(filename):
    """Get full path to a test file in fixtures directory."""
    return FIXTURES_DIR / filename