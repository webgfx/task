"""
Task scheduler
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from common.models import TaskStatus, MachineStatus
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
        
        # Regularly clean offline machines
        self.scheduler.add_job(
            func=self._cleanup_offline_machines,
            trigger='interval',
            seconds=30,
            id='cleanup_offline_machines'
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
                # Legacy single-machine task
                available_machine = self._find_available_machine(task.target_machine)
                if not available_machine:
                    logger.warning(f"No available machine to execute task: {task.name}")
                    return
                
                self._dispatch_task_to_machine(task, available_machine)
            
        except Exception as e:
            logger.error(f"Failed to execute scheduled task {task_id}: {e}")
    
    def _execute_subtask_task(self, task):
        """Execute a subtask-based task on multiple machines"""
        try:
            # Get all unique target machines from subtasks
            target_machines = task.get_all_target_machines()
            
            if not target_machines:
                logger.warning(f"No target machines found for task: {task.name}")
                return
            
            # Check if all required machines are available
            available_machines = {}
            for machine_name in target_machines:
                machine = self._find_available_machine(machine_name)
                if not machine:
                    logger.warning(f"Machine {machine_name} not available for task {task.name}")
                    return
                available_machines[machine_name] = machine
            
            # All required machines are available, start the task
            logger.info(f"Starting subtask-based task {task.name} on {len(available_machines)} machines")
            
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self.database.update_task(task)
            
            # Dispatch to each machine
            for machine_name, machine in available_machines.items():
                # Get subtasks for this machine
                machine_subtasks = task.get_subtasks_for_machine(machine_name)
                
                if machine_subtasks:
                    # Update machine status
                    self.database.update_machine_heartbeat_by_name(machine.name, MachineStatus.BUSY)
                    
                    # Prepare task data with only relevant subtasks
                    task_data = {
                        'task_id': task.id,
                        'id': task.id,
                        'name': task.name,
                        'machine_name': machine.name,
                        'subtasks': [subtask.to_dict() for subtask in machine_subtasks]
                    }
                    
                    # Send task via WebSocket
                    self.socketio.emit('task_dispatch', task_data, room=f"machine_{machine.name}")
                    
                    logger.info(f"Dispatched {len(machine_subtasks)} subtasks to machine {machine.name}")
            
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
            
            for task in pending_tasks:
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
                        # Legacy single-machine task
                        available_machine = self._find_available_machine(task.target_machine)
                        if available_machine:
                            self._dispatch_task_to_machine(task, available_machine)
                        else:
                            logger.debug(f"No available machine to execute task: {task.name}")
                        
        except Exception as e:
            logger.error(f"Failed to check pending execution tasks: {e}")
    
    def _find_available_machine(self, target_machine=None):
        """Find available machines"""
        try:
            online_machines = self.database.get_online_machines()
            
            if target_machine:
                # Find specified machine
                for machine in online_machines:
                    if machine.name == target_machine and machine.status == MachineStatus.ONLINE:
                        return machine
                return None
            else:
                # Find any available machine
                for machine in online_machines:
                    if machine.status == MachineStatus.ONLINE:
                        return machine
                return None
                
        except Exception as e:
            logger.error(f"Find available machinesFailed: {e}")
            return None
    
    def _dispatch_task_to_machine(self, task, machine):
        """Distribute task to specified machine (supports both legacy and subtask format)"""
        try:
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self.database.update_task(task)
            
            # Update Machine Status using machine name
            self.database.update_machine_heartbeat_by_name(machine.name, MachineStatus.BUSY)
            
            # Prepare task data for client
            task_data = {
                'task_id': task.id,
                'id': task.id,  # Add id field for compatibility
                'name': task.name,
                'command': task.command,  # Legacy support
                'machine_name': machine.name
            }
            
            # Add subtasks if available
            if task.subtasks:
                task_data['subtasks'] = [subtask.to_dict() for subtask in task.subtasks]
                logger.info(f"Dispatching task {task.name} with {len(task.subtasks)} subtasks to machine {machine.name}")
            else:
                # Legacy command-based task
                task_data['commands'] = task.commands
                task_data['execution_order'] = task.execution_order
                logger.info(f"Dispatching legacy task {task.name} to machine {machine.name}")
            
            # Send task via WebSocket (using machine name for room)
            self.socketio.emit('task_dispatch', task_data, room=f"machine_{machine.name}")
            
            logger.info(f"Task {task.name} distributed to machine {machine.name}")
            
        except Exception as e:
            logger.error(f"Failed to distribute task: {e}")
            # Reset task status
            task.status = TaskStatus.PENDING
            task.started_at = None
            self.database.update_task(task)
    
    def _cleanup_offline_machines(self):
        """Clean offline machines"""
        try:
            machines = self.database.get_all_machines()
            current_time = datetime.now()
            offline_threshold = timedelta(seconds=90)  # 90 seconds without heartbeat considered offline
            
            for machine in machines:
                if machine.last_heartbeat:
                    time_since_heartbeat = current_time - machine.last_heartbeat
                    if time_since_heartbeat > offline_threshold and machine.status != MachineStatus.OFFLINE:
                        # Mark machine as offline
                        self.database.update_machine_heartbeat(machine.name, MachineStatus.OFFLINE)
                        
                        # Broadcast machine offline event
                        self.socketio.emit('machine_offline', {
                            'machine_name': machine.name,
                            'offline_at': current_time.isoformat()
                        })
                        
                        logger.warning(f"Machine {machine.name} is offline")
                        
        except Exception as e:
            logger.error(f"Failed to clean offline machines: {e}")
    
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
