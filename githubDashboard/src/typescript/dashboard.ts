// TypeScript Dashboard Application
// This will replace the broken spa.js with proper type safety

interface Repository {
    name: string;
    full_name: string;
    open_issues: number;
    closed_issues: number;
    total_issues: number;
}

interface Issue {
    id: number;
    title: string;
    state: string;
    repository_name: string;
    labels: string[];
    created_at: string;
    updated_at: string;
    url: string;
}

interface AppState {
    dataType: 'issues' | 'prs';
    showState: 'all' | 'open' | 'closed';
    selectedRepo: string;
    repositories: Repository[];
    cache: Map<string, any>;
    loading: boolean;
}

class DashboardApp {
    private state: AppState;

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

    private init(): void {
        console.log('Dashboard TypeScript app initializing...');
        this.setupEventListeners();
        this.loadDashboardData();
    }

    private setupEventListeners(): void {
        // Add event listeners here
        document.addEventListener('DOMContentLoaded', () => {
            console.log('DOM loaded, app ready');
        });
    }

    private async loadDashboardData(): Promise<void> {
        this.setLoading(true);
        
        try {
            console.log('Loading dashboard data...');
            // Basic implementation to get the app working
            this.setLoading(false);
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.setLoading(false);
        }
    }

    private setLoading(loading: boolean): void {
        this.state.loading = loading;
        const loadingElement = document.getElementById('loading');
        if (loadingElement) {
            loadingElement.style.display = loading ? 'block' : 'none';
        }
    }
}

// Initialize the app
new DashboardApp();