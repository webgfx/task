#!/usr/bin/env python3
"""
Client Configuration Tool
Utility for managing client.cfg configuration file
"""
import os
import sys
import argparse
import logging

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config_manager import get_config_manager
    from common.utils import setup_logging
except ImportError:
    print("Error: Unable to import required modules")
    print("Make sure you're running this from the client directory")
    sys.exit(1)

def show_config(cfg_manager):
    """显示当前配置"""
    print("=" * 60)
    print("Current Client Configuration")
    print("=" * 60)
    print(cfg_manager.get_config_summary())
    print("=" * 60)

def edit_heartbeat(cfg_manager, interval):
    """编辑心跳间隔"""
    if interval <= 0:
        print("Error: Heartbeat interval must be greater than 0")
        return False
    
    cfg_manager.set('DEFAULT', 'heartbeat_interval', str(interval))
    print(f"Heartbeat interval set to {interval} seconds")
    return True

def edit_config_update_interval(cfg_manager, interval):
    """编辑配置更新间隔"""
    if interval <= 0:
        print("Error: Configuration update interval must be greater than 0")
        return False
    
    cfg_manager.set('DEFAULT', 'config_update_interval', str(interval))
    print(f"Configuration update interval set to {interval} seconds")
    return True

def edit_log_level(cfg_manager, level):
    """编辑日志级别"""
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
    if level.upper() not in valid_levels:
        print(f"Error: Log level must be one of {valid_levels}")
        return False
    
    cfg_manager.set('DEFAULT', 'log_level', level.upper())
    print(f"Log level set to {level.upper()}")
    return True

def edit_debug_mode(cfg_manager, enabled):
    """编辑调试模式"""
    cfg_manager.set('ADVANCED', 'debug_mode', 'true' if enabled else 'false')
    print(f"Debug mode {'enabled' if enabled else 'disabled'}")
    return True

def edit_websocket_ping(cfg_manager, interval):
    """编辑WebSocket ping间隔"""
    if interval <= 0:
        print("Error: WebSocket ping interval must be greater than 0")
        return False
    
    cfg_manager.set('ADVANCED', 'websocket_ping_interval', str(interval))
    print(f"WebSocket ping interval set to {interval} seconds")
    return True

def validate_and_save(cfg_manager, config_file):
    """验证并保存配置"""
    if not cfg_manager.validate_config():
        print("Error: Configuration validation failed")
        return False
    
    try:
        cfg_manager.save_config(config_file)
        print(f"Configuration saved to {config_file}")
        return True
    except Exception as e:
        print(f"Error: Failed to save configuration: {e}")
        return False

def interactive_mode(cfg_manager, config_file):
    """交互式配置模式"""
    print("=" * 60)
    print("Interactive Configuration Mode")
    print("=" * 60)
    print()
    
    while True:
        print("Current configuration:")
        print(f"1. Heartbeat interval: {cfg_manager.get_int('DEFAULT', 'heartbeat_interval', 30)} seconds")
        print(f"2. Config update interval: {cfg_manager.get_int('DEFAULT', 'config_update_interval', 600)} seconds")
        print(f"3. Log level: {cfg_manager.get('DEFAULT', 'log_level', 'INFO')}")
        print(f"4. Debug mode: {cfg_manager.get_boolean('ADVANCED', 'debug_mode', False)}")
        print(f"5. WebSocket ping interval: {cfg_manager.get_int('ADVANCED', 'websocket_ping_interval', 25)} seconds")
        print()
        print("Options:")
        print("1-5: Edit configuration item")
        print("s: Save configuration")
        print("r: Reset to defaults")
        print("q: Quit without saving")
        print("w: Save and quit")
        print()
        
        choice = input("Choose an option: ").strip().lower()
        
        if choice == '1':
            try:
                value = int(input("Enter heartbeat interval (seconds): "))
                edit_heartbeat(cfg_manager, value)
            except ValueError:
                print("Error: Please enter a valid number")
        
        elif choice == '2':
            try:
                value = int(input("Enter config update interval (seconds): "))
                edit_config_update_interval(cfg_manager, value)
            except ValueError:
                print("Error: Please enter a valid number")
        
        elif choice == '3':
            value = input("Enter log level (DEBUG/INFO/WARNING/ERROR): ")
            edit_log_level(cfg_manager, value)
        
        elif choice == '4':
            value = input("Enable debug mode? (y/n): ").strip().lower()
            edit_debug_mode(cfg_manager, value in ['y', 'yes', 'true', '1'])
        
        elif choice == '5':
            try:
                value = int(input("Enter WebSocket ping interval (seconds): "))
                edit_websocket_ping(cfg_manager, value)
            except ValueError:
                print("Error: Please enter a valid number")
        
        elif choice == 's':
            validate_and_save(cfg_manager, config_file)
        
        elif choice == 'r':
            confirm = input("Are you sure you want to reset to defaults? (y/n): ")
            if confirm.strip().lower() in ['y', 'yes']:
                cfg_manager._create_default_config()
                print("Configuration reset to defaults")
        
        elif choice == 'q':
            print("Exiting without saving")
            break
        
        elif choice == 'w':
            if validate_and_save(cfg_manager, config_file):
                print("Configuration saved. Exiting.")
                break
        
        else:
            print("Invalid option. Please try again.")
        
        print()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Task Client Configuration Tool')
    parser.add_argument('--config', default='client.cfg',
                       help='Configuration file path (default: client.cfg)')
    parser.add_argument('--show', action='store_true',
                       help='Show current configuration')
    parser.add_argument('--heartbeat-interval', type=int,
                       help='Set heartbeat interval (seconds)')
    parser.add_argument('--config-update-interval', type=int,
                       help='Set configuration update interval (seconds)')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Set log level')
    parser.add_argument('--debug-mode', action='store_true',
                       help='Enable debug mode')
    parser.add_argument('--no-debug-mode', action='store_true',
                       help='Disable debug mode')
    parser.add_argument('--websocket-ping-interval', type=int,
                       help='Set WebSocket ping interval (seconds)')
    parser.add_argument('--interactive', action='store_true',
                       help='Run in interactive mode')
    parser.add_argument('--validate', action='store_true',
                       help='Validate configuration')
    parser.add_argument('--save', action='store_true',
                       help='Save configuration after making changes')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging('INFO')
    
    # Check if config file exists
    if not os.path.exists(args.config):
        print(f"Configuration file not found: {args.config}")
        create = input("Would you like to create a new configuration file? (y/n): ")
        if create.strip().lower() not in ['y', 'yes']:
            print("Exiting")
            sys.exit(1)
    
    # Load configuration
    try:
        cfg_manager = get_config_manager(args.config)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)
    
    # Handle different modes
    if args.interactive:
        interactive_mode(cfg_manager, args.config)
        return
    
    if args.show:
        show_config(cfg_manager)
        return
    
    if args.validate:
        if cfg_manager.validate_config():
            print("✅ Configuration is valid")
        else:
            print("❌ Configuration validation failed")
            sys.exit(1)
        return
    
    # Handle individual configuration changes
    changes_made = False
    
    if args.heartbeat_interval is not None:
        if edit_heartbeat(cfg_manager, args.heartbeat_interval):
            changes_made = True
    
    if args.config_update_interval is not None:
        if edit_config_update_interval(cfg_manager, args.config_update_interval):
            changes_made = True
    
    if args.log_level:
        if edit_log_level(cfg_manager, args.log_level):
            changes_made = True
    
    if args.debug_mode:
        if edit_debug_mode(cfg_manager, True):
            changes_made = True
    
    if args.no_debug_mode:
        if edit_debug_mode(cfg_manager, False):
            changes_made = True
    
    if args.websocket_ping_interval is not None:
        if edit_websocket_ping(cfg_manager, args.websocket_ping_interval):
            changes_made = True
    
    # Save if requested or if changes were made
    if args.save or changes_made:
        validate_and_save(cfg_manager, args.config)
    
    # If no specific action was requested, show configuration
    if not any([args.show, args.validate, args.save, changes_made]):
        show_config(cfg_manager)
        print()
        print("Use --help to see available options")
        print("Use --interactive for interactive configuration mode")

if __name__ == '__main__':
    main()

