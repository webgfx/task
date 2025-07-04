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
let allTaskDetailsVisible = true; // Track global visibility state

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
                const subtaskDisplay = data.subtask_id !== null && data.subtask_id !== undefined ? `"${data.subtask_name}" (ID: ${data.subtask_id})` : `"${data.subtask_name}"`;
                showNotification('Subtask Completed', 
                    `Subtask ${subtaskDisplay} completed on client ${data.client}`, 'success');
            } else if (data.status === 'failed') {
                const subtaskDisplay = data.subtask_id !== null && data.subtask_id !== undefined ? `"${data.subtask_name}" (ID: ${data.subtask_id})` : `"${data.subtask_name}"`;
                showNotification('Subtask Failed', 
                    `Subtask ${subtaskDisplay} failed on client ${data.client}`, 'error');
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
            const subtaskDisplay = data.subtask_id !== null && data.subtask_id !== undefined ? `"${data.subtask_name}" (ID: ${data.subtask_id})` : `"${data.subtask_name}"`;
            showNotification('Subtask Deleted', 
                `Subtask ${subtaskDisplay} deleted from client ${data.client}`, 'info');
                
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

        // Listen for client status updates (from ping or heartbeat)
        socket.on('client_status_updated', function(data) {
            console.log('Client status updated:', data);
            
            // Update client status in the client list
            const clientIndex = clientsList.findIndex(c => c.name === data.client_name);
            if (clientIndex !== -1) {
                clientsList[clientIndex].status = data.status;
                if (data.last_heartbeat) {
                    clientsList[clientIndex].last_heartbeat = data.last_heartbeat;
                }
            }
            
            // Refresh task display to show updated client status
            if (typeof refreshTasks === 'function') {
                refreshTasks();
            }
            
            // Show notification for ping results if applicable
            if (data.ping_success === true) {
                console.log(`Client ${data.client_name} ping successful`);
            } else if (data.ping_success === false) {
                console.log(`Client ${data.client_name} ping timeout`);
            }
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
        const copyModal = document.getElementById('taskCopyModal');

        if (e.target === taskModal) {
            closeTaskModal();
        }
        if (e.target === detailModal) {
            closeTaskDetailModal();
        }
        if (e.target === copyModal) {
            closeTaskCopyModal();
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
        showNotification('Error', 'Failed to load clients', 'error');
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
            <div class="subtask-id-display" style="display: none;">
                <small class="text-muted">ID: <span class="subtask-id-value">Not assigned</span></small>
            </div>
            <button type="button" class="btn btn-small btn-danger" onclick="removeSubtask(this)">
                <i class="fas fa-trash"></i> Remove
            </button>
        </div>
        <div class="subtask-content">
            <div class="form-row">
                <div class="form-group">
                    <label>Description <span class="required">*</span></label>
                    <select class="subtask-name" onchange="updateSubtaskDescription(this)" required>
                        <option value="">Select subtask...</option>
                        ${availableSubtasks.map(subtask => {
                            let displayName = subtask.name;
                            let description = subtask.description || 'No description available';
                            // Truncate description for the option data attribute
                            let shortDescription = description.length > 100 ? description.substring(0, 100) + '...' : description;
                            return `<option value="${subtask.name}" data-description="${shortDescription}">${displayName}</option>`;
                        }).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label>Clients <span class="required">*</span></label>
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
                    <strong>Description:</strong> ${subtask.description || 'No description available'}
            `;
            
            // Add result definition information if available
            if (subtask.result_definition) {
                const rd = subtask.result_definition;
                
                if (rd.format_hint) {
                    descriptionHTML += `<br>
                    <strong>Format:</strong> ${rd.format_hint}`;
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
            showNotification('Validation Error', 'Task name is required', 'error');
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
            showNotification('Validation Error', 'At least one subtask is required', 'error');
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
                showNotification('Warning', 'Email notifications enabled but no recipients specified. Default recipient will be used.', 'warning');
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
            if (taskId) {
                // For updates, close immediately
                showNotification('Success', 'Task updated successfully', 'success');
                closeTaskModal();
                await refreshTasks();
            } else {
                // For new tasks, show the generated subtask IDs briefly, then close
                showNotification('Success', 'Task created successfully', 'success');
                console.log('Task creation response:', response.data);
                if (response.data && response.data.id) {
                    await displayGeneratedSubtaskIds(response.data.id);
                } else {
                    console.warn('No task ID in response, closing modal');
                    closeTaskModal();
                }
                await refreshTasks();
            }
        } else {
            showNotification('Error', response.error || 'Failed to save task', 'error');
        }

    } catch (error) {
        console.error('Failed to save task:', error);
        showNotification('Error', 'Failed to save task', 'error');
    }
}

// Display generated subtask IDs after task creation
async function displayGeneratedSubtaskIds(taskId) {
    try {
        console.log('Fetching subtask IDs for task:', taskId);
        const response = await apiGet(`/api/tasks/${taskId}`);
        console.log('Fetched task data:', response);
        
        if (response.success && response.data.subtasks && response.data.subtasks.length > 0) {
            const task = response.data;
            const subtaskRows = document.querySelectorAll('.subtask-row');
            
            console.log('Found subtask rows:', subtaskRows.length);
            console.log('Server subtasks:', task.subtasks.length);
            
            // Create a simple mapping based on order
            let idsUpdated = 0;
            subtaskRows.forEach((subtaskRow, rowIndex) => {
                // Find subtasks for this row (by order)
                const matchingSubtasks = task.subtasks.filter(st => st.order === rowIndex);
                
                if (matchingSubtasks.length > 0) {
                    const firstSubtask = matchingSubtasks[0];
                    console.log(`Updating row ${rowIndex} with subtask ID:`, firstSubtask.subtask_id);
                    
                    subtaskRow.setAttribute('data-subtask-id', firstSubtask.subtask_id);
                    
                    // Display the subtask ID in the UI
                    const idDisplay = subtaskRow.querySelector('.subtask-id-display');
                    const idValue = subtaskRow.querySelector('.subtask-id-value');
                    if (idDisplay && idValue) {
                        if (matchingSubtasks.length === 1) {
                            idValue.textContent = firstSubtask.subtask_id;
                        } else {
                            idValue.textContent = `${firstSubtask.subtask_id} (+${matchingSubtasks.length - 1} more)`;
                        }
                        idDisplay.style.display = 'block';
                        idsUpdated++;
                    }
                }
            });
            
            console.log('Updated IDs for', idsUpdated, 'subtask rows');
            
            // Show IDs for 3 seconds, then close
            if (idsUpdated > 0) {
                showNotification('Subtask IDs Generated', 
                    `Unique IDs assigned to ${task.subtasks.length} subtasks.`, 
                    'info', 100);
                
                setTimeout(() => {
                    closeTaskModal();
                }, 3000);
            } else {
                // Close immediately if no IDs to show
                setTimeout(() => {
                    closeTaskModal();
                }, 1000);
            }
        } else {
            console.warn('No subtasks in response, closing modal');
            setTimeout(() => {
                closeTaskModal();
            }, 1000);
        }
    } catch (error) {
        console.error('Failed to load generated subtask IDs:', error);
        setTimeout(() => {
            closeTaskModal();
        }, 1000);
    }
}

// Collect subtasks from form
function collectSubtasks() {
    const subtaskRows = document.querySelectorAll('.subtask-row');
    const subtasks = [];

    subtaskRows.forEach((row, index) => {
        const name = row.querySelector('.subtask-name').value;
        const checkedClients = Array.from(row.querySelectorAll('.client-checkbox:checked')).map(cb => cb.value);
        const existingSubtaskId = row.getAttribute('data-subtask-id'); // Get preserved subtask ID

        if (name && checkedClients.length > 0) {
            // For editing: if we have an existing subtask ID and only one client is selected,
            // preserve the ID. For new subtasks or when multiple clients are selected,
            // each will get a new/separate ID on the server side.
            checkedClients.forEach((clientName, clientIndex) => {
                const subtaskData = {
                    name: name,
                    client: clientName,
                    order: index,
                    args: [],
                    kwargs: {},
                    timeout: 300
                };
                
                // Preserve subtask ID only for the first client if editing
                if (existingSubtaskId && clientIndex === 0) {
                    subtaskData.subtask_id = existingSubtaskId;
                }
                
                subtasks.push(subtaskData);
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
        showNotification('Error', 'Failed to load tasks', 'error');
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
                <td colspan="9" class="no-tasks-message">
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
    
    // Ensure all toggle icons are in correct initial state
    initializeToggleIconStates();
}

// Initialize toggle icon states to match current visibility
function initializeToggleIconStates() {
    // Set individual task toggle icons based on current visibility state
    const allToggleIcons = document.querySelectorAll('.collapse-toggle i[id^="toggle-icon-"]');
    allToggleIcons.forEach(icon => {
        // Since details are visible by default (not collapsed), show chevron-up
        icon.className = 'fas fa-chevron-up';
    });
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
        <td colspan="9">
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
                    <button class="collapse-toggle" onclick="toggleTaskGroup(${task.id})" 
                            title="Toggle subtask details">
                        <i class="fas fa-chevron-up" id="toggle-icon-${task.id}"></i>
                    </button>
                    <button class="btn btn-small btn-primary" onclick="viewTaskDetails(${task.id})" 
                            title="View Details">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn btn-small btn-secondary" onclick="copyTask(${task.id})" 
                            title="Copy Task">
                        <i class="fas fa-copy"></i>
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
            const executionData = findExecutionData(task, subtask.name, subtask.client);
            
            // Determine the subtask_id: prefer execution data, fall back to task definition
            let subtaskId = null;
            if (executionData && executionData.subtask_id !== undefined && executionData.subtask_id !== null) {
                subtaskId = executionData.subtask_id;
            } else if (subtask.subtask_id !== undefined && subtask.subtask_id !== null) {
                subtaskId = subtask.subtask_id;
            }
            
            executions.push({
                subtask_id: subtaskId,
                subtask_name: subtask.name,
                client: subtask.client,
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
        // Legacy subtask-based task
        const targetClients = task.clients && task.clients.length > 0 
            ? task.clients 
            : [task.client || 'Any Available'];
        
        targetClients.forEach(client => {
            executions.push({
                subtask_name: 'Subtask Execution',
                client: client,
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
        return a.client.localeCompare(b.client);
    });
    
    return executions;
}

// Find execution data for a specific subtask-client combination
function findExecutionData(task, subtaskName, targetClient) {
    if (!task.executions) return null;
    
    return task.executions.find(exec => 
        exec.subtask_name === subtaskName && 
        exec.client === targetClient
    );
}

// Determine client working status based on current tasks and heartbeat
function getClientWorkingStatus(client, allTasks) {
    if (!client) {
        return 'unknown';
    }
    
    // Check if client is offline based on heartbeat
    if (client.status === 'offline' || !client.last_heartbeat) {
        return 'offline';
    }
    
    // Check if last heartbeat is too old (more than 30 seconds)
    if (client.last_heartbeat) {
        const lastHeartbeat = new Date(client.last_heartbeat);
        const now = new Date();
        const timeSinceHeartbeat = (now - lastHeartbeat) / 1000; // in seconds
        
        if (timeSinceHeartbeat > 30) {
            return 'offline';
        }
    }
    
    // Check if client is currently working on any running tasks
    const isWorking = allTasks.some(task => {
        if (task.status !== 'running') return false;
        
        // Check if this client has running subtasks in this task
        if (task.executions) {
            return task.executions.some(execution => 
                execution.client === client.name && 
                execution.status === 'running'
            );
        }
        
        // Legacy support: check if client is in task's client list
        return (task.clients && task.clients.includes(client.name)) ||
               (task.client === client.name);
    });
    
    return isWorking ? 'busy' : 'free';
}

// Create a subtask execution row
function createSubtaskExecutionRow(task, execution) {
    const row = document.createElement('tr');
    row.className = `subtask-execution-row task-${task.id}-executions`;
    
    // Get client and determine actual working status
    const client = clientsList.find(m => m.name === execution.client);
    const clientStatus = getClientWorkingStatus(client, allTasks);
    
    // Format timing information
    const timingInfo = formatTimingInfo(execution);
    
    // Format result information
    const resultInfo = formatResultInfo(execution);
    
    row.innerHTML = `
        <td class="task-id-col"></td>
        <td class="task-name-col"></td>
        <td class="subtask-id-col">
            ${execution.subtask_id !== null && execution.subtask_id !== undefined ? `<span class="subtask-id-badge">${execution.subtask_id}</span>` : '<span class="no-id">—</span>'}
        </td>
        <td class="subtask-name-col">
            <div class="subtask-name-info">
                <span class="subtask-name">${execution.subtask_name}</span>
            </div>
        </td>
        <td class="client-col">
            <div class="client-info-inline">
                <span class="client-name">${execution.client}</span>
                <span class="client-status ${clientStatus}">${clientStatus}</span>
                <button class="btn btn-micro btn-outline" onclick="event.stopPropagation(); pingClient('${execution.client}')" title="Ping Client">
                    <i class="fas fa-wifi"></i> Ping Client
                </button>
            </div>
        </td>
        <td class="status-col">
            <span class="status-badge ${execution.status}">${execution.status}</span>
        </td>
        <td class="result-col">
            ${resultInfo}
        </td>
        <td class="timing-col">
            ${timingInfo}
        </td>
        <td class="actions-col">
            <div class="row-actions">
                ${execution.status === 'failed' && execution.error_message ? 
                    `<button class="btn btn-small btn-danger" onclick="showExecutionError('${execution.subtask_name}', '${execution.client}', \`${execution.error_message.replace(/`/g, '\\`')}\`, '${execution.subtask_id !== null && execution.subtask_id !== undefined ? execution.subtask_id : ''}')" title="View Error">
                        <i class="fas fa-exclamation-triangle"></i>
                    </button>` : ''
                }
                ${execution.status === 'pending' && task.status !== 'completed' && task.status !== 'failed' && task.status !== 'cancelled' ? 
                    `<button class="btn btn-small btn-warning" onclick="deleteSubtaskExecution(${task.id}, '${execution.subtask_name}', '${execution.client}', '${execution.subtask_id !== null && execution.subtask_id !== undefined ? execution.subtask_id : ''}')" title="Delete Pending Subtask">
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
    
    return stats;
}

// Format result information for display
function formatResultInfo(execution) {
    if (!execution.result) {
        return '<span class="no-result">—</span>';
    }
    
    const result = execution.result;
    const maxPreviewLength = 50; // Maximum characters to show in preview
    
    // Create preview text
    let preview = result.length > maxPreviewLength 
        ? result.substring(0, maxPreviewLength) + '...' 
        : result;
    
    // Escape HTML and newlines for preview
    preview = escapeHtml(preview.replace(/\n/g, ' '));
    
    // Determine result type for styling
    let resultClass = 'result-preview';
    if (execution.status === 'failed') {
        resultClass += ' result-error';
    } else if (execution.status === 'completed') {
        resultClass += ' result-success';
    }
    
    return `
        <div class="result-info">
            <div class="${resultClass}" title="${escapeHtml(result.substring(0, 200))}">${preview}</div>
            <button class="btn btn-small btn-info result-details-btn" 
                    onclick="showExecutionResult('${execution.subtask_name}', '${execution.client}', \`${result.replace(/`/g, '\\`')}\`, '${execution.subtask_id !== null && execution.subtask_id !== undefined ? execution.subtask_id : ''}')" 
                    title="View Full Result">
                <i class="fas fa-eye"></i>
            </button>
        </div>
    `;
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
        // Update toggle icon based on NEW state after toggle
        // If was collapsed (now expanding) → show up arrow (visible state)  
        // If was visible (now collapsing) → show down arrow (hidden state)
        toggleIcon.className = isCollapsed ? 'fas fa-chevron-up' : 'fas fa-chevron-down';
    }
}

// Toggle all task details visibility (page-wise toggle)
function toggleAllTaskDetails() {
    const toggleIcon = document.getElementById('toggleAllIcon');
    const toggleText = document.getElementById('toggleAllText');
    
    // Get all execution rows and toggle icons
    const allExecutionRows = document.querySelectorAll('.subtask-execution-row');
    const allToggleIcons = document.querySelectorAll('.collapse-toggle i[id^="toggle-icon-"]');
    
    if (allTaskDetailsVisible) {
        // Hide all details
        allExecutionRows.forEach(row => {
            row.classList.add('collapsed');
        });
        
        allToggleIcons.forEach(icon => {
            icon.className = 'fas fa-chevron-down'; // Down arrow when hidden
        });
        
        toggleIcon.className = 'fas fa-eye';
        toggleText.textContent = 'Show All Details';
        allTaskDetailsVisible = false;
    } else {
        // Show all details
        allExecutionRows.forEach(row => {
            row.classList.remove('collapsed');
        });
        
        allToggleIcons.forEach(icon => {
            icon.className = 'fas fa-chevron-up'; // Up arrow when visible
        });
        
        toggleIcon.className = 'fas fa-eye-slash';
        toggleText.textContent = 'Hide All Details';
        allTaskDetailsVisible = true;
    }
}

// Show execution error details
function showExecutionError(subtaskName, targetClient, errorMessage, subtaskId = null) {
    const subtaskDisplay = subtaskId ? `${subtaskName} (ID: ${subtaskId})` : subtaskName;
    showNotification('Execution Error', 
        `Error in ${subtaskDisplay} on ${targetClient}:\n\n${errorMessage}`, 'error');
}

// Show execution result details
function showExecutionResult(subtaskName, targetClient, result, subtaskId = null) {
    const subtaskDisplay = subtaskId ? `${subtaskName} (ID: ${subtaskId})` : subtaskName;
    showNotification('Execution Result', 
        `Result from ${subtaskDisplay} on ${targetClient}:\n\n${result}`, 'info');
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
            const hasTargetClient = task.subtasks && task.subtasks.some(st => st.client === clientFilter) ||
                                   task.clients && task.clients.includes(clientFilter) ||
                                   task.client === clientFilter;
            if (!hasTargetClient) {
                return false;
            }
        }
        
        // Search filter
        if (searchInput) {
            const searchTerm = searchInput.toLowerCase();
            const matchesName = task.name.toLowerCase().includes(searchTerm);
            const matchesSubtaskLegacy = task.command && task.command.toLowerCase().includes(searchTerm);
            const matchesSubtask = task.subtasks && task.subtasks.some(st => 
                st.name.toLowerCase().includes(searchTerm)
            );
            
            if (!matchesName && !matchesSubtaskLegacy && !matchesSubtask) {
                return false;
            }
        }
        
        return true;
    });
    
    tasksCurrentPage = 1;
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
async function deleteSubtaskExecution(taskId, subtaskName, targetClient, subtaskId = null) {
    const subtaskDisplay = subtaskId ? `"${subtaskName}" (ID: ${subtaskId})` : `"${subtaskName}"`;
    
    if (!confirm(`Are you sure you want to delete the pending subtask ${subtaskDisplay} for client "${targetClient}"?\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/tasks/${taskId}/subtasks/${encodeURIComponent(subtaskName)}/delete`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                client: targetClient
            })
        });

        const result = await response.json();

        if (result.success) {
            const successMessage = subtaskId ? 
                `Subtask "${subtaskName}" (ID: ${subtaskId}) deleted successfully` :
                `Subtask "${subtaskName}" deleted successfully`;
            showNotification('Subtask Deleted', successMessage, 'success');
            
            // Check if all subtasks were deleted
            if (result.remaining_subtasks === 0) {
                showNotification('Task Status', 'All subtasks deleted - task has been cancelled', 'info');
            }
            
            // Refresh the task list to show updated state
            await refreshTasks();
        } else {
            showNotification('Error', result.error || 'Failed to delete subtask', 'error');
        }
    } catch (error) {
        console.error('Failed to delete subtask:', error);
        showNotification('Error', 'Failed to delete subtask', 'error');
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
            showNotification('Error', response.error || 'Failed to load task details', 'error');
        }
    } catch (error) {
        console.error('Failed to load task details:', error);
        showNotification('Error', 'Failed to load task details', 'error');
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
            const key = `${exec.subtask_name}_${exec.client}`;
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
            const executionKey = `${subtask.name}_${subtask.client}`;
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
                            ${execution && execution.subtask_id !== null && execution.subtask_id !== undefined ? `<span class="subtask-id-badge">ID: ${execution.subtask_id}</span>` : ''}
                        </div>
                    </div>
                    <div class="subtask-detail-content">
                        <div class="detail-grid">
                            ${execution && execution.subtask_id !== null && execution.subtask_id !== undefined ? `
                                <div class="detail-item">
                                    <label>Subtask ID:</label>
                                    <span>${execution.subtask_id}</span>
                                </div>
                            ` : ''}
                            <div class="detail-item">
                                <label>Subtask Name:</label>
                                <span>${subtask.name}</span>
                            </div>
                            <div class="detail-item">
                                <label>Target Client:</label>
                                <span>${subtask.client}</span>
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
                <h4>Legacy Subtask</h4>
                <div class="subtask-detail">
                    <code>${task.command}</code>
                </div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <label>Target Client:</label>
                        <span>${task.client || 'Any available'}</span>
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

// Copy task - open copy modal with original task data
async function copyTask(taskId) {
    try {
        const response = await apiGet(`/api/tasks/${taskId}`);
        if (response.success) {
            const originalTask = response.data;
            openTaskCopyModal(originalTask);
        } else {
            showNotification('Error', response.error || 'Failed to load task for copying', 'error');
        }
    } catch (error) {
        console.error('Failed to load task for copying:', error);
        showNotification('Error', 'Failed to load task for copying', 'error');
    }
}

// Open task copy modal
function openTaskCopyModal(originalTask) {
    const modal = document.getElementById('taskCopyModal');
    const form = document.getElementById('taskCopyForm');
    
    // Reset form
    form.reset();
    
    // Set original task data
    document.getElementById('originalTaskId').value = originalTask.id;
    document.getElementById('copyTaskName').value = `${originalTask.name} (Copy)`;
    
    // Set original email settings
    document.getElementById('copySendEmail').checked = originalTask.send_email || false;
    document.getElementById('copyEmailRecipients').value = originalTask.email_recipients || '';
    
    // Set default schedule to immediate
    document.getElementById('copyScheduleType').value = 'immediate';
    
    // Update modal title
    document.getElementById('copyModalTitle').textContent = `Copy Task: ${originalTask.name}`;
    
    // Populate client updates list
    populateClientUpdatesList(originalTask);
    
    // Toggle visibility of schedule and email options
    toggleCopyScheduleOptions();
    toggleCopyEmailRecipients();
    
    modal.style.display = 'block';
}

// Close task copy modal
function closeTaskCopyModal() {
    document.getElementById('taskCopyModal').style.display = 'none';
}

// Toggle copy schedule options
function toggleCopyScheduleOptions() {
    const scheduleType = document.getElementById('copyScheduleType').value;
    const scheduleTimeGroup = document.getElementById('copyScheduleTimeGroup');
    const cronGroup = document.getElementById('copyCronGroup');
    
    scheduleTimeGroup.style.display = scheduleType === 'scheduled' ? 'block' : 'none';
    cronGroup.style.display = scheduleType === 'cron' ? 'block' : 'none';
}

// Toggle copy email recipients field
function toggleCopyEmailRecipients() {
    const sendEmail = document.getElementById('copySendEmail').checked;
    const emailRecipientsGroup = document.getElementById('copyEmailRecipientsGroup');
    
    emailRecipientsGroup.style.display = sendEmail ? 'block' : 'none';
}

// Populate client updates list for copy modal
function populateClientUpdatesList(originalTask) {
    const clientUpdatesList = document.getElementById('clientUpdatesList');
    
    if (!originalTask.subtasks || originalTask.subtasks.length === 0) {
        clientUpdatesList.innerHTML = '<p class="help-text">No subtasks to configure client assignments.</p>';
        return;
    }
    
    // Get unique clients from original task
    const uniqueClients = [...new Set(originalTask.subtasks.map(st => st.client))];
    
    if (uniqueClients.length === 0) {
        clientUpdatesList.innerHTML = '<p class="help-text">No client assignments to modify.</p>';
        return;
    }
    
    let html = '<div class="help-text" style="margin-bottom: 15px;">Choose new clients for the copied task (leave unchanged to keep original assignments):</div>';
    
    uniqueClients.forEach(originalClient => {
        html += `
            <div class="client-update-item">
                <label>Client "${originalClient}":</label>
                <select class="client-update-select" data-original-client="${originalClient}">
                    <option value="${originalClient}">Keep: ${originalClient}</option>
                    ${clientsList.map(client => 
                        client.name !== originalClient ? 
                        `<option value="${client.name}">Change to: ${client.name}</option>` : ''
                    ).join('')}
                </select>
            </div>
        `;
    });
    
    clientUpdatesList.innerHTML = html;
}

// Save task copy
async function saveTaskCopy() {
    try {
        const originalTaskId = document.getElementById('originalTaskId').value;
        const copyData = {
            name: document.getElementById('copyTaskName').value.trim(),
            send_email: document.getElementById('copySendEmail').checked,
            email_recipients: document.getElementById('copyEmailRecipients').value.trim()
        };
        
        if (!copyData.name) {
            showNotification('Validation Error', 'Task name is required', 'error');
            return;
        }
        
        // Handle schedule
        const scheduleType = document.getElementById('copyScheduleType').value;
        copyData.schedule_type = scheduleType;
        
        if (scheduleType === 'scheduled') {
            const scheduleTime = document.getElementById('copyScheduleTime').value;
            if (scheduleTime) {
                copyData.schedule_time = scheduleTime;
            }
        } else if (scheduleType === 'cron') {
            const cronExpression = document.getElementById('copyCronExpression').value.trim();
            if (cronExpression) {
                copyData.cron_expression = cronExpression;
            }
        }
        
        // Handle client updates
        const clientUpdateSelects = document.querySelectorAll('.client-update-select');
        if (clientUpdateSelects.length > 0) {
            copyData.update_clients = true;
            copyData.client_updates = {};
            
            clientUpdateSelects.forEach(select => {
                const originalClient = select.getAttribute('data-original-client');
                const newClient = select.value;
                if (newClient !== originalClient) {
                    copyData.client_updates[originalClient] = newClient;
                }
            });
        }
        
        // Submit copy request
        const response = await apiPost(`/api/tasks/${originalTaskId}/copy`, copyData);
        
        if (response.success) {
            showNotification('Success', response.message || 'Task copied successfully', 'success');
            closeTaskCopyModal();
            await refreshTasks();
        } else {
            showNotification('Error', response.error || 'Failed to copy task', 'error');
        }
        
    } catch (error) {
        console.error('Failed to copy task:', error);
        showNotification('Error', 'Failed to copy task', 'error');
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
                // Create a subtask row for each individual subtask (preserving unique IDs)
                task.subtasks.forEach(subtask => {
                    addSubtask();
                    const subtaskRows = document.querySelectorAll('.subtask-row');
                    const subtaskRow = subtaskRows[subtaskRows.length - 1];

                    // Set subtask name
                    subtaskRow.querySelector('.subtask-name').value = subtask.name;
                    
                    // Store the subtask ID for preservation during save
                    if (subtask.subtask_id) {
                        subtaskRow.setAttribute('data-subtask-id', subtask.subtask_id);
                        
                        // Display the subtask ID in the UI
                        const idDisplay = subtaskRow.querySelector('.subtask-id-display');
                        const idValue = subtaskRow.querySelector('.subtask-id-value');
                        if (idDisplay && idValue) {
                            idValue.textContent = subtask.subtask_id;
                            idDisplay.style.display = 'block';
                        }
                    }
                    
                    // Select the target client for this specific subtask
                    const clientCheckbox = subtaskRow.querySelector(`.client-checkbox[value="${subtask.client}"]`);
                    if (clientCheckbox) {
                        clientCheckbox.checked = true;
                        // Update client selection state
                        updateClientSelection(clientCheckbox);
                    }

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
            showNotification('Error', response.error || 'Failed to load task data', 'error');
        }
    } catch (error) {
        console.error('Failed to load task for edit:', error);
        showNotification('Error', 'Failed to load task data', 'error');
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
        // Add clients from subtasks
        if (task.subtasks) {
            task.subtasks.forEach(subtask => {
                if (subtask.client && subtask.client !== 'any_available') {
                    clientNames.add(subtask.client);
                }
            });
        }
        
        // Add clients from legacy task format
        if (task.clients) {
            task.clients.forEach(client => {
                if (client && client !== 'any_available') {
                    clientNames.add(client);
                }
            });
        }
        
        // Add single target client
        if (task.client && task.client !== 'any_available') {
            clientNames.add(task.client);
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

// Ping client and refresh its status
async function pingClient(clientName) {
    try {
        showNotification('Info', `Pinging ${clientName}...`, 'info');
        
        const response = await apiPost(`/api/clients/${clientName}/ping`);
        
        if (response.success) {
            showNotification('Success', 
                `${clientName} is reachable (${response.data.response_time})`, 'success');
            
            // Refresh task list to show updated client status
            await refreshTasks();
        } else {
            const errorMsg = response.message || response.error || 'Client not reachable';
            showNotification('Warning', errorMsg, 'warning');
            
            // Still refresh to show offline status
            await refreshTasks();
        }
    } catch (error) {
        console.error('Ping client failed:', error);
        showNotification('Error', error.message || 'Failed to ping client', 'error');
        
        // Refresh anyway to potentially show updated status
        await refreshTasks();
    }
}
