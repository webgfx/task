/**
 * Task Management page JavaScript with Subtask Support
 */

console.log('Loading tasks.js...');

let allTasks = [];
let clientsList = [];
let availableSubtasks = [];
let filteredTasks = [];
let tasksCurrentPage = 1;
const tasksItemsPerPage = 10;

console.log('Tasks.js variables initialized');

// Initialize after page load
document.addEventListener('DOMContentLoaded', function() {
    initializeTasksPage();
    setupWebSocketListeners();
});

// Setup WebSocket listeners for real-time updates
function setupWebSocketListeners() {
    if (typeof socket !== 'undefined' && socket) {
        // Listen for subtask status updates
        socket.on('subtask_updated', function(data) {
            console.log('Subtask updated:', data);
            
            // Update task details view if it's open and matches this task
            const taskDetailModal = document.getElementById('taskDetailModal');
            if (taskDetailModal && taskDetailModal.style.display === 'block') {
                const currentTaskId = getCurrentTaskDetailId();
                if (currentTaskId && currentTaskId == data.task_id) {
                    refreshTaskDetails(data.task_id);
                }
            }
            
            // Refresh task list to update overall status
            if (typeof refreshTasks === 'function') {
                refreshTasks();
            }
            
            // Show notification for completion or failure
            if (data.status === 'completed') {
                showNotification('Subtask Completed', 
                    `Subtask "${data.subtask_name}" completed on client ${data.target_client}`, 'success');
            } else if (data.status === 'failed') {
                showNotification('Subtask Failed', 
                    `Subtask "${data.subtask_name}" failed on client ${data.target_client}`, 'error');
            }
        });
        
        // Listen for task status updates
        socket.on('task_completed', function(data) {
            console.log('Task completed:', data);
            
            // Update task details view if it's open and matches this task
            const taskDetailModal = document.getElementById('taskDetailModal');
            if (taskDetailModal && taskDetailModal.style.display === 'block') {
                const currentTaskId = getCurrentTaskDetailId();
                if (currentTaskId && currentTaskId == data.task_id) {
                    refreshTaskDetails(data.task_id);
                }
            }
        });
        
        // Listen for subtask deletion events
        socket.on('subtask_deleted', function(data) {
            console.log('Subtask deleted:', data);
            
            // Update task details view if it's open and matches this task
            const taskDetailModal = document.getElementById('taskDetailModal');
            if (taskDetailModal && taskDetailModal.style.display === 'block') {
                const currentTaskId = getCurrentTaskDetailId();
                if (currentTaskId && currentTaskId == data.task_id) {
                    refreshTaskDetails(data.task_id);
                }
            }
            
            // Refresh task list to show updated state
            if (typeof refreshTasks === 'function') {
                refreshTasks();
            }
            
            // Show notification
            showNotification('Subtask Deleted', 
                `Subtask "${data.subtask_name}" deleted from client ${data.target_client}`, 'info');
                
            // If all subtasks were deleted, show task cancellation notice
            if (data.remaining_subtasks === 0) {
                showNotification('Task Cancelled', 
                    'All subtasks were deleted - task has been cancelled', 'warning');
            }
        });
        
        // Listen for task deletion events
        socket.on('task_deleted', function(data) {
            console.log('Task deleted:', data);
            
            // Close task details modal if it's open for this task
            const taskDetailModal = document.getElementById('taskDetailModal');
            if (taskDetailModal && taskDetailModal.style.display === 'block') {
                const currentTaskId = getCurrentTaskDetailId();
                if (currentTaskId && currentTaskId == data.task_id) {
                    taskDetailModal.style.display = 'none';
                }
            }
            
            // Refresh task list to remove deleted task
            if (typeof refreshTasks === 'function') {
                refreshTasks();
            }
            
            // Show notification
            showNotification('Task Deleted', 
                `Task "${data.task_name}" has been deleted`, 'info');
        });
    }
}

// Initialize task page
async function initializeTasksPage() {
    await loadClients();
    await loadAvailableSubtasks();
    await refreshTasks();
    populateClientFilter();
    setupEventListeners();
}

// Setup event listeners
function setupEventListeners() {
    // Form submission
    document.getElementById('taskForm').addEventListener('submit', function(e) {
        e.preventDefault();
        saveTask();
    });

    // Modal close on outside click
    window.addEventListener('click', function(e) {
        const taskModal = document.getElementById('taskModal');
        const detailModal = document.getElementById('taskDetailModal');

        if (e.target === taskModal) {
            closeTaskModal();
        }
        if (e.target === detailModal) {
            closeTaskDetailModal();
        }
    });
}

// Load clients from server
async function loadClients() {
    try {
        const response = await apiGet('/api/clients');
        clientsList = response.data || [];
    } catch (error) {
        console.error('Failed to load clients:', error);
        showNotification('Failed to load clients', 'error');
    }
}

// Load available subtasks from server
async function loadAvailableSubtasks() {
    try {
        // Try to load enhanced subtask definitions first
        let response;
        try {
            response = await apiGet('/api/subtasks/definitions');
            if (response.success && response.data) {
                // Enhanced format with result definitions
                availableSubtasks = Object.keys(response.data).map(name => {
                    const def = response.data[name];
                    return {
                        name: name,
                        description: def.description,
                        result_definition: def.result_definition
                    };
                });
                console.log('Loaded enhanced subtask definitions:', availableSubtasks);
                return;
            }
        } catch (error) {
            console.warn('Enhanced subtasks endpoint not available, falling back to basic subtasks');
        }
        
        // Fallback to basic subtasks list
        response = await apiGet('/api/subtasks');
        if (response.success && response.data) {
            availableSubtasks = response.data.map(subtask => ({
                name: subtask.name,
                description: subtask.description || 'No description available',
                result_definition: null
            }));
        } else {
            availableSubtasks = [];
        }
        console.log('Loaded basic subtasks:', availableSubtasks);
    } catch (error) {
        console.error('Failed to load available subtasks:', error);
        showNotification('Error', 'Failed to load available subtasks', 'error');
        availableSubtasks = [];
    }
}

// Add a new subtask row
function addSubtask() {
    const subtasksList = document.getElementById('subtasksList');
    if (!subtasksList) {
        console.error('Could not find subtasksList element');
        return;
    }
    
    const subtaskIndex = subtasksList.children.length;

    const subtaskRow = document.createElement('div');
    subtaskRow.className = 'subtask-row';
    subtaskRow.innerHTML = `
        <div class="subtask-header">
            <h5>Subtask ${subtaskIndex + 1}</h5>
            <button type="button" class="btn btn-small btn-danger" onclick="removeSubtask(this)">
                <i class="fas fa-trash"></i> Remove
            </button>
        </div>
        <div class="subtask-content">
            <div class="form-row">
                <div class="form-group">
                    <label>Subtask Type <span class="required">*</span></label>
                    <select class="subtask-name" onchange="updateSubtaskDescription(this)" required>
                        <option value="">Select subtask...</option>
                        ${availableSubtasks.map(subtask => {
                            let displayName = subtask.name;
                            if (subtask.result_definition && subtask.result_definition.result_type) {
                                displayName += ` (${subtask.result_definition.result_type})`;
                            }
                            let description = subtask.description || 'No description available';
                            // Truncate description for the option data attribute
                            let shortDescription = description.length > 100 ? description.substring(0, 100) + '...' : description;
                            return `<option value="${subtask.name}" data-description="${shortDescription}" data-result-type="${subtask.result_definition ? subtask.result_definition.result_type : ''}">${displayName}</option>`;
                        }).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label>Target Clients <span class="required">*</span></label>
                    <div class="client-selection">
                        <div class="client-option">
                            <label class="checkbox-label">
                                <input type="checkbox" class="all-clients-checkbox" onchange="toggleAllClients(this)">
                                <span>All Clients</span>
                            </label>
                        </div>
                        ${clientsList.map(client =>
                            `<div class="client-option">
                                <label class="checkbox-label">
                                    <input type="checkbox" class="client-checkbox" value="${client.name}" onchange="updateClientSelection(this)">
                                    <span>${client.name} (${client.ip_address})</span>
                                </label>
                            </div>`
                        ).join('')}
                    </div>
                </div>
            </div>
            <div class="subtask-description">
                <small class="description-text">Select a subtask to see its description</small>
            </div>
        </div>
    `;

    subtasksList.appendChild(subtaskRow);
    updateSubtaskNumbers();
}

// Toggle all clients selection
function toggleAllClients(checkbox) {
    if (!checkbox) return;
    
    const subtaskRow = checkbox.closest('.subtask-row');
    if (!subtaskRow) return;
    
    const clientCheckboxes = subtaskRow.querySelectorAll('.client-checkbox');

    clientCheckboxes.forEach(cb => {
        cb.checked = checkbox.checked;
    });
}

// Update client selection when individual checkboxes change
function updateClientSelection(checkbox) {
    if (!checkbox) return;
    
    const subtaskRow = checkbox.closest('.subtask-row');
    if (!subtaskRow) return;
    
    const allClientsCheckbox = subtaskRow.querySelector('.all-clients-checkbox');
    const clientCheckboxes = subtaskRow.querySelectorAll('.client-checkbox');
    const checkedBoxes = subtaskRow.querySelectorAll('.client-checkbox:checked');

    if (!allClientsCheckbox) return;

    // Update "All Clients" checkbox state
    if (checkedBoxes.length === clientCheckboxes.length) {
        allClientsCheckbox.checked = true;
        allClientsCheckbox.indeterminate = false;
    } else if (checkedBoxes.length === 0) {
        allClientsCheckbox.checked = false;
        allClientsCheckbox.indeterminate = false;
    } else {
        allClientsCheckbox.checked = false;
        allClientsCheckbox.indeterminate = true;
    }
}

// Remove a subtask row
function removeSubtask(button) {
    if (!button) return;
    
    const subtaskRow = button.closest('.subtask-row');
    if (subtaskRow) {
        subtaskRow.remove();
        updateSubtaskNumbers();
    }
}

// Update subtask numbers after add/remove
function updateSubtaskNumbers() {
    const subtaskRows = document.querySelectorAll('.subtask-row');
    subtaskRows.forEach((row, index) => {
        const header = row.querySelector('.subtask-header h5');
        if (header) {
            header.textContent = `Subtask ${index + 1}`;
        }

        // Only try to update order input if it exists
        const orderInput = row.querySelector('.subtask-order');
        if (orderInput) {
            if (orderInput.value == index + 1 || orderInput.value == index) {
                orderInput.value = index;
            }
        }
    });
}

// Update subtask description when type is selected
function updateSubtaskDescription(selectElement) {
    if (!selectElement) return;
    
    const subtaskName = selectElement.value;
    const subtaskRow = selectElement.closest('.subtask-row');
    
    if (!subtaskRow) return;
    
    const descriptionDiv = subtaskRow.querySelector('.subtask-description');
    
    if (!descriptionDiv) return;

    if (subtaskName) {
        const subtask = availableSubtasks.find(s => s.name === subtaskName);
        if (subtask) {
            let descriptionHTML = `
                <small class="help-text">
                    <strong>${subtask.name}:</strong> ${subtask.description || 'No description available'}
            `;
            
            // Add result definition information if available
            if (subtask.result_definition) {
                const rd = subtask.result_definition;
                descriptionHTML += `<br>
                    <strong>Result Type:</strong> ${rd.result_type}`;
                
                if (rd.format_hint) {
                    descriptionHTML += `<br>
                    <strong>Format:</strong> ${rd.format_hint}`;
                }
                
                if (rd.is_critical !== undefined) {
                    descriptionHTML += `<br>
                    <strong>Critical:</strong> ${rd.is_critical ? 'Yes' : 'No'}`;
                }
                
                if (rd.required_fields && rd.required_fields.length > 0) {
                    descriptionHTML += `<br>
                    <strong>Required Fields:</strong> ${rd.required_fields.join(', ')}`;
                }
            }
            
            descriptionHTML += '</small>';
            descriptionDiv.innerHTML = descriptionHTML;
        }
    } else {
        descriptionDiv.innerHTML = '<small class="help-text">Select a subtask to see its description and result specification</small>';
    }
}

// Open task creation modal
function openTaskModal(taskId = null) {
    console.log('openTaskModal called with taskId:', taskId);

    const modal = document.getElementById('taskModal');
    const modalTitle = document.getElementById('modalTitle');
    const form = document.getElementById('taskForm');

    // Reset form
    form.reset();
    document.getElementById('taskId').value = '';

    // Clear subtasks
    const subtasksList = document.getElementById('subtasksList');
    subtasksList.innerHTML = '';

    if (taskId) {
        modalTitle.textContent = 'Edit Task';
        loadTaskForEdit(taskId);
    } else {
        modalTitle.textContent = 'Create Task';
        // Add initial subtask for new tasks
        addSubtask();
    }

    modal.style.display = 'block';
}

// Close task modal
function closeTaskModal() {
    document.getElementById('taskModal').style.display = 'none';
}

// Toggle schedule options
function toggleScheduleOptions() {
    const scheduleType = document.getElementById('scheduleType').value;
    const scheduleTimeGroup = document.getElementById('scheduleTimeGroup');
    const cronGroup = document.getElementById('cronGroup');

    scheduleTimeGroup.style.display = scheduleType === 'scheduled' ? 'block' : 'none';
    cronGroup.style.display = scheduleType === 'cron' ? 'block' : 'none';
}

// Toggle email recipients field
function toggleEmailRecipients() {
    const sendEmail = document.getElementById('sendEmail').checked;
    const emailRecipientsGroup = document.getElementById('emailRecipientsGroup');
    
    emailRecipientsGroup.style.display = sendEmail ? 'block' : 'none';
    
    // Clear recipients field if email is disabled
    if (!sendEmail) {
        document.getElementById('emailRecipients').value = '';
    }
}

// Save task (create or update)
async function saveTask() {
    try {
        const taskData = {
            name: document.getElementById('taskName').value.trim()
        };

        if (!taskData.name) {
            showNotification('Task name is required', 'error');
            return;
        }

        // Handle schedule
        const scheduleType = document.getElementById('scheduleType').value;
        if (scheduleType === 'scheduled') {
            const scheduleTime = document.getElementById('scheduleTime').value;
            if (scheduleTime) {
                taskData.schedule_time = scheduleTime;
            }
        } else if (scheduleType === 'cron') {
            const cronExpression = document.getElementById('cronExpression').value.trim();
            if (cronExpression) {
                taskData.cron_expression = cronExpression;
            }
        }

        // Collect subtasks
        const subtasks = collectSubtasks();
        if (subtasks.length === 0) {
            showNotification('At least one subtask is required', 'error');
            return;
        }
        taskData.subtasks = subtasks;

        // Handle email notification settings
        const sendEmail = document.getElementById('sendEmail').checked;
        taskData.send_email = sendEmail;
        
        if (sendEmail) {
            const emailRecipients = document.getElementById('emailRecipients').value.trim();
            if (emailRecipients) {
                taskData.email_recipients = emailRecipients;
            } else {
                // If send_email is true but no recipients specified, show warning
                showNotification('Warning: Email notifications enabled but no recipients specified. Default recipient will be used.', 'warning');
            }
        }

        // Submit to server
        const taskId = document.getElementById('taskId').value;
        let response;

        if (taskId) {
            response = await apiPut(`/api/tasks/${taskId}`, taskData);
        } else {
            response = await apiPost('/api/tasks', taskData);
        }

        if (response.success) {
            showNotification(taskId ? 'Task updated successfully' : 'Task created successfully', 'success');
            closeTaskModal();
            await refreshTasks();
        } else {
            showNotification(response.error || 'Failed to save task', 'error');
        }

    } catch (error) {
        console.error('Failed to save task:', error);
        showNotification('Failed to save task', 'error');
    }
}

// Collect subtasks from form
function collectSubtasks() {
    const subtaskRows = document.querySelectorAll('.subtask-row');
    const subtasks = [];

    subtaskRows.forEach((row, index) => {
        const name = row.querySelector('.subtask-name').value;
        const checkedClients = Array.from(row.querySelectorAll('.client-checkbox:checked')).map(cb => cb.value);

        if (name && checkedClients.length > 0) {
            // Create a subtask for each selected client
            checkedClients.forEach((clientName, clientIndex) => {
                subtasks.push({
                    name: name,
                    target_client: clientName,
                    order: index,
                    args: [],
                    kwargs: {},
                    timeout: 300
                });
            });
        }
    });

    return subtasks;
}

// Load tasks from server and get execution data
async function refreshTasks() {
    try {
        const response = await apiGet('/api/tasks');
        if (response.success) {
            allTasks = response.data || [];
        } else {
            throw new Error(response.error || 'Unknown error');
        }
        
        // Load subtask execution data for each task
        for (const task of allTasks) {
            try {
                const executionsResponse = await apiGet(`/api/tasks/${task.id}/subtask-executions`);
                task.executions = executionsResponse.success ? executionsResponse.data : [];
            } catch (error) {
                console.warn(`Failed to load executions for task ${task.id}:`, error);
                task.executions = [];
            }
        }
        
        filterTasks();
        renderEnhancedTasks();
    } catch (error) {
        console.error('Failed to load tasks:', error);
        showNotification('Failed to load tasks', 'error');
    }
}

// Enhanced task rendering with subtask-client combinations
function renderEnhancedTasks() {
    const tasksTableBody = document.getElementById('taskTableBody');
    if (!tasksTableBody) {
        console.error('Could not find taskTableBody element');
        return;
    }

    const start = (tasksCurrentPage - 1) * tasksItemsPerPage;
    const end = start + tasksItemsPerPage;
    const paginatedTasks = filteredTasks.slice(start, end);

    tasksTableBody.innerHTML = '';

    if (paginatedTasks.length === 0) {
        tasksTableBody.innerHTML = `
            <tr>
                <td colspan="8" class="no-tasks-message">
                    <i class="fas fa-tasks"></i><br>
                    No tasks found
                </td>
            </tr>
        `;
        return;
    }

    paginatedTasks.forEach(task => {
        renderTaskGroup(task, tasksTableBody);
    });

    updatePagination();
}

// Render a complete task group with all subtask-client combinations
function renderTaskGroup(task, container) {
    // Calculate task statistics
    const taskStats = calculateTaskStatistics(task);
    
    // Create task group header row
    const groupRow = document.createElement('tr');
    groupRow.className = 'task-group-row';
    groupRow.innerHTML = `
        <td>${task.id}</td>
        <td colspan="7">
            <div class="task-group-header">
                <div class="task-group-title">${task.name}</div>
                <div class="task-group-summary">
                    ${taskStats.totalExecutions} executions • 
                    ${taskStats.completed} completed • 
                    ${taskStats.running} running • 
                    ${taskStats.failed} failed • 
                    ${taskStats.pending} pending
                </div>
                <div class="task-group-actions">
                    <div class="task-group-progress">
                        <div class="task-group-progress-fill ${taskStats.progressClass}" 
                             style="width: ${taskStats.completionPercentage}%"></div>
                    </div>
                    <span class="status-badge ${task.status}">${task.status}</span>
                    <button class="collapse-toggle" onclick="toggleTaskGroup(${task.id})" 
                            title="Toggle subtask details">
                        <i class="fas fa-chevron-down" id="toggle-icon-${task.id}"></i>
                    </button>
                    <button class="btn btn-small btn-primary" onclick="viewTaskDetails(${task.id})" 
                            title="View Details">
                        <i class="fas fa-eye"></i>
                    </button>
                    ${task.status !== 'running' ? 
                        `<button class="btn btn-small btn-danger" onclick="deleteTask(${task.id})" 
                                title="Delete Task">
                            <i class="fas fa-trash"></i>
                        </button>` : ''
                    }
                </div>
            </div>
        </td>
    `;
    container.appendChild(groupRow);

    // Create subtask execution rows
    const subtaskExecutions = generateSubtaskExecutions(task);
    subtaskExecutions.forEach(execution => {
        const executionRow = createSubtaskExecutionRow(task, execution);
        container.appendChild(executionRow);
    });
}

// Generate subtask execution combinations
function generateSubtaskExecutions(task) {
    const executions = [];
    
    if (task.subtasks && task.subtasks.length > 0) {
        // Group subtasks by name and order, then create execution for each target client
        task.subtasks.forEach(subtask => {
            const executionData = findExecutionData(task, subtask.name, subtask.target_client);
            
            executions.push({
                subtask_name: subtask.name,
                target_client: subtask.target_client,
                order: subtask.order,
                timeout: subtask.timeout,
                status: executionData ? executionData.status : 'pending',
                started_at: executionData ? executionData.started_at : null,
                completed_at: executionData ? executionData.completed_at : null,
                execution_time: executionData ? executionData.execution_time : null,
                result: executionData ? executionData.result : null,
                error_message: executionData ? executionData.error_message : null
            });
        });
    } else {
        // Legacy command-based task
        const targetClients = task.target_clients && task.target_clients.length > 0 
            ? task.target_clients 
            : [task.target_client || 'Any Available'];
        
        targetClients.forEach(client => {
            executions.push({
                subtask_name: 'Command Execution',
                target_client: client,
                order: 0,
                timeout: 300,
                status: task.status,
                started_at: task.started_at,
                completed_at: task.completed_at,
                execution_time: null,
                result: task.result,
                error_message: task.error_message
            });
        });
    }
    
    // Sort by order and then by target client
    executions.sort((a, b) => {
        if (a.order !== b.order) {
            return a.order - b.order;
        }
        return a.target_client.localeCompare(b.target_client);
    });
    
    return executions;
}

// Find execution data for a specific subtask-client combination
function findExecutionData(task, subtaskName, targetClient) {
    if (!task.executions) return null;
    
    return task.executions.find(exec => 
        exec.subtask_name === subtaskName && 
        exec.target_client === targetClient
    );
}

// Create a subtask execution row
function createSubtaskExecutionRow(task, execution) {
    const row = document.createElement('tr');
    row.className = `subtask-execution-row task-${task.id}-executions`;
    
    // Get client status
    const client = clientsList.find(m => m.name === execution.target_client);
    const clientStatus = client ? client.status : 'unknown';
    
    // Format timing information
    const timingInfo = formatTimingInfo(execution);
    
    // Progress indicator
    const progressIcon = getProgressIcon(execution.status);
    
    row.innerHTML = `
        <td class="task-id-col"></td>
        <td class="task-name-col"></td>
        <td class="subtask-col">
            <span class="subtask-name">${execution.subtask_name}</span>
            <div style="font-size: 0.75rem; color: #6c757d; margin-top: 2px;">
                Order: ${execution.order} | Timeout: ${execution.timeout}s
            </div>
        </td>
        <td class="client-col">
            <div class="client-name">${execution.target_client}</div>
            <div class="client-status ${clientStatus}">${clientStatus}</div>
        </td>
        <td class="status-col">
            <span class="status-badge ${execution.status}">${execution.status}</span>
        </td>
        <td class="timing-col">
            ${timingInfo}
        </td>
        <td class="progress-col">
            <div class="progress-indicator ${execution.status}">
                ${progressIcon}
            </div>
        </td>
        <td class="actions-col">
            <div class="row-actions">
                ${execution.status === 'failed' && execution.error_message ? 
                    `<button class="btn btn-small btn-danger" onclick="showExecutionError('${execution.subtask_name}', '${execution.target_client}', \`${execution.error_message.replace(/`/g, '\\`')}\`)" title="View Error">
                        <i class="fas fa-exclamation-triangle"></i>
                    </button>` : ''
                }
                ${execution.result ? 
                    `<button class="btn btn-small btn-info" onclick="showExecutionResult('${execution.subtask_name}', '${execution.target_client}', \`${execution.result.replace(/`/g, '\\`')}\`)" title="View Result">
                        <i class="fas fa-info-circle"></i>
                    </button>` : ''
                }
                ${execution.status === 'pending' && task.status !== 'completed' && task.status !== 'failed' && task.status !== 'cancelled' ? 
                    `<button class="btn btn-small btn-warning" onclick="deleteSubtaskExecution(${task.id}, '${execution.subtask_name}', '${execution.target_client}')" title="Delete Pending Subtask">
                        <i class="fas fa-trash"></i>
                    </button>` : ''
                }
            </div>
        </td>
    `;
    
    return row;
}

// Calculate task statistics
function calculateTaskStatistics(task) {
    const executions = generateSubtaskExecutions(task);
    
    const stats = {
        totalExecutions: executions.length,
        completed: executions.filter(e => e.status === 'completed').length,
        running: executions.filter(e => e.status === 'running').length,
        failed: executions.filter(e => e.status === 'failed').length,
        pending: executions.filter(e => e.status === 'pending').length
    };
    
    stats.completionPercentage = stats.totalExecutions > 0 
        ? Math.round((stats.completed / stats.totalExecutions) * 100) 
        : 0;
    
    // Determine progress bar class
    if (stats.failed > 0 && stats.completed > 0) {
        stats.progressClass = 'mixed';
    } else if (stats.running > 0) {
        stats.progressClass = 'running';
    } else if (stats.completed === stats.totalExecutions) {
        stats.progressClass = 'completed';
    } else if (stats.failed > 0) {
        stats.progressClass = 'failed';
    } else {
        stats.progressClass = 'pending';
    }
    
    return stats;
}

// Format timing information for display
function formatTimingInfo(execution) {
    if (!execution.started_at) {
        return '<span class="timing-info">Not started</span>';
    }
    
    let timingHtml = `<div class="timing-info">`;
    
    timingHtml += `<div><span class="timing-label">Started:</span> ${new Date(execution.started_at).toLocaleString()}</div>`;
    
    if (execution.completed_at) {
        timingHtml += `<div><span class="timing-label">Completed:</span> ${new Date(execution.completed_at).toLocaleString()}</div>`;
    }
    
    if (execution.execution_time) {
        timingHtml += `<div><span class="timing-label">Duration:</span><span class="execution-time">${execution.execution_time.toFixed(2)}s</span></div>`;
    }
    
    timingHtml += '</div>';
    
    return timingHtml;
}

// Get progress icon for status
function getProgressIcon(status) {
    switch (status) {
        case 'pending':
            return '⏳';
        case 'running':
            return '⚡';
        case 'completed':
            return '✓';
        case 'failed':
            return '✗';
        case 'cancelled':
            return '⊘';
        default:
            return '?';
    }
}

// Toggle task group visibility
function toggleTaskGroup(taskId) {
    const executionRows = document.querySelectorAll(`.task-${taskId}-executions`);
    const toggleIcon = document.getElementById(`toggle-icon-${taskId}`);
    
    const isCollapsed = executionRows[0] && executionRows[0].classList.contains('collapsed');
    
    executionRows.forEach(row => {
        if (isCollapsed) {
            row.classList.remove('collapsed');
        } else {
            row.classList.add('collapsed');
        }
    });
    
    if (toggleIcon) {
        toggleIcon.className = isCollapsed ? 'fas fa-chevron-down' : 'fas fa-chevron-up';
    }
}

// Show execution error details
function showExecutionError(subtaskName, targetClient, errorMessage) {
    showNotification('Execution Error', 
        `Error in ${subtaskName} on ${targetClient}:\n\n${errorMessage}`, 'error');
}

// Show execution result details
function showExecutionResult(subtaskName, targetClient, result) {
    showNotification('Execution Result', 
        `Result from ${subtaskName} on ${targetClient}:\n\n${result}`, 'info');
}

// Filter tasks based on current filters  
function filterTasks() {
    const statusFilter = document.getElementById('statusFilter')?.value || '';
    const clientFilter = document.getElementById('clientFilter')?.value || '';
    const searchInput = document.getElementById('searchInput')?.value || '';
    
    filteredTasks = allTasks.filter(task => {
        // Status filter
        if (statusFilter && task.status !== statusFilter) {
            return false;
        }
        
        // Client filter - check if task has any subtasks or executions on the specified client
        if (clientFilter) {
            const hasTargetClient = task.subtasks && task.subtasks.some(st => st.target_client === clientFilter) ||
                                   task.target_clients && task.target_clients.includes(clientFilter) ||
                                   task.target_client === clientFilter;
            if (!hasTargetClient) {
                return false;
            }
        }
        
        // Search filter
        if (searchInput) {
            const searchTerm = searchInput.toLowerCase();
            const matchesName = task.name.toLowerCase().includes(searchTerm);
            const matchesCommand = task.command && task.command.toLowerCase().includes(searchTerm);
            const matchesSubtask = task.subtasks && task.subtasks.some(st => 
                st.name.toLowerCase().includes(searchTerm)
            );
            
            if (!matchesName && !matchesCommand && !matchesSubtask) {
                return false;
            }
        }
        
        return true;
    });
    
    tasksCurrentPage = 1;
}

// Toggle task group visibility
function toggleTaskGroup(taskId) {
    const subtaskRows = document.querySelectorAll(`[data-task-id="${taskId}"].subtask-execution-row`);
    const toggleIcon = document.querySelector(`[data-task-id="${taskId}"] .toggle-subtasks i`);
    
    if (!toggleIcon) return;
    
    const isCollapsed = toggleIcon.classList.contains('fa-chevron-down');
    
    subtaskRows.forEach(row => {
        row.style.display = isCollapsed ? 'table-row' : 'none';
    });
    
    toggleIcon.classList.toggle('fa-chevron-down', !isCollapsed);
    toggleIcon.classList.toggle('fa-chevron-right', isCollapsed);
}

// Show execution error details
function showExecutionError(error) {
    const modal = document.createElement('div');
    modal.className = 'modal modal-overlay';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>Execution Error</h3>
                <button class="btn-close" onclick="this.closest('.modal').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <pre class="error-details">${error}</pre>
            </div>
            <div class="modal-footer">
                <button class="btn btn-primary" onclick="this.closest('.modal').remove()">Close</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

// Show execution result details
function showExecutionResult(result) {
    const modal = document.createElement('div');
    modal.className = 'modal modal-overlay';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>Execution Result</h3>
                <button class="btn-close" onclick="this.closest('.modal').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <pre class="result-details">${result}</pre>
            </div>
            <div class="modal-footer">
                <button class="btn btn-primary" onclick="this.closest('.modal').remove()">Close</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

// Format execution time
function formatExecutionTime(startTime, endTime) {
    if (!startTime) return '-';
    
    const start = new Date(startTime);
    if (!endTime) {
        return `Started: ${start.toLocaleString()}`;
    }
    
    const end = new Date(endTime);
    const duration = end - start;
    const seconds = Math.floor(duration / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    
    let durationStr = '';
    if (hours > 0) {
        durationStr = `${hours}h ${minutes % 60}m ${seconds % 60}s`;
    } else if (minutes > 0) {
        durationStr = `${minutes}m ${seconds % 60}s`;
    } else {
        durationStr = `${seconds}s`;
    }
    
    return `${durationStr} (${start.toLocaleString()} - ${end.toLocaleString()})`;
}

// Get status class for styling
function getStatusClass(status) {
    const statusMap = {
        'pending': 'status-pending',
        'running': 'status-running',
        'completed': 'status-completed',
        'failed': 'status-failed',
        'cancelled': 'status-cancelled',
        'paused': 'status-paused'
    };
    return statusMap[status] || 'status-unknown';
}

// Calculate task progress percentage
function calculateTaskProgress(executions) {
    if (!executions || executions.length === 0) return 0;
    
    const completed = executions.filter(exec => 
        exec.status === 'completed' || exec.status === 'failed'
    ).length;
    
    return Math.round((completed / executions.length) * 100);
}

// Update task statistics
function updateTasksStats() {
    const totalTasks = allTasks.length;
    const filteredCount = filteredTasks.length;
    
    // Update counters
    const totalElement = document.getElementById('totalTasks');
    const filteredElement = document.getElementById('filteredTasks');
    
    if (totalElement) totalElement.textContent = totalTasks;
    if (filteredElement) filteredElement.textContent = filteredCount;
    
    // Calculate status distribution
    const statusCounts = {};
    allTasks.forEach(task => {
        statusCounts[task.status] = (statusCounts[task.status] || 0) + 1;
    });
    
    // Update status badges
    Object.keys(statusCounts).forEach(status => {
        const element = document.getElementById(`${status}Tasks`);
        if (element) {
            element.textContent = statusCounts[status];
        }
    });
}

// API helper functions
async function apiGet(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();
        return { success: true, data: data };
    } catch (error) {
        console.error('API GET error:', error);
        return { success: false, error: error.message };
    }
}

async function apiPost(url, data) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        return { success: true, data: result };
    } catch (error) {
        console.error('API POST error:', error);
        return { success: false, error: error.message };
    }
}

// Update pagination for enhanced view
function updatePagination() {
    const totalPages = Math.ceil(filteredTasks.length / tasksItemsPerPage);
    const pagination = document.getElementById('pagination');

    if (!pagination) return;

    pagination.innerHTML = '';

    if (totalPages <= 1) return;

    // Previous button
    const prevButton = document.createElement('button');
    prevButton.className = 'btn btn-secondary';
    prevButton.innerHTML = '<i class="fas fa-chevron-left"></i> Previous';
    prevButton.disabled = tasksCurrentPage === 1;
    prevButton.onclick = () => {
        if (tasksCurrentPage > 1) {
            tasksCurrentPage--;
            renderEnhancedTasks();
        }
    };
    pagination.appendChild(prevButton);

    // Page numbers (show max 5 pages around current)
    const startPage = Math.max(1, tasksCurrentPage - 2);
    const endPage = Math.min(totalPages, tasksCurrentPage + 2);
    
    if (startPage > 1) {
        const firstButton = document.createElement('button');
        firstButton.className = 'btn btn-outline-secondary';
        firstButton.textContent = '1';
        firstButton.onclick = () => {
            tasksCurrentPage = 1;
            renderEnhancedTasks();
        };
        pagination.appendChild(firstButton);
        
        if (startPage > 2) {
            const ellipsis = document.createElement('span');
            ellipsis.textContent = '...';
            ellipsis.className = 'pagination-ellipsis';
            pagination.appendChild(ellipsis);
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        const pageButton = document.createElement('button');
        pageButton.className = i === tasksCurrentPage ? 'btn btn-primary' : 'btn btn-outline-secondary';
        pageButton.textContent = i;
        pageButton.onclick = () => {
            tasksCurrentPage = i;
            renderEnhancedTasks();
        };
        pagination.appendChild(pageButton);
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const ellipsis = document.createElement('span');
            ellipsis.textContent = '...';
            ellipsis.className = 'pagination-ellipsis';
            pagination.appendChild(ellipsis);
        }
        
        const lastButton = document.createElement('button');
        lastButton.className = 'btn btn-outline-secondary';
        lastButton.textContent = totalPages;
        lastButton.onclick = () => {
            tasksCurrentPage = totalPages;
            renderEnhancedTasks();
        };
        pagination.appendChild(lastButton);
    }

    // Next button
    const nextButton = document.createElement('button');
    nextButton.className = 'btn btn-secondary';
    nextButton.innerHTML = 'Next <i class="fas fa-chevron-right"></i>';
    nextButton.disabled = tasksCurrentPage === totalPages;
    nextButton.onclick = () => {
        if (tasksCurrentPage < totalPages) {
            tasksCurrentPage++;
            renderEnhancedTasks();
        }
    };
    pagination.appendChild(nextButton);
}

// Delete task
async function deleteTask(taskId) {
    // Get task info for better confirmation message
    const task = allTasks.find(t => t.id === taskId);
    const taskName = task ? task.name : `Task ${taskId}`;
    
    if (!confirm(`Are you sure you want to delete "${taskName}"?\n\nThis will permanently delete:\n• The task itself\n• All execution history\n• All subtask records\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const response = await apiDelete(`/api/tasks/${taskId}`);

        if (response.success) {
            showNotification('Task Deleted', response.message || 'Task deleted successfully', 'success');
            await refreshTasks();
        } else {
            showNotification('Delete Failed', response.error || 'Failed to delete task', 'error');
        }
    } catch (error) {
        console.error('Failed to delete task:', error);
        showNotification('Delete Error', 'Failed to delete task', 'error');
    }
}

// Delete subtask execution that hasn't started yet
async function deleteSubtaskExecution(taskId, subtaskName, targetClient) {
    if (!confirm(`Are you sure you want to delete the pending subtask "${subtaskName}" for client "${targetClient}"?\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/tasks/${taskId}/subtasks/${encodeURIComponent(subtaskName)}/delete`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                target_client: targetClient
            })
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`Subtask "${subtaskName}" deleted successfully`, 'success');
            
            // Check if all subtasks were deleted
            if (result.remaining_subtasks === 0) {
                showNotification('All subtasks deleted - task has been cancelled', 'info');
            }
            
            // Refresh the task list to show updated state
            await refreshTasks();
        } else {
            showNotification(result.error || 'Failed to delete subtask', 'error');
        }
    } catch (error) {
        console.error('Failed to delete subtask:', error);
        showNotification('Failed to delete subtask', 'error');
    }
}

// View task details
async function viewTaskDetails(taskId) {
    try {
        // Store current task ID for real-time updates
        window.currentTaskDetailId = taskId;
        
        const response = await apiGet(`/api/tasks/${taskId}`);

        if (response.success) {
            const task = response.data;
            
            // Get subtask execution status
            const executionsResponse = await apiGet(`/api/tasks/${taskId}/subtask-executions`);
            const executions = executionsResponse.success ? executionsResponse.data : [];
            
            displayTaskDetailsWithExecutions(task, executions);
        } else {
            showNotification(response.error || 'Failed to load task details', 'error');
        }
    } catch (error) {
        console.error('Failed to load task details:', error);
        showNotification('Failed to load task details', 'error');
    }
}

// Display task details with execution status in modal
function displayTaskDetailsWithExecutions(task, executions = []) {
    const modal = document.getElementById('taskDetailModal');
    const content = document.getElementById('taskDetailContent');

    let detailsHtml = `
        <div class="task-detail-section">
            <h4>Basic Information</h4>
            <div class="detail-grid">
                <div class="detail-item">
                    <label>Task ID:</label>
                    <span>${task.id}</span>
                </div>
                <div class="detail-item">
                    <label>Name:</label>
                    <span>${task.name}</span>
                </div>
                <div class="detail-item">
                    <label>Status:</label>
                    <span class="status-badge ${task.status}">${task.status}</span>
                </div>
                <div class="detail-item">
                    <label>Created:</label>
                    <span>${task.created_at ? new Date(task.created_at).toLocaleString() : '-'}</span>
                </div>
                <div class="detail-item">
                    <label>Started:</label>
                    <span>${task.started_at ? new Date(task.started_at).toLocaleString() : '-'}</span>
                </div>
                <div class="detail-item">
                    <label>Completed:</label>
                    <span>${task.completed_at ? new Date(task.completed_at).toLocaleString() : '-'}</span>
                </div>
            </div>
        </div>
    `;

    if (task.subtasks && task.subtasks.length > 0) {
        // Create execution status map for quick lookup
        const executionMap = {};
        executions.forEach(exec => {
            const key = `${exec.subtask_name}_${exec.target_client}`;
            executionMap[key] = exec;
        });

        // Calculate overall subtask statistics
        const totalSubtasks = task.subtasks.length;
        const completedSubtasks = executions.filter(e => e.status === 'completed').length;
        const failedSubtasks = executions.filter(e => e.status === 'failed').length;
        const runningSubtasks = executions.filter(e => e.status === 'running').length;
        const pendingSubtasks = totalSubtasks - completedSubtasks - failedSubtasks - runningSubtasks;

        detailsHtml += `
            <div class="task-detail-section">
                <h4>Subtask Execution Overview</h4>
                <div class="subtask-overview">
                    <div class="overview-stats">
                        <div class="stat-item">
                            <span class="stat-number">${totalSubtasks}</span>
                            <span class="stat-label">Total</span>
                        </div>
                        <div class="stat-item completed">
                            <span class="stat-number">${completedSubtasks}</span>
                            <span class="stat-label">Completed</span>
                        </div>
                        <div class="stat-item running">
                            <span class="stat-number">${runningSubtasks}</span>
                            <span class="stat-label">Running</span>
                        </div>
                        <div class="stat-item failed">
                            <span class="stat-number">${failedSubtasks}</span>
                            <span class="stat-label">Failed</span>
                        </div>
                        <div class="stat-item pending">
                            <span class="stat-number">${pendingSubtasks}</span>
                            <span class="stat-label">Pending</span>
                        </div>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${totalSubtasks > 0 ? (completedSubtasks / totalSubtasks * 100) : 0}%"></div>
                    </div>
                    <div class="progress-text">${totalSubtasks > 0 ? Math.round(completedSubtasks / totalSubtasks * 100) : 0}% Complete</div>
                </div>
            </div>
        `;

        detailsHtml += `
            <div class="task-detail-section">
                <h4>Subtask Details (${task.subtasks.length})</h4>
                <div class="subtasks-detail">
        `;

        task.subtasks.forEach((subtask, index) => {
            const executionKey = `${subtask.name}_${subtask.target_client}`;
            const execution = executionMap[executionKey];
            
            // Determine status and timing
            const status = execution ? execution.status : 'pending';
            const startTime = execution && execution.started_at ? new Date(execution.started_at).toLocaleString() : '-';
            const endTime = execution && execution.completed_at ? new Date(execution.completed_at).toLocaleString() : '-';
            const executionTime = execution && execution.execution_time ? `${execution.execution_time.toFixed(3)}s` : '-';
            const result = execution && execution.result ? execution.result : '-';
            const errorMessage = execution && execution.error_message ? execution.error_message : '';

            detailsHtml += `
                <div class="subtask-detail-item">
                    <div class="subtask-detail-header">
                        <h5>Subtask ${index + 1}: ${subtask.name}</h5>
                        <div class="subtask-status-info">
                            <span class="status-badge ${status}">${status}</span>
                            <span class="subtask-order">Order: ${subtask.order}</span>
                        </div>
                    </div>
                    <div class="subtask-detail-content">
                        <div class="detail-grid">
                            <div class="detail-item">
                                <label>Target Client:</label>
                                <span>${subtask.target_client}</span>
                            </div>
                            <div class="detail-item">
                                <label>Timeout:</label>
                                <span>${subtask.timeout || 300}s</span>
                            </div>
                            <div class="detail-item">
                                <label>Started At:</label>
                                <span>${startTime}</span>
                            </div>
                            <div class="detail-item">
                                <label>Completed At:</label>
                                <span>${endTime}</span>
                            </div>
                            <div class="detail-item">
                                <label>Execution Time:</label>
                                <span>${executionTime}</span>
                            </div>
                            <div class="detail-item">
                                <label>Result:</label>
                                <span class="result-text">${result}</span>
                            </div>
                            <div class="detail-item">
                                <label>Arguments:</label>
                                <span><code>${JSON.stringify(subtask.args || [])}</code></span>
                            </div>
                            <div class="detail-item">
                                <label>Keyword Arguments:</label>
                                <span><code>${JSON.stringify(subtask.kwargs || {})}</code></span>
                            </div>
                        </div>
                        ${errorMessage ? `
                            <div class="error-message">
                                <label>Error Message:</label>
                                <div class="error-text">${errorMessage}</div>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        });

        detailsHtml += `
                </div>
            </div>
        `;
    } else if (task.command) {
        detailsHtml += `
            <div class="task-detail-section">
                <h4>Command</h4>
                <div class="command-detail">
                    <code>${task.command}</code>
                </div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <label>Target Client:</label>
                        <span>${task.target_client || 'Any available'}</span>
                    </div>
                </div>
            </div>
        `;
    }

    if (task.schedule_time || task.cron_expression) {
        detailsHtml += `
            <div class="task-detail-section">
                <h4>Schedule</h4>
                <div class="detail-grid">
                    ${task.schedule_time ? `
                        <div class="detail-item">
                            <label>Scheduled Time:</label>
                            <span>${new Date(task.schedule_time).toLocaleString()}</span>
                        </div>
                    ` : ''}
                    ${task.cron_expression ? `
                        <div class="detail-item">
                            <label>Cron Expression:</label>
                            <span><code>${task.cron_expression}</code></span>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // Add action buttons for completed or failed tasks
    if (task.status === 'completed' || task.status === 'failed') {
        detailsHtml += `
            <div class="task-detail-section">
                <h4>Actions</h4>
                <div class="action-buttons">
                    <button class="btn btn-primary" onclick="generateTaskReport(${task.id})">
                        <i class="fas fa-file-alt"></i> Generate Report
                    </button>
                    <button class="btn btn-secondary" onclick="sendTaskNotification(${task.id})">
                        <i class="fas fa-envelope"></i> Send Email Notification
                    </button>
                </div>
                <p class="help-text">
                    <small>
                        • Generate Report: Creates a detailed HTML report with all subtask results<br>
                        • Send Email: Sends notification email with attached report (requires email configuration)
                    </small>
                </p>
            </div>
        `;
    }

    content.innerHTML = detailsHtml;
    modal.style.display = 'block';
}

// Keep the original function for backward compatibility
function displayTaskDetails(task) {
    displayTaskDetailsWithExecutions(task, []);
}

// Close task detail modal
function closeTaskDetailModal() {
    document.getElementById('taskDetailModal').style.display = 'none';
    // Clear the stored task ID
    if (window.currentTaskDetailId) {
        delete window.currentTaskDetailId;
    }
}

// Get current task detail ID
function getCurrentTaskDetailId() {
    return window.currentTaskDetailId || null;
}

// Refresh task details view
async function refreshTaskDetails(taskId) {
    try {
        const response = await apiGet(`/api/tasks/${taskId}`);
        if (response.success) {
            const task = response.data;
            
            // Get subtask execution status
            const executionsResponse = await apiGet(`/api/tasks/${taskId}/subtask-executions`);
            const executions = executionsResponse.success ? executionsResponse.data : [];
            
            displayTaskDetailsWithExecutions(task, executions);
        }
    } catch (error) {
        console.error('Failed to refresh task details:', error);
    }
}

// Load task data for editing
async function loadTaskForEdit(taskId) {
    try {
        const response = await apiGet(`/api/tasks/${taskId}`);
        if (response.success) {
            const task = response.data;

            // Set task ID for update
            document.getElementById('taskId').value = task.id;

            // Set basic fields
            document.getElementById('taskName').value = task.name;

            // Load subtasks (always subtask-based now)
            if (task.subtasks && task.subtasks.length > 0) {
                // Group subtasks by name and order to handle multiple clients per subtask
                const subtaskGroups = {};
                task.subtasks.forEach(subtask => {
                    const key = `${subtask.name}_${subtask.order}`;
                    if (!subtaskGroups[key]) {
                        subtaskGroups[key] = {
                            name: subtask.name,
                            order: subtask.order,
                            clients: []
                        };
                    }
                    subtaskGroups[key].clients.push(subtask.target_client);
                });

                // Create subtask rows for each group
                Object.values(subtaskGroups).forEach(group => {
                    addSubtask();
                    const subtaskRows = document.querySelectorAll('.subtask-row');
                    const subtaskRow = subtaskRows[subtaskRows.length - 1];

                    // Set subtask name
                    subtaskRow.querySelector('.subtask-name').value = group.name;                    // Select the appropriate clients
                    group.clients.forEach(clientName => {
                        const clientCheckbox = subtaskRow.querySelector(`.client-checkbox[value="${clientName}"]`);
                        if (clientCheckbox) {
                            clientCheckbox.checked = true;
                        }
                    });
                    
                    // Update client selection state
                    updateClientSelection(subtaskRow.querySelector('.client-checkbox'));

                    // Update description
                    updateSubtaskDescription(subtaskRow.querySelector('.subtask-name'));
                });
            }

            // Set schedule information
            if (task.cron_expression) {
                document.getElementById('scheduleType').value = 'cron';
                document.getElementById('cronExpression').value = task.cron_expression;
            } else if (task.schedule_time) {
                document.getElementById('scheduleType').value = 'scheduled';
                document.getElementById('scheduleTime').value = task.schedule_time;
            } else {
                document.getElementById('scheduleType').value = 'immediate';
            }

            toggleScheduleOptions();

            // Set email notification information
            const sendEmailCheckbox = document.getElementById('sendEmail');
            const emailRecipientsField = document.getElementById('emailRecipients');
            
            if (task.send_email) {
                sendEmailCheckbox.checked = true;
                if (task.email_recipients) {
                    emailRecipientsField.value = task.email_recipients;
                }
            } else {
                sendEmailCheckbox.checked = false;
                emailRecipientsField.value = '';
            }
            
            toggleEmailRecipients();
            
        } else {
            showNotification(response.error || 'Failed to load task data', 'error');
        }
    } catch (error) {
        console.error('Failed to load task for edit:', error);
        showNotification('Failed to load task data', 'error');
    }
}

// Populate client filter dropdown
function populateClientFilter() {
    const clientFilter = document.getElementById('clientFilter');
    if (!clientFilter) return;
    
    // Clear existing options (except the "All Clients" option)
    clientFilter.innerHTML = '<option value="">All Clients</option>';
    
    // Get unique client names from tasks
    const clientNames = new Set();
    
    allTasks.forEach(task => {
        // Add target clients from subtasks
        if (task.subtasks) {
            task.subtasks.forEach(subtask => {
                if (subtask.target_client && subtask.target_client !== 'any_available') {
                    clientNames.add(subtask.target_client);
                }
            });
        }
        
        // Add target clients from legacy task format
        if (task.target_clients) {
            task.target_clients.forEach(client => {
                if (client && client !== 'any_available') {
                    clientNames.add(client);
                }
            });
        }
        
        // Add single target client
        if (task.target_client && task.target_client !== 'any_available') {
            clientNames.add(task.target_client);
        }
    });
    
    // Sort client names and add to dropdown
    const sortedClients = Array.from(clientNames).sort();
    sortedClients.forEach(clientName => {
        const option = document.createElement('option');
        option.value = clientName;
        option.textContent = clientName;
        clientFilter.appendChild(option);
    });
}

// Utility functions for API calls
async function apiGet(url) {
    const response = await fetch(url);
    return await response.json();
}

async function apiPost(url, data) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    });
    return await response.json();
}

async function apiPut(url, data) {
    const response = await fetch(url, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    });
    return await response.json();
}

async function apiDelete(url) {
    const response = await fetch(url, {
        method: 'DELETE'
    });
    return await response.json();
}

// Show notification
function showNotification(message, type = 'info') {
    const notifications = document.getElementById('notifications');
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <span>${message}</span>
        <button class="close-notification" onclick="this.parentElement.remove()">×</button>
    `;

    notifications.appendChild(notification);

    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Generate manual report for a task
async function generateTaskReport(taskId) {
    try {
        showNotification('Report Generation', 'Generating report...', 'info');
        
        const response = await apiPost(`/api/tasks/${taskId}/generate-report?force=true`);
        
        if (response.success) {
            showNotification('Report Generated', 
                `Report generated successfully: ${response.report_path}`, 'success');
        } else {
            showNotification('Report Generation Failed', 
                response.error || 'Unknown error', 'error');
        }
    } catch (error) {
        console.error('Error generating report:', error);
        showNotification('Error', 'Failed to generate report', 'error');
    }
}

// Send email notification for a task
async function sendTaskNotification(taskId) {
    try {
        showNotification('Email Notification', 'Sending email notification...', 'info');
        
        const response = await apiPost(`/api/tasks/${taskId}/send-notification`);
        
        if (response.success) {
            showNotification('Email Sent', 
                'Email notification sent successfully', 'success');
        } else {
            const errorMsg = response.error || 'Unknown error';
            if (errorMsg.toLowerCase().includes('not configured')) {
                showNotification('Email Not Configured', 
                    'Email notifications are not configured. Check server logs for setup instructions.', 'warning');
            } else {
                showNotification('Email Failed', errorMsg, 'error');
            }
        }
    } catch (error) {
        console.error('Error sending email notification:', error);
        showNotification('Error', 'Failed to send email notification', 'error');
    }
}
