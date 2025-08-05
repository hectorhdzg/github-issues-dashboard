"""
JavaScript Unit Tests for Dashboard Functionality
Uses jsdom to simulate browser environment for testing
"""

import unittest
import os
import sys
import subprocess
import tempfile

class TestJavaScriptWithNode(unittest.TestCase):
    """Test JavaScript functionality using Node.js and jsdom"""
    
    def setUp(self):
        """Set up Node.js test environment"""
        self.test_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.js_file = os.path.join(self.test_dir, 'static', 'js', 'dashboard.js')
        
    def test_javascript_syntax(self):
        """Test that JavaScript file has valid syntax"""
        # Read the JavaScript file with proper encoding
        try:
            with open(self.js_file, 'r', encoding='utf-8') as f:
                js_content = f.read()
            
            # Create a simple Node.js script to check syntax
            test_script = """
const fs = require('fs');

try {
    // Test syntax by creating a Function
    new Function(process.argv[2]);
    console.log('SYNTAX_OK');
} catch (error) {
    console.log('SYNTAX_ERROR:', error.message);
    process.exit(1);
}
"""
        except UnicodeDecodeError:
            # Try with different encoding
            with open(self.js_file, 'r', encoding='latin-1') as f:
                js_content = f.read()
        
        # Write test script to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(test_script)
            temp_script = f.name
        
        try:
            # Run the test script with Node.js, passing JS content as argument
            result = subprocess.run(['node', temp_script, js_content], 
                                  capture_output=True, text=True, timeout=10)
            
            self.assertEqual(result.returncode, 0, f"JavaScript syntax error: {result.stdout}")
            self.assertIn('SYNTAX_OK', result.stdout)
            
        except FileNotFoundError:
            self.skipTest("Node.js not available for JavaScript syntax testing")
        except subprocess.TimeoutExpired:
            self.fail("JavaScript syntax check timed out")
        finally:
            os.unlink(temp_script)
    
    def test_required_functions_present(self):
        """Test that required JavaScript functions are present"""
        with open(self.js_file, 'r') as f:
            js_content = f.read()
        
        required_functions = [
            'initializePageFromUrl',
            'setActiveRepo', 
            'hideAllContent',
            'showIntroPage',
            'activateRepoSection',
            'initializeDropdowns',
            'toggleDataType',
            'sortTable',
            'filterTable',
            'updateNavbarCountsFromCurrentContent',
            'updateNavbarCountsFromContent',
            'fetchStateDataFromServer',
            'fetchDataTypeFromServer',
            'updateDropdownMenusFromContent',
            'updateDropdownMenuCounts',
            'clearRepoSelection',
            'cleanupModalState',
            'openIssueModal',
            'openPullRequestModal'
        ]
        
        for func_name in required_functions:
            self.assertIn(f'function {func_name}', js_content, 
                         f"Required function '{func_name}' not found in JavaScript")

if __name__ == '__main__':
    unittest.main()
