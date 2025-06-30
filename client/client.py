"""
Client process main program - DEPRECATED
This file is maintained for backward compatibility.
Please use client_installer.py for installation and client_runner.py for runtime.

Migration Guide:
1. Install: python client_installer.py install --server-url <url> --machine-name <name>
2. Run: Use the generated startup scripts or python client_runner.py --config config.json
3. Update: python client_installer.py update (updates core files without reinstalling)
"""
import os
import sys
import warnings
import argparse
import subprocess
from datetime import datetime

# Add project root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.utils import setup_logging

# Issue deprecation warning
warnings.warn(
    "client.py is deprecated. Please use client_installer.py for installation "
    "and client_runner.py for runtime. This provides better separation of "
    "installation and runtime logic.",
    DeprecationWarning,
    stacklevel=2
)

def show_migration_help():
    """Show migration help message"""
    print("=" * 60)
    print("DEPRECATION NOTICE: client.py is deprecated")
    print("=" * 60)
    print()
    print("The client has been restructured for better modularity:")
    print()
    print("🔧 INSTALLATION (one-time setup):")
    print("   python client_installer.py install \\")
    print("     --server-url http://your-server:5000 \\")
    print("     --machine-name your-machine-name")
    print()
    print("🚀 RUNNING:")
    print("   Option 1: Use generated scripts")
    print("     # Windows: ~/.task_client/start_client.bat")
    print("     # Linux/Mac: ~/.task_client/start_client.sh")
    print()
    print("   Option 2: Direct execution")
    print("     python client_runner.py --config ~/.task_client/config.json")
    print()
    print("🔄 UPDATING (without reinstalling):")
    print("   python client_installer.py update")
    print()
    print("ℹ️  MANAGEMENT:")
    print("   python client_installer.py status     # Check installation")
    print("   python client_installer.py info       # Show configuration")
    print("   python client_installer.py uninstall  # Remove client")
    print()
    print("=" * 60)

def main():
    """Main function - provides compatibility wrapper"""
    parser = argparse.ArgumentParser(
        description='Task execution client process (DEPRECATED - use client_installer.py)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
DEPRECATION NOTICE:
This script is deprecated. Please use the new modular approach:

1. Install once: python client_installer.py install --server-url URL --machine-name NAME
2. Run anytime: Use generated startup scripts or client_runner.py
3. Update easily: python client_installer.py update

This separation allows updating core functionality without reinstalling.
        """
    )
    
    parser.add_argument('--server-url', default='http://localhost:5000',
                       help='Server URL (default: http://localhost:5000)')
    parser.add_argument('--machine-name', required=True,
                       help='Machine name (required)')
    parser.add_argument('--heartbeat-interval', type=int, default=30,
                       help='Heartbeat interval seconds (default: 30)')
    parser.add_argument('--config-update-interval', type=int, default=600,
                       help='Configuration update interval in seconds (default: 600 = 10 minutes)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Log level (default: INFO)')
    parser.add_argument('--force-legacy', action='store_true',
                       help='Force use of legacy client (not recommended)')
    parser.add_argument('--migrate', action='store_true',
                       help='Show migration instructions and exit')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    if args.migrate:
        show_migration_help()
        return
    
    # Check if new installer/runner is available
    current_dir = os.path.dirname(os.path.abspath(__file__))
    installer_path = os.path.join(current_dir, 'client_installer.py')
    runner_path = os.path.join(current_dir, 'client_runner.py')
    
    if os.path.exists(installer_path) and os.path.exists(runner_path) and not args.force_legacy:
        print("🚨 DEPRECATION WARNING: You are using the deprecated client.py")
        print()
        print("The client has been restructured for better modularity.")
        print("Would you like to:")
        print()
        print("1. 🔧 Install the new modular client (recommended)")
        print("2. ℹ️  Show migration instructions")
        print("3. ⚠️  Continue with legacy client (not recommended)")
        print("4. ❌ Exit")
        print()
        
        try:
            choice = input("Please choose an option (1-4): ").strip()
            
            if choice == '1':
                # Auto-install using new installer
                print("\n🔧 Installing new modular client...")
                install_cmd = [
                    sys.executable, installer_path, 'install',
                    '--server-url', args.server_url,
                    '--machine-name', args.machine_name,
                    '--heartbeat-interval', str(args.heartbeat_interval),
                    '--config-update-interval', str(args.config_update_interval),
                    '--log-level', args.log_level
                ]
                
                result = subprocess.run(install_cmd)
                if result.returncode == 0:
                    print("\n✅ Installation successful!")
                    print("\nTo start the client, run one of:")
                    home_dir = os.path.expanduser('~')
                    if os.name == 'nt':
                        print(f"  {os.path.join(home_dir, '.task_client', 'start_client.bat')}")
                    else:
                        print(f"  {os.path.join(home_dir, '.task_client', 'start_client.sh')}")
                    print(f"  python {runner_path} --config {os.path.join(home_dir, '.task_client', 'config.json')}")
                else:
                    print("\n❌ Installation failed. Please check the error messages above.")
                return
                
            elif choice == '2':
                show_migration_help()
                return
                
            elif choice == '3':
                print("\n⚠️  Continuing with legacy client...")
                print("Note: Consider migrating to the new modular approach soon.")
                
            elif choice == '4':
                print("\nExiting...")
                return
                
            else:
                print("\nInvalid choice. Exiting...")
                return
                
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            return
        except EOFError:
            print("\n\nNo input provided. Exiting...")
            return
    
    # If forced legacy or new files don't exist, show error
    if args.force_legacy:
        print("⚠️  WARNING: Legacy client functionality has been removed.")
        print("The old monolithic client has been replaced with a modular architecture.")
        print()
        print("Please use the new approach:")
        show_migration_help()
        sys.exit(1)
    else:
        print("❌ ERROR: Legacy client functionality is no longer available.")
        print()
        print("Please install and use the new modular client:")
        show_migration_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
