"""
Client Runtime Manager
Handles client execution, server communication, and task processing.

The runner is designed to execute from the repo directory so that updates to the
repo (e.g. git pull) automatically take effect without reinstalling or restarting
the service.  task modules in common/tasks/ are periodically reloaded to
pick up newly added or modified definitions.
"""
import os
import sys
import time
import json
import argparse
import logging
import threading
import requests
import socketio
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Path setup: prefer repo root so code changes are picked up without reinstall
# ---------------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

# If a --repo-root arg is provided early, prepend it so repo code wins.
# This is parsed "early" before argparse so the imports below use the right path.
_repo_root = None
for i, arg in enumerate(sys.argv):
    if arg == '--repo-root' and i + 1 < len(sys.argv):
        _repo_root = os.path.abspath(sys.argv[i + 1])
        break

if _repo_root and os.path.isdir(_repo_root):
    # Repo root takes highest priority
    sys.path.insert(0, os.path.join(_repo_root, 'client'))
    sys.path.insert(0, _repo_root)
else:
    # Fallback: derive from this file's location
    sys.path.insert(0, current_dir)   # For client modules
    sys.path.insert(0, parent_dir)    # For common modules

# Import local modules
try:
    from common.system_info import get_client_name, get_server_url
    from common.client_info_collector import prepare_registration_data, prepare_ping_response_data
    from common.config import ClientConfig
    from common.utils import setup_logging, get_local_ip
    from heartbeat import HeartbeatManager
    from config_manager import get_config_manager, get_heartbeat_interval, get_config_update_interval
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    print("Make sure the client is properly installed or --repo-root is correct")
    sys.exit(1)

logger = logging.getLogger(__name__)

class TaskClientRunner:
    """
    Runtime client responsible only for execution and communication
    Installation and configuration management is handled separately
    """

    def __init__(self, config_data, cfg_file_path=None):
        """
        Initialize client runner with configuration

        Args:
            config_data: Configuration dictionary loaded from config file
            cfg_file_path: Path to client.cfg file for additional configuration
        """
        self.config = config_data
        self.server_url = config_data['server_url']

        # Get client name: priority config_data > client.cfg > system hostname
        self.client_name = self._get_client_name(config_data, cfg_file_path)
        self.local_ip = get_local_ip()

        # Validate client name validity
        if not self.client_name or self.client_name.strip() == '':
            raise ValueError("Client name cannot be empty. Please configure client_name in client.cfg or config.json")

        # Record client name source
        logger.info(f"Using client name: {self.client_name}")

        # Initialize configuration manager for client.cfg
        if cfg_file_path:
            self.cfg_manager = get_config_manager(cfg_file_path)
        else:
            # Try to find client.cfg in the same directory as runner
            runner_dir = os.path.dirname(os.path.abspath(__file__))
            cfg_path = os.path.join(runner_dir, 'client.cfg')
            self.cfg_manager = get_config_manager(cfg_path if os.path.exists(cfg_path) else None)

        # Use configuration from client.cfg if available, otherwise fall back to config.json
        self.config_update_interval = self.cfg_manager.get_int('DEFAULT', 'config_update_interval',
                                                              config_data.get('config_update_interval', 600))
        # Note: heartbeat_interval is now read from common.cfg via get_heartbeat_interval()

        self.last_config_update = None
        self.running = False
        self.task_results = {}

        # Working directories from config
        self.work_dir = config_data.get('work_dir', os.path.join(os.getcwd(), 'work'))
        self.log_dir = config_data.get('log_dir', os.path.join(os.getcwd(), 'logs'))

        # Ensure working directories exist
        os.makedirs(self.work_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        # Initialize task executor
        try:
            # Add current directory to path for imports
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)

            import task_executor
            self.task_adapter = task_executor.TaskAdapter(self.server_url, self.client_name)
            logger.info("Task executor initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to import task executor: {e}")
            self.task_adapter = None

        # Initialize components with configuration from cfg file
        self.heartbeat = HeartbeatManager(self.server_url, self.client_name, get_heartbeat_interval)

        # Initialize SocketIO client
        self.sio = socketio.Client()
        self._setup_socketio_handlers()

        # Configuration update thread
        self.config_update_thread = None

        # Task auto-reload: track known task files to detect repo changes
        self._last_task_snapshot = self._snapshot_tasks()
        # task reload interval (in seconds) — defaults to config_update_interval
        self.task_reload_interval = self.cfg_manager.get_int(
            'ADVANCED', 'task_reload_interval',
            self.config_update_interval
        )

        logger.info(f"Client runner initialized: {self.client_name} ({self.local_ip}) -> {self.server_url}")
        logger.info(f"Heartbeat interval: {get_heartbeat_interval()} seconds")
        logger.info(f"Configuration update interval: {self.config_update_interval} seconds")
        logger.info(f"task reload interval: {self.task_reload_interval} seconds")

        # Log configuration summary
        if self.cfg_manager.get_boolean('ADVANCED', 'verbose_logging', False):
            logger.info("Configuration summary:")
            logger.info(self.cfg_manager.get_config_summary())

    def _get_client_name(self, config_data, cfg_file_path=None) -> str:
        """
        Get client name by priority order:
        1. client_name in config_data
        2. client_name in client.cfg
        3. system hostname

        Args:
            config_data: Configuration data dictionary
            cfg_file_path: client.cfg file path

        Returns:
            Client name string
        """
        # First try to get from config_data
        client_name = config_data.get('client_name', '').strip()
        if client_name:
            logger.debug(f"Client name from config_data: {client_name}")
            return client_name

        # Then try to get from client.cfg
        try:
            if cfg_file_path:
                cfg_manager = get_config_manager(cfg_file_path)
            else:
                runner_dir = os.path.dirname(os.path.abspath(__file__))
                cfg_path = os.path.join(runner_dir, 'client.cfg')
                cfg_manager = get_config_manager(cfg_path if os.path.exists(cfg_path) else None)

            client_name = cfg_manager.get('DEFAULT', 'client_name', '').strip()
            if client_name:
                logger.debug(f"Client name from client.cfg: {client_name}")
                return client_name
        except Exception as e:
            logger.warning(f"Failed to read client name from client.cfg: {e}")

        # Finally use system hostname
        try:
            client_name = get_client_name().strip()
            if client_name:
                logger.debug(f"Client name from system hostname: {client_name}")
                return client_name
        except Exception as e:
            logger.error(f"Failed to get system hostname: {e}")

        # If all failed, return default value
        logger.warning("Could not determine client name, using default")
        return f"unknown-{self.local_ip.replace('.', '-')}" if hasattr(self, 'local_ip') else "unknown-client"

    def _setup_socketio_handlers(self):
        """Setup SocketIO event handlers"""

        @self.sio.event
        def connect():
            logger.info("Connected to server")
            # Join client-specific room using IP address instead of client name
            room_name = f"client_{self.local_ip.replace('.', '_')}"
            print(f"DEBUG: Joining room: {room_name}")
            self.sio.emit('join_room', {'room': room_name})

        @self.sio.event
        def disconnect():
            logger.warning("Disconnected from server")

        @self.sio.event
        def task_dispatch(data):
            """Receive task distribution (supports both legacy and Task format)"""
            try:
                task_id = data.get('task_id')
                task_name = data.get('name', f'Task-{task_id}')

                # Check if this is a task-based job
                if 'tasks' in data and data['tasks']:
                    # Enhanced logging for task reception
                    logger.info(f"📨 TASK_RECEIVED: '{task_name}' (ID: {task_id}) with {len(data['tasks'])} tasks from server")
                    logger.info(f"TASK_DETAILS: Client '{self.client_name}' received task assignment")

                    # Log tasks assigned to this client
                    my_tasks = [s for s in data['tasks'] if s.get('client') == self.client_name]
                    logger.info(f"TASK_ASSIGNMENT: {len(my_tasks)}/{len(data['tasks'])} tasks assigned to this client")

                    for i, Task in enumerate(my_tasks, 1):
                        logger.info(f"ASSIGNED_TASK[{i}]: '{Task.get('name')}' (order: {Task.get('order', 0)})")

                    logger.info(f"Received task-based job: {task_name} (ID: {task_id}) with {len(data['tasks'])} tasks")

                    # Execute task-based job in new thread
                    threading.Thread(
                        target=self._execute_job,
                        args=(task_id, task_name, data),
                        daemon=True
                    ).start()
                else:
                    logger.warning(f"Received task without tasks field: {task_name} (ID: {task_id}) - ignoring legacy format")

            except Exception as e:
                logger.error(f"Failed to handle task distribution: {e}")

        @self.sio.event
        def ping():
            """Respond to server ping"""
            self.sio.emit('pong', {'client_ip': self.local_ip, 'client_name': self.client_name})

        @self.sio.event
        def repo_update(data):
            """Handle repo update command from server — runs git pull in the specified directory."""
            try:
                repo_path = data.get('repo_path', '')
                target_client = data.get('client_name', '')

                # Only act if targeted at this client
                if target_client and target_client != self.client_name:
                    return

                if not repo_path:
                    # Default: update the ai-test project sibling directory
                    import configparser
                    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    cfg_path = os.path.join(project_root, 'common', 'common.cfg')
                    if os.path.exists(cfg_path):
                        cfg = configparser.ConfigParser()
                        cfg.read(cfg_path, encoding='utf-8')
                        repo_path = cfg.get('PATHS', 'ai_test_path', fallback='')
                    if not repo_path:
                        repo_path = os.path.normpath(os.path.join(project_root, '..', 'ai-test'))

                logger.info(f"REPO_UPDATE: Running git pull in {repo_path}")

                if not os.path.isdir(repo_path):
                    logger.error(f"REPO_UPDATE: Directory not found: {repo_path}")
                    self.sio.emit('repo_update_result', {
                        'client_name': self.client_name,
                        'success': False,
                        'error': f'Directory not found: {repo_path}',
                    })
                    return

                import subprocess
                result = subprocess.run(
                    ['git', 'pull'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                success = result.returncode == 0
                msg = result.stdout.strip() if success else result.stderr.strip()
                logger.info(f"REPO_UPDATE: {'Success' if success else 'Failed'} - {msg}")

                self.sio.emit('repo_update_result', {
                    'client_name': self.client_name,
                    'success': success,
                    'output': msg,
                    'repo_path': repo_path,
                })

            except Exception as e:
                logger.error(f"REPO_UPDATE: Failed: {e}")
                self.sio.emit('repo_update_result', {
                    'client_name': self.client_name,
                    'success': False,
                    'error': str(e),
                })

        @self.sio.event
        def ping_request(data):
            """Handle ping request from server and respond with real status"""
            try:
                requested_client = data.get('client_name')
                if requested_client == self.client_name:
                    logger.info(f"PING_REQUEST: Received ping request from server")

                    # Determine current status based on task execution state
                    current_status = self.get_current_status()

                    logger.info(f"PING_REQUEST: Responding with status '{current_status}' and fresh system info")

                    # Prepare ping response with fresh system information
                    additional_data = {
                        'client_ip': self.local_ip,
                        'current_task_id': getattr(self, 'current_task_id', None),
                        'current_task_id': getattr(self, 'current_task_id', None)
                    }

                    try:
                        ping_response_data = prepare_ping_response_data(
                            client_name=self.client_name,
                            additional_data=additional_data
                        )
                        # Update status from current execution state
                        ping_response_data['status'] = current_status

                        # Send response back to server with fresh system info
                        self.sio.emit('client_ping_response', ping_response_data)

                        logger.info(f"PING_RESPONSE: Sent response with fresh system information")

                    except Exception as e:
                        logger.warning(f"Failed to prepare ping response with fresh info, using fallback: {e}")
                        # Fallback to minimal response
                        self.sio.emit('client_ping_response', {
                            'client_name': self.client_name,
                            'client_ip': self.local_ip,
                            'status': current_status,
                            'timestamp': datetime.now().isoformat(),
                            'current_task_id': getattr(self, 'current_task_id', None),
                            'current_task_id': getattr(self, 'current_task_id', None),
                            'collection_source': 'ping_response_fallback'
                        })
                else:
                    logger.debug(f"PING_REQUEST: Ignoring ping for different client '{requested_client}'")

            except Exception as e:
                logger.error(f"Failed to handle ping request: {e}")

        @self.sio.event
        def task_cancelled(data):
            """Handle task cancellation from server"""
            try:
                task_id = data.get('task_id')
                logger.warning(f"Task {task_id} has been cancelled by server")

                # If task is running, mark as cancelled
                if hasattr(self, 'current_task_id') and self.current_task_id == task_id:
                    logger.info(f"Attempting to cancel currently running task {task_id}")
                    # Here we can add logic to stop current task execution

            except Exception as e:
                logger.error(f"Failed to handle task cancellation: {e}")

        @self.sio.event
        def client_unregistered(data):
            """Handle client unregistration notification from server"""
            try:
                client_name = data.get('client_name')
                reason = data.get('reason', 'client unregistered')
                timestamp = data.get('timestamp')

                if client_name == self.client_name:
                    logger.warning(f"This client ({client_name}) has been unregistered from the server")
                    logger.warning(f"Reason: {reason}")
                    logger.warning(f"Timestamp: {timestamp}")

                    # Set client to offline state
                    self.running = False

                    # Stop heartbeat if running
                    if hasattr(self, 'heartbeat_manager') and self.heartbeat_manager:
                        self.heartbeat_manager.stop()

                    # Disconnect from server
                    if self.sio and self.sio.connected:
                        logger.info("Disconnecting from server due to unregistration")
                        self.sio.disconnect()

                    logger.error("CLIENT OFFLINE: client has been unregistered by administrator")
                    logger.error("This client will now shut down. Please re-register the client to continue.")

                    # Exit the process gracefully
                    import os
                    os._exit(1)
            except Exception as e:
                logger.error(f"Failed to handle client unregistration: {e}")

        @self.sio.event
        def reload_tasks(data):
            """Handle task reload request from server"""
            try:
                client_name = data.get('client_name')

                # If specific client requested or broadcast to all
                if client_name == self.client_name or client_name is None:
                    logger.info(f"🔄 TASK_RELOAD: Received task reload request from server")

                    # reload tasks
                    try:
                        from common.tasks import reload_tasks
                        reloaded_count = reload_tasks()

                        logger.info(f"✅ TASK_RELOAD: Successfully reloaded {reloaded_count} task modules")

                        # Send response back to server
                        self.sio.emit('TASK_RELOAD_response', {
                            'client_name': self.client_name,
                            'success': True,
                            'reloaded_count': reloaded_count,
                            'message': f'Successfully reloaded {reloaded_count} task modules',
                            'timestamp': datetime.now().isoformat()
                        })

                    except Exception as e:
                        error_msg = str(e)
                        logger.error(f"❌ TASK_RELOAD: Failed to reload tasks: {error_msg}")

                        # Send error response back to server
                        self.sio.emit('TASK_RELOAD_response', {
                            'client_name': self.client_name,
                            'success': False,
                            'error': error_msg,
                            'message': f'Failed to reload tasks: {error_msg}',
                            'timestamp': datetime.now().isoformat()
                        })
                else:
                    logger.debug(f"TASK_RELOAD: Ignoring reload request for different client '{client_name}'")

            except Exception as e:
                logger.error(f"Failed to handle task reload request: {e}")

            except Exception as e:
                logger.error(f"Failed to handle client unregistration: {e}")

    def start(self):
        """Start client runtime"""
        if self.running:
            logger.warning("Client runtime is already running")
            return

        try:
            # Register client with server
            self._register_client()

            # Connect to server
            self._connect_to_server()

            # Start heartbeat
            self.heartbeat.start()

            # Start configuration update thread
            self._start_config_update_thread()

            self.running = True
            logger.info("Client runtime started")

            # Main loop
            self._main_loop()

        except Exception as e:
            logger.error(f"Failed to start client runtime: {e}")
            self.stop()

    def stop(self):
        """Stop client runtime"""
        if not self.running:
            return

        logger.info("Stopping client runtime...")

        self.running = False

        # Stop configuration update thread
        if self.config_update_thread and self.config_update_thread.is_alive():
            self.config_update_thread.join(timeout=2)

        # Unregister from server
        self._unregister_client()

        # Stop heartbeat
        if self.heartbeat:
            self.heartbeat.stop()

        # Disconnect SocketIO connection
        if self.sio.connected:
            self.sio.disconnect()

        logger.info("Client runtime stopped")

    def get_current_status(self):
        """
        Get the current status of the client based on its execution state

        Returns:
            str: 'free' if not executing tasks, 'busy' if executing tasks
        """
        try:
            # Check if currently executing a task
            if hasattr(self, 'current_task_id') and self.current_task_id is not None:
                return 'busy'

            # Check task adapter status if available
            if self.task_adapter and hasattr(self.task_adapter, 'is_executing'):
                if self.task_adapter.is_executing():
                    return 'busy'

            # Default to free if no active execution detected
            return 'free'

        except Exception as e:
            logger.warning(f"Error determining current status: {e}")
            return 'free'  # Default to free on error

    def run(self):
        """
        Run method for service wrapper integration
        This method can be called by the service wrapper to start and run the client
        """
        try:
            logger.info("Starting client runtime via run() method...")
            self.start()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Runtime error: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            self.stop()

    def _register_client(self):
        """Register client with server including system information"""
        try:
            logger.info("Preparing registration with fresh system information...")

            # DEBUG: Log the exact client name being used
            logger.info(f"DEBUG: Registering client with name: '{self.client_name}'")
            logger.info(f"DEBUG: client name type: {type(self.client_name)}")
            logger.info(f"DEBUG: client name length: {len(self.client_name)}")

            # Use unified client info collector
            registration_data = prepare_registration_data(
                client_name=self.client_name,
                ip_address=self.local_ip,
                port=8080
            )

            # Log system summary if available
            if 'system_summary' in registration_data:
                system_summary = registration_data['system_summary']
                logger.info(f"System summary: CPU: {system_summary.get('cpu', 'Unknown')}")
                logger.info(f"System summary: Memory: {system_summary.get('memory', 'Unknown')}")
                logger.info(f"System summary: GPU: {system_summary.get('gpu', 'Unknown')}")
                logger.info(f"System summary: OS: {system_summary.get('os', 'Unknown')}")

            response = requests.post(
                f"{self.server_url}/api/clients/register",
                json=registration_data,
                timeout=10
            )

            if response.status_code in [200, 201]:
                logger.info(f"client registered successfully: {self.client_name} ({self.local_ip})")
                self.last_config_update = datetime.now()
            else:
                logger.error(f"client registration failed: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Failed to register client: {e}")
            raise

    def _unregister_client(self):
        """Unregister client from server"""
        try:
            unregistration_data = {
                'name': self.client_name,
                'ip_address': self.local_ip,
                'status': 'offline'
            }

            response = requests.post(
                f"{self.server_url}/api/clients/unregister",
                json=unregistration_data,
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"client unregistered successfully: {self.client_name} ({self.local_ip})")
            else:
                logger.warning(f"client unregistration failed: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Failed to unregister client: {e}")

    def _connect_to_server(self):
        """Connect to server"""
        try:
            print(f"DEBUG: Attempting to connect to {self.server_url}")
            print(f"DEBUG: Client IP: {self.local_ip}")
            print(f"DEBUG: client name: {self.client_name}")
            self.sio.connect(self.server_url, wait_timeout=10)
            print("DEBUG: SocketIO connection successful")
            logger.info("Connected to server WebSocket")
        except Exception as e:
            print(f"DEBUG: Connection failed: {e}")
            logger.error(f"Failed to connect to server: {e}")
            raise

    def _main_loop(self):
        """Main runtime loop"""
        try:
            while self.running:
                time.sleep(1)

                # Check connection status
                if not self.sio.connected:
                    logger.warning("Connection lost, attempting to reconnect...")
                    try:
                        self.sio.connect(self.server_url)
                    except Exception as e:
                        logger.error(f"Reconnection failed: {e}")
                        time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Main loop exception: {e}")
        finally:
            self.stop()

    def _start_config_update_thread(self):
        """Start configuration and Task update thread"""
        def config_update_loop():
            task_check_elapsed = 0
            while self.running:
                try:
                    time.sleep(min(self.config_update_interval, self.task_reload_interval, 60))

                    if not self.running:
                        break

                    task_check_elapsed += min(self.config_update_interval, self.task_reload_interval, 60)

                    # Check for task changes periodically
                    if task_check_elapsed >= self.task_reload_interval:
                        task_check_elapsed = 0
                        self._check_and_reload_tasks()

                    # Update configuration information
                    self._update_client_config()

                except Exception as e:
                    logger.error(f"Configuration update error: {e}")

        self.config_update_thread = threading.Thread(target=config_update_loop, daemon=True)
        self.config_update_thread.start()
        logger.info(f"Started configuration update thread (interval: {self.config_update_interval}s)")
        logger.info(f"Task auto-reload enabled (interval: {self.task_reload_interval}s)")

    def _update_client_config(self):
        """Update client configuration information to server"""
        try:
            logger.info("Updating client configuration with fresh system information...")

            # Use unified client info collector for fresh configuration update
            update_data = prepare_registration_data(
                client_name=self.client_name,
                ip_address=self.local_ip,
                port=8080
            )

            response = requests.post(
                f"{self.server_url}/api/clients/update_config",
                json=update_data,
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"client configuration updated successfully: {self.client_name} ({self.local_ip})")
                self.last_config_update = datetime.now()

                # Log updated system information summary if available
                if 'system_summary' in update_data:
                    system_summary = update_data['system_summary']
                    logger.info(f"  Updated CPU: {system_summary.get('cpu', 'Unknown')}")
                    logger.info(f"  Updated Memory: {system_summary.get('memory', 'Unknown')}")
                    logger.info(f"  Updated GPU: {system_summary.get('gpu', 'Unknown')}")
            else:
                logger.error(f"client configuration update failed: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Failed to update client configuration: {e}")

    def _snapshot_tasks(self):
        """
        Take a snapshot of Task module files (name → mtime) so we can detect
        when the repo is updated (e.g. git pull adds or modifies a Task).
        """
        snapshot = {}
        try:
            import common.tasks as tasks_pkg
            tasks_dir = os.path.dirname(tasks_pkg.__file__)
            for filename in os.listdir(tasks_dir):
                if (filename.endswith('.py') and
                        filename not in ['__init__.py', 'base.py'] and
                        not filename.startswith('_')):
                    filepath = os.path.join(tasks_dir, filename)
                    snapshot[filename] = os.path.getmtime(filepath)
        except Exception as e:
            logger.debug(f"Could not snapshot task files: {e}")
        return snapshot

    def _check_and_reload_tasks(self):
        """
        Compare the current Task file snapshot against the saved one.
        If files were added, removed, or modified, reload task modules.
        """
        try:
            current = self._snapshot_tasks()
            if current != self._last_task_snapshot:
                added = set(current.keys()) - set(self._last_task_snapshot.keys())
                removed = set(self._last_task_snapshot.keys()) - set(current.keys())
                modified = {f for f in current if f in self._last_task_snapshot
                            and current[f] != self._last_task_snapshot[f]}

                changes = []
                if added:
                    changes.append(f"added: {', '.join(added)}")
                if removed:
                    changes.append(f"removed: {', '.join(removed)}")
                if modified:
                    changes.append(f"modified: {', '.join(modified)}")

                logger.info(f"task changes detected ({'; '.join(changes)}), reloading...")

                from common.tasks import reload_tasks
                reloaded = reload_tasks()
                self._last_task_snapshot = current
                logger.info(f"task reload complete: {reloaded} modules loaded")
            else:
                logger.debug("No task changes detected")
        except Exception as e:
            logger.error(f"Error checking/reloading tasks: {e}")

    def _execute_job(self, task_id, task_name, task_data):
        """Execute task-based job"""
        try:
            # Set current executing task ID
            self.current_task_id = task_id

            logger.info(f"Start executing task-based job: {task_name}")

            # Notify server task execution started
            self._notify_task_start(task_id)

            # Check if task adapter is available
            if not self.task_adapter:
                error_msg = "task adapter not available"
                logger.error(error_msg)
                self._notify_task_completion(task_id, False, error_msg)
                return

            # Execute task using task adapter
            result = self.task_adapter.execute_task(task_data)

            if result['success']:
                logger.info(f"task-based job {task_name} completed successfully")
                logger.info(f"Executed {result['executed_count']}/{result['total_count']} tasks")
                self._notify_task_completion(task_id, True, result['message'])
            else:
                logger.error(f"task-based job {task_name} failed: {result.get('message', 'Unknown error')}")
                self._notify_task_completion(task_id, False, result.get('message', 'Task execution failed'))

        except Exception as e:
            logger.error(f"Failed to execute task-based job {task_name}: {e}")
            self._notify_task_completion(task_id, False, str(e))
        finally:
            # Clear current task ID
            self.current_task_id = None

    def _notify_task_start(self, task_id):
        """Notify server task execution started"""
        try:
            data = {
                'task_id': task_id,
                'client_name': self.client_name,
                'client_ip': self.local_ip,
            }

            response = requests.post(
                f"{self.server_url}/api/execute",
                json=data,
                timeout=10
            )

            if response.status_code != 200:
                logger.warning(f"Failed to notify task start: {response.status_code}")

        except Exception as e:
            logger.error(f"Exception notifying task start: {e}")

    def _notify_task_completion(self, task_id, success, message):
        """Notify server task execution completed"""
        try:
            data = {
                'task_id': task_id,
                'client_name': self.client_name,
                'client_ip': self.local_ip,
                'success': success,
                'message': message
            }

            # Use the same endpoint for now (could be extended later)
            response = requests.post(
                f"{self.server_url}/api/execute",
                json=data,
                timeout=10
            )

            if response.status_code != 200:
                logger.warning(f"Failed to notify task completion: {response.status_code}")
            else:
                logger.info(f"Task {task_id} completion notified: {success} - {message}")

        except Exception as e:
            logger.error(f"Exception notifying task completion: {e}")

    def _save_intermediate_result(self, task_id, run_task_id, result):
        """Save intermediate result locally"""
        try:
            # Create task results directory
            task_results_dir = os.path.join(self.work_dir, 'task_results')
            os.makedirs(task_results_dir, exist_ok=True)

            # Save intermediate result
            result_file = os.path.join(task_results_dir, f'task_{task_id}_task_{run_task_id}.json')
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved intermediate result for task {task_id}, Task {TASK_id}")

        except Exception as e:
            logger.error(f"Failed to save intermediate result: {e}")

    def _upload_task_result(self, task_id, task_result):
        """Upload Task result to server immediately"""
        try:
            data = {
                'task_id': task_id,
                'client_name': self.client_name,
                'client_ip': self.local_ip,
                'task_result': task_result
            }

            response = requests.post(
                f"{self.server_url}/api/task_result",
                json=data,
                timeout=10
            )

            if response.status_code == 200:
                logger.debug(f"Uploaded Task result for task {task_id}, Task {task_result['TASK_id']}")
            else:
                logger.warning(f"Failed to upload Task result: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to upload Task result: {e}")

    def _send_task_result(self, task_id, result):
        """Send task execution result"""
        try:
            data = {
                'task_id': task_id,
                'client_name': self.client_name,
                'client_ip': self.local_ip,
                'success': result.get('success', False),
                'output': result.get('output', ''),
                'error': result.get('error', ''),
                'exit_code': result.get('exit_code', 0)
            }

            response = requests.post(
                f"{self.server_url}/api/result",
                json=data,
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"Task result sent successfully: {task_id}")
            else:
                logger.error(f"Failed to send task result: {response.status_code}")

        except Exception as e:
            logger.error(f"Exception sending task result: {e}")


def load_config(config_path):
    """Load configuration from file"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Failed to load configuration from {config_path}: {e}")
        return None


def main():
    """Main function for client runner"""
    parser = argparse.ArgumentParser(description='Task Client Runtime')

    # Optional arguments for override
    parser.add_argument('--config',
                       help='Configuration file path (optional)')
    parser.add_argument('--client-name',
                       help='Override client name (optional)')
    parser.add_argument('--server-url',
                       help='Override server URL (optional)')
    parser.add_argument('--cfg',
                       help='Client configuration file path (client.cfg)')
    parser.add_argument('--repo-root',
                       help='Repository root directory (for running from repo)')
    parser.add_argument('--log-level',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Override log level from config')

    args = parser.parse_args()

    # Auto-detect configuration
    # Auto-detect client.cfg file if not specified
    cfg_file = args.cfg
    if not cfg_file:
        # Look for client.cfg in current directory and parent directories
        current_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(current_dir, 'client.cfg'),
            os.path.join(os.path.dirname(current_dir), 'client', 'client.cfg'),
            'client.cfg'
        ]
        for path in possible_paths:
            if os.path.exists(path):
                cfg_file = path
                print(f"Auto-detected client.cfg: {cfg_file}")
                break

    # Load client.cfg configuration first
    cfg_manager = None
    if cfg_file and os.path.exists(cfg_file):
        cfg_manager = get_config_manager(cfg_file)

    try:
        # Get client name automatically
        client_name = args.client_name if args.client_name else get_client_name()

        # Get server URL - check client.cfg first, then common.cfg
        server_url = args.server_url
        if not server_url:
            # Try to get from client.cfg first
            if cfg_manager:
                server_host = cfg_manager.get('DEFAULT', 'server_host')
                if server_host:
                    # Get port from common.cfg
                    import configparser
                    try:
                        # Get path to common.cfg in common directory
                        client_dir = os.path.dirname(os.path.abspath(__file__))
                        project_root = os.path.dirname(client_dir)
                        common_cfg_path = os.path.join(project_root, 'common', 'common.cfg')
                        if os.path.exists(common_cfg_path):
                            common_config = configparser.ConfigParser()
                            common_config.read(common_cfg_path, encoding='utf-8')
                            port = common_config.get('SERVER', 'port', fallback='5000')
                            server_url = f"http://{server_host}:{port}"
                        else:
                            server_url = f"http://{server_host}:5000"
                    except Exception:
                        server_url = f"http://{server_host}:5000"

            # Fallback to common.cfg only
            if not server_url:
                server_url = get_server_url()

        print(f"Auto-detected client name: {client_name}")
        print(f"Auto-detected server URL: {server_url}")

        # Create configuration
        config = {
            'client_name': client_name,
            'server_url': server_url,
            'log_level': 'INFO'
        }

    except Exception as e:
        print(f"Failed to auto-detect configuration: {e}")
        sys.exit(1)

    # Load configuration file if provided
    if args.config:
        file_config = load_config(args.config)
        if file_config:
            # Override auto-detected values with file values
            config.update(file_config)
        else:
            print("Failed to load configuration file, using auto-detected values")

    # Override log level if specified
    if args.log_level:
        config['log_level'] = args.log_level
    elif cfg_manager:
        # Use log level from client.cfg if available
        cfg_log_level = cfg_manager.get('DEFAULT', 'log_level')
        if cfg_log_level:
            config['log_level'] = cfg_log_level

    # Setup logging
    log_level = config.get('log_level', 'INFO')
    setup_logging(log_level)

    # Validate configuration if cfg_manager is available
    if cfg_manager and not cfg_manager.validate_config():
        logger.error("Configuration validation failed")
        sys.exit(1)

    # Create and start client runner
    runner = TaskClientRunner(config, args.cfg)

    try:
        runner.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, exiting...")
    except Exception as e:
        logger.error(f"Client runner exception: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

