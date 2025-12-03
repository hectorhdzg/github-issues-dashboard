

"""
GitHub Issues Sync Service
A dedicated service for synchronizing GitHub issues and pull requests data.
This service provides REST APIs for data synchronization operations.
"""

import os
import sys
import json
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
import os
import time
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Dict, List, Optional, Any
from uuid import uuid4
from flask import Flask, jsonify, request
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

# Enhanced import handling for requests module
requests = None
try:
    import requests
    print(f"SUCCESS: requests module loaded successfully from: {requests.__file__}")
except ImportError as e:
    print(f"WARNING: requests module not available - sync functionality will be limited. Error: {e}")
    # Enhanced diagnostic information
    print(f"Python executable: {sys.executable}")
    print(f"Python path: {sys.path}")
    print(f"PYTHONPATH environment: {os.environ.get('PYTHONPATH', 'Not set')}")

# Environment configuration
IS_AZURE = bool(os.environ.get('WEBSITE_SITE_NAME'))
DATABASE_PATH = os.environ.get('DATABASE_PATH', '/tmp/github_issues.db' if IS_AZURE else 'data/github_issues.db')

# Ensure database directory exists
if IS_AZURE:
    DATA_DIR = os.path.dirname(DATABASE_PATH)
    os.makedirs(DATA_DIR, exist_ok=True)

# Configure logging with rotation
if not os.path.exists('data'):
    os.makedirs('data')

# Clear any existing logging configuration
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Console handler for real-time monitoring
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s %(levelname)s:%(name)s:%(message)s')
console_handler.setFormatter(console_formatter)

# Rotating file handler for persistent logs
file_handler = RotatingFileHandler(
    'data/sync-service.log',
    maxBytes=10*1024*1024,  # 10MB per file
    backupCount=5,          # Keep 5 backup files
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s %(levelname)s:%(name)s:%(funcName)s:%(message)s')
file_handler.setFormatter(file_formatter)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler]
)
logger = logging.getLogger('sync-service')

logging.info("Sync service starting with rotating file logs (10MB max, 5 backups)")

# Initialize Flask application with static files support
app = Flask(__name__, 
            static_folder='ui',
            static_url_path='')
CORS(app)  # Enable CORS for all routes

class GitHubSyncService:
    """Service for synchronizing GitHub data"""

    def __init__(self, database_path: str):
        self.database_path = database_path
        self.base_url = "https://api.github.com"
        self.github_token = os.environ.get('GITHUB_TOKEN', '')
        self.headers: Dict[str, str] = {}
        if self.github_token:
            self.headers['Authorization'] = f'token {self.github_token}'

        # Heuristics for mapping repositories to language groupings used by the dashboard UI
        self.language_overrides = {
            'microsoft/applicationinsights-node.js': 'Node.js',
            'microsoft/applicationinsights-node.js-native-metrics': 'Node.js',
            'microsoft/node-diagnostic-channel': 'Node.js',
            'open-telemetry/opentelemetry-js': 'Node.js',
            'open-telemetry/opentelemetry-js-contrib': 'Node.js',
            'microsoft/applicationinsights-js': 'Web/Browser',
            'microsoft/applicationinsights-react-js': 'Web/Browser',
            'microsoft/applicationinsights-react-native': 'Web/Browser',
            'microsoft/applicationinsights-angularplugin-js': 'Web/Browser',
            'microsoft/dynamicproto-js': 'Web/Browser'
        }
        self.language_overrides = {key.lower(): value for key, value in self.language_overrides.items()}
        self.node_language_keywords = ('node', 'native-metrics', 'diagnostic-channel')
        self.browser_language_keywords = ('browser', 'react', 'react-native', 'angular', 'web', 'frontend', 'front-end', 'ui', 'spa')

        # Initialize database
        self._init_database()

        # Initialize automatic sync scheduler
        self.scheduler = BackgroundScheduler()
        self.auto_sync_enabled = True
        self._setup_automatic_sync()

        logger.info(f"GitHubSyncService initialized with database: {database_path}")

    def _get_last_sync_timestamp(self, repository: str, sync_type: str) -> Optional[str]:
        """Return the last recorded sync timestamp for the repository/type in ISO format."""
        try:
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT last_sync FROM sync_metadata WHERE repository = ? AND sync_type = ? ORDER BY id DESC LIMIT 1",
                (repository, sync_type)
            )
            row = cursor.fetchone()
            conn.close()
            if row and row['last_sync']:
                return row['last_sync']
        except Exception as exc:
            logger.warning(f"Unable to read last sync timestamp for {repository} ({sync_type}): {exc}")
        return None

    def _update_sync_metadata(
        self,
        repository: str,
        sync_type: str,
        status: str,
        items_synced: int = 0,
        error_message: Optional[str] = None,
        last_synced_at: Optional[str] = None
    ) -> None:
        """Upsert sync metadata so future runs can request only new data."""
        try:
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, last_sync FROM sync_metadata WHERE repository = ? AND sync_type = ?",
                (repository, sync_type)
            )
            row = cursor.fetchone()

            new_last_sync = last_synced_at
            if not new_last_sync:
                # Preserve existing timestamp if we do not have a newer value yet.
                new_last_sync = row['last_sync'] if row and row['last_sync'] else None

            if row:
                cursor.execute(
                    """
                    UPDATE sync_metadata
                    SET last_sync = ?, status = ?, items_synced = ?, error_message = ?
                    WHERE id = ?
                    """,
                    (new_last_sync, status, items_synced, error_message, row['id'])
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO sync_metadata (repository, sync_type, last_sync, status, items_synced, error_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (repository, sync_type, new_last_sync, status, items_synced, error_message)
                )

            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning(f"Unable to update sync metadata for {repository} ({sync_type}): {exc}")

    def _build_conditional_headers(self, last_sync_iso: Optional[str]) -> Dict[str, str]:
        """Clone default headers and add If-Modified-Since when we have historical data."""
        headers = dict(self.headers) if self.headers else {}
        if last_sync_iso:
            try:
                normalized = last_sync_iso.replace('Z', '+00:00') if last_sync_iso.endswith('Z') else last_sync_iso
                dt_value = datetime.fromisoformat(normalized)
                if dt_value.tzinfo is None:
                    dt_value = dt_value.replace(tzinfo=timezone.utc)
                headers['If-Modified-Since'] = format_datetime(dt_value.astimezone(timezone.utc), usegmt=True)
            except Exception as exc:
                logger.warning(f"Failed to format If-Modified-Since header from {last_sync_iso}: {exc}")
        return headers

    @staticmethod
    def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
        """Convert an ISO 8601 string into a timezone-aware datetime."""
        if not value:
            return None
        normalized = value.replace('Z', '+00:00') if value.endswith('Z') else value
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            logger.debug(f"Unable to parse timestamp value {value}")
            return None

    def _determine_language_group(
        self,
        repo_name: Optional[str],
        display_name: Optional[str],
        classification: Optional[str],
        main_category: Optional[str]
    ) -> str:
        """Infer the language grouping used by the dashboard navigation."""
        repo_key = (repo_name or '').lower()
        if repo_key in self.language_overrides:
            return self.language_overrides[repo_key]

        normalized_classification = (classification or '').strip().lower()
        if normalized_classification in ('.net', 'dotnet', 'c#', 'csharp', 'c-sharp'):
            return 'DotNet'
        if normalized_classification == 'python':
            return 'Python'
        if normalized_classification == 'java':
            return 'Java'

        if normalized_classification in ('javascript', 'typescript', 'node', 'node.js', 'nodejs'):
            combined = ' '.join(filter(None, (
                repo_name or '',
                display_name or '',
                main_category or '',
                classification or ''
            ))).lower()
            if any(keyword in combined for keyword in self.node_language_keywords):
                return 'Node.js'
            if any(keyword in combined for keyword in self.browser_language_keywords):
                return 'Web/Browser'
            return 'JavaScript'

        if normalized_classification:
            return classification if classification else 'Other'

        return 'Other'

    def _refresh_repository_language_groups(self, cursor: sqlite3.Cursor) -> None:
        """Ensure repositories.language_group is populated and up to date."""
        cursor.execute("PRAGMA table_info(repositories)")
        columns = {row[1] for row in cursor.fetchall()}
        if 'language_group' not in columns:
            return

        cursor.execute("SELECT repo, display_name, main_category, classification, language_group FROM repositories")
        for repo, display_name, main_category, classification, current_language in cursor.fetchall():
            inferred_language = self._determine_language_group(repo, display_name, classification, main_category)
            if inferred_language != (current_language or 'Other'):
                cursor.execute(
                    "UPDATE repositories SET language_group = ?, updated_at = datetime('now') WHERE repo = ?",
                    (inferred_language, repo)
                )
    
    def _init_database(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        # Create repositories table with updated schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repositories (
                repo TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                main_category TEXT NOT NULL,
                classification TEXT NOT NULL,
                language_group TEXT DEFAULT 'Other',
                priority INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                filters TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add filters column if it doesn't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE repositories ADD COLUMN filters TEXT DEFAULT '{}'")
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add language_group column for existing databases
        try:
            cursor.execute("ALTER TABLE repositories ADD COLUMN language_group TEXT DEFAULT 'Other'")
        except sqlite3.OperationalError:
            pass
        
        # Add sample repositories if table is empty
        cursor.execute("SELECT COUNT(*) FROM repositories")
        if cursor.fetchone()[0] == 0:
            import json
            
            # Define filter configurations for different repository types
            azure_sdk_filters = {
                "issues": {
                    "labels": ["bug", "feature-request", "question"],
                    "exclude_labels": ["duplicate", "wontfix"],
                    "state": "all"
                },
                "pull_requests": {
                    "state": "all",
                    "exclude_labels": ["work-in-progress"]
                }
            }
            
            appinsights_filters = {
                "issues": {
                    "labels": ["bug", "enhancement"],
                    "state": "open"
                },
                "pull_requests": {
                    "state": "all"
                }
            }
            
            opentelemetry_filters = {
                "issues": {
                    "labels": ["bug", "enhancement", "good first issue"],
                    "state": "all"
                },
                "pull_requests": {
                    "state": "all"
                }
            }
            
            sample_repos = [
                ('Azure/azure-sdk-for-js', 'Azure SDK for JavaScript', 'Azure SDK', 'JavaScript', 1, 1, json.dumps(azure_sdk_filters)),
                ('Azure/azure-sdk-for-python', 'Azure SDK for Python', 'Azure SDK', 'Python', 1, 1, json.dumps(azure_sdk_filters)),
                ('Azure/azure-sdk-for-net', 'Azure SDK for .NET', 'Azure SDK', 'DotNet', 1, 1, json.dumps(azure_sdk_filters)),
                ('microsoft/ApplicationInsights-js', 'Application Insights JavaScript SDK', 'Application Insights', 'JavaScript', 2, 1, json.dumps(appinsights_filters)),
                ('microsoft/ApplicationInsights-dotnet', 'Application Insights .NET SDK', 'Application Insights', 'DotNet', 2, 1, json.dumps(appinsights_filters)),
                ('open-telemetry/opentelemetry-js', 'OpenTelemetry JavaScript', 'OpenTelemetry', 'JavaScript', 3, 1, json.dumps(opentelemetry_filters)),
                ('open-telemetry/opentelemetry-python', 'OpenTelemetry Python', 'OpenTelemetry', 'Python', 3, 1, json.dumps(opentelemetry_filters))
            ]
            
            for repo_data in sample_repos:
                cursor.execute('''
                    INSERT OR IGNORE INTO repositories 
                    (repo, display_name, main_category, classification, priority, is_active, filters)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', repo_data)
            
            logger.info(f"Added {len(sample_repos)} sample repositories with filter configurations to database")

        # Ensure language group classifications are populated for all repositories
        self._refresh_repository_language_groups(cursor)
        
        # Create issues table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY,
                number INTEGER,
                title TEXT,
                body TEXT,
                state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                closed_at TIMESTAMP,
                labels TEXT,
                assignees TEXT,
                milestone TEXT,
                repository TEXT,
                url TEXT,
                user_login TEXT,
                user_avatar_url TEXT,
                comments_count INTEGER DEFAULT 0,
                UNIQUE(id)
            )
        ''')
        
        # Create pull_requests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pull_requests (
                id INTEGER PRIMARY KEY,
                number INTEGER,
                title TEXT,
                body TEXT,
                state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                closed_at TIMESTAMP,
                merged_at TIMESTAMP,
                labels TEXT,
                assignees TEXT,
                milestone TEXT,
                repository TEXT,
                url TEXT,
                user_login TEXT,
                user_avatar_url TEXT,
                draft BOOLEAN DEFAULT 0,
                UNIQUE(id)
            )
        ''')
        
        # Create sync metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_type TEXT,
                repository TEXT,
                last_sync TIMESTAMP,
                status TEXT,
                items_synced INTEGER DEFAULT 0,
                error_message TEXT
            )
        ''')
        
        # Create comprehensive sync history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_session_id TEXT NOT NULL,
                sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                repository TEXT NOT NULL,
                sync_type TEXT NOT NULL, -- 'issues', 'pull_requests', 'full'
                issues_new INTEGER DEFAULT 0,
                issues_updated INTEGER DEFAULT 0,
                issues_total INTEGER DEFAULT 0,
                prs_new INTEGER DEFAULT 0,
                prs_updated INTEGER DEFAULT 0,
                prs_total INTEGER DEFAULT 0,
                duration_seconds INTEGER DEFAULT 0,
                status TEXT DEFAULT 'success', -- 'success', 'error', 'partial'
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sync_history_date 
            ON sync_history(sync_date DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sync_history_session 
            ON sync_history(sync_session_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sync_history_repo 
            ON sync_history(repository)
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database schema initialized")
    
    def get_repository_filters(self, repository: str) -> dict:
        """Get filter configuration for a specific repository"""
        try:
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT filters FROM repositories WHERE repo = ?", (repository,))
            result = cursor.fetchone()
            conn.close()
            
            if result and result['filters']:
                import json
                return json.loads(result['filters'])
            
            # Return default filters if none configured
            return {
                "issues": {"state": "all"},
                "pull_requests": {"state": "all"}
            }
        except Exception as e:
            logger.error(f"Error getting repository filters for {repository}: {e}")
            return {
                "issues": {"state": "all"},
                "pull_requests": {"state": "all"}
            }
    
    def build_github_api_params(self, filters: dict, content_type: str) -> dict:
        """Build GitHub API parameters from filter configuration"""
        params = {}
        
        filter_config = filters.get(content_type, {})
        
        # Add state filter
        if 'state' in filter_config:
            params['state'] = filter_config['state']
        
        # Add labels filter (GitHub API supports labels as comma-separated string)
        if 'labels' in filter_config and filter_config['labels']:
            params['labels'] = ','.join(filter_config['labels'])
        
        # Add assignee filter
        if 'assignee' in filter_config:
            params['assignee'] = filter_config['assignee']
        
        # Add milestone filter
        if 'milestone' in filter_config:
            params['milestone'] = filter_config['milestone']
        
        # Add creator filter
        if 'creator' in filter_config:
            params['creator'] = filter_config['creator']
        
        # Add sort and direction
        if 'sort' in filter_config:
            params['sort'] = filter_config['sort']
        if 'direction' in filter_config:
            params['direction'] = filter_config['direction']
        
        return params
    
    def should_exclude_item(self, item: dict, filters: dict, content_type: str) -> bool:
        """Check if an item should be excluded based on exclude filters"""
        filter_config = filters.get(content_type, {})
        
        # Check exclude_labels
        if 'exclude_labels' in filter_config and filter_config['exclude_labels']:
            item_labels = [label['name'] for label in item.get('labels', [])]
            for exclude_label in filter_config['exclude_labels']:
                if exclude_label in item_labels:
                    return True
        
        # Check exclude_assignees
        if 'exclude_assignees' in filter_config and filter_config['exclude_assignees']:
            assignees = [assignee['login'] for assignee in item.get('assignees', [])]
            if item.get('assignee'):
                assignees.append(item['assignee']['login'])
            for exclude_assignee in filter_config['exclude_assignees']:
                if exclude_assignee in assignees:
                    return True
        
        return False
    
    def record_sync_history(self, sync_session_id: str, repository: str, sync_type: str, 
                          issues_new: int = 0, issues_updated: int = 0, issues_total: int = 0,
                          prs_new: int = 0, prs_updated: int = 0, prs_total: int = 0,
                          duration_seconds: int = 0, status: str = 'success', error_message: str = None):
        """Record detailed sync history for dashboard display"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO sync_history 
                (sync_session_id, repository, sync_type, issues_new, issues_updated, issues_total,
                 prs_new, prs_updated, prs_total, duration_seconds, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (sync_session_id, repository, sync_type, issues_new, issues_updated, issues_total,
                  prs_new, prs_updated, prs_total, duration_seconds, status, error_message))
            
            conn.commit()
            conn.close()
            logger.info(f"Recorded sync history for {repository}: {sync_type}")
        except Exception as e:
            logger.error(f"Error recording sync history: {e}")
    
    def get_sync_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent sync history for dashboard display"""
        try:
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT sync_session_id, sync_date, repository, sync_type,
                       issues_new, issues_updated, issues_total,
                       prs_new, prs_updated, prs_total,
                       duration_seconds, status, error_message
                FROM sync_history 
                ORDER BY sync_date DESC 
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert to list of dictionaries
            history = []
            for row in rows:
                history.append({
                    'sync_session_id': row['sync_session_id'],
                    'sync_date': row['sync_date'],
                    'repository': row['repository'],
                    'sync_type': row['sync_type'],
                    'issues_new': row['issues_new'],
                    'issues_updated': row['issues_updated'],
                    'issues_total': row['issues_total'],
                    'prs_new': row['prs_new'],
                    'prs_updated': row['prs_updated'],
                    'prs_total': row['prs_total'],
                    'duration_seconds': row['duration_seconds'],
                    'status': row['status'],
                    'error_message': row['error_message']
                })
            
            return history
        except Exception as e:
            logger.error(f"Error getting sync history: {e}")
            return []
    
    def _setup_automatic_sync(self):
        """Setup automatic sync job to run every 2 hours"""
        try:
            # Add job to run every 2 hours
            self.scheduler.add_job(
                func=self._automatic_full_sync,
                trigger=IntervalTrigger(hours=2),
                id='auto_sync_job',
                name='Automatic Full Sync',
                replace_existing=True
            )
            
            # Start the scheduler
            self.scheduler.start()
            logger.info("Automatic sync scheduler started - running every 2 hours")
        except Exception as e:
            logger.error(f"Error setting up automatic sync: {e}")
    
    def _automatic_full_sync(self):
        """Perform automatic full sync (called by scheduler)"""
        try:
            session_id = str(uuid4())
            logger.info(f"Starting automatic full sync - Session ID: {session_id}")
            
            repositories = self.get_repositories()
            total_success = 0
            total_errors = 0
            
            for repo in repositories:
                repo_name = repo['repo']
                try:
                    # Sync both issues and PRs
                    issues_result = self.sync_repository_issues(repo_name, session_id)
                    prs_result = self.sync_repository_prs(repo_name, session_id)
                    
                    if issues_result.get('success') and prs_result.get('success'):
                        total_success += 1
                    else:
                        total_errors += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing {repo_name} in automatic sync: {e}")
                    total_errors += 1
            
            logger.info(f"Automatic sync completed - Session ID: {session_id}, Success: {total_success}, Errors: {total_errors}")
            
        except Exception as e:
            logger.error(f"Error in automatic sync: {e}")
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current status of the automatic sync scheduler"""
        try:
            if not hasattr(self, 'scheduler'):
                return {"enabled": False, "running": False, "error": "Scheduler not initialized"}
            
            jobs = self.scheduler.get_jobs()
            auto_sync_job = None
            for job in jobs:
                if job.id == 'auto_sync_job':
                    auto_sync_job = job
                    break
            
            if auto_sync_job:
                next_run = auto_sync_job.next_run_time
                return {
                    "enabled": self.auto_sync_enabled,
                    "running": self.scheduler.running,
                    "next_run": next_run.isoformat() if next_run else None,
                    "job_id": auto_sync_job.id,
                    "interval": "2 hours"
                }
            else:
                return {
                    "enabled": False,
                    "running": self.scheduler.running,
                    "error": "Auto sync job not found"
                }
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            return {"enabled": False, "running": False, "error": str(e)}
    
    def enable_automatic_sync(self):
        """Enable automatic syncing"""
        try:
            self.auto_sync_enabled = True
            if not self.scheduler.running:
                self.scheduler.start()
            logger.info("Automatic sync enabled")
            return {"success": True, "message": "Automatic sync enabled"}
        except Exception as e:
            logger.error(f"Error enabling automatic sync: {e}")
            return {"success": False, "error": str(e)}
    
    def disable_automatic_sync(self):
        """Disable automatic syncing"""
        try:
            self.auto_sync_enabled = False
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            logger.info("Automatic sync disabled")
            return {"success": True, "message": "Automatic sync disabled"}
        except Exception as e:
            logger.error(f"Error disabling automatic sync: {e}")
            return {"success": False, "error": str(e)}
    
    def get_repositories(self) -> List[Dict[str, Any]]:
        """Get list of active repositories with full details including issue/PR counts"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                r.repo, 
                r.display_name, 
                r.main_category, 
                r.classification, 
                r.language_group,
                r.priority, 
                r.is_active, 
                r.created_at, 
                r.updated_at,
                COALESCE(i.issue_count, 0) as issue_count,
                COALESCE(p.pr_count, 0) as pr_count
            FROM repositories r
            LEFT JOIN (
                SELECT repo, COUNT(*) as issue_count 
                FROM issues 
                GROUP BY repo
            ) i ON r.repo = i.repo
            LEFT JOIN (
                SELECT repo, COUNT(*) as pr_count 
                FROM pull_requests 
                GROUP BY repo
            ) p ON r.repo = p.repo
            WHERE r.is_active = 1 
            ORDER BY r.priority, r.repo
        ''')
        
        columns = ['repo', 'display_name', 'main_category', 'classification', 'language_group', 'priority', 'is_active', 'created_at', 'updated_at', 'issue_count', 'pr_count']
        repos = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return repos

    def add_repository(self, repo: str, display_name: str, main_category: str, classification: str, priority: int, is_active: bool = True) -> Dict[str, Any]:
        """Add a new repository to the database"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Check if repository already exists
            cursor.execute("SELECT repo FROM repositories WHERE repo = ?", (repo,))
            if cursor.fetchone():
                conn.close()
                return {"success": False, "error": "Repository already exists"}
            
            language_group = self._determine_language_group(repo, display_name, classification, main_category)

            # Insert new repository
            cursor.execute('''
                INSERT INTO repositories 
                (repo, display_name, main_category, classification, language_group, priority, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ''', (repo, display_name, main_category, classification, language_group, priority, is_active))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Added repository: {repo}")
            return {"success": True, "message": f"Repository {repo} added successfully"}
            
        except Exception as e:
            logger.error(f"Error adding repository {repo}: {e}")
            return {"success": False, "error": str(e)}

    def remove_repository(self, repo: str) -> Dict[str, Any]:
        """Remove a repository from the database"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Check if repository exists
            cursor.execute("SELECT repo FROM repositories WHERE repo = ?", (repo,))
            if not cursor.fetchone():
                conn.close()
                return {"success": False, "error": "Repository not found"}
            
            # Delete repository
            cursor.execute("DELETE FROM repositories WHERE repo = ?", (repo,))
            
            # Also delete related sync data
            cursor.execute("DELETE FROM sync_metadata WHERE repository = ?", (repo,))
            cursor.execute("DELETE FROM issues WHERE repository = ?", (repo,))
            cursor.execute("DELETE FROM pull_requests WHERE repository = ?", (repo,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Removed repository: {repo}")
            return {"success": True, "message": f"Repository {repo} removed successfully"}
            
        except Exception as e:
            logger.error(f"Error removing repository {repo}: {e}")
            return {"success": False, "error": str(e)}

    def update_repository(self, repo: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update repository information"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Check if repository exists
            cursor.execute("SELECT repo FROM repositories WHERE repo = ?", (repo,))
            if not cursor.fetchone():
                conn.close()
                return {"success": False, "error": "Repository not found"}
            
            # Build update query
            allowed_fields = ['display_name', 'main_category', 'classification', 'priority', 'is_active']
            updates = []
            values = []
            
            for field in allowed_fields:
                if field in data:
                    updates.append(f"{field} = ?")
                    values.append(data[field])
            
            if not updates:
                conn.close()
                return {"success": False, "error": "No valid fields to update"}
            
            # Add updated_at timestamp
            updates.append("updated_at = datetime('now')")
            values.append(repo)
            
            query = f"UPDATE repositories SET {', '.join(updates)} WHERE repo = ?"
            cursor.execute(query, values)

            # Recompute language group using the latest repository attributes
            cursor.execute("SELECT display_name, main_category, classification, language_group FROM repositories WHERE repo = ?", (repo,))
            row = cursor.fetchone()
            if row:
                inferred_language = self._determine_language_group(repo, row[0], row[2], row[1])
                current_language = row[3] or 'Other'
                if inferred_language != current_language:
                    cursor.execute(
                        "UPDATE repositories SET language_group = ?, updated_at = datetime('now') WHERE repo = ?",
                        (inferred_language, repo)
                    )
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated repository: {repo}")
            return {"success": True, "message": f"Repository {repo} updated successfully"}
            
        except Exception as e:
            logger.error(f"Error updating repository {repo}: {e}")
            return {"success": False, "error": str(e)}
    
    def sync_repository_issues(self, repo_name: str, sync_session_id: str = None) -> Dict[str, Any]:
        """Sync issues for a specific repository"""
        if not requests:
            logger.error("requests module not available - cannot sync issues")
            return {"success": False, "error": "requests module not available"}

        if sync_session_id is None:
            sync_session_id = str(uuid4())

        start_time = time.time()

        try:
            logger.info(f"Syncing issues for repository: {repo_name}")

            repo_filters = self.get_repository_filters(repo_name)
            logger.info(f"Using filters for {repo_name}: {repo_filters}")

            last_sync_iso = self._get_last_sync_timestamp(repo_name, 'issues')
            if last_sync_iso:
                logger.info(f"Last successful issues sync for {repo_name}: {last_sync_iso}")
            headers = self._build_conditional_headers(last_sync_iso)

            url = f"{self.base_url}/repos/{repo_name}/issues"

            params = self.build_github_api_params(repo_filters, 'issues')
            params.update({
                'per_page': 100,
                'sort': params.get('sort', 'updated'),
                'direction': params.get('direction', 'desc')
            })
            if last_sync_iso:
                params['since'] = last_sync_iso

            logger.info(f"GitHub API request params: {params}")

            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 304:
                logger.info(f"No new issues for {repo_name} since {last_sync_iso}")
                duration_seconds = int(time.time() - start_time)
                self._update_sync_metadata(
                    repository=repo_name,
                    sync_type='issues',
                    status='not_modified',
                    items_synced=0,
                    last_synced_at=last_sync_iso
                )
                self.record_sync_history(
                    sync_session_id=sync_session_id,
                    repository=repo_name,
                    sync_type='issues',
                    issues_new=0,
                    issues_updated=0,
                    issues_total=0,
                    duration_seconds=duration_seconds,
                    status='success'
                )
                return {
                    "success": True,
                    "repository": repo_name,
                    "issues_synced": 0,
                    "issues_new": 0,
                    "issues_updated": 0,
                    "total_items": 0,
                    "count": 0
                }

            response.raise_for_status()

            issues_data = response.json()

            latest_seen_dt = self._parse_iso_datetime(last_sync_iso)
            latest_seen_iso = last_sync_iso
            for raw_item in issues_data:
                updated_iso = raw_item.get('updated_at')
                updated_dt = self._parse_iso_datetime(updated_iso)
                if updated_dt and (latest_seen_dt is None or updated_dt > latest_seen_dt):
                    latest_seen_dt = updated_dt
                    latest_seen_iso = updated_iso

            issues = [item for item in issues_data if 'pull_request' not in item]

            filtered_issues = []
            for issue in issues:
                if not self.should_exclude_item(issue, repo_filters, 'issues'):
                    filtered_issues.append(issue)
                else:
                    logger.debug(f"Excluding issue #{issue['number']} due to filter rules")

            logger.info(f"Fetched {len(issues)} issues, {len(filtered_issues)} after filtering")

            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()

            issues_new = 0
            issues_updated = 0
            for issue in filtered_issues:
                try:
                    cursor.execute('''
                        SELECT updated_at FROM issues 
                        WHERE repo = ? AND number = ?
                    ''', (repo_name, issue['number']))

                    existing = cursor.fetchone()
                    is_new = existing is None
                    is_updated = False

                    if not is_new:
                        existing_updated_at = existing[0]
                        current_updated_at = issue['updated_at']
                        is_updated = existing_updated_at != current_updated_at

                    cursor.execute('''
                        INSERT OR REPLACE INTO issues (
                            repo, number, title, html_url, assignee_login, created_at, updated_at, 
                            body, state, labels, assignees, user_login, user_avatar_url, comments
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        repo_name,
                        issue['number'],
                        issue['title'],
                        issue['html_url'],
                        issue.get('assignee', {}).get('login') if issue.get('assignee') else None,
                        issue['created_at'],
                        issue['updated_at'],
                        issue.get('body', ''),
                        issue['state'],
                        json.dumps([label['name'] for label in issue.get('labels', [])]),
                        json.dumps([assignee['login'] for assignee in issue.get('assignees', [])]),
                        issue['user']['login'],
                        issue['user']['avatar_url'],
                        str(issue.get('comments', 0))
                    ))

                    if is_new:
                        issues_new += 1
                    elif is_updated:
                        issues_updated += 1

                except Exception as exc:
                    logger.error(f"Error processing issue {issue['number']}: {exc}")

            conn.commit()
            conn.close()

            if latest_seen_iso is None:
                latest_seen_iso = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')

            self._update_sync_metadata(
                repository=repo_name,
                sync_type='issues',
                status='success',
                items_synced=issues_new + issues_updated,
                last_synced_at=latest_seen_iso
            )

            duration_seconds = int(time.time() - start_time)
            self.record_sync_history(
                sync_session_id=sync_session_id,
                repository=repo_name,
                sync_type='issues',
                issues_new=issues_new,
                issues_updated=issues_updated,
                issues_total=len(issues),
                duration_seconds=duration_seconds,
                status='success'
            )

            logger.info(
                f"Successfully synced {issues_new + issues_updated} issues for {repo_name} "
                f"(new: {issues_new}, updated: {issues_updated})"
            )
            return {
                "success": True,
                "repository": repo_name,
                "issues_synced": issues_new + issues_updated,
                "issues_new": issues_new,
                "issues_updated": issues_updated,
                "total_items": len(issues_data),
                "count": issues_new + issues_updated
            }

        except Exception as exc:
            logger.error(f"Error syncing issues for {repo_name}: {exc}")

            duration_seconds = int(time.time() - start_time)
            self.record_sync_history(
                sync_session_id=sync_session_id,
                repository=repo_name,
                sync_type='issues',
                duration_seconds=duration_seconds,
                status='error',
                error_message=str(exc)
            )

            self._update_sync_metadata(
                repository=repo_name,
                sync_type='issues',
                status='error',
                items_synced=0,
                error_message=str(exc)
            )

            return {"success": False, "error": str(exc), "repository": repo_name}
    
    def sync_repository_prs(self, repo_name: str, sync_session_id: str = None) -> Dict[str, Any]:
        """Sync pull requests for a specific repository"""
        if not requests:
            logger.error("requests module not available - cannot sync PRs")
            return {"success": False, "error": "requests module not available"}
        
        if sync_session_id is None:
            sync_session_id = str(uuid4())
        
        start_time = time.time()
        
        try:
            logger.info(f"Syncing PRs for repository: {repo_name}")
            
            # Get repository-specific filters
            repo_filters = self.get_repository_filters(repo_name)

            last_sync_iso = self._get_last_sync_timestamp(repo_name, 'pull_requests')
            if last_sync_iso:
                logger.info(f"Last successful PR sync for {repo_name}: {last_sync_iso}")
            headers = self._build_conditional_headers(last_sync_iso)
            
            url = f"{self.base_url}/repos/{repo_name}/pulls"
            
            # Build API parameters from filters
            params = self.build_github_api_params(repo_filters, 'pull_requests')
            params.update({
                'per_page': 100,
                'sort': params.get('sort', 'updated'),
                'direction': params.get('direction', 'desc')
            })
            
            logger.info(f"GitHub API request params for PRs: {params}")
            
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 304:
                logger.info(f"No new pull requests for {repo_name} since {last_sync_iso}")
                duration_seconds = int(time.time() - start_time)
                self._update_sync_metadata(
                    repository=repo_name,
                    sync_type='pull_requests',
                    status='not_modified',
                    items_synced=0,
                    last_synced_at=last_sync_iso
                )
                self.record_sync_history(
                    sync_session_id=sync_session_id,
                    repository=repo_name,
                    sync_type='pull_requests',
                    prs_new=0,
                    prs_updated=0,
                    prs_total=0,
                    duration_seconds=duration_seconds,
                    status='success'
                )
                return {
                    "success": True,
                    "repository": repo_name,
                    "prs_synced": 0,
                    "prs_new": 0,
                    "prs_updated": 0,
                    "total_items": 0,
                    "count": 0
                }
            response.raise_for_status()
            
            prs_data = response.json()
            
            latest_seen_dt = self._parse_iso_datetime(last_sync_iso)
            latest_seen_iso = last_sync_iso
            for pr_item in prs_data:
                updated_iso = pr_item.get('updated_at')
                updated_dt = self._parse_iso_datetime(updated_iso)
                if updated_dt and (latest_seen_dt is None or updated_dt > latest_seen_dt):
                    latest_seen_dt = updated_dt
                    latest_seen_iso = updated_iso
            
            # Apply exclude filters
            filtered_prs = []
            for pr in prs_data:
                if not self.should_exclude_item(pr, repo_filters, 'pull_requests'):
                    filtered_prs.append(pr)
                else:
                    logger.debug(f"Excluding PR #{pr['number']} due to filter rules")
            
            logger.info(f"Fetched {len(prs_data)} PRs, {len(filtered_prs)} after filtering")
            
            # Store PRs in database using existing schema
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            prs_new = 0
            prs_updated = 0
            for pr in filtered_prs:
                try:
                    # Check if this PR already exists
                    cursor.execute('''
                        SELECT updated_at FROM pull_requests 
                        WHERE repo = ? AND number = ?
                    ''', (repo_name, pr['number']))
                    
                    existing = cursor.fetchone()
                    is_new = existing is None
                    is_updated = False
                    
                    if not is_new:
                        # Check if the PR was actually updated
                        existing_updated_at = existing[0]
                        current_updated_at = pr['updated_at']
                        is_updated = existing_updated_at != current_updated_at
                    
                    # Insert or replace the PR
                    cursor.execute('''
                        INSERT OR REPLACE INTO pull_requests (
                            repo, number, title, html_url, user_login, user_avatar_url, 
                            created_at, updated_at, body, state, draft, merged, 
                            base_ref, head_ref, labels, assignees, comments
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        repo_name,
                        pr['number'],
                        pr['title'],
                        pr['html_url'],
                        pr['user']['login'],
                        pr['user']['avatar_url'],
                        pr['created_at'],
                        pr['updated_at'],
                        pr.get('body', ''),
                        pr['state'],
                        pr.get('draft', False),
                        pr.get('merged', False),
                        pr.get('base', {}).get('ref'),
                        pr.get('head', {}).get('ref'),
                        json.dumps([label['name'] for label in pr.get('labels', [])]),
                        json.dumps([assignee['login'] for assignee in pr.get('assignees', [])]),
                        str(pr.get('comments', 0))
                    ))
                    
                    # Track the operation
                    if is_new:
                        prs_new += 1
                    elif is_updated:
                        prs_updated += 1
                        
                except Exception as e:
                    logger.error(f"Error processing PR {pr['number']}: {e}")
            
            conn.commit()
            conn.close()
            
            if latest_seen_iso is None:
                latest_seen_iso = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')

            self._update_sync_metadata(
                repository=repo_name,
                sync_type='pull_requests',
                status='success',
                items_synced=prs_new + prs_updated,
                last_synced_at=latest_seen_iso
            )

            # Record sync history
            duration_seconds = int(time.time() - start_time)
            self.record_sync_history(
                sync_session_id=sync_session_id,
                repository=repo_name,
                sync_type='pull_requests',
                prs_new=prs_new,
                prs_updated=prs_updated,
                prs_total=len(prs_data),
                duration_seconds=duration_seconds,
                status='success'
            )
            
            logger.info(f"Successfully synced {prs_new + prs_updated} PRs for {repo_name} (new: {prs_new}, updated: {prs_updated})")
            return {
                "success": True,
                "repository": repo_name,
                "prs_synced": prs_new + prs_updated,
                "prs_new": prs_new,
                "prs_updated": prs_updated,
                "total_items": len(prs_data),
                "count": prs_new + prs_updated
            }
            
        except Exception as e:
            logger.error(f"Error syncing PRs for {repo_name}: {e}")
            
            # Record sync history for error
            duration_seconds = int(time.time() - start_time)
            self.record_sync_history(
                sync_session_id=sync_session_id,
                repository=repo_name,
                sync_type='pull_requests',
                duration_seconds=duration_seconds,
                status='error',
                error_message=str(e)
            )
            
            self._update_sync_metadata(
                repository=repo_name,
                sync_type='pull_requests',
                status='error',
                items_synced=0,
                error_message=str(e)
            )

            return {"success": False, "error": str(e), "repository": repo_name}
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get sync status for all repositories"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        # Get sync status from sync_history table instead
        cursor.execute('''
            SELECT repository, sync_type, 
                   MAX(sync_date) as last_sync,
                   SUM(issues_new + issues_updated) as issues_count,
                   SUM(prs_new + prs_updated) as prs_count,
                   status, error_message
            FROM sync_history 
            GROUP BY repository, sync_type
            ORDER BY last_sync DESC
            LIMIT 20
        ''')
        
        status_data = []
        for row in cursor.fetchall():
            key, value, updated_at = row
            # Parse the key to get repo and type
            if '_issues_' in key:
                repo = key.replace('_issues_last_sync', '').replace('_issues_count', '').replace('_issues_last_error', '')
                sync_type = 'issues'
                if '_last_sync' in key:
                    status_type = 'last_sync'
                elif '_count' in key:
                    status_type = 'count'
                else:
                    status_type = 'error'
            elif '_prs_' in key:
                repo = key.replace('_prs_last_sync', '').replace('_prs_count', '').replace('_prs_last_error', '')
                sync_type = 'prs'
                if '_last_sync' in key:
                    status_type = 'last_sync'
                elif '_count' in key:
                    status_type = 'count'
                else:
                    status_type = 'error'
            else:
                continue
            
            status_data.append({
                'sync_type': sync_type,
                'repository': repo,
                'status_type': status_type,
                'value': value,
                'updated_at': updated_at
            })
        
        conn.close()
        return {"sync_status": status_data}
    
    def get_issues(self, repository: Optional[str] = None, state: Optional[str] = None, limit: int = 10000) -> List[Dict[str, Any]]:
        """Get issues from database with optional filtering"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM issues"
        params = []
        conditions = []
        
        if repository:
            conditions.append("repository = ?")
            params.append(repository)
        
        if state:
            conditions.append("state = ?")
            params.append(state)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        columns = [description[0] for description in cursor.description]
        
        issues = []
        for row in cursor.fetchall():
            issue = dict(zip(columns, row))
            issues.append(issue)
        
        conn.close()
        return issues
    
    def get_pull_requests(self, repository: Optional[str] = None, state: Optional[str] = None, limit: int = 10000) -> List[Dict[str, Any]]:
        """Get pull requests from database with optional filtering"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM pull_requests"
        params = []
        conditions = []
        
        if repository:
            conditions.append("repository = ?")
            params.append(repository)
        
        if state:
            conditions.append("state = ?")
            params.append(state)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        columns = [description[0] for description in cursor.description]
        
        prs = []
        for row in cursor.fetchall():
            pr = dict(zip(columns, row))
            prs.append(pr)
        
        conn.close()
        return prs
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from the database"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        # Get repository count
        cursor.execute("SELECT COUNT(*) FROM repositories WHERE is_active = 1")
        repo_count = cursor.fetchone()[0]
        
        # Get total issues count
        cursor.execute("SELECT COUNT(*) FROM issues")
        issues_count = cursor.fetchone()[0]
        
        # Get issues by state
        cursor.execute("SELECT state, COUNT(*) FROM issues GROUP BY state")
        issues_by_state = dict(cursor.fetchall())
        
        # Get total PRs count
        cursor.execute("SELECT COUNT(*) FROM pull_requests")
        prs_count = cursor.fetchone()[0]
        
        # Get PRs by state
        cursor.execute("SELECT state, COUNT(*) FROM pull_requests GROUP BY state")
        prs_by_state = dict(cursor.fetchall())
        
        # Get recent activity
        cursor.execute("SELECT COUNT(*) FROM issues WHERE updated_at > datetime('now', '-7 days')")
        recent_issues = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM pull_requests WHERE updated_at > datetime('now', '-7 days')")
        recent_prs = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "repositories": repo_count,
            "total_issues": issues_count,
            "issues_by_state": issues_by_state,
            "total_pull_requests": prs_count,
            "pull_requests_by_state": prs_by_state,
            "recent_activity": {
                "issues_last_7_days": recent_issues,
                "prs_last_7_days": recent_prs
            }
        }

    def get_data_freshness(self) -> Dict[str, Any]:
        """Get data freshness information"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        # Get latest updates
        cursor.execute("SELECT MAX(updated_at) FROM issues")
        latest_issue_update = cursor.fetchone()[0]
        
        cursor.execute("SELECT MAX(updated_at) FROM pull_requests")
        latest_pr_update = cursor.fetchone()[0]
        
        # Get freshness by repository
        cursor.execute("""
            SELECT repo, 
                   COUNT(*) as total_issues,
                   MAX(updated_at) as latest_update,
                   COUNT(CASE WHEN updated_at > datetime('now', '-1 day') THEN 1 END) as updated_last_24h,
                   COUNT(CASE WHEN updated_at > datetime('now', '-7 days') THEN 1 END) as updated_last_week
            FROM issues 
            GROUP BY repo 
            ORDER BY latest_update DESC
        """)
        
        repo_freshness = []
        for row in cursor.fetchall():
            repo_freshness.append({
                'repo': row[0],
                'total_issues': row[1],
                'latest_update': row[2],
                'updated_last_24h': row[3],
                'updated_last_week': row[4]
            })
        
        # Get sync history from sync_history table instead
        sync_history = []
        try:
            # Get latest sync data from sync_history table
            cursor.execute("""
                SELECT repository, sync_type, sync_date, status, error_message,
                       issues_new, issues_updated, prs_new, prs_updated
                FROM sync_history 
                ORDER BY sync_date DESC
                LIMIT 50
            """)
            
            sync_history = []
            for row in cursor.fetchall():
                repository, sync_type, sync_date, status, error_message, issues_new, issues_updated, prs_new, prs_updated = row
                sync_history.append({
                    'repo': repository,
                    'sync_type': sync_type,
                    'sync_date': sync_date,
                    'status': status,
                    'error_message': error_message,
                    'issues_count': (issues_new or 0) + (issues_updated or 0),
                    'prs_count': (prs_new or 0) + (prs_updated or 0),
                    'last_sync': sync_date,
                    'updated_at': sync_date
                })
            
            # Sort by most recent sync
            sync_history.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
            sync_history = sync_history[:10]  # Limit to 10 most recent
            
        except Exception as e:
            # Table might not exist or have issues
            logger.error(f"Error getting sync history: {e}")
            sync_history = []
        
        conn.close()
        
        return {
            "latest_issue_update": latest_issue_update,
            "latest_pr_update": latest_pr_update,
            "repo_freshness": repo_freshness,
            "sync_history": sync_history
        }

# Initialize sync service
sync_service = GitHubSyncService(DATABASE_PATH)

# API Routes
@app.route('/', methods=['GET'])
def index():
    """Redirect to management UI"""
    return app.send_static_file('index.html')

@app.route('/management', methods=['GET'])
def management_ui():
    """Serve the management UI"""
    return app.send_static_file('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "github-sync-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requests_available": requests is not None
    })

@app.route('/api/repositories', methods=['GET'])
def get_repositories():
    """Get list of repositories"""
    try:
        repos = sync_service.get_repositories()
        return jsonify({"repositories": repos})
    except Exception as e:
        logger.error(f"Error getting repositories: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/repositories', methods=['POST'])
def add_repository():
    """Add a new repository"""
    try:
        data = request.get_json()
        required_fields = ['repo', 'display_name', 'main_category', 'classification', 'priority']
        
        # Validate required fields
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        result = sync_service.add_repository(
            repo=data['repo'],
            display_name=data['display_name'],
            main_category=data['main_category'],
            classification=data['classification'],
            priority=data['priority'],
            is_active=data.get('is_active', True)
        )
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error adding repository: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/repositories/<path:repo_name>', methods=['DELETE'])
def remove_repository(repo_name):
    """Remove a repository"""
    try:
        result = sync_service.remove_repository(repo_name)
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error removing repository: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/repositories/<path:repo_name>', methods=['PUT'])
def update_repository(repo_name):
    """Update a repository"""
    try:
        data = request.get_json()
        result = sync_service.update_repository(repo_name, data)
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error updating repository: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/issues', methods=['GET'])
def get_issues():
    """Get issues with optional filtering"""
    try:
        repository = request.args.get('repository')
        state = request.args.get('state')  
        limit = int(request.args.get('limit', 10000))
        
        issues = sync_service.get_issues(repository=repository, state=state, limit=limit)
        return jsonify({"success": True, "issues": issues, "count": len(issues)})
    except Exception as e:
        logger.error(f"Error getting issues: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/pull_requests', methods=['GET'])
def get_pull_requests():
    """Get pull requests with optional filtering"""
    try:
        repository = request.args.get('repository')
        state = request.args.get('state')
        limit = int(request.args.get('limit', 10000))
        
        prs = sync_service.get_pull_requests(repository=repository, state=state, limit=limit)
        return jsonify({"success": True, "pull_requests": prs, "count": len(prs)})
    except Exception as e:
        logger.error(f"Error getting pull requests: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics"""
    try:
        stats = sync_service.get_stats()
        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Get dashboard statistics"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get total counts
        cursor.execute("SELECT COUNT(*) as count FROM issues")
        total_issues = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM pull_requests")
        total_prs = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(DISTINCT LOWER(repo)) as count FROM repositories WHERE is_active = 1")
        total_repositories = cursor.fetchone()['count']
        
        # Get last sync time from sync_history table
        cursor.execute("SELECT MAX(sync_date) as last_sync FROM sync_history")
        last_sync_row = cursor.fetchone()
        last_sync_raw = last_sync_row['last_sync'] if last_sync_row and last_sync_row['last_sync'] else None
        
        # Convert local timestamp to UTC for consistent frontend handling
        last_sync = None
        if last_sync_raw:
            try:
                from datetime import datetime, timezone, timedelta
                # Parse the SQLite timestamp - SQLite CURRENT_TIMESTAMP is UTC
                # But our database might be storing local time, so let's handle both cases
                local_dt = datetime.fromisoformat(last_sync_raw.replace('Z', ''))
                
                # Since SQLite CURRENT_TIMESTAMP uses local time, treat it as local and convert to UTC
                # Get the current local timezone offset
                import time
                is_dst = time.daylight and time.localtime().tm_isdst > 0
                offset = - (time.altzone if is_dst else time.timezone)
                
                # Create timezone-aware datetime in local timezone
                local_tz = timezone(timedelta(seconds=offset))
                aware_local_dt = local_dt.replace(tzinfo=local_tz)
                
                # Convert to UTC
                utc_dt = aware_local_dt.astimezone(timezone.utc)
                last_sync = utc_dt.isoformat()
                
                logger.info(f"Converted timestamp: {last_sync_raw} (local) -> {last_sync} (UTC)")
            except Exception as e:
                logger.warning(f"Error converting timestamp {last_sync_raw} to UTC: {e}")
                last_sync = last_sync_raw
        
        conn.close()
        
        return jsonify({
            "total_issues": total_issues,
            "total_prs": total_prs, 
            "total_repositories": total_repositories,
            "last_sync": last_sync
        })
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync/repositories/<path:repo_name>/issues', methods=['POST'])
def sync_repository_issues(repo_name):
    """Sync issues for a specific repository"""
    try:
        result = sync_service.sync_repository_issues(repo_name)
        status_code = 200 if result.get('success') else 500
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Error in sync issues endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync/repositories/<path:repo_name>/prs', methods=['POST'])
def sync_repository_prs(repo_name):
    """Sync pull requests for a specific repository"""
    try:
        result = sync_service.sync_repository_prs(repo_name)
        status_code = 200 if result.get('success') else 500
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Error in sync PRs endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync/repositories/<path:repo_name>', methods=['POST'])
def sync_repository_all(repo_name):
    """Sync both issues and PRs for a specific repository"""
    try:
        # Generate a session ID for this repository sync
        sync_session_id = str(uuid4())
        
        issues_result = sync_service.sync_repository_issues(repo_name, sync_session_id)
        prs_result = sync_service.sync_repository_prs(repo_name, sync_session_id)
        
        return jsonify({
            "repository": repo_name,
            "issues": issues_result,
            "prs": prs_result,
            "success": issues_result.get('success', False) and prs_result.get('success', False)
        })
    except Exception as e:
        logger.error(f"Error in sync all endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync/full', methods=['POST'])
def trigger_full_sync():
    """Trigger a full sync of all repositories"""
    try:
        # Generate a unique session ID for this full sync operation
        sync_session_id = str(uuid4())
        logger.info(f"Starting full sync with session ID: {sync_session_id}")
        
        # Get all active repositories
        repositories = sync_service.get_repositories()
        results = []
        
        for repo in repositories:
            repo_name = repo['repo']
            try:
                # Sync both issues and PRs for each repository with the same session ID
                issue_result = sync_service.sync_repository_issues(repo_name, sync_session_id)
                pr_result = sync_service.sync_repository_prs(repo_name, sync_session_id)
                
                results.append({
                    "repository": repo_name,
                    "issues_synced": issue_result.get('count', 0),
                    "prs_synced": pr_result.get('count', 0),
                    "success": True
                })
            except Exception as e:
                results.append({
                    "repository": repo_name,
                    "error": str(e),
                    "success": False
                })
        
        logger.info(f"Full sync completed. Session ID: {sync_session_id}")
        return jsonify({
            "success": True,
            "message": "Full sync completed",
            "results": results,
            "total_repositories": len(repositories),
            "sync_session_id": sync_session_id
        })
    except Exception as e:
        logger.error(f"Error in full sync: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync/status', methods=['GET'])
def get_sync_status():
    """Get sync status"""
    try:
        status = sync_service.get_sync_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/data/freshness', methods=['GET'])
def get_data_freshness():
    """Get data freshness information"""
    try:
        freshness = sync_service.get_data_freshness()
        return jsonify({"success": True, "freshness": freshness})
    except Exception as e:
        logger.error(f"Error getting data freshness: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/sync/history', methods=['GET'])
def get_sync_history():
    """Get detailed sync history for dashboard"""
    try:
        limit = request.args.get('limit', 20, type=int)
        history = sync_service.get_sync_history(limit=limit)
        return jsonify({
            "success": True, 
            "sync_history": history,
            "count": len(history)
        })
    except Exception as e:
        logger.error(f"Error getting sync history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/repositories', methods=['GET'])
def get_repositories_api():
    """Get all repositories with their filter configurations"""
    try:
        import json
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT repo, display_name, main_category, classification, 
                   priority, is_active, filters, created_at, updated_at
            FROM repositories 
            ORDER BY priority, display_name
        ''')
        
        repositories = []
        for row in cursor.fetchall():
            repo_data = dict(row)
            if repo_data['filters']:
                try:
                    repo_data['filters'] = json.loads(repo_data['filters'])
                except:
                    repo_data['filters'] = {}
            else:
                repo_data['filters'] = {}
            repositories.append(repo_data)
        
        conn.close()
        return jsonify({"success": True, "repositories": repositories})
    except Exception as e:
        logger.error(f"Error getting repositories: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/repositories/<path:repo_name>/filters', methods=['GET'])
def get_repository_filters_api(repo_name):
    """Get filter configuration for a repository"""
    try:
        filters = sync_service.get_repository_filters(repo_name)
        return jsonify({"success": True, "filters": filters})
    except Exception as e:
        logger.error(f"Error getting repository filters: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/repositories/<path:repo_name>/filters', methods=['PUT'])
def update_repository_filters_api(repo_name):
    """Update filter configuration for a repository"""
    try:
        import json
        data = request.get_json()
        filters = data.get('filters', {})
        
        # Validate JSON structure
        json.dumps(filters)  # This will raise an exception if not serializable
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE repositories 
            SET filters = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE repo = ?
        ''', (json.dumps(filters), repo_name))
        
        if cursor.rowcount == 0:
            return jsonify({"success": False, "error": "Repository not found"}), 404
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated filters for repository {repo_name}")
        return jsonify({"success": True, "message": "Filters updated successfully"})
    except Exception as e:
        logger.error(f"Error updating repository filters: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/sync/history/sample', methods=['POST'])
def create_sample_sync_history():
    """Create sample sync history data for testing"""
    try:
        import uuid
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Create a sample sync session
        session_id = str(uuid.uuid4())
        sample_syncs = [
            ('Azure/azure-sdk-for-python', 'full', 12, 8, 145, 5, 3, 67),
            ('Azure/azure-sdk-for-js', 'full', 8, 5, 98, 7, 2, 45),
            ('microsoft/ApplicationInsights-js', 'full', 3, 2, 34, 2, 1, 12)
        ]
        
        for repo, sync_type, issues_new, issues_updated, issues_total, prs_new, prs_updated, prs_total in sample_syncs:
            cursor.execute('''
                INSERT INTO sync_history 
                (sync_session_id, repository, sync_type, issues_new, issues_updated, issues_total,
                 prs_new, prs_updated, prs_total, duration_seconds, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session_id, repo, sync_type, issues_new, issues_updated, issues_total,
                  prs_new, prs_updated, prs_total, 45, 'success'))
        
        conn.commit()
        conn.close()
        
        logger.info("Sample sync history created successfully")
        return jsonify({
            "success": True, 
            "message": "Sample sync history created",
            "session_id": session_id
        })
    except Exception as e:
        logger.error(f"Error creating sample sync history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# Automatic Sync Scheduler API endpoints
@app.route('/api/scheduler/status', methods=['GET'])
def get_scheduler_status():
    """Get automatic sync scheduler status"""
    try:
        status = sync_service.get_scheduler_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/scheduler/enable', methods=['POST'])
def enable_scheduler():
    """Enable automatic sync scheduler"""
    try:
        result = sync_service.enable_automatic_sync()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error enabling scheduler: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/scheduler/disable', methods=['POST'])
def disable_scheduler():
    """Disable automatic sync scheduler"""
    try:
        result = sync_service.disable_automatic_sync()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error disabling scheduler: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# Properly shut down scheduler when app closes
@atexit.register
def shutdown_scheduler():
    """Shutdown scheduler on app exit"""
    if hasattr(sync_service, 'scheduler') and sync_service.scheduler.running:
        sync_service.scheduler.shutdown()
        logger.info("Scheduler shut down")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting GitHub Sync Service on port {port}")
    logger.info(f"Database path: {DATABASE_PATH}")
    logger.info(f"Azure environment: {IS_AZURE}")
    logger.info(f"Requests module available: {requests is not None}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)