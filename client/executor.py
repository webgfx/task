"""
Task executor
Responsible for executing commands locally and returning results
"""
import os
import subprocess
import logging
import threading
import signal
import time
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class TaskExecutor:
    def __init__(self):
        self.running_processes = {}
        self.process_lock = threading.Lock()
        
    def execute(self, subtask: str, timeout: int = 300, work_dir: str = None) -> Dict[str, Any]:
        """
        Execute subtask
        
        Args:
            subtask: Subtask to execute
            timeout: Timeout (seconds)
            work_dir: Working directory
            
        Returns:
            Execution result dictionary containing success, output, error, exit_code
        """
        try:
            logger.info(f"Start executing command: {command}")
            start_time = datetime.now()
            
            # Set working directory
            if not work_dir:
                work_dir = os.getcwd()
            
            # Set command execution method based on operating system
            if os.name == 'nt':  # Windows
                # Use cmd for execution on Windows
                full_command = ['cmd', '/c', command]
                shell = False
            else:  # Unix/Linux
                # Use shell for execution on Unix/Linux
                full_command = command
                shell = True
            
            # Create process
            process = subprocess.Popen(
                full_command,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=work_dir,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Record process
            process_id = id(process)
            with self.process_lock:
                self.running_processes[process_id] = {
                    'process': process,
                    'command': command,
                    'start_time': start_time
                }
            
            try:
                # Wait for process completion or timeout
                stdout, stderr = process.communicate(timeout=timeout)
                exit_code = process.returncode
                
                # Remove process record
                with self.process_lock:
                    self.running_processes.pop(process_id, None)
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                success = exit_code == 0
                
                result = {
                    'success': success,
                    'output': stdout.strip() if stdout else '',
                    'error': stderr.strip() if stderr else '',
                    'exit_code': exit_code,
                    'duration': duration,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat()
                }
                
                if success:
                    logger.info(f"Command execution successful, duration: {duration:.2f} seconds")
                else:
                    logger.warning(f"Command execution failed, exit code: {exit_code}, duration: {duration:.2f} seconds")
                
                return result
                
            except subprocess.TimeoutExpired:
                # Timeout, forcefully terminate process
                logger.warning(f"Command execution timeout ({timeout} seconds), terminating process")
                self._terminate_process(process)
                
                with self.process_lock:
                    self.running_processes.pop(process_id, None)
                
                return {
                    'success': False,
                    'output': '',
                    'error': f'Command execution timeout ({timeout} seconds)',
                    'exit_code': -1,
                    'duration': timeout,
                    'start_time': start_time.isoformat(),
                    'end_time': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Command exception: {e}")
            return {
                'success': False,
                'output': '',
                'error': f'Execution exception: {str(e)}',
                'exit_code': -1,
                'duration': 0,
                'start_time': start_time.isoformat() if 'start_time' in locals() else None,
                'end_time': datetime.now().isoformat()
            }
    
    def _terminate_process(self, process: subprocess.Popen):
        """Terminate process"""
        try:
            if os.name == 'nt':  # Windows
                # Send CTRL_BREAK_EVENT on Windows
                process.send_signal(signal.CTRL_BREAK_EVENT)
                time.sleep(2)
                if process.poll() is None:
                    # If process is still running, forcefully terminate
                    process.terminate()
                    time.sleep(1)
                    if process.poll() is None:
                        process.kill()
            else:  # Unix/Linux
                # Send SIGTERM on Unix/Linux
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    # If process is still running, send SIGKILL
                    process.kill()
                    
        except Exception as e:
            logger.error(f"Failed to terminate process: {e}")
    
    def get_running_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get running process information"""
        with self.process_lock:
            result = {}
            for process_id, info in self.running_processes.items():
                result[process_id] = {
                    'command': info['command'],
                    'start_time': info['start_time'].isoformat(),
                    'duration': (datetime.now() - info['start_time']).total_seconds(),
                    'pid': info['process'].pid
                }
            return result
    
    def stop_all_processes(self):
        """Stop all running processes"""
        with self.process_lock:
            for process_id, info in list(self.running_processes.items()):
                try:
                    logger.info(f"Stopping process: {info['command']}")
                    self._terminate_process(info['process'])
                except Exception as e:
                    logger.error(f"Failed to stop process: {e}")
            
            self.running_processes.clear()
    
    def stop(self):
        """Stop executor"""
        logger.info("Stopping Task executor...")
        self.stop_all_processes()
        logger.info("Task executor stopped")

# Predefined command templates
COMMAND_TEMPLATES = {
    'python': 'python {script}',
    'python3': 'python3 {script}',
    'node': 'node {script}',
    'bash': 'bash {script}',
    'cmd': 'cmd /c {command}',
    'powershell': 'powershell -Command "{command}"',
    'git_pull': 'git pull origin {branch}',
    'git_clone': 'git clone {repo_url} {target_dir}',
    'docker_run': 'docker run --rm {image} {command}',
    'pip_install': 'pip install {packages}',
    'npm_install': 'npm install {packages}',
    'systemctl': 'systemctl {action} {service}',
    'service': 'service {service} {action}',
    'backup': 'tar -czf {backup_file} {source_dir}',
    'sync': 'rsync -av {source} {destination}'
}

def get_command_template(template_name: str) -> Optional[str]:
    """Get command template"""
    return COMMAND_TEMPLATES.get(template_name)

def list_command_templates() -> Dict[str, str]:
    """List all command templates"""
    return COMMAND_TEMPLATES.copy()

