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
from flask import Flask, render_template, render_template_string, jsonify, request, redirect, url_for
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote, quote
import uuid

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
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
        ERROR = "ERROR"

class DummyTracer:
    def start_as_current_span(self, name):
        return DummySpan()

class DummySpan:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def set_status(self, status):
        pass

class DummyMetrics:
    def get_meter(self, name):
        return None

trace = DummyTrace()
metrics = DummyMetrics()
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
        # Configure Azure Monitor with additional settings for better reliability (commented for testing)
        # configure_azure_monitor(
        #     connection_string=connection_string,
        #     # Auto-instrumentation is enabled by default and includes:
        #     # - Flask (HTTP requests, responses)
        #     # - Requests (outbound HTTP calls)
        #     # - SQLite3 (database operations)
        #     # - Logging (application logs)
        #     # - And many more libraries automatically
        #     
        #     # Additional configuration for better telemetry
        #     enable_logging=True,
        #     # Set sampling rate to ensure data is sent
        #     sampling_ratio=1.0,
        # )
        
        # Get tracer and meter for custom telemetry only
        tracer = trace.get_tracer(__name__)
        meter = metrics.get_meter(__name__)
        
        # Create custom metrics for business logic
        issue_counter = meter.create_counter(
            name="github_issues_processed",
            description="Number of GitHub issues processed",
            unit="1"
        )
        
        pr_counter = meter.create_counter(
            name="github_prs_processed",
            description="Number of GitHub pull requests processed",
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
        pr_counter = None
        repo_counter = None
else:
    print("⚠️ APPLICATIONINSIGHTS_CONNECTION_STRING not found, OpenTelemetry disabled")
    logger.warning("APPLICATIONINSIGHTS_CONNECTION_STRING environment variable not found")
    tracer = None
    meter = None
    issue_counter = None
    pr_counter = None
    repo_counter = None

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', str(uuid.uuid4()))

# GitHub API Configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_API_BASE = 'https://api.github.com'

# Repositories to sync (same as in the database)
REPOSITORIES = [
    'Azure/azure-sdk-for-js',
    'Azure/azure-sdk-for-python',
    'Azure/azure-sdk-for-net',
    'microsoft/ApplicationInsights-js',
    'microsoft/ApplicationInsights-node.js',
    'microsoft/ApplicationInsights-node.js-native-metrics',
    'microsoft/ApplicationInsights-dotnet',
    'microsoft/ApplicationInsights-Java',
    'microsoft/DynamicProto-JS',
    'microsoft/applicationinsights-angularplugin-js',
    'microsoft/applicationinsights-react-js',
    'microsoft/applicationinsights-react-native',
    'microsoft/node-diagnostic-channel',
    'open-telemetry/opentelemetry-js',
    'open-telemetry/opentelemetry-js-contrib',
    'open-telemetry/opentelemetry-python',
    'open-telemetry/opentelemetry-python-contrib',
    'open-telemetry/opentelemetry-dotnet',
    'open-telemetry/opentelemetry-java'
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
        
        # Check if Phase 2 columns exist and recreate table without them if needed
        phase2_columns = ['mentioned_handles', 'pr_references', 'pr_mentions_last_updated']
        has_phase2_columns = any(col in columns for col in phase2_columns)
        
        if has_phase2_columns:
            print("📋 Removing Phase 2 columns (mentioned_handles, pr_references, pr_mentions_last_updated)...")
            
            # Create new table without Phase 2 columns
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS issues_new (
                    repo TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    html_url TEXT NOT NULL,
                    assignee_login TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    body TEXT,
                    state TEXT NOT NULL,
                    last_fetched TEXT,
                    labels TEXT DEFAULT '[]',
                    assignees TEXT DEFAULT '[]',
                    comments TEXT DEFAULT '',
                    triage INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT -1,
                    PRIMARY KEY (repo, number)
                )
            ''')
            
            # Copy data from old table to new table (excluding Phase 2 columns)
            cursor.execute('''
                INSERT INTO issues_new (
                    repo, number, title, html_url, assignee_login, 
                    created_at, updated_at, body, state, last_fetched,
                    labels, assignees, comments, triage, priority
                )
                SELECT 
                    repo, number, title, html_url, assignee_login,
                    created_at, updated_at, body, state, last_fetched,
                    COALESCE(labels, '[]'),
                    COALESCE(assignees, '[]'),
                    COALESCE(comments, ''),
                    COALESCE(triage, 0),
                    COALESCE(priority, -1)
                FROM issues
            ''')
            
            # Replace old table with new table
            cursor.execute('DROP TABLE issues')
            cursor.execute('ALTER TABLE issues_new RENAME TO issues')
            print("✅ Successfully removed Phase 2 columns and cleaned up database schema")
        
        # Add mentioned_handles column if it doesn't exist
        if 'mentioned_handles' not in columns:
            print("📋 Adding 'mentioned_handles' column to issues table...")
            cursor.execute("ALTER TABLE issues ADD COLUMN mentioned_handles TEXT DEFAULT '[]'")
            print("✅ Added 'mentioned_handles' column")
        
        # Add pr_mentions_last_updated column if it doesn't exist (to track Phase 2 execution)
        if 'pr_mentions_last_updated' not in columns:
            print("📋 Adding 'pr_mentions_last_updated' column to issues table...")
            cursor.execute("ALTER TABLE issues ADD COLUMN pr_mentions_last_updated TEXT DEFAULT NULL")
            print("✅ Added 'pr_mentions_last_updated' column")
        
        # Create pull_requests table if it doesn't exist or has wrong schema
        # Check if pull_requests table exists and get its schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pull_requests'")
        pr_table_exists = cursor.fetchone() is not None
        
        should_recreate_pr_table = False
        
        if pr_table_exists:
            # Check if the existing table has the correct schema
            cursor.execute("PRAGMA table_info(pull_requests)")
            pr_columns = [row[1] for row in cursor.fetchall()]
            
            # Expected columns for the current schema
            expected_pr_columns = [
                'repo', 'number', 'title', 'html_url', 'user_login', 'user_avatar_url',
                'created_at', 'updated_at', 'body', 'state', 'draft', 'merged', 
                'mergeable_state', 'base_ref', 'head_ref', 'last_fetched', 
                'labels', 'assignees', 'requested_reviewers', 'comments'
            ]
            
            # Check if schema has wrong columns (like triage/priority from old issues schema)
            wrong_columns = ['triage', 'priority']
            has_wrong_columns = any(col in pr_columns for col in wrong_columns)
            
            # Check if missing required columns
            missing_columns = [col for col in expected_pr_columns if col not in pr_columns]
            
            if has_wrong_columns or missing_columns:
                print(f"📋 Pull requests table has incorrect schema. Wrong columns: {[c for c in wrong_columns if c in pr_columns]}, Missing columns: {missing_columns}")
                should_recreate_pr_table = True
            else:
                print("✅ Pull requests table already has correct schema")
        else:
            print("📋 Pull requests table doesn't exist, will create it")
            should_recreate_pr_table = True
        
        if should_recreate_pr_table:
            if pr_table_exists:
                print("🗑️ Dropping pull_requests table with incorrect schema...")
                cursor.execute('DROP TABLE pull_requests')
            
            print("📋 Creating pull_requests table with correct schema...")
            cursor.execute('''
                CREATE TABLE pull_requests (
                    repo TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    html_url TEXT NOT NULL,
                    user_login TEXT NOT NULL,
                    user_avatar_url TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    body TEXT,
                    state TEXT NOT NULL,
                    draft BOOLEAN DEFAULT FALSE,
                    merged BOOLEAN DEFAULT FALSE,
                    mergeable_state TEXT,
                    base_ref TEXT,
                    head_ref TEXT,
                    last_fetched TEXT,
                    labels TEXT DEFAULT '[]',
                    assignees TEXT DEFAULT '[]',
                    requested_reviewers TEXT DEFAULT '[]',
                    comments TEXT DEFAULT '',
                    PRIMARY KEY (repo, number)
                )
            ''')
            print("✅ Created pull_requests table with correct schema")
        else:
            print("✅ Pull requests table schema is already correct, preserving existing data")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error updating database schema: {e}")
        return False

def fetch_github_pull_requests(repo, per_page=100):
    """
    Fetch pull requests from a GitHub repository.
    
    For Azure repos: Filters by monitoring labels and fetches PRs for each label.
    For other repos: Fetches all PRs.
    
    Returns: List of pull requests from GitHub API
    """
    print(f"🔄 Fetching pull requests from {repo}...")
    
    # Check rate limit status before starting
    if not GITHUB_TOKEN:
        print(f"📡 Using unauthenticated GitHub API for {repo} (60 requests/hour limit)")
    else:
        print(f"🔑 Using authenticated GitHub API for {repo} (5000 requests/hour limit)")
    
    # Define Azure monitoring labels for filtering (same as issues)
    azure_monitor_labels = [
        "Monitor - Distro",
        "Monitor - Exporter", 
        "Monitor - ApplicationInsights"
    ]
    
    # Add LiveMetrics label specifically for .NET repositories
    dotnet_labels = azure_monitor_labels + ["Monitor - LiveMetrics"]
    
    all_prs = []
    seen_pr_numbers = set()  # Track duplicates when fetching by label
    
    # Determine which labels to use based on repository type (same logic as issues)
    labels_to_use = []
    if repo.startswith('Azure/'):
        if 'dotnet' in repo.lower() or repo == 'Azure/azure-sdk-for-net':
            labels_to_use = dotnet_labels  # Use Azure + LiveMetrics labels for .NET
        else:
            labels_to_use = azure_monitor_labels  # Use standard Azure labels
    elif 'ApplicationInsights' in repo:
        # All ApplicationInsights repos don't use Azure monitor labels, fetch all PRs
        labels_to_use = []
    elif repo.startswith('microsoft/') and any(azure_term in repo for azure_term in ['azure']):
        labels_to_use = azure_monitor_labels  # Use Azure labels for other Microsoft Azure-related repos
    
    try:
        headers = get_github_headers()
        
        # For repos with specific label filtering, fetch PRs by each monitoring label separately
        if labels_to_use:
            repo_type = 'Azure' if repo.startswith('Azure/') else 'Microsoft Azure-related'
            print(f"  🏷️ Filtering {repo_type} repo '{repo}' for monitoring labels: {', '.join(labels_to_use)}")
            
            # Fetch all PRs (open, closed, merged) for each label
            states = ['open', 'closed']
            
            for label in labels_to_use:
                for state in states:
                    print(f"  📝 Fetching {state} pull requests with label '{label}'...")
                    
                    page = 1
                    max_pages = 2 if not GITHUB_TOKEN else 3  # Conservative for Azure repos with filtering
                    
                    while page <= max_pages:
                        # Use issues endpoint with label filter to get PRs (GitHub API quirk)
                        issues_url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
                        params = {
                            'state': state,
                            'per_page': per_page,
                            'page': page,
                            'sort': 'updated',
                            'direction': 'desc',
                            'labels': label
                        }
                        
                        print(f"    🌐 Requesting labeled PRs: {issues_url} (page {page}, state: {state}, label: {label})")
                        
                        response = requests.get(issues_url, headers=headers, params=params, timeout=30)
                        
                        if response.status_code == 200:
                            issues = response.json()
                            
                            if not issues:  # No more issues/PRs for this label
                                print(f"    ✅ No more {state} items found for label '{label}' (page {page})")
                                break
                            
                            # Filter to only get pull requests from the issues endpoint
                            prs_in_page = [item for item in issues if 'pull_request' in item and item['number'] not in seen_pr_numbers]
                            
                            for pr in prs_in_page:
                                all_prs.append(pr)
                                seen_pr_numbers.add(pr['number'])
                            
                            print(f"    ✅ Found {len(issues)} items, {len(prs_in_page)} PRs with label '{label}' on page {page}")
                            
                            # Check if we got fewer results than requested (last page)
                            if len(issues) < per_page:
                                print(f"    ✅ Reached last page for label '{label}' {state} PRs (page {page})")
                                break
                            
                            page += 1
                            
                            # Small delay to be respectful
                            time.sleep(0.1)
                            
                        elif response.status_code == 403:
                            print(f"    ⚠️ Rate limit hit for {repo} PRs with label '{label}'")
                            break
                        elif response.status_code == 404:
                            print(f"    ❌ Repository {repo} not found or not accessible")
                            return []
                        else:
                            print(f"    ❌ Error fetching PRs with label '{label}': HTTP {response.status_code}")
                            break
        
        else:
            # For non-Azure repos, fetch all PRs without label filtering
            print(f"  📝 Fetching all pull requests (no label filtering)")
            
            states = ['open', 'closed']
            
            for state in states:
                print(f"  📝 Fetching {state} pull requests...")
                
                # Start with first page
                page = 1
                max_pages = 3  # Limit to avoid excessive API usage
                
                while page <= max_pages:
                    pr_url = f"{GITHUB_API_BASE}/repos/{repo}/pulls"
                    params = {
                        'state': state,
                        'per_page': per_page,
                        'page': page,
                        'sort': 'updated',
                        'direction': 'desc'
                    }
                    
                    print(f"    🌐 Requesting: {pr_url} (page {page}, state: {state})")
                    
                    response = requests.get(pr_url, headers=headers, params=params, timeout=30)
                    
                    if response.status_code == 200:
                        prs = response.json()
                        
                        if not prs:  # No more PRs
                            print(f"    ✅ No more {state} PRs found (page {page})")
                            break
                        
                        print(f"    ✅ Found {len(prs)} {state} PRs on page {page}")
                        all_prs.extend(prs)
                        
                        # Check if we got fewer results than requested (last page)
                        if len(prs) < per_page:
                            print(f"    ✅ Reached last page for {state} PRs (page {page})")
                            break
                        
                        page += 1
                        
                        # Small delay to be respectful
                        time.sleep(0.1)
                        
                    elif response.status_code == 403:
                        print(f"    ⚠️ Rate limit hit for {repo} PRs")
                        # Check if we have some PRs to return
                        if all_prs:
                            print(f"    📊 Returning {len(all_prs)} PRs collected before rate limit")
                            break
                        return []
                        
                    elif response.status_code == 404:
                        print(f"    ❌ Repository {repo} not found or not accessible")
                        return []
                        
                    else:
                        print(f"    ❌ Error fetching PRs: HTTP {response.status_code}")
                        print(f"    📝 Response: {response.text[:200]}...")
                        return []
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error fetching PRs from {repo}: {e}")
        return []
    except Exception as e:
        print(f"❌ Unexpected error fetching PRs from {repo}: {e}")
        return []
    
    print(f"📊 Successfully fetched {len(all_prs)} total pull requests from {repo}")
    return all_prs

def update_database_with_pull_requests(repo, pull_requests):
    """Update database with pull request data"""
    try:
        # Try different database paths for local and Azure environments
        db_paths = [
            'github_issues.db',
            '/home/site/wwwroot/github_issues.db',
            os.path.join(os.path.dirname(__file__), 'github_issues.db')
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
            print(f"❌ Could not connect to database for PR updates in {repo}")
            return 0
        
        cursor = conn.cursor()
        updated_count = 0
        last_fetched = datetime.now(timezone.utc).isoformat()
        
        for pr in pull_requests:
            try:
                # Extract basic PR information
                number = pr['number']
                title = pr['title']
                html_url = pr['html_url']
                user_login = pr['user']['login'] if pr.get('user') else None
                user_avatar_url = pr['user']['avatar_url'] if pr.get('user') else None
                created_at = pr['created_at']
                updated_at = pr['updated_at']
                body = pr.get('body', '') or ''
                state = pr['state']
                draft = pr.get('draft', False)
                merged = pr.get('merged', False)
                mergeable_state = pr.get('mergeable_state', '')
                
                # Extract base and head refs
                base_ref = pr.get('base', {}).get('ref', '') if pr.get('base') else ''
                head_ref = pr.get('head', {}).get('ref', '') if pr.get('head') else ''
                
                # Extract labels with colors
                labels_json = extract_labels_with_colors(pr)
                
                # Extract assignees
                assignees_json = extract_assignees_with_info(pr)
                
                # Extract requested reviewers
                requested_reviewers = []
                if pr.get('requested_reviewers'):
                    for reviewer in pr['requested_reviewers']:
                        requested_reviewers.append({
                            'login': reviewer.get('login', ''),
                            'avatar_url': reviewer.get('avatar_url', ''),
                            'html_url': reviewer.get('html_url', '')
                        })
                requested_reviewers_json = json.dumps(requested_reviewers)
                
                # Insert or update PR (preserve custom user data)
                cursor.execute('''
                    UPDATE pull_requests SET 
                        title = ?, html_url = ?, user_login = ?, user_avatar_url = ?,
                        created_at = ?, updated_at = ?, body = ?, state = ?, draft = ?, merged = ?,
                        mergeable_state = ?, base_ref = ?, head_ref = ?, last_fetched = ?,
                        labels = ?, assignees = ?, requested_reviewers = ?
                    WHERE repo = ? AND number = ?
                ''', (
                    title, html_url, user_login, user_avatar_url,
                    created_at, updated_at, body, state, draft, merged,
                    mergeable_state, base_ref, head_ref, last_fetched,
                    labels_json, assignees_json, requested_reviewers_json,
                    repo, number
                ))
                
                # If no rows were updated, insert new record
                if cursor.rowcount == 0:
                    cursor.execute('''
                        INSERT INTO pull_requests (
                            repo, number, title, html_url, user_login, user_avatar_url,
                            created_at, updated_at, body, state, draft, merged,
                            mergeable_state, base_ref, head_ref, last_fetched,
                            labels, assignees, requested_reviewers, comments
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        repo, number, title, html_url, user_login, user_avatar_url,
                        created_at, updated_at, body, state, draft, merged,
                        mergeable_state, base_ref, head_ref, last_fetched,
                        labels_json, assignees_json, requested_reviewers_json,
                        ''  # Default value for comments
                    ))
                
                updated_count += 1
                
            except Exception as e:
                print(f"❌ Error processing PR #{pr.get('number', 'unknown')}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        print(f"✅ Successfully updated {updated_count} pull requests for {repo}")
        return updated_count
        
    except Exception as e:
        print(f"❌ Error updating database with PRs for {repo}: {e}")
        return 0

def fetch_github_issues(repo, per_page=100):
    """
    Fetch only open issues from a GitHub repository.
    
    For Azure repos: Filters by monitoring labels and fetches open issues for each label.
    For other repos: Fetches all open issues.
    
    Returns: List of open issues from GitHub API
    """
    print(f"🔄 Fetching open issues from {repo}...")
    
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
    
    # Add LiveMetrics label specifically for .NET repositories
    dotnet_labels = azure_monitor_labels + ["Monitor - LiveMetrics"]
    
    all_issues = []
    seen_issue_numbers = set()  # Track duplicates when fetching by label
    
    # Determine which labels to use based on repository type
    labels_to_use = []
    if repo.startswith('Azure/'):
        if 'dotnet' in repo.lower() or repo == 'Azure/azure-sdk-for-net':
            labels_to_use = dotnet_labels  # Use Azure + LiveMetrics labels for .NET
        else:
            labels_to_use = azure_monitor_labels  # Use standard Azure labels
    elif 'ApplicationInsights' in repo:
        # All ApplicationInsights repos don't use Azure monitor labels, fetch all issues
        labels_to_use = []
    elif repo.startswith('microsoft/') and any(azure_term in repo for azure_term in ['azure']):
        labels_to_use = azure_monitor_labels  # Use Azure labels for other Microsoft Azure-related repos
    
    # For repos with specific label filtering, fetch issues by each monitoring label separately
    if labels_to_use:
        repo_type = 'Azure' if repo.startswith('Azure/') else 'Microsoft Azure-related'
        print(f"  🏷️ Filtering {repo_type} repo '{repo}' for monitoring labels: {', '.join(labels_to_use)}")
        
        for label in labels_to_use:
            page = 1
            while True:
                try:
                    url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
                    params = {
                        'state': 'open',  # Only fetch open issues
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
                    
                    # Limit pages for rate limiting - increased for Azure repos to get more complete data
                    if repo.startswith('Azure/'):
                        max_pages = 3 if not GITHUB_TOKEN else 5  # Allow more pages for Azure repos
                    else:
                        max_pages = 1 if not GITHUB_TOKEN else 2  # Conservative for other repos
                    
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
        
        print(f"✅ Fetched {len(all_issues)} total filtered open issues from {repo}")
        return all_issues
    
    # For non-Azure repos, use the original logic
    else:
        print(f"  📋 Fetching open issues from non-Azure repo: {repo}")
        page = 1
        
        while True:
            try:
                # Get only open issues
                url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
                params = {
                    'state': 'open',  # Only fetch open issues
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
                    # Unauthenticated: very conservative limit to ensure we get through all 14 repos
                    # 14 repos × 1 page = 14 requests, leaving 46 requests for other operations
                    max_pages = 1
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
        
        print(f"✅ Fetched {len(all_issues)} total open issues from {repo}")
        return all_issues

def update_database_with_issues_basic(repo, issues):
    """Update the database with fetched issues - BASIC DATA ONLY (no PR/mentions fetching)"""
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
                # Extract basic issue data (no PR fetching in this phase)
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
                
                # Basic mentions extraction (from issue body only, no PR content - Phase 2 DISABLED)
                mentioned_handles_json = extract_mentioned_handles(body, '')
                
                # Insert or update issue (preserve custom user data)
                # First try to update existing record, preserving comments, triage, and priority
                cursor.execute('''
                    UPDATE issues SET 
                        title = ?, html_url = ?, assignee_login = ?,
                        created_at = ?, updated_at = ?, body = ?, state = ?, last_fetched = ?,
                        labels = ?, mentioned_handles = ?, assignees = ?
                    WHERE repo = ? AND number = ?
                ''', (
                    title, html_url, assignee_login,
                    created_at, updated_at, body, state, last_fetched,
                    labels_json, mentioned_handles_json, assignees_json,
                    repo, number
                ))
                
                # If no rows were updated, insert new record with default custom values
                if cursor.rowcount == 0:
                    cursor.execute('''
                        INSERT INTO issues (
                            repo, number, title, html_url, assignee_login, 
                            created_at, updated_at, body, state, last_fetched,
                            labels, mentioned_handles, assignees, comments, triage, priority
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        repo, number, title, html_url, assignee_login,
                        created_at, updated_at, body, state, last_fetched,
                        labels_json, mentioned_handles_json, assignees_json,
                        '', 0, -1  # Default values for comments, triage, priority
                    ))
                
                updated_count += 1
                
            except Exception as e:
                print(f"❌ Error updating issue #{issue.get('number', '?')} in {repo}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        print(f"✅ Updated {updated_count} basic issue data for {repo}")
        return updated_count
        
    except Exception as e:
        print(f"❌ Database error for {repo}: {e}")
        sync_status['errors'].append(f"Database error for {repo}: {str(e)}")
        return 0

def detect_and_mark_closed_issues(repo, current_open_issues):
    """
    Detect issues that are no longer in GitHub's open issues list and mark them as closed.
    
    This function compares:
    - Issues we have stored as 'open' in our database
    - Issues that GitHub currently returns as 'open'
    
    Any issues in our database marked as 'open' but not in GitHub's current open list
    are assumed to have been closed and will be marked as 'closed' in our database.
    """
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
        
        # CRITICAL BUG FIX: Don't mark issues as closed if we didn't get any data from GitHub
        # This happens when API rate limits are exceeded and current_open_issues is empty
        if not current_open_issues and db_open_issues:
            print(f"⚠️ Skipping closed issue detection for {repo} - no current issues fetched (likely rate limited)")
            print(f"   Database has {len(db_open_issues)} open issues, but GitHub returned 0 issues")
            print(f"   This could be due to rate limiting or API errors - not marking any issues as closed")
            conn.close()
            return 0
        
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
    """
    Detect closed issues by fetching current open issues from GitHub without updating database.
    
    This is a lightweight operation that only:
    1. Fetches current open issues from GitHub
    2. Compares with issues marked as 'open' in our database  
    3. Marks issues as 'closed' if they're no longer in GitHub's open list
    4. Does NOT update the database with the fetched open issues
    """
    print("🔍 Detecting closed issues without full sync...")
    
    total_closed = 0
    
    try:
        for i, repo in enumerate(REPOSITORIES):
            print(f"\n📋 Checking repository {i+1}/{len(REPOSITORIES)}: {repo}")
            
            # Fetch current open issues from GitHub (without updating database)
            open_issues = fetch_github_issues(repo)
            
            # Detect and mark closed issues
            closed_count = detect_and_mark_closed_issues(repo, open_issues)
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
    print(f"🔑 GitHub API access: {'authenticated (5000/hour)' if GITHUB_TOKEN else 'unauthenticated (60/hour)'}")
    
    sync_status['sync_in_progress'] = True
    sync_status['errors'] = []  # Clear previous errors
    
    total_updated = 0
    start_time = datetime.now(timezone.utc)
    
    # Check initial rate limit
    try:
        rate_check_url = f"{GITHUB_API_BASE}/rate_limit"
        rate_response = requests.get(rate_check_url, headers=get_github_headers(), timeout=5)
        
        if rate_response.status_code == 200:
            rate_data = rate_response.json()
            remaining = rate_data.get('resources', {}).get('core', {}).get('remaining', 'unknown')
            reset_time = rate_data.get('resources', {}).get('core', {}).get('reset', 'unknown')
            print(f"📊 Initial API quota: {remaining} requests remaining")
            
            if isinstance(remaining, int) and remaining < 20:
                print(f"⚠️ Low API quota ({remaining} requests). Consider waiting or adding GITHUB_TOKEN.")
                if not GITHUB_TOKEN:
                    print("💡 Add GITHUB_TOKEN environment variable to increase quota to 5000/hour")
        else:
            print("⚠️ Could not check rate limit status")
    except Exception as e:
        print(f"⚠️ Could not check initial rate limit: {e}")
    
    try:
        # PHASE 1: Get basic issue data from all repositories first
        print("📋 Phase 1: Fetching basic issue data from all repositories...")
        
        # Prioritize getting basic issue data from all repositories first
        # Reduce delay for unauthenticated requests to get through more repos quickly
        delay_between_repos = 1 if not GITHUB_TOKEN else 0.5
        
        for i, repo in enumerate(REPOSITORIES):
            if not sync_status['sync_in_progress']:  # Check if sync was cancelled
                break
                
            print(f"\n📋 Syncing repository {i+1}/{len(REPOSITORIES)}: {repo}")
            
            try:
                # Fetch only open issues from GitHub
                issues = fetch_github_issues(repo)
                
                # Detect and mark closed issues (issues that are in our DB as 'open' but not in GitHub's current open list)
                closed_count = detect_and_mark_closed_issues(repo, issues)
                
                # Update database with basic issue data only (no PR fetching in Phase 1)
                updated_count = update_database_with_issues_basic(repo, issues)
                total_updated += updated_count
                
                if closed_count > 0:
                    print(f"  🔒 Marked {closed_count} issues as closed")
                    
                print(f"  ✅ Updated {updated_count} basic issue data for {repo}")
                
                # Also fetch and update pull requests
                try:
                    pull_requests = fetch_github_pull_requests(repo)
                    pr_updated_count = update_database_with_pull_requests(repo, pull_requests)
                    print(f"  🔀 Updated {pr_updated_count} pull requests for {repo}")
                except Exception as pr_error:
                    print(f"  ⚠️ Warning: Could not sync pull requests for {repo}: {pr_error}")
                    # Don't fail the entire sync for PR errors
                
            except Exception as e:
                error_msg = f"Error syncing {repo}: {str(e)}"
                print(f"  ❌ {error_msg}")
                sync_status['errors'].append(error_msg)
                continue  # Continue with next repository
            
            # Add delay between repositories to be respectful to GitHub API
            if i < len(REPOSITORIES) - 1:  # Don't delay after the last repo
                print(f"  ⏱️ Waiting {delay_between_repos} seconds before next repository...")
                time.sleep(delay_between_repos)
        
        sync_status['last_sync'] = datetime.now(timezone.utc).isoformat()
        sync_status['total_synced'] = total_updated
        
        print(f"\n🎉 Sync completed! Updated {total_updated} issues across {len(REPOSITORIES)} repositories")
        print("📊 Summary:")
        print(f"   • Basic issue data for all {len(REPOSITORIES)} repositories")
        print(f"   • Pull requests data for all {len(REPOSITORIES)} repositories")
        print(f"   • Total issues updated: {total_updated}")
        
        if sync_status['errors']:
            print(f"⚠️ Encountered {len(sync_status['errors'])} errors during sync:")
            for error in sync_status['errors']:
                print(f"   • {error}")
        
        # Check final rate limit
        try:
            rate_response = requests.get(rate_check_url, headers=get_github_headers(), timeout=5)
            if rate_response.status_code == 200:
                rate_data = rate_response.json()
                remaining = rate_data.get('resources', {}).get('core', {}).get('remaining', 'unknown')
                print(f"📊 Final API quota: {remaining} requests remaining")
        except Exception:
            pass  # Don't fail sync for rate limit check
        
    except Exception as e:
        print(f"❌ Critical error during sync: {e}")
        sync_status['errors'].append(f"Critical sync error: {str(e)}")
    
    finally:
        sync_status['sync_in_progress'] = False
        
        # Calculate next sync time (8 AM Pacific tomorrow)
        now_pacific = datetime.now(PACIFIC_TZ)
        
        # Set to 8 AM Pacific today
        next_sync_pacific = now_pacific.replace(hour=8, minute=0, second=0, microsecond=0)
        
        # If 8 AM Pacific today has already passed, move to tomorrow
        if next_sync_pacific <= now_pacific:
            next_sync_pacific = next_sync_pacific.replace(day=next_sync_pacific.day + 1)
        
        # Convert to UTC for storage
        next_sync_utc = next_sync_pacific.astimezone(timezone.utc)
        sync_status['next_sync'] = next_sync_utc.isoformat()

def start_sync_scheduler():
    """Start the background sync scheduler"""
    auth_status = "authenticated" if GITHUB_TOKEN else "unauthenticated"
    rate_limit = "5000 requests/hour" if GITHUB_TOKEN else "60 requests/hour"
    
    print(f"⏰ Starting sync scheduler (every 24 hours at 8:00 AM Pacific Time)")
    print(f"🔑 GitHub API access: {auth_status} ({rate_limit})")
    
    # Update database schema if needed
    print("🔧 Checking database schema...")
    update_database_schema()
    
    try:
        # Calculate 8 AM Pacific Time in UTC for scheduling
        # Pacific timezone handles PST/PDT automatically
        
        # Create a datetime for 8 AM Pacific today
        today_pacific = datetime.now(PACIFIC_TZ).replace(hour=8, minute=0, second=0, microsecond=0)
        
        # Convert to UTC for the scheduler
        utc_time = today_pacific.astimezone(timezone.utc)
        schedule_time = utc_time.strftime("%H:%M")
        
        print(f"📅 Scheduling sync for 8:00 AM Pacific (currently {schedule_time} UTC)")
        
        # Schedule daily sync at the calculated UTC time
        schedule.every().day.at(schedule_time).do(sync_all_repositories)
        
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

def get_pull_requests_from_db(state_filter='open'):
    """Get pull requests from database with optional state filtering"""
    # Create a custom span for database operations
    if tracer:
        with tracer.start_as_current_span("get_pull_requests_from_db") as span:
            return _get_pull_requests_from_db_internal(span, state_filter)
    else:
        return _get_pull_requests_from_db_internal(None, state_filter)

def _get_pull_requests_from_db_internal(span=None, state_filter='open'):
    """Internal function to get pull requests from database with telemetry"""
    try:
        if span:
            span.set_attribute("operation.type", "database_read")
            span.set_attribute("database.name", "github_issues.db")
        
        # Try different database paths for local and Azure environments
        db_paths = [
            'github_issues.db',
            '/home/site/wwwroot/github_issues.db',
            os.path.join(os.path.dirname(__file__), 'github_issues.db')
        ]
        
        conn = None
        for db_path in db_paths:
            try:
                if os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    break
            except Exception:
                continue
        
        if conn is None:
            print("❌ Could not connect to database for pull requests")
            return get_sample_pull_requests()
        
        # SQLite operations are automatically instrumented by Azure Monitor
        cursor = conn.cursor()
        
        # Build the query based on state filter
        if state_filter == 'all':
            cursor.execute('''
                SELECT repo, number, title, html_url, user_login, user_avatar_url, created_at, updated_at, body, 
                       state, draft, merged, mergeable_state, base_ref, head_ref, last_fetched,
                       labels, assignees, requested_reviewers, comments
                FROM pull_requests 
                ORDER BY updated_at DESC
            ''')
        else:
            cursor.execute('''
                SELECT repo, number, title, html_url, user_login, user_avatar_url, created_at, updated_at, body, 
                       state, draft, merged, mergeable_state, base_ref, head_ref, last_fetched,
                       labels, assignees, requested_reviewers, comments
                FROM pull_requests 
                WHERE state = ? 
                ORDER BY updated_at DESC
            ''', (state_filter,))
        
        if span:
            span.set_attribute("database.operation", "SELECT")
            span.set_attribute("database.table", "pull_requests")
        
        prs = []
        for row in cursor.fetchall():
            pr = {
                'repository': row[0],
                'repo': row[0],
                'repo_name': row[0],  # Add repo_name field for consistency with issues
                'number': row[1],
                'title': row[2],
                'html_url': row[3],
                'user_login': row[4],
                'user_avatar_url': row[5],
                'created_at': row[6],
                'updated_at': row[7],
                'body': row[8],
                'state': row[9],
                'draft': row[10],
                'merged': row[11],
                'mergeable_state': row[12],
                'base_ref': row[13],
                'head_ref': row[14],
                'last_fetched': row[15],
                'labels': row[16],
                'assignees': row[17],
                'requested_reviewers': row[18],
                'comments': row[19] or ''
            }
            
            # Parse labels JSON (with fallback for old records)
            try:
                if 'labels' in pr and pr['labels']:
                    pr['labels'] = json.loads(pr['labels'])
                else:
                    pr['labels'] = []
            except (json.JSONDecodeError, TypeError):
                pr['labels'] = []
            
            # Parse assignees JSON (with fallback for old records)
            try:
                if 'assignees' in pr and pr['assignees']:
                    pr['assignees'] = json.loads(pr['assignees'])
                else:
                    pr['assignees'] = []
            except (json.JSONDecodeError, TypeError):
                pr['assignees'] = []
            
            # Parse requested reviewers JSON (with fallback for old records)
            try:
                if 'requested_reviewers' in pr and pr['requested_reviewers']:
                    pr['requested_reviewers'] = json.loads(pr['requested_reviewers'])
                else:
                    pr['requested_reviewers'] = []
            except (json.JSONDecodeError, TypeError):
                pr['requested_reviewers'] = []
            
            # Ensure comments field exists (with fallback for old records)
            if 'comments' not in pr:
                pr['comments'] = ''
            
            prs.append(pr)
        
        conn.close()
        
        # Log telemetry for business metrics only
        pr_count = len(prs)
        print(f"Successfully loaded {pr_count} pull requests from database")
        
        if span:
            span.set_attribute("operation.count", pr_count)
        
        # Custom business metric
        if pr_counter:
            pr_counter.add(pr_count, {"state": state_filter})
        
        return prs
    except Exception as e:
        print(f"Error getting pull requests from database: {e}")
        if span:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
        return get_sample_pull_requests()

def get_sample_pull_requests():
    """Return sample pull requests when database is not available"""
    return [
        {
            'id': 1,
            'repository': 'Azure/azure-sdk-for-python',
            'repo': 'Azure/azure-sdk-for-python', 
            'number': 456,
            'title': 'Sample Pull Request - Database Not Available',
            'html_url': 'https://github.com/Azure/azure-sdk-for-python/pull/456',
            'state': 'open',
            'user_login': 'octocat',
            'created_at': '2025-01-01T00:00:00Z',
            'updated_at': '2025-01-01T00:00:00Z',
            'body': 'This is a sample pull request displayed when the database is not available.',
            'draft': False,
            'merged': False,
            'mergeable_state': 'clean',
            'base_ref': 'main',
            'head_ref': 'feature-branch',
            'labels': [{'name': 'sample', 'color': '00ff00', 'description': 'Sample label'}],
            'assignees': [],
            'requested_reviewers': [],
            'comments': '',
            'last_fetched': '2025-01-01T00:00:00Z',
            'triage': 0,
            'priority': -1
        }
    ]

def get_sync_statistics():
    """Get comprehensive sync statistics for the dashboard"""
    try:
        # Try different database paths for local and Azure environments
        db_paths = [
            'github_issues.db',
            '/home/site/wwwroot/github_issues.db',
            os.path.join(os.path.dirname(__file__), 'github_issues.db')
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
            return get_default_sync_stats()
        
        cursor = conn.cursor()
        
        # Get overall statistics
        cursor.execute('SELECT COUNT(*) FROM issues WHERE state = "open"')
        total_open_issues = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM issues WHERE state = "closed"')
        total_closed_issues = cursor.fetchone()[0]
        
        # Get last sync information from sync_status
        last_sync = sync_status.get('last_sync')
        last_sync_formatted = 'Never'
        if last_sync:
            try:
                last_sync_dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                last_sync_formatted = last_sync_dt.strftime('%Y-%m-%d %H:%M UTC')
            except:
                last_sync_formatted = 'Unknown'
        
        # Get issues created/updated in last 24 hours
        twenty_four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        cursor.execute('SELECT COUNT(*) FROM issues WHERE created_at > ? AND state = "open"', (twenty_four_hours_ago,))
        new_issues_24h = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM issues WHERE updated_at > ? AND state = "open"', (twenty_four_hours_ago,))
        updated_issues_24h = cursor.fetchone()[0]
        
        # Get repository-specific statistics
        cursor.execute('''
            SELECT repo, 
                   COUNT(CASE WHEN state = 'open' THEN 1 END) as open_count,
                   COUNT(CASE WHEN state = 'closed' THEN 1 END) as closed_count,
                   COUNT(CASE WHEN created_at > ? AND state = 'open' THEN 1 END) as new_24h,
                   COUNT(CASE WHEN updated_at > ? AND state = 'open' THEN 1 END) as updated_24h,
                   MAX(last_fetched) as last_updated
            FROM issues 
            GROUP BY repo 
            ORDER BY open_count DESC
        ''', (twenty_four_hours_ago, twenty_four_hours_ago))
        
        repo_stats = []
        for row in cursor.fetchall():
            repo, open_count, closed_count, new_24h, updated_24h, last_updated = row
            
            # Format last updated time
            last_updated_formatted = 'Never'
            if last_updated:
                try:
                    last_updated_dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                    last_updated_formatted = last_updated_dt.strftime('%Y-%m-%d %H:%M UTC')
                except:
                    last_updated_formatted = 'Unknown'
            
            repo_stats.append({
                'repo': repo,
                'open_count': open_count,
                'closed_count': closed_count,
                'new_24h': new_24h,
                'updated_24h': updated_24h,
                'last_updated': last_updated_formatted,
                'issues': open_count + closed_count,  # Total issues for template
                'prs': 0  # We don't track PRs separately yet
            })
        
        # Ensure all configured repositories are included, even if they have no issues yet
        repo_stats_dict = {rs['repo']: rs for rs in repo_stats}
        for repo_name in REPOSITORIES:
            if repo_name not in repo_stats_dict:
                repo_stats_dict[repo_name] = {
                    'repo': repo_name,
                    'open_count': 0,
                    'closed_count': 0,
                    'new_24h': 0,
                    'updated_24h': 0,
                    'last_updated': 'Never synced',
                    'issues': 0,
                    'prs': 0
                }
        
        # Convert back to list for sorting, then back to dict
        repo_stats_list = list(repo_stats_dict.values())
        repo_stats_list.sort(key=lambda x: x['open_count'], reverse=True)
        repo_stats_final = {rs['repo']: rs for rs in repo_stats_list}
        
        # Get issues with recent PR/mentions processing (if column exists)
        try:
            cursor.execute('SELECT COUNT(*) FROM issues WHERE pr_mentions_last_updated IS NOT NULL')
            processed_pr_mentions = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            # Column doesn't exist (Phase 2 is disabled)
            processed_pr_mentions = 0
        
        # Calculate API efficiency stats
        total_issues = total_open_issues + total_closed_issues
        pr_processing_percentage = (processed_pr_mentions / total_issues * 100) if total_issues > 0 else 0
        
        conn.close()
        
        return {
            'total_open_issues': total_open_issues,
            'total_closed_issues': total_closed_issues,
            'total_issues': total_issues,
            'new_issues_24h': new_issues_24h,
            'updated_issues_24h': updated_issues_24h,
            'last_sync': last_sync_formatted,
            'last_sync_formatted': last_sync_formatted,  # Template expects this
            'in_progress': sync_status.get('sync_in_progress', False),  # Template expects this
            'sync_in_progress': sync_status.get('sync_in_progress', False),
            'errors': len(sync_status.get('errors', [])),  # Template expects this
            'sync_errors': len(sync_status.get('errors', [])),
            'error_details': '\n'.join(sync_status.get('errors', [])) if sync_status.get('errors') else None,
            'next_sync': sync_status.get('next_sync'),
            'repo_stats': repo_stats_final,  # Now a dictionary as expected by template
            'processed_pr_mentions': processed_pr_mentions,
            'pr_processing_percentage': round(pr_processing_percentage, 1),
            'repositories_count': len(REPOSITORIES),
            'repository_count': len(REPOSITORIES),  # Template expects this
            'total_prs': 0  # Template expects this - we'll need to calculate this if needed
        }
        
    except Exception as e:
        print(f"❌ Error getting sync statistics: {e}")
        return get_default_sync_stats()

def get_default_sync_stats():
    """Return default sync stats when database is unavailable"""
    return {
        'total_open_issues': 0,
        'total_closed_issues': 0,
        'total_issues': 0,
        'new_issues_24h': 0,
        'updated_issues_24h': 0,
        'last_sync': 'Never',
        'last_sync_formatted': 'Never',  # Template expects this
        'in_progress': False,  # Template expects this
        'sync_in_progress': False,
        'errors': 0,  # Template expects this
        'sync_errors': 0,
        'error_details': None,
        'next_sync': None,
        'repo_stats': {},  # Empty dictionary as expected by template
        'processed_pr_mentions': 0,
        'pr_processing_percentage': 0,
        'repositories_count': len(REPOSITORIES),
        'repository_count': len(REPOSITORIES),  # Template expects this
        'total_prs': 0  # Template expects this
    }

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

def get_repo_sort_order(repo):
    """Get sort order for repository (Azure=1, OpenTelemetry=2, Microsoft=3)"""
    if repo.startswith('Azure/'):
        return 1
    elif repo.startswith('open-telemetry/'):
        return 2
    elif repo.startswith('microsoft/'):
        return 3
    else:
        return 4

def sort_repositories_by_priority(repos):
    """Sort repositories by Azure, OpenTelemetry, then Microsoft"""
    return sorted(repos, key=lambda repo: (get_repo_sort_order(repo), repo.lower()))

def get_all_configured_repositories():
    """Get all configured repositories, sorted by priority"""
    return sort_repositories_by_priority(REPOSITORIES)

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
        return 'opentelemetry'  # All OpenTelemetry repos use OpenTelemetry theme
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
        'opentelemetry': 'otel-theme',     # Orange/Red theme for OpenTelemetry (including dotnet)
        'azure': 'azure-theme',           # Blue theme for Azure
        'microsoft': 'microsoft-theme',   # Cyan theme for Microsoft
        'other': 'default-theme'          # Gray theme for others
    }
    return color_classes.get(category, 'default-theme')

def get_all_repositories_from_db():
    """Get list of all repositories that have been synced (even if no current issues)"""
    try:
        conn = sqlite3.connect('github_issues.db')
        cursor = conn.cursor()
        
        # Get distinct repositories from the database
        cursor.execute("SELECT DISTINCT repo FROM issues ORDER BY repo")
        repos = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return repos
    except Exception as e:
        print(f"❌ Error getting repositories from database: {e}")
        return []

def generate_empty_repo_section(repo, current_state='open', data_type='issues'):
    """Generate HTML section for a repository with no issues matching current filter"""
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
    
    # Generate appropriate empty message based on state and data type
    data_label = "pull requests" if data_type == 'prs' else "issues"
    data_label_cap = "Pull Requests" if data_type == 'prs' else "Issues"
    
    if current_state == 'closed':
        empty_message = f"""
        <tr>
            <td colspan="8" class="text-center py-4">
                <div class="empty-table-message">
                    <i class="fas fa-check-circle text-muted" style="font-size: 2rem; margin-bottom: 1rem;"></i>
                    <h5 class="text-muted">No closed {data_label} found</h5>
                    <p class="text-muted mb-0">This repository has no closed {data_label} in the database.</p>
                    <button class="btn btn-outline-primary btn-sm mt-2" onclick="toggleIssueState()">
                        <i class="fas fa-exclamation-circle"></i> View Open {data_label_cap}
                    </button>
                </div>
            </td>
        </tr>
        """
    elif current_state == 'open':
        empty_message = f"""
        <tr>
            <td colspan="8" class="text-center py-4">
                <div class="empty-table-message">
                    <i class="fas fa-inbox text-success" style="font-size: 2rem; margin-bottom: 1rem;"></i>
                    <h5 class="text-success">No open {data_label}!</h5>
                    <p class="text-muted mb-0">Great news! This repository has no open {data_label}.</p>
                    <button class="btn btn-outline-secondary btn-sm mt-2" onclick="toggleIssueState()">
                        <i class="fas fa-check-circle"></i> View Closed {data_label_cap}
                    </button>
                </div>
            </td>
        </tr>
        """
    else:  # 'all'
        empty_message = f"""
        <tr>
            <td colspan="8" class="text-center py-4">
                <div class="empty-table-message">
                    <i class="fas fa-database text-muted" style="font-size: 2rem; margin-bottom: 1rem;"></i>
                    <h5 class="text-muted">No {data_label} found</h5>
                    <p class="text-muted mb-0">This repository has no {data_label} in the database.</p>
                    <a href="/sync" class="btn btn-outline-primary btn-sm mt-2">
                        <i class="fas fa-sync"></i> Sync Data
                    </a>
                </div>
            </td>
        </tr>
        """
    
    # Get color theme for this repository
    color_class = get_repo_color_class(repo)
    repo_category = get_repo_category(repo)
    
    # Add state-specific styling
    state_class = "closed-issues" if current_state == 'closed' else ""
    header_style = 'style="background-color: #4a4a4a; color: #e0e0e0;"' if current_state == 'closed' else ""
    
    repo_name = repo.split('/')[-1]
    repo_id = repo.replace('/', '-').replace('.', '-')
    data_count = 0  # Empty repo has 0 items
    
    # Set CSS classes for visibility - no repo is active by default
    active_class = ""
    
    # Get state button text
    state_button_text = get_state_button_text(current_state)
    
    return f"""
    <div class="repo-section{active_class} {color_class}" id="repo-{repo_id}" data-language="{lang_class}" data-repo-name="{repo}" data-category="{repo_category}">
        <div class="repo-header{active_class} {color_class}" onclick="toggleSection('{repo_id}')">
            <h2>
                <a href="https://github.com/{repo}" target="_blank">{repo_name}</a>
                <span class="category-badge {color_class}">{data_count}</span>
                <span class="category-badge {color_class}">{repo_category.upper()}</span>
            </h2>
        </div>
        <div class="controls d-flex justify-content-between align-items-center">
            <input type="text" class="form-control search-box" id="search-{repo_id}" 
                   placeholder="🔍 Search {data_type}..." 
                   onkeyup="filterTable('{repo_id}', this.value)" style="flex: 1; margin-right: 10px;">
            <div class="data-type-indicator">
                <span class="badge badge-info">{data_type.title()}</span>
            </div>
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
        
        <!-- Age Classification Legend (for repository view only) -->
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color recent"></div>
                <span>0-14 days (Recent)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color medium"></div>
                <span>15-30 days (Medium)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color old"></div>
                <span>31-60 days (Old)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color stale"></div>
                <span>60+ days (Stale)</span>
            </div>
        </div>
        
        <div class="table-container">
            <table class="table table-hover table-striped issues-table {color_class} {state_class}" id="table-{repo_id}">
                <thead class="table-header {color_class}" {header_style}>
                    <tr>
                        <th style="width: 60px;">Actions</th>
                        <th class="sortable" data-column="title" onclick="sortTable('{repo_id}', 'title')">
                            Title <i class="fas fa-sort sort-icon"></i>
                        </th>""" + (f"""
                        <th class="sortable" data-column="author" onclick="sortTable('{repo_id}', 'author')">
                            Author <i class="fas fa-sort sort-icon"></i>
                        </th>
                        <th class="sortable" data-column="reviewers" onclick="sortTable('{repo_id}', 'reviewers')">
                            Reviewers <i class="fas fa-sort sort-icon"></i>
                        </th>""" if data_type == 'prs' else f"""
                        <th class="sortable" data-column="assignee" onclick="sortTable('{repo_id}', 'assignee')">
                            Assignees <i class="fas fa-sort sort-icon"></i>
                        </th>""") + f"""
                        <th>Labels</th>
                        <th class="sortable" data-column="created" onclick="sortTable('{repo_id}', 'created')">
                            Created <i class="fas fa-sort sort-icon"></i>
                        </th>
                        <th class="sortable" data-column="updated" onclick="sortTable('{repo_id}', 'updated')">
                            Updated <i class="fas fa-sort sort-icon"></i>
                        </th>""" + (f"""
                        <th class="sortable" data-column="triage" onclick="sortTable('{repo_id}', 'triage')">
                            Triage <i class="fas fa-sort sort-icon"></i>
                        </th>
                        <th class="sortable" data-column="priority" onclick="sortTable('{repo_id}', 'priority')">
                            Priority <i class="fas fa-sort sort-icon"></i>
                        </th>""" if data_type == 'issues' else f"""
                        <th class="sortable" data-column="status" onclick="sortTable('{repo_id}', 'status')">
                            Status <i class="fas fa-sort sort-icon"></i>
                        </th>""") + f"""
                    </tr>
                </thead>
                <tbody>
                    {empty_message}
                </tbody>
            </table>
            <!-- No pagination needed for empty tables -->
        </div>
    </div>
    """

def generate_repo_section(repo, data_items, is_first=False, current_state='open', data_type='issues'):
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
    data_count = len(data_items)
    
    # Set CSS classes for visibility - no repo is active by default
    active_class = ""
    
    # Generate data rows (issues or PRs)
    data_rows = ""
    for i, item in enumerate(data_items):  # Show ALL items, pagination will handle display
        try:
            created_date = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
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
            if item['updated_at']:
                updated_date = datetime.fromisoformat(item['updated_at'].replace('Z', '+00:00'))
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
                updated_display = item['updated_at'][:10]
            else:
                updated_age_class = "unknown"
                updated_display = 'N/A'
        except:
            updated_age_class = "unknown"
            updated_display = item['updated_at'][:10] if item['updated_at'] else 'N/A'
        
        # Get assignee information (support both new multiple assignees and old single assignee)
        assignees = item.get('assignees', [])
        fallback_assignee = item.get('assignee_login')
        
        if data_type == 'prs':
            # For PRs, get author and reviewers
            author_login = item.get('user_login', 'Unknown')
            reviewers = item.get('requested_reviewers', [])
            
            # Format reviewers for display
            if isinstance(reviewers, str):
                try:
                    reviewers = json.loads(reviewers)
                except:
                    reviewers = []
            
            reviewer_display = format_assignees_for_display(reviewers, None) if reviewers else 'None'
            
            # For sorting, use author login
            assignee_sort_key = author_login.lower() if author_login else 'zzz_unknown'
            
            # Set PR status
            pr_status = "Draft" if item.get('draft', False) else ("Merged" if item.get('merged', False) else item.get('state', 'open').title())
            
        else:
            # For Issues, use existing assignee logic
            assignee_display = format_assignees_for_display(assignees, fallback_assignee)
            
            # For sorting purposes, create a simplified assignee string
            if assignees and len(assignees) > 0:
                assignee_sort_key = assignees[0].get('login', 'zzz_unassigned').lower()
            elif fallback_assignee:
                assignee_sort_key = fallback_assignee.lower()
            else:
                assignee_sort_key = 'zzz_unassigned'
        
        # Extract PR references from issue body instead of using database linked_pr field
        # pr_references = extract_pr_references(item.get('body', ''), repo)
        # pr_display = format_pr_references(pr_references)
        
        # Format labels for display
        labels_display = format_labels_for_display(item.get('labels', []))
        
        # Format mentions for display (kept for modal, but not displayed in table)
        # mentions_display = format_mentions_for_display(item.get('mentioned_handles', []))
        
        # Get triage and priority information (only for issues)
        if data_type == 'issues':
            triage = item.get('triage', 0)
            priority = item.get('priority', -1)
        else:
            triage = 0
            priority = -1
        
        # Get parsed assignees (should already be a list from database loading)
        assignees_data = item.get('assignees', [])
        print(f"DEBUG: Item #{item['number']} assignees: {assignees_data} (type: {type(assignees_data)})")
        
        # Prepare safe JSON data for modal (properly escaped for JavaScript)
        modal_data = {
            'repo': repo,
            'number': item['number'],
            'title': item['title'],
            'htmlUrl': item['html_url'],
            'body': item.get('body', ''),
            'dataType': data_type,
            'comments': item.get('comments', ''),
            'labels': item.get('labels', []),
            'mentions': item.get('mentioned_handles', [])
        }
        
        # Add data-type specific fields
        if data_type == 'prs':
            modal_data.update({
                'author': author_login,
                'reviewers': reviewers,
                'status': pr_status,
                'draft': item.get('draft', False),
                'merged': item.get('merged', False),
                'baseRef': item.get('base_ref', ''),
                'headRef': item.get('head_ref', '')
            })
        else:
            modal_data.update({
                'triage': triage,
                'priority': priority,
                'assignees': assignees_data
            })
        
        # Convert to JSON and escape for HTML attributes
        modal_data_json = html.escape(json.dumps(modal_data))
        
        data_rows += f"""
        <tr data-repo="{html.escape(repo)}" data-number="{item['number']}" 
            data-title="{html.escape(item['title'].lower())}" 
            data-assignee="{html.escape(assignee_sort_key)}"
            data-created="{html.escape(item['created_at'])}" 
            data-updated="{html.escape(item['updated_at'])}"
            data-state="{html.escape(item.get('state', 'open'))}"
            {'data-triage="' + str(triage) + '" data-priority="' + str(priority) + '"' if data_type == 'issues' else 'data-status="' + html.escape(pr_status) + '"'}>
            <td style="text-align: center;">
                <a href="{item['html_url']}" target="_blank" class="btn btn-sm btn-outline-dark github-btn" title="View on GitHub">
                    <i class="fab fa-github"></i>
                </a>
            </td>
            <td>
                <a href="#" class="issue-title-link" 
                   data-modal-data="{modal_data_json}"
                   onclick="openIssueModalFromData(this); return false;"
                   title="Click to edit {'issue' if data_type == 'issues' else 'pull request'} details">
                    #{item['number']} - {html.escape(item['title'])}
                </a>
            </td>""" + (f"""
            <td>{author_login}</td>
            <td>{reviewer_display}</td>""" if data_type == 'prs' else f"""
            <td>{assignee_display}</td>""") + f"""
            <td>{labels_display}</td>
            <td class="{created_age_class}">{item['created_at'][:10]}</td>
            <td class="{updated_age_class}">{updated_display}</td>""" + (f"""
            <td class="triage-display">
                {format_triage_text(triage)}
            </td>
            <td class="priority-display">
                {format_priority_text(priority)}
            </td>""" if data_type == 'issues' else f"""
            <td class="status-display">
                <span class="badge badge-{'success' if pr_status == 'Merged' else 'secondary' if pr_status == 'Draft' else 'primary'}">{pr_status}</span>
            </td>""") + f"""
        </tr>
        """
    
    # Get state button text
    state_button_text = get_state_button_text(current_state)
    
    return f"""
    <div class="repo-section{active_class} {color_class}" id="repo-{repo_id}" data-language="{lang_class}" data-repo-name="{repo}" data-category="{repo_category}">
        <div class="repo-header{active_class} {color_class}" onclick="toggleSection('{repo_id}')">
            <h2>
                <a href="https://github.com/{repo}" target="_blank">{repo_name}</a>
                <span class="category-badge {color_class}">{data_count}</span>
                <span class="category-badge {color_class}">{repo_category.upper()}</span>
            </h2>
        </div>
        <div class="controls d-flex justify-content-between align-items-center">
            <input type="text" class="form-control search-box" id="search-{repo_id}" 
                   placeholder="🔍 Search {data_type}..." 
                   onkeyup="filterTable('{repo_id}', this.value)" style="flex: 1; margin-right: 10px;">
            <div class="data-type-indicator">
                <span class="badge badge-info">{data_type.title()}</span>
            </div>
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
        
        <!-- Age Classification Legend (for repository view only) -->
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color recent"></div>
                <span>0-14 days (Recent)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color medium"></div>
                <span>15-30 days (Medium)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color old"></div>
                <span>31-60 days (Old)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color stale"></div>
                <span>60+ days (Stale)</span>
            </div>
        </div>
        
        <div class="table-container">
            <table class="table table-hover table-striped issues-table {color_class} {state_class}" id="table-{repo_id}">
                <thead class="table-header {color_class}" {header_style}>
                    <tr>
                        <th style="width: 60px;">Actions</th>
                        <th class="sortable" data-column="title" onclick="sortTable('{repo_id}', 'title')">
                            Title <i class="fas fa-sort sort-icon"></i>
                        </th>""" + (f"""
                        <th class="sortable" data-column="author" onclick="sortTable('{repo_id}', 'author')">
                            Author <i class="fas fa-sort sort-icon"></i>
                        </th>
                        <th class="sortable" data-column="reviewers" onclick="sortTable('{repo_id}', 'reviewers')">
                            Reviewers <i class="fas fa-sort sort-icon"></i>
                        </th>""" if data_type == 'prs' else f"""
                        <th class="sortable" data-column="assignee" onclick="sortTable('{repo_id}', 'assignee')">
                            Assignees <i class="fas fa-sort sort-icon"></i>
                        </th>""") + f"""
                        <th>Labels</th>
                        <th class="sortable" data-column="created" onclick="sortTable('{repo_id}', 'created')">
                            Created <i class="fas fa-sort sort-icon"></i>
                        </th>
                        <th class="sortable" data-column="updated" onclick="sortTable('{repo_id}', 'updated')">
                            Updated <i class="fas fa-sort sort-icon"></i>
                        </th>""" + (f"""
                        <th class="sortable" data-column="triage" onclick="sortTable('{repo_id}', 'triage')">
                            Triage <i class="fas fa-sort sort-icon"></i>
                        </th>
                        <th class="sortable" data-column="priority" onclick="sortTable('{repo_id}', 'priority')">
                            Priority <i class="fas fa-sort sort-icon"></i>
                        </th>""" if data_type == 'issues' else f"""
                        <th class="sortable" data-column="status" onclick="sortTable('{repo_id}', 'status')">
                            Status <i class="fas fa-sort sort-icon"></i>
                        </th>""") + f"""
                    </tr>
                </thead>
                <tbody>
                    {data_rows}
                </tbody>
            </table>
            <!-- Pagination controls -->
            <div class="d-flex justify-content-between align-items-center pagination" id="pagination-{repo_id}" style="display: none;">
                <div class="pagination-info text-muted" id="page-info-{repo_id}">
                    Showing 1-10 of {data_count} {data_type}
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

@app.route('/')
def dashboard():
    """Main dashboard route"""
    # Create custom span for dashboard rendering
    if tracer:
        with tracer.start_as_current_span("dashboard_render") as span:
            span.set_attribute("user.name", "anonymous")
            span.set_attribute("user.email", "anonymous")
            return _dashboard_internal(span)
    else:
        return _dashboard_internal(None)

def _dashboard_internal(span=None):
    """Internal dashboard function with telemetry - SPA version"""
    print("🌐 Serving GitHub Issues Dashboard (SPA)...")
    logger.info("Dashboard request received")
    
    # Get parameters for initial state (SPA will handle the actual data loading)
    selected_repo = request.args.get('repo', '')
    selected_repo = unquote(selected_repo) if selected_repo else ''
    
    data_type = request.args.get('type', 'issues')
    if data_type not in ['issues', 'prs']:
        data_type = 'issues'
    
    show_state = request.args.get('state', 'open')
    if show_state not in ['open', 'closed', 'all']:
        show_state = 'open'
    
    if span:
        span.set_attribute("dashboard.selected_repo", selected_repo)
        span.set_attribute("dashboard.data_type", data_type)
        span.set_attribute("dashboard.show_state", show_state)
        span.set_attribute("request.method", "GET")
        span.set_attribute("request.user_agent", request.headers.get('User-Agent', 'unknown'))
        span.set_attribute("dashboard.spa_mode", True)
        logger.info(f"Dashboard SPA mode with selected_repo: {selected_repo}, type: {data_type}, state: {show_state}")
    
    # Get sync stats for initial page load
    sync_stats = get_sync_statistics()
    
    if span:
        span.set_attribute("dashboard.sync_in_progress", sync_stats.get('in_progress', False))
    
    # Render minimal template - SPA will populate the content
    return render_template('dashboard.html',
                         selected_repo=selected_repo,
                         data_type=data_type,
                         show_state=show_state,
                         sync_stats=sync_stats)
    
    # If no data found, we'll render the template with empty sections
    # This ensures the UI is always consistent with navigation and toggle
    if not data_items:
        if span:
            span.set_attribute("dashboard.empty_state", True)
    
    # Group data by repository (will be empty dict if no data)
    repo_groups = group_issues_by_repo(data_items)  # Note: function name is generic for both issues and PRs
    
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
    dotnet_nav_links = ""
    java_nav_links = ""
    
    nodejs_count = 0
    python_count = 0
    browser_count = 0
    dotnet_count = 0
    java_count = 0
    is_first = True
    
    # Get all configured repositories in sorted order (Azure, OpenTelemetry, Microsoft)
    all_repositories = get_all_configured_repositories()
    
    # Generate repository sections for repos with data
    for repo, repo_data in repo_groups.items():
        repo_id = repo.replace('/', '-').replace('.', '-')
        repo_sections += generate_repo_section(repo, repo_data, is_first, show_state, data_type)
        is_first = False
    
    # Generate empty sections for repos without data in current state
    for repo in all_repositories:
        if repo not in repo_groups:
            repo_sections += generate_empty_repo_section(repo, show_state, data_type)
    
    # Generate navigation links for ALL repositories (sorted by priority)
    for repo in all_repositories:
        repo_id = repo.replace('/', '-').replace('.', '-')
        repo_name = repo.split('/')[-1]
        
        # Get issue count for this repo (0 if no issues)
        issue_count = len(repo_groups.get(repo, []))
        
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
        elif repo in ['Azure/azure-sdk-for-net', 'microsoft/ApplicationInsights-dotnet']:
            dotnet_nav_links += nav_link
            dotnet_count += issue_count
        elif repo in ['open-telemetry/opentelemetry-dotnet']:
            # OpenTelemetry .NET goes with other OpenTelemetry repos - determine based on primary language
            # Since it's .NET, it makes sense to group with other .NET repos despite being OpenTelemetry
            dotnet_nav_links += nav_link  
            dotnet_count += issue_count
        elif repo in ['open-telemetry/opentelemetry-java', 'microsoft/ApplicationInsights-Java']:
            java_nav_links += nav_link
            java_count += issue_count
        else:
            browser_nav_links += nav_link
            browser_count += issue_count
    
    # Get sync statistics
    sync_stats = get_sync_statistics()
    
    # Prepare template context
    template_context = {
        'selected_repo': selected_repo,
        'data_type': data_type,
        'repo_sections': repo_sections,
        'sync_stats': sync_stats,
        'nodejs_nav_links': nodejs_nav_links,
        'python_nav_links': python_nav_links,
        'browser_nav_links': browser_nav_links,
        'dotnet_nav_links': dotnet_nav_links,
        'java_nav_links': java_nav_links,
        'nodejs_count': nodejs_count,
        'python_count': python_count,
        'browser_count': browser_count,
        'dotnet_count': dotnet_count,
        'java_count': java_count,
        'current_state': show_state,
        'group_counts_script': f'''
        <script>
            // Update navbar badge counts
            document.getElementById('navbar-nodejs-count').textContent = '{nodejs_count}';
            document.getElementById('navbar-python-count').textContent = '{python_count}';
            document.getElementById('navbar-browser-count').textContent = '{browser_count}';
            document.getElementById('navbar-dotnet-count').textContent = '{dotnet_count}';
            document.getElementById('navbar-java-count').textContent = '{java_count}';
            
            // Set current state for state toggle functionality
            window.currentState = '{show_state}';
        </script>
        '''
    }
    
    # Render the dashboard template
    return render_template('dashboard.html', **template_context)
    repo_sections = ""
    nodejs_nav_links = ""
    python_nav_links = ""
    browser_nav_links = ""
    dotnet_nav_links = ""
    java_nav_links = ""
    
    nodejs_count = 0
    python_count = 0
    browser_count = 0
    dotnet_count = 0
    java_count = 0
    is_first = True
    
    # Get all configured repositories in sorted order (Azure, OpenTelemetry, Microsoft)
    all_repositories = get_all_configured_repositories()
    
    # Generate repository sections for repos with data
    for repo, repo_data in repo_groups.items():
        repo_id = repo.replace('/', '-').replace('.', '-')
        repo_sections += generate_repo_section(repo, repo_data, is_first, show_state, data_type)
        is_first = False
    
    # Generate empty sections for repos without data in current state
    for repo in all_repositories:
        if repo not in repo_groups:
            repo_sections += generate_empty_repo_section(repo, show_state, data_type)
    
    # Generate navigation links for ALL repositories (sorted by priority)
    for repo in all_repositories:
        repo_id = repo.replace('/', '-').replace('.', '-')
        repo_name = repo.split('/')[-1]
        
        # Get issue count for this repo (0 if no issues)
        issue_count = len(repo_groups.get(repo, []))
        
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
        elif repo in ['Azure/azure-sdk-for-net', 'microsoft/ApplicationInsights-dotnet']:
            dotnet_nav_links += nav_link
            dotnet_count += issue_count
        elif repo in ['open-telemetry/opentelemetry-dotnet']:
            # OpenTelemetry .NET goes with other OpenTelemetry repos - determine based on primary language
            # Since it's .NET, it makes sense to group with other .NET repos despite being OpenTelemetry
            dotnet_nav_links += nav_link  
            dotnet_count += issue_count
        elif repo in ['open-telemetry/opentelemetry-java', 'microsoft/ApplicationInsights-Java']:
            java_nav_links += nav_link
            java_count += issue_count
        else:
            browser_nav_links += nav_link
            browser_count += issue_count
    
    # Handle completely empty state - when no repositories have been synced at all
    if not all_repositories:
        # If no repositories at all configured, show the full empty state
        state_display = show_state.title()
        empty_state_message = """
        <div class="empty-state-container">
            <div class="empty-state-content">
                <div class="empty-state-icon">
                    <i class="fas fa-database"></i>
                </div>
                <h3>No Issues Found</h3>
                <p class="text-muted">No repositories configured. Please check the REPOSITORIES configuration.</p>
                <div class="empty-state-actions">
                    <a href="/sync" class="btn btn-primary">
                        <i class="fas fa-sync"></i> Sync Now
                    </a>
                    <a href="https://github.com/hectorhdzg/github-issues-dashboard" target="_blank" class="btn btn-outline-secondary">
                        <i class="fab fa-github"></i> View Project
                    </a>
                </div>
            </div>
        </div>
        """
        
        # Add the empty state CSS if it's not already in the template
        empty_state_css = """
        <style>
        .empty-state-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 400px;
            padding: 2rem;
            background: white;
            border-radius: 8px;
            margin: 2rem auto;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .empty-state-content {
            text-align: center;
            max-width: 500px;
        }
        
        .empty-state-icon {
            font-size: 4rem;
            color: #6c757d;
            margin-bottom: 1.5rem;
        }
        
        .empty-state-content h3 {
            color: #495057;
            margin-bottom: 1rem;
        }
        
        .empty-state-content p {
            font-size: 1.1rem;
            margin-bottom: 2rem;
        }
        
        .empty-state-actions .btn {
            margin: 0 0.5rem;
        }
        </style>
        """
        
        repo_sections = empty_state_css + empty_state_message
    
    # Calculate statistics
    total_repos = len(all_repositories)  # Count all configured repos, not just those with data
    total_items = len(data_items)
    recent_items = sum(1 for item in data_items if (datetime.now(timezone.utc) - datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))).days < 14)
    stale_items = sum(1 for item in data_items if (datetime.now(timezone.utc) - datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))).days > 60)
    
    # Get sync statistics
    sync_stats = get_sync_statistics()
    
    # Load template and replace all placeholders
    template = load_html_template()
    html = template.replace('{repo_sections}', repo_sections)
    html = html.replace('{nodejs_nav_links}', nodejs_nav_links)
    html = html.replace('{python_nav_links}', python_nav_links)
    html = html.replace('{browser_nav_links}', browser_nav_links)
    html = html.replace('{dotnet_nav_links}', dotnet_nav_links)
    html = html.replace('{java_nav_links}', java_nav_links)
    html = html.replace('{total_repos}', str(total_repos))
    html = html.replace('{total_issues}', str(total_items))
    html = html.replace('{recent_issues}', str(recent_items))
    html = html.replace('{stale_issues}', str(stale_items))
    html = html.replace('{database_info_text}', get_last_sync_time())
    html = html.replace('{selected_repo}', selected_repo)
    html = html.replace('{current_state}', show_state)
    html = html.replace('{current_data_type}', data_type)
    html = html.replace('{data_label}', data_label)
    html = html.replace('{data_label_singular}', data_label_singular)
    html = html.replace('{state_button_text}', get_state_button_text(show_state))
    
    # Add sync statistics replacements
    html = html.replace('{sync_stats_total_open}', str(sync_stats['total_open_issues']))
    html = html.replace('{sync_stats_total_closed}', str(sync_stats['total_closed_issues']))
    html = html.replace('{sync_stats_new_24h}', str(sync_stats['new_issues_24h']))
    html = html.replace('{sync_stats_updated_24h}', str(sync_stats['updated_issues_24h']))
    html = html.replace('{sync_stats_last_sync}', sync_stats['last_sync'])
    html = html.replace('{sync_stats_in_progress}', 'true' if sync_stats['sync_in_progress'] else 'false')
    html = html.replace('{sync_stats_errors}', str(sync_stats['sync_errors']))
    html = html.replace('{sync_stats_pr_processed}', str(sync_stats['processed_pr_mentions']))
    html = html.replace('{sync_stats_pr_percentage}', str(sync_stats['pr_processing_percentage']))
    
    # Generate repo stats table for sync section
    repo_stats_html = ""
    # Convert repo_stats dictionary to list of values for iteration
    repo_stats_list = list(sync_stats['repo_stats'].values()) if isinstance(sync_stats['repo_stats'], dict) else sync_stats['repo_stats']
    for repo_stat in repo_stats_list:
        repo_display_name = repo_stat['repo'].split('/')[-1]
        repo_stats_html += f'''
        <tr>
            <td class="repo-name">{repo_display_name}</td>
            <td><span class="badge badge-success">{repo_stat['open_count']}</span></td>
            <td><span class="badge badge-secondary">{repo_stat['closed_count']}</span></td>
            <td><span class="badge badge-info">{repo_stat['new_24h']}</span></td>
            <td><span class="badge badge-warning">{repo_stat['updated_24h']}</span></td>
            <td class="text-muted small">{repo_stat['last_updated']}</td>
        </tr>
        '''
    
    html = html.replace('{sync_repo_stats_table}', repo_stats_html)
    html = html.replace('{group_counts_script}', f'''
    <script>
        // Update navbar badge counts
        document.getElementById('navbar-nodejs-count').textContent = '{nodejs_count}';
        document.getElementById('navbar-python-count').textContent = '{python_count}';
        document.getElementById('navbar-browser-count').textContent = '{browser_count}';
        document.getElementById('navbar-dotnet-count').textContent = '{dotnet_count}';
        document.getElementById('navbar-java-count').textContent = '{java_count}';
        
        // Set current state for state toggle functionality
        window.currentState = '{show_state}';
    </script>
    ''')
    
    return html

def get_repository_language(repo_name):
    """Get the language category for a repository"""
    if repo_name in ['Azure/azure-sdk-for-python', 'open-telemetry/opentelemetry-python', 'open-telemetry/opentelemetry-python-contrib']:
        return 'python'
    elif repo_name in ['Azure/azure-sdk-for-js', 'open-telemetry/opentelemetry-js', 'open-telemetry/opentelemetry-js-contrib',
                      'microsoft/ApplicationInsights-node.js', 'microsoft/ApplicationInsights-node.js-native-metrics', 
                      'microsoft/node-diagnostic-channel']:
        return 'nodejs'
    elif repo_name in ['Azure/azure-sdk-for-net', 'microsoft/ApplicationInsights-dotnet', 'open-telemetry/opentelemetry-dotnet']:
        return 'dotnet'
    elif repo_name in ['open-telemetry/opentelemetry-java', 'microsoft/ApplicationInsights-Java']:
        return 'java'
    else:
        return 'browser'

def generate_stats_template(issues, pull_requests, sync_stats):
    """Generate the stats page HTML - DEPRECATED: Now using Flask templates"""
    # This function is deprecated and replaced with proper Flask template rendering
    # Keeping for reference but should not be used
    return "This function is deprecated. Use render_template('stats.html') instead."
    """Generate the stats page HTML"""
    
    # Create basic navbar links (same as dashboard)
    nodejs_nav_links = ""
    python_nav_links = ""
    browser_nav_links = ""
    dotnet_nav_links = ""
    java_nav_links = ""
    
    # Group repositories by language
    repos_by_language = {
        'nodejs': [],
        'python': [],
        'browser': [],
        'dotnet': [],
        'java': []
    }
    
    for repo_name in REPOSITORIES:
        language = get_repository_language(repo_name)
        if language in repos_by_language:
            repos_by_language[language].append(repo_name)
    
    # Generate navigation links for each language
    for language, repos in repos_by_language.items():
        nav_links = ""
        total_count = 0
        for repo_name in repos:
            safe_name = quote(repo_name)
            display_name = repo_name.replace("opentelemetry-", "").replace("azure-", "").replace("dotnet-", "").replace("java-", "")
            repo_issues = [issue for issue in issues if issue['repo'] == repo_name]
            open_count = len([issue for issue in repo_issues if issue['state'] == 'open'])
            total_count += open_count
            
            nav_links += f'''
                <a class="dropdown-item otel-theme" href="/?repo={safe_name}">
                    <span class="nav-repo-name">{display_name}</span>
                    <span class="badge badge-primary ml-auto">{open_count}</span>
                </a>
            '''
        
        # Store the navigation links and counts
        if language == 'nodejs':
            nodejs_nav_links = nav_links
        elif language == 'python':
            python_nav_links = nav_links
        elif language == 'browser':
            browser_nav_links = nav_links
        elif language == 'dotnet':
            dotnet_nav_links = nav_links
        elif language == 'java':
            java_nav_links = nav_links
    
    # Calculate statistics
    total_repos = len(REPOSITORIES)
    total_issues = len(issues)
    total_prs = len(pull_requests)
    recent_issues = sum(1 for issue in issues if (datetime.now(timezone.utc) - datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))).days < 14)
    stale_issues = sum(1 for issue in issues if (datetime.now(timezone.utc) - datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))).days > 60)
    
    # Generate repo stats table
    repo_stats_html = ""
    # Convert repo_stats dictionary to list of values for iteration
    repo_stats_list = list(sync_stats['repo_stats'].values()) if isinstance(sync_stats['repo_stats'], dict) else sync_stats['repo_stats']
    for repo_stat in repo_stats_list:
        repo_stats_html += f"""
        <tr>
            <td><strong>{repo_stat['repo']}</strong></td>
            <td><span class="badge badge-success">{repo_stat['open_count']}</span></td>
            <td><span class="badge badge-secondary">{repo_stat['closed_count']}</span></td>
            <td><span class="badge badge-info">{repo_stat['new_24h']}</span></td>
            <td><span class="badge badge-warning">{repo_stat['updated_24h']}</span></td>
            <td><small class="text-muted">{repo_stat['last_updated']}</small></td>
        </tr>
        """
    
    # Create stats page content (no data type toggle, just stats)
    stats_content = f"""
        <div class="intro-page">
            <div class="intro-content">
                <div class="intro-header">
                    <i class="fas fa-chart-bar intro-icon"></i>
                    <h1>Repository Statistics</h1>
                    <p class="intro-subtitle">Comprehensive overview of all repositories</p>
                </div>
                
                <div class="intro-stats">
                    <h3>Repository Overview</h3>
                    <div class="stats-grid">
                        <div class="stat-item">
                            <span class="stat-number">{total_repos}</span>
                            <span class="stat-label">Total Repositories</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-number">{total_issues}</span>
                            <span class="stat-label">Total Issues</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-number">{total_prs}</span>
                            <span class="stat-label">Total Pull Requests</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-number text-info">{recent_issues}</span>
                            <span class="stat-label">Recent Issues (14 days)</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-number text-warning">{stale_issues}</span>
                            <span class="stat-label">Stale Issues (60+ days)</span>
                        </div>
                    </div>
                    
                    <!-- Sync Statistics Section -->
                    <div class="sync-stats-section">
                        <h4><i class="fas fa-sync-alt"></i> Sync Status</h4>
                        <div class="row">
                            <div class="col-md-3">
                                <div class="sync-stat-card">
                                    <div class="sync-stat-number text-success">{sync_stats['total_open_issues']}</div>
                                    <div class="sync-stat-label">Total Open</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="sync-stat-card">
                                    <div class="sync-stat-number text-secondary">{sync_stats['total_closed_issues']}</div>
                                    <div class="sync-stat-label">Total Closed</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="sync-stat-card">
                                    <div class="sync-stat-number text-info">{sync_stats['new_issues_24h']}</div>
                                    <div class="sync-stat-label">New (24h)</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="sync-stat-card">
                                    <div class="sync-stat-number text-warning">{sync_stats['updated_issues_24h']}</div>
                                    <div class="sync-stat-label">Updated (24h)</div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="sync-info-section">
                            <p><strong>Last Sync:</strong> {sync_stats['last_sync']}</p>
                            <p><strong>Sync Status:</strong> {'In Progress' if sync_stats['sync_in_progress'] else 'Completed'}</p>
                            {f"<p><strong>Sync Errors:</strong> {sync_stats['sync_errors']}</p>" if sync_stats['sync_errors'] > 0 else ""}
                        </div>
                    </div>
                    
                    <!-- Repository Stats Table -->
                    <div class="repo-stats-table">
                        <h5><i class="fas fa-table"></i> Repository Breakdown</h5>
                        <div class="table-responsive">
                            <table class="table table-sm table-hover">
                                <thead class="thead-light">
                                    <tr>
                                        <th>Repository</th>
                                        <th><i class="fas fa-exclamation-circle text-success"></i> Open</th>
                                        <th><i class="fas fa-check-circle text-secondary"></i> Closed</th>
                                        <th><i class="fas fa-plus text-info"></i> New (24h)</th>
                                        <th><i class="fas fa-edit text-warning"></i> Updated (24h)</th>
                                        <th><i class="fas fa-clock"></i> Last Updated</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {repo_stats_html}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                <div class="intro-actions">
                    <div class="action-section">
                        <h3>About This Project</h3>
                        <p>This dashboard is built to help manage GitHub issues across Azure Monitor TelReach SDKs.</p>
                        <a href="https://github.com/hectorhdzg/github-issues-dashboard" target="_blank" class="github-link">
                            <i class="fab fa-github"></i>
                            View on GitHub
                        </a>
                    </div>
                </div>
            </div>
        </div>
    """
    
    # Load template and replace placeholders
    template = load_html_template()
    
    # For stats page, hide the data type toggle and show stats content
    stats_template = template.replace('class="global-data-type-toggle"', 'class="global-data-type-toggle" style="display: none;"')
    
    html = stats_template.replace('{repo_sections}', stats_content)
    html = html.replace('{nodejs_nav_links}', nodejs_nav_links)
    html = html.replace('{python_nav_links}', python_nav_links)
    html = html.replace('{browser_nav_links}', browser_nav_links)
    html = html.replace('{dotnet_nav_links}', dotnet_nav_links)
    html = html.replace('{java_nav_links}', java_nav_links)
    html = html.replace('{total_repos}', str(total_repos))
    html = html.replace('{total_issues}', str(total_issues))
    html = html.replace('{recent_issues}', str(recent_issues))
    html = html.replace('{stale_issues}', str(stale_issues))
    html = html.replace('{database_info_text}', get_last_sync_time())
    html = html.replace('{selected_repo}', '')  # No repo selected on stats page
    html = html.replace('{current_state}', 'open')
    html = html.replace('{current_data_type}', 'issues')
    html = html.replace('{data_label}', 'Issues')
    html = html.replace('{data_label_singular}', 'Issue')
    html = html.replace('{state_button_text}', 'Open Issues')
    
    # Add counts for navbar badges
    nodejs_count = len([issue for issue in issues if issue['repository'] in repos_by_language['nodejs']])
    python_count = len([issue for issue in issues if issue['repository'] in repos_by_language['python']])
    browser_count = len([issue for issue in issues if issue['repository'] in repos_by_language['browser']])
    dotnet_count = len([issue for issue in issues if issue['repository'] in repos_by_language['dotnet']])
    java_count = len([issue for issue in issues if issue['repository'] in repos_by_language['java']])
    
    # Add the script to update navbar counts
    html += f'''
    <script>
        // Update navbar counts
        document.getElementById('navbar-nodejs-count').textContent = '{nodejs_count}';
        document.getElementById('navbar-python-count').textContent = '{python_count}';
        document.getElementById('navbar-browser-count').textContent = '{browser_count}';
        document.getElementById('navbar-dotnet-count').textContent = '{dotnet_count}';
        document.getElementById('navbar-java-count').textContent = '{java_count}';
    </script>
    '''
    
    return html

@app.route('/stats')

def stats():
    """Stats page route"""
    # Create custom span for stats page rendering
    if tracer:
        with tracer.start_as_current_span("stats_render") as span:
            span.set_attribute("user.name", "anonymous")
            span.set_attribute("user.email", "anonymous")
            return _stats_internal(span)
    else:
        return _stats_internal(None)

def _stats_internal(span=None):
    """Internal stats function with telemetry"""
    print("📊 Serving Stats Page...")
    logger.info("Stats request received")
    
    if span:
        span.set_attribute("stats.page", "overview")
        span.set_attribute("request.method", "GET")
        logger.info("Stats telemetry span active")
    else:
        logger.warning("Stats telemetry span is None - telemetry may not be configured")
    
    # Load data from database
    issues = get_issues_from_db()
    pull_requests = get_pull_requests_from_db()
    
    # Get repository information and statistics
    sync_stats = get_sync_statistics()
    
    if span:
        span.set_attribute("stats.issues_count", len(issues))
        span.set_attribute("stats.pull_requests_count", len(pull_requests))
    
    # Calculate additional statistics
    total_prs = len(pull_requests)
    recent_issues = sum(1 for issue in issues if (datetime.now(timezone.utc) - datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))).days < 14)
    stale_issues = sum(1 for issue in issues if (datetime.now(timezone.utc) - datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))).days > 60)
    
    # Group repositories by language for navbar counts
    repos_by_language = {
        'nodejs': ['Azure/azure-sdk-for-js', 'open-telemetry/opentelemetry-js', 'open-telemetry/opentelemetry-js-contrib',
                   'microsoft/ApplicationInsights-node.js', 'microsoft/ApplicationInsights-node.js-native-metrics', 
                   'microsoft/node-diagnostic-channel'],
        'python': ['Azure/azure-sdk-for-python', 'open-telemetry/opentelemetry-python', 'open-telemetry/opentelemetry-python-contrib'],
        'browser': [],  # Add browser repos here if any
        'dotnet': ['Azure/azure-sdk-for-net', 'microsoft/ApplicationInsights-dotnet', 'open-telemetry/opentelemetry-dotnet'],
        'java': ['open-telemetry/opentelemetry-java', 'microsoft/ApplicationInsights-Java']
    }
    
    # Calculate navbar counts
    nodejs_count = len([issue for issue in issues if issue['repository'] in repos_by_language['nodejs']])
    python_count = len([issue for issue in issues if issue['repository'] in repos_by_language['python']])
    browser_count = len([issue for issue in issues if issue['repository'] in repos_by_language['browser']])
    dotnet_count = len([issue for issue in issues if issue['repository'] in repos_by_language['dotnet']])
    java_count = len([issue for issue in issues if issue['repository'] in repos_by_language['java']])
    
    # Generate navigation links (same as main dashboard)
    nodejs_nav_links = ""
    python_nav_links = ""
    browser_nav_links = ""
    dotnet_nav_links = ""
    java_nav_links = ""
    
    all_repositories = get_all_configured_repositories()
    for repo in all_repositories:
        repo_id = repo.replace('/', '-').replace('.', '-')
        repo_name = repo.split('/')[-1]
        
        # Get issue count for this repo (0 if no issues)
        issue_count = len([issue for issue in issues if issue['repository'] == repo])
        
        color_class = get_repo_color_class(repo)
        category = get_repo_category(repo)
        
        nav_link = f'''<a class="dropdown-item {color_class}" href="{url_for('dashboard')}?repo={repo}" data-category="{category}">
            <span class="nav-repo-name">{repo_name}</span>
            <span class="badge badge-light ml-auto">{issue_count}</span>
            <small class="category-indicator {color_class}">{category.upper()}</small>
        </a>'''
        
        # Categorize by language
        if repo in repos_by_language['python']:
            python_nav_links += nav_link
        elif repo in repos_by_language['nodejs']:
            nodejs_nav_links += nav_link
        elif repo in repos_by_language['dotnet']:
            dotnet_nav_links += nav_link
        elif repo in repos_by_language['java']:
            java_nav_links += nav_link
        else:
            browser_nav_links += nav_link
    
    # Use proper Flask template rendering
    return render_template('stats.html',
        sync_stats=sync_stats,
        total_prs=total_prs,
        recent_issues=recent_issues,
        stale_issues=stale_issues,
        nodejs_count=nodejs_count,
        python_count=python_count,
        browser_count=browser_count,
        dotnet_count=dotnet_count,
        java_count=java_count,
        nodejs_nav_links=nodejs_nav_links,
        python_nav_links=python_nav_links,
        browser_nav_links=browser_nav_links,
        dotnet_nav_links=dotnet_nav_links,
        java_nav_links=java_nav_links
    )

@app.route('/test')

def test_page():
    """UX Testing page for isolated UI/UX experiments"""
    # Create custom span for test page rendering
    if tracer:
        with tracer.start_as_current_span("test_page_render") as span:
            span.set_attribute("user.name", "anonymous")
            span.set_attribute("user.email", "anonymous")
            return _test_page_internal(span)
    else:
        return _test_page_internal(None)

def _test_page_internal(span=None):
    """Internal test page function with telemetry"""
    print("🧪 Serving UX Test Page...")
    logger.info("Test page request received")
    
    if span:
        span.set_attribute("test.page", "ux_testing")
        span.set_attribute("request.method", "GET")
        logger.info("Test page telemetry span active")
    else:
        logger.warning("Test page telemetry span is None - telemetry may not be configured")
    
    # Simple placeholder data for navbar (to avoid complex data loading)
    # This is just for testing UI components
    if span:
        span.set_attribute("test.navbar_data_loaded", True)
    
    # Render the test template with minimal navbar data
    return render_template('test.html', 
                         nodejs_count=42,
                         python_count=38,
                         browser_count=15,
                         dotnet_count=29,
                         java_count=12,
                         nodejs_nav_links='<a class="dropdown-item" href="#">Test Node.js Repo</a>',
                         python_nav_links='<a class="dropdown-item" href="#">Test Python Repo</a>',
                         browser_nav_links='<a class="dropdown-item" href="#">Test Browser Repo</a>',
                         dotnet_nav_links='<a class="dropdown-item" href="#">Test .NET Repo</a>',
                         java_nav_links='<a class="dropdown-item" href="#">Test Java Repo</a>',
                         current_state='open',  # Default state for testing
                         last_updated=datetime.now(PACIFIC_TZ).strftime('%m/%d %I:%M %p'))

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
        user = {"name": "anonymous", "email": "anonymous"}
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

def sync_page():
    """Sync management page using new template structure"""
    # Get sync statistics
    sync_stats = get_sync_statistics()
    
    # Render the sync template
    return render_template('sync.html', sync_stats=sync_stats)

@app.route('/sync_all')

def sync_all():
    """Trigger sync and redirect to sync page"""
    # Start sync in background
    threading.Thread(target=sync_all_repositories, daemon=True).start()
    
    # Redirect back to sync page with a message
    return redirect(url_for('sync_page'))

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

@app.route('/api/telemetry_test')

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

# ============================================================================
# SPA API ENDPOINTS
# ============================================================================

@app.route('/api/dashboard/data')

def api_dashboard_data():
    """API endpoint to get all dashboard data for SPA"""
    try:
        # Get query parameters
        data_type = request.args.get('type', 'issues')
        show_state = request.args.get('state', 'open')
        
        if data_type not in ['issues', 'prs']:
            data_type = 'issues'
        if show_state not in ['open', 'closed', 'all']:
            show_state = 'open'
        
        # Get data based on type
        if data_type == 'prs':
            data_items = get_pull_requests_from_db(state_filter=show_state)
        else:
            data_items = get_issues_from_db(state_filter=show_state)
        
        # Group data by repository
        repo_groups = group_issues_by_repo(data_items)
        
        # Get all configured repositories
        all_repositories = get_all_configured_repositories()
        
        # Calculate counts by SDK
        sdk_counts = {
            'nodejs': 0,
            'python': 0,
            'browser': 0,
            'dotnet': 0,
            'java': 0,
            'total': 0
        }
        
        # Count items by SDK type
        for repo, items in repo_groups.items():
            count = len(items)
            sdk_counts['total'] += count
            
            if 'azure-sdk-for-js' in repo:
                sdk_counts['nodejs'] += count
            elif 'azure-sdk-for-python' in repo:
                sdk_counts['python'] += count
            elif 'azure-sdk-for-browser' in repo:
                sdk_counts['browser'] += count
            elif 'azure-sdk-for-net' in repo:
                sdk_counts['dotnet'] += count
            elif 'azure-sdk-for-java' in repo:
                sdk_counts['java'] += count
        
        # Prepare repository data
        repositories = []
        for repo in all_repositories:
            repo_data = repo_groups.get(repo, [])
            repo_info = {
                'name': repo,
                'id': repo.replace('/', '-').replace('.', '-'),
                'display_name': repo.split('/')[-1],
                'items': repo_data,
                'count': len(repo_data),
                'sdk_type': get_sdk_type(repo)
            }
            repositories.append(repo_info)
        
        # Get sync status
        sync_stats = get_sync_statistics()
        
        response_data = {
            'data_type': data_type,
            'show_state': show_state,
            'sdk_counts': sdk_counts,
            'repositories': repositories,
            'sync_stats': sync_stats,
            'all_repositories': all_repositories
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in api_dashboard_data: {e}")
        return jsonify({'error': str(e)}), 500

def get_sdk_type(repo_name):
    """Determine SDK type from repository name"""
    repo_lower = repo_name.lower()
    
    # Browser JavaScript repositories (client-side)
    if ('applicationinsights-js' in repo_lower or
        'angularplugin-js' in repo_lower or 
        'react-js' in repo_lower or
        'react-native' in repo_lower or
        'azure-sdk-for-browser' in repo_lower):
        return 'browser'
    
    # Node.js repositories (server-side)
    elif ('azure-sdk-for-js' in repo_lower or 
          'node.js' in repo_lower or
          'opentelemetry-js' in repo_lower or
          'dynamicproto-js' in repo_lower or
          'node-diagnostic' in repo_lower):
        return 'nodejs'
    
    # Python repositories  
    elif ('azure-sdk-for-python' in repo_lower or
          'opentelemetry-python' in repo_lower):
        return 'python'
        
    # .NET repositories
    elif ('azure-sdk-for-net' in repo_lower or
          'insights-dotnet' in repo_lower or
          'opentelemetry-dotnet' in repo_lower):
        return 'dotnet'
        
    # Java repositories
    elif ('azure-sdk-for-java' in repo_lower or
          'insights-java' in repo_lower or
          'opentelemetry-java' in repo_lower):
        return 'java'
    
    else:
        return 'other'

@app.route('/api/repositories')

def api_repositories():
    """API endpoint to get all configured repositories"""
    try:
        repositories = get_all_configured_repositories()
        return jsonify({'repositories': repositories})
    except Exception as e:
        logger.error(f"Error in api_repositories: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/repository/<path:repo_name>')

def api_repository_data(repo_name):
    """API endpoint to get data for a specific repository"""
    try:
        data_type = request.args.get('type', 'issues')
        show_state = request.args.get('state', 'open')
        
        if data_type not in ['issues', 'prs']:
            data_type = 'issues'
        if show_state not in ['open', 'closed', 'all']:
            show_state = 'open'
        
        # Get data based on type
        if data_type == 'prs':
            all_items = get_pull_requests_from_db(state_filter=show_state)
        else:
            all_items = get_issues_from_db(state_filter=show_state)
        
        # Filter for specific repository
        repo_items = [item for item in all_items if item.get('repository_name') == repo_name]
        
        repo_info = {
            'name': repo_name,
            'id': repo_name.replace('/', '-').replace('.', '-'),
            'display_name': repo_name.split('/')[-1],
            'items': repo_items,
            'count': len(repo_items),
            'sdk_type': get_sdk_type(repo_name)
        }
        
        return jsonify(repo_info)
        
    except Exception as e:
        logger.error(f"Error in api_repository_data: {e}")
        return jsonify({'error': str(e)}), 500

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

