/**
 * Main application JavaScript file
 * Contains common functionality and WebSocket connections
 */

// Global variables
let socket = null;
let currentPage = 1;
let itemsPerPage = 10;

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initializeSocket();
    setupNavigation();
    setupNotifications();
});

// Initialize WebSocket connection
function initializeSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('WebSocket connection successful');
        updateConnectionStatus(true);
        showNotification('Connection Successful', 'Connected to server', 'success');
    });
    
    socket.on('disconnect', function() {
        console.log('WebSocket connection disconnected');
        updateConnectionStatus(false);
        showNotification('Connection Lost', 'Connection to server has been lost', 'error');
    });
    
    socket.on('task_created', function(data) {
        showNotification('Task Created', `Task ${data.name} has been created`, 'success');
        if (typeof refreshTasks === 'function') {
            refreshTasks();
        }
    });
    
    socket.on('task_updated', function(data) {
        showNotification('Task Updated', `Task ${data.name} has been updated`, 'info');
        if (typeof refreshTasks === 'function') {
            refreshTasks();
        }
    });
    
    socket.on('task_deleted', function(data) {
        showNotification('Task Deleted', `Task ID: ${data.id} deleted`, 'warning');
        if (typeof refreshTasks === 'function') {
            refreshTasks();
        }
    });
    
    socket.on('task_started', function(data) {
        showNotification('Taskstart execute', `Task ID: ${data.task_id} started executing on machine ${data.machine_name}`, 'info');
        if (typeof refreshTasks === 'function') {
            refreshTasks();
        }
    });
    
    socket.on('task_completed', function(data) {
        const status = data.success ? 'Success' : 'Failed';
        const type = data.success ? 'success' : 'error';
        showNotification('Task execution completed', `Task ID: ${data.task_id} execute${status}`, type);
        if (typeof refreshTasks === 'function') {
            refreshTasks();
        }
    });
    
    socket.on('machine_registered', function(data) {
        showNotification('Machine Registered', `Machine ${data.name} registered`, 'success');
        if (typeof refreshMachines === 'function') {
            refreshMachines();
        }
    });
    
    socket.on('machine_heartbeat', function(data) {
        console.log('Machine heartbeat:', data);
        if (typeof updateMachineStatus === 'function') {
            updateMachineStatus(data);
        }
    });
    
    socket.on('machine_offline', function(data) {
        showNotification('MachineOffline', `Machine ${data.machine_name} Offlineed`, 'warning');
        if (typeof refreshMachines === 'function') {
            refreshMachines();
        }
    });
}

// Update connection status
function updateConnectionStatus(connected) {
    const statusElement = document.getElementById('connectionStatus');
    if (statusElement) {
        if (connected) {
            statusElement.innerHTML = '<i class=fas fa-circle text-success></i> Connected';
            statusElement.className = 'connection-status';
        } else {
            statusElement.innerHTML = '<i class=fas fa-circle text-danger></i> Connection Lost';
            statusElement.className = 'connection-status text-danger';
        }
    }
}

// Setup navigation
function setupNavigation() {
    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        const link = item.querySelector('.nav-link');
        if (link && link.getAttribute('href') === currentPath) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

// Setup notification system
function setupNotifications() {
    // Create notification container (if not exists)
    if (!document.getElementById('notifications')) {
        const notificationsContainer = document.createElement('div');
        notificationsContainer.id = 'notifications';
        notificationsContainer.className = 'notifications';
        document.body.appendChild(notificationsContainer);
    }
}

// Show notification
function showNotification(title, message, type = 'info', duration = 5000) {
    const notificationsContainer = document.getElementById('notifications');
    if (!notificationsContainer) return;
    
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class=notification-header>
            <span class=notification-title>${title}</span>
            <button class=notification-close onclick=closeNotification(this)>
                <i class=fas fa-times></i>
            </button>
        </div>
        <div class=notification-message>${message}</div>
    `;
    
    notificationsContainer.appendChild(notification);
    
    // Auto-close notification
    if (duration > 0) {
        setTimeout(() => {
            closeNotification(notification.querySelector('.notification-close'));
        }, duration);
    }
}

// Close notification
function closeNotification(button) {
    const notification = button.closest('.notification');
    if (notification) {
        notification.style.animation = 'notificationSlideOut 0.3s ease';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }
}

// API request wrapper
async function apiRequest(url, options = {}) {
    try {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };
        
        const finalOptions = { ...defaultOptions, ...options };
        
        const response = await fetch(url, finalOptions);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }
        
        return data;
    } catch (error) {
        console.error('API request failed:', error);
        showNotification('Request failed', error.message, 'error');
        throw error;
    }
}

// GET request
async function apiGet(url) {
    return apiRequest(url, { method: 'GET' });
}

// POST request
async function apiPost(url, data) {
    return apiRequest(url, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

// PUT request
async function apiPut(url, data) {
    return apiRequest(url, {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}

// DELETE request
async function apiDelete(url) {
    return apiRequest(url, { method: 'DELETE' });
}

// Format datetime
function formatDateTime(dateString) {
    if (!dateString) return '-';
    
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// Format relative time
function formatRelativeTime(dateString) {
    if (!dateString) return '-';
    
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) return `${days} days ago`;
    if (hours > 0) return `${hours} hours ago`;
    if (minutes > 0) return `${minutes} minutes ago`;
    return `${seconds} seconds ago`;
}

// Get Status Badge HTML
function getStatusBadge(status) {
    const statusMap = {
        'pending': { class: 'status-pending', text: 'Pending' },
        'running': { class: 'status-running', text: 'Running' },
        'completed': { class: 'status-completed', text: 'Completed' },
        'failed': { class: 'status-failed', text: 'Failed' },
        'cancelled': { class: 'status-cancelled', text: 'Canceled' }
    };
    
    const statusInfo = statusMap[status] || { class: 'status-pending', text: status };
    return `<span class=status-badge ${statusInfo.class}>${statusInfo.text}</span>`;
}

// Get Machine StatusTagsHTML
function getMachineStatusBadge(status) {
    const statusMap = {
        'online': { class: 'machine-online', text: 'Online' },
        'offline': { class: 'machine-offline', text: 'Offline' },
        'busy': { class: 'machine-busy', text: 'Busy' }
    };
    
    const statusInfo = statusMap[status] || { class: 'machine-offline', text: status };
    return `<span class=machine-status ${statusInfo.class}>${statusInfo.text}</span>`;
}

// Confirmdialog
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Loading state management
function showLoading(element) {
    if (element) {
        element.style.opacity = '0.5';
        element.style.pointerEvents = 'none';
    }
}

function hideLoading(element) {
    if (element) {
        element.style.opacity = '1';
        element.style.pointerEvents = 'auto';
    }
}

// Form validation
function validateForm(formElement) {
    const requiredFields = formElement.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('error');
            isValid = false;
        } else {
            field.classList.remove('error');
        }
    });
    
    return isValid;
}

// Clear form inputs
function clearForm(formElement) {
    const inputs = formElement.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        if (input.type === 'checkbox' || input.type === 'radio') {
            input.checked = false;
        } else {
            input.value = '';
        }
        input.classList.remove('error');
    });
}

// Set form data
function setFormData(formElement, data) {
    Object.keys(data).forEach(key => {
        const element = formElement.querySelector(`[name=${key}], #${key}`);
        if (element) {
            if (element.type === 'checkbox') {
                element.checked = data[key];
            } else {
                element.value = data[key] || '';
            }
        }
    });
}

// Get form data
function getFormData(formElement) {
    const formData = new FormData(formElement);
    const data = {};
    
    for (let [key, value] of formData.entries()) {
        data[key] = value;
    }
    
    // Handle fields with ID attributes
    const inputs = formElement.querySelectorAll('input[id], select[id], textarea[id]');
    inputs.forEach(input => {
        const key = input.id;
        if (input.type === 'checkbox') {
            data[key] = input.checked;
        } else {
            data[key] = input.value;
        }
    });
    
    return data;
}

// Pagination function
function createPagination(totalItems, currentPage, itemsPerPage, container, onPageChange) {
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    let html = '';
    
    // Previous page button
    html += `<button ${currentPage === 1 ? 'disabled' : ''} onclick=${onPageChange}(${currentPage - 1})>
        <i class=fas fa-chevron-left></i>
    </button>`;
    
    // Page number buttons
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            html += `<button class=${i === currentPage ? 'active' : ''} onclick=${onPageChange}(${i})>${i}</button>`;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            html += '<span>...</span>';
        }
    }
    
    // Next page button
    html += `<button ${currentPage === totalPages ? 'disabled' : ''} onclick=${onPageChange}(${currentPage + 1})>
        <i class=fas fa-chevron-right></i>
    </button>`;
    
    container.innerHTML = html;
}

// Add CSS animation classes
const style = document.createElement('style');
style.textContent = `
    @keyframes notificationSlideOut {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100%);
        }
    }
    
    .error {
        border-color: #dc3545 !important;
        box-shadow: 0 0 0 3px rgba(220, 53, 69, 0.1) !important;
    }
`;
document.head.appendChild(style);
