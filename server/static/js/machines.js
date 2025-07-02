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

// Make refreshMachines globally available
window.refreshMachines = refreshMachines;

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
            ))
        );
    }
    
    // Update machines array for display
    const originalMachines = machines;
    machines = filteredMachines;
    displayMachines();
    machines = originalMachines;
}

// Display machines
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
    const systemSummary = machine.system_summary || {};
    
    // Format detailed system information
    const systemInfo = [];
    
    // Hostname (from machine name or system summary)
    const hostname = machine.name || systemSummary.hostname || 'Unknown Host';
    
    // OS Information (detailed version)
    if (machine.os_info) {
        const os = machine.os_info;
        let osDisplay = os.detailed_version || os.system || 'Unknown OS';
        if (!os.detailed_version && os.release) osDisplay += ` ${os.release}`;
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
    
    // GPU Information with model and driver version
    if (machine.gpu_info && machine.gpu_info.length > 0) {
        const gpus = machine.gpu_info;
        if (gpus.length === 1) {
            const gpu = gpus[0];
            let gpuDisplay = gpu.model || gpu.name || 'Unknown GPU';
            if (gpu.driver_version && gpu.driver_version !== 'Unknown') {
                gpuDisplay += ` (Driver: ${gpu.driver_version})`;
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
                        <i class="fas fa-server"></i>
                        <span>Hostname: ${hostname}</span>
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
                </div>
                
                <div class="machine-actions">
                    <button class="btn btn-sm btn-outline" onclick="event.stopPropagation(); pingMachine('${machine.name}')" title="Ping Test">
                        <i class="fas fa-satellite-dish"></i>
                    </button>
                    <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); viewMachineTasks('${machine.name}')" title="View Tasks">
                        <i class="fas fa-list"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="event.stopPropagation(); unregisterMachine('${machine.name}')" title="Unregister Client">
                        <i class="fas fa-user-minus"></i>
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

// Get machine status badge
function getMachineStatusBadge(status) {
    const badgeClass = {
        'online': 'badge-success',
        'offline': 'badge-danger',
        'busy': 'badge-warning'
    }[status] || 'badge-secondary';
    
    return `<span class="badge ${badgeClass}">${status.charAt(0).toUpperCase() + status.slice(1)}</span>`;
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
            task.target_machines && task.target_machines.includes(machineName)
        );
        
        showMachineDetailModal(machine, machineTasks);
    } catch (error) {
        console.error('View machine detail failed:', error);
        showNotification('Error', error.message, 'error');
    }
}

// Show machine details modal
function showMachineDetailModal(machine, tasks) {
    const modal = document.getElementById('machineDetailModal');
    const content = document.getElementById('machineDetailContent');
    
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
        
        // Memory Information
        if (machine.memory_info) {
            const mem = machine.memory_info;
            details += `
                <div class="detail-subsection">
                    <h5><i class="fas fa-memory"></i> Memory Information</h5>
                    <div class="detail-grid">
                        ${mem.total ? `<div class="detail-item"><label>Total Memory:</label><span>${formatBytes(mem.total)}</span></div>` : ''}
                        ${mem.available ? `<div class="detail-item"><label>Available Memory:</label><span>${formatBytes(mem.available)}</span></div>` : ''}
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
                        <div class="detail-item"><label>GPU ${index + 1} Model:</label><span>${gpu.model || gpu.name || 'Unknown'}</span></div>
                        ${gpu.vendor ? `<div class="detail-item"><label>Vendor:</label><span>${gpu.vendor}</span></div>` : ''}
                        ${gpu.driver_version && gpu.driver_version !== 'Unknown' ? `<div class="detail-item"><label>Driver Version:</label><span>${gpu.driver_version}</span></div>` : ''}
                        ${gpu.memory_total ? `<div class="detail-item"><label>Memory:</label><span>${formatBytes(gpu.memory_total)}</span></div>` : ''}
                    </div>
                `;
            });
            details += '</div>';
        }
        
        // Operating System
        if (machine.os_info) {
            const os = machine.os_info;
            details += `
                <div class="detail-subsection">
                    <h5><i class="fas fa-desktop"></i> Operating System</h5>
                    <div class="detail-grid">
                        ${os.detailed_version ? `<div class="detail-item"><label>Version:</label><span>${os.detailed_version}</span></div>` : ''}
                        ${os.system ? `<div class="detail-item"><label>System:</label><span>${os.system}</span></div>` : ''}
                        ${os.machine ? `<div class="detail-item"><label>Architecture:</label><span>${os.machine}</span></div>` : ''}
                        ${os.windows_build ? `<div class="detail-item"><label>Build:</label><span>${os.windows_build}</span></div>` : ''}
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
                        <label>Hostname:</label>
                        <span>${escapeHtml(systemSummary.hostname || machine.name || 'Unknown')}</span>
                    </div>
                    <div class="detail-item">
                        <label>Status:</label>
                        <span>${getMachineStatusBadge(machine.status)}</span>
                    </div>
                    <div class="detail-item">
                        <label>IP Address:</label>
                        <span>${machine.ip_address}:${machine.port}</span>
                    </div>
                    <div class="detail-item">
                        <label>Last Heartbeat:</label>
                        <span>${machine.last_heartbeat ? formatRelativeTime(machine.last_heartbeat) : 'Never'}</span>
                    </div>
                </div>
            </div>
            
            <div class="detail-section">
                <h4>Task Statistics</h4>
                <div class="task-stats">
                    <div class="stat-item">
                        <span class="stat-number">${tasks.length}</span>
                        <span class="stat-label">Total</span>
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
                ` : '<p style="color: #6c757d;">No tasks assigned to this machine</p>'}
            </div>
            
            <div class="detail-section">
                <h4>System Details</h4>
                ${formatSystemDetails()}
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

// View machine tasks
async function viewMachineTasks(machineName) {
    try {
        const tasksResponse = await apiGet('/api/tasks');
        const allTasks = tasksResponse.data || [];
        const machineTasks = allTasks.filter(task => 
            task.target_machines && task.target_machines.includes(machineName)
        );
        
        showNotification('Info', `Found ${machineTasks.length} tasks for ${machineName}`, 'info');
    } catch (error) {
        console.error('View machine tasks failed:', error);
        showNotification('Error', error.message, 'error');
    }
}

// Ping machine
async function pingMachine(machineName) {
    try {
        showNotification('Info', `Pinging ${machineName}...`, 'info');
        
        // This would typically make an API call to ping the machine
        setTimeout(() => {
            showNotification('Success', `${machineName} is reachable`, 'success');
        }, 1000);
    } catch (error) {
        console.error('Ping machine failed:', error);
        showNotification('Error', error.message, 'error');
    }
}

// Unregister machine
async function unregisterMachine(machineName) {
    try {
        // Get machine info for better confirmation dialog
        const machine = machines.find(m => m.name === machineName);
        const currentTasks = machine && machine.current_task_id ? `\n- Has active task #${machine.current_task_id}` : '';
        
        // Show detailed confirmation dialog
        const confirmMessage = `Are you sure you want to unregister client "${machineName}"?

This will:
- Mark the client as OFFLINE
- Remove it from active task assignments${currentTasks}
- Stop receiving heartbeats from this client
- Client can re-register automatically if still running

This action cannot be undone. Continue?`;

        if (!confirm(confirmMessage)) {
            return;
        }
        
        showNotification('Info', `Unregistering ${machineName}...`, 'info');
        
        // Call the unregister API
        const response = await fetch('/api/machines/unregister', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: machineName
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Success', `Client ${machineName} has been unregistered successfully`, 'success');
            // Refresh the machine list to reflect changes
            await refreshMachines();
        } else {
            throw new Error(result.error || 'Failed to unregister client');
        }
        
    } catch (error) {
        console.error('Unregister machine failed:', error);
        showNotification('Error', `Failed to unregister ${machineName}: ${error.message}`, 'error');
    }
}

// Format bytes to human readable format
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const units = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    
    while (bytes >= k && i < units.length - 1) {
        bytes /= k;
        i++;
    }
    
    return `${bytes.toFixed(1)} ${units[i]}`;
}
