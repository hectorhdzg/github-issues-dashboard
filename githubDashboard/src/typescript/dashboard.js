"use strict";
// TypeScript Dashboard Application
// This will replace the broken spa.js with proper type safety
Object.defineProperty(exports, "__esModule", { value: true });
class DashboardApp {
    state;
    constructor() {
        this.state = {
            dataType: 'issues',
            showState: 'all',
            selectedRepo: '',
            repositories: [],
            cache: new Map(),
            loading: false
        };
        this.init();
    }
    init() {
        console.log('Dashboard TypeScript app initializing...');
        this.setupEventListeners();
        this.loadDashboardData();
    }
    setupEventListeners() {
        // Add event listeners here
        document.addEventListener('DOMContentLoaded', () => {
            console.log('DOM loaded, app ready');
        });
    }
    async loadDashboardData() {
        this.setLoading(true);
        try {
            console.log('Loading dashboard data...');
            // Basic implementation to get the app working
            this.setLoading(false);
        }
        catch (error) {
            console.error('Error loading dashboard data:', error);
            this.setLoading(false);
        }
    }
    setLoading(loading) {
        this.state.loading = loading;
        const loadingElement = document.getElementById('loading');
        if (loadingElement) {
            loadingElement.style.display = loading ? 'block' : 'none';
        }
    }
}
// Initialize the app
new DashboardApp();
//# sourceMappingURL=dashboard.js.map