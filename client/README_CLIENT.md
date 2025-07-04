# Task Client - Modular Architecture

## Overview

The client has been refactored into a modular architecture, separating installation/uninstallation logic from startup/stop logic to provide better deployment and update experience.

## Architecture Description

### 🏗️ File Structure

```
client/
├── client_installer.py    # Installation/uninstallation/update manager
├── client_runner.py       # Runtime executor
├── client.cfg            # Client configuration file template
├── config_manager.py     # Configuration management module
├── config_tool.py        # Configuration management tool
├── quick_setup.sh        # Linux/Mac quick installation script
├── quick_setup.bat       # Windows quick installation script
├── executor.py           # Task executor
├── heartbeat.py          # Heartbeat manager
└── README_CLIENT.md      # This document
```

### 🔧 Component Description

1. **client_installer.py** - Installation manager
   - One-time installation and configuration
   - Update core files (no need to reinstall)
   - Uninstallation and cleanup
   - Generate startup scripts and configuration files

2. **client_runner.py** - Runtime executor
   - Handle server communication
   - Execute tasks
   - System information collection
   - Heartbeat management

3. **client.cfg** - Configuration file
   - Heartbeat frequency configuration
   - Log level settings
   - Network parameter tuning
   - Performance and security settings

4. **config_manager.py** - Configuration management module
   - Configuration file reading and validation
   - Default value management
   - Configuration item access interface

5. **config_tool.py** - Configuration management tool
   - Interactive configuration editing
   - Configuration validation and saving
   - Configuration reset functionality

## ⚙️ Configuration Management

### Configuration File Description

The client uses two configuration files:

1. **config.json** - Basic configuration generated during installation
2. **client.cfg** - Detailed runtime configuration (can be manually edited)

### Heartbeat Frequency Configuration

Heartbeat frequency determines the interval at which the client sends alive signals to the server, in seconds.

**Set during installation:**
```bash
python client_installer.py install \
    --server-url http://localhost:5000 \
    --client-name my-client \
    --heartbeat-interval 60  # 60 second interval
```

**Modify after installation:**
```bash
# Method 1: Use configuration tool
python config_tool.py --heartbeat-interval 60 --save

# Method 2: Interactive configuration
python config_tool.py --interactive

# Method 3: Directly edit client.cfg file
```

### Configuration Tool Usage

**View current configuration:**
```bash
python config_tool.py --show
```

**Set various parameters:**
```bash
# Set heartbeat interval to 60 seconds
python config_tool.py --heartbeat-interval 60 --save

# Set log level to DEBUG
python config_tool.py --log-level DEBUG --save

# Enable debug mode
python config_tool.py --debug-mode --save

# Set WebSocket ping interval
python config_tool.py --websocket-ping-interval 30 --save
```

**Interactive configuration mode:**
```bash
python config_tool.py --interactive
```

**Validate configuration:**
```bash
python config_tool.py --validate
```

### Configuration Items Description

| Configuration Item | Default Value | Description |
|-------|-------|------|
| `heartbeat_interval` | 30 | Heartbeat send interval (seconds) |
| `config_update_interval` | 600 | Configuration update interval (seconds) |
| `log_level` | INFO | Log level (DEBUG/INFO/WARNING/ERROR) |
| `connection_timeout` | 10 | Connection timeout (seconds) |
| `websocket_ping_interval` | 25 | WebSocket ping interval (seconds) |
| `debug_mode` | false | Whether to enable debug mode |
| `max_concurrent_tasks` | 1 | Maximum concurrent tasks |

### Configuration Takes Effect

Configuration changes require client restart to take effect:

```bash
# Stop client
~/.task_client/stop_client.sh

# Start client
~/.task_client/start_client.sh
```

## 🚀 Quick Start

### Method 1: Use Quick Installation Script (Recommended)

**Linux/Mac:**
```bash
./quick_setup.sh --server-url http://your-server:5000 --client-name your-client
```

**Windows:**
```cmd
quick_setup.bat --server-url http://your-server:5000 --client-name your-client
```

### Method 2: Manual Installation

#### 1. Install Client
```bash
python client_installer.py install \
    --server-url http://localhost:5000 \
    --client-name my-client
```

#### 2. Start Client
```bash
# Use generated startup script
~/.task_client/start_client.sh    # Linux/Mac
%USERPROFILE%\.task_client\start_client.bat    # Windows

# Or run directly
python client_runner.py --config ~/.task_client/config.json
```

#### 3. Stop Client
```bash
~/.task_client/stop_client.sh     # Linux/Mac
%USERPROFILE%\.task_client\stop_client.bat     # Windows
```

## 🔄 Advantages

### 🎯 Modular Design
- **Separation of Concerns**: Installation logic completely separated from runtime logic
- **Independent Updates**: Can update only runtime files without reinstallation
- **Clear Responsibilities**: Each component has clear responsibility boundaries

### 🚀 Simplified Deployment
- **One-time Installation**: Generates standard startup scripts after installation
- **Standardization**: Consistent installation and runtime experience across platforms
- **Automation**: Supports scripted deployment and management

### 🔧 Convenient Maintenance
- **Hot Updates**: Update core functionality without downtime reinstallation
- **Version Management**: Clear version and configuration management
- **Status Monitoring**: Built-in status checking and diagnostic tools

## 📋 Usage Instructions

### Installation Options

```bash
python client_installer.py install \
    --server-url http://localhost:5000 \
    --client-name my-client \
    --heartbeat-interval 30 \
    --config-update-interval 600 \
    --log-level INFO \
    --install-dir ~/.task_client
```

### Configuration Management

**View current configuration:**
```bash
python config_tool.py --show
```

**Set heartbeat frequency (seconds):**
```bash
python config_tool.py --heartbeat-interval 60 --save
```

**Interactive configuration:**
```bash
python config_tool.py --interactive
```

**Validate configuration:**
```bash
python config_tool.py --validate
```

### Management Subtasks

```bash
# Check installation status
python client_installer.py status

# View configuration information
python client_installer.py info

# Update core files (without reinstallation)
python client_installer.py update

# Uninstall (keep data)
python client_installer.py uninstall

# Complete uninstall (delete all data)
python client_installer.py uninstall --remove-data
```

### Runtime Options

```bash
# Run with configuration file
python client_runner.py --config ~/.task_client/config.json

# Override log level
python client_runner.py --config ~/.task_client/config.json --log-level DEBUG
```

## 🗂️ File Organization

### Installation Directory Structure (~/.task_client)

```
.task_client/
├── config.json           # Main configuration file
├── client.cfg            # Client detailed configuration
├── client_runner.py      # Runtime executor
├── executor.py           # Task executor
├── heartbeat.py          # Heartbeat manager
├── config_manager.py     # Configuration management module
├── common/               # Common modules
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── system_info.py
│   └── utils.py
├── logs/                 # Log directory
├── work/                 # Work directory
│   └── task_results/     # Task results
├── start_client.bat      # Windows startup script
├── stop_client.bat       # Windows stop script
├── start_client.sh       # Linux/Mac startup script
└── stop_client.sh        # Linux/Mac stop script
```

### Configuration File (client.cfg)

```ini
# Task Client Configuration File
[DEFAULT]
# Server connection settings
server_url = http://localhost:5000

# Client identifier
client_name = 

# Heartbeat settings (seconds)
heartbeat_interval = 30

# Configuration update settings (seconds)
config_update_interval = 600

# Log settings
log_level = INFO

# Network settings
connection_timeout = 10
reconnect_delay = 5

[ADVANCED]
# WebSocket settings
websocket_ping_interval = 25
websocket_ping_timeout = 20

# System information collection interval (seconds)
system_info_update_interval = 300

# Debug settings
debug_mode = false
verbose_logging = false

[PERFORMANCE]
# Performance tuning settings
max_concurrent_tasks = 1
max_worker_threads = 4
```

## 🔄 Update Process

### Update Core Functionality (Recommended)
```bash
# 1. Stop client
~/.task_client/stop_client.sh

# 2. Update core files
python client_installer.py update

# 3. Restart client
~/.task_client/start_client.sh
```

### Complete Reinstallation
```bash
# 1. Uninstall existing installation
python client_installer.py uninstall

# 2. Reinstall
python client_installer.py install \
    --server-url http://localhost:5000 \
    --client-name my-client
```

## 🐛 Troubleshooting

### Check Installation Status
```bash
python client_installer.py status
```

### View Logs
```bash
# Real-time logs
tail -f ~/.task_client/logs/client.log

# View configuration
python client_installer.py info
```

### Common Issues

1. **Module Import Error**
   - Ensure using `client_runner.py` for runtime execution
   - Check if files in installation directory are complete

2. **Permission Issues**
   - Ensure startup scripts have execute permissions
   - Linux/Mac: `chmod +x ~/.task_client/start_client.sh`

3. **Configuration Issues**
   - Use `python client_installer.py info` to check configuration
   - Manually edit `~/.task_client/config.json` to fix configuration

## 🔄 Migration from Old Version

If you are using the old single-file client (client.py):

1. **Stop old client**
2. **Install new modular client**:
   ```bash
   python client_installer.py install \
       --server-url YOUR_SERVER_URL \
       --client-name YOUR_CLIENT_NAME
   ```
3. **Use new startup method**

The old single-file client has been completely replaced with modular architecture.

## 🎯 Best Practices

1. **Use configuration files**: Avoid hardcoding parameters in command line
2. **Regular updates**: Use `python client_installer.py update` to get latest features
3. **Monitor logs**: Regularly check logs in `~/.task_client/logs/` directory
4. **Backup configuration**: Backup configuration files before important deployments
5. **Environment isolation**: Use different client names and configurations for different environments

## 📝 Notes

- New architecture is fully compatible with old version servers
- Configuration file format is backward compatible
- All existing functionality remains unchanged
- Supports all existing server APIs
