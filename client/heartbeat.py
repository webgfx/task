"""
Heartbeat manager
Responsible for sending periodic heartbeats to the server to maintain machine online status
"""
import time
import threading
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

class HeartbeatManager:
    def __init__(self, server_url: str, machine_name: str, interval: int = 30):
        """
        Initialize heartbeat manager
        
        Args:
            server_url: Server URL
            machine_name: Machine name
            interval: Heartbeat interval (seconds)
        """
        self.server_url = server_url
        self.machine_name = machine_name
        self.interval = interval
        self.running = False
        self.thread = None
        self.last_heartbeat = None
        self.error_count = 0
        self.max_errors = 5  # Maximum consecutive error count
        
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
        """Send heartbeat to server"""
        try:
            heartbeat_data = {
                'machine_name': self.machine_name,
                'status': 'online',
                'timestamp': datetime.now().isoformat()
            }
            
            response = requests.post(
                f"{self.server_url}/api/machines/heartbeat",
                json=heartbeat_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.debug(f"Heartbeat sent successfully: {self.machine_name}")
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
                'machine_name': self.machine_name,
                'status': 'offline',
                'timestamp': datetime.now().isoformat()
            }
            
            response = requests.post(
                f"{self.server_url}/api/machines/heartbeat",
                json=offline_data,
                timeout=5  # Shorter timeout
            )
            
            if response.status_code == 200:
                logger.info(f"Offline status sent successfully: {self.machine_name}")
            else:
                logger.warning(f"Offline status send failed: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Send offline status exception: {e}")
    
    def get_status(self) -> dict:
        """Get heartbeat status"""
        return {
            'running': self.running,
            'machine_name': self.machine_name,
            'interval': self.interval,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'error_count': self.error_count,
            'is_healthy': self.error_count < self.max_errors
        }
    
    def force_heartbeat(self) -> bool:
        """Force send heartbeat once"""
        logger.info("Force send heartbeat")
        return self._send_heartbeat()
