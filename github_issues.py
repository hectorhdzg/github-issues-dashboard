import requests
import csv
import sys
import time
import json
import math
import sqlite3
from datetime import datetime, timedelta, timezone

# Database setup
DB_NAME = "github_issues.db"

def init_database():
    """Initialize the SQLite database with required tables"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create issues table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY,
            repo TEXT NOT NULL,
            number INTEGER NOT NULL,
            title TEXT NOT NULL,
            html_url TEXT NOT NULL,
            assignee_login TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            body TEXT,
            state TEXT NOT NULL,
            linked_pr TEXT,
            triage INTEGER DEFAULT 0,
            priority INTEGER DEFAULT -1,
            last_fetched TEXT NOT NULL,
            UNIQUE(repo, number)
        )
    ''')
    
    # Add new columns to existing table if they don't exist
    try:
        cursor.execute('ALTER TABLE issues ADD COLUMN triage INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE issues ADD COLUMN priority INTEGER DEFAULT -1')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create repositories table to track last sync
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS repositories (
            repo TEXT PRIMARY KEY,
            last_sync TEXT NOT NULL,
            total_issues INTEGER DEFAULT 0
        )
    ''')
    
    # Create index for faster queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_repo_updated ON issues(repo, updated_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON issues(created_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_state ON issues(state)')
    
    conn.commit()
    conn.close()

def should_sync_repo(repo, max_age_hours=6):
    """Check if a repository needs to be synced based on last sync time"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT last_sync FROM repositories WHERE repo = ?', (repo,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return True  # Never synced before
    
    last_sync = datetime.fromisoformat(result[0])
    now = datetime.now(timezone.utc)
    
    return (now - last_sync).total_seconds() > (max_age_hours * 3600)

def update_repo_sync_time(repo, issue_count):
    """Update the last sync time for a repository"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute('''
        INSERT OR REPLACE INTO repositories (repo, last_sync, total_issues)
        VALUES (?, ?, ?)
    ''', (repo, now, issue_count))
    
    conn.commit()
    conn.close()

def save_issues_to_db(repo, issues):
    """Save or update issues in the database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    now = datetime.now(timezone.utc).isoformat()
    
    for issue in issues:
        linked_pr = extract_pr_links(issue.get("body", ""), repo)
        
        cursor.execute('''
            INSERT OR REPLACE INTO issues 
            (repo, number, title, html_url, assignee_login, created_at, updated_at, 
             body, state, linked_pr, last_fetched)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            repo,
            issue["number"],
            issue["title"],
            issue["html_url"],
            issue["assignee"]["login"] if issue["assignee"] else None,
            issue["created_at"],
            issue["updated_at"],
            issue.get("body", ""),
            issue["state"],
            linked_pr,
            now
        ))
    
    conn.commit()
    conn.close()

def get_issues_from_db(repo):
    """Retrieve issues for a repository from the database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT number, title, html_url, assignee_login, created_at, updated_at, linked_pr
        FROM issues 
        WHERE repo = ? AND state = 'open'
        ORDER BY created_at DESC
    ''', (repo,))
    
    issues = []
    for row in cursor.fetchall():
        issues.append({
            "number": row[0],
            "title": row[1],
            "html_url": row[2],
            "assignee.login": row[3],
            "created_at": row[4],
            "updated_at": row[5],
            "linked_pr": row[6]
        })
    
    conn.close()
    return issues

def get_db_stats():
    """Get database statistics"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM issues WHERE state = "open"')
    total_issues = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT repo) FROM issues')
    total_repos = cursor.fetchone()[0]
    
    # Get recent issues (last 2 weeks)
    two_weeks_ago = (datetime.now(timezone.utc) - timedelta(weeks=2)).isoformat()
    cursor.execute('SELECT COUNT(*) FROM issues WHERE state = "open" AND created_at >= ?', (two_weeks_ago,))
    recent_issues = cursor.fetchone()[0]
    
    # Get stale issues (older than 2 months)
    two_months_ago = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    cursor.execute('SELECT COUNT(*) FROM issues WHERE state = "open" AND updated_at < ?', (two_months_ago,))
    stale_issues = cursor.fetchone()[0]
    
    conn.close()
    return total_issues, total_repos, recent_issues, stale_issues

def cleanup_old_issues():
    """Remove closed issues and very old data"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Remove issues older than 6 months that are closed
    six_months_ago = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
    cursor.execute('DELETE FROM issues WHERE state != "open" AND last_fetched < ?', (six_months_ago,))
    
    conn.commit()
    conn.close()

repos = ["Azure/azure-sdk-for-python", "Azure/azure-sdk-for-js"]
microsoft_repos = [
    "microsoft/ApplicationInsights-node.js", 
    "microsoft/ApplicationInsights-js",
    "microsoft/applicationinsights-react-js",
    "microsoft/applicationinsights-react-native",
    "microsoft/applicationinsights-angularplugin-js",
    "microsoft/DynamicProto-JS",
    "microsoft/node-diagnostic-channel",
    "microsoft/ApplicationInsights-node.js-native-metrics"
]
opentelemetry_repos = [
    "open-telemetry/opentelemetry-js",
    "open-telemetry/opentelemetry-js-contrib",
    "open-telemetry/opentelemetry-python",
    "open-telemetry/opentelemetry-python-contrib"
]
labels = ["Monitor - Distro", "Monitor - Exporter", "Monitor - ApplicationInsights"]
headers = {"Accept": "application/vnd.github.v3+json"}

def fetch_issues(repo, label=None):
    base_url = f"https://api.github.com/repos/{repo}/issues"
    params = {"state": "open", "per_page": 100}
    if label:
        params["labels"] = label
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(base_url, headers=headers, params=params)
            
            # Check rate limit headers
            remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            
            if response.status_code == 403 and 'rate limit' in response.text.lower():
                if remaining == 0:
                    wait_time = reset_time - int(time.time()) + 5  # Add 5 seconds buffer
                    if wait_time > 0:
                        print(f"Rate limit exceeded. Waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                
            response.raise_for_status()
            
            # Add a small delay between requests to be respectful
            time.sleep(0.5)
            
            # Filter out pull requests, only return actual issues
            return [item for item in response.json() if "pull_request" not in item]
            
        except requests.exceptions.HTTPError as e:
            if attempt == max_retries - 1:
                print(f"Failed to fetch issues from {repo} with label {label}: {e}")
                return []
            print(f"Attempt {attempt + 1} failed, retrying...")
            time.sleep(2 ** attempt)  # Exponential backoff
        except Exception as e:
            print(f"Unexpected error fetching issues from {repo}: {e}")
            return []
    
    return []

def extract_pr_links(issue_body, repo):
    """Extract PR links from issue body"""
    if not issue_body:
        return ""
    
    import re
    
    # Pattern to match PR references like #123 or full URLs
    pr_patterns = [
        r"#(\d+)",  # #123
        rf"https://github.com/{repo}/pull/(\d+)",  # Full URL
        rf"github.com/{repo}/pull/(\d+)",  # Partial URL
    ]
    
    pr_numbers = set()
    for pattern in pr_patterns:
        matches = re.findall(pattern, issue_body)
        pr_numbers.update(matches)
    
    if pr_numbers:
        # Return the first PR found as a link
        first_pr = sorted(pr_numbers)[0]
        return f"https://github.com/{repo}/pull/{first_pr}"
    
    return ""

seen = set()
repo_results = {}

# Initialize database
init_database()

# Cleanup old data
cleanup_old_issues()

# Initialize results for each repo
for repo in repos:
    repo_results[repo] = []

for repo in microsoft_repos:
    repo_results[repo] = []

for repo in opentelemetry_repos:
    repo_results[repo] = []

print("🗃️  GitHub Issues Dashboard with Database Cache")
print("=" * 60)

# Check which repos need syncing and fetch accordingly
total_api_calls = 0
cached_repos = 0

# Fetch issues from Azure repos with specific labels
for repo in repos:
    if should_sync_repo(repo):
        print(f"🔄 Syncing {repo}...")
        repo_issues = []
        for label in labels:
            print(f"  - Fetching issues with label: {label}")
            issues = fetch_issues(repo, label)
            total_api_calls += 1
            for issue in issues:
                if issue["number"] not in seen:
                    seen.add(issue["number"])
                    repo_issues.append(issue)
        
        # Save to database
        save_issues_to_db(repo, repo_issues)
        update_repo_sync_time(repo, len(repo_issues))
        print(f"  ✅ Synced {len(repo_issues)} issues to database")
    else:
        print(f"📋 Using cached data for {repo}")
        cached_repos += 1
    
    # Load from database
    repo_results[repo] = get_issues_from_db(repo)
    print(f"  📊 Loaded {len(repo_results[repo])} issues from cache")

# Fetch all open issues from Microsoft repos (no label filtering)
for repo in microsoft_repos:
    if should_sync_repo(repo):
        print(f"🔄 Syncing {repo}...")
        issues = fetch_issues(repo)  # No label parameter
        total_api_calls += 1
        repo_issues = []
        for issue in issues:
            if issue["number"] not in seen:
                seen.add(issue["number"])
                repo_issues.append(issue)
        
        # Save to database
        save_issues_to_db(repo, repo_issues)
        update_repo_sync_time(repo, len(repo_issues))
        print(f"  ✅ Synced {len(repo_issues)} issues to database")
    else:
        print(f"📋 Using cached data for {repo}")
        cached_repos += 1
    
    # Load from database
    repo_results[repo] = get_issues_from_db(repo)
    print(f"  📊 Loaded {len(repo_results[repo])} issues from cache")

# Fetch all open issues from OpenTelemetry repos (no label filtering)
for repo in opentelemetry_repos:
    if should_sync_repo(repo):
        print(f"🔄 Syncing {repo}...")
        issues = fetch_issues(repo)  # No label parameter
        total_api_calls += 1
        repo_issues = []
        for issue in issues:
            if issue["number"] not in seen:
                seen.add(issue["number"])
                repo_issues.append(issue)
        
        # Save to database
        save_issues_to_db(repo, repo_issues)
        update_repo_sync_time(repo, len(repo_issues))
        print(f"  ✅ Synced {len(repo_issues)} issues to database")
    else:
        print(f"📋 Using cached data for {repo}")
        cached_repos += 1
    
    # Load from database
    repo_results[repo] = get_issues_from_db(repo)
    print(f"  📊 Loaded {len(repo_results[repo])} issues from cache")

print("\n" + "=" * 60)
print(f"📈 Sync Summary:")
print(f"   • API calls made: {total_api_calls}")
print(f"   • Repositories cached: {cached_repos}")
print(f"   • Cache efficiency: {(cached_repos/14)*100:.1f}%")
def get_age_class(date_str):
    """Get CSS class based on date age"""
    date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    two_weeks_ago = now - timedelta(weeks=2)
    one_month_ago = now - timedelta(days=30)
    two_months_ago = now - timedelta(days=60)
    
    if date >= two_weeks_ago:
        return "recent"  # Green
    elif date >= one_month_ago:
        return "medium"  # Yellow
    elif date >= two_months_ago:
        return "old"     # Red
    else:
        return "stale"   # Purple

def load_html_template():
    """Load the HTML template from file"""
    try:
        with open('dashboard_template.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print("⚠️  Warning: dashboard_template.html not found. Creating basic template...")
        return """
<!DOCTYPE html>
<html>
<head>
    <title>GitHub Issues Dashboard</title>
    <meta charset="UTF-8">
</head>
<body>
    <h1>GitHub Issues Dashboard</h1>
    <p>Template file not found. Please ensure dashboard_template.html exists.</p>
    {repo_sections}
</body>
</html>
"""

# Generate HTML sections for each repository
repo_sections = []
nodejs_nav_links = []
python_nav_links = []
browser_nav_links = []
total_issues = 0
recent_issues = 0
stale_issues = 0

# Count issues by language group
nodejs_total = 0
python_total = 0
browser_total = 0

# Define language groupings
nodejs_repos = [
    "Azure/azure-sdk-for-js",
    "microsoft/ApplicationInsights-node.js",
    "open-telemetry/opentelemetry-js",
    "open-telemetry/opentelemetry-js-contrib",
    "microsoft/node-diagnostic-channel",
    "microsoft/ApplicationInsights-node.js-native-metrics"
]

python_repos = [
    "Azure/azure-sdk-for-python",
    "open-telemetry/opentelemetry-python",
    "open-telemetry/opentelemetry-python-contrib"
]

# Browser JavaScript repos are the remaining Microsoft repos
browser_repos = [
    "microsoft/ApplicationInsights-js",
    "microsoft/applicationinsights-react-js",
    "microsoft/applicationinsights-react-native",
    "microsoft/applicationinsights-angularplugin-js",
    "microsoft/DynamicProto-JS"
]

for repo in repos + microsoft_repos + opentelemetry_repos:
    repo_name = repo.split('/')[1]
    clean_repo_id = repo.replace('/', '-').replace('.', '-')
    
    # Sort issues by creation date (newest first)
    sorted_issues = sorted(repo_results[repo], key=lambda x: x['created_at'], reverse=True)
    
    # Count issue stats
    repo_recent = 0
    repo_stale = 0
    now = datetime.now(timezone.utc)
    two_weeks_ago = now - timedelta(weeks=2)
    two_months_ago = now - timedelta(days=60)
    
    for issue in sorted_issues:
        created_date = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))
        if created_date >= two_weeks_ago:
            repo_recent += 1
        elif created_date < two_months_ago:
            repo_stale += 1
    
    total_issues += len(sorted_issues)
    recent_issues += repo_recent
    stale_issues += repo_stale
    
    # Generate navigation link for this repo
    nav_link = f'<a href="#" class="nav-link" onclick="setActiveRepo(\'{clean_repo_id}\')"><span>{repo_name}</span><span class="issue-count-badge">{len(sorted_issues)}</span></a>'
    
    # Categorize nav links by programming language and count issues
    if repo in nodejs_repos:
        nodejs_nav_links.append(nav_link)
        nodejs_total += len(sorted_issues)
    elif repo in python_repos:
        python_nav_links.append(nav_link)
        python_total += len(sorted_issues)
    elif repo in browser_repos:
        browser_nav_links.append(nav_link)
        browser_total += len(sorted_issues)
    
    # Generate table rows
    table_rows = ""
    if sorted_issues:
        for issue in sorted_issues:
            assignee = issue['assignee.login'] or ''
            created_date_str = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00')).strftime('%Y-%m-%d')
            updated_date_str = datetime.fromisoformat(issue['updated_at'].replace('Z', '+00:00')).strftime('%Y-%m-%d')
            
            created_class = get_age_class(issue['created_at'])
            updated_class = get_age_class(issue['updated_at'])
            
            pr_link_html = ""
            if issue.get('linked_pr'):
                pr_link_html = f'<a href="{issue["linked_pr"]}" class="pr-link" target="_blank">PR Link</a>'
            
            assignee_html = f'<span class="assignee">{assignee}</span>' if assignee else ''
            
            table_rows += f"""
            <tr>
                <td><span class="issue-number">#{issue['number']}</span></td>
                <td class="issue-title">
                    <a href="{issue['html_url']}" target="_blank">{issue['title']}</a>
                </td>
                <td class="{created_class}">{created_date_str}</td>
                <td>{assignee_html}</td>
                <td class="{updated_class}">{updated_date_str}</td>
                <td>
                    <select class="priority-select">
                        <option value="">-</option>
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                        <option value="4">4</option>
                    </select>
                </td>
                <td>
                    <input type="checkbox" class="triage-checkbox">
                </td>
                <td>{pr_link_html}</td>
            </tr>
            """
    else:
        table_rows = '<tr><td colspan="8" class="no-issues">No issues found</td></tr>'
    
    # Calculate pagination values
    total_pages = max(1, math.ceil(len(sorted_issues) / 15))
    items_shown = min(len(sorted_issues), 15)
    next_disabled = 'disabled' if len(sorted_issues) <= 15 else ''
    
    repo_section = f"""
    <div class="repo-section" id="repo-{clean_repo_id}">
        <div class="repo-header" onclick="setActiveRepo('{clean_repo_id}')">
            <div class="repo-name">📁 {repo}</div>
            <div class="issue-count">{len(sorted_issues)} issues</div>
        </div>
        <div id="content-{clean_repo_id}" class="repo-content">
            <div class="controls">
                <input type="text" class="search-box" placeholder="Search issues..." 
                       onkeyup="filterTable('{clean_repo_id}', this.value)">
                <span>Recent: {repo_recent} | Stale: {repo_stale}</span>
            </div>
            <table class="issues-table" id="table-{clean_repo_id}">
                <thead>
                    <tr>
                        <th>Issue #</th>
                        <th>Title</th>
                        <th>Created</th>
                        <th>Assignee</th>
                        <th>Last Activity</th>
                        <th>Priority</th>
                        <th>Triage</th>
                        <th>Linked PR</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
            <div class="pagination" id="pagination-{clean_repo_id}">
                <div class="pagination-info" id="page-info-{clean_repo_id}">
                    Showing 1-{items_shown} of {len(sorted_issues)} issues
                </div>
                <div class="pagination-controls">
                    <button class="pagination-btn" id="prev-btn-{clean_repo_id}" 
                            onclick="prevPage('{clean_repo_id}')" disabled>Previous</button>
                    <span id="page-counter-{clean_repo_id}">Page 1 of {total_pages}</span>
                    <input type="number" class="page-input" id="page-input-{clean_repo_id}" 
                           value="1" min="1" max="{total_pages}"
                           onchange="goToPage('{clean_repo_id}', this.value)">
                    <button class="pagination-btn" id="next-btn-{clean_repo_id}" 
                            onclick="nextPage('{clean_repo_id}')" {next_disabled}>Next</button>
                </div>
            </div>
        </div>
    </div>
    <script>
        // Initialize pagination for this table
        document.addEventListener('DOMContentLoaded', function() {{
            initializePagination('{clean_repo_id}', {len(sorted_issues)});
        }});
    </script>
    """
    repo_sections.append(repo_section)

# Get database statistics
db_total_issues, db_total_repos, db_recent_issues, db_stale_issues = get_db_stats()

print(f"\n📊 Dashboard Generation Complete!")
print(f"   • Database: {DB_NAME}")
print(f"   • Total issues in DB: {db_total_issues}")
print(f"   • Recent issues: {db_recent_issues}")
print(f"   • Stale issues: {db_stale_issues}")
print(f"   • Unique issues processed: {len(seen)}")

# Update the HTML template to include database info
html_template = load_html_template()

# Add database info section to the header
db_info_html = f"""
            <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 5px; margin-top: 1rem; font-size: 0.9rem;">
                <strong>📊 Data Source:</strong> SQLite Database ({DB_NAME}) • 
                <strong>API Calls:</strong> {total_api_calls} • 
                <strong>Cache Hit Rate:</strong> {(cached_repos/14)*100:.1f}% • 
                <strong>Last Update:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>"""

final_html = html_template.replace('{database_info}', db_info_html)
final_html = final_html.replace('{total_repos}', str(len(repos + microsoft_repos + opentelemetry_repos)))
final_html = final_html.replace('{total_issues}', str(total_issues))
final_html = final_html.replace('{recent_issues}', str(recent_issues))
final_html = final_html.replace('{stale_issues}', str(stale_issues))
final_html = final_html.replace('{nodejs_nav_links}', '\n                            '.join(nodejs_nav_links))
final_html = final_html.replace('{python_nav_links}', '\n                            '.join(python_nav_links))
final_html = final_html.replace('{browser_nav_links}', '\n                            '.join(browser_nav_links))
final_html = final_html.replace('{repo_sections}', '\n'.join(repo_sections))

# Add script to update group counts
group_counts_script = f"""
<script>
document.addEventListener('DOMContentLoaded', function() {{
    document.getElementById('nodejs-count').textContent = '{nodejs_total}';
    document.getElementById('python-count').textContent = '{python_total}';
    document.getElementById('browser-count').textContent = '{browser_total}';
}});
</script>
"""
final_html = final_html.replace('{group_counts_script}', group_counts_script)

# Save the HTML file
html_filename = "github_issues_dashboard.html"
with open(html_filename, 'w', encoding='utf-8') as f:
    f.write(final_html)

print(f"\n🎉 HTML dashboard '{html_filename}' has been created!")
print(f"📁 File size: {round(len(final_html)/1024, 1)} KB")
print(f"🔗 Repository sections: {len(repos + microsoft_repos + opentelemetry_repos)}")
print(f"📈 Performance improvement: ~{(cached_repos/14)*100:.0f}% faster due to caching")
print(f"\n💡 Next sync will occur in ~{6-(datetime.now().hour % 6)} hours or when manually run")

if total_api_calls == 0:
    print("⚡ Lightning fast! All data served from cache - no API calls needed!")
elif cached_repos > 0:
    print(f"🚀 Hybrid mode: {total_api_calls} fresh API calls + {cached_repos} cached repos")
