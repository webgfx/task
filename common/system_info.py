"""
System information collection utilities
"""
import os
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
    """Get memory information (total only, without used info)"""
    try:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            'total': memory.total,
            'available': memory.available,
            'free': memory.free,
            'swap_total': swap.total,
            'swap_free': swap.free
        }
    except Exception as e:
        return {
            'total': 0,
            'available': 0,
            'free': 0,
            'error': str(e)
        }


def get_gpu_info() -> List[Dict[str, Any]]:
    """Get GPU information with model and driver version"""
    gpus = []
    
    # Try to get NVIDIA GPU info using nvidia-smi
    try:
        result = subprocess.run([
            'nvidia-smi', '--query-gpu=name,memory.total,driver_version,uuid',
            '--format=csv,noheader,nounits'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for i, line in enumerate(lines):
                if line.strip():
                    parts = [part.strip() for part in line.split(',')]
                    if len(parts) >= 3:
                        gpus.append({
                            'index': i,
                            'model': parts[0],  # GPU型号
                            'name': parts[0],   # 保持兼容性
                            'memory_total': int(parts[1]) * 1024 * 1024 if parts[1].isdigit() else 0,  # Convert MB to bytes
                            'driver_version': parts[2],  # Driver版本
                            'vendor': 'NVIDIA',
                            'uuid': parts[3] if len(parts) > 3 else None
                        })
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, ValueError):
        pass
    
    # Try to get AMD GPU info with driver version
    try:
        if platform.system() == 'Windows':
            # Get GPU name and memory
            result = subprocess.run([
                'wmic', 'path', 'win32_VideoController', 'get', 'name,AdapterRAM,DriverVersion'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for i, line in enumerate(lines):
                    if line.strip() and ('AMD' in line.upper() or 'ATI' in line.upper()):
                        # Parse the line more carefully
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            # Try to extract memory, driver version, and name
                            memory = 0
                            driver_version = 'Unknown'
                            name = 'Unknown AMD GPU'
                            
                            # Look for numeric memory value
                            for part in parts:
                                if part.isdigit() and int(part) > 1000000:  # Likely memory in bytes
                                    memory = int(part)
                                    break
                            
                            # Look for driver version pattern (usually contains dots)
                            for part in parts:
                                if '.' in part and any(c.isdigit() for c in part):
                                    driver_version = part
                                    break
                            
                            # The rest should be the name
                            name_parts = []
                            for part in parts:
                                if not part.isdigit() and part != driver_version:
                                    name_parts.append(part)
                            if name_parts:
                                name = ' '.join(name_parts)
                            
                            gpus.append({
                                'index': len(gpus),
                                'model': name,
                                'name': name,
                                'memory_total': memory,
                                'driver_version': driver_version,
                                'vendor': 'AMD'
                            })
    except:
        pass
    
    # If no dedicated GPUs found, check for integrated graphics
    if not gpus:
        try:
            if platform.system() == 'Windows':
                result = subprocess.run([
                    'wmic', 'path', 'win32_VideoController', 'get', 'name,DriverVersion'
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    for i, line in enumerate(lines):
                        if line.strip():
                            parts = line.strip().split()
                            if len(parts) >= 1:
                                # Extract name and driver version
                                driver_version = 'Unknown'
                                name_parts = []
                                
                                for part in parts:
                                    if '.' in part and any(c.isdigit() for c in part):
                                        driver_version = part
                                    else:
                                        name_parts.append(part)
                                
                                name = ' '.join(name_parts) if name_parts else 'Unknown GPU'
                                
                                gpus.append({
                                    'index': i,
                                    'model': name,
                                    'name': name,
                                    'driver_version': driver_version,
                                    'vendor': 'Integrated',
                                    'memory_total': 0
                                })
        except:
            pass
    
    return gpus


def get_os_info() -> Dict[str, Any]:
    """Get operating system information with detailed version"""
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
        
        # Get additional Windows info with detailed version
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
                
                try:
                    os_info['windows_display_version'] = winreg.QueryValueEx(key, "DisplayVersion")[0]
                except:
                    pass
                
                try:
                    os_info['windows_product_name'] = winreg.QueryValueEx(key, "ProductName")[0]
                except:
                    pass
                    
                winreg.CloseKey(key)
                winreg.CloseKey(reg)
                
                # Create a more detailed version string for Windows
                version_parts = []
                if 'windows_product_name' in os_info:
                    version_parts.append(os_info['windows_product_name'])
                if 'windows_display_version' in os_info:
                    version_parts.append(f"Version {os_info['windows_display_version']}")
                if 'windows_build' in os_info:
                    version_parts.append(f"Build {os_info['windows_build']}")
                
                if version_parts:
                    os_info['detailed_version'] = ' '.join(version_parts)
                else:
                    os_info['detailed_version'] = f"{os_info['system']} {os_info['release']}"
                    
            except:
                os_info['detailed_version'] = f"{os_info['system']} {os_info['release']}"
        
        # For Linux systems, try to get distribution info
        elif platform.system() == 'Linux':
            try:
                # Try to read /etc/os-release
                with open('/etc/os-release', 'r') as f:
                    lines = f.readlines()
                    
                distro_info = {}
                for line in lines:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        distro_info[key] = value.strip('"')
                
                if 'PRETTY_NAME' in distro_info:
                    os_info['detailed_version'] = distro_info['PRETTY_NAME']
                elif 'NAME' in distro_info and 'VERSION' in distro_info:
                    os_info['detailed_version'] = f"{distro_info['NAME']} {distro_info['VERSION']}"
                else:
                    os_info['detailed_version'] = f"{os_info['system']} {os_info['release']}"
                    
                os_info.update(distro_info)
                
            except:
                os_info['detailed_version'] = f"{os_info['system']} {os_info['release']}"
        
        # For macOS
        elif platform.system() == 'Darwin':
            try:
                import plistlib
                with open('/System/Library/CoreServices/SystemVersion.plist', 'rb') as f:
                    plist = plistlib.load(f)
                    
                product_name = plist.get('ProductName', 'macOS')
                product_version = plist.get('ProductVersion', os_info['release'])
                build_version = plist.get('ProductBuildVersion', '')
                
                if build_version:
                    os_info['detailed_version'] = f"{product_name} {product_version} (Build {build_version})"
                else:
                    os_info['detailed_version'] = f"{product_name} {product_version}"
                    
                os_info['macos_product_name'] = product_name
                os_info['macos_product_version'] = product_version
                os_info['macos_build_version'] = build_version
                
            except:
                os_info['detailed_version'] = f"{os_info['system']} {os_info['release']}"
        
        else:
            # For other systems, use basic info
            os_info['detailed_version'] = f"{os_info['system']} {os_info['release']}"
        
        return os_info
    except Exception as e:
        return {
            'system': platform.system() if platform.system() else 'Unknown',
            'release': 'Unknown',
            'version': 'Unknown',
            'detailed_version': 'Unknown',
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
        
        # Memory summary (total only, no used info)
        memory = system_info['memory']
        memory_total = format_bytes(memory.get('total', 0))
        memory_summary = f"{memory_total}"
        
        # GPU summary with model and driver version
        gpus = system_info['gpu']
        if gpus:
            gpu_summaries = []
            for gpu in gpus[:2]:  # First 2 GPUs
                model = gpu.get('model', gpu.get('name', 'Unknown GPU'))
                driver = gpu.get('driver_version', 'Unknown')
                if driver != 'Unknown':
                    gpu_summaries.append(f"{model} (Driver: {driver})")
                else:
                    gpu_summaries.append(model)
            gpu_summary = ', '.join(gpu_summaries)
        else:
            gpu_summary = 'No dedicated GPU detected'
        
        # OS summary with detailed version
        os_info = system_info['os']
        os_summary = os_info.get('detailed_version', f"{os_info.get('system', 'Unknown')} {os_info.get('release', '')}")
        
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


def get_machine_name() -> str:
    """Get machine/hostname for client identification"""
    try:
        return socket.gethostname()
    except Exception:
        try:
            return platform.node()
        except Exception:
            return 'unknown-machine'


def get_server_url(common_cfg_path: str = None) -> str:
    """Get server URL from common.cfg file"""
    try:
        import configparser
        
        if common_cfg_path is None:
            # Default path in common directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            common_cfg_path = os.path.join(current_dir, 'common.cfg')
        
        if os.path.exists(common_cfg_path):
            config = configparser.ConfigParser()
            config.read(common_cfg_path, encoding='utf-8')
            
            # Get host and port from common.cfg
            host = config.get('SERVER', 'host', fallback='127.0.0.1')
            port = config.get('SERVER', 'port', fallback='5000')
            
            # Construct URL
            url = f"http://{host}:{port}"
            return url
    except Exception as e:
        print(f"Warning: Failed to read server URL from {common_cfg_path}: {e}")
    
    # Default fallback
    return 'http://localhost:5000'
