"""
REST API interfaces
"""
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_socketio import emit

from common.models import Task, Client, TaskStatus, ClientStatus, SubtaskDefinition
from common.utils import parse_datetime, validate_cron_expression
from common.subtasks import list_subtasks, get_subtask, execute_subtask

logger = logging.getLogger(__name__)

def create_api_blueprint(database, socketio, result_collector=None):
    """Create API blueprint"""
    api = Blueprint('api', __name__)

    # Task ManagementAPI
    @api.route('/tasks', methods=['GET'])
    def get_tasks():
        """Get all tasks"""
        try:
            tasks = database.get_all_tasks()
            return jsonify({
                'success': True,
                'data': [task.to_dict() for task in tasks]
            })
        except Exception as e:
            logger.error(f"Get task listFailed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks', methods=['POST'])
    def create_task():
        """Create new task with support for subtasks and multiple clients"""
        try:
            data = request.get_json()

            # Validate required fields
            if not data.get('name'):
                return jsonify({
                    'success': False,
                    'error': 'Task name cannot be empty'
                }), 400

            # Parse subtasks
            subtasks_data = data.get('subtasks', [])
            subtasks = []

            if subtasks_data:
                # New subtask format
                for i, subtask_data in enumerate(subtasks_data):
                    # Validate subtask
                    if not subtask_data.get('name'):
                        return jsonify({
                            'success': False,
                            'error': f'Subtask {i+1}: name is required'
                        }), 400

                    if not subtask_data.get('target_client'):
                        return jsonify({
                            'success': False,
                            'error': f'Subtask {i+1}: target_client is required'
                        }), 400

                    # Check if subtask exists in registry
                    if not get_subtask(subtask_data['name']):
                        return jsonify({
                            'success': False,
                            'error': f'Subtask {i+1}: "{subtask_data["name"]}" is not a valid subtask. Available subtasks: {list_subtasks()}'
                        }), 400

                    subtask = SubtaskDefinition(
                        name=subtask_data['name'],
                        target_client=subtask_data['target_client'],
                        order=subtask_data.get('order', i),
                        args=subtask_data.get('args', []),
                        kwargs=subtask_data.get('kwargs', {}),
                        timeout=subtask_data.get('timeout', 300),
                        retry_count=0,
                        max_retries=3  # Default value, not configurable from UI
                    )
                    subtasks.append(subtask)

                # Sort subtasks by order
                subtasks.sort(key=lambda x: x.order)

            else:
                # Legacy format support: convert commands to subtasks if no subtasks provided
                commands = data.get('commands', [])
                execution_order = data.get('execution_order', [])

                # 向后兼容：如果没有指定commands但有command，创建默认格式
                if not commands and data.get('command'):
                    commands = [{
                        'id': 1,
                        'name': 'Default Command',
                        'command': data.get('command'),
                        'timeout': 300,
                        'retry_count': 0
                    }]
                    execution_order = [1]

                # 验证至少有一个指令或subtask
                if not commands and not subtasks:
                    return jsonify({
                        'success': False,
                        'error': 'At least one command or subtask must be specified'
                    }), 400

                # 验证执行顺序（仅对legacy commands）
                if execution_order and commands:
                    command_ids = {cmd['id'] for cmd in commands}
                    for order_id in execution_order:
                        if order_id not in command_ids:
                            return jsonify({
                                'success': False,
                                'error': f'Execution order contains invalid command ID: {order_id}'
                            }), 400
                else:
                    # 如果没有指定执行顺序，按照command的id顺序执行
                    execution_order = [cmd['id'] for cmd in commands] if commands else []

            # Validate cron expression
            cron_expr = data.get('cron_expression')
            if cron_expr and not validate_cron_expression(cron_expr):
                return jsonify({
                    'success': False,
                    'error': 'Invalid cron expression format'
                }), 400

            # 处理目标机器列表（可能来自legacy字段或subtasks）
            target_clients = data.get('target_clients', [])
            if not target_clients and data.get('target_client'):
                target_clients = [data.get('target_client')]

            # 如果使用subtasks，从subtasks中提取所有目标机器
            if subtasks:
                subtask_clients = list(set(s.target_client for s in subtasks))
                target_clients.extend(subtask_clients)
                target_clients = list(set(target_clients))  # Remove duplicates

            # Create task object
            task = Task(
                name=data['name'],
                command=data.get('command', ''),  # 保持向后兼容
                target_clients=target_clients,
                commands=data.get('commands', []),
                execution_order=data.get('execution_order', []),
                subtasks=subtasks,
                schedule_time=parse_datetime(data.get('schedule_time')),
                cron_expression=cron_expr,
                target_client=data.get('target_client'),  # 保持向后兼容
                max_retries=3,  # Default value, not configurable from UI
                send_email=data.get('send_email', False),
                email_recipients=data.get('email_recipients')
            )

            # Save to database
            task_id = database.create_task(task)
            task.id = task_id

            # Broadcast new task creation event
            socketio.emit('task_created', task.to_dict())

            if subtasks:
                logger.info(f"Created task: {task.name} with {len(subtasks)} subtasks for {len(target_clients)} clients")
            else:
                logger.info(f"Created task: {task.name} with {len(task.commands)} commands for {len(target_clients)} clients")

            return jsonify({
                'success': True,
                'data': task.to_dict()
            }), 201

        except Exception as e:
            logger.error(f"Create Task Failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>', methods=['GET'])
    def get_task(task_id):
        """Get specified task"""
        try:
            task = database.get_task(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            return jsonify({
                'success': True,
                'data': task.to_dict()
            })
        except Exception as e:
            logger.error(f"Failed to get task: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>', methods=['PUT'])
    def update_task(task_id):
        """Update task"""
        try:
            task = database.get_task(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            data = request.get_json()

            # Update task fields
            if 'name' in data:
                task.name = data['name']
            if 'command' in data:
                task.command = data['command']
            if 'target_clients' in data:
                task.target_clients = data['target_clients']
            if 'commands' in data:
                task.commands = data['commands']
            if 'execution_order' in data:
                task.execution_order = data['execution_order']
            if 'schedule_time' in data:
                task.schedule_time = parse_datetime(data['schedule_time'])
            if 'cron_expression' in data:
                cron_expr = data['cron_expression']
                if cron_expr and not validate_cron_expression(cron_expr):
                    return jsonify({
                        'success': False,
                        'error': 'Invalid cron expression format'
                    }), 400
                task.cron_expression = cron_expr
            if 'target_client' in data:
                task.target_client = data['target_client']
            if 'max_retries' in data:
                task.max_retries = data['max_retries']
            if 'send_email' in data:
                task.send_email = data['send_email']
            if 'email_recipients' in data:
                task.email_recipients = data['email_recipients']

            # Save update
            database.update_task(task)

            # Broadcast task update event
            socketio.emit('task_updated', task.to_dict())

            return jsonify({
                'success': True,
                'data': task.to_dict()
            })

        except Exception as e:
            logger.error(f"Update taskFailed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>', methods=['DELETE'])
    def delete_task(task_id):
        """Delete task and all related execution records"""
        try:
            task = database.get_task(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            # Check if task is currently running
            if task.status in [TaskStatus.RUNNING]:
                return jsonify({
                    'success': False,
                    'error': f'Cannot delete task while it is {task.status.value}. Please cancel the task first.'
                }), 400

            success = database.delete_task(task_id)
            
            if success:
                # Note: WebSocket emission is now handled in the database method
                return jsonify({
                    'success': True,
                    'message': f'Task "{task.name}" deleted successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Task could not be deleted'
                }), 500

        except Exception as e:
            logger.error(f"Delete task failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>/cancel', methods=['POST'])
    def cancel_task(task_id):
        """Cancel task execution"""
        try:
            task = database.get_task(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            # 只能取消正在运行或待执行的任务
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return jsonify({
                    'success': False,
                    'error': f'Cannot cancel task with status: {task.status.value}'
                }), 400

            # 更新任务状态为已取消
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            task.error_message = "Task cancelled by user"
            database.update_task(task)

            # 广播任务取消事件
            socketio.emit('task_cancelled', {
                'task_id': task_id,
                'cancelled_at': task.completed_at.isoformat()
            })

            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Cancel taskFailed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>/subtasks/<subtask_name>/delete', methods=['DELETE'])
    def delete_subtask(task_id, subtask_name):
        """Delete a specific subtask that hasn't started execution yet"""
        try:
            data = request.get_json() or {}
            target_client = data.get('target_client')
            
            if not target_client:
                return jsonify({
                    'success': False,
                    'error': 'target_client parameter is required'
                }), 400

            # Get the task
            task = database.get_task(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            # Check if task is in a state where subtasks can be deleted
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return jsonify({
                    'success': False,
                    'error': f'Cannot delete subtasks from task with status: {task.status.value}'
                }), 400

            # Find the subtask to delete
            subtask_to_delete = None
            for subtask in task.subtasks:
                if subtask.name == subtask_name and subtask.target_client == target_client:
                    subtask_to_delete = subtask
                    break

            if not subtask_to_delete:
                return jsonify({
                    'success': False,
                    'error': f'Subtask "{subtask_name}" for client "{target_client}" not found in task'
                }), 404

            # Check if subtask has already started execution
            executions = database.get_subtask_executions_by_client(task_id, target_client)
            for execution in executions:
                if (execution.subtask_name == subtask_name and 
                    execution.status in [TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.FAILED]):
                    return jsonify({
                        'success': False,
                        'error': f'Cannot delete subtask "{subtask_name}" - it has already started execution (status: {execution.status.value})'
                    }), 400

            # Remove the subtask from the task
            task.subtasks = [s for s in task.subtasks 
                           if not (s.name == subtask_name and s.target_client == target_client)]
            
            # Update target_clients list if no more subtasks target this client
            remaining_clients = set(s.target_client for s in task.subtasks)
            task.target_clients = [m for m in task.target_clients if m in remaining_clients]

            # If no subtasks remain, set task status to cancelled
            if not task.subtasks:
                task.status = TaskStatus.CANCELLED
                task.error_message = "All subtasks were deleted"
                task.completed_at = datetime.now()

            # Update the task in database
            database.update_task(task)

            # Remove any pending subtask execution records for this subtask
            database.delete_pending_subtask_executions(task_id, subtask_name, target_client)

            logger.info(f"SUBTASK_DELETION: Deleted subtask '{subtask_name}' from task {task_id} for client '{target_client}'")

            # Broadcast subtask deletion event
            socketio.emit('subtask_deleted', {
                'task_id': task_id,
                'subtask_name': subtask_name,
                'target_client': target_client,
                'deleted_at': datetime.now().isoformat(),
                'remaining_subtasks': len(task.subtasks)
            })

            return jsonify({
                'success': True,
                'message': f'Subtask "{subtask_name}" deleted successfully',
                'remaining_subtasks': len(task.subtasks),
                'task_status': task.status.value
            })

        except Exception as e:
            logger.error(f"Delete subtask failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>/executions', methods=['GET'])
    def get_task_executions(task_id):
        """Get task execution records"""
        try:
            executions = database.get_task_executions(task_id)
            return jsonify({
                'success': True,
                'data': [exec.to_dict() for exec in executions]
            })
        except Exception as e:
            logger.error(f"Get task execution recordsFailed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>/subtask-executions', methods=['GET'])
    def get_subtask_executions(task_id):
        """Get subtask execution records for a task"""
        try:
            executions = database.get_subtask_executions(task_id)
            return jsonify({
                'success': True,
                'data': [exec.to_dict() for exec in executions]
            })
        except Exception as e:
            logger.error(f"Get subtask execution records failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>/subtask-executions/<client_name>', methods=['GET'])
    def get_subtask_executions_by_client(task_id, client_name):
        """Get subtask execution records for a specific task and client"""
        try:
            executions = database.get_subtask_executions_by_client(task_id, client_name)
            return jsonify({
                'success': True,
                'data': [exec.to_dict() for exec in executions]
            })
        except Exception as e:
            logger.error(f"Get subtask execution records by client failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>/subtask-executions', methods=['POST'])
    def update_subtask_execution(task_id):
        """Update subtask execution status (called by client)"""
        try:
            data = request.get_json()
            
            # Enhanced logging for subtask execution status
            subtask_name = data.get('subtask_name')
            target_client = data.get('target_client')
            status = data.get('status')
            execution_time = data.get('execution_time')
            result = data.get('result')
            error_message = data.get('error_message')
            
            logger.info(f"SUBTASK_EXECUTION: Task {task_id} - '{subtask_name}' on '{target_client}' - Status: {status}")
            if execution_time:
                logger.info(f"SUBTASK_EXECUTION: Task {task_id} - '{subtask_name}' execution time: {execution_time}s")
            if result:
                logger.debug(f"SUBTASK_EXECUTION: Task {task_id} - '{subtask_name}' result: {result[:200]}{'...' if len(str(result)) > 200 else ''}")
            if error_message:
                logger.warning(f"SUBTASK_EXECUTION: Task {task_id} - '{subtask_name}' error: {error_message}")

            # Validate required fields
            required_fields = ['subtask_name', 'target_client', 'status']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }), 400

            # Find or create subtask execution record
            executions = database.get_subtask_executions_by_client(task_id, data['target_client'])
            execution = None

            for exec in executions:
                if exec.subtask_name == data['subtask_name'] and exec.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    execution = exec
                    break

            if not execution:
                # Create new execution record
                from common.models import SubtaskExecution
                
                # Find the subtask definition to get the subtask_id
                task = database.get_task(task_id)
                subtask_id = None
                if task and task.subtasks:
                    for subtask_def in task.subtasks:
                        if (subtask_def.name == data['subtask_name'] and 
                            subtask_def.target_client == data['target_client']):
                            subtask_id = subtask_def.subtask_id
                            break
                
                execution = SubtaskExecution(
                    task_id=task_id,
                    subtask_id=subtask_id or f"{data.get('order', 0)}_{data['subtask_name']}",  # Fallback ID
                    subtask_name=data['subtask_name'],
                    subtask_order=data.get('order', 0),
                    target_client=data['target_client'],
                    status=TaskStatus(data['status'])
                )
                execution.id = database.create_subtask_execution(execution)
                logger.info(f"SUBTASK_EXECUTION: Created new execution record for Task {task_id} - '{subtask_name}' on '{target_client}'")

            # Update execution status
            execution.status = TaskStatus(data['status'])
            execution.result = data.get('result')
            execution.error_message = data.get('error_message')
            execution.execution_time = data.get('execution_time')

            if data['status'] in ['completed', 'failed']:
                execution.completed_at = datetime.now()
                logger.info(f"SUBTASK_EXECUTION: Task {task_id} - '{subtask_name}' on '{target_client}' completed at {execution.completed_at.isoformat()}")

            database.update_subtask_execution(execution)

            # Update client's current subtask status
            if data['status'] == 'running':
                # Client started working on this subtask
                # Find the subtask definition to get the subtask_id
                task = database.get_task(task_id)
                if task and task.subtasks:
                    for subtask_def in task.subtasks:
                        if (subtask_def.name == data['subtask_name'] and 
                            subtask_def.target_client == data['target_client']):
                            database.update_client_current_task(
                                data['target_client'], 
                                task_id, 
                                subtask_def.subtask_id
                            )
                            break
            elif data['status'] in ['completed', 'failed']:
                # Client finished this subtask, check if there are more subtasks for this client
                task = database.get_task(task_id)
                if task and task.subtasks:
                    remaining_subtasks = [
                        s for s in task.subtasks 
                        if (s.target_client == data['target_client'] and 
                            s.order > data.get('order', 0))
                    ]
                    if remaining_subtasks:
                        # Move to next subtask
                        next_subtask = min(remaining_subtasks, key=lambda x: x.order)
                        database.update_client_current_task(
                            data['target_client'], 
                            task_id, 
                            next_subtask.subtask_id
                        )
                    else:
                        # No more subtasks, clear current task
                        database.update_client_current_task(data['target_client'], None, None)
                        # Set client back to online
                        database.update_client_heartbeat_by_name(data['target_client'], ClientStatus.ONLINE)

            # Check if all subtasks are completed and update overall task status
            logger.debug(f"SUBTASK_EXECUTION: Checking task completion for task {task_id}")
            
            # Notify result collector about subtask completion
            if result_collector and data['status'] in ['completed', 'failed']:
                result_collector.on_subtask_completion(
                    task_id=task_id,
                    client_name=data['target_client'],
                    subtask_name=data['subtask_name'],
                    subtask_status=TaskStatus(data['status']),
                    result=data.get('result'),
                    error_message=data.get('error_message'),
                    execution_time=data.get('execution_time')
                )
            else:
                # Fallback to original completion check
                check_and_update_task_completion(task_id)
            
            logger.info(f"DEBUG: Finished processing subtask completion for task {task_id}")

            # Broadcast subtask status update
            socketio.emit('subtask_updated', {
                'task_id': task_id,
                'subtask_name': data['subtask_name'],
                'target_client': data['target_client'],
                'status': data['status'],
                'result': data.get('result'),
                'error_message': data.get('error_message'),
                'execution_time': data.get('execution_time')
            })

            return jsonify({
                'success': True,
                'data': execution.to_dict()
            })

        except Exception as e:
            logger.error(f"Update subtask execution failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # Subtasks API
    @api.route('/subtasks', methods=['GET'])
    def get_available_subtasks():
        """Get all available subtasks"""
        try:
            subtasks = list_subtasks()
            subtask_info = []
            
            for subtask_name in subtasks:
                subtask_func = get_subtask(subtask_name)
                if subtask_func:
                    # Get docstring for description
                    description = subtask_func.__doc__ or "No description available"
                    subtask_info.append({
                        'name': subtask_name,
                        'description': description.strip(),
                        'function': subtask_func.__name__
                    })
            
            return jsonify({
                'success': True,
                'data': subtask_info,
                'count': len(subtask_info)
            })
        except Exception as e:
            logger.error(f"Get available subtasks failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/subtasks/<string:subtask_name>/execute', methods=['POST'])
    def execute_subtask_api(subtask_name):
        """Execute a specific subtask"""
        try:
            # Get any parameters from request body
            data = request.get_json() or {}
            args = data.get('args', [])
            kwargs = data.get('kwargs', {})
            
            # Execute the subtask
            result = execute_subtask(subtask_name, *args, **kwargs)
            
            return jsonify({
                'success': result['success'],
                'data': result['result'],
                'error': result['error']
            })
        except Exception as e:
            logger.error(f"Execute subtask {subtask_name} failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/subtasks/<string:subtask_name>/info', methods=['GET'])
    def get_subtask_info(subtask_name):
        """Get information about a specific subtask"""
        try:
            subtask_func = get_subtask(subtask_name)
            if not subtask_func:
                return jsonify({
                    'success': False,
                    'error': f'Subtask "{subtask_name}" not found'
                }), 404

            # Get detailed information about the subtask
            info = {
                'name': subtask_name,
                'function': subtask_func.__name__,
                'description': subtask_func.__doc__ or "No description available",
                'module': subtask_func.__module__,
            }
            
            # Try to get function signature if available
            try:
                import inspect
                sig = inspect.signature(subtask_func)
                info['parameters'] = {
                    'signature': str(sig),
                    'parameters': [
                        {
                            'name': param.name,
                            'default': str(param.default) if param.default != inspect.Parameter.empty else None,
                            'annotation': str(param.annotation) if param.annotation != inspect.Parameter.empty else None
                        }
                        for param in sig.parameters.values()
                    ]
                }
            except Exception:
                info['parameters'] = 'Unable to determine parameters'

            return jsonify({
                'success': True,
                'data': info
            })
        except Exception as e:
            logger.error(f"Get subtask info for {subtask_name} failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/subtasks/<subtask_name>/test', methods=['POST'])
    def test_subtask(subtask_name):
        """Test a subtask execution (for debugging)"""
        try:
            from common.subtasks import execute_subtask

            # Get args and kwargs from request
            data = request.get_json() or {}
            args = data.get('args', [])
            kwargs = data.get('kwargs', {})

            # Execute subtask
            result = execute_subtask(subtask_name, *args, **kwargs)

            return jsonify({
                'success': True,
                'data': result
            })
        except Exception as e:
            logger.error(f"Test subtask {subtask_name} failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # Client Management API
    @api.route('/clients', methods=['GET'])
    def get_clients():
        """Get all clients"""
        try:
            clients = database.get_all_clients()
            return jsonify({
                'success': True,
                'data': [client.to_dict() for client in clients]
            })
        except Exception as e:
            logger.error(f"Get client list failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/clients/register', methods=['POST'])
    def register_client():
        """Register clients with system information (using client name as primary identifier)"""
        try:
            data = request.get_json()

            if not data.get('name') or not data.get('ip_address'):
                return jsonify({
                    'success': False,
                    'error': 'Client name and IP address cannot be empty'
                }), 400

            # Check if client with same name or IP already exists
            existing_client_by_name = database.get_client_by_name(data['name'])
            existing_client_by_ip = database.get_client_by_ip(data['ip_address'])

            # If client exists with same name but different IP, return error
            if existing_client_by_name and existing_client_by_name.ip_address != data['ip_address']:
                return jsonify({
                    'success': False,
                    'error': f'Client name "{data["name"]}" already exists with different IP address'
                }), 400

            # Use existing client record (if exists) or create new record
            existing_client = existing_client_by_name or existing_client_by_ip

            client = Client(
                name=data['name'],
                ip_address=data['ip_address'],
                port=data.get('port', 8080),
                status=ClientStatus.ONLINE,
                # System information
                cpu_info=data.get('cpu_info'),
                memory_info=data.get('memory_info'),
                gpu_info=data.get('gpu_info'),
                os_info=data.get('os_info'),
                disk_info=data.get('disk_info'),
                system_summary=data.get('system_summary')
            )

            database.register_client(client)

            # Log client registration
            client_ip = request.environ.get('REMOTE_ADDR', data['ip_address'])
            if existing_client:
                database.log_client_action(
                    client_ip=client.ip_address,
                    client_name=client.name,
                    action='CLIENT_UPDATE',
                    message=f"Client {client.name} updated registration",
                    data={
                        'system_summary': client.system_summary
                    }
                )
            else:
                database.log_client_action(
                    client_ip=client.ip_address,
                    client_name=client.name,
                    action='CLIENT_REGISTER',
                    message=f"New client {client.name} registered",
                    data={
                        'system_summary': client.system_summary
                    }
                )

            # Enhanced logging for client registration
            if existing_client:
                logger.info(f"CLIENT_REGISTRATION: Updated existing client '{client.name}' ({client.ip_address})")
            else:
                logger.info(f"CLIENT_REGISTRATION: New client '{client.name}' registered from {client.ip_address}")
            
            # Log system information
            if client.system_summary:
                logger.info(f"CLIENT_REGISTRATION: Client '{client.name}' system info:")
                logger.info(f"  CPU: {client.system_summary.get('cpu', 'Unknown')}")
                logger.info(f"  Memory: {client.system_summary.get('memory', 'Unknown')}")
                logger.info(f"  GPU: {client.system_summary.get('gpu', 'Unknown')}")
                logger.info(f"  OS: {client.system_summary.get('os', 'Unknown')}")

            # Broadcast client registration event
            socketio.emit('client_registered', client.to_dict())

            return jsonify({
                'success': True,
                'data': client.to_dict()
            }), 201

        except Exception as e:
            logger.error(f"Register client failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/clients/update_config', methods=['POST'])
    def update_client_config():
        """Update client configuration information"""
        try:
            data = request.get_json()
            client_name = data.get('name')
            ip_address = data.get('ip_address')

            # Prioritize client name, fallback to IP address for backward compatibility
            if client_name:
                existing_client = database.get_client_by_name(client_name)
                if not existing_client:
                    return jsonify({
                        'success': False,
                        'error': f'Client "{client_name}" not found'
                    }), 404
            elif ip_address:
                existing_client = database.get_client_by_ip(ip_address)
                if not existing_client:
                    return jsonify({
                        'success': False,
                        'error': 'Client not found'
                    }), 404
            else:
                return jsonify({
                    'success': False,
                    'error': 'Client name or IP address is required'
                }), 400

            # Update client information
            client = Client(
                name=data.get('name', existing_client.name),
                ip_address=data.get('ip_address', existing_client.ip_address),
                port=data.get('port', existing_client.port),
                status=existing_client.status,  # Keep existing status
                # Update system information
                cpu_info=data.get('cpu_info'),
                memory_info=data.get('memory_info'),
                gpu_info=data.get('gpu_info'),
                os_info=data.get('os_info'),
                disk_info=data.get('disk_info'),
                system_summary=data.get('system_summary')
            )

            database.update_client_config(client)

            # Log updated system information
            if client.system_summary:
                logger.info(f"Updated client config for {client.name} ({client.ip_address}):")
                logger.info(f"  CPU: {client.system_summary.get('cpu', 'Unknown')}")
                logger.info(f"  Memory: {client.system_summary.get('memory', 'Unknown')}")
                logger.info(f"  GPU: {client.system_summary.get('gpu', 'Unknown')}")
                logger.info(f"  OS: {client.system_summary.get('os', 'Unknown')}")

            # Broadcast client update event
            socketio.emit('client_config_updated', client.to_dict())

            return jsonify({
                'success': True,
                'data': client.to_dict()
            })

        except Exception as e:
            logger.error(f"Update client config failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/clients/unregister', methods=['POST'])
    def unregister_client():
        """Unregister client using client name as primary identifier"""
        try:
            data = request.get_json()
            client_name = data.get('name')
            ip_address = data.get('ip_address')  # Backward compatibility

            # Prioritize client name, fallback to IP if not provided
            if client_name:
                # Unregister by client name
                database.update_client_heartbeat_by_name(client_name, ClientStatus.OFFLINE)

                # Get client information for broadcast
                client = database.get_client_by_name(client_name)
                actual_ip = client.ip_address if client else (ip_address or 'unknown')
            elif ip_address:
                # Backward compatibility: unregister by IP
                database.update_client_heartbeat(ip_address, ClientStatus.OFFLINE)
                actual_ip = ip_address
                client_name = data.get('name', 'Unknown')
            else:
                return jsonify({
                    'success': False,
                    'error': 'Client name or IP address is required'
                }), 400

            # Broadcast client unregistration event
            socketio.emit('client_unregistered', {
                'ip_address': actual_ip,
                'client_name': client_name,
                'status': 'offline',
                'timestamp': datetime.now().isoformat()
            })

            logger.info(f"Client unregistered: {client_name} ({actual_ip})")

            return jsonify({
                'success': True,
                'message': f'Client {client_name} unregistered successfully'
            })

        except Exception as e:
            logger.error(f"Unregister client failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/clients/heartbeat', methods=['POST'])
    def client_heartbeat():
        """Client heartbeat using client name as primary identifier"""
        try:
            data = request.get_json()
            client_name = data.get('client_name')
            status = data.get('status', 'online')

            if not client_name:
                return jsonify({
                    'success': False,
                    'error': 'Client name cannot be empty'
                }), 400

            # Update heartbeat using client name
            client_status = ClientStatus(status) if status else ClientStatus.ONLINE
            database.update_client_heartbeat_by_name(client_name, client_status)

            # Get client info for broadcast (optional)
            client = database.get_client_by_name(client_name)
            ip_address = client.ip_address if client else 'unknown'

            # Enhanced logging for heartbeat
            logger.info(f"HEARTBEAT: Client '{client_name}' ({ip_address}) heartbeat - Status: {status}")
            if client:
                logger.debug(f"HEARTBEAT: Client '{client_name}' last seen at {datetime.now().isoformat()}")

            # Broadcast heartbeat event
            socketio.emit('client_heartbeat', {
                'ip_address': ip_address,
                'client_name': client_name,
                'status': status,
                'timestamp': datetime.now().isoformat()
            })

            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Update heartbeat failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # Task execution API
    @api.route('/execute', methods=['POST'])
    def execute_task():
        """Receive task execution request"""
        try:
            data = request.get_json()
            task_id = data.get('task_id')
            client_name = data.get('client_name')  # Using client name as primary identifier
            client_ip = data.get('client_ip')  # IP as auxiliary information

            if not task_id or not client_name:
                return jsonify({
                    'success': False,
                    'error': 'Task ID and client name cannot be empty'
                }), 400

            # Get task
            task = database.get_task(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            # Get client info by name
            client = database.get_client_by_name(client_name)
            if not client:
                return jsonify({
                    'success': False,
                    'error': f'Client "{client_name}" not found'
                }), 404

            # Use client's IP if not provided
            if not client_ip:
                client_ip = client.ip_address

            # Update task status to running
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            database.update_task(task)

            # Enhanced logging for task scheduling to client
            logger.info(f"TASK_SCHEDULING: Task {task_id} '{task.name}' scheduled to client '{client_name}' ({client_ip})")
            logger.info(f"TASK_SCHEDULING: Task details - Subtasks: {len(task.subtasks) if task.subtasks else 0}, Status: {task.status.value}")
            if task.subtasks:
                for i, subtask in enumerate(task.subtasks):
                    logger.debug(f"TASK_SCHEDULING: Task {task_id} Subtask {i+1}: '{subtask.name}' -> '{subtask.target_client}'")

            # Broadcast task start execution event
            socketio.emit('task_started', {
                'task_id': task_id,
                'client_ip': client_ip,
                'client_name': client_name,
                'started_at': task.started_at.isoformat()
            })

            return jsonify({
                'success': True,
                'task': task.to_dict()
            })

        except Exception as e:
            logger.error(f"Execute taskFailed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/result', methods=['POST'])
    def submit_result():
        """Receive task execution result"""
        try:
            data = request.get_json()
            task_id = data.get('task_id')
            client_name = data.get('client_name')  # 使用机器名作为主要标识
            client_ip = data.get('client_ip', 'Unknown')  # IP作为辅助信息

            # Support both old and new result formats
            if 'subtask_results' in data:
                # New format with subtask results
                result_data = data
                success = result_data.get('success', False)
                subtask_results = result_data.get('subtask_results', [])
                total_subtasks = result_data.get('total_subtasks', 0)
                successful_subtasks = result_data.get('successful_subtasks', 0)
                failed_subtasks = result_data.get('failed_subtasks', 0)
                error = result_data.get('error', '')
                exit_code = result_data.get('exit_code', 0)

                # Generate summary output from subtask results
                output_parts = []
                if subtask_results:
                    output_parts.append(f"Task completed with {total_subtasks} subtasks: {successful_subtasks} successful, {failed_subtasks} failed\n")
                    for subtask in subtask_results:
                        output_parts.append(f"[Subtask {subtask.get('subtask_id')}: {subtask.get('subtask_name')}]")
                        output_parts.append(f"Success: {subtask.get('success')}")
                        if subtask.get('output'):
                            output_parts.append(f"Output: {subtask.get('output')}")
                        if subtask.get('error'):
                            output_parts.append(f"Error: {subtask.get('error')}")
                        output_parts.append("")

                output = '\n'.join(output_parts)
            else:
                # Old format for backward compatibility
                success = data.get('success', False)
                output = data.get('output', '')
                error = data.get('error', '')
                exit_code = data.get('exit_code', 0)

            if not task_id:
                return jsonify({
                    'success': False,
                    'error': 'Task ID cannot be empty'
                }), 400

            # Get task
            task = database.get_task(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            # Update taskStatus
            task.completed_at = datetime.now()
            if success:
                task.status = TaskStatus.COMPLETED
                task.result = output
            else:
                task.status = TaskStatus.FAILED
                task.error_message = error

            database.update_task(task)

            # Broadcast task completion event
            socketio.emit('task_completed', {
                'task_id': task_id,
                'client_ip': client_ip,
                'client_name': client_name,
                'success': success,
                'completed_at': task.completed_at.isoformat(),
                'output': output,
                'error': error
            })

            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Failed to submit result: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/subtask_result', methods=['POST'])
    def submit_subtask_result():
        """Receive subtask execution result"""
        try:
            data = request.get_json()
            task_id = data.get('task_id')
            client_name = data.get('client_name')  # 使用机器名作为主要标识
            client_ip = data.get('client_ip', 'Unknown')  # IP作为辅助信息
            subtask_result = data.get('subtask_result', {})

            if not task_id:
                return jsonify({
                    'success': False,
                    'error': 'Task ID cannot be empty'
                }), 400

            if not subtask_result:
                return jsonify({
                    'success': False,
                    'error': 'Subtask result cannot be empty'
                }), 400

            # Get task to verify it exists
            task = database.get_task(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            # Broadcast subtask completion event to connected clients
            socketio.emit('subtask_completed', {
                'task_id': task_id,
                'client_ip': client_ip,
                'client_name': client_name,
                'subtask_result': subtask_result
            })

            logger.info(f"Received subtask result for task {task_id}, subtask {subtask_result.get('subtask_id')}")

            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Failed to submit subtask result: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # Report Generation and Email Notification API
    @api.route('/tasks/<int:task_id>/generate-report', methods=['POST'])
    def generate_task_report(task_id):
        """Generate HTML report for a specific task"""
        try:
            if not result_collector:
                return jsonify({
                    'success': False, 
                    'error': 'Result collector not available'
                }), 503
            
            force = request.args.get('force', 'false').lower() == 'true'
            report_path = result_collector.generate_report_for_task(task_id, force=force)
            
            if report_path:
                return jsonify({
                    'success': True,
                    'report_path': report_path,
                    'message': 'Report generated successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to generate report'
                }), 500
                
        except Exception as e:
            logger.error(f"Generate task report failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>/send-notification', methods=['POST'])
    def send_task_notification(task_id):
        """Send email notification for a specific task"""
        try:
            if not result_collector:
                return jsonify({
                    'success': False, 
                    'error': 'Result collector not available'
                }), 503
            
            success = result_collector.send_manual_notification(task_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Email notification sent successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to send email notification'
                }), 500
                
        except Exception as e:
            logger.error(f"Send task notification failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/subtasks/definitions', methods=['GET'])
    def get_subtask_definitions():
        """Get subtask definitions with result specifications"""
        try:
            from common.subtasks import list_subtasks_with_definitions, get_subtask_result_definition
            
            definitions = list_subtasks_with_definitions()
            
            # Add result definitions to the response
            result = {}
            for name, info in definitions.items():
                result_def = get_subtask_result_definition(name)
                result[name] = {
                    'description': info['function'],
                    'result_definition': {
                        'name': result_def.name,
                        'description': result_def.description,
                        'result_type': result_def.result_type,
                        'required_fields': result_def.required_fields,
                        'is_critical': result_def.is_critical,
                        'format_hint': result_def.format_hint
                    } if result_def else None
                }
            
            return jsonify({
                'success': True,
                'data': result
            })
            
        except Exception as e:
            logger.error(f"Get subtask definitions failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # Client Communication Logs API
    @api.route('/logs', methods=['GET'])
    def get_client_logs():
        """Get client communication logs"""
        try:
            limit = int(request.args.get('limit', 100))
            client_ip = request.args.get('client_ip')

            logs = database.get_client_logs(limit=limit, client_ip=client_ip)

            return jsonify({
                'success': True,
                'data': logs
            })

        except Exception as e:
            logger.error(f"Failed to get client logs: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/logs/clear', methods=['POST'])
    def clear_client_logs():
        """Clear client logs before a specified date"""
        try:
            data = request.get_json()
            
            if 'clear_before_date' in data:
                # Clear logs before specific date
                clear_date = data['clear_before_date']
                
                # Validate date format
                try:
                    from datetime import datetime
                    datetime.strptime(clear_date, '%Y-%m-%d')
                except ValueError:
                    return jsonify({
                        'success': False, 
                        'error': 'Invalid date format. Use YYYY-MM-DD.'
                    }), 400
                
                # Clear logs directly with SQL
                with database.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        DELETE FROM client_logs
                        WHERE date(timestamp) < date(?)
                    ''', (clear_date,))
                    deleted_count = cursor.rowcount
                    conn.commit()
                
                message = f"Cleared {deleted_count} log entries before {clear_date}"
                
            elif 'older_than_days' in data:
                # Legacy support for older_than_days
                days = int(data['older_than_days'])
                deleted_count = database.clear_client_logs(older_than_days=days)
                message = f"Cleared {deleted_count} log entries older than {days} days"
                
            else:
                return jsonify({
                    'success': False,
                    'error': 'Either clear_before_date or older_than_days must be specified'
                }), 400

            return jsonify({
                'success': True,
                'message': message,
                'deleted_count': deleted_count
            })

        except Exception as e:
            logger.error(f"Failed to clear client logs: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/clients/<client_name>', methods=['GET'])
    def get_client_by_name(client_name):
        """Get client by name (primary method)"""
        try:
            client = database.get_client_by_name(client_name)
            if not client:
                return jsonify({
                    'success': False,
                    'error': f'Client "{client_name}" not found'
                }), 404

            return jsonify({
                'success': True,
                'data': client.to_dict()
            })
        except Exception as e:
            logger.error(f"Get client by name failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/clients/<client_name>', methods=['DELETE'])
    def delete_client_by_name(client_name):
        """Delete client by name (primary method - client names are unique)"""
        try:
            # Get client details before deleting
            client = database.get_client_by_name(client_name)
            if not client:
                return jsonify({
                    'success': False,
                    'error': f'Client "{client_name}" not found'
                }), 404

            # Notify the specific client that it's being unregistered
            room_name = f"client_{client.ip_address.replace('.', '_')}"
            socketio.emit('client_unregistered', {
                'client_name': client_name,
                'reason': 'Client unregistered by administrator',
                'timestamp': datetime.now().isoformat()
            }, room=room_name)

            # Delete the client from database
            success = database.delete_client(client_name)
            if not success:
                return jsonify({
                    'success': False,
                    'error': f'Failed to delete client "{client_name}"'
                }), 500

            # Broadcast general client deletion event for UI updates
            socketio.emit('client_deleted', {
                'client_name': client_name,
                'deleted_at': datetime.now().isoformat()
            })

            logger.info(f"Client unregistered and notified: {client_name} ({client.ip_address})")

            return jsonify({
                'success': True,
                'message': f'Client "{client_name}" deleted successfully'
            })

        except Exception as e:
            logger.error(f"Delete client by name failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/clients/names', methods=['GET'])
    def get_client_names():
        """Get all client names"""
        try:
            # Check if only online clients are requested
            only_online = request.args.get('online', '').lower() == 'true'
            
            if only_online:
                client_names = database.get_online_client_names()
            else:
                client_names = database.get_client_names()
            
            return jsonify({
                'success': True,
                'data': client_names
            })
        except Exception as e:
            logger.error(f"Get client names failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/clients/validate_name', methods=['POST'])
    def validate_client_name():
        """Validate if client name is available"""
        try:
            data = request.get_json()
            client_name = data.get('name')
            
            if not client_name:
                return jsonify({
                    'success': False,
                    'error': 'Client name is required'
                }), 400
            
            # Check if name already exists
            exists = database.client_name_exists(client_name)
            
            return jsonify({
                'success': True,
                'data': {
                    'name': client_name,
                    'available': not exists,
                    'exists': exists
                }
            })
            
        except Exception as e:
            logger.error(f"Validate client name failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    def check_and_update_task_completion(task_id):
        """
        Check if all subtasks are completed and update overall task status
        
        Args:
            task_id: ID of the task to check
        """
        try:
            # Get task and its subtasks
            task = database.get_task(task_id)
            if not task or not task.subtasks:
                logger.warning(f"TASK_COMPLETION: Task {task_id} not found or has no subtasks")
                return
            
            # Get all subtask executions for this task
            executions = database.get_subtask_executions(task_id)
            logger.debug(f"TASK_COMPLETION: Found {len(executions)} subtask executions for task {task_id}")
            
            # Create a map of executed subtasks
            execution_map = {}
            for exec in executions:
                key = f"{exec.subtask_name}_{exec.target_client}"
                execution_map[key] = exec
            
            # Check completion status
            total_subtasks = len(task.subtasks)
            completed_subtasks = 0
            failed_subtasks = 0
            
            for subtask in task.subtasks:
                key = f"{subtask.name}_{subtask.target_client}"
                execution = execution_map.get(key)
                
                if execution:
                    if execution.status == TaskStatus.COMPLETED:
                        completed_subtasks += 1
                    elif execution.status == TaskStatus.FAILED:
                        failed_subtasks += 1
            
            # Determine if task is complete
            all_subtasks_finished = (completed_subtasks + failed_subtasks) == total_subtasks
            
            logger.info(f"TASK_COMPLETION: Task {task_id} '{task.name}' - Progress: {completed_subtasks}/{total_subtasks} completed, {failed_subtasks} failed")
            
            if all_subtasks_finished and task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                # Update task status
                task.completed_at = datetime.now()
                
                if failed_subtasks > 0:
                    task.status = TaskStatus.FAILED
                    task.error_message = f"{failed_subtasks} out of {total_subtasks} subtasks failed"
                    logger.warning(f"TASK_COMPLETION: Task {task_id} '{task.name}' FAILED - {failed_subtasks}/{total_subtasks} subtasks failed")
                else:
                    task.status = TaskStatus.COMPLETED
                    task.result = f"All {total_subtasks} subtasks completed successfully"
                    logger.info(f"TASK_COMPLETION: Task {task_id} '{task.name}' COMPLETED successfully - All {total_subtasks} subtasks completed")
                
                update_success = database.update_task(task)
                
                # Clear current task from all clients that were working on this task
                target_clients = task.get_all_target_clients()
                for client_name in target_clients:
                    database.update_client_current_task(client_name, None, None)
                    # Also update client status back to online if it was busy
                    database.update_client_heartbeat_by_name(client_name, ClientStatus.ONLINE)
                
                # Broadcast task completion
                logger.info(f"TASK_COMPLETION: Broadcasting completion event for task {task_id}")
                socketio.emit('task_completed', {
                    'task_id': task_id,
                    'status': task.status.value,
                    'success': task.status == TaskStatus.COMPLETED,
                    'completed_at': task.completed_at.isoformat(),
                    'total_subtasks': total_subtasks,
                    'completed_subtasks': completed_subtasks,
                    'failed_subtasks': failed_subtasks,
                    'result': task.result,
                    'error_message': task.error_message
                })
        
        except Exception as e:
            logger.error(f"TASK_COMPLETION: Failed to check task completion for task {task_id}: {e}")

    @api.route('/test_update_client_task', methods=['POST'])
    def test_update_client_task():
        """Test endpoint to update client current task - for debugging only"""
        try:
            data = request.get_json()
            client_name = data.get('client_name')
            task_id = data.get('task_id')
            subtask_id = data.get('subtask_id')
            
            success = database.update_client_current_task(client_name, task_id, subtask_id)
            
            return jsonify({
                'success': success,
                'message': f"Updated client '{client_name}' current task to {task_id}, subtask {subtask_id}"
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    return api

