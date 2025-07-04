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
    """Get GPU information with model and driver version using PowerShell, marking active GPU"""
    gpus = []
    active_gpu_pnp_id = None
        
    # Try to get active GPU information first
    try:
        if platform.system() == 'Windows':
            # Method 1: Get the primary display adapter using Win32_VideoController Primary property
            result = subprocess.run([
                'powershell', '-Command', 
                "Get-CimInstance -ClassName Win32_VideoController | Where-Object {$_.Primary -eq $true} | Select-Object -First 1 -ExpandProperty PNPDeviceID"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                active_gpu_pnp_id = result.stdout.strip()
            
            # Method 2: If primary method fails, try to get the adapter being used by the current session
            # Focus on enabled devices (ConfigManagerErrorCode -eq 0) and exclude disabled ones (ErrorCode 22)
            if not active_gpu_pnp_id:
                result = subprocess.run([
                    'powershell', '-Command', 
                    "Get-CimInstance -ClassName Win32_VideoController | Where-Object {$_.Name -notlike '*Basic*' -and $_.ConfigManagerErrorCode -eq 0 -and $_.Status -eq 'OK'} | Sort-Object AdapterRAM -Descending | Select-Object -First 1 -ExpandProperty PNPDeviceID"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0 and result.stdout.strip():
                    active_gpu_pnp_id = result.stdout.strip()
            
            # Method 3: If still no active GPU found, get any functioning GPU (not disabled)
            if not active_gpu_pnp_id:
                result = subprocess.run([
                    'powershell', '-Command', 
                    "Get-CimInstance -ClassName Win32_VideoController | Where-Object {$_.ConfigManagerErrorCode -ne 22 -and $_.Name -notlike '*Basic*'} | Sort-Object AdapterRAM -Descending | Select-Object -First 1 -ExpandProperty PNPDeviceID"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0 and result.stdout.strip():
                    active_gpu_pnp_id = result.stdout.strip()
    except:
        pass
        
    # Try to get GPU info using PowerShell CIM command
    try:
        if platform.system() == 'Windows':
            # Get comprehensive GPU information using PowerShell with status details
            result = subprocess.run([
                'powershell', '-Command', 
                "Get-CIMInstance -ClassName Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion,DriverDate,DeviceID,PNPDeviceID,Status,ConfigManagerErrorCode,Availability,Present | ConvertTo-Csv -NoTypeInformation"
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # Skip header line
                    # Parse CSV header to get column indices
                    header = lines[0].replace('"', '').split(',')
                    name_idx = next((i for i, col in enumerate(header) if 'name' in col.lower()), -1)
                    adapter_ram_idx = next((i for i, col in enumerate(header) if 'adapterram' in col.lower()), -1)
                    driver_version_idx = next((i for i, col in enumerate(header) if 'driverversion' in col.lower()), -1)
                    driver_date_idx = next((i for i, col in enumerate(header) if 'driverdate' in col.lower()), -1)
                    device_id_idx = next((i for i, col in enumerate(header) if 'deviceid' in col.lower() and 'pnp' not in col.lower()), -1)
                    pnp_device_id_idx = next((i for i, col in enumerate(header) if 'pnpdeviceid' in col.lower()), -1)
                    status_idx = next((i for i, col in enumerate(header) if col.lower() == 'status'), -1)
                    config_error_idx = next((i for i, col in enumerate(header) if 'configmanagererrorcode' in col.lower()), -1)
                    availability_idx = next((i for i, col in enumerate(header) if 'availability' in col.lower()), -1)
                    present_idx = next((i for i, col in enumerate(header) if 'present' in col.lower()), -1)
                    
                    # First pass: collect all GPU info
                    gpu_candidates = []
                    for line in lines[1:]:  # Skip header
                        if line.strip():
                            # Parse CSV line, handling quoted values
                            import csv
                            import io
                            try:
                                reader = csv.reader(io.StringIO(line))
                                parts = next(reader, [])
                                
                                max_idx = max(name_idx, adapter_ram_idx, driver_version_idx, driver_date_idx, 
                                            device_id_idx, pnp_device_id_idx, status_idx, config_error_idx, 
                                            availability_idx, present_idx)
                                
                                if len(parts) > max_idx:
                                    name = parts[name_idx] if name_idx >= 0 and name_idx < len(parts) else ''
                                    adapter_ram = parts[adapter_ram_idx] if adapter_ram_idx >= 0 and adapter_ram_idx < len(parts) else ''
                                    driver_version = parts[driver_version_idx] if driver_version_idx >= 0 and driver_version_idx < len(parts) else ''
                                    driver_date = parts[driver_date_idx] if driver_date_idx >= 0 and driver_date_idx < len(parts) else ''
                                    device_id = parts[device_id_idx] if device_id_idx >= 0 and device_id_idx < len(parts) else ''
                                    pnp_device_id = parts[pnp_device_id_idx] if pnp_device_id_idx >= 0 and pnp_device_id_idx < len(parts) else ''
                                    status = parts[status_idx] if status_idx >= 0 and status_idx < len(parts) else ''
                                    config_error = parts[config_error_idx] if config_error_idx >= 0 and config_error_idx < len(parts) else ''
                                    availability = parts[availability_idx] if availability_idx >= 0 and availability_idx < len(parts) else ''
                                    present = parts[present_idx] if present_idx >= 0 and present_idx < len(parts) else ''
                                    
                                    # Skip empty entries
                                    if not name or name.lower() in ['', 'null']:
                                        continue
                                    
                                    # Check if GPU is disabled in Device Manager
                                    is_disabled = False
                                    try:
                                        error_code = int(config_error) if config_error.isdigit() else 0
                                        if error_code == 22:  # Device is disabled
                                            is_disabled = True
                                    except:
                                        pass
                                    
                                    # Also check status for disabled state
                                    if status.lower() in ['error', 'degraded'] and not status.lower() == 'ok':
                                        is_disabled = True
                                    
                                    # Skip disabled GPUs completely - they shouldn't be listed
                                    if is_disabled:
                                        continue
                                    
                                    # Convert memory if available
                                    memory = 0
                                    if adapter_ram and adapter_ram.isdigit():
                                        memory = int(adapter_ram)
                                    
                                    # Parse driver date from PowerShell CIM format
                                    if driver_date and driver_date not in ['NULL', '']:
                                        try:
                                            # PowerShell CIM can return dates in different formats:
                                            # Format 1: "2024/11/27 8:00:00"
                                            # Format 2: "20231201000000.000000-000"
                                            if '/' in driver_date:
                                                # Format: "2024/11/27 8:00:00"
                                                date_part = driver_date.split(' ')[0]  # Get date part before space
                                                if date_part:
                                                    # Convert from YYYY/MM/DD to YYYY-MM-DD, ensuring zero-padding
                                                    parts = date_part.split('/')
                                                    if len(parts) == 3:
                                                        year, month, day = parts
                                                        driver_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                                                    else:
                                                        driver_date = date_part.replace('/', '-')
                                            elif len(driver_date) >= 8 and driver_date[:8].isdigit():
                                                # Format: "20231201000000.000000-000"
                                                date_part = driver_date[:8]
                                                year = date_part[:4]
                                                month = date_part[4:6]
                                                day = date_part[6:8]
                                                driver_date = f"{year}-{month}-{day}"
                                            else:
                                                driver_date = None
                                        except:
                                            driver_date = None
                                    else:
                                        driver_date = None
                                    
                                    # Extract device ID from PNP device ID if available
                                    # Replace if device_id is empty, NULL, or in VideoControllerX format
                                    if (not device_id or device_id == 'NULL' or 
                                        (device_id and device_id.startswith('VideoController'))):
                                        if pnp_device_id:
                                            try:
                                                # Handle standard PCI devices with VEN_/DEV_ pattern
                                                if 'VEN_' in pnp_device_id and 'DEV_' in pnp_device_id:
                                                    # Extract vendor and device IDs from PNP device ID
                                                    # Example: PCI\VEN_10DE&DEV_2C02&SUBSYS_41761458&REV_A1\1AFA3104CC2DB04800
                                                    ven_start = pnp_device_id.find('VEN_') + 4
                                                    ven_end = pnp_device_id.find('&', ven_start)
                                                    if ven_end == -1:
                                                        ven_end = pnp_device_id.find('\\', ven_start)
                                                    if ven_end == -1:
                                                        ven_end = len(pnp_device_id)
                                                    
                                                    dev_start = pnp_device_id.find('DEV_') + 4
                                                    dev_end = pnp_device_id.find('&', dev_start)
                                                    if dev_end == -1:
                                                        dev_end = pnp_device_id.find('\\', dev_start)
                                                    if dev_end == -1:
                                                        dev_end = len(pnp_device_id)
                                                    
                                                    vendor_id = pnp_device_id[ven_start:ven_end].upper()
                                                    device_id_part = pnp_device_id[dev_start:dev_end].upper()
                                                    
                                                    # Use human-readable format: VENDOR:DEVICE (e.g., 10DE:2C02)
                                                    device_id = f"{vendor_id}:{device_id_part}"
                                                
                                                # Handle Microsoft Remote Display Adapter and other SWD devices
                                                elif pnp_device_id.startswith('SWD\\'):
                                                    # Example: SWD\REMOTEDISPLAYENUM\RDPIDD_INDIRECTDISPLAY&SESSIONID_0001
                                                    if 'REMOTEDISPLAYENUM' in pnp_device_id:
                                                        # Microsoft Remote Display Adapter uses vendor ID 1414
                                                        device_id = "1414:REMOTE_DISPLAY"
                                                    else:
                                                        # Other SWD devices - use a generic identifier
                                                        parts = pnp_device_id.split('\\')
                                                        if len(parts) >= 3:
                                                            device_type = parts[1].upper()
                                                            device_id = f"SWD:{device_type}"
                                                        else:
                                                            device_id = "SWD:UNKNOWN"
                                                
                                                # Handle ROOT devices (virtual/system devices)
                                                elif pnp_device_id.startswith('ROOT\\'):
                                                    parts = pnp_device_id.split('\\')
                                                    if len(parts) >= 2:
                                                        device_type = parts[1].upper()
                                                        device_id = f"ROOT:{device_type}"
                                                    else:
                                                        device_id = "ROOT:UNKNOWN"
                                                
                                                # Handle other device types
                                                else:
                                                    # Try to extract a meaningful identifier from the PNP ID
                                                    parts = pnp_device_id.split('\\')
                                                    if len(parts) >= 2:
                                                        bus_type = parts[0].upper()
                                                        device_type = parts[1].split('&')[0].upper()
                                                        device_id = f"{bus_type}:{device_type}"
                                                    else:
                                                        device_id = f"UNKNOWN:{pnp_device_id[:20]}"  # Truncate for readability
                                            except:
                                                device_id = None
                                    
                                    # Determine vendor
                                    vendor = 'Unknown'
                                    name_upper = name.upper()
                                    if 'NVIDIA' in name_upper:
                                        vendor = 'NVIDIA'
                                    elif 'AMD' in name_upper or 'ATI' in name_upper:
                                        vendor = 'AMD'
                                    elif 'INTEL' in name_upper:
                                        vendor = 'Intel'
                                    elif 'MICROSOFT' in name_upper:
                                        vendor = 'Microsoft'
                                    elif pnp_device_id and ('SWD\\REMOTEDISPLAYENUM' in pnp_device_id or 'REMOTE' in name_upper):
                                        vendor = 'Microsoft'
                                    else:
                                        # Check device ID for vendor identification
                                        if device_id and ':' in device_id:
                                            vendor_id = device_id.split(':')[0]
                                            vendor_map = {
                                                '1414': 'Microsoft',
                                                '10DE': 'NVIDIA',
                                                '1002': 'AMD',
                                                '8086': 'Intel',
                                                '102B': 'Matrox',
                                                '5333': 'S3 Graphics'
                                            }
                                            vendor = vendor_map.get(vendor_id, 'Integrated')
                                        else:
                                            vendor = 'Integrated'
                                    
                                    gpu_candidates.append({
                                        'index': len(gpu_candidates),
                                        'model': name,
                                        'name': name,
                                        'memory_total': memory,
                                        'driver_version': driver_version if driver_version and driver_version != 'NULL' else 'Unknown',
                                        'driver_date': driver_date,
                                        'device_id': device_id if device_id and device_id != 'NULL' else None,
                                        'vendor': vendor,
                                        'pnp_device_id': pnp_device_id if pnp_device_id and pnp_device_id != 'NULL' else None,
                                        'status': status if status and status != 'NULL' else 'Unknown',
                                        'config_error_code': int(config_error) if config_error.isdigit() else 0,
                                        'is_enabled': True  # Only enabled GPUs reach this point
                                    })
                            except (ValueError, IndexError, csv.Error):
                                continue
                    
                    # Second pass: determine which GPU is active
                    for gpu in gpu_candidates:
                        # Determine if this is the active GPU
                        is_active = False
                        if active_gpu_pnp_id and gpu['pnp_device_id']:
                            is_active = (gpu['pnp_device_id'] == active_gpu_pnp_id)
                        
                        # Add is_active field
                        gpu['is_active'] = is_active
                        gpus.append(gpu)
                    
                    # If no GPU was marked as active by Windows, use heuristics for the best GPU
                    if not any(gpu.get('is_active', False) for gpu in gpus):
                        # Find the best GPU using smart heuristics
                        best_gpu = None
                        
                        # Priority: High-memory NVIDIA > High-memory AMD > Any NVIDIA > Any AMD > Intel > First
                        for gpu in gpus:
                            if gpu['vendor'] == 'NVIDIA' and gpu['memory_total'] > 2000000000:  # > 2GB NVIDIA
                                best_gpu = gpu
                                break
                        
                        if not best_gpu:
                            for gpu in gpus:
                                if gpu['vendor'] == 'AMD' and gpu['memory_total'] > 2000000000:  # > 2GB AMD
                                    best_gpu = gpu
                                    break
                        
                        if not best_gpu:
                            for gpu in gpus:
                                if gpu['vendor'] == 'NVIDIA':  # Any NVIDIA
                                    best_gpu = gpu
                                    break
                        
                        if not best_gpu:
                            for gpu in gpus:
                                if gpu['vendor'] == 'AMD':  # Any AMD
                                    best_gpu = gpu
                                    break
                        
                        if not best_gpu and gpus:
                            best_gpu = gpus[0]  # First GPU as last resort
                        
                        if best_gpu:
                            best_gpu['is_active'] = True
    except:
        pass
    
    # If no GPUs found with the comprehensive method, try simple fallback
    if not gpus:
        try:
            if platform.system() == 'Windows':
                result = subprocess.run([
                    'wmic', 'path', 'win32_VideoController', 'get', 
                    'name,DriverVersion,DriverDate,DeviceID',
                    '/format:csv'
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    for i, line in enumerate(lines):
                        if line.strip() and ',' in line:
                            parts = [part.strip() for part in line.split(',')]
                            if len(parts) >= 4:
                                try:
                                    device_id = parts[1] if parts[1] != 'NULL' else None
                                    driver_date = parts[2] if parts[2] != 'NULL' else None
                                    driver_version = parts[3] if parts[3] != 'NULL' else 'Unknown'
                                    name = parts[4] if len(parts) > 4 and parts[4] != 'NULL' else 'Unknown GPU'
                                    
                                    if not name or name == 'Unknown GPU':
                                        continue
                                    
                                    # Clean up driver date
                                    if driver_date and len(driver_date) == 8 and driver_date.isdigit():
                                        try:
                                            year = driver_date[:4]
                                            month = driver_date[4:6]
                                            day = driver_date[6:8]
                                            driver_date = f"{year}-{month}-{day}"
                                        except:
                                            driver_date = None
                                    
                                    # For fallback method, mark first GPU or NVIDIA as active
                                    is_active = False
                                    if not any(gpu.get('is_active', False) for gpu in gpus):
                                        if 'NVIDIA' in name.upper():
                                            is_active = True
                                        elif i == 0:  # First GPU
                                            is_active = True
                                    
                                    gpus.append({
                                        'index': i,
                                        'model': name,
                                        'name': name,
                                        'driver_version': driver_version,
                                        'driver_date': driver_date,
                                        'device_id': device_id,
                                        'vendor': 'Integrated',
                                        'memory_total': 0,
                                        'is_active': is_active
                                    })
                                except (ValueError, IndexError):
                                    continue
        except:
            pass
    
    return gpus


def get_os_info() -> Dict[str, Any]:
    """Get operating system information with detailed version using ver command"""
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
        
        # Get additional Windows info with detailed version using ver command
        if platform.system() == 'Windows':
            try:
                # Use ver command to get Windows version
                result = subprocess.run(['ver'], capture_output=True, text=True, shell=True, timeout=5)
                if result.returncode == 0:
                    ver_output = result.stdout.strip()
                    # Extract version from ver command output
                    # Example: "Microsoft Windows [Version 10.0.26100.4349]"
                    if 'Version' in ver_output:
                        import re
                        version_match = re.search(r'Version\s+([\d\.]+)', ver_output)
                        if version_match:
                            os_info['ver_command_version'] = version_match.group(1)
                        os_info['ver_command_output'] = ver_output
            except:
                pass
            
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
                
                # Get UBR (Update Build Revision) for the full build number
                try:
                    os_info['windows_ubr'] = winreg.QueryValueEx(key, "UBR")[0]
                except:
                    pass
                    
                winreg.CloseKey(key)
                winreg.CloseKey(reg)
                
                # Create a more detailed version string for Windows, prefer ver command output
                version_parts = []
                if 'ver_command_version' in os_info:
                    # Use version from ver command as primary source (already includes build info)
                    version_parts.append(f"Windows Version {os_info['ver_command_version']}")
                elif 'windows_product_name' in os_info:
                    version_parts.append(os_info['windows_product_name'])
                    if 'windows_display_version' in os_info:
                        version_parts.append(f"Version {os_info['windows_display_version']}")
                    
                    # Only add build info if we're not using ver command (which already includes it)
                    if 'windows_build' in os_info:
                        build_str = f"Build {os_info['windows_build']}"
                        # Add UBR if available for full build number like 26100.4349
                        if 'windows_ubr' in os_info:
                            build_str += f".{os_info['windows_ubr']}"
                        version_parts.append(build_str)
                
                if version_parts:
                    os_info['detailed_version'] = ' '.join(version_parts)
                else:
                    os_info['detailed_version'] = f"{os_info['system']} {os_info['release']}"
                    
            except:
                # Fallback to ver command output if registry fails
                if 'ver_command_output' in os_info:
                    os_info['detailed_version'] = os_info['ver_command_output']
                else:
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
        # Clean hostname - remove any domain suffix and numbers that might be appended
        clean_hostname = hostname.split('.')[0]  # Remove domain suffix
        
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
        ip_addresses = []
        try:
            for interface, addrs in psutil.net_if_addrs().items():
                interface_info = {'name': interface, 'addresses': []}
                for addr in addrs:
                    if addr.family == socket.AF_INET:  # IPv4
                        # Clean IP address - remove any port numbers
                        clean_ip = addr.address.split(':')[0]
                        interface_info['addresses'].append({
                            'type': 'IPv4',
                            'address': clean_ip,
                            'netmask': addr.netmask if hasattr(addr, 'netmask') else None
                        })
                        # Collect non-loopback IPs
                        if not clean_ip.startswith('127.'):
                            ip_addresses.append(clean_ip)
                    elif addr.family == socket.AF_INET6:  # IPv6
                        # Clean IPv6 address - remove zone identifier and port
                        clean_ip = addr.address.split('%')[0].split(']')[0].lstrip('[')
                        interface_info['addresses'].append({
                            'type': 'IPv6',
                            'address': clean_ip,
                            'netmask': addr.netmask if hasattr(addr, 'netmask') else None
                        })
                interfaces.append(interface_info)
        except:
            pass
        
        return {
            'hostname': hostname,
            'clean_hostname': clean_hostname,
            'local_ip': local_ip,
            'ip_addresses': ip_addresses,
            'interfaces': interfaces[:5]  # Limit to first 5 interfaces
        }
    except Exception as e:
        return {
            'hostname': 'unknown',
            'clean_hostname': 'unknown',
            'local_ip': '127.0.0.1',
            'ip_addresses': [],
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
        
        # GPU summary with model and driver version, prioritize active GPU
        gpus = system_info['gpu']
        if gpus:
            gpu_summaries = []
            # Show active GPU first
            active_gpus = [gpu for gpu in gpus if gpu.get('is_active', False)]
            other_gpus = [gpu for gpu in gpus if not gpu.get('is_active', False)]
            
            for gpu in active_gpus + other_gpus[:1]:  # Active GPU + 1 other
                model = gpu.get('model', gpu.get('name', 'Unknown GPU'))
                driver = gpu.get('driver_version', 'Unknown')
                active_marker = " (Active)" if gpu.get('is_active', False) else ""
                if driver != 'Unknown':
                    gpu_summaries.append(f"{model}{active_marker} (Driver: {driver})")
                else:
                    gpu_summaries.append(f"{model}{active_marker}")
            gpu_summary = ', '.join(gpu_summaries)
        else:
            gpu_summary = 'No dedicated GPU detected'
        
        # OS summary with detailed version including UBR
        os_info = system_info['os']
        os_summary = os_info.get('detailed_version', f"{os_info.get('system', 'Unknown')} {os_info.get('release', '')}")
        
        # Network info with clean hostname
        network_info = system_info['network']
        clean_hostname = network_info.get('clean_hostname', network_info.get('hostname', 'unknown'))
        clean_ip = network_info.get('local_ip', '127.0.0.1')
        
        return {
            'cpu': cpu_summary,
            'memory': memory_summary,
            'gpu': gpu_summary,
            'os': os_summary,
            'hostname': clean_hostname,
            'ip': clean_ip,
            'full_hostname': network_info.get('hostname', 'unknown')  # Keep original for reference
        }
    except Exception as e:
        return {
            'cpu': 'Unknown',
            'memory': 'Unknown', 
            'gpu': 'Unknown',
            'os': 'Unknown',
            'hostname': 'unknown',
            'ip': '127.0.0.1',
            'full_hostname': 'unknown',
            'error': str(e)
        }


def get_client_name() -> str:
    """Get client/hostname for client identification"""
    try:
        return socket.gethostname()
    except Exception:
        try:
            return platform.node()
        except Exception:
            return 'unknown-client'


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
