"""
System information collection utilities
"""
import platform
import psutil
import socket
import subprocess
import json
from typing import Dict, Any, Optional, List


def get_cpu_info() -> Dict[str, Any]:
    """Get CPU information"""
    try:
        cpu_info = {
            'processor': platform.processor(),
            'architecture': platform.architecture()[0],
            'cpu_count_logical': psutil.cpu_count(logical=True),
            'cpu_count_physical': psutil.cpu_count(logical=False),
            'cpu_freq_max': None,
            'cpu_freq_current': None
        }
        
        # Get CPU frequency if available
        try:
            freq = psutil.cpu_freq()
            if freq:
                cpu_info['cpu_freq_max'] = freq.max
                cpu_info['cpu_freq_current'] = freq.current
        except:
            pass
            
        return cpu_info
    except Exception as e:
        return {
            'processor': 'Unknown',
            'architecture': platform.architecture()[0] if platform.architecture() else 'Unknown',
            'cpu_count_logical': 1,
            'cpu_count_physical': 1,
            'error': str(e)
        }


def get_memory_info() -> Dict[str, Any]:
    """Get memory information"""
    try:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            'total': memory.total,
            'available': memory.available,
            'used': memory.used,
            'free': memory.free,
            'percentage': memory.percent,
            'swap_total': swap.total,
            'swap_used': swap.used,
            'swap_free': swap.free,
            'swap_percentage': swap.percent
        }
    except Exception as e:
        return {
            'total': 0,
            'available': 0,
            'used': 0,
            'free': 0,
            'percentage': 0,
            'error': str(e)
        }


def get_gpu_info() -> List[Dict[str, Any]]:
    """Get GPU information"""
    gpus = []
    
    # Try to get NVIDIA GPU info using nvidia-smi
    try:
        result = subprocess.run([
            'nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free,driver_version',
            '--format=csv,noheader,nounits'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for i, line in enumerate(lines):
                if line.strip():
                    parts = [part.strip() for part in line.split(',')]
                    if len(parts) >= 5:
                        gpus.append({
                            'index': i,
                            'name': parts[0],
                            'memory_total': int(parts[1]) * 1024 * 1024,  # Convert MB to bytes
                            'memory_used': int(parts[2]) * 1024 * 1024,
                            'memory_free': int(parts[3]) * 1024 * 1024,
                            'driver_version': parts[4],
                            'vendor': 'NVIDIA'
                        })
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, ValueError):
        pass
    
    # Try to get AMD GPU info (basic detection)
    try:
        if platform.system() == 'Windows':
            result = subprocess.run([
                'wmic', 'path', 'win32_VideoController', 'get', 'name,AdapterRAM'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    if line.strip() and 'AMD' in line.upper():
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            name = ' '.join(parts[1:])
                            memory = int(parts[0]) if parts[0].isdigit() else 0
                            gpus.append({
                                'name': name,
                                'memory_total': memory,
                                'vendor': 'AMD'
                            })
    except:
        pass
    
    # If no dedicated GPUs found, check for integrated graphics
    if not gpus:
        try:
            if platform.system() == 'Windows':
                result = subprocess.run([
                    'wmic', 'path', 'win32_VideoController', 'get', 'name'
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    for i, line in enumerate(lines):
                        if line.strip():
                            gpus.append({
                                'index': i,
                                'name': line.strip(),
                                'vendor': 'Integrated',
                                'memory_total': 0
                            })
        except:
            pass
    
    return gpus


def get_os_info() -> Dict[str, Any]:
    """Get operating system information"""
    try:
        os_info = {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'node': platform.node(),
            'platform': platform.platform(),
            'processor': platform.processor()
        }
        
        # Get additional Windows info
        if platform.system() == 'Windows':
            try:
                import winreg
                reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                key = winreg.OpenKey(reg, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
                
                try:
                    os_info['windows_edition'] = winreg.QueryValueEx(key, "EditionID")[0]
                except:
                    pass
                    
                try:
                    os_info['windows_build'] = winreg.QueryValueEx(key, "CurrentBuild")[0]
                except:
                    pass
                    
                winreg.CloseKey(key)
                winreg.CloseKey(reg)
            except:
                pass
        
        return os_info
    except Exception as e:
        return {
            'system': platform.system() if platform.system() else 'Unknown',
            'release': 'Unknown',
            'version': 'Unknown',
            'error': str(e)
        }


def get_network_info() -> Dict[str, Any]:
    """Get network information"""
    try:
        hostname = socket.gethostname()
        
        # Get local IP
        local_ip = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = '127.0.0.1'
        
        # Get network interfaces
        interfaces = []
        try:
            for interface, addrs in psutil.net_if_addrs().items():
                interface_info = {'name': interface, 'addresses': []}
                for addr in addrs:
                    if addr.family == socket.AF_INET:  # IPv4
                        interface_info['addresses'].append({
                            'type': 'IPv4',
                            'address': addr.address,
                            'netmask': addr.netmask
                        })
                    elif addr.family == socket.AF_INET6:  # IPv6
                        interface_info['addresses'].append({
                            'type': 'IPv6',
                            'address': addr.address,
                            'netmask': addr.netmask
                        })
                interfaces.append(interface_info)
        except:
            pass
        
        return {
            'hostname': hostname,
            'local_ip': local_ip,
            'interfaces': interfaces[:5]  # Limit to first 5 interfaces
        }
    except Exception as e:
        return {
            'hostname': 'unknown',
            'local_ip': '127.0.0.1',
            'error': str(e)
        }


def get_disk_info() -> List[Dict[str, Any]]:
    """Get disk information"""
    disks = []
    try:
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percentage': (usage.used / usage.total * 100) if usage.total > 0 else 0
                })
            except (PermissionError, OSError):
                # Skip partitions we can't access
                continue
    except Exception as e:
        return [{'error': str(e)}]
    
    return disks


def get_system_info() -> Dict[str, Any]:
    """Get comprehensive system information"""
    return {
        'cpu': get_cpu_info(),
        'memory': get_memory_info(),
        'gpu': get_gpu_info(),
        'os': get_os_info(),
        'network': get_network_info(),
        'disk': get_disk_info(),
        'timestamp': platform.time.time() if hasattr(platform, 'time') else None
    }


def format_bytes(bytes_value: int) -> str:
    """Format bytes to human readable string"""
    if bytes_value == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while bytes_value >= 1024 and i < len(units) - 1:
        bytes_value /= 1024
        i += 1
    
    return f"{bytes_value:.1f} {units[i]}"


def get_system_summary() -> Dict[str, str]:
    """Get a summary of system information for display"""
    try:
        system_info = get_system_info()
        
        # CPU summary
        cpu = system_info['cpu']
        cpu_summary = f"{cpu.get('processor', 'Unknown')} ({cpu.get('cpu_count_logical', 1)} cores)"
        
        # Memory summary
        memory = system_info['memory']
        memory_total = format_bytes(memory.get('total', 0))
        memory_summary = f"{memory_total} ({memory.get('percentage', 0):.1f}% used)"
        
        # GPU summary
        gpus = system_info['gpu']
        if gpus:
            gpu_summary = ', '.join([gpu.get('name', 'Unknown GPU') for gpu in gpus[:2]])  # First 2 GPUs
        else:
            gpu_summary = 'No dedicated GPU detected'
        
        # OS summary
        os_info = system_info['os']
        os_summary = f"{os_info.get('system', 'Unknown')} {os_info.get('release', '')}"
        
        return {
            'cpu': cpu_summary,
            'memory': memory_summary,
            'gpu': gpu_summary,
            'os': os_summary,
            'hostname': system_info['network'].get('hostname', 'unknown'),
            'ip': system_info['network'].get('local_ip', '127.0.0.1')
        }
    except Exception as e:
        return {
            'cpu': 'Unknown',
            'memory': 'Unknown', 
            'gpu': 'Unknown',
            'os': 'Unknown',
            'hostname': 'unknown',
            'ip': '127.0.0.1',
            'error': str(e)
        }
