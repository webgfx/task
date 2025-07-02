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

## Official Test Scenarios

### Quick Start
To run official test scenarios that verify core system functionality:

```bash
# Windows - Run all test scenarios
tests\run_tests.bat

# Windows - Run specific test scenario
tests\run_tests.bat single-subtask-single-client-now

# Linux/Mac - Run all test scenarios
python tests/run_official_tests.py

# Linux/Mac - Run specific test scenario
python tests/run_official_tests.py single-subtask-single-client-now
```

### Available Test Scenarios
- **`single-subtask-single-client-now`**: Basic task with one subtask on one client, immediate execution

### Test Scenario Documentation
See `TEST_SCENARIOS.md` for detailed documentation of all official test scenarios, including:
- Test objectives and requirements
- Step-by-step execution procedures
- Expected results and success criteria
- Failure conditions and troubleshooting

## Prerequisites for Official Tests
1. Server running on `http://localhost:5000`
2. At least one client connected and registered
3. WebSocket connections established
4. Network connectivity between server and clients

## Guidelines

- **All test files must be written in English** (code, comments, documentation)
- Use descriptive test names that explain what is being tested
- Include both positive and negative test cases
- Ensure tests are independent and can run in any order
- Use proper assertions and error messages
- Document complex test scenarios

## Running Unit/Integration Tests

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
