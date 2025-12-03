import sqlite3

conn = sqlite3.connect('data/github_issues.db')
cursor = conn.cursor()

print("Successful syncs with data:")
cursor.execute("""
    SELECT repository, sync_type, issues_new, prs_new, status, sync_date 
    FROM sync_history 
    WHERE status = 'success' AND (issues_new > 0 OR prs_new > 0) 
    ORDER BY created_at DESC 
    LIMIT 10
""")

for row in cursor.fetchall():
    repo, sync_type, issues_new, prs_new, status, sync_date = row
    print(f"  {repo} ({sync_type}): {issues_new} issues, {prs_new} PRs - {sync_date}")

print("\nAll recent sync history (last 5):")
cursor.execute("""
    SELECT repository, sync_type, issues_new, prs_new, status, error_message, sync_date
    FROM sync_history 
    ORDER BY created_at DESC 
    LIMIT 5
""")

for row in cursor.fetchall():
    repo, sync_type, issues_new, prs_new, status, error, sync_date = row
    print(f"  {repo} ({sync_type}): {issues_new} issues, {prs_new} PRs - {status}")
    if error:
        print(f"    Error: {error[:60]}...")

conn.close()