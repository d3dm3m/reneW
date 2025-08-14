import unittest
import sys
import os

# Add the project root to the Python path to allow imports from reneW and tests
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from tests.mock_utils import setup_qgis_mocks

def run_all_tests():
    """
    A custom test runner that sets up mocks before discovering and running tests.
    """
    # 1. Set up the mocks BEFORE any code from the 'reneW' package is imported.
    print("Setting up QGIS mocks...")
    setup_qgis_mocks()
    print("Mocks configured.")

    # 2. Discover all tests in the 'tests' directory
    print("Discovering tests...")
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir='tests', pattern='test_*.py')
    print(f"Found {suite.countTestCases()} tests.")

    # 3. Run the discovered tests with a text runner.
    print("Running test suite...")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 4. Exit with a non-zero status code if any tests failed, to support CI/CD pipelines.
    if not result.wasSuccessful():
        print("Test suite failed.")
        sys.exit(1)
    else:
        print("Test suite passed successfully.")
        sys.exit(0)

if __name__ == '__main__':
    run_all_tests()
