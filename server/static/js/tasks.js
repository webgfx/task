/**
 * Task Management page JavaScript
 */

let tasks = [];
let machines = [];
let filteredTasks = [];
let currentPage = 1;
const itemsPerPage = 10;

// Initialize after page load
document.addEventListener('DOMContentLoaded', function() {
    initializeTasksPage();
});

// Initialize task page
async function initializeTasksPage() {
    await loadMachines();
    await refreshTasks();
    populateMachineFilter();
    setupEventListeners();
}

// settings[TRANSLATED] [TRANSLATED]server
function setupEventListeners() {
    // tablesingleSubmit
    document.getElementById('taskForm').addEventListener('submit', function(e) {
        e.preventDefault();
        saveTask();
    });
    
    // [TRANSLATED] [TRANSLATED]close
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

// loadMachine [TRANSLATED]table
async function loadMachines() {
    try {
        const response = await apiGet('/api/machines');
        machines = response.data || [];
    } catch (error) {
        console.error('loadMachine[TRANSLATED]tableFailed:', error);
        machines = [];
    }
}

// [TRANSLATED] [TRANSLATED]MachineFilter
function populateMachineFilter() {
    const machineFilter = document.getElementById('machineFilter');
    const targetMachineSelect = document.getElementById('targetMachine');
    
    // Clear[TRANSLATED] [TRANSLATED]options
    machineFilter.innerHTML = '<option value=>allMachine</option>';
    targetMachineSelect.innerHTML = '<option value=>[TRANSLATED]availableMachine</option>';
    
    // [TRANSLATED] [TRANSLATED]Machineoptions
    machines.forEach(machine => {
        const option1 = document.createElement('option');
        option1.value = machine.name;
        option1.textContent = `${machine.name} (${machine.status})`;
        machineFilter.appendChild(option1);
        
        const option2 = document.createElement('option');
        option2.value = machine.name;
        option2.textContent = `${machine.name} (${machine.ip_address})`;
        targetMachineSelect.appendChild(option2);
    });
}

// RefreshTask [TRANSLATED]table
async function refreshTasks() {
    try {
        showLoading(document.querySelector('.task-table-container'));
        const response = await apiGet('/api/tasks');
        tasks = response.data || [];
        filterTasks();
    } catch (error) {
        console.error('RefreshTask[TRANSLATED]tableFailed:', error);
        showNotification('RefreshFailed', error.message, 'error');
    } finally {
        hideLoading(document.querySelector('.task-table-container'));
    }
}

// [TRANSLATED] [TRANSLATED]Task
function filterTasks() {
    const statusFilter = document.getElementById('statusFilter').value;
    const machineFilter = document.getElementById('machineFilter').value;
    const searchInput = document.getElementById('searchInput').value.toLowerCase();
    
    filteredTasks = tasks.filter(task => {
        const statusMatch = !statusFilter || task.status === statusFilter;
        const machineMatch = !machineFilter || task.target_machine === machineFilter;
        const searchMatch = !searchInput || 
            task.name.toLowerCase().includes(searchInput) ||
            task.command.toLowerCase().includes(searchInput);
        
        return statusMatch && machineMatch && searchMatch;
    });
    
    currentPage = 1;
    displayTasks();
    updatePagination();
}

// showTask [TRANSLATED]table
function displayTasks() {
    const tbody = document.getElementById('taskTableBody');
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const currentTasks = filteredTasks.slice(startIndex, endIndex);
    
    if (currentTasks.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan=8 style=text-align: center; padding: 40px; color: #6c757d;>
                    ${filteredTasks.length === 0 ? 'NoTask' : 'current[TRANSLATED]data'}
                </td>
            </tr>
        `;
        return;
    }
    
    const html = currentTasks.map(task => `
        <tr>
            <td>${task.id}</td>
            <td>${escapeHtml(task.name)}</td>
            <td class=command-cell title=${escapeHtml(task.command)}>${escapeHtml(task.command)}</td>
            <td>${task.target_machine || '[TRANSLATED]Machine'}</td>
            <td>${getStatusBadge(task.status)}</td>
            <td>${formatDateTime(task.schedule_time) || (task.cron_expression ? `Cron: ${task.cron_expression}` : 'Execute Now')}</td>
            <td>${formatDateTime(task.created_at)}</td>
            <td>
                <div class=action-buttons>
                    <button class=btn btn-sm btn-outline onclick=viewTaskDetail(${task.id}) title=viewdetails>
                        <i class=fas fa-eye></i>
                    </button>
                    <button class=btn btn-sm btn-secondary onclick=editTask(${task.id}) title=Edit>
                        <i class=fas fa-edit></i>
                    </button>
                    ${task.status === 'running' || task.status === 'pending' ? `
                    <button class=btn btn-sm btn-warning onclick=cancelTask(${task.id}) title=Cancel>
                        <i class=fas fa-stop></i>
                    </button>
                    ` : ''}
                    <button class=btn btn-sm btn-danger onclick=deleteTask(${task.id}) title=Delete>
                        <i class=fas fa-trash></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
    
    tbody.innerHTML = html;
}

// Update Pagination
function updatePagination() {
    const paginationContainer = document.getElementById('pagination');
    const totalItems = filteredTasks.length;
    
    createPagination(totalItems, currentPage, itemsPerPage, paginationContainer, 'goToPage');
}

// [TRANSLATED]to[TRANSLATED] [TRANSLATED]
function goToPage(page) {
    currentPage = page;
    displayTasks();
    updatePagination();
}

// openTask[TRANSLATED] [TRANSLATED]
function openTaskModal(taskData = null) {
    const modal = document.getElementById('taskModal');
    const form = document.getElementById('taskForm');
    const title = document.getElementById('modalTitle');
    
    clearForm(form);
    
    if (taskData) {
        title.textContent = 'EditTask';
        setFormData(form, taskData);
        
        // set schedule type
        if (taskData.cron_expression) {
            document.getElementById('scheduleType').value = 'cron';
        } else if (taskData.schedule_time) {
            document.getElementById('scheduleType').value = 'scheduled';
        } else {
            document.getElementById('scheduleType').value = 'immediate';
        }
        
        toggleScheduleOptions();
    } else {
        title.textContent = 'Create Task';
    }
    
    modal.style.display = 'block';
}

// closeTask[TRANSLATED] [TRANSLATED]
function closeTaskModal() {
    const modal = document.getElementById('taskModal');
    modal.style.display = 'none';
}

// toggle[TRANSLATED] [TRANSLATED]options
function toggleScheduleOptions() {
    const scheduleType = document.getElementById('scheduleType').value;
    const scheduleTimeGroup = document.getElementById('scheduleTimeGroup');
    const cronGroup = document.getElementById('cronGroup');
    
    scheduleTimeGroup.style.display = scheduleType === 'scheduled' ? 'block' : 'none';
    cronGroup.style.display = scheduleType === 'cron' ? 'block' : 'none';
}

// SaveTask
async function saveTask() {
    const form = document.getElementById('taskForm');
    
    if (!validateForm(form)) {
        showNotification('validateFailed', 'please[TRANSLATED]Required field', 'error');
        return;
    }
    
    try {
        const formData = getFormData(form);
        const taskData = {
            name: formData.taskName,
            command: formData.taskCommand,
            target_machine: formData.targetMachine || null,
            max_retries: parseInt(formData.maxRetries) || 3
        };
        
        // Process[TRANSLATED] [TRANSLATED]settings
        switch (formData.scheduleType) {
            case 'scheduled':
                if (formData.scheduleTime) {
                    taskData.schedule_time = formData.scheduleTime;
                }
                break;
            case 'cron':
                if (formData.cronExpression) {
                    taskData.cron_expression = formData.cronExpression;
                }
                break;
        }
        
        const taskId = formData.taskId;
        let response;
        
        if (taskId) {
            // Update task
            response = await apiPut(`/api/tasks/${taskId}`, taskData);
        } else {
            // Create Task
            response = await apiPost('/api/tasks', taskData);
        }
        
        showNotification(
            taskId ? 'Task Updated' : 'Task Created', 
            `Task ${taskData.name} ${taskId ? 'update' : 'create'}Success`, 
            'success'
        );
        
        closeTaskModal();
        refreshTasks();
        
    } catch (error) {
        console.error('SaveTaskFailed:', error);
        showNotification('SaveFailed', error.message, 'error');
    }
}

// EditTask
function editTask(taskId) {
    const task = tasks.find(t => t.id === taskId);
    if (task) {
        openTaskModal(task);
    }
}

// Delete task
function deleteTask(taskId) {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    
    confirmAction(`确认删除任务 ${task.name} 吗？`, async () => {
        try {
            await apiDelete(`/api/tasks/${taskId}`);
            showNotification('Task Deleted', `Task ${task.name} deleted`, 'success');
            refreshTasks();
        } catch (error) {
            console.error('Delete taskFailed:', error);
            showNotification('DeleteFailed', error.message, 'error');
        }
    });
}

// Cancel task
function cancelTask(taskId) {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    
    confirmAction(`确认取消任务 ${task.name} 吗？`, async () => {
        try {
            await apiPost(`/api/tasks/${taskId}/cancel`, {});
            showNotification('Task Cancelled', `Task ${task.name} cancelled`, 'success');
            refreshTasks();
        } catch (error) {
            console.error('Cancel taskFailed:', error);
            showNotification('CancelFailed', error.message, 'error');
        }
    });
}

// viewTaskdetails
async function viewTaskDetail(taskId) {
    try {
        const response = await apiGet(`/api/tasks/${taskId}`);
        const task = response.data;
        
        // Get execute[TRANSLATED]
        const execResponse = await apiGet(`/api/tasks/${taskId}/executions`);
        const executions = execResponse.data || [];
        
        showTaskDetailModal(task, executions);
        
    } catch (error) {
        console.error('Get taskdetailsFailed:', error);
        showNotification('Get detailsFailed', error.message, 'error');
    }
}

// showTaskdetails[TRANSLATED] [TRANSLATED]
function showTaskDetailModal(task, executions) {
    const modal = document.getElementById('taskDetailModal');
    const content = document.getElementById('taskDetailContent');
    
    const html = `
        <div class=task-detail>
            <div class=detail-section>
                <h4>basicInfo</h4>
                <div class=detail-grid>
                    <div class=detail-item>
                        <label>TaskID:</label>
                        <span>${task.id}</span>
                    </div>
                    <div class=detail-item>
                        <label>Task Name:</label>
                        <span>${escapeHtml(task.name)}</span>
                    </div>
                    <div class=detail-item>
                        <label>Status:</label>
                        <span>${getStatusBadge(task.status)}</span>
                    </div>
                    <div class=detail-item>
                        <label>Target Machine:</label>
                        <span>${task.target_machine || '[TRANSLATED]availableMachine'}</span>
                    </div>
                </div>
            </div>
            
            <div class=detail-section>
                <h4>Command</h4>
                <div class=command-display>${escapeHtml(task.command)}</div>
            </div>
            
            <div class=detail-section>
                <h4>[TRANSLATED]settings</h4>
                <div class=detail-grid>
                    <div class=detail-item>
                        <label>schedule time:</label>
                        <span>${formatDateTime(task.schedule_time) || '-'}</span>
                    </div>
                    <div class=detail-item>
                        <label>Crontable[TRANSLATED]:</label>
                        <span>${task.cron_expression || '-'}</span>
                    </div>
                    <div class=detail-item>
                        <label>maximumRetry Count:</label>
                        <span>${task.max_retries}</span>
                    </div>
                    <div class=detail-item>
                        <label>currentRetry Count:</label>
                        <span>${task.retry_count}</span>
                    </div>
                </div>
            </div>
            
            <div class=detail-section>
                <h4>timeInfo</h4>
                <div class=detail-grid>
                    <div class=detail-item>
                        <label>Created time:</label>
                        <span>${formatDateTime(task.created_at)}</span>
                    </div>
                    <div class=detail-item>
                        <label>Start time:</label>
                        <span>${formatDateTime(task.started_at)}</span>
                    </div>
                    <div class=detail-item>
                        <label>complete time:</label>
                        <span>${formatDateTime(task.completed_at)}</span>
                    </div>
                </div>
            </div>
            
            ${task.result ? `
            <div class=detail-section>
                <h4>executeresult</h4>
                <div class=result-display success>${escapeHtml(task.result)}</div>
            </div>
            ` : ''}
            
            ${task.error_message ? `
            <div class=detail-section>
                <h4>ErrorInfo</h4>
                <div class=result-display error>${escapeHtml(task.error_message)}</div>
            </div>
            ` : ''}
            
            <div class=detail-section>
                <h4>execute[TRANSLATED]</h4>
                ${executions.length > 0 ? `
                    <div class=execution-list>
                        ${executions.map(exec => `
                            <div class=execution-item>
                                <div class=execution-header>
                                    <span class=execution-machine>${exec.machine_name}</span>
                                    <span class=execution-status>${getStatusBadge(exec.status)}</span>
                                    <span class=execution-time>${formatDateTime(exec.started_at)}</span>
                                </div>
                                ${exec.output ? `<div class=execution-output>${escapeHtml(exec.output)}</div>` : ''}
                                ${exec.error_output ? `<div class=execution-error>${escapeHtml(exec.error_output)}</div>` : ''}
                            </div>
                        `).join('')}
                    </div>
                ` : '<p style=color: #6c757d;>Noexecute[TRANSLATED]</p>'}
            </div>
        </div>
    `;
    
    content.innerHTML = html;
    modal.style.display = 'block';
}

// closeTaskdetails[TRANSLATED] [TRANSLATED]
function closeTaskDetailModal() {
    const modal = document.getElementById('taskDetailModal');
    modal.style.display = 'none';
}

// HTMLescape[TRANSLATED] [TRANSLATED]
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// [TRANSLATED]CSS[TRANSLATED] [TRANSLATED]
const style = document.createElement('style');
style.textContent = `
    .btn-sm {
        padding: 5px 10px;
        font-size: 0.8rem;
    }
    
    .action-buttons {
        display: flex;
        gap: 5px;
    }
    
    .detail-section {
        margin-bottom: 25px;
        padding-bottom: 20px;
        border-bottom: 1px solid #e1e8ed;
    }
    
    .detail-section:last-child {
        border-bottom: none;
    }
    
    .detail-section h4 {
        margin-bottom: 15px;
        color: #2c3e50;
        font-weight: 600;
    }
    
    .detail-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 15px;
    }
    
    .detail-item {
        display: flex;
        flex-direction: column;
        gap: 5px;
    }
    
    .detail-item label {
        font-weight: 600;
        color: #6c757d;
        font-size: 0.9rem;
    }
    
    .detail-item span {
        color: #2c3e50;
    }
    
    .command-display {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 6px;
        font-family: 'Courier New', monospace;
        border-left: 4px solid #667eea;
    }
    
    .result-display {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 6px;
        font-family: 'Courier New', monospace;
        white-space: pre-wrap;
        max-height: 200px;
        overflow-y: auto;
    }
    
    .result-display.success {
        border-left: 4px solid #28a745;
    }
    
    .result-display.error {
        border-left: 4px solid #dc3545;
    }
    
    .execution-list {
        max-height: 300px;
        overflow-y: auto;
    }
    
    .execution-item {
        background-color: #f8f9fa;
        border-radius: 6px;
        padding: 15px;
        margin-bottom: 10px;
    }
    
    .execution-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    
    .execution-machine {
        font-weight: 600;
        color: #2c3e50;
    }
    
    .execution-time {
        font-size: 0.9rem;
        color: #6c757d;
    }
    
    .execution-output,
    .execution-error {
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        white-space: pre-wrap;
        padding: 10px;
        border-radius: 4px;
        margin-top: 10px;
    }
    
    .execution-output {
        background-color: #d4edda;
        color: #155724;
    }
    
    .execution-error {
        background-color: #f8d7da;
        color: #721c24;
    }
`;
document.head.appendChild(style);
