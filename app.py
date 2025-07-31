#!/usr/bin/env python3
"""
Fixed Simple Flask server for GitHub Issues Dashboard
Serves the dashboard using existing cached data with proper navigation
"""

import os
import logging
import threading
import time
import requests
import schedule
import html
import re
from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
import sqlite3
import json
from datetime import datetime, timezone
from urllib.parse import unquote
import uuid

# Azure Monitor OpenTelemetry SDK imports
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace, metrics
import logging

# Set up logging to help debug telemetry issues
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Azure Monitor OpenTelemetry with auto-instrumentation
connection_string = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
if connection_string:
    print(f"🔧 Configuring Azure Monitor OpenTelemetry with connection string: {connection_string[:50]}...")
    logger.info(f"Azure Monitor connection string detected (length: {len(connection_string)})")
    
    try:
        # Configure Azure Monitor with additional settings for better reliability
        configure_azure_monitor(
            connection_string=connection_string,
            # Auto-instrumentation is enabled by default and includes:
            # - Flask (HTTP requests, responses)
            # - Requests (outbound HTTP calls)
            # - SQLite3 (database operations)
            # - Logging (application logs)
            # - And many more libraries automatically
            
            # Additional configuration for better telemetry
            enable_logging=True,
            # Set sampling rate to ensure data is sent
            sampling_ratio=1.0,
        )
        
        # Get tracer and meter for custom telemetry only
        tracer = trace.get_tracer(__name__)
        meter = metrics.get_meter(__name__)
        
        # Create custom metrics for business logic
        issue_counter = meter.create_counter(
            name="github_issues_processed",
            description="Number of GitHub issues processed",
            unit="1"
        )
        
        repo_counter = meter.create_counter(
            name="repository_sections_rendered",
            description="Number of repository sections rendered",
            unit="1"
        )
        
        print("✅ Azure Monitor OpenTelemetry configured with auto-instrumentation")
        logger.info("Azure Monitor OpenTelemetry successfully configured")
        
        # Test telemetry immediately
        with tracer.start_as_current_span("app_startup_test") as span:
            span.set_attribute("environment", "azure")
            span.set_attribute("app_version", "1.0")
            span.set_attribute("startup_timestamp", datetime.now().isoformat())
            print("🧪 Test telemetry span created during startup")
            logger.info("Startup telemetry test span created")
        
        # Test custom metric
        issue_counter.add(1, {"source": "startup_test"})
        print("🧪 Test metric sent during startup")
        logger.info("Startup telemetry test metric sent")
        
    except Exception as e:
        print(f"❌ Error configuring Azure Monitor OpenTelemetry: {e}")
        print(f"📋 Exception details: {type(e).__name__}: {str(e)}")
        logger.error(f"Failed to configure Azure Monitor OpenTelemetry: {e}", exc_info=True)
        tracer = None
        meter = None
        issue_counter = None
        repo_counter = None
else:
    print("⚠️ APPLICATIONINSIGHTS_CONNECTION_STRING not found, OpenTelemetry disabled")
    logger.warning("APPLICATIONINSIGHTS_CONNECTION_STRING environment variable not found")
    tracer = None
    meter = None
    issue_counter = None
    repo_counter = None

app = Flask(__name__)

# Configure session for MSAL
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', str(uuid.uuid4()))

# Azure AD Configuration for Certificate-Based User Authentication
AAD_CONFIG = {
    'CLIENT_ID': os.environ.get('AZURE_CLIENT_ID'),
    'CERTIFICATE_PATH': os.environ.get('AZURE_CERTIFICATE_PATH'),  # Path to certificate file
    'CERTIFICATE_THUMBPRINT': os.environ.get('AZURE_CERTIFICATE_THUMBPRINT'),  # Certificate thumbprint
    'TENANT_ID': os.environ.get('AZURE_TENANT_ID'),
    'AUTHORITY': f"https://login.microsoftonline.com/{os.environ.get('AZURE_TENANT_ID', 'common')}",
    'REDIRECT_PATH': '/auth/callback',
    'SCOPES': ['User.Read'],  # Basic profile information
    'ENABLED': bool(os.environ.get('ENABLE_USER_AUTHENTICATION', 'false').lower() == 'true' and 
                   os.environ.get('AZURE_CLIENT_ID') and 
                   os.environ.get('AZURE_CERTIFICATE_PATH') and 
                   os.environ.get('AZURE_CERTIFICATE_THUMBPRINT')),
    'ACCESS_CONTROL_MODE': os.environ.get('ACCESS_CONTROL_MODE', 'open'),  # 'open' or 'restricted'
    'AUTHORIZED_USERS': [email.strip() for email in os.environ.get('AUTHORIZED_USERS', '').split(',') if email.strip()]
}

# Initialize session
from flask_session import Session
Session(app)

def build_msal_app(cache=None, authority=None):
    """Build MSAL application with certificate-based authentication"""
    try:
        import msal
        
        # Use certificate-based authentication only
        print("🔐 Using certificate-based authentication")
        return msal.ConfidentialClientApplication(
            AAD_CONFIG['CLIENT_ID'],
            authority=authority or AAD_CONFIG['AUTHORITY'],
            client_credential={
                "private_key": open(AAD_CONFIG['CERTIFICATE_PATH'], 'r').read(),
                "thumbprint": AAD_CONFIG['CERTIFICATE_THUMBPRINT']
            },
            token_cache=cache
        )
    except ImportError:
        print("❌ MSAL library not found. Install with: pip install msal")
        return None
    except Exception as e:
        print(f"❌ MSAL setup failed: {e}")
        return None

def load_cache():
    """Load token cache from session"""
    try:
        import msal
        cache = msal.SerializableTokenCache()
        if session.get('token_cache'):
            cache.deserialize(session['token_cache'])
        return cache
    except ImportError:
        return None

def save_cache(cache):
    """Save token cache to session"""
    if cache and cache.has_state_changed:
        session['token_cache'] = cache.serialize()

def is_user_authorized(user_email):
    """Check if user is authorized to access the application"""
    if not AAD_CONFIG['ENABLED']:
        return True  # Skip authorization if authentication is disabled
    
    if AAD_CONFIG['ACCESS_CONTROL_MODE'] == 'open':
        return True  # Anyone with valid authentication can access
    
    # Restricted mode - check against authorized users list
    return user_email.lower() in [email.lower() for email in AAD_CONFIG['AUTHORIZED_USERS']]

def is_authenticated():
    """Check if user is authenticated"""
    if not AAD_CONFIG['ENABLED']:
        return True  # Skip authentication if disabled
    return 'user' in session

def get_current_user():
    """Get current authenticated user info"""
    if not AAD_CONFIG['ENABLED']:
        return {'name': 'Local User', 'email': 'local@example.com'}
    return session.get('user', {})

def login_required(f):
    """Decorator to require authentication"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            # If authentication is disabled, allow access
            if not AAD_CONFIG['ENABLED']:
                return f(*args, **kwargs)
            
            # Store the original URL to redirect back after login
            session['redirect_url'] = request.url
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def auth_required(f):
    """Decorator to strictly require authentication - redirects to unauthorized page if auth is disabled or user not logged in"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AAD_CONFIG['ENABLED']:
            # Authentication is disabled, redirect to unauthorized page
            return redirect(url_for('unauthorized'))
        
        if not is_authenticated():
            # Store the original URL to redirect back after login
            session['redirect_url'] = request.url
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# GitHub API Configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_API_BASE = 'https://api.github.com'

# Repositories to sync (same as in the database)
REPOSITORIES = [
    'Azure/azure-sdk-for-js',
    'Azure/azure-sdk-for-python',
    'microsoft/ApplicationInsights-js',
    'microsoft/ApplicationInsights-node.js',
    'microsoft/ApplicationInsights-node.js-native-metrics',
    'microsoft/DynamicProto-JS',
    'microsoft/applicationinsights-angularplugin-js',
    'microsoft/applicationinsights-react-js',
    'microsoft/applicationinsights-react-native',
    'microsoft/node-diagnostic-channel',
    'open-telemetry/opentelemetry-js',
    'open-telemetry/opentelemetry-js-contrib',
    'open-telemetry/opentelemetry-python',
    'open-telemetry/opentelemetry-python-contrib'
]

# Sync status tracking
sync_status = {
    'last_sync': None,
    'sync_in_progress': False,
    'next_sync': None,
    'total_synced': 0,
    'errors': []
}

def get_github_headers():
    """Get headers for GitHub API requests"""
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'GitHub-Issues-Dashboard/1.0'
    }
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    return headers

def extract_labels_with_colors(issue_data):
    """Extract labels with their names and colors from GitHub issue data"""
    labels = []
    if 'labels' in issue_data and issue_data['labels']:
        for label in issue_data['labels']:
            labels.append({
                'name': label.get('name', ''),
                'color': label.get('color', 'cccccc'),  # Default to gray if no color
                'description': label.get('description', '')
            })
    return json.dumps(labels)

def extract_assignees_with_info(issue_data):
    """Extract assignees with their login names from GitHub issue data"""
    assignees = []
    if 'assignees' in issue_data and issue_data['assignees']:
        for assignee in issue_data['assignees']:
            if assignee and 'login' in assignee:
                assignees.append({
                    'login': assignee['login'],
                    'avatar_url': assignee.get('avatar_url', ''),
                    'html_url': assignee.get('html_url', f"https://github.com/{assignee['login']}")
                })
    return json.dumps(assignees)

def extract_mentioned_handles(issue_body, pr_references_text=''):
    """Extract GitHub handles mentioned in issue body and PR references"""
    handles = set()
    
    # Pattern to match GitHub handles (@username)
    # Matches @username but not email addresses
    github_handle_pattern = r'(?:^|\s)@([a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38})(?=\s|$|[^\w-])'
    
    # Extract from issue body
    if issue_body:
        matches = re.findall(github_handle_pattern, issue_body, re.MULTILINE)
        handles.update(matches)
    
    # Extract from PR references text (if provided)
    if pr_references_text:
        matches = re.findall(github_handle_pattern, pr_references_text, re.MULTILINE)
        handles.update(matches)
    
    # Remove common false positives and system accounts
    filtered_handles = []
    exclude_handles = {
        'dependabot', 'github-actions', 'codecov', 'coveralls', 
        'renovate', 'greenkeeper', 'mergify', 'travis', 'appveyor'
    }
    
    for handle in handles:
        if handle.lower() not in exclude_handles and len(handle) > 1:
            filtered_handles.append(handle)
    
    return json.dumps(sorted(list(set(filtered_handles))))

def fetch_pr_content_for_mentions(repo, pr_number, headers):
    """Fetch PR content to extract mentions (with rate limiting consideration)"""
    try:
        pr_url = f"{GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}"
        response = requests.get(pr_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            pr_data = response.json()
            return pr_data.get('body', '')
        elif response.status_code == 404:
            # PR might not exist, could be an issue reference
            issue_url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{pr_number}"
            response = requests.get(issue_url, headers=headers, timeout=10)
            if response.status_code == 200:
                issue_data = response.json()
                return issue_data.get('body', '')
    except Exception as e:
        print(f"  ⚠️ Could not fetch PR/issue #{pr_number}: {e}")
    
    return ''

def update_database_schema():
    """Update database schema to add new columns if they don't exist"""
    try:
        # Try different database paths for local and Azure environments
        db_paths = [
            'github_issues.db',  # Local relative path
            '/home/site/wwwroot/github_issues.db',  # Azure Linux App Service path
            os.path.join(os.path.dirname(__file__), 'github_issues.db')  # Absolute path relative to script
        ]
        
        conn = None
        for db_path in db_paths:
            try:
                if os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    break
            except Exception:
                continue
        
        if not conn:
            print("❌ Could not connect to database for schema update")
            return False
        
        cursor = conn.cursor()
        
        # Check if new columns exist
        cursor.execute("PRAGMA table_info(issues)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add labels column if it doesn't exist
        if 'labels' not in columns:
            print("📋 Adding 'labels' column to issues table...")
            cursor.execute("ALTER TABLE issues ADD COLUMN labels TEXT DEFAULT '[]'")
            print("✅ Added 'labels' column")
        
        # Add mentioned_handles column if it doesn't exist
        if 'mentioned_handles' not in columns:
            print("📋 Adding 'mentioned_handles' column to issues table...")
            cursor.execute("ALTER TABLE issues ADD COLUMN mentioned_handles TEXT DEFAULT '[]'")
            print("✅ Added 'mentioned_handles' column")
        
        # Add assignees column if it doesn't exist (JSON array for multiple assignees)
        if 'assignees' not in columns:
            print("📋 Adding 'assignees' column to issues table...")
            cursor.execute("ALTER TABLE issues ADD COLUMN assignees TEXT DEFAULT '[]'")
            print("✅ Added 'assignees' column")
        
        # Add comments column if it doesn't exist (for user notes/comments)
        if 'comments' not in columns:
            print("📋 Adding 'comments' column to issues table...")
            cursor.execute("ALTER TABLE issues ADD COLUMN comments TEXT DEFAULT ''")
            print("✅ Added 'comments' column")
        
        # Add triage column if it doesn't exist (for triaging status)
        if 'triage' not in columns:
            print("📋 Adding 'triage' column to issues table...")
            cursor.execute("ALTER TABLE issues ADD COLUMN triage INTEGER DEFAULT 0")
            print("✅ Added 'triage' column")
        
        # Add priority column if it doesn't exist (for priority ranking)
        if 'priority' not in columns:
            print("📋 Adding 'priority' column to issues table...")
            cursor.execute("ALTER TABLE issues ADD COLUMN priority INTEGER DEFAULT -1")
            print("✅ Added 'priority' column")
        else:
            # Fix existing priority values that have incorrect default (2 -> -1)
            # Only update rows where priority is exactly 2 (the old incorrect default)
            cursor.execute("SELECT COUNT(*) FROM issues WHERE priority = 2")
            count_before = cursor.fetchone()[0]
            
            if count_before > 0:
                cursor.execute("UPDATE issues SET priority = -1 WHERE priority = 2")
                updated_rows = cursor.rowcount
                print(f"🔧 Fixed {updated_rows} issues with incorrect default priority (2 -> -1)")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error updating database schema: {e}")
        return False

def fetch_github_issues(repo, per_page=100):
    """Fetch issues from a GitHub repository"""
    print(f"🔄 Fetching issues from {repo}...")
    
    # Check rate limit status before starting
    if not GITHUB_TOKEN:
        print(f"📡 Using unauthenticated GitHub API for {repo} (60 requests/hour limit)")
    else:
        print(f"🔑 Using authenticated GitHub API for {repo} (5000 requests/hour limit)")
    
    # Define Azure monitoring labels for filtering
    azure_monitor_labels = [
        "Monitor - Distro",
        "Monitor - Exporter", 
        "Monitor - ApplicationInsights"
    ]
    
    all_issues = []
    seen_issue_numbers = set()  # Track duplicates when fetching by label
    
    # For Azure repos, fetch issues by each monitoring label separately
    if repo.startswith('Azure/'):
        print(f"  🏷️ Filtering Azure repo '{repo}' for monitoring labels: {', '.join(azure_monitor_labels)}")
        
        for label in azure_monitor_labels:
            page = 1
            while True:
                try:
                    url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
                    params = {
                        'state': 'all',
                        'per_page': per_page,
                        'page': page,
                        'sort': 'updated',
                        'direction': 'desc',
                        'labels': label  # Fetch issues with this specific label
                    }
                    
                    response = requests.get(url, headers=get_github_headers(), params=params)
                    
                    # Check rate limit headers
                    rate_limit_remaining = response.headers.get('X-RateLimit-Remaining', 'unknown')
                    if rate_limit_remaining != 'unknown':
                        print(f"  🚦 Rate limit remaining: {rate_limit_remaining}")
                    
                    response.raise_for_status()
                    
                    issues = response.json()
                    if not issues:
                        break  # No more issues for this label
                    
                    # Filter out pull requests and duplicates
                    for issue in issues:
                        if 'pull_request' not in issue and issue['number'] not in seen_issue_numbers:
                            all_issues.append(issue)
                            seen_issue_numbers.add(issue['number'])
                    
                    print(f"  📄 Label '{label}' page {page}: {len(issues)} issues ({len([i for i in issues if 'pull_request' not in i])} after PR filter)")
                    
                    page += 1
                    
                    # Limit pages for rate limiting
                    max_pages = 2 if not GITHUB_TOKEN else 3
                    if page > max_pages:
                        print(f"  ⚠️ Reached page limit ({max_pages}) for label '{label}' in {repo}")
                        break
                        
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 403:
                        rate_limit_remaining = e.response.headers.get('X-RateLimit-Remaining', '0')
                        if rate_limit_remaining == '0':
                            print(f"❌ Rate limit exceeded for {repo} while fetching label '{label}'. Try again later or add GITHUB_TOKEN.")
                            return all_issues  # Return what we have so far
                    print(f"❌ HTTP error fetching label '{label}' from {repo}: {e}")
                    break
                    
                except Exception as e:
                    print(f"❌ Error fetching label '{label}' from {repo}: {e}")
                    break
        
        print(f"✅ Fetched {len(all_issues)} total filtered issues from {repo}")
        return all_issues
    
    # For non-Azure repos, use the original logic
    else:
        print(f"  📋 Fetching all issues from non-Azure repo: {repo}")
        page = 1
        
        while True:
            try:
                # Get both open and closed issues
                url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
                params = {
                    'state': 'all',  # Include both open and closed
                    'per_page': per_page,
                    'page': page,
                    'sort': 'updated',
                    'direction': 'desc'
                }
            
                response = requests.get(url, headers=get_github_headers(), params=params)
                
                # Check rate limit headers
                rate_limit_remaining = response.headers.get('X-RateLimit-Remaining', 'unknown')
                rate_limit_reset = response.headers.get('X-RateLimit-Reset', 'unknown')
                
                if rate_limit_remaining != 'unknown':
                    print(f"  🚦 Rate limit remaining: {rate_limit_remaining}")
                
                response.raise_for_status()
                
                issues = response.json()
                if not issues:
                    break  # No more issues
                
                # Filter out pull requests (they have 'pull_request' key)
                issues = [issue for issue in issues if 'pull_request' not in issue]
                
                all_issues.extend(issues)
                print(f"  � Fetched page {page}: {len(issues)} issues")
                
                page += 1
                
                # Adjust page limit based on authentication status to respect rate limits
                if not GITHUB_TOKEN:
                    # Unauthenticated: limit to 2 pages per repo to stay within 60 req/hour
                    # With 14 repos, that's 28 requests, leaving room for other API calls
                    max_pages = 2
                else:
                    # Authenticated: can use more pages
                    max_pages = 5
                
                if page > max_pages:
                    print(f"  ⚠️ Reached page limit ({max_pages}) for {repo}")
                    break
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    rate_limit_remaining = e.response.headers.get('X-RateLimit-Remaining', '0')
                    if rate_limit_remaining == '0':
                        print(f"❌ Rate limit exceeded for {repo}. Try again later or add GITHUB_TOKEN.")
                        sync_status['errors'].append(f"Rate limit exceeded for {repo}")
                    else:
                        print(f"❌ Forbidden error for {repo}: {e}")
                        sync_status['errors'].append(f"Forbidden error for {repo}: {str(e)}")
                else:
                    print(f"❌ HTTP error fetching issues from {repo}: {e}")
                    sync_status['errors'].append(f"HTTP error fetching {repo}: {str(e)}")
                break
                
            except requests.exceptions.RequestException as e:
                print(f"❌ Network error fetching issues from {repo}: {e}")
                sync_status['errors'].append(f"Network error fetching {repo}: {str(e)}")
                break
                
            except Exception as e:
                print(f"❌ Unexpected error fetching {repo}: {e}")
                sync_status['errors'].append(f"Unexpected error for {repo}: {str(e)}")
                break
        
        print(f"✅ Fetched {len(all_issues)} total issues from {repo}")
        return all_issues

def update_database_with_issues(repo, issues):
    """Update the database with fetched issues"""
    if not issues:
        return 0
    
    try:
        # Try different database paths for local and Azure environments
        db_paths = [
            'github_issues.db',  # Local relative path
            '/home/site/wwwroot/github_issues.db',  # Azure Linux App Service path
            os.path.join(os.path.dirname(__file__), 'github_issues.db')  # Absolute path relative to script
        ]
        
        conn = None
        for db_path in db_paths:
            try:
                if os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    break
            except Exception:
                continue
        
        if not conn:
            print(f"❌ Could not connect to database for {repo}")
            return 0
        
        cursor = conn.cursor()
        updated_count = 0
        
        for issue in issues:
            try:
                # Extract issue data
                number = issue['number']
                title = issue['title']
                html_url = issue['html_url']
                assignee_login = issue['assignee']['login'] if issue['assignee'] else None
                created_at = issue['created_at']
                updated_at = issue['updated_at']
                body = issue.get('body', '')
                state = issue['state']
                last_fetched = datetime.now(timezone.utc).isoformat()
                
                # Extract labels with colors
                labels_json = extract_labels_with_colors(issue)
                
                # Extract assignees with info (new feature for multiple assignees)
                assignees_json = extract_assignees_with_info(issue)
                
                # Extract PR references for additional mention context
                pr_references = extract_pr_references(body, repo)
                pr_content = ''
                
                # Optionally fetch content from a few PR references for mentions
                # (Limited to avoid rate limiting - only first 2 PRs)
                if pr_references and len(pr_references) <= 2:
                    for pr_ref in pr_references[:2]:
                        if pr_ref.get('is_same_repo', False):
                            pr_num = pr_ref.get('number')
                            if pr_num:
                                pr_body = fetch_pr_content_for_mentions(repo, pr_num, get_github_headers())
                                pr_content += ' ' + pr_body
                
                # Extract mentioned GitHub handles
                mentioned_handles_json = extract_mentioned_handles(body, pr_content)
                
                # Insert or update issue
                cursor.execute('''
                    INSERT OR REPLACE INTO issues (
                        repo, number, title, html_url, assignee_login, 
                        created_at, updated_at, body, state, last_fetched,
                        labels, mentioned_handles, assignees
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    repo, number, title, html_url, assignee_login,
                    created_at, updated_at, body, state, last_fetched,
                    labels_json, mentioned_handles_json, assignees_json
                ))
                
                updated_count += 1
                
            except Exception as e:
                print(f"❌ Error updating issue #{issue.get('number', '?')} in {repo}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        print(f"✅ Updated {updated_count} issues for {repo}")
        return updated_count
        
    except Exception as e:
        print(f"❌ Database error for {repo}: {e}")
        sync_status['errors'].append(f"Database error for {repo}: {str(e)}")
        return 0

def detect_and_mark_closed_issues(repo, current_open_issues):
    """Detect issues that are no longer in the open issues list and mark them as closed"""
    try:
        # Try different database paths for local and Azure environments
        db_paths = [
            'github_issues.db',  # Local relative path
            '/home/site/wwwroot/github_issues.db',  # Azure Linux App Service path
            os.path.join(os.path.dirname(__file__), 'github_issues.db')  # Absolute path relative to script
        ]
        
        conn = None
        for db_path in db_paths:
            try:
                if os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    break
            except Exception:
                continue
        
        if not conn:
            print(f"❌ Could not connect to database for closed issue detection in {repo}")
            return 0
        
        cursor = conn.cursor()
        
        # Get all currently open issues in our database for this repo
        cursor.execute('''
            SELECT number FROM issues 
            WHERE repo = ? AND state = 'open'
        ''', (repo,))
        
        db_open_issues = {row[0] for row in cursor.fetchall()}
        
        # Get the issue numbers from the current GitHub open issues
        current_open_numbers = {issue['number'] for issue in current_open_issues}
        
        # Find issues that are in our database as open but not in current GitHub open issues
        closed_issues = db_open_issues - current_open_numbers
        
        closed_count = 0
        if closed_issues:
            print(f"🔒 Detected {len(closed_issues)} issues that are no longer open in {repo}")
            
            # Mark these issues as closed in our database
            for issue_number in closed_issues:
                cursor.execute('''
                    UPDATE issues 
                    SET state = 'closed', last_fetched = ?
                    WHERE repo = ? AND number = ? AND state = 'open'
                ''', (datetime.now(timezone.utc).isoformat(), repo, issue_number))
                
                if cursor.rowcount > 0:
                    closed_count += 1
                    print(f"  📝 Marked issue #{issue_number} as closed")
        
        conn.commit()
        conn.close()
        
        if closed_count > 0:
            print(f"✅ Marked {closed_count} issues as closed for {repo}")
        
        return closed_count
        
    except Exception as e:
        print(f"❌ Error detecting closed issues for {repo}: {e}")
        return 0

def detect_closed_issues_without_sync():
    """Detect closed issues by fetching current open issues from GitHub without updating database"""
    print("🔍 Detecting closed issues without full sync...")
    
    total_closed = 0
    
    try:
        for i, repo in enumerate(REPOSITORIES):
            print(f"\n📋 Checking repository {i+1}/{len(REPOSITORIES)}: {repo}")
            
            # Fetch current open issues from GitHub (without updating database)
            issues = fetch_github_issues(repo)
            
            # Detect and mark closed issues
            closed_count = detect_and_mark_closed_issues(repo, issues)
            total_closed += closed_count
            
            # Add small delay to be respectful
            if i < len(REPOSITORIES) - 1:
                time.sleep(1)
        
        print(f"\n🎉 Closed issue detection completed! Marked {total_closed} issues as closed across {len(REPOSITORIES)} repositories")
        return total_closed
        
    except Exception as e:
        print(f"❌ Error during closed issue detection: {e}")
        return 0

def sync_all_repositories():
    """Sync all configured repositories"""
    if sync_status['sync_in_progress']:
        print("🔄 Sync already in progress, skipping...")
        return
    
    print("🚀 Starting GitHub repositories sync...")
    sync_status['sync_in_progress'] = True
    sync_status['errors'] = []  # Clear previous errors
    
    total_updated = 0
    start_time = datetime.now(timezone.utc)
    
    try:
        # Add delay between repos to respect rate limits, especially for unauthenticated requests
        delay_between_repos = 2 if not GITHUB_TOKEN else 1
        
        for i, repo in enumerate(REPOSITORIES):
            if not sync_status['sync_in_progress']:  # Check if sync was cancelled
                break
                
            print(f"\n📋 Syncing repository {i+1}/{len(REPOSITORIES)}: {repo}")
            
            # Fetch issues from GitHub
            issues = fetch_github_issues(repo)
            
            # Detect and mark closed issues (issues that are no longer in the open list)
            closed_count = detect_and_mark_closed_issues(repo, issues)
            
            # Update database with current open issues
            updated_count = update_database_with_issues(repo, issues)
            total_updated += updated_count
            
            if closed_count > 0:
                print(f"  🔒 Marked {closed_count} issues as closed")
            
            # Add delay between repositories to be respectful to GitHub API
            if i < len(REPOSITORIES) - 1:  # Don't delay after the last repo
                print(f"  ⏱️ Waiting {delay_between_repos} seconds before next repository...")
                time.sleep(delay_between_repos)
        
        sync_status['last_sync'] = datetime.now(timezone.utc).isoformat()
        sync_status['total_synced'] = total_updated
        
        print(f"\n🎉 Sync completed! Updated {total_updated} issues across {len(REPOSITORIES)} repositories")
        
        if sync_status['errors']:
            print(f"⚠️ Encountered {len(sync_status['errors'])} errors during sync")
            for error in sync_status['errors']:
                print(f"   • {error}")
        
    except Exception as e:
        print(f"❌ Critical error during sync: {e}")
        sync_status['errors'].append(f"Critical sync error: {str(e)}")
    
    finally:
        sync_status['sync_in_progress'] = False
        
        # Calculate next sync time (24 hours from now)
        next_sync = datetime.now(timezone.utc).replace(hour=2, minute=0, second=0, microsecond=0)
        if next_sync <= datetime.now(timezone.utc):
            next_sync = next_sync.replace(day=next_sync.day + 1)
        sync_status['next_sync'] = next_sync.isoformat()

def start_sync_scheduler():
    """Start the background sync scheduler"""
    auth_status = "authenticated" if GITHUB_TOKEN else "unauthenticated"
    rate_limit = "5000 requests/hour" if GITHUB_TOKEN else "60 requests/hour"
    
    print(f"⏰ Starting sync scheduler (every 24 hours at 2:00 AM UTC)")
    print(f"🔑 GitHub API access: {auth_status} ({rate_limit})")
    
    # Update database schema if needed
    print("🔧 Checking database schema...")
    update_database_schema()
    
    try:
        # Schedule daily sync at 2:00 AM UTC to avoid peak hours
        schedule.every().day.at("02:00").do(sync_all_repositories)
        
        # Run initial sync check in a separate thread to avoid blocking import
        def check_and_run_initial_sync():
            try:
                time.sleep(2)  # Small delay to ensure app is fully loaded
                conn = sqlite3.connect('github_issues.db')
                cursor = conn.execute('SELECT MAX(last_fetched) FROM issues')
                last_fetch = cursor.fetchone()[0]
                conn.close()
                
                if not last_fetch:
                    print("📊 No sync data found, but skipping initial sync during startup")
                    print("💡 Visit /sync to trigger manual sync")
                else:
                    last_fetch_time = datetime.fromisoformat(last_fetch.replace('Z', '+00:00'))
                    hours_since = (datetime.now(timezone.utc) - last_fetch_time).total_seconds() / 3600
                    
                    if hours_since > 24:
                        print(f"📊 Data is {hours_since:.1f} hours old, sync recommended")
                        print("💡 Visit /sync to check sync status and trigger manual sync")
                    else:
                        print(f"📊 Data is {hours_since:.1f} hours old, sync not needed")
            except Exception as e:
                print(f"⚠️ Could not check sync status: {e}")
        
        # Start the initial check in a daemon thread
        threading.Thread(target=check_and_run_initial_sync, daemon=True).start()
        
        # Start the scheduler in a background daemon thread
        def run_scheduler():
            while True:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    print(f"⚠️ Scheduler error: {e}")
                    time.sleep(60)  # Continue despite errors
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        print("✅ Sync scheduler started successfully")
        
    except Exception as e:
        print(f"⚠️ Failed to start sync scheduler: {e}")
        print("💡 Sync functionality will be disabled")

def load_html_template():
    """Load the HTML template from file"""
    try:
        template_path = os.path.join(os.path.dirname(__file__), 'dashboard_template.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return """
<!DOCTYPE html>
<html>
<head>
    <title>GitHub Issues Dashboard</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        .error { color: red; background: #ffe6e6; padding: 20px; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="error">
        <h1>⚠️ Template Not Found</h1>
        <p>The dashboard template file is missing. Please ensure dashboard_template.html exists.</p>
    </div>
    {repo_sections}
</body>
</html>
"""

def get_last_sync_time():
    """Get the most recent sync time from the database"""
    try:
        # Try different database paths for local and Azure environments
        db_paths = [
            'github_issues.db',  # Local relative path
            '/home/site/wwwroot/github_issues.db',  # Azure Linux App Service path
            os.path.join(os.path.dirname(__file__), 'github_issues.db')  # Absolute path relative to script
        ]
        
        conn = None
        for db_path in db_paths:
            try:
                if os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    break
            except Exception:
                continue
        
        if not conn:
            return "No database found"
        
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(last_fetched) FROM issues')
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            # Parse the ISO timestamp and format it nicely
            last_sync = datetime.fromisoformat(result[0].replace('Z', '+00:00'))
            # Convert to local time for display
            local_time = last_sync.replace(tzinfo=timezone.utc).astimezone()
            return f"Last synced: {local_time.strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            return "No sync data available"
            
    except Exception as e:
        print(f"Error getting last sync time: {e}")
        return "Sync status unknown"

def get_state_button_text(state):
    """Get button text for state toggle"""
    if state == 'open':
        return 'Open'
    elif state == 'closed':
        return 'Closed'
    else:
        return 'Open'

def get_issues_from_db(state_filter='open'):
    """Get issues from database with optional state filtering"""
    # Create a custom span for database operations
    if tracer:
        with tracer.start_as_current_span("get_issues_from_db") as span:
            return _get_issues_from_db_internal(span, state_filter)
    else:
        return _get_issues_from_db_internal(None, state_filter)

def _get_issues_from_db_internal(span=None, state_filter='open'):
    """Internal function to get issues from database with telemetry"""
    try:
        if span:
            span.set_attribute("operation.type", "database_read")
            span.set_attribute("database.name", "github_issues.db")
        
        # Try different database paths for local and Azure environments
        db_paths = [
            'github_issues.db',  # Local relative path
            '/home/site/wwwroot/github_issues.db',  # Azure Linux App Service path
            os.path.join(os.path.dirname(__file__), 'github_issues.db')  # Absolute path relative to script
        ]
        
        conn = None
        for db_path in db_paths:
            try:
                if os.path.exists(db_path):
                    print(f"Trying to connect to database at: {db_path}")
                    conn = sqlite3.connect(db_path)
                    conn.row_factory = sqlite3.Row
                    if span:
                        span.set_attribute("database.path", db_path)
                    break
            except Exception as e:
                print(f"Failed to connect to database at {db_path}: {e}")
                if span:
                    span.record_exception(e)
                continue
        
        if conn is None:
            print("No database found. Creating sample data.")
            if span:
                span.set_attribute("data.source", "sample_data")
            return get_sample_issues()
        
        # SQLite operations are automatically instrumented by Azure Monitor
        cursor = conn.cursor()
        
        # Build the query based on state filter
        if state_filter == 'all':
            query = '''
                SELECT * FROM issues 
                ORDER BY created_at DESC
            '''
            cursor.execute(query)
        else:
            query = '''
                SELECT * FROM issues 
                WHERE state = ?
                ORDER BY created_at DESC
            '''
            cursor.execute(query, (state_filter,))
        
        if span:
            span.set_attribute("query.state_filter", state_filter)
        
        issues = []
        for row in cursor.fetchall():
            issue = dict(row)
            # Map repo to repository for compatibility
            issue['repository'] = issue['repo']
            
            # Parse labels JSON (with fallback for old records)
            try:
                if 'labels' in issue and issue['labels']:
                    issue['labels'] = json.loads(issue['labels'])
                else:
                    issue['labels'] = []
            except (json.JSONDecodeError, TypeError):
                issue['labels'] = []
            
            # Parse mentioned handles JSON (with fallback for old records)
            try:
                if 'mentioned_handles' in issue and issue['mentioned_handles']:
                    issue['mentioned_handles'] = json.loads(issue['mentioned_handles'])
                else:
                    issue['mentioned_handles'] = []
            except (json.JSONDecodeError, TypeError):
                issue['mentioned_handles'] = []
            
            # Parse assignees JSON (with fallback for old records)
            try:
                if 'assignees' in issue and issue['assignees']:
                    issue['assignees'] = json.loads(issue['assignees'])
                else:
                    issue['assignees'] = []
            except (json.JSONDecodeError, TypeError):
                issue['assignees'] = []
            
            # Ensure comments field exists (with fallback for old records)
            if 'comments' not in issue:
                issue['comments'] = ''
            elif issue['comments'] is None:
                issue['comments'] = ''
            
            issues.append(issue)
        
        conn.close()
        
        # Log telemetry for business metrics only
        issue_count = len(issues)
        print(f"Successfully loaded {issue_count} issues from database")
        
        if span:
            span.set_attribute("issues.count", issue_count)
            span.set_attribute("data.source", "database")
        
        # Custom business metric
        if issue_counter:
            issue_counter.add(issue_count, {"source": "database"})
        
        return issues
    except Exception as e:
        print(f"Error getting issues from database: {e}")
        if span:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
        return get_sample_issues()

def get_sample_issues():
    """Return sample issues when database is not available"""
    return [
        {
            'id': 1,
            'repository': 'Azure/azure-sdk-for-python',
            'repo': 'Azure/azure-sdk-for-python', 
            'number': 123,
            'title': 'Sample Issue - Database Not Available',
            'html_url': 'https://github.com/Azure/azure-sdk-for-python/issues/123',
            'state': 'open',
            'assignee_login': None,
            'created_at': '2025-01-01T00:00:00Z',
            'updated_at': '2025-01-01T00:00:00Z',
            'body': 'This is a sample issue displayed when the database is not available.',
            'labels': [{'name': 'sample', 'color': '00ff00', 'description': 'Sample label'}],
            'mentioned_handles': ['octocat'],
            'assignees': [],  # Empty array for sample issue
            'comments': '',  # Empty comments for sample issue
            'linked_pr': None,
            'last_fetched': '2025-01-01T00:00:00Z',
            'triage': 0,
            'priority': -1  # Correct default: "Not Set"
        }
    ]

def group_issues_by_repo(issues):
    """Group issues by repository"""
    repos = {}
    for issue in issues:
        repo = issue['repository']
        if repo not in repos:
            repos[repo] = []
        repos[repo].append(issue)
    return repos

def extract_pr_references(issue_body, repo_name):
    """Extract PR references from issue body text"""
    
    if not issue_body:
        return []
    
    pr_references = []
    
    # Pattern 1: Full GitHub PR URLs
    # Example: https://github.com/Azure/azure-sdk-for-python/pull/1234
    full_pr_pattern = r'https://github\.com/([^/]+)/([^/]+)/pull/(\d+)'
    full_matches = re.findall(full_pr_pattern, issue_body)
    
    for owner, repo, pr_number in full_matches:
        pr_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}"
        pr_references.append({
            'url': pr_url,
            'number': pr_number,
            'repo': f"{owner}/{repo}",
            'is_same_repo': f"{owner}/{repo}" == repo_name
        })
    
    # Pattern 2: Short PR references within the same repo
    # Pattern 2: Short references within the same repo
    # Example: #1234 (could be PR or issue)
    if repo_name:
        short_pr_pattern = r'(?:^|\s)#(\d+)(?:\s|$|[^\w])'
        short_matches = re.findall(short_pr_pattern, issue_body)
        
        for pr_number in short_matches:
            # Create a reference URL for the same repo (will link to PR, but could be issue)
            pr_url = f"https://github.com/{repo_name}/pull/{pr_number}"
            pr_references.append({
                'url': pr_url,
                'number': pr_number,
                'repo': repo_name,
                'is_same_repo': True
            })
    
    # Pattern 3: Text-based PR references (but not from full URLs)
    # Example: "PR 1234", "pull request #1234"
    # Note: We exclude "pull/1234" if it's part of a full GitHub URL
    
    # First, remove all full GitHub URLs from the text to avoid false positives
    cleaned_body = re.sub(r'https://github\.com/[^/]+/[^/]+/pull/\d+[^\s]*', '', issue_body)
    
    text_pr_patterns = [
        r'(?:PR|pr)\s*#?(\d+)',
        r'(?:pull request|Pull Request)\s*#?(\d+)',
        r'(?<!/)\bpull/(\d+)'  # pull/1234 but not if preceded by /
    ]
    
    for pattern in text_pr_patterns:
        matches = re.findall(pattern, cleaned_body, re.IGNORECASE)
        for pr_number in matches:
            if repo_name:
                pr_url = f"https://github.com/{repo_name}/pull/{pr_number}"
                pr_references.append({
                    'url': pr_url,
                    'number': pr_number,
                    'repo': repo_name,
                    'is_same_repo': True,
                    'is_text_reference': True
                })
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_references = []
    for ref in pr_references:
        if ref['url'] not in seen_urls:
            seen_urls.add(ref['url'])
            unique_references.append(ref)
    
    return unique_references

def format_pr_references(pr_references):
    """Format PR references for display in the dashboard"""
    if not pr_references:
        return 'None'
    
    formatted_refs = []
    for ref in pr_references:
        pr_number = ref['number']
        
        # Add indicators for different types of references
        indicators = []
        if ref.get('is_text_reference'):
            indicators.append('T')  # Text-based reference
        if not ref['is_same_repo']:
            indicators.append('E')  # External repository
        
        indicator_str = ''.join(indicators)
        if indicator_str:
            indicator_str = f"<sup>{indicator_str}</sup>"
        
        # Always display as #number, regardless of repository
        link_text = f"#{pr_number}{indicator_str}"
        
        formatted_refs.append(f'<a href="{ref["url"]}" target="_blank">{link_text}</a>')
    
    return ', '.join(formatted_refs)

def format_labels_for_display(labels):
    """Format labels with colors for display in the dashboard"""
    if not labels:
        return '<span class="text-muted">None</span>'
    
    formatted_labels = []
    for label in labels:
        name = html.escape(label.get('name', ''))
        color = label.get('color', 'cccccc')
        # Handle None description values properly
        description_raw = label.get('description', '') or ''
        description = html.escape(description_raw)
        
        # Calculate text color based on background color brightness
        # Convert hex to RGB and calculate brightness
        try:
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            text_color = '#000000' if brightness > 128 else '#ffffff'
        except:
            text_color = '#000000'
        
        title_text = f"title=\"{description}\"" if description else ""
        formatted_labels.append(
            f'<span class="badge" style="background-color: #{color}; color: {text_color}; margin-right: 4px;" {title_text}>{name}</span>'
        )
    
    return ''.join(formatted_labels)

def format_assignees_for_display(assignees, fallback_assignee=None):
    """Format multiple assignees for display in the dashboard"""
    # If we have the new assignees array, use it
    if assignees and len(assignees) > 0:
        formatted_assignees = []
        for assignee in assignees:
            login = assignee.get('login', '')
            if login:
                formatted_assignees.append(
                    f'<a href="https://github.com/{html.escape(login)}" target="_blank" class="assignee-link">@{html.escape(login)}</a>'
                )
        
        if formatted_assignees:
            return ', '.join(formatted_assignees)
    
    # Fallback to the old single assignee field for backwards compatibility
    if fallback_assignee:
        return f'<a href="https://github.com/{html.escape(fallback_assignee)}" target="_blank" class="assignee-link">@{html.escape(fallback_assignee)}</a>'
    
    return '<span class="text-muted">Unassigned</span>'

def format_mentions_for_display(mentioned_handles):
    """Format mentioned GitHub handles for display in the dashboard"""
    if not mentioned_handles:
        return '<span class="text-muted">None</span>'
    
    formatted_mentions = []
    for handle in mentioned_handles:
        formatted_mentions.append(
            f'<a href="https://github.com/{html.escape(handle)}" target="_blank" class="mention-link">@{html.escape(handle)}</a>'
        )
    
    return ', '.join(formatted_mentions)

def format_priority_text(priority):
    """Format priority value as display text"""
    priority_map = {
        -1: "Not Set",
        0: "0 - Critical",
        1: "1 - High", 
        2: "2 - Medium",
        3: "3 - Low",
        4: "4 - Minimal"
    }
    return priority_map.get(priority, "Unknown")

def format_triage_text(triage):
    """Format triage value as simple icon"""
    if triage:
        return '<i class="fas fa-check text-success" title="Triaged"></i>'
    else:
        return '<span class="text-muted" title="Not triaged">—</span>'

def get_repo_category(repo):
    """Determine the category of a repository for color coding"""
    if repo.startswith('open-telemetry/'):
        return 'opentelemetry'
    elif repo.startswith('Azure/'):
        return 'azure'
    elif repo.startswith('microsoft/'):
        return 'microsoft'
    else:
        return 'other'

def get_repo_color_class(repo):
    """Get CSS color class based on repository category"""
    category = get_repo_category(repo)
    color_classes = {
        'opentelemetry': 'otel-theme',     # Orange/Red theme for OpenTelemetry
        'azure': 'azure-theme',           # Blue theme for Azure
        'microsoft': 'microsoft-theme',   # Green theme for Microsoft
        'other': 'default-theme'          # Gray theme for others
    }
    return color_classes.get(category, 'default-theme')

def generate_repo_section(repo, issues, is_first=False, current_state='open'):
    """Generate HTML section for a repository"""
    # Determine language group
    if repo in ['Azure/azure-sdk-for-python', 'open-telemetry/opentelemetry-python', 'open-telemetry/opentelemetry-python-contrib']:
        language = 'Python'
        lang_class = 'python'
    elif repo in ['Azure/azure-sdk-for-js', 'open-telemetry/opentelemetry-js', 'open-telemetry/opentelemetry-js-contrib', 
                  'microsoft/ApplicationInsights-node.js', 'microsoft/ApplicationInsights-node.js-native-metrics', 
                  'microsoft/node-diagnostic-channel']:
        language = 'Node.js'
        lang_class = 'nodejs'
    else:
        language = 'Browser JavaScript'
        lang_class = 'browser-js'
    
    # Get color theme for this repository
    color_class = get_repo_color_class(repo)
    repo_category = get_repo_category(repo)
    
    # Add state-specific styling
    state_class = "closed-issues" if current_state == 'closed' else ""
    header_style = 'style="background-color: #4a4a4a; color: #e0e0e0;"' if current_state == 'closed' else ""
    
    repo_name = repo.split('/')[-1]
    repo_id = repo.replace('/', '-').replace('.', '-')
    issue_count = len(issues)
    
    # Set CSS classes for visibility - no repo is active by default
    active_class = ""
    
    # Generate issue rows
    issue_rows = ""
    for i, issue in enumerate(issues):  # Show ALL issues, pagination will handle display
        try:
            created_date = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))
            created_days_old = (datetime.now(timezone.utc) - created_date).days
            # New age classification: 0-14 days = recent (green), 15-30 days = medium (yellow), 
            # 31-60 days = old (red), 60+ days = stale (purple)
            if created_days_old <= 14:
                created_age_class = "recent"
            elif created_days_old <= 30:
                created_age_class = "medium"
            elif created_days_old <= 60:
                created_age_class = "old"
            else:
                created_age_class = "stale"
        except:
            created_age_class = "unknown"
        
        # Calculate age class for updated date
        try:
            if issue['updated_at']:
                updated_date = datetime.fromisoformat(issue['updated_at'].replace('Z', '+00:00'))
                updated_days_old = (datetime.now(timezone.utc) - updated_date).days
                # Same age classification for updated dates
                if updated_days_old <= 14:
                    updated_age_class = "recent"
                elif updated_days_old <= 30:
                    updated_age_class = "medium"
                elif updated_days_old <= 60:
                    updated_age_class = "old"
                else:
                    updated_age_class = "stale"
                updated_display = issue['updated_at'][:10]
            else:
                updated_age_class = "unknown"
                updated_display = 'N/A'
        except:
            updated_age_class = "unknown"
            updated_display = issue['updated_at'][:10] if issue['updated_at'] else 'N/A'
        
        # Get assignee information (support both new multiple assignees and old single assignee)
        assignees = issue.get('assignees', [])
        fallback_assignee = issue.get('assignee_login')
        assignee_display = format_assignees_for_display(assignees, fallback_assignee)
        
        # For sorting purposes, create a simplified assignee string
        if assignees and len(assignees) > 0:
            assignee_sort_key = assignees[0].get('login', 'zzz_unassigned').lower()
        elif fallback_assignee:
            assignee_sort_key = fallback_assignee.lower()
        else:
            assignee_sort_key = 'zzz_unassigned'
        
        # Extract PR references from issue body instead of using database linked_pr field
        pr_references = extract_pr_references(issue.get('body', ''), repo)
        pr_display = format_pr_references(pr_references)
        
        # Format labels for display
        labels_display = format_labels_for_display(issue.get('labels', []))
        
        # Format mentions for display
        mentions_display = format_mentions_for_display(issue.get('mentioned_handles', []))
        
        # Get triage and priority information
        triage = issue.get('triage', 0)
        priority = issue.get('priority', -1)
        
        # Get parsed assignees (should already be a list from database loading)
        assignees_data = issue.get('assignees', [])
        print(f"DEBUG: Issue #{issue['number']} assignees: {assignees_data} (type: {type(assignees_data)})")
        
        # Prepare safe JSON data for modal (properly escaped for JavaScript)
        modal_data = {
            'repo': repo,
            'number': issue['number'],
            'title': issue['title'],
            'htmlUrl': issue['html_url'],
            'triage': triage,
            'priority': priority,
            'comments': issue.get('comments', ''),
            'assignees': assignees_data,
            'labels': issue.get('labels', []),
            'mentions': issue.get('mentioned_handles', [])
        }
        
        # Convert to JSON and escape for HTML attributes
        modal_data_json = html.escape(json.dumps(modal_data))
        
        issue_rows += f"""
        <tr data-repo="{html.escape(repo)}" data-number="{issue['number']}" 
            data-title="{html.escape(issue['title'].lower())}" 
            data-assignee="{html.escape(assignee_sort_key)}"
            data-created="{html.escape(issue['created_at'])}" 
            data-updated="{html.escape(issue['updated_at'])}"
            data-triage="{triage}"
            data-priority="{priority}">
            <td style="text-align: center;">
                <button class="btn btn-sm btn-outline-primary edit-btn" 
                        data-modal-data="{modal_data_json}"
                        onclick="openIssueModalFromData(this)"
                        title="Edit issue details">
                    <i class="fas fa-edit"></i>
                </button>
            </td>
            <td>
                <a href="{issue['html_url']}" target="_blank" class="issue-title-link">#{issue['number']} - {html.escape(issue['title'])}</a>
            </td>
            <td>{assignee_display}</td>
            <td>{pr_display}</td>
            <td>{labels_display}</td>
            <td>{mentions_display}</td>
            <td class="{created_age_class}">{issue['created_at'][:10]}</td>
            <td class="{updated_age_class}">{updated_display}</td>
            <td class="triage-display">
                {format_triage_text(triage)}
            </td>
            <td class="priority-display">
                {format_priority_text(priority)}
            </td>
        </tr>
        """
    
    # Get state button text
    state_button_text = get_state_button_text(current_state)
    
    return f"""
    <div class="repo-section{active_class} {color_class}" id="repo-{repo_id}" data-language="{lang_class}" data-repo-name="{repo}" data-category="{repo_category}">
        <div class="repo-header{active_class} {color_class}" onclick="toggleSection('{repo_id}')">
            <h2>
                <a href="https://github.com/{repo}" target="_blank">{repo_name}</a>
                <span class="category-badge {color_class}">{issue_count}</span>
                <span class="category-badge {color_class}">{repo_category.upper()}</span>
            </h2>
        </div>
        <div class="controls d-flex justify-content-between align-items-center">
            <input type="text" class="form-control search-box" id="search-{repo_id}" 
                   placeholder="🔍 Search issues..." 
                   onkeyup="filterTable('{repo_id}', this.value)" style="flex: 1; margin-right: 10px;">
            <div class="state-controls">
                <div class="toggle-switch" onclick="toggleIssueState()">
                    <input type="checkbox" id="state-toggle-{repo_id}" class="toggle-input" 
                           {'checked' if current_state == 'closed' else ''}>
                    <label for="state-toggle-{repo_id}" class="toggle-label">
                        <span class="toggle-text toggle-open">OPEN</span>
                        <span class="toggle-text toggle-closed">CLOSED</span>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            </div>
        </div>
        <div class="table-container">
            <table class="table table-hover table-striped issues-table {color_class} {state_class}" id="table-{repo_id}">
                <thead class="table-header {color_class}" {header_style}>
                    <tr>
                        <th style="width: 60px;">Edit</th>
                        <th class="sortable" data-column="title" onclick="sortTable('{repo_id}', 'title')">
                            Title <i class="fas fa-sort sort-icon"></i>
                        </th>
                        <th class="sortable" data-column="assignee" onclick="sortTable('{repo_id}', 'assignee')">
                            Assignees <i class="fas fa-sort sort-icon"></i>
                        </th>
                        <th>Related PRs/Issues</th>
                        <th>Labels</th>
                        <th>Mentions</th>
                        <th class="sortable" data-column="created" onclick="sortTable('{repo_id}', 'created')">
                            Created <i class="fas fa-sort sort-icon"></i>
                        </th>
                        <th class="sortable" data-column="updated" onclick="sortTable('{repo_id}', 'updated')">
                            Updated <i class="fas fa-sort sort-icon"></i>
                        </th>
                        <th class="sortable" data-column="triage" onclick="sortTable('{repo_id}', 'triage')">
                            Triage <i class="fas fa-sort sort-icon"></i>
                        </th>
                        <th class="sortable" data-column="priority" onclick="sortTable('{repo_id}', 'priority')">
                            Priority <i class="fas fa-sort sort-icon"></i>
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {issue_rows}
                </tbody>
            </table>
            <!-- Pagination controls -->
            <div class="d-flex justify-content-between align-items-center pagination" id="pagination-{repo_id}" style="display: none;">
                <div class="pagination-info text-muted" id="page-info-{repo_id}">
                    Showing 1-10 of {issue_count} issues
                </div>
                <div class="pagination-controls d-flex align-items-center">
                    <button class="btn btn-outline-secondary btn-sm me-2" id="prev-btn-{repo_id}" onclick="prevPage('{repo_id}')" disabled>
                        <i class="fas fa-chevron-left"></i> Previous
                    </button>
                    <input type="number" class="form-control form-control-sm page-input me-2" id="page-input-{repo_id}" 
                           value="1" min="1" max="1" style="width: 80px;"
                           onchange="goToPage('{repo_id}', this.value)">
                    <span class="text-muted me-2" id="page-counter-{repo_id}">Page 1 of 1</span>
                    <button class="btn btn-outline-secondary btn-sm" id="next-btn-{repo_id}" onclick="nextPage('{repo_id}')" disabled>
                        Next <i class="fas fa-chevron-right"></i>
                    </button>
                </div>
            </div>
        </div>
    </div>
    """

# Authentication Routes
@app.route('/login')
def login():
    """Initiate Azure AD certificate-based user authentication"""
    if not AAD_CONFIG['ENABLED']:
        return redirect(url_for('dashboard'))
    
    # Build MSAL app
    cache = load_cache()
    auth_app = build_msal_app(cache=cache)
    if not auth_app:
        return "Certificate-based authentication is not configured properly. Please ensure AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CERTIFICATE_PATH, and AZURE_CERTIFICATE_THUMBPRINT are set.", 500
    
    # Generate authorization request URL
    auth_url = auth_app.get_authorization_request_url(
        AAD_CONFIG['SCOPES'],
        redirect_uri=url_for('auth_callback', _external=True)
    )
    
    save_cache(cache)
    return redirect(auth_url)

@app.route('/auth/callback')
def auth_callback():
    """Handle Azure AD authentication callback"""
    if not AAD_CONFIG['ENABLED']:
        return redirect(url_for('dashboard'))
    
    # Build MSAL app
    cache = load_cache()
    auth_app = build_msal_app(cache=cache)
    if not auth_app:
        return "Authentication configuration error", 500
    
    try:
        # Get token from authorization code
        result = auth_app.acquire_token_by_authorization_code(
            request.args.get('code'),
            scopes=AAD_CONFIG['SCOPES'],
            redirect_uri=url_for('auth_callback', _external=True)
        )
        
        if 'error' in result:
            print(f"❌ Authentication failed: {result.get('error_description', result.get('error'))}")
            return f"Authentication failed: {result.get('error_description', result.get('error'))}", 400
        
        # Get user info from token
        user_info = result.get('id_token_claims', {})
        user_email = user_info.get('preferred_username') or user_info.get('email') or user_info.get('upn', '')
        
        # Check if user is authorized
        if not is_user_authorized(user_email):
            print(f"❌ Unauthorized access attempt by: {user_email}")
            session.clear()
            return redirect(url_for('unauthorized_user'))
        
        # Store user info in session
        session['user'] = {
            'name': user_info.get('name', 'Unknown User'),
            'preferred_username': user_email,
            'oid': user_info.get('oid', ''),
            'auth_method': 'azure_ad_user'
        }
        
        save_cache(cache)
        print(f"✅ User authentication successful for: {user_email}")
        
        # Redirect to original URL or dashboard
        redirect_url = session.pop('redirect_url', url_for('dashboard'))
        return redirect(redirect_url)
        
    except Exception as e:
        print(f"❌ Authentication callback failed: {e}")
        return f"Authentication failed: {str(e)}", 500

@app.route('/logout')
def logout():
    """Logout user"""
    user_name = session.get('user', {}).get('name', 'Unknown User')
    session.clear()
    logger.info(f"User logged out: {user_name}")
    
    if AAD_CONFIG['ENABLED']:
        # Redirect to Azure AD logout
        logout_url = f"{AAD_CONFIG['AUTHORITY']}/oauth2/v2.0/logout?post_logout_redirect_uri={url_for('dashboard', _external=True)}"
        return redirect(logout_url)
    
    return redirect(url_for('dashboard'))

@app.route('/auth/status')
def auth_status():
    """API endpoint to check authentication status"""
    return jsonify({
        'authenticated': is_authenticated(),
        'aad_enabled': AAD_CONFIG['ENABLED'],
        'user': get_current_user() if is_authenticated() else None,
        'access_control_mode': AAD_CONFIG['ACCESS_CONTROL_MODE'],
        'login_url': url_for('login') if AAD_CONFIG['ENABLED'] else None,
        'logout_url': url_for('logout') if AAD_CONFIG['ENABLED'] else None
    })

@app.route('/unauthorized')
def unauthorized():
    """Page for unauthorized users when authentication is disabled"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Authentication Disabled - GitHub Issues Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .unauthorized-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }
        .unauthorized-card {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            padding: 60px 40px;
            text-align: center;
            max-width: 600px;
            width: 100%;
        }
        .unauthorized-icon {
            font-size: 80px;
            color: #dc3545;
            margin-bottom: 30px;
        }
        .unauthorized-title {
            color: #333;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 20px;
        }
        .unauthorized-message {
            color: #666;
            font-size: 1.2rem;
            line-height: 1.6;
            margin-bottom: 40px;
        }
    </style>
</head>
<body>
    <div class="unauthorized-container">
        <div class="unauthorized-card">
            <i class="fas fa-shield-alt unauthorized-icon"></i>
            <h1 class="unauthorized-title">Authentication Required</h1>
            <p class="unauthorized-message">
                Authentication is currently disabled for this application. Contact your administrator to enable user authentication.
            </p>
        </div>
    </div>
</body>
</html>
    """

@app.route('/unauthorized-user')
def unauthorized_user():
    """Page for users who are authenticated but not authorized"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Access Denied - GitHub Issues Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .unauthorized-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }
        .unauthorized-card {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            padding: 60px 40px;
            text-align: center;
            max-width: 600px;
            width: 100%;
        }
        .unauthorized-icon {
            font-size: 80px;
            color: #ffc107;
            margin-bottom: 30px;
        }
        .unauthorized-title {
            color: #333;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 20px;
        }
        .unauthorized-message {
            color: #666;
            font-size: 1.2rem;
            line-height: 1.6;
            margin-bottom: 40px;
        }
        .btn-logout {
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            border: none;
            color: white;
            padding: 15px 30px;
            font-size: 1.1rem;
            font-weight: 600;
            border-radius: 50px;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
            box-shadow: 0 10px 20px rgba(220, 53, 69, 0.3);
        }
        .btn-logout:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 30px rgba(220, 53, 69, 0.4);
            color: white;
        }
    </style>
</head>
<body>
    <div class="unauthorized-container">
        <div class="unauthorized-card">
            <i class="fas fa-user-times unauthorized-icon"></i>
            <h1 class="unauthorized-title">Access Denied</h1>
            <p class="unauthorized-message">
                You have successfully authenticated, but you are not authorized to access this application. 
                Please contact your administrator to request access.
            </p>
            <a href="/logout" class="btn-logout">
                <i class="fas fa-sign-out-alt me-2"></i>
                Sign Out
            </a>
        </div>
    </div>
</body>
</html>
    """

@app.route('/')
@login_required
def dashboard():
    """Main dashboard route"""
    # Create custom span for dashboard rendering
    if tracer:
        with tracer.start_as_current_span("dashboard_render") as span:
            span.set_attribute("user.name", get_current_user().get('name', 'unknown'))
            span.set_attribute("user.email", get_current_user().get('email', 'unknown'))
            return _dashboard_internal(span)
    else:
        return _dashboard_internal(None)

def _dashboard_internal(span=None):
    """Internal dashboard function with telemetry"""
    print("🌐 Serving GitHub Issues Dashboard...")
    logger.info("Dashboard request received")
    
    # Get the selected repo from query parameter
    selected_repo = request.args.get('repo', '')
    selected_repo = unquote(selected_repo) if selected_repo else ''
    
    # Get the state filter from query parameter (default to 'open')
    show_state = request.args.get('state', 'open')
    if show_state not in ['open', 'closed', 'all']:
        show_state = 'open'  # Default to open if invalid value
    
    if span:
        span.set_attribute("dashboard.selected_repo", selected_repo)
        span.set_attribute("dashboard.show_state", show_state)
        span.set_attribute("request.method", "GET")
        span.set_attribute("request.user_agent", request.headers.get('User-Agent', 'unknown'))
        logger.info(f"Dashboard telemetry span active with selected_repo: {selected_repo}, state: {show_state}")
    else:
        logger.warning("Dashboard telemetry span is None - telemetry may not be configured")
    
    # Get issues from database
    issues = get_issues_from_db(state_filter=show_state)
    if not issues:
        if span:
            span.set_attribute("dashboard.issues_found", False)
        return "<h1>No issues found in database. Please run sync first.</h1>"
    
    if span:
        span.set_attribute("dashboard.issues_found", True)
        span.set_attribute("dashboard.total_issues", len(issues))
    
    # Group issues by repository
    repo_groups = group_issues_by_repo(issues)
    
    if span:
        span.set_attribute("dashboard.repository_count", len(repo_groups))
    
    # Custom business metric for repository rendering
    if repo_counter:
        repo_counter.add(len(repo_groups), {"type": "dashboard_render"})
    
    # Generate repository sections and navigation links
    repo_sections = ""
    nodejs_nav_links = ""
    python_nav_links = ""
    browser_nav_links = ""
    
    nodejs_count = 0
    python_count = 0
    browser_count = 0
    is_first = True
    
    for repo, repo_issues in repo_groups.items():
        repo_id = repo.replace('/', '-').replace('.', '-')
        
        repo_sections += generate_repo_section(repo, repo_issues, is_first, show_state)
        
        # Generate navigation link for Bootstrap dropdown with color coding
        repo_name = repo.split('/')[-1]
        issue_count = len(repo_issues)
        color_class = get_repo_color_class(repo)
        category = get_repo_category(repo)
        
        nav_link = f'''<a class="dropdown-item {color_class}" href="#" onclick="setActiveRepo('{repo_id}')" data-category="{category}">
            <span class="nav-repo-name">{repo_name}</span>
            <span class="badge badge-light ml-auto">{issue_count}</span>
            <small class="category-indicator {color_class}">{category.upper()}</small>
        </a>'''
        
        # Categorize by language
        if repo in ['Azure/azure-sdk-for-python', 'open-telemetry/opentelemetry-python', 'open-telemetry/opentelemetry-python-contrib']:
            python_nav_links += nav_link
            python_count += issue_count
        elif repo in ['Azure/azure-sdk-for-js', 'open-telemetry/opentelemetry-js', 'open-telemetry/opentelemetry-js-contrib',
                      'microsoft/ApplicationInsights-node.js', 'microsoft/ApplicationInsights-node.js-native-metrics', 
                      'microsoft/node-diagnostic-channel']:
            nodejs_nav_links += nav_link
            nodejs_count += issue_count
        else:
            browser_nav_links += nav_link
            browser_count += issue_count
        
        is_first = False
    
    # Calculate statistics
    total_repos = len(repo_groups)
    total_issues = len(issues)
    recent_issues = sum(1 for issue in issues if (datetime.now(timezone.utc) - datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))).days < 14)
    stale_issues = sum(1 for issue in issues if (datetime.now(timezone.utc) - datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))).days > 60)
    
    # Load template and replace all placeholders
    template = load_html_template()
    html = template.replace('{repo_sections}', repo_sections)
    html = html.replace('{nodejs_nav_links}', nodejs_nav_links)
    html = html.replace('{python_nav_links}', python_nav_links)
    html = html.replace('{browser_nav_links}', browser_nav_links)
    html = html.replace('{total_repos}', str(total_repos))
    html = html.replace('{total_issues}', str(total_issues))
    html = html.replace('{recent_issues}', str(recent_issues))
    html = html.replace('{stale_issues}', str(stale_issues))
    html = html.replace('{database_info_text}', get_last_sync_time())
    html = html.replace('{selected_repo}', selected_repo)
    html = html.replace('{current_state}', show_state)
    html = html.replace('{state_button_text}', get_state_button_text(show_state))
    html = html.replace('{group_counts_script}', f'''
    <script>
        // Update navbar badge counts
        document.getElementById('navbar-nodejs-count').textContent = '{nodejs_count}';
        document.getElementById('navbar-python-count').textContent = '{python_count}';
        document.getElementById('navbar-browser-count').textContent = '{browser_count}';
        
        // Set current state for state toggle functionality
        window.currentState = '{show_state}';
    </script>
    ''')
    
    return html

@app.route('/api/status')
@login_required
def status():
    """API endpoint for status"""
    try:
        conn = sqlite3.connect('github_issues.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM issues')
        issue_count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'status': 'running',
            'issue_count': issue_count,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/update_issue', methods=['POST'])
@login_required
def update_issue():
    """API endpoint to update issue triage and priority"""
    try:
        user = get_current_user()
        print(f"🔄 Received update request from user: {user.get('name', 'Unknown')}")
        data = request.get_json()
        print(f"📝 Request data: {data}")
        repo = data.get('repo')
        number = data.get('number')
        triage = 1 if data.get('triage') else 0
        priority = int(data.get('priority', -1))
        comments = data.get('comments', '').strip()  # Get comments from request
        print(f"🎯 Updating issue #{number} in {repo}: triage={triage}, priority={priority}, comments='{comments[:50]}...'")
        
        conn = sqlite3.connect('github_issues.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE issues 
            SET triage = ?, priority = ?, comments = ?
            WHERE repo = ? AND number = ?
        ''', (triage, priority, comments, repo, number))
        
        conn.commit()
        conn.close()
        
        print("✅ Issue updated successfully!")
        return jsonify({
            'status': 'success',
            'message': 'Issue updated successfully'
        })
    except Exception as e:
        print(f"❌ Error updating issue: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/sync')
@login_required
def sync_page():
    """Simple sync status page"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>GitHub Sync Status</title>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="30">
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .status {{ padding: 15px; margin: 10px 0; border-radius: 5px; }}
        .success {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
        .warning {{ background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }}
        .error {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
        .info {{ background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; border: 1px solid #ddd; text-align: left; }}
        th {{ background: #f8f9fa; }}
        .btn {{ padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }}
        .btn:hover {{ background: #0056b3; }}
        .btn:disabled {{ background: #6c757d; cursor: not-allowed; }}
    </style>
</head>
<body>
    <h1>🔄 GitHub Sync Status</h1>
    
    <div id="status">Loading...</div>
    
    <div style="margin: 20px 0;">
        <button id="syncBtn" class="btn" onclick="triggerSync()">🚀 Trigger Manual Sync</button>
        <button class="btn" onclick="location.reload()">🔄 Refresh</button>
        <a href="/" class="btn" style="text-decoration: none; margin-left: 10px;">🏠 Back to Dashboard</a>
    </div>
    
    <script>
        function loadStatus() {{
            fetch('/api/sync_status')
                .then(response => response.json())
                .then(data => {{
                    updateStatusDisplay(data);
                }})
                .catch(error => {{
                    document.getElementById('status').innerHTML = 
                        '<div class="status error">❌ Error loading status: ' + error + '</div>';
                }});
        }}
        
        function updateStatusDisplay(data) {{
            let html = '';
            
            if (!data.authenticated) {{
                html += '<div class="status warning">⚠️ Running in unauthenticated mode (' + data.rate_limit + '). Add GITHUB_TOKEN for higher rate limits.</div>';
            }} else {{
                html += '<div class="status success">🔑 Authenticated mode (' + data.rate_limit + ')</div>';
            }}
            
            if (data.sync_in_progress) {{
                html += '<div class="status info">🔄 Sync in progress...</div>';
            }} else if (data.last_sync) {{
                const lastSync = new Date(data.last_sync);
                html += '<div class="status success">✅ Last sync: ' + lastSync.toLocaleString() + '</div>';
            }} else {{
                html += '<div class="status warning">⚠️ No sync has been performed yet.</div>';
            }}
            
            if (data.next_sync) {{
                const nextSync = new Date(data.next_sync);
                html += '<div class="status info">⏰ Next scheduled sync: ' + nextSync.toLocaleString() + '</div>';
            }}
            
            if (data.total_synced > 0) {{
                html += '<div class="status info">📊 Total issues synced: ' + data.total_synced + '</div>';
            }}
            
            if (data.errors && data.errors.length > 0) {{
                html += '<div class="status error">❌ Recent errors:<ul>';
                data.errors.forEach(error => {{
                    html += '<li>' + error + '</li>';
                }});
                html += '</ul></div>';
            }}
            
            html += '<h3>📋 Repositories:</h3><table><tr><th>Repository</th><th>Status</th></tr>';
            data.repositories.forEach(repo => {{
                html += '<tr><td>' + repo + '</td><td>✅ Configured</td></tr>';
            }});
            html += '</table>';
            
            document.getElementById('status').innerHTML = html;
            
            // Update button state
            const syncBtn = document.getElementById('syncBtn');
            if (data.sync_in_progress) {{
                syncBtn.disabled = true;
                syncBtn.textContent = '🔄 Syncing...';
            }} else {{
                syncBtn.disabled = false;
                const mode = data.authenticated ? 'Authenticated' : 'Unauthenticated';
                syncBtn.textContent = '🚀 Trigger Manual Sync (' + mode + ')';
            }}
        }}
        
        function triggerSync() {{
            const syncBtn = document.getElementById('syncBtn');
            syncBtn.disabled = true;
            syncBtn.textContent = '🔄 Starting...';
            
            fetch('/api/sync_now', {{ method: 'POST' }})
                .then(response => response.json())
                .then(data => {{
                    if (data.status === 'success') {{
                        alert('✅ Sync started in background!');
                        setTimeout(loadStatus, 2000); // Reload status after 2 seconds
                    }} else {{
                        alert('❌ Error: ' + data.message);
                        syncBtn.disabled = false;
                        syncBtn.textContent = '🚀 Trigger Manual Sync';
                    }}
                }})
                .catch(error => {{
                    alert('❌ Network error: ' + error);
                    syncBtn.disabled = false;
                    syncBtn.textContent = '🚀 Trigger Manual Sync';
                }});
        }}
        
        // Load status on page load
        loadStatus();
        
        // Auto-refresh every 30 seconds
        setInterval(loadStatus, 30000);
    </script>
</body>
</html>
"""

@app.route('/api/sync_status')
@login_required
def get_sync_status():
    """Get current sync status"""
    return jsonify({
        'sync_enabled': True,  # Always enabled now (can run with or without token)
        'authenticated': GITHUB_TOKEN is not None,
        'rate_limit': '5000 requests/hour' if GITHUB_TOKEN else '60 requests/hour',
        'last_sync': sync_status['last_sync'],
        'sync_in_progress': sync_status['sync_in_progress'],
        'next_sync': sync_status['next_sync'],
        'total_synced': sync_status['total_synced'],
        'errors': sync_status['errors'][-5:],  # Last 5 errors only
        'repositories': REPOSITORIES
    })

@app.route('/api/sync_now', methods=['POST'])
@login_required
def trigger_sync():
    """Manually trigger a sync (admin endpoint)"""
    if sync_status['sync_in_progress']:
        return jsonify({
            'status': 'error',
            'message': 'Sync already in progress'
        }), 409
    
    auth_status = "authenticated" if GITHUB_TOKEN else "unauthenticated"
    
    # Start sync in background thread
    def run_sync():
        sync_all_repositories()
    
    threading.Thread(target=run_sync, daemon=True).start()
    
    return jsonify({
        'status': 'success',
        'message': f'Sync started in background ({auth_status} mode)',
        'authenticated': GITHUB_TOKEN is not None
    })

@app.route('/health')
def health():
    """Simple health check endpoint with telemetry"""
    if tracer:
        with tracer.start_as_current_span("health_check") as span:
            span.set_attribute("endpoint.type", "health_check")
            response_data = {'status': 'healthy', 'timestamp': datetime.now().isoformat(), 'telemetry_enabled': True}
            span.set_attribute("health.status", "healthy")
            return jsonify(response_data)
    else:
        return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat(), 'telemetry_enabled': False})

@app.route('/api/telemetry_test')
@login_required
def telemetry_test():
    """Test endpoint to verify Azure Monitor telemetry is working"""
    if not tracer or not meter:
        return jsonify({
            'status': 'disabled',
            'message': 'Azure Monitor OpenTelemetry is not configured',
            'telemetry_enabled': False
        })
    
    try:
        # Test custom span with attributes
        with tracer.start_as_current_span("telemetry_test") as span:
            span.set_attribute("test.type", "manual")
            span.set_attribute("test.timestamp", datetime.now().isoformat())
            span.set_attribute("test.endpoint", "/api/telemetry_test")
            
            # Test custom metrics
            if issue_counter:
                issue_counter.add(1, {"source": "telemetry_test", "test": "true"})
            if repo_counter:
                repo_counter.add(1, {"type": "telemetry_test", "test": "true"})
            
            # Add some logging for Azure Monitor
            print("🧪 Telemetry test executed - span and metrics sent")
            
            return jsonify({
                'status': 'success',
                'message': 'Telemetry test completed successfully',
                'telemetry_enabled': True,
                'timestamp': datetime.now().isoformat(),
                'connection_string_present': bool(os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')),
                'span_created': True,
                'metrics_sent': True
            })
    except Exception as e:
        print(f"❌ Telemetry test failed: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Telemetry test failed: {str(e)}',
            'telemetry_enabled': True,
            'error_type': type(e).__name__
        }), 500

@app.route('/api/detect-closed-issues', methods=['POST'])
def api_detect_closed_issues():
    """API endpoint to detect closed issues without full sync"""
    try:
        print("🔍 Starting closed issue detection (without sync)...")
        closed_issues = detect_closed_issues_without_sync()
        
        if closed_issues:
            print(f"✅ Detected {len(closed_issues)} newly closed issues")
            return jsonify({
                'status': 'success',
                'message': f'Detected {len(closed_issues)} newly closed issues',
                'closed_issues_count': len(closed_issues),
                'closed_issues': [{'number': issue['number'], 'title': issue['title'], 'repository': issue['repository']} for issue in closed_issues]
            })
        else:
            print("✅ No newly closed issues detected")
            return jsonify({
                'status': 'success',
                'message': 'No newly closed issues detected',
                'closed_issues_count': 0,
                'closed_issues': []
            })
    except Exception as e:
        print(f"❌ Error detecting closed issues: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error detecting closed issues: {str(e)}'
        }), 500

if __name__ == '__main__':
    print("🚀 Starting Fixed GitHub Issues Dashboard Server...")
    print("=" * 60)
    print("📊 Dashboard will be available at http://localhost:5000")
    print("💡 Press Ctrl+C to stop the server")
    print("")
    
    # Start the sync scheduler
    start_sync_scheduler()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
else:
    # For production deployment (e.g., gunicorn), start scheduler when module is imported
    start_sync_scheduler()
