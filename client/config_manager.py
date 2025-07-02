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
    管理客户端配置文件的读取和验证
    """
    
    def __init__(self, config_file_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_file_path: 配置文件路径，如果为None则使用默认路径
        """
        if config_file_path is None:
            # 默认配置文件路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_file_path = os.path.join(current_dir, 'client.cfg')
        
        self.config_file_path = config_file_path
        self.config = configparser.ConfigParser()
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
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
        """创建默认配置"""
        self.config['DEFAULT'] = {
            'server_url': 'http://localhost:5000',
            'machine_name': '',
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
        获取配置值
        
        Args:
            section: 配置段名
            key: 配置键名
            fallback: 默认值
            
        Returns:
            配置值
        """
        try:
            return self.config.get(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback
    
    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """
        获取整数配置值
        
        Args:
            section: 配置段名
            key: 配置键名
            fallback: 默认值
            
        Returns:
            整数配置值
        """
        try:
            return self.config.getint(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_float(self, section: str, key: str, fallback: float = 0.0) -> float:
        """
        获取浮点数配置值
        
        Args:
            section: 配置段名
            key: 配置键名
            fallback: 默认值
            
        Returns:
            浮点数配置值
        """
        try:
            return self.config.getfloat(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_boolean(self, section: str, key: str, fallback: bool = False) -> bool:
        """
        获取布尔配置值
        
        Args:
            section: 配置段名
            key: 配置键名
            fallback: 默认值
            
        Returns:
            布尔配置值
        """
        try:
            return self.config.getboolean(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_all_config(self) -> Dict[str, Dict[str, str]]:
        """
        获取所有配置
        
        Returns:
            包含所有配置的字典
        """
        result = {}
        for section_name in self.config.sections():
            result[section_name] = dict(self.config[section_name])
        
        # 包含DEFAULT段
        if 'DEFAULT' in self.config:
            result['DEFAULT'] = dict(self.config['DEFAULT'])
        
        return result
    
    def validate_config(self) -> bool:
        """
        验证配置的有效性
        
        Returns:
            True if config is valid, False otherwise
        """
        try:
            # 验证必需的配置项
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
            
            # 验证服务器URL
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
        设置配置值
        
        Args:
            section: 配置段名
            key: 配置键名
            value: 配置值
        """
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)
    
    def save_config(self, file_path: Optional[str] = None):
        """
        保存配置到文件
        
        Args:
            file_path: 保存路径，如果为None则使用原路径
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
        """重新加载配置文件"""
        self._load_config()
    
    def get_config_summary(self) -> str:
        """
        获取配置摘要信息
        
        Returns:
            配置摘要字符串
        """
        summary = []
        summary.append("=== Client Configuration Summary ===")
        
        # 基本配置
        summary.append(f"Server URL: {self.get('DEFAULT', 'server_url', 'N/A')}")
        summary.append(f"Machine Name: {self.get('DEFAULT', 'machine_name', 'N/A')}")
        summary.append(f"Heartbeat Interval: {get_heartbeat_interval()} seconds (from common.cfg)")
        summary.append(f"Config Update Interval: {self.get_int('DEFAULT', 'config_update_interval', 600)} seconds")
        summary.append(f"Log Level: {self.get('DEFAULT', 'log_level', 'INFO')}")
        
        # 高级配置
        summary.append(f"WebSocket Ping Interval: {self.get_int('ADVANCED', 'websocket_ping_interval', 25)} seconds")
        summary.append(f"System Info Update Interval: {self.get_int('ADVANCED', 'system_info_update_interval', 300)} seconds")
        summary.append(f"Debug Mode: {self.get_boolean('ADVANCED', 'debug_mode', False)}")
        
        # 性能配置
        summary.append(f"Max Concurrent Tasks: {self.get_int('DEFAULT', 'max_concurrent_tasks', 1)}")
        summary.append(f"Task Timeout: {self.get_int('DEFAULT', 'task_timeout', 3600)} seconds")
        
        return "\n".join(summary)


# 全局配置实例
_config_manager = None

def get_config_manager(config_file_path: Optional[str] = None) -> ClientConfigManager:
    """
    获取全局配置管理器实例
    
    Args:
        config_file_path: 配置文件路径
        
    Returns:
        配置管理器实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ClientConfigManager(config_file_path)
    return _config_manager

def reload_config():
    """重新加载配置"""
    global _config_manager
    if _config_manager is not None:
        _config_manager.reload()

# 便捷函数
def get_heartbeat_interval() -> int:
    """获取心跳间隔（秒）- 从 common.cfg 读取"""
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
    """获取服务器URL"""
    return get_config_manager().get('DEFAULT', 'server_url', 'http://localhost:5000')

def get_machine_name() -> str:
    """获取机器名"""
    return get_config_manager().get('DEFAULT', 'machine_name', '')

def get_config_update_interval() -> int:
    """获取配置更新间隔（秒）"""
    return get_config_manager().get_int('DEFAULT', 'config_update_interval', 600)

def get_log_level() -> str:
    """获取日志级别"""
    return get_config_manager().get('DEFAULT', 'log_level', 'INFO')

def get_connection_timeout() -> int:
    """获取连接超时时间（秒）"""
    return get_config_manager().get_int('DEFAULT', 'connection_timeout', 10)

def get_websocket_ping_interval() -> int:
    """获取WebSocket ping间隔（秒）"""
    return get_config_manager().get_int('ADVANCED', 'websocket_ping_interval', 25)

def get_system_info_update_interval() -> int:
    """获取系统信息更新间隔（秒）"""
    return get_config_manager().get_int('ADVANCED', 'system_info_update_interval', 300)

def is_debug_mode() -> bool:
    """是否开启调试模式"""
    return get_config_manager().get_boolean('ADVANCED', 'debug_mode', False)
