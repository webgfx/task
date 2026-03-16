/**
 * Results page JavaScript - Cached task results viewer
 */

let allResults = [];
let clientsList = [];
let subtasksList = [];

// Initialize after page load
document.addEventListener('DOMContentLoaded', function() {
    initializeResultsPage();
});

async function initializeResultsPage() {
    await loadClients();
    await loadSubtasks();
    await refreshResults();
    populateFilters();
}

// Load clients for filter dropdown
async function loadClients() {
    try {
        const response = await apiGet('/api/clients');
        clientsList = response.data || [];
    } catch (error) {
        console.error('Failed to load clients:', error);
    }
}

// Load subtask definitions for filter dropdown
async function loadSubtasks() {
    try {
        const response = await apiGet('/api/subtasks');
        subtasksList = response.data || [];
    } catch (error) {
        console.error('Failed to load subtasks:', error);
    }
}

// Populate filter dropdowns
function populateFilters() {
    const clientFilter = document.getElementById('clientFilter');
    if (clientFilter) {
        // Keep the first "All Clients" option
        clientFilter.innerHTML = '<option value="">All Clients</option>';
        clientsList.forEach(client => {
            const option = document.createElement('option');
            option.value = client.name;
            option.textContent = client.name;
            clientFilter.appendChild(option);
        });
    }

    const subtaskFilter = document.getElementById('subtaskFilter');
    if (subtaskFilter) {
        subtaskFilter.innerHTML = '<option value="">All Subtasks</option>';
        // Extract unique subtask names from results
        const uniqueSubtasks = new Set();
        allResults.forEach(r => uniqueSubtasks.add(r.subtask_name));
        // Also add from subtask definitions
        subtasksList.forEach(s => uniqueSubtasks.add(s.name));

        uniqueSubtasks.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            subtaskFilter.appendChild(option);
        });
    }
}

// Refresh results from server
async function refreshResults() {
    try {
        const response = await apiGet('/api/results?limit=200');
        allResults = response.data || [];
        renderResults(allResults);
        populateFilters();
    } catch (error) {
        console.error('Failed to load results:', error);
        showNotification('Error', 'Failed to load cached results', 'error');
    }
}

// Filter results based on selected criteria
function filterResults() {
    const clientFilter = document.getElementById('clientFilter');
    const subtaskFilter = document.getElementById('subtaskFilter');
    const statusFilter = document.getElementById('statusFilter');

    const clientValue = clientFilter ? clientFilter.value : '';
    const subtaskValue = subtaskFilter ? subtaskFilter.value : '';
    const statusValue = statusFilter ? statusFilter.value : '';

    let filtered = allResults;

    if (clientValue) {
        filtered = filtered.filter(r => r.client_name === clientValue);
    }
    if (subtaskValue) {
        filtered = filtered.filter(r => r.subtask_name === subtaskValue);
    }
    if (statusValue) {
        filtered = filtered.filter(r => r.status === statusValue);
    }

    renderResults(filtered);
}

// Render results table
function renderResults(results) {
    const tbody = document.getElementById('resultsBody');
    const countEl = document.getElementById('resultCount');
    if (!tbody) return;

    if (countEl) {
        countEl.textContent = `${results.length} results`;
    }

    if (results.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center">No results found</td></tr>';
        return;
    }

    tbody.innerHTML = results.map(result => {
        const statusClass = result.status === 'completed' ? 'status-completed' :
                           result.status === 'failed' ? 'status-failed' : 'status-pending';
        const statusIcon = result.status === 'completed' ? 'fa-check-circle' :
                          result.status === 'failed' ? 'fa-times-circle' : 'fa-clock';

        const execTime = result.execution_time !== null && result.execution_time !== undefined
            ? `${parseFloat(result.execution_time).toFixed(2)}s` : '-';

        const completedAt = result.completed_at
            ? new Date(result.completed_at).toLocaleString() : '-';

        return `
            <tr>
                <td>${result.id}</td>
                <td>${escapeHtml(result.task_name)}</td>
                <td>${escapeHtml(result.client_name)}</td>
                <td><code>${escapeHtml(result.subtask_name)}</code></td>
                <td>
                    <span class="status-badge ${statusClass}">
                        <i class="fas ${statusIcon}"></i>
                        ${result.status}
                    </span>
                </td>
                <td>${execTime}</td>
                <td>${completedAt}</td>
                <td>
                    <button class="btn btn-small btn-info" onclick="viewResultDetail(${result.id})"
                            title="View Details">
                        <i class="fas fa-eye"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// View detailed result
async function viewResultDetail(resultId) {
    try {
        const response = await apiGet(`/api/results/${resultId}`);
        const result = response.data;
        if (!result) {
            showNotification('Error', 'Result not found', 'error');
            return;
        }

        const modal = document.getElementById('resultDetailModal');
        const title = document.getElementById('resultDetailTitle');
        const body = document.getElementById('resultDetailBody');

        if (!modal || !title || !body) return;

        title.textContent = `Result: ${result.task_name} - ${result.subtask_name}`;

        // Parse result data if it's a JSON string
        let resultData = result.result;
        let resultHtml = '';
        if (resultData) {
            try {
                const parsed = JSON.parse(resultData);
                resultHtml = `<pre class="result-json">${escapeHtml(JSON.stringify(parsed, null, 2))}</pre>`;
            } catch (e) {
                // Not JSON, display as plain text
                resultHtml = `<pre class="result-text">${escapeHtml(resultData)}</pre>`;
            }
        } else {
            resultHtml = '<p class="text-muted">No result data available</p>';
        }

        const statusClass = result.status === 'completed' ? 'status-completed' :
                           result.status === 'failed' ? 'status-failed' : 'status-pending';

        body.innerHTML = `
            <div class="result-detail-grid">
                <div class="detail-row">
                    <strong>Task:</strong>
                    <span>${escapeHtml(result.task_name)} (ID: ${result.task_id})</span>
                </div>
                <div class="detail-row">
                    <strong>Client:</strong>
                    <span>${escapeHtml(result.client_name)}</span>
                </div>
                <div class="detail-row">
                    <strong>Subtask:</strong>
                    <span><code>${escapeHtml(result.subtask_name)}</code></span>
                </div>
                <div class="detail-row">
                    <strong>Status:</strong>
                    <span class="status-badge ${statusClass}">${result.status}</span>
                </div>
                <div class="detail-row">
                    <strong>Execution Time:</strong>
                    <span>${result.execution_time != null ? parseFloat(result.execution_time).toFixed(2) + 's' : '-'}</span>
                </div>
                <div class="detail-row">
                    <strong>Completed At:</strong>
                    <span>${result.completed_at ? new Date(result.completed_at).toLocaleString() : '-'}</span>
                </div>
                <div class="detail-row">
                    <strong>Cached At:</strong>
                    <span>${result.created_at ? new Date(result.created_at).toLocaleString() : '-'}</span>
                </div>
            </div>
            <div class="result-data-section">
                <h4>Result Data</h4>
                ${resultHtml}
            </div>
        `;

        modal.style.display = 'flex';

    } catch (error) {
        console.error('Failed to load result detail:', error);
        showNotification('Error', 'Failed to load result details', 'error');
    }
}

// Close result detail modal
function closeResultDetailModal() {
    const modal = document.getElementById('resultDetailModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Close modal on outside click
window.addEventListener('click', function(e) {
    const modal = document.getElementById('resultDetailModal');
    if (e.target === modal) {
        closeResultDetailModal();
    }
});

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}
