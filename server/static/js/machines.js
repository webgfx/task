/**
 * Machine Management page JavaScript
 */

let machines = [];

// Initialize after page load
document.addEventListener('DOMContentLoaded', function() {
    initializeMachinesPage();
});

// Initialize machine page
async function initializeMachinesPage() {
    await refreshMachines();
    setupEventListeners();
}

// Setup event listeners
function setupEventListeners() {
    // Close modal when clicking outside
    window.addEventListener('click', function(e) {
        const detailModal = document.getElementById('machineDetailModal');
        if (e.target === detailModal) {
            closeMachineDetailModal();
        }
    });
}

// Refresh machine list
async function refreshMachines() {
    try {
        showLoading(document.getElementById('machineGrid'));
        const response = await apiGet('/api/machines');
        machines = response.data || [];
        displayMachines();
        
        // Update connection counts
        updateConnectionStats();
    } catch (error) {
        console.error('Refresh machine list failed:', error);
        showNotification('Refresh Failed', error.message, 'error');
    } finally {
        hideLoading(document.getElementById('machineGrid'));
    }
}

// Update connection statistics
function updateConnectionStats() {
    const stats = {
        total: machines.length,
        online: machines.filter(m => m.status === 'online').length,
        offline: machines.filter(m => m.status === 'offline').length,
        busy: machines.filter(m => m.status === 'busy').length
    };
    
    // Update header if stats element exists
    const headerActions = document.querySelector('.header-actions');
    if (headerActions) {
        const existingStats = headerActions.querySelector('.connection-stats');
        if (existingStats) {
            existingStats.remove();
        }
        
        const statsElement = document.createElement('div');
        statsElement.className = 'connection-stats';
        statsElement.innerHTML = `
            <span class="stat-badge">Total: ${stats.total}</span>
            <span class="stat-badge stat-online">Online: ${stats.online}</span>
            <span class="stat-badge stat-offline">Offline: ${stats.offline}</span>
            ${stats.busy > 0 ? `<span class="stat-badge stat-busy">Busy: ${stats.busy}</span>` : ''}
        `;
        
        headerActions.insertBefore(statsElement, headerActions.firstChild);
    }
}

// Filter machines based on search and status
function filterMachines() {
    const statusFilter = document.getElementById('statusFilter').value;
    const searchInput = document.getElementById('searchInput').value.toLowerCase();
    
    let filteredMachines = machines;
    
    // Apply status filter
    if (statusFilter) {
        filteredMachines = filteredMachines.filter(machine => machine.status === statusFilter);
    }
    
    // Apply search filter
    if (searchInput) {
        filteredMachines = filteredMachines.filter(machine => 
            machine.name.toLowerCase().includes(searchInput) ||
            machine.ip_address.toLowerCase().includes(searchInput) ||
            (machine.system_summary && (
                machine.system_summary.os?.toLowerCase().includes(searchInput) ||
                machine.system_summary.cpu?.toLowerCase().includes(searchInput) ||
                machine.system_summary.hostname?.toLowerCase().includes(searchInput)
            )) ||
            (machine.capabilities && machine.capabilities.some(cap => 
                cap.toLowerCase().includes(searchInput)
            ))
        );
    }
    
    // Display filtered results
    const container = document.getElementById('machineGrid');
    if (filteredMachines.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-search" style="font-size: 3rem; color: #6c757d; margin-bottom: 1rem;"></i>
                <h3>No Matching Clients</h3>
                <p>No clients match your search criteria</p>
                <button class="btn btn-primary" onclick="clearFilters()">Clear Filters</button>
            </div>
        `;
    } else {
        const html = filteredMachines.map(machine => createMachineCard(machine)).join('');
        container.innerHTML = html;
    }
}

// Clear all filters
function clearFilters() {
    document.getElementById('statusFilter').value = '';
    document.getElementById('searchInput').value = '';
    displayMachines();
}

// Display machine list
function displayMachines() {
    const container = document.getElementById('machineGrid');
    
    if (machines.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-server" style="font-size: 3rem; color: #6c757d; margin-bottom: 1rem;"></i>
                <h3>No Registered Clients</h3>
                <p>Please start client processes to register machines</p>
                <div class="empty-actions">
                    <code>python client/client.py --machine-name your-machine-name</code>
                </div>
            </div>
        `;
        return;
    }
    
    const html = machines.map(machine => createMachineCard(machine)).join('');
    container.innerHTML = html;
}

// Create Machine Card with enhanced system information display
function createMachineCard(machine) {
    const statusIcon = getStatusIcon(machine.status);
    const lastHeartbeat = machine.last_heartbeat ? formatRelativeTime(machine.last_heartbeat) : 'Never';
    const capabilities = machine.capabilities || [];
    const systemSummary = machine.system_summary || {};
    
    // Format detailed system information
    const systemInfo = [];
    
    // OS Information (basic only)
    if (machine.os_info) {
        const os = machine.os_info;
        let osDisplay = os.system || 'Unknown OS';
        if (os.release) osDisplay += ` ${os.release}`;
        systemInfo.push(`<i class="fas fa-desktop"></i><span>OS: ${osDisplay}</span>`);
    } else if (systemSummary.os) {
        systemInfo.push(`<i class="fas fa-desktop"></i><span>OS: ${systemSummary.os}</span>`);
    }
    
    // CPU Information
    if (machine.cpu_info) {
        const cpu = machine.cpu_info;
        let cpuDisplay = cpu.processor || 'Unknown CPU';
        if (cpu.cpu_count_logical) {
            cpuDisplay += ` (${cpu.cpu_count_logical} cores)`;
        }
        if (cpu.cpu_freq_max) {
            cpuDisplay += ` @ ${(cpu.cpu_freq_max / 1000).toFixed(1)}GHz`;
        }
        systemInfo.push(`<i class="fas fa-microchip"></i><span>CPU: ${cpuDisplay}</span>`);
    } else if (systemSummary.cpu) {
        systemInfo.push(`<i class="fas fa-microchip"></i><span>CPU: ${systemSummary.cpu}</span>`);
    }
    
    // Memory Information (only show total)
    if (machine.memory_info) {
        const mem = machine.memory_info;
        if (mem.total) {
            systemInfo.push(`<i class="fas fa-memory"></i><span>Memory: ${formatBytes(mem.total)}</span>`);
        }
    } else if (systemSummary.memory) {
        systemInfo.push(`<i class="fas fa-memory"></i><span>Memory: ${systemSummary.memory}</span>`);
    }
    
    // GPU Information
    if (machine.gpu_info && machine.gpu_info.length > 0) {
        const gpus = machine.gpu_info;
        if (gpus.length === 1) {
            const gpu = gpus[0];
            let gpuDisplay = gpu.name || 'Unknown GPU';
            if (gpu.memory_total) {
                gpuDisplay += ` (${formatBytes(gpu.memory_total)})`;
            }
            systemInfo.push(`<i class="fas fa-tv"></i><span>GPU: ${gpuDisplay}</span>`);
        } else {
            systemInfo.push(`<i class="fas fa-tv"></i><span>GPU: ${gpus.length} GPUs detected</span>`);
        }
    } else if (systemSummary.gpu) {
        systemInfo.push(`<i class="fas fa-tv"></i><span>GPU: ${systemSummary.gpu}</span>`);
    }
    
    return `
        <div class="machine-card" onclick="viewMachineDetail('${machine.name}')">
            <div class="machine-header">
                <div class="machine-title">
                    <div class="machine-name">
                        ${statusIcon}
                        ${escapeHtml(machine.name)}
                    </div>
                    ${getMachineStatusBadge(machine.status)}
                </div>
            </div>
            
            <div class="machine-body">
                <div class="machine-info">
                    <div class="info-item">
                        <i class="fas fa-network-wired"></i>
                        <span>IP Address: ${machine.ip_address}:${machine.port}</span>
                    </div>
                    <div class="info-item">
                        <i class="fas fa-heartbeat"></i>
                        <span>Last Heartbeat: ${lastHeartbeat}</span>
                    </div>
                    ${machine.current_task_id ? `
                    <div class="info-item">
                        <i class="fas fa-tasks"></i>
                        <span>Current Task: #${machine.current_task_id}</span>
                    </div>
                    ` : ''}
                    ${systemInfo.length > 0 ? systemInfo.map(info => `
                    <div class="info-item system-info">
                        ${info}
                    </div>
                    `).join('') : ''}
                    ${capabilities.length > 0 ? `
                    <div class="info-item">
                        <i class="fas fa-cogs"></i>
                        <span>Capabilities: ${capabilities.join(', ')}</span>
                    </div>
                    ` : ''}
                </div>
                
                <div class="machine-actions">
                    <button class="btn btn-sm btn-outline" onclick="event.stopPropagation(); pingMachine('${machine.name}')" title="Ping Test">
                        <i class="fas fa-satellite-dish"></i>
                    </button>
                    <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); viewMachineTasks('${machine.name}')" title="View Tasks">
                        <i class="fas fa-list"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Get status icon
function getStatusIcon(status) {
    const iconMap = {
        'online': '<i class="fas fa-circle text-success"></i>',
        'offline': '<i class="fas fa-circle text-danger"></i>',
        'busy': '<i class="fas fa-circle text-warning"></i>'
    };
    
    return iconMap[status] || '<i class="fas fa-circle text-secondary"></i>';
}

// View machine details
async function viewMachineDetail(machineName) {
    try {
        const machine = machines.find(m => m.name === machineName);
        if (!machine) {
            showNotification('Error', 'Machine not found', 'error');
            return;
        }
        
        // Get machine tasks
        const tasksResponse = await apiGet('/api/tasks');
        const allTasks = tasksResponse.data || [];
        const machineTasks = allTasks.filter(task => 
            task.target_machine === machineName || 
            (!task.target_machine && task.status !== 'pending')
        );
        
        showMachineDetailModal(machine, machineTasks);
        
    } catch (error) {
        console.error('Get machine details failed:', error);
        showNotification('Get details failed', error.message, 'error');
    }
}

// Show machine details modal
function showMachineDetailModal(machine, tasks) {
    const modal = document.getElementById('machineDetailModal');
    const content = document.getElementById('machineDetailContent');
    
    const capabilities = machine.capabilities || [];
    const onlineTasks = tasks.filter(task => task.status === 'running');
    const completedTasks = tasks.filter(task => task.status === 'completed');
    const failedTasks = tasks.filter(task => task.status === 'failed');
    const systemSummary = machine.system_summary || {};
    
    // Format detailed system information
    function formatSystemDetails() {
        if (!machine.cpu_info && !machine.memory_info && !machine.gpu_info && !machine.os_info) {
            return '<p style="color: #6c757d;">No detailed system information available</p>';
        }
        
        let details = '';
        
        // CPU Information
        if (machine.cpu_info) {
            const cpu = machine.cpu_info;
            details += `
                <div class="detail-subsection">
                    <h5><i class="fas fa-microchip"></i> CPU Information</h5>
                    <div class="detail-grid">
                        ${cpu.processor ? `<div class="detail-item"><label>Processor:</label><span>${cpu.processor}</span></div>` : ''}
                        ${cpu.architecture ? `<div class="detail-item"><label>Architecture:</label><span>${cpu.architecture}</span></div>` : ''}
                        ${cpu.cpu_count_logical ? `<div class="detail-item"><label>Logical Cores:</label><span>${cpu.cpu_count_logical}</span></div>` : ''}
                        ${cpu.cpu_count_physical ? `<div class="detail-item"><label>Physical Cores:</label><span>${cpu.cpu_count_physical}</span></div>` : ''}
                        ${cpu.cpu_freq_max ? `<div class="detail-item"><label>Max Frequency:</label><span>${(cpu.cpu_freq_max / 1000).toFixed(2)} GHz</span></div>` : ''}
                    </div>
                </div>
            `;
        }
        
        // Memory Information (only total)
        if (machine.memory_info) {
            const mem = machine.memory_info;
            details += `
                <div class="detail-subsection">
                    <h5><i class="fas fa-memory"></i> Memory Information</h5>
                    <div class="detail-grid">
                        ${mem.total ? `<div class="detail-item"><label>Total Memory:</label><span>${formatBytes(mem.total)}</span></div>` : ''}
                    </div>
                </div>
            `;
        }
        
        // GPU Information
        if (machine.gpu_info && machine.gpu_info.length > 0) {
            details += `
                <div class="detail-subsection">
                    <h5><i class="fas fa-tv"></i> GPU Information</h5>
            `;
            machine.gpu_info.forEach((gpu, index) => {
                details += `
                    <div class="detail-grid">
                        <div class="detail-item"><label>GPU ${index + 1}:</label><span>${gpu.name || 'Unknown'}</span></div>
                        ${gpu.vendor ? `<div class="detail-item"><label>Vendor:</label><span>${gpu.vendor}</span></div>` : ''}
                        ${gpu.memory_total ? `<div class="detail-item"><label>Memory:</label><span>${formatBytes(gpu.memory_total)}</span></div>` : ''}
                        ${gpu.driver_version ? `<div class="detail-item"><label>Driver:</label><span>${gpu.driver_version}</span></div>` : ''}
                    </div>
                `;
            });
            details += '</div>';
        }
        
        // Operating System (basic only)
        if (machine.os_info) {
            const os = machine.os_info;
            details += `
                <div class="detail-subsection">
                    <h5><i class="fas fa-desktop"></i> Operating System</h5>
                    <div class="detail-grid">
                        ${os.system ? `<div class="detail-item"><label>System:</label><span>${os.system}</span></div>` : ''}
                        ${os.release ? `<div class="detail-item"><label>Release:</label><span>${os.release}</span></div>` : ''}
                    </div>
                </div>
            `;
        }
        
        return details;
    }
    
    const html = `
        <div class="machine-detail">
            <div class="detail-section">
                <h4>Machine Information</h4>
                <div class="detail-grid">
                    <div class="detail-item">
                        <label>Machine Name:</label>
                        <span>${escapeHtml(machine.name)}</span>
                    </div>
                    <div class="detail-item">
                        <label>Status:</label>
                        <span>${getMachineStatusBadge(machine.status)}</span>
                    </div>
                    <div class="detail-item">
                        <label>IP Address:</label>
                        <span>${machine.ip_address}</span>
                    </div>
                    <div class="detail-item">
                        <label>Port:</label>
                        <span>${machine.port}</span>
                    </div>
                    ${systemSummary.hostname ? `
                    <div class="detail-item">
                        <label>Hostname:</label>
                        <span>${systemSummary.hostname}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
            
            <div class="detail-section">
                <h4>Connection Information</h4>
                <div class="detail-grid">
                    <div class="detail-item">
                        <label>Last Heartbeat:</label>
                        <span>${formatDateTime(machine.last_heartbeat) || 'Never'}</span>
                    </div>
                    <div class="detail-item">
                        <label>Heartbeat Status:</label>
                        <span>${getHeartbeatStatus(machine.last_heartbeat)}</span>
                    </div>
                    <div class="detail-item">
                        <label>Last Config Update:</label>
                        <span>${formatDateTime(machine.last_config_update) || 'Never'}</span>
                    </div>
                    <div class="detail-item">
                        <label>Current Task:</label>
                        <span>${machine.current_task_id ? `#${machine.current_task_id}` : 'None'}</span>
                    </div>
                </div>
            </div>
            
            <div class="detail-section">
                <h4>System Information</h4>
                ${formatSystemDetails()}
            </div>
            
            ${capabilities.length > 0 ? `
            <div class="detail-section">
                <h4>Capability Tags</h4>
                <div class="capabilities-list">
                    ${capabilities.map(cap => `<span class="capability-tag">${escapeHtml(cap)}</span>`).join('')}
                </div>
            </div>
            ` : ''}
            
            <div class="detail-section">
                <h4>Task Statistics</h4>
                <div class="task-stats">
                    <div class="stat-item">
                        <span class="stat-number">${tasks.length}</span>
                        <span class="stat-label">Total Tasks</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-number">${onlineTasks.length}</span>
                        <span class="stat-label">Running</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-number">${completedTasks.length}</span>
                        <span class="stat-label">Completed</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-number">${failedTasks.length}</span>
                        <span class="stat-label">Failed</span>
                    </div>
                </div>
            </div>
            
            <div class="detail-section">
                <h4>Recent Tasks</h4>
                ${tasks.length > 0 ? `
                    <div class="task-list-small">
                        ${tasks.slice(0, 5).map(task => `
                            <div class="task-item-small">
                                <div class="task-info-small">
                                    <div class="task-name-small">${escapeHtml(task.name)}</div>
                                    <div class="task-time-small">${formatRelativeTime(task.created_at)}</div>
                                </div>
                                <div class="task-status-small">${getStatusBadge(task.status)}</div>
                            </div>
                        `).join('')}
                    </div>
                    ${tasks.length > 5 ? `
                        <div class="view-all-link">
                            <a href="/tasks?machine=${encodeURIComponent(machine.name)}">View All Tasks (${tasks.length})</a>
                        </div>
                    ` : ''}
                ` : '<p style="color: #6c757d;">No tasks assigned to this machine</p>'}
            </div>
        </div>
    `;
    
    content.innerHTML = html;
    modal.style.display = 'block';
}

// Close machine details modal
function closeMachineDetailModal() {
    const modal = document.getElementById('machineDetailModal');
    modal.style.display = 'none';
}

// Get heartbeat status
function getHeartbeatStatus(lastHeartbeat) {
    if (!lastHeartbeat) {
        return '<span class="text-danger">No connection</span>';
    }
    
    const now = new Date();
    const heartbeatTime = new Date(lastHeartbeat);
    const diffMinutes = (now - heartbeatTime) / (1000 * 60);
    
    if (diffMinutes < 2) {
        return '<span class="text-success">Normal</span>';
    } else if (diffMinutes < 5) {
        return '<span class="text-warning">Delayed</span>';
    } else {
        return '<span class="text-danger">Timeout</span>';
    }
}

// Ping machine
async function pingMachine(machineName) {
    try {
        // Show ping test prompt
        showNotification('Ping Test', `Testing connection to machine ${machineName}...`, 'info');
        
        // Simulate ping test
        setTimeout(() => {
            const machine = machines.find(m => m.name === machineName);
            if (machine && machine.status === 'online') {
                showNotification('Ping Success', `Machine ${machineName} connection normal`, 'success');
            } else {
                showNotification('Ping Failed', `Machine ${machineName} unreachable`, 'error');
            }
        }, 2000);
        
    } catch (error) {
        console.error('Ping machine failed:', error);
        showNotification('Ping Failed', error.message, 'error');
    }
}

// View machine tasks
function viewMachineTasks(machineName) {
    window.location.href = `/tasks?machine=${encodeURIComponent(machineName)}`;
}

// Update Machine Status (for real-time updates)
function updateMachineStatus(data) {
    const machineIndex = machines.findIndex(m => m.name === data.machine_name);
    if (machineIndex !== -1) {
        machines[machineIndex].status = data.status;
        machines[machineIndex].last_heartbeat = data.timestamp;
        displayMachines();
    }
}

// HTML escape utility
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Format bytes to human readable string
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) {
        bytes /= 1024;
        i++;
    }
    
    return `${bytes.toFixed(1)} ${units[i]}`;
}

// Add CSS styles
const style = document.createElement('style');
style.textContent = `
    .empty-state {
        grid-column: 1 / -1;
        text-align: center;
        padding: 60px 20px;
        color: #6c757d;
    }
    
    .empty-state h3 {
        margin-bottom: 10px;
        color: #2c3e50;
    }
    
    .empty-actions {
        margin-top: 20px;
        padding: 15px;
        background-color: #f8f9fa;
        border-radius: 6px;
        border-left: 4px solid #667eea;
    }
    
    .empty-actions code {
        background-color: #e9ecef;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: 'Courier New', monospace;
    }
    
    .machine-title {
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
    }
    
    .machine-name {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 1.2rem;
        font-weight: 600;
    }
    
    .machine-body {
        margin-top: 15px;
    }
    
    .info-item {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 8px;
        font-size: 0.9rem;
        color: #6c757d;
    }
    
    .info-item.system-info {
        font-size: 0.85rem;
        background-color: #f8f9fa;
        padding: 6px 10px;
        border-radius: 4px;
        margin-bottom: 6px;
        border-left: 3px solid #667eea;
    }
    
    .info-item i {
        width: 16px;
        text-align: center;
        color: #999;
    }
    
    .system-info i {
        color: #667eea;
    }
    
    .machine-actions {
        display: flex;
        gap: 10px;
        margin-top: 15px;
        padding-top: 15px;
        border-top: 1px solid #e1e8ed;
    }
    
    .capabilities-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }
    
    .capability-tag {
        background-color: #e7f1ff;
        color: #0056b3;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    
    .task-stats {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 20px;
        text-align: center;
    }
    
    .stat-item {
        padding: 15px;
        background-color: #f8f9fa;
        border-radius: 8px;
    }
    
    .stat-number {
        display: block;
        font-size: 1.5rem;
        font-weight: 700;
        color: #2c3e50;
    }
    
    .stat-label {
        font-size: 0.9rem;
        color: #6c757d;
    }
    
    .task-list-small {
        max-height: 200px;
        overflow-y: auto;
    }
    
    .task-item-small {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 15px;
        border-bottom: 1px solid #f0f0f0;
        transition: background-color 0.3s ease;
    }
    
    .task-item-small:hover {
        background-color: #f8f9fa;
    }
    
    .task-item-small:last-child {
        border-bottom: none;
    }
    
    .task-info-small {
        flex: 1;
    }
    
    .task-name-small {
        font-weight: 600;
        color: #2c3e50;
        margin-bottom: 2px;
    }
    
    .task-time-small {
        font-size: 0.8rem;
        color: #6c757d;
    }
    
    .task-status-small .status-badge {
        font-size: 0.7rem;
        padding: 2px 8px;
    }
    
    .view-all-link {
        text-align: center;
        padding: 15px;
        border-top: 1px solid #e1e8ed;
    }
    
    .view-all-link a {
        color: #667eea;
        text-decoration: none;
        font-weight: 500;
    }
    
    .view-all-link a:hover {
        text-decoration: underline;
    }
    
    .detail-subsection {
        margin-bottom: 20px;
        padding: 15px;
        background-color: #f8f9fa;
        border-radius: 6px;
        border-left: 4px solid #667eea;
    }
    
    .detail-subsection h5 {
        margin: 0 0 15px 0;
        color: #2c3e50;
        font-size: 1rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .detail-subsection h5 i {
        color: #667eea;
    }
    
    .detail-subsection .detail-grid {
        background-color: white;
        padding: 15px;
        border-radius: 4px;
        border: 1px solid #e1e8ed;
    }
    
    .detail-subsection .detail-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid #f0f0f0;
    }
    
    .detail-subsection .detail-item:last-child {
        border-bottom: none;
    }
    
    .detail-subsection .detail-item label {
        font-weight: 600;
        color: #495057;
        min-width: 120px;
    }
    
    .detail-subsection .detail-item span {
        color: #6c757d;
        text-align: right;
        flex: 1;
    }
    
    /* Enhanced machine card styling */
    .machine-card {
        border: 1px solid #e1e8ed;
        border-radius: 8px;
        padding: 20px;
        background-color: white;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .machine-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        border-color: #667eea;
    }
    
    /* Grid layout for machines */
    .machine-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
        gap: 20px;
        padding: 20px 0;
    }
    
    /* Connection statistics */
    .connection-stats {
        display: flex;
        gap: 10px;
        margin-right: 15px;
        align-items: center;
    }
    
    .stat-badge {
        background-color: #e9ecef;
        color: #495057;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .stat-badge.stat-online {
        background-color: #d4edda;
        color: #155724;
    }
    
    .stat-badge.stat-offline {
        background-color: #f8d7da;
        color: #721c24;
    }
    
    .stat-badge.stat-busy {
        background-color: #fff3cd;
        color: #856404;
    }
    
    /* Filter bar styling */
    .filter-bar {
        background-color: #f8f9fa;
        padding: 15px 20px;
        border-radius: 6px;
        margin-bottom: 20px;
        display: flex;
        gap: 20px;
        align-items: center;
        flex-wrap: wrap;
    }
    
    .filter-group {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .filter-group label {
        font-weight: 600;
        color: #495057;
        min-width: 60px;
    }
    
    .filter-group select,
    .filter-group input {
        padding: 6px 12px;
        border: 1px solid #ced4da;
        border-radius: 4px;
        font-size: 0.9rem;
    }
    
    .filter-group input[type="text"] {
        min-width: 200px;
    }
    
    @media (max-width: 768px) {
        .machine-grid {
            grid-template-columns: 1fr;
        }
        
        .task-stats {
            grid-template-columns: repeat(2, 1fr);
        }
        
        .connection-stats {
            flex-wrap: wrap;
            margin-bottom: 10px;
        }
        
        .filter-bar {
            flex-direction: column;
            align-items: stretch;
        }
        
        .filter-group {
            flex-direction: column;
            align-items: stretch;
        }
        
        .filter-group input[type="text"] {
            min-width: auto;
        }
    }
`;
document.head.appendChild(style);
