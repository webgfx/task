"""
Subtask definitions for distributed task execution.

This module defines all available subtasks that can be executed by both client and server.
Each subtask corresponds to a Python function that performs a specific operation.
"""

import socket
import platform
import os
import sys
import logging
from typing import Dict, Any, Callable, Optional


class SubtaskRegistry:
    """Registry for all available subtasks"""
    
    def __init__(self):
        self._subtasks: Dict[str, Callable] = {}
        self._register_builtin_subtasks()
        
    def register(self, name: str, func: Callable) -> None:
        """Register a new subtask function"""
        self._subtasks[name] = func
        
    def get(self, name: str) -> Optional[Callable]:
        """Get a subtask function by name"""
        return self._subtasks.get(name)
        
    def list_subtasks(self) -> list:
        """List all available subtask names"""
        return list(self._subtasks.keys())
        
    def execute(self, name: str, *args, **kwargs) -> Dict[str, Any]:
        """Execute a subtask and return the result"""
        if name not in self._subtasks:
            return {
                'success': False,
                'error': f'Subtask "{name}" not found',
                'result': None
            }
            
        try:
            result = self._subtasks[name](*args, **kwargs)
            return {
                'success': True,
                'error': None,
                'result': result
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'result': None
            }
    
    def _register_builtin_subtasks(self):
        """Register all built-in subtasks"""
        # This will be called after all functions are defined
        pass


# Global subtask registry instance (will be initialized later)
_registry = None


def register_subtask(name: str):
    """Decorator to register a subtask function"""
    def decorator(func: Callable):
        _registry.register(name, func)
        return func
    return decorator


def get_subtask(name: str) -> Optional[Callable]:
    """Get a subtask function by name"""
    return _registry.get(name)


def list_subtasks() -> list:
    """List all available subtask names"""
    return _registry.list_subtasks()


def execute_subtask(name: str, *args, **kwargs) -> Dict[str, Any]:
    """Execute a subtask and return the result"""
    return _registry.execute(name, *args, **kwargs)


# ============================================================================
# Built-in Subtask Implementations
# ============================================================================

def get_hostname() -> str:
    """
    Get the hostname of the current machine.
    
    Returns:
        str: The hostname of the current machine
        
    Example:
        >>> result = execute_subtask('get_hostname')
        >>> print(result['result'])  # 'DESKTOP-ABC123' or similar
    """
    try:
        # Try multiple methods to get hostname
        hostname = socket.gethostname()
        
        # If hostname is empty or just localhost, try alternative methods
        if not hostname or hostname.lower() in ['localhost', '127.0.0.1']:
            # Try platform.node() as fallback
            hostname = platform.node()
            
        # If still empty, try environment variables
        if not hostname:
            hostname = os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'unknown-host'))
            
        return hostname.strip()
        
    except Exception as e:
        # If all methods fail, return a default value
        logging.warning(f"Failed to get hostname: {e}")
        return f"unknown-host-{platform.system().lower()}"


# Initialize the global registry and register built-in subtasks
def _initialize_registry():
    """Initialize the global subtask registry"""
    global _registry
    if _registry is None:
        _registry = SubtaskRegistry()
        # Register all built-in subtasks
        _registry.register('get_hostname', get_hostname)
        # Add more subtasks here as they are implemented

# Initialize registry when module is imported
_initialize_registry()


# Example of how to add more subtasks:
# 
# @register_subtask('get_cpu_info')
# def get_cpu_info() -> Dict[str, Any]:
#     """Get CPU information"""
#     import psutil
#     return {
#         'cpu_count': psutil.cpu_count(),
#         'cpu_percent': psutil.cpu_percent(interval=1),
#         'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
#     }


if __name__ == '__main__':
    # Test the subtask system
    print("Available subtasks:", list_subtasks())
    
    # Test get_hostname
    result = execute_subtask('get_hostname')
    print(f"get_hostname result: {result}")
    
    # Test non-existent subtask
    result = execute_subtask('non_existent')
    print(f"non_existent result: {result}")
