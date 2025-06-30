/**
 * Dashboard page JavaScript
 */

let dashboardData = {
    tasks: [],
    machines: []
};

// Initialize after page load
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
    startAutoRefresh();
});

// Initialize dashboard
async function initializeDashboard() {
    await loadDashboardData();
    updateStatistics();
    displayRecentTasks();
    displayMachineStatus();
    addLogEntry('systemstarted', 'info');
}

// Load dashboard data
async function loadDashboardData() {
    try {
        const [tasksResponse, machinesResponse] = await Promise.all([
            apiGet('/api/tasks'),
            apiGet('/api/machines')
        ]);
        
        dashboardData.tasks = tasksResponse.data || [];
        dashboardData.machines = machinesResponse.data || [];
        
    } catch (error) {
        console.error('Failed to load dashboard data:', error);
        addLogEntry(`Data loading failed: ${error.message}`, 'error');
    }
}

// Update statistics
function updateStatistics() {
    const tasks = dashboardData.tasks;
    const machines = dashboardData.machines;
    
    // Calculate statistics
    const totalTasks = tasks.length;
    const runningTasks = tasks.filter(task => task.status === 'running').length;
    const completedTasks = tasks.filter(task => task.status === 'completed').length;
    const onlineMachines = machines.filter(machine => machine.status === 'online').length;
    
    // Update page display
    updateElement('totalTasks', totalTasks);
    updateElement('runningTasks', runningTasks);
    updateElement('completedTasks', completedTasks);
    updateElement('onlineMachines', onlineMachines);
}

// showRecent Tasks
function displayRecentTasks() {
    const container = document.getElementById('recentTasks');
    if (!container) return;
    
    const recentTasks = dashboardData.tasks
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
        .slice(0, 5);
    
    if (recentTasks.length === 0) {
        container.innerHTML = '<div style=padding: 20px; text-align: center; color: #6c757d;>No tasks</div>';
        return;
    }
    
    const html = recentTasks.map(task => `
        <div class=task-item onclick=viewTaskDetail(${task.id})>
            <div class=task-info>
                <div class=task-name>${escapeHtml(task.name)}</div>
                <div class=task-command>${escapeHtml(task.command.substring(0, 60))}${task.command.length > 60 ? '...' : ''}</div>
                <div class=task-meta>
                    <span>Created time: ${formatRelativeTime(task.created_at)}</span>
                    ${task.target_machine ? `<span> • Target Machine: ${task.target_machine}</span>` : ''}
                </div>
            </div>
            <div class=task-status>
                ${getStatusBadge(task.status)}
            </div>
        </div>
    `).join('');
    
    container.innerHTML = html;
}

// showMachine Status
function displayMachineStatus() {
    const container = document.getElementById('machineStatus');
    if (!container) return;
    
    if (dashboardData.machines.length === 0) {
        container.innerHTML = '<div style=padding: 20px; text-align: center; color: #6c757d;>No machines</div>';
        return;
    }
    
    const html = dashboardData.machines.map(machine => `
        <div class=machine-card onclick=viewMachineDetail('${machine.name}')>
            <div class=machine-header>
                <div class=machine-name>${escapeHtml(machine.name)}</div>
                ${getMachineStatusBadge(machine.status)}
            </div>
            <div class=machine-info>
                <div><i class=fas fa-network-wired></i> IP: ${machine.ip_address}:${machine.port}</div>
                <div><i class=fas fa-heartbeat></i> last heartbeat: ${formatRelativeTime(machine.last_heartbeat)}</div>
                ${machine.current_task_id ? `<div><i class=fas fa-tasks></i> currentTask: #${machine.current_task_id}</div>` : ''}
            </div>
        </div>
    `).join('');
    
    container.innerHTML = html;
}

// Add log entry
function addLogEntry(message, level = 'info') {
    const container = document.getElementById('systemLogs');
    if (!container) return;
    
    const timestamp = new Date().toLocaleTimeString('zh-CN');
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    logEntry.innerHTML = `
        <span class=log-timestamp>[${timestamp}]</span>
        <span class=log-level log-level-${level}>[${level.toUpperCase()}]</span>
        ${escapeHtml(message)}
    `;
    
    container.appendChild(logEntry);
    container.scrollTop = container.scrollHeight;
    
    // keep maximum 100 logs
    const entries = container.querySelectorAll('.log-entry');
    if (entries.length > 100) {
        entries[0].remove();
    }
}

// Clear logs
function clearLogs() {
    const container = document.getElementById('systemLogs');
    if (container) {
        container.innerHTML = '';
        addLogEntry('Logs cleared', 'info');
    }
}

// viewTaskdetails
function viewTaskDetail(taskId) {
    window.location.href = `/tasks?view=${taskId}`;
}

// viewMachinedetails
function viewMachineDetail(machineName) {
    window.location.href = `/machines?view=${encodeURIComponent(machineName)}`;
}

// Auto refresh data
function startAutoRefresh() {
    setInterval(async () => {
        await loadDashboardData();
        updateStatistics();
        displayRecentTasks();
        displayMachineStatus();
    }, 30000); // refresh every 30 seconds
}

// Update element content
function updateElement(id, content) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = content;
    }
}

// HTMLescape
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// WebSocket event handling
if (typeof socket !== 'undefined') {
    socket.on('task_created', function(data) {
        addLogEntry(`NewTask Created: ${data.name}`, 'success');
        loadDashboardData().then(() => {
            updateStatistics();
            displayRecentTasks();
        });
    });
    
    socket.on('task_started', function(data) {
        addLogEntry(`Taskstart execute: ID ${data.task_id} [TRANSLATED]Machine ${data.machine_name}`, 'info');
        loadDashboardData().then(() => {
            updateStatistics();
            displayRecentTasks();
        });
    });
    
    socket.on('task_completed', function(data) {
        const status = data.success ? 'Success' : 'Failed';
        addLogEntry(`Taskexecute${status}: ID ${data.task_id}`, data.success ? 'success' : 'error');
        loadDashboardData().then(() => {
            updateStatistics();
            displayRecentTasks();
        });
    });
    
    socket.on('machine_registered', function(data) {
        addLogEntry(`NewMachine Registered: ${data.name} (${data.ip_address})`, 'success');
        loadDashboardData().then(() => {
            updateStatistics();
            displayMachineStatus();
        });
    });
    
    socket.on('machine_heartbeat', function(data) {
        // [TRANSLATED] [TRANSLATED]Update Machine Status[TRANSLATED]day[TRANSLATED]show
        loadDashboardData().then(() => {
            displayMachineStatus();
        });
    });
    
    socket.on('machine_offline', function(data) {
        addLogEntry(`MachineOffline: ${data.machine_name}`, 'warning');
        loadDashboardData().then(() => {
            updateStatistics();
            displayMachineStatus();
        });
    });
}
