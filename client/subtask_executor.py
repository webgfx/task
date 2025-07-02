"""
Subtask executor for client
Responsible for executing subtasks and reporting results to server
"""
import logging
import time
import json
import requests
import os
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
        self.task_log_folder = None
        self.task_logger = None
        
    def _create_task_log_folder(self, task_name: str) -> str:
        """
        Create timestamped log folder for task execution
        
        Args:
            task_name: Name of the task
            
        Returns:
            Path to the created log folder
        """
        # Create timestamp in format yyyymmddhhmmss
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Clean task name for folder name (remove invalid characters)
        clean_task_name = "".join(c for c in task_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_task_name = clean_task_name.replace(' ', '_')
        
        # Create folder name: [timestamp]-[taskname]
        folder_name = f"[{timestamp}]-[{clean_task_name}]"
        
        # Create full path
        logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
        task_log_folder = os.path.join(logs_dir, folder_name)
        
        # Create directories if they don't exist
        os.makedirs(task_log_folder, exist_ok=True)
        
        return task_log_folder
        
    def _setup_task_logger(self, task_log_folder: str, task_name: str):
        """
        Set up dedicated logger for task execution
        
        Args:
            task_log_folder: Path to task log folder
            task_name: Name of the task
        """
        # Create task-specific logger
        task_logger_name = f"task_execution_{task_name}"
        self.task_logger = logging.getLogger(task_logger_name)
        
        # Remove existing handlers to avoid duplicates
        for handler in self.task_logger.handlers[:]:
            self.task_logger.removeHandler(handler)
            
        # Set log level
        self.task_logger.setLevel(logging.INFO)
        
        # Create file handler for task execution log
        execution_log_file = os.path.join(task_log_folder, 'execution.log')
        file_handler = logging.FileHandler(execution_log_file, encoding='utf-8')
        
        # Create detailed formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.task_logger.addHandler(file_handler)
        
        # Don't propagate to parent logger to avoid duplicate logs
        self.task_logger.propagate = False
        
    def execute_task_subtasks(self, task_id: int, task_name: str, subtasks: List[SubtaskDefinition]) -> Dict[str, Any]:
        """
        Execute all subtasks for this machine in the given task
        
        Args:
            task_id: ID of the task
            task_name: Name of the task
            subtasks: List of subtasks to execute
            
        Returns:
            Overall execution result
        """
        # Create timestamped log folder for this task execution
        self.task_log_folder = self._create_task_log_folder(task_name)
        self._setup_task_logger(self.task_log_folder, task_name)
        
        # Log task start
        start_time = datetime.now()
        self.task_logger.info(f"=== TASK EXECUTION STARTED ===")
        self.task_logger.info(f"Task ID: {task_id}")
        self.task_logger.info(f"Task Name: {task_name}")
        self.task_logger.info(f"Machine: {self.machine_name}")
        self.task_logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.task_logger.info(f"Log Folder: {self.task_log_folder}")
        
        # Filter subtasks for this machine
        my_subtasks = [s for s in subtasks if s.target_machine == self.machine_name]
        
        if not my_subtasks:
            self.task_logger.info(f"No subtasks assigned to machine {self.machine_name}")
            logger.info(f"No subtasks assigned to machine {self.machine_name} for task {task_id}")
            return {
                'success': True,
                'executed_count': 0,
                'message': 'No subtasks assigned to this machine'
            }
        
        # Sort by order
        my_subtasks.sort(key=lambda x: x.order)
        
        self.task_logger.info(f"Found {len(my_subtasks)} subtasks assigned to this machine")
        for i, subtask in enumerate(my_subtasks):
            self.task_logger.info(f"  {i+1}. {subtask.name} (order: {subtask.order})")
        
        logger.info(f"Executing {len(my_subtasks)} subtasks for task {task_id}")
        
        executed_count = 0
        failed_count = 0
        results = []
        
        for subtask in my_subtasks:
            try:
                self.task_logger.info(f"--- Starting subtask: {subtask.name} ---")
                result = self.execute_single_subtask(task_id, subtask)
                results.append(result)
                
                if result['success']:
                    executed_count += 1
                    self.task_logger.info(f"✓ Subtask {subtask.name} completed successfully")
                    self.task_logger.info(f"  Execution time: {result.get('execution_time', 0):.2f} seconds")
                    self.task_logger.info(f"  Result: {result.get('result', 'No result')}")
                    logger.info(f"Subtask {subtask.name} completed successfully")
                else:
                    failed_count += 1
                    error_msg = result.get('error', 'Unknown error')
                    self.task_logger.error(f"✗ Subtask {subtask.name} failed: {error_msg}")
                    logger.error(f"Subtask {subtask.name} failed: {error_msg}")
                    
                    # Stop execution on failure if configured to do so
                    # For now, continue with remaining subtasks
                    
            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                self.task_logger.error(f"✗ Exception executing subtask {subtask.name}: {error_msg}")
                logger.error(f"Exception executing subtask {subtask.name}: {e}")
                results.append({
                    'success': False,
                    'subtask_name': subtask.name,
                    'error': error_msg
                })
        
        overall_success = failed_count == 0
        end_time = datetime.now()
        total_execution_time = (end_time - start_time).total_seconds()
        
        # Log task completion
        self.task_logger.info(f"=== TASK EXECUTION COMPLETED ===")
        self.task_logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.task_logger.info(f"Total Execution Time: {total_execution_time:.2f} seconds")
        self.task_logger.info(f"Overall Success: {overall_success}")
        self.task_logger.info(f"Executed: {executed_count}/{len(my_subtasks)} subtasks")
        if failed_count > 0:
            self.task_logger.info(f"Failed: {failed_count} subtasks")
        
        # Write summary file
        self._write_task_summary(task_id, task_name, start_time, end_time, 
                                executed_count, failed_count, len(my_subtasks), results)
        
        return {
            'success': overall_success,
            'executed_count': executed_count,
            'failed_count': failed_count,
            'total_count': len(my_subtasks),
            'results': results,
            'message': f"Executed {executed_count}/{len(my_subtasks)} subtasks successfully",
            'execution_time': total_execution_time,
            'log_folder': self.task_log_folder
        }
    
    def _write_task_summary(self, task_id: int, task_name: str, start_time: datetime, 
                           end_time: datetime, executed_count: int, failed_count: int, 
                           total_count: int, results: List[Dict[str, Any]]):
        """
        Write task execution summary to a JSON file
        
        Args:
            task_id: ID of the task
            task_name: Name of the task
            start_time: Task start time
            end_time: Task end time
            executed_count: Number of successfully executed subtasks
            failed_count: Number of failed subtasks
            total_count: Total number of subtasks
            results: List of subtask execution results
        """
        if not self.task_log_folder:
            return
            
        summary_data = {
            'task_info': {
                'id': task_id,
                'name': task_name,
                'machine': self.machine_name
            },
            'execution_info': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'total_execution_time_seconds': (end_time - start_time).total_seconds()
            },
            'results_summary': {
                'total_subtasks': total_count,
                'executed_successfully': executed_count,
                'failed': failed_count,
                'success_rate': (executed_count / total_count * 100) if total_count > 0 else 0
            },
            'subtask_results': results
        }
        
        summary_file = os.path.join(self.task_log_folder, 'task_summary.json')
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
            self.task_logger.info(f"Task summary written to: {summary_file}")
        except Exception as e:
            self.task_logger.error(f"Failed to write task summary: {e}")
            logger.error(f"Failed to write task summary: {e}")
    
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
        if self.task_logger:
            self.task_logger.info(f"Executing subtask: {subtask.name}")
            self.task_logger.info(f"  Order: {subtask.order}")
            self.task_logger.info(f"  Target machine: {subtask.target_machine}")
            if subtask.args:
                self.task_logger.info(f"  Arguments: {subtask.args}")
            if subtask.kwargs:
                self.task_logger.info(f"  Keyword arguments: {subtask.kwargs}")
        
        # Report subtask started
        self._report_subtask_status(task_id, subtask, TaskStatus.RUNNING)
        
        start_time = time.time()
        
        try:
            if self.task_logger:
                self.task_logger.info(f"Calling execute_subtask({subtask.name}, {subtask.args}, {subtask.kwargs})")
            
            # Execute the subtask
            result = execute_subtask(
                subtask.name,
                *subtask.args,
                **subtask.kwargs
            )
            
            execution_time = time.time() - start_time
            
            if self.task_logger:
                self.task_logger.info(f"Subtask execution completed in {execution_time:.2f} seconds")
                self.task_logger.info(f"Raw result: {result}")
            
            if result['success']:
                # Report successful completion
                self._report_subtask_status(
                    task_id, subtask, TaskStatus.COMPLETED,
                    result=result['result'],
                    execution_time=execution_time
                )
                
                if self.task_logger:
                    self.task_logger.info(f"✓ Subtask {subtask.name} completed successfully")
                    self.task_logger.info(f"  Final result: {result['result']}")
                
                return {
                    'success': True,
                    'subtask_name': subtask.name,
                    'result': result['result'],
                    'execution_time': execution_time
                }
            else:
                # Report failure
                error_msg = result.get('error', 'Unknown error')
                self._report_subtask_status(
                    task_id, subtask, TaskStatus.FAILED,
                    error_message=error_msg,
                    execution_time=execution_time
                )
                
                if self.task_logger:
                    self.task_logger.error(f"✗ Subtask {subtask.name} failed: {error_msg}")
                
                return {
                    'success': False,
                    'subtask_name': subtask.name,
                    'error': error_msg,
                    'execution_time': execution_time
                }
                
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            if self.task_logger:
                self.task_logger.error(f"✗ Exception during subtask {subtask.name} execution: {error_msg}")
                self.task_logger.error(f"  Execution time before exception: {execution_time:.2f} seconds")
            
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
        from client.executor import TaskExecutor
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
        task_name = task_data.get('name', f'Task_{task_id}')
        
        # Check if this is a subtask-based task
        if 'subtasks' in task_data and task_data['subtasks']:
            logger.info(f"Executing subtask-based task {task_id}: {task_name}")
            return self._execute_subtask_task(task_id, task_name, task_data['subtasks'])
        else:
            logger.info(f"Executing legacy command-based task {task_id}: {task_name}")
            return self._execute_legacy_task(task_data)
    
    def _execute_subtask_task(self, task_id: int, task_name: str, subtasks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
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
        
        return self.subtask_executor.execute_task_subtasks(task_id, task_name, subtasks)
    
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
