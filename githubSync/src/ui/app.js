// Main Dashboard JavaScript

document.addEventListener('DOMContentLoaded', function() {
    loadDashboardData();
    // Refresh data every 30 seconds
    setInterval(loadDashboardData, 30000);
});

async function loadDashboardData() {
    await Promise.all([
        loadStatistics(),
        loadSyncActivity(),
        loadSchedulerStatus()
    ]);
}

async function loadStatistics() {
    try {
        const response = await fetch('/api/statistics');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const stats = await response.json();
        
        // Update the summary cards
        document.getElementById('total-issues').textContent = formatNumber(stats.total_issues || 0);
        document.getElementById('total-prs').textContent = formatNumber(stats.total_prs || 0);
        document.getElementById('total-repos').textContent = stats.total_repositories || 0;
        
        // Calculate and display data age
        if (stats.last_sync) {
            // Just show the raw timestamp with UTC label
            document.getElementById('data-age').textContent = `${stats.last_sync} UTC`;
            document.getElementById('data-age').className = 'mb-1 text-info';
        } else {
            document.getElementById('data-age').textContent = 'No data';
            document.getElementById('data-age').className = 'mb-1 text-muted';
        }
    } catch (error) {
        console.error('Error loading statistics:', error);
        // Set default values on error
        document.getElementById('total-issues').textContent = '-';
        document.getElementById('total-prs').textContent = '-';
        document.getElementById('total-repos').textContent = '-';
        document.getElementById('data-age').textContent = 'Error';
    }
}

async function loadSyncActivity() {
    try {
        const response = await fetch('/api/sync/history?limit=50');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        renderSyncActivity(data.sync_history || []);
    } catch (error) {
        console.error('Error loading sync activity:', error);
        renderSyncActivityError();
    }
}

function renderSyncActivity(syncHistory) {
    const container = document.getElementById('sync-activity-container');
    
    if (!syncHistory || syncHistory.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="bi bi-clock-history" style="font-size: 3rem;"></i>
                <h5 class="mt-3">No sync activity found</h5>
                <p>No recent synchronization data available. Click "Trigger Full Sync" to start syncing repositories.</p>
            </div>
        `;
        return;
    }

    // Group sync history by sync session
    const allSessions = groupSyncHistoryBySessions(syncHistory);
    
    if (allSessions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="bi bi-exclamation-triangle" style="font-size: 3rem;"></i>
                <h5 class="mt-3">No sync sessions found</h5>
                <p>Unable to organize sync data into sessions.</p>
            </div>
        `;
        return;
    }

    // Prioritize sessions that have successful syncs with data
    const sessionsWithData = allSessions.filter(session => 
        session.items.some(item => item.status === 'success' && (item.issues_new > 0 || item.prs_new > 0))
    );
    
    // Show sessions with data first, then recent sessions (up to 5 total)
    const sessionsToShow = [
        ...sessionsWithData.slice(0, 3),
        ...allSessions.filter(s => !sessionsWithData.includes(s)).slice(0, 2)
    ].slice(0, 5);

    const syncActivityHtml = sessionsToShow.map(session => {
        const totalIssuesNew = session.items.reduce((sum, item) => sum + (item.issues_new || 0), 0);
        const totalIssuesUpdated = session.items.reduce((sum, item) => sum + (item.issues_updated || 0), 0);
        const totalPRsNew = session.items.reduce((sum, item) => sum + (item.prs_new || 0), 0);
        const totalPRsUpdated = session.items.reduce((sum, item) => sum + (item.prs_updated || 0), 0);
        const totalItems = totalIssuesNew + totalIssuesUpdated + totalPRsNew + totalPRsUpdated;
        
        // Group by repository to get unique repositories and their combined stats
        const repoGroups = {};
        session.items.forEach(item => {
            if (!repoGroups[item.repository]) {
                repoGroups[item.repository] = {
                    repository: item.repository,
                    issues_total: 0,
                    prs_total: 0,
                    has_error: false,
                    error_message: null
                };
            }
            
            repoGroups[item.repository].issues_total += (item.issues_new || 0) + (item.issues_updated || 0);
            repoGroups[item.repository].prs_total += (item.prs_new || 0) + (item.prs_updated || 0);
            
            if (item.status !== 'success') {
                repoGroups[item.repository].has_error = true;
                repoGroups[item.repository].error_message = item.error_message;
            }
        });
        
        const uniqueRepositories = Object.keys(repoGroups).length;
        
        const repoDetails = Object.values(repoGroups).map(repo => {
            return `
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="repo-name">${repo.repository}</span>
                    <div class="sync-stats">
                        <span class="stat-item issues-stat">
                            <i class="bi bi-exclamation-circle"></i>
                            <span class="stat-number">${repo.issues_total}</span> issues
                        </span>
                        <span class="stat-item prs-stat">
                            <i class="bi bi-git-pull-request"></i>
                            <span class="stat-number">${repo.prs_total}</span> PRs
                        </span>
                        ${repo.has_error ? `<span class="badge bg-warning" title="${repo.error_message || 'Unknown error'}">${repo.error_message ? (repo.error_message.length > 50 ? repo.error_message.substring(0, 47) + '...' : repo.error_message) : 'Error'}</span>` : ''}
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="sync-item">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <h6 class="mb-0">
                        <i class="bi bi-arrow-clockwise text-primary"></i>
                        Sync Session - ${uniqueRepositories} repositories
                    </h6>
                    <span class="sync-time">${formatRelativeTime(session.sync_date)}</span>
                </div>
                
                <div class="sync-stats mb-3">
                    <div class="stat-item">
                        <i class="bi bi-bar-chart text-info"></i>
                        <span class="stat-number">${totalItems}</span> total items
                    </div>
                    <div class="stat-item issues-stat">
                        <i class="bi bi-exclamation-circle"></i>
                        <span class="stat-number">${totalIssuesNew + totalIssuesUpdated}</span> issues
                        <small class="text-muted">(${totalIssuesNew} new, ${totalIssuesUpdated} updated)</small>
                    </div>
                    <div class="stat-item prs-stat">
                        <i class="bi bi-git-pull-request"></i>
                        <span class="stat-number">${totalPRsNew + totalPRsUpdated}</span> PRs
                        <small class="text-muted">(${totalPRsNew} new, ${totalPRsUpdated} updated)</small>
                    </div>
                </div>
                
                <div class="repositories-details">
                    ${repoDetails}
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = syncActivityHtml;
}

function renderSyncActivityError() {
    const container = document.getElementById('sync-activity-container');
    container.innerHTML = `
        <div class="empty-state">
            <i class="bi bi-exclamation-triangle text-warning" style="font-size: 3rem;"></i>
            <h5 class="mt-3">Unable to load sync activity</h5>
            <p>There was an error loading the sync activity data. Please check if the sync service is running.</p>
            <button class="btn btn-outline-primary" onclick="loadSyncActivity()">
                <i class="bi bi-arrow-clockwise"></i> Retry
            </button>
        </div>
    `;
}

function groupSyncHistoryBySessions(syncHistory) {
    // Group by sync_session_id and sync_date
    const sessions = {};
    
    syncHistory.forEach(item => {
        const sessionKey = item.sync_session_id || item.sync_date;
        if (!sessions[sessionKey]) {
            sessions[sessionKey] = {
                sync_session_id: sessionKey,
                sync_date: item.sync_date,
                items: []
            };
        }
        
        sessions[sessionKey].items.push(item);
    });
    
    // Convert to array and sort by date (newest first)
    return Object.values(sessions).sort((a, b) => new Date(b.sync_date) - new Date(a.sync_date));
}

async function triggerFullSync() {
    const button = event.target;
    const originalText = button.innerHTML;
    
    // Update button to show loading state
    button.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Syncing...';
    button.disabled = true;
    
    try {
        const response = await fetch('/api/sync/full', {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        showSuccess('Full sync started successfully! The dashboard will update automatically.');
        
        // Refresh data after a short delay
        setTimeout(loadDashboardData, 2000);
        
    } catch (error) {
        console.error('Error triggering sync:', error);
        showError('Failed to start sync. Please check if the sync service is running.');
    } finally {
        // Restore button
        button.innerHTML = originalText;
        button.disabled = false;
    }
}

function calculateDataAge(lastSyncTime) {
    try {
        const now = new Date();
        let lastSync;
        
        if (lastSyncTime.includes(' ') && !lastSyncTime.includes('T')) {
            // Format: "2025-10-07 22:46:59" - this is local time from database
            // Parse it explicitly as local time
            const parts = lastSyncTime.split(' ');
            const datePart = parts[0];
            const timePart = parts[1];
            lastSync = new Date(`${datePart}T${timePart}`);
        } else if (lastSyncTime.includes('+') || lastSyncTime.endsWith('Z')) {
            // Format: "2025-10-07T16:46:59+00:00" or "2025-10-07T16:46:59Z" - UTC timestamp
            lastSync = new Date(lastSyncTime);
        } else {
            // Fallback for other formats
            lastSync = new Date(lastSyncTime);
        }
        
        // Check if date parsing was successful
        if (isNaN(lastSync.getTime())) {
            console.error('Invalid date format:', lastSyncTime);
            return { text: 'Unknown', class: 'text-muted' };
        }
        
        const diffMs = now - lastSync;
        const diffMinutes = Math.floor(diffMs / (1000 * 60));
        
        // Debug logging to troubleshoot
        console.log(`Data age calculation: now=${now.toISOString()}, lastSync=${lastSync.toISOString()}, diffMs=${diffMs}, diffMinutes=${diffMinutes}`);
        
        if (diffMinutes < 1) {
            return { text: 'Just now', class: 'text-success' };
        } else if (diffMinutes < 60) {
            return { text: `${diffMinutes}m ago`, class: 'text-success' };
        } else if (diffMinutes < 24 * 60) {
            const hours = Math.floor(diffMinutes / 60);
            return { text: `${hours}h ago`, class: hours < 6 ? 'text-warning' : 'text-danger' };
        } else {
            const days = Math.floor(diffMinutes / (24 * 60));
            return { text: `${days}d ago`, class: 'text-danger' };
        }
    } catch (error) {
        console.error('Error calculating data age:', error, 'for timestamp:', lastSyncTime);
        return { text: 'Error', class: 'text-muted' };
    }
}

function formatRelativeTime(timestamp) {
    // Just return the raw timestamp with UTC label
    return `${timestamp} UTC`;
}

function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

function showSuccess(message) {
    showAlert(message, 'success');
}

function showError(message) {
    showAlert(message, 'danger');
}

function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Automatic Sync Functions
async function loadSchedulerStatus() {
    try {
        const response = await fetch('/api/scheduler/status');
        const data = await response.json();
        updateSchedulerUI(data);
    } catch (error) {
        console.error('Error loading scheduler status:', error);
        updateSchedulerUI({
            enabled: false,
            running: false,
            error: 'Failed to load status'
        });
    }
}

function updateSchedulerUI(status) {
    const statusBadge = document.getElementById('auto-sync-status-badge');
    const statusText = document.getElementById('auto-sync-status-text');
    const nextRunSpan = document.getElementById('auto-sync-next-run');
    const enableBtn = document.getElementById('enable-auto-sync-btn');
    const disableBtn = document.getElementById('disable-auto-sync-btn');

    if (status.enabled && status.running) {
        statusBadge.className = 'badge bg-success me-2';
        statusBadge.textContent = 'Enabled';
        statusText.textContent = 'Automatic sync is running';
        enableBtn.disabled = true;
        disableBtn.disabled = false;
        
        if (status.next_run) {
            const nextRun = new Date(status.next_run);
            nextRunSpan.textContent = nextRun.toLocaleString();
        } else {
            nextRunSpan.textContent = 'Calculating...';
        }
    } else {
        statusBadge.className = 'badge bg-secondary me-2';
        statusBadge.textContent = 'Disabled';
        statusText.textContent = status.error || 'Automatic sync is disabled';
        enableBtn.disabled = false;
        disableBtn.disabled = true;
        nextRunSpan.textContent = '-';
    }
}

function enableAutoSync() {
    fetch('/api/scheduler/enable', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('Automatic sync enabled successfully!', 'success');
                setTimeout(loadSchedulerStatus, 1000); // Reload status after 1 second
            } else {
                showAlert('Failed to enable automatic sync: ' + (data.error || 'Unknown error'), 'danger');
            }
        })
        .catch(error => {
            console.error('Error enabling auto sync:', error);
            showAlert('Error enabling automatic sync', 'danger');
        });
}

function disableAutoSync() {
    fetch('/api/scheduler/disable', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('Automatic sync disabled successfully!', 'warning');
                setTimeout(loadSchedulerStatus, 1000); // Reload status after 1 second
            } else {
                showAlert('Failed to disable automatic sync: ' + (data.error || 'Unknown error'), 'danger');
            }
        })
        .catch(error => {
            console.error('Error disabling auto sync:', error);
            showAlert('Error disabling automatic sync', 'danger');
        });
}