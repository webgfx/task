/**
 * Results page JavaScript - Cached task results viewer
 */

let allResults = [];
let clientsList = [];
let TASKsList = [];

// Initialize after page load
document.addEventListener('DOMContentLoaded', function() {
    initializeResultsPage();
});

async function initializeResultsPage() {
    await loadClients();
    await loadTASKs();
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

// Load task definitions for filter dropdown
async function loadTASKs() {
    try {
        const response = await apiGet('/api/tasks');
        TASKsList = response.data || [];
    } catch (error) {
        console.error('Failed to load tasks:', error);
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

    const TASKFilter = document.getElementById('TASKFilter');
    if (TASKFilter) {
        TASKFilter.innerHTML = '<option value="">All tasks</option>';
        // Extract unique Task names from results
        const uniqueTASKs = new Set();
        allResults.forEach(r => uniqueTASKs.add(r.task_name));
        // Also add from task definitions
        TASKsList.forEach(s => uniqueTASKs.add(s.name));

        uniqueTASKs.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            TASKFilter.appendChild(option);
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
    const TASKFilter = document.getElementById('TASKFilter');
    const statusFilter = document.getElementById('statusFilter');

    const clientValue = clientFilter ? clientFilter.value : '';
    const TASKValue = TASKFilter ? TASKFilter.value : '';
    const statusValue = statusFilter ? statusFilter.value : '';

    let filtered = allResults;

    if (clientValue) {
        filtered = filtered.filter(r => r.client_name === clientValue);
    }
    if (TASKValue) {
        filtered = filtered.filter(r => r.task_name === TASKValue);
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
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No results found</td></tr>';
        return;
    }

    tbody.innerHTML = results.map(result => {
        const statusLabel = result.status === 'completed' ? 'PASSED' : result.status.toUpperCase();

        const execTime = result.execution_time !== null && result.execution_time !== undefined
            ? `${parseFloat(result.execution_time).toFixed(2)}s` : '-';

        const completedAt = result.completed_at
            ? new Date(result.completed_at).toLocaleString() : '-';

        const resultFile = result.result_file || '';

        return `
            <tr>
                <td>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <input type="checkbox" class="result-checkbox" value="${result.id}" onclick="updateCompareButton()" style="width:18px; height:18px; cursor:pointer; accent-color:#6366f1;">
                        <span class="task-id-badge">#${result.task_id}</span>
                        <strong>${escapeHtml(result.task_name)}</strong>
                    </div>
                </td>
                <td>${escapeHtml(result.client_name)}</td>
                <td><span class="Task-name">${escapeHtml(result.task_name).replace(/_/g, '-')}</span></td>
                <td><span class="status-badge ${result.status}">${statusLabel}</span></td>
                <td><span class="execution-time">${execTime}</span></td>
                <td>${completedAt}</td>
                <td>
                    <button class="btn btn-small btn-primary" onclick="viewResultDetail(${result.id})"
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

        title.textContent = `Result: ${result.task_name} - ${result.task_name}`;

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
        const statusLabel = result.status === 'completed' ? 'PASSED' : result.status.toUpperCase();

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
                    <strong>Task:</strong>
                    <span><code>${escapeHtml(result.task_name)}</code></span>
                </div>
                <div class="detail-row">
                    <strong>Status:</strong>
                    <span class="status-badge ${statusClass}">${statusLabel}</span>
                </div>
                <div class="detail-row">
                    <strong>Execution Time:</strong>
                    <span>${result.execution_time != null ? parseFloat(result.execution_time).toFixed(2) + 's' : '-'}</span>
                </div>
                <div class="detail-row">
                    <strong>Finished At:</strong>
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
    const compModal = document.getElementById('comparisonModal');
    if (e.target === compModal) {
        closeComparisonModal();
    }
});

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

// ============================================================
// Results Comparison
// ============================================================

let comparisonCharts = [];

function selectAllResults() {
    const checkboxes = document.querySelectorAll('.result-checkbox');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => { cb.checked = !allChecked; });
    updateCompareButton();
}

function getSelectedResultIds() {
    return Array.from(document.querySelectorAll('.result-checkbox:checked'))
        .map(cb => parseInt(cb.value));
}

function updateCompareButton() {
    const ids = getSelectedResultIds();
    const btn = document.getElementById('compareBtn');
    const count = document.getElementById('selectedCount');
    if (btn) btn.disabled = ids.length < 1;
    if (count) count.textContent = ids.length;
}

function toggleSelectAll(masterCheckbox) {
    document.querySelectorAll('.result-checkbox').forEach(cb => {
        cb.checked = masterCheckbox.checked;
    });
    updateCompareButton();
}

async function compareSelected() {
    const ids = getSelectedResultIds();
    if (ids.length < 1) {
        showNotification('Warning', 'Select at least 1 result to view comparison charts', 'warning');
        return;
    }

    try {
        const response = await apiPost('/api/results/compare', { result_ids: ids });
        if (!response.success) {
            showNotification('Error', response.error || 'Comparison failed', 'error');
            return;
        }

        renderComparison(response.data);

    } catch (error) {
        console.error('Comparison failed:', error);
    }
}

function renderComparison(data) {
    // Destroy previous charts
    comparisonCharts.forEach(c => c.destroy());
    comparisonCharts = [];

    const modal = document.getElementById('comparisonModal');
    if (!modal) return;

    // Info section
    const info = document.getElementById('comparisonInfo');
    if (info) {
        info.innerHTML = `<p style="color:var(--c-text-secondary); font-size:.85rem;">Comparing <strong>${data.resultCount}</strong> result(s) &mdash; ${data.series.length} series</p>`;
    }

    const colors = [
        '#6366f1', '#ef4444', '#22c55e', '#f59e0b',
        '#8b5cf6', '#06b6d4', '#f97316', '#3b82f6',
        '#14b8a6', '#e11d48', '#0ea5e9', '#eab308',
    ];

    const plLabels = data.promptLengths.map(String);

    function buildDatasets(metric) {
        return data.series.map((s, i) => {
            const color = colors[i % colors.length];
            const d = plLabels.map(pl => {
                const pt = s.points.find(p => String(p.pl) === pl);
                return pt ? pt[metric] : null;
            });
            return {
                label: s.label,
                data: d,
                borderColor: color,
                backgroundColor: color + '22',
                pointBackgroundColor: color,
                pointRadius: 5,
                borderWidth: 2.5,
                tension: 0.3,
                fill: false,
            };
        });
    }

    const chartOpts = {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: { position: 'bottom', labels: { padding: 14, usePointStyle: true, pointStyle: 'circle', font: { size: 11 } } },
        },
        scales: {
            x: { grid: { color: '#e2e8f0' }, title: { display: true, text: 'Prompt Length' } },
            y: { grid: { color: '#e2e8f0' }, beginAtZero: true },
        },
    };

    // TTFT chart
    const ttftCtx = document.getElementById('ttftChart');
    if (ttftCtx) {
        comparisonCharts.push(new Chart(ttftCtx, {
            type: 'line',
            data: { labels: plLabels, datasets: buildDatasets('ttftMs') },
            options: { ...chartOpts, scales: { ...chartOpts.scales, y: { ...chartOpts.scales.y, title: { display: true, text: 'TTFT (ms)' } } } },
        }));
    }

    // Prefill TPS chart
    const plCtx = document.getElementById('prefillChart');
    if (plCtx) {
        comparisonCharts.push(new Chart(plCtx, {
            type: 'line',
            data: { labels: plLabels, datasets: buildDatasets('plTs') },
            options: { ...chartOpts, scales: { ...chartOpts.scales, y: { ...chartOpts.scales.y, title: { display: true, text: 'Prefill TPS (t/s)' } } } },
        }));
    }

    // Gen TPS chart
    const genCtx = document.getElementById('genTpsChart');
    if (genCtx) {
        comparisonCharts.push(new Chart(genCtx, {
            type: 'line',
            data: { labels: plLabels, datasets: buildDatasets('tgTs') },
            options: { ...chartOpts, scales: { ...chartOpts.scales, y: { ...chartOpts.scales.y, title: { display: true, text: 'Generation TPS (t/s)' } } } },
        }));
    }

    // Summary table
    const tableDiv = document.getElementById('comparisonTable');
    if (tableDiv) {
        let rows = '';
        for (const s of data.series) {
            for (const p of s.points) {
                rows += `<tr>
                    <td>${escapeHtml(s.shortLabel)}</td>
                    <td>${escapeHtml(s.clientName)}</td>
                    <td>${p.pl != null ? p.pl : '-'}</td>
                    <td>${p.ttftMs != null ? p.ttftMs.toFixed(2) : '-'}</td>
                    <td>${p.tgTs != null ? p.tgTs.toFixed(2) : '-'}</td>
                    <td>${p.plTs != null ? p.plTs.toFixed(2) : '-'}</td>
                    <td>${p.e2eMs != null ? Math.round(p.e2eMs) : '-'}</td>
                </tr>`;
            }
        }
        tableDiv.innerHTML = `
            <h4 style="margin-bottom:12px; font-size:.9rem;">Detailed Results</h4>
            <div style="overflow-x:auto;">
            <table class="task-table" style="font-size:.82rem;">
                <thead><tr>
                    <th>Configuration</th><th>Client</th><th>Prompt Len</th>
                    <th>TTFT (ms)</th><th>TPS (t/s)</th><th>PL (t/s)</th><th>E2E (ms)</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>
            </div>`;
    }

    modal.style.display = 'flex';
}

function closeComparisonModal() {
    const modal = document.getElementById('comparisonModal');
    if (modal) modal.style.display = 'none';
}
