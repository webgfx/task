# Tests Directory

This directory contains all official production-ready tests for the Distributed Task Management System.

## Structure

### `/unit/`
Unit tests for individual functions and classes. These tests should:
- Test isolated functionality
- Use mocking for external dependencies
- Be fast and reliable
- Have descriptive test names

### `/integration/`
Integration tests for API endpoints and component interactions. These tests should:
- Test API endpoints with various input scenarios
- Test database operations
- Test component interactions
- Include error scenario testing

### `/e2e/`
End-to-end tests for complete workflows. These tests should:
- Test complete user workflows
- Test frontend and backend integration
- Test real-world scenarios
- Include performance considerations

## Guidelines

- **All test files must be written in English** (code, comments, documentation)
- Use descriptive test names that explain what is being tested
- Include both positive and negative test cases
- Ensure tests are independent and can run in any order
- Use proper assertions and error messages
- Document complex test scenarios

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run unit tests only
python -m pytest tests/unit/

# Run integration tests only
python -m pytest tests/integration/

# Run e2e tests only
python -m pytest tests/e2e/

# Run with verbose output
python -m pytest tests/ -v
```

## Test Files

- Test files should follow the pattern: `test_*.py`
- Test classes should follow the pattern: `Test*`
- Test methods should follow the pattern: `test_*`

## Temporary Tests

❌ **Do NOT place temporary or debug tests in this folder**  
✅ **Use `ignore/temp_tests/` for temporary test scripts**
