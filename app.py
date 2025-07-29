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
from flask import Flask, render_template_string, jsonify, request
import sqlite3
import json
from datetime import datetime, timezone
from urllib.parse import unquote

# Azure Monitor OpenTelemetry SDK imports
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace, metrics

# Configure Azure Monitor OpenTelemetry with auto-instrumentation
connection_string = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
if connection_string:
    print(f"🔧 Configuring Azure Monitor OpenTelemetry with connection string: {connection_string[:50]}...")
    # Azure Monitor auto-instruments Flask, requests, SQLite, and more automatically
    configure_azure_monitor(
        connection_string=connection_string,
        # Auto-instrumentation is enabled by default and includes:
        # - Flask (HTTP requests, responses)
        # - Requests (outbound HTTP calls)
        # - SQLite3 (database operations)
        # - Logging (application logs)
        # - And many more libraries automatically
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
else:
    print("⚠️ APPLICATIONINSIGHTS_CONNECTION_STRING not found, OpenTelemetry disabled")
    tracer = None
    meter = None
    issue_counter = None
    repo_counter = None

app = Flask(__name__)

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

def fetch_github_issues(repo, per_page=100):
    """Fetch issues from a GitHub repository"""
    print(f"🔄 Fetching issues from {repo}...")
    
    # Check rate limit status before starting
    if not GITHUB_TOKEN:
        print(f"📡 Using unauthenticated GitHub API for {repo} (60 requests/hour limit)")
    else:
        print(f"� Using authenticated GitHub API for {repo} (5000 requests/hour limit)")
    
    all_issues = []
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
            print(f"  📄 Fetched page {page}: {len(issues)} issues")
            
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
                
                # Insert or update issue
                cursor.execute('''
                    INSERT OR REPLACE INTO issues (
                        repo, number, title, html_url, assignee_login, 
                        created_at, updated_at, body, state, last_fetched
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    repo, number, title, html_url, assignee_login,
                    created_at, updated_at, body, state, last_fetched
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
            
            # Update database
            updated_count = update_database_with_issues(repo, issues)
            total_updated += updated_count
            
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

def get_issues_from_db():
    """Get all issues from database"""
    # Create a custom span for database operations
    if tracer:
        with tracer.start_as_current_span("get_issues_from_db") as span:
            return _get_issues_from_db_internal(span)
    else:
        return _get_issues_from_db_internal(None)

def _get_issues_from_db_internal(span=None):
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
        
        cursor.execute('''
            SELECT * FROM issues 
            ORDER BY created_at DESC
        ''')
        
        issues = []
        for row in cursor.fetchall():
            issue = dict(row)
            # Map repo to repository for compatibility
            issue['repository'] = issue['repo']
            # Set empty labels array since labels aren't stored in this schema
            issue['labels'] = []
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
            'labels': [],
            'linked_pr': None,
            'last_fetched': '2025-01-01T00:00:00Z',
            'triage': 0,
            'priority': 2
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
    import re
    
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

def generate_repo_section(repo, issues, is_first=False):
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
            created_age_class = "recent" if created_days_old < 30 else "stale"
        except:
            created_age_class = "unknown"
        
        # Calculate age class for updated date
        try:
            if issue['updated_at']:
                updated_date = datetime.fromisoformat(issue['updated_at'].replace('Z', '+00:00'))
                updated_days_old = (datetime.now(timezone.utc) - updated_date).days
                updated_age_class = "recent" if updated_days_old < 30 else "stale"
                updated_display = issue['updated_at'][:10]
            else:
                updated_age_class = "unknown"
                updated_display = 'N/A'
        except:
            updated_age_class = "unknown"
            updated_display = issue['updated_at'][:10] if issue['updated_at'] else 'N/A'
        
        # Get assignee information
        assignee = issue.get('assignee_login')
        if assignee:
            assignee_display = f'<a href="https://github.com/{assignee}" target="_blank">@{assignee}</a>'
        else:
            assignee_display = 'Unassigned'
        
        # Extract PR references from issue body instead of using database linked_pr field
        pr_references = extract_pr_references(issue.get('body', ''), repo)
        pr_display = format_pr_references(pr_references)
        
        # Get triage and priority information
        triage = issue.get('triage', 0)
        priority = issue.get('priority', -1)
        
        issue_rows += f"""
        <tr data-repo="{repo}" data-number="{issue['number']}">
            <td><a href="{issue['html_url']}" target="_blank">#{issue['number']}</a></td>
            <td><a href="{issue['html_url']}" target="_blank">{issue['title']}</a></td>
            <td>{assignee_display}</td>
            <td>{pr_display}</td>
            <td class="{created_age_class}">{issue['created_at'][:10]}</td>
            <td class="{updated_age_class}">{updated_display}</td>
            <td>
                <input type="checkbox" class="triage-checkbox" {'checked' if triage else ''} 
                       onchange="markDirty(this)">
            </td>
            <td>
                <select class="priority-select" onchange="markDirty(this)">
                    <option value="-1" {'selected' if priority == -1 else ''}>Not Set</option>
                    <option value="0" {'selected' if priority == 0 else ''}>0 - Critical</option>
                    <option value="1" {'selected' if priority == 1 else ''}>1 - High</option>
                    <option value="2" {'selected' if priority == 2 else ''}>2 - Medium</option>
                    <option value="3" {'selected' if priority == 3 else ''}>3 - Low</option>
                    <option value="4" {'selected' if priority == 4 else ''}>4 - Minimal</option>
                </select>
            </td>
            <td class="actions-cell">
                <button class="save-btn" onclick="saveIssueChanges(this)" style="display: none;">Save Changes</button>
            </td>
        </tr>
        """
    
    return f"""
    <div class="repo-section{active_class}" id="repo-{repo_id}" data-language="{lang_class}" data-repo-name="{repo}">
        <div class="repo-header{active_class}" onclick="toggleSection('{repo_id}')">
            <h2>
                <a href="https://github.com/{repo}" target="_blank">{repo_name}</a>
                <span class="issue-count">({issue_count} issues)</span>
            </h2>
        </div>
        <div class="controls">
            <input type="text" class="search-box" id="search-{repo_id}" 
                   placeholder="Search issues..." 
                   onkeyup="filterTable('{repo_id}', this.value)">
        </div>
        <div class="table-container">
            <table class="issues-table" id="table-{repo_id}">
                <thead>
                    <tr>
                        <th>Issue #</th>
                        <th>Title</th>
                        <th>Assignee</th>
                        <th>Related PRs/Issues</th>
                        <th>Created</th>
                        <th>Updated</th>
                        <th>Triage</th>
                        <th>Priority</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {issue_rows}
                </tbody>
            </table>
            <!-- Pagination controls -->
            <div class="pagination" id="pagination-{repo_id}" style="display: none;">
                <div class="pagination-info" id="page-info-{repo_id}">
                    Showing 1-10 of {issue_count} issues
                </div>
                <div class="pagination-controls">
                    <button class="pagination-btn" id="prev-btn-{repo_id}" onclick="prevPage('{repo_id}')" disabled>
                        ← Previous
                    </button>
                    <input type="number" class="page-input" id="page-input-{repo_id}" 
                           value="1" min="1" max="1" 
                           onchange="goToPage('{repo_id}', this.value)">
                    <span id="page-counter-{repo_id}">Page 1 of 1</span>
                    <button class="pagination-btn" id="next-btn-{repo_id}" onclick="nextPage('{repo_id}')" disabled>
                        Next →
                    </button>
                </div>
            </div>
        </div>
    </div>
    """

@app.route('/')
def dashboard():
    """Main dashboard route"""
    # Create custom span for dashboard rendering
    if tracer:
        with tracer.start_as_current_span("dashboard_render") as span:
            return _dashboard_internal(span)
    else:
        return _dashboard_internal(None)

def _dashboard_internal(span=None):
    """Internal dashboard function with telemetry"""
    print("🌐 Serving GitHub Issues Dashboard...")
    
    # Get the selected repo from query parameter
    selected_repo = request.args.get('repo', '')
    selected_repo = unquote(selected_repo) if selected_repo else ''
    
    if span:
        span.set_attribute("dashboard.selected_repo", selected_repo)
        span.set_attribute("request.method", "GET")
    
    # Get issues from database
    issues = get_issues_from_db()
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
        
        repo_sections += generate_repo_section(repo, repo_issues, is_first)
        
        # Generate navigation link
        repo_name = repo.split('/')[-1]
        issue_count = len(repo_issues)
        nav_link_class = "nav-link"
        nav_link = f'''<a href="#" class="{nav_link_class}" onclick="setActiveRepo('{repo_id}')">
            {repo_name}
            <span class="issue-count-badge">{issue_count}</span>
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
    html = html.replace('{database_info}', f'<div style="margin-top: 1rem; font-size: 0.9rem; opacity: 0.8;">📅 Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>')
    html = html.replace('{selected_repo}', selected_repo)
    html = html.replace('{group_counts_script}', f'''
    <script>
        document.getElementById('nodejs-count').textContent = '{nodejs_count}';
        document.getElementById('python-count').textContent = '{python_count}';
        document.getElementById('browser-count').textContent = '{browser_count}';
    </script>
    ''')
    
    return html

@app.route('/api/status')
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
def update_issue():
    """API endpoint to update issue triage and priority"""
    try:
        print("🔄 Received update request...")
        data = request.get_json()
        print(f"📝 Request data: {data}")
        repo = data.get('repo')
        number = data.get('number')
        triage = 1 if data.get('triage') else 0
        priority = int(data.get('priority', -1))
        print(f"🎯 Updating issue #{number} in {repo}: triage={triage}, priority={priority}")
        
        conn = sqlite3.connect('github_issues.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE issues 
            SET triage = ?, priority = ? 
            WHERE repo = ? AND number = ?
        ''', (triage, priority, repo, number))
        
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
