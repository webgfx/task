/**
 * Dashboard page JavaScript
 */

let dashboardData = {
    tasks: [],
    clients: []
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
    displayClientStatus();
    addLogEntry('systemstarted', 'info');
}

// Load dashboard data
async function loadDashboardData() {
    try {
        const [tasksResponse, clientsResponse] = await Promise.all([
            apiGet('/api/tasks'),
            apiGet('/api/clients')
        ]);
        
        dashboardData.tasks = tasksResponse.data || [];
        dashboardData.clients = clientsResponse.data || [];
        
    } catch (error) {
        console.error('Failed to load dashboard data:', error);
        addLogEntry(`Data loading failed: ${error.message}`, 'error');
    }
}

// Update statistics
function updateStatistics() {
    const tasks = dashboardData.tasks;
    const clients = dashboardData.clients;
    
    // Calculate statistics
    const totalTasks = tasks.length;
    const runningTasks = tasks.filter(task => task.status === 'running').length;
    const completedTasks = tasks.filter(task => task.status === 'completed').length;
    const onlineClients = clients.filter(client => client.status === 'online').length;
    
    // Update page display
    updateElement('totalTasks', totalTasks);
    updateElement('runningTasks', runningTasks);
    updateElement('completedTasks', completedTasks);
    updateElement('onlineClients', onlineClients);
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
                <div class=task-subtask>${escapeHtml(task.command.substring(0, 60))}${task.command.length > 60 ? '...' : ''}</div>
                <div class=task-meta>
                    <span>Created time: ${formatRelativeTime(task.created_at)}</span>
                    ${task.client ? `<span> • Target Client: ${task.client}</span>` : ''}
                </div>
            </div>
            <div class=task-status>
                ${getStatusBadge(task.status)}
            </div>
        </div>
    `).join('');
    
    container.innerHTML = html;
}

// showClient Status
function displayClientStatus() {
    const container = document.getElementById('clientStatus');
    if (!container) return;
    
    if (dashboardData.clients.length === 0) {
        container.innerHTML = '<div style=padding: 20px; text-align: center; color: #6c757d;>No clients</div>';
        return;
    }
    
    const html = dashboardData.clients.map(client => `
        <div class=client-card onclick=viewClientDetail('${client.name}')>
            <div class=client-header>
                <div class=client-name>${escapeHtml(client.name)}</div>
                ${getClientStatusBadge(client.status)}
            </div>
            <div class=client-info>
                <div><i class=fas fa-network-wired></i> IP: ${client.ip_address}:${client.port}</div>
                <div><i class=fas fa-heartbeat></i> last heartbeat: ${formatRelativeTime(client.last_heartbeat)}</div>
                ${client.current_task_id ? `<div><i class=fas fa-tasks></i> currentTask: #${client.current_task_id}</div>` : ''}
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

// viewClientdetails
function viewClientDetail(clientName) {
    window.location.href = `/clients?view=${encodeURIComponent(clientName)}`;
}

// Auto refresh data
function startAutoRefresh() {
    setInterval(async () => {
        await loadDashboardData();
        updateStatistics();
        displayRecentTasks();
        displayClientStatus();
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
        addLogEntry(`Taskstart execute: ID ${data.task_id} [TRANSLATED]Client ${data.client_name}`, 'info');
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
    
    socket.on('client_registered', function(data) {
        addLogEntry(`NewClient Registered: ${data.name} (${data.ip_address})`, 'success');
        loadDashboardData().then(() => {
            updateStatistics();
            displayClientStatus();
        });
    });
    
    socket.on('client_heartbeat', function(data) {
        // [TRANSLATED] [TRANSLATED]Update Client Status[TRANSLATED]day[TRANSLATED]show
        loadDashboardData().then(() => {
            displayClientStatus();
        });
    });
    
    socket.on('client_offline', function(data) {
        addLogEntry(`ClientOffline: ${data.client_name}`, 'warning');
        loadDashboardData().then(() => {
            updateStatistics();
            displayClientStatus();
        });
    });
}
