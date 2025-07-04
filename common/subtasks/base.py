"""
Base classes and definitions for the subtasks system.

This module provides the core infrastructure for the modular subtask system.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass


@dataclass
class SubtaskResultDefinition:
    """Defines the expected result format for a subtask"""
    name: str
    description: str
    result_type: str  # 'string', 'number', 'object', 'list', 'boolean'
    required_fields: Optional[List[str]] = None  # For object types
    is_critical: bool = True  # Whether failure should stop task execution
    format_hint: Optional[str] = None  # Additional formatting information
    
    def __post_init__(self):
        if self.required_fields is None:
            self.required_fields = []


class SubtaskRegistry:
    """Registry for all available subtasks"""
    
    def __init__(self):
        self._subtasks: Dict[str, Callable] = {}
        self._result_definitions: Dict[str, SubtaskResultDefinition] = {}
        
    def register(self, name: str, func: Callable, result_def: Optional[SubtaskResultDefinition] = None) -> None:
        """Register a new subtask function"""
        self._subtasks[name] = func
        if result_def:
            self._result_definitions[name] = result_def
        logging.debug(f"Registered subtask: {name}")
        
    def get(self, name: str) -> Optional[Callable]:
        """Get a subtask function by name"""
        return self._subtasks.get(name)
        
    def get_result_definition(self, name: str) -> Optional[SubtaskResultDefinition]:
        """Get the result definition for a subtask"""
        return self._result_definitions.get(name)
        
    def list_subtasks(self) -> List[str]:
        """List all available subtask names"""
        return list(self._subtasks.keys())
        
    def list_subtasks_with_definitions(self) -> Dict[str, Dict[str, Any]]:
        """List all subtasks with their result definitions"""
        result = {}
        for name in self._subtasks.keys():
            result[name] = {
                'function': self._subtasks[name].__doc__ or 'No description available',
                'result_definition': self._result_definitions.get(name)
            }
        return result
        
    def execute(self, name: str, *args, **kwargs) -> Dict[str, Any]:
        """Execute a subtask and return the result"""
        if name not in self._subtasks:
            return {
                'success': False,
                'error': f'Subtask "{name}" not found',
                'result': None,
                'timestamp': datetime.now().isoformat()
            }
            
        try:
            start_time = datetime.now()
            result = self._subtasks[name](*args, **kwargs)
            end_time = datetime.now()
            
            return {
                'success': True,
                'error': None,
                'result': result,
                'execution_time': (end_time - start_time).total_seconds(),
                'timestamp': start_time.isoformat()
            }
        except Exception as e:
            logging.error(f"Subtask '{name}' execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'result': None,
                'timestamp': datetime.now().isoformat()
            }

