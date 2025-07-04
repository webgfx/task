"""
Common data model definitions
"""
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

class TaskStatus(Enum):
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
class SubtaskDefinition:
    """Represents a subtask definition within a task"""
    name: str = ""
    target_client: str = ""  # Target client for this subtask
    order: int = 0
    args: List[Any] = None
    kwargs: Dict[str, Any] = None
    timeout: int = 300  # seconds
    retry_count: int = 0
    max_retries: int = 3
    subtask_id: Optional[str] = None  # Unique identifier for the subtask within the task
    
    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.kwargs is None:
            self.kwargs = {}
        # Generate subtask_id if not provided (format: task_order_name)
        if not self.subtask_id:
            self.subtask_id = f"{self.order}_{self.name}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'target_client': self.target_client,
            'order': self.order,
            'args': self.args,
            'kwargs': self.kwargs,
            'timeout': self.timeout,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'subtask_id': self.subtask_id
        }

@dataclass
class Task:
    id: Optional[int] = None
    name: str = ""
    command: str = ""
    schedule_time: Optional[datetime] = None
    cron_expression: Optional[str] = None
    target_clients: List[str] = None  # Support multiple clients
    commands: List[Dict[str, Any]] = None  # Predefined command list
    execution_order: List[int] = None  # Command execution order
    subtasks: List[SubtaskDefinition] = None  # New: subtask definition list
    status: TaskStatus = TaskStatus.PENDING
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Email notification settings
    send_email: bool = False  # Whether to send email notifications
    email_recipients: Optional[str] = None  # Semicolon-separated email addresses
    
    # For backward compatibility, keep single client field
    target_client: Optional[str] = None
    
    def __post_init__(self):
        if self.target_clients is None:
            self.target_clients = []
        if self.commands is None:
            self.commands = []
        if self.execution_order is None:
            self.execution_order = []
        if self.subtasks is None:
            self.subtasks = []
        
        # Backward compatibility: if target_client is used, add to target_clients
        if self.target_client and self.target_client not in self.target_clients:
            self.target_clients.append(self.target_client)
        
        # If only command field exists, convert to commands format
        if self.command and not self.commands and not self.subtasks:
            self.commands = [{
                'id': 1,
                'name': 'Default Command',
                'command': self.command,
                'timeout': 300,
                'retry_count': 0
            }]
            self.execution_order = [1]
    
    def get_all_target_clients(self) -> List[str]:
        """Get all unique target clients from subtasks and legacy fields"""
        clients = set()
        
        # Add from legacy target_clients
        clients.update(self.target_clients or [])
        
        # Add from subtasks
        for subtask in self.subtasks or []:
            if subtask.target_client:
                clients.add(subtask.target_client)
        
        # Add legacy target_client
        if self.target_client:
            clients.add(self.target_client)
        
        return list(clients)
    
    # Backward compatibility alias
    def get_all_target_clients(self) -> List[str]:
        """Deprecated: Use get_all_target_clients() instead"""
        return self.get_all_target_clients()
    
    def get_subtasks_for_client(self, client_name: str) -> List[SubtaskDefinition]:
        """Deprecated: Use get_subtasks_for_client() instead"""
        return self.get_subtasks_for_client(client_name)
    
    def get_subtasks_for_client(self, client_name: str) -> List[SubtaskDefinition]:
        """Get all subtasks assigned to a specific client"""
        return [subtask for subtask in (self.subtasks or []) 
                if subtask.target_client == client_name]
    
    def get_email_recipients_list(self) -> List[str]:
        """Get email recipients as a list, parsing semicolon-separated string"""
        if not self.email_recipients:
            return []
        
        # Split by semicolon and clean up whitespace
        recipients = [email.strip() for email in self.email_recipients.split(';')]
        
        # Filter out empty strings
        return [email for email in recipients if email]
    
    def should_send_email(self) -> bool:
        """Check if email notifications should be sent for this task"""
        return self.send_email and bool(self.get_email_recipients_list())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'command': self.command,  # Keep backward compatibility
            'schedule_time': self.schedule_time.isoformat() if self.schedule_time else None,
            'cron_expression': self.cron_expression,
            'target_client': self.target_client,  # Keep backward compatibility
            'target_clients': self.target_clients,
            'commands': self.commands,
            'execution_order': self.execution_order,
            'subtasks': [subtask.to_dict() for subtask in (self.subtasks or [])],
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
    last_config_update: Optional[datetime] = None  # Last configuration update time
    current_task_id: Optional[int] = None
    current_subtask_id: Optional[str] = None  # Currently executing subtask ID
    
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
        Determine if this is the same client
        Priority is given to client name comparison, with backward compatibility for IP address comparison
        
        Args:
            other_name: Other client's name
            other_ip: Other client's IP address (backward compatibility)
        """
        if other_name:
            return self.name == other_name
        elif other_ip:
            # Backward compatibility: compare using IP address
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
            'current_task_id': self.current_task_id,
            'current_subtask_id': self.current_subtask_id,
            'cpu_info': self.cpu_info,
            'memory_info': self.memory_info,
            'gpu_info': self.gpu_info,
            'os_info': self.os_info,
            'disk_info': self.disk_info,
            'system_summary': self.system_summary
        }


@dataclass
class SubtaskExecution:
    """Represents the execution of a single subtask within a task"""
    id: Optional[int] = None
    task_id: int = 0
    subtask_id: str = ""  # Unique identifier for the subtask within the task
    subtask_name: str = ""
    subtask_order: int = 0
    target_client: str = ""  # Target client for execution
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error_message: Optional[str] = None
    execution_time: Optional[float] = None  # in seconds
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'task_id': self.task_id,
            'subtask_id': self.subtask_id,
            'subtask_name': self.subtask_name,
            'subtask_order': self.subtask_order,
            'target_client': self.target_client,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'result': self.result,
            'error_message': self.error_message,
            'execution_time': self.execution_time
        }

@dataclass
class TaskExecution:
    id: Optional[int] = None
    task_id: int = 0
    client_name: str = ""  # Client name
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    output: Optional[str] = None
    error_output: Optional[str] = None
    exit_code: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'task_id': self.task_id,
            'client_name': self.client_name,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'output': self.output,
            'error_output': self.error_output,
            'exit_code': self.exit_code
        }

