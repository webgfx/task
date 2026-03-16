"""
Task executor for client.
Responsible for executing tasks and reporting results (runs) to server.
"""
import logging
import time
import json
import requests
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from common.tasks import execute_task, list_tasks
from common.models import JobStatus, TaskDefinition

logger = logging.getLogger(__name__)

class TaskExecutor:
    """Executes tasks and reports results (runs) to server"""

    def __init__(self, server_url: str, client_name: str):
        self.server_url = server_url
        self.client_name = client_name
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

    def execute_job_tasks(self, task_id: int, task_name: str, tasks: List[TaskDefinition]) -> Dict[str, Any]:
        """
        Execute all tasks for this client in the given task

        Args:
            task_id: ID of the task
            task_name: Name of the task
            tasks: List of tasks to execute

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
        self.task_logger.info(f"client: {self.client_name}")
        self.task_logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.task_logger.info(f"Log Folder: {self.task_log_folder}")

        # Filter tasks for this client
        my_tasks = [s for s in tasks if s.client == self.client_name]

        if not my_tasks:
            self.task_logger.info(f"No tasks assigned to client {self.client_name}")
            logger.info(f"No tasks assigned to client {self.client_name} for task {task_id}")
            return {
                'success': True,
                'executed_count': 0,
                'message': 'No tasks assigned to this client'
            }

        # Sort by order
        my_tasks.sort(key=lambda x: x.order)

        self.task_logger.info(f"Found {len(my_tasks)} tasks assigned to this client")
        for i, Task in enumerate(my_tasks):
            self.task_logger.info(f"  {i+1}. {Task.name} (order: {Task.order})")

        logger.info(f"Executing {len(my_tasks)} tasks for task {task_id}")

        executed_count = 0
        failed_count = 0
        results = []

        for Task in my_tasks:
            try:
                self.task_logger.info(f"--- Starting Task: {Task.name} ---")
                result = self.execute_single_task(task_id, Task)
                results.append(result)

                if result['success']:
                    executed_count += 1
                    self.task_logger.info(f"✓ Task {Task.name} completed successfully")
                    self.task_logger.info(f"  Execution time: {result.get('execution_time', 0):.2f} seconds")
                    self.task_logger.info(f"  Result: {result.get('result', 'No result')}")
                    logger.info(f"Task {Task.name} completed successfully")
                else:
                    failed_count += 1
                    error_msg = result.get('error', 'Unknown error')
                    self.task_logger.error(f"✗ Task {Task.name} failed: {error_msg}")
                    logger.error(f"Task {Task.name} failed: {error_msg}")

                    # Stop execution on failure if configured to do so
                    # For now, continue with remaining tasks

            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                self.task_logger.error(f"✗ Exception executing Task {Task.name}: {error_msg}")
                logger.error(f"Exception executing Task {Task.name}: {e}")
                results.append({
                    'success': False,
                    'task_name': Task.name,
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
        self.task_logger.info(f"Executed: {executed_count}/{len(my_tasks)} tasks")
        if failed_count > 0:
            self.task_logger.info(f"Failed: {failed_count} tasks")

        # Write summary file
        self._write_task_summary(task_id, task_name, start_time, end_time,
                                executed_count, failed_count, len(my_tasks), results)

        return {
            'success': overall_success,
            'executed_count': executed_count,
            'failed_count': failed_count,
            'total_count': len(my_tasks),
            'results': results,
            'message': f"Executed {executed_count}/{len(my_tasks)} tasks successfully",
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
            executed_count: Number of successfully executed tasks
            failed_count: Number of failed tasks
            total_count: Total number of tasks
            results: List of Task execution results
        """
        if not self.task_log_folder:
            return

        summary_data = {
            'task_info': {
                'id': task_id,
                'name': task_name,
                'client': self.client_name
            },
            'execution_info': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'total_execution_time_seconds': (end_time - start_time).total_seconds()
            },
            'results_summary': {
                'total_tasks': total_count,
                'executed_successfully': executed_count,
                'failed': failed_count,
                'success_rate': (executed_count / total_count * 100) if total_count > 0 else 0
            },
            'task_results': results
        }

        summary_file = os.path.join(self.task_log_folder, 'task_summary.json')
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
            self.task_logger.info(f"Task summary written to: {summary_file}")
        except Exception as e:
            self.task_logger.error(f"Failed to write task summary: {e}")
            logger.error(f"Failed to write task summary: {e}")

    def execute_single_task(self, task_id: int, Task: TaskDefinition) -> Dict[str, Any]:
        """
        Execute a single Task and report result to server

        Args:
            task_id: ID of the task
            Task: task definition to execute

        Returns:
            Execution result
        """
        logger.info(f"Starting Task: {Task.name} (order: {Task.order})")
        if self.task_logger:
            self.task_logger.info(f"Executing Task: {Task.name}")
            self.task_logger.info(f"  Order: {Task.order}")
            self.task_logger.info(f"  Target client: {Task.client}")
            if Task.args:
                self.task_logger.info(f"  Arguments: {Task.args}")
            if Task.kwargs:
                self.task_logger.info(f"  Keyword arguments: {Task.kwargs}")

        # Report Task started with enhanced logging
        logger.info(f"🏃 TASK_START: Task {task_id} - '{Task.name}' execution starting on client '{self.client_name}'")
        if self.task_logger:
            self.task_logger.info(f"🏃 Starting execution of Task '{Task.name}' (order: {Task.order})")

        self._report_task_status(task_id, Task, JobStatus.RUNNING)

        start_time = time.time()

        try:
            if self.task_logger:
                self.task_logger.info(f"Calling execute_task({Task.name}, {Task.args}, {Task.kwargs})")

            # Execute the Task
            result = execute_task(
                Task.name,
                *Task.args,
                **Task.kwargs
            )

            execution_time = time.time() - start_time

            if self.task_logger:
                self.task_logger.info(f"Task execution completed in {execution_time:.2f} seconds")
                self.task_logger.info(f"Raw result: {result}")

            if result['success']:
                # Report successful completion
                self._report_task_status(
                    task_id, Task, JobStatus.COMPLETED,
                    result=result['result'],
                    execution_time=execution_time
                )

                if self.task_logger:
                    self.task_logger.info(f"✓ Task {Task.name} completed successfully")
                    self.task_logger.info(f"  Final result: {result['result']}")

                return {
                    'success': True,
                    'task_name': Task.name,
                    'result': result['result'],
                    'execution_time': execution_time
                }
            else:
                # Report failure
                error_msg = result.get('error', 'Unknown error')
                self._report_task_status(
                    task_id, Task, JobStatus.FAILED,
                    error_message=error_msg,
                    execution_time=execution_time
                )

                if self.task_logger:
                    self.task_logger.error(f"✗ Task {Task.name} failed: {error_msg}")

                return {
                    'success': False,
                    'task_name': Task.name,
                    'error': error_msg,
                    'execution_time': execution_time
                }

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)

            if self.task_logger:
                self.task_logger.error(f"✗ Exception during Task {Task.name} execution: {error_msg}")
                self.task_logger.error(f"  Execution time before exception: {execution_time:.2f} seconds")

            # Report exception
            self._report_task_status(
                task_id, Task, JobStatus.FAILED,
                error_message=error_msg,
                execution_time=execution_time
            )

            return {
                'success': False,
                'task_name': Task.name,
                'error': error_msg,
                'execution_time': execution_time
            }

    def _report_task_status(self, task_id: int, Task: TaskDefinition,
                              status: JobStatus, result: Any = None,
                              error_message: str = None, execution_time: float = None):
        """Report Task execution status to server"""
        try:
            data = {
                'task_name': Task.name,
                'client': self.client_name,
                'status': status.value,
                'order': Task.order
            }

            if result is not None:
                # Ensure result is properly serialized
                if isinstance(result, str):
                    data['result'] = result
                else:
                    data['result'] = json.dumps(result, ensure_ascii=False, default=str)

            if error_message:
                data['error_message'] = error_message

            if execution_time is not None:
                data['execution_time'] = execution_time

            url = f"{self.server_url}/api/jobs/{task_id}/runs"

            response = requests.post(url, json=data, timeout=10)

            if response.status_code == 200:
                # Enhanced logging for successful result reporting
                logger.info(f"📤 REPORT_SUCCESS: Task {task_id} - '{Task.name}' status '{status.value}' reported to server")
                if self.task_logger:
                    self.task_logger.info(f"✅ Successfully reported Task '{Task.name}' status '{status.value}' to server")
                    if result is not None and status == JobStatus.COMPLETED:
                        result_preview = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                        self.task_logger.info(f"REPORT_RESULT: Sent result to server: {result_preview}")
                    elif error_message and status == JobStatus.FAILED:
                        error_preview = str(error_message)[:100] + "..." if len(str(error_message)) > 100 else str(error_message)
                        self.task_logger.info(f"REPORT_ERROR: Sent error to server: {error_preview}")

                logger.debug(f"Reported Task {Task.name} status: {status.value}")
                if self.task_logger:
                    self.task_logger.info(f"Successfully reported Task {Task.name} status to server")
            else:
                # Enhanced logging for failed result reporting
                logger.error(f"❌ REPORT_FAILED: Task {task_id} - '{Task.name}' status report failed: {response.status_code}")
                logger.warning(f"Failed to report Task status: {response.status_code} - {response.text}")
                if self.task_logger:
                    self.task_logger.error(f"❌ Failed to report Task '{Task.name}' status to server: {response.status_code}")
                    self.task_logger.warning(f"Failed to report Task status: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Error reporting Task status: {e}")
            if self.task_logger:
                self.task_logger.error(f"Error reporting Task status: {e}")

    def get_available_tasks(self) -> List[str]:
        """Get list of available tasks on this client"""
        return list_tasks()

    def test_task(self, task_name: str, *args, **kwargs) -> Dict[str, Any]:
        """Test a Task execution locally (for debugging)"""
        try:
            logger.info(f"Testing Task: {task_name}")
            result = execute_task(task_name, *args, **kwargs)
            logger.info(f"Test result: {result}")
            return result
        except Exception as e:
            logger.error(f"Test Task failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'result': None
            }

class TaskAdapter:
    """Adapter to dispatch job task execution"""

    def __init__(self, server_url: str, client_name: str):
        self.executor = TaskExecutor(server_url, client_name)

    def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task - either legacy Task-based or new task-based

        Args:
            task_data: Task data from server

        Returns:
            Execution result
        """
        task_id = task_data.get('id')
        task_name = task_data.get('name', f'Task_{task_id}')

        # Execute tasks from job data
        if 'tasks' in task_data and task_data['tasks']:
            logger.info(f"Executing job {task_id}: {task_name}")
            return self._execute_task_job(task_id, task_name, task_data['tasks'])
        else:
            logger.warning(f"Job {task_id} has no tasks defined")
            return {'success': False, 'error': 'No tasks defined in job'}

    def _execute_task_job(self, task_id: int, task_name: str, tasks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute tasks within a job"""
        task_defs = []
        for td in tasks_data:
            task_def = TaskDefinition(
                name=td.get('name', ''),
                client=td.get('client', ''),
                order=td.get('order', 0),
                args=td.get('args', []),
                kwargs=td.get('kwargs', {}),
                timeout=td.get('timeout', 300),
                retry_count=td.get('retry_count', 0),
                max_retries=td.get('max_retries', 3)
            )
            task_defs.append(task_def)

        return self.executor.execute_job_tasks(task_id, task_name, task_defs)

