# GitHub Copilot Instructions for Distributed Task Management System

## Project Overview

This is a distributed task management and execution system built with Flask and SQLite, supporting web interface management, multi-client distributed execution, and real-time monitoring.

### Key Features
- 🌐 **Web Interface Management** - Intuitive task and client management interface
- 🔄 **Multi-client Distributed Execution** - Tasks can be distributed across multiple client clients
- 📊 **Real-time Monitoring** - WebSocket-based real-time status updates
- 📋 **Subtask Support** - Complex tasks can be broken down into subtasks
- 🕐 **Flexible Scheduling** - Support for immediate execution, scheduled execution, and cron expressions
- 🔐 **Client Name Based Identity** - Uses client names as unique identifiers instead of IP addresses

## Architecture

### Server Components (`server/`)
- **`app.py`** - Flask main application with SocketIO support
- **`api.py`** - REST API endpoints for task and client management
- **`database.py`** - SQLite database operations and client management
- **`scheduler.py`** - Task scheduling and execution coordination
- **`templates/`** - HTML templates for web interface
- **`static/`** - CSS and JavaScript files for frontend

### Client Components (`client/`)
- **`client.py`** - Main client application
- **`client_runner.py`** - Client execution engine
- **`service.py`** - Windows service implementation
- **`executor.py`** - Task execution logic
- **`subtask_executor.py`** - Subtask execution handling
- **`heartbeat.py`** - Client health monitoring

### Common Components (`common/`)
- **`models.py`** - Data models (Task, Client, SubtaskDefinition)
- **`config.py`** - Configuration management
- **`subtasks.py`** - Predefined subtask definitions
- **`utils.py`** - Utility functions

## File Organization and Structure

### Project Structure
```
project/
├── .github/                    # GitHub configuration
│   └── copilot-instructions.md
├── client/                     # Client components
├── common/                     # Shared components
├── server/                     # Server components
├── tests/                      # Official tests and test suites
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end tests
└── ignore/                     # Intermediate tests and temporary files
    ├── temp_tests/             # Temporary test scripts
    ├── debug_scripts/          # Debug and verification scripts
    └── temp_docs/              # Temporary markdown files
```

### File Organization Rules
- **Official Tests**: All production-ready tests must be placed in the `tests/` folder
  - Unit tests go in `tests/unit/`
  - Integration tests go in `tests/integration/`
  - End-to-end tests go in `tests/e2e/`
- **Intermediate Files**: All temporary tests, debug scripts, and intermediate markdown files must be placed in the `ignore/` folder
  - Temporary test scripts: `ignore/temp_tests/`
  - Debug and verification scripts: `ignore/debug_scripts/`
  - Temporary documentation: `ignore/temp_docs/`
- **Version Control**: The `ignore/` folder should be added to `.gitignore` to prevent temporary files from being committed

## Coding Guidelines

### Python Style
- Follow PEP 8 conventions
- **All code and comments must be written in English**
- Use type hints where appropriate
- Include comprehensive docstrings for functions and classes
- Use `logging` module for all logging instead of `print()`
- Handle exceptions gracefully with appropriate error messages

### Database Design
- **Client Identity**: Use `client_name` as primary identifier, NOT IP addresses
- **Unique Constraints**: Client names must be unique across the system
- **Foreign Keys**: Use client names for referencing clients in tasks
- **Data Models**: Always use the models from `common/models.py`

### Frontend Development
- Use vanilla JavaScript (no frameworks required)
- **All JavaScript code and comments must be written in English**
- Implement null safety checks for DOM operations
- Use WebSocket for real-time updates
- Follow Bootstrap-like CSS patterns for consistency
- Always validate form inputs client-side and server-side

### API Design
- RESTful endpoints under `/api/` prefix
- **All API documentation and comments must be written in English**
- Return consistent JSON responses with proper HTTP status codes
- Include error handling with meaningful error messages
- Use Flask-SocketIO for real-time communication
- Validate all input parameters

## Key Design Patterns

### Client Management
```python
# Always use client name as identifier
client = database.get_client_by_name(client_name)
if not client:
    # Handle client not found
    
# Use the Client model methods
unique_id = client.get_unique_id()  # Returns client.name
is_same = client.is_same_client(other_client)
```

### Task Creation with Subtasks
```python
# Tasks should include subtask definitions
task_data = {
    'name': 'Task Name',
    'subtasks': [
        {
            'name': 'subtask_type',
            'description': 'Human readable description',
            'order': 0
        }
    ],
    'clients': ['client1', 'client2']  # Use client names
}
```

### Error Handling
```python
try:
    # Operation
    result = some_operation()
    return {'success': True, 'data': result}
except Exception as e:
    logger.error(f"Operation failed: {e}")
    return {'success': False, 'error': str(e)}, 500
```

### Frontend JavaScript Patterns
```javascript
// Always check for null before accessing DOM elements
function updateElement(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value;
    }
}

// Use fetch for API calls with proper error handling
async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const response = await fetch(endpoint, {
            method: method,
            headers: data ? {'Content-Type': 'application/json'} : {},
            body: data ? JSON.stringify(data) : null
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        showNotification('Error', error.message, 'error');
        throw error;
    }
}
```

## Important Considerations

### Client Identity
- **CRITICAL**: Always use client names as unique identifiers
- IP addresses can change, client names are stable
- Implement proper validation for client name uniqueness
- Use `client.get_unique_id()` method consistently

### Python 3.13 Compatibility
- Use compatible versions of dependencies:
  - `gevent>=24.10.3` (not 24.2.1)
  - `pywin32>=310`
  - `flask>=3.0.3`
  - `flask-socketio>=5.4.1`

### WebSocket Communication
- Don't show unnecessary "connection successful" notifications
- Keep connection status indicators but avoid popup notifications
- Maintain error notifications for connection failures
- Use background tasks for long-running operations

### Task Execution Flow
1. **Task Creation**: Web interface → API → Database
2. **Task Distribution**: Scheduler → Client via HTTP API
3. **Execution**: Client executes subtasks in order
4. **Status Updates**: Client → Server via WebSocket
5. **Monitoring**: Real-time updates via WebSocket

### Security Considerations
- Validate all inputs (client-side AND server-side)
- Use proper HTTP status codes
- Log security-relevant events
- Don't expose sensitive information in error messages

## File Naming Conventions
- Python files: `snake_case.py`
- JavaScript files: `camelCase.js` or `kebab-case.js`
- CSS files: `kebab-case.css`
- HTML templates: `kebab-case.html`

## Testing Guidelines
- **All test files must be written in English** (code, comments, documentation)
- **Official Tests**: Place all production-ready tests in the `tests/` folder
  - Write unit tests for critical functions in `tests/unit/`
  - Create integration tests for API endpoints in `tests/integration/`
  - Develop end-to-end tests for complete workflows in `tests/e2e/`
- **Temporary Tests**: Place intermediate and debug tests in `ignore/temp_tests/`
- Test API endpoints with various input scenarios
- Test frontend JavaScript with null/undefined values
- Test client registration and task distribution flows
- Include error scenario testing
- Use descriptive test names and clear assertions

## Common Patterns to Avoid
- ❌ Don't use IP addresses as client identifiers
- ❌ Don't show unnecessary connection success notifications
- ❌ Don't access DOM elements without null checks
- ❌ Don't use print() for logging in production code
- ❌ Don't hardcode configuration values
- ❌ Don't write code or comments in languages other than English
- ❌ Don't place temporary tests or debug scripts in the main tests/ folder
- ❌ Don't commit intermediate markdown files to version control

## When Adding New Features
1. **Database Changes**: Update models in `common/models.py` first
2. **API Endpoints**: Add to `server/api.py` with proper validation
3. **Frontend**: Update JavaScript in `static/js/` with null safety
4. **Client Support**: Update client execution logic if needed
5. **Documentation**: Update relevant README sections

## Debugging Tips
- Use browser developer tools for frontend issues
- Check server logs in `server/logs/`
- Monitor WebSocket connections in network tab
- Use database browser for SQLite debugging
- Test with multiple client hosts for distributed scenarios

---

This document should be updated as the project evolves. Always refer to the latest version for current guidelines and best practices.
