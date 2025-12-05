#!/usr/bin/env python3
"""
Test runner script for GitHub Issues Dashboard.
Provides convenient commands to run different types of tests.
"""
import os
import sys
import unittest
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

def discover_and_run_tests(test_dir, pattern='test_*.py', verbosity=2):
    """Discover and run tests in the specified directory."""
    loader = unittest.TestLoader()
    suite = loader.discover(test_dir, pattern=pattern)
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return result.wasSuccessful()

def run_unit_tests():
    """Run all unit tests."""
    print("🧪 Running unit tests...")
    test_dir = Path(__file__).parent / 'unit'
    return discover_and_run_tests(str(test_dir))

def run_integration_tests():
    """Run all integration tests."""
    print("🔗 Running integration tests...")
    # Set environment variable to enable integration tests
    os.environ['INTEGRATION_TESTS'] = '1'
    test_dir = Path(__file__).parent / 'integration'
    return discover_and_run_tests(str(test_dir))

def run_all_tests():
    """Run all tests (unit and integration)."""
    print("🚀 Running all tests...")
    unit_success = run_unit_tests()
    print("\n" + "="*50 + "\n")
    integration_success = run_integration_tests()
    return unit_success and integration_success

def run_specific_test(test_module):
    """Run a specific test module."""
    print(f"🎯 Running specific test: {test_module}")
    try:
        suite = unittest.TestLoader().loadTestsFromName(test_module)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        return result.wasSuccessful()
    except Exception as e:
        print(f"❌ Error running test {test_module}: {e}")
        return False

def check_test_dependencies():
    """Check if required test dependencies are available."""
    print("🔍 Checking test dependencies...")
    try:
        import requests
        print("✅ requests library available")
    except ImportError:
        print("❌ requests library not found - install with: pip install requests")
        return False
    
    # Check if Flask is available
    try:
        import flask
        print("✅ Flask library available")
    except ImportError:
        print("❌ Flask library not found - install with: pip install flask")
        return False
    
    print("✅ All test dependencies available")
    return True

def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description='GitHub Issues Dashboard Test Runner')
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--test', type=str, help='Run specific test module')
    parser.add_argument('--check-deps', action='store_true', help='Check test dependencies')
    
    args = parser.parse_args()
    
    # If no arguments provided, run all tests
    if not any(vars(args).values()):
        args.all = True
    
    success = True
    
    if args.check_deps:
        success = check_test_dependencies()
        if not success:
            sys.exit(1)
        return
    
    # Check dependencies before running tests
    if not check_test_dependencies():
        print("❌ Please install missing dependencies before running tests")
        sys.exit(1)
    
    if args.unit:
        success = run_unit_tests()
    elif args.integration:
        success = run_integration_tests()
    elif args.all:
        success = run_all_tests()
    elif args.test:
        success = run_specific_test(args.test)
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()