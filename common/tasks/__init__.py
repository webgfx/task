"""
Tasks package for distributed job execution.

This package provides a modular approach to task definitions where each
task type is defined as a class inheriting from BaseTask.

Usage:
    from common.tasks import get_task, list_tasks, execute_task

    # Execute a task
    result = execute_task('get_hostname')

    # List available tasks
    available = list_tasks()

    # Reload tasks (useful for development)
    reload_tasks()
"""

import os
import sys
import importlib
import logging
from typing import Dict, Any, Optional, List

from .base import BaseTask, TaskRegistry, TaskResultDefinition

# Global registry instance
_registry = None


def get_registry() -> TaskRegistry:
    """Get the global task registry"""
    global _registry
    if _registry is None:
        _registry = TaskRegistry()
        _load_all_tasks()
    return _registry


def _load_all_tasks():
    """Automatically load all task modules from the tasks directory"""
    global _registry

    tasks_dir = os.path.dirname(__file__)

    for filename in os.listdir(tasks_dir):
        if (filename.endswith('.py') and
            filename not in ['__init__.py', 'base.py'] and
            not filename.startswith('_')):

            module_name = filename[:-3]
            try:
                spec = importlib.util.spec_from_file_location(
                    f'common.tasks.{module_name}',
                    os.path.join(tasks_dir, filename)
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[f'common.tasks.{module_name}'] = module
                spec.loader.exec_module(module)
                logging.debug(f"Loaded task module: {module_name}")
            except Exception as e:
                logging.error(f"Failed to load task module {module_name}: {e}")


def reload_tasks():
    """Reload all task modules to pick up changes without restarting the service."""
    global _registry

    logging.info("Reloading all task modules...")

    if _registry is not None:
        _registry._tasks.clear()

    tasks_dir = os.path.dirname(__file__)

    task_modules = []
    for filename in os.listdir(tasks_dir):
        if (filename.endswith('.py') and
            filename not in ['__init__.py', 'base.py'] and
            not filename.startswith('_')):
            module_name = f'common.tasks.{filename[:-3]}'
            task_modules.append(module_name)

    reloaded_count = 0
    for module_name in task_modules:
        try:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
                logging.debug(f"Reloaded existing module: {module_name}")
            else:
                base_name = module_name.split('.')[-1]
                filepath = os.path.join(tasks_dir, base_name + '.py')
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                logging.debug(f"Imported new module: {module_name}")
            reloaded_count += 1
        except Exception as e:
            logging.error(f"Failed to reload task module {module_name}: {e}")

    logging.info(f"Successfully reloaded {reloaded_count} task modules")

    if _registry:
        loaded = _registry.list_tasks()
        logging.info(f"Available tasks after reload: {', '.join(loaded)}")

    return reloaded_count


def register_task_class(name: str, task_instance: BaseTask):
    """Register a task instance"""
    get_registry().register(name, task_instance)


def get_task(name: str) -> Optional[BaseTask]:
    """Get a task instance by name"""
    return get_registry().get(name)


def list_tasks() -> List[str]:
    """List all available task names"""
    return get_registry().list_tasks()


def list_tasks_with_descriptions() -> Dict[str, str]:
    """List all tasks with their descriptions"""
    return get_registry().list_tasks_with_descriptions()


def execute_task(name: str, *args, **kwargs) -> Dict[str, Any]:
    """Execute a task and return the result"""
    return get_registry().execute(name, *args, **kwargs)


def get_task_result_definition(name: str) -> Optional[TaskResultDefinition]:
    """Get result definition for a task type"""
    task = get_task(name)
    if task:
        return TaskResultDefinition(
            name=name,
            description=task.get_description(),
            result_type="any"
        )
    return None


def list_tasks_with_definitions() -> Dict[str, Dict[str, Any]]:
    """List tasks with full definitions"""
    result = {}
    registry = get_registry()
    for name in registry.list_tasks():
        task = registry.get(name)
        result[name] = {
            'function': task.get_description(),
            'result_definition': TaskResultDefinition(
                name=name,
                description=task.get_description(),
                result_type="any"
            )
        }
    return result

