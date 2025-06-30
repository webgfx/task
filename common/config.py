"""
Configuration management
"""
import os
from typing import Dict, Any

class Config:
    # Database configuration
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'server/server.db')
    
    # Web server configuration
    SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
    SERVER_PORT = int(os.getenv('SERVER_PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Heartbeat configuration
    HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', 30))  # seconds
    MACHINE_TIMEOUT = int(os.getenv('MACHINE_TIMEOUT', 90))  # seconds
    
    # Task execution configuration
    TASK_TIMEOUT = int(os.getenv('TASK_TIMEOUT', 3600))  # seconds
    MAX_CONCURRENT_TASKS = int(os.getenv('MAX_CONCURRENT_TASKS', 5))
    
    # Log configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'server/logs/server.log')
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Return configuration dictionary"""
        config = {}
        for attr_name in dir(cls):
            if not attr_name.startswith('_') and not callable(getattr(cls, attr_name)):
                config[attr_name] = getattr(cls, attr_name)
        return config

class ClientConfig:
    # Server connection configuration
    SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')
    MACHINE_NAME = os.getenv('MACHINE_NAME', 'default-machine')
    
    # Client process configuration
    HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', 30))
    TASK_CHECK_INTERVAL = int(os.getenv('TASK_CHECK_INTERVAL', 10))
    
    # Task execution configuration
    WORK_DIR = os.getenv('WORK_DIR', './work')
    LOG_DIR = os.getenv('LOG_DIR', './logs')
    
    @classmethod
    def from_args(cls, args):
        """Update configuration from command line arguments"""
        if args.server_url:
            cls.SERVER_URL = args.server_url
        if args.machine_name:
            cls.MACHINE_NAME = args.machine_name
        if args.heartbeat_interval:
            cls.HEARTBEAT_INTERVAL = args.heartbeat_interval
