"""
Database operations module
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from common.models import Task, Machine, TaskExecution, TaskStatus, MachineStatus
from common.utils import parse_datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create tasks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    command TEXT NOT NULL,
                    target_machines TEXT DEFAULT '[]',
                    commands TEXT DEFAULT '[]',
                    execution_order TEXT DEFAULT '[]',
                    schedule_time TEXT,
                    cron_expression TEXT,
                    target_machine TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    started_at TEXT,
                    completed_at TEXT,
                    result TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3
                )
            ''')
            
            # Create machines table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS machines (
                    ip_address TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    port INTEGER DEFAULT 8080,
                    status TEXT DEFAULT 'offline',
                    last_heartbeat TEXT,
                    last_config_update TEXT,
                    current_task_id INTEGER,
                    capabilities TEXT DEFAULT '[]',
                    cpu_info TEXT,
                    memory_info TEXT,
                    gpu_info TEXT,
                    os_info TEXT,
                    disk_info TEXT,
                    system_summary TEXT
                )
            ''')
            
            # Migrate existing tables
            self._migrate_tasks_table(cursor)
            self._migrate_machines_table(cursor)
            
            # Create task execution table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    machine_name TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    status TEXT DEFAULT 'pending',
                    output TEXT,
                    error_output TEXT,
                    exit_code INTEGER,
                    FOREIGN KEY (task_id) REFERENCES tasks (id),
                    FOREIGN KEY (machine_name) REFERENCES machines (name)
                )
            ''')
            
            # Create client communication logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS client_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    client_ip TEXT NOT NULL,
                    client_name TEXT,
                    action TEXT NOT NULL,
                    message TEXT,
                    data TEXT,
                    level TEXT DEFAULT 'INFO'
                )
            ''')
            
            conn.commit()
            logger.info("Database initialization completed")
    
    def _migrate_tasks_table(self, cursor):
        """Migrate tasks table to add new columns"""
        try:
            # Check if new columns exist
            cursor.execute("PRAGMA table_info(tasks)")
            columns = [column[1] for column in cursor.fetchall()]
            
            new_columns = [
                ('target_machines', 'TEXT DEFAULT \'[]\''),
                ('commands', 'TEXT DEFAULT \'[]\''),
                ('execution_order', 'TEXT DEFAULT \'[]\'')
            ]
            
            for column_name, column_def in new_columns:
                if column_name not in columns:
                    cursor.execute(f"ALTER TABLE tasks ADD COLUMN {column_name} {column_def}")
                    logger.info(f"Added column {column_name} to tasks table")
                    
        except Exception as e:
            logger.warning(f"Tasks table migration warning: {e}")
    
    def _migrate_machines_table(self, cursor):
        """Migrate machines table to add system information columns and change primary key"""
        try:
            # Check if system info columns exist
            cursor.execute("PRAGMA table_info(machines)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Check if we need to recreate table for primary key change
            primary_key_columns = [col for col in cursor.fetchall() if col[5] == 1]  # pk column
            
            new_columns = [
                ('last_config_update', 'TEXT'),
                ('cpu_info', 'TEXT'),
                ('memory_info', 'TEXT'),
                ('gpu_info', 'TEXT'),
                ('os_info', 'TEXT'),
                ('disk_info', 'TEXT'),
                ('system_summary', 'TEXT')
            ]
            
            for column_name, column_type in new_columns:
                if column_name not in columns:
                    cursor.execute(f"ALTER TABLE machines ADD COLUMN {column_name} {column_type}")
                    logger.info(f"Added column {column_name} to machines table")
                    
        except Exception as e:
            logger.warning(f"Machines table migration warning: {e}")
            
    def _migrate_machines_primary_key(self, cursor):
        """Migration: change machines table primary key from name to ip_address"""
        try:
            # Create new table with ip_address as primary key
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS machines_new (
                    ip_address TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    port INTEGER DEFAULT 8080,
                    status TEXT DEFAULT 'offline',
                    last_heartbeat TEXT,
                    last_config_update TEXT,
                    current_task_id INTEGER,
                    capabilities TEXT DEFAULT '[]',
                    cpu_info TEXT,
                    memory_info TEXT,
                    gpu_info TEXT,
                    os_info TEXT,
                    disk_info TEXT,
                    system_summary TEXT
                )
            ''')
            
            # Copy data from old table
            cursor.execute('''
                INSERT OR IGNORE INTO machines_new 
                SELECT ip_address, name, port, status, last_heartbeat, 
                       last_config_update, current_task_id, capabilities,
                       cpu_info, memory_info, gpu_info, os_info, disk_info, system_summary
                FROM machines
            ''')
            
            # Drop old table and rename new table
            cursor.execute('DROP TABLE machines')
            cursor.execute('ALTER TABLE machines_new RENAME TO machines')
            
            logger.info("Successfully migrated machines table to use ip_address as primary key")
            
        except Exception as e:
            logger.warning(f"Machines table primary key migration warning: {e}")
    
    @contextmanager
    def get_connection(self):
        """Get database connection context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Make results accessible by column name
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database operation error: {e}")
            raise
        finally:
            conn.close()
    
    # Task-related operations
    def create_task(self, task: Task) -> int:
        """Create new task"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tasks (name, command, target_machines, commands, execution_order,
                                 schedule_time, cron_expression, target_machine, status, 
                                 created_at, max_retries)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task.name, task.command, 
                json.dumps(task.target_machines) if task.target_machines else '[]',
                json.dumps(task.commands) if task.commands else '[]',
                json.dumps(task.execution_order) if task.execution_order else '[]',
                task.schedule_time.isoformat() if task.schedule_time else None,
                task.cron_expression, task.target_machine, task.status.value,
                datetime.now().isoformat(), task.max_retries
            ))
            task_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Create Task: {task.name} (ID: {task_id})")
            return task_id
    
    def get_task(self, task_id: int) -> Optional[Task]:
        """Get task by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_task(row)
            return None
    
    def get_all_tasks(self) -> List[Task]:
        """Get all tasks"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks ORDER BY created_at DESC')
            rows = cursor.fetchall()
            return [self._row_to_task(row) for row in rows]
    
    def update_task(self, task: Task):
        """Update task"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE tasks SET name=?, command=?, target_machines=?, commands=?, 
                               execution_order=?, schedule_time=?, cron_expression=?,
                               target_machine=?, status=?, started_at=?, completed_at=?,
                               result=?, error_message=?, retry_count=?, max_retries=?
                WHERE id=?
            ''', (
                task.name, task.command,
                json.dumps(task.target_machines) if task.target_machines else '[]',
                json.dumps(task.commands) if task.commands else '[]',
                json.dumps(task.execution_order) if task.execution_order else '[]',
                task.schedule_time.isoformat() if task.schedule_time else None,
                task.cron_expression, task.target_machine, task.status.value,
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                task.result, task.error_message, task.retry_count, task.max_retries,
                task.id
            ))
            conn.commit()
    
    def delete_task(self, task_id: int):
        """Delete task"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            conn.commit()
            logger.info(f"Deleted task ID: {task_id}")
    
    def get_pending_tasks(self) -> List[Task]:
        """Get pending tasks"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM tasks 
                WHERE status = 'pending' 
                ORDER BY created_at ASC
            ''')
            rows = cursor.fetchall()
            return [self._row_to_task(row) for row in rows]
    
    # Machine-related operations
    def register_machine(self, machine: Machine):
        """Register or update machine with system information (using IP as unique identifier)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO machines 
                (ip_address, name, port, status, last_heartbeat, last_config_update, capabilities,
                 cpu_info, memory_info, gpu_info, os_info, disk_info, system_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                machine.ip_address, machine.name, machine.port,
                machine.status.value, datetime.now().isoformat(), datetime.now().isoformat(),
                json.dumps(machine.capabilities) if machine.capabilities else '[]',
                json.dumps(machine.cpu_info) if machine.cpu_info else None,
                json.dumps(machine.memory_info) if machine.memory_info else None,
                json.dumps(machine.gpu_info) if machine.gpu_info else None,
                json.dumps(machine.os_info) if machine.os_info else None,
                json.dumps(machine.disk_info) if machine.disk_info else None,
                json.dumps(machine.system_summary) if machine.system_summary else None
            ))
            conn.commit()
            logger.info(f"Registered machine: {machine.name} ({machine.ip_address})")
            if machine.system_summary:
                logger.info(f"  System: {machine.system_summary.get('os', 'Unknown')}")
                logger.info(f"  CPU: {machine.system_summary.get('cpu', 'Unknown')}")
                logger.info(f"  Memory: {machine.system_summary.get('memory', 'Unknown')}")
    
    def update_machine_heartbeat(self, ip_address: str, status: MachineStatus = None):
        """Update machine heartbeat (using IP as identifier)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute('''
                    UPDATE machines SET last_heartbeat = ?, status = ?
                    WHERE ip_address = ?
                ''', (datetime.now().isoformat(), status.value, ip_address))
            else:
                cursor.execute('''
                    UPDATE machines SET last_heartbeat = ?
                    WHERE ip_address = ?
                ''', (datetime.now().isoformat(), ip_address))
            conn.commit()
    
    def update_machine_config(self, machine: Machine):
        """Update machine configuration information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE machines SET 
                    name=?, port=?, last_config_update=?, capabilities=?,
                    cpu_info=?, memory_info=?, gpu_info=?, os_info=?, 
                    disk_info=?, system_summary=?
                WHERE ip_address=?
            ''', (
                machine.name, machine.port, datetime.now().isoformat(),
                json.dumps(machine.capabilities) if machine.capabilities else '[]',
                json.dumps(machine.cpu_info) if machine.cpu_info else None,
                json.dumps(machine.memory_info) if machine.memory_info else None,
                json.dumps(machine.gpu_info) if machine.gpu_info else None,
                json.dumps(machine.os_info) if machine.os_info else None,
                json.dumps(machine.disk_info) if machine.disk_info else None,
                json.dumps(machine.system_summary) if machine.system_summary else None,
                machine.ip_address
            ))
            conn.commit()
            logger.info(f"Updated machine config: {machine.name} ({machine.ip_address})")
    
    def get_machine_by_ip(self, ip_address: str) -> Optional[Machine]:
        """Get machine by IP address"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM machines WHERE ip_address = ?', (ip_address,))
            row = cursor.fetchone()
            if row:
                return self._row_to_machine(row)
            return None
    
    def get_all_machines(self) -> List[Machine]:
        """Get all machines"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM machines')
            rows = cursor.fetchall()
            return [self._row_to_machine(row) for row in rows]
    
    def get_online_machines(self) -> List[Machine]:
        """Get Online Machines"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM machines 
                WHERE status = 'online'
                ORDER BY last_heartbeat DESC
            ''')
            rows = cursor.fetchall()
            return [self._row_to_machine(row) for row in rows]
    
    # Task execution related operations
    def create_task_execution(self, execution: TaskExecution) -> int:
        """Create task execution record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO task_executions 
                (task_id, machine_name, started_at, status)
                VALUES (?, ?, ?, ?)
            ''', (
                execution.task_id, execution.machine_name,
                datetime.now().isoformat(), execution.status.value
            ))
            execution_id = cursor.lastrowid
            conn.commit()
            return execution_id
    
    def update_task_execution(self, execution: TaskExecution):
        """Update task execution record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE task_executions 
                SET completed_at=?, status=?, output=?, error_output=?, exit_code=?
                WHERE id=?
            ''', (
                execution.completed_at.isoformat() if execution.completed_at else None,
                execution.status.value, execution.output, execution.error_output,
                execution.exit_code, execution.id
            ))
            conn.commit()
    
    def get_task_executions(self, task_id: int) -> List[TaskExecution]:
        """Get all execution records for a task"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM task_executions 
                WHERE task_id = ? 
                ORDER BY started_at DESC
            ''', (task_id,))
            rows = cursor.fetchall()
            return [self._row_to_execution(row) for row in rows]
    
    # Helper methods
    def _row_to_task(self, row) -> Task:
        """Convert database row to Task object"""
        # Parse JSON fields safely
        def safe_json_parse(field_value, default=None):
            try:
                return json.loads(field_value) if field_value else default
            except:
                return default or []
        
        target_machines = safe_json_parse(row.get('target_machines'), [])
        commands = safe_json_parse(row.get('commands'), [])
        execution_order = safe_json_parse(row.get('execution_order'), [])
        
        task = Task(
            id=row['id'],
            name=row['name'],
            command=row['command'],
            target_machines=target_machines,
            commands=commands,
            execution_order=execution_order,
            schedule_time=parse_datetime(row['schedule_time']),
            cron_expression=row['cron_expression'],
            target_machine=row['target_machine'],
            status=TaskStatus(row['status']),
            created_at=parse_datetime(row['created_at']),
            started_at=parse_datetime(row['started_at']),
            completed_at=parse_datetime(row['completed_at']),
            result=row['result'],
            error_message=row['error_message'],
            retry_count=row['retry_count'],
            max_retries=row['max_retries']
        )
        
        return task
    
    def _row_to_machine(self, row) -> Machine:
        """Convert database row to Machine object"""
        try:
            capabilities = json.loads(row['capabilities']) if row['capabilities'] else []
        except:
            capabilities = []
        
        # Parse system information JSON fields
        def safe_json_parse(field_value):
            try:
                return json.loads(field_value) if field_value else None
            except:
                return None
        
        return Machine(
            name=row['name'],
            ip_address=row['ip_address'],
            port=row['port'],
            status=MachineStatus(row['status']),
            last_heartbeat=parse_datetime(row['last_heartbeat']),
            last_config_update=parse_datetime(row.get('last_config_update')),
            current_task_id=row['current_task_id'],
            capabilities=capabilities,
            cpu_info=safe_json_parse(row.get('cpu_info')),
            memory_info=safe_json_parse(row.get('memory_info')),
            gpu_info=safe_json_parse(row.get('gpu_info')),
            os_info=safe_json_parse(row.get('os_info')),
            disk_info=safe_json_parse(row.get('disk_info')),
            system_summary=safe_json_parse(row.get('system_summary'))
        )
    
    # Client Communication Logs
    def log_client_action(self, client_ip: str, client_name: str, action: str, 
                         message: str = None, data: Any = None, level: str = 'INFO'):
        """Log client communication action"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO client_logs 
                (client_ip, client_name, action, message, data, level)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                client_ip,
                client_name,
                action,
                message,
                json.dumps(data) if data else None,
                level
            ))
            conn.commit()
            logger.debug(f"Logged client action: {client_ip} - {action}")
    
    def get_client_logs(self, limit: int = 100, client_ip: str = None) -> List[Dict[str, Any]]:
        """Get client communication logs"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if client_ip:
                cursor.execute('''
                    SELECT * FROM client_logs 
                    WHERE client_ip = ?
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (client_ip, limit))
            else:
                cursor.execute('''
                    SELECT * FROM client_logs 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            logs = []
            
            for row in rows:
                log_entry = {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'client_ip': row['client_ip'],
                    'client_name': row['client_name'],
                    'action': row['action'],
                    'message': row['message'],
                    'data': json.loads(row['data']) if row['data'] else None,
                    'level': row['level']
                }
                logs.append(log_entry)
            
            return logs
    
    def clear_client_logs(self, older_than_days: int = 30):
        """Clear old client logs"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM client_logs 
                WHERE timestamp < datetime('now', '-{} days')
            '''.format(older_than_days))
            deleted_count = cursor.rowcount
            conn.commit()
            logger.info(f"Cleared {deleted_count} old client log entries")
            return deleted_count
    
    def _row_to_execution(self, row) -> TaskExecution:
        """Convert database row to TaskExecution object"""
        return TaskExecution(
            id=row['id'],
            task_id=row['task_id'],
            machine_name=row['machine_name'],
            started_at=parse_datetime(row['started_at']),
            completed_at=parse_datetime(row['completed_at']),
            status=TaskStatus(row['status']),
            output=row['output'],
            error_output=row['error_output'],
            exit_code=row['exit_code']
        )
