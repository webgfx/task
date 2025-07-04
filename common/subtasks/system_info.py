"""
System information subtask for comprehensive system details.

This subtask provides detailed information about the system including
OS details, Python environment, hardware specs, and more.
"""

import platform
import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any

from .base import BaseSubtask
from . import register_subtask_class


class GetSystemInfoSubtask(BaseSubtask):
    """Subtask to get comprehensive system information"""
    
    def run(self) -> Dict[str, Any]:
        """
        Get comprehensive system information.
        
        This function collects detailed information about the current system
        including operating system details, Python environment, and hardware
        specifications (if psutil is available).
        
        Returns:
            Dict[str, Any]: Dictionary containing system information with the following structure:
                - hostname: Client hostname
                - os: Operating system details (system, release, version, etc.)
                - python: Python environment details (version, implementation, executable)
                - timestamp: When the information was collected
                - memory: Memory information (if psutil available)
                - cpu: CPU information (if psutil available)
                - disk: Disk usage information (if psutil available)
                - network: Network interface information (if psutil available)
        """
        try:
            # Import hostname function from the hostname module
            from .hostname import get_hostname
            
            # Basic system information (always available)
            info = {
                'hostname': get_hostname(),
                'os': {
                    'system': platform.system(),
                    'release': platform.release(),
                    'version': platform.version(),
                    'platform': platform.platform(),
                    'machine': platform.machine(),
                    'processor': platform.processor(),
                    'architecture': platform.architecture()
                },
                'python': {
                    'version': platform.python_version(),
                    'version_info': {
                        'major': sys.version_info.major,
                        'minor': sys.version_info.minor,
                        'micro': sys.version_info.micro
                    },
                    'implementation': platform.python_implementation(),
                    'executable': sys.executable,
                    'path': sys.path[:5],  # First 5 path entries to avoid too much data
                    'prefix': sys.prefix
                },
                'environment': {
                    'user': os.environ.get('USER', os.environ.get('USERNAME', 'unknown')),
                    'home': os.environ.get('HOME', os.environ.get('USERPROFILE', 'unknown')),
                    'shell': os.environ.get('SHELL', os.environ.get('COMSPEC', 'unknown')),
                    'path_entries': len(os.environ.get('PATH', '').split(os.pathsep))
                },
                'timestamp': datetime.now().isoformat(),
                'collection_method': 'basic'
            }
            
            # Try to get additional system info if psutil is available
            try:
                import psutil
                
                # Memory information
                virtual_memory = psutil.virtual_memory()
                info['memory'] = {
                    'total': virtual_memory.total,
                    'available': virtual_memory.available,
                    'used': virtual_memory.used,
                    'percent': virtual_memory.percent,
                    'total_gb': round(virtual_memory.total / (1024**3), 2),
                    'available_gb': round(virtual_memory.available / (1024**3), 2)
                }
                
                # CPU information
                info['cpu'] = {
                    'count_logical': psutil.cpu_count(logical=True),
                    'count_physical': psutil.cpu_count(logical=False),
                    'percent': psutil.cpu_percent(interval=1),
                    'per_cpu_percent': psutil.cpu_percent(interval=1, percpu=True)
                }
                
                # CPU frequency (may not be available on all systems)
                try:
                    cpu_freq = psutil.cpu_freq()
                    if cpu_freq:
                        info['cpu']['frequency'] = {
                            'current': cpu_freq.current,
                            'min': cpu_freq.min,
                            'max': cpu_freq.max
                        }
                except (AttributeError, OSError):
                    info['cpu']['frequency'] = 'unavailable'
                
                # Disk information
                info['disk'] = []
                for partition in psutil.disk_partitions():
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        disk_info = {
                            'device': partition.device,
                            'mountpoint': partition.mountpoint,
                            'fstype': partition.fstype,
                            'total': usage.total,
                            'used': usage.used,
                            'free': usage.free,
                            'percent': round((usage.used / usage.total) * 100, 2),
                            'total_gb': round(usage.total / (1024**3), 2),
                            'free_gb': round(usage.free / (1024**3), 2)
                        }
                        info['disk'].append(disk_info)
                    except (PermissionError, OSError):
                        # Skip partitions that can't be accessed
                        continue
                
                # Network interfaces
                info['network'] = {}
                try:
                    network_interfaces = psutil.net_if_addrs()
                    for interface_name, addresses in network_interfaces.items():
                        interface_info = []
                        for addr in addresses:
                            interface_info.append({
                                'family': str(addr.family),
                                'address': addr.address,
                                'netmask': addr.netmask,
                                'broadcast': addr.broadcast
                            })
                        info['network'][interface_name] = interface_info
                except (AttributeError, OSError):
                    info['network'] = 'unavailable'
                
                # Boot time
                try:
                    boot_time = psutil.boot_time()
                    info['boot_time'] = datetime.fromtimestamp(boot_time).isoformat()
                    info['uptime_seconds'] = datetime.now().timestamp() - boot_time
                except (AttributeError, OSError):
                    info['boot_time'] = 'unavailable'
                
                info['collection_method'] = 'enhanced_with_psutil'
                
            except ImportError:
                # psutil not available, add note
                info['note'] = 'Install psutil package for detailed hardware information'
                info['psutil_available'] = False
            except Exception as e:
                # psutil available but failed to get some info
                info['psutil_error'] = str(e)
                info['psutil_available'] = True
            
            return info
            
        except Exception as e:
            # If basic system info collection fails, return minimal info
            logging.error(f"Failed to get system info: {e}")
            
            fallback_info = {
                'error': str(e),
                'hostname': 'unknown',
                'os': {
                    'system': platform.system() if hasattr(platform, 'system') else 'unknown'
                },
                'python': {
                    'version': platform.python_version() if hasattr(platform, 'python_version') else 'unknown'
                },
                'timestamp': datetime.now().isoformat(),
                'collection_method': 'fallback_due_to_error'
            }
            
            # Try to get hostname even in error case
            try:
                from .hostname import get_hostname
                fallback_info['hostname'] = get_hostname()
            except:
                pass
            
            return fallback_info
    
    def get_result(self) -> Dict[str, Any]:
        """Get the last execution result"""
        return self._last_result
    
    def get_description(self) -> str:
        """Get a human-readable description of what this subtask does"""
        return "Get comprehensive system information including OS, Python environment, and hardware details"


# Register the subtask
register_subtask_class('get_system_info', GetSystemInfoSubtask())


def get_system_summary() -> Dict[str, Any]:
    """
    Get a condensed summary of system information.
    
    Returns:
        Dict[str, Any]: Condensed system information suitable for logging or quick display
    """
    try:
        subtask = GetSystemInfoSubtask()
        full_info = subtask.run()
        
        summary = {
            'hostname': full_info.get('hostname', 'unknown'),
            'os': f"{full_info.get('os', {}).get('system', 'unknown')} {full_info.get('os', {}).get('release', '')}".strip(),
            'python': full_info.get('python', {}).get('version', 'unknown'),
            'timestamp': full_info.get('timestamp')
        }
        
        # Add memory info if available
        if 'memory' in full_info:
            memory = full_info['memory']
            summary['memory_gb'] = f"{memory.get('available_gb', 0):.1f}/{memory.get('total_gb', 0):.1f}"
            summary['memory_percent'] = f"{memory.get('percent', 0):.1f}%"
        
        # Add CPU info if available
        if 'cpu' in full_info:
            cpu = full_info['cpu']
            summary['cpu_cores'] = cpu.get('count_logical', 'unknown')
            summary['cpu_percent'] = f"{cpu.get('percent', 0):.1f}%"
        
        return summary
        
    except Exception as e:
        return {
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


# Legacy function for backward compatibility
def get_system_info() -> Dict[str, Any]:
    """Legacy function - use GetSystemInfoSubtask class instead"""
    subtask = GetSystemInfoSubtask()
    return subtask.run()
