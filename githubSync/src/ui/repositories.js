// Repository Management JavaScript

let repositories = [];

document.addEventListener('DOMContentLoaded', function() {
    loadRepositories();
});

async function loadRepositories() {
    try {
        const response = await fetch('/api/repositories');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        // Handle the API response format which includes a "repositories" key
        repositories = data.repositories || data || [];
        renderRepositories();
    } catch (error) {
        console.error('Error loading repositories:', error);
        showError('Failed to load repositories. Please check if the sync service is running.');
    }
}

function renderRepositories() {
    const container = document.getElementById('repository-list');
    
    if (repositories.length === 0) {
        container.innerHTML = `
            <div class="col-12">
                <div class="text-center p-5">
                    <i class="bi bi-folder-x text-muted" style="font-size: 4rem;"></i>
                    <h4 class="mt-3 text-muted">No repositories configured</h4>
                    <p class="text-muted">Add your first repository to start syncing GitHub issues and pull requests.</p>
                    <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addRepoModal">
                        <i class="bi bi-plus-circle"></i> Add Repository
                    </button>
                </div>
            </div>
        `;
        return;
    }

    const repoCards = repositories.map(repo => {
        const priorityClass = `priority-${repo.priority}`;
        const statusIcon = repo.is_active ? 'check-circle-fill text-success' : 'x-circle-fill text-danger';
        const status = repo.is_active ? 'active' : 'inactive';
        
        // Parse owner/name from repo field (format: "owner/name")
        const [owner, name] = repo.repo.split('/');
        
        return `
            <div class="col-md-6 col-lg-4 mb-4">
                <div class="card repo-card h-100 ${priorityClass}">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-3">
                            <h5 class="card-title mb-0">
                                <i class="bi bi-github"></i> ${repo.repo}
                            </h5>
                            <span class="badge status-badge ${status === 'active' ? 'bg-success' : 'bg-danger'}">
                                <i class="bi bi-${statusIcon}"></i> ${status}
                            </span>
                        </div>
                        
                        <div class="mb-3">
                            <small class="text-muted">Display Name: </small>
                            <div class="fw-bold">${repo.display_name}</div>
                        </div>
                        
                        <div class="mb-3">
                            <small class="text-muted">Category: </small>
                            <span class="badge bg-info">${repo.main_category}</span>
                            <small class="text-muted ms-2">Priority: </small>
                            <span class="badge bg-secondary">${repo.priority}</span>
                        </div>
                        
                        <div class="row text-center mb-3">
                            <div class="col-6">
                                <div class="text-primary">
                                    <i class="bi bi-exclamation-circle"></i>
                                </div>
                                <small class="text-muted">Issues</small>
                                <div class="fw-bold">${repo.issue_count || '-'}</div>
                            </div>
                            <div class="col-6">
                                <div class="text-success">
                                    <i class="bi bi-git-pull-request"></i>
                                </div>
                                <small class="text-muted">PRs</small>
                                <div class="fw-bold">${repo.pr_count || '-'}</div>
                            </div>
                        </div>
                        
                        <div class="d-flex gap-2">
                            <button class="btn btn-outline-primary btn-sm flex-fill" onclick="syncRepository('${owner}', '${name}')">
                                <i class="bi bi-arrow-clockwise"></i> Sync
                            </button>
                            <button class="btn btn-outline-danger btn-sm" onclick="removeRepository('${repo.repo}')">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = repoCards;
}

async function addRepository() {
    const owner = document.getElementById('repoOwner').value.trim();
    const name = document.getElementById('repoName').value.trim();
    const priority = document.getElementById('repoPriority').value;

    if (!owner || !name) {
        alert('Please enter both owner and repository name.');
        return;
    }

    try {
        const response = await fetch('/api/repositories', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ owner, name, priority })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Close modal and refresh
        const modal = bootstrap.Modal.getInstance(document.getElementById('addRepoModal'));
        modal.hide();
        document.getElementById('add-repo-form').reset();
        loadRepositories();
        
        showSuccess(`Repository ${owner}/${name} added successfully!`);
    } catch (error) {
        console.error('Error adding repository:', error);
        showError('Failed to add repository. Please try again.');
    }
}

async function removeRepository(repoPath) {
    if (!confirm(`Are you sure you want to remove ${repoPath}?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/repositories/${encodeURIComponent(repoPath)}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        loadRepositories();
        showSuccess(`Repository ${repoPath} removed successfully!`);
    } catch (error) {
        console.error('Error removing repository:', error);
        showError('Failed to remove repository. Please try again.');
    }
}

async function syncRepository(owner, name) {
    try {
        showInfo(`Starting sync for ${owner}/${name}...`);
        
        const response = await fetch('/api/sync/single', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ owner, name })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        showSuccess(`Sync completed for ${owner}/${name}! ${result.message || ''}`);
        
        // Refresh repository data
        setTimeout(loadRepositories, 1000);
    } catch (error) {
        console.error('Error syncing repository:', error);
        showError(`Failed to sync ${owner}/${name}. Please try again.`);
    }
}

function showSuccess(message) {
    showAlert(message, 'success');
}

function showError(message) {
    showAlert(message, 'danger');
}

function showInfo(message) {
    showAlert(message, 'info');
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