"""
Base classes and definitions for the subtasks system.

This module provides the core infrastructure for the modular subtask system.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List
from abc import ABC, abstractmethod


class BaseSubtask(ABC):
    """Base class for all subtasks"""
    
    @abstractmethod
    def run(self) -> Any:
        """Execute the subtask and return the result"""
        pass
    
    @abstractmethod
    def get_result(self) -> Any:
        """Get the last execution result"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get a human-readable description of what this subtask does"""
        pass
    
    def __init__(self):
        self._last_result = None
        self._last_error = None
        self._last_execution_time = None
        self._last_timestamp = None
    
    def execute(self) -> Dict[str, Any]:
        """Execute the subtask and return a standardized result"""
        try:
            start_time = datetime.now()
            result = self.run()
            end_time = datetime.now()
            
            self._last_result = result
            self._last_error = None
            self._last_execution_time = (end_time - start_time).total_seconds()
            self._last_timestamp = start_time.isoformat()
            
            return {
                'success': True,
                'error': None,
                'result': result,
                'execution_time': self._last_execution_time,
                'timestamp': self._last_timestamp
            }
        except Exception as e:
            self._last_result = None
            self._last_error = str(e)
            self._last_execution_time = None
            self._last_timestamp = datetime.now().isoformat()
            
            logging.error(f"Subtask '{self.__class__.__name__}' execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'result': None,
                'timestamp': self._last_timestamp
            }


class SubtaskRegistry:
    """Registry for all available subtasks"""
    
    def __init__(self):
        self._subtasks: Dict[str, BaseSubtask] = {}
        
    def register(self, name: str, subtask_instance: BaseSubtask) -> None:
        """Register a new subtask instance"""
        self._subtasks[name] = subtask_instance
        logging.debug(f"Registered subtask: {name}")
        
    def get(self, name: str) -> Optional[BaseSubtask]:
        """Get a subtask instance by name"""
        return self._subtasks.get(name)
        
    def list_subtasks(self) -> List[str]:
        """List all available subtask names"""
        return list(self._subtasks.keys())
        
    def list_subtasks_with_descriptions(self) -> Dict[str, str]:
        """List all subtasks with their descriptions"""
        result = {}
        for name, subtask in self._subtasks.items():
            result[name] = subtask.get_description()
        return result
        
    def execute(self, name: str) -> Dict[str, Any]:
        """Execute a subtask and return the result"""
        if name not in self._subtasks:
            return {
                'success': False,
                'error': f'Subtask "{name}" not found',
                'result': None,
                'timestamp': datetime.now().isoformat()
            }
            
        return self._subtasks[name].execute()


# Legacy support - keeping for backward compatibility
from dataclasses import dataclass

@dataclass
class SubtaskResultDefinition:
    """Legacy result definition - kept for backward compatibility"""
    name: str
    description: str
    result_type: str = "any"
    required_fields: Optional[List[str]] = None
    is_critical: bool = True
    format_hint: Optional[str] = None
    
    def __post_init__(self):
        if self.required_fields is None:
            self.required_fields = []

