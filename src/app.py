#!/usr/bin/env python3
"""
GitHub Issues Dashboard Web Application
Serves the dashboard UI and communicates with the separate sync service
"""

import os
import logging
import html
import re
from flask import Flask, render_template, render_template_string, jsonify, request, redirect, url_for
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote, quote
import uuid

# Import HTTP client for sync service communication (optional at startup)
try:
    import requests
except Exception:
    requests = None

# Azure deployment configuration
IS_AZURE = bool(os.environ.get('WEBSITE_SITE_NAME'))

# On Azure with WEBSITE_RUN_FROM_PACKAGE, wwwroot is read-only. Use /home/site/data.
if IS_AZURE:
    default_data_dir = '/home/site/data'
else:
    default_data_dir = os.path.join(os.getcwd(), 'data')

# Resolve paths relative to this file
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Resolve database path and data directory
DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(default_data_dir, 'github_issues.db'))
DATA_DIR = os.path.dirname(DATABASE_PATH)

# Ensure data directory exists (should be writable: /home/site/data on Azure)
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception as e:
    # Log later once logger is configured; for early init, just print to stderr as fallback
    try:
        import sys
        print(f"Warning: failed to ensure data dir {DATA_DIR}: {e}", file=sys.stderr)
    except Exception:
        pass

# Load environment variables from .env file (for local development)
try:
    from dotenv import load_dotenv
    if not IS_AZURE:  # Only load .env in local development
        load_dotenv()
except ImportError:
    pass  # dotenv not available, continue without it

# Import timezone support with fallback
try:
    import pytz
    PACIFIC_TZ = pytz.timezone("America/Los_Angeles")
except ImportError:
    # Fallback to UTC for testing
    PACIFIC_TZ = timezone.utc

# Azure Monitor OpenTelemetry SDK imports (commented for testing)
# from azure.monitor.opentelemetry import configure_azure_monitor
# from opentelemetry import trace, metrics

# Define trace and metrics as dummy objects for testing
class DummyTrace:
    def get_tracer(self, name):
        return DummyTracer()
    
    class Status:
        def __init__(self, status_code, message):
            pass
    
    class StatusCode:
        OK = "OK"
        ERROR = "ERROR"

class DummyTracer:
    def start_as_current_span(self, name):
        return DummySpan()

class DummySpan:
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def set_status(self, status):
        pass
    
    def set_attribute(self, key, value):
        pass

class DummyMeter:
    def create_counter(self, name, description=None):
        return DummyCounter()
    
    def create_histogram(self, name, description=None):
        return DummyHistogram()

class DummyCounter:
    def add(self, value, attributes=None):
        pass

class DummyHistogram:
    def record(self, value, attributes=None):
        pass

class DummyMetrics:
    def get_meter(self, name):
        return DummyMeter()

# Initialize dummy telemetry
trace = DummyTrace()
metrics = DummyMetrics()

# Simple HTTP client for sync service communication
class SyncServiceClient:
    def __init__(self, base_url):
        self.base_url = base_url
        
    def health_check(self):
        if requests is None:
            return {"success": False, "error": "requests not available"}
        try:
            response = requests.get(f"{self.base_url}/health")
            if response.status_code == 200:
                return response.json()
            return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_sync_status(self):
        if requests is None:
            return {"success": False, "error": "requests not available"}
        try:
            response = requests.get(f"{self.base_url}/api/sync/status")
            if response.status_code == 200:
                return response.json()
            return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_issues(self, repo=None, limit=1000, **kwargs):
        if requests is None:
            return {"success": False, "error": "requests not available", "data": []}
        try:
            params = {'limit': limit}
            if repo:
                params['repo'] = repo
            response = requests.get(f"{self.base_url}/api/data/issues", params=params)
            if response.status_code == 200:
                return response.json()
            return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_prs(self, repo=None, limit=1000, **kwargs):
        if requests is None:
            return {"success": False, "error": "requests not available", "data": []}
        try:
            params = {'limit': limit}
            if repo:
                params['repo'] = repo
            response = requests.get(f"{self.base_url}/api/data/prs", params=params)
            if response.status_code == 200:
                return response.json()
            return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_repositories(self):
        if requests is None:
            return {"success": False, "error": "requests not available", "repositories": []}
        try:
            response = requests.get(f"{self.base_url}/api/data/repositories")
            if response.status_code == 200:
                return response.json()
            return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def start_sync(self):
        if requests is None:
            return {"success": False, "error": "requests not available"}
        try:
            response = requests.post(f"{self.base_url}/api/sync/start")
            if response.status_code == 200:
                return response.json()
            return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_queue_status(self):
        """Get queue status from sync service"""
        if requests is None:
            return {"success": False, "error": "requests not available"}
        try:
            response = requests.get(f"{self.base_url}/api/queue/status")
            if response.status_code == 200:
                return response.json()
            return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_auth_status(self):
        """Get authentication status from sync service"""
        if requests is None:
            return {"success": False, "error": "requests not available"}
        try:
            response = requests.get(f"{self.base_url}/api/auth/status")
            if response.status_code == 200:
                return response.json()
            return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_dashboard_data(self):
        """Get comprehensive dashboard data by combining multiple API calls"""
        try:
            # Get all data from sync service
            repositories_resp = self.get_repositories()
            issues_resp = self.get_issues()
            prs_resp = self.get_prs()
            sync_status = self.get_sync_status()
            
            if not repositories_resp.get('success') or not issues_resp.get('success') or not prs_resp.get('success'):
                return {"success": False, "error": "Failed to get data from sync service"}
            
            repositories = repositories_resp.get('repositories', [])
            issues = issues_resp.get('data', [])
            prs = prs_resp.get('data', [])
            
            # Organize data by repository
            repo_data = {}
            for repo in repositories:
                repo_data[repo] = {
                    'issues': [issue for issue in issues if issue.get('repo') == repo],
                    'prs': [pr for pr in prs if pr.get('repo') == repo],
                    'open_issues': [issue for issue in issues if issue.get('repo') == repo and issue.get('state') == 'open'],
                    'closed_issues': [issue for issue in issues if issue.get('repo') == repo and issue.get('state') == 'closed'],
                    'open_prs': [pr for pr in prs if pr.get('repo') == repo and pr.get('state') == 'open'],
                    'closed_prs': [pr for pr in prs if pr.get('repo') == repo and pr.get('state') == 'closed']
                }
            
            return {
                'success': True,
                'repositories': repositories,
                'repo_data': repo_data,
                'sync_status': sync_status
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

# Initialize sync service client
sync_client = None

def get_sync_client_instance():
    """Get or create sync service client"""
    global sync_client
    if sync_client is None:
        if IS_AZURE:
            # In Azure, sync service runs on the same host/port
            sync_service_url = f"http://localhost:{os.environ.get('PORT', 8000)}"
        else:
            # Local development uses separate service
            sync_service_url = os.environ.get('SYNC_SERVICE_URL', 'http://127.0.0.1:5001')
        sync_client = SyncServiceClient(base_url=sync_service_url)
    return sync_client

def _get_sdk_type_from_repo_name(repo_name):
    """Get SDK type from repository name using enhanced logic"""
    repo_lower = repo_name.lower()
    
    # Browser-specific classifications
    if ('applicationinsights-js' in repo_lower and 'node.js' not in repo_lower):
        return 'browser'
    # Node.js/JavaScript server-side
    elif ('azure-sdk-for-js' in repo_lower or
          'applicationinsights-node.js' in repo_lower or
          'opentelemetry-js-contrib' in repo_lower or
          ('opentelemetry-js' in repo_lower and 'contrib' not in repo_lower)):
        return 'nodejs'
    # Python
    elif ('azure-sdk-for-python' in repo_lower or
          'opentelemetry-python' in repo_lower):
        return 'python'
    # .NET
    elif ('applicationinsights-dotnet' in repo_lower or
          'opentelemetry-dotnet' in repo_lower):
        return 'dotnet'
    # Java
    elif ('applicationinsights-java' in repo_lower or
          'opentelemetry-java' in repo_lower):
        return 'java'
    
    return None  # Unknown type

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask application configuration
app = Flask(__name__, 
            template_folder='../templates',
            static_folder='../static')
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Configure trace and metrics
app_tracer = trace.get_tracer(__name__)
app_meter = metrics.get_meter(__name__)

# Metrics
page_views = app_meter.create_counter("page_views", "Number of page views")
api_calls = app_meter.create_counter("api_calls", "Number of API calls")
response_time = app_meter.create_histogram("response_time", "Response time in seconds")

def get_github_data():
    """Get GitHub data from sync service"""
    client = get_sync_client_instance()
    
    try:
        # Get dashboard data from sync service
        dashboard_data = client.get_dashboard_data()
        
        if not dashboard_data.get('success'):
            logger.error(f"Failed to get dashboard data: {dashboard_data.get('error', 'Unknown error')}")
            return {
                'repositories': [],
                'repo_data': {},
                'sync_status': {
                    'success': False,
                    'service_available': False,
                    'error': dashboard_data.get('error', 'Sync service unavailable')
                }
            }
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Error getting GitHub data: {e}")
        return {
            'repositories': [],
            'repo_data': {},
            'sync_status': {
                'success': False,
                'service_available': False,
                'error': str(e)
            }
        }

def get_dashboard_metrics(github_data):
    """Calculate dashboard metrics from GitHub data"""
    try:
        repo_data = github_data.get('repo_data', {})
        
        metrics = {
            'total_open_issues': 0,
            'total_closed_issues': 0,
            'total_open_prs': 0,
            'total_closed_prs': 0,
            'total_merged_prs': 0,
            'by_repo': {}
        }
        
        for repo, data in repo_data.items():
            open_issues = len(data.get('open_issues', []))
            closed_issues = len(data.get('closed_issues', []))
            open_prs = len(data.get('open_prs', []))
            closed_prs = data.get('closed_prs', [])
            merged_prs = len([pr for pr in closed_prs if pr.get('merged')])
            
            metrics['total_open_issues'] += open_issues
            metrics['total_closed_issues'] += closed_issues
            metrics['total_open_prs'] += open_prs
            metrics['total_closed_prs'] += len(closed_prs)
            metrics['total_merged_prs'] += merged_prs
            
            metrics['by_repo'][repo] = {
                'open_issues': open_issues,
                'closed_issues': closed_issues,
                'open_prs': open_prs,
                'closed_prs': len(closed_prs),
                'merged_prs': merged_prs
            }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error calculating dashboard metrics: {e}")
        return {
            'total_open_issues': 0,
            'total_closed_issues': 0,
            'total_open_prs': 0,
            'total_closed_prs': 0,
            'total_merged_prs': 0,
            'by_repo': {}
        }

def format_datetime_for_display(dt_str):
    """Format datetime string for display"""
    if not dt_str:
        return "Never"
    
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        
        # Calculate time difference
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"
    except:
        return dt_str

@app.route('/')
def dashboard():
    """Main dashboard route"""
    with app_tracer.start_as_current_span("dashboard_view") as span:
        try:
            page_views.add(1, {"page": "dashboard"})
            
            github_data = get_github_data()
            metrics = get_dashboard_metrics(github_data)
            
            span.set_attribute("repositories_count", len(github_data.get('repositories', [])))
            span.set_attribute("total_open_issues", metrics['total_open_issues'])
            span.set_attribute("service_available", github_data.get('sync_status', {}).get('service_available', False))
            
            # Prepare comprehensive sync_stats for template compatibility
            sync_status_data = github_data.get('sync_status', {})
            totals = sync_status_data.get('totals', {})
            
            sync_stats = {
                'in_progress': sync_status_data.get('sync_in_progress', False),
                'errors': 0 if not sync_status_data.get('error') else 1,  # Number of errors, not list
                'error_details': sync_status_data.get('error') if sync_status_data.get('error') else None,
                'last_sync_formatted': format_datetime_for_display(sync_status_data.get('last_sync')) if sync_status_data.get('last_sync') else 'Never',
                'total_issues': totals.get('open_issues', 0) + totals.get('closed_issues', 0),
                'total_prs': totals.get('open_prs', 0) + totals.get('closed_prs', 0) + totals.get('merged_prs', 0),
                'repository_count': len(github_data.get('repositories', [])),
                'repositories_count': len(github_data.get('repositories', [])),  # Alternative name used in templates
                'repo_stats': {},  # Repository-specific statistics
                'sync_in_progress': sync_status_data.get('sync_in_progress', False)
            }
            
            return render_template('dashboard.html',
                                   repositories=github_data.get('repositories', []),
                                   repo_data=github_data.get('repo_data', {}),
                                   metrics=metrics,
                                   sync_status=github_data.get('sync_status'),
                                   sync_stats=sync_stats,
                                   format_datetime=format_datetime_for_display)
        
        except Exception as e:
            logger.error(f"Error in dashboard route: {e}")
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            
            # Prepare comprehensive error sync_stats for template compatibility
            error_sync_stats = {
                'in_progress': False,
                'errors': 1,
                'error_details': str(e),
                'last_sync_formatted': 'Error',
                'total_issues': 0,
                'total_prs': 0,
                'repository_count': 0,
                'repositories_count': 0,
                'repo_stats': {},
                'sync_in_progress': False
            }
            
            return render_template('dashboard.html',
                                   repositories=[],
                                   repo_data={},
                                   metrics={'total_open_issues': 0, 'total_closed_issues': 0,
                                           'total_open_prs': 0, 'total_closed_prs': 0, 'total_merged_prs': 0,
                                           'by_repo': {}},
                                   sync_status={'success': False, 'error': str(e)},
                                   sync_stats=error_sync_stats,
                                   format_datetime=format_datetime_for_display)

@app.route('/sync')
def sync_page():
    """Sync status page"""
    with app_tracer.start_as_current_span("sync_page_view") as span:
        try:
            page_views.add(1, {"page": "sync"})
            
            client = get_sync_client_instance()
            sync_status = client.get_sync_status()
            queue_status = client.get_queue_status()
            auth_status = client.get_auth_status()
            
            span.set_attribute("sync_in_progress", sync_status.get('sync_in_progress', False))
            span.set_attribute("service_available", sync_status.get('success', False))
            
            # Prepare sync_stats from sync_status data
            sync_stats_data = {
                'in_progress': sync_status.get('sync_in_progress', False),
                'errors': 0,  # Count of errors
                'last_sync_formatted': format_datetime_for_display(sync_status.get('last_sync')),
                'total_issues': sync_status.get('totals', {}).get('open_issues', 0) + sync_status.get('totals', {}).get('closed_issues', 0),
                'total_prs': sync_status.get('totals', {}).get('open_prs', 0) + sync_status.get('totals', {}).get('closed_prs', 0),
                'repository_count': len(sync_status.get('by_repo', {}).get('issues', {})),
                'repo_stats': sync_status.get('by_repo', {}),
                'error_details': sync_status.get('error') if not sync_status.get('success', True) else None
            }
            
            return render_template('sync.html',
                                   sync_status=sync_status,
                                   sync_stats=sync_stats_data,
                                   queue_status=queue_status,
                                   auth_status=auth_status,
                                   format_datetime=format_datetime_for_display)
        
        except Exception as e:
            logger.error(f"Error in sync page: {e}")
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            return render_template('sync.html',
                                   sync_status={'success': False, 'error': str(e)},
                                   sync_stats={
                                       'in_progress': False,
                                       'errors': 1,
                                       'last_sync_formatted': 'Never',
                                       'total_issues': 0,
                                       'total_prs': 0,
                                       'repository_count': 0,
                                       'repo_stats': {},
                                       'error_details': str(e)
                                   },
                                   queue_status={'success': False},
                                   auth_status={'success': False},
                                   format_datetime=format_datetime_for_display)

@app.route('/stats')
def stats_page():
    """Statistics page"""
    with app_tracer.start_as_current_span("stats_page_view") as span:
        try:
            page_views.add(1, {"page": "stats"})
            
            github_data = get_github_data()
            metrics = get_dashboard_metrics(github_data)
            
            # Get detailed stats from sync service
            client = get_sync_client_instance()
            sync_status = client.get_sync_status()
            
            span.set_attribute("total_repositories", len(github_data.get('repositories', [])))
            span.set_attribute("total_issues", metrics['total_open_issues'] + metrics['total_closed_issues'])
            
            # Prepare sync_stats for stats template
            totals = sync_status.get('totals', {})
            sync_stats_data = {
                'repositories_count': len(github_data.get('repositories', [])),
                'total_issues': metrics['total_open_issues'] + metrics['total_closed_issues'],
                'sync_in_progress': sync_status.get('sync_in_progress', False),
                'errors': 0,
                'last_sync_formatted': format_datetime_for_display(sync_status.get('last_sync')),
                'total_open_issues': metrics['total_open_issues'],
                'total_closed_issues': metrics['total_closed_issues'],
                'new_issues_24h': 0,  # Would need additional calculation
                'updated_issues_24h': 0,  # Would need additional calculation
                'repo_stats': sync_status.get('by_repo', {}),
                'error_details': sync_status.get('error') if not sync_status.get('success', True) else None
            }
            
            return render_template('stats.html',
                                   metrics=metrics,
                                   sync_status=sync_status,
                                   sync_stats=sync_stats_data,
                                   repositories=github_data.get('repositories', []),
                                   repo_data=github_data.get('repo_data', {}),
                                   format_datetime=format_datetime_for_display)
        
        except Exception as e:
            logger.error(f"Error in stats page: {e}")
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            return render_template('stats.html',
                                   metrics={'total_open_issues': 0, 'total_closed_issues': 0,
                                           'total_open_prs': 0, 'total_closed_prs': 0, 'total_merged_prs': 0,
                                           'by_repo': {}},
                                   sync_status={'success': False, 'error': str(e)},
                                   sync_stats={
                                       'repositories_count': 0,
                                       'total_issues': 0,
                                       'sync_in_progress': False,
                                       'errors': 1,
                                       'last_sync_formatted': 'Never',
                                       'total_open_issues': 0,
                                       'total_closed_issues': 0,
                                       'new_issues_24h': 0,
                                       'updated_issues_24h': 0,
                                       'repo_stats': {},
                                       'error_details': str(e)
                                   },
                                   repositories=[],
                                   repo_data={},
                                   format_datetime=format_datetime_for_display)

@app.route('/repositories')
def repository_management_page():
    """Repository Management page"""
    with app_tracer.start_as_current_span("repository_management_page_view") as span:
        try:
            page_views.add(1, {"page": "repositories"})
            return render_template('repositories.html')
        except Exception as e:
            print(f"Error rendering repository management page: {e}")
            return render_template('repositories.html'), 500

@app.route('/repo-management')
def standalone_repo_management():
    """Standalone Repository Management page - completely independent"""
    try:
        # Simple standalone page with no dependencies on main app functionality
        return render_template('repo_management.html')
    except Exception as e:
        # Return minimal error page without main app dependencies
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Repository Management - Error</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; padding: 2rem; background: #f8f9fa;">
            <div style="max-width: 600px; margin: 0 auto; background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <h1 style="color: #dc3545;">Error Loading Repository Management</h1>
                <p>Error: {str(e)}</p>
                <p><a href="/repo-management" style="color: #0078d4;">Try Again</a></p>
            </div>
        </body>
        </html>
        """, 500

# API Routes
@app.route('/api/sync_status')
def api_sync_status():
    """API endpoint for sync status"""
    with app_tracer.start_as_current_span("api_sync_status") as span:
        try:
            api_calls.add(1, {"endpoint": "sync_status"})
            
            client = get_sync_client_instance()
            sync_status = client.get_sync_status()
            
            span.set_attribute("service_available", sync_status.get('success', False))
            
            return jsonify(sync_status)
        
        except Exception as e:
            logger.error(f"Error in sync status API: {e}")
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

@app.route('/api/sync_now', methods=['POST'])
def api_sync_now():
    """API endpoint to trigger sync"""
    with app_tracer.start_as_current_span("api_sync_now") as span:
        try:
            api_calls.add(1, {"endpoint": "sync_now"})
            
            client = get_sync_client_instance()
            result = client.start_sync()
            
            span.set_attribute("sync_started", result.get('success', False))
            
            return jsonify(result)
        
        except Exception as e:
            logger.error(f"Error starting sync: {e}")
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

@app.route('/api/data/issues')
def api_get_issues():
    """API endpoint to get issues data"""
    with app_tracer.start_as_current_span("api_get_issues") as span:
        try:
            api_calls.add(1, {"endpoint": "get_issues"})
            
            repo = request.args.get('repo')
            state = request.args.get('state')
            limit = request.args.get('limit', 100, type=int)
            offset = request.args.get('offset', 0, type=int)
            
            client = get_sync_client_instance()
            result = client.get_issues(repo=repo, state=state, limit=limit, offset=offset)
            
            span.set_attribute("issues_count", len(result.get('data', [])))
            
            return jsonify(result)
        
        except Exception as e:
            logger.error(f"Error getting issues: {e}")
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

@app.route('/api/data/prs')
def api_get_prs():
    """API endpoint to get pull requests data"""
    with app_tracer.start_as_current_span("api_get_prs") as span:
        try:
            api_calls.add(1, {"endpoint": "get_prs"})
            
            repo = request.args.get('repo')
            state = request.args.get('state')
            limit = request.args.get('limit', 100, type=int)
            offset = request.args.get('offset', 0, type=int)
            
            client = get_sync_client_instance()
            result = client.get_prs(repo=repo, state=state, limit=limit, offset=offset)
            
            span.set_attribute("prs_count", len(result.get('data', [])))
            
            return jsonify(result)
        
        except Exception as e:
            logger.error(f"Error getting PRs: {e}")
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

@app.route('/health')
def simple_health():
    """Simple health check endpoint for deployment scripts"""
    return jsonify({
        'status': 'healthy',
        'service': 'GitHub Issues Dashboard',
        'environment': 'azure' if IS_AZURE else 'local',
        'database_exists': os.path.exists(DATABASE_PATH),
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    try:
        client = get_sync_client_instance()
        service_health = client.health_check()
        
        return jsonify({
            'status': 'healthy',
            'service': 'GitHub Issues Dashboard Web App',
            'sync_service_status': service_health.get('status', 'unknown'),
            'sync_service_available': service_health.get('status') in ['healthy', 'mock'],
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

@app.route('/api/dashboard/debug')
def api_debug():
    """Debug endpoint to check what data is being processed"""
    client = get_sync_client_instance()
    github_data = client.get_dashboard_data()
    
    debug_info = {
        'github_data_keys': list(github_data.keys()) if isinstance(github_data, dict) else str(type(github_data)),
        'success': github_data.get('success', False),
        'repositories_count': len(github_data.get('repositories', [])),
        'repo_data_keys': list(github_data.get('repo_data', {}).keys()),
        'sample_repo_data': {}
    }
    
    # Get sample data from first repo
    repo_data = github_data.get('repo_data', {})
    if repo_data:
        first_repo = list(repo_data.keys())[0]
        first_repo_data = repo_data[first_repo]
        debug_info['sample_repo_data'] = {
            'repo_name': first_repo,
            'data_keys': list(first_repo_data.keys()),
            'issues_count': len(first_repo_data.get('issues', [])),
            'prs_count': len(first_repo_data.get('prs', [])),
            'first_issue_keys': list(first_repo_data.get('issues', [{}])[0].keys()) if first_repo_data.get('issues') else [],
            'first_pr_keys': list(first_repo_data.get('prs', [{}])[0].keys()) if first_repo_data.get('prs') else []
        }
    
    return jsonify(debug_info)

@app.route('/api/dashboard/data')
def api_dashboard_data():
    """API endpoint for dashboard data used by SPA"""
    with app_tracer.start_as_current_span("api_dashboard_data") as span:
        try:
            api_calls.add(1, {"endpoint": "dashboard_data"})
            
            # Get query parameters
            data_type = request.args.get('type', 'all')  # all, issues, prs
            state = request.args.get('state', 'open')    # open, closed
            repo = request.args.get('repo')              # specific repo or all
            
            logger.info(f"Dashboard API called: type={data_type}, state={state}, repo={repo}")
            
            # Get data directly from sync service
            client = get_sync_client_instance()
            
            # Calculate SDK counts based on repository names
            sdk_counts = {
                'nodejs': 0,
                'python': 0,
                'browser': 0,
                'dotnet': 0,
                'java': 0,
                'total': 0
            }
            
            # Get all items and collect repository names from actual data
            all_items = []
            all_repositories = set()  # Use set to avoid duplicates
            
            # Get issues if requested
            if data_type in ['all', 'issues']:
                issues_resp = client.get_issues(limit=10000)
                if issues_resp.get('success'):
                    issues = issues_resp.get('data', [])
                    logger.info(f"Got {len(issues)} issues from sync service")
                    
                    for issue in issues:
                        repo_name = issue.get('repo', '')
                        all_repositories.add(repo_name)  # Collect actual repository names
                        
                        # Count for SDK stats (count all issues regardless of filters)
                        repo_name = issue.get('repo', '')
                        all_repositories.add(repo_name)  # Collect actual repository names
                        
                        # Count for SDK stats using repository metadata or fallback to name-based classification
                        sdk_type = _get_sdk_type_from_repo_name(repo_name)
                        if sdk_type:
                            sdk_counts[sdk_type] += 1
                            sdk_counts['total'] += 1
                        
                        # Apply filters for final data
                        if repo and repo != 'all' and repo != repo_name:
                            continue
                        if state != 'all' and issue.get('state') != state:
                            continue
                        
                        # Add item type and fix repository field name
                        issue['item_type'] = 'issue'
                        issue['repository'] = repo_name
                        all_items.append(issue)
            
            # Get PRs if requested
            if data_type in ['all', 'prs']:
                prs_resp = client.get_prs(limit=10000)
                if prs_resp.get('success'):
                    prs = prs_resp.get('data', [])
                    logger.info(f"Got {len(prs)} PRs from sync service")
                    
                    for pr in prs:
                        repo_name = pr.get('repo', '')
                        all_repositories.add(repo_name)  # Collect actual repository names
                        
                        # Apply filters for final data
                        if repo and repo != 'all' and repo != repo_name:
                            continue
                        if state != 'all' and pr.get('state') != state:
                            continue
                        
                        # Add item type and fix repository field name
                        pr['item_type'] = 'pr'
                        pr['repository'] = repo_name
                        all_items.append(pr)
            
            logger.info(f"Final all_items count: {len(all_items)} (after filtering)")
            logger.info(f"Found repositories: {sorted(all_repositories)}")
            
            # Get sync stats
            sync_status = client.get_sync_status()

            # Get repositories metadata to enrich frontend grouping/classification
            repos_meta_resp = client.get_repositories()
            repositories_metadata = []
            if isinstance(repos_meta_resp, dict) and repos_meta_resp.get('success'):
                # Use metadata from sync service; optionally filter to repos present in data
                repositories_metadata = repos_meta_resp.get('repositories_metadata', []) or []
            
            # Sort by updated_at descending
            all_items.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
            
            # Convert repositories set to sorted list
            repositories_list = sorted(all_repositories)
            
            # Prepare response in expected SPA format
            result = {
                'success': True,
                'data': all_items,
                'repositories': repositories_list,        # Repositories from actual data
                'all_repositories': repositories_list,    # Same as repositories
                'repositories_metadata': repositories_metadata,
                'sdk_counts': sdk_counts,
                'sync_stats': {
                    'in_progress': sync_status.get('sync_in_progress', False),
                    'last_sync': sync_status.get('last_sync'),
                    'errors': sync_status.get('errors', 0)
                },
                'pagination': {
                    'count': len(all_items),
                    'total': len(all_items)
                }
            }
            
            span.set_attribute("data_type", data_type)
            span.set_attribute("state", state)
            span.set_attribute("repo", repo or "all")
            span.set_attribute("items_count", len(all_items))
            span.set_attribute("repositories_count", len(repositories_list))
            
            return jsonify(result)
        
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            return jsonify({
                'success': False,
                'error': str(e),
                'data': [],
                'repositories': [],
                'all_repositories': [],
                'sdk_counts': {
                    'nodejs': 0, 'python': 0, 'browser': 0, 'dotnet': 0, 'java': 0, 'total': 0
                },
                'sync_stats': {'in_progress': False, 'errors': 0},
                'pagination': {'count': 0, 'total': 0}
            }), 500

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('dashboard.html',
                          repositories=[],
                          repo_data={},
                          metrics={'total_open_issues': 0, 'total_closed_issues': 0,
                                  'total_open_prs': 0, 'total_closed_prs': 0, 'total_merged_prs': 0,
                                  'by_repo': {}},
                          sync_status={'success': False, 'error': 'Page not found'},
                          sync_stats={
                              'in_progress': False,
                              'errors': ['Page not found']
                          },
                          format_datetime=format_datetime_for_display), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('dashboard.html',
                          repositories=[],
                          repo_data={},
                          metrics={'total_open_issues': 0, 'total_closed_issues': 0,
                                  'total_open_prs': 0, 'total_closed_prs': 0, 'total_merged_prs': 0,
                                  'by_repo': {}},
                          sync_status={'success': False, 'error': 'Internal server error'},
                          sync_stats={
                              'in_progress': False,
                              'errors': ['Internal server error']
                          },
                          format_datetime=format_datetime_for_display), 500

if __name__ == '__main__':
    # Azure-specific configuration
    if IS_AZURE:
        # In Azure App Service, use PORT environment variable
        host = '0.0.0.0'
        port = int(os.environ.get('PORT', 8000))
        debug = False
        
        # Initialize database if it doesn't exist or if auto-init is requested
        auto_init = os.environ.get('AUTO_INIT_REPOS', 'false').lower() == 'true'
        if not os.path.exists(DATABASE_PATH) or auto_init:
            try:
                import sys
                sys.path.append(os.path.join(APP_ROOT, 'scripts'))
                from setup_deployment_repos import DeploymentRepositoryManager
                
                logger.info("Initializing database for Azure deployment...")
                repo_manager = DeploymentRepositoryManager(DATABASE_PATH)
                repo_manager.create_database_schema()
                repo_manager.populate_repositories(force_update=auto_init)
                
                # Get repository summary
                summary = repo_manager.get_repository_summary()
                logger.info(f"Database initialized with {summary['total_configured']} repositories")
                logger.info(f"Categories: {list(summary['by_category'].keys())}")
                
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
    else:
        # Local development configuration
        host = os.environ.get('FLASK_HOST', '127.0.0.1')
        port = int(os.environ.get('FLASK_PORT', 5000))
        debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting GitHub Issues Dashboard on {host}:{port}")
    logger.info(f"Environment: {'Azure' if IS_AZURE else 'Local'}")
    logger.info(f"Database path: {DATABASE_PATH}")
    logger.info(f"Sync service URL: {os.environ.get('SYNC_SERVICE_URL', 'http://127.0.0.1:5001')}")
    logger.info(f"Using mock sync service: {os.environ.get('USE_MOCK_SYNC', 'False')}")
    
    # Test sync service connection (only in local development)
    if not IS_AZURE:
        try:
            client = get_sync_client_instance()
            health = client.health_check()
            logger.info(f"Sync service status: {health.get('status', 'unknown')}")
        except Exception as e:
            logger.warning(f"Could not connect to sync service: {e}")
    
    app.run(host=host, port=port, debug=debug)
