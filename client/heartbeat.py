"""
Heartbeat manager
Responsible for sending periodic heartbeats to the server to maintain client online status
"""
import time
import threading
import logging
import requests
import sys
import os
from datetime import datetime

# Add parent directory to path for importing common modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from common.client_info_collector import prepare_heartbeat_data
except ImportError as e:
    print(f"Warning: Failed to import client_info_collector module: {e}")
    prepare_heartbeat_data = None

logger = logging.getLogger(__name__)

class HeartbeatManager:
    def __init__(self, server_url: str, client_name: str, get_interval_func=None):
        """
        Initialize heartbeat manager
        
        Args:
            server_url: Server URL
            client_name: client name
            get_interval_func: Function to get heartbeat interval dynamically (if None, defaults to 60)
        """
        self.server_url = server_url
        self.client_name = client_name
        self.get_interval_func = get_interval_func
        self.running = False
        self.thread = None
        self.last_heartbeat = None
        self.error_count = 0
        self.max_errors = 5  # Maximum consecutive error count
        
    @property
    def interval(self):
        """Get current heartbeat interval from configuration"""
        if self.get_interval_func:
            return self.get_interval_func()
        return 60  # Default fallback
        
    def start(self):
        """Start heartbeat"""
        if self.running:
            logger.warning("Heartbeat manager is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.thread.start()
        logger.info(f"Heartbeat manager started, interval: {self.interval} seconds")
    
    def stop(self):
        """Stop heartbeat"""
        if not self.running:
            return
        
        logger.info("Stopping heartbeat manager...")
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        # Send offline status
        self._send_offline_status()
        
        logger.info("Heartbeat manager stopped")
    
    def _heartbeat_loop(self):
        """Heartbeat loop"""
        while self.running:
            try:
                success = self._send_heartbeat()
                
                if success:
                    self.error_count = 0
                    self.last_heartbeat = datetime.now()
                else:
                    self.error_count += 1
                    
                    if self.error_count >= self.max_errors:
                        logger.error(f"Failed heartbeat {self.error_count} times consecutively, may have lost connection to server")
                        # Can add reconnection logic or alerts here
                
                # Wait for next heartbeat
                for _ in range(self.interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Heartbeat loop exception: {e}")
                time.sleep(5)  # Wait 5 seconds before retry after exception
    
    def _send_heartbeat(self) -> bool:
        """Send heartbeat to server with fresh system information"""
        try:
            # Use unified client info collector for fresh system information
            heartbeat_data = None
            
            if prepare_heartbeat_data:
                try:
                    logger.debug("Using unified client info collector for heartbeat...")
                    heartbeat_data = prepare_heartbeat_data(self.client_name, 'online')
                    logger.debug("Fresh system information collected via unified collector")
                except Exception as e:
                    logger.warning(f"Failed to use unified collector, falling back to minimal heartbeat: {e}")
            
            # Fallback to minimal heartbeat if unified collector fails or unavailable
            if not heartbeat_data:
                heartbeat_data = {
                    'client_name': self.client_name,
                    'status': 'online',
                    'timestamp': datetime.now().isoformat(),
                    'collection_source': 'fallback_minimal'
                }
            
            response = requests.post(
                f"{self.server_url}/api/clients/heartbeat",
                json=heartbeat_data,
                timeout=10
            )
            
            if response.status_code == 200:
                collection_source = heartbeat_data.get('collection_source', 'unknown')
                if 'system_summary' in heartbeat_data:
                    system_summary = heartbeat_data['system_summary']
                    logger.debug(f"Heartbeat sent with fresh system info ({collection_source}): CPU={system_summary.get('cpu', 'Unknown')}, GPU={system_summary.get('gpu', 'Unknown')}")
                else:
                    logger.debug(f"Heartbeat sent ({collection_source}): {self.client_name}")
                return True
            else:
                logger.warning(f"Heartbeat send failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.warning("Heartbeat send timeout")
            return False
        except requests.exceptions.ConnectionError:
            logger.warning("Unable to connect to server")
            return False
        except Exception as e:
            logger.error(f"Send heartbeat exception: {e}")
            return False
    
    def _send_offline_status(self):
        """Send offline status"""
        try:
            offline_data = {
                'client_name': self.client_name,
                'status': 'offline',
                'timestamp': datetime.now().isoformat()
            }
            
            response = requests.post(
                f"{self.server_url}/api/clients/heartbeat",
                json=offline_data,
                timeout=5  # Shorter timeout
            )
            
            if response.status_code == 200:
                logger.info(f"Offline status sent successfully: {self.client_name}")
            else:
                logger.warning(f"Offline status send failed: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Send offline status exception: {e}")
    
    def get_status(self) -> dict:
        """Get heartbeat status"""
        return {
            'running': self.running,
            'client_name': self.client_name,
            'interval': self.interval,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'error_count': self.error_count,
            'is_healthy': self.error_count < self.max_errors
        }
    
    def force_heartbeat(self) -> bool:
        """Force send heartbeat once with fresh system information"""
        logger.info("Force send heartbeat with fresh system information")
        return self._send_heartbeat()

