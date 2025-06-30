"""
Utility functions
"""
import logging
import json
import socket
from datetime import datetime
from typing import Optional, Dict, Any

def setup_logging(log_level: str = 'INFO', log_file: Optional[str] = None):
    """Setup logging configuration"""
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Set log format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    handlers = [console_handler]
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True
    )

def get_local_ip() -> str:
    """Get local IP address"""
    try:
        # Connect to a non-existent address to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime"""
    if dt is None:
        return None
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse datetime string"""
    if not dt_str:
        return None
    try:
        # Try to parse ISO format
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except ValueError:
        try:
            # Try to parse standard format
            return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None

def safe_json_loads(json_str: str, default=None) -> Any:
    """Safely parse JSON string"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default

def safe_json_dumps(obj: Any, default=None) -> str:
    """Safely serialize to JSON string"""
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps(default) if default is not None else "{}"

def validate_cron_expression(cron_expr: str) -> bool:
    """Validate cron expression format"""
    if not cron_expr:
        return False
    
    parts = cron_expr.split()
    if len(parts) != 5:
        return False
    
    # Simple validation for each part
    for i, part in enumerate(parts):
        if part == '*':
            continue
        
        # Validate numeric ranges
        try:
            if '/' in part:
                # Handle step expressions, like */5
                base, step = part.split('/')
                if base != '*':
                    int(base)
                int(step)
            elif '-' in part:
                # Handle range expressions, like 1-5
                start, end = part.split('-')
                int(start)
                int(end)
            elif ',' in part:
                # Handle list expressions, like 1,3,5
                for num in part.split(','):
                    int(num)
            else:
                # Plain number
                int(part)
        except ValueError:
            return False
    
    return True

def check_port_available(host: str, port: int) -> bool:
    """Check if port is available"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result != 0  # 0 indicates successful connection, port is in use
    except Exception:
        return False
