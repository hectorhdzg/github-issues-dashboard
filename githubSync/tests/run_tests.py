#!/usr/bin/env python3
"""
Test runner for GitHub Sync Service
Run all tests with proper setup and reporting
"""

import sys
import os
import unittest

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

def run_tests():
    """Run all tests and report results"""
    print("🧪 Running GitHub Sync Service Tests...")
    print("=" * 50)
    
    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(__file__)
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 50)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED!")
        return 0
    else:
        print(f"❌ TESTS FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
        return 1

if __name__ == '__main__':
    exit_code = run_tests()
    sys.exit(exit_code)