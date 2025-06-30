/**
 * Monitor DashboardPageJavaScript
 */

let monitorData = {
    tasks: [],
    machines: [],
    metrics: {}
};

let charts = {};

// Initialize after page load
document.addEventListener('DOMContentLoaded', function() {
    initializeMonitorPage();
    startDataRefresh();
});

// Initialize monitoring page
async function initializeMonitorPage() {
    await loadMonitorData();
    initializeCharts();
    updateRealtimeData();
    updateMetrics();
}

// loadmonitoring data
async function loadMonitorData() {
    try {
        const [tasksResponse, machinesResponse] = await Promise.all([
            apiGet('/api/tasks'),
            apiGet('/api/machines')
        ]);
        
        monitorData.tasks = tasksResponse.data || [];
        monitorData.machines = machinesResponse.data || [];
        
        // [TRANSLATED] [TRANSLATED]
        calculateMetrics();
        
    } catch (error) {
        console.error('loadmonitoring dataFailed:', error);
        showNotification('dataloadFailed', error.message, 'error');
    }
}

// [TRANSLATED] [TRANSLATED]
function calculateMetrics() {
    const tasks = monitorData.tasks;
    const machines = monitorData.machines;
    
    const totalTasks = tasks.length;
    const completedTasks = tasks.filter(t => t.status === 'completed').length;
    const failedTasks = tasks.filter(t => t.status === 'failed').length;
    const runningTasks = tasks.filter(t => t.status === 'running').length;
    const onlineMachines = machines.filter(m => m.status === 'online').length;
    
    // [TRANSLATED]Success [TRANSLATED]
    const executedTasks = completedTasks + failedTasks;
    const successRate = executedTasks > 0 ? ((completedTasks / executedTasks) * 100).toFixed(1) : 0;
    
    // [TRANSLATED] [TRANSLATED]Execution Time
    const completedTasksWithTime = tasks.filter(t => 
        t.status === 'completed' && t.started_at && t.completed_at
    );
    
    let avgExecutionTime = 0;
    if (completedTasksWithTime.length > 0) {
        const totalTime = completedTasksWithTime.reduce((sum, task) => {
            const start = new Date(task.started_at);
            const end = new Date(task.completed_at);
            return sum + (end - start);
        }, 0);
        avgExecutionTime = totalTime / completedTasksWithTime.length / 1000; // [TRANSLATED] [TRANSLATED]seconds
    }
    
    // system[TRANSLATED] [TRANSLATED]
    const loadLevel = runningTasks < 3 ? '[TRANSLATED]' : runningTasks < 8 ? '[TRANSLATED]' : '[TRANSLATED]';
    
    monitorData.metrics = {
        successRate: `${successRate}%`,
        avgExecutionTime: formatDuration(avgExecutionTime),
        systemLoad: loadLevel,
        onlineMachinesCount: `${onlineMachines}/${machines.length}`
    };
}

// Format duration
function formatDuration(seconds) {
    if (seconds < 60) {
        return `${Math.round(seconds)}seconds`;
    } else if (seconds < 3600) {
        return `${Math.round(seconds / 60)}minutes`;
    } else {
        return `${Math.round(seconds / 3600)}hours`;
    }
}

// initialize charttable
function initializeCharts() {
    initTaskStatusChart();
    initMachineStatusChart();
    initTaskTrendChart();
}

// InitializeTaskStatus [TRANSLATED]table
function initTaskStatusChart() {
    const ctx = document.getElementById('taskStatusChart').getContext('2d');
    const tasks = monitorData.tasks;
    
    const statusCounts = {
        pending: tasks.filter(t => t.status === 'pending').length,
        running: tasks.filter(t => t.status === 'running').length,
        completed: tasks.filter(t => t.status === 'completed').length,
        failed: tasks.filter(t => t.status === 'failed').length,
        cancelled: tasks.filter(t => t.status === 'cancelled').length
    };
    
    charts.taskStatus = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['[TRANSLATED]execute', 'Running', 'Completed', 'Failed', 'Canceled'],
            datasets: [{
                data: [
                    statusCounts.pending,
                    statusCounts.running,
                    statusCounts.completed,
                    statusCounts.failed,
                    statusCounts.cancelled
                ],
                backgroundColor: [
                    '#ffc107',
                    '#17a2b8',
                    '#28a745',
                    '#dc3545',
                    '#6c757d'
                ],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// [TRANSLATED] [TRANSLATED]Machine Status[TRANSLATED]table
function initMachineStatusChart() {
    const ctx = document.getElementById('machineStatusChart').getContext('2d');
    const machines = monitorData.machines;
    
    const statusCounts = {
        online: machines.filter(m => m.status === 'online').length,
        offline: machines.filter(m => m.status === 'offline').length,
        busy: machines.filter(m => m.status === 'busy').length
    };
    
    charts.machineStatus = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['Online', 'Offline', 'Busy'],
            datasets: [{
                data: [statusCounts.online, statusCounts.offline, statusCounts.busy],
                backgroundColor: ['#28a745', '#dc3545', '#ffc107'],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// InitializeTask[TRANSLATED] [TRANSLATED]table
function initTaskTrendChart() {
    const ctx = document.getElementById('taskTrendChart').getContext('2d');
    const tasks = monitorData.tasks;
    
    // pressdateminute[TRANSLATED] [TRANSLATED]
    const dateGroups = {};
    const now = new Date();
    
    // [TRANSLATED]7daysof[TRANSLATED] [TRANSLATED]
    for (let i = 6; i >= 0; i--) {
        const date = new Date(now);
        date.setDate(date.getDate() - i);
        const dateKey = date.toISOString().split('T')[0];
        dateGroups[dateKey] = { completed: 0, failed: 0, total: 0 };
    }
    
    // [TRANSLATED] [TRANSLATED]Task
    tasks.forEach(task => {
        if (task.completed_at) {
            const completedDate = new Date(task.completed_at).toISOString().split('T')[0];
            if (dateGroups[completedDate]) {
                dateGroups[completedDate].total++;
                if (task.status === 'completed') {
                    dateGroups[completedDate].completed++;
                } else if (task.status === 'failed') {
                    dateGroups[completedDate].failed++;
                }
            }
        }
    });
    
    const labels = Object.keys(dateGroups).map(date => {
        const d = new Date(date);
        return `${d.getMonth() + 1}/${d.getDate()}`;
    });
    
    const completedData = Object.values(dateGroups).map(group => group.completed);
    const failedData = Object.values(dateGroups).map(group => group.failed);
    
    charts.taskTrend = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Success',
                data: completedData,
                borderColor: '#28a745',
                backgroundColor: 'rgba(40, 167, 69, 0.1)',
                tension: 0.4,
                fill: true
            }, {
                label: 'Failed',
                data: failedData,
                borderColor: '#dc3545',
                backgroundColor: 'rgba(220, 53, 69, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

// Update [TRANSLATED]hourdata
function updateRealtimeData() {
    updateRunningTasks();
    updateMachineLoad();
}

// Update executeofTasking
function updateRunningTasks() {
    const container = document.getElementById('runningTasksList');
    const runningTasks = monitorData.tasks.filter(task => task.status === 'running');
    
    if (runningTasks.length === 0) {
        container.innerHTML = '<p style=color: #6c757d; text-align: center; padding: 20px;>NoexecuteofTasking</p>';
        return;
    }
    
    const html = runningTasks.map(task => `
        <div class=running-task-item>
            <div class=task-info>
                <div class=task-name>${escapeHtml(task.name)}</div>
                <div class=task-machine>${task.target_machine || '[TRANSLATED]Machine'}</div>
            </div>
            <div class=task-duration>
                ${task.started_at ? formatDuration((new Date() - new Date(task.started_at)) / 1000) : '-'}
            </div>
        </div>
    `).join('');
    
    container.innerHTML = html;
}

// Update Machine[TRANSLATED]
function updateMachineLoad() {
    const container = document.getElementById('machineLoadList');
    const machines = monitorData.machines;
    
    if (machines.length === 0) {
        container.innerHTML = '<p style=color: #6c757d; text-align: center; padding: 20px;>NoMachine</p>';
        return;
    }
    
    const html = machines.map(machine => {
        const load = getLoadPercentage(machine);
        const loadClass = load > 80 ? 'high' : load > 50 ? 'medium' : 'low';
        
        return `
            <div class=machine-load-item>
                <div class=machine-info>
                    <div class=machine-name>${escapeHtml(machine.name)}</div>
                    <div class=machine-status>${getMachineStatusBadge(machine.status)}</div>
                </div>
                <div class=load-bar>
                    <div class=load-progress load-${loadClass} style=width: ${load}%></div>
                    <span class=load-text>${load}%</span>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = html;
}

// Get Machineload percentage（[TRANSLATED]）
function getLoadPercentage(machine) {
    if (machine.status === 'offline') return 0;
    if (machine.status === 'busy') return 75 + Math.random() * 25; // 75-100%
    return Math.random() * 30; // 0-30%
}

// Update [TRANSLATED]
function updateMetrics() {
    const metrics = monitorData.metrics;
    
    updateElement('successRate', metrics.successRate);
    updateElement('avgExecutionTime', metrics.avgExecutionTime);
    updateElement('systemLoad', metrics.systemLoad);
    updateElement('onlineMachinesCount', metrics.onlineMachinesCount);
}

// Refreshmonitoring data
async function refreshMonitorData() {
    await loadMonitorData();
    
    // Update [TRANSLATED]table
    updateChartData();
    
    // Update [TRANSLATED]hourdata
    updateRealtimeData();
    
    // Update [TRANSLATED]
    updateMetrics();
}

// Update [TRANSLATED]tabledata
function updateChartData() {
    // Update taskStatus[TRANSLATED]table
    if (charts.taskStatus) {
        const tasks = monitorData.tasks;
        const statusCounts = [
            tasks.filter(t => t.status === 'pending').length,
            tasks.filter(t => t.status === 'running').length,
            tasks.filter(t => t.status === 'completed').length,
            tasks.filter(t => t.status === 'failed').length,
            tasks.filter(t => t.status === 'cancelled').length
        ];
        
        charts.taskStatus.data.datasets[0].data = statusCounts;
        charts.taskStatus.update();
    }
    
    // Update Machine Status[TRANSLATED]table
    if (charts.machineStatus) {
        const machines = monitorData.machines;
        const statusCounts = [
            machines.filter(m => m.status === 'online').length,
            machines.filter(m => m.status === 'offline').length,
            machines.filter(m => m.status === 'busy').length
        ];
        
        charts.machineStatus.data.datasets[0].data = statusCounts;
        charts.machineStatus.update();
    }
}

// start dataautoRefresh
function startDataRefresh() {
    // every30secondsRefresh[TRANSLATED] [TRANSLATED]
    setInterval(refreshMonitorData, 30000);
    
    // every5secondsUpdate [TRANSLATED]hourdata
    setInterval(updateRealtimeData, 5000);
}

// Update element content
function updateElement(id, content) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = content;
    }
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
    .running-task-item,
    .machine-load-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 15px;
        border-bottom: 1px solid #f0f0f0;
        transition: background-color 0.3s ease;
    }
    
    .running-task-item:hover,
    .machine-load-item:hover {
        background-color: #f8f9fa;
    }
    
    .running-task-item:last-child,
    .machine-load-item:last-child {
        border-bottom: none;
    }
    
    .task-info .task-name,
    .machine-info .machine-name {
        font-weight: 600;
        color: #2c3e50;
        margin-bottom: 2px;
    }
    
    .task-info .task-machine {
        font-size: 0.8rem;
        color: #6c757d;
    }
    
    .task-duration {
        font-size: 0.9rem;
        color: #6c757d;
        font-weight: 500;
    }
    
    .machine-info {
        flex: 1;
    }
    
    .machine-info .machine-status .machine-status {
        font-size: 0.7rem;
        padding: 2px 8px;
    }
    
    .load-bar {
        position: relative;
        width: 100px;
        height: 8px;
        background-color: #e9ecef;
        border-radius: 4px;
        overflow: hidden;
    }
    
    .load-progress {
        height: 100%;
        border-radius: 4px;
        transition: width 0.3s ease;
    }
    
    .load-low {
        background-color: #28a745;
    }
    
    .load-medium {
        background-color: #ffc107;
    }
    
    .load-high {
        background-color: #dc3545;
    }
    
    .load-text {
        position: absolute;
        top: 50%;
        right: 5px;
        transform: translateY(-50%);
        font-size: 0.7rem;
        color: #2c3e50;
        font-weight: 600;
    }
    
    .chart-container canvas {
        max-height: 300px;
    }
    
    .chart-large canvas {
        max-height: 200px;
    }
`;
document.head.appendChild(style);
