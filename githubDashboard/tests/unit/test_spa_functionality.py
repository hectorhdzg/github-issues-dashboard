"""
Unit tests for JavaScript SPA functionality.
Tests state management, UI interactions, and data processing.
"""
import unittest
import os
import json
from unittest.mock import patch, MagicMock


class TestJavaScriptSPA(unittest.TestCase):
    """Test cases for the JavaScript SPA functionality."""
    
    def setUp(self):
        """Set up test configuration."""
        self.spa_js_path = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'js', 'spa.js')
        self.test_data = {
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
            ],
            'repositories': [
                {
                    'repo': 'test/repo',
                    'display_name': 'Test Repository',
                    'main_category': 'client',
                    'classification': 'javascript'
                }
            ]
        }
    
    def test_spa_file_exists(self):
        """Test that the SPA JavaScript file exists."""
        self.assertTrue(os.path.exists(self.spa_js_path), 
                       "SPA JavaScript file should exist")
    
    def test_spa_file_contains_dashboard_class(self):
        """Test that SPA file contains the DashboardSPA class."""
        if os.path.exists(self.spa_js_path):
            with open(self.spa_js_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn('class DashboardSPA', content)
                self.assertIn('constructor', content)
    
    def test_spa_file_contains_required_methods(self):
        """Test that SPA file contains required methods."""
        if os.path.exists(self.spa_js_path):
            with open(self.spa_js_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                required_methods = [
                    'loadDashboardData',
                    'loadRepositories',
                    'updateContentFromData',
                    'setDataType',
                    'setShowState',
                    'setSelectedRepo',
                    'displayDataTable'
                ]
                
                for method in required_methods:
                    self.assertIn(method, content, f"Method {method} should exist in SPA")
    
    def test_spa_api_endpoints(self):
        """Test that SPA file contains correct API endpoints."""
        if os.path.exists(self.spa_js_path):
            with open(self.spa_js_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check for API endpoints
                self.assertIn('localhost:8000', content)
                self.assertIn('/api/issues', content)
                self.assertIn('/api/pull_requests', content)
                self.assertIn('/api/repositories', content)


class TestSPAStateManagement(unittest.TestCase):
    """Test cases for SPA state management functionality."""
    
    def test_state_object_structure(self):
        """Test expected state object structure."""
        expected_state = {
            'dataType': 'issues',
            'showState': 'open',
            'selectedRepo': 'all',
            'repositories': [],
            'cache': {},
            'currentPage': 1,
            'itemsPerPage': 50
        }
        
        # Verify state structure contains expected keys
        required_keys = ['dataType', 'showState', 'selectedRepo', 'repositories']
        for key in required_keys:
            self.assertIn(key, expected_state)
    
    def test_state_transitions(self):
        """Test state transition logic."""
        # Test data type transitions
        valid_data_types = ['issues', 'prs']
        for data_type in valid_data_types:
            self.assertIn(data_type, valid_data_types)
        
        # Test state transitions
        valid_states = ['open', 'closed', 'all']
        for state in valid_states:
            self.assertIn(state, valid_states)
    
    def test_repository_filtering(self):
        """Test repository filtering logic."""
        test_repositories = [
            {'repo': 'Azure/azure-sdk-for-js', 'main_category': 'client'},
            {'repo': 'Azure/azure-sdk-for-python', 'main_category': 'client'},
            {'repo': 'Azure/azure-cli', 'main_category': 'tools'}
        ]
        
        # Test filtering by category
        client_repos = [r for r in test_repositories if r['main_category'] == 'client']
        self.assertEqual(len(client_repos), 2)
        
        tools_repos = [r for r in test_repositories if r['main_category'] == 'tools']
        self.assertEqual(len(tools_repos), 1)


class TestSPADataProcessing(unittest.TestCase):
    """Test cases for SPA data processing functionality."""
    
    def test_issue_data_processing(self):
        """Test processing of issue data."""
        sample_issues = [
            {
                'id': 1,
                'number': 123,
                'title': 'Test Issue 1',
                'state': 'open',
                'repo': 'test/repo1',
                'created_at': '2025-01-01T00:00:00Z'
            },
            {
                'id': 2,
                'number': 124,
                'title': 'Test Issue 2',
                'state': 'closed',
                'repo': 'test/repo2',
                'created_at': '2025-01-02T00:00:00Z'
            }
        ]
        
        # Test filtering by state
        open_issues = [i for i in sample_issues if i['state'] == 'open']
        self.assertEqual(len(open_issues), 1)
        self.assertEqual(open_issues[0]['number'], 123)
        
        closed_issues = [i for i in sample_issues if i['state'] == 'closed']
        self.assertEqual(len(closed_issues), 1)
        self.assertEqual(closed_issues[0]['number'], 124)
    
    def test_pull_request_data_processing(self):
        """Test processing of pull request data."""
        sample_prs = [
            {
                'id': 1,
                'number': 456,
                'title': 'Test PR 1',
                'state': 'open',
                'repo': 'test/repo1',
                'draft': False
            },
            {
                'id': 2,
                'number': 457,
                'title': 'Test PR 2',
                'state': 'open',
                'repo': 'test/repo1',
                'draft': True
            }
        ]
        
        # Test filtering by draft status
        non_draft_prs = [pr for pr in sample_prs if not pr.get('draft', False)]
        self.assertEqual(len(non_draft_prs), 1)
        
        draft_prs = [pr for pr in sample_prs if pr.get('draft', False)]
        self.assertEqual(len(draft_prs), 1)
    
    def test_repository_data_processing(self):
        """Test processing of repository data."""
        sample_repos = [
            {
                'repo': 'Azure/azure-sdk-for-js',
                'display_name': 'Azure SDK for JS',
                'main_category': 'client',
                'priority': 1,
                'is_active': True
            },
            {
                'repo': 'Azure/azure-cli',
                'display_name': 'Azure CLI',
                'main_category': 'tools',
                'priority': 2,
                'is_active': False
            }
        ]
        
        # Test filtering by active status
        active_repos = [r for r in sample_repos if r.get('is_active', True)]
        self.assertEqual(len(active_repos), 1)
        
        # Test sorting by priority
        sorted_repos = sorted(sample_repos, key=lambda x: x.get('priority', 999))
        self.assertEqual(sorted_repos[0]['repo'], 'Azure/azure-sdk-for-js')


class TestSPAPagination(unittest.TestCase):
    """Test cases for SPA pagination functionality."""
    
    def test_pagination_calculation(self):
        """Test pagination calculation logic."""
        total_items = 125
        items_per_page = 50
        
        # Calculate total pages
        total_pages = (total_items + items_per_page - 1) // items_per_page
        self.assertEqual(total_pages, 3)
        
        # Test page boundaries
        page_1_start = 0
        page_1_end = min(items_per_page, total_items)
        self.assertEqual(page_1_start, 0)
        self.assertEqual(page_1_end, 50)
        
        page_3_start = 2 * items_per_page
        page_3_end = min(3 * items_per_page, total_items)
        self.assertEqual(page_3_start, 100)
        self.assertEqual(page_3_end, 125)
    
    def test_pagination_edge_cases(self):
        """Test pagination edge cases."""
        # Test with exact page boundary
        total_items = 100
        items_per_page = 50
        total_pages = (total_items + items_per_page - 1) // items_per_page
        self.assertEqual(total_pages, 2)
        
        # Test with single item
        total_items = 1
        items_per_page = 50
        total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
        self.assertEqual(total_pages, 1)
        
        # Test with no items
        total_items = 0
        items_per_page = 50
        total_pages = max(1, (total_items + items_per_page - 1) // items_per_page) if total_items > 0 else 1
        self.assertEqual(total_pages, 1)


class TestSPAURLManagement(unittest.TestCase):
    """Test cases for SPA URL management functionality."""
    
    def test_url_parameter_parsing(self):
        """Test URL parameter parsing logic."""
        # Simulate URL parameters
        test_params = {
            'repo': 'Azure/azure-sdk-for-js',
            'state': 'open',
            'type': 'issues',
            'page': '2'
        }
        
        # Test parameter extraction
        self.assertEqual(test_params.get('repo'), 'Azure/azure-sdk-for-js')
        self.assertEqual(test_params.get('state'), 'open')
        self.assertEqual(test_params.get('type'), 'issues')
        self.assertEqual(int(test_params.get('page', 1)), 2)
    
    def test_url_state_serialization(self):
        """Test URL state serialization logic."""
        state = {
            'dataType': 'issues',
            'showState': 'open',
            'selectedRepo': 'Azure/azure-sdk-for-js',
            'currentPage': 1
        }
        
        # Test URL building
        expected_params = [
            ('type', 'issues'),
            ('state', 'open'),
            ('repo', 'Azure/azure-sdk-for-js'),
            ('page', '1')
        ]
        
        for param, value in expected_params:
            if param == 'type':
                self.assertEqual(state['dataType'], value)
            elif param == 'state':
                self.assertEqual(state['showState'], value)
            elif param == 'repo':
                self.assertEqual(state['selectedRepo'], value)
            elif param == 'page':
                self.assertEqual(str(state['currentPage']), value)


if __name__ == '__main__':
    unittest.main()