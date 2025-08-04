#!/usr/bin/env python3
"""
Sync Manager Module for GitHub Issues Dashboard
Handles all data synchronization logic separate from the main Flask app
"""

import os
import threading
import time
import requests
import schedule
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote, quote

# Import timezone support with fallback
try:
    from zoneinfo import ZoneInfo
    PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
except ImportError:
    # Fallback for Python < 3.9
    try:
        import pytz
        PACIFIC_TZ = pytz.timezone("America/Los_Angeles")
    except ImportError:
        # If neither is available, use a simple UTC offset approximation
        from datetime import timedelta
        class SimplePacificTZ(timezone):
            def __init__(self):
                super().__init__(timedelta(hours=-8), "Pacific")
        PACIFIC_TZ = SimplePacificTZ()

class GitHubSyncManager:
    """Manages GitHub data synchronization"""
    
    def __init__(self, db_path='github_issues.db', github_token=None):
        self.db_path = db_path
        self.github_token = github_token
        self.sync_in_progress = False
        self.sync_lock = threading.Lock()
        
        # Repository configuration
        self.repositories = [
            'open-telemetry/opentelemetry-js',
            'open-telemetry/opentelemetry-python',
            'open-telemetry/opentelemetry-browser-extension',
            'microsoft/ApplicationInsights-dotnet',
            'microsoft/ApplicationInsights-Java'
        ]
    
    def get_headers(self):
        """Get headers for GitHub API requests"""
        headers = {
            'User-Agent': 'GitHub-Issues-Dashboard/1.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        return headers
    
    def detect_closed_issues_without_sync(self):
        """Detect and update issues that were closed outside of our sync process"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all open issues from database
            cursor.execute("""
                SELECT repo, number, html_url 
                FROM issues 
                WHERE state = 'open'
            """)
            open_issues = cursor.fetchall()
            
            updated_count = 0
            headers = self.get_headers()
            
            for repo, number, html_url in open_issues:
                try:
                    # Check current status on GitHub
                    api_url = f"https://api.github.com/repos/{repo}/issues/{number}"
                    response = requests.get(api_url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        issue_data = response.json()
                        if issue_data['state'] == 'closed':
                            # Update the issue as closed
                            cursor.execute("""
                                UPDATE issues 
                                SET state = 'closed', 
                                    closed_at = ?,
                                    updated_at = ?
                                WHERE repo = ? AND number = ?
                            """, (
                                issue_data.get('closed_at'),
                                issue_data.get('updated_at'),
                                repo,
                                number
                            ))
                            updated_count += 1
                            print(f"✅ Updated issue #{number} in {repo} to closed")
                    
                    # Rate limiting
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"⚠️ Error checking issue #{number} in {repo}: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            if updated_count > 0:
                print(f"📊 Updated {updated_count} issues that were closed externally")
            
        except Exception as e:
            print(f"❌ Error in detect_closed_issues_without_sync: {e}")
    
    def sync_all_repositories(self):
        """Sync all configured repositories"""
        with self.sync_lock:
            if self.sync_in_progress:
                print("⚠️ Sync already in progress, skipping...")
                return False
            
            self.sync_in_progress = True
        
        try:
            print("🔄 Starting repository sync...")
            start_time = datetime.now(timezone.utc)
            
            # First detect any issues closed outside our sync
            self.detect_closed_issues_without_sync()
            
            # Sync each repository
            for repo in self.repositories:
                try:
                    print(f"📊 Syncing {repo}...")
                    self._sync_repository_issues(repo)
                    self._sync_repository_prs(repo)
                    time.sleep(1)  # Rate limiting
                except Exception as e:
                    print(f"❌ Error syncing {repo}: {e}")
                    continue
            
            # Update sync metadata
            self._update_sync_metadata(start_time)
            
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            print(f"✅ Sync completed in {duration:.1f} seconds")
            
            return True
            
        except Exception as e:
            print(f"❌ Critical error during sync: {e}")
            return False
        finally:
            with self.sync_lock:
                self.sync_in_progress = False
    
    def _sync_repository_issues(self, repo):
        """Sync issues for a specific repository"""
        # Implementation would go here - extracting from original app.py
        pass
    
    def _sync_repository_prs(self, repo):
        """Sync pull requests for a specific repository"""
        # Implementation would go here - extracting from original app.py
        pass
    
    def _update_sync_metadata(self, start_time):
        """Update sync metadata in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create metadata table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Update last sync time
            cursor.execute("""
                INSERT OR REPLACE INTO sync_metadata (key, value, updated_at)
                VALUES ('last_sync', ?, ?)
            """, (start_time.isoformat(), datetime.now(timezone.utc).isoformat()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"❌ Error updating sync metadata: {e}")
    
    def get_last_sync_time(self):
        """Get the last sync time from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT value FROM sync_metadata WHERE key = 'last_sync'
                ORDER BY updated_at DESC LIMIT 1
            """)
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result[0]
            return None
            
        except Exception as e:
            print(f"❌ Error getting last sync time: {e}")
            return None
    
    def get_sync_statistics(self):
        """Get synchronization statistics from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get issue counts by repository and state
            cursor.execute("""
                SELECT repo, state, COUNT(*) as count
                FROM issues
                GROUP BY repo, state
            """)
            
            issue_stats = {}
            for repo, state, count in cursor.fetchall():
                if repo not in issue_stats:
                    issue_stats[repo] = {}
                issue_stats[repo][state] = count
            
            # Get PR counts by repository and state
            cursor.execute("""
                SELECT repo, state, COUNT(*) as count
                FROM pull_requests
                GROUP BY repo, state
            """)
            
            pr_stats = {}
            for repo, state, count in cursor.fetchall():
                if repo not in pr_stats:
                    pr_stats[repo] = {}
                pr_stats[repo][state] = count
            
            # Get total counts
            cursor.execute("SELECT COUNT(*) FROM issues WHERE state = 'open'")
            total_open_issues = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM issues WHERE state = 'closed'")
            total_closed_issues = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM pull_requests WHERE state = 'open'")
            total_open_prs = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM pull_requests WHERE state = 'closed'")
            total_closed_prs = cursor.fetchone()[0]
            
            # Get last sync time
            last_sync = self.get_last_sync_time()
            
            conn.close()
            
            return {
                'total_open_issues': total_open_issues,
                'total_closed_issues': total_closed_issues,
                'total_open_prs': total_open_prs,
                'total_closed_prs': total_closed_prs,
                'issue_stats': issue_stats,
                'pr_stats': pr_stats,
                'last_sync': last_sync,
                'sync_in_progress': self.sync_in_progress,
                'errors': 0  # Could be enhanced to track errors
            }
            
        except Exception as e:
            print(f"❌ Error getting sync statistics: {e}")
            return self.get_default_sync_stats()
    
    def get_default_sync_stats(self):
        """Return default sync stats when database is unavailable"""
        return {
            'total_open_issues': 0,
            'total_closed_issues': 0,
            'total_open_prs': 0,
            'total_closed_prs': 0,
            'issue_stats': {},
            'pr_stats': {},
            'last_sync': None,
            'sync_in_progress': False,
            'errors': 0
        }
    
    def start_sync_scheduler(self):
        """Start the background sync scheduler"""
        try:
            # Schedule sync every 6 hours
            schedule.every(6).hours.do(self.sync_all_repositories)
            print("📅 Scheduled sync every 6 hours")
            
            # Check if initial sync is needed
            def check_and_run_initial_sync():
                try:
                    last_fetch = self.get_last_sync_time()
                    
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

# Global sync manager instance
sync_manager = None

def get_sync_manager():
    """Get or create the global sync manager instance"""
    global sync_manager
    if sync_manager is None:
        github_token = os.environ.get('GITHUB_TOKEN')
        sync_manager = GitHubSyncManager(github_token=github_token)
    return sync_manager
