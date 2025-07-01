/**
 * Task Management page JavaScript with Subtask Support
 */

console.log('Loading tasks.js...');

let tasksList = [];
let machinesList = [];
let availableSubtasks = [];
let filteredTasks = [];
let tasksCurrentPage = 1;
const tasksItemsPerPage = 10;

console.log('Tasks.js variables initialized');

// Initialize after page load
document.addEventListener('DOMContentLoaded', function() {
    initializeTasksPage();
});

// Initialize task page
async function initializeTasksPage() {
    await loadMachines();
    await loadAvailableSubtasks();
    await refreshTasks();
    populateMachineFilter();
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

// Load machines from server
async function loadMachines() {
    try {
        const response = await apiGet('/api/machines');
        machinesList = response.data || [];
    } catch (error) {
        console.error('Failed to load machines:', error);
        showNotification('Failed to load machines', 'error');
    }
}

// Load available subtasks from server
async function loadAvailableSubtasks() {
    try {
        const response = await apiGet('/api/subtasks');
        availableSubtasks = response.data || [];
        console.log('Loaded available subtasks:', availableSubtasks);
    } catch (error) {
        console.error('Failed to load available subtasks:', error);
        showNotification('Failed to load available subtasks', 'error');
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
                        ${availableSubtasks.map(subtask =>
                            `<option value="${subtask.name}">${subtask.name}</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label>Target Machines <span class="required">*</span></label>
                    <div class="machine-selection">
                        <div class="machine-option">
                            <label class="checkbox-label">
                                <input type="checkbox" class="all-machines-checkbox" onchange="toggleAllMachines(this)">
                                <span>All Machines</span>
                            </label>
                        </div>
                        ${machinesList.map(machine =>
                            `<div class="machine-option">
                                <label class="checkbox-label">
                                    <input type="checkbox" class="machine-checkbox" value="${machine.name}" onchange="updateMachineSelection(this)">
                                    <span>${machine.name} (${machine.ip_address})</span>
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

// Toggle all machines selection
function toggleAllMachines(checkbox) {
    if (!checkbox) return;
    
    const subtaskRow = checkbox.closest('.subtask-row');
    if (!subtaskRow) return;
    
    const machineCheckboxes = subtaskRow.querySelectorAll('.machine-checkbox');

    machineCheckboxes.forEach(cb => {
        cb.checked = checkbox.checked;
    });
}

// Update machine selection when individual checkboxes change
function updateMachineSelection(checkbox) {
    if (!checkbox) return;
    
    const subtaskRow = checkbox.closest('.subtask-row');
    if (!subtaskRow) return;
    
    const allMachinesCheckbox = subtaskRow.querySelector('.all-machines-checkbox');
    const machineCheckboxes = subtaskRow.querySelectorAll('.machine-checkbox');
    const checkedBoxes = subtaskRow.querySelectorAll('.machine-checkbox:checked');

    if (!allMachinesCheckbox) return;

    // Update "All Machines" checkbox state
    if (checkedBoxes.length === machineCheckboxes.length) {
        allMachinesCheckbox.checked = true;
        allMachinesCheckbox.indeterminate = false;
    } else if (checkedBoxes.length === 0) {
        allMachinesCheckbox.checked = false;
        allMachinesCheckbox.indeterminate = false;
    } else {
        allMachinesCheckbox.checked = false;
        allMachinesCheckbox.indeterminate = true;
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
            descriptionDiv.innerHTML = `
                <small class="help-text">
                    <strong>${subtask.name}:</strong> ${subtask.description}
                </small>
            `;
        }
    } else {
        descriptionDiv.innerHTML = '<small class="help-text">Select a subtask to see its description</small>';
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
        const checkedMachines = Array.from(row.querySelectorAll('.machine-checkbox:checked')).map(cb => cb.value);

        if (name && checkedMachines.length > 0) {
            // Create a subtask for each selected machine
            checkedMachines.forEach((machineName, machineIndex) => {
                subtasks.push({
                    name: name,
                    target_machine: machineName,
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

// Load tasks from server
async function refreshTasks() {
    try {
        const response = await apiGet('/api/tasks');
        tasksList = response.data || [];
        filterTasks();
        renderTasks();
    } catch (error) {
        console.error('Failed to load tasks:', error);
        showNotification('Failed to load tasks', 'error');
    }
}

// Filter tasks based on current filters
function filterTasks() {
    filteredTasks = tasksList;
    // Add filtering logic here if needed
    tasksCurrentPage = 1;
}

// Render tasks table
function renderTasks() {
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
                <td colspan="8" class="text-center">No tasks found</td>
            </tr>
        `;
        return;
    }

    paginatedTasks.forEach(task => {
        const row = document.createElement('tr');

        // Get subtask details
        const subtaskCount = task.subtasks ? task.subtasks.length : 0;
        const subtaskDetails = subtaskCount > 0
            ? `${subtaskCount} subtask${subtaskCount > 1 ? 's' : ''}`
            : 'No subtasks';

        // Get target machines
        const targetMachines = task.subtasks && task.subtasks.length > 0
            ? [...new Set(task.subtasks.map(st => st.target_machine))].join(', ')
            : task.target_machine || 'Not specified';

        row.innerHTML = `
            <td>${task.id}</td>
            <td>${task.name}</td>
            <td>${subtaskDetails}</td>
            <td>${targetMachines}</td>
            <td><span class="status-badge ${task.status}">${task.status}</span></td>
            <td>${task.schedule_time ? new Date(task.schedule_time).toLocaleString() : task.cron_expression || 'Immediate'}</td>
            <td>${task.created_at ? new Date(task.created_at).toLocaleString() : '-'}</td>
            <td class="task-actions">
                <button class="btn btn-small btn-primary" onclick="viewTaskDetails(${task.id})" title="View Details">
                    <i class="fas fa-eye"></i>
                </button>
                <button class="btn btn-small btn-secondary" onclick="openTaskModal(${task.id})" title="Edit">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn btn-small btn-danger" onclick="deleteTask(${task.id})" title="Delete">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        `;

        tasksTableBody.appendChild(row);
    });

    updatePagination();
}

// Update pagination
function updatePagination() {
    const totalPages = Math.ceil(filteredTasks.length / tasksItemsPerPage);
    const pagination = document.getElementById('pagination');

    pagination.innerHTML = '';

    if (totalPages <= 1) return;

    // Previous button
    const prevButton = document.createElement('button');
    prevButton.textContent = 'Previous';
    prevButton.disabled = tasksCurrentPage === 1;
    prevButton.onclick = () => {
        if (tasksCurrentPage > 1) {
            tasksCurrentPage--;
            renderTasks();
        }
    };
    pagination.appendChild(prevButton);

    // Page numbers
    for (let i = 1; i <= totalPages; i++) {
        const pageButton = document.createElement('button');
        pageButton.textContent = i;
        pageButton.className = i === tasksCurrentPage ? 'active' : '';
        pageButton.onclick = () => {
            tasksCurrentPage = i;
            renderTasks();
        };
        pagination.appendChild(pageButton);
    }

    // Next button
    const nextButton = document.createElement('button');
    nextButton.textContent = 'Next';
    nextButton.disabled = tasksCurrentPage === totalPages;
    nextButton.onclick = () => {
        if (tasksCurrentPage < totalPages) {
            tasksCurrentPage++;
            renderTasks();
        }
    };
    pagination.appendChild(nextButton);
}

// Delete task
async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) return;

    try {
        const response = await apiDelete(`/api/tasks/${taskId}`);

        if (response.success) {
            showNotification('Task deleted successfully', 'success');
            await refreshTasks();
        } else {
            showNotification(response.error || 'Failed to delete task', 'error');
        }
    } catch (error) {
        console.error('Failed to delete task:', error);
        showNotification('Failed to delete task', 'error');
    }
}

// View task details
async function viewTaskDetails(taskId) {
    try {
        const response = await apiGet(`/api/tasks/${taskId}`);

        if (response.success) {
            const task = response.data;
            displayTaskDetails(task);
        } else {
            showNotification(response.error || 'Failed to load task details', 'error');
        }
    } catch (error) {
        console.error('Failed to load task details:', error);
        showNotification('Failed to load task details', 'error');
    }
}

// Display task details in modal
function displayTaskDetails(task) {
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
            </div>
        </div>
    `;

    if (task.subtasks && task.subtasks.length > 0) {
        detailsHtml += `
            <div class="task-detail-section">
                <h4>Subtasks (${task.subtasks.length})</h4>
                <div class="subtasks-detail">
        `;

        task.subtasks.forEach((subtask, index) => {
            detailsHtml += `
                <div class="subtask-detail-item">
                    <div class="subtask-detail-header">
                        <h5>Subtask ${index + 1}: ${subtask.name}</h5>
                        <span class="subtask-order">Order: ${subtask.order}</span>
                    </div>
                    <div class="subtask-detail-content">
                        <div class="detail-grid">
                            <div class="detail-item">
                                <label>Target Machine:</label>
                                <span>${subtask.target_machine}</span>
                            </div>
                            <div class="detail-item">
                                <label>Timeout:</label>
                                <span>${subtask.timeout || 300}s</span>
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
                        <label>Target Machine:</label>
                        <span>${task.target_machine || 'Any available'}</span>
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

    content.innerHTML = detailsHtml;
    modal.style.display = 'block';
}

// Close task detail modal
function closeTaskDetailModal() {
    document.getElementById('taskDetailModal').style.display = 'none';
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
                // Group subtasks by name and order to handle multiple machines per subtask
                const subtaskGroups = {};
                task.subtasks.forEach(subtask => {
                    const key = `${subtask.name}_${subtask.order}`;
                    if (!subtaskGroups[key]) {
                        subtaskGroups[key] = {
                            name: subtask.name,
                            order: subtask.order,
                            machines: []
                        };
                    }
                    subtaskGroups[key].machines.push(subtask.target_machine);
                });

                // Create subtask rows for each group
                Object.values(subtaskGroups).forEach(group => {
                    addSubtask();
                    const subtaskRows = document.querySelectorAll('.subtask-row');
                    const subtaskRow = subtaskRows[subtaskRows.length - 1];

                    // Set subtask name
                    subtaskRow.querySelector('.subtask-name').value = group.name;

                    // Select the appropriate machines
                    group.machines.forEach(machineName => {
                        const machineCheckbox = subtaskRow.querySelector(`.machine-checkbox[value="${machineName}"]`);
                        if (machineCheckbox) {
                            machineCheckbox.checked = true;
                        }
                    });

                    // Update machine selection state
                    updateMachineSelection(subtaskRow.querySelector('.machine-checkbox'));

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
        } else {
            showNotification(response.error || 'Failed to load task data', 'error');
        }
    } catch (error) {
        console.error('Failed to load task for edit:', error);
        showNotification('Failed to load task data', 'error');
    }
}

// Populate machine filter dropdown
function populateMachineFilter() {
    // Implementation for machine filter if needed
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
