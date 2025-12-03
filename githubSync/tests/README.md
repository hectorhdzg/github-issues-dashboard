# Unit Tests

This directory contains proper unit tests for the GitHub Sync Service.

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python tests/test_service.py

# Run with coverage
python -m pytest tests/ --cov=src
```

## Test Structure

- `test_service.py` - Tests for main service functionality
- Additional test files can be added as needed

## Test Guidelines

- Use proper unittest framework
- Mock external dependencies (GitHub API calls)
- Test both success and failure scenarios
- Keep tests focused and independent