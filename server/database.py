"""
Database operations module
"""
import os
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from common.models import Job, Client, JobStatus, ClientStatus, Run, TaskDefinition
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

            # Create tasks (jobs) table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    command TEXT NOT NULL DEFAULT '',
                    clients TEXT DEFAULT '[]',
                    tasks TEXT DEFAULT '[]',
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
                    current_job_id INTEGER,
                    current_task_id TEXT,
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

            # Create runs (execution) table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    task_name TEXT NOT NULL,
                    task_order INTEGER NOT NULL,
                    task_id TEXT,
                    client TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    status TEXT DEFAULT 'pending',
                    result TEXT,
                    error_message TEXT,
                    execution_time REAL,
                    FOREIGN KEY (job_id) REFERENCES tasks (id)
                )
            ''')

            # Migrate old schema to new naming
            self._migrate_to_job_task_run_naming(cursor)

            # Add tasks column to tasks table if it doesn't exist
            cursor.execute("PRAGMA table_info(tasks)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'tasks' not in columns:
                cursor.execute("ALTER TABLE tasks ADD COLUMN tasks TEXT DEFAULT '[]'")
                logger.info("Added tasks column to tasks table")

            # Create task results cache table for storing completed task results
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    job_name TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    status TEXT DEFAULT 'completed',
                    result TEXT,
                    execution_time REAL,
                    completed_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES tasks (id)
                )
            ''')

            # Migrate task_results columns to job/task naming
            self._migrate_task_results_columns(cursor)

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

            # Create administrators table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS administrators (
                    email TEXT PRIMARY KEY,
                    added_by TEXT NOT NULL,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Seed default admin if table is empty
            cursor.execute('SELECT COUNT(*) FROM administrators')
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO administrators (email, added_by) VALUES (?, ?)',
                    ('ygu@microsoft.com', 'system')
                )
                logger.info("Seeded default administrator: ygu@microsoft.com")

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
                ('tasks', 'TEXT DEFAULT \'[]\''),
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

    # Job-related operations
    def create_job(self, task: Job) -> int:
        """Create new job"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tasks (name, command, clients, execution_order,
                                 tasks, schedule_time, cron_expression, client, status,
                                 created_at, started_at, completed_at, result, error_message,
                                 retry_count, max_retries, send_email, email_recipients)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task.name, task.command,
                json.dumps(task.clients) if task.clients else '[]',
                json.dumps(task.execution_order) if task.execution_order else '[]',
                json.dumps([s.to_dict() for s in task.tasks]) if task.tasks else '[]',
                task.schedule_time.isoformat() if task.schedule_time else None,
                task.cron_expression, task.client, task.status.value,
                datetime.now().isoformat(), None, None, None, None,
                task.retry_count, task.max_retries,
                1 if task.send_email else 0,  # Convert boolean to integer for SQLite
                task.email_recipients
            ))
            task_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Create Task: {task.name} (ID: {task_id})")
            return task_id

    def get_job(self, task_id: int) -> Optional[Job]:
        """Get job by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_job(row)
            return None

    def get_all_jobs(self) -> List[Job]:
        """Get all jobs"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks ORDER BY created_at DESC')
            rows = cursor.fetchall()
            return [self._row_to_job(row) for row in rows]

    def update_job(self, task: Job):
        """Update job"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE tasks SET name=?, command=?, clients=?, execution_order=?,
                               tasks=?, schedule_time=?, cron_expression=?,
                               client=?, status=?, started_at=?, completed_at=?,
                               result=?, error_message=?, retry_count=?, max_retries=?,
                               send_email=?, email_recipients=?
                WHERE id=?
            ''', (
                task.name, task.command,
                json.dumps(task.clients) if task.clients else '[]',
                json.dumps(task.execution_order) if task.execution_order else '[]',
                json.dumps([s.to_dict() for s in task.tasks]) if task.tasks else '[]',
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

    def delete_job(self, task_id: int):
        """Delete job and all related run records"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT name FROM tasks WHERE id = ?', (task_id,))
            task_row = cursor.fetchone()
            task_name = task_row[0] if task_row else f"ID:{task_id}"

            # Delete runs first (child records)
            cursor.execute('DELETE FROM runs WHERE job_id = ?', (task_id,))
            runs_deleted = cursor.rowcount

            # Delete the job itself
            cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            task_deleted = cursor.rowcount

            conn.commit()

            if task_deleted > 0:
                logger.info(f"Deleted job '{task_name}' (ID: {task_id}) with {runs_deleted} runs")

                if self.socketio:
                    self.socketio.emit('task_deleted', {
                        'task_id': task_id,
                        'task_name': task_name,
                        'runs_deleted': runs_deleted
                    })

                return True
            else:
                logger.warning(f"Task with ID {task_id} not found for deletion")
                return False

    def get_pending_jobs(self) -> List[Job]:
        """Get pending tasks"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM tasks
                WHERE status = 'pending'
                ORDER BY created_at ASC
            ''')
            rows = cursor.fetchall()
            return [self._row_to_job(row) for row in rows]

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
                (name, ip_address, port, status, last_heartbeat, last_config_update, current_task_id, current_task_id,
                 cpu_info, memory_info, gpu_info, os_info, disk_info, system_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                client.name, client.ip_address, client.port,
                client.status.value, datetime.now().isoformat(), datetime.now().isoformat(),
                client.current_job_id, client.current_task_id,
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
        """Get all clients using cached status from the database.
        Status is maintained by the scheduler's periodic cleanup job."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM clients')
            rows = cursor.fetchall()
            return [self._row_to_client(row) for row in rows]

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

    # Run related operations
    def create_run(self, run: Run) -> int:
        """Create run record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO runs
                (job_id, task_name, task_order, task_id, client, started_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                run.job_id, run.task_name, run.task_order, run.task_id,
                run.client, datetime.now().isoformat(), run.status.value
            ))
            run_id = cursor.lastrowid
            conn.commit()
            return run_id

    def update_run(self, run: Run):
        """Update run record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE runs
                SET completed_at=?, status=?, result=?, error_message=?, execution_time=?
                WHERE id=?
            ''', (
                run.completed_at.isoformat() if run.completed_at else None,
                run.status.value, run.result, run.error_message,
                run.execution_time, run.id
            ))
            conn.commit()

    def get_runs(self, job_id: int) -> List[Run]:
        """Get all run records for a job"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM runs
                WHERE job_id = ?
                ORDER BY task_order ASC, started_at ASC
            ''', (job_id,))
            rows = cursor.fetchall()
            return [self._row_to_run(row) for row in rows]

    def get_all_runs_grouped(self) -> Dict[int, List[Run]]:
        """Get all runs grouped by job_id in a single query."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM runs ORDER BY job_id, task_order ASC, started_at ASC')
            grouped: Dict[int, List[Run]] = {}
            for row in cursor.fetchall():
                jid = row['job_id']
                if jid not in grouped:
                    grouped[jid] = []
                grouped[jid].append(self._row_to_run(row))
            return grouped

    def get_runs_by_client(self, job_id: int, client_name: str) -> List[Run]:
        """Get Task execution records for a specific task and client"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM runs
                WHERE job_id = ? AND client = ?
                ORDER BY task_order ASC, started_at ASC
            ''', (job_id, client_name))
            rows = cursor.fetchall()
            return [self._row_to_run(row) for row in rows]

    # Helper methods
    def _row_to_job(self, row) -> Job:
        """Convert database row to Job object"""
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
        execution_order = safe_json_parse(safe_get('execution_order'), [])

        # Parse task definitions from DB 'tasks' column
        tasks_data = safe_json_parse(safe_get('tasks'), [])
        tasks = []
        for td in tasks_data:
            try:
                task_def = TaskDefinition(
                    name=td.get('name', ''),
                    client=td.get('client', ''),
                    order=td.get('order', 0),
                    args=td.get('args', []),
                    kwargs=td.get('kwargs', {}),
                    timeout=td.get('timeout', 300),
                    retry_count=td.get('retry_count', 0),
                    max_retries=td.get('max_retries', 3),
                    task_id=td.get('task_id', None)
                )
                tasks.append(task_def)
            except Exception as e:
                logger.warning(f"Failed to parse task definition: {e}")

        job = Job(
            id=row['id'],
            name=row['name'],
            command=safe_get('command', ''),
            clients=clients,
            execution_order=execution_order,
            tasks=tasks,
            schedule_time=parse_datetime(row['schedule_time']),
            cron_expression=row['cron_expression'],
            client=safe_get('client'),
            status=JobStatus(row['status']),
            created_at=parse_datetime(row['created_at']),
            started_at=parse_datetime(row['started_at']),
            completed_at=parse_datetime(row['completed_at']),
            result=row['result'],
            error_message=row['error_message'],
            retry_count=row['retry_count'],
            max_retries=row['max_retries'],
            send_email=bool(safe_get('send_email', 0)),
            email_recipients=safe_get('email_recipients')
        )

        return job

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
            current_job_id=safe_get('current_job_id'),
            current_task_id=safe_get('current_task_id'),
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

    def _row_to_run(self, row) -> Run:
        """Convert database row to Run object"""
        return Run(
            id=row['id'],
            job_id=row['job_id'],
            task_name=row['task_name'],
            task_order=row['task_order'],
            task_id=row['task_id'] if 'task_id' in row.keys() else '',
            client=row['client'],
            started_at=parse_datetime(row['started_at']),
            completed_at=parse_datetime(row['completed_at']),
            status=JobStatus(row['status']),
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

    def update_client_current_task(self, client_name: str, job_id: Optional[int] = None, task_id: Optional[str] = None) -> bool:
        """Update the current job and task being executed by a client"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE clients
                    SET current_job_id = ?, current_task_id = ?
                    WHERE name = ?
                ''', (job_id, task_id, client_name))

                if cursor.rowcount == 0:
                    logger.warning(f"Client '{client_name}' not found when updating current task")
                    return False

                conn.commit()

                if job_id and task_id:
                    logger.debug(f"Client '{client_name}' assigned to job {job_id}, task '{task_id}'")
                elif job_id:
                    logger.debug(f"Client '{client_name}' assigned to job {job_id}")
                else:
                    logger.debug(f"Client '{client_name}' freed from current job")

                return True

        except Exception as e:
            logger.error(f"Failed to update client current task: {e}")
            return False

    # Client aliases for backward compatibility and cleaner terminology
    def _migrate_task_ids(self, cursor):
        """Add task_id field to executions table and current_task_id to clients table"""
        try:
            # Check if task_id column exists in executions table
            cursor.execute("PRAGMA table_info(executions)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'task_id' not in columns:
                cursor.execute("ALTER TABLE executions ADD COLUMN task_id TEXT")
                logger.info("Added task_id column to executions table")

            # Check if current_task_id column exists in clients table
            cursor.execute("PRAGMA table_info(clients)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'current_task_id' not in columns:
                cursor.execute("ALTER TABLE clients ADD COLUMN current_task_id TEXT")
                logger.info("Added current_task_id column to clients table")

        except Exception as e:
            logger.error(f"Failed to migrate Task IDs: {e}")

    def delete_pending_runs(self, task_id: int, task_name: str, client: str):
        """Delete pending Task execution records for a specific Task"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM runs
                WHERE job_id = ? AND task_name = ? AND client = ? AND status = 'pending'
            ''', (task_id, task_name, client))
            deleted_count = cursor.rowcount
            conn.commit()

            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} pending Task execution(s) for task {task_id}, Task '{task_name}', client '{client}'")

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
    def get_runs_filtered(self, job_id: int, task_name: str = None, client_name: str = None) -> List[Run]:
        """
        Get Task execution records with optional filtering

        Args:
            task_id: ID of the task
            task_name: Optional Task name filter
            client_name: Optional client name filter

        Returns:
            List of Run objects
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = 'SELECT * FROM runs WHERE job_id = ?'
            params = [job_id]

            if task_name:
                query += ' AND task_name = ?'
                params.append(task_name)

            if client_name:
                query += ' AND client = ?'
                params.append(client_name)

            query += ' ORDER BY task_order ASC, started_at ASC'

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_run(row) for row in rows]

    def update_job_status(self, task_id: int, status: JobStatus, completed_at: datetime = None,
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

    def delete_pending_runs(self, task_id: int, task_name: str, client: str):
        """Delete pending Task execution records for a specific Task"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Only delete records that are pending (haven't started execution)
                cursor.execute('''
                    DELETE FROM runs
                    WHERE job_id = ? AND task_name = ? AND client = ? AND status = ?
                ''', (task_id, task_name, client, JobStatus.PENDING.value))

                deleted_count = cursor.rowcount
                conn.commit()

                logger.info(f"Deleted {deleted_count} pending Task execution records for task {task_id}, Task '{task_name}', client '{client}'")
                return deleted_count > 0

        except Exception as e:
            logger.error(f"Failed to delete pending Task executions: {e}")
            return False

    def _migrate_task_ids(self, cursor):
        """Add task_id field to executions table and current_task_id to clients table"""
        try:
            # Check if task_id column exists in executions table
            cursor.execute("PRAGMA table_info(executions)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'task_id' not in columns:
                cursor.execute("ALTER TABLE executions ADD COLUMN task_id TEXT")
                logger.info("Added task_id column to executions table")

            # Check if current_task_id column exists in clients table
            cursor.execute("PRAGMA table_info(clients)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'current_task_id' not in columns:
                cursor.execute("ALTER TABLE clients ADD COLUMN current_task_id TEXT")
                logger.info("Added current_task_id column to clients table")

        except Exception as e:
            logger.error(f"Failed to migrate Task IDs: {e}")
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

            # 2. UPDATE runs table: target_machine -> client
            cursor.execute("PRAGMA table_info(executions)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'target_machine' in columns and 'client' not in columns:
                cursor.execute("ALTER TABLE executions RENAME COLUMN target_machine TO client")
                logger.info("Renamed target_machine column to client in executions table")
            elif 'target_machine' in columns and 'client' in columns:
                # Both exist, copy data and recreate table
                cursor.execute("UPDATE runs SET client = target_machine WHERE client IS NULL")
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
                tasks TEXT DEFAULT '[]',
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
                tasks TEXT DEFAULT '[]',
                send_email INTEGER DEFAULT 0,
                email_recipients TEXT
            )
        ''')

        cursor.execute('''
            INSERT INTO tasks_new (id, name, command, clients, tasks, execution_order,
                                 schedule_time, cron_expression, status, created_at, started_at,
                                 completed_at, result, error_message, retry_count, max_retries,
                                 tasks, send_email, email_recipients)
            SELECT id, name, command, clients, tasks, execution_order,
                   schedule_time, cron_expression, status, created_at, started_at,
                   completed_at, result, error_message, retry_count, max_retries,
                   tasks, send_email, email_recipients FROM tasks
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
                tasks TEXT DEFAULT '[]',
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
                tasks TEXT DEFAULT '[]',
                send_email INTEGER DEFAULT 0,
                email_recipients TEXT
            )
        ''')

        cursor.execute('''
            INSERT INTO tasks_new (id, name, command, clients, tasks, execution_order,
                                 schedule_time, cron_expression, status, created_at, started_at,
                                 completed_at, result, error_message, retry_count, max_retries,
                                 tasks, send_email, email_recipients)
            SELECT id, name, command, clients, tasks, execution_order,
                   schedule_time, cron_expression, status, created_at, started_at,
                   completed_at, result, error_message, retry_count, max_retries,
                   tasks, send_email, email_recipients FROM tasks
        ''')

        cursor.execute('DROP TABLE tasks')
        cursor.execute('ALTER TABLE tasks_new RENAME TO tasks')

    def _recreate_executions_table_without_target_machine(self, cursor):
        """Recreate executions table without target_machine column"""
        cursor.execute('''
            CREATE TABLE executions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                task_name TEXT NOT NULL,
                task_order INTEGER NOT NULL,
                client TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT,
                error_message TEXT,
                execution_time REAL,
                task_id TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks (id)
            )
        ''')

        cursor.execute('''
            INSERT INTO executions_new (id, task_id, task_name, task_order, client,
                                              started_at, completed_at, status, result, error_message,
                                              execution_time, task_id)
            SELECT id, task_id, task_name, task_order, client,
                   started_at, completed_at, status, result, error_message,
                   execution_time, task_id FROM runs
        ''')

        cursor.execute('DROP TABLE executions')
        cursor.execute('ALTER TABLE executions_new RENAME TO executions')

    def _migrate_remove_task_executions_table(self, cursor):
        """Remove the legacy task_executions table as it's no longer needed"""
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_executions'")
            if cursor.fetchone():
                cursor.execute("DROP TABLE task_executions")
                logger.info("Removed legacy task_executions table")
        except Exception as e:
            logger.error(f"Failed to remove task_executions table: {e}")

    def _migrate_to_job_task_run_naming(self, cursor):
        """Migrate old 'executions' table to new 'runs' table with renamed columns.
        Also renames columns in tasks and clients tables."""
        try:
            # 1. Migrate executions → runs
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='executions'")
            if cursor.fetchone():
                logger.info("Migrating executions table → runs table...")
                cursor.execute('''
                    INSERT OR IGNORE INTO runs
                    (id, job_id, task_name, task_order, task_id, client,
                     started_at, completed_at, status, result, error_message, execution_time)
                    SELECT id, task_id, task_name, TASK_order,
                           COALESCE(TASK_id, ''), client,
                           started_at, completed_at, status, result, error_message, execution_time
                    FROM executions
                ''')
                cursor.execute("DROP TABLE executions")
                logger.info("Migrated executions → runs successfully")

            # 2. Rename 'tasks' column to 'tasks' in tasks table
            cursor.execute("PRAGMA table_info(tasks)")
            cols = [c[1] for c in cursor.fetchall()]
            if 'tasks' in cols and 'tasks' not in cols:
                cursor.execute("ALTER TABLE tasks RENAME COLUMN tasks TO tasks")
                logger.info("Renamed tasks.tasks → tasks.tasks")

            # 3. Rename client columns: current_task_id → current_job_id, current_task_id → current_task_id
            cursor.execute("PRAGMA table_info(clients)")
            cols = [c[1] for c in cursor.fetchall()]
            if 'current_task_id' in cols and 'current_job_id' not in cols:
                cursor.execute("ALTER TABLE clients RENAME COLUMN current_task_id TO current_job_id")
                logger.info("Renamed clients.current_task_id → clients.current_job_id")
            if 'current_task_id' in cols and 'current_task_id' not in cols:
                cursor.execute("ALTER TABLE clients RENAME COLUMN current_task_id TO current_task_id")
                logger.info("Renamed clients.current_task_id → clients.current_task_id")

        except Exception as e:
            logger.error(f"Migration to job/task/run naming failed: {e}")
            raise

    def _migrate_task_results_columns(self, cursor):
        """Rename task_results columns: task_id→job_id, task_name→job_name, subtask_name→task_name"""
        try:
            cursor.execute("PRAGMA table_info(task_results)")
            columns = [c[1] for c in cursor.fetchall()]

            if 'subtask_name' in columns or ('task_id' in columns and 'job_id' not in columns):
                logger.info("Migrating task_results columns to job/task naming...")
                cursor.execute('''
                    CREATE TABLE task_results_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id INTEGER NOT NULL,
                        job_name TEXT NOT NULL,
                        client_name TEXT NOT NULL,
                        task_name TEXT NOT NULL,
                        status TEXT DEFAULT 'completed',
                        result TEXT,
                        execution_time REAL,
                        completed_at TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (job_id) REFERENCES tasks (id)
                    )
                ''')
                # Map old columns to new: task_id→job_id, task_name→job_name, subtask_name→task_name
                old_task_col = 'subtask_name' if 'subtask_name' in columns else 'task_name'
                cursor.execute(f'''
                    INSERT INTO task_results_new
                    (id, job_id, job_name, client_name, task_name, status,
                     result, execution_time, completed_at, created_at)
                    SELECT id, task_id, task_name, client_name, {old_task_col}, status,
                           result, execution_time, completed_at, created_at
                    FROM task_results
                ''')
                cursor.execute('DROP TABLE task_results')
                cursor.execute('ALTER TABLE task_results_new RENAME TO task_results')
                logger.info("Migrated task_results columns successfully")
        except Exception as e:
            logger.error(f"task_results column migration failed: {e}")

    # Task result caching methods

    # Directory for result files — stored under gitignore/ to avoid committing
    RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'gitignore', 'server', 'results')

    def _save_result_file(self, task_id: int, client_name: str,
                          task_name: str, result_data: str) -> str:
        """Save result data to a text file and generate an HTML report.
        Returns the relative path to the text file."""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        # Sanitize names for safe filesystem paths
        safe_client = "".join(c if c.isalnum() or c in '-_.' else '_' for c in client_name)
        safe_task = "".join(c if c.isalnum() or c in '-_.' else '_' for c in task_name)

        rel_dir = os.path.join(str(task_id), safe_client)
        abs_dir = os.path.join(self.RESULTS_DIR, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)

        filename = f"{safe_task}_{timestamp}.txt"
        rel_path = os.path.join(rel_dir, filename)
        abs_path = os.path.join(self.RESULTS_DIR, rel_path)

        with open(abs_path, 'w', encoding='utf-8') as f:
            if isinstance(result_data, str):
                f.write(result_data)
            else:
                f.write(json.dumps(result_data, indent=2))

        # Generate HTML report from the result data
        self._generate_result_html(abs_dir, safe_task, timestamp, result_data)

        return rel_path

    def _generate_result_html(self, abs_dir: str, safe_task: str,
                              timestamp: str, result_data: str):
        """Generate an HTML report using compare-results.js with Chart.js visuals."""
        try:
            import shutil
            import subprocess
            import tempfile
            import re

            parsed = json.loads(result_data) if isinstance(result_data, str) else result_data
            if not isinstance(parsed, dict):
                return

            # Extract structured results or find result files from stdout
            results_obj = parsed.get('results')
            run_id = parsed.get('run_id')

            # Fallback: extract run_id from stdout
            if not run_id:
                stdout = parsed.get('stdout', '')
                match = re.search(r'Results:\s+\S+[/\\](\d{14})', stdout)
                if match:
                    run_id = match.group(1)
            if not run_id:
                run_id = f'report_{timestamp}'

            # Resolve compare-results.js script path
            try:
                import importlib
                ai_test_module = importlib.import_module('common.tasks.ai-test')
                ai_test_path = ai_test_module._resolve_ai_test_path()
            except Exception:
                logger.warning("Could not resolve ai-test path for report generation")
                return

            script_path = os.path.join(ai_test_path, 'scripts', 'compare-results.js')
            if not os.path.isfile(script_path):
                logger.warning(f"compare-results.js not found at {script_path}")
                return

            node = shutil.which('node')
            if not node:
                logger.warning("Node.js not found, skipping HTML report generation")
                return

            # Build temp results directory from stored data
            tmp_dir = tempfile.mkdtemp(prefix='ai_report_')
            run_dir = os.path.join(tmp_dir, run_id)
            os.makedirs(run_dir, exist_ok=True)

            try:
                files_written = False

                # Write structured result files if available
                if results_obj and isinstance(results_obj, dict) and 'files' in results_obj:
                    for filename, filedata in results_obj['files'].items():
                        with open(os.path.join(run_dir, filename), 'w', encoding='utf-8') as f:
                            json.dump(filedata, f, indent=2)
                    files_written = True

                # Fallback: try to copy unified results.json from disk
                if not files_written:
                    stdout = parsed.get('stdout', '')
                    match = re.search(r'Unified results saved to:\s+(\S+)', stdout)
                    if match and os.path.isfile(match.group(1)):
                        shutil.copy2(match.group(1), os.path.join(run_dir, 'results.json'))
                        files_written = True

                if not files_written:
                    logger.debug("No result data available for compare-results.js report")
                    return

                # Set up wrapper: compare-results.js reads config from __dirname/../config.json
                wrapper_dir = os.path.join(tmp_dir, '_wrapper')
                scripts_dir = os.path.join(wrapper_dir, 'scripts')
                os.makedirs(scripts_dir, exist_ok=True)
                shutil.copy2(script_path, scripts_dir)
                local_script = os.path.join(scripts_dir, 'compare-results.js')

                # Remove the browser-open code from the copied script
                with open(local_script, 'r', encoding='utf-8') as f:
                    script_content = f.read()
                script_content = script_content.replace(
                    "require('child_process').execSync(`start", "// disabled: execSync(`start"
                )
                with open(local_script, 'w', encoding='utf-8') as f:
                    f.write(script_content)

                with open(os.path.join(wrapper_dir, 'config.json'), 'w', encoding='utf-8') as f:
                    json.dump({'paths': {'results': tmp_dir}}, f)

                html_filename = f"{safe_task}_{timestamp}.html"
                output_path = os.path.join(abs_dir, html_filename)

                proc = subprocess.run(
                    [node, local_script, run_id, '-o', output_path],
                    cwd=wrapper_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if proc.returncode == 0 and os.path.isfile(output_path):
                    logger.info(f"Generated Chart.js HTML report: {output_path}")
                else:
                    logger.warning(f"compare-results.js failed (rc={proc.returncode}): "
                                   f"{proc.stderr or proc.stdout}")

            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        except Exception as e:
            logger.warning(f"Failed to generate HTML report: {e}")

    def _read_result_file(self, rel_path: str) -> Optional[str]:
        """Read result data from a file given its relative path."""
        if not rel_path:
            return None
        abs_path = os.path.join(self.RESULTS_DIR, rel_path)
        if os.path.isfile(abs_path):
            with open(abs_path, 'r', encoding='utf-8') as f:
                return f.read()
        return None

    def cache_task_result(self, job_id: int, job_name: str, client_name: str,
                         task_name: str, status: str, result: str = None,
                         execution_time: float = None, completed_at: str = None) -> int:
        """
        Cache a task result. The result data is saved as a file; only the
        file path is stored in the database.

        Args:
            task_id: ID of the task
            task_name: Name of the task
            client_name: Name of the client that executed the Task
            task_name: Name of the Task
            status: Execution status
            result: JSON-encoded result data (will be saved as a file)
            execution_time: Time taken to execute
            completed_at: When execution completed

        Returns:
            ID of the cached result record
        """
        # Save result data to file, store path in DB
        result_path = None
        if result:
            try:
                result_path = self._save_result_file(job_id, client_name, task_name, result)
            except Exception as e:
                logger.error(f"Failed to save result file: {e}. Storing inline.")
                result_path = result

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO task_results
                (job_id, job_name, client_name, task_name, status,
                 result, execution_time, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job_id, job_name, client_name, task_name, status,
                result_path, execution_time,
                completed_at or datetime.now().isoformat()
            ))
            result_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Cached result for job {job_id} ({job_name}), "
                       f"task '{task_name}' on client '{client_name}' -> {result_path}")
            return result_id

    def _resolve_result_row(self, row, load_content: bool = True) -> Dict[str, Any]:
        """Convert a task_results DB row into a dict, resolving file-based results."""
        stored = row['result']
        result_file = None
        result_data = stored

        # Detect if stored value is a relative file path (not raw JSON)
        if stored and not stored.startswith('{') and not stored.startswith('['):
            result_file = stored
            if load_content:
                result_data = self._read_result_file(stored)
            else:
                result_data = None  # Don't load full content for listings

        # Check if an HTML report exists alongside the result file
        html_file = None
        if result_file:
            html_path = result_file.rsplit('.', 1)[0] + '.html'
            abs_html = os.path.join(self.RESULTS_DIR, html_path)
            if os.path.isfile(abs_html):
                html_file = html_path

        d = {
            'id': row['id'],
            'job_id': row['job_id'],
            'job_name': row['job_name'],
            'client_name': row['client_name'],
            'task_name': row['task_name'],
            'status': row['status'],
            'result': result_data,
            'result_file': result_file,
            'html_file': html_file,
            'execution_time': row['execution_time'],
            'completed_at': row['completed_at'],
            'created_at': row['created_at'],
        }
        return d

    def get_cached_results(self, job_id: int = None, client_name: str = None,
                          task_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get cached task results with optional filtering.
        File content is NOT loaded for listings — use get_cached_result_by_id for full data.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = 'SELECT * FROM task_results WHERE 1=1'
            params = []

            if job_id is not None:
                query += ' AND job_id = ?'
                params.append(job_id)
            if client_name:
                query += ' AND client_name = ?'
                params.append(client_name)
            if task_name:
                query += ' AND task_name = ?'
                params.append(task_name)

            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)

            cursor.execute(query, params)
            return [self._resolve_result_row(row, load_content=False) for row in cursor.fetchall()]

    def get_cached_result_by_id(self, result_id: int) -> Optional[Dict[str, Any]]:
        """Get a single cached result by ID, with full file content loaded."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM task_results WHERE id = ?', (result_id,))
            row = cursor.fetchone()
            if row:
                return self._resolve_result_row(row, load_content=True)
            return None

    def get_latest_result_for_client(self, client_name: str,
                                     task_name: str = None) -> Optional[Dict[str, Any]]:
        """Get the latest cached result for a client, optionally filtered by Task"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = 'SELECT * FROM task_results WHERE client_name = ?'
            params = [client_name]

            if task_name:
                query += ' AND task_name = ?'
                params.append(task_name)

            query += ' ORDER BY created_at DESC LIMIT 1'

            cursor.execute(query, params)
            row = cursor.fetchone()
            if row:
                return self._resolve_result_row(row, load_content=True)
            return None

    def delete_cached_results(self, older_than_days: int = 90) -> int:
        """Delete cached results older than specified days"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM task_results
                WHERE created_at < datetime('now', '-' || ? || ' days')
            ''', (older_than_days,))
            deleted_count = cursor.rowcount
            conn.commit()
            logger.info(f"Deleted {deleted_count} cached results older than {older_than_days} days")
            return deleted_count

    # Administrator operations

    def is_admin(self, email: str) -> bool:
        """Check if an email is an administrator"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM administrators WHERE email = ?', (email.lower(),))
            return cursor.fetchone() is not None

    def get_all_admins(self) -> List[Dict[str, Any]]:
        """Get all administrators"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT email, added_by, added_at FROM administrators ORDER BY added_at')
            return [dict(row) for row in cursor.fetchall()]

    def add_admin(self, email: str, added_by: str) -> bool:
        """Add an administrator"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    'INSERT INTO administrators (email, added_by, added_at) VALUES (?, ?, ?)',
                    (email.lower(), added_by.lower(), datetime.now().isoformat())
                )
                conn.commit()
                logger.info(f"Administrator added: {email} by {added_by}")
                return True
            except sqlite3.IntegrityError:
                logger.warning(f"Administrator already exists: {email}")
                return False

    def remove_admin(self, email: str) -> bool:
        """Remove an administrator"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM administrators WHERE email = ?', (email.lower(),))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info(f"Administrator removed: {email}")
            return deleted
