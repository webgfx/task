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

class MachineStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"

@dataclass
class Task:
    id: Optional[int] = None
    name: str = ""
    command: str = ""
    schedule_time: Optional[datetime] = None
    cron_expression: Optional[str] = None
    target_machines: List[str] = None  # 支持多台机器
    commands: List[Dict[str, Any]] = None  # 预定义指令列表
    execution_order: List[int] = None  # 指令执行顺序
    status: TaskStatus = TaskStatus.PENDING
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # 为了向后兼容保留单机器字段
    target_machine: Optional[str] = None
    
    def __post_init__(self):
        if self.target_machines is None:
            self.target_machines = []
        if self.commands is None:
            self.commands = []
        if self.execution_order is None:
            self.execution_order = []
        
        # 向后兼容：如果使用了target_machine，添加到target_machines
        if self.target_machine and self.target_machine not in self.target_machines:
            self.target_machines.append(self.target_machine)
        
        # 如果只有command字段，转换为commands格式
        if self.command and not self.commands:
            self.commands = [{
                'id': 1,
                'name': 'Default Command',
                'command': self.command,
                'timeout': 300,
                'retry_count': 0
            }]
            self.execution_order = [1]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'command': self.command,  # 保持向后兼容
            'schedule_time': self.schedule_time.isoformat() if self.schedule_time else None,
            'cron_expression': self.cron_expression,
            'target_machine': self.target_machine,  # 保持向后兼容
            'target_machines': self.target_machines,
            'commands': self.commands,
            'execution_order': self.execution_order,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result': self.result,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries
        }

@dataclass
class Machine:
    name: str
    ip_address: str
    port: int = 8080
    status: MachineStatus = MachineStatus.OFFLINE
    last_heartbeat: Optional[datetime] = None
    last_config_update: Optional[datetime] = None  # 最后配置更新时间
    current_task_id: Optional[int] = None
    capabilities: List[str] = None
    
    # System information fields
    cpu_info: Optional[Dict[str, Any]] = None
    memory_info: Optional[Dict[str, Any]] = None
    gpu_info: Optional[List[Dict[str, Any]]] = None
    os_info: Optional[Dict[str, Any]] = None
    disk_info: Optional[List[Dict[str, Any]]] = None
    system_summary: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
    
    def get_unique_id(self) -> str:
        """获取机器的唯一标识（基于IP地址）"""
        return self.ip_address
    
    def is_same_machine(self, other_ip: str) -> bool:
        """判断是否为同一台机器（基于IP地址）"""
        return self.ip_address == other_ip
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'ip_address': self.ip_address,
            'port': self.port,
            'status': self.status.value,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'last_config_update': self.last_config_update.isoformat() if self.last_config_update else None,
            'current_task_id': self.current_task_id,
            'capabilities': self.capabilities,
            'cpu_info': self.cpu_info,
            'memory_info': self.memory_info,
            'gpu_info': self.gpu_info,
            'os_info': self.os_info,
            'disk_info': self.disk_info,
            'system_summary': self.system_summary
        }

@dataclass
class TaskExecution:
    id: Optional[int] = None
    task_id: int = 0
    machine_name: str = ""
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
            'machine_name': self.machine_name,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'output': self.output,
            'error_output': self.error_output,
            'exit_code': self.exit_code
        }
