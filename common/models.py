"""
Common data model definitions

Naming convention:
  - Job:            A scheduled container assigned to devices (one task type + N clients)
  - Task:           The type of work to execute (ai-test, hostname, system-info, …)
  - Run:            One instance of a job executing on a specific device
  - TaskDefinition: Parameters for a task within a job (name, client, kwargs, …)
"""
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ClientStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"


@dataclass
class TaskDefinition:
    """Parameters for a task within a job"""
    name: str = ""
    client: str = ""  # Target client for this task
    order: int = 0
    args: List[Any] = None
    kwargs: Dict[str, Any] = None
    timeout: int = 300  # seconds
    retry_count: int = 0
    max_retries: int = 3
    task_id: Optional[int] = None  # Unique identifier for the task within the job

    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.kwargs is None:
            self.kwargs = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'client': self.client,
            'order': self.order,
            'args': self.args,
            'kwargs': self.kwargs,
            'timeout': self.timeout,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'task_id': self.task_id
        }


@dataclass
class Job:
    id: Optional[int] = None
    name: str = ""
    command: str = ""
    schedule_time: Optional[datetime] = None
    cron_expression: Optional[str] = None
    clients: List[str] = None  # Support multiple clients
    commands: List[Dict[str, Any]] = None  # Legacy command list for backward compatibility
    execution_order: List[int] = None  # Command execution order
    tasks: List[TaskDefinition] = None  # Task definitions for this job
    status: JobStatus = JobStatus.PENDING
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    # Email notification settings
    send_email: bool = False
    email_recipients: Optional[str] = None  # Semicolon-separated email addresses

    # For backward compatibility, keep single client field
    client: Optional[str] = None

    def __post_init__(self):
        if self.clients is None:
            self.clients = []
        if self.commands is None:
            self.commands = []
        if self.execution_order is None:
            self.execution_order = []
        if self.tasks is None:
            self.tasks = []

        # Backward compatibility: if client is used, add to clients
        if self.client and self.client not in self.clients:
            self.clients.append(self.client)

        # If only command field exists, convert to commands format
        if self.command and not self.commands and not self.tasks:
            self.commands = [{
                'id': 1,
                'name': 'Default Command',
                'command': self.command,
                'timeout': 300,
                'retry_count': 0
            }]
            self.execution_order = [1]

    def get_all_clients(self) -> List[str]:
        """Get all unique clients from tasks and legacy fields"""
        clients = set()

        # Add from legacy clients
        clients.update(self.clients or [])

        # Add from tasks
        for task in self.tasks or []:
            if task.client:
                clients.add(task.client)

        # Add legacy client
        if self.client:
            clients.add(self.client)

        return list(clients)

    def get_tasks_for_client(self, client_name: str) -> List[TaskDefinition]:
        """Get all tasks assigned to a specific client"""
        return [task for task in (self.tasks or [])
                if task.client == client_name]

    def get_email_recipients_list(self) -> List[str]:
        """Get email recipients as a list, parsing semicolon-separated string"""
        if not self.email_recipients:
            return []
        recipients = [email.strip() for email in self.email_recipients.split(';')]
        return [email for email in recipients if email]

    def should_send_email(self) -> bool:
        """Check if email notifications should be sent for this job"""
        return self.send_email and bool(self.get_email_recipients_list())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'command': self.command,
            'schedule_time': self.schedule_time.isoformat() if self.schedule_time else None,
            'cron_expression': self.cron_expression,
            'client': self.client,
            'clients': self.clients,
            'commands': self.commands,
            'execution_order': self.execution_order,
            'tasks': [task.to_dict() for task in (self.tasks or [])],
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result': self.result,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'send_email': self.send_email,
            'email_recipients': self.email_recipients
        }


@dataclass
class Client:
    name: str
    ip_address: str
    port: int = 8080
    status: ClientStatus = ClientStatus.OFFLINE
    last_heartbeat: Optional[datetime] = None
    last_config_update: Optional[datetime] = None
    current_job_id: Optional[int] = None
    current_task_id: Optional[str] = None  # Currently executing task ID

    # System information fields
    cpu_info: Optional[Dict[str, Any]] = None
    memory_info: Optional[Dict[str, Any]] = None
    gpu_info: Optional[List[Dict[str, Any]]] = None
    os_info: Optional[Dict[str, Any]] = None
    disk_info: Optional[List[Dict[str, Any]]] = None
    system_summary: Optional[Dict[str, str]] = None

    def get_unique_id(self) -> str:
        """Get the unique identifier of the client (based on client name)"""
        return self.name

    def is_same_client(self, other_name: str = None, other_ip: str = None) -> bool:
        """
        Determine if this is the same client.
        Priority is given to client name comparison.
        """
        if other_name:
            return self.name == other_name
        elif other_ip:
            return self.ip_address == other_ip
        else:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'ip_address': self.ip_address,
            'port': self.port,
            'status': self.status.value,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'last_config_update': self.last_config_update.isoformat() if self.last_config_update else None,
            'current_job_id': self.current_job_id,
            'current_task_id': self.current_task_id,
            'cpu_info': self.cpu_info,
            'memory_info': self.memory_info,
            'gpu_info': self.gpu_info,
            'os_info': self.os_info,
            'disk_info': self.disk_info,
            'system_summary': self.system_summary
        }


@dataclass
class Run:
    """Represents a single run of a task on a specific client within a job"""
    id: Optional[int] = None
    job_id: int = 0
    task_id: str = ""  # Unique identifier for the task within the job
    task_name: str = ""
    task_order: int = 0
    client: str = ""  # Target client for execution
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: JobStatus = JobStatus.PENDING
    result: Optional[str] = None
    error_message: Optional[str] = None
    execution_time: Optional[float] = None  # in seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'job_id': self.job_id,
            'task_id': self.task_id,
            'task_name': self.task_name,
            'task_order': self.task_order,
            'client': self.client,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'result': self.result,
            'error_message': self.error_message,
            'execution_time': self.execution_time
        }


