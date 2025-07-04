"""
Task scheduler
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from common.models import TaskStatus, ClientStatus
from common.utils import parse_datetime

logger = logging.getLogger(__name__)

class TaskScheduler:
    def __init__(self, database, socketio):
        self.database = database
        self.socketio = socketio
        self.scheduler = BackgroundScheduler()
        self.running = False
        
        # Regularly check tasks pending execution
        self.scheduler.add_job(
            func=self._check_pending_tasks,
            trigger='interval',
            seconds=10,
            id='check_pending_tasks'
        )
        
        # Regularly clean offline clients
        self.scheduler.add_job(
            func=self._cleanup_offline_clients,
            trigger='interval',
            seconds=30,
            id='cleanup_offline_clients'
        )
    
    def start(self):
        """Start scheduler"""
        if not self.running:
            self.scheduler.start()
            self.running = True
            logger.info("Task scheduler started")
    
    def stop(self):
        """Stop scheduler"""
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            logger.info("Task scheduler stopped")
    
    def schedule_task(self, task):
        """Schedule single task"""
        try:
            job_id = f"task_{task.id}"
            
            # If task is already scheduled, remove old schedule first
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            
            if task.cron_expression:
                # Schedule using cron expression
                try:
                    trigger = CronTrigger.from_crontab(task.cron_expression)
                    self.scheduler.add_job(
                        func=self._execute_scheduled_task,
                        trigger=trigger,
                        args=[task.id],
                        id=job_id,
                        name=f"Task: {task.name}"
                    )
                    logger.info(f"Task {task.name} scheduled using cron expression: {task.cron_expression}")
                except Exception as e:
                    logger.error(f"Invalid cron expression {task.cron_expression}: {e}")
                    
            elif task.schedule_time:
                # Schedule using specified time
                if task.schedule_time > datetime.now():
                    self.scheduler.add_job(
                        func=self._execute_scheduled_task,
                        trigger='date',
                        run_date=task.schedule_time,
                        args=[task.id],
                        id=job_id,
                        name=f"Task: {task.name}"
                    )
                    logger.info(f"Task {task.name} scheduled to: {task.schedule_time}")
                    
        except Exception as e:
            logger.error(f"Failed to schedule task {task.name}: {e}")
    
    def unschedule_task(self, task_id):
        """Cancel task schedule"""
        try:
            job_id = f"task_{task_id}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"Cancelled task schedule: {task_id}")
        except Exception as e:
            logger.error(f"Cancel task scheduleFailed {task_id}: {e}")
    
    def _execute_scheduled_task(self, task_id):
        """Execute scheduled task (supports subtasks)"""
        try:
            task = self.database.get_task(task_id)
            if not task:
                logger.warning(f"Task does not exist: {task_id}")
                return
            
            if task.status != TaskStatus.PENDING:
                logger.warning(f"Task status is not pending execution: {task.name} ({task.status})")
                return
            
            # Check if this is a subtask-based task
            if task.subtasks:
                self._execute_subtask_task(task)
            else:
                # Legacy single-client task
                available_client = self._find_available_client(task.target_client)
                if not available_client:
                    logger.warning(f"No available client to execute task: {task.name}")
                    return
                
                self._dispatch_task_to_client(task, available_client)
            
        except Exception as e:
            logger.error(f"Failed to execute scheduled task {task_id}: {e}")
    
    def _execute_subtask_task(self, task):
        """Execute a subtask-based task on multiple clients"""
        try:
            # Get all unique target clients from subtasks
            target_clients = task.get_all_target_clients()
            
            if not target_clients:
                logger.warning(f"No target clients found for task: {task.name}")
                return
            
            # Check if all required clients are available
            available_clients = {}
            for client_name in target_clients:
                client = self._find_available_client(client_name)
                if not client:
                    logger.warning(f"Client {client_name} not available for task {task.name}")
                    return
                available_clients[client_name] = client
            
            # All required clients are available, start the task
            logger.info(f"Starting subtask-based task {task.name} on {len(available_clients)} clients")
            
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self.database.update_task(task)
            
            # Dispatch to each client
            for client_name, client in available_clients.items():
                # Get subtasks for this client
                client_subtasks = task.get_subtasks_for_client(client_name)
                
                if client_subtasks:
                    # Update client status
                    self.database.update_client_heartbeat_by_name(client.name, ClientStatus.BUSY)
                    
                    # Prepare task data with only relevant subtasks
                    task_data = {
                        'task_id': task.id,
                        'id': task.id,
                        'name': task.name,
                        'client_name': client.name,
                        'subtasks': [subtask.to_dict() for subtask in client_subtasks]
                    }
                    
                    # Send task via WebSocket using IP-based room name
                    room_name = f"client_{client.ip_address.replace('.', '_')}"
                    logger.info(f"Dispatching subtask to room: {room_name} for client {client.name} ({client.ip_address})")
                    self.socketio.emit('task_dispatch', task_data, room=room_name)
                    
                    logger.info(f"Dispatched {len(client_subtasks)} subtasks to client {client.name}")
            
        except Exception as e:
            logger.error(f"Failed to execute subtask task {task.name}: {e}")
            # Reset task status
            task.status = TaskStatus.PENDING
            task.started_at = None
            self.database.update_task(task)
    
    def _check_pending_tasks(self):
        """Check tasks pending execution"""
        try:
            pending_tasks = self.database.get_pending_tasks()
            current_time = datetime.now()
            
            logger.info(f"DEBUG: Found {len(pending_tasks)} pending tasks to check")
            
            for task in pending_tasks:
                logger.info(f"DEBUG: Checking task {task.id} - {task.name}, status: {task.status}")
                # Check if execution time has come
                should_execute = False
                
                if task.schedule_time:
                    # Check scheduled time tasks
                    if task.schedule_time <= current_time:
                        should_execute = True
                elif not task.cron_expression:
                    # Execute now tasks
                    should_execute = True
                
                if should_execute:
                    if task.subtasks:
                        # Subtask-based task
                        self._execute_subtask_task(task)
                    else:
                        # Legacy single-client task
                        available_client = self._find_available_client(task.target_client)
                        if available_client:
                            self._dispatch_task_to_client(task, available_client)
                        else:
                            logger.debug(f"No available client to execute task: {task.name}")
                        
        except Exception as e:
            logger.error(f"Failed to check pending execution tasks: {e}")
    
    def _find_available_client(self, target_client=None):
        """Find available clients"""
        try:
            online_clients = self.database.get_online_clients()
            
            if target_client:
                # Find specified client
                for client in online_clients:
                    if client.name == target_client and client.status == ClientStatus.ONLINE:
                        return client
                return None
            else:
                # Find any available client
                for client in online_clients:
                    if client.status == ClientStatus.ONLINE:
                        return client
                return None
                
        except Exception as e:
            logger.error(f"Find available clientsFailed: {e}")
            return None
    
    def _dispatch_task_to_client(self, task, client):
        """Distribute task to specified client (supports both legacy and subtask format)"""
        try:
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self.database.update_task(task)
            
            # Update Client Status using client name
            self.database.update_client_heartbeat_by_name(client.name, ClientStatus.BUSY)
            
            # Prepare task data for client
            task_data = {
                'task_id': task.id,
                'id': task.id,  # Add id field for compatibility
                'name': task.name,
                'command': task.command,  # Legacy support
                'client_name': client.name
            }
            
            # Add subtasks if available
            if task.subtasks:
                task_data['subtasks'] = [subtask.to_dict() for subtask in task.subtasks]
                logger.info(f"Dispatching task {task.name} with {len(task.subtasks)} subtasks to client {client.name}")
            else:
                # Legacy command-based task
                task_data['commands'] = task.commands
                task_data['execution_order'] = task.execution_order
                logger.info(f"Dispatching legacy task {task.name} to client {client.name}")
            
            # Send task via WebSocket using IP-based room name
            room_name = f"client_{client.ip_address.replace('.', '_')}"
            logger.info(f"Dispatching task to room: {room_name} for client {client.name} ({client.ip_address})")
            self.socketio.emit('task_dispatch', task_data, room=room_name)
            
            logger.info(f"Task {task.name} distributed to client {client.name}")
            
        except Exception as e:
            logger.error(f"Failed to distribute task: {e}")
            # Reset task status
            task.status = TaskStatus.PENDING
            task.started_at = None
            self.database.update_task(task)
    
    def _cleanup_offline_clients(self):
        """Clean offline clients"""
        try:
            clients = self.database.get_all_clients()
            current_time = datetime.now()
            offline_threshold = timedelta(seconds=90)  # 90 seconds without heartbeat considered offline
            
            for client in clients:
                if client.last_heartbeat:
                    time_since_heartbeat = current_time - client.last_heartbeat
                    if time_since_heartbeat > offline_threshold and client.status != ClientStatus.OFFLINE:
                        # Mark client as offline using client name
                        self.database.update_client_heartbeat_by_name(client.name, ClientStatus.OFFLINE)
                        
                        # Broadcast client offline event
                        self.socketio.emit('client_offline', {
                            'client_name': client.name,
                            'offline_at': current_time.isoformat()
                        })
                        
                        logger.warning(f"Client {client.name} is offline")
                        
        except Exception as e:
            logger.error(f"Failed to clean offline clients: {e}")
    
    def reschedule_all_tasks(self):
        """Reschedule all tasks"""
        try:
            tasks = self.database.get_all_tasks()
            for task in tasks:
                if task.status == TaskStatus.PENDING and (task.cron_expression or task.schedule_time):
                    self.schedule_task(task)
            logger.info("Rescheduled all tasks")
        except Exception as e:
            logger.error(f"Failed to reschedule tasks: {e}")

