"""
Client Configuration Manager
Handles reading and managing client configuration from client.cfg file
"""
import os
import configparser
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ClientConfigManager:
    """
    Manages client configuration file reading and validation
    """
    
    def __init__(self, config_file_path: Optional[str] = None):
        """
        Initialize configuration manager
        
        Args:
            config_file_path: Configuration file path, if None, use default path
        """
        if config_file_path is None:
            # Default configuration file path
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_file_path = os.path.join(current_dir, 'client.cfg')
        
        self.config_file_path = config_file_path
        self.config = configparser.ConfigParser()
        self._load_config()
    
    def _load_config(self):
        """Load configuration file"""
        try:
            if os.path.exists(self.config_file_path):
                self.config.read(self.config_file_path, encoding='utf-8')
                logger.info(f"Loaded configuration from: {self.config_file_path}")
            else:
                logger.warning(f"Configuration file not found: {self.config_file_path}")
                logger.info("Using default configuration values")
                self._create_default_config()
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            logger.info("Using default configuration values")
            self._create_default_config()
    
    def _create_default_config(self):
        """Create default configuration"""
        self.config['DEFAULT'] = {
            'server_url': 'http://localhost:5000',
            'client_name': '',
            # Note: heartbeat_interval is now in common.cfg
            'config_update_interval': '600',
            'log_level': 'INFO',
            'install_dir': '~/.task_client',
            'connection_timeout': '10',
            'reconnect_delay': '5',
            'max_retry_attempts': '3',
            'task_timeout': '3600',
            'max_concurrent_tasks': '1',
            'log_dir': 'logs',
            'work_dir': 'work'
        }
        
        self.config['ADVANCED'] = {
            'websocket_ping_interval': '25',
            'websocket_ping_timeout': '20',
            'system_info_update_interval': '300',
            'task_result_retention_days': '30',
            'max_memory_usage_mb': '1024',
            'debug_mode': 'false',
            'verbose_logging': 'false'
        }
        
        self.config['SECURITY'] = {
            'verify_ssl': 'true',
            'ssl_cert_path': '',
            'ssl_key_path': '',
            'auth_token': '',
            'api_key': ''
        }
        
        self.config['PERFORMANCE'] = {
            'output_buffer_size': '8192',
            'error_buffer_size': '4096',
            'enable_compression': 'true',
            'max_worker_threads': '4',
            'thread_pool_size': '2'
        }

    def get(self, section: str, key: str, fallback: Any = None) -> str:
        """
        Get configuration value
        
        Args:
            section: Configuration section name
            key: Configuration key name
            fallback: Default value
            
        Returns:
            Configuration value
        """
        try:
            return self.config.get(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback
    
    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """
        Get integer configuration value
        
        Args:
            section: Configuration section name
            key: Configuration key name
            fallback: Default value
            
        Returns:
            Integer configuration value
        """
        try:
            return self.config.getint(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_float(self, section: str, key: str, fallback: float = 0.0) -> float:
        """
        Get float configuration value
        
        Args:
            section: Configuration section name
            key: Configuration key name
            fallback: Default value
            
        Returns:
            Float configuration value
        """
        try:
            return self.config.getfloat(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_boolean(self, section: str, key: str, fallback: bool = False) -> bool:
        """
        Get boolean configuration value
        
        Args:
            section: Configuration section name
            key: Configuration key name
            fallback: Default value
            
        Returns:
            Boolean configuration value
        """
        try:
            return self.config.getboolean(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_all_config(self) -> Dict[str, Dict[str, str]]:
        """
        Get all configuration
        
        Returns:
            Dictionary containing all configuration
        """
        result = {}
        for section_name in self.config.sections():
            result[section_name] = dict(self.config[section_name])
        
        # Include DEFAULT section
        if 'DEFAULT' in self.config:
            result['DEFAULT'] = dict(self.config['DEFAULT'])
        
        return result
    
    def validate_config(self) -> bool:
        """
        Validate configuration validity
        
        Returns:
            True if config is valid, False otherwise
        """
        try:
            # Validate required configuration items
            # Note: heartbeat_interval is now in common.cfg, validate it there
            heartbeat_interval = get_heartbeat_interval()
            if heartbeat_interval <= 0:
                logger.error("heartbeat_interval must be greater than 0")
                return False
            
            config_update_interval = self.get_int('DEFAULT', 'config_update_interval', 600)
            if config_update_interval <= 0:
                logger.error("config_update_interval must be greater than 0")
                return False
            
            connection_timeout = self.get_int('DEFAULT', 'connection_timeout', 10)
            if connection_timeout <= 0:
                logger.error("connection_timeout must be greater than 0")
                return False
            
            # Validate server URL
            server_url = self.get('DEFAULT', 'server_url', 'http://localhost:5000')
            if not server_url.startswith(('http://', 'https://')):
                logger.error("server_url must start with http:// or https://")
                return False
            
            logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def set(self, section: str, key: str, value: str):
        """
        Set configuration value
        
        Args:
            section: Configuration section name
            key: Configuration key name
            value: Configuration value
        """
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)
    
    def save_config(self, file_path: Optional[str] = None):
        """
        Save configuration to file
        
        Args:
            file_path: Save path, if None use original path
        """
        if file_path is None:
            file_path = self.config_file_path
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                self.config.write(f)
            logger.info(f"Configuration saved to: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
    
    def reload(self):
        """Reload configuration file"""
        self._load_config()
    
    def get_config_summary(self) -> str:
        """
        Get configuration summary information
        
        Returns:
            Configuration summary string
        """
        summary = []
        summary.append("=== Client Configuration Summary ===")
        
        # Basic configuration
        summary.append(f"Server URL: {self.get('DEFAULT', 'server_url', 'N/A')}")
        summary.append(f"client Name: {self.get('DEFAULT', 'client_name', 'N/A')}")
        summary.append(f"Heartbeat Interval: {get_heartbeat_interval()} seconds (from common.cfg)")
        summary.append(f"Config Update Interval: {self.get_int('DEFAULT', 'config_update_interval', 600)} seconds")
        summary.append(f"Log Level: {self.get('DEFAULT', 'log_level', 'INFO')}")
        
        # Advanced configuration
        summary.append(f"WebSocket Ping Interval: {self.get_int('ADVANCED', 'websocket_ping_interval', 25)} seconds")
        summary.append(f"System Info Update Interval: {self.get_int('ADVANCED', 'system_info_update_interval', 300)} seconds")
        summary.append(f"Debug Mode: {self.get_boolean('ADVANCED', 'debug_mode', False)}")
        
        # Performance configuration
        summary.append(f"Max Concurrent Tasks: {self.get_int('DEFAULT', 'max_concurrent_tasks', 1)}")
        summary.append(f"Task Timeout: {self.get_int('DEFAULT', 'task_timeout', 3600)} seconds")
        
        return "\n".join(summary)


# Global configuration instance
_config_manager = None

def get_config_manager(config_file_path: Optional[str] = None) -> ClientConfigManager:
    """
    Get global configuration manager instance
    
    Args:
        config_file_path: Configuration file path
        
    Returns:
        Configuration manager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ClientConfigManager(config_file_path)
    return _config_manager

def reload_config():
    """Reload configuration"""
    global _config_manager
    if _config_manager is not None:
        _config_manager.reload()

# Convenience functions
def get_heartbeat_interval() -> int:
    """Get heartbeat interval (seconds) - read from common.cfg"""
    try:
        import configparser
        import os
        
        # Get path to common.cfg
        current_dir = os.path.dirname(os.path.abspath(__file__))
        common_cfg_path = os.path.join(current_dir, '..', 'common', 'common.cfg')
        
        if os.path.exists(common_cfg_path):
            config = configparser.ConfigParser()
            config.read(common_cfg_path, encoding='utf-8')
            return int(config.get('CLIENT', 'heartbeat_interval', fallback='60'))
        else:
            logger.warning(f"common.cfg not found at {common_cfg_path}, using default heartbeat interval")
            return 60
    except Exception as e:
        logger.error(f"Failed to read heartbeat_interval from common.cfg: {e}")
        return 60

def get_server_url() -> str:
    """Get server URL"""
    return get_config_manager().get('DEFAULT', 'server_url', 'http://localhost:5000')

def get_client_name() -> str:
    """Get client name"""
    return get_config_manager().get('DEFAULT', 'client_name', '')

def get_config_update_interval() -> int:
    """Get configuration update interval (seconds)"""
    return get_config_manager().get_int('DEFAULT', 'config_update_interval', 600)

def get_log_level() -> str:
    """Get log level"""
    return get_config_manager().get('DEFAULT', 'log_level', 'INFO')

def get_connection_timeout() -> int:
    """Get connection timeout (seconds)"""
    return get_config_manager().get_int('DEFAULT', 'connection_timeout', 10)

def get_websocket_ping_interval() -> int:
    """Get WebSocket ping interval (seconds)"""
    return get_config_manager().get_int('ADVANCED', 'websocket_ping_interval', 25)

def get_system_info_update_interval() -> int:
    """Get system information update interval (seconds)"""
    return get_config_manager().get_int('ADVANCED', 'system_info_update_interval', 300)

def is_debug_mode() -> bool:
    """Whether debug mode is enabled"""
    return get_config_manager().get_boolean('ADVANCED', 'debug_mode', False)

