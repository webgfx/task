# Distributed Task Management System

A distributed task management and execution system based on Flask and SQLite, supporting web interface management, multi-machine distributed execution, and real-time monitoring.

## ✨ Features

- 🌐 **Web Interface Management** - Intuitive task and machine management interface
- 📋 **Task Scheduling** - Support for scheduled tasks, instant tasks, and recurring tasks
- 🖥️ **Distributed Execution** - Multi-machine parallel task execution
- 💾 **Data Persistence** - SQLite database storage, no additional configuration required
- 🔄 **Real-time Monitoring** - WebSocket real-time status updates and log viewing
- 📡 **API Interface** - Complete RESTful API support
- 🤖 **Client Process** - Automatic registration, heartbeat, and task execution
- 🏷️ **Tag Management** - Support for task and machine tag classification
- 📊 **Statistics Dashboard** - System runtime status and performance monitoring

## 🛠️ Technology Stack

- **Backend Framework**: Flask, Flask-SocketIO, SQLAlchemy
- **Task Scheduling**: APScheduler
- **Frontend Technology**: HTML5, Bootstrap 5, JavaScript ES6
- **Database**: SQLite 3
- **Communication Protocol**: HTTP/HTTPS, WebSocket
- **Runtime Environment**: Python 3.7+

## 📁 Project Structure

```
task/
├── common/                 # Common modules
│   ├── __init__.py
│   ├── models.py          # Data model definitions
│   ├── config.py          # Configuration management
│   ├── server.txt         # Server IP and port configuration (format: IP:PORT)
│   ├── predefined_commands.py # Built-in system commands
│   ├── system_info.py     # System information collection
│   └── utils.py           # Utility functions
├── server/                # Web server
│   ├── __init__.py
│   ├── app.py             # Flask main application
│   ├── api.py             # REST API interface
│   ├── scheduler.py       # Task scheduler
│   ├── database.py        # Database operations
│   ├── templates/         # HTML templates
│   │   ├── index.html     # Home page
│   │   ├── tasks.html     # Task management
│   │   ├── machines.html  # Machine management
│   │   └── monitor.html   # System monitoring
│   └── static/            # Static resources
│       ├── css/style.css  # Style files
│       └── js/            # JavaScript files
├── client/                # Client process
│   ├── __init__.py
│   ├── client.py          # Main client process
│   ├── service.py         # Windows service implementation
│   ├── executor.py        # Task executor
│   ├── heartbeat.py       # Heartbeat monitoring
│   └── requirements.txt   # Client dependencies
├── server/                # Server components
│   ├── task_server.py     # Main server
│   ├── api_routes.py      # REST API routes
│   ├── websocket_handler.py # WebSocket handling
│   └── requirements.txt   # Server dependencies
├── examples/              # Example code
├── demo.py                # Complete demo script
├── test_api.py            # API test script
├── test_client.py         # Client process test
├── .env.example           # Configuration template
├── start.sh              # Linux startup script
├── start.bat             # Windows startup script
├── service_manager.bat   # Windows service management
├── QUICKSTART.md         # Quick start guide
├── WINDOWS_SERVICE_GUIDE.md  # Windows service documentation
└── README.md             # Project documentation
```

## 🚀 Quick Start

### Method 1: One-click Demo (Recommended for beginners)
```bash
# Install server dependencies
pip install -r server/requirements.txt

# Run complete demo
python demo.py
```

### Method 2: Manual Component Startup

#### 1. Install Dependencies
```bash
# For server components
pip install -r server/requirements.txt

# For client components (if running client separately)
pip install -r client/requirements.txt
```

#### 2. Start Web Server
```bash
# Method 1: Direct run
python -m server.app

# Method 2: Using scripts
# Windows:
start.bat
# Linux/Mac:
./start.sh
```

#### 3. Start Client Process (on target execution machines)
```bash
python -m client.client
# or
python test_client.py
```

#### 4. Access Web Interface
Open browser and visit: http://localhost:5000

## 🌐 Web Interface Features

### Main Pages
- **Home** (`/`) - System overview and quick operations
- **Task Management** (`/tasks`) - Create, edit, and monitor tasks
- **Machine Management** (`/machines`) - View machine status and management
- **System Monitoring** (`/monitor`) - Real-time monitoring and performance metrics

### Core Functions
1. **Task Management**
   - 📝 Create scheduled and instant tasks
   - 🎯 Specify target execution machines
   - ⏰ Set execution time and retry strategies
   - 📊 Real-time view of execution status and logs

2. **Machine Management**
   - 🖥️ Automatic discovery and registration of machines
   - 💗 Real-time heartbeat monitoring
   - 📈 Machine performance and status display
   - 🏷️ Machine tag classification management

3. **Monitoring Dashboard**
   - 📊 System runtime statistics
   - 🔄 Real-time status updates
   - 📈 Performance metric charts
   - 📋 Operation log recording

## 📡 API Documentation

### Basic Interfaces
- `GET /api/health` - Health check
- `GET /api/dashboard` - System overview data

### Task Management
- `GET /api/tasks` - Get task list
- `POST /api/tasks` - Create new task
- `GET /api/tasks/{id}` - Get task details
- `PUT /api/tasks/{id}` - Update task information
- `DELETE /api/tasks/{id}` - Delete task

### Machine Management
- `GET /api/machines` - Get machine list
- `POST /api/machines/register` - Register new machine
- `PUT /api/machines/{id}/heartbeat` - Update machine heartbeat

### WebSocket Events
- `task_status_changed` - Task status change
- `machine_status_changed` - Machine status change
- `task_log` - Task execution log

## 🔧 Configuration

Copy `.env.example` to `.env` and modify configuration:

```env
# Server configuration
SERVER_HOST=0.0.0.0          # Server listening address
SERVER_PORT=5000             # Server port
DEBUG=True                   # Debug mode

# Database configuration
DATABASE_URL=sqlite:///tasks.db  # SQLite database file

# Time interval configuration (seconds)
HEARTBEAT_INTERVAL=30        # Heartbeat interval
TASK_POLL_INTERVAL=10        # Task polling interval
TASK_TIMEOUT=300             # Task execution timeout

# Log configuration
LOG_LEVEL=INFO               # Log level
```

## 🤖 Client Deployment

### **Windows Service Deployment (Recommended for Production)**

The client can be installed as a Windows service for automatic startup and management:

#### **Quick Service Installation**
```batch
# Install as Windows service with automatic server configuration
service_manager.bat install

# Start the service
service_manager.bat start

# Check service status
service_manager.bat status
```

#### **Automatic Server Configuration**
The service automatically reads server address from `common/server.txt` file:

1. **Create server configuration file**:
   ```batch
   # Using IP address with port
   echo 192.168.1.100:5000 > common\server.txt
   
   # Using IP address only (default port 5000)
   echo 192.168.1.100 > common\server.txt
   
   # Using full URL (if needed)
   echo http://192.168.1.100:8080 > common\server.txt
   ```

2. **Service reads configuration automatically**:
   - Primary: `common/server.txt` (supports IP:PORT, IP only, or full URLs)
   - Format: IP:PORT (e.g., 192.168.1.100:5000)
   - Fallback: Default localhost (127.0.0.1:5000)
   - Configuration updates every 10 minutes

3. **No manual server URL input required**

#### **Service Management Commands**
```batch
# Service control
service_manager.bat start    # Start service
service_manager.bat stop     # Stop service  
service_manager.bat restart  # Restart service
service_manager.bat status   # Show status
service_manager.bat uninstall # Remove service
```

#### **Service Features**
- ✅ **Automatic Registration**: Registers with server on service start
- ✅ **Automatic Unregistration**: Unregisters from server on service stop
- ✅ **Automatic Server Configuration**: Reads server address from `common/server.txt` file
- ✅ **Windows Integration**: Runs as native Windows service
- ✅ **System Information**: Automatically collects and reports CPU, Memory, GPU, OS details
- ✅ **Persistent Configuration**: Stored in `C:/WebGraphicsTasks/config.json`
- ✅ **Comprehensive Logging**: Service logs in `C:/WebGraphicsTasks/logs/`
- ✅ **Periodic Updates**: Configuration refreshed every 10 minutes
- ✅ **Administrator Tools**: Easy install/uninstall/management

### **Server Configuration Options**

The `common/server.txt` file supports multiple formats for IP and port configuration:

**📍 IP:PORT Format (Recommended):**
```
192.168.1.100:5000
```
*Used exactly as: `http://192.168.1.100:5000`*

**📍 IP Address Only:**
```
192.168.1.100
```
*Automatically becomes: `http://192.168.1.100:5000`*

**🔗 Full URL Format (Optional):**
```
http://192.168.1.100:8080
https://secure-server.com:443
```
*Used exactly as specified*

**🔄 Dynamic Updates:**
- Configuration is reloaded every 10 minutes automatically
- No service restart required when server address changes
- Supports seamless server migration

For detailed service documentation, see [WINDOWS_SERVICE_GUIDE.md](WINDOWS_SERVICE_GUIDE.md)

### **Manual Deployment (Development/Testing)**

Deployment steps on target machines:

1. **Copy project files**
```bash
scp -r task/ user@target-machine:/opt/task-client/
```

2. **Install dependencies**
```bash
pip install -r client/requirements.txt
```

3. **Configure server address**
Modify `SERVER_URL` in `.env` file

4. **Start client process**
```bash
python -m client.client --server-url http://server:5000 --machine-name client-machine
```

### Auto-start on boot

#### **Windows Service (Recommended)**
```batch
# Install as Windows service (runs automatically on startup)
service_manager.bat install --server-url http://your-server:5000
service_manager.bat start

# Service will automatically start on system boot
# No additional configuration needed
```

#### **Windows Task Scheduler (Alternative)**
```batch
# Using task scheduler for non-service deployment
schtasks /create /tn "TaskClient" /tr "python C:\path\to\client\client.py --server-url http://server:5000 --machine-name client" /sc onstart
```

#### **Linux System**
```bash
# Create systemd service
sudo tee /etc/systemd/system/task-client.service > /dev/null <<EOF
[Unit]
Description=Distributed Task Management Client
After=network.target

[Service]
Type=simple
User=taskuser
WorkingDirectory=/opt/task-client
ExecStart=/usr/bin/python3 -m client.client --server-url http://server:5000 --machine-name client
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable task-client
sudo systemctl start task-client
```

## 📋 Usage Examples

### Create Task via API
```python
import requests
from datetime import datetime, timedelta

# Create task data
task_data = {
    "name": "System Backup Task",
    "command": "tar -czf /backup/system-$(date +%Y%m%d).tar.gz /etc /home",
    "target_machines": ["server-001", "server-002"],
    "scheduled_time": (datetime.now() + timedelta(hours=1)).isoformat(),
    "timeout": 3600,
    "retry_count": 2,
    "tags": ["backup", "daily"]
}

# Submit task
response = requests.post("http://localhost:5000/api/tasks", json=task_data)
if response.status_code == 201:
    task = response.json()
    print(f"Task created successfully, ID: {task['id']}")
```

### Query Task Status
```python
import requests

# Get task list
response = requests.get("http://localhost:5000/api/tasks")
tasks = response.json()

for task in tasks:
    print(f"Task: {task['name']} - Status: {task['status']}")
```

## 🧪 Testing and Validation

### Run Test Scripts
```bash
# API functionality test
python test_api.py

# Client functionality test
python test_client.py

# Complete system demo
python demo.py
```

### Validate System Functions
1. ✅ Web interface access normal
2. ✅ Client process successfully registered
3. ✅ Tasks created and executed normally
4. ✅ Real-time status updates
5. ✅ Logs recorded correctly

## 🔍 Troubleshooting

### Common Issues and Solutions

**Q: SSL error - 'module ssl has no attribute wrap_socket'**
```bash
# This issue occurs with Python 3.13+ and older Flask-SocketIO versions
# Solution: Update to compatible versions (already fixed in this project)
pip install flask==3.0.3 flask-socketio==5.4.1
# Or reinstall all dependencies: pip install -r server/requirements.txt
```

**Q: Port 5000 is in use**
```bash
# Find occupying process
netstat -ano | findstr :5000
# Kill process or modify port in configuration file
```

**Q: Client process cannot connect to server**
- Check network connection and firewall settings
- Confirm server address and port configuration
- Check if server is running normally

**Q: Task execution failed**
- Check if command syntax is correct
- Confirm target machine is online
- View task execution logs for detailed errors

**Q: Database operation failed**
- Check database file permissions
- Ensure SQLite file directory is writable
- Reinitialize database

## 📈 Performance Optimization

### System Tuning Recommendations
1. **Database Optimization**
   - Regularly clean historical logs
   - Add indexes for common queries
   - Consider using PostgreSQL to replace SQLite

2. **Network Optimization**
   - Adjust heartbeat interval to balance real-time and performance
   - Use connection pools to reduce connection overhead
   - Enable compression to reduce data transmission

3. **Concurrent Processing**
   - Increase number of worker processes
   - Use asynchronous task queues
   - Implement load balancing

## 🛡️ Security Recommendations

1. **Authentication and Authorization**
   - Implement user login and access control
   - Use JWT or Session to manage user state
   - Limit API access permissions

2. **Network Security**
   - Use HTTPS for encrypted communication
   - Configure firewall to restrict access
   - Validate all user inputs

3. **Data Security**
   - Regularly backup database
   - Encrypt sensitive information storage
   - Record detailed operation audit logs

## 🎯 Extension Development

### Feature Extension Directions
1. **Task Type Extensions**
   - Support script file upload and execution
   - Integrate Docker container tasks
   - Add data synchronization tasks

2. **Monitoring Enhancements**
   - Integrate Prometheus metrics
   - Add email/SMS alerts
   - Implement performance analysis dashboard

3. **Cluster Deployment**
   - Support multi-server clusters
   - Implement load balancing
   - Add failover mechanisms

### Secondary Development Guide
For detailed development documentation and API reference, please see the `QUICKSTART.md` file.

## 📄 License

This project is licensed under the MIT License, see LICENSE file for details.

## 🤝 Contributing

Welcome to submit Issues and Pull Requests to improve the project!

1. Fork the project
2. Create feature branch
3. Submit changes
4. Create Pull Request

## 📞 Technical Support

If you encounter problems, please:
1. Check the quick start guide `QUICKSTART.md`
2. Run test scripts to verify functionality
3. Check console logs for error information
4. Submit Issue with detailed problem description
