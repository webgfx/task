"""
REST API interfaces
"""
import json
import logging
import os
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_socketio import emit

from common.config import Config
from common.models import Job, Client, JobStatus, ClientStatus, TaskDefinition
from common.utils import parse_datetime, validate_cron_expression
from common.tasks import list_tasks, get_task, execute_task

logger = logging.getLogger(__name__)

def create_api_blueprint(database, socketio, result_collector=None):
    """Create API blueprint"""
    api = Blueprint('api', __name__)

    # Task ManagementAPI
    @api.route('/jobs', methods=['GET'])
    def get_tasks():
        """Get all tasks with their run data included"""
        try:
            tasks = database.get_all_jobs()
            # Bulk-load all runs in one query instead of N+1
            all_execs = database.get_all_runs_grouped()
            task_dicts = []
            for job in tasks:
                d = job.to_dict()
                execs = all_execs.get(job.id, [])
                d['runs'] = [e.to_dict() for e in execs]
                task_dicts.append(d)
            return jsonify({
                'success': True,
                'data': task_dicts
            })
        except Exception as e:
            logger.error(f"Get task listFailed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/jobs', methods=['POST'])
    def create_task():
        """Create new job with task definitions and target clients"""
        try:
            data = request.get_json()

            # Validate required fields
            if not data.get('name'):
                return jsonify({
                    'success': False,
                    'error': 'Job name cannot be empty'
                }), 400

            # Parse task definitions
            tasks_data = data.get('tasks', [])
            task_defs = []

            if not tasks_data:
                return jsonify({
                    'success': False,
                    'error': 'At least one task must be specified'
                }), 400

            for i, td in enumerate(tasks_data):
                if not td.get('name'):
                    return jsonify({
                        'success': False,
                        'error': f'Task {i+1}: name is required'
                    }), 400

                if not td.get('client'):
                    return jsonify({
                        'success': False,
                        'error': f'Task {i+1}: client is required'
                    }), 400

                # Check if task type exists in registry
                if not get_task(td['name']):
                    return jsonify({
                        'success': False,
                        'error': f'Task {i+1}: "{td["name"]}" is not a valid task type. Available: {list_tasks()}'
                    }), 400

                task_def = TaskDefinition(
                    name=td['name'],
                    client=td['client'],
                    order=td.get('order', i),
                    args=td.get('args', []),
                    kwargs=td.get('kwargs', {}),
                    timeout=td.get('timeout', 300),
                    retry_count=0,
                    max_retries=3,
                    task_id=i
                )
                task_defs.append(task_def)

            task_defs.sort(key=lambda x: x.order)

            # Validate cron expression
            cron_expr = data.get('cron_expression')
            if cron_expr and not validate_cron_expression(cron_expr):
                return jsonify({
                    'success': False,
                    'error': 'Invalid cron expression format'
                }), 400

            # Extract all target clients from task definitions
            clients = list(set(t.client for t in task_defs))

            # Create job object
            job = Job(
                name=data['name'],
                clients=clients,
                tasks=task_defs,
                schedule_time=parse_datetime(data.get('schedule_time')),
                cron_expression=cron_expr,
                max_retries=3,
                send_email=data.get('send_email', False),
                email_recipients=data.get('email_recipients')
            )

            # Save to database
            job_id = database.create_job(job)
            job.id = job_id

            job_dict = job.to_dict()
            socketio.emit('task_created', job_dict)

            logger.info(f"Created job: {job.name} with {len(task_defs)} tasks for {len(clients)} clients")

            return jsonify({
                'success': True,
                'data': job_dict
            }), 201

        except Exception as e:
            logger.error(f"Create Task Failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/jobs/<int:task_id>', methods=['GET'])
    def get_job(task_id):
        """Get specified task"""
        try:
            task = database.get_job(task_id)
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

    @api.route('/jobs/<int:task_id>', methods=['PUT'])
    def update_job(task_id):
        """Update task"""
        try:
            task = database.get_job(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            data = request.get_json()

            # Update task fields
            if 'name' in data:
                td.name = data['name']
            if 'command' in data:
                task.command = data['command']
            if 'clients' in data:
                task.clients = data['clients']
            if 'tasks' in data:
                task.commands = data['tasks']
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
                td.client = data['client']
            if 'max_retries' in data:
                task.max_retries = data['max_retries']
            if 'send_email' in data:
                task.send_email = data['send_email']
            if 'email_recipients' in data:
                task.email_recipients = data['email_recipients']

            # Save update
            database.update_job(task)

            # Broadcast task update event
            socketio.emit('subtask_updated', task.to_dict())

            return jsonify({
                'success': True,
                'data': task.to_dict()
            })

        except Exception as e:
            logger.error(f"Update taskFailed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/jobs/<int:task_id>', methods=['DELETE'])
    def delete_job(task_id):
        """Delete task and all related run records"""
        try:
            task = database.get_job(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            success = database.delete_job(task_id)

            if success:
                # Note: WebSocket emission is now handled in the database method
                return jsonify({
                    'success': True,
                    'message': f'Task "{td.name}" deleted successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Task could not be deleted'
                }), 500

        except Exception as e:
            logger.error(f"Delete task failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/jobs/<int:task_id>/copy', methods=['POST'])
    def copy_job(task_id):
        """Copy an existing task with optional modifications"""
        try:
            # Get the original task
            original_task = database.get_job(task_id)
            if not original_task:
                return jsonify({
                    'success': False,
                    'error': 'Original task does not exist'
                }), 404

            # Get copy parameters from request
            data = request.get_json() or {}

            # Create copied task data with defaults from original
            copied_task_data = {
                'name': data.get('name', f"{original_td.name} (Copy)"),
                'tasks': [],
                'send_email': data.get('send_email', original_task.send_email),
                'email_recipients': data.get('email_recipients', original_task.email_recipients)
            }

            # Handle schedule - default to immediate run for copies
            schedule_type = data.get('schedule_type', 'immediate')
            if schedule_type == 'scheduled' and data.get('schedule_time'):
                copied_task_data['schedule_time'] = data.get('schedule_time')
            elif schedule_type == 'cron' and data.get('cron_expression'):
                copied_task_data['cron_expression'] = data.get('cron_expression')

            # Copy tasks from original task
            if original_task.tasks:
                for td in original_task.tasks:
                    copied_task = {
                        'name': td.name,
                        'client': td.client,
                        'order': td.order,
                        'args': Task.args or [],
                        'kwargs': Task.kwargs or {},
                        'timeout': Task.timeout
                        # Note: task_id will be auto-generated for new task
                    }
                    copied_task_data['tasks'].append(copied_task)

            # Apply any client modifications if specified
            if data.get('update_clients'):
                client_updates = data.get('client_updates', {})
                for td in copied_task_data['tasks']:
                    old_client = td['client']
                    if old_client in client_updates:
                        Task['client'] = client_updates[old_client]

            # Validate the copied task data using the same logic as create_task
            if not copied_task_data['name']:
                return jsonify({
                    'success': False,
                    'error': 'Task name cannot be empty'
                }), 400

            # Parse and validate tasks
            tasks = []
            for i, task_data in enumerate(copied_task_data['tasks']):
                # Validate Task
                if not task_data.get('name'):
                    return jsonify({
                        'success': False,
                        'error': f'Task {i+1}: name is required'
                    }), 400

                if not task_data.get('client'):
                    return jsonify({
                        'success': False,
                        'error': f'Task {i+1}: client is required'
                    }), 400

                # Check if Task exists in registry
                if not get_task(task_data['name']):
                    return jsonify({
                        'success': False,
                        'error': f'Task {i+1}: "{task_data["name"]}" is not a valid Task'
                    }), 400

                Task = TaskDefinition(
                    name=task_data['name'],
                    client=task_data['client'],
                    order=task_data.get('order', i),
                    args=task_data.get('args', []),
                    kwargs=task_data.get('kwargs', {}),
                    timeout=task_data.get('timeout', 300),
                    retry_count=0,
                    max_retries=3,
                    task_id=i  # New ID for copied task
                )
                tasks.append(Task)

            # Sort tasks by order
            tasks.sort(key=lambda x: x.order)

            # Create the copied task
            task = Job(
                name=copied_task_data['name'],
                tasks=tasks,
                schedule_time=parse_datetime(copied_task_data.get('schedule_time')),
                cron_expression=copied_task_data.get('cron_expression'),
                send_email=copied_task_data.get('send_email', False),
                email_recipients=copied_task_data.get('email_recipients', ''),
                status=JobStatus.PENDING,
                created_at=datetime.now()
            )

            # Validate cron expression if provided
            if task.cron_expression and not validate_cron_expression(task.cron_expression):
                return jsonify({
                    'success': False,
                    'error': 'Invalid cron expression format'
                }), 400

            # Save the copied task
            task_id = database.create_job(task)
            task.id = task_id

            logger.info(f"Task copied successfully: {original_td.name} -> {td.name} (ID: {task_id})")

            return jsonify({
                'success': True,
                'data': task.to_dict(),
                'message': f'Task copied successfully from "{original_td.name}"'
            })

        except Exception as e:
            logger.error(f"Copy task failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/jobs/<int:task_id>/cancel', methods=['POST'])
    def cancel_job(task_id):
        """Cancel task run"""
        try:
            task = database.get_job(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            # Can only cancel running or pending tasks
            if task.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                return jsonify({
                    'success': False,
                    'error': f'Cannot cancel task with status: {task.status.value}'
                }), 400

            # Update task status to cancelled
            task.status = JobStatus.CANCELLED
            task.completed_at = datetime.now()
            task.error_message = "Task cancelled by user"
            database.update_job(task)

            # Broadcast task cancellation event
            socketio.emit('task_cancelled', {
                'task_id': task_id,
                'cancelled_at': task.completed_at.isoformat()
            })

            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Cancel taskFailed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>/tasks/<task_name>/delete', methods=['DELETE'])
    def delete_TASK(task_id, task_name):
        """Delete a specific Task that hasn't started run yet"""
        try:
            data = request.get_json() or {}
            client = data.get('client')

            if not client:
                return jsonify({
                    'success': False,
                    'error': 'client parameter is required'
                }), 400

            # Get the task
            task = database.get_job(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            # Check if task is in a state where tasks can be deleted
            if task.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                return jsonify({
                    'success': False,
                    'error': f'Cannot delete tasks from task with status: {task.status.value}'
                }), 400

            # Find the Task to delete
            task_to_delete = None
            for td in task.tasks:
                if td.name == task_name and td.client == client:
                    task_to_delete = td
                    break

            if not task_to_delete:
                return jsonify({
                    'success': False,
                    'error': f'Task "{task_name}" for client "{client}" not found in task'
                }), 404

            # Check if Task has already started run and get task_id
            task_id = None
            runs = database.get_runs_by_client(task_id, client)
            for run in runs:
                if run.task_name == task_name:
                    if run.status in [JobStatus.RUNNING, JobStatus.COMPLETED, JobStatus.FAILED]:
                        return jsonify({
                            'success': False,
                            'error': f'Cannot delete Task "{task_name}" - it has already started run (status: {run.status.value})'
                        }), 400
                    # Store task_id for pending runs
                    if run.status == JobStatus.PENDING:
                        task_id = run.task_id

            # Remove the Task from the task
            task.tasks = [s for s in task.tasks
                           if not (s.name == task_name and s.client == client)]

            # Update clients list if no more tasks target this client
            remaining_clients = set(s.client for s in task.tasks)
            task.clients = [m for m in task.clients if m in remaining_clients]

            # If No tasks remain, set task status to cancelled
            if not task.tasks:
                task.status = JobStatus.CANCELLED
                task.error_message = "All tasks were deleted"
                task.completed_at = datetime.now()

            # Update the task in database
            database.update_job(task)

            # Remove any pending Task run records for this Task
            database.delete_pending_runs(task_id, task_name, client)

            logger.info(f"TASK_DELETION: Deleted Task '{task_name}' from task {task_id} for client '{client}'")

            # Broadcast Task deletion event
            socketio.emit('task_deleted', {
                'task_id': task_id,
                'task_id': task_id,
                'task_name': task_name,
                'client': client,
                'deleted_at': datetime.now().isoformat(),
                'remaining_TASKs': len(task.tasks)
            })

            return jsonify({
                'success': True,
                'message': f'Task "{task_name}" deleted successfully',
                'remaining_TASKs': len(task.tasks),
                'run_status': task.status.value
            })

        except Exception as e:
            logger.error(f"Delete Task failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/jobs/<int:task_id>/runs', methods=['GET'])
    def get_runs(task_id):
        """Get Task run records for a task"""
        try:
            runs = database.get_runs(task_id)
            return jsonify({
                'success': True,
                'data': [r.to_dict() for r in runs]
            })
        except Exception as e:
            logger.error(f"Get Task run records failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/jobs/<int:task_id>/runs/<client_name>', methods=['GET'])
    def get_runs_by_client(task_id, client_name):
        """Get Task run records for a specific task and client"""
        try:
            runs = database.get_runs_by_client(task_id, client_name)
            return jsonify({
                'success': True,
                'data': [r.to_dict() for r in runs]
            })
        except Exception as e:
            logger.error(f"Get Task run records by client failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/jobs/<int:task_id>/runs', methods=['POST'])
    def update_run(task_id):
        """Update Task run status (called by client)"""
        try:
            data = request.get_json()

            # Enhanced logging for Task run status
            task_name = data.get('task_name')
            client = data.get('client')
            status = data.get('status')
            execution_time = data.get('execution_time')
            result = data.get('result')
            error_message = data.get('error_message')

            # Enhanced logging for Task result reception
            logger.info(f"📨 RESULT_RECEIVED: Task {task_id} - '{task_name}' from client '{client}' - Status: {status}")
            if execution_time:
                logger.info(f"RESULT_TIMING: Task {task_id} - '{task_name}' executed in {execution_time:.2f}s on '{client}'")

            # Log result details based on status
            if status == 'completed' and result:
                result_preview = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                logger.info(f"RESULT_SUCCESS: Task {task_id} - '{task_name}' → Result: {result_preview}")
            elif status == 'failed' and error_message:
                error_preview = str(error_message)[:100] + "..." if len(str(error_message)) > 100 else str(error_message)
                logger.info(f"RESULT_ERROR: Task {task_id} - '{task_name}' → Error: {error_preview}")

            logger.info(f"TASK_EXECUTION: Task {task_id} - '{task_name}' on '{client}' - Status: {status}")
            if execution_time:
                logger.info(f"TASK_EXECUTION: Task {task_id} - '{task_name}' run time: {execution_time}s")
            if result:
                logger.debug(f"TASK_EXECUTION: Task {task_id} - '{task_name}' result: {result[:200]}{'...' if len(str(result)) > 200 else ''}")
            if error_message:
                logger.warning(f"TASK_EXECUTION: Task {task_id} - '{task_name}' error: {error_message}")

            # Validate required fields
            required_fields = ['task_name', 'client', 'status']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }), 400

            # Find or create run record
            runs = database.get_runs_by_client(task_id, data['client'])
            run = None

            for r in runs:
                if r.task_name == data['task_name'] and r.status in [JobStatus.PENDING, JobStatus.RUNNING]:
                    run = r
                    break

            if not run:
                # Create new run record
                from common.models import Run

                # Find the task definition to get the task_id
                task = database.get_job(task_id)
                run_task_id = None
                if task and task.tasks:
                    for task_def in task.tasks:
                        if (task_def.name == data['task_name'] and
                            task_def.client == data['client']):
                            run_task_id = task_def.task_id
                            break

                run = Run(
                    job_id=task_id,
                    task_id=run_task_id or f"{data.get('order', 0)}_{data['task_name']}",
                    task_name=data['task_name'],
                    task_order=data.get('order', 0),
                    client=data['client'],
                    status=JobStatus(data['status'])
                )
                run.id = database.create_run(run)
                logger.info(f"Created run record for job {task_id} - '{task_name}' on '{client}'")

            # Update run status
            run.status = JobStatus(data['status'])
            run.result = data.get('result')
            run.error_message = data.get('error_message')
            run.execution_time = data.get('execution_time')

            if data['status'] in ['completed', 'failed']:
                run.completed_at = datetime.now()

            database.update_run(run)

            # Update client's current task status
            if data['status'] == 'running':
                task = database.get_job(task_id)
                if task and task.tasks:
                    for task_def in task.tasks:
                        if (task_def.name == data['task_name'] and
                            task_def.client == data['client']):
                            database.update_client_current_task(
                                data['client'],
                                task_id,
                                task_def.task_id
                            )
                            break
            elif data['status'] in ['completed', 'failed']:
                task = database.get_job(task_id)
                if task and task.tasks:
                    remaining = [
                        t for t in task.tasks
                        if (t.client == data['client'] and
                            t.order > data.get('order', 0))
                    ]
                    if remaining:
                        next_td = min(remaining, key=lambda x: x.order)
                        database.update_client_current_task(
                            data['client'],
                            task_id,
                            next_td.task_id
                        )
                    else:
                        # No more tasks, clear current task
                        database.update_client_current_task(data['client'], None, None)
                        # Set client back to online
                        database.update_client_heartbeat_by_name(data['client'], ClientStatus.ONLINE)

            # Check if all tasks are completed and update overall task status
            logger.debug(f"TASK_EXECUTION: Checking task completion for task {task_id}")

            # Notify result collector about Task completion
            if result_collector and data['status'] in ['completed', 'failed']:
                result_collector.on_run_completion(
                    job_id=task_id,
                    client_name=data['client'],
                    task_name=data['task_name'],
                    task_status=JobStatus(data['status']),
                    result=data.get('result'),
                    error_message=data.get('error_message'),
                    execution_time=data.get('execution_time')
                )
            else:
                # Fallback to original completion check
                check_and_update_task_completion(task_id)

            logger.info(f"DEBUG: Finished processing Task completion for task {task_id}")

            # Broadcast task run status update
            socketio.emit('subtask_updated', {
                'task_id': task_id,
                'run_task_id': run.task_id,
                'task_name': data['task_name'],
                'client': data['client'],
                'status': data['status'],
                'result': data.get('result'),
                'error_message': data.get('error_message'),
                'execution_time': data.get('execution_time')
            })

            return jsonify({
                'success': True,
                'data': run.to_dict()
            })

        except Exception as e:
            logger.error(f"Update Task run failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # Task Types API
    @api.route('/tasks', methods=['GET'])
    def get_available_tasks():
        """Get all available task types"""
        try:
            tasks = list_tasks()
            task_info = []

            for task_name in tasks:
                task_instance = get_task(task_name)
                if task_instance:
                    # Get description from instance method
                    description = task_instance.get_description() or "No description available"
                    task_info.append({
                        'name': task_name,
                        'description': description.strip(),
                        'function': task_name  # Use the name instead of function name
                    })

            return jsonify({
                'success': True,
                'data': task_info,
                'count': len(task_info)
            })
        except Exception as e:
            logger.error(f"Get available tasks failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<string:task_name>/execute', methods=['POST'])
    def execute_task_api(task_name):
        """Execute a specific Task"""
        try:
            # Get any parameters from request body
            data = request.get_json() or {}
            args = data.get('args', [])
            kwargs = data.get('kwargs', {})

            # Execute the Task
            result = execute_task(task_name, *args, **kwargs)

            return jsonify({
                'success': result['success'],
                'data': result['result'],
                'error': result['error']
            })
        except Exception as e:
            logger.error(f"Execute Task {task_name} failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<string:task_name>/info', methods=['GET'])
    def get_task_info(task_name):
        """Get information about a specific Task"""
        try:
            task_func = get_task(task_name)
            if not task_func:
                return jsonify({
                    'success': False,
                    'error': f'Task "{task_name}" not found'
                }), 404

            # Get detailed information about the Task
            info = {
                'name': task_name,
                'function': task_func.__class__.__name__,
                'description': task_func.get_description(),
                'module': task_func.__class__.__module__,
            }

            # Try to get function signature if available
            try:
                import inspect
                # For class instances, inspect the run method
                run_method = getattr(task_func, 'run', None)
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
            logger.error(f"Get Task info for {task_name} failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<task_name>/test', methods=['POST'])
    def test_task(task_name):
        """Test a Task run (for debugging)"""
        try:
            from common.tasks import execute_task

            # Get args and kwargs from request
            data = request.get_json() or {}
            args = data.get('args', [])
            kwargs = data.get('kwargs', {})

            # Execute Task
            result = execute_task(task_name, *args, **kwargs)

            return jsonify({
                'success': True,
                'data': result
            })
        except Exception as e:
            logger.error(f"Test Task {task_name} failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # Client Management API
    @api.route('/clients', methods=['GET'])
    def get_clients():
        """Get all clients with cached status (no live connectivity checks)"""
        try:
            clients = database.get_all_clients()

            # Build a task name lookup in one query instead of N separate queries
            task_ids = set(c.current_task_id for c in clients if c.current_task_id)
            task_names = {}
            if task_ids:
                all_tasks = database.get_all_jobs()
                task_names = {t.id: t.name for t in all_tasks}

            enhanced_clients = []
            for client in clients:
                client_dict = client.to_dict()
                client_dict['current_task_name'] = task_names.get(client.current_task_id) if client.current_task_id else None
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

    # Task run API
    @api.route('/execute', methods=['POST'])
    def execute_task():
        """Receive task run request"""
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
            task = database.get_job(task_id)
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

            # Update task status to running (only if still pending)
            if task.status == JobStatus.PENDING:
                task.status = JobStatus.RUNNING
                task.started_at = datetime.now()
                database.update_job(task)

            # Enhanced logging for task scheduling to client
            logger.info(f"TASK_SCHEDULING: Task {task_id} '{task.name}' scheduled to client '{client_name}' ({client_ip})")
            logger.info(f"TASK_SCHEDULING: Task details - tasks: {len(task.tasks) if task.tasks else 0}, Status: {task.status.value}")
            if task.tasks:
                for i, td in enumerate(task.tasks):
                    logger.debug(f"TASK_SCHEDULING: Task {task_id} Task {i+1}: '{td.name}' -> '{td.client}'")

            # Broadcast task start run event
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
        """Receive task run result"""
        try:
            data = request.get_json()
            task_id = data.get('task_id')
            client_name = data.get('client_name')  # Use client name as primary identifier
            client_ip = data.get('client_ip', 'Unknown')  # IP as auxiliary information

            # Support both old and new result formats
            if 'task_results_list' in data:
                # New format with Task results
                result_data = data
                success = result_data.get('success', False)
                task_results_list = result_data.get('task_results_list', [])
                total_tasks = result_data.get('total_tasks', 0)
                successful_tasks = result_data.get('successful_tasks', 0)
                failed_tasks = result_data.get('failed_tasks', 0)
                error = result_data.get('error', '')
                exit_code = result_data.get('exit_code', 0)

                # Generate summary output from Task results
                output_parts = []
                if task_results_list:
                    output_parts.append(f"Task completed with {total_tasks} tasks: {successful_tasks} successful, {failed_tasks} failed\n")
                    for td in task_results_list:
                        output_parts.append(f"[Task {td.get('task_id')}: {td.get('task_name')}]")
                        output_parts.append(f"Success: {td.get('success')}")
                        if td.get('output'):
                            output_parts.append(f"Output: {td.get('output')}")
                        if td.get('error'):
                            output_parts.append(f"Error: {td.get('error')}")
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
            task = database.get_job(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            # Update JobStatus
            task.completed_at = datetime.now()
            if success:
                task.status = JobStatus.COMPLETED
                task.result = output
            else:
                task.status = JobStatus.FAILED
                task.error_message = error

            database.update_job(task)

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

    @api.route('/task_result', methods=['POST'])
    def submit_TASK_result():
        """Receive Task run result"""
        try:
            data = request.get_json()
            task_id = data.get('task_id')
            client_name = data.get('client_name')  # Use client name as primary identifier
            client_ip = data.get('client_ip', 'Unknown')  # IP as auxiliary information
            task_result = data.get('task_result', {})

            if not task_id:
                return jsonify({
                    'success': False,
                    'error': 'Task ID cannot be empty'
                }), 400

            if not task_result:
                return jsonify({
                    'success': False,
                    'error': 'Task result cannot be empty'
                }), 400

            # Get task to verify it exists
            task = database.get_job(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            # Broadcast Task completion event to connected clients
            socketio.emit('task_completed', {
                'task_id': task_id,
                'client_ip': client_ip,
                'client_name': client_name,
                'task_result': task_result
            })

            logger.info(f"Received Task result for task {task_id}, Task {task_result.get('task_id')}")

            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Failed to submit Task result: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # Report Generation and Email Notification API
    @api.route('/jobs/<int:task_id>/generate-report', methods=['POST'])
    def generate_task_report(task_id):
        """Generate HTML report for a specific task"""
        try:
            if not result_collector:
                return jsonify({
                    'success': False,
                    'error': 'Result collector not available'
                }), 503

            force = request.args.get('force', 'false').lower() == 'true'
            report_path = result_collector.generate_report_for_job(task_id, force=force)

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

    @api.route('/jobs/<int:task_id>/send-notification', methods=['POST'])
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

    @api.route('/tasks/definitions', methods=['GET'])
    def get_TASK_definitions():
        """Get task definitions with result specifications"""
        try:
            from common.tasks import list_tasks, get_task

            # Build definitions using the new class-based system
            result = {}
            for task_name in list_tasks():
                task_instance = get_task(task_name)
                if task_instance:
                    description = task_instance.get_description()
                    result[task_name] = {
                        'description': description,
                        'result_definition': {
                            'name': task_name,
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
            logger.error(f"Get task definitions failed: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/tasks/reload', methods=['POST'])
    def reload_tasks_endpoint():
        """Reload all task modules to pick up changes without restarting the service"""
        try:
            from common.tasks import reload_tasks

            # reload tasks on server
            reloaded_count = reload_tasks()

            # Get client name from request (optional - if not specified, broadcast to all)
            data = request.get_json() or {}
            client_name = data.get('client_name')

            # Send reload request to client(s) via SocketIO
            if client_name:
                # Send to specific client
                socketio.emit('reload_tasks', {'client_name': client_name})
                logger.info(f"Sent task reload request to client: {client_name}")
                target_info = f"client '{client_name}'"
            else:
                # Broadcast to all clients
                socketio.emit('reload_tasks', {'client_name': None})
                logger.info("Sent task reload request to all clients")
                target_info = "all clients"

            logger.info(f"Server tasks reloaded via API: {reloaded_count} modules")

            return jsonify({
                'success': True,
                'message': f'Successfully reloaded {reloaded_count} task modules on server and sent reload request to {target_info}',
                'reloaded_count': reloaded_count,
                'target': target_info
            })

        except Exception as e:
            logger.error(f"reload tasks failed: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

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
        Check if all tasks are completed and update overall task status

        Args:
            task_id: ID of the task to check
        """
        try:
            # Get task and its tasks
            task = database.get_job(task_id)
            if not task or not task.tasks:
                logger.warning(f"TASK_COMPLETION: Task {task_id} not found or has No tasks")
                return

            # Get all Task runs for this task
            runs = database.get_runs(task_id)
            logger.debug(f"TASK_COMPLETION: Found {len(runs)} Task runs for task {task_id}")

            # Create a map of executed tasks
            execution_map = {}
            for r in runs:
                key = f"{r.task_name}_{r.client}"
                execution_map[key] = r

            # Check completion status
            total_tasks_count = len(task.tasks)
            completed_count = 0
            failed_count = 0

            for td in task.tasks:
                key = f"{td.name}_{td.client}"
                run = execution_map.get(key)

                if run:
                    if run.status == JobStatus.COMPLETED:
                        completed_count += 1
                    elif run.status == JobStatus.FAILED:
                        failed_count += 1

            # Determine if task is complete
            all_finished = (completed_count + failed_count) == total_tasks_count

            logger.info(f"TASK_COMPLETION: Task {task_id} '{td.name}' - Progress: {completed_count}/{total_tasks_count} completed, {failed_count} failed")

            if all_finished and task.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
                # Update task status
                task.completed_at = datetime.now()

                if failed_count > 0:
                    task.status = JobStatus.FAILED
                    task.error_message = f"{failed_count} out of {total_tasks_count} tasks failed"
                    logger.warning(f"TASK_COMPLETION: Task {task_id} '{td.name}' FAILED - {failed_count}/{total_tasks_count} tasks failed")
                else:
                    task.status = JobStatus.COMPLETED
                    task.result = f"All {total_tasks_count} tasks completed successfully"
                    logger.info(f"TASK_COMPLETION: Task {task_id} '{td.name}' COMPLETED successfully")

                database.update_job(task)

                # Clear current task from all clients
                clients = task.get_all_clients()
                for client_name in clients:
                    database.update_client_current_task(client_name, None, None)
                    database.update_client_heartbeat_by_name(client_name, ClientStatus.ONLINE)

                # Broadcast task completion
                socketio.emit('task_completed', {
                    'task_id': task_id,
                    'status': task.status.value,
                    'success': task.status == JobStatus.COMPLETED,
                    'completed_at': task.completed_at.isoformat(),
                    'total_tasks': total_tasks_count,
                    'completed_tasks': completed_count,
                    'failed_tasks': failed_count,
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
            task_id = data.get('task_id')

            success = database.update_client_current_task(client_name, task_id, task_id)

            return jsonify({
                'success': success,
                'message': f"Updated client '{client_name}' current task to {task_id}, Task {task_id}"
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

    # Cached Results API

    @api.route('/clients/<client_name>/reload-tasks', methods=['POST'])
    def reload_client_tasks(client_name):
        """Send reload-tasks command to a specific client via SocketIO"""
        try:
            client = database.get_client_by_name(client_name)
            if not client:
                return jsonify({'success': False, 'error': f'Client {client_name} not found'}), 404

            room_name = f"client_{client.ip_address.replace('.', '_')}"
            socketio.emit('reload_tasks', {'client_name': client_name}, room=room_name)
            logger.info(f"Sent reload_tasks to client '{client_name}' (room: {room_name})")

            return jsonify({'success': True, 'message': f'Reload command sent to {client_name}'})
        except Exception as e:
            logger.error(f"Failed to send reload to {client_name}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/results', methods=['GET'])
    def get_cached_results():
        """Get cached task results with optional filtering"""
        try:
            job_id = request.args.get('job_id', type=int)
            client_name = request.args.get('client_name')
            task_name = request.args.get('task_name')
            limit = request.args.get('limit', 100, type=int)

            results = database.get_cached_results(
                job_id=job_id,
                client_name=client_name,
                task_name=task_name,
                limit=limit
            )

            return jsonify({
                'success': True,
                'data': results,
                'count': len(results)
            })
        except Exception as e:
            logger.error(f"Failed to get cached results: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/results/<int:result_id>', methods=['GET'])
    def get_cached_result(result_id):
        """Get a single cached result by ID"""
        try:
            result = database.get_cached_result_by_id(result_id)
            if not result:
                return jsonify({
                    'success': False,
                    'error': 'Result not found'
                }), 404

            return jsonify({
                'success': True,
                'data': result
            })
        except Exception as e:
            logger.error(f"Failed to get cached result: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/results/<int:result_id>/ai-report', methods=['POST'])
    def generate_ai_report(result_id):
        """Generate an AI test benchmark report using compare-results.js"""
        try:
            import subprocess
            import shutil

            result = database.get_cached_result_by_id(result_id)
            if not result:
                return jsonify({'success': False, 'error': 'Result not found'}), 404

            if result.get('task_name') != 'ai_test':
                return jsonify({'success': False, 'error': 'Not an ai_test result'}), 400

            # Parse the result data to get run_id
            result_data = result.get('result')
            if not result_data:
                return jsonify({'success': False, 'error': 'No result data'}), 400

            parsed = json.loads(result_data) if isinstance(result_data, str) else result_data
            run_id = parsed.get('run_id')

            # Fallback: extract run_id from stdout if not set
            if not run_id:
                import re
                stdout = parsed.get('stdout', '')
                # Look for "Results:     D:\...\20260317033901" pattern
                match = re.search(r'Results:\s+\S+[/\\](\d{14})', stdout)
                if match:
                    run_id = match.group(1)

            if not run_id:
                return jsonify({'success': False, 'error': 'No run_id found in result data or stdout'}), 400

            # Use ai_test_path from the result data (where the client ran it),
            # falling back to the local server's resolved path
            ai_test_path = parsed.get('ai_test_path')
            if not ai_test_path or not os.path.isdir(ai_test_path):
                import importlib
                ai_test_module = importlib.import_module('common.tasks.ai-test')
                ai_test_path = ai_test_module._resolve_ai_test_path()

            script_path = os.path.join(ai_test_path, 'scripts', 'compare-results.js')
            if not os.path.isfile(script_path):
                return jsonify({'success': False, 'error': 'compare-results.js not found'}), 500

            # Find node
            node = shutil.which('node')
            if not node:
                return jsonify({'success': False, 'error': 'Node.js not found'}), 500

            # Generate report to a temp file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w') as tmp:
                output_path = tmp.name

            try:
                proc = subprocess.run(
                    [node, script_path, run_id, '-o', output_path],
                    cwd=ai_test_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if proc.returncode != 0:
                    return jsonify({
                        'success': False,
                        'error': f'compare-results.js failed: {proc.stderr or proc.stdout}'
                    }), 500

                with open(output_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()

                return jsonify({'success': True, 'html': html_content})

            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)

        except Exception as e:
            logger.error(f"Failed to generate AI report: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/results/client/<client_name>', methods=['GET'])
    def get_client_results(client_name):
        """Get all cached results for a specific client"""
        try:
            task_name = request.args.get('task_name')
            limit = request.args.get('limit', 50, type=int)

            results = database.get_cached_results(
                client_name=client_name,
                task_name=task_name,
                limit=limit
            )

            return jsonify({
                'success': True,
                'data': results,
                'count': len(results)
            })
        except Exception as e:
            logger.error(f"Failed to get results for client {client_name}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/results/client/<client_name>/latest', methods=['GET'])
    def get_client_latest_result(client_name):
        """Get the latest cached result for a specific client"""
        try:
            task_name = request.args.get('task_name')

            result = database.get_latest_result_for_client(
                client_name=client_name,
                task_name=task_name
            )

            if not result:
                return jsonify({
                    'success': False,
                    'error': f'No results found for client {client_name}'
                }), 404

            return jsonify({
                'success': True,
                'data': result
            })
        except Exception as e:
            logger.error(f"Failed to get latest result for client {client_name}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # --- Results Comparison API ---

    @api.route('/results/compare', methods=['POST'])
    def compare_results():
        """Compare multiple cached results and return chart-ready data.

        Expects JSON body: { "result_ids": [1, 2, 3] }
        Returns normalized series for TTFT, prefill TPS, generation TPS charts.
        """
        try:
            data = request.get_json()
            result_ids = data.get('result_ids', [])

            if len(result_ids) < 1:
                return jsonify({'success': False, 'error': 'At least 1 result required'}), 400

            loaded = []
            for rid in result_ids:
                r = database.get_cached_result_by_id(rid)
                if not r:
                    continue
                # Parse the JSON result string
                result_data = r.get('result')
                if isinstance(result_data, str):
                    try:
                        result_data = json.loads(result_data)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if not isinstance(result_data, dict):
                    continue
                loaded.append({
                    'id': rid,
                    'task_name': r.get('task_name', ''),
                    'client_name': r.get('client_name', ''),
                    'task_name': r.get('task_name', ''),
                    'completed_at': r.get('completed_at', ''),
                    'result': result_data,
                })

            if not loaded:
                return jsonify({'success': False, 'error': 'No valid results with benchmark data'}), 400

            # Normalize into chart series (same logic as compare-results.js)
            series = []
            for item in loaded:
                result = item['result']
                bench_results = result.get('results', [])
                if not bench_results:
                    continue

                # Detect source type
                source = 'unknown'
                if result.get('llamacpp_available') or item['task_name'] == 'ai_test':
                    source = 'llamacpp'
                inner_results = result.get('results', bench_results)
                if isinstance(inner_results, dict) and 'results' in inner_results:
                    inner_results = inner_results['results']

                for r in inner_results:
                    if not isinstance(r, dict) or r.get('error'):
                        continue

                    if source == 'llamacpp':
                        config_label = f"{r.get('model', '?')} / {r.get('backend', '?')} (llama.cpp)"
                    else:
                        config_label = f"{r.get('model', '?')} / {source}"

                    series_key = f"{item['id']}|{config_label}"
                    s = next((x for x in series if x['key'] == series_key), None)
                    if not s:
                        run_label = item['client_name']
                        if item['completed_at']:
                            run_label += f" @ {item['completed_at'][:19]}"
                        s = {
                            'key': series_key,
                            'label': f"{config_label} [{run_label}]",
                            'shortLabel': config_label,
                            'resultId': item['id'],
                            'clientName': item['client_name'],
                            'points': [],
                        }
                        series.append(s)

                    s['points'].append({
                        'pl': r.get('pl') or r.get('pp'),
                        'ttftMs': r.get('ttftMs'),
                        'tgTs': r.get('tgTs'),
                        'plTs': r.get('plTs') or r.get('ppTs'),
                        'e2eMs': r.get('e2eMs'),
                    })

            # Sort points within each series
            for s in series:
                s['points'].sort(key=lambda p: p.get('pl') or 0)

            # Collect all unique prompt lengths
            all_pls = sorted(set(
                p.get('pl') for s in series for p in s['points'] if p.get('pl') is not None
            ))

            return jsonify({
                'success': True,
                'data': {
                    'series': series,
                    'promptLengths': all_pls,
                    'resultCount': len(loaded),
                }
            })

        except Exception as e:
            logger.error(f"Results comparison failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # --- Repo Update Command API ---

    @api.route('/clients/<client_name>/update-repo', methods=['POST'])
    def update_client_repo(client_name):
        """Send a command to a client to update (git pull) a repository via WebSocket."""
        try:
            client = database.get_client_by_name(client_name)
            if not client:
                return jsonify({'success': False, 'error': f'Client {client_name} not found'}), 404

            if client.status.value == 'offline':
                return jsonify({'success': False, 'error': f'Client {client_name} is offline'}), 400

            data = request.get_json() or {}
            repo_path = data.get('repo_path', '')  # Path on the client machine

            # Send command via WebSocket to the client's room
            room_name = f"client_{client.ip_address.replace('.', '_')}"
            socketio.emit('repo_update', {
                'client_name': client_name,
                'repo_path': repo_path,
            }, room=room_name)

            logger.info(f"Repo update command sent to {client_name} (room: {room_name})")

            return jsonify({
                'success': True,
                'message': f'Repo update command sent to {client_name}',
            })

        except Exception as e:
            logger.error(f"Repo update failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    return api

