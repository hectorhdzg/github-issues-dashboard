// GitHub Issues Dashboard JavaScript
// Immediate URL parameter detection to prevent flash
(function() {
    const urlParams = new URLSearchParams(window.location.search);
    const hasRepoParam = urlParams.get('repo') || 
                        (typeof selectedRepoFromTemplate !== 'undefined' && selectedRepoFromTemplate.trim() !== '');
    const hasAnyParam = urlParams.toString().length > 0;
    
    // Only add has-url-params class if there's a specific repo parameter
    // This ensures the intro page shows when only type/state parameters are present
    if (hasRepoParam) {
        document.documentElement.classList.add('has-url-params');
    }
})();

// Pagination state for each table
const pageStates = {};
const itemsPerPage = 10;
let activeRepoId = null;

// Sorting state for each table
const sortStates = {};

// Sync status variables
let syncStatsInProgress = false;
let syncStatsErrors = 0;

function initializeSorting(repoId) {
    if (!sortStates[repoId]) {
        sortStates[repoId] = {
            column: null,
            direction: 'asc'
        };
    }
}

function sortTable(repoId, column) {
    initializeSorting(repoId);
    const sortState = sortStates[repoId];
    const table = document.getElementById('table-' + repoId);
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // Toggle direction if same column, else reset to ascending
    if (sortState.column === column) {
        sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc';
    } else {
        sortState.direction = 'asc';
    }
    sortState.column = column;
    
    // Update header styling
    updateSortHeaders(repoId);
    
    // Sort rows based on column and direction
    rows.sort((a, b) => {
        let aVal = getSortValue(a, column);
        let bVal = getSortValue(b, column);
        
        // Handle different data types
        if (column === 'number' || column === 'priority' || column === 'triage') {
            aVal = parseInt(aVal) || 0;
            bVal = parseInt(bVal) || 0;
        } else if (column === 'created' || column === 'updated') {
            aVal = new Date(aVal);
            bVal = new Date(bVal);
        }
        
        let result;
        if (aVal < bVal) result = -1;
        else if (aVal > bVal) result = 1;
        else result = 0;
        
        return sortState.direction === 'desc' ? -result : result;
    });
    
    // Re-append sorted rows
    rows.forEach(row => tbody.appendChild(row));
    
    // Update pagination after sorting
    const state = pageStates[repoId];
    if (state) {
        showPage(repoId, state.currentPage);
    }
    
    // Ensure first visible row is not hidden behind sticky header
    setTimeout(() => {
        const firstVisibleRow = tbody.querySelector('tr:not(.pagination-hidden)');
        if (firstVisibleRow) {
            firstVisibleRow.scrollIntoView({ 
                behavior: 'instant', 
                block: 'nearest',
                inline: 'nearest'
            });
        }
    }, 50);
}

function getSortValue(row, column) {
    switch (column) {
        case 'number':
            return row.dataset.number;
        case 'title':
            return row.dataset.title;
        case 'assignee':
            return row.dataset.assignee;
        case 'created':
            return row.dataset.created;
        case 'updated':
            return row.dataset.updated;
        case 'triage':
            return row.dataset.triage;
        case 'priority':
            return row.dataset.priority;
        default:
            return '';
    }
}

function updateSortHeaders(repoId) {
    const table = document.getElementById('table-' + repoId);
    const headers = table.querySelectorAll('th.sortable');
    const sortState = sortStates[repoId];
    
    headers.forEach(header => {
        header.classList.remove('sort-asc', 'sort-desc');
        if (header.dataset.column === sortState.column) {
            header.classList.add('sort-' + sortState.direction);
        }
    });
}

function initializePagination(repoId, totalItems) {
    if (!pageStates[repoId]) {
        pageStates[repoId] = {
            currentPage: 1,
            totalItems: totalItems,
            totalPages: Math.ceil(totalItems / itemsPerPage),
            filteredItems: totalItems
        };
    }
    initializeSorting(repoId);
    
    // For performance, hide all rows initially except first page
    showPage(repoId, 1);
}

function showPage(repoId, page) {
    const table = document.getElementById('table-' + repoId);
    
    // Add null check for table
    if (!table) {
        console.log('Table not found for repo:', repoId);
        return;
    }
    
    const rows = Array.from(table.getElementsByTagName('tr')).slice(1); // Skip header
    const state = pageStates[repoId];
    
    // Add null check for state
    if (!state) {
        console.log('Page state not found for repo:', repoId);
        return;
    }
    
    // Filter visible rows first
    const visibleRows = rows.filter(row => row.style.display !== 'none');
    state.filteredItems = visibleRows.length;
    state.totalPages = Math.ceil(state.filteredItems / itemsPerPage);
    
    // Ensure page is within bounds
    page = Math.max(1, Math.min(page, state.totalPages));
    state.currentPage = page;
    
    // Hide all rows first
    rows.forEach(row => {
        if (row.style.display !== 'none') {
            row.classList.add('pagination-hidden');
        }
    });
    
    // Show only current page rows
    const startIndex = (page - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    
    visibleRows.slice(startIndex, endIndex).forEach(row => {
        row.classList.remove('pagination-hidden');
    });
    
    updatePaginationControls(repoId);
}

function updatePaginationControls(repoId) {
    const state = pageStates[repoId];
    const controls = document.getElementById('pagination-' + repoId);
    
    // Add null check for controls
    if (!controls) {
        console.log('Pagination controls not found for repo:', repoId);
        return;
    }
    
    if (state.totalPages <= 1) {
        controls.style.display = 'none';
        return;
    } else {
        controls.style.display = 'flex';
    }
    
    // Update info with null checks
    const pageInfoElement = document.getElementById('page-info-' + repoId);
    if (pageInfoElement) {
        const startItem = (state.currentPage - 1) * itemsPerPage + 1;
        const endItem = Math.min(state.currentPage * itemsPerPage, state.filteredItems);
        pageInfoElement.textContent = 
            `Showing ${startItem}-${endItem} of ${state.filteredItems} issues`;
    }
    
    // Update buttons with null checks
    const prevBtn = document.getElementById('prev-btn-' + repoId);
    const nextBtn = document.getElementById('next-btn-' + repoId);
    
    if (prevBtn) {
        prevBtn.disabled = state.currentPage === 1;
    }
    if (nextBtn) {
        nextBtn.disabled = state.currentPage === state.totalPages;
    }
    
    // Update page input
    const pageInput = document.getElementById('page-input-' + repoId);
    pageInput.value = state.currentPage;
    pageInput.max = state.totalPages;
    
    // Update page counter
    document.getElementById('page-counter-' + repoId).textContent = 
        `Page ${state.currentPage} of ${state.totalPages}`;
}

function goToPage(repoId, page) {
    const state = pageStates[repoId];
    if (!state) return;
    
    const pageNum = parseInt(page);
    if (isNaN(pageNum) || pageNum < 1 || pageNum > state.totalPages) {
        // Reset input to current page if invalid
        const pageInput = document.getElementById('page-input-' + repoId);
        if (pageInput) {
            pageInput.value = state.currentPage;
        }
        return;
    }
    
    showPage(repoId, pageNum);
}

function nextPage(repoId) {
    const state = pageStates[repoId];
    if (state.currentPage < state.totalPages) {
        showPage(repoId, state.currentPage + 1);
    }
}

function prevPage(repoId) {
    const state = pageStates[repoId];
    if (state.currentPage > 1) {
        showPage(repoId, state.currentPage - 1);
    }
}

function filterTable(repoId, searchTerm) {
    const table = document.getElementById('table-' + repoId);
    const rows = table.getElementsByTagName('tr');
    
    for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        const text = row.textContent.toLowerCase();
        if (text.includes(searchTerm.toLowerCase())) {
            row.style.display = '';
            row.classList.remove('pagination-hidden');
        } else {
            row.style.display = 'none';
            row.classList.add('pagination-hidden');
        }
    }
    
    // Reset to page 1 after filtering
    showPage(repoId, 1);
}

function setActiveRepo(repoId) {
    // Hide intro page immediately to prevent flash
    const introPage = document.getElementById('intro-page');
    if (introPage) {
        introPage.classList.add('hidden');
        introPage.classList.remove('force-show');
    }
    
    // Hide all repo sections except the active one
    document.querySelectorAll('.repo-section').forEach(section => {
        section.classList.add('hidden');
        section.classList.remove('active');
    });
    document.querySelectorAll('.repo-header').forEach(header => {
        header.classList.remove('active');
    });
    document.querySelectorAll('.dropdown-item').forEach(link => {
        link.classList.remove('active');
    });
    
    // Show the selected repo section and mark header as active
    const repoSection = document.getElementById('repo-' + repoId);
    const header = document.querySelector(`#repo-${repoId} .repo-header`);
    const navLink = document.querySelector(`[onclick="setActiveRepo('${repoId}')"]`);
    
    if (repoSection && header) {
        // Check if the repo section has any data (table with rows)
        const table = repoSection.querySelector('table tbody');
        const hasRows = table && table.children.length > 0;
        
        if (!hasRows) {
            console.log('Repository has no data, showing empty state');
            const repoName = repoSection.getAttribute('data-repo-name') || repoId.replace(/-/g, '/');
            showEmptyRepositoryState(repoId, repoName);
            return;
        }
        
        repoSection.classList.remove('hidden');
        repoSection.classList.add('active');
        header.classList.add('active');
        if (navLink) {
            navLink.classList.add('active');
        }
        activeRepoId = repoId;
        
        // Update URL with selected repo parameter but preserve current state
        const repoName = repoSection.getAttribute('data-repo-name') || repoId.replace(/-/g, '/');
        const newUrl = new URL(window.location);
        newUrl.searchParams.set('repo', repoName);
        
        // Only set state to 'open' if no state is currently specified
        const currentState = newUrl.searchParams.get('state');
        if (!currentState) {
            newUrl.searchParams.set('state', 'open');
        }
        
        // Only set type to 'issues' if no type is currently specified
        const currentType = newUrl.searchParams.get('type');
        if (!currentType) {
            newUrl.searchParams.set('type', 'issues');
        }
        
        // Update browser URL without page reload
        window.history.replaceState({}, '', newUrl.toString());
    }
    
    // Initialize pagination for the active repo
    const table = document.getElementById('table-' + repoId);
    if (table) {
        const rows = table.getElementsByTagName('tr');
        const totalIssues = rows.length - 1; // Subtract header row
        
        // Only initialize pagination if there are issues
        if (totalIssues > 0) {
            initializePagination(repoId, totalIssues);
            // Setup page input handlers for this repo
            setupPageInputHandlers();
        }
    }
    
    // Scroll to the repo section
    if (repoSection) {
        repoSection.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}

function toggleSection(repoId) {
    // Always use setActiveRepo for consistent behavior
    setActiveRepo(repoId);
}

function scrollToRepo(repoId) {
    setActiveRepo(repoId);
}

function clearRepoSelection() {
    // Hide all repo sections and remove active class first
    document.querySelectorAll('.repo-section').forEach(section => {
        section.classList.add('hidden');
        section.classList.remove('active');
    });
    document.querySelectorAll('.repo-header').forEach(header => {
        header.classList.remove('active');
    });
    document.querySelectorAll('.dropdown-item').forEach(link => {
        link.classList.remove('active');
    });
    
    // Remove has-url-params class from document element to allow intro page to show
    document.documentElement.classList.remove('has-url-params');
    
    // Clear URL parameters that specify a repository
    const newUrl = new URL(window.location);
    newUrl.searchParams.delete('repo');
    window.history.replaceState({}, '', newUrl);
    
    // Show intro page with proper classes
    const introPage = document.getElementById('intro-page');
    if (introPage) {
        introPage.classList.remove('hidden');
        introPage.classList.add('force-show');
    }
    
    // Clear active repo tracking
    activeRepoId = null;
    
    // Update intro page statistics to ensure fresh data
    updateIntroStats();
    
    console.log('Cleared repo selection, showing intro page');
}

// Add keyboard event handler for page inputs
function setupPageInputHandlers() {
    document.querySelectorAll('.page-input').forEach(input => {
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const repoId = this.id.replace('page-input-', '');
                goToPage(repoId, this.value);
            }
        });
        
        // Also handle blur event for when user clicks away
        input.addEventListener('blur', function() {
            const repoId = this.id.replace('page-input-', '');
            goToPage(repoId, this.value);
        });
    });
}

// Hide all content sections
function hideAllContent() {
    document.querySelectorAll('.repo-section').forEach(section => {
        section.classList.add('hidden');
        section.classList.remove('active');
    });
    document.querySelectorAll('.repo-header').forEach(header => {
        header.classList.remove('active');
    });
    document.querySelectorAll('.dropdown-item').forEach(link => {
        link.classList.remove('active');
    });
    
    // Also clean up any empty states
    cleanupEmptyStates();
}

// Clean up any existing empty state displays
function cleanupEmptyStates() {
    const emptyRepoState = document.getElementById('empty-repo-state');
    if (emptyRepoState) {
        emptyRepoState.remove();
    }
    
    const repoNotFoundState = document.getElementById('repo-not-found-state');
    if (repoNotFoundState) {
        repoNotFoundState.remove();
    }
}

// Show the intro page
function showIntroPage() {
    const introPage = document.getElementById('intro-page');
    if (introPage) {
        introPage.classList.remove('hidden');
        introPage.classList.add('force-show');
    }
    hideAllContent();
}

// Activate a specific repository section
function activateRepoSection(repoId) {
    // Hide all content first
    hideAllContent();
    
    // Show the selected repo section
    const repoSection = document.getElementById('repo-' + repoId);
    const header = document.querySelector(`#repo-${repoId} .repo-header`);
    const navLink = document.querySelector(`[onclick="setActiveRepo('${repoId}')"]`);
    
    if (repoSection && header) {
        repoSection.classList.remove('hidden');
        repoSection.classList.add('active');
        header.classList.add('active');
        if (navLink) {
            navLink.classList.add('active');
        }
        activeRepoId = repoId;
        
        // Update URL with selected repo parameter but preserve current state
        const repoName = repoSection.getAttribute('data-repo-name') || repoId.replace(/-/g, '/');
        const newUrl = new URL(window.location);
        newUrl.searchParams.set('repo', repoName);
        
        // Only set state to 'open' if no state is currently specified
        const currentState = newUrl.searchParams.get('state');
        if (!currentState) {
            newUrl.searchParams.set('state', 'open');
        }
        
        // Only set type to 'issues' if no type is currently specified
        const currentType = newUrl.searchParams.get('type');
        if (!currentType) {
            newUrl.searchParams.set('type', 'issues');
        }
        
        // Update browser URL without page reload
        window.history.replaceState({}, '', newUrl.toString());
        
        // Update current table based on URL parameters
        updateCurrentTable(repoId);
    }
}

// Function to update intro page statistics
function updateIntroStats() {
    // Get counts from navbar badges
    const nodejsCount = document.getElementById('navbar-nodejs-count')?.textContent || '0';
    const pythonCount = document.getElementById('navbar-python-count')?.textContent || '0';
    const browserCount = document.getElementById('navbar-browser-count')?.textContent || '0';
    const dotnetCount = document.getElementById('navbar-dotnet-count')?.textContent || '0';
    const javaCount = document.getElementById('navbar-java-count')?.textContent || '0';
    
    // Calculate total
    const totalCount = parseInt(nodejsCount) + parseInt(pythonCount) + parseInt(browserCount) + parseInt(dotnetCount) + parseInt(javaCount);
    
    // Update intro page stats
    const introNodejsCount = document.getElementById('intro-nodejs-count');
    const introPythonCount = document.getElementById('intro-python-count');
    const introBrowserCount = document.getElementById('intro-browser-count');
    const introDotnetCount = document.getElementById('intro-dotnet-count');
    const introJavaCount = document.getElementById('intro-java-count');
    const introTotalCount = document.getElementById('intro-total-count');
    
    if (introNodejsCount) introNodejsCount.textContent = nodejsCount;
    if (introPythonCount) introPythonCount.textContent = pythonCount;
    if (introBrowserCount) introBrowserCount.textContent = browserCount;
    if (introDotnetCount) introDotnetCount.textContent = dotnetCount;
    if (introJavaCount) introJavaCount.textContent = javaCount;
    if (introTotalCount) introTotalCount.textContent = totalCount.toString();
}

// Function to update sync status indicators
function updateSyncStatus() {
    const syncInProgress = syncStatsInProgress || false;
    const syncErrors = syncStatsErrors || 0;
    const statusIndicator = document.getElementById('sync-status-indicator');
    const statusText = document.getElementById('sync-status-text');
    
    // Only update if the elements exist (they might not exist on stats page)
    if (statusIndicator && statusText) {
        if (syncInProgress) {
            statusIndicator.className = 'status-indicator in-progress';
            statusText.textContent = 'Sync in Progress...';
            statusText.style.color = '#ed8936';
        } else if (syncErrors > 0) {
            statusIndicator.className = 'status-indicator error';
            statusText.textContent = `Ready (${syncErrors} errors)`;
            statusText.style.color = '#f56565';
        } else {
            statusIndicator.className = 'status-indicator';
            statusText.textContent = 'Ready';
            statusText.style.color = '#48bb78';
        }
    } else {
        // Elements don't exist (probably on stats page or other page without sync indicators)
        console.log('Sync status indicators not found - page might not need them');
    }
}

// Function to fetch sync status from API
function fetchSyncStatus() {
    fetch('/api/sync_status')
        .then(response => response.json())
        .then(data => {
            syncStatsInProgress = data.sync_in_progress || false;
            syncStatsErrors = data.errors ? data.errors.length : 0;
            updateSyncStatus();
        })
        .catch(error => {
            console.warn('Could not fetch sync status:', error);
            // Keep default values
            syncStatsInProgress = false;
            syncStatsErrors = 0;
            updateSyncStatus();
        });
}

// Modal-related variables
let currentModalIssue = null;
let currentModalPR = null;

// Initialize modal event handlers on page load
document.addEventListener('DOMContentLoaded', function() {
    // Add global ESC key handler for modals
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            cleanupModalState();
        }
    });
    
    // Add click handlers for modal close buttons (only for actual close buttons)
    document.querySelectorAll('[data-dismiss="modal"]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            cleanupModalState();
        });
    });
    
    // Add close button event handler
    $('#modal-close-btn').on('click', function(e) {
        e.preventDefault();
        cleanupModalState();
    });

    // Ensure "View on GitHub" buttons always open in a new tab from modals
    const handleModalGitHubLinkClick = function(e) {
        const anchor = e.target.closest('#modal-github-link, #modal-pr-github-link');
        if (!anchor) return;
        const href = anchor.getAttribute('href');
        if (href && href !== '#') {
            e.preventDefault();
            e.stopPropagation();
            try {
                window.open(href, '_blank', 'noopener');
            } catch (err) {
                // Fallback to location change if popup blocked
                window.location.href = href;
            }
        }
    };
    document.addEventListener('click', handleModalGitHubLinkClick, true);
});

// Function to clean up modal state - simplified
function cleanupModalState() {
    console.log('🧹 Cleaning up modal state...');
    
    // Hide any visible modals
    $('#issueModal').modal('hide');
    $('#prModal').modal('hide');
    
    // Clear modal data
    currentModalIssue = null;
    
    console.log('✅ Modal state cleaned up');
}

// Function to open modal from data attribute (handles both issues and PRs)
function openIssueModalFromData(button) {
    try {
        const modalDataJson = button.getAttribute('data-modal-data');
        console.log('Raw modal data:', modalDataJson);
        
        // Decode HTML entities using a more robust method
        function decodeHtmlEntities(str) {
            const textarea = document.createElement('textarea');
            textarea.innerHTML = str;
            return textarea.value;
        }
        
        const decodedString = decodeHtmlEntities(modalDataJson);
        console.log('Decoded modal data:', decodedString);
        
        const modalData = JSON.parse(decodedString);
        console.log('Parsed modal data:', modalData);
        
        // Route to appropriate modal based on data type
        if (modalData.dataType === 'prs') {
            openPullRequestModal(modalData);
        } else {
            openIssueModal(
                modalData.repo,
                modalData.number, 
                modalData.title,
                modalData.htmlUrl,
                modalData.body,
                modalData.triage,
                modalData.priority,
                modalData.comments,
                modalData.assignees,
                modalData.labels,
                modalData.mentions
            );
        }
    } catch (error) {
        console.error('Error parsing modal data:', error);
        console.error('Modal data JSON:', button.getAttribute('data-modal-data'));
        alert('Error opening details. Please refresh the page and try again.');
    }
}

// Function to open issue modal
function openIssueModal(repo, number, title, htmlUrl, body, triage, priority, comments = '', assignees = [], labels = [], mentions = []) {
    console.log('Opening modal with data:', { repo, number, title, body, assignees, labels, mentions });
    
    // Store current issue data
    currentModalIssue = {
        repo: repo,
        number: number,
        title: title,
        htmlUrl: htmlUrl,
        body: body,
        triage: triage,
        priority: priority,
        comments: comments,
        assignees: assignees,
        labels: labels,
        mentions: mentions
    };
    
    // Update modal title for issues
    document.getElementById('issueModalLabel').innerHTML = '<i class="fas fa-bug"></i> Issue Details';
    
    // Populate modal fields
    document.getElementById('modal-issue-number').textContent = '#' + number;
    document.getElementById('modal-github-link').href = htmlUrl;
    document.getElementById('modal-issue-title').textContent = title;
    
    // Populate issue body/description
    const bodyElement = document.getElementById('modal-issue-body');
    if (body && body.trim()) {
        // Handle long descriptions by truncating if necessary
        let displayBody = body.trim();
        
        // If description is very long, truncate it
        if (displayBody.length > 2000) {
            displayBody = displayBody.substring(0, 2000) + '...\n\n[Description truncated - view full description on GitHub]';
        }
        
        bodyElement.textContent = displayBody;
        bodyElement.style.color = '#333';
    } else {
        bodyElement.textContent = '';  // Will show placeholder via CSS
        bodyElement.style.color = '#6c757d';
        bodyElement.style.fontStyle = 'italic';
    }
    
    document.getElementById('modal-triage').checked = triage == 1;
    document.getElementById('modal-priority').value = priority;
    document.getElementById('modal-comments').value = comments || '';
    
    // Populate context information
    console.log('Populating assignees:', assignees);
    populateAssignees(assignees);
    console.log('Populating labels:', labels);
    populateLabels(labels);
    console.log('Populating mentions:', mentions);
    populateMentions(mentions);
    
    // Reset save button state for issues
    const saveBtn = document.getElementById('modal-save-btn');
    saveBtn.style.display = 'inline-block';  // Show save button for issues
    saveBtn.disabled = false;
    saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Changes';
    saveBtn.className = 'btn btn-success';
    
    // Ensure any existing modal is properly closed first
    $('#issueModal').modal('hide');
    
    // Wait a moment then show the modal with simple Bootstrap configuration
    setTimeout(() => {
        console.log('🚀 Opening issue modal...');
        
        $('#issueModal').modal('show');
        
        // Simple event handling
        $('#issueModal').on('shown.bs.modal', function() {
            console.log('✅ Issue modal shown successfully');
            $(this).find('input, textarea, select, button').first().focus();
        });
        
        // Simple cleanup when modal is closed
        $('#issueModal').on('hidden.bs.modal', function() {
            currentModalIssue = null;
            $(this).off('shown.bs.modal hidden.bs.modal');
        });
    }, 100);
}

// Function to open pull request modal
function openPullRequestModal(modalData) {
    console.log('Opening PR modal with data:', modalData);

    // Store current PR data separately
    currentModalPR = {
        repo: modalData.repo,
        number: modalData.number,
        title: modalData.title,
        htmlUrl: modalData.htmlUrl,
        body: modalData.body,
        dataType: modalData.dataType,
        author: modalData.author,
        reviewers: modalData.reviewers,
        status: modalData.status,
        draft: modalData.draft,
        merged: modalData.merged,
        baseRef: modalData.baseRef,
        headRef: modalData.headRef,
        labels: modalData.labels,
        mentions: modalData.mentions,
        comments: modalData.comments
    };

    // Update PR modal title
    const prTitleEl = document.getElementById('prModalLabel');
    if (prTitleEl) {
        prTitleEl.innerHTML = '<i class="fas fa-code-branch"></i> Pull Request Details';
    }

    // Populate PR modal fields
    const prNumberEl = document.getElementById('modal-pr-number');
    const prLinkEl = document.getElementById('modal-pr-github-link');
    const prTitleTextEl = document.getElementById('modal-pr-title');
    const prBodyEl = document.getElementById('modal-pr-body');

    if (prNumberEl) prNumberEl.textContent = '#' + modalData.number;
    if (prLinkEl) prLinkEl.href = modalData.htmlUrl;
    if (prTitleTextEl) prTitleTextEl.textContent = modalData.title;

    if (prBodyEl) {
        if (modalData.body && modalData.body.trim()) {
            prBodyEl.textContent = modalData.body;
            prBodyEl.style.color = '#333';
            prBodyEl.style.fontStyle = 'normal';
        } else {
            prBodyEl.textContent = 'No description provided.';
            prBodyEl.style.color = '#999';
            prBodyEl.style.fontStyle = 'italic';
        }
    }

    // Populate PR-specific information targeting PR modal fields
    populatePRAuthor(modalData.author);
    populatePRReviewers(modalData.reviewers);
    populatePRStatus(modalData.status, modalData.draft, modalData.merged);
    populatePRBranches(modalData.baseRef, modalData.headRef);

    // Populate common information for PRs
    populatePRLabels(modalData.labels);
    populatePRMentions(modalData.mentions);

    // Set PR comments
    const prCommentsEl = document.getElementById('modal-pr-comments');
    if (prCommentsEl) prCommentsEl.value = modalData.comments || '';

    // Hide PR save button for now (read-only)
    const prSaveBtn = document.getElementById('modal-pr-save-btn');
    if (prSaveBtn) prSaveBtn.style.display = 'none';

    // Ensure issue modal is closed first
    $('#issueModal').modal('hide');

    // Show PR modal
    setTimeout(() => {
        console.log('🚀 Opening PR modal...');
        $('#prModal').modal('show');

        $('#prModal').on('shown.bs.modal', function() {
            console.log('✅ PR modal shown successfully');
            $(this).find('input, textarea, select, button').first().focus();
        });

        $('#prModal').on('hidden.bs.modal', function() {
            currentModalPR = null;
            $(this).off('shown.bs.modal hidden.bs.modal');
        });
    }, 100);
}

// Helper function to populate assignees display
function populateAssignees(assignees) {
    console.log('populateAssignees called with:', assignees);
    console.log('Assignees type:', typeof assignees);
    console.log('Assignees is array:', Array.isArray(assignees));
    
    const container = document.getElementById('modal-assignees');
    console.log('Assignees container found:', container);
    
    // Ensure assignees is always an array
    if (!assignees) {
        console.log('No assignees provided, setting to unassigned');
        container.innerHTML = '<span class="text-muted">Unassigned</span>';
        return;
    }
    
    // Convert single assignee object to array if needed
    let assigneesArray = Array.isArray(assignees) ? assignees : [assignees];
    console.log('Processed assignees array:', assigneesArray);
    
    if (assigneesArray.length === 0) {
        console.log('Empty assignees array, setting to unassigned');
        container.innerHTML = '<span class="text-muted">Unassigned</span>';
        return;
    }
    
    console.log('Processing', assigneesArray.length, 'assignees');
    const assigneeLinks = assigneesArray.map(assignee => {
        console.log('Processing assignee:', assignee);
        if (!assignee || !assignee.login) {
            console.error('Invalid assignee object:', assignee);
            return '';
        }
        return `<a href="https://github.com/${assignee.login}" target="_blank" class="badge badge-primary mr-1" style="font-size: 0.75rem; text-decoration: none;">
            <i class="fas fa-user"></i> @${assignee.login}
         </a>`;
    }).filter(link => link !== '').join('');
    
    console.log('Setting assignee HTML:', assigneeLinks);
    container.innerHTML = assigneeLinks;
}

// Helper function to populate labels display
function populateLabels(labels) {
    const container = document.getElementById('modal-labels');
    if (!labels || labels.length === 0) {
        container.innerHTML = '<span class="text-muted">None</span>';
        return;
    }
    
    const labelBadges = labels.map(label => {
        const color = label.color || 'cccccc';
        // Calculate text color based on background brightness
        const r = parseInt(color.substr(0, 2), 16);
        const g = parseInt(color.substr(2, 2), 16);
        const b = parseInt(color.substr(4, 2), 16);
        const brightness = (r * 299 + g * 587 + b * 114) / 1000;
        const textColor = brightness > 128 ? '#000000' : '#ffffff';
        
        return `<span class="badge mr-1" style="background-color: #${color}; color: ${textColor}; font-size: 0.75rem;" title="${label.description || ''}">
            ${label.name}
        </span>`;
    }).join('');
    
    container.innerHTML = labelBadges;
}

// Helper function to populate mentions display
function populateMentions(mentions) {
    const container = document.getElementById('modal-mentions');
    if (!mentions || mentions.length === 0) {
        container.innerHTML = '<span class="text-muted">None</span>';
        return;
    }
    
    const mentionLinks = mentions.map(mention => 
        `<a href="https://github.com/${mention}" target="_blank" class="badge badge-info mr-1">
            <i class="fas fa-at"></i> ${mention}
         </a>`
    ).join('');
    
    container.innerHTML = mentionLinks;
}

// Helper functions for PR-specific data
function populatePRAuthor(author) {
    const container = document.getElementById('modal-pr-author');
    if (!container) return; // Container doesn't exist yet
    
    if (!author) {
        container.innerHTML = '<span class="text-muted">Unknown</span>';
        return;
    }
    
    container.innerHTML = `<a href="https://github.com/${author}" target="_blank" class="badge badge-primary">
        <i class="fas fa-user"></i> ${author}
    </a>`;
}

function populatePRReviewers(reviewers) {
    const container = document.getElementById('modal-pr-reviewers');
    if (!container) return; // Container doesn't exist yet
    
    if (!reviewers || reviewers.length === 0) {
        container.innerHTML = '<span class="text-muted">No reviewers</span>';
        return;
    }
    
    const reviewerLinks = reviewers.map(reviewer => 
        `<a href="https://github.com/${reviewer}" target="_blank" class="badge badge-info mr-1">
            <i class="fas fa-user-check"></i> ${reviewer}
         </a>`
    ).join('');
    
    container.innerHTML = reviewerLinks;
}

function populatePRStatus(status, draft, merged) {
    const container = document.getElementById('modal-pr-status');
    if (!container) return; // Container doesn't exist yet
    
    let statusBadge = '';
    if (merged) {
        statusBadge = '<span class="badge badge-success"><i class="fas fa-check"></i> Merged</span>';
    } else if (draft) {
        statusBadge = '<span class="badge badge-secondary"><i class="fas fa-pencil-alt"></i> Draft</span>';
    } else if (status === 'open') {
        statusBadge = '<span class="badge badge-success"><i class="fas fa-exclamation-circle"></i> Open</span>';
    } else if (status === 'closed') {
        statusBadge = '<span class="badge badge-danger"><i class="fas fa-times"></i> Closed</span>';
    } else {
        statusBadge = `<span class="badge badge-secondary">${status}</span>`;
    }
    
    container.innerHTML = statusBadge;
}

function populatePRBranches(baseRef, headRef) {
    const container = document.getElementById('modal-pr-branches');
    if (!container) return; // Container doesn't exist yet
    
    if (!baseRef && !headRef) {
        container.innerHTML = '<span class="text-muted">No branch information</span>';
        return;
    }
    
    const baseDisplay = baseRef ? `<span class="badge badge-light mr-1"><i class="fas fa-code-branch"></i> ${baseRef}</span>` : '';
    const arrow = (baseRef && headRef) ? '<i class="fas fa-arrow-left mx-1"></i>' : '';
    const headDisplay = headRef ? `<span class="badge badge-info"><i class="fas fa-code-branch"></i> ${headRef}</span>` : '';
    
    container.innerHTML = `${headDisplay}${arrow}${baseDisplay}`;
}

function populatePRLabels(labels) {
    const container = document.getElementById('modal-pr-labels');
    if (!container) return; // Container doesn't exist yet
    
    if (!labels || labels.length === 0) {
        container.innerHTML = '<span class="text-muted">None</span>';
        return;
    }
    
    const labelBadges = labels.map(label => {
        const color = label.color || 'cccccc';
        // Calculate text color based on background brightness
        const r = parseInt(color.substr(0, 2), 16);
        const g = parseInt(color.substr(2, 2), 16);
        const b = parseInt(color.substr(4, 2), 16);
        const brightness = (r * 299 + g * 587 + b * 114) / 1000;
        const textColor = brightness > 128 ? '#000000' : '#ffffff';
        
        return `<span class="badge mr-1" style="background-color: #${color}; color: ${textColor}; font-size: 0.75rem;" title="${label.description || ''}">
            ${label.name}
        </span>`;
    }).join('');
    
    container.innerHTML = labelBadges;
}

function populatePRMentions(mentions) {
    const container = document.getElementById('modal-pr-mentions');
    if (!container) return; // Container doesn't exist yet
    
    if (!mentions || mentions.length === 0) {
        container.innerHTML = '<span class="text-muted">None</span>';
        return;
    }
    
    const mentionLinks = mentions.map(mention => 
        `<a href="https://github.com/${mention}" target="_blank" class="badge badge-info mr-1">
            <i class="fas fa-at"></i> ${mention}
         </a>`
    ).join('');
    
    container.innerHTML = mentionLinks;
}

// Function to save modal changes
function saveModalChanges() {
    if (!currentModalIssue) return;
    
    const saveBtn = document.getElementById('modal-save-btn');
    const triage = document.getElementById('modal-triage').checked;
    const priority = parseInt(document.getElementById('modal-priority').value);
    const comments = document.getElementById('modal-comments').value;
    
    // Update button state to show saving
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    saveBtn.className = 'btn btn-primary';
    
    console.log('🔄 Saving modal changes for issue #' + currentModalIssue.number);
    
    fetch('/api/update_issue', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            repo: currentModalIssue.repo,
            number: currentModalIssue.number,
            triage: triage,
            priority: priority,
            comments: comments
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('📊 Modal save response:', data);
        if (data.status === 'success') {
            // Success state
            saveBtn.innerHTML = '<i class="fas fa-check"></i> Saved!';
            saveBtn.className = 'btn btn-success';
            
            // Update the original table row
            updateTableRow(currentModalIssue.repo, currentModalIssue.number, triage, priority);
            
            // Update the current modal issue object with new values
            currentModalIssue.triage = triage;
            currentModalIssue.priority = priority;
            currentModalIssue.comments = comments;
            
            // Update the modal data attribute in the button for future opens
            updateModalDataAttribute(currentModalIssue.repo, currentModalIssue.number, currentModalIssue);
            
            // Close modal after 1 second
            setTimeout(() => {
                $('#issueModal').modal('hide');
            }, 1000);
        } else {
            // Error state
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error';
            saveBtn.className = 'btn btn-danger';
            
            setTimeout(() => {
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Changes';
                saveBtn.className = 'btn btn-success';
            }, 3000);
            
            alert('Error saving changes: ' + data.error);
        }
    })
    .catch(error => {
        console.error('❌ Modal save error:', error);
        
        // Error state
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error';
        saveBtn.className = 'btn btn-danger';
        
        setTimeout(() => {
            saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Changes';
            saveBtn.className = 'btn btn-success';
        }, 3000);
        
        alert('Error saving changes: ' + error.message);
    });
}

// Function to update table row after modal save
function updateTableRow(repo, number, triage, priority) {
    // Find the table row
    const row = document.querySelector(`tr[data-repo="${repo}"][data-number="${number}"]`);
    if (row) {
        // Update triage display
        const triageDisplay = row.querySelector('.triage-display');
        if (triageDisplay) {
            if (triage) {
                triageDisplay.innerHTML = '<i class="fas fa-check text-success" title="Triaged"></i>';
            } else {
                triageDisplay.innerHTML = '<span class="text-muted" title="Not triaged">—</span>';
            }
        }
        
        // Update priority display
        const priorityDisplay = row.querySelector('.priority-display');
        if (priorityDisplay) {
            const priorityMap = {
                '-1': 'Not Set',
                '0': '0 - Critical',
                '1': '1 - High',
                '2': '2 - Medium',
                '3': '3 - Low',
                '4': '4 - Minimal'
            };
            priorityDisplay.textContent = priorityMap[priority.toString()] || 'Unknown';
        }
        
        // Update data attributes
        row.dataset.triage = triage ? '1' : '0';
        row.dataset.priority = priority.toString();
    }
}

// Function to update the modal data attribute after save
function updateModalDataAttribute(repo, number, updatedModalData) {
    // Find the edit button for this issue
    const row = document.querySelector(`tr[data-repo="${repo}"][data-number="${number}"]`);
    if (row) {
        const editButton = row.querySelector('.edit-btn[data-modal-data]');
        if (editButton) {
            // Update the modal data attribute with the new values
            const newModalDataJson = JSON.stringify(updatedModalData);
            const escapedModalData = newModalDataJson
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#x27;');
            
            editButton.setAttribute('data-modal-data', escapedModalData);
            console.log('Updated modal data attribute for issue #' + number);
        }
    }
}

// Function to save PR modal changes
function savePRModalChanges() {
    if (!currentModalPR) return;
    
    const saveBtn = document.getElementById('modal-pr-save-btn');
    const reviewed = document.getElementById('modal-pr-reviewed').checked;
    const mergeReady = document.getElementById('modal-pr-merge-ready').checked;
    const comments = document.getElementById('modal-pr-comments').value;
    
    // Update button state to show saving
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    saveBtn.className = 'btn btn-primary';
    
    console.log('🔄 Saving PR modal changes for PR #' + currentModalPR.number);
    
    fetch('/api/update_pr', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            repo: currentModalPR.repo,
            number: currentModalPR.number,
            reviewed: reviewed,
            merge_ready: mergeReady,
            comments: comments
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('📊 PR modal save response:', data);
        if (data.status === 'success') {
            // Success state
            saveBtn.innerHTML = '<i class="fas fa-check"></i> Saved!';
            saveBtn.className = 'btn btn-success';
            
            // Update the original table row
            updatePRTableRow(currentModalPR.repo, currentModalPR.number, reviewed, mergeReady);
            
            // Update the current modal PR object with new values
            currentModalPR.reviewed = reviewed;
            currentModalPR.merge_ready = mergeReady;
            currentModalPR.comments = comments;
            
            // Close modal after 1 second
            setTimeout(() => {
                $('#prModal').modal('hide');
            }, 1000);
        } else {
            // Error state
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error';
            saveBtn.className = 'btn btn-danger';
            
            setTimeout(() => {
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Changes';
                saveBtn.className = 'btn btn-primary';
            }, 3000);
            
            alert('Error saving PR changes: ' + data.error);
        }
    })
    .catch(error => {
        console.error('❌ PR modal save error:', error);
        
        // Error state
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error';
        saveBtn.className = 'btn btn-danger';
        
        setTimeout(() => {
            saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Changes';
            saveBtn.className = 'btn btn-primary';
        }, 3000);
        
        alert('Error saving PR changes: ' + error.message);
    });
}

// Function to update PR table row after modal save
function updatePRTableRow(repo, number, reviewed, mergeReady) {
    // Find the table row
    const row = document.querySelector(`tr[data-repo="${repo}"][data-number="${number}"]`);
    if (row) {
        // Update reviewed display (you may need to add this column to your table)
        const reviewedDisplay = row.querySelector('.reviewed-display');
        if (reviewedDisplay) {
            if (reviewed) {
                reviewedDisplay.innerHTML = '<i class="fas fa-check text-success" title="Reviewed"></i>';
            } else {
                reviewedDisplay.innerHTML = '<span class="text-muted" title="Not reviewed">—</span>';
            }
        }
        
        // Update merge ready display
        const mergeReadyDisplay = row.querySelector('.merge-ready-display');
        if (mergeReadyDisplay) {
            if (mergeReady) {
                mergeReadyDisplay.innerHTML = '<i class="fas fa-check-circle text-success" title="Ready to merge"></i>';
            } else {
                mergeReadyDisplay.innerHTML = '<span class="text-muted" title="Not ready">—</span>';
            }
        }
        
        // Update data attributes
        row.dataset.reviewed = reviewed ? '1' : '0';
        row.dataset.mergeReady = mergeReady ? '1' : '0';
    }
}

// State Toggle Functions
function toggleIssueState() {
    // Get current state from URL or default to 'open'
    const currentParams = new URLSearchParams(window.location.search);
    const currentState = currentParams.get('state') || 'open';
    
    // Toggle to opposite state
    const newState = currentState === 'open' ? 'closed' : 'open';
    
    // Update URL parameter
    currentParams.set('state', newState);
    
    // Update browser URL without page reload (SPA behavior)
    const newUrl = window.location.pathname + '?' + currentParams.toString();
    window.history.replaceState({}, '', newUrl);
    
    // Try client-side filtering first
    const hasFilteredData = updateStateFilterInstantly(newState);
    
    // If no data was found after filtering, fetch from server
    if (!hasFilteredData) {
        console.log('No data found for state:', newState, '- fetching from server');
        fetchStateDataFromServer(newState);
    }
    
    // Update toggle switches to reflect new state
    updateToggleSwitches(newState);
    
    console.log('State toggled to:', newState, '(SPA mode)');
}

// Function to update toggle switches to reflect current state
function updateToggleSwitches(state, dataType) {
    // Update state toggle switches
    if (state) {
        document.querySelectorAll('.issue-state-toggle').forEach(toggle => {
            const openBtn = toggle.querySelector('[data-state="open"]');
            const closedBtn = toggle.querySelector('[data-state="closed"]');
            
            if (openBtn && closedBtn) {
                if (state === 'open') {
                    openBtn.classList.add('btn-primary');
                    openBtn.classList.remove('btn-outline-primary');
                    closedBtn.classList.add('btn-outline-primary');
                    closedBtn.classList.remove('btn-primary');
                } else {
                    closedBtn.classList.add('btn-primary');
                    closedBtn.classList.remove('btn-outline-primary');
                    openBtn.classList.add('btn-outline-primary');
                    openBtn.classList.remove('btn-primary');
                }
            }
        });
    }
    
    // Update data type toggle switches
    if (dataType) {
        document.querySelectorAll('.btn-toggle-data-type').forEach(btn => {
            const btnType = btn.getAttribute('data-type');
            if (btnType === dataType) {
                btn.classList.add('btn-primary');
                btn.classList.remove('btn-outline-primary');
            } else {
                btn.classList.add('btn-outline-primary');
                btn.classList.remove('btn-primary');
            }
        });
    }
}

function toggleDataType(dataType) {
    // Get current URL parameters
    const currentParams = new URLSearchParams(window.location.search);
    const currentDataType = currentParams.get('type') || 'issues';
    
    // If already on the requested data type, do nothing
    if (currentDataType === dataType) {
        return;
    }
    
    // Set the data type parameter while preserving all other parameters (repo, state, etc.)
    currentParams.set('type', dataType);
    
    // Update browser URL without page reload (SPA behavior)
    const newUrl = window.location.pathname + '?' + currentParams.toString();
    window.history.replaceState({}, '', newUrl);
    
    // For data type changes, we always need to fetch from server since it's different data structure
    console.log('Data type changed to:', dataType, '- fetching from server');
    fetchDataTypeFromServer(dataType);
    
    console.log('Data type changed to:', dataType, '(SPA mode)');
}

// New function to instantly update state filtering
function updateStateFilterInstantly(newState) {
    let hasVisibleContent = false;
    let foundAnyData = false;
    
    // Update each repository section
    document.querySelectorAll('.repo-section').forEach(section => {
        const table = section.querySelector('table tbody');
        if (!table) return;
        
        const rows = table.querySelectorAll('tr[data-state]');
        let visibleRowsInThisRepo = 0;
        
        // Check if we have any data rows at all
        if (rows.length > 0) {
            foundAnyData = true;
        }
        
        // Filter rows based on state
        rows.forEach(row => {
            const rowState = row.getAttribute('data-state');
            
            if (newState === 'all' || rowState === newState) {
                row.style.display = '';
                visibleRowsInThisRepo++;
                hasVisibleContent = true;
            } else {
                row.style.display = 'none';
            }
        });
        
        // Update repo section visibility and show/hide empty state
        const repoId = section.id.replace('repo-', '');
        if (visibleRowsInThisRepo === 0 && rows.length > 0) {
            // Show empty state message for this repo (has data but not for this state)
            showEmptyStateInRepo(section, newState, 'filtered');
        } else if (visibleRowsInThisRepo > 0) {
            // Hide any empty state and show normal content
            hideEmptyStateInRepo(section);
            
            // Reinitialize pagination for this repo
            initializePagination(repoId, visibleRowsInThisRepo);
        }
    });
    
    // If no content is visible but we found data, it means we need to fetch the other state
    if (!hasVisibleContent && foundAnyData) {
        console.log('Found data but none for state:', newState);
        return false; // Indicate that server fetch is needed
    }
    
    // If no content is visible at all, show a global message
    if (!hasVisibleContent) {
        showGlobalEmptyStateMessage(newState);
    } else {
        hideGlobalEmptyStateMessage();
    }
    
    // Update navbar counts based on filtered content
    updateNavbarCountsFromCurrentContent();
    
    return hasVisibleContent; // Return whether we successfully showed content
}

// Helper function to show empty state in a specific repo
function showEmptyStateInRepo(repoSection, state, reason = 'empty') {
    const table = repoSection.querySelector('table tbody');
    if (!table) return;
    
    // Remove existing empty state
    const existingEmpty = table.querySelector('.empty-state-row');
    if (existingEmpty) {
        existingEmpty.remove();
    }
    
    // Add empty state row
    const emptyRow = document.createElement('tr');
    emptyRow.className = 'empty-state-row';
    
    let message, icon, actionButton = '';
    
    if (reason === 'filtered') {
        // Data exists but not for this state
        icon = state === 'closed' ? 'check-circle' : 'inbox';
        message = `No ${state} items in current view`;
        actionButton = `
            <button class="btn btn-outline-primary btn-sm mt-2" onclick="fetchStateDataForRepo('${repoSection.id.replace('repo-', '')}', '${state}')">
                <i class="fas fa-sync"></i> Load ${state} items
            </button>
        `;
    } else {
        // No data at all
        icon = state === 'closed' ? 'check-circle' : 'inbox';
        message = `No ${state} items found`;
    }
    
    emptyRow.innerHTML = `
        <td colspan="8" class="text-center py-4">
            <div class="empty-table-message">
                <i class="fas fa-${icon} text-muted" style="font-size: 2rem; margin-bottom: 1rem;"></i>
                <h5 class="text-muted">${message}</h5>
                <p class="text-muted mb-0">Items may exist in the other state or might not be loaded yet.</p>
                ${actionButton}
            </div>
        </td>
    `;
    table.appendChild(emptyRow);
}

// Helper function to hide empty state in a specific repo
function hideEmptyStateInRepo(repoSection) {
    const existingEmpty = repoSection.querySelector('.empty-state-row');
    if (existingEmpty) {
        existingEmpty.remove();
    }
}

// Helper function to show global empty state message
function showGlobalEmptyStateMessage(state) {
    hideGlobalEmptyStateMessage(); // Remove existing first
    
    const messageDiv = document.createElement('div');
    messageDiv.id = 'global-empty-state';
    messageDiv.className = 'alert alert-warning text-center mt-3';
    messageDiv.innerHTML = `
        <i class="fas fa-exclamation-triangle"></i>
        <strong>No ${state} items found.</strong> 
        Try toggling to the other state or 
        <a href="javascript:void(0)" onclick="window.location.reload()" class="alert-link">refresh the page</a> 
        to load fresh data.
    `;
    
    const mainContainer = document.querySelector('.main-container');
    if (mainContainer) {
        mainContainer.insertBefore(messageDiv, mainContainer.firstChild);
    }
}

// Helper function to hide global empty state message
function hideGlobalEmptyStateMessage() {
    const existingMessage = document.getElementById('global-empty-state');
    if (existingMessage) {
        existingMessage.remove();
    }
}

// Function to fetch state data from server
function fetchStateDataFromServer(newState) {
    console.log('Fetching data for state:', newState);
    
    // Show loading indicator
    showLoadingIndicator('Fetching ' + newState + ' items...');
    
    // Build URL with current parameters but new state
    const currentParams = new URLSearchParams(window.location.search);
    currentParams.set('state', newState);
    const fetchUrl = window.location.pathname + '?' + currentParams.toString();
    
    // Fetch the new page content
    fetch(fetchUrl)
        .then(response => response.text())
        .then(html => {
            // Parse the response and extract repository sections
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newRepoSections = doc.querySelectorAll('.repo-section');
            
            // Replace current repository sections with new ones
            updateRepositorySections(newRepoSections);
            
            // Update navbar counts from the new content
            updateNavbarCountsFromContent(doc);
            
            // Hide loading indicator
            hideLoadingIndicator();
            
            // Update toggle switches
            updateToggleSwitches(newState);
            
            console.log('Successfully fetched and updated data for state:', newState);
        })
        .catch(error => {
            console.error('Error fetching state data:', error);
            hideLoadingIndicator();
            
            // Show error message
            showErrorMessage('Failed to load ' + newState + ' items. Please try refreshing the page.');
        });
}

// Function to fetch data type from server
function fetchDataTypeFromServer(dataType) {
    console.log('Fetching data for type:', dataType);
    
    // Show loading indicator
    showLoadingIndicator('Switching to ' + dataType + '...');
    
    // Build URL with current parameters but new data type
    const currentParams = new URLSearchParams(window.location.search);
    currentParams.set('type', dataType);
    const fetchUrl = window.location.pathname + '?' + currentParams.toString();
    
    // Fetch the new page content
    fetch(fetchUrl)
        .then(response => response.text())
        .then(html => {
            // Parse the response and extract repository sections
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newRepoSections = doc.querySelectorAll('.repo-section');
            const newToggleButtons = doc.querySelectorAll('.btn-toggle-data-type');
            
            // Replace current repository sections with new ones
            updateRepositorySections(newRepoSections);
            
            // Update data type toggle buttons
            updateDataTypeToggleButtons(newToggleButtons);
            
            // Update navbar counts from the new content
            updateNavbarCountsFromContent(doc);
            
            // Hide loading indicator
            hideLoadingIndicator();
            
            console.log('Successfully fetched and updated data for type:', dataType);
        })
        .catch(error => {
            console.error('Error fetching data type:', error);
            hideLoadingIndicator();
            
            // Show error message
            showErrorMessage('Failed to load ' + dataType + '. Please try refreshing the page.');
        });
}

// Function to show loading indicator
function showLoadingIndicator(message) {
    hideLoadingIndicator(); // Remove any existing indicator
    
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'spa-loading-indicator';
    loadingDiv.className = 'alert alert-info text-center';
    loadingDiv.innerHTML = `
        <div class="d-flex align-items-center justify-content-center">
            <div class="spinner-border spinner-border-sm me-2" role="status">
                <span class="sr-only">Loading...</span>
            </div>
            <span>${message}</span>
        </div>
    `;
    
    const mainContainer = document.querySelector('.main-container');
    if (mainContainer) {
        mainContainer.insertBefore(loadingDiv, mainContainer.firstChild);
    }
}

// Function to hide loading indicator
function hideLoadingIndicator() {
    const existingIndicator = document.getElementById('spa-loading-indicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }
}

// Function to show error message
function showErrorMessage(message) {
    hideErrorMessage(); // Remove any existing error
    
    const errorDiv = document.createElement('div');
    errorDiv.id = 'spa-error-message';
    errorDiv.className = 'alert alert-danger text-center';
    errorDiv.innerHTML = `
        <i class="fas fa-exclamation-triangle"></i>
        <strong>Error:</strong> ${message}
        <button type="button" class="close ml-2" onclick="hideErrorMessage()">
            <span>&times;</span>
        </button>
    `;
    
    const mainContainer = document.querySelector('.main-container');
    if (mainContainer) {
        mainContainer.insertBefore(errorDiv, mainContainer.firstChild);
    }
    
    // Auto-remove after 10 seconds
    setTimeout(hideErrorMessage, 10000);
}

// Function to hide error message
function hideErrorMessage() {
    const existingError = document.getElementById('spa-error-message');
    if (existingError) {
        existingError.remove();
    }
}

// Function to update repository sections with new content
function updateRepositorySections(newRepoSections) {
    // Remove existing repository sections
    document.querySelectorAll('.repo-section').forEach(section => section.remove());
    
    // Clear any existing page states to prevent stale references
    // Since pageStates is const, clear its properties instead of reassigning
    Object.keys(pageStates).forEach(key => delete pageStates[key]);
    
    // Add new repository sections
    const mainContainer = document.querySelector('.main-container');
    if (mainContainer && newRepoSections.length > 0) {
        newRepoSections.forEach(section => {
            mainContainer.appendChild(section.cloneNode(true));
        });
        
        // Reinitialize functionality for new sections
        setupPageInputHandlers();
        initializeDropdowns();
        
        // Reinitialize page state - but do it after DOM is ready
        setTimeout(() => {
            initializePageFromUrl();
        }, 0);
        
        // Update navbar counts based on new content
        updateNavbarCountsFromCurrentContent();
    }
}

// Function to update data type toggle buttons
function updateDataTypeToggleButtons(newToggleButtons) {
    const currentToggleContainer = document.querySelector('.global-data-type-toggle .btn-group');
    if (currentToggleContainer && newToggleButtons.length > 0) {
        // Clear current buttons
        currentToggleContainer.innerHTML = '';
        
        // Add new buttons
        newToggleButtons.forEach(button => {
            currentToggleContainer.appendChild(button.cloneNode(true));
        });
    }
}

// Function to fetch state data for a specific repo
function fetchStateDataForRepo(repoId, state) {
    console.log('Fetching', state, 'data for repo:', repoId);
    // For now, fall back to full fetch
    fetchStateDataFromServer(state);
}

// Function to update navbar counts from server response
function updateNavbarCountsFromContent(doc) {
    // Look for the count update script in the new content
    const scripts = doc.querySelectorAll('script');
    for (let script of scripts) {
        const scriptContent = script.textContent || script.innerHTML;
        if (scriptContent.includes('navbar-nodejs-count')) {
            // Extract count values from the script content
            const nodejsMatch = scriptContent.match(/navbar-nodejs-count.*?'(\d+)'/);
            const pythonMatch = scriptContent.match(/navbar-python-count.*?'(\d+)'/);
            const browserMatch = scriptContent.match(/navbar-browser-count.*?'(\d+)'/);
            const dotnetMatch = scriptContent.match(/navbar-dotnet-count.*?'(\d+)'/);
            const javaMatch = scriptContent.match(/navbar-java-count.*?'(\d+)'/);
            
            // Update the counts
            if (nodejsMatch) document.getElementById('navbar-nodejs-count').textContent = nodejsMatch[1];
            if (pythonMatch) document.getElementById('navbar-python-count').textContent = pythonMatch[1];
            if (browserMatch) document.getElementById('navbar-browser-count').textContent = browserMatch[1];
            if (dotnetMatch) document.getElementById('navbar-dotnet-count').textContent = dotnetMatch[1];
            if (javaMatch) document.getElementById('navbar-java-count').textContent = javaMatch[1];
            
            console.log('Updated navbar counts from server response');
            break;
        }
    }
    
    // Also update dropdown menu content from server response
    updateDropdownMenusFromContent(doc);
}

// Function to update dropdown menu content from server response
function updateDropdownMenusFromContent(doc) {
    console.log('🔄 Updating dropdown menus from server content');
    
    // Update each dropdown menu with new content from server
    const dropdownMenus = [
        { id: 'nodejs-dropdown-menu', selector: '#nodejs-dropdown-menu' },
        { id: 'python-dropdown-menu', selector: '#python-dropdown-menu' },
        { id: 'browser-dropdown-menu', selector: '#browser-dropdown-menu' },
        { id: 'dotnet-dropdown-menu', selector: '#dotnet-dropdown-menu' },
        { id: 'java-dropdown-menu', selector: '#java-dropdown-menu' }
    ];
    
    dropdownMenus.forEach(menu => {
        const newMenuContent = doc.querySelector(menu.selector);
        const currentMenu = document.querySelector(menu.selector);
        
        console.log(`Checking dropdown ${menu.id}:`, {
            newMenuFound: !!newMenuContent,
            currentMenuFound: !!currentMenu,
            newMenuHTML: newMenuContent?.innerHTML?.substring(0, 100),
            currentMenuHTML: currentMenu?.innerHTML?.substring(0, 100)
        });
        
        if (newMenuContent && currentMenu) {
            // Replace the innerHTML with updated content
            currentMenu.innerHTML = newMenuContent.innerHTML;
            console.log('✅ Updated dropdown menu:', menu.id);
        } else {
            console.warn('❌ Failed to update dropdown menu:', menu.id, {
                newMenuContent: !!newMenuContent,
                currentMenu: !!currentMenu
            });
        }
    });
}

// Function to recalculate and update navbar counts from current visible content
function updateNavbarCountsFromCurrentContent() {
    const repoCategorization = {
        'Azure-azure-sdk-for-python': 'python',
        'open-telemetry-opentelemetry-python': 'python',
        'open-telemetry-opentelemetry-python-contrib': 'python',
        'Azure-azure-sdk-for-js': 'nodejs',
        'open-telemetry-opentelemetry-js': 'nodejs',
        'open-telemetry-opentelemetry-js-contrib': 'nodejs',
        'microsoft-ApplicationInsights-node-js': 'nodejs',
        'microsoft-ApplicationInsights-node-js-native-metrics': 'nodejs',
        'microsoft-node-diagnostic-channel': 'nodejs',
        'Azure-azure-sdk-for-net': 'dotnet',
        'microsoft-ApplicationInsights-dotnet': 'dotnet',
        'open-telemetry-opentelemetry-dotnet': 'dotnet',
        'open-telemetry-opentelemetry-java': 'java',
        'microsoft-ApplicationInsights-Java': 'java'
    };
    
    const counts = {
        nodejs: 0,
        python: 0,
        browser: 0,
        dotnet: 0,
        java: 0
    };
    
    const repoCounts = {};
    
    // Count visible items in each repository
    document.querySelectorAll('.repo-section').forEach(section => {
        const repoId = section.id;
        const category = repoCategorization[repoId] || 'browser';
        
        // Count visible rows in this repo
        const visibleRows = section.querySelectorAll('tbody tr:not([style*="display: none"])');
        const repoCount = visibleRows.length;
        
        counts[category] += repoCount;
        repoCounts[repoId] = repoCount;
    });
    
    // Update navbar badges
    document.getElementById('navbar-nodejs-count').textContent = counts.nodejs;
    document.getElementById('navbar-python-count').textContent = counts.python;
    document.getElementById('navbar-browser-count').textContent = counts.browser;
    document.getElementById('navbar-dotnet-count').textContent = counts.dotnet;
    document.getElementById('navbar-java-count').textContent = counts.java;
    
    // Update individual repository counts in dropdown menus
    updateDropdownMenuCounts(repoCounts);
    
    console.log('Updated navbar counts from current content:', counts);
}

// Function to update individual repository counts in dropdown menus
function updateDropdownMenuCounts(repoCounts) {
    // Map repo IDs to their original repo names for finding dropdown items
    const repoIdToName = {
        'Azure-azure-sdk-for-python': 'azure-sdk-for-python',
        'open-telemetry-opentelemetry-python': 'opentelemetry-python', 
        'open-telemetry-opentelemetry-python-contrib': 'opentelemetry-python-contrib',
        'Azure-azure-sdk-for-js': 'azure-sdk-for-js',
        'open-telemetry-opentelemetry-js': 'opentelemetry-js',
        'open-telemetry-opentelemetry-js-contrib': 'opentelemetry-js-contrib',
        'microsoft-ApplicationInsights-node-js': 'ApplicationInsights-node.js',
        'microsoft-ApplicationInsights-node-js-native-metrics': 'ApplicationInsights-node.js-native-metrics',
        'microsoft-node-diagnostic-channel': 'node-diagnostic-channel',
        'Azure-azure-sdk-for-net': 'azure-sdk-for-net',
        'microsoft-ApplicationInsights-dotnet': 'ApplicationInsights-dotnet',
        'open-telemetry-opentelemetry-dotnet': 'opentelemetry-dotnet',
        'open-telemetry-opentelemetry-java': 'opentelemetry-java',
        'microsoft-ApplicationInsights-Java': 'ApplicationInsights-Java'
    };
    
    // Update each dropdown menu item
    Object.keys(repoCounts).forEach(repoId => {
        const repoName = repoIdToName[repoId];
        const count = repoCounts[repoId];
        
        // Find dropdown items that match this repository
        document.querySelectorAll('.dropdown-item').forEach(item => {
            const repoNameSpan = item.querySelector('.nav-repo-name');
            const badgeSpan = item.querySelector('.badge.badge-light.ml-auto');
            
            if (repoNameSpan && badgeSpan) {
                const itemRepoName = repoNameSpan.textContent.trim();
                if (repoName && itemRepoName.includes(repoName.split('-').pop())) {
                    badgeSpan.textContent = count;
                    console.log(`Updated dropdown count for ${itemRepoName}: ${count}`);
                }
            }
        });
    });
}

// New function to update toggle switch states
function updateToggleSwitches(newState) {
    document.querySelectorAll('.toggle-input').forEach(toggle => {
        toggle.checked = (newState === 'closed');
    });
}

// New function to handle data type transitions with loading state
function showDataTypeTransition(newDataType) {
    // Show message explaining that data type switching requires page content
    const messageDiv = document.createElement('div');
    messageDiv.id = 'data-type-message';
    messageDiv.className = 'alert alert-info text-center mt-3';
    messageDiv.innerHTML = `
        <i class="fas fa-info-circle"></i>
        <strong>Data type changed to ${newDataType}.</strong> 
        <a href="javascript:void(0)" onclick="window.location.reload()" class="alert-link">
            Click here to reload and view ${newDataType}
        </a> or continue browsing current content.
    `;
    
    // Remove any existing message
    const existingMessage = document.getElementById('data-type-message');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    // Add message to the top of the main container
    const mainContainer = document.querySelector('.main-container');
    if (mainContainer) {
        mainContainer.insertBefore(messageDiv, mainContainer.firstChild);
        
        // Auto-remove message after 10 seconds
        setTimeout(() => {
            if (messageDiv && messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 10000);
    }
}

// Initialize data type toggle buttons based on current state
function initializeDataTypeToggle() {
    // Get current data type from template variable or URL params as fallback
    const currentDataType = (typeof currentDataTypeFromTemplate !== 'undefined') ? 
        currentDataTypeFromTemplate : 
        (new URLSearchParams(window.location.search).get('type') || 'issues');
    
    // Update button states - remove all active classes and btn-primary, add btn-outline-primary
    document.querySelectorAll('.btn-toggle-data-type').forEach(btn => {
        btn.classList.remove('active', 'btn-primary');
        btn.classList.add('btn-outline-primary');
    });
    
    // Set the active button with proper Bootstrap classes
    const activeButton = document.getElementById(currentDataType + '-toggle');
    if (activeButton) {
        activeButton.classList.remove('btn-outline-primary');
        activeButton.classList.add('btn-primary', 'active');
    }
}

// Initialize page state based on URL parameters and template variables
function initializePageFromUrl() {
    // Get URL parameters (define outside try block)
    const urlParams = new URLSearchParams(window.location.search);
    const urlRepo = urlParams.get('repo');
    const urlType = urlParams.get('type');
    const urlState = urlParams.get('state');
    
    try {
        // Check template variable for selected repo (passed from Flask backend)
        const templateRepo = (typeof selectedRepoFromTemplate !== 'undefined') ? selectedRepoFromTemplate : '';
        
        // Use URL repo parameter or template variable as fallback
        const selectedRepo = urlRepo || templateRepo;
        
        console.log('Initializing page with:', {
            urlRepo,
            templateRepo,
            selectedRepo,
            urlType,
            urlState
        });
        
        if (selectedRepo && selectedRepo.trim() !== '') {
            // Convert repo name to repo ID format
            const selectedRepoId = selectedRepo.replace('/', '-').replace(/\./g, '-');
            
            // Try to find and select the repository
            const repoSection = document.getElementById('repo-' + selectedRepoId);
            if (repoSection) {
                console.log('Found repo section, activating:', selectedRepoId);
                // Check if the repo section has any data (table with rows)
                const table = repoSection.querySelector('table tbody');
                const hasRows = table && table.children.length > 0;
                
                if (!hasRows) {
                    console.log('Repository section exists but has no data, showing empty state');
                    // Show empty state for this repository
                    showEmptyRepositoryState(selectedRepoId, selectedRepo);
                    return;
                }
                
                // Immediately make the repo section active (visible) and hide intro
                repoSection.classList.add('active');
                repoSection.classList.remove('hidden');
                
                // Hide intro page immediately
                const introPage = document.getElementById('intro-page');
                if (introPage) {
                    introPage.classList.add('hidden');
                    introPage.classList.remove('force-show');
                }
                
                // Call setActiveRepo for full setup
                setActiveRepo(selectedRepoId);
                return; // Exit early if we found and selected the repo
            } else {
                console.warn('Repository section not found for:', selectedRepoId);
                // Instead of showing intro page, show empty state message
                showRepositoryNotFoundState(selectedRepo);
                return; // Exit early after handling missing repo
            }
        }
    } catch (error) {
        console.error('Error in initializePageFromUrl:', error);
        // Fall back to showing intro page on any error
        const introPage = document.getElementById('intro-page');
        if (introPage) {
            introPage.classList.remove('hidden');
            introPage.classList.add('force-show');
        }
        return;
    }
    
    // Show intro page if no URL parameters are present OR if only type/state parameters are present (no specific repo)
    const hasAnyParams = urlParams.toString().length > 0;
    const hasRepoParam = urlRepo && urlRepo.trim() !== '';
    
    if (!hasAnyParams || (!hasRepoParam && hasAnyParams)) {
        // Show intro page when:
        // 1. No parameters at all
        // 2. Parameters present but no specific repo (e.g., just ?type=prs or ?state=closed)
        console.log('Showing intro page - no specific repo selected');
        const introPage = document.getElementById('intro-page');
        if (introPage) {
            introPage.classList.remove('hidden');
            introPage.classList.add('force-show');
        }
    } else {
        console.log('Parameters present with specific repo, keeping intro page hidden');
        const introPage = document.getElementById('intro-page');
        if (introPage) {
            introPage.classList.add('hidden');
            introPage.classList.remove('force-show');
        }
    }
}

// Show empty repository state when repo exists but has no data
function showEmptyRepositoryState(repoId, repoName) {
    // Hide intro page
    const introPage = document.getElementById('intro-page');
    if (introPage) {
        introPage.classList.add('hidden');
        introPage.classList.remove('force-show');
    }
    
    // Hide all repo sections first
    hideAllContent();
    
    // Show a message that the repository exists but has no issues/PRs
    const container = document.querySelector('.container-fluid');
    if (container) {
        const emptyStateHtml = `
            <div id="empty-repo-state" class="empty-repo-state text-center py-5">
                <div class="card mx-auto" style="max-width: 600px;">
                    <div class="card-body">
                        <i class="fas fa-inbox fa-4x text-muted mb-3"></i>
                        <h3 class="card-title">No Issues Found</h3>
                        <p class="card-text text-muted">
                            The repository <strong>${repoName}</strong> exists but doesn't have any issues or pull requests matching the current filters.
                        </p>
                        <p class="card-text">
                            <small class="text-muted">
                                Try adjusting your filters or check back later when new issues are added.
                            </small>
                        </p>
                        <a href="/" class="btn btn-primary">
                            <i class="fas fa-home"></i> Back to Dashboard
                        </a>
                    </div>
                </div>
            </div>
        `;
        
        // Remove any existing empty state
        const existingEmptyState = document.getElementById('empty-repo-state');
        if (existingEmptyState) {
            existingEmptyState.remove();
        }
        
        // Insert the empty state after the intro page
        const introPageElement = document.getElementById('intro-page');
        if (introPageElement) {
            introPageElement.insertAdjacentHTML('afterend', emptyStateHtml);
        }
    }
}

// Show repository not found state when repo doesn't exist
function showRepositoryNotFoundState(repoName) {
    // Hide intro page
    const introPage = document.getElementById('intro-page');
    if (introPage) {
        introPage.classList.add('hidden');
        introPage.classList.remove('force-show');
    }
    
    // Hide all repo sections first
    hideAllContent();
    
    // Show a message that the repository was not found
    const container = document.querySelector('.container-fluid');
    if (container) {
        const notFoundStateHtml = `
            <div id="repo-not-found-state" class="repo-not-found-state text-center py-5">
                <div class="card mx-auto" style="max-width: 600px;">
                    <div class="card-body">
                        <i class="fas fa-search fa-4x text-muted mb-3"></i>
                        <h3 class="card-title">Repository Not Found</h3>
                        <p class="card-text text-muted">
                            The repository <strong>${repoName}</strong> was not found in the dashboard.
                        </p>
                        <p class="card-text">
                            <small class="text-muted">
                                This could mean the repository hasn't been synced yet, or the name in the URL is incorrect.
                            </small>
                        </p>
                        <a href="/" class="btn btn-primary">
                            <i class="fas fa-home"></i> Back to Dashboard
                        </a>
                    </div>
                </div>
            </div>
        `;
        
        // Remove any existing not found state
        const existingNotFoundState = document.getElementById('repo-not-found-state');
        if (existingNotFoundState) {
            existingNotFoundState.remove();
        }
        
        // Clear the invalid repo parameter from URL
        const newUrl = new URL(window.location);
        newUrl.searchParams.delete('repo');
        window.history.replaceState({}, '', newUrl.toString());
        
        // Insert the not found state after the intro page
        const introPageElement = document.getElementById('intro-page');
        if (introPageElement) {
            introPageElement.insertAdjacentHTML('afterend', notFoundStateHtml);
        }
    }
}

// Document ready event handler
document.addEventListener('DOMContentLoaded', function() {
    // FIRST: Initialize page state immediately to prevent flash
    initializePageFromUrl();
    
    // Setup page input handlers
    setupPageInputHandlers();
    
    // Update intro page statistics
    updateIntroStats();
    
    // Fetch and update sync status
    fetchSyncStatus();
    
    // Set up periodic sync status updates (every 30 seconds)
    setInterval(fetchSyncStatus, 30000);
    
    // Initialize data type toggle
    initializeDataTypeToggle();
    
    // Initialize dropdown functionality
    initializeDropdowns();
    
    // Add modal event handlers to prevent backdrop issues
    $('#issueModal').on('show.bs.modal', function (e) {
        // Clean up any existing backdrops first
        $('.modal-backdrop').remove();
        // Ensure body has proper modal classes
        $('body').addClass('modal-open');
    });
    
    $('#issueModal').on('shown.bs.modal', function (e) {
        // Ensure backdrop is properly positioned after modal is shown
        $('.modal-backdrop').css({
            'z-index': '1040',
            'position': 'fixed',
            'top': '0',
            'left': '0',
            'width': '100vw',
            'height': '100vh'
        });
    });

    $('#issueModal').on('hidden.bs.modal', function (e) {
        // Clean up after modal closes
        $('body').removeClass('modal-open');
        $('.modal-backdrop').remove();
        // Ensure no modal-open class remains on body
        setTimeout(() => {
            $('body').removeClass('modal-open');
            $('.modal-backdrop').remove();
        }, 300);
    });
    
    // Add some debug info on page load
    console.log('Page loaded');
    const toggles = document.querySelectorAll('.toggle-switch');
    console.log(`Found ${toggles.length} toggle switches`);
    
    toggles.forEach((toggle, index) => {
        console.log(`Toggle ${index}:`, toggle);
    });
});  // Close the DOMContentLoaded event handler

// Initialize dropdown functionality  
function initializeDropdowns() {
    console.log('Initializing dropdowns...');
    
    // Handle dropdown toggle clicks
    document.querySelectorAll('.dropdown-toggle').forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const dropdown = this.nextElementSibling;
            const isOpen = dropdown.classList.contains('show');
            
            // Close all other dropdowns
            document.querySelectorAll('.dropdown-menu').forEach(menu => {
                menu.classList.remove('show');
            });
            
            // Toggle current dropdown
            if (!isOpen) {
                dropdown.classList.add('show');
            }
            
            console.log('Dropdown toggled:', this.id, 'Now open:', !isOpen);
        });
    });
    
    // Handle dropdown item clicks
    document.querySelectorAll('.dropdown-item').forEach(item => {
        item.addEventListener('click', function(e) {
            // Get the onclick attribute
            const onclickAttr = this.getAttribute('onclick');
            const href = this.getAttribute('href');
            
            if (onclickAttr) {
                // If there's an onclick handler, prevent default and execute it
                e.preventDefault();
                e.stopPropagation();
                
                console.log('Executing onclick:', onclickAttr);
                try {
                    eval(onclickAttr);
                } catch (error) {
                    console.error('Error executing onclick:', error);
                }
            } else if (href && href !== '#') {
                // If there's a valid href but no onclick, allow normal navigation
                console.log('Following link:', href);
                // Don't prevent default - let the browser handle the navigation
                e.stopPropagation(); // Still stop propagation to close dropdown
            } else {
                // No onclick and no valid href, prevent default
                e.preventDefault();
                e.stopPropagation();
            }
            
            // Close the dropdown
            const dropdown = this.closest('.dropdown-menu');
            if (dropdown) {
                dropdown.classList.remove('show');
            }
        });
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.dropdown')) {
            document.querySelectorAll('.dropdown-menu').forEach(menu => {
                menu.classList.remove('show');
            });
        }
    });
    
    console.log('Dropdowns initialized');
}