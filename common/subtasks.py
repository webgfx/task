"""
Subtask definitions for distributed task execution.

This module provides backward compatibility with the new modular subtask system.
All subtasks are now organized in individual files under the subtasks/ package.

For new development, use the modular subtasks system:
    from common.subtasks import execute_subtask, list_subtasks

This file maintains backward compatibility for existing code.
"""

# Import everything from the new modular subtasks system
from .subtasks import (
    SubtaskResultDefinition,
    register_subtask,
    get_subtask,
    get_subtask_result_definition,
    list_subtasks,
    list_subtasks_with_definitions,
    execute_subtask,
    get_hostname,
    get_system_info
)

# Re-export for backward compatibility
__all__ = [
    'SubtaskResultDefinition',
    'register_subtask', 
    'get_subtask',
    'get_subtask_result_definition',
    'list_subtasks',
    'list_subtasks_with_definitions',
    'execute_subtask',
    'get_hostname',
    'get_system_info'
]

