// Repository Management JavaScript

let repositories = [];

const PRIORITY_CONFIG = {
    1: { label: 'High', className: 'priority-high', badgeClass: 'bg-danger' },
    2: { label: 'Medium', className: 'priority-medium', badgeClass: 'bg-warning text-dark' },
    3: { label: 'Low', className: 'priority-low', badgeClass: 'bg-success' }
};

const LANGUAGE_BADGE_CLASS = {
    'DotNet': 'bg-primary',
    'Node.js': 'bg-success',
    'Web/Browser': 'bg-info text-dark',
    'JavaScript': 'bg-warning text-dark',
    'Python': 'bg-secondary',
    'Java': 'bg-danger',
    'Other': 'bg-dark'
};

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

    const sortedRepos = repositories
        .slice()
        .sort((a, b) => {
            const priorityA = Number(a.priority) || 99;
            const priorityB = Number(b.priority) || 99;
            if (priorityA !== priorityB) {
                return priorityA - priorityB;
            }
            return (a.repo || '').localeCompare(b.repo || '');
        });

    const repoCards = sortedRepos.map(repo => {
        const isActive = repo.is_active === 1 || repo.is_active === true;
        const statusIcon = isActive ? 'check-circle-fill text-success' : 'x-circle-fill text-danger';
        const status = isActive ? 'Active' : 'Inactive';

        const priorityValue = Number(repo.priority);
        const priorityInfo = PRIORITY_CONFIG[priorityValue] || {
            label: Number.isFinite(priorityValue) ? `Custom (${priorityValue})` : 'Unspecified',
            className: 'priority-custom',
            badgeClass: 'bg-secondary'
        };

        const languageKey = repo.language_group || repo.classification || 'Other';
        const languageLabel = languageKey;
        const languageBadge = LANGUAGE_BADGE_CLASS[languageKey] || LANGUAGE_BADGE_CLASS.Other;

        const issueTotal = Number.isFinite(Number(repo.issue_count)) ? Number(repo.issue_count) : '-';
        const prTotal = Number.isFinite(Number(repo.pr_count)) ? Number(repo.pr_count) : '-';

        const updatedAt = formatDate(repo.updated_at);
        const createdAt = formatDate(repo.created_at);

        return `
            <div class="col-md-6 col-lg-4 mb-4">
                <div class="card repo-card h-100 ${priorityInfo.className}">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-3">
                            <h5 class="card-title mb-0">
                                <i class="bi bi-github"></i> ${repo.repo}
                            </h5>
                            <span class="badge status-badge ${isActive ? 'bg-success' : 'bg-danger'}">
                                <i class="bi bi-${statusIcon}"></i> ${status}
                            </span>
                        </div>
                        
                        <div class="mb-3">
                            <small class="text-muted">Display Name: </small>
                            <div class="fw-bold">${repo.display_name}</div>
                        </div>
                        
                        <div class="mb-3">
                            <small class="text-muted">Category: </small>
                            <span class="badge bg-info text-dark">${repo.main_category}</span>
                        </div>

                        <div class="mb-3 d-flex flex-wrap gap-2 align-items-center">
                            <span class="badge ${languageBadge}">
                                <i class="bi bi-translate"></i> ${languageLabel}
                            </span>
                            <span class="badge ${priorityInfo.badgeClass}">
                                <i class="bi bi-bar-chart"></i> Priority: ${priorityInfo.label}
                            </span>
                            <span class="badge bg-light text-muted border">
                                Classification: ${repo.classification}
                            </span>
                        </div>
                        
                        <div class="row text-center mb-3">
                            <div class="col-6">
                                <div class="text-primary">
                                    <i class="bi bi-exclamation-circle"></i>
                                </div>
                                <small class="text-muted">Issues</small>
                                <div class="fw-bold">${issueTotal}</div>
                            </div>
                            <div class="col-6">
                                <div class="text-success">
                                    <i class="bi bi-git-pull-request"></i>
                                </div>
                                <small class="text-muted">PRs</small>
                                <div class="fw-bold">${prTotal}</div>
                            </div>
                        </div>

                        <div class="small text-muted mb-3">
                            <div>Created: ${createdAt}</div>
                            <div>Last Updated: ${updatedAt}</div>
                        </div>
                        
                        <div class="d-flex gap-2">
                            <button class="btn btn-outline-primary btn-sm flex-fill" onclick="syncRepository('${repo.repo}')">
                                <i class="bi bi-arrow-clockwise"></i> Sync All
                            </button>
                            <button class="btn btn-outline-secondary btn-sm" onclick="syncRepositoryIssues('${repo.repo}')">
                                <i class="bi bi-exclamation-circle"></i>
                            </button>
                            <button class="btn btn-outline-success btn-sm" onclick="syncRepositoryPullRequests('${repo.repo}')">
                                <i class="bi bi-git-pull-request"></i>
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
    const displayName = document.getElementById('repoDisplayName').value.trim();
    const mainCategory = document.getElementById('repoCategory').value.trim();
    const classification = document.getElementById('repoClassification').value;
    const priorityValue = parseInt(document.getElementById('repoPriority').value, 10);
    const isActive = document.getElementById('repoActive').checked;

    if (!owner || !name || !mainCategory) {
        alert('Please enter repository owner, name, and main category.');
        return;
    }

    try {
        const repoIdentifier = `${owner}/${name}`;
        const payload = {
            repo: repoIdentifier,
            display_name: displayName || name,
            main_category: mainCategory,
            classification: classification || 'Other',
            priority: Number.isFinite(priorityValue) ? priorityValue : 3,
            is_active: isActive
        };

        const response = await fetch('/api/repositories', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Close modal and refresh
        const modal = bootstrap.Modal.getInstance(document.getElementById('addRepoModal'));
        modal.hide();
        document.getElementById('add-repo-form').reset();
        loadRepositories();
        
        showSuccess(`Repository ${repoIdentifier} added successfully!`);
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

async function syncRepository(repoPath) {
    try {
        showInfo(`Starting full sync for ${repoPath}...`);

        const response = await fetch(`/api/sync/repositories/${encodeURIComponent(repoPath)}`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        showSuccess(`Sync completed for ${repoPath}!`);
        
        // Refresh repository data
        setTimeout(loadRepositories, 1000);
    } catch (error) {
        console.error('Error syncing repository:', error);
        showError(`Failed to sync ${repoPath}. Please try again.`);
    }
}

async function syncRepositoryIssues(repoPath) {
    await syncRepositoryByType(repoPath, 'issues');
}

async function syncRepositoryPullRequests(repoPath) {
    await syncRepositoryByType(repoPath, 'prs');
}

async function syncRepositoryByType(repoPath, type) {
    const endpoint = type === 'issues'
        ? `/api/sync/repositories/${encodeURIComponent(repoPath)}/issues`
        : `/api/sync/repositories/${encodeURIComponent(repoPath)}/prs`;

    try {
        showInfo(`Syncing ${type.toUpperCase()} for ${repoPath}...`);

        const response = await fetch(endpoint, { method: 'POST' });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        if (result.success) {
            showSuccess(`${type.toUpperCase()} sync completed for ${repoPath}.`);
        } else {
            showError(`Sync completed with issues for ${repoPath}: ${result.error || 'Unknown error'}`);
        }

        setTimeout(loadRepositories, 1000);
    } catch (error) {
        console.error(`Error syncing ${type} for repository:`, error);
        showError(`Failed to sync ${type} for ${repoPath}. Please try again.`);
    }
}

function formatDate(value) {
    if (!value) {
        return '—';
    }

    try {
        const date = new Date(value.replace(' ', 'T'));
        if (Number.isNaN(date.getTime())) {
            return value;
        }
        return date.toLocaleString();
    } catch (error) {
        return value;
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