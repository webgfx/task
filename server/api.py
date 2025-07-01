"""
REST API interfaces
"""
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_socketio import emit

from common.models import Task, Machine, TaskStatus, MachineStatus, SubtaskDefinition
from common.utils import parse_datetime, validate_cron_expression
from common.predefined_commands import predefined_command_manager
from common.subtasks import list_subtasks, get_subtask

logger = logging.getLogger(__name__)

def create_api_blueprint(database, socketio):
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
        """Create new task with support for subtasks and multiple machines"""
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

                    if not subtask_data.get('target_machine'):
                        return jsonify({
                            'success': False,
                            'error': f'Subtask {i+1}: target_machine is required'
                        }), 400

                    # Check if subtask exists in registry
                    if not get_subtask(subtask_data['name']):
                        return jsonify({
                            'success': False,
                            'error': f'Subtask {i+1}: "{subtask_data["name"]}" is not a valid subtask. Available subtasks: {list_subtasks()}'
                        }), 400

                    subtask = SubtaskDefinition(
                        name=subtask_data['name'],
                        target_machine=subtask_data['target_machine'],
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
            target_machines = data.get('target_machines', [])
            if not target_machines and data.get('target_machine'):
                target_machines = [data.get('target_machine')]

            # 如果使用subtasks，从subtasks中提取所有目标机器
            if subtasks:
                subtask_machines = list(set(s.target_machine for s in subtasks))
                target_machines.extend(subtask_machines)
                target_machines = list(set(target_machines))  # Remove duplicates

            # Create task object
            task = Task(
                name=data['name'],
                command=data.get('command', ''),  # 保持向后兼容
                target_machines=target_machines,
                commands=data.get('commands', []),
                execution_order=data.get('execution_order', []),
                subtasks=subtasks,
                schedule_time=parse_datetime(data.get('schedule_time')),
                cron_expression=cron_expr,
                target_machine=data.get('target_machine'),  # 保持向后兼容
                max_retries=3  # Default value, not configurable from UI
            )

            # Save to database
            task_id = database.create_task(task)
            task.id = task_id

            # Broadcast new task creation event
            socketio.emit('task_created', task.to_dict())

            if subtasks:
                logger.info(f"Created task: {task.name} with {len(subtasks)} subtasks for {len(target_machines)} machines")
            else:
                logger.info(f"Created task: {task.name} with {len(task.commands)} commands for {len(target_machines)} machines")

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
            if 'target_machines' in data:
                task.target_machines = data['target_machines']
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
            if 'target_machine' in data:
                task.target_machine = data['target_machine']
            if 'max_retries' in data:
                task.max_retries = data['max_retries']

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
        """Delete task"""
        try:
            task = database.get_task(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            database.delete_task(task_id)

            # Broadcast task deletion event
            socketio.emit('task_deleted', {'id': task_id})

            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Delete taskFailed: {e}")
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

    @api.route('/tasks/<int:task_id>/subtask-executions/<machine_name>', methods=['GET'])
    def get_subtask_executions_by_machine(task_id, machine_name):
        """Get subtask execution records for a specific task and machine"""
        try:
            executions = database.get_subtask_executions_by_machine(task_id, machine_name)
            return jsonify({
                'success': True,
                'data': [exec.to_dict() for exec in executions]
            })
        except Exception as e:
            logger.error(f"Get subtask execution records by machine failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/tasks/<int:task_id>/subtask-executions', methods=['POST'])
    def update_subtask_execution(task_id):
        """Update subtask execution status (called by client)"""
        try:
            data = request.get_json()

            # Validate required fields
            required_fields = ['subtask_name', 'target_machine', 'status']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }), 400

            # Find or create subtask execution record
            executions = database.get_subtask_executions_by_machine(task_id, data['target_machine'])
            execution = None

            for exec in executions:
                if exec.subtask_name == data['subtask_name'] and exec.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    execution = exec
                    break

            if not execution:
                # Create new execution record
                from common.models import SubtaskExecution
                execution = SubtaskExecution(
                    task_id=task_id,
                    subtask_name=data['subtask_name'],
                    subtask_order=data.get('order', 0),
                    target_machine=data['target_machine'],
                    status=TaskStatus(data['status'])
                )
                execution.id = database.create_subtask_execution(execution)

            # Update execution status
            execution.status = TaskStatus(data['status'])
            execution.result = data.get('result')
            execution.error_message = data.get('error_message')
            execution.execution_time = data.get('execution_time')

            if data['status'] in ['completed', 'failed']:
                execution.completed_at = datetime.now()

            database.update_subtask_execution(execution)

            # Broadcast subtask status update
            socketio.emit('subtask_updated', {
                'task_id': task_id,
                'subtask_name': data['subtask_name'],
                'target_machine': data['target_machine'],
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

    # 预定义指令管理API
    @api.route('/predefined-commands', methods=['GET'])
    def get_predefined_commands():
        """获取所有预定义指令"""
        try:
            # 获取查询参数
            category = request.args.get('category')
            target_os = request.args.get('target_os')
            search = request.args.get('search')

            if search:
                commands = predefined_command_manager.search_commands(search)
            elif category:
                commands = predefined_command_manager.get_commands_by_category(category)
            elif target_os:
                commands = predefined_command_manager.get_commands_by_os(target_os)
            else:
                commands = predefined_command_manager.get_all_commands()

            return jsonify({
                'success': True,
                'data': [cmd.to_dict() for cmd in commands],
                'categories': predefined_command_manager.get_categories()
            })
        except Exception as e:
            logger.error(f"Get predefined commands failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/predefined-commands', methods=['POST'])
    def create_predefined_command():
        """创建新的预定义指令"""
        try:
            data = request.get_json()

            if not data.get('name') or not data.get('command'):
                return jsonify({
                    'success': False,
                    'error': 'Command name and command text cannot be empty'
                }), 400

            from common.predefined_commands import PredefinedCommand
            command = PredefinedCommand(
                id=data.get('id', 0),  # 0 will auto-generate
                name=data['name'],
                command=data['command'],
                description=data.get('description', ''),
                category=data.get('category', 'general'),
                timeout=data.get('timeout', 300),
                requires_admin=data.get('requires_admin', False),
                target_os=data.get('target_os', [])
            )

            command_id = predefined_command_manager.add_command(command)
            command.id = command_id

            return jsonify({
                'success': True,
                'data': command.to_dict()
            }), 201

        except Exception as e:
            logger.error(f"Create predefined command failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/predefined-commands/<int:command_id>', methods=['GET'])
    def get_predefined_command(command_id):
        """获取指定的预定义指令"""
        try:
            command = predefined_command_manager.get_command(command_id)
            if not command:
                return jsonify({
                    'success': False,
                    'error': 'Command does not exist'
                }), 404

            return jsonify({
                'success': True,
                'data': command.to_dict()
            })
        except Exception as e:
            logger.error(f"Get predefined command failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/predefined-commands/<int:command_id>', methods=['PUT'])
    def update_predefined_command(command_id):
        """更新预定义指令"""
        try:
            command = predefined_command_manager.get_command(command_id)
            if not command:
                return jsonify({
                    'success': False,
                    'error': 'Command does not exist'
                }), 404

            data = request.get_json()

            # 更新字段
            if 'name' in data:
                command.name = data['name']
            if 'command' in data:
                command.command = data['command']
            if 'description' in data:
                command.description = data['description']
            if 'category' in data:
                command.category = data['category']
            if 'timeout' in data:
                command.timeout = data['timeout']
            if 'requires_admin' in data:
                command.requires_admin = data['requires_admin']
            if 'target_os' in data:
                command.target_os = data['target_os']

            predefined_command_manager.update_command(command)

            return jsonify({
                'success': True,
                'data': command.to_dict()
            })

        except Exception as e:
            logger.error(f"Update predefined command failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/predefined-commands/<int:command_id>', methods=['DELETE'])
    def delete_predefined_command(command_id):
        """删除预定义指令"""
        try:
            command = predefined_command_manager.get_command(command_id)
            if not command:
                return jsonify({
                    'success': False,
                    'error': 'Command does not exist'
                }), 404

            predefined_command_manager.delete_command(command_id)

            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Delete predefined command failed: {e}")
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
                    doc = subtask_func.__doc__ or f"Subtask: {subtask_name}"
                    subtask_info.append({
                        'name': subtask_name,
                        'description': doc.strip().split('\n')[0] if doc else f"Subtask: {subtask_name}",
                        'full_doc': doc.strip() if doc else None
                    })

            return jsonify({
                'success': True,
                'data': subtask_info
            })
        except Exception as e:
            logger.error(f"Get subtasks failed: {e}")
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

    # Machine ManagementAPI
    @api.route('/machines', methods=['GET'])
    def get_machines():
        """Get all machines"""
        try:
            machines = database.get_all_machines()
            return jsonify({
                'success': True,
                'data': [machine.to_dict() for machine in machines]
            })
        except Exception as e:
            logger.error(f"Get machine listFailed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/machines/register', methods=['POST'])
    def register_machine():
        """Register machines with system information (using machine name as primary identifier)"""
        try:
            data = request.get_json()

            if not data.get('name') or not data.get('ip_address'):
                return jsonify({
                    'success': False,
                    'error': 'Machine name and IP address cannot be empty'
                }), 400

            # 检查是否已存在相同名称或IP的机器
            existing_machine_by_name = database.get_machine_by_name(data['name'])
            existing_machine_by_ip = database.get_machine_by_ip(data['ip_address'])

            # 如果存在同名但不同IP的机器，返回错误
            if existing_machine_by_name and existing_machine_by_name.ip_address != data['ip_address']:
                return jsonify({
                    'success': False,
                    'error': f'Machine name "{data["name"]}" already exists with different IP address'
                }), 400

            # 使用现有机器记录（如果存在）或创建新记录
            existing_machine = existing_machine_by_name or existing_machine_by_ip

            machine = Machine(
                name=data['name'],
                ip_address=data['ip_address'],
                port=data.get('port', 8080),
                status=MachineStatus.ONLINE,
                capabilities=data.get('capabilities', []),
                # System information
                cpu_info=data.get('cpu_info'),
                memory_info=data.get('memory_info'),
                gpu_info=data.get('gpu_info'),
                os_info=data.get('os_info'),
                disk_info=data.get('disk_info'),
                system_summary=data.get('system_summary')
            )

            database.register_machine(machine)

            # Log machine registration
            client_ip = request.environ.get('REMOTE_ADDR', data['ip_address'])
            if existing_machine:
                database.log_client_action(
                    client_ip=machine.ip_address,
                    client_name=machine.name,
                    action='MACHINE_UPDATE',
                    message=f"Machine {machine.name} updated registration",
                    data={
                        'system_summary': machine.system_summary,
                        'capabilities': machine.capabilities
                    }
                )
            else:
                database.log_client_action(
                    client_ip=machine.ip_address,
                    client_name=machine.name,
                    action='MACHINE_REGISTER',
                    message=f"New machine {machine.name} registered",
                    data={
                        'system_summary': machine.system_summary,
                        'capabilities': machine.capabilities
                    }
                )

            # Log system information for debugging
            if machine.system_summary:
                if existing_machine:
                    logger.info(f"Updated existing machine {machine.name} ({machine.ip_address}):")
                else:
                    logger.info(f"Registered new machine {machine.name} ({machine.ip_address}):")
                logger.info(f"  CPU: {machine.system_summary.get('cpu', 'Unknown')}")
                logger.info(f"  Memory: {machine.system_summary.get('memory', 'Unknown')}")
                logger.info(f"  GPU: {machine.system_summary.get('gpu', 'Unknown')}")
                logger.info(f"  OS: {machine.system_summary.get('os', 'Unknown')}")

            # Broadcast machine registration event
            socketio.emit('machine_registered', machine.to_dict())

            return jsonify({
                'success': True,
                'data': machine.to_dict()
            }), 201

        except Exception as e:
            logger.error(f"Registered machinesFailed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/machines/update_config', methods=['POST'])
    def update_machine_config():
        """Update machine configuration information"""
        try:
            data = request.get_json()
            machine_name = data.get('name')
            ip_address = data.get('ip_address')

            # 优先使用机器名，向后兼容IP地址
            if machine_name:
                existing_machine = database.get_machine_by_name(machine_name)
                if not existing_machine:
                    return jsonify({
                        'success': False,
                        'error': f'Machine "{machine_name}" not found'
                    }), 404
            elif ip_address:
                existing_machine = database.get_machine_by_ip(ip_address)
                if not existing_machine:
                    return jsonify({
                        'success': False,
                        'error': 'Machine not found'
                    }), 404
            else:
                return jsonify({
                    'success': False,
                    'error': 'Machine name or IP address is required'
                }), 400

            # 更新机器信息
            machine = Machine(
                name=data.get('name', existing_machine.name),
                ip_address=data.get('ip_address', existing_machine.ip_address),
                port=data.get('port', existing_machine.port),
                status=existing_machine.status,  # 保持现有状态
                capabilities=data.get('capabilities', existing_machine.capabilities),
                # 更新系统信息
                cpu_info=data.get('cpu_info'),
                memory_info=data.get('memory_info'),
                gpu_info=data.get('gpu_info'),
                os_info=data.get('os_info'),
                disk_info=data.get('disk_info'),
                system_summary=data.get('system_summary')
            )

            database.update_machine_config(machine)

            # Log updated system information
            if machine.system_summary:
                logger.info(f"Updated machine config for {machine.name} ({machine.ip_address}):")
                logger.info(f"  CPU: {machine.system_summary.get('cpu', 'Unknown')}")
                logger.info(f"  Memory: {machine.system_summary.get('memory', 'Unknown')}")
                logger.info(f"  GPU: {machine.system_summary.get('gpu', 'Unknown')}")
                logger.info(f"  OS: {machine.system_summary.get('os', 'Unknown')}")

            # Broadcast machine update event
            socketio.emit('machine_config_updated', machine.to_dict())

            return jsonify({
                'success': True,
                'data': machine.to_dict()
            })

        except Exception as e:
            logger.error(f"Update machine config failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/machines/unregister', methods=['POST'])
    def unregister_machine():
        """Unregister machine using machine name as primary identifier"""
        try:
            data = request.get_json()
            machine_name = data.get('name')
            ip_address = data.get('ip_address')  # 向后兼容

            # 优先使用机器名，如果没有则使用IP
            if machine_name:
                # 通过机器名注销
                database.update_machine_heartbeat_by_name(machine_name, MachineStatus.OFFLINE)

                # 获取机器信息用于广播
                machine = database.get_machine_by_name(machine_name)
                actual_ip = machine.ip_address if machine else (ip_address or 'unknown')
            elif ip_address:
                # 向后兼容：通过IP注销
                database.update_machine_heartbeat(ip_address, MachineStatus.OFFLINE)
                actual_ip = ip_address
                machine_name = data.get('name', 'Unknown')
            else:
                return jsonify({
                    'success': False,
                    'error': 'Machine name or IP address is required'
                }), 400

            # Broadcast machine unregistration event
            socketio.emit('machine_unregistered', {
                'ip_address': actual_ip,
                'machine_name': machine_name,
                'status': 'offline',
                'timestamp': datetime.now().isoformat()
            })

            logger.info(f"Machine unregistered: {machine_name} ({actual_ip})")

            return jsonify({
                'success': True,
                'message': f'Machine {machine_name} unregistered successfully'
            })

        except Exception as e:
            logger.error(f"Unregister machine failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/machines/heartbeat', methods=['POST'])
    def machine_heartbeat():
        """Machine heartbeat using machine name as primary identifier"""
        try:
            data = request.get_json()
            machine_name = data.get('machine_name')
            status = data.get('status', 'online')

            if not machine_name:
                return jsonify({
                    'success': False,
                    'error': 'Machine name cannot be empty'
                }), 400

            # Update heartbeat using machine name
            machine_status = MachineStatus(status) if status else MachineStatus.ONLINE
            database.update_machine_heartbeat_by_name(machine_name, machine_status)

            # Get machine info for broadcast (optional)
            machine = database.get_machine_by_name(machine_name)
            ip_address = machine.ip_address if machine else 'unknown'

            # Broadcast heartbeat event
            socketio.emit('machine_heartbeat', {
                'ip_address': ip_address,
                'machine_name': machine_name,
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
            machine_name = data.get('machine_name')  # 使用机器名作为主要标识
            machine_ip = data.get('machine_ip')  # IP作为辅助信息

            if not task_id or not machine_name:
                return jsonify({
                    'success': False,
                    'error': 'Task ID and machine name cannot be empty'
                }), 400

            # Get task
            task = database.get_task(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': 'Task does not exist'
                }), 404

            # Get machine info by name
            machine = database.get_machine_by_name(machine_name)
            if not machine:
                return jsonify({
                    'success': False,
                    'error': f'Machine "{machine_name}" not found'
                }), 404

            # Use machine's IP if not provided
            if not machine_ip:
                machine_ip = machine.ip_address

            # Update task status to running
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            database.update_task(task)

            # Broadcast task start execution event
            socketio.emit('task_started', {
                'task_id': task_id,
                'machine_ip': machine_ip,
                'machine_name': machine_name,
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
            machine_name = data.get('machine_name')  # 使用机器名作为主要标识
            machine_ip = data.get('machine_ip', 'Unknown')  # IP作为辅助信息

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
                'machine_ip': machine_ip,
                'machine_name': machine_name,
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
            machine_name = data.get('machine_name')  # 使用机器名作为主要标识
            machine_ip = data.get('machine_ip', 'Unknown')  # IP作为辅助信息
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
                'machine_ip': machine_ip,
                'machine_name': machine_name,
                'subtask_result': subtask_result
            })

            logger.info(f"Received subtask result for task {task_id}, subtask {subtask_result.get('subtask_id')}")

            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Failed to submit subtask result: {e}")
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

    @api.route('/machines/<machine_name>', methods=['GET'])
    def get_machine_by_name(machine_name):
        """Get machine by name (primary method)"""
        try:
            machine = database.get_machine_by_name(machine_name)
            if not machine:
                return jsonify({
                    'success': False,
                    'error': f'Machine "{machine_name}" not found'
                }), 404

            return jsonify({
                'success': True,
                'data': machine.to_dict()
            })
        except Exception as e:
            logger.error(f"Get machine by name failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/machines/<machine_name>', methods=['DELETE'])
    def delete_machine_by_name(machine_name):
        """Delete machine by name (primary method - machine names are unique)"""
        try:
            success = database.delete_machine(machine_name)
            if not success:
                return jsonify({
                    'success': False,
                    'error': f'Machine "{machine_name}" not found'
                }), 404

            # Broadcast machine deletion event
            socketio.emit('machine_deleted', {
                'machine_name': machine_name,
                'deleted_at': datetime.now().isoformat()
            })

            return jsonify({
                'success': True,
                'message': f'Machine "{machine_name}" deleted successfully'
            })

        except Exception as e:
            logger.error(f"Delete machine by name failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/machines/names', methods=['GET'])
    def get_machine_names():
        """Get all machine names"""
        try:
            # Check if only online machines are requested
            only_online = request.args.get('online', '').lower() == 'true'
            
            if only_online:
                machine_names = database.get_online_machine_names()
            else:
                machine_names = database.get_machine_names()
            
            return jsonify({
                'success': True,
                'data': machine_names
            })
        except Exception as e:
            logger.error(f"Get machine names failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @api.route('/machines/validate_name', methods=['POST'])
    def validate_machine_name():
        """Validate if machine name is available"""
        try:
            data = request.get_json()
            machine_name = data.get('name')
            
            if not machine_name:
                return jsonify({
                    'success': False,
                    'error': 'Machine name is required'
                }), 400
            
            # Check if name already exists
            exists = database.machine_name_exists(machine_name)
            
            return jsonify({
                'success': True,
                'data': {
                    'name': machine_name,
                    'available': not exists,
                    'exists': exists
                }
            })
            
        except Exception as e:
            logger.error(f"Validate machine name failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    return api
