"""
Client Runtime Manager
Handles client execution, server communication, and task processing
Separated from installation logic for easier updates
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

# Ensure we can import local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import local modules (these will be copied to installation directory)
try:
    from common.system_info import get_system_info, get_system_summary
    from common.config import ClientConfig
    from common.utils import setup_logging, get_local_ip
    from executor import TaskExecutor
    from heartbeat import HeartbeatManager
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    print("Make sure the client is properly installed")
    sys.exit(1)

logger = logging.getLogger(__name__)

class TaskClientRunner:
    """
    Runtime client responsible only for execution and communication
    Installation and configuration management is handled separately
    """
    
    def __init__(self, config_data):
        """
        Initialize client runner with configuration
        
        Args:
            config_data: Configuration dictionary loaded from config file
        """
        self.config = config_data
        self.server_url = config_data['server_url']
        self.machine_name = config_data['machine_name']
        self.local_ip = get_local_ip()
        self.config_update_interval = config_data.get('config_update_interval', 600)
        self.last_config_update = None
        self.running = False
        self.task_results = {}
        
        # Working directories from config
        self.work_dir = config_data.get('work_dir', os.path.join(os.getcwd(), 'work'))
        self.log_dir = config_data.get('log_dir', os.path.join(os.getcwd(), 'logs'))
        
        # Ensure working directories exist
        os.makedirs(self.work_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Initialize components
        self.executor = TaskExecutor()
        self.heartbeat = HeartbeatManager(self.server_url, self.machine_name)
        
        # Initialize SocketIO client
        self.sio = socketio.Client()
        self._setup_socketio_handlers()
        
        # Configuration update thread
        self.config_update_thread = None
        
        logger.info(f"Client runner initialized: {self.machine_name} ({self.local_ip}) -> {self.server_url}")
        logger.info(f"Configuration update interval: {self.config_update_interval} seconds")
    
    def _setup_socketio_handlers(self):
        """Setup SocketIO event handlers"""
        
        @self.sio.event
        def connect():
            logger.info("Connected to server")
            # Join machine-specific room using machine name
            self.sio.emit('join_room', {'room': f"machine_{self.machine_name}"})
        
        @self.sio.event
        def disconnect():
            logger.warning("Disconnected from server")
        
        @self.sio.event
        def task_dispatch(data):
            """Receive task distribution"""
            try:
                task_id = data.get('task_id')
                task_name = data.get('name', f'Task-{task_id}')
                
                # 支持新的指令格式
                commands = data.get('commands', [])
                execution_order = data.get('execution_order', [])
                
                # 向后兼容旧的单指令格式
                if not commands and data.get('command'):
                    commands = [{
                        'id': 1,
                        'name': 'Default Command',
                        'command': data.get('command'),
                        'timeout': 300,
                        'retry_count': 0
                    }]
                    execution_order = [1]
                
                logger.info(f"Received task: {task_name} (ID: {task_id}) with {len(commands)} commands")
                
                # Execute task in new thread
                threading.Thread(
                    target=self._execute_task,
                    args=(task_id, task_name, commands, execution_order),
                    daemon=True
                ).start()
                
            except Exception as e:
                logger.error(f"Failed to handle task distribution: {e}")
        
        @self.sio.event
        def ping():
            """Respond to server ping"""
            self.sio.emit('pong', {'machine_ip': self.local_ip, 'machine_name': self.machine_name})
        
        @self.sio.event
        def task_cancelled(data):
            """Handle task cancellation from server"""
            try:
                task_id = data.get('task_id')
                logger.warning(f"Task {task_id} has been cancelled by server")
                
                # 如果任务正在执行，标记为取消状态
                if hasattr(self, 'current_task_id') and self.current_task_id == task_id:
                    logger.info(f"Attempting to cancel currently running task {task_id}")
                    # 这里可以添加停止当前任务执行的逻辑
                
            except Exception as e:
                logger.error(f"Failed to handle task cancellation: {e}")
    
    def start(self):
        """Start client runtime"""
        if self.running:
            logger.warning("Client runtime is already running")
            return
        
        try:
            # Register machine with server
            self._register_machine()
            
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
        self._unregister_machine()
        
        # Stop heartbeat
        if self.heartbeat:
            self.heartbeat.stop()
        
        # Disconnect SocketIO connection
        if self.sio.connected:
            self.sio.disconnect()
        
        # Stop task executor
        if self.executor:
            self.executor.stop()
        
        logger.info("Client runtime stopped")
    
    def _register_machine(self):
        """Register machine with server including system information"""
        try:
            logger.info("Collecting system information...")
            system_info = get_system_info()
            system_summary = get_system_summary()
            
            registration_data = {
                'name': self.machine_name,
                'ip_address': self.local_ip,
                'port': 8080,
                'capabilities': ['shell', 'python', 'general'],
                'status': 'online',
                # System information
                'cpu_info': system_info['cpu'],
                'memory_info': system_info['memory'],
                'gpu_info': system_info['gpu'],
                'os_info': system_info['os'],
                'disk_info': system_info['disk'],
                'system_summary': system_summary
            }
            
            logger.info(f"System summary: CPU: {system_summary.get('cpu', 'Unknown')}")
            logger.info(f"System summary: Memory: {system_summary.get('memory', 'Unknown')}")
            logger.info(f"System summary: GPU: {system_summary.get('gpu', 'Unknown')}")
            logger.info(f"System summary: OS: {system_summary.get('os', 'Unknown')}")
            
            response = requests.post(
                f"{self.server_url}/api/machines/register",
                json=registration_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Machine registered successfully: {self.machine_name} ({self.local_ip})")
                self.last_config_update = datetime.now()
            else:
                logger.error(f"Machine registration failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Failed to register machine: {e}")
            raise
    
    def _unregister_machine(self):
        """Unregister machine from server"""
        try:
            unregistration_data = {
                'name': self.machine_name,
                'ip_address': self.local_ip,
                'status': 'offline'
            }
            
            response = requests.post(
                f"{self.server_url}/api/machines/unregister",
                json=unregistration_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Machine unregistered successfully: {self.machine_name} ({self.local_ip})")
            else:
                logger.warning(f"Machine unregistration failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Failed to unregister machine: {e}")
    
    def _connect_to_server(self):
        """Connect to server"""
        try:
            self.sio.connect(self.server_url)
            logger.info("Connected to server WebSocket")
        except Exception as e:
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
        """启动配置更新线程"""
        def config_update_loop():
            while self.running:
                try:
                    # 等待指定的时间间隔
                    time.sleep(self.config_update_interval)
                    
                    if not self.running:
                        break
                    
                    # 更新配置信息
                    self._update_machine_config()
                    
                except Exception as e:
                    logger.error(f"Configuration update error: {e}")
        
        self.config_update_thread = threading.Thread(target=config_update_loop, daemon=True)
        self.config_update_thread.start()
        logger.info(f"Started configuration update thread (interval: {self.config_update_interval}s)")
    
    def _update_machine_config(self):
        """更新机器配置信息到服务器"""
        try:
            logger.info("Updating machine configuration...")
            
            # 重新收集系统信息
            system_info = get_system_info()
            system_summary = get_system_summary()
            
            update_data = {
                'name': self.machine_name,
                'ip_address': self.local_ip,
                'port': 8080,
                'capabilities': ['shell', 'python', 'general'],
                # 更新的系统信息
                'cpu_info': system_info['cpu'],
                'memory_info': system_info['memory'],
                'gpu_info': system_info['gpu'],
                'os_info': system_info['os'],
                'disk_info': system_info['disk'],
                'system_summary': system_summary
            }
            
            response = requests.post(
                f"{self.server_url}/api/machines/update_config",
                json=update_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Machine configuration updated successfully: {self.machine_name} ({self.local_ip})")
                self.last_config_update = datetime.now()
                
                # 记录更新的系统信息摘要
                if system_summary:
                    logger.info(f"  Updated CPU: {system_summary.get('cpu', 'Unknown')}")
                    logger.info(f"  Updated Memory: {system_summary.get('memory', 'Unknown')}")
                    logger.info(f"  Updated GPU: {system_summary.get('gpu', 'Unknown')}")
            else:
                logger.error(f"Machine configuration update failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Failed to update machine configuration: {e}")
    
    def _execute_task(self, task_id, task_name, commands, execution_order):
        """Execute task with multiple commands in specified order"""
        try:
            # 设置当前执行的任务ID
            self.current_task_id = task_id
            
            logger.info(f"Start executing task: {task_name} with {len(commands)} commands")
            
            # Notify server task execution started
            self._notify_task_start(task_id)
            
            # 按照执行顺序执行指令
            overall_success = True
            subtask_results = []
            overall_errors = []
            
            # 创建指令ID到指令的映射
            command_map = {cmd['id']: cmd for cmd in commands}
            
            for cmd_id in execution_order:
                if cmd_id not in command_map:
                    error_msg = f"Command ID {cmd_id} not found in commands list"
                    logger.error(error_msg)
                    overall_errors.append(error_msg)
                    overall_success = False
                    continue
                
                cmd = command_map[cmd_id]
                cmd_name = cmd.get('name', f'Command-{cmd_id}')
                cmd_command = cmd.get('command', '')
                cmd_timeout = cmd.get('timeout', 300)
                
                logger.info(f"Executing subtask {cmd_id}: {cmd_name}")
                
                try:
                    # Execute individual command
                    result = self.executor.execute(cmd_command, timeout=cmd_timeout)
                    
                    # 记录subtask结果
                    subtask_result = {
                        'subtask_id': cmd_id,
                        'subtask_name': cmd_name,
                        'command': cmd_command,
                        'success': result.get('success', False),
                        'output': result.get('output', ''),
                        'error': result.get('error', ''),
                        'exit_code': result.get('exit_code', 0),
                        'duration': result.get('duration', 0),
                        'completed_at': datetime.now().isoformat()
                    }
                    
                    subtask_results.append(subtask_result)
                    
                    # 保存中间结果到本地
                    self._save_intermediate_result(task_id, cmd_id, subtask_result)
                    
                    # 立即上传subtask结果到服务器
                    self._upload_subtask_result(task_id, subtask_result)
                    
                    if not result.get('success', False):
                        overall_success = False
                        error_msg = f"Subtask {cmd_id} failed: {result.get('error', 'Unknown error')}"
                        overall_errors.append(error_msg)
                        logger.warning(error_msg)
                        
                        # 检查是否应该继续执行后续指令
                        if cmd.get('stop_on_failure', False):
                            logger.info(f"Stopping execution due to subtask {cmd_id} failure")
                            break
                    else:
                        logger.info(f"Subtask {cmd_id} completed successfully")
                        
                except Exception as e:
                    error_msg = f"Exception executing subtask {cmd_id}: {str(e)}"
                    logger.error(error_msg)
                    overall_errors.append(error_msg)
                    overall_success = False
                    
                    # 记录失败的subtask结果
                    subtask_result = {
                        'subtask_id': cmd_id,
                        'subtask_name': cmd_name,
                        'command': cmd_command,
                        'success': False,
                        'output': '',
                        'error': str(e),
                        'exit_code': -1,
                        'duration': 0,
                        'completed_at': datetime.now().isoformat()
                    }
                    subtask_results.append(subtask_result)
                    self._save_intermediate_result(task_id, cmd_id, subtask_result)
                    self._upload_subtask_result(task_id, subtask_result)
                    
                    if cmd.get('stop_on_failure', False):
                        logger.info(f"Stopping execution due to subtask {cmd_id} exception")
                        break
            
            # Prepare final result with all subtask results
            final_result = {
                'success': overall_success,
                'subtask_results': subtask_results,
                'total_subtasks': len(subtask_results),
                'successful_subtasks': len([r for r in subtask_results if r['success']]),
                'failed_subtasks': len([r for r in subtask_results if not r['success']]),
                'error': '\n'.join(overall_errors) if overall_errors else '',
                'exit_code': 0 if overall_success else 1
            }
            
            # Send final task result
            self._send_task_result(task_id, final_result)
            
            logger.info(f"Task execution completed: {task_name} (Success: {overall_success}, {len(subtask_results)} subtasks)")
            
        except Exception as e:
            logger.error(f"Failed to execute task: {e}")
            # Send failure result
            self._send_task_result(task_id, {
                'success': False,
                'subtask_results': [],
                'total_subtasks': 0,
                'successful_subtasks': 0,
                'failed_subtasks': 0,
                'error': str(e),
                'exit_code': -1
            })
        finally:
            # 清除当前任务ID
            self.current_task_id = None
    
    def _notify_task_start(self, task_id):
        """Notify server task execution started"""
        try:
            data = {
                'task_id': task_id,
                'machine_name': self.machine_name,
                'machine_ip': self.local_ip,
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
    
    def _save_intermediate_result(self, task_id, subtask_id, result):
        """Save intermediate result locally"""
        try:
            # 创建任务结果目录
            task_results_dir = os.path.join(self.work_dir, 'task_results')
            os.makedirs(task_results_dir, exist_ok=True)
            
            # 保存中间结果
            result_file = os.path.join(task_results_dir, f'task_{task_id}_subtask_{subtask_id}.json')
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved intermediate result for task {task_id}, subtask {subtask_id}")
            
        except Exception as e:
            logger.error(f"Failed to save intermediate result: {e}")
    
    def _upload_subtask_result(self, task_id, subtask_result):
        """Upload subtask result to server immediately"""
        try:
            data = {
                'task_id': task_id,
                'machine_name': self.machine_name,
                'machine_ip': self.local_ip,
                'subtask_result': subtask_result
            }
            
            response = requests.post(
                f"{self.server_url}/api/subtask_result",
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.debug(f"Uploaded subtask result for task {task_id}, subtask {subtask_result['subtask_id']}")
            else:
                logger.warning(f"Failed to upload subtask result: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to upload subtask result: {e}")
    
    def _send_task_result(self, task_id, result):
        """Send task execution result"""
        try:
            data = {
                'task_id': task_id,
                'machine_name': self.machine_name,
                'machine_ip': self.local_ip,
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
    parser.add_argument('--config', required=True,
                       help='Configuration file path (required)')
    parser.add_argument('--log-level', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Override log level from config')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    if not config:
        print("Failed to load configuration")
        sys.exit(1)
    
    # Override log level if specified
    if args.log_level:
        config['log_level'] = args.log_level
    
    # Setup logging
    log_level = config.get('log_level', 'INFO')
    setup_logging(log_level)
    
    # Create and start client runner
    runner = TaskClientRunner(config)
    
    try:
        runner.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, exiting...")
    except Exception as e:
        logger.error(f"Client runner exception: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
