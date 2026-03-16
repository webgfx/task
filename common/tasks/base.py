"""
Base classes and definitions for the task system.

This module provides the core infrastructure for the modular task system.
Each task type (ai-test, hostname, …) inherits from BaseTask.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List
from abc import ABC, abstractmethod


class BaseTask(ABC):
    """Base class for all task types"""

    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """Execute the task and return the result"""
        pass

    @abstractmethod
    def get_result(self) -> Any:
        """Get the last execution result"""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get a human-readable description of what this task does"""
        pass

    def __init__(self):
        self._last_result = None
        self._last_error = None
        self._last_execution_time = None
        self._last_timestamp = None

    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """Execute the task and return a standardized result"""
        try:
            start_time = datetime.now()
            result = self.run(*args, **kwargs)
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

            logging.error(f"Task '{self.__class__.__name__}' execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'result': None,
                'timestamp': self._last_timestamp
            }


class TaskRegistry:
    """Registry for all available task types"""

    def __init__(self):
        self._tasks: Dict[str, BaseTask] = {}

    def register(self, name: str, task_instance: BaseTask) -> None:
        """Register a new task instance"""
        self._tasks[name] = task_instance
        logging.debug(f"Registered task: {name}")

    def get(self, name: str) -> Optional[BaseTask]:
        """Get a task instance by name"""
        return self._tasks.get(name)

    def list_tasks(self) -> List[str]:
        """List all available task names"""
        return list(self._tasks.keys())

    def list_tasks_with_descriptions(self) -> Dict[str, str]:
        """List all tasks with their descriptions"""
        result = {}
        for name, task in self._tasks.items():
            result[name] = task.get_description()
        return result

    def execute(self, name: str, *args, **kwargs) -> Dict[str, Any]:
        """Execute a task and return the result"""
        if name not in self._tasks:
            return {
                'success': False,
                'error': f'Task "{name}" not found',
                'result': None,
                'timestamp': datetime.now().isoformat()
            }

        return self._tasks[name].execute(*args, **kwargs)


from dataclasses import dataclass

@dataclass
class TaskResultDefinition:
    """Result definition for task types"""
    name: str
    description: str
    result_type: str = "any"
    required_fields: Optional[List[str]] = None
    is_critical: bool = True
    format_hint: Optional[str] = None

    def __post_init__(self):
        if self.required_fields is None:
            self.required_fields = []

