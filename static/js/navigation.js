// Global navigation functions for all pages
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

// Make it globally available
window.handleHomeNavigation = handleHomeNavigation;
