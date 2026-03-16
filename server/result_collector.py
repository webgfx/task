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
        self._processing_jobs = set()  # Track jobs currently being processed

    def _is_email_configured(self) -> bool:
        """Check if legacy email configuration is available (fallback)"""
        email_config = self.config.get('email', {})
        # For Outlook, minimal configuration is needed
        return bool(email_config.get('default_recipient') or email_config.get('to_emails'))

    def on_run_completion(self, job_id: int, client_name: str, task_name: str,
                            task_status: JobStatus, result: Any = None,
                            error_message: str = None, execution_time: float = None):
        """
        Handle task run completion event

        Args:
            job_id: ID of the Job
            client_name: Name of the client that executed the task
            task_name: Name of the completed task
            task_status: Status of the task execution
            result: Task execution result
            error_message: Error message if task failed
            execution_time: Time taken to execute task
        """
        try:
            logger.info(f"Processing run completion: Job {job_id}, Client {client_name}, Task {task_name}, Status {task_status.value}")

            # Check if all tasks for this job are completed
            if self._check_job_completion(job_id):
                # Process job completion in a separate thread to avoid blocking
                threading.Thread(
                    target=self._process_job_completion,
                    args=(job_id,),
                    daemon=True
                ).start()

        except Exception as e:
            logger.error(f"Error processing run completion: {e}")

    def _check_job_completion(self, job_id: int) -> bool:
        """
        Check if all tasks for a job are completed

        Args:
            job_id: ID of the job to check

        Returns:
            bool: True if all tasks are completed, False otherwise
        """
        try:
            with self._completion_lock:
                # Avoid processing the same job multiple times
                if job_id in self._processing_jobs:
                    return False

                # Get job information
                job = self.database.get_job(job_id)
                if not job:
                    logger.error(f"Job {job_id} not found")
                    return False

                # Check if job already completed
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    return False

                # Get all clients involved in this job
                clients = job.get_all_clients()
                if not clients:
                    logger.warning(f"Job {job_id} has no clients")
                    return False

                # Check completion status for each client
                all_completed = True
                for client_name in clients:
                    client_tasks = job.get_tasks_for_client(client_name)
                    if not client_tasks:
                        continue  # No tasks for this client

                    # Check if all tasks for this client are completed
                    for td in client_tasks:
                        executions = self.database.get_runs_filtered(
                            task_id, td.name, client_name
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
                    # Mark job as being processed
                    self._processing_jobs.add(job_id)

                return all_completed

        except Exception as e:
            logger.error(f"Error checking job completion for Job {job_id}: {e}")
            return False

    def _process_job_completion(self, job_id: int):
        """
        Process completed job - generate report and send notifications

        Args:
            job_id: ID of the completed job
        """
        try:
            logger.info(f"Processing completion for Job {job_id}")

            # Get job and update status
            job = self.database.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found during completion processing")
                return

            # Collect all results
            client_results = self._collect_job_results(job)

            # Determine overall job status
            overall_success = self._determine_overall_success(client_results)
            new_status = JobStatus.COMPLETED if overall_success else JobStatus.FAILED

            # Update job status
            self.database.update_job_status(job_id, new_status, completed_at=datetime.now())

            # Generate HTML report
            report_file_path = None
            try:
                html_content = self.report_generator.generate_task_report(job, client_results)
                report_file_path = self.report_generator.save_report_to_file(html_content, job)
                logger.info(f"Report generated for Job {job_id}: {report_file_path}")
            except Exception as e:
                logger.error(f"Failed to generate report for Job {job_id}: {e}")

            # Send email notification if configured and job requests it
            if self.email_notifier and job.should_send_email():
                try:
                    # Get custom recipients from Job, or use default
                    custom_recipients = job.get_email_recipients_list()

                    if custom_recipients:
                        # Send to custom recipients specified in Job
                        for recipient in custom_recipients:
                            try:
                                # Use the send_notification method with custom recipient
                                result = self.email_notifier.send_notification(
                                    task_name=job.name,
                                    client_name=job.get_all_clients()[0] if job.get_all_clients() else 'unknown',
                                    report_html=self.report_generator.generate_html_report(job, client_results),
                                    to_email=recipient.strip()
                                )
                                if result.get('success'):
                                    logger.info(f"Email notification sent to {recipient} for Job {job_id}")
                                else:
                                    logger.error(f"Failed to send email to {recipient} for Job {job_id}: {result.get('error', 'Unknown error')}")
                            except Exception as e:
                                logger.error(f"Error sending email to {recipient} for Job {job_id}: {e}")
                    else:
                        # Fallback to default notification method
                        success = self.email_notifier.send_task_completion_notification(job, client_results, report_file_path
                        )
                        if success:
                            logger.info(f"Email notification sent (default) for Job {job_id}")
                        else:
                            logger.error(f"Failed to send email notification (default) for Job {job_id}")

                except Exception as e:
                    logger.error(f"Error sending email notification for Job {job_id}: {e}")
            elif job.send_email and not self.email_notifier:
                logger.warning(f"Job {job_id} requested email notification but email notifier is not configured")
            elif job.send_email and not job.get_email_recipients_list():
                logger.warning(f"Job {job_id} requested email notification but no recipients specified")

            # Cache job results for future reference
            self._cache_job_results(job, client_results)

            # Emit real-time notification
            self._emit_job_completion_event(job, client_results, overall_success)

            logger.info(f"Job {job_id} completion processing finished")

        except Exception as e:
            logger.error(f"Error processing job completion for Job {job_id}: {e}")

        finally:
            # Remove from processing set
            with self._completion_lock:
                self._processing_jobs.discard(job_id)

    def _collect_job_results(self, job: Job) -> Dict[str, Any]:
        """
        Collect all execution results for a job organized by client

        Args:
            Job: Job object

        Returns:
            Dict containing results organized by client
        """
        client_results = {}

        try:
            clients = job.get_all_clients()

            for client_name in clients:
                client_tasks = job.get_tasks_for_client(client_name)

                if not client_tasks:
                    continue

                client_data = {
                    'client_name': client_name,
                    'tasks': [],
                    'total_count': len(client_tasks),
                    'successful_count': 0,
                    'failed_count': 0,
                    'overall_success': False
                }

                for td in client_tasks:
                    # Get Task execution results
                    executions = self.database.get_runs_filtered(
                        job.id, td.name, client_name
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
                            task_id=job.id,
                            task_name=td.name,
                            task_order=td.order,
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

    def _emit_job_completion_event(self, job: Job, client_results: Dict[str, Any],
                                  overall_success: bool):
        """
        Emit real-time job completion event via WebSocket

        Args:
            Job: Completed Job
            client_results: Results organized by client
            overall_success: Whether the Job succeeded overall
        """
        try:
            # Calculate summary statistics
            total_clients = len(client_results)
            successful_clients = sum(1 for data in client_results.values() if data.get('overall_success', False))

            total_tasks = sum(data.get('total_count', 0) for data in client_results.values())
            successful_tasks = sum(data.get('successful_count', 0) for data in client_results.values())

            event_data = {
                'task_id': job.id,
                'task_name': job.name,
                'overall_success': overall_success,
                'status': JobStatus.COMPLETED.value if overall_success else JobStatus.FAILED.value,
                'completed_at': datetime.now().isoformat(),
                'summary': {
                    'total_clients': total_clients,
                    'successful_clients': successful_clients,
                    'total_tasks': total_tasks,
                    'successful_tasks': successful_tasks
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
            logger.debug(f"Emitted Job completion event for Job {job.id}")

        except Exception as e:
            logger.error(f"Error emitting Job completion event: {e}")

    def generate_report_for_job(self, job_id: int, force: bool = False) -> Optional[str]:
        """
        Generate report for a specific job (can be called manually)

        Args:
            job_id: ID of the job
            force: Force report generation even if job is not completed

        Returns:
            str: Path to generated report file, or None if failed
        """
        try:
            job = self.database.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return None

            if not force and job.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
                logger.error(f"Job {job_id} is not completed (status: {job.status.value})")
                return None

            # Collect results
            client_results = self._collect_job_results(job)

            # Generate report
            html_content = self.report_generator.generate_task_report(job, client_results)
            report_file_path = self.report_generator.save_report_to_file(html_content, job)

            logger.info(f"Manual report generated for Job {job_id}: {report_file_path}")
            return report_file_path

        except Exception as e:
            logger.error(f"Error generating manual report for Job {job_id}: {e}")
            return None

    def send_manual_notification(self, job_id: int) -> bool:
        """
        Send manual email notification for a job

        Args:
            job_id: ID of the job

        Returns:
            bool: True if notification sent successfully, False otherwise
        """
        try:
            if not self.email_notifier:
                logger.error("Email notifier not configured")
                return False

            job = self.database.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return False

            # Collect results
            client_results = self._collect_job_results(job)

            # Generate report file
            report_file_path = self.generate_report_for_job(job_id, force=True)

            # Send notification
            success = self.email_notifier.send_task_completion_notification(job, client_results, report_file_path
            )

            if success:
                logger.info(f"Manual email notification sent for Job {job_id}")
            else:
                logger.error(f"Failed to send manual email notification for Job {job_id}")

            return success

        except Exception as e:
            logger.error(f"Error sending manual notification for Job {job_id}: {e}")
            return False


    def _cache_job_results(self, job: Job, client_results: Dict[str, Any]):
        """
        Cache completed job results to the task_results table for future reference.

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
                            job_id=job.id,
                            job_name=job.name,
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

            logger.info(f"Cached results for Job {job.id} ({job.name})")

        except Exception as e:
            logger.error(f"Error caching Job results for Job {job.id}: {e}")


def create_default_config() -> Dict[str, Any]:
    """Create default configuration for the result collector"""
    return {
        'email': create_default_email_config(),
        'reports': {
            'output_directory': 'reports',
            'keep_reports_days': 30  # How long to keep report files
        }
    }

