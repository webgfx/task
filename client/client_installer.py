"""
Client Installation and Uninstallation Manager
Handles client installation, service registration, and cleanup
"""
import os
import sys
import json
import argparse
import logging
import subprocess
import shutil
from pathlib import Path

# Add project root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import ClientConfig
from common.utils import setup_logging

logger = logging.getLogger(__name__)

class ClientInstaller:
    def __init__(self, install_dir=None, service_name=None):
        """
        Initialize client installer
        
        Args:
            install_dir: Installation directory (default: ~/.task_client)
            service_name: Service name for registration (default: task-client)
        """
        self.install_dir = install_dir or os.path.join(os.path.expanduser('~'), '.task_client')
        self.service_name = service_name or 'task-client'
        self.config_file = os.path.join(self.install_dir, 'config.json')
        self.log_dir = os.path.join(self.install_dir, 'logs')
        self.work_dir = os.path.join(self.install_dir, 'work')
        
        # Ensure install directory exists
        os.makedirs(self.install_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.work_dir, exist_ok=True)
    
    def install(self, server_url, machine_name, **kwargs):
        """Install client with configuration"""
        try:
            logger.info(f"Installing task client to: {self.install_dir}")
            
            # Create configuration
            config = {
                'server_url': server_url,
                'machine_name': machine_name,
                'heartbeat_interval': kwargs.get('heartbeat_interval', 30),
                'config_update_interval': kwargs.get('config_update_interval', 600),
                'log_level': kwargs.get('log_level', 'INFO'),
                'install_dir': self.install_dir,
                'log_dir': self.log_dir,
                'work_dir': self.work_dir,
                'service_name': self.service_name,
                'installed_at': kwargs.get('installed_at'),
                'version': kwargs.get('version', '1.0.0')
            }
            
            # Save configuration
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration saved to: {self.config_file}")
            
            # Copy core files to installation directory
            self._copy_core_files()
            
            # Create startup scripts
            self._create_startup_scripts(config)
            
            # Register as service (optional)
            if kwargs.get('register_service', False):
                self._register_service(config)
            
            logger.info("Client installation completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Installation failed: {e}")
            return False
    
    def uninstall(self, remove_data=False):
        """Uninstall client"""
        try:
            logger.info("Uninstalling task client...")
            
            # Stop service if running
            self._stop_service()
            
            # Unregister service
            self._unregister_service()
            
            # Remove startup scripts
            self._remove_startup_scripts()
            
            # Remove core files (keep config and logs unless specified)
            if remove_data:
                logger.info(f"Removing all data from: {self.install_dir}")
                if os.path.exists(self.install_dir):
                    shutil.rmtree(self.install_dir)
            else:
                # Only remove core executable files, keep config and data
                core_files = ['client_runner.py', 'start_client.bat', 'stop_client.bat', 'start_client.sh', 'stop_client.sh']
                for file in core_files:
                    file_path = os.path.join(self.install_dir, file)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Removed: {file_path}")
            
            logger.info("Client uninstallation completed")
            return True
            
        except Exception as e:
            logger.error(f"Uninstallation failed: {e}")
            return False
    
    def update_core_files(self):
        """Update only core execution files without changing configuration"""
        try:
            logger.info("Updating core client files...")
            
            # Copy updated core files
            self._copy_core_files()
            
            logger.info("Core files updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Core files update failed: {e}")
            return False
    
    def _copy_core_files(self):
        """Copy core files to installation directory"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        
        # Files to copy
        files_to_copy = [
            ('client/client_runner.py', 'client_runner.py'),
            ('client/executor.py', 'executor.py'),
            ('client/heartbeat.py', 'heartbeat.py'),
            ('common/__init__.py', 'common/__init__.py'),
            ('common/config.py', 'common/config.py'),
            ('common/models.py', 'common/models.py'),
            ('common/system_info.py', 'common/system_info.py'),
            ('common/utils.py', 'common/utils.py'),
        ]
        
        for src_path, dst_name in files_to_copy:
            src_file = os.path.join(project_root, src_path)
            dst_file = os.path.join(self.install_dir, dst_name)
            
            # Create directory if needed
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            
            if os.path.exists(src_file):
                shutil.copy2(src_file, dst_file)
                logger.debug(f"Copied: {src_path} -> {dst_name}")
            else:
                logger.warning(f"Source file not found: {src_file}")
    
    def _create_startup_scripts(self, config):
        """Create startup scripts for different platforms"""
        python_exe = sys.executable
        runner_script = os.path.join(self.install_dir, 'client_runner.py')
        
        # Windows batch script
        batch_content = f"""@echo off
cd /d "{self.install_dir}"
"{python_exe}" client_runner.py --config config.json
"""
        batch_file = os.path.join(self.install_dir, 'start_client.bat')
        with open(batch_file, 'w', encoding='utf-8') as f:
            f.write(batch_content)
        
        # Windows stop script
        stop_batch_content = """@echo off
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Task Client*" 2>nul
echo Task client stopped
"""
        stop_batch_file = os.path.join(self.install_dir, 'stop_client.bat')
        with open(stop_batch_file, 'w', encoding='utf-8') as f:
            f.write(stop_batch_content)
        
        # Unix shell script
        shell_content = f"""#!/bin/bash
cd "{self.install_dir}"
"{python_exe}" client_runner.py --config config.json
"""
        shell_file = os.path.join(self.install_dir, 'start_client.sh')
        with open(shell_file, 'w', encoding='utf-8') as f:
            f.write(shell_content)
        
        # Make shell script executable
        if os.name != 'nt':
            os.chmod(shell_file, 0o755)
        
        # Unix stop script
        stop_shell_content = f"""#!/bin/bash
pkill -f "client_runner.py"
echo "Task client stopped"
"""
        stop_shell_file = os.path.join(self.install_dir, 'stop_client.sh')
        with open(stop_shell_file, 'w', encoding='utf-8') as f:
            f.write(stop_shell_content)
        
        if os.name != 'nt':
            os.chmod(stop_shell_file, 0o755)
        
        logger.info("Startup scripts created")
    
    def _remove_startup_scripts(self):
        """Remove startup scripts"""
        scripts = ['start_client.bat', 'stop_client.bat', 'start_client.sh', 'stop_client.sh']
        for script in scripts:
            script_path = os.path.join(self.install_dir, script)
            if os.path.exists(script_path):
                os.remove(script_path)
                logger.debug(f"Removed script: {script_path}")
    
    def _register_service(self, config):
        """Register as system service (platform specific)"""
        if os.name == 'nt':
            self._register_windows_service(config)
        else:
            self._register_unix_service(config)
    
    def _register_windows_service(self, config):
        """Register Windows service"""
        try:
            # This would require additional service wrapper implementation
            logger.info("Windows service registration not implemented yet")
        except Exception as e:
            logger.error(f"Windows service registration failed: {e}")
    
    def _register_unix_service(self, config):
        """Register Unix/Linux systemd service"""
        try:
            # This would create systemd service file
            logger.info("Unix service registration not implemented yet")
        except Exception as e:
            logger.error(f"Unix service registration failed: {e}")
    
    def _unregister_service(self):
        """Unregister system service"""
        try:
            logger.info("Service unregistration not implemented yet")
        except Exception as e:
            logger.error(f"Service unregistration failed: {e}")
    
    def _stop_service(self):
        """Stop running service"""
        try:
            if os.name == 'nt':
                # Windows
                subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE eq Task Client*'], 
                             capture_output=True, check=False)
            else:
                # Unix/Linux
                subprocess.run(['pkill', '-f', 'client_runner.py'], 
                             capture_output=True, check=False)
            logger.info("Service stopped")
        except Exception as e:
            logger.error(f"Failed to stop service: {e}")
    
    def get_installation_info(self):
        """Get current installation information"""
        if not os.path.exists(self.config_file):
            return None
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"Failed to read installation info: {e}")
            return None
    
    def is_installed(self):
        """Check if client is installed"""
        return os.path.exists(self.config_file)


def main():
    """Main function for installer"""
    parser = argparse.ArgumentParser(description='Task Client Installer')
    parser.add_argument('action', choices=['install', 'uninstall', 'update', 'info', 'status'],
                       help='Action to perform')
    parser.add_argument('--server-url', default='http://localhost:5000',
                       help='Server URL (required for install)')
    parser.add_argument('--machine-name', 
                       help='Machine name (required for install)')
    parser.add_argument('--install-dir',
                       help='Installation directory (default: ~/.task_client)')
    parser.add_argument('--service-name', default='task-client',
                       help='Service name (default: task-client)')
    parser.add_argument('--heartbeat-interval', type=int, default=30,
                       help='Heartbeat interval in seconds (default: 30)')
    parser.add_argument('--config-update-interval', type=int, default=600,
                       help='Configuration update interval in seconds (default: 600)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Log level (default: INFO)')
    parser.add_argument('--register-service', action='store_true',
                       help='Register as system service')
    parser.add_argument('--remove-data', action='store_true',
                       help='Remove all data during uninstall')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Create installer
    installer = ClientInstaller(args.install_dir, args.service_name)
    
    try:
        if args.action == 'install':
            if not args.machine_name:
                print("Error: --machine-name is required for installation")
                sys.exit(1)
            
            success = installer.install(
                server_url=args.server_url,
                machine_name=args.machine_name,
                heartbeat_interval=args.heartbeat_interval,
                config_update_interval=args.config_update_interval,
                log_level=args.log_level,
                register_service=args.register_service,
                installed_at=datetime.now().isoformat()
            )
            
            if success:
                print(f"✅ Client installed successfully to: {installer.install_dir}")
                print(f"To start the client, run: {os.path.join(installer.install_dir, 'start_client.bat' if os.name == 'nt' else 'start_client.sh')}")
            else:
                print("❌ Installation failed")
                sys.exit(1)
        
        elif args.action == 'uninstall':
            if not installer.is_installed():
                print("Client is not installed")
                sys.exit(1)
            
            success = installer.uninstall(remove_data=args.remove_data)
            
            if success:
                print("✅ Client uninstalled successfully")
            else:
                print("❌ Uninstallation failed")
                sys.exit(1)
        
        elif args.action == 'update':
            if not installer.is_installed():
                print("Client is not installed. Please install first.")
                sys.exit(1)
            
            success = installer.update_core_files()
            
            if success:
                print("✅ Core files updated successfully")
                print("Restart the client to apply changes")
            else:
                print("❌ Update failed")
                sys.exit(1)
        
        elif args.action == 'info':
            info = installer.get_installation_info()
            if info:
                print("📋 Installation Information:")
                for key, value in info.items():
                    print(f"  {key}: {value}")
            else:
                print("Client is not installed")
        
        elif args.action == 'status':
            if installer.is_installed():
                print("✅ Client is installed")
                info = installer.get_installation_info()
                if info:
                    print(f"  Location: {info.get('install_dir', 'Unknown')}")
                    print(f"  Machine Name: {info.get('machine_name', 'Unknown')}")
                    print(f"  Server URL: {info.get('server_url', 'Unknown')}")
            else:
                print("❌ Client is not installed")
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Installer error: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    from datetime import datetime
    main()
