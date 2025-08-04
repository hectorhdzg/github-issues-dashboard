// GitHub Issues Dashboard JavaScript
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
    const rows = Array.from(table.getElementsByTagName('tr')).slice(1); // Skip header
    const state = pageStates[repoId];
    
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
    
    if (state.totalPages <= 1) {
        controls.style.display = 'none';
        return;
    } else {
        controls.style.display = 'flex';
    }
    
    // Update info
    const startItem = (state.currentPage - 1) * itemsPerPage + 1;
    const endItem = Math.min(state.currentPage * itemsPerPage, state.filteredItems);
    document.getElementById('page-info-' + repoId).textContent = 
        `Showing ${startItem}-${endItem} of ${state.filteredItems} issues`;
    
    // Update buttons
    document.getElementById('prev-btn-' + repoId).disabled = state.currentPage === 1;
    document.getElementById('next-btn-' + repoId).disabled = state.currentPage === state.totalPages;
    
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
    // Hide intro page
    const introPage = document.getElementById('intro-page');
    if (introPage) {
        introPage.classList.add('hidden');
    }
    
    // Hide all repo sections and remove active class
    document.querySelectorAll('.repo-section').forEach(section => {
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
            newUrl.searchParams.set('state', 'open'); // Default to open issues only when no state specified
        }
        
        window.history.replaceState({}, '', newUrl);
        
        // Close the dropdown menu after selection
        $('.dropdown-menu').dropdown('hide');
        
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
    // Show intro page
    const introPage = document.getElementById('intro-page');
    if (introPage) {
        introPage.classList.remove('hidden');
    }
    
    // Hide all repo sections and remove active class
    document.querySelectorAll('.repo-section').forEach(section => {
        section.classList.remove('active');
    });
    document.querySelectorAll('.repo-header').forEach(header => {
        header.classList.remove('active');
    });
    document.querySelectorAll('.dropdown-item').forEach(link => {
        link.classList.remove('active');
    });
    
    // Hide active repo indicator
    const indicator = document.getElementById('active-repo-indicator');
    // Clear URL parameter
    const newUrl = new URL(window.location);
    newUrl.searchParams.delete('repo');
    window.history.replaceState({}, '', newUrl);
    
    activeRepoId = null;
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
    
    // Wait a moment then show the modal without backdrop issues
    setTimeout(() => {
        $('#issueModal').modal({
            backdrop: false,  // Disable backdrop entirely
            keyboard: true,
            focus: true,
            show: true
        });
    }, 100);
}

// Function to open pull request modal
function openPullRequestModal(modalData) {
    console.log('Opening PR modal with data:', modalData);
    
    // Store current PR data
    currentModalIssue = {
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
    
    // Update modal title and type indicator
    document.getElementById('issueModalLabel').innerHTML = '<i class="fas fa-code-branch"></i> Pull Request Details';
    
    // Populate modal fields
    document.getElementById('modal-issue-number').textContent = '#' + modalData.number;
    document.getElementById('modal-github-link').href = modalData.htmlUrl;
    document.getElementById('modal-issue-title').textContent = modalData.title;
    
    // Populate PR body/description
    const bodyElement = document.getElementById('modal-issue-body');
    if (modalData.body && modalData.body.trim()) {
        bodyElement.textContent = modalData.body;
        bodyElement.style.color = '#333';
    } else {
        bodyElement.textContent = 'No description provided.';
        bodyElement.style.color = '#999';
        bodyElement.style.fontStyle = 'italic';
    }
    
    // Populate PR-specific information
    populatePRAuthor(modalData.author);
    populatePRReviewers(modalData.reviewers);
    populatePRStatus(modalData.status, modalData.draft, modalData.merged);
    populatePRBranches(modalData.baseRef, modalData.headRef);
    
    // Populate common information for PRs
    populatePRLabels(modalData.labels);
    populatePRMentions(modalData.mentions);
    
    // Set comments
    document.getElementById('modal-comments').value = modalData.comments || '';
    
    // Hide save button for PRs (they're read-only for now)
    const saveBtn = document.getElementById('modal-save-btn');
    saveBtn.style.display = 'none';
    
    // Ensure any existing modal is properly closed first
    $('#issueModal').modal('hide');
    
    // Wait a moment then show the modal without backdrop issues
    setTimeout(() => {
        $('#issueModal').modal({
            backdrop: false,  // Disable backdrop entirely
            keyboard: true,
            focus: true,
            show: true
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
    
    // Navigate to new URL
    window.location.href = window.location.pathname + '?' + currentParams.toString();
}

function toggleDataType(dataType) {
    // Get current URL parameters
    const currentParams = new URLSearchParams(window.location.search);
    
    // Set the data type parameter
    currentParams.set('type', dataType);
    
    // Navigate to new URL
    window.location.href = window.location.pathname + '?' + currentParams.toString();
}

// Initialize data type toggle buttons based on current state
function initializeDataTypeToggle() {
    const currentParams = new URLSearchParams(window.location.search);
    const currentDataType = currentParams.get('type') || 'issues';
    
    // Update button states
    document.querySelectorAll('.btn-toggle-data-type').forEach(btn => {
        btn.classList.remove('active');
    });
    
    const activeButton = document.getElementById(currentDataType + '-toggle');
    if (activeButton) {
        activeButton.classList.add('active');
    }
}

// Document ready event handler
document.addEventListener('DOMContentLoaded', function() {
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
        // Ensure backdrop doesn't interfere
        $('body').addClass('modal-open');
    });
    
    $('#issueModal').on('hidden.bs.modal', function (e) {
        // Clean up after modal closes
        $('body').removeClass('modal-open');
        $('.modal-backdrop').remove();
    });
    
    // Check if there's a selected repo from template variable
    const selectedRepo = (typeof selectedRepoFromTemplate !== 'undefined') ? selectedRepoFromTemplate : '';
    if (selectedRepo && selectedRepo.trim() !== '') {
        // Convert repo name to repo ID format
        const selectedRepoId = selectedRepo.replace('/', '-').replace(/\./g, '-');
        
        // Try to find and select the repository
        const repoSection = document.getElementById('repo-' + selectedRepoId);
        if (repoSection) {
            setActiveRepo(selectedRepoId);
            return; // Exit early if we found and selected the repo
        }
    }
    
    // If no repo selected, ensure intro page is visible
    const introPage = document.getElementById('intro-page');
    if (introPage) {
        introPage.classList.remove('hidden');
    }
    
    // Add some debug info on page load
    console.log('Page loaded');
    const toggles = document.querySelectorAll('.toggle-switch');
    console.log(`Found ${toggles.length} toggle switches`);
    
    toggles.forEach((toggle, index) => {
        console.log(`Toggle ${index}:`, toggle);
    });
});

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
            e.preventDefault();
            e.stopPropagation();
            
            // Get the onclick attribute and execute it
            const onclickAttr = this.getAttribute('onclick');
            if (onclickAttr) {
                console.log('Executing onclick:', onclickAttr);
                try {
                    eval(onclickAttr);
                } catch (error) {
                    console.error('Error executing onclick:', error);
                }
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
