"""
Example usage of the subtask system for both client and server.

This example demonstrates how to use the subtask system in both client and server code.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.subtasks import execute_subtask, list_subtasks, get_subtask


def example_client_usage():
    """Example of how client code can use subtasks"""
    print("=== Client Example ===")
    
    # List available subtasks
    available = list_subtasks()
    print(f"Available subtasks: {available}")
    
    # Execute the get_hostname subtask
    result = execute_subtask('get_hostname')
    
    if result['success']:
        hostname = result['result']
        print(f"✓ Current hostname: {hostname}")
        
        # Client might send this information to server
        client_info = {
            'machine_name': hostname,
            'type': 'client',
            'timestamp': 'now'
        }
        print(f"Client info to send: {client_info}")
    else:
        print(f"❌ Failed to get hostname: {result['error']}")


def example_server_usage():
    """Example of how server code can use subtasks"""
    print("\n=== Server Example ===")
    
    # Server might execute subtasks on behalf of clients
    subtask_name = 'get_hostname'
    
    # Check if subtask exists before executing
    subtask_func = get_subtask(subtask_name)
    if subtask_func:
        print(f"✓ Subtask '{subtask_name}' is available")
        
        # Execute subtask
        result = execute_subtask(subtask_name)
        
        if result['success']:
            print(f"✓ Server hostname: {result['result']}")
            
            # Server might store this in database or log
            server_record = {
                'subtask': subtask_name,
                'result': result['result'],
                'status': 'completed',
                'server': result['result']
            }
            print(f"Server record: {server_record}")
        else:
            print(f"❌ Subtask execution failed: {result['error']}")
    else:
        print(f"❌ Subtask '{subtask_name}' not found")


def example_task_execution():
    """Example of executing multiple subtasks as part of a task"""
    print("\n=== Task Execution Example ===")
    
    # Simulate a task that requires hostname information
    task_steps = ['get_hostname']  # Will add more subtasks later
    
    task_results = {}
    
    for step in task_steps:
        print(f"Executing step: {step}")
        result = execute_subtask(step)
        
        if result['success']:
            task_results[step] = result['result']
            print(f"  ✓ {step}: {result['result']}")
        else:
            task_results[step] = f"ERROR: {result['error']}"
            print(f"  ❌ {step}: {result['error']}")
    
    print(f"\nTask completed. Results: {task_results}")
    return task_results


if __name__ == '__main__':
    # Run all examples
    example_client_usage()
    example_server_usage()
    example_task_execution()
