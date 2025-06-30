# Subtask System Documentation

## Overview

The subtask system provides a unified way to define and execute small, reusable functions that can be called by both client and server components. Each subtask corresponds to a Python function that performs a specific operation.

## Files

- `common/subtasks.py` - Main subtask system implementation
- `common/subtask_examples.py` - Usage examples for client and server

## Current Subtasks

### get_hostname
- **Function**: `get_hostname()`
- **Returns**: `str` - The hostname of the current machine
- **Description**: Gets the hostname using multiple fallback methods for reliability
- **Usage**: `execute_subtask('get_hostname')`

## How to Use Subtasks

### Basic Usage

```python
from common.subtasks import execute_subtask, list_subtasks

# List all available subtasks
available = list_subtasks()
print(f"Available subtasks: {available}")

# Execute a subtask
result = execute_subtask('get_hostname')
if result['success']:
    hostname = result['result']
    print(f"Hostname: {hostname}")
else:
    print(f"Error: {result['error']}")
```

### Result Format

All subtask executions return a dictionary with this format:

```python
{
    'success': bool,    # True if execution succeeded, False otherwise
    'error': str|None,  # Error message if failed, None if succeeded
    'result': Any       # The actual result if succeeded, None if failed
}
```

## How to Add New Subtasks

### Method 1: Direct Function Definition

1. Define your function in `common/subtasks.py`:

```python
def get_cpu_info() -> Dict[str, Any]:
    """Get CPU information"""
    import psutil
    return {
        'cpu_count': psutil.cpu_count(),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
    }
```

2. Register it in the `_initialize_registry()` function:

```python
def _initialize_registry():
    global _registry
    if _registry is None:
        _registry = SubtaskRegistry()
        _registry.register('get_hostname', get_hostname)
        _registry.register('get_cpu_info', get_cpu_info)  # Add this line
```

### Method 2: Using the Decorator (Future Enhancement)

```python
@register_subtask('get_memory_info')
def get_memory_info() -> Dict[str, Any]:
    """Get memory information"""
    import psutil
    memory = psutil.virtual_memory()
    return {
        'total': memory.total,
        'available': memory.available,
        'percent': memory.percent,
        'used': memory.used,
        'free': memory.free
    }
```

### Best Practices for New Subtasks

1. **Function Naming**: Use descriptive names starting with the action (get_, set_, check_, etc.)

2. **Error Handling**: Always include try-catch blocks for robust error handling

3. **Documentation**: Include comprehensive docstrings with examples

4. **Return Types**: Use type hints and return consistent data types

5. **Dependencies**: Import required modules inside the function to avoid startup issues

6. **Testing**: Test your subtask both directly and through the registry system

### Example New Subtask Template

```python
def get_disk_usage(path: str = '/') -> Dict[str, Any]:
    """
    Get disk usage information for a given path.
    
    Args:
        path (str): The path to check (default: '/')
        
    Returns:
        Dict[str, Any]: Dictionary containing disk usage information
        
    Example:
        >>> result = execute_subtask('get_disk_usage', 'C:')
        >>> print(result['result']['free'])
    """
    try:
        import shutil
        total, used, free = shutil.disk_usage(path)
        
        return {
            'path': path,
            'total': total,
            'used': used,
            'free': free,
            'percent_used': (used / total) * 100 if total > 0 else 0
        }
        
    except Exception as e:
        logging.warning(f"Failed to get disk usage for {path}: {e}")
        return {
            'path': path,
            'total': 0,
            'used': 0,
            'free': 0,
            'percent_used': 0,
            'error': str(e)
        }
```

## Integration with Client and Server

### Client Side Usage

Clients can execute subtasks locally and report results to the server:

```python
# In client code
from common.subtasks import execute_subtask

def report_system_info():
    hostname = execute_subtask('get_hostname')
    # Send to server
    send_to_server({'hostname': hostname['result']})
```

### Server Side Usage

Servers can execute subtasks for system monitoring or task coordination:

```python
# In server code
from common.subtasks import execute_subtask

def get_server_status():
    hostname = execute_subtask('get_hostname')
    return {
        'server': hostname['result'],
        'status': 'running'
    }
```

## Future Enhancements

1. **Remote Execution**: Execute subtasks on remote clients
2. **Async Support**: Add async versions of subtasks
3. **Parameter Validation**: Add input parameter validation
4. **Caching**: Cache subtask results for performance
5. **Metrics**: Add execution time and performance metrics
6. **Security**: Add permission checks for sensitive operations
