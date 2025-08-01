"""
Windows Service implementation for Task Management Client
"""
import os
import sys
import time
import json
import logging
import tempfile
import platform
import socket
from pathlib import Path

# Fix Python path for Windows service
def fix_service_path():
    """Fix Python path for Windows service execution"""
    # Get the directory where this service.py file is located
    service_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(service_dir)
    
    # Add project root to Python path if not already present
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Also add service directory for relative imports
    if service_dir not in sys.path:
        sys.path.insert(0, service_dir)
    
    # Change working directory to project root for consistent file operations
    try:
        os.chdir(project_root)
    except Exception:
        pass  # If we can't change directory, continue anyway
    
    return project_root

# Fix path immediately
project_root = fix_service_path()

# Only import Windows-specific modules on Windows
if platform.system() == 'Windows':
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
else:
    # Mock classes for non-Windows systems - this should not be used on Windows
    print("Warning: Running on non-Windows system, service functionality disabled")
    class MockServiceFramework:
        pass
    win32serviceutil = MockServiceFramework()
    win32service = MockServiceFramework()
    win32event = MockServiceFramework()
    servicemanager = MockServiceFramework()

# Import project modules after path fix
try:
    from common.system_info import get_system_info, get_system_summary
    from common.config import ClientConfig
    from common.utils import setup_logging
except ImportError as e:
    # If imports fail, we'll handle it later in the service
    print(f"Warning: Failed to import common modules: {e}")

def check_windows_service_support():
    """Check if Windows service support is available"""
    if platform.system() != 'Windows':
        raise RuntimeError("Windows services are only supported on Windows")
    
    try:
        # Test if we can access the required modules
        win32serviceutil.InstallService
        win32service.SERVICE_RUNNING
        win32event.CreateEvent
        servicemanager.LogMsg
        return True
    except AttributeError as e:
        raise RuntimeError(f"Windows service modules not properly loaded: {e}")
    except Exception as e:
        raise RuntimeError(f"Windows service support check failed: {e}")

def generate_client_name():
    """Generate client name using hostname only"""
    try:
        hostname = platform.node()
        return hostname
    except Exception:
        # Ultimate fallback
        return f"windows-{platform.node()}"

class TaskClientService(win32serviceutil.ServiceFramework):
    """Windows Service for Task Management Client"""
    
    _svc_name_ = "WebGraphicsService"
    _svc_display_name_ = "Web Graphics Service"
    _svc_description_ = "Client service for distributed task execution and management"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.client = None
        self.config_file = None
        self.logger = None
        
    def SvcStop(self):
        """Stop the service"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        
        if self.logger:
            self.logger.info("Service stop requested")
        
        # Unregister from server
        if self.client:
            try:
                self.client._unregister_client()
                self.client.stop()
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error stopping client: {e}")
        
        win32event.SetEvent(self.hWaitStop)
        
        if self.logger:
            self.logger.info("Service stopped")
    
    def SvcDoRun(self):
        """Run the service"""
        try:
            # Initialize logging for service
            self._setup_service_logging()
            
            if not self.logger:
                # Fallback logging if setup failed
                import logging
                logging.basicConfig(level=logging.INFO)
                self.logger = logging.getLogger(__name__)
            
            self.logger.info("Service starting...")
            
            # Load configuration
            config = self._load_config()
            if not config:
                self.logger.error("Failed to load configuration, creating default config")
                config = {
                    'server_url': 'http://localhost:5000',
                    'client_name': generate_client_name(),
                    'heartbeat_interval': 600
                }
            
            # Log service start
            try:
                servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                                    servicemanager.PYS_SERVICE_STARTED,
                                    (self._svc_name_, ''))
            except Exception as e:
                self.logger.warning(f"Failed to log to event manager: {e}")
            
            self.logger.info(f"Starting Web Graphics Service")
            self.logger.info(f"Server URL: {config.get('server_url')}")
            self.logger.info(f"client Name: {config.get('client_name')}")
            
            # Wait a moment for system to stabilize
            import time
            time.sleep(2)
            
            # Create and start client with error handling
            try:
                self.logger.info("Fixing Python path for service execution...")
                # Re-fix path in case service changed working directory
                fix_service_path()
                
                self.logger.info("Importing TaskClient...")
                # Import TaskClient dynamically to avoid import issues at module level
                try:
                    # Use new modular client architecture
                    from client.client_runner import TaskClientRunner
                    from client.config_manager import get_config_manager
                    self.logger.info("TaskClientRunner imported successfully")
                except ImportError as e:
                    self.logger.error(f"Failed to import TaskClientRunner: {e}")
                    self.logger.info("Attempting alternative import...")
                    # Try absolute import
                    import importlib.util
                    runner_path = os.path.join(project_root, 'client', 'client_runner.py')
                    spec = importlib.util.spec_from_file_location("client.client_runner", runner_path)
                    runner_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(runner_module)
                    TaskClientRunner = runner_module.TaskClientRunner
                    self.logger.info("TaskClientRunner imported via alternative method")
                
                self.logger.info("Creating TaskClientRunner instance...")
                
                # Create a configuration data structure for the runner
                runner_config = {
                    'server_url': config.get('server_url', 'http://localhost:5000'),
                    'client_name': config.get('client_name', 'default-client'),
                    'heartbeat_interval': config.get('heartbeat_interval', 30),
                    'config_update_interval': config.get('config_update_interval', 600),
                    'log_level': config.get('log_level', 'INFO'),
                    'log_dir': os.path.join(os.path.dirname(__file__), 'logs'),
                    'work_dir': os.path.join(os.path.dirname(__file__), 'work')
                }
                
                self.client = TaskClientRunner(runner_config)
                self.logger.info("TaskClientRunner instance created successfully")
                
                # Start client in separate thread with delay
                import threading
                client_thread = threading.Thread(target=self._delayed_client_start)
                client_thread.daemon = True
                client_thread.start()
                
                self.logger.info("Client thread started successfully")
                
            except Exception as e:
                self.logger.error(f"Failed to create/start client: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                # Don't exit immediately, keep service running for monitoring
            
            # Wait for stop signal
            self.logger.info("Service main loop started, waiting for stop signal")
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
            
        except Exception as e:
            error_msg = f"Service critical error: {e}"
            if self.logger:
                self.logger.error(error_msg)
                import traceback
                self.logger.error(traceback.format_exc())
            try:
                servicemanager.LogErrorMsg(error_msg)
            except:
                pass
            # Re-raise to ensure service stops properly
            raise
    
    def _delayed_client_start(self):
        """Start the client with delay to allow service to fully initialize"""
        try:
            import time
            time.sleep(5)  # Wait 5 seconds before starting client
            
            if self.client:
                self.logger.info("Starting TaskClient...")
                self.client.start()
                self.logger.info("TaskClient started successfully")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Delayed client start error: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            else:
                print(f"Delayed client start error: {e}")
                
    def _safe_client_start(self):
        """Safely start the client with error handling (deprecated, use _delayed_client_start)"""
        try:
            if self.client:
                self.client.start()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Client start error: {e}")
            else:
                print(f"Client start error: {e}")
    
    def _setup_service_logging(self):
        """Setup logging for Windows service"""
        try:
            # Create logs directory
            log_dir = Path("C:/WebGraphicsService/logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Setup logging
            log_file = log_dir / "service.log"
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file),
                    logging.StreamHandler()
                ]
            )
            
            self.logger = logging.getLogger(__name__)
            self.logger.info("Service logging initialized")
            
        except Exception as e:
            # Fallback to basic logging
            self.logger = logging.getLogger(__name__)
            self.logger.error(f"Failed to setup service logging: {e}")
    
    def _load_config(self):
        """Load service configuration"""
        try:
            # First try to read server address from common.cfg
            server_url = self._read_server_ip()
            
            # Try multiple config file locations
            config_files = [
                "C:/WebGraphicsService/config.json",
                Path(project_root) / "client_config.json",
                Path(tempfile.gettempdir()) / "web_graphics_tasks_config.json"
            ]
            
            config = None
            for config_file in config_files:
                if Path(config_file).exists():
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        self.logger.info(f"Loaded config from: {config_file}")
                        break
            
            # If no config file found, create default configuration
            if not config:
                config = {
                    'client_name': generate_client_name(),
                    'heartbeat_interval': 30,
                    'log_level': 'INFO'
                }
                self.logger.warning("No config file found, using defaults")
            
            # Override server_url with value from common.cfg if available
            if server_url:
                config['server_url'] = server_url
                self.logger.info(f"Using server URL from common.cfg: {server_url}")
            elif 'server_url' not in config:
                config['server_url'] = 'http://localhost:5000'
                self.logger.warning("Using default server URL: http://localhost:5000")
            
            return config
            
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return None
    
    def _read_server_ip(self):
        """Read server address from common.cfg file"""
        try:
            import configparser
            
            # Try common.cfg first
            common_cfg_file = Path(project_root) / "common" / "common.cfg"
            
            if common_cfg_file.exists():
                config = configparser.ConfigParser()
                config.read(common_cfg_file, encoding='utf-8')
                
                # Get host and port from common.cfg
                host = config.get('SERVER', 'host', fallback='127.0.0.1')
                port = config.get('SERVER', 'port', fallback='5000')
                
                server_url = f"http://{host}:{port}"
                self.logger.info(f"Read server address from {common_cfg_file}: {server_url}")
                return server_url
            else:
                self.logger.info(f"common.cfg file not found at {common_cfg_file}")
                
        except Exception as e:
            self.logger.error(f"Failed to read server address from common.cfg: {e}")
        
        return None

    def _unregister_client(self):
        """Unregister client from server when service stops"""
        if not self.client:
            return
            
        try:
            import requests
            
            data = {
                'name': self.client.client_name,
                'status': 'offline'
            }
            
            response = requests.post(
                f"{self.client.server_url}/api/clients/unregister",
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info(f"client unregistered successfully: {self.client.client_name}")
            else:
                self.logger.warning(f"Failed to unregister client: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Error unregistering client: {e}")

def install_service(server_url=None, client_name=None):
    """Install the Windows service"""
    try:
        # Check Windows service support first
        check_windows_service_support()
        
        # Create config directory
        config_dir = Path("C:/WebGraphicsService")
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to read server URL from common.cfg if not provided
        if not server_url:
            server_url = _read_server_ip_for_install()
        
        # Create configuration file
        config = {
            'server_url': server_url or 'http://localhost:5000',
            'client_name': client_name or generate_client_name(),
            'heartbeat_interval': 600,  # 10 minutes
            'log_level': 'INFO'
        }
        
        config_file = config_dir / "config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Configuration saved to: {config_file}")
        print(f"  Server URL: {config['server_url']}")
        print(f"  client Name: {config['client_name']}")
        print(f"  Heartbeat Interval: {config['heartbeat_interval']} seconds (10 minutes)")
        
        # Install service with explicit string encoding
        service_name = str(TaskClientService._svc_name_)
        display_name = str(TaskClientService._svc_display_name_)
        description = str(TaskClientService._svc_description_)
        
        # Get absolute paths for service installation
        service_script = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(service_script))
        
        print(f"  Service script: {service_script}")
        print(f"  Project root: {project_root}")
        
        # Install service with proper paths
        # Use string path to the class, not the class object itself
        python_class_string = f"{TaskClientService.__module__}.{TaskClientService.__name__}"
        
        win32serviceutil.InstallService(
            python_class_string,  # Use string path to class
            service_name,
            display_name,
            description=description,
            startType=win32service.SERVICE_AUTO_START,
            exeName=sys.executable,  # Python executable
            exeArgs=f'"{service_script}"'  # Service script path
        )
        
        print(f"✓ Service '{display_name}' installed successfully")
        print(f"  Service Name: {service_name}")
        print("  Use 'net start WebGraphicsService' to start the service")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to install service: {e}")
        import traceback
        traceback.print_exc()
        return False

def _read_server_ip_for_install():
    """Read server address from common.cfg file during installation"""
    try:
        import configparser
        
        # Get project root directory
        current_dir = Path(__file__).parent.parent
        common_cfg_file = current_dir / "common" / "common.cfg"
        
        if common_cfg_file.exists():
            config = configparser.ConfigParser()
            config.read(common_cfg_file, encoding='utf-8')
            
            # Get host and port from common.cfg
            host = config.get('SERVER', 'host', fallback='127.0.0.1')
            port = config.get('SERVER', 'port', fallback='5000')
            
            server_url = f"http://{host}:{port}"
            print(f"✓ Read server address from {common_cfg_file}: {server_url}")
            return server_url
        else:
            print(f"ℹ️  common.cfg file not found at {common_cfg_file}")
            print(f"   Using default server configuration")
            
    except Exception as e:
        print(f"⚠️  Failed to read server address from common.cfg: {e}")
    
    return None

def uninstall_service():
    """Uninstall the Windows service"""
    try:
        # Stop service if running
        service_name = str(TaskClientService._svc_name_)
        try:
            win32serviceutil.StopService(service_name)
            print("✓ Service stopped")
        except Exception:
            pass  # Service might not be running
        
        # Remove service
        win32serviceutil.RemoveService(service_name)
        print(f"✓ Service '{TaskClientService._svc_display_name_}' uninstalled successfully")
        
        # Optionally remove config files
        config_file = Path("C:/WebGraphicsService/config.json")
        if config_file.exists():
            try:
                config_file.unlink()
                print("✓ Configuration file removed")
            except Exception as e:
                print(f"⚠️  Could not remove config file: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to uninstall service: {e}")
        import traceback
        traceback.print_exc()
        return False

def start_service():
    """Start the Windows service"""
    try:
        service_name = str(TaskClientService._svc_name_)
        win32serviceutil.StartService(service_name)
        print(f"✓ Service '{TaskClientService._svc_display_name_}' started successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to start service: {e}")
        return False

def stop_service():
    """Stop the Windows service"""
    try:
        service_name = str(TaskClientService._svc_name_)
        win32serviceutil.StopService(service_name)
        print(f"✓ Service '{TaskClientService._svc_display_name_}' stopped successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to stop service: {e}")
        return False

def restart_service():
    """Restart the Windows service"""
    try:
        service_name = str(TaskClientService._svc_name_)
        win32serviceutil.RestartService(service_name)
        print(f"✓ Service '{TaskClientService._svc_display_name_}' restarted successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to restart service: {e}")
        return False

def status_service():
    """Check service status"""
    try:
        service_name = str(TaskClientService._svc_name_)
        status = win32serviceutil.QueryServiceStatus(service_name)
        status_text = {
            win32service.SERVICE_STOPPED: "STOPPED",
            win32service.SERVICE_START_PENDING: "START_PENDING",
            win32service.SERVICE_STOP_PENDING: "STOP_PENDING",
            win32service.SERVICE_RUNNING: "RUNNING",
            win32service.SERVICE_CONTINUE_PENDING: "CONTINUE_PENDING",
            win32service.SERVICE_PAUSE_PENDING: "PAUSE_PENDING",
            win32service.SERVICE_PAUSED: "PAUSED"
        }.get(status[1], "UNKNOWN")
        
        print(f"Service Status: {status_text}")
        
        # Show config if service exists
        config_file = Path("C:/WebGraphicsService/config.json")
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"Server URL: {config.get('server_url', 'Unknown')}")
                print(f"client Name: {config.get('client_name', 'Unknown')}")
            except Exception:
                pass
        
        return True
        
    except Exception as e:
        print(f"❌ Service not found or error checking status: {e}")
        return False

def debug_service():
    """Debug mode - test service initialization without running as service"""
    print("=== Service Debug Mode ===")
    try:
        print("Testing path configuration...")
        project_root = fix_service_path()
        print(f"✓ Project root: {project_root}")
        print(f"✓ Current working directory: {os.getcwd()}")
        print(f"✓ Service script location: {__file__}")
        print(f"✓ Python executable: {sys.executable}")
        print(f"✓ Python path (first 5): {sys.path[:5]}")
        
        # Test if key files exist
        runner_file = os.path.join(project_root, 'client', 'client_runner.py')
        print(f"✓ Client runner file exists: {os.path.exists(runner_file)} ({runner_file})")
        
        installer_file = os.path.join(project_root, 'client', 'client_installer.py')
        print(f"✓ Client installer file exists: {os.path.exists(installer_file)} ({installer_file})")
        
        print("\nTesting service class initialization...")
        service = TaskClientService()
        print("✓ Service class created successfully")
        
        print("\nTesting configuration loading...")
        config = service._load_config()
        if config:
            print(f"✓ Configuration loaded: {config}")
        else:
            print("❌ Configuration loading failed")
        
        print("\nTesting TaskClientRunner import and creation...")
        try:
            from client.client_runner import TaskClientRunner
            print("✓ TaskClientRunner imported successfully")
        except ImportError as e:
            print(f"❌ Direct import failed: {e}")
            print("Trying alternative import method...")
            import importlib.util
            runner_path = os.path.join(project_root, 'client', 'client_runner.py')
            if os.path.exists(runner_path):
                spec = importlib.util.spec_from_file_location("client.client_runner", runner_path)
                runner_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(runner_module)
                TaskClientRunner = runner_module.TaskClientRunner
                print("✓ TaskClientRunner imported via alternative method")
            else:
                print(f"❌ Runner file not found: {runner_path}")
                return
        
        # Test creating runner instance
        if config:
            runner_config = {
                'server_url': config.get('server_url', 'http://localhost:5000'),
                'client_name': config.get('client_name', 'debug-client'),
                'heartbeat_interval': config.get('heartbeat_interval', 30),
                'config_update_interval': config.get('config_update_interval', 600),
                'log_level': config.get('log_level', 'INFO'),
                'log_dir': os.path.join(os.path.dirname(__file__), 'logs'),
                'work_dir': os.path.join(os.path.dirname(__file__), 'work')
            }
        else:
            runner_config = {
                'server_url': 'http://localhost:5000',
                'client_name': 'debug-client',
                'heartbeat_interval': 30,
                'config_update_interval': 600,
                'log_level': 'INFO',
                'log_dir': os.path.join(os.path.dirname(__file__), 'logs'),
                'work_dir': os.path.join(os.path.dirname(__file__), 'work')
            }
        
        try:
            client_runner = TaskClientRunner(runner_config)
            print("✓ TaskClientRunner instance created successfully")
        except Exception as e:
            print(f"❌ TaskClientRunner creation failed: {e}")
            return
        
        print("\n✅ All tests passed! Service should work correctly.")
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()


def check_config():
    """Check configuration"""
    try:
        service = TaskClientService()
        config = service._load_config()
        if config:
            print("Configuration loaded successfully:")
            print(json.dumps(config, indent=2))
        else:
            print("Configuration not found, will use defaults")
    except Exception as e:
        print(f"Configuration check failed: {e}")

if __name__ == '__main__':
    # Always fix the Python path first, regardless of how the script is called
    project_root = fix_service_path()
    
    if len(sys.argv) == 1:
        # Run as service - ensure we're in the right directory
        try:
            os.chdir(project_root)
        except Exception:
            pass
            
        # Initialize and start the service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(TaskClientService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Handle command line arguments
        if 'install' in sys.argv:
            server_url = None
            client_name = None
            
            # Parse additional arguments
            for i, arg in enumerate(sys.argv):
                if arg == '--server-url' and i + 1 < len(sys.argv):
                    server_url = sys.argv[i + 1]
                elif arg == '--client-name' and i + 1 < len(sys.argv):
                    client_name = sys.argv[i + 1]
            
            install_service(server_url, client_name)
            
        elif 'debug' in sys.argv:
            debug_service()
            
        elif 'check-config' in sys.argv:
            check_config()
            
        elif 'uninstall' in sys.argv:
            uninstall_service()
            
        elif 'start' in sys.argv:
            start_service()
            
        elif 'stop' in sys.argv:
            stop_service()
            
        elif 'restart' in sys.argv:
            restart_service()
            
        elif 'status' in sys.argv:
            status_service()
            
        else:
            win32serviceutil.HandleCommandLine(TaskClientService)

