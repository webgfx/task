"""
Hostname subtas    description="Returns the hostname of the current client",
    result_type="string",
    is_critical=True,
    format_hint="Client hostname string (e.g., 'DESKTOP-ABC123')")r retrieving client hostname.

This subtask provides functionality to get the hostname of the current client
using multiple fallback methods for reliability.
"""

import socket
import platform
import os
import logging
from typing import Dict, Any

from .base import SubtaskResultDefinition
from . import register_subtask


# Define the result specification for this subtask
HOSTNAME_RESULT_DEF = SubtaskResultDefinition(
    name="get_hostname",
    description="Returns the hostname of the current client",
    result_type="string",
    is_critical=True,
    format_hint="client hostname string (e.g., 'DESKTOP-ABC123')"
)


@register_subtask('get_hostname', HOSTNAME_RESULT_DEF)
def get_hostname() -> str:
    """
    Get the hostname of the current client.
    
    This function tries multiple methods to reliably get the hostname:
    1. socket.gethostname() - Primary method
    2. platform.node() - Fallback method
    3. Environment variables (COMPUTERNAME/HOSTNAME) - Final fallback
    
    Returns:
        str: The hostname of the current client
        
    Example:
        >>> result = execute_subtask('get_hostname')
        >>> print(result['result'])  # 'DESKTOP-ABC123' or similar
        
    Raises:
        Exception: If all hostname detection methods fail
    """
    try:
        # Method 1: Try socket.gethostname() - most reliable
        hostname = socket.gethostname()
        
        # Validate the hostname - reject localhost and empty values
        if hostname and hostname.lower() not in ['localhost', '127.0.0.1', '']:
            return hostname.strip()
        
        # Method 2: Try platform.node() as fallback
        hostname = platform.node()
        if hostname and hostname.lower() not in ['localhost', '127.0.0.1', '']:
            return hostname.strip()
        
        # Method 3: Try environment variables as final fallback
        hostname = os.environ.get('COMPUTERNAME')  # Windows
        if hostname:
            return hostname.strip()
            
        hostname = os.environ.get('HOSTNAME')  # Unix/Linux
        if hostname:
            return hostname.strip()
        
        # Method 4: If all else fails, generate a system-based name
        system_name = platform.system().lower()
        fallback_hostname = f"unknown-host-{system_name}"
        
        logging.warning(f"Could not determine hostname, using fallback: {fallback_hostname}")
        return fallback_hostname
        
    except Exception as e:
        # Log the error but still return a usable hostname
        error_msg = f"Failed to get hostname: {e}"
        logging.error(error_msg)
        
        # Return a fallback hostname even in error cases
        system_name = platform.system().lower() if hasattr(platform, 'system') else 'unknown'
        fallback_hostname = f"error-host-{system_name}"
        
        logging.warning(f"Using emergency fallback hostname: {fallback_hostname}")
        return fallback_hostname


def validate_hostname(hostname: str) -> Dict[str, Any]:
    """
    Validate a hostname for correctness and provide details.
    
    Args:
        hostname: The hostname to validate
        
    Returns:
        Dict[str, Any]: Validation results including validity and details
    """
    validation_result = {
        'hostname': hostname,
        'is_valid': False,
        'is_localhost': False,
        'is_ip_address': False,
        'length': len(hostname),
        'issues': []
    }
    
    # Check for empty or None
    if not hostname:
        validation_result['issues'].append('Hostname is empty or None')
        return validation_result
    
    # Check for localhost variants
    localhost_variants = ['localhost', '127.0.0.1', '::1']
    if hostname.lower() in localhost_variants:
        validation_result['is_localhost'] = True
        validation_result['issues'].append('Hostname is localhost variant')
    
    # Check if it looks like an IP address
    parts = hostname.split('.')
    if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
        validation_result['is_ip_address'] = True
        validation_result['issues'].append('Hostname appears to be an IP address')
    
    # Check length constraints (RFC 1035)
    if len(hostname) > 253:
        validation_result['issues'].append('Hostname exceeds maximum length (253 characters)')
    
    # Check for valid characters (basic check)
    allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.')
    if not all(c in allowed_chars for c in hostname):
        validation_result['issues'].append('Hostname contains invalid characters')
    
    # If no issues found, mark as valid
    if not validation_result['issues']:
        validation_result['is_valid'] = True
    
    return validation_result

