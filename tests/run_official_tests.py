#!/usr/bin/env python3
"""
Official Test Execution Script for Distributed Task Management System

This script automates the execution of official test scenarios defined in TEST_SCENARIOS.md
"""

import sys
import os
import time
import requests
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestExecutor:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.test_results = {}
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
    def verify_server_running(self):
        """Verify server is accessible"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            if response.status_code == 200:
                self.log("✅ Server is running and accessible")
                return True
            else:
                self.log(f"❌ Server returned status code: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Cannot connect to server: {e}", "ERROR")
            return False
    
    def get_online_clients(self):
        """Get list of online clients"""
        try:
            response = requests.get(f"{self.base_url}/api/clients")
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    online_clients = [m for m in data['data'] if m['status'] == 'online']
                    self.log(f"✅ Found {len(online_clients)} online clients")
                    return online_clients
                else:
                    self.log(f"❌ API error: {data.get('error', 'Unknown error')}", "ERROR")
                    return []
            else:
                self.log(f"❌ Failed to get clients: {response.status_code}", "ERROR")
                return []
        except Exception as e:
            self.log(f"❌ Error getting clients: {e}", "ERROR")
            return []
    
    def create_task(self, task_name, subtasks, target_clients):
        """Create a new task"""
        try:
            task_data = {
                "name": task_name,
                "subtasks": subtasks,
                "target_clients": target_clients,
                "execution_type": "now"
            }
            
            response = requests.post(
                f"{self.base_url}/api/tasks",
                headers={"Content-Type": "application/json"},
                data=json.dumps(task_data)
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    task_id = data['data']['id']
                    self.log(f"✅ Task created successfully with ID: {task_id}")
                    return task_id
                else:
                    self.log(f"❌ Task creation failed: {data.get('error', 'Unknown error')}", "ERROR")
                    return None
            else:
                self.log(f"❌ HTTP error creating task: {response.status_code}", "ERROR")
                return None
        except Exception as e:
            self.log(f"❌ Error creating task: {e}", "ERROR")
            return None
    
    def wait_for_task_completion(self, task_id, timeout=60):
        """Wait for task to complete"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.base_url}/api/tasks/{task_id}")
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        task = data['data']
                        status = task.get('status')
                        self.log(f"Task {task_id} status: {status}")
                        
                        if status == 'completed':
                            self.log(f"✅ Task {task_id} completed successfully")
                            return True, task
                        elif status == 'failed':
                            self.log(f"❌ Task {task_id} failed", "ERROR")
                            return False, task
                        elif status in ['pending', 'running']:
                            time.sleep(2)  # Wait before checking again
                            continue
                        else:
                            self.log(f"❌ Unknown task status: {status}", "ERROR")
                            return False, task
                    else:
                        self.log(f"❌ API error: {data.get('error', 'Unknown error')}", "ERROR")
                        return False, None
                else:
                    self.log(f"❌ HTTP error getting task: {response.status_code}", "ERROR")
                    return False, None
            except Exception as e:
                self.log(f"❌ Error checking task status: {e}", "ERROR")
                return False, None
        
        self.log(f"❌ Task {task_id} timed out after {timeout} seconds", "ERROR")
        return False, None
    
    def test_single_subtask_single_client_now(self):
        """Execute the single-subtask-single-client-now test scenario"""
        self.log("🧪 Starting test: single-subtask-single-client-now")
        
        # Step 1: Verify server is running
        if not self.verify_server_running():
            return False
        
        # Step 2: Check for online clients
        online_clients = self.get_online_clients()
        if not online_clients:
            self.log("❌ No online clients found. Please start at least one client.", "ERROR")
            return False
        
        # Use the first online client
        target_client = online_clients[0]['name']
        self.log(f"Using target client: {target_client}")
        
        # Step 3: Create task with get_hostname subtask
        subtasks = [
            {
                "name": "get_hostname",
                "description": "Get system hostname",
                "order": 0
            }
        ]
        
        task_id = self.create_task(
            task_name="Test Single Hostname Task",
            subtasks=subtasks,
            target_clients=[target_client]
        )
        
        if not task_id:
            return False
        
        # Step 4: Wait for task completion
        success, task_result = self.wait_for_task_completion(task_id)
        
        if success and task_result:
            # Step 5: Verify results
            self.log("📊 Verifying task results...")
            
            # Check if task has subtasks with results
            subtasks_data = task_result.get('subtasks', [])
            if subtasks_data:
                hostname_subtask = subtasks_data[0]
                if hostname_subtask.get('status') == 'completed':
                    result = hostname_subtask.get('result', '')
                    if result and 'hostname' in result.lower():
                        self.log(f"✅ Hostname subtask completed successfully: {result}")
                        self.log("🎉 Test PASSED: single-subtask-single-client-now")
                        return True
                    else:
                        self.log(f"❌ Invalid hostname result: {result}", "ERROR")
                else:
                    self.log(f"❌ Subtask status: {hostname_subtask.get('status')}", "ERROR")
            else:
                self.log("❌ No subtask results found", "ERROR")
        
        self.log("💥 Test FAILED: single-subtask-single-client-now")
        return False

def main():
    """Main test execution function"""
    print("=" * 60)
    print("🚀 DISTRIBUTED TASK MANAGEMENT SYSTEM - OFFICIAL TESTS")
    print("=" * 60)
    
    executor = TestExecutor()
    
    # Available test scenarios
    test_scenarios = {
        "single-subtask-single-client-now": executor.test_single_subtask_single_client_now
    }
    
    if len(sys.argv) > 1:
        # Run specific test scenario
        scenario_name = sys.argv[1]
        if scenario_name in test_scenarios:
            success = test_scenarios[scenario_name]()
            sys.exit(0 if success else 1)
        else:
            print(f"❌ Unknown test scenario: {scenario_name}")
            print(f"Available scenarios: {', '.join(test_scenarios.keys())}")
            sys.exit(1)
    else:
        # Run all test scenarios
        print("Running all available test scenarios...")
        total_tests = len(test_scenarios)
        passed_tests = 0
        
        for scenario_name, test_func in test_scenarios.items():
            print(f"\n--- Running {scenario_name} ---")
            if test_func():
                passed_tests += 1
        
        print(f"\n{'=' * 60}")
        print(f"📈 TEST SUMMARY: {passed_tests}/{total_tests} tests passed")
        print(f"{'=' * 60}")
        
        sys.exit(0 if passed_tests == total_tests else 1)

if __name__ == "__main__":
    main()

