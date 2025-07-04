"""
Subtasks package for distributed task execution.

This package provides a modular approach to subtask definitions where each
subtask is defined in its own file with proper result specifications.

Usage:
    from common.subtasks import get_subtask, list_subtasks, execute_subtask
    
    # Execute a subtask
    result = execute_subtask('get_hostname')
    
    # List available subtasks
    available = list_subtasks()
"""

import os
import importlib
import logging
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass

# Import the base classes
from .base import SubtaskResultDefinition, SubtaskRegistry

# Global registry instance
_registry = None


def get_registry() -> SubtaskRegistry:
    """Get the global subtask registry"""
    global _registry
    if _registry is None:
        _registry = SubtaskRegistry()
        _load_all_subtasks()
    return _registry


def _load_all_subtasks():
    """Automatically load all subtask modules from the subtasks directory"""
    global _registry
    
    # Get the directory containing subtask modules
    subtasks_dir = os.path.dirname(__file__)
    
    # Import all Python files in the subtasks directory (except __init__.py and base.py)
    for filename in os.listdir(subtasks_dir):
        if (filename.endswith('.py') and 
            filename not in ['__init__.py', 'base.py'] and
            not filename.startswith('_')):
            
            module_name = filename[:-3]  # Remove .py extension
            try:
                # Import the module - this will trigger registration
                importlib.import_module(f'common.subtasks.{module_name}')
                logging.debug(f"Loaded subtask module: {module_name}")
            except Exception as e:
                logging.error(f"Failed to load subtask module {module_name}: {e}")


def register_subtask(name: str, result_def: Optional[SubtaskResultDefinition] = None):
    """Decorator to register a subtask function"""
    def decorator(func: Callable):
        registry = get_registry()
        registry.register(name, func, result_def)
        return func
    return decorator


def get_subtask(name: str) -> Optional[Callable]:
    """Get a subtask function by name"""
    return get_registry().get(name)


def get_subtask_result_definition(name: str) -> Optional[SubtaskResultDefinition]:
    """Get the result definition for a subtask"""
    return get_registry().get_result_definition(name)


def list_subtasks() -> List[str]:
    """List all available subtask names"""
    return get_registry().list_subtasks()


def list_subtasks_with_definitions() -> Dict[str, Dict[str, Any]]:
    """List all subtasks with their result definitions"""
    return get_registry().list_subtasks_with_definitions()


def execute_subtask(name: str, *args, **kwargs) -> Dict[str, Any]:
    """Execute a subtask and return the result"""
    return get_registry().execute(name, *args, **kwargs)


# Convenience functions for backward compatibility
def get_hostname() -> str:
    """Backward compatibility wrapper for get_hostname subtask"""
    result = execute_subtask('get_hostname')
    if result['success']:
        return result['result']
    else:
        raise Exception(result['error'])


def get_system_info() -> Dict[str, Any]:
    """Backward compatibility wrapper for get_system_info subtask"""
    result = execute_subtask('get_system_info')
    if result['success']:
        return result['result']
    else:
        raise Exception(result['error'])

