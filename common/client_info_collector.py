"""
Unified Client Information Collection Module

This module provides standardized client information collection logic
that can be used across different scenarios:
1. Client registration
2. Heartbeat updates
3. Proactive ping responses

The logic is separated from service/daemon code to allow hot-reloading
without requiring service restarts.
"""

import logging
import importlib
import sys
import os
from typing import Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class ClientInfoCollector:
    """
    Unified client information collector that can be dynamically reloaded
    without service restart
    """
    
    def __init__(self):
        self._system_info_module = None
        self._last_reload_time = None
        self._collection_cache = {}
        self._cache_duration = 5  # Cache for 5 seconds to avoid repeated calls
        
    def _ensure_system_info_module(self):
        """Ensure system_info module is loaded and up-to-date"""
        try:
            # Import or reload the system_info module
            if 'common.system_info' in sys.modules:
                # Reload existing module to get latest changes
                importlib.reload(sys.modules['common.system_info'])
                logger.debug("Reloaded common.system_info module")
            else:
                # First-time import
                logger.debug("Loading common.system_info module")
            
            from common.system_info import get_system_info, get_system_summary
            self._system_info_module = {
                'get_system_info': get_system_info,
                'get_system_summary': get_system_summary
            }
            self._last_reload_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Failed to load/reload system_info module: {e}")
            self._system_info_module = None
            raise
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self._collection_cache:
            return False
        
        cache_entry = self._collection_cache[cache_key]
        cache_time = cache_entry.get('timestamp')
        if not cache_time:
            return False
        
        time_diff = (datetime.now() - cache_time).total_seconds()
        return time_diff < self._cache_duration
    
    def _cache_result(self, cache_key: str, data: Dict[str, Any]):
        """Cache collection result"""
        self._collection_cache[cache_key] = {
            'data': data,
            'timestamp': datetime.now()
        }
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached result if valid"""
        if self._is_cache_valid(cache_key):
            return self._collection_cache[cache_key]['data']
        return None
    
    def collect_fresh_system_info(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Collect fresh system information
        
        Args:
            force_reload: Force reload of system_info module
            
        Returns:
            Dict containing system information and summary
        """
        cache_key = "fresh_system_info"
        
        # Check cache first (unless force_reload is True)
        if not force_reload:
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                logger.debug("Using cached system information")
                return cached_result
        
        logger.debug("Collecting fresh system information...")
        
        try:
            # Ensure we have the latest system_info module
            if force_reload or not self._system_info_module:
                self._ensure_system_info_module()
            
            if not self._system_info_module:
                raise Exception("System info module not available")
            
            # Collect fresh information
            get_system_info = self._system_info_module['get_system_info']
            get_system_summary = self._system_info_module['get_system_summary']
            
            system_info = get_system_info()
            system_summary = get_system_summary()
            
            result = {
                'system_info': system_info,
                'system_summary': system_summary,
                'collection_timestamp': datetime.now().isoformat(),
                'collection_source': 'fresh_collection'
            }
            
            # Cache the result
            self._cache_result(cache_key, result)
            
            logger.debug(f"Fresh system info collected - CPU: {system_summary.get('cpu', 'Unknown')}, GPU: {system_summary.get('gpu', 'Unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to collect fresh system information: {e}")
            # Return minimal fallback information
            return {
                'system_info': {
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                },
                'system_summary': {
                    'error': str(e),
                    'cpu': 'Unknown',
                    'memory': 'Unknown',
                    'gpu': 'Unknown',
                    'os': 'Unknown',
                    'hostname': 'unknown',
                    'ip': '127.0.0.1'
                },
                'collection_timestamp': datetime.now().isoformat(),
                'collection_source': 'error_fallback'
            }
    
    def prepare_registration_data(self, client_name: str, ip_address: str, port: int = 8080) -> Dict[str, Any]:
        """
        Prepare client registration data with fresh system information
        
        Args:
            client_name: Name of the client
            ip_address: IP address of the client
            port: Port number (default: 8080)
            
        Returns:
            Dict containing registration data with fresh system information
        """
        logger.info(f"Preparing registration data for client: {client_name}")
        
        try:
            # Collect fresh system information
            info_result = self.collect_fresh_system_info(force_reload=True)
            system_info = info_result['system_info']
            system_summary = info_result['system_summary']
            
            registration_data = {
                'name': client_name,
                'ip_address': ip_address,
                'port': port,
                'status': 'online',
                # Fresh system information
                'cpu_info': system_info.get('cpu'),
                'memory_info': system_info.get('memory'),
                'gpu_info': system_info.get('gpu'),
                'os_info': system_info.get('os'),
                'disk_info': system_info.get('disk'),
                'system_summary': system_summary,
                # Metadata
                'collection_timestamp': info_result['collection_timestamp'],
                'collection_source': 'registration'
            }
            
            logger.info(f"Registration data prepared - System: {system_summary.get('os', 'Unknown')}")
            return registration_data
            
        except Exception as e:
            logger.error(f"Failed to prepare registration data: {e}")
            raise
    
    def prepare_heartbeat_data(self, client_name: str, status: str = 'online') -> Dict[str, Any]:
        """
        Prepare heartbeat data with fresh system information
        
        Args:
            client_name: Name of the client
            status: Client status (default: 'online')
            
        Returns:
            Dict containing heartbeat data with fresh system information
        """
        logger.debug(f"Preparing heartbeat data for client: {client_name}")
        
        try:
            # Collect fresh system information (allow short-term caching for heartbeats)
            info_result = self.collect_fresh_system_info(force_reload=False)
            system_info = info_result['system_info']
            system_summary = info_result['system_summary']
            
            heartbeat_data = {
                'client_name': client_name,
                'status': status,
                'timestamp': datetime.now().isoformat(),
                # Fresh system information
                'cpu_info': system_info.get('cpu'),
                'memory_info': system_info.get('memory'),
                'gpu_info': system_info.get('gpu'),
                'os_info': system_info.get('os'),
                'disk_info': system_info.get('disk'),
                'system_summary': system_summary,
                # Metadata
                'collection_timestamp': info_result['collection_timestamp'],
                'collection_source': 'heartbeat'
            }
            
            logger.debug(f"Heartbeat data prepared with fresh system info")
            return heartbeat_data
            
        except Exception as e:
            logger.warning(f"Failed to collect fresh system info for heartbeat, using minimal data: {e}")
            # Return minimal heartbeat data without system info
            return {
                'client_name': client_name,
                'status': status,
                'timestamp': datetime.now().isoformat(),
                'collection_source': 'heartbeat_minimal',
                'error': str(e)
            }
    
    def prepare_ping_response_data(self, client_name: str, additional_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Prepare ping response data with fresh system information
        
        Args:
            client_name: Name of the client
            additional_data: Additional data to include in response
            
        Returns:
            Dict containing ping response data with fresh system information
        """
        logger.debug(f"Preparing ping response data for client: {client_name}")
        
        try:
            # Collect fresh system information for ping responses
            info_result = self.collect_fresh_system_info(force_reload=True)
            system_info = info_result['system_info']
            system_summary = info_result['system_summary']
            
            ping_data = {
                'client_name': client_name,
                'status': 'online',
                'response_timestamp': datetime.now().isoformat(),
                # Fresh system information
                'cpu_info': system_info.get('cpu'),
                'memory_info': system_info.get('memory'),
                'gpu_info': system_info.get('gpu'),
                'os_info': system_info.get('os'),
                'disk_info': system_info.get('disk'),
                'system_summary': system_summary,
                # Metadata
                'collection_timestamp': info_result['collection_timestamp'],
                'collection_source': 'ping_response'
            }
            
            # Add any additional data
            if additional_data:
                ping_data.update(additional_data)
            
            logger.debug(f"Ping response data prepared with fresh system info")
            return ping_data
            
        except Exception as e:
            logger.error(f"Failed to prepare ping response data: {e}")
            # Return minimal response
            ping_data = {
                'client_name': client_name,
                'status': 'online',
                'response_timestamp': datetime.now().isoformat(),
                'collection_source': 'ping_response_minimal',
                'error': str(e)
            }
            
            if additional_data:
                ping_data.update(additional_data)
            
            return ping_data
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about information collection"""
        return {
            'module_loaded': self._system_info_module is not None,
            'last_reload_time': self._last_reload_time.isoformat() if self._last_reload_time else None,
            'cache_entries': len(self._collection_cache),
            'cache_duration': self._cache_duration
        }
    
    def clear_cache(self):
        """Clear collection cache"""
        self._collection_cache.clear()
        logger.debug("Client info collection cache cleared")
    
    def force_module_reload(self):
        """Force reload of system info module"""
        try:
            self._ensure_system_info_module()
            self.clear_cache()
            logger.info("System info module forcibly reloaded")
        except Exception as e:
            logger.error(f"Failed to force reload system info module: {e}")
            raise


# Global instance for shared use
_client_info_collector = None

def get_client_info_collector() -> ClientInfoCollector:
    """Get the global client info collector instance"""
    global _client_info_collector
    if _client_info_collector is None:
        _client_info_collector = ClientInfoCollector()
    return _client_info_collector

def collect_fresh_system_info(force_reload: bool = False) -> Dict[str, Any]:
    """Convenience function to collect fresh system information"""
    collector = get_client_info_collector()
    return collector.collect_fresh_system_info(force_reload=force_reload)

def prepare_registration_data(client_name: str, ip_address: str, port: int = 8080) -> Dict[str, Any]:
    """Convenience function to prepare registration data"""
    collector = get_client_info_collector()
    return collector.prepare_registration_data(client_name, ip_address, port)

def prepare_heartbeat_data(client_name: str, status: str = 'online') -> Dict[str, Any]:
    """Convenience function to prepare heartbeat data"""
    collector = get_client_info_collector()
    return collector.prepare_heartbeat_data(client_name, status)

def prepare_ping_response_data(client_name: str, additional_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Convenience function to prepare ping response data"""
    collector = get_client_info_collector()
    return collector.prepare_ping_response_data(client_name, additional_data)
