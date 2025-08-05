#!/usr/bin/env python3
"""
Test Runner for GitHub Issues Dashboard
Runs all tests and provides detailed reporting
"""

import os
import sys
import subprocess
import unittest
from io import StringIO

def install_test_requirements():
    """Install test requirements if needed"""
    requirements_file = os.path.join(os.path.dirname(__file__), 'test_requirements.txt')
    
    try:
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install', '-r', requirements_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ Test requirements installed/verified")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Warning: Could not install test requirements: {e}")
        print("Continuing with available packages...")
        return False

def run_python_tests():
    """Run Python unit tests"""
    print("\n" + "="*60)
    print("🐍 RUNNING PYTHON TESTS")
    print("="*60)
    
    # Add current directory to Python path
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, current_dir)
    
    # Import and run the main test suite
    try:
        from tests.test_main import run_all_tests
        result = run_all_tests()
        return result.wasSuccessful()
    except Exception as e:
        print(f"❌ Error running Python tests: {e}")
        return False

def run_javascript_tests():
    """Run JavaScript tests"""
    print("\n" + "="*60)
    print("🟨 RUNNING JAVASCRIPT TESTS")
    print("="*60)
    
    try:
        from tests.test_javascript import TestJavaScriptWithNode
        suite = unittest.TestLoader().loadTestsFromTestCase(TestJavaScriptWithNode)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        return result.wasSuccessful()
    except Exception as e:
        print(f"❌ Error running JavaScript tests: {e}")
        return False

def check_code_quality():
    """Run code quality checks"""
    print("\n" + "="*60)
    print("🔍 RUNNING CODE QUALITY CHECKS")
    print("="*60)
    
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Check Python code with basic syntax validation
    python_files = []
    for root, dirs, files in os.walk(current_dir):
        # Skip test directory and virtual environment
        if 'tests' in root or '.venv' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"📝 Checking {len(python_files)} Python files...")
    
    syntax_errors = 0
    for py_file in python_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                compile(f.read(), py_file, 'exec')
        except SyntaxError as e:
            print(f"❌ Syntax error in {py_file}: {e}")
            syntax_errors += 1
        except Exception as e:
            print(f"⚠️  Warning checking {py_file}: {e}")
    
    if syntax_errors == 0:
        print("✅ All Python files have valid syntax")
        return True
    else:
        print(f"❌ Found {syntax_errors} Python syntax errors")
        return False

def run_integration_tests():
    """Run integration tests with actual Flask app"""
    print("\n" + "="*60)
    print("🔗 RUNNING INTEGRATION TESTS")
    print("="*60)
    
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, current_dir)
    
    try:
        # Import Flask app
        from app import app
        app.config['TESTING'] = True
        client = app.test_client()
        
        # Test basic routes
        routes_to_test = [
            ('/', 'GET', 200),
            ('/api/sync_status', 'GET', 200), 
            ('/static/css/dashboard.css', 'GET', 200),
            ('/static/js/dashboard.js', 'GET', 200),
        ]
        
        passed = 0
        failed = 0
        
        for route, method, expected_status in routes_to_test:
            try:
                if method == 'GET':
                    response = client.get(route)
                else:
                    response = client.post(route)
                
                if response.status_code == expected_status:
                    print(f"✅ {method} {route} -> {response.status_code}")
                    passed += 1
                else:
                    print(f"❌ {method} {route} -> {response.status_code} (expected {expected_status})")
                    failed += 1
                    
            except Exception as e:
                print(f"❌ {method} {route} -> Error: {e}")
                failed += 1
        
        print(f"\n📊 Integration test results: {passed} passed, {failed} failed")
        return failed == 0
        
    except Exception as e:
        print(f"❌ Error running integration tests: {e}")
        return False

def main():
    """Main test runner"""
    print("🧪 GitHub Issues Dashboard - Test Suite Runner")
    print("=" * 60)
    
    # Install test requirements
    install_test_requirements()
    
    # Track test results
    test_results = {
        'python_tests': False,
        'javascript_tests': False, 
        'code_quality': False,
        'integration_tests': False
    }
    
    # Run all test suites
    test_results['python_tests'] = run_python_tests()
    test_results['javascript_tests'] = run_javascript_tests()
    test_results['code_quality'] = check_code_quality()
    test_results['integration_tests'] = run_integration_tests()
    
    # Print final summary
    print("\n" + "="*60)
    print("📋 FINAL TEST SUMMARY")
    print("="*60)
    
    total_suites = len(test_results)
    passed_suites = sum(test_results.values())
    
    for suite_name, passed in test_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{suite_name.replace('_', ' ').title():<20} {status}")
    
    print(f"\n📊 Overall: {passed_suites}/{total_suites} test suites passed")
    
    if passed_suites == total_suites:
        print("\n🎉 ALL TESTS PASSED! The application is ready for use.")
        return 0
    else:
        print(f"\n⚠️  {total_suites - passed_suites} test suite(s) failed. Please fix issues before deployment.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
