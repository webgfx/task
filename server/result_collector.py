"""
Job Result Collection and Report Generation Service

This service collects Task results from all clients and generates reports
when all tasks for a Job are completed.
"""

import logging
import json
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict

from common.models import Job, JobStatus, Run
from server.report_generator import ReportGenerator, EmailNotifier, create_default_email_config

logger = logging.getLogger(__name__)


class TaskResultCollector:
    """Collects and processes Job execution results"""

    def __init__(self, database, socketio, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the result collector

        Args:
            database: Database instance
            socketio: SocketIO instance for real-time updates
            config: Configuration dictionary containing email settings
        """
        self.database = database
        self.socketio = socketio
        self.config = config or {}

        # Initialize report generator
        self.report_generator = ReportGenerator()

        # Initialize email notifier if configured
        self.email_notifier = None
        try:
            from server.email_config import get_email_config
            email_config = get_email_config()
            self.email_notifier = EmailNotifier(email_config)
            logger.info("Email notifier initialized successfully with Outlook configuration")
        except ImportError:
            # Fallback to old configuration method
            if self._is_email_configured():
                try:
                    self.email_notifier = EmailNotifier(self.config.get('email', {}))
                    logger.info("Email notifier initialized with legacy configuration")
                except Exception as e:
                    logger.error(f"Failed to initialize email notifier: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize email notifier: {e}")

        # Track Job completion status
        self._completion_lock = threading.Lock()
        self._processing_tasks = set()  # Track tasks currently being processed

    def _is_email_configured(self) -> bool:
        """Check if legacy email configuration is available (fallback)"""
        email_config = self.config.get('email', {})
        # For Outlook, minimal configuration is needed
        return bool(email_config.get('default_recipient') or email_config.get('to_emails'))

    def on_task_completion(self, task_id: int, client_name: str, task_name: str,
                            task_status: JobStatus, result: Any = None,
                            error_message: str = None, execution_time: float = None):
        """
        Handle Task completion event

        Args:
            task_id: ID of the Job
            client_name: Name of the client that executed the Task
            task_name: Name of the completed Task
            task_status: Status of the Task execution
            result: Task execution result
            error_message: Error message if Task failed
            execution_time: Time taken to execute Task
        """
        try:
            logger.info(f"Processing Task completion: Job {task_id}, Client {client_name}, Task {task_name}, Status {task_status.value}")

            # Check if all tasks for this Job are completed
            if self._check_task_completion(task_id):
                # Process Job completion in a separate thread to avoid blocking
                threading.Thread(
                    target=self._process_task_completion,
                    args=(task_id,),
                    daemon=True
                ).start()

        except Exception as e:
            logger.error(f"Error processing Task completion: {e}")

    def _check_task_completion(self, task_id: int) -> bool:
        """
        Check if all tasks for a Job are completed

        Args:
            task_id: ID of the Job to check

        Returns:
            bool: True if all tasks are completed, False otherwise
        """
        try:
            with self._completion_lock:
                # Avoid processing the same Job multiple times
                if task_id in self._processing_tasks:
                    return False

                # Get Job information
                job = self.database.get_task(task_id)
                if not Job:
                    logger.error(f"Job {task_id} not found")
                    return False

                # Check if Job already completed
                if Job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    return False

                # Get all clients involved in this Job
                clients = Job.get_all_clients()
                if not clients:
                    logger.warning(f"Job {task_id} has no clients")
                    return False

                # Check completion status for each client
                all_completed = True
                for client_name in clients:
                    client_TASKs = Job.get_tasks_for_client(client_name)
                    if not client_TASKs:
                        continue  # No tasks for this client

                    # Check if all tasks for this client are completed
                    for Task in client_TASKs:
                        executions = self.database.get_runs_filtered(
                            task_id, Task.name, client_name
                        )

                        if not executions:
                            # Task not started yet
                            all_completed = False
                            break

                        # Check if any execution is not completed
                        latest_execution = max(executions, key=lambda x: x.id or 0)
                        if latest_execution.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
                            all_completed = False
                            break

                    if not all_completed:
                        break

                if all_completed:
                    # Mark Job as being processed
                    self._processing_tasks.add(task_id)

                return all_completed

        except Exception as e:
            logger.error(f"Error checking Job completion for Job {task_id}: {e}")
            return False

    def _process_task_completion(self, task_id: int):
        """
        Process completed Job - generate report and send notifications

        Args:
            task_id: ID of the completed Job
        """
        try:
            logger.info(f"Processing completion for Job {task_id}")

            # Get Job and update status
            job = self.database.get_task(task_id)
            if not Job:
                logger.error(f"Job {task_id} not found during completion processing")
                return

            # Collect all results
            client_results = self._collect_task_results(Job)

            # Determine overall Job status
            overall_success = self._determine_overall_success(client_results)
            new_task_status = JobStatus.COMPLETED if overall_success else JobStatus.FAILED

            # Update Job status
            self.database.update_task_status(task_id, new_task_status, completed_at=datetime.now())

            # Generate HTML report
            report_file_path = None
            try:
                html_content = self.report_generator.generate_task_report(Job, client_results)
                report_file_path = self.report_generator.save_report_to_file(html_content, Job)
                logger.info(f"Report generated for Job {task_id}: {report_file_path}")
            except Exception as e:
                logger.error(f"Failed to generate report for Job {task_id}: {e}")

            # Send email notification if configured and Job requests it
            if self.email_notifier and Job.should_send_email():
                try:
                    # Get custom recipients from Job, or use default
                    custom_recipients = Job.get_email_recipients_list()

                    if custom_recipients:
                        # Send to custom recipients specified in Job
                        for recipient in custom_recipients:
                            try:
                                # Use the send_notification method with custom recipient
                                result = self.email_notifier.send_notification(
                                    task_name=Job.name,
                                    client_name=Job.get_all_clients()[0] if Job.get_all_clients() else 'unknown',
                                    report_html=self.report_generator.generate_html_report(Job, client_results),
                                    to_email=recipient.strip()
                                )
                                if result.get('success'):
                                    logger.info(f"Email notification sent to {recipient} for Job {task_id}")
                                else:
                                    logger.error(f"Failed to send email to {recipient} for Job {task_id}: {result.get('error', 'Unknown error')}")
                            except Exception as e:
                                logger.error(f"Error sending email to {recipient} for Job {task_id}: {e}")
                    else:
                        # Fallback to default notification method
                        success = self.email_notifier.send_task_completion_notification(
                            Job, client_results, report_file_path
                        )
                        if success:
                            logger.info(f"Email notification sent (default) for Job {task_id}")
                        else:
                            logger.error(f"Failed to send email notification (default) for Job {task_id}")

                except Exception as e:
                    logger.error(f"Error sending email notification for Job {task_id}: {e}")
            elif Job.send_email and not self.email_notifier:
                logger.warning(f"Job {task_id} requested email notification but email notifier is not configured")
            elif Job.send_email and not Job.get_email_recipients_list():
                logger.warning(f"Job {task_id} requested email notification but no recipients specified")

            # Cache Job results for future reference
            self._cache_task_results(Job, client_results)

            # Emit real-time notification
            self._emit_task_completion_event(Job, client_results, overall_success)

            logger.info(f"Job {task_id} completion processing finished")

        except Exception as e:
            logger.error(f"Error processing Job completion for Job {task_id}: {e}")

        finally:
            # Remove from processing set
            with self._completion_lock:
                self._processing_tasks.discard(task_id)

    def _collect_task_results(self, Job: Job) -> Dict[str, Any]:
        """
        Collect all execution results for a Job organized by client

        Args:
            Job: Job object

        Returns:
            Dict containing results organized by client
        """
        client_results = {}

        try:
            clients = Job.get_all_clients()

            for client_name in clients:
                client_TASKs = Job.get_tasks_for_client(client_name)

                if not client_TASKs:
                    continue

                client_data = {
                    'client_name': client_name,
                    'tasks': [],
                    'total_count': len(client_TASKs),
                    'successful_count': 0,
                    'failed_count': 0,
                    'overall_success': False
                }

                for Task in client_TASKs:
                    # Get Task execution results
                    executions = self.database.get_runs_filtered(
                        Job.id, Task.name, client_name
                    )

                    if executions:
                        # Get the latest execution
                        latest_execution = max(executions, key=lambda x: x.id or 0)

                        if latest_execution.status == JobStatus.COMPLETED:
                            client_data['successful_count'] += 1
                        else:
                            client_data['failed_count'] += 1

                        client_data['tasks'].append(latest_execution)
                    else:
                        # Create a placeholder for missing Task execution
                        placeholder = Run(
                            task_id=Job.id,
                            task_name=Task.name,
                            TASK_order=Task.order,
                            client=client_name,
                            status=JobStatus.FAILED,
                            error_message="Task was not executed"
                        )
                        client_data['tasks'].append(placeholder)
                        client_data['failed_count'] += 1

                # Determine client overall success
                client_data['overall_success'] = (client_data['failed_count'] == 0)

                # Sort tasks by order
                client_data['tasks'].sort(key=lambda x: x.task_order)

                client_results[client_name] = client_data

            return client_results

        except Exception as e:
            logger.error(f"Error collecting Job results: {e}")
            return {}

    def _determine_overall_success(self, client_results: Dict[str, Any]) -> bool:
        """
        Determine overall Job success based on client results

        Args:
            client_results: Results organized by client

        Returns:
            bool: True if overall Job succeeded, False otherwise
        """
        if not client_results:
            return False

        # Job succeeds if all clients succeed
        return all(data.get('overall_success', False) for data in client_results.values())

    def _emit_task_completion_event(self, Job: Job, client_results: Dict[str, Any],
                                  overall_success: bool):
        """
        Emit real-time Job completion event via WebSocket

        Args:
            Job: Completed Job
            client_results: Results organized by client
            overall_success: Whether the Job succeeded overall
        """
        try:
            # Calculate summary statistics
            total_clients = len(client_results)
            successful_clients = sum(1 for data in client_results.values() if data.get('overall_success', False))

            total_TASKs = sum(data.get('total_count', 0) for data in client_results.values())
            successful_TASKs = sum(data.get('successful_count', 0) for data in client_results.values())

            event_data = {
                'task_id': Job.id,
                'task_name': Job.name,
                'overall_success': overall_success,
                'status': JobStatus.COMPLETED.value if overall_success else JobStatus.FAILED.value,
                'completed_at': datetime.now().isoformat(),
                'summary': {
                    'total_clients': total_clients,
                    'successful_clients': successful_clients,
                    'total_TASKs': total_TASKs,
                    'successful_TASKs': successful_TASKs
                },
                'client_results': {
                    name: {
                        'overall_success': data.get('overall_success', False),
                        'successful_count': data.get('successful_count', 0),
                        'total_count': data.get('total_count', 0)
                    }
                    for name, data in client_results.items()
                }
            }

            # Emit to all connected clients
            self.socketio.emit('task_completed', event_data)
            logger.debug(f"Emitted Job completion event for Job {Job.id}")

        except Exception as e:
            logger.error(f"Error emitting Job completion event: {e}")

    def generate_report_for_task(self, task_id: int, force: bool = False) -> Optional[str]:
        """
        Generate report for a specific Job (can be called manually)

        Args:
            task_id: ID of the Job
            force: Force report generation even if Job is not completed

        Returns:
            str: Path to generated report file, or None if failed
        """
        try:
            job = self.database.get_task(task_id)
            if not Job:
                logger.error(f"Job {task_id} not found")
                return None

            if not force and Job.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
                logger.error(f"Job {task_id} is not completed (status: {Job.status.value})")
                return None

            # Collect results
            client_results = self._collect_task_results(Job)

            # Generate report
            html_content = self.report_generator.generate_task_report(Job, client_results)
            report_file_path = self.report_generator.save_report_to_file(html_content, Job)

            logger.info(f"Manual report generated for Job {task_id}: {report_file_path}")
            return report_file_path

        except Exception as e:
            logger.error(f"Error generating manual report for Job {task_id}: {e}")
            return None

    def send_manual_notification(self, task_id: int) -> bool:
        """
        Send manual email notification for a Job

        Args:
            task_id: ID of the Job

        Returns:
            bool: True if notification sent successfully, False otherwise
        """
        try:
            if not self.email_notifier:
                logger.error("Email notifier not configured")
                return False

            job = self.database.get_task(task_id)
            if not Job:
                logger.error(f"Job {task_id} not found")
                return False

            # Collect results
            client_results = self._collect_task_results(Job)

            # Generate report file
            report_file_path = self.generate_report_for_task(task_id, force=True)

            # Send notification
            success = self.email_notifier.send_task_completion_notification(
                Job, client_results, report_file_path
            )

            if success:
                logger.info(f"Manual email notification sent for Job {task_id}")
            else:
                logger.error(f"Failed to send manual email notification for Job {task_id}")

            return success

        except Exception as e:
            logger.error(f"Error sending manual notification for Job {task_id}: {e}")
            return False


    def _cache_task_results(self, Job: Job, client_results: Dict[str, Any]):
        """
        Cache completed Job results to the task_results table for future reference.

        Args:
            Job: Completed Job
            client_results: Results organized by client
        """
        try:
            import json

            for client_name, client_data in client_results.items():
                for execution in client_data.get('tasks', []):
                    try:
                        self.database.cache_task_result(
                            task_id=Job.id,
                            task_name=Job.name,
                            client_name=client_name,
                            task_name=execution.task_name,
                            status=execution.status.value,
                            result=execution.result,
                            execution_time=execution.execution_time,
                            completed_at=(execution.completed_at.isoformat()
                                         if execution.completed_at else None)
                        )
                    except Exception as e:
                        logger.error(f"Failed to cache result for Task "
                                   f"'{execution.task_name}' on '{client_name}': {e}")

            logger.info(f"Cached results for Job {Job.id} ({Job.name})")

        except Exception as e:
            logger.error(f"Error caching Job results for Job {Job.id}: {e}")


def create_default_config() -> Dict[str, Any]:
    """Create default configuration for the result collector"""
    return {
        'email': create_default_email_config(),
        'reports': {
            'output_directory': 'reports',
            'keep_reports_days': 30  # How long to keep report files
        }
    }

