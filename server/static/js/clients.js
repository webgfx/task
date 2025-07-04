/**
 * Client Management page JavaScript
 */

let clients = [];
let allClientDetailsVisible = true; // Track global visibility state for clients

// Legacy function stub for backward compatibility (prevents console errors)
function toggleView() {
    console.warn('toggleView function called but card/table view toggle has been removed. Using table view only.');
}

// Initialize after page load
document.addEventListener('DOMContentLoaded', function() {
    // Add a small delay to ensure all elements are rendered
    setTimeout(() => {
        initializeClientsPage();
    }, 100);
});

// Initialize client page
async function initializeClientsPage() {
    // Wait for DOM to be fully ready and check multiple times if needed
    let retryCount = 0;
    const maxRetries = 5;
    
    while (retryCount < maxRetries) {
        const clientTableContainer = document.getElementById('clientTableContainer');
        
        if (clientTableContainer) {
            // Table container found, proceed with initialization
            await refreshClients();
            setupEventListeners();
            return;
        }
        
        // Elements not found, wait and retry
        retryCount++;
        console.log(`Client table container not ready, retry ${retryCount}/${maxRetries}`);
        await new Promise(resolve => setTimeout(resolve, 200));
    }
    
    // If we get here, elements weren't found after retries
    console.error('Required client page elements not found after retries');
    showNotification('Page Error', 'Client management page failed to initialize properly', 'error');
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
        // Show loading on the table container
        const loadingContainer = document.getElementById('clientTableContainer');
            
        if (loadingContainer) {
            showLoading(loadingContainer);
        } else {
            // Fallback: show a general loading notification
            console.log('Loading clients...');
        }
        
        const response = await apiGet('/api/clients');
        clients = response.data || [];
        displayClients();
        
        // Update connection counts
        updateConnectionStats();
    } catch (error) {
        console.error('Refresh client list failed:', error);
        showNotification('Refresh Failed', error.message, 'error');
    } finally {
        // Hide loading from the table container
        const loadingContainer = document.getElementById('clientTableContainer');
            
        if (loadingContainer) {
            hideLoading(loadingContainer);
        }
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
        online: clients.filter(c => c.status === 'online').length,
        offline: clients.filter(c => c.status === 'offline').length,
        busy: clients.filter(c => c.status === 'busy').length
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

// Display clients (table view only)
function displayClients() {
    displayClientsTable();
}

// Display clients in table view
function displayClientsTable() {
    const tbody = document.getElementById('clientTableBody');
    
    if (!tbody) {
        console.error('Client table body not found');
        return;
    }
    
    if (clients.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center" style="padding: 40px;">
                    <i class="fas fa-server" style="font-size: 2rem; color: #6c757d; margin-bottom: 1rem;"></i>
                    <div>No Registered Clients</div>
                    <small style="color: #6c757d;">Please start client processes to register clients</small>
                </td>
            </tr>
        `;
        return;
    }
    
    const html = clients.map(client => createClientTableRow(client)).join('');
    tbody.innerHTML = html;
    
    // Ensure all toggle icons are in correct initial state
    initializeClientToggleIconStates();
    
    // Load details for all clients immediately since they're shown by default
    // Add a small delay between requests to avoid overwhelming the server
    clients.forEach((client, index) => {
        setTimeout(() => {
            loadClientDetails(client.name);
        }, index * 100); // 100ms delay between each client detail load
    });
}

// Create client table row with toggle functionality
function createClientTableRow(client) {
    const statusIcon = getStatusIcon(client.status);
    const lastHeartbeat = client.last_heartbeat ? formatRelativeTime(client.last_heartbeat) : 'Never';
    
    // Get current task and subtask information
    const taskId = client.current_task_id || '-';
    const taskName = client.current_task_name || '-';
    const subtaskId = client.current_subtask_id || '-';
    const subtaskName = client.current_subtask_id ? getSubtaskDisplayName(client.current_subtask_id) : '-';
    
    // Main client row
    const mainRow = `
        <tr class="client-main-row" data-client="${client.name}">
            <td class="client-name-col">
                ${statusIcon}
                <span style="margin-left: 8px;">${escapeHtml(client.name)}</span>
            </td>
            <td class="status-col">
                ${getClientStatusBadge(client.status)}
            </td>
            <td class="ip-col">
                ${client.ip_address}
            </td>
            <td class="task-id-col">
                ${taskId !== '-' ? `<span class="task-id-badge">#${taskId}</span>` : '<span class="no-id">—</span>'}
            </td>
            <td class="task-name-col">
                <div class="task-name-info">
                    <span class="task-name">${escapeHtml(taskName)}</span>
                </div>
            </td>
            <td class="subtask-id-col">
                ${subtaskId !== '-' ? `<span class="subtask-id-badge">${escapeHtml(subtaskId)}</span>` : '<span class="no-id">—</span>'}
            </td>
            <td class="subtask-name-col">
                <div class="subtask-name-info">
                    <span class="subtask-name">${escapeHtml(subtaskName)}</span>
                </div>
            </td>
            <td class="heartbeat-col">
                ${lastHeartbeat}
            </td>
            <td class="actions-col">
                <div class="row-actions">
                    <button class="collapse-toggle" onclick="event.stopPropagation(); toggleClientDetails('${client.name}')" 
                            title="Toggle client details">
                        <i class="fas fa-chevron-up" id="toggle-icon-${client.name}"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="event.stopPropagation(); unregisterClient('${client.name}')" title="Remove Client">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
    
    // Details row (initially expanded to show details by default)
    const detailsRow = `
        <tr class="client-details-row client-${client.name}-details" data-client="${client.name}">
            <td colspan="9">
                <div class="client-details-content" id="client-details-${client.name}">
                    <!-- Content will be loaded dynamically -->
                    <div class="loading-placeholder">
                        <i class="fas fa-spinner fa-spin"></i> Loading details...
                    </div>
                </div>
            </td>
        </tr>
    `;
    
    return mainRow + detailsRow;
}

// Initialize client toggle icon states to match current visibility
function initializeClientToggleIconStates() {
    // Set individual client toggle icons based on current visibility state
    const allToggleIcons = document.querySelectorAll('.collapse-toggle i[id^="toggle-icon-"]');
    allToggleIcons.forEach(icon => {
        // Since details are visible by default (not collapsed), show chevron-up
        icon.className = 'fas fa-chevron-up';
    });
}

// Toggle client details visibility
async function toggleClientDetails(clientName) {
    const detailsRows = document.querySelectorAll(`.client-${clientName}-details`);
    const toggleIcon = document.getElementById(`toggle-icon-${clientName}`);
    
    if (!toggleIcon || detailsRows.length === 0) return;
    
    const isCollapsed = detailsRows[0].classList.contains('collapsed');
    
    detailsRows.forEach(row => {
        if (isCollapsed) {
            row.classList.remove('collapsed');
        } else {
            row.classList.add('collapsed');
        }
    });
    
    // Update toggle icon based on NEW state after toggle
    // If was collapsed (now expanding) → show up arrow (visible state)
    // If was visible (now collapsing) → show down arrow (hidden state)
    toggleIcon.className = isCollapsed ? 'fas fa-chevron-up' : 'fas fa-chevron-down';
    
    // Load detailed content when expanding (or initially if details are shown by default)
    if (isCollapsed) {
        await loadClientDetails(clientName);
    }
}

// Toggle all client details visibility (page-wise toggle)
function toggleAllClientDetails() {
    const toggleIcon = document.getElementById('toggleAllClientsIcon');
    const toggleText = document.getElementById('toggleAllClientsText');
    
    // Get all client detail rows and toggle icons
    const allDetailRows = document.querySelectorAll('.client-details-row');
    const allToggleIcons = document.querySelectorAll('.collapse-toggle i[id^="toggle-icon-"]');
    
    if (allClientDetailsVisible) {
        // Hide all details
        allDetailRows.forEach(row => {
            row.classList.add('collapsed');
        });
        
        allToggleIcons.forEach(icon => {
            icon.className = 'fas fa-chevron-down'; // Down arrow when hidden
        });
        
        toggleIcon.className = 'fas fa-eye';
        toggleText.textContent = 'Show All Details';
        allClientDetailsVisible = false;
    } else {
        // Show all details
        allDetailRows.forEach(row => {
            row.classList.remove('collapsed');
        });
        
        allToggleIcons.forEach(icon => {
            icon.className = 'fas fa-chevron-up'; // Up arrow when visible
        });
        
        toggleIcon.className = 'fas fa-eye-slash';
        toggleText.textContent = 'Hide All Details';
        allClientDetailsVisible = true;
        
        // Load details for all clients when showing
        clients.forEach((client, index) => {
            setTimeout(() => {
                loadClientDetails(client.name);
            }, index * 100);
        });
    }
}

// Load comprehensive client details
async function loadClientDetails(clientName) {
    try {
        const client = clients.find(c => c.name === clientName);
        if (!client) {
            console.error('Client not found:', clientName);
            return;
        }
        
        // Get client tasks
        const tasksResponse = await apiGet('/api/tasks');
        const allTasks = tasksResponse.data || [];
        const clientTasks = allTasks.filter(task => 
            task.clients && task.clients.includes(clientName)
        );
        
        const detailsContent = formatClientDetails(client, clientTasks);
        const contentElement = document.getElementById(`client-details-${clientName}`);
        if (contentElement) {
            contentElement.innerHTML = detailsContent;
        }
    } catch (error) {
        console.error('Failed to load client details:', error);
        const contentElement = document.getElementById(`client-details-${clientName}`);
        if (contentElement) {
            contentElement.innerHTML = '<div class="error-message">Failed to load client details</div>';
        }
    }
}

// Format comprehensive client details
function formatClientDetails(client, tasks) {
    const systemSummary = client.system_summary || {};
    
    // Format compact system information
    function formatCompactSystemDetails() {
        if (!client.cpu_info && !client.memory_info && !client.gpu_info && !client.os_info) {
            return '<p style="color: #6c757d;">No system information available</p>';
        }
        
        let details = '<div class="compact-system-info">';
        
        // CPU Information (compact)
        if (client.cpu_info) {
            const cpu = client.cpu_info;
            const cpuText = cpu.processor || 'Unknown CPU';
            const cores = cpu.cpu_count_logical ? ` (${cpu.cpu_count_logical} cores)` : '';
            const freq = cpu.cpu_freq_max ? ` @ ${(cpu.cpu_freq_max / 1000).toFixed(1)}GHz` : '';
            details += `
                <div class="system-info-item">
                    <i class="fas fa-microchip"></i>
                    <span class="info-label">CPU:</span>
                    <span class="info-value">${cpuText}${cores}${freq}</span>
                </div>
            `;
        }
        
        // Memory Information (compact)
        if (client.memory_info) {
            const mem = client.memory_info;
            const total = mem.total ? formatBytes(mem.total) : 'Unknown';
            details += `
                <div class="system-info-item">
                    <i class="fas fa-memory"></i>
                    <span class="info-label">Memory:</span>
                    <span class="info-value">${total}</span>
                </div>
            `;
        }
        
        // GPU Information (compact)
        if (client.gpu_info && client.gpu_info.length > 0) {
            client.gpu_info.forEach((gpu, index) => {
                const gpuName = gpu.model || gpu.name || 'Unknown GPU';
                const memory = gpu.memory_total ? ` (${formatBytes(gpu.memory_total)})` : '';
                const driver = gpu.driver_version ? ` - Driver: ${gpu.driver_version}` : '';
                const driverDate = gpu.driver_date ? ` (${gpu.driver_date})` : '';
                const deviceId = gpu.device_id ? ` - ID: ${gpu.device_id}` : '';
                const prefix = client.gpu_info.length > 1 ? `GPU ${index + 1}: ` : 'GPU: ';
                details += `
                    <div class="system-info-item">
                        <i class="fas fa-tv"></i>
                        <span class="info-label">${prefix}</span>
                        <span class="info-value">${gpuName}${memory}${driver}${driverDate}${deviceId}</span>
                    </div>
                `;
            });
        }
        
        // Operating System (compact)
        if (client.os_info) {
            const os = client.os_info;
            const osText = os.detailed_version || os.system || 'Unknown OS';
            const arch = os.machine ? ` (${os.machine})` : '';
            details += `
                <div class="system-info-item">
                    <i class="fas fa-desktop"></i>
                    <span class="info-label">OS:</span>
                    <span class="info-value">${osText}${arch}</span>
                </div>
            `;
        }
        
        details += '</div>';
        return details;
    }
    
    return `
        <div class="client-detail">
            <div class="detail-section">
                ${formatCompactSystemDetails()}
            </div>
        </div>
    `;
}

// Get display name for subtask (convert ID to readable name)
function getSubtaskDisplayName(subtaskId) {
    // Convert snake_case or camelCase to readable names
    if (!subtaskId || subtaskId === '-' || subtaskId === '') return '—';
    
    // Common subtask name mappings
    const nameMap = {
        'get_hostname': 'Get Hostname',
        'get_system_info': 'Get System Info',
        'dawn_e2e_tests': 'Dawn E2E Tests',
        'system_info': 'System Info',
        'hostname': 'Hostname',
        'log_cleanup': 'Log Cleanup',
        'file_download': 'File Download',
        'command_execution': 'Subtask Execution',
        'system_monitoring': 'System Monitoring'
    };
    
    // Check if we have a predefined mapping
    if (nameMap[subtaskId]) {
        return nameMap[subtaskId];
    }
    
    // Convert snake_case to readable format
    return subtaskId
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
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



// Unregister client
async function unregisterClient(clientName) {
    try {
        // Get client info for better confirmation dialog
        const client = clients.find(c => c.name === clientName);
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
