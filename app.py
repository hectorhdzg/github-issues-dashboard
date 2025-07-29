#!/usr/bin/env python3
"""
Fixed Simple Flask server for GitHub Issues Dashboard
Serves the dashboard using existing cached data with proper navigation
"""

from flask import Flask, render_template_string, jsonify, request
import sqlite3
import json
from datetime import datetime, timezone
import os
from urllib.parse import unquote

app = Flask(__name__)

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
                    print(f"Trying to connect to database at: {db_path}")
                    conn = sqlite3.connect(db_path)
                    conn.row_factory = sqlite3.Row
                    break
            except Exception as e:
                print(f"Failed to connect to database at {db_path}: {e}")
                continue
        
        if conn is None:
            print("No database found. Creating sample data.")
            return get_sample_issues()
        
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
        print(f"Successfully loaded {len(issues)} issues from database")
        return issues
    except Exception as e:
        print(f"Error getting issues from database: {e}")
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
        
        # Get linked PR information
        linked_pr = issue.get('linked_pr')
        if linked_pr:
            pr_number = linked_pr.split("/")[-1]
            pr_display = f'<a href="{linked_pr}" target="_blank">PR #{pr_number}</a>'
        else:
            pr_display = 'None'
        
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
                        <th>Linked PR</th>
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
    print("🌐 Serving GitHub Issues Dashboard...")
    
    # Get the selected repo from query parameter
    selected_repo = request.args.get('repo', '')
    selected_repo = unquote(selected_repo) if selected_repo else ''
    
    # Get issues from database
    issues = get_issues_from_db()
    if not issues:
        return "<h1>No issues found in database. Please run sync first.</h1>"
    
    # Group issues by repository
    repo_groups = group_issues_by_repo(issues)
    
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

@app.route('/health')
def health():
    """Simple health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    print("🚀 Starting Fixed GitHub Issues Dashboard Server...")
    print("=" * 60)
    print("📊 Dashboard will be available at http://localhost:5000")
    print("💡 Press Ctrl+C to stop the server")
    print("")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
