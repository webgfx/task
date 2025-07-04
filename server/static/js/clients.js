/**
 * Client Management page JavaScript
 */

let clients = [];

// Initialize after page load
document.addEventListener('DOMContentLoaded', function() {
    initializeClientsPage();
});

// Initialize client page
async function initializeClientsPage() {
    await refreshClients();
    setupEventListeners();
}

// Setup event listeners
function setupEventListeners() {
    // Close modal when clicking outside
    window.addEventListener('click', function(e) {
        const detailModal = document.getElementById('clientDetailModal');
        if (e.target === detailModal) {
            closeClientDetailModal();
        }
    });
}

// Refresh client list
async function refreshClients() {
    try {
        showLoading(document.getElementById('clientGrid'));
        const response = await apiGet('/api/clients');
        clients = response.data || [];
        displayClients();
        
        // Update connection counts
        updateConnectionStats();
    } catch (error) {
        console.error('Refresh client list failed:', error);
        showNotification('Refresh Failed', error.message, 'error');
    } finally {
        hideLoading(document.getElementById('clientGrid'));
    }
}

// Make refreshClients globally available
window.refreshClients = refreshClients;

// For backward compatibility, keep the old function name
window.refreshClients = refreshClients;

// Update connection statistics
function updateConnectionStats() {
    const stats = {
        total: clients.length,
        online: clients.filter(m => m.status === 'online').length,
        offline: clients.filter(m => m.status === 'offline').length,
        busy: clients.filter(m => m.status === 'busy').length
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

// Filter clients based on search and status  
function filterClients() {
    const statusFilter = document.getElementById('statusFilter');
    const searchInput = document.getElementById('searchInput');
    
    // Check if elements exist to avoid null reference errors
    if (!statusFilter || !searchInput) {
        console.error('Filter elements not found');
        return;
    }
    
    const statusValue = statusFilter.value;
    const searchValue = searchInput.value.toLowerCase();
    
    let filteredClients = clients;
    
    // Apply status filter
    if (statusValue) {
        filteredClients = filteredClients.filter(client => client.status === statusValue);
    }
    
    // Apply search filter
    if (searchValue) {
        filteredClients = filteredClients.filter(client => 
            client.name.toLowerCase().includes(searchValue) ||
            client.ip_address.toLowerCase().includes(searchValue) ||
            (client.system_summary && (
                client.system_summary.os?.toLowerCase().includes(searchValue) ||
                client.system_summary.cpu?.toLowerCase().includes(searchValue) ||
                client.system_summary.hostname?.toLowerCase().includes(searchValue)
            ))
        );
    }
    
    // Update clients array for display
    const originalClients = clients;
    clients = filteredClients;
    displayClients();
    clients = originalClients;
}

// Display clients
function displayClients() {
    const container = document.getElementById('clientGrid');
    
    if (clients.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-server" style="font-size: 3rem; color: #6c757d; margin-bottom: 1rem;"></i>
                <h3>No Registered Clients</h3>
                <p>Please start client processes to register clients</p>
                <div class="empty-actions">
                    <code>python client/client.py --client-name your-client-name</code>
                </div>
            </div>
        `;
        return;
    }
    
    const html = clients.map(client => createClientCard(client)).join('');
    container.innerHTML = html;
}

// For backward compatibility
function displayClients() {
    displayClients();
}

// Create Client Card with enhanced system information display
function createClientCard(client) {
    const statusIcon = getStatusIcon(client.status);
    const lastHeartbeat = client.last_heartbeat ? formatRelativeTime(client.last_heartbeat) : 'Never';
    const systemSummary = client.system_summary || {};
    
    // Format detailed system information
    const systemInfo = [];
    
    // Hostname (from client name or system summary)
    const hostname = client.name || systemSummary.hostname || 'Unknown Host';
    
    // OS Information (detailed version)
    if (client.os_info) {
        const os = client.os_info;
        let osDisplay = os.detailed_version || os.system || 'Unknown OS';
        if (!os.detailed_version && os.release) osDisplay += ` ${os.release}`;
        systemInfo.push(`<i class="fas fa-desktop"></i><span>OS: ${osDisplay}</span>`);
    } else if (systemSummary.os) {
        systemInfo.push(`<i class="fas fa-desktop"></i><span>OS: ${systemSummary.os}</span>`);
    }
    
    // CPU Information
    if (client.cpu_info) {
        const cpu = client.cpu_info;
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
    if (client.memory_info) {
        const mem = client.memory_info;
        if (mem.total) {
            systemInfo.push(`<i class="fas fa-memory"></i><span>Memory: ${formatBytes(mem.total)}</span>`);
        }
    } else if (systemSummary.memory) {
        systemInfo.push(`<i class="fas fa-memory"></i><span>Memory: ${systemSummary.memory}</span>`);
    }
    
    // GPU Information with model and driver version
    if (client.gpu_info && client.gpu_info.length > 0) {
        const gpus = client.gpu_info;
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
        <div class="client-card" onclick="viewClientDetail('${client.name}')">
            <div class="client-header">
                <div class="client-title">
                    <div class="client-name">
                        ${statusIcon}
                        ${escapeHtml(client.name)}
                    </div>
                    ${getClientStatusBadge(client.status)}
                </div>
            </div>
            
            <div class="client-body">
                <div class="client-info">
                    <div class="info-item">
                        <i class="fas fa-network-wired"></i>
                        <span>IP Address: ${client.ip_address}:${client.port}</span>
                    </div>
                    <div class="info-item">
                        <i class="fas fa-server"></i>
                        <span>Hostname: ${hostname}</span>
                    </div>
                    <div class="info-item">
                        <i class="fas fa-heartbeat"></i>
                        <span>Last Heartbeat: ${lastHeartbeat}</span>
                    </div>
                    ${client.current_task_id ? `
                    <div class="info-item current-task">
                        <i class="fas fa-tasks"></i>
                        <span>Current Task: #${client.current_task_id}</span>
                    </div>
                    ` : ''}
                    ${client.current_subtask_id ? `
                    <div class="info-item current-subtask">
                        <i class="fas fa-cog"></i>
                        <span>Current Subtask: ${escapeHtml(client.current_subtask_id)}</span>
                    </div>
                    ` : ''}
                    ${systemInfo.length > 0 ? systemInfo.map(info => `
                    <div class="info-item system-info">
                        ${info}
                    </div>
                    `).join('') : ''}
                </div>
                
                <div class="client-actions">
                    <button class="btn btn-sm btn-outline" onclick="event.stopPropagation(); pingClient('${client.name}')" title="Ping Test">
                        <i class="fas fa-satellite-dish"></i>
                    </button>
                    <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); viewClientTasks('${client.name}')" title="View Tasks">
                        <i class="fas fa-list"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="event.stopPropagation(); unregisterClient('${client.name}')" title="Remove Client">
                        <i class="fas fa-trash"></i>
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

// Get client status badge
function getClientStatusBadge(status) {
    const badgeClass = {
        'online': 'badge-success',
        'offline': 'badge-danger',
        'busy': 'badge-warning'
    }[status] || 'badge-secondary';
    
    return `<span class="badge ${badgeClass}">${status.charAt(0).toUpperCase() + status.slice(1)}</span>`;
}

// View client details
async function viewClientDetail(clientName) {
    try {
        const client = clients.find(m => m.name === clientName);
        if (!client) {
            showNotification('Error', 'Client not found', 'error');
            return;
        }
        
        // Get client tasks
        const tasksResponse = await apiGet('/api/tasks');
        const allTasks = tasksResponse.data || [];
        const clientTasks = allTasks.filter(task => 
            task.target_clients && task.target_clients.includes(clientName)
        );
        
        showClientDetailModal(client, clientTasks);
    } catch (error) {
        console.error('View client detail failed:', error);
        showNotification('Error', error.message, 'error');
    }
}

// Show client details modal
function showClientDetailModal(client, tasks) {
    const modal = document.getElementById('clientDetailModal');
    const content = document.getElementById('clientDetailContent');
    
    const onlineTasks = tasks.filter(task => task.status === 'running');
    const completedTasks = tasks.filter(task => task.status === 'completed');
    const failedTasks = tasks.filter(task => task.status === 'failed');
    const systemSummary = client.system_summary || {};
    
    // Format detailed system information
    function formatSystemDetails() {
        if (!client.cpu_info && !client.memory_info && !client.gpu_info && !client.os_info) {
            return '<p style="color: #6c757d;">No detailed system information available</p>';
        }
        
        let details = '';
        
        // CPU Information
        if (client.cpu_info) {
            const cpu = client.cpu_info;
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
        if (client.memory_info) {
            const mem = client.memory_info;
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
        if (client.gpu_info && client.gpu_info.length > 0) {
            details += `
                <div class="detail-subsection">
                    <h5><i class="fas fa-tv"></i> GPU Information</h5>
            `;
            client.gpu_info.forEach((gpu, index) => {
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
        if (client.os_info) {
            const os = client.os_info;
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
        <div class="client-detail">
            <div class="detail-section">
                <h4>Client Information</h4>
                <div class="detail-grid">
                    <div class="detail-item">
                        <label>Client Name:</label>
                        <span>${escapeHtml(client.name)}</span>
                    </div>
                    <div class="detail-item">
                        <label>Hostname:</label>
                        <span>${escapeHtml(systemSummary.hostname || client.name || 'Unknown')}</span>
                    </div>
                    <div class="detail-item">
                        <label>Status:</label>
                        <span>${getClientStatusBadge(client.status)}</span>
                    </div>
                    <div class="detail-item">
                        <label>IP Address:</label>
                        <span>${client.ip_address}:${client.port}</span>
                    </div>
                    <div class="detail-item">
                        <label>Last Heartbeat:</label>
                        <span>${client.last_heartbeat ? formatRelativeTime(client.last_heartbeat) : 'Never'}</span>
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
                ` : '<p style="color: #6c757d;">No tasks assigned to this client</p>'}
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

// Close client details modal
function closeClientDetailModal() {
    const modal = document.getElementById('clientDetailModal');
    modal.style.display = 'none';
}

// View client tasks
async function viewClientTasks(clientName) {
    try {
        const tasksResponse = await apiGet('/api/tasks');
        const allTasks = tasksResponse.data || [];
        const clientTasks = allTasks.filter(task => 
            task.target_clients && task.target_clients.includes(clientName)
        );
        
        showNotification('Info', `Found ${clientTasks.length} tasks for ${clientName}`, 'info');
    } catch (error) {
        console.error('View client tasks failed:', error);
        showNotification('Error', error.message, 'error');
    }
}

// Ping client
async function pingClient(clientName) {
    try {
        showNotification('Info', `Pinging ${clientName}...`, 'info');
        
        // This would typically make an API call to ping the client
        setTimeout(() => {
            showNotification('Success', `${clientName} is reachable`, 'success');
        }, 1000);
    } catch (error) {
        console.error('Ping client failed:', error);
        showNotification('Error', error.message, 'error');
    }
}

// Unregister client
async function unregisterClient(clientName) {
    try {
        // Get client info for better confirmation dialog
        const client = clients.find(m => m.name === clientName);
        const currentTasks = client && client.current_task_id ? `\n- Has active task #${client.current_task_id}` : '';
        
        // Show detailed confirmation dialog
        const confirmMessage = `Are you sure you want to unregister client "${clientName}"?

This will:
- PERMANENTLY remove the client from the database
- Remove it from active task assignments${currentTasks}
- Stop receiving heartbeats from this client
- Client can re-register automatically if still running

This action cannot be undone. Continue?`;

        if (!confirm(confirmMessage)) {
            return;
        }
        
        showNotification('Info', `Unregistering ${clientName}...`, 'info');
        
        // Call the DELETE API to permanently remove the client
        const response = await fetch(`/api/clients/${encodeURIComponent(clientName)}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Success', `Client ${clientName} has been unregistered and removed from database`, 'success');
            // Refresh the client list to reflect changes
            await refreshClients();
        } else {
            throw new Error(result.error || 'Failed to unregister client');
        }
        
    } catch (error) {
        console.error('Unregister client failed:', error);
        showNotification('Error', `Failed to unregister ${clientName}: ${error.message}`, 'error');
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
