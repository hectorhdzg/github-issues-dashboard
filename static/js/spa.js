// SPA Controller for GitHub Issues Dashboard
// Handles all client-side state management, routing, and data loading

class DashboardSPA {
    constructor() {
        this.state = {
            dataType: 'issues',
            showState: 'open',
            selectedRepo: '',
            repositories: [], // Repos with data
            allRepositories: [], // All repos including those with 0 records
            sdkCounts: {},
            syncStats: {},
            isLoading: false,
            cache: new Map()
        };
        
        this.isInitializing = false; // Flag to prevent URL updates during initialization
        
        this.init();
    }
    
    // Map repository name to SDK type (matches backend logic)
    getSdkType(repoName) {
        const repoLower = repoName.toLowerCase();
        
        // Browser JavaScript repositories (client-side)
        if (repoLower.includes('applicationinsights-js') && !repoLower.includes('node.js')) {
            return 'browser';
        }
        
        // Node.js repositories (server-side)
        else if (repoLower.includes('azure-sdk-for-js') ||
                 repoLower.includes('applicationinsights-node.js') ||
                 repoLower.includes('opentelemetry-js-contrib') ||
                 (repoLower.includes('opentelemetry-js') && !repoLower.includes('contrib'))) {
            return 'nodejs';
        }
        
        // Python repositories
        else if (repoLower.includes('azure-sdk-for-python') ||
                 repoLower.includes('opentelemetry-python')) {
            return 'python';
        }
        
        // .NET repositories  
        else if (repoLower.includes('applicationinsights-dotnet') ||
                 repoLower.includes('opentelemetry-dotnet')) {
            return 'dotnet';
        }
        
        // Java repositories
        else if (repoLower.includes('applicationinsights-java') ||
                 repoLower.includes('opentelemetry-java')) {
            return 'java';
        }
        
        else {
            return 'other';
        }
    }
    
    // Get display name from repository name
    getDisplayName(repoName) {
        return repoName.split('/').pop(); // Get the part after the last slash
    }
    
    init() {
        // Initialize the SPA
        this.setupEventListeners();
        this.setupRouter();
        this.loadInitialState();
        this.applyInitialState(); // Apply the state using the same functions as menu buttons
        // Note: applyInitialState will trigger data loading through setDataType/setShowState calls
    }
    
    setupEventListeners() {
        // Data type toggle buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('.btn-toggle-data-type')) {
                const dataType = e.target.id === 'issues-toggle' ? 'issues' : 'prs';
                this.setDataType(dataType);
            }
        });
        
        // Repository navigation
        document.addEventListener('click', (e) => {
            if (e.target.matches('.nav-link[data-repo]')) {
                e.preventDefault();
                const repo = e.target.getAttribute('data-repo');
                this.setSelectedRepo(repo);
            }
        });
        
        // State filter buttons (when they're added dynamically)
        document.addEventListener('click', (e) => {
            if (e.target.matches('.state-filter-btn')) {
                e.preventDefault();
                const state = e.target.getAttribute('data-state');
                this.setShowState(state);
            }
        });
        
        // Clear repository selection
        document.addEventListener('click', (e) => {
            if (e.target.matches('.clear-repo-btn')) {
                e.preventDefault();
                this.setSelectedRepo('');
            }
        });
        
        // Dropdown menu item clicks (for repository selection)
        document.addEventListener('click', (e) => {
            // Handle dropdown items with onclick handlers
            if (e.target.matches('.dropdown-item[onclick*="selectRepository"]')) {
                e.preventDefault();
                console.log('Dropdown item clicked via onclick handler:', e.target);
                // Extract repository name from onclick attribute
                const onclickAttr = e.target.getAttribute('onclick');
                const match = onclickAttr.match(/selectRepository\('([^']+)'\)/);
                if (match) {
                    const repoName = match[1];
                    console.log('Selecting repository from dropdown:', repoName);
                    this.selectRepository(repoName);
                }
                return false;
            }
            
            // Also handle dropdown items without onclick (fallback)
            if (e.target.matches('.dropdown-item') && e.target.textContent.trim() !== '') {
                const dropdownMenu = e.target.closest('.dropdown-menu');
                if (dropdownMenu && dropdownMenu.id.includes('-dropdown-menu')) {
                    console.log('Dropdown item clicked (fallback):', e.target.textContent);
                    e.preventDefault();
                    // This is a fallback - the onclick handler should handle it
                }
            }
        });
        
        // Browser back/forward buttons
        window.addEventListener('popstate', (e) => {
            this.handlePopState(e);
        });
    }
    
    setupRouter() {
        // Setup client-side routing without page refresh
        // Don't call updateURLFromState() here as it will overwrite URL parameters
    }
    
    loadInitialState() {
        // Load initial state from URL parameters and apply them using the same
        // functions that menu buttons use to ensure consistency
        const urlParams = new URLSearchParams(window.location.search);
        
        const dataType = urlParams.get('type') || 'issues';
        const showState = urlParams.get('state') || 'open';
        const selectedRepo = urlParams.get('repo') || '';
        
        // Validate and set data type using the same function as menu buttons
        if (['issues', 'prs'].includes(dataType)) {
            this.state.dataType = dataType; // Set directly since setDataType would reload data
        } else {
            this.state.dataType = 'issues';
        }
        
        // Validate and set show state using the same function as menu buttons  
        if (['open', 'closed', 'all'].includes(showState)) {
            this.state.showState = showState; // Set directly since setShowState would reload data
        } else {
            this.state.showState = 'open';
        }
        
        // Set selected repo using the same function as menu buttons
        if (selectedRepo) {
            this.state.selectedRepo = selectedRepo; // Set directly since setSelectedRepo would update URL
        }
        
        console.log('Initial state loaded from URL:', {
            dataType: this.state.dataType,
            showState: this.state.showState,
            selectedRepo: this.state.selectedRepo
        });
    }
    
    applyInitialState() {
        // Apply the initial state loaded from URL using the same functions
        // that menu buttons use to ensure complete consistency
        console.log('Applying initial state using menu button functions:', this.state);
        
        // Temporarily disable URL updates during initial state application
        this.isInitializing = true;
        
        // Apply data type using the same function as data type buttons
        this.setDataType(this.state.dataType);
        
        // Apply show state using the same function as state buttons  
        this.setShowState(this.state.showState);
        
        // Apply repository selection using the same function as dropdown
        if (this.state.selectedRepo) {
            this.selectRepository(this.state.selectedRepo);
        }
        
        // Re-enable URL updates
        this.isInitializing = false;
        
        // Force data load if no data was loaded during state application
        if (!this.state.repositories || this.state.repositories.length === 0) {
            console.log('Forcing initial data load...');
            this.loadDashboardData();
        }
    }
    
    async loadDashboardData() {
        this.setLoading(true);
        
        try {
            const cacheKey = `${this.state.dataType}-${this.state.showState}`;
            
            // Check cache first
            if (this.state.cache.has(cacheKey)) {
                const cachedData = this.state.cache.get(cacheKey);
                this.updateUIFromData(cachedData);
                this.setLoading(false);
                return;
            }
            
            // Fetch fresh data
            const response = await fetch(`/api/dashboard/data?type=${this.state.dataType}&state=${this.state.showState}`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                if (response.status === 401 || response.status === 403) {
                    // Authentication removed - no redirect needed
                    throw new Error('Access denied');
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Handle API errors
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Cache the data
            this.state.cache.set(cacheKey, data);
            
            // Update UI
            this.updateUIFromData(data);
            
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError(`Failed to load dashboard data: ${error.message}`);
        } finally {
            this.setLoading(false);
        }
    }
    
    updateUIFromData(data) {
        // Process repository data from backend format to frontend format
        const processedRepos = this.processRepositoryData(data);
        
        // Update state
        this.state.repositories = processedRepos; // Processed repo objects with data
        this.state.allRepositories = data.all_repositories || []; // Raw repo names (for navigation)
        this.state.sdkCounts = data.sdk_counts;
        this.state.syncStats = data.sync_stats;
        
        // Update data type toggle
        this.updateDataTypeToggle();
        
        // Update intro page stats
        this.updateIntroStats();
        
        // Update repository sections
        this.updateRepositorySections();
        
        // Update navigation
        this.updateNavigation();
        
        // Show/hide appropriate sections
        this.updateVisibility();
    }
    
    processRepositoryData(data) {
        // Use new API structure with metadata
        const repositories = data.repositories || [];
        const repositoriesMetadata = data.repositories_metadata || [];
        const items = data.data || [];
        
        // Create metadata lookup for faster access
        const metadataLookup = {};
        repositoriesMetadata.forEach(repoMeta => {
            metadataLookup[repoMeta.repo] = repoMeta;
        });
        
        // Group items by repository
        const itemsByRepo = {};
        items.forEach(item => {
            const repoName = item.repository;
            if (!itemsByRepo[repoName]) {
                itemsByRepo[repoName] = [];
            }
            itemsByRepo[repoName].push(item);
        });
        
        // Create repository objects with processed data using metadata
        return repositories.map(repoName => {
            const repoItems = itemsByRepo[repoName] || [];
            const metadata = metadataLookup[repoName];
            
            // Use metadata if available, otherwise fallback to old logic
            const displayName = metadata ? metadata.display_name : this.getDisplayName(repoName);
            const mainCategory = metadata ? metadata.main_category : this.getSdkType(repoName);
            const classification = metadata ? metadata.classification : 'other';
            const priority = metadata ? metadata.priority : 999;
            
            return {
                id: repoName.replace(/[^a-zA-Z0-9]/g, '-'), // Safe ID for HTML
                name: repoName,
                display_name: displayName,
                sdk_type: mainCategory, // Using main_category as SDK type for backwards compatibility
                main_category: mainCategory,
                classification: classification,
                priority: priority,
                count: repoItems.length,
                items: repoItems
            };
        });
    }
    
    updateDataTypeToggle() {
        const issuesToggle = document.getElementById('issues-toggle');
        const prsToggle = document.getElementById('prs-toggle');
        
        if (issuesToggle && prsToggle) {
            // Update active states
            if (this.state.dataType === 'issues') {
                issuesToggle.className = 'btn btn-toggle-data-type btn-primary active';
                prsToggle.className = 'btn btn-toggle-data-type btn-outline-primary';
            } else {
                issuesToggle.className = 'btn btn-toggle-data-type btn-outline-primary';
                prsToggle.className = 'btn btn-toggle-data-type btn-primary active';
            }
        }
    }
    
    updateIntroStats() {
        // Update intro page statistics
        const counts = this.state.sdkCounts;
        
        this.updateElementText('intro-nodejs-count', counts.nodejs || 0);
        this.updateElementText('intro-python-count', counts.python || 0);
        this.updateElementText('intro-browser-count', counts.browser || 0);
        this.updateElementText('intro-dotnet-count', counts.dotnet || 0);
        this.updateElementText('intro-java-count', counts.java || 0);
        this.updateElementText('intro-total-count', counts.total || 0);
    }
    
    updateRepositorySections() {
        // Find the main container for repository sections
        const mainContainer = document.querySelector('.main-container');
        if (!mainContainer) return;
        
        // Remove existing repository sections but keep intro page and empty state
        const existingSections = mainContainer.querySelectorAll('.repository-section');
        existingSections.forEach(section => section.remove());
        
        // Find the repositories container or create it
        let repositoriesContainer = document.getElementById('repositories-container');
        if (!repositoriesContainer) {
            repositoriesContainer = document.createElement('div');
            repositoriesContainer.id = 'repositories-container';
            mainContainer.appendChild(repositoriesContainer);
        }
        
        // Clear the container
        repositoriesContainer.innerHTML = '';
        
        // Add new repository sections
        this.state.repositories.forEach((repo, index) => {
            const sectionHTML = this.generateRepositorySection(repo, index === 0);
            repositoriesContainer.insertAdjacentHTML('beforeend', sectionHTML);
        });
        
        // Reinitialize any JavaScript functionality for the new sections
        this.initializeRepositorySections();
    }
    
    generateRepositorySection(repo, isFirst) {
        if (repo.count === 0) {
            return this.generateEmptyRepositorySection(repo);
        }
        
        const dataTypeLabel = this.state.dataType === 'prs' ? 'Pull Requests' : 'Issues';
        const dataTypeLabelSingular = this.state.dataType === 'prs' ? 'Pull Request' : 'Issue';
        
        let itemRows = '';
        repo.items.forEach(item => {
            itemRows += this.generateItemRow(item);
        });
        
        // Generate state filter buttons
        const stateFilters = `
            <div class="state-filters mb-3">
                <div class="btn-group btn-group-sm" role="group">
                    <button type="button" class="btn state-filter-btn ${this.state.showState === 'open' ? 'btn-primary' : 'btn-outline-primary'}" data-state="open">
                        <i class="fas fa-exclamation-circle"></i> Open
                    </button>
                    <button type="button" class="btn state-filter-btn ${this.state.showState === 'closed' ? 'btn-success' : 'btn-outline-success'}" data-state="closed">
                        <i class="fas fa-check-circle"></i> Closed
                    </button>
                    <button type="button" class="btn state-filter-btn ${this.state.showState === 'all' ? 'btn-secondary' : 'btn-outline-secondary'}" data-state="all">
                        <i class="fas fa-list"></i> All
                    </button>
                </div>
            </div>
        `;
        
    // Generate search/filter controls (expected by dashboard.js)
        const searchControls = `
            <div class="controls mb-3">
                <div class="input-group">
                    <div class="input-group-prepend">
                        <span class="input-group-text">
                            <i class="fas fa-search"></i>
                        </span>
                    </div>
                    <input type="text" class="form-control search-box" 
                           placeholder="Search ${dataTypeLabel.toLowerCase()}..." 
                           oninput="filterTable('${repo.id}', this.value)"
                           id="search-${repo.id}">
                </div>
            </div>
        `;
        
        // Generate pagination controls (expected by dashboard.js)
        const paginationControls = `
            <div class="pagination-container mt-3" id="pagination-${repo.id}" style="display: none;">
                <div class="d-flex justify-content-between align-items-center">
                    <div id="page-info-${repo.id}" class="text-muted"></div>
                    <div class="btn-group" role="group">
                        <button type="button" class="btn btn-outline-primary btn-sm" 
                                id="prev-btn-${repo.id}" onclick="prevPage('${repo.id}')">
                            <i class="fas fa-chevron-left"></i> Previous
                        </button>
                        <button type="button" class="btn btn-outline-primary btn-sm" 
                                id="next-btn-${repo.id}" onclick="nextPage('${repo.id}')">
                            Next <i class="fas fa-chevron-right"></i>
                        </button>
                    </div>
                </div>
                <div class="mt-2 text-center">
                    <small class="text-muted">
                        Page <input type="number" id="page-input-${repo.id}" 
                                   class="form-control d-inline-block" 
                                   style="width: 70px; height: 25px; padding: 2px 5px; font-size: 12px;"
                                   min="1" onchange="goToPage('${repo.id}', this.value)"> 
                        of <span id="page-counter-${repo.id}">1</span>
                    </small>
                </div>
            </div>
        `;
        
        // Dynamic table headers based on data type
        const isPRs = this.state.dataType === 'prs' || (repo.items[0] && repo.items[0].item_type === 'pr');
    const tableHeaders = isPRs ? `
                        <tr>
                <th onclick="sortTable('${repo.id}', 'number')" class="sortable" data-column="number"># <i class="fas fa-sort sort-icon"></i></th>
                <th onclick="sortTable('${repo.id}', 'title')" class="sortable" data-column="title">Title <i class="fas fa-sort sort-icon"></i></th>
                <th>Labels</th>
                <th>Author</th>
                <th>Reviewers</th>
                <th>Assignees</th>
                <th onclick="sortTable('${repo.id}', 'created')" class="sortable" data-column="created">Created <i class="fas fa-sort sort-icon"></i></th>
                <th onclick="sortTable('${repo.id}', 'updated')" class="sortable" data-column="updated">Updated <i class="fas fa-sort sort-icon"></i></th>
                        </tr>` : `
                        <tr>
                <th onclick="sortTable('${repo.id}', 'number')" class="sortable" data-column="number"># <i class="fas fa-sort sort-icon"></i></th>
                <th onclick="sortTable('${repo.id}', 'title')" class="sortable" data-column="title">Title <i class="fas fa-sort sort-icon"></i></th>
                <th onclick="sortTable('${repo.id}', 'labels')" class="sortable" data-column="labels">Labels <i class="fas fa-sort sort-icon"></i></th>
                <th onclick="sortTable('${repo.id}', 'assignee')" class="sortable" data-column="assignee">Assignee <i class="fas fa-sort sort-icon"></i></th>
                <th onclick="sortTable('${repo.id}', 'created')" class="sortable" data-column="created">Created <i class="fas fa-sort sort-icon"></i></th>
                <th onclick="sortTable('${repo.id}', 'updated')" class="sortable" data-column="updated">Updated <i class="fas fa-sort sort-icon"></i></th>
                        </tr>`;

        return `
        <div class="repository-section repo-section spa-fade-in" id="repo-${repo.id}" data-repo="${repo.name}">
            <div class="repo-header">
                <h2 class="repo-title">
                    <a href="https://github.com/${repo.name}" target="_blank">
                        <i class="fab fa-github"></i>
                        ${repo.display_name}
                    </a>
                    <span class="issue-count badge badge-primary ml-2">${repo.count}</span>
                </h2>
            </div>
            
            ${stateFilters}
            ${searchControls}
            
            <div class="table-responsive">
                <table class="table table-striped table-hover table-sm issues-table ${isPRs ? 'prs' : ''}" id="table-${repo.id}">
                    <thead class="thead-light">
                        ${tableHeaders}
                    </thead>
                    <tbody>
                        ${itemRows}
                    </tbody>
                </table>
            </div>
            
            ${paginationControls}
        </div>
        `;
    }
    
    generateEmptyRepositorySection(repo) {
        const dataTypeLabel = this.state.dataType === 'prs' ? 'pull requests' : 'issues';
        const stateLabel = this.state.showState === 'all' ? '' : ` ${this.state.showState}`;
        
        return `
        <div class="repository-section empty" id="section-${repo.id}" data-repo="${repo.name}">
            <div class="repo-header">
                <h2 class="repo-title">
                    <a href="https://github.com/${repo.name}" target="_blank">
                        <i class="fab fa-github"></i>
                        ${repo.display_name}
                    </a>
                </h2>
            </div>
            <div class="empty-repo-state">
                <i class="fas fa-check-circle text-success"></i>
                <p>No${stateLabel} ${dataTypeLabel} found</p>
            </div>
        </div>
        `;
    }
    
    generateItemRow(item) {
        const isPR = (this.state.dataType === 'prs') || (item.item_type === 'pr');
        if (isPR) {
            return this.generatePRRow(item);
        }
        return this.generateIssueRow(item);
    }

    generateIssueRow(item) {
        const labels = this.generateLabelsHTML(item.labels || []);
        const assignee = this.generateAssigneeHTML(item.assignee);
    const createdDate = this.formatDate(item.created_at);
    const updatedDate = this.formatDate(item.updated_at);
    const createdBadge = this.renderDateBadge(item.created_at);
    const updatedBadge = this.renderDateBadge(item.updated_at);

        const modalData = {
            repo: item.repository || item.repo,
            number: item.number,
            title: item.title,
            htmlUrl: item.html_url,
            body: item.body || '',
            triage: item.triage || '0',
            priority: item.priority || '0',
            comments: item.comments || '',
            assignees: item.assignee ? [item.assignee] : [],
            labels: Array.isArray(item.labels) ? item.labels : (item.labels ? JSON.parse(item.labels) : []),
            mentions: item.mentions || []
        };

        return `
    <tr data-repo="${this.escapeHtml(item.repository || item.repo || '')}"
            data-modal-data='${JSON.stringify(modalData).replace(/'/g, "&apos;")}'
            data-number="${item.number}"
            data-title="${this.escapeHtml(item.title)}"
            data-assignee="${assignee ? this.escapeHtml(assignee) : ''}"
            data-created="${item.created_at}"
            data-updated="${item.updated_at}"
            data-state="${item.state || ''}"
            data-triage="${item.triage || '0'}"
            data-priority="${item.priority || '0'}"
            onclick="openIssueModalFromData(this); return false;"
            style="cursor: pointer;">
            <td><a href="${item.html_url}" target="_blank" onclick="event.stopPropagation();">#${item.number}</a></td>
            <td><strong>${this.escapeHtml(item.title)}</strong>${item.state === 'closed' ? '<span class="badge badge-danger ml-2">Closed</span>' : ''}</td>
            <td>${labels}</td>
            <td>${assignee}</td>
            <td>${createdBadge}</td>
            <td>${updatedBadge}</td>
        </tr>`;
    }

    generatePRRow(item) {
    const updatedDate = this.formatDate(item.updated_at);
    const createdDate = this.formatDate(item.created_at);
    const createdBadge = this.renderDateBadge(item.created_at);
    const updatedBadge = this.renderDateBadge(item.updated_at);

        // Prefer explicit user_login from sync service; fallback to user object/string or author
        let authorLogin = '';
        if (item.user_login) {
            authorLogin = item.user_login;
        } else if (item.user) {
            authorLogin = (typeof item.user === 'string') ? item.user : (item.user && item.user.login ? item.user.login : '');
        } else if (item.author) {
            authorLogin = (typeof item.author === 'string') ? item.author : (item.author && item.author.login ? item.author.login : '');
        }

    // Map reviewers to array of login strings (requested_reviewers preferred)
    const reviewersRaw = Array.isArray(item.requested_reviewers) ? item.requested_reviewers
                  : (Array.isArray(item.reviewers) ? item.reviewers : []);
    const reviewers = reviewersRaw.map(r => typeof r === 'string' ? r : (r && r.login ? r.login : '')).filter(Boolean);

    // Assignees may be array of objects with login/html_url
    const assigneesRaw = Array.isArray(item.assignees) ? item.assignees : [];

        const labelsHTML = this.generateLabelsHTML(item.labels || []);
    const reviewersHTML = this.generateUserBadgesHTML(reviewers);
    const assigneesHTML = this.generateUserBadgesHTML(assigneesRaw);

        const modalData = {
            dataType: 'prs',
            repo: item.repository || item.repo,
            number: item.number,
            title: item.title,
            htmlUrl: item.html_url,
            body: item.body || '',
            author: authorLogin,
            reviewers: reviewers,
            status: item.state,
            draft: !!item.draft,
            merged: !!item.merged,
            baseRef: item.base_ref || '',
            headRef: item.head_ref || '',
            labels: Array.isArray(item.labels) ? item.labels : (item.labels ? JSON.parse(item.labels) : []),
            mentions: item.mentions || [],
            comments: item.comments || ''
        };

        return `
    <tr data-repo="${this.escapeHtml(item.repository || item.repo || '')}"
            data-modal-data='${JSON.stringify(modalData).replace(/'/g, "&apos;")}'
            data-number="${item.number}"
            data-title="${this.escapeHtml(item.title)}"
            data-created="${item.created_at}"
            data-updated="${item.updated_at}"
            data-state="${item.state || ''}"
            onclick="openIssueModalFromData(this); return false;"
            style="cursor: pointer;">
            <td><a href="${item.html_url}" target="_blank" onclick="event.stopPropagation();">#${item.number}</a></td>
            <td><strong>${this.escapeHtml(item.title)}</strong></td>
            <td>${labelsHTML || '<span class="text-muted">None</span>'}</td>
            <td>${authorLogin ? `<a href="https://github.com/${authorLogin}" target="_blank">@${authorLogin}</a>` : '<span class="text-muted">Unknown</span>'}</td>
            <td>${reviewersHTML || '<span class="text-muted">None</span>'}</td>
            <td>${assigneesHTML || '<span class="text-muted">None</span>'}</td>
            <td>${createdBadge}</td>
            <td>${updatedBadge}</td>
        </tr>`;
    }

    // Weeks-based date badge helpers
    getWeeksSince(dateStr) {
        if (!dateStr) return null;
        const now = new Date();
        const then = new Date(dateStr);
        const diffMs = now - then;
        const weeks = Math.floor(diffMs / (1000 * 60 * 60 * 24 * 7));
        return weeks < 0 ? 0 : weeks; // clamp
    }

    getDateBadgeClass(weeks) {
        if (weeks === null || weeks === undefined) return 'date-unknown';
        if (weeks <= 1) return 'date-fresh';
        if (weeks <= 4) return 'date-warm';
        if (weeks <= 12) return 'date-stale';
        return 'date-old';
    }

    renderDateBadge(dateStr) {
        if (!dateStr) return '<span class="text-muted">—</span>';
        const weeks = this.getWeeksSince(dateStr);
        const cls = this.getDateBadgeClass(weeks);
        const label = isNaN(weeks) ? '—' : `${weeks}w`;
        const formatted = this.formatDate(dateStr);
        return `<span class="date-badge ${cls}" title="${formatted}">${label}</span> <span class="text-muted">${formatted}</span>`;
    }

    generateUserBadgesHTML(users) {
        if (!users || users.length === 0) return '';
        try {
            // Normalize to list of {login, html_url}
            const norm = users.map(u => {
                if (typeof u === 'string') {
                    return { login: u, html_url: `https://github.com/${u}` };
                } else if (u && typeof u === 'object') {
                    const login = u.login || '';
                    const url = u.html_url || (login ? `https://github.com/${login}` : '#');
                    return { login, html_url: url };
                }
                return null;
            }).filter(Boolean);

            // Limit to first 3 and show "+N" for the rest
            const visible = norm.slice(0, 3);
            const remaining = norm.length - visible.length;
            const badges = visible.map(u => 
                `<a href="${u.html_url}" target="_blank" class="badge badge-info mr-1">@${this.escapeHtml(u.login)}</a>`
            ).join('');
            return remaining > 0 ? `${badges}<span class="badge badge-light">+${remaining} more</span>` : badges;
        } catch (e) {
            return '';
        }
    }
    
    generateLabelsHTML(labels) {
        if (!labels) return '';
        
        try {
            // Handle both array and string formats
            const labelsArray = Array.isArray(labels) ? labels : JSON.parse(labels);
            return labelsArray.map(label => 
                `<span class="badge badge-secondary" style="background-color: #${label.color}; color: ${this.getContrastColor(label.color)};">
                    ${this.escapeHtml(label.name)}
                </span>`
            ).join(' ');
        } catch (e) {
            return '';
        }
    }
    
    generateAssigneeHTML(assignee) {
        if (!assignee) return '<span class="text-muted">Unassigned</span>';
        
        try {
            // Handle both object and string formats
            if (typeof assignee === 'string') {
                // Could be a simple login string or JSON
                if (assignee.startsWith('{') || assignee.startsWith('[')) {
                    const assigneeData = JSON.parse(assignee);
                    if (Array.isArray(assigneeData) && assigneeData.length > 0) {
                        return `<a href="${assigneeData[0].html_url}" target="_blank">${this.escapeHtml(assigneeData[0].login)}</a>`;
                    } else if (assigneeData.login) {
                        return `<a href="${assigneeData.html_url}" target="_blank">${this.escapeHtml(assigneeData.login)}</a>`;
                    }
                } else {
                    // Simple string login
                    return this.escapeHtml(assignee);
                }
            } else if (assignee.login) {
                // Direct object
                return `<a href="${assignee.html_url}" target="_blank">${this.escapeHtml(assignee.login)}</a>`;
            }
        } catch (e) {
            console.warn('Error parsing assignee:', e, assignee);
        }
        
        return this.escapeHtml(String(assignee));
    }
    
    formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toLocaleDateString();
    }
    
    getContrastColor(hexColor) {
        // Simple contrast color calculation
        const r = parseInt(hexColor.substr(0, 2), 16);
        const g = parseInt(hexColor.substr(2, 2), 16);
        const b = parseInt(hexColor.substr(4, 2), 16);
        const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        return luminance > 0.5 ? '#000000' : '#ffffff';
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    updateNavigation() {
        // Update navbar counts based on current data
        if (!this.state.repositories) return;
        
        // Calculate counts by main_category (using new metadata structure)
        const counts = {
            nodejs: 0,
            python: 0,
            browser: 0,
            dotnet: 0,
            java: 0,
            react: 0
        };
        
        this.state.repositories.forEach(repo => {
            const category = repo.main_category || repo.sdk_type; // Fallback to old field
            switch(category) {
                case 'nodejs':
                    counts.nodejs += repo.count;
                    break;
                case 'python':
                    counts.python += repo.count;
                    break;
                case 'browser':
                case 'javascript': // Group javascript with browser
                    counts.browser += repo.count;
                    break;
                case 'dotnet':
                    counts.dotnet += repo.count;
                    break;
                case 'java':
                    counts.java += repo.count;
                    break;
                case 'react':
                case 'react-native':
                case 'angular': // Group React-related frameworks
                    counts.react += repo.count;
                    break;
            }
        });
        
        // Update navbar count badges
        this.updateNavbarCount('navbar-nodejs-count', counts.nodejs);
        this.updateNavbarCount('navbar-python-count', counts.python);
        this.updateNavbarCount('navbar-browser-count', counts.browser);
        this.updateNavbarCount('navbar-dotnet-count', counts.dotnet);
        this.updateNavbarCount('navbar-java-count', counts.java);
        this.updateNavbarCount('navbar-react-count', counts.react);
        
        // Update dropdown menus
        this.updateNavbarDropdowns();
    }
    
    updateNavbarCount(elementId, count) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = count.toString();
        }
    }
    
    updateNavbarDropdowns() {
        // Update dropdown menus with repository links using new metadata structure
        this.updateDropdownMenu('nodejs-dropdown-menu', 'nodejs');
        this.updateDropdownMenu('python-dropdown-menu', 'python');
        this.updateDropdownMenu('dotnet-dropdown-menu', 'dotnet');
        this.updateDropdownMenu('browser-dropdown-menu', 'browser');
        this.updateDropdownMenu('react-dropdown-menu', 'react');
        this.updateDropdownMenu('java-dropdown-menu', 'java');
        
        // Handle additional categories by grouping them
        this.updateMultiCategoryDropdownMenu('react-dropdown-menu', ['react', 'react-native', 'angular']);
        
        console.log('Navbar dropdowns updated, repositories available:', this.state.repositories.length);
        
        // Initialize Bootstrap dropdowns after content is updated
        this.initializeBootstrapDropdowns();
    }
    
    updateMultiCategoryDropdownMenu(dropdownId, categories) {
        const dropdown = document.getElementById(dropdownId);
        if (!dropdown || !this.state.repositories) return;
        
        // Filter repositories by multiple categories and sort by classification priority and then by priority
        const repos = this.state.repositories
            .filter(repo => categories.includes(repo.main_category))
            .sort((a, b) => {
                // First sort by classification priority (azure=1, opentelemetry=2, microsoft=3)
                const classificationOrder = {'azure': 1, 'opentelemetry': 2, 'microsoft': 3};
                const aClassPriority = classificationOrder[a.classification] || 999;
                const bClassPriority = classificationOrder[b.classification] || 999;
                
                if (aClassPriority !== bClassPriority) {
                    return aClassPriority - bClassPriority;
                }
                
                // Then sort by individual priority within classification
                return (a.priority || 999) - (b.priority || 999);
            });
            
        if (repos.length === 0) {
            dropdown.innerHTML = '<span class="dropdown-item-text text-muted">No repositories</span>';
            return;
        }
        
        // Group by classification and then by main_category for better organization
        const groupedRepos = {};
        repos.forEach(repo => {
            const classification = repo.classification || 'other';
            const mainCategory = repo.main_category || 'other';
            
            if (!groupedRepos[classification]) {
                groupedRepos[classification] = {};
            }
            if (!groupedRepos[classification][mainCategory]) {
                groupedRepos[classification][mainCategory] = [];
            }
            groupedRepos[classification][mainCategory].push(repo);
        });
        
        // Generate dropdown HTML with classification and category groups
        const dropdownHTML = [];
        
        // Order classifications: azure, opentelemetry, microsoft, others
        const classificationOrder = ['azure', 'opentelemetry', 'microsoft', 'other'];
        
        classificationOrder.forEach(classification => {
            if (groupedRepos[classification]) {
                // Add classification header
                if (dropdownHTML.length > 0) {
                    dropdownHTML.push('<div class="dropdown-divider"></div>');
                }
                
                const classificationLabel = this.getClassificationLabel(classification);
                dropdownHTML.push(`<h6 class="dropdown-header">${classificationLabel}</h6>`);
                
                // Add repositories grouped by main category
                Object.keys(groupedRepos[classification]).forEach(mainCategory => {
                    const categoryRepos = groupedRepos[classification][mainCategory];
                    
                    // Add sub-category header if multiple categories
                    if (categories.length > 1) {
                        dropdownHTML.push(`<div class="dropdown-item-text font-weight-bold text-capitalize px-3">${mainCategory}</div>`);
                    }
                    
                    categoryRepos.forEach(repo => {
                        const isActive = repo.name === this.state.selectedRepo ? 'active' : '';
                        const countBadge = repo.count > 0 ? 
                            `<span class="badge badge-light ml-2">${repo.count}</span>` : 
                            `<span class="badge badge-secondary ml-2">0</span>`;
                        
                        dropdownHTML.push(`<a class="dropdown-item ${isActive}" href="#" onclick="dashboardSPA.selectRepository('${repo.name}'); return false;">
                            ${repo.display_name} ${countBadge}
                        </a>`);
                    });
                });
            }
        });
        
        dropdown.innerHTML = dropdownHTML.join('');
    }
    
    updateDropdownMenu(dropdownId, mainCategory) {
        const dropdown = document.getElementById(dropdownId);
        if (!dropdown || !this.state.repositories) return;
        
        // Filter repositories by main_category and sort by classification priority and then by priority
        const repos = this.state.repositories
            .filter(repo => repo.main_category === mainCategory)
            .sort((a, b) => {
                // First sort by classification priority (azure=1, opentelemetry=2, microsoft=3)
                const classificationOrder = {'azure': 1, 'opentelemetry': 2, 'microsoft': 3};
                const aClassPriority = classificationOrder[a.classification] || 999;
                const bClassPriority = classificationOrder[b.classification] || 999;
                
                if (aClassPriority !== bClassPriority) {
                    return aClassPriority - bClassPriority;
                }
                
                // Then sort by individual priority within classification
                return (a.priority || 999) - (b.priority || 999);
            });
            
        if (repos.length === 0) {
            dropdown.innerHTML = '<span class="dropdown-item-text text-muted">No repositories</span>';
            return;
        }
        
        // Group by classification for better organization
        const groupedRepos = {};
        repos.forEach(repo => {
            const classification = repo.classification || 'other';
            if (!groupedRepos[classification]) {
                groupedRepos[classification] = [];
            }
            groupedRepos[classification].push(repo);
        });
        
        // Generate dropdown HTML with classification groups
        const dropdownHTML = [];
        
        // Order classifications: azure, opentelemetry, microsoft, others
        const classificationOrder = ['azure', 'opentelemetry', 'microsoft', 'other'];
        
        classificationOrder.forEach(classification => {
            if (groupedRepos[classification] && groupedRepos[classification].length > 0) {
                // Add classification header
                if (dropdownHTML.length > 0) {
                    dropdownHTML.push('<div class="dropdown-divider"></div>');
                }
                
                const classificationLabel = this.getClassificationLabel(classification);
                dropdownHTML.push(`<h6 class="dropdown-header">${classificationLabel}</h6>`);
                
                // Add repositories in this classification
                groupedRepos[classification].forEach(repo => {
                    const isActive = repo.name === this.state.selectedRepo ? 'active' : '';
                    const countBadge = repo.count > 0 ? 
                        `<span class="badge badge-light ml-2">${repo.count}</span>` : 
                        `<span class="badge badge-secondary ml-2">0</span>`;
                    
                    dropdownHTML.push(`<a class="dropdown-item ${isActive}" href="#" onclick="dashboardSPA.selectRepository('${repo.name}'); return false;">
                        ${repo.display_name} ${countBadge}
                    </a>`);
                });
            }
        });
        
        dropdown.innerHTML = dropdownHTML.join('');
    }
    
    getClassificationLabel(classification) {
        const labels = {
            'azure': '🔵 Azure',
            'opentelemetry': '🔗 OpenTelemetry', 
            'microsoft': '🏢 Microsoft',
            'other': '📦 Other'
        };
        return labels[classification] || labels['other'];
    }
    
    initializeBootstrapDropdowns() {
        // Initialize or re-initialize Bootstrap dropdowns after dynamic content is added
        try {
            // Use jQuery to initialize dropdowns (Bootstrap 4 syntax)
            if (typeof $ !== 'undefined') {
                const dropdownCount = $('.dropdown-toggle').length;
                console.log('Found', dropdownCount, 'dropdown toggles to initialize');
                
                // Dispose existing dropdown instances first
                $('.dropdown-toggle').dropdown('dispose');
                // Re-initialize dropdowns
                $('.dropdown-toggle').dropdown();
                console.log('Bootstrap 4 dropdowns initialized via jQuery');
            } else {
                console.warn('jQuery not available - cannot initialize Bootstrap 4 dropdowns');
            }
        } catch (error) {
            console.warn('Could not initialize Bootstrap dropdowns:', error);
        }
    }
    
    updateVisibility() {
        const hasRepo = this.state.selectedRepo !== '';
        
        console.log('updateVisibility called with:', {
            hasRepo,
            selectedRepo: this.state.selectedRepo,
            repositoriesLoaded: this.state.repositories.length
        });
        
        // Show/hide intro page - show when no specific repo is selected
        const introPage = document.getElementById('intro-page');
        if (introPage) {
            if (hasRepo) {
                introPage.style.display = 'none';
                console.log('Intro page hidden');
            } else {
                introPage.style.display = 'block';
                console.log('Intro page shown');
            }
        }
        
        // Show/hide empty state
        const emptyState = document.getElementById('empty-state');
        if (emptyState) {
            emptyState.style.display = 'none';
        }
        
        // Show/hide repository sections based on selection
        const allSections = document.querySelectorAll('.repository-section');
        console.log('Found repository sections:', allSections.length);
        
        if (hasRepo) {
            // Show only the selected repository section
            let foundMatchingSection = false;
            allSections.forEach(section => {
                const sectionRepo = section.getAttribute('data-repo');
                const shouldShow = sectionRepo === this.state.selectedRepo;
                section.style.display = shouldShow ? 'block' : 'none';
                
                // Also handle the 'active' class required by CSS
                if (shouldShow) {
                    section.classList.add('active');
                } else {
                    section.classList.remove('active');
                }
                
                console.log(`Section ${sectionRepo}: display = ${section.style.display}, shouldShow = ${shouldShow}, hasActive = ${section.classList.contains('active')}`);
                if (shouldShow) {
                    foundMatchingSection = true;
                }
            });
            
            if (!foundMatchingSection) {
                console.warn('No matching repository section found for:', this.state.selectedRepo);
                console.log('Available sections:', Array.from(allSections).map(s => s.getAttribute('data-repo')));
            }
        } else {
            // Hide all repository sections when no specific repo is selected - show only intro page
            allSections.forEach(section => {
                section.style.display = 'none'; // Hide all sections
                section.classList.remove('active'); // Remove active class
                console.log(`Section ${section.getAttribute('data-repo')}: hidden (no specific selection)`);
            });
        }
    }
    
    initializeRepositorySections() {
        // Initialize pagination, sorting, and other functionality for new sections
        // This integrates with existing dashboard.js functionality
        this.state.repositories.forEach(repo => {
            if (repo.count > 0) {
                // Use setTimeout to ensure DOM elements are ready
                setTimeout(() => {
                    // Initialize pagination for this repository
                    if (typeof initializePagination === 'function') {
                        const pageInput = document.getElementById('page-input-' + repo.id);
                        if (pageInput) {
                            initializePagination(repo.id, repo.count);
                        }
                    }
                    
                    // Initialize sorting for this repository  
                    if (typeof initializeSorting === 'function') {
                        initializeSorting(repo.id);
                    }
                    
                    // Show first page
                    if (typeof showPage === 'function') {
                        showPage(repo.id, 1);
                    }
                }, 10); // Small delay to ensure DOM is updated
            }
        });
    }
    
    setDataType(dataType) {
        if (dataType !== this.state.dataType) {
            this.state.dataType = dataType;
            this.updateURL();
            this.loadDashboardData();
        }
    }
    
    setShowState(showState) {
        if (showState !== this.state.showState) {
            this.state.showState = showState;
            this.updateURL();
            this.loadDashboardData();
        }
    }
    
    setSelectedRepo(repo) {
        if (repo !== this.state.selectedRepo) {
            this.state.selectedRepo = repo;
            this.updateURL();
            this.updateVisibility();
        }
    }
    
    updateURL() {
        // Don't update URL during initial state application to prevent conflicts
        if (this.isInitializing) {
            console.log('Skipping URL update during initialization');
            return;
        }
        
        const params = new URLSearchParams();
        
        if (this.state.dataType !== 'issues') {
            params.set('type', this.state.dataType);
        }
        if (this.state.showState !== 'open') {
            params.set('state', this.state.showState);
        }
        if (this.state.selectedRepo) {
            params.set('repo', this.state.selectedRepo);
        }
        
        const newURL = `${window.location.pathname}${params.toString() ? '?' + params.toString() : ''}`;
        window.history.pushState({ spa: true }, '', newURL);
    }
    
    updateURLFromState() {
        // Only update URL if we're not in the initial loading phase
        if (this.state.repositories && this.state.repositories.length > 0) {
            this.updateURL();
        }
    }
    
    handlePopState(e) {
        if (e.state && e.state.spa) {
            // Handle browser back/forward
            this.loadInitialState();
            this.loadDashboardData();
        }
    }
    
    setLoading(loading) {
        this.state.isLoading = loading;
        
        // Show/hide loading indicator
        const existingLoader = document.querySelector('.spa-loading');
        if (loading && !existingLoader) {
            const loader = document.createElement('div');
            loader.className = 'spa-loading';
            loader.innerHTML = `
                <div class="d-flex justify-content-center align-items-center" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(255,255,255,0.8); z-index: 9999;">
                    <div class="spinner-border" role="status">
                        <span class="sr-only">Loading...</span>
                    </div>
                </div>
            `;
            document.body.appendChild(loader);
        } else if (!loading && existingLoader) {
            existingLoader.remove();
        }
    }
    
    showError(message) {
        // Show error message to user
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger alert-dismissible fade show';
        errorDiv.innerHTML = `
            ${message}
            <button type="button" class="close" data-dismiss="alert">
                <span>&times;</span>
            </button>
        `;
        
        const container = document.querySelector('.main-container');
        if (container) {
            container.insertBefore(errorDiv, container.firstChild);
            
            // Auto-dismiss after 5 seconds
            setTimeout(() => {
                if (errorDiv.parentNode) {
                    errorDiv.remove();
                }
            }, 5000);
        }
    }
    
    updateElementText(id, text) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = text;
        }
    }
    
    // Public methods for external integration
    toggleDataType(dataType) {
        this.setDataType(dataType);
    }
    
    selectRepository(repo) {
        this.setSelectedRepo(repo);
    }
    
    changeState(state) {
        this.setShowState(state);
    }
    
    refresh() {
        // Clear cache and reload data
        this.state.cache.clear();
        this.loadDashboardData();
    }
}

// Global SPA instance
let dashboardSPA;

// Initialize SPA when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Set a flag to indicate SPA is taking control
    window.spaActive = true;
    
    // Override the original dashboard.js initialization to prevent conflicts
    window.initializePageFromUrl = function() {
        console.log('Dashboard.js initializePageFromUrl disabled - SPA is active');
    };
    
    dashboardSPA = new DashboardSPA();
    window.dashboardSPA = dashboardSPA; // Make it available globally
    
    // Initialize Bootstrap dropdowns on page load
    if (dashboardSPA && dashboardSPA.initializeBootstrapDropdowns) {
        setTimeout(() => {
            dashboardSPA.initializeBootstrapDropdowns();
        }, 100); // Small delay to ensure DOM is fully ready
    }
});

// Global functions for backward compatibility with existing code
function toggleDataType(dataType) {
    if (dashboardSPA) {
        dashboardSPA.toggleDataType(dataType);
    }
}

function clearRepoSelection() {
    if (dashboardSPA) {
        // Clear all URL parameters and return to home page default state
        dashboardSPA.state.selectedRepo = '';
        dashboardSPA.state.dataType = 'issues';
        dashboardSPA.state.showState = 'open';
        
        // Clear URL parameters by navigating to clean URL
        window.history.pushState({ spa: true }, '', window.location.pathname);
        
        // Reload data with default parameters and update UI
        dashboardSPA.loadDashboardData();
        dashboardSPA.updateDataTypeToggle();
        dashboardSPA.updateVisibility();
    }
}

function testRepoSelection(repo) {
    console.log('testRepoSelection called with:', repo);
    if (dashboardSPA) {
        dashboardSPA.selectRepository(repo);
    }
}

// Export for use in other scripts
window.DashboardSPA = DashboardSPA;
window.testRepoSelection = testRepoSelection;

// Handle home navigation - works on both SPA and non-SPA pages
function handleHomeNavigation() {
    // If we're on the dashboard page and have SPA functionality, use SPA navigation
    if (window.location.pathname === '/' && typeof clearRepoSelection === 'function') {
        clearRepoSelection();
        return false; // Prevent default href navigation
    }
    
    // For other pages or if SPA isn't available, navigate to home
    window.location.href = '/';
    return false;
}

// Export the navigation function
window.handleHomeNavigation = handleHomeNavigation;
