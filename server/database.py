"""
Database operations module
"""
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from common.models import Task, Client, TaskStatus, ClientStatus, SubtaskExecution, SubtaskDefinition
from common.utils import parse_datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str, socketio=None):
        self.db_path = db_path
        self.socketio = socketio
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
                    clients TEXT DEFAULT '[]',
                    subtasks TEXT DEFAULT '[]',
                    execution_order TEXT DEFAULT '[]',
                    schedule_time TEXT,
                    cron_expression TEXT,
                    client TEXT,
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

            # Create clients table (using client name as primary key)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS clients (
                    name TEXT PRIMARY KEY,
                    ip_address TEXT NOT NULL,
                    port INTEGER DEFAULT 8080,
                    status TEXT DEFAULT 'offline',
                    last_heartbeat TEXT,
                    last_config_update TEXT,
                    current_task_id INTEGER,
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
            self._migrate_email_notification_fields(cursor)
            self._migrate_clients_table(cursor)
            self._migrate_clients_to_name_primary_key(cursor)
            self._migrate_clients_to_clients(cursor)
            self._migrate_machine_to_client_terminology(cursor)
            self._migrate_remove_task_executions_table(cursor)

            # Create subtask execution table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    subtask_name TEXT NOT NULL,
                    subtask_order INTEGER NOT NULL,
                    client TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    status TEXT DEFAULT 'pending',
                    result TEXT,
                    error_message TEXT,
                    execution_time REAL,
                    FOREIGN KEY (task_id) REFERENCES tasks (id)
                )
            ''')

            # Run migrations that depend on executions table
            self._migrate_subtask_ids(cursor)

            # Add subtasks column to tasks table if it doesn't exist
            cursor.execute("PRAGMA table_info(tasks)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'subtasks' not in columns:
                cursor.execute("ALTER TABLE tasks ADD COLUMN subtasks TEXT DEFAULT '[]'")
                logger.info("Added subtasks column to tasks table")

            # Create client communication logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
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
                ('clients', 'TEXT DEFAULT \'[]\''),
                ('subtasks', 'TEXT DEFAULT \'[]\''),
                ('execution_order', 'TEXT DEFAULT \'[]\'')
            ]

            for column_name, column_def in new_columns:
                if column_name not in columns:
                    cursor.execute(f"ALTER TABLE tasks ADD COLUMN {column_name} {column_def}")
                    logger.info(f"Added column {column_name} to tasks table")

        except Exception as e:
            logger.warning(f"Tasks table migration warning: {e}")

    def _migrate_email_notification_fields(self, cursor):
        """Migrate tasks table to add email notification fields"""
        try:
            # Check if email notification columns exist
            cursor.execute("PRAGMA table_info(tasks)")
            columns = [column[1] for column in cursor.fetchall()]

            email_columns = [
                ('send_email', 'INTEGER DEFAULT 0'),  # SQLite uses INTEGER for boolean
                ('email_recipients', 'TEXT')
            ]

            for column_name, column_def in email_columns:
                if column_name not in columns:
                    cursor.execute(f"ALTER TABLE tasks ADD COLUMN {column_name} {column_def}")
                    logger.info(f"Added email notification column {column_name} to tasks table")

        except Exception as e:
            logger.warning(f"Email notification fields migration warning: {e}")

    def _migrate_clients_table(self, cursor):
        """Migrate clients table to add system information columns and change primary key"""
        try:
            # Check if clients table exists and if system info columns exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clients'")
            clients_exists = cursor.fetchone() is not None
            
            if clients_exists:
                cursor.execute("PRAGMA table_info(clients)")
                columns = [column[1] for column in cursor.fetchall()]

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
                        cursor.execute(f"ALTER TABLE clients ADD COLUMN {column_name} {column_type}")
                        logger.info(f"Added column {column_name} to clients table")

        except Exception as e:
            logger.warning(f"clients table migration warning: {e}")

    def _migrate_clients_to_name_primary_key(self, cursor):
        """Migration: change clients table primary key from ip_address to name"""
        try:
            # Check if clients table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clients'")
            clients_exists = cursor.fetchone() is not None
            
            if not clients_exists:
                logger.info("clients table doesn't exist - no primary key migration needed")
                return
                
            # Check if table exists and what its current structure is
            cursor.execute("PRAGMA table_info(clients)")
            columns_info = cursor.fetchall()
            
            # Check if the primary key is currently ip_address
            primary_key_columns = [col for col in columns_info if col[5] == 1]  # pk column
            
            if primary_key_columns and primary_key_columns[0][1] == 'ip_address':
                logger.info("Migrating clients table to use name as primary key...")
                
                # Create new table with name as primary key
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS clients_new (
                        name TEXT PRIMARY KEY,
                        ip_address TEXT NOT NULL,
                        port INTEGER DEFAULT 8080,
                        status TEXT DEFAULT 'offline',
                        last_heartbeat TEXT,
                        last_config_update TEXT,
                        current_task_id INTEGER,
                        cpu_info TEXT,
                        memory_info TEXT,
                        gpu_info TEXT,
                        os_info TEXT,
                        disk_info TEXT,
                        system_summary TEXT
                    )
                ''')
                
                # Copy data from old table, handling potential duplicates by name
                cursor.execute('''
                    INSERT OR REPLACE INTO clients_new
                    SELECT name, ip_address, port, status, last_heartbeat,
                           last_config_update, current_task_id,
                           cpu_info, memory_info, gpu_info, os_info, disk_info, system_summary
                    FROM clients
                    WHERE name IS NOT NULL AND name != ''
                ''')
                
                # Drop old table and rename new table
                cursor.execute('DROP TABLE clients')
                cursor.execute('ALTER TABLE clients_new RENAME TO clients')
                
                logger.info("Successfully migrated clients table to use name as primary key")
            else:
                logger.info("clients table already uses name as primary key")
                
        except Exception as e:
            logger.warning(f"clients table primary key migration warning: {e}")

    def _migrate_clients_primary_key(self, cursor):
        """Legacy migration function - kept for backward compatibility"""
        # This function is now handled by _migrate_clients_to_name_primary_key
        pass

    def _migrate_clients_to_clients(self, cursor):
        """Migration: rename machines table to clients (if it exists)"""
        try:
            # Check if machines table exists (old table name)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='machines'")
            machines_exists = cursor.fetchone() is not None
            
            # Check if clients table exists (new table name)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clients'")
            clients_exists = cursor.fetchone() is not None
            
            if machines_exists and clients_exists:
                logger.info("Both machines and clients tables exist, copying data from machines to clients...")
                
                # Copy data from machines to clients, mapping columns correctly
                cursor.execute('''
                    INSERT OR REPLACE INTO clients
                    (name, ip_address, port, status, last_heartbeat, last_config_update,
                     current_task_id, cpu_info, memory_info, gpu_info, os_info, disk_info, system_summary)
                    SELECT name, ip_address, port, status, last_heartbeat, last_config_update,
                           current_task_id, cpu_info, memory_info, gpu_info, os_info, disk_info, system_summary
                    FROM machines
                ''')
                
                # Check how many records were copied
                cursor.execute("SELECT COUNT(*) FROM clients")
                clients_count = cursor.fetchone()[0]
                
                # Drop the old machines table
                cursor.execute('DROP TABLE machines')
                
                logger.info(f"Successfully migrated {clients_count} records from machines to clients and removed machines table")
                
            elif machines_exists and not clients_exists:
                logger.info("Migrating machines table to clients table...")
                
                # Rename machines table to clients
                cursor.execute('ALTER TABLE machines RENAME TO clients')
                
                logger.info("Successfully migrated machines table to clients table")
            else:
                logger.info("Clients table already exists or machines table doesn't exist - no migration needed")
                
        except Exception as e:
            logger.warning(f"clients to clients table migration warning: {e}")

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
                INSERT INTO tasks (name, command, clients, subtasks, execution_order,
                                 subtasks, schedule_time, cron_expression, client, status,
                                 created_at, max_retries, send_email, email_recipients)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task.name, task.command,
                json.dumps(task.clients) if task.clients else '[]',
                json.dumps(task.subtasks) if task.subtasks else '[]',
                json.dumps(task.execution_order) if task.execution_order else '[]',
                json.dumps([s.to_dict() for s in task.subtasks]) if task.subtasks else '[]',
                task.schedule_time.isoformat() if task.schedule_time else None,
                task.cron_expression, task.client, task.status.value,
                datetime.now().isoformat(), task.max_retries,
                1 if task.send_email else 0,  # Convert boolean to integer for SQLite
                task.email_recipients
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
                UPDATE tasks SET name=?, command=?, clients=?, subtasks=?,
                               execution_order=?, subtasks=?, schedule_time=?, cron_expression=?,
                               client=?, status=?, started_at=?, completed_at=?,
                               result=?, error_message=?, retry_count=?, max_retries=?,
                               send_email=?, email_recipients=?
                WHERE id=?
            ''', (
                task.name, task.command,
                json.dumps(task.clients) if task.clients else '[]',
                json.dumps(task.subtasks) if task.subtasks else '[]',
                json.dumps(task.execution_order) if task.execution_order else '[]',
                json.dumps([s.to_dict() for s in task.subtasks]) if task.subtasks else '[]',
                task.schedule_time.isoformat() if task.schedule_time else None,
                task.cron_expression, task.client, task.status.value,
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                task.result, task.error_message, task.retry_count, task.max_retries,
                1 if task.send_email else 0,  # Convert boolean to integer
                task.email_recipients,
                task.id
            ))
            conn.commit()

    def delete_task(self, task_id: int):
        """Delete task and all related execution records"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # First, get task info for logging
            cursor.execute('SELECT name FROM tasks WHERE id = ?', (task_id,))
            task_row = cursor.fetchone()
            task_name = task_row[0] if task_row else f"ID:{task_id}"
            
            # Delete subtask executions first (child records)
            cursor.execute('DELETE FROM executions WHERE task_id = ?', (task_id,))
            subtask_deleted = cursor.rowcount
            
            # Finally delete the task itself (parent record)
            cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            task_deleted = cursor.rowcount
            
            conn.commit()
            
            if task_deleted > 0:
                logger.info(f"Deleted task '{task_name}' (ID: {task_id}) with {subtask_deleted} subtask executions")
                
                # Broadcast task deletion via WebSocket if available
                if self.socketio:
                    self.socketio.emit('task_deleted', {
                        'task_id': task_id,
                        'task_name': task_name,
                        'subtask_records_deleted': subtask_deleted
                    })
                
                return True
            else:
                logger.warning(f"Task with ID {task_id} not found for deletion")
                return False

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

    # Client-related operations
    def register_client(self, client: Client):
        """Register or update client with system information (using client name as unique identifier)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Validate client name uniqueness
            if not self._validate_client_name_uniqueness(client.name, client.ip_address):
                raise ValueError(f"Client name '{client.name}' conflicts with existing client on different IP")
            
            cursor.execute('''
                INSERT OR REPLACE INTO clients
                (name, ip_address, port, status, last_heartbeat, last_config_update, current_task_id, current_subtask_id,
                 cpu_info, memory_info, gpu_info, os_info, disk_info, system_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                client.name, client.ip_address, client.port,
                client.status.value, datetime.now().isoformat(), datetime.now().isoformat(),
                client.current_task_id, client.current_subtask_id,
                json.dumps(client.cpu_info) if client.cpu_info else None,
                json.dumps(client.memory_info) if client.memory_info else None,
                json.dumps(client.gpu_info) if client.gpu_info else None,
                json.dumps(client.os_info) if client.os_info else None,
                json.dumps(client.disk_info) if client.disk_info else None,
                json.dumps(client.system_summary) if client.system_summary else None
            ))
            conn.commit()
            logger.info(f"Registered client: {client.name} ({client.ip_address})")
            if client.system_summary:
                logger.info(f"  System: {client.system_summary.get('os', 'Unknown')}")
                logger.info(f"  CPU: {client.system_summary.get('cpu', 'Unknown')}")
                logger.info(f"  Memory: {client.system_summary.get('memory', 'Unknown')}")

    def client_name_exists(self, client_name: str) -> bool:
        """
        Check if client name already exists
        
        Args:
            client_name: Client name to check
            
        Returns:
            True if exists, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM clients WHERE name = ?', (client_name,))
            return cursor.fetchone() is not None

    def get_client_names(self) -> List[str]:
        """
        Get all client names list
        
        Returns:
            List of client names
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM clients ORDER BY name')
            rows = cursor.fetchall()
            return [row[0] for row in rows]

    def get_online_client_names(self) -> List[str]:
        """
        Get all online client names list
        
        Returns:
            List of online client names
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name FROM clients
                WHERE status = 'online'
                ORDER BY last_heartbeat DESC
            ''')
            rows = cursor.fetchall()
            return [row[0] for row in rows]

    def _validate_client_name_uniqueness(self, client_name: str, client_ip: str) -> bool:
        """
        Validate client name uniqueness
        Ensure the same client name is not assigned to different IP addresses
        
        Args:
            client_name: Client name to validate
            client_ip: Client IP address
            
        Returns:
            True if unique or belongs to same IP, False if conflicts
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT ip_address FROM clients WHERE name = ?', (client_name,))
            result = cursor.fetchone()
            
            if result is None:
                # New client name, allow registration
                return True
            
            # Check if it's the same IP address
            existing_ip = result[0]
            return existing_ip == client_ip

    def update_client_heartbeat(self, ip_address: str, status: ClientStatus = None):
        """Update client heartbeat (using IP as identifier)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute('''
                    UPDATE clients SET last_heartbeat = ?, status = ?
                    WHERE ip_address = ?
                ''', (datetime.now().isoformat(), status.value, ip_address))
            else:
                cursor.execute('''
                    UPDATE clients SET last_heartbeat = ?
                    WHERE ip_address = ?
                ''', (datetime.now().isoformat(), ip_address))
            conn.commit()

    def update_client_heartbeat_by_name(self, client_name: str, status: ClientStatus = None):
        """Update client heartbeat (using client name as identifier)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute('''
                    UPDATE clients SET last_heartbeat = ?, status = ?
                    WHERE name = ?
                ''', (datetime.now().isoformat(), status.value, client_name))
            else:
                cursor.execute('''
                    UPDATE clients SET last_heartbeat = ?
                    WHERE name = ?
                ''', (datetime.now().isoformat(), client_name))
            conn.commit()

    def update_client_config(self, client: Client):
        """Update client configuration information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE clients SET
                    ip_address=?, port=?, last_config_update=?,
                    cpu_info=?, memory_info=?, gpu_info=?, os_info=?,
                    disk_info=?, system_summary=?
                WHERE name=?
            ''', (
                client.ip_address, client.port, datetime.now().isoformat(),
                json.dumps(client.cpu_info) if client.cpu_info else None,
                json.dumps(client.memory_info) if client.memory_info else None,
                json.dumps(client.gpu_info) if client.gpu_info else None,
                json.dumps(client.os_info) if client.os_info else None,
                json.dumps(client.disk_info) if client.disk_info else None,
                json.dumps(client.system_summary) if client.system_summary else None,
                client.name
            ))
            conn.commit()
            logger.info(f"Updated client config: {client.name} ({client.ip_address})")

    def get_client_by_ip(self, ip_address: str) -> Optional[Client]:
        """Get client by IP address (for backward compatibility, not recommended as primary method)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM clients WHERE ip_address = ?', (ip_address,))
            row = cursor.fetchone()
            if row:
                return self._row_to_client(row)
            return None

    def get_client_by_name(self, client_name: str) -> Optional[Client]:
        """Get client by name (primary method - client names are unique)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM clients WHERE name = ?', (client_name,))
            row = cursor.fetchone()
            if row:
                return self._row_to_client(row)
            return None

    def get_all_clients(self) -> List[Client]:
        """Get all clients with computed status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM clients')
            rows = cursor.fetchall()
            clients = [self._row_to_client(row) for row in rows]
            
            # Update status based on heartbeat timing and current task
            current_time = datetime.now()
            from common.config import Config
            offline_threshold = timedelta(seconds=Config.CLIENT_TIMEOUT)  # Use configured timeout for offline detection
            
            for client in clients:
                if client.last_heartbeat is None:
                    # Never sent heartbeat, mark as offline
                    client.status = ClientStatus.OFFLINE
                else:
                    time_since_heartbeat = current_time - client.last_heartbeat
                    if time_since_heartbeat > offline_threshold:
                        # No recent heartbeat, mark as offline
                        client.status = ClientStatus.OFFLINE
                    elif client.current_task_id is not None:
                        # Has recent heartbeat and is executing a task, mark as busy
                        client.status = ClientStatus.BUSY
                    else:
                        # Has recent heartbeat but no current task, mark as free (online)
                        client.status = ClientStatus.ONLINE
            
            return clients

    def get_online_clients(self) -> List[Client]:
        """Get clients that are free (not busy)"""
        all_clients = self.get_all_clients()  # This computes the real-time status
        # Return only clients that are FREE (online status), exclude BUSY and OFFLINE
        return [client for client in all_clients if client.status == ClientStatus.ONLINE]

    def get_available_clients(self) -> List[Client]:
        """Get clients that are available for new tasks (alias for get_free_clients)"""
        return self.get_online_clients()

    def get_free_clients(self) -> List[Client]:
        """Get clients that are free (available for new tasks)"""
        return self.get_online_clients()

    def get_busy_clients(self) -> List[Client]:
        """Get clients that are currently busy executing tasks"""
        all_clients = self.get_all_clients()  # This computes the real-time status
        return [client for client in all_clients if client.status == ClientStatus.BUSY]

    def get_offline_clients(self) -> List[Client]:
        """Get clients that are offline"""
        all_clients = self.get_all_clients()  # This computes the real-time status
        return [client for client in all_clients if client.status == ClientStatus.OFFLINE]

    # Subtask execution related operations
    def create_subtask_execution(self, execution: SubtaskExecution) -> int:
        """Create subtask execution record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO executions
                (task_id, subtask_name, subtask_order, client, started_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                execution.task_id, execution.subtask_name, execution.subtask_order,
                execution.client, datetime.now().isoformat(), execution.status.value
            ))
            execution_id = cursor.lastrowid
            conn.commit()
            return execution_id

    def update_subtask_execution(self, execution: SubtaskExecution):
        """Update subtask execution record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE executions
                SET completed_at=?, status=?, result=?, error_message=?, execution_time=?
                WHERE id=?
            ''', (
                execution.completed_at.isoformat() if execution.completed_at else None,
                execution.status.value, execution.result, execution.error_message,
                execution.execution_time, execution.id
            ))
            conn.commit()

    def get_executions(self, task_id: int) -> List[SubtaskExecution]:
        """Get all subtask execution records for a task"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM executions
                WHERE task_id = ?
                ORDER BY subtask_order ASC, started_at ASC
            ''', (task_id,))
            rows = cursor.fetchall()
            return [self._row_to_subtask_execution(row) for row in rows]

    def get_executions_by_client(self, task_id: int, client_name: str) -> List[SubtaskExecution]:
        """Get subtask execution records for a specific task and client"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM executions
                WHERE task_id = ? AND client = ?
                ORDER BY subtask_order ASC, started_at ASC
            ''', (task_id, client_name))
            rows = cursor.fetchall()
            return [self._row_to_subtask_execution(row) for row in rows]

    # Helper methods
    def _row_to_task(self, row) -> Task:
        """Convert database row to Task object"""
        # Parse JSON fields safely
        def safe_json_parse(field_value, default=None):
            try:
                return json.loads(field_value) if field_value else default
            except:
                return default or []

        # Helper function to safely get row values
        def safe_get(key, default=None):
            try:
                return row[key]
            except (KeyError, IndexError):
                return default

        clients = safe_json_parse(safe_get('clients'), [])
        subtasks_legacy = safe_json_parse(safe_get('subtasks'), [])
        execution_order = safe_json_parse(safe_get('execution_order'), [])

        # Parse subtasks
        subtasks_data = safe_json_parse(safe_get('subtasks'), [])
        subtasks = []
        for subtask_dict in subtasks_data:
            try:
                subtask = SubtaskDefinition(
                    name=subtask_dict.get('name', ''),
                    client=subtask_dict.get('client', ''),
                    order=subtask_dict.get('order', 0),
                    args=subtask_dict.get('args', []),
                    kwargs=subtask_dict.get('kwargs', {}),
                    timeout=subtask_dict.get('timeout', 300),
                    retry_count=subtask_dict.get('retry_count', 0),
                    max_retries=subtask_dict.get('max_retries', 3),
                    subtask_id=subtask_dict.get('subtask_id', None)  # Preserve existing subtask ID
                )
                subtasks.append(subtask)
            except Exception as e:
                logger.warning(f"Failed to parse subtask: {e}")

        task = Task(
            id=row['id'],
            name=row['name'],
            command=row['command'],
            clients=clients,
            commands=subtasks_legacy,
            execution_order=execution_order,
            subtasks=subtasks,
            schedule_time=parse_datetime(row['schedule_time']),
            cron_expression=row['cron_expression'],
            client=safe_get('client'),
            status=TaskStatus(row['status']),
            created_at=parse_datetime(row['created_at']),
            started_at=parse_datetime(row['started_at']),
            completed_at=parse_datetime(row['completed_at']),
            result=row['result'],
            error_message=row['error_message'],
            retry_count=row['retry_count'],
            max_retries=row['max_retries'],
            send_email=bool(safe_get('send_email', 0)),  # Convert integer back to boolean
            email_recipients=safe_get('email_recipients')
        )

        return task

    def _row_to_client(self, row) -> Client:
        """Convert database row to client object"""# Parse system information JSON fields
        def safe_json_parse(field_value):
            try:
                return json.loads(field_value) if field_value else None
            except:
                return None

        # Helper function to safely get row values
        def safe_get(key, default=None):
            try:
                return row[key]
            except (KeyError, IndexError):
                return default

        return Client(
            name=row['name'],
            ip_address=row['ip_address'],
            port=row['port'],
            status=ClientStatus(row['status']),
            last_heartbeat=parse_datetime(row['last_heartbeat']),
            last_config_update=parse_datetime(safe_get('last_config_update')),
            current_task_id=safe_get('current_task_id'),
            current_subtask_id=safe_get('current_subtask_id'),
            cpu_info=safe_json_parse(safe_get('cpu_info')),
            memory_info=safe_json_parse(safe_get('memory_info')),
            gpu_info=safe_json_parse(safe_get('gpu_info')),
            os_info=safe_json_parse(safe_get('os_info')),
            disk_info=safe_json_parse(safe_get('disk_info')),
            system_summary=safe_json_parse(safe_get('system_summary'))
        )

    # Client Communication Logs
    def log_client_action(self, client_ip: str, client_name: str, action: str,
                         message: str = None, data: Any = None, level: str = 'INFO'):
        """Log client communication action"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO logs
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
            
            # Emit real-time log update via WebSocket
            if self.socketio:
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'client_ip': client_ip,
                    'client_name': client_name,
                    'action': action,
                    'message': message,
                    'level': level,
                    'data': json.loads(json.dumps(data)) if data else None
                }
                self.socketio.emit('new_log_entry', log_entry)

    def get_client_logs(self, limit: int = 100, client_ip: str = None) -> List[Dict[str, Any]]:
        """Get client communication logs"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if client_ip:
                cursor.execute('''
                    SELECT * FROM logs
                    WHERE client_ip = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (client_ip, limit))
            else:
                cursor.execute('''
                    SELECT * FROM logs
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
                DELETE FROM logs
                WHERE timestamp < datetime('now', '-{} days')
            '''.format(older_than_days))
            deleted_count = cursor.rowcount
            conn.commit()
            logger.info(f"Cleared {deleted_count} old client log entries")
            return deleted_count

    def _row_to_subtask_execution(self, row) -> SubtaskExecution:
        """Convert database row to SubtaskExecution object"""
        return SubtaskExecution(
            id=row['id'],
            task_id=row['task_id'],
            subtask_name=row['subtask_name'],
            subtask_order=row['subtask_order'],
            client=row['client'],
            started_at=parse_datetime(row['started_at']),
            completed_at=parse_datetime(row['completed_at']),
            status=TaskStatus(row['status']),
            result=row['result'],
            error_message=row['error_message'],
            execution_time=row['execution_time']
        )

    def delete_client(self, client_name: str) -> bool:
        """Delete client by name (primary method - client names are unique)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Check if client exists and get its details
            cursor.execute('SELECT ip_address FROM clients WHERE name = ?', (client_name,))
            result = cursor.fetchone()
            if not result:
                return False

            ip_address = result[0]

            # Delete client from database
            cursor.execute('DELETE FROM clients WHERE name = ?', (client_name,))
            deleted_count = cursor.rowcount
            conn.commit()

            if deleted_count > 0:
                logger.info(f"Deleted client: {client_name} ({ip_address})")
                return True
            return False

    def delete_client_by_ip(self, ip_address: str) -> bool:
        """Delete client by IP address (for backward compatibility, not recommended)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Check if client exists and get its name
            cursor.execute('SELECT name FROM clients WHERE ip_address = ?', (ip_address,))
            result = cursor.fetchone()
            if not result:
                return False

            client_name = result[0]

            # Delete client from database using IP (not recommended but kept for compatibility)
            cursor.execute('DELETE FROM clients WHERE ip_address = ?', (ip_address,))
            deleted_count = cursor.rowcount
            conn.commit()

            if deleted_count > 0:
                logger.info(f"Deleted client: {client_name} ({ip_address})")
                return True
            return False

    def update_client_current_task(self, client_name: str, task_id: Optional[int] = None, subtask_id: Optional[str] = None) -> bool:
        """Update the current task and subtask being executed by a client"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE clients 
                    SET current_task_id = ?, current_subtask_id = ? 
                    WHERE name = ?
                ''', (task_id, subtask_id, client_name))
                
                if cursor.rowcount == 0:
                    logger.warning(f"Client '{client_name}' not found when updating current task")
                    return False
                
                conn.commit()
                
                # Log the update
                if task_id and subtask_id:
                    logger.debug(f"Client '{client_name}' assigned to task {task_id}, subtask '{subtask_id}'")
                elif task_id:
                    logger.debug(f"Client '{client_name}' assigned to task {task_id}")
                else:
                    logger.debug(f"Client '{client_name}' freed from current task")

                return True
                
        except Exception as e:
            logger.error(f"Failed to update client current task: {e}")
            return False

    def update_subtask_execution(self, execution: SubtaskExecution):
        """Update subtask execution record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE executions
                SET completed_at=?, status=?, result=?, error_message=?, execution_time=?
                WHERE id=?
            ''', (
                execution.completed_at.isoformat() if execution.completed_at else None,
                execution.status.value, execution.result, execution.error_message,
                execution.execution_time, execution.id
            ))
            conn.commit()

    def get_executions(self, task_id: int) -> List[SubtaskExecution]:
        """Get all subtask execution records for a task"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM executions
                WHERE task_id = ?
                ORDER BY subtask_order ASC, started_at ASC
            ''', (task_id,))
            rows = cursor.fetchall()
            return [self._row_to_subtask_execution(row) for row in rows]

    def get_executions_by_client(self, task_id: int, client_name: str) -> List[SubtaskExecution]:
        """Get subtask execution records for a specific task and client"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM executions
                WHERE task_id = ? AND client = ?
                ORDER BY subtask_order ASC, started_at ASC
            ''', (task_id, client_name))
            rows = cursor.fetchall()
            return [self._row_to_subtask_execution(row) for row in rows]

    # Client aliases for backward compatibility and cleaner terminology
    def _migrate_subtask_ids(self, cursor):
        """Add subtask_id field to executions table and current_subtask_id to clients table"""
        try:
            # Check if subtask_id column exists in executions table
            cursor.execute("PRAGMA table_info(executions)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'subtask_id' not in columns:
                cursor.execute("ALTER TABLE executions ADD COLUMN subtask_id TEXT")
                logger.info("Added subtask_id column to executions table")
            
            # Check if current_subtask_id column exists in clients table
            cursor.execute("PRAGMA table_info(clients)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'current_subtask_id' not in columns:
                cursor.execute("ALTER TABLE clients ADD COLUMN current_subtask_id TEXT")
                logger.info("Added current_subtask_id column to clients table")
                
        except Exception as e:
            logger.error(f"Failed to migrate subtask IDs: {e}")

    def delete_pending_executions(self, task_id: int, subtask_name: str, client: str):
        """Delete pending subtask execution records for a specific subtask"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM executions 
                WHERE task_id = ? AND subtask_name = ? AND client = ? AND status = 'pending'
            ''', (task_id, subtask_name, client))
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} pending subtask execution(s) for task {task_id}, subtask '{subtask_name}', client '{client}'")
            
            return deleted_count
    
    def client_name_exists(self, client_name: str) -> bool:
        """Check if client name exists"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM clients WHERE name = ?', (client_name,))
            return cursor.fetchone()[0] > 0
    
    def get_client_names(self) -> List[str]:
        """Get client names"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM clients ORDER BY name ASC')
            rows = cursor.fetchall()
            return [row['name'] for row in rows]
    
    def get_online_client_names(self) -> List[str]:
        """Get free client names using real-time status"""
        online_clients = self.get_online_clients()  # This uses real-time status calculation
        return [client.name for client in online_clients]

    def get_free_client_names(self) -> List[str]:
        """Get free client names using real-time status"""
        return self.get_online_client_names()

    def get_busy_client_names(self) -> List[str]:
        """Get busy client names using real-time status"""
        busy_clients = self.get_busy_clients()  # This uses real-time status calculation
        return [client.name for client in busy_clients]

    def get_offline_client_names(self) -> List[str]:
        """Get offline client names using real-time status"""
        offline_clients = self.get_offline_clients()  # This uses real-time status calculation
        return [client.name for client in offline_clients]
    
    # Additional methods for result collection system
    def get_executions_filtered(self, task_id: int, subtask_name: str = None, client_name: str = None) -> List[SubtaskExecution]:
        """
        Get subtask execution records with optional filtering
        
        Args:
            task_id: ID of the task
            subtask_name: Optional subtask name filter
            client_name: Optional client name filter
            
        Returns:
            List of SubtaskExecution objects
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM executions WHERE task_id = ?'
            params = [task_id]
            
            if subtask_name:
                query += ' AND subtask_name = ?'
                params.append(subtask_name)
            
            if client_name:
                query += ' AND client = ?'
                params.append(client_name)
            
            query += ' ORDER BY subtask_order ASC, started_at ASC'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_subtask_execution(row) for row in rows]

    def update_task_status(self, task_id: int, status: TaskStatus, completed_at: datetime = None, 
                          result: str = None, error_message: str = None):
        """
        Update task status and completion information
        
        Args:
            task_id: ID of the task to update
            status: New task status
            completed_at: Completion timestamp
            result: Task result
            error_message: Error message if task failed
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            update_fields = ['status = ?']
            params = [status.value]
            
            if completed_at:
                update_fields.append('completed_at = ?')
                params.append(completed_at.isoformat())
            
            if result:
                update_fields.append('result = ?')
                params.append(result)
            
            if error_message:
                update_fields.append('error_message = ?')
                params.append(error_message)
            
            query = f'UPDATE tasks SET {", ".join(update_fields)} WHERE id = ?'
            params.append(task_id)
            
            cursor.execute(query, params)
            conn.commit()
            
            logger.debug(f"Updated task {task_id} status to {status.value}")
            
            # Emit real-time update
            if self.socketio:
                self.socketio.emit('task_status_updated', {
                    'task_id': task_id,
                    'status': status.value,
                    'completed_at': completed_at.isoformat() if completed_at else None
                })

    def delete_pending_executions(self, task_id: int, subtask_name: str, client: str):
        """Delete pending subtask execution records for a specific subtask"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Only delete records that are pending (haven't started execution)
                cursor.execute('''
                    DELETE FROM executions 
                    WHERE task_id = ? AND subtask_name = ? AND client = ? AND status = ?
                ''', (task_id, subtask_name, client, TaskStatus.PENDING.value))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Deleted {deleted_count} pending subtask execution records for task {task_id}, subtask '{subtask_name}', client '{client}'")
                return deleted_count > 0
                
        except Exception as e:
            logger.error(f"Failed to delete pending subtask executions: {e}")
            return False

    def update_client_current_task(self, client_name: str, task_id: int = None, subtask_id: str = None):
        """Update the current task and subtask being executed by a client"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE clients 
                    SET current_task_id = ?, current_subtask_id = ? 
                    WHERE name = ?
                ''', (task_id, subtask_id, client_name))
                
                if cursor.rowcount == 0:
                    logger.warning(f"No client found with name: {client_name}")
                    return False
                
                conn.commit()
                
                # Log the update
                if task_id and subtask_id:
                    logger.info(f"Client '{client_name}' started executing task {task_id}, subtask '{subtask_id}'")
                elif task_id:
                    logger.info(f"Client '{client_name}' started executing task {task_id}")
                else:
                    logger.info(f"Client '{client_name}' finished executing tasks")
                
                # Emit real-time update
                if self.socketio:
                    self.socketio.emit('client_task_updated', {
                        'client_name': client_name,
                        'task_id': task_id,
                        'subtask_id': subtask_id
                    })
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to update client current task: {e}")
            return False

    def _migrate_subtask_ids(self, cursor):
        """Add subtask_id field to executions table and current_subtask_id to clients table"""
        try:
            # Check if subtask_id column exists in executions table
            cursor.execute("PRAGMA table_info(executions)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'subtask_id' not in columns:
                cursor.execute("ALTER TABLE executions ADD COLUMN subtask_id TEXT")
                logger.info("Added subtask_id column to executions table")
            
            # Check if current_subtask_id column exists in clients table
            cursor.execute("PRAGMA table_info(clients)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'current_subtask_id' not in columns:
                cursor.execute("ALTER TABLE clients ADD COLUMN current_subtask_id TEXT")
                logger.info("Added current_subtask_id column to clients table")
                
        except Exception as e:
            logger.error(f"Failed to migrate subtask IDs: {e}")
            raise

    def _migrate_machine_to_client_terminology(self, cursor):
        """Migrate remaining machine terminology to client terminology in database tables"""
        try:
            # 1. Update tasks table: target_machines -> clients (if still exists), target_machine -> client (if still exists)
            cursor.execute("PRAGMA table_info(tasks)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Check if old target_machines column still exists (should be replaced by clients)
            if 'target_machines' in columns and 'clients' not in columns:
                # Rename target_machines to clients
                cursor.execute("ALTER TABLE tasks RENAME COLUMN target_machines TO clients")
                logger.info("Renamed target_machines column to clients in tasks table")
            elif 'target_machines' in columns and 'clients' in columns:
                # Both exist, copy data and drop old column
                cursor.execute("UPDATE tasks SET clients = target_machines WHERE clients = '[]' OR clients IS NULL")
                # SQLite doesn't support DROP COLUMN directly, so we'll recreate the table
                self._recreate_tasks_table_without_target_machines(cursor)
                logger.info("Migrated data from target_machines to clients and removed old column")
            
            # Check if old target_machine column still exists (should be removed as it's legacy)
            if 'target_machine' in columns:
                # SQLite doesn't support DROP COLUMN directly, so we'll recreate the table
                self._recreate_tasks_table_without_target_machine(cursor)
                logger.info("Removed target_machine column from tasks table")
            
            # 2. Update executions table: target_machine -> client
            cursor.execute("PRAGMA table_info(executions)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'target_machine' in columns and 'client' not in columns:
                cursor.execute("ALTER TABLE executions RENAME COLUMN target_machine TO client")
                logger.info("Renamed target_machine column to client in executions table")
            elif 'target_machine' in columns and 'client' in columns:
                # Both exist, copy data and recreate table
                cursor.execute("UPDATE executions SET client = target_machine WHERE client IS NULL")
                self._recreate_executions_table_without_target_machine(cursor)
                logger.info("Migrated data from target_machine to client and removed old column")
                
        except Exception as e:
            logger.error(f"Failed to migrate machine to client terminology: {e}")
            raise

    def _recreate_tasks_table_without_target_machines(self, cursor):
        """Recreate tasks table without target_machines column"""
        cursor.execute('''
            CREATE TABLE tasks_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                command TEXT NOT NULL,
                clients TEXT DEFAULT '[]',
                subtasks TEXT DEFAULT '[]',
                execution_order TEXT DEFAULT '[]',
                schedule_time TEXT,
                cron_expression TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT,
                completed_at TEXT,
                result TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                subtasks TEXT DEFAULT '[]',
                send_email INTEGER DEFAULT 0,
                email_recipients TEXT
            )
        ''')
        
        cursor.execute('''
            INSERT INTO tasks_new (id, name, command, clients, subtasks, execution_order,
                                 schedule_time, cron_expression, status, created_at, started_at,
                                 completed_at, result, error_message, retry_count, max_retries,
                                 subtasks, send_email, email_recipients)
            SELECT id, name, command, clients, subtasks, execution_order,
                   schedule_time, cron_expression, status, created_at, started_at,
                   completed_at, result, error_message, retry_count, max_retries,
                   subtasks, send_email, email_recipients FROM tasks
        ''')
        
        cursor.execute('DROP TABLE tasks')
        cursor.execute('ALTER TABLE tasks_new RENAME TO tasks')

    def _recreate_tasks_table_without_target_machine(self, cursor):
        """Recreate tasks table without target_machine column"""
        cursor.execute('''
            CREATE TABLE tasks_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                command TEXT NOT NULL,
                clients TEXT DEFAULT '[]',
                subtasks TEXT DEFAULT '[]',
                execution_order TEXT DEFAULT '[]',
                schedule_time TEXT,
                cron_expression TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT,
                completed_at TEXT,
                result TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                subtasks TEXT DEFAULT '[]',
                send_email INTEGER DEFAULT 0,
                email_recipients TEXT
            )
        ''')
        
        cursor.execute('''
            INSERT INTO tasks_new (id, name, command, clients, subtasks, execution_order,
                                 schedule_time, cron_expression, status, created_at, started_at,
                                 completed_at, result, error_message, retry_count, max_retries,
                                 subtasks, send_email, email_recipients)
            SELECT id, name, command, clients, subtasks, execution_order,
                   schedule_time, cron_expression, status, created_at, started_at,
                   completed_at, result, error_message, retry_count, max_retries,
                   subtasks, send_email, email_recipients FROM tasks
        ''')

        cursor.execute('DROP TABLE tasks')
        cursor.execute('ALTER TABLE tasks_new RENAME TO tasks')

    def _recreate_executions_table_without_target_machine(self, cursor):
        """Recreate executions table without target_machine column"""
        cursor.execute('''
            CREATE TABLE executions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                subtask_name TEXT NOT NULL,
                subtask_order INTEGER NOT NULL,
                client TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT,
                error_message TEXT,
                execution_time REAL,
                subtask_id TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks (id)
            )
        ''')
        
        cursor.execute('''
            INSERT INTO executions_new (id, task_id, subtask_name, subtask_order, client,
                                              started_at, completed_at, status, result, error_message,
                                              execution_time, subtask_id)
            SELECT id, task_id, subtask_name, subtask_order, client,
                   started_at, completed_at, status, result, error_message,
                   execution_time, subtask_id FROM executions
        ''')
        
        cursor.execute('DROP TABLE executions')
        cursor.execute('ALTER TABLE executions_new RENAME TO executions')

    def _migrate_remove_task_executions_table(self, cursor):
        """Remove the legacy task_executions table as it's no longer needed"""
        try:
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_executions'")
            if cursor.fetchone():
                cursor.execute("DROP TABLE task_executions")
                logger.info("Removed legacy task_executions table - no longer needed with subtask-based execution")
        except Exception as e:
            logger.error(f"Failed to remove task_executions table: {e}")
            # Don't raise - this is not critical

