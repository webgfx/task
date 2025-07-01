"""
Subtask executor for client
Responsible for executing subtasks and reporting results to server
"""
import logging
import time
import json
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from common.subtasks import execute_subtask, list_subtasks
from common.models import TaskStatus, SubtaskDefinition

logger = logging.getLogger(__name__)

class SubtaskExecutor:
    """Executes subtasks and reports results to server"""
    
    def __init__(self, server_url: str, machine_name: str):
        self.server_url = server_url
        self.machine_name = machine_name
        
    def execute_task_subtasks(self, task_id: int, subtasks: List[SubtaskDefinition]) -> Dict[str, Any]:
        """
        Execute all subtasks for this machine in the given task
        
        Args:
            task_id: ID of the task
            subtasks: List of subtasks to execute
            
        Returns:
            Overall execution result
        """
        # Filter subtasks for this machine
        my_subtasks = [s for s in subtasks if s.target_machine == self.machine_name]
        
        if not my_subtasks:
            logger.info(f"No subtasks assigned to machine {self.machine_name} for task {task_id}")
            return {
                'success': True,
                'executed_count': 0,
                'message': 'No subtasks assigned to this machine'
            }
        
        # Sort by order
        my_subtasks.sort(key=lambda x: x.order)
        
        logger.info(f"Executing {len(my_subtasks)} subtasks for task {task_id}")
        
        executed_count = 0
        failed_count = 0
        results = []
        
        for subtask in my_subtasks:
            try:
                result = self.execute_single_subtask(task_id, subtask)
                results.append(result)
                
                if result['success']:
                    executed_count += 1
                    logger.info(f"Subtask {subtask.name} completed successfully")
                else:
                    failed_count += 1
                    logger.error(f"Subtask {subtask.name} failed: {result.get('error')}")
                    
                    # Stop execution on failure if configured to do so
                    # For now, continue with remaining subtasks
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Exception executing subtask {subtask.name}: {e}")
                results.append({
                    'success': False,
                    'subtask_name': subtask.name,
                    'error': str(e)
                })
        
        overall_success = failed_count == 0
        
        return {
            'success': overall_success,
            'executed_count': executed_count,
            'failed_count': failed_count,
            'total_count': len(my_subtasks),
            'results': results,
            'message': f"Executed {executed_count}/{len(my_subtasks)} subtasks successfully"
        }
    
    def execute_single_subtask(self, task_id: int, subtask: SubtaskDefinition) -> Dict[str, Any]:
        """
        Execute a single subtask and report result to server
        
        Args:
            task_id: ID of the task
            subtask: Subtask definition to execute
            
        Returns:
            Execution result
        """
        logger.info(f"Starting subtask: {subtask.name} (order: {subtask.order})")
        
        # Report subtask started
        self._report_subtask_status(task_id, subtask, TaskStatus.RUNNING)
        
        start_time = time.time()
        
        try:
            # Execute the subtask
            result = execute_subtask(
                subtask.name,
                *subtask.args,
                **subtask.kwargs
            )
            
            execution_time = time.time() - start_time
            
            if result['success']:
                # Report successful completion
                self._report_subtask_status(
                    task_id, subtask, TaskStatus.COMPLETED,
                    result=result['result'],
                    execution_time=execution_time
                )
                
                return {
                    'success': True,
                    'subtask_name': subtask.name,
                    'result': result['result'],
                    'execution_time': execution_time
                }
            else:
                # Report failure
                self._report_subtask_status(
                    task_id, subtask, TaskStatus.FAILED,
                    error_message=result['error'],
                    execution_time=execution_time
                )
                
                return {
                    'success': False,
                    'subtask_name': subtask.name,
                    'error': result['error'],
                    'execution_time': execution_time
                }
                
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            # Report exception
            self._report_subtask_status(
                task_id, subtask, TaskStatus.FAILED,
                error_message=error_msg,
                execution_time=execution_time
            )
            
            return {
                'success': False,
                'subtask_name': subtask.name,
                'error': error_msg,
                'execution_time': execution_time
            }
    
    def _report_subtask_status(self, task_id: int, subtask: SubtaskDefinition, 
                              status: TaskStatus, result: Any = None, 
                              error_message: str = None, execution_time: float = None):
        """Report subtask execution status to server"""
        try:
            data = {
                'subtask_name': subtask.name,
                'target_machine': self.machine_name,
                'status': status.value,
                'order': subtask.order
            }
            
            if result is not None:
                data['result'] = json.dumps(result) if not isinstance(result, str) else result
            
            if error_message:
                data['error_message'] = error_message
                
            if execution_time is not None:
                data['execution_time'] = execution_time
            
            url = f"{self.server_url}/api/tasks/{task_id}/subtask-executions"
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                logger.debug(f"Reported subtask {subtask.name} status: {status.value}")
            else:
                logger.warning(f"Failed to report subtask status: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error reporting subtask status: {e}")
    
    def get_available_subtasks(self) -> List[str]:
        """Get list of available subtasks on this client"""
        return list_subtasks()
    
    def test_subtask(self, subtask_name: str, *args, **kwargs) -> Dict[str, Any]:
        """Test a subtask execution locally (for debugging)"""
        try:
            logger.info(f"Testing subtask: {subtask_name}")
            result = execute_subtask(subtask_name, *args, **kwargs)
            logger.info(f"Test result: {result}")
            return result
        except Exception as e:
            logger.error(f"Test subtask failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'result': None
            }

class TaskSubtaskAdapter:
    """Adapter to handle both legacy tasks and new subtask-based tasks"""
    
    def __init__(self, server_url: str, machine_name: str):
        self.subtask_executor = SubtaskExecutor(server_url, machine_name)
        
        # Import legacy executor
        from .executor import TaskExecutor
        self.legacy_executor = TaskExecutor()
        
    def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task - either legacy command-based or new subtask-based
        
        Args:
            task_data: Task data from server
            
        Returns:
            Execution result
        """
        task_id = task_data.get('id')
        
        # Check if this is a subtask-based task
        if 'subtasks' in task_data and task_data['subtasks']:
            logger.info(f"Executing subtask-based task {task_id}")
            return self._execute_subtask_task(task_id, task_data['subtasks'])
        else:
            logger.info(f"Executing legacy command-based task {task_id}")
            return self._execute_legacy_task(task_data)
    
    def _execute_subtask_task(self, task_id: int, subtasks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute subtask-based task"""
        # Convert subtask data to SubtaskDefinition objects
        subtasks = []
        for subtask_data in subtasks_data:
            subtask = SubtaskDefinition(
                name=subtask_data.get('name', ''),
                target_machine=subtask_data.get('target_machine', ''),
                order=subtask_data.get('order', 0),
                args=subtask_data.get('args', []),
                kwargs=subtask_data.get('kwargs', {}),
                timeout=subtask_data.get('timeout', 300),
                retry_count=subtask_data.get('retry_count', 0),
                max_retries=subtask_data.get('max_retries', 3)
            )
            subtasks.append(subtask)
        
        return self.subtask_executor.execute_task_subtasks(task_id, subtasks)
    
    def _execute_legacy_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute legacy command-based task"""
        command = task_data.get('command', '')
        if not command:
            return {
                'success': False,
                'error': 'No command specified in legacy task'
            }
        
        # Use legacy executor
        return self.legacy_executor.execute(command)
