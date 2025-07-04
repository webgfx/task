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

                    if not subtask_data.get('client'):
                        return jsonify({
                            'success': False,
                            'error': f'Subtask {i+1}: client is required'
                        }), 400

                    # Check if subtask exists in registry
                    if not get_subtask(subtask_data['name']):
                        return jsonify({
                            'success': False,
                            'error': f'Subtask {i+1}: "{subtask_data["name"]}" is not a valid subtask. Available subtasks: {list_subtasks()}'
                        }), 400

                    subtask = SubtaskDefinition(
                        name=subtask_data['name'],
                        client=subtask_data['client'],
                        order=subtask_data.get('order', i),
                        args=subtask_data.get('args', []),
                        kwargs=subtask_data.get('kwargs', {}),
                        timeout=subtask_data.get('timeout', 300),
                        retry_count=0,
                        max_retries=3,  # Default value, not configurable from UI
                        subtask_id=i  # Assign incremental ID starting from 0
                    )
                    subtasks.append(subtask)

                # Sort subtasks by order
                subtasks.sort(key=lambda x: x.order)

            else:
                # Legacy format support: convert subtasks to subtasks if no subtasks provided
                subtasks_legacy = data.get('subtasks', [])
                execution_order = data.get('execution_order', [])

                # Backward compatibility: if no subtasks specified but have command, create default format
                if not subtasks_legacy and data.get('command'):
                    subtasks_legacy = [{
                        'id': 1,
                        'name': 'Default Command',
                        'command': data.get('command'),
                        'timeout': 300,
                        'retry_count': 0
                    }]
                    execution_order = [1]

                # Validate at least one command or subtask
                if not subtasks_legacy and not subtasks:
                    return jsonify({
                        'success': False,
                        'error': 'At least one command or subtask must be specified'
                    }), 400

                # Validate execution order (for legacy subtasks only)
                if execution_order and subtasks_legacy:
                    subtask_ids = {cmd['id'] for cmd in subtasks_legacy}
                    for order_id in execution_order:
                        if order_id not in command_ids:
                            return jsonify({
                                'success': False,
                                'error': f'Execution order contains invalid command ID: {order_id}'
                            }), 400
                else:
                    # If no execution order is specified, execute subtasks in ID order
                    execution_order = [cmd['id'] for cmd in subtasks_legacy] if subtasks_legacy else []

            # Validate cron expression
            cron_expr = data.get('cron_expression')
            if cron_expr and not validate_cron_expression(cron_expr):
                return jsonify({
                    'success': False,
                    'error': 'Invalid cron expression format'
                }), 400

            # Handle target client list (may come from legacy fields or subtasks)
            clients = data.get('clients', [])
            if not clients and data.get('client'):
                clients = [data.get('client')]

            # If using subtasks, extract all target clients from subtasks
            if subtasks:
                subtask_clients = list(set(s.client for s in subtasks))
                clients.extend(subtask_clients)
                clients = list(set(clients))  # Remove duplicates

            # Create task object
            task = Task(
                name=data['name'],
                command=data.get('command', ''),  # Maintain backward compatibility
                clients=clients,
                commands=data.get('subtasks', []),
                execution_order=data.get('execution_order', []),
                subtasks=subtasks,
                schedule_time=parse_datetime(data.get('schedule_time')),
                cron_expression=cron_expr,
                client=data.get('client'),  # Maintain backward compatibility
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
                logger.info(f"Created task: {task.name} with {len(subtasks)} subtasks for {len(clients)} clients")
            else:
                logger.info(f"Created task: {task.name} with {len(task.commands)} subtasks for {len(clients)} clients")

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
            if 'clients' in data:
                task.clients = data['clients']
            if 'subtasks' in data:
                task.commands = data['subtasks']
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
            if 'client' in data:
                task.client = data['client']
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

    @api.route('/tasks/<int:task_id>/copy', methods=['POST'])
    def copy_task(task_id):
        """Copy an existing task with optional modifications"""
        try:
            # Get the original task
            original_task = database.get_task(task_id)
            if not original_task:
                return jsonify({
                    'success': False,
                    'error': 'Original task does not exist'
                }), 404

            # Get copy parameters from request
            data = request.get_json() or {}
            
            # Create copied task data with defaults from original
            copied_task_data = {
                'name': data.get('name', f"{original_task.name} (Copy)"),
                'subtasks': [],
                'send_email': data.get('send_email', original_task.send_email),
                'email_recipients': data.get('email_recipients', original_task.email_recipients)
            }
            
            # Handle schedule - default to immediate execution for copies
            schedule_type = data.get('schedule_type', 'immediate')
            if schedule_type == 'scheduled' and data.get('schedule_time'):
                copied_task_data['schedule_time'] = data.get('schedule_time')
            elif schedule_type == 'cron' and data.get('cron_expression'):
                copied_task_data['cron_expression'] = data.get('cron_expression')
            
            # Copy subtasks from original task
            if original_task.subtasks:
                for subtask in original_task.subtasks:
                    copied_subtask = {
                        'name': subtask.name,
                        'client': subtask.client,
                        'order': subtask.order,
                        'args': subtask.args or [],
                        'kwargs': subtask.kwargs or {},
                        'timeout': subtask.timeout
                        # Note: subtask_id will be auto-generated for new task
                    }
                    copied_task_data['subtasks'].append(copied_subtask)
            
            # Apply any client modifications if specified
            if data.get('update_clients'):
                client_updates = data.get('client_updates', {})
                for subtask in copied_task_data['subtasks']:
                    old_client = subtask['client']
                    if old_client in client_updates:
                        subtask['client'] = client_updates[old_client]
            
            # Validate the copied task data using the same logic as create_task
            if not copied_task_data['name']:
                return jsonify({
                    'success': False,
                    'error': 'Task name cannot be empty'
                }), 400
            
            # Parse and validate subtasks
            subtasks = []
            for i, subtask_data in enumerate(copied_task_data['subtasks']):
                # Validate subtask
                if not subtask_data.get('name'):
                    return jsonify({
                        'success': False,
                        'error': f'Subtask {i+1}: name is required'
                    }), 400

                if not subtask_data.get('client'):
                    return jsonify({
                        'success': False,
                        'error': f'Subtask {i+1}: client is required'
                    }), 400

                # Check if subtask exists in registry
                if not get_subtask(subtask_data['name']):
                    return jsonify({
                        'success': False,
                        'error': f'Subtask {i+1}: "{subtask_data["name"]}" is not a valid subtask'
                    }), 400

                subtask = SubtaskDefinition(
                    name=subtask_data['name'],
                    client=subtask_data['client'],
                    order=subtask_data.get('order', i),
                    args=subtask_data.get('args', []),
                    kwargs=subtask_data.get('kwargs', {}),
                    timeout=subtask_data.get('timeout', 300),
                    retry_count=0,
                    max_retries=3,
                    subtask_id=i  # New ID for copied task
                )
                subtasks.append(subtask)

            # Sort subtasks by order
            subtasks.sort(key=lambda x: x.order)

            # Create the copied task
            task = Task(
                name=copied_task_data['name'],
                subtasks=subtasks,
                schedule_time=parse_datetime(copied_task_data.get('schedule_time')),
                cron_expression=copied_task_data.get('cron_expression'),
                send_email=copied_task_data.get('send_email', False),
                email_recipients=copied_task_data.get('email_recipients', ''),
                status=TaskStatus.PENDING,
                created_at=datetime.now()
            )

            # Validate cron expression if provided
            if task.cron_expression and not validate_cron_expression(task.cron_expression):
                return jsonify({
                    'success': False,
                    'error': 'Invalid cron expression format'
                }), 400

            # Save the copied task
            task_id = database.create_task(task)
            task.id = task_id

            logger.info(f"Task copied successfully: {original_task.name} -> {task.name} (ID: {task_id})")

            return jsonify({
                'success': True,
                'data': task.to_dict(),
                'message': f'Task copied successfully from "{original_task.name}"'
            })

        except Exception as e:
            logger.error(f"Copy task failed: {e}")
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

            # Can only cancel running or pending tasks
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return jsonify({
                    'success': False,
                    'error': f'Cannot cancel task with status: {task.status.value}'
                }), 400

            # Update task status to cancelled
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            task.error_message = "Task cancelled by user"
            database.update_task(task)

            # Broadcast task cancellation event
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
            client = data.get('client')
            
            if not client:
                return jsonify({
                    'success': False,
                    'error': 'client parameter is required'
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
                if subtask.name == subtask_name and subtask.client == client:
                    subtask_to_delete = subtask
                    break

            if not subtask_to_delete:
                return jsonify({
                    'success': False,
                    'error': f'Subtask "{subtask_name}" for client "{client}" not found in task'
                }), 404

            # Check if subtask has already started execution and get subtask_id
            subtask_id = None
            executions = database.get_executions_by_client(task_id, client)
            for execution in executions:
                if execution.subtask_name == subtask_name:
                    if execution.status in [TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.FAILED]:
                        return jsonify({
                            'success': False,
                            'error': f'Cannot delete subtask "{subtask_name}" - it has already started execution (status: {execution.status.value})'
                        }), 400
                    # Store subtask_id for pending executions
                    if execution.status == TaskStatus.PENDING:
                        subtask_id = execution.subtask_id

            # Remove the subtask from the task
            task.subtasks = [s for s in task.subtasks 
                           if not (s.name == subtask_name and s.client == client)]
            
            # Update clients list if no more subtasks target this client
            remaining_clients = set(s.client for s in task.subtasks)
            task.clients = [m for m in task.clients if m in remaining_clients]

            # If no subtasks remain, set task status to cancelled
            if not task.subtasks:
                task.status = TaskStatus.CANCELLED
                task.error_message = "All subtasks were deleted"
                task.completed_at = datetime.now()

            # Update the task in database
            database.update_task(task)

            # Remove any pending subtask execution records for this subtask
            database.delete_pending_executions(task_id, subtask_name, client)

            logger.info(f"SUBTASK_DELETION: Deleted subtask '{subtask_name}' from task {task_id} for client '{client}'")

            # Broadcast subtask deletion event
            socketio.emit('subtask_deleted', {
                'task_id': task_id,
                'subtask_id': subtask_id,
                'subtask_name': subtask_name,
                'client': client,
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

    @api.route('/tasks/<int:task_id>/subtask-executions', methods=['GET'])
    def get_executions(task_id):
        """Get subtask execution records for a task"""
        try:
            executions = database.get_executions(task_id)
            return jsonify({
                'success': True,
                'data': [exec.to_dict() for exec in executions]
            })
        except Exception as e:
            logger.error(f"Get subtask execution records failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>/subtask-executions/<client_name>', methods=['GET'])
    def get_executions_by_client(task_id, client_name):
        """Get subtask execution records for a specific task and client"""
        try:
            executions = database.get_executions_by_client(task_id, client_name)
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
            client = data.get('client')
            status = data.get('status')
            execution_time = data.get('execution_time')
            result = data.get('result')
            error_message = data.get('error_message')
            
            # Enhanced logging for subtask result reception
            logger.info(f"📨 RESULT_RECEIVED: Task {task_id} - '{subtask_name}' from client '{client}' - Status: {status}")
            if execution_time:
                logger.info(f"RESULT_TIMING: Task {task_id} - '{subtask_name}' executed in {execution_time:.2f}s on '{client}'")
            
            # Log result details based on status
            if status == 'completed' and result:
                result_preview = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                logger.info(f"RESULT_SUCCESS: Task {task_id} - '{subtask_name}' → Result: {result_preview}")
            elif status == 'failed' and error_message:
                error_preview = str(error_message)[:100] + "..." if len(str(error_message)) > 100 else str(error_message)
                logger.info(f"RESULT_ERROR: Task {task_id} - '{subtask_name}' → Error: {error_preview}")
            
            logger.info(f"SUBTASK_EXECUTION: Task {task_id} - '{subtask_name}' on '{client}' - Status: {status}")
            if execution_time:
                logger.info(f"SUBTASK_EXECUTION: Task {task_id} - '{subtask_name}' execution time: {execution_time}s")
            if result:
                logger.debug(f"SUBTASK_EXECUTION: Task {task_id} - '{subtask_name}' result: {result[:200]}{'...' if len(str(result)) > 200 else ''}")
            if error_message:
                logger.warning(f"SUBTASK_EXECUTION: Task {task_id} - '{subtask_name}' error: {error_message}")

            # Validate required fields
            required_fields = ['subtask_name', 'client', 'status']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }), 400

            # Find or create subtask execution record
            executions = database.get_executions_by_client(task_id, data['client'])
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
                            subtask_def.client == data['client']):
                            subtask_id = subtask_def.subtask_id
                            break
                
                execution = SubtaskExecution(
                    task_id=task_id,
                    subtask_id=subtask_id or f"{data.get('order', 0)}_{data['subtask_name']}",  # Fallback ID
                    subtask_name=data['subtask_name'],
                    subtask_order=data.get('order', 0),
                    client=data['client'],
                    status=TaskStatus(data['status'])
                )
                execution.id = database.create_subtask_execution(execution)
                logger.info(f"📝 EXECUTION_RECORD: Created execution record for Task {task_id} - '{subtask_name}' on '{client}'")
                logger.info(f"SUBTASK_EXECUTION: Created new execution record for Task {task_id} - '{subtask_name}' on '{client}'")

            # Update execution status
            execution.status = TaskStatus(data['status'])
            execution.result = data.get('result')
            execution.error_message = data.get('error_message')
            execution.execution_time = data.get('execution_time')

            if data['status'] in ['completed', 'failed']:
                execution.completed_at = datetime.now()
                logger.info(f"SUBTASK_EXECUTION: Task {task_id} - '{subtask_name}' on '{client}' completed at {execution.completed_at.isoformat()}")

            database.update_subtask_execution(execution)

            # Update client's current subtask status
            if data['status'] == 'running':
                # Client started working on this subtask
                # Find the subtask definition to get the subtask_id
                task = database.get_task(task_id)
                if task and task.subtasks:
                    for subtask_def in task.subtasks:
                        if (subtask_def.name == data['subtask_name'] and 
                            subtask_def.client == data['client']):
                            database.update_client_current_task(
                                data['client'], 
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
                        if (s.client == data['client'] and 
                            s.order > data.get('order', 0))
                    ]
                    if remaining_subtasks:
                        # Move to next subtask
                        next_subtask = min(remaining_subtasks, key=lambda x: x.order)
                        database.update_client_current_task(
                            data['client'], 
                            task_id, 
                            next_subtask.subtask_id
                        )
                    else:
                        # No more subtasks, clear current task
                        database.update_client_current_task(data['client'], None, None)
                        # Set client back to online
                        database.update_client_heartbeat_by_name(data['client'], ClientStatus.ONLINE)

            # Check if all subtasks are completed and update overall task status
            logger.debug(f"SUBTASK_EXECUTION: Checking task completion for task {task_id}")
            
            # Notify result collector about subtask completion
            if result_collector and data['status'] in ['completed', 'failed']:
                result_collector.on_subtask_completion(
                    task_id=task_id,
                    client_name=data['client'],
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
                'subtask_id': execution.subtask_id,
                'subtask_name': data['subtask_name'],
                'client': data['client'],
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
                subtask_instance = get_subtask(subtask_name)
                if subtask_instance:
                    # Get description from instance method
                    description = subtask_instance.get_description() or "No description available"
                    subtask_info.append({
                        'name': subtask_name,
                        'description': description.strip(),
                        'function': subtask_name  # Use the name instead of function name
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
                'function': subtask_func.__class__.__name__,
                'description': subtask_func.get_description(),
                'module': subtask_func.__class__.__module__,
            }
            
            # Try to get function signature if available
            try:
                import inspect
                # For class instances, inspect the run method
                run_method = getattr(subtask_func, 'run', None)
                if run_method:
                    sig = inspect.signature(run_method)
                    info['parameters'] = {
                        'signature': str(sig),
                        'parameters': [
                            {
                                'name': param.name,
                                'default': str(param.default) if param.default != inspect.Parameter.empty else None,
                                'annotation': str(param.annotation) if param.annotation != inspect.Parameter.empty else None
                            }
                            for param in sig.parameters.values()
                            if param.name != 'self'  # Skip 'self' parameter
                        ]
                    }
                else:
                    info['parameters'] = 'No run method found'
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
        """Get all clients with enhanced task information"""
        try:
            clients = database.get_all_clients()
            
            # Enhance clients with task names
            enhanced_clients = []
            for client in clients:
                client_dict = client.to_dict()
                
                # Add task name if client has current task
                if client.current_task_id:
                    task = database.get_task(client.current_task_id)
                    if task:
                        client_dict['current_task_name'] = task.name
                    else:
                        client_dict['current_task_name'] = 'Unknown Task'
                else:
                    client_dict['current_task_name'] = None
                
                enhanced_clients.append(client_dict)
            
            return jsonify({
                'success': True,
                'data': enhanced_clients
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
        """Client heartbeat using client name as primary identifier with optional system information update"""
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

            # Check if fresh system information is included in heartbeat
            system_info_updated = False
            if any(key in data for key in ['cpu_info', 'memory_info', 'gpu_info', 'os_info', 'disk_info', 'system_summary']):
                try:
                    # Get existing client
                    client = database.get_client_by_name(client_name)
                    if client:
                        # Check if system information has actually changed
                        old_system_summary = client.system_summary or {}
                        new_system_summary = data.get('system_summary', {})
                        
                        # Update system information if provided
                        changes_detected = False
                        if 'cpu_info' in data:
                            client.cpu_info = data['cpu_info']
                            changes_detected = True
                        if 'memory_info' in data:
                            client.memory_info = data['memory_info']
                            changes_detected = True
                        if 'gpu_info' in data:
                            # Check if GPU info actually changed
                            old_gpu = client.gpu_info or []
                            new_gpu = data['gpu_info'] or []
                            if old_gpu != new_gpu:
                                client.gpu_info = data['gpu_info']
                                changes_detected = True
                                logger.debug(f"HEARTBEAT: GPU information changed for '{client_name}'")
                        if 'os_info' in data:
                            client.os_info = data['os_info']
                            changes_detected = True
                        if 'disk_info' in data:
                            client.disk_info = data['disk_info']
                            changes_detected = True
                        if 'system_summary' in data:
                            # Check if system summary changed
                            if old_system_summary != new_system_summary:
                                client.system_summary = data['system_summary']
                                changes_detected = True
                                logger.debug(f"HEARTBEAT: System summary changed for '{client_name}'")
                        
                        # Only update if changes were detected
                        if changes_detected:
                            # Use update_client_config for system info updates
                            database.update_client_config(client)
                            system_info_updated = True
                            
                            logger.info(f"HEARTBEAT: Updated system information for client '{client_name}' (changes detected)")
                            if client.system_summary:
                                logger.debug(f"  Updated CPU: {client.system_summary.get('cpu', 'Unknown')}")
                                logger.debug(f"  Updated GPU: {client.system_summary.get('gpu', 'Unknown')}")
                        else:
                            logger.debug(f"HEARTBEAT: No system information changes detected for '{client_name}'")
                    else:
                        logger.warning(f"HEARTBEAT: Client '{client_name}' not found for system info update")
                        
                except Exception as e:
                    logger.warning(f"HEARTBEAT: Failed to update system information for '{client_name}': {e}")
                    import traceback
                    logger.debug(f"HEARTBEAT: System info update error details: {traceback.format_exc()}")

            # Get client info for broadcast
            client = database.get_client_by_name(client_name)
            ip_address = client.ip_address if client else 'unknown'

            # Enhanced logging for heartbeat
            heartbeat_msg = f"HEARTBEAT: Client '{client_name}' ({ip_address}) heartbeat - Status: {status}"
            if system_info_updated:
                heartbeat_msg += " (with fresh system info)"
            logger.info(heartbeat_msg)
            
            if client:
                logger.debug(f"HEARTBEAT: Client '{client_name}' last seen at {datetime.now().isoformat()}")

            # Broadcast heartbeat event
            socketio.emit('client_heartbeat', {
                'ip_address': ip_address,
                'client_name': client_name,
                'status': status,
                'timestamp': datetime.now().isoformat(),
                'system_info_updated': system_info_updated
            })

            return jsonify({
                'success': True,
                'system_info_updated': system_info_updated
            })

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
                    logger.debug(f"TASK_SCHEDULING: Task {task_id} Subtask {i+1}: '{subtask.name}' -> '{subtask.client}'")

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
            client_name = data.get('client_name')  # Use client name as primary identifier
            client_ip = data.get('client_ip', 'Unknown')  # IP as auxiliary information

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
            client_name = data.get('client_name')  # Use client name as primary identifier
            client_ip = data.get('client_ip', 'Unknown')  # IP as auxiliary information
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
            from common.subtasks import list_subtasks, get_subtask
            
            # Build definitions using the new class-based system
            result = {}
            for subtask_name in list_subtasks():
                subtask_instance = get_subtask(subtask_name)
                if subtask_instance:
                    description = subtask_instance.get_description()
                    result[subtask_name] = {
                        'description': description,
                        'result_definition': {
                            'name': subtask_name,
                            'description': description,
                            'result_type': 'any',
                            'required_fields': [],
                            'is_critical': False,
                            'format_hint': 'Any valid JSON object'
                        }
                    }
            
            return jsonify({
                'success': True,
                'data': result
            })
            
        except Exception as e:
            logger.error(f"Get subtask definitions failed: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
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
                        DELETE FROM logs
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

    @api.route('/clients/<client_name>/ping', methods=['POST'])
    def ping_client(client_name):
        """Ping a client via WebSocket and get its real-time status"""
        try:
            logger.info(f"PING: Starting ping for client '{client_name}'")
            
            # Get client from database
            client = database.get_client_by_name(client_name)
            if not client:
                return jsonify({
                    'success': False,
                    'error': f'Client "{client_name}" not found'
                }), 404
            
            # Check if client has recent heartbeat (basic connectivity check)
            current_time = datetime.now()
            is_reachable = False
            response_time = None
            
            if client.last_heartbeat:
                time_since_heartbeat = current_time - client.last_heartbeat
                response_time = f"{time_since_heartbeat.total_seconds():.1f}s ago"
                is_reachable = time_since_heartbeat.total_seconds() <= 30
            else:
                response_time = "Never"
            
            if not is_reachable:
                # Client is offline - no point in trying to ping
                return jsonify({
                    'success': False,
                    'message': f"Client '{client_name}' is unreachable (last seen {response_time})",
                    'data': {
                        'client_name': client_name,
                        'status': 'offline',
                        'response_time': response_time,
                        'ping_success': False
                    }
                })
            
            # Send ping request via WebSocket and wait for response
            ping_response = send_ping_to_client(client_name, socketio)
            
            if ping_response is None:
                # No WebSocket connection or timeout
                working_status = 'offline'
                message = f"Client '{client_name}' is not connected via WebSocket"
                ping_success = False
            else:
                working_status = ping_response.get('status', 'unknown')
                ping_success = True
                message = f"Client '{client_name}' responded - Status: {working_status.upper()}"
                if response_time:
                    message += f" (last heartbeat {response_time})"
            
            # Broadcast real-time update
            socketio.emit('client_status_updated', {
                'client_name': client_name,
                'status': working_status,
                'ping_success': ping_success,
                'response_time': response_time
            })
            
            return jsonify({
                'success': True,
                'message': message,
                'data': {
                    'client_name': client_name,
                    'status': working_status,
                    'response_time': response_time,
                    'ping_success': ping_success
                }
            })
            
        except Exception as e:
            logger.error(f"PING: Failed to ping client '{client_name}': {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to ping client: {str(e)}'
            }), 500

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

    @api.route('/test-ping', methods=['GET', 'POST'])
    def test_ping():
        """Test ping endpoint"""
        print("DEBUG: test_ping function called")
        return jsonify({'success': True, 'message': 'Test ping works'})

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
            executions = database.get_executions(task_id)
            logger.debug(f"TASK_COMPLETION: Found {len(executions)} subtask executions for task {task_id}")
            
            # Create a map of executed subtasks
            execution_map = {}
            for exec in executions:
                key = f"{exec.subtask_name}_{exec.client}"
                execution_map[key] = exec
            
            # Check completion status
            total_subtasks = len(task.subtasks)
            completed_subtasks = 0
            failed_subtasks = 0
            
            for subtask in task.subtasks:
                key = f"{subtask.name}_{subtask.client}"
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
                clients = task.get_all_clients()
                for client_name in clients:
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

    def send_ping_to_client(client_name, socketio_instance):
        """
        Send a ping request to a specific client via WebSocket and wait for response
        
        Args:
            client_name: Name of the client to ping
            socketio_instance: SocketIO instance to use for communication
            
        Returns:
            dict: Response from client with status information, or None if no response
        """
        import threading
        import time
        
        # Storage for ping response
        ping_responses = {}
        ping_event = threading.Event()
        
        def ping_response_handler(data):
            """Handle ping response from client"""
            if data.get('client_name') == client_name:
                ping_responses[client_name] = data
                ping_event.set()
                
                # Update system information if provided in ping response
                try:
                    if any(key in data for key in ['cpu_info', 'memory_info', 'gpu_info', 'os_info', 'disk_info', 'system_summary']):
                        logger.info(f"PING: Updating client system info from ping response for '{client_name}'")
                        
                        # Get existing client
                        client = database.get_client_by_name(client_name)
                        if client:
                            # Update system information
                            update_data = {}
                            if 'cpu_info' in data:
                                update_data['cpu_info'] = data['cpu_info']
                            if 'memory_info' in data:
                                update_data['memory_info'] = data['memory_info']
                            if 'gpu_info' in data:
                                update_data['gpu_info'] = data['gpu_info']
                            if 'os_info' in data:
                                update_data['os_info'] = data['os_info']
                            if 'disk_info' in data:
                                update_data['disk_info'] = data['disk_info']
                            if 'system_summary' in data:
                                update_data['system_summary'] = data['system_summary']
                            
                            if update_data:
                                database.update_client_config(client_name, update_data)
                                logger.info(f"PING: Updated system info for client '{client_name}' from ping response")
                                
                                # Emit system info update event
                                socketio_instance.emit('client_config_updated', {
                                    'client_name': client_name,
                                    'source': 'ping_response',
                                    'system_info_updated': True
                                })
                        else:
                            logger.warning(f"PING: Client '{client_name}' not found for system info update")
                            
                except Exception as e:
                    logger.error(f"PING: Failed to update system info from ping response: {e}")
        
        # Register temporary event handler for ping responses
        @socketio_instance.event
        def client_ping_response(data):
            ping_response_handler(data)
        
        try:
            # Send ping request to specific client
            logger.info(f"PING: Sending ping request to client '{client_name}'")
            socketio_instance.emit('ping_request', {
                'client_name': client_name,
                'timestamp': datetime.now().isoformat()
            })
            
            # Wait for response with timeout
            response_received = ping_event.wait(timeout=5.0)  # 5 second timeout
            
            if response_received and client_name in ping_responses:
                response = ping_responses[client_name]
                logger.info(f"PING: Received response from client '{client_name}': {response.get('status', 'unknown')}")
                return response
            else:
                logger.warning(f"PING: No response from client '{client_name}' within timeout")
                return None
                
        except Exception as e:
            logger.error(f"PING: Error sending ping to client '{client_name}': {e}")
            return None
        finally:
            # Clean up
            ping_responses.pop(client_name, None)

    return api

