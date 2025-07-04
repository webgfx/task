"""
Subtasks package for distributed task execution.

This package provides a modular approach to subtask definitions where each
subtask is defined as a class inheriting from BaseSubtask.

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
from typing import Dict, Any, Optional, List

# Import the base classes
from .base import BaseSubtask, SubtaskRegistry, SubtaskResultDefinition

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


def register_subtask_class(name: str, subtask_instance: BaseSubtask):
    """Register a subtask instance"""
    registry = get_registry()
    registry.register(name, subtask_instance)


def get_subtask(name: str) -> Optional[BaseSubtask]:
    """Get a subtask instance by name"""
    return get_registry().get(name)


def list_subtasks() -> List[str]:
    """List all available subtask names"""
    return get_registry().list_subtasks()


def list_subtasks_with_descriptions() -> Dict[str, str]:
    """List all subtasks with their descriptions"""
    return get_registry().list_subtasks_with_descriptions()


def execute_subtask(name: str) -> Dict[str, Any]:
    """Execute a subtask and return the result"""
    return get_registry().execute(name)


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


# Legacy registration function for backward compatibility
def register_subtask(name: str, result_def: Optional[SubtaskResultDefinition] = None):
    """Legacy decorator - kept for backward compatibility"""
    def decorator(func):
        # This is kept for legacy support but new subtasks should use classes
        logging.warning(f"Legacy subtask registration for {name}. Consider migrating to BaseSubtask class.")
        return func
    return decorator


# Legacy function for getting result definitions
def get_subtask_result_definition(name: str) -> Optional[SubtaskResultDefinition]:
    """Legacy function - result definitions are now handled by subtask classes"""
    subtask = get_subtask(name)
    if subtask:
        # Create a legacy result definition from the subtask description
        return SubtaskResultDefinition(
            name=name,
            description=subtask.get_description(),
            result_type="any"
        )
    return None


# Legacy function for listing with definitions
def list_subtasks_with_definitions() -> Dict[str, Dict[str, Any]]:
    """Legacy function - returns subtasks with descriptions"""
    result = {}
    registry = get_registry()
    for name in registry.list_subtasks():
        subtask = registry.get(name)
        result[name] = {
            'function': subtask.get_description(),
            'result_definition': SubtaskResultDefinition(
                name=name,
                description=subtask.get_description(),
                result_type="any"
            )
        }
    return result

