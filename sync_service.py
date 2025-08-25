#!/usr/bin/env python3
"""
GitHub Issues Sync Service
Standalone service that manages GitHub data synchronization and exposes REST APIs
"""

import os
import threading
import time
import requests
import sqlite3
import json
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote, quote
from collections import deque
from flask import Flask, jsonify, request
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
from werkzeug.serving import run_simple
import hashlib

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GitHubSyncService:
    """GitHub data synchronization service with REST API endpoints"""
    
    def __init__(self, db_path='github_issues.db'):
        self.db_path = db_path
        self.sync_in_progress = False
        self.sync_lock = threading.Lock()
        
        # No GitHub token - running unauthenticated
        self.github_token = None
        
        # Rate limiting and queue management (unauthenticated: 60 requests/hour)
        self.rate_limit_reset_time = None
        self.rate_limit_remaining = 60  # Start with assumption of 60 requests available
        self.last_rate_limit_check = None
        
        # Retry queue for failed requests (retry after 75 minutes)
        self.retry_queue = deque()
        self.retry_delay_seconds = 75 * 60  # 75 minutes
        
        # Repository configuration - now loaded from database
        self.repositories = []
        self._load_repositories_from_db()
        
        # Sync statistics
        self.sync_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'rate_limited_requests': 0,
            'queued_requests': 0,
            'incremental_updates': 0,
            'full_syncs': 0,
            'last_sync': None,
            'sync_duration': 0
        }
        
        # Initialize database schema
        self._ensure_database_schema()
        
        # Start queue monitoring
        self._start_queue_monitor()
        
    def _load_repositories_from_db(self):
        """Load active repositories from database, ordered by classification priority then priority"""
        try:
            # Ensure database schema exists first
            self._ensure_database_schema()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Load repositories ordered by classification priority (azure=1, opentelemetry=2, microsoft=3) then by priority
            cursor.execute('''
                SELECT repo FROM repositories 
                WHERE is_active = TRUE 
                ORDER BY 
                    CASE classification 
                        WHEN 'azure' THEN 1 
                        WHEN 'opentelemetry' THEN 2 
                        WHEN 'microsoft' THEN 3 
                        ELSE 4 
                    END,
                    priority ASC
            ''')
            
            self.repositories = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not self.repositories:
                logger.warning("No active repositories found in database")
            else:
                logger.info(f"Loaded {len(self.repositories)} active repositories from database")
                
        except Exception as e:
            logger.error(f"Error loading repositories from database: {e}")
            # Fallback to empty list - schema initialization will add defaults
            self.repositories = []
        
    def get_repositories_with_metadata(self):
        """Get repositories with all metadata for API responses"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT repo, display_name, main_category, classification, priority, is_active 
                FROM repositories 
                WHERE is_active = TRUE 
                ORDER BY 
                    CASE classification 
                        WHEN 'azure' THEN 1 
                        WHEN 'opentelemetry' THEN 2 
                        WHEN 'microsoft' THEN 3 
                        ELSE 4 
                    END,
                    priority ASC
            ''')
            
            repositories = []
            for row in cursor.fetchall():
                repositories.append({
                    'repo': row['repo'],
                    'display_name': row['display_name'],
                    'main_category': row['main_category'],
                    'classification': row['classification'],
                    'priority': row['priority'],
                    'is_active': bool(row['is_active'])
                })
            
            conn.close()
            return repositories
            
        except Exception as e:
            logger.error(f"Error getting repositories with metadata: {e}")
            return []
        
    def get_headers(self):
        """Get headers for GitHub API requests (unauthenticated)"""
        headers = {
            'User-Agent': 'GitHub-Issues-Dashboard-Sync-Service/1.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        # No authentication - running unauthenticated
        return headers
    
    def _check_rate_limit(self, response):
        """Check and update rate limit information from GitHub response"""
        if response:
            self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            reset_timestamp = int(response.headers.get('X-RateLimit-Reset', 0))
            if reset_timestamp:
                self.rate_limit_reset_time = datetime.fromtimestamp(reset_timestamp, tz=timezone.utc)
            self.last_rate_limit_check = datetime.now(timezone.utc)
            
            # Log rate limit status
            if self.rate_limit_remaining < 100:
                reset_time_str = self.rate_limit_reset_time.strftime('%H:%M:%S UTC') if self.rate_limit_reset_time else 'Unknown'
                logger.warning(f"Rate limit low: {self.rate_limit_remaining} requests remaining. Resets at {reset_time_str}")
    
    def _is_rate_limited(self):
        """Check if we're currently rate limited"""
        if not self.rate_limit_remaining or not self.rate_limit_reset_time:
            return False
        
        if self.rate_limit_remaining <= 0:
            if datetime.now(timezone.utc) < self.rate_limit_reset_time:
                return True
        
        return False
    
    def _make_github_request(self, url, params=None):
        """Make a GitHub API request with rate limiting and retry logic"""
        self.sync_stats['total_requests'] += 1
        
        # Check if we're rate limited
        if self._is_rate_limited():
            reset_time = self.rate_limit_reset_time.strftime('%H:%M:%S UTC') if self.rate_limit_reset_time else 'Unknown'
            logger.info(f"Rate limited. Queueing request for retry after {reset_time}")
            
            # Add to retry queue with timestamp
            retry_item = {
                'url': url,
                'params': params,
                'retry_after': datetime.now(timezone.utc) + timedelta(seconds=self.retry_delay_seconds),
                'attempts': 1
            }
            self.retry_queue.append(retry_item)
            self.sync_stats['rate_limited_requests'] += 1
            self.sync_stats['queued_requests'] += 1
            return None
        
        try:
            headers = self.get_headers()
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            # Always check rate limit info
            self._check_rate_limit(response)
            
            if response.status_code == 200:
                self.sync_stats['successful_requests'] += 1
                return response
            elif response.status_code == 403:
                # Rate limit exceeded
                logger.warning(f"Rate limit exceeded for {url}")
                retry_item = {
                    'url': url,
                    'params': params,
                    'retry_after': datetime.now(timezone.utc) + timedelta(seconds=self.retry_delay_seconds),
                    'attempts': 1
                }
                self.retry_queue.append(retry_item)
                self.sync_stats['rate_limited_requests'] += 1
                self.sync_stats['queued_requests'] += 1
                return None
            elif response.status_code == 401:
                logger.error(f"Unauthorized access to {url}. Check GitHub token permissions.")
                self.sync_stats['failed_requests'] += 1
                return None
            elif response.status_code == 404:
                logger.warning(f"Resource not found: {url}")
                self.sync_stats['failed_requests'] += 1
                return None
            else:
                logger.error(f"HTTP {response.status_code} error for {url}: {response.text[:200]}")
                self.sync_stats['failed_requests'] += 1
                return None
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout for {url}. Adding to retry queue.")
            retry_item = {
                'url': url,
                'params': params,
                'retry_after': datetime.now(timezone.utc) + timedelta(minutes=5),  # Shorter retry for timeouts
                'attempts': 1
            }
            self.retry_queue.append(retry_item)
            self.sync_stats['failed_requests'] += 1
            self.sync_stats['queued_requests'] += 1
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error for {url}: {e}")
            self.sync_stats['failed_requests'] += 1
            return None
    
    def _process_retry_queue(self):
        """Process items in the retry queue that are ready to be retried"""
        current_time = datetime.now(timezone.utc)
        processed_items = []
        
        while self.retry_queue:
            item = self.retry_queue.popleft()
            
            if current_time >= item['retry_after']:
                logger.info(f"Retrying queued request: {item['url']}")
                response = self._make_github_request(item['url'], item['params'])
                
                if response is None and item['attempts'] < 3:
                    # Failed again, re-queue with exponential backoff
                    item['attempts'] += 1
                    backoff_minutes = 5 * (2 ** item['attempts'])  # 10, 20, 40 minutes
                    item['retry_after'] = current_time + timedelta(minutes=backoff_minutes)
                    self.retry_queue.append(item)
                    logger.info(f"Re-queuing failed request for {backoff_minutes} minutes")
                else:
                    processed_items.append((item, response))
                    if response:
                        self.sync_stats['queued_requests'] -= 1
            else:
                # Not ready yet, put it back
                self.retry_queue.append(item)
                break  # Since queue is ordered by time, we can stop here
        
        return processed_items
    
    def _fetch_github_data(self, repo, data_type='issues', state='all', since=None, page=1, per_page=100):
        """Fetch data from GitHub API with comprehensive pagination and filtering"""
        base_url = f"https://api.github.com/repos/{repo}/{data_type}"
        
        params = {
            'state': state,
            'page': page,
            'per_page': per_page,
            'sort': 'updated',
            'direction': 'desc'
        }
        
        # Add since parameter for incremental updates
        if since:
            params['since'] = since
        
        logger.info(f"Fetching {data_type} for {repo} (page {page}, state={state}, since={since})")
        
        response = self._make_github_request(base_url, params)
        
        if response:
            try:
                data = response.json()
                # Check if there are more pages
                link_header = response.headers.get('Link', '')
                has_next_page = 'rel="next"' in link_header
                
                return {
                    'data': data,
                    'has_next_page': has_next_page,
                    'page': page
                }
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for {repo} {data_type}: {e}")
                return None
        
        return None
    
    def _get_last_sync_time_for_repo(self, repo):
        """Get the last sync time for a specific repository"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT last_sync, last_issue_update, last_pr_update 
                FROM repo_sync_metadata 
                WHERE repo = ?
            """, (repo,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'last_sync': result[0],
                    'last_issue_update': result[1],
                    'last_pr_update': result[2]
                }
            return {
                'last_sync': None,
                'last_issue_update': None,
                'last_pr_update': None
            }
            
        except Exception as e:
            logger.error(f"Error getting last sync time for {repo}: {e}")
            return {
                'last_sync': None,
                'last_issue_update': None,
                'last_pr_update': None
            }
    
    def _update_repo_sync_metadata(self, repo, sync_data):
        """Update sync metadata for a specific repository"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            current_time = datetime.now(timezone.utc).isoformat()
            
            cursor.execute("""
                INSERT OR REPLACE INTO repo_sync_metadata 
                (repo, last_sync, last_issue_update, last_pr_update, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                repo, 
                sync_data.get('last_sync', current_time),
                sync_data.get('last_issue_update'),
                sync_data.get('last_pr_update'),
                current_time
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating repo sync metadata for {repo}: {e}")
    
    def _sync_repository_issues(self, repo):
        """Sync issues for a specific repository with incremental updates"""
        try:
            # Get last sync information
            repo_sync_data = self._get_last_sync_time_for_repo(repo)
            since_param = repo_sync_data.get('last_issue_update')
            
            if since_param:
                logger.info(f"Performing incremental sync for {repo} issues since {since_param}")
                self.sync_stats['incremental_updates'] += 1
            else:
                logger.info(f"Performing full sync for {repo} issues")
                self.sync_stats['full_syncs'] += 1
            
            all_issues = []
            page = 1
            max_pages = 3  # Limit pages for unauthenticated requests
            
            while page <= max_pages:
                # Process any pending retries first
                self._process_retry_queue()
                
                result = self._fetch_github_data(repo, 'issues', 'all', since_param, page)
                
                if result is None:
                    logger.warning(f"Failed to fetch issues page {page} for {repo}")
                    break
                
                issues_data = result['data']
                
                # Filter out pull requests (GitHub API includes PRs in issues endpoint)
                issues_only = [item for item in issues_data if not item.get('pull_request')]
                
                if not issues_only:
                    logger.info(f"No more issues found for {repo} at page {page}")
                    break
                
                all_issues.extend(issues_only)
                logger.info(f"Fetched {len(issues_only)} issues from page {page} for {repo}")
                
                # Check if we should continue pagination
                if not result['has_next_page'] or len(issues_only) < 50:
                    break
                
                page += 1
                time.sleep(1)  # Rate limiting between pages
            
            if all_issues:
                # Update database with issues (replace all data - no state tracking)
                updated_count = self._update_database_with_issues(repo, all_issues)
                
                # Update sync metadata
                latest_update = max(issue['updated_at'] for issue in all_issues) if all_issues else None
                sync_data = {
                    'last_sync': datetime.now(timezone.utc).isoformat(),
                    'last_issue_update': latest_update
                }
                self._update_repo_sync_metadata(repo, sync_data)
                
                logger.info(f"Updated {updated_count} issues for {repo}")
                return updated_count
            else:
                logger.info(f"No issues to update for {repo}")
                return 0
                
        except Exception as e:
            logger.error(f"Error syncing issues for {repo}: {e}")
            return 0
    
    def _sync_repository_prs(self, repo):
        """Sync pull requests for a specific repository with incremental updates"""
        try:
            # Get last sync information
            repo_sync_data = self._get_last_sync_time_for_repo(repo)
            since_param = repo_sync_data.get('last_pr_update')
            
            if since_param:
                logger.info(f"Performing incremental sync for {repo} PRs since {since_param}")
                self.sync_stats['incremental_updates'] += 1
            else:
                logger.info(f"Performing full sync for {repo} PRs")
                self.sync_stats['full_syncs'] += 1
            
            all_prs = []
            page = 1
            max_pages = 3  # Limit pages for unauthenticated requests
            
            while page <= max_pages:
                # Process any pending retries first
                self._process_retry_queue()
                
                result = self._fetch_github_data(repo, 'pulls', 'all', since_param, page)
                
                if result is None:
                    logger.warning(f"Failed to fetch PRs page {page} for {repo}")
                    break
                
                prs_data = result['data']
                
                if not prs_data:
                    logger.info(f"No more PRs found for {repo} at page {page}")
                    break
                
                all_prs.extend(prs_data)
                logger.info(f"Fetched {len(prs_data)} PRs from page {page} for {repo}")
                
                # Check if we should continue pagination
                if not result['has_next_page'] or len(prs_data) < 50:
                    break
                
                page += 1
                time.sleep(1)  # Rate limiting between pages
            
            if all_prs:
                # Update database with PRs (replace all data - no state tracking)
                updated_count = self._update_database_with_prs(repo, all_prs)
                
                # Update sync metadata
                latest_update = max(pr['updated_at'] for pr in all_prs) if all_prs else None
                repo_sync_data = self._get_last_sync_time_for_repo(repo)
                sync_data = {
                    'last_sync': datetime.now(timezone.utc).isoformat(),
                    'last_issue_update': repo_sync_data.get('last_issue_update'),  # Preserve existing
                    'last_pr_update': latest_update
                }
                self._update_repo_sync_metadata(repo, sync_data)
                
                logger.info(f"Updated {updated_count} PRs for {repo}")
                return updated_count
            else:
                logger.info(f"No PRs to update for {repo}")
                return 0
                
        except Exception as e:
            logger.error(f"Error syncing PRs for {repo}: {e}")
            return 0
    
    def _update_database_with_issues(self, repo, issues):
        """Update database with issues data - completely replace existing data"""
        if not issues:
            return 0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            updated_count = 0
            last_fetched = datetime.now(timezone.utc).isoformat()
            
            for issue in issues:
                try:
                    # Extract issue data directly from GitHub response
                    number = issue['number']
                    title = issue['title']
                    html_url = issue['html_url']
                    assignee_login = issue['assignee']['login'] if issue.get('assignee') else None
                    created_at = issue['created_at']
                    updated_at = issue['updated_at']
                    body = issue.get('body', '') or ''
                    state = issue['state']  # Use GitHub's actual state
                    closed_at = issue.get('closed_at')
                    
                    # Extract labels
                    labels = []
                    for label in issue.get('labels', []):
                        labels.append({
                            'name': label.get('name', ''),
                            'color': label.get('color', ''),
                            'description': label.get('description', '')
                        })
                    labels_json = json.dumps(labels)
                    
                    # Extract assignees
                    assignees = []
                    for assignee in issue.get('assignees', []):
                        assignees.append({
                            'login': assignee.get('login', ''),
                            'avatar_url': assignee.get('avatar_url', ''),
                            'html_url': assignee.get('html_url', '')
                        })
                    assignees_json = json.dumps(assignees)
                    
                    # Extract mentioned handles from body
                    mentioned_handles = self._extract_mentioned_handles(body)
                    mentioned_handles_json = json.dumps(mentioned_handles)
                    
                    # Use INSERT OR IGNORE first, then UPDATE if needed (preserves existing data)
                    cursor.execute('''
                        INSERT OR IGNORE INTO issues (
                            repo, number, title, html_url, assignee_login, 
                            created_at, updated_at, body, state, closed_at, last_fetched,
                            labels, assignees, mentioned_handles, comments, triage, priority
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 0, -1)
                    ''', (
                        repo, number, title, html_url, assignee_login,
                        created_at, updated_at, body, state, closed_at, last_fetched,
                        labels_json, assignees_json, mentioned_handles_json
                    ))
                    
                    # Update existing record only with changed GitHub data (preserves local data)
                    cursor.execute('''
                        UPDATE issues SET 
                            title = ?, html_url = ?, assignee_login = ?, 
                            updated_at = ?, body = ?, state = ?, closed_at = ?, last_fetched = ?,
                            labels = ?, assignees = ?, mentioned_handles = ?
                        WHERE repo = ? AND number = ? 
                        AND (title != ? OR body != ? OR state != ? OR updated_at != ?)
                    ''', (
                        title, html_url, assignee_login, updated_at, body, state, closed_at, last_fetched,
                        labels_json, assignees_json, mentioned_handles_json,
                        repo, number, title, body, state, updated_at
                    ))
                    
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing issue #{issue.get('number', 'unknown')}: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Database error updating issues for {repo}: {e}")
            return 0
    
    def _update_database_with_prs(self, repo, prs):
        """Update database with pull requests data - completely replace existing data"""
        if not prs:
            return 0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            updated_count = 0
            last_fetched = datetime.now(timezone.utc).isoformat()
            
            for pr in prs:
                try:
                    # Extract PR data directly from GitHub response
                    number = pr['number']
                    title = pr['title']
                    html_url = pr['html_url']
                    user_login = pr['user']['login'] if pr.get('user') else None
                    user_avatar_url = pr['user']['avatar_url'] if pr.get('user') else None
                    created_at = pr['created_at']
                    updated_at = pr['updated_at']
                    body = pr.get('body', '') or ''
                    state = pr['state']  # Use GitHub's actual state
                    draft = pr.get('draft', False)
                    merged = pr.get('merged', False)
                    mergeable_state = pr.get('mergeable_state', '')
                    
                    # Extract base and head refs
                    base_ref = pr.get('base', {}).get('ref', '') if pr.get('base') else ''
                    head_ref = pr.get('head', {}).get('ref', '') if pr.get('head') else ''
                    
                    # Extract labels
                    labels = []
                    for label in pr.get('labels', []):
                        labels.append({
                            'name': label.get('name', ''),
                            'color': label.get('color', ''),
                            'description': label.get('description', '')
                        })
                    labels_json = json.dumps(labels)
                    
                    # Extract assignees
                    assignees = []
                    for assignee in pr.get('assignees', []):
                        assignees.append({
                            'login': assignee.get('login', ''),
                            'avatar_url': assignee.get('avatar_url', ''),
                            'html_url': assignee.get('html_url', '')
                        })
                    assignees_json = json.dumps(assignees)
                    
                    # Extract requested reviewers
                    reviewers = []
                    for reviewer in pr.get('requested_reviewers', []):
                        reviewers.append({
                            'login': reviewer.get('login', ''),
                            'avatar_url': reviewer.get('avatar_url', ''),
                            'html_url': reviewer.get('html_url', '')
                        })
                    reviewers_json = json.dumps(reviewers)
                    
                    # Use INSERT OR IGNORE first, then UPDATE if needed (preserves existing data)
                    cursor.execute('''
                        INSERT OR IGNORE INTO pull_requests (
                            repo, number, title, html_url, user_login, user_avatar_url,
                            created_at, updated_at, body, state, draft, merged,
                            mergeable_state, base_ref, head_ref, last_fetched,
                            labels, assignees, requested_reviewers, comments
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')
                    ''', (
                        repo, number, title, html_url, user_login, user_avatar_url,
                        created_at, updated_at, body, state, draft, merged,
                        mergeable_state, base_ref, head_ref, last_fetched,
                        labels_json, assignees_json, reviewers_json
                    ))
                    
                    # Update existing record only with changed GitHub data (preserves local data like comments)
                    cursor.execute('''
                        UPDATE pull_requests SET 
                            title = ?, html_url = ?, user_login = ?, user_avatar_url = ?,
                            updated_at = ?, body = ?, state = ?, draft = ?, merged = ?,
                            mergeable_state = ?, base_ref = ?, head_ref = ?, last_fetched = ?,
                            labels = ?, assignees = ?, requested_reviewers = ?
                        WHERE repo = ? AND number = ?
                        AND (title != ? OR body != ? OR state != ? OR updated_at != ?)
                    ''', (
                        title, html_url, user_login, user_avatar_url, updated_at, body, state, draft, merged,
                        mergeable_state, base_ref, head_ref, last_fetched,
                        labels_json, assignees_json, reviewers_json,
                        repo, number, title, body, state, updated_at
                    ))
                    
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing PR #{pr.get('number', 'unknown')}: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Database error updating PRs for {repo}: {e}")
            return 0
    
    def _extract_mentioned_handles(self, text):
        """Extract GitHub handles mentioned in text"""
        import re
        if not text:
            return []
        
        # Pattern to match @username mentions
        mention_pattern = r'@([a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38})'
        matches = re.findall(mention_pattern, text)
        
        # Remove duplicates and return
        unique_handles = list(set(matches))
        return unique_handles
    
    def _ensure_database_schema(self):
        """Ensure database has the required schema"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create repositories table with metadata
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS repositories (
                    repo TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    main_category TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert default repositories if they don't exist
            default_repos = [
                ('Azure/azure-sdk-for-js', 'Azure SDK for JavaScript', 'nodejs', 'azure', 1),
                ('Azure/azure-sdk-for-python', 'Azure SDK for Python', 'python', 'azure', 2),
                ('open-telemetry/opentelemetry-js', 'OpenTelemetry JavaScript', 'nodejs', 'opentelemetry', 3),
                ('open-telemetry/opentelemetry-dotnet', 'OpenTelemetry .NET', 'dotnet', 'opentelemetry', 4),
                ('microsoft/ApplicationInsights-js', 'Application Insights JavaScript', 'browser', 'microsoft', 5),
                ('microsoft/ApplicationInsights-node.js', 'Application Insights Node.js', 'nodejs', 'microsoft', 6),
                ('microsoft/ApplicationInsights-dotnet', 'Application Insights .NET', 'dotnet', 'microsoft', 7),
            ]
            
            for repo, display_name, main_category, classification, priority in default_repos:
                cursor.execute('''
                    INSERT OR IGNORE INTO repositories 
                    (repo, display_name, main_category, classification, priority, is_active)
                    VALUES (?, ?, ?, ?, ?, TRUE)
                ''', (repo, display_name, main_category, classification, priority))
            
            # Create issues table - simplified without state tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS issues (
                    repo TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    html_url TEXT NOT NULL,
                    assignee_login TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    body TEXT,
                    state TEXT NOT NULL,
                    closed_at TEXT,
                    last_fetched TEXT,
                    labels TEXT DEFAULT '[]',
                    assignees TEXT DEFAULT '[]',
                    mentioned_handles TEXT DEFAULT '[]',
                    comments TEXT DEFAULT '',
                    triage INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT -1,
                    PRIMARY KEY (repo, number)
                )
            ''')
            
            # Create pull_requests table - simplified without state tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pull_requests (
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
            
            # Create sync metadata tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS repo_sync_metadata (
                    repo TEXT PRIMARY KEY,
                    last_sync TEXT,
                    last_issue_update TEXT,
                    last_pr_update TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database schema initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database schema: {e}")
    
    def sync_all_repositories(self):
        """Sync all configured repositories"""
        with self.sync_lock:
            if self.sync_in_progress:
                logger.warning("Sync already in progress, skipping...")
                return {'success': False, 'message': 'Sync already in progress'}
            
            self.sync_in_progress = True
        
        try:
            logger.info("Starting comprehensive repository sync...")
            start_time = datetime.now(timezone.utc)
            
            # Reset sync statistics
            self.sync_stats.update({
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'rate_limited_requests': 0,
                'queued_requests': len(self.retry_queue),
                'incremental_updates': 0,
                'full_syncs': 0
            })
            
            # Process any pending retry items first
            processed_retries = self._process_retry_queue()
            if processed_retries:
                logger.info(f"Processed {len(processed_retries)} queued requests from retry queue")
            
            total_issues_updated = 0
            total_prs_updated = 0
            
            # Sync each repository
            for i, repo in enumerate(self.repositories):
                try:
                    logger.info(f"Syncing {repo} ({i+1}/{len(self.repositories)})...")
                    
                    # Sync issues
                    issues_updated = self._sync_repository_issues(repo)
                    total_issues_updated += issues_updated
                    
                    # Brief pause between issues and PRs
                    time.sleep(2)
                    
                    # Sync pull requests
                    prs_updated = self._sync_repository_prs(repo)
                    total_prs_updated += prs_updated
                    
                    logger.info(f"{repo}: {issues_updated} issues, {prs_updated} PRs updated")
                    
                    # Longer pause between repositories to respect rate limits
                    if i < len(self.repositories) - 1:  # Don't sleep after the last repo
                        time.sleep(5)
                        
                except Exception as e:
                    logger.error(f"Error syncing {repo}: {e}")
                    continue
            
            # Update global sync metadata
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            self.sync_stats.update({
                'last_sync': start_time.isoformat(),
                'sync_duration': duration
            })
            
            logger.info(f"Sync completed: {total_issues_updated} issues, {total_prs_updated} PRs updated in {duration:.1f}s")
            
            return {
                'success': True,
                'message': 'Sync completed successfully',
                'stats': {
                    'issues_updated': total_issues_updated,
                    'prs_updated': total_prs_updated,
                    'duration': duration,
                    'queued_requests': len(self.retry_queue)
                }
            }
            
        except Exception as e:
            logger.error(f"Critical error during sync: {e}")
            return {'success': False, 'message': f'Sync failed: {str(e)}'}
        finally:
            with self.sync_lock:
                self.sync_in_progress = False
    
    def _start_queue_monitor(self):
        """Start a background thread to monitor and process the retry queue"""
        def queue_monitor():
            while True:
                try:
                    if self.retry_queue:
                        # Check if any items are ready to be processed
                        processed = self._process_retry_queue()
                        if processed:
                            logger.info(f"Queue monitor processed {len(processed)} ready items")
                    
                    # Sleep for 30 seconds between checks
                    time.sleep(30)
                    
                except Exception as e:
                    logger.error(f"Queue monitor error: {e}")
                    time.sleep(30)
        
        monitor_thread = threading.Thread(target=queue_monitor, daemon=True)
        monitor_thread.start()
        logger.info("Queue monitor started successfully")


# Create Flask app for REST API
app = Flask(__name__)

# Add CORS support for repository management
@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

# Handle OPTIONS requests for CORS preflight
@app.route('/api/repositories/manage', methods=['OPTIONS'])
def handle_options():
    return '', 204

# Handle preflight requests
@app.route('/api/repositories/manage', methods=['OPTIONS'])
@app.route('/api/repositories/manage/<path:repo>', methods=['OPTIONS'])
def handle_cors_preflight(repo=None):
    response = jsonify({'status': 'OK'})
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

# Global sync service instance
sync_service = None

def get_sync_service():
    """Get or create the global sync service instance"""
    global sync_service
    if sync_service is None:
        sync_service = GitHubSyncService()
    return sync_service

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'GitHub Issues Sync Service',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/sync/status', methods=['GET'])
def get_sync_status():
    """Get current sync status and statistics"""
    service = get_sync_service()
    
    try:
        conn = sqlite3.connect(service.db_path)
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
        
        cursor.execute("SELECT COUNT(*) FROM pull_requests WHERE merged = 1")
        total_merged_prs = cursor.fetchone()[0]
        
        conn.close()
        
        # Add queue and rate limit information
        queue_status = {
            'retry_queue_size': len(service.retry_queue),
            'next_retry_time': None,
            'rate_limit_remaining': service.rate_limit_remaining,
            'rate_limit_reset_time': service.rate_limit_reset_time.isoformat() if service.rate_limit_reset_time else None,
            'is_rate_limited': service._is_rate_limited()
        }
        
        # Get next retry time if queue is not empty
        if service.retry_queue:
            queue_status['next_retry_time'] = service.retry_queue[0]['retry_after'].isoformat()
        
        return jsonify({
            'success': True,
            'sync_in_progress': service.sync_in_progress,
            'last_sync': service.sync_stats.get('last_sync'),
            'sync_duration': service.sync_stats.get('sync_duration', 0),
            'totals': {
                'open_issues': total_open_issues,
                'closed_issues': total_closed_issues,
                'open_prs': total_open_prs,
                'closed_prs': total_closed_prs,
                'merged_prs': total_merged_prs
            },
            'by_repo': {
                'issues': issue_stats,
                'prs': pr_stats
            },
            'queue_status': queue_status,
            'sync_stats': service.sync_stats
        })
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sync/start', methods=['POST'])
def start_sync():
    """Start a new sync operation"""
    service = get_sync_service()
    
    if service.sync_in_progress:
        return jsonify({
            'success': False,
            'message': 'Sync already in progress'
        }), 409
    
    # Start sync in background thread
    def run_sync():
        service.sync_all_repositories()
    
    sync_thread = threading.Thread(target=run_sync, daemon=True)
    sync_thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Sync started successfully'
    })

@app.route('/api/data/issues', methods=['GET'])
def get_issues():
    """Get issues data with optional filtering"""
    service = get_sync_service()
    
    try:
        # Get query parameters
        repo = request.args.get('repo')
        state = request.args.get('state')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        conn = sqlite3.connect(service.db_path)
        cursor = conn.cursor()
        
        # Build query with filters
        query = "SELECT * FROM issues"
        params = []
        conditions = []
        
        if repo:
            conditions.append("repo = ?")
            params.append(repo)
        
        if state:
            conditions.append("state = ?")
            params.append(state)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        columns = [description[0] for description in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            issue = dict(zip(columns, row))
            # Parse JSON fields
            try:
                issue['labels'] = json.loads(issue.get('labels', '[]'))
                issue['assignees'] = json.loads(issue.get('assignees', '[]'))
                issue['mentioned_handles'] = json.loads(issue.get('mentioned_handles', '[]'))
            except json.JSONDecodeError:
                pass
            results.append(issue)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': results,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'count': len(results)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting issues: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/data/prs', methods=['GET'])
def get_prs():
    """Get pull requests data with optional filtering"""
    service = get_sync_service()
    
    try:
        # Get query parameters
        repo = request.args.get('repo')
        state = request.args.get('state')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        conn = sqlite3.connect(service.db_path)
        cursor = conn.cursor()
        
        # Build query with filters
        query = "SELECT * FROM pull_requests"
        params = []
        conditions = []
        
        if repo:
            conditions.append("repo = ?")
            params.append(repo)
        
        if state:
            conditions.append("state = ?")
            params.append(state)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        columns = [description[0] for description in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            pr = dict(zip(columns, row))
            # Parse JSON fields
            try:
                pr['labels'] = json.loads(pr.get('labels', '[]'))
                pr['assignees'] = json.loads(pr.get('assignees', '[]'))
                pr['requested_reviewers'] = json.loads(pr.get('requested_reviewers', '[]'))
            except json.JSONDecodeError:
                pass
            results.append(pr)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': results,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'count': len(results)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting PRs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/data/repositories', methods=['GET'])
def get_repositories():
    """Get list of repositories with metadata"""
    service = get_sync_service()
    
    try:
        # Get repositories with full metadata
        repositories_with_metadata = service.get_repositories_with_metadata()
        
        # Also get simple list for backward compatibility
        repository_names = [repo['repo'] for repo in repositories_with_metadata]
        
        # Get actual repositories from the database that have data
        conn = sqlite3.connect(service.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get unique repository names from both issues and pull_requests tables
        cursor.execute("""
            SELECT DISTINCT repo FROM (
                SELECT DISTINCT repo FROM issues
                UNION
                SELECT DISTINCT repo FROM pull_requests
            ) ORDER BY repo
        """)
        
        repos_with_data = [row['repo'] for row in cursor.fetchall()]
        conn.close()
        
        # Filter metadata to only include repos that actually have data
        active_repositories = []
        for repo_metadata in repositories_with_metadata:
            if repo_metadata['repo'] in repos_with_data:
                active_repositories.append(repo_metadata)
        
        return jsonify({
            'success': True,
            'repositories': repos_with_data,  # Simple list for backward compatibility
            'repositories_metadata': active_repositories,  # Rich metadata
            'total_configured': len(repositories_with_metadata),
            'total_with_data': len(repos_with_data)
        })
    except Exception as e:
        logger.error(f"Error getting repositories: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'repositories': [],
            'repositories_metadata': []
        }), 500

@app.route('/api/repositories/manage', methods=['GET'])
def list_all_repositories():
    """Get all repositories (including inactive) for management"""
    service = get_sync_service()
    
    try:
        conn = sqlite3.connect(service.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT repo, display_name, main_category, classification, priority, is_active,
                   created_at, updated_at
            FROM repositories 
            ORDER BY 
                CASE classification 
                    WHEN 'azure' THEN 1 
                    WHEN 'opentelemetry' THEN 2 
                    WHEN 'microsoft' THEN 3 
                    ELSE 4 
                END,
                priority ASC
        ''')
        
        repositories = []
        for row in cursor.fetchall():
            repositories.append({
                'repo': row['repo'],
                'display_name': row['display_name'],
                'main_category': row['main_category'],
                'classification': row['classification'],
                'priority': row['priority'],
                'is_active': bool(row['is_active']),
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'repositories': repositories,
            'total': len(repositories)
        })
        
    except Exception as e:
        logger.error(f"Error listing all repositories: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/repositories/manage', methods=['POST'])
def add_repository():
    """Add a new repository to monitor"""
    service = get_sync_service()
    
    try:
        data = request.get_json()
        required_fields = ['repo', 'display_name', 'main_category', 'classification', 'priority']
        
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        conn = sqlite3.connect(service.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO repositories 
            (repo, display_name, main_category, classification, priority, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['repo'],
            data['display_name'],
            data['main_category'],
            data['classification'],
            data['priority'],
            data.get('is_active', True)
        ))
        
        conn.commit()
        conn.close()
        
        # Reload repositories list
        service._load_repositories_from_db()
        
        return jsonify({
            'success': True,
            'message': f'Repository {data["repo"]} added successfully'
        })
        
    except sqlite3.IntegrityError:
        return jsonify({
            'success': False,
            'error': 'Repository already exists'
        }), 409
    except Exception as e:
        logger.error(f"Error adding repository: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/repositories/manage/<path:repo>', methods=['PUT'])
def update_repository(repo):
    """Update repository metadata"""
    service = get_sync_service()
    
    try:
        data = request.get_json()
        
        conn = sqlite3.connect(service.db_path)
        cursor = conn.cursor()
        
        # Build dynamic update query
        update_fields = []
        update_values = []
        
        allowed_fields = ['display_name', 'main_category', 'classification', 'priority', 'is_active']
        for field in allowed_fields:
            if field in data:
                update_fields.append(f'{field} = ?')
                update_values.append(data[field])
        
        if not update_fields:
            return jsonify({
                'success': False,
                'error': 'No valid fields to update'
            }), 400
        
        update_values.append(repo)  # Add repo for WHERE clause
        
        query = f'''
            UPDATE repositories 
            SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE repo = ?
        '''
        
        cursor.execute(query, update_values)
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Repository not found'
            }), 404
        
        conn.commit()
        conn.close()
        
        # Reload repositories list
        service._load_repositories_from_db()
        
        return jsonify({
            'success': True,
            'message': f'Repository {repo} updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating repository: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/repositories/manage/<path:repo>', methods=['DELETE'])
def delete_repository(repo):
    """Delete repository from database"""
    service = get_sync_service()
    
    try:
        conn = sqlite3.connect(service.db_path)
        cursor = conn.cursor()
        
        # Check if repository exists
        cursor.execute('SELECT COUNT(*) FROM repositories WHERE repo = ?', (repo,))
        if cursor.fetchone()[0] == 0:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Repository not found'
            }), 404
        
        # Delete the repository
        cursor.execute('DELETE FROM repositories WHERE repo = ?', (repo,))
        
        # Also delete related issues and PRs
        cursor.execute('DELETE FROM issues WHERE repo = ?', (repo,))
        cursor.execute('DELETE FROM prs WHERE repo = ?', (repo,))
        
        conn.commit()
        conn.close()
        
        # Reload repositories list
        service._load_repositories_from_db()
        
        return jsonify({
            'success': True,
            'message': f'Repository {repo} deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting repository: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/queue/status', methods=['GET'])
def get_queue_status():
    """Get detailed retry queue status"""
    service = get_sync_service()
    
    queue_items = []
    for item in list(service.retry_queue):
        queue_items.append({
            'url': item['url'],
            'retry_after': item['retry_after'].isoformat(),
            'attempts': item['attempts'],
            'time_until_retry': (item['retry_after'] - datetime.now(timezone.utc)).total_seconds()
        })
    
    return jsonify({
        'success': True,
        'queue_size': len(service.retry_queue),
        'queue_items': queue_items,
        'rate_limit_remaining': service.rate_limit_remaining,
        'rate_limit_reset_time': service.rate_limit_reset_time.isoformat() if service.rate_limit_reset_time else None,
        'is_rate_limited': service._is_rate_limited()
    })

@app.route('/api/queue/process', methods=['POST'])
def process_queue():
    """Force process retry queue"""
    service = get_sync_service()
    
    if not service.retry_queue:
        return jsonify({
            'success': True,
            'message': 'Retry queue is empty',
            'processed': 0
        })
    
    processed_items = service._process_retry_queue()
    
    return jsonify({
        'success': True,
        'message': f'Processed {len(processed_items)} queued requests',
        'processed': len(processed_items),
        'remaining_in_queue': len(service.retry_queue)
    })

@app.route('/api/auth/status', methods=['GET'])
def get_auth_status():
    """Get authentication status"""
    
    return jsonify({
        'success': True,
        'status': 'unauthenticated',
        'has_token': False,
        'expected_rate_limit': 60,
        'current_rate_limit_remaining': get_sync_service().rate_limit_remaining,
        'rate_limit_reset_time': get_sync_service().rate_limit_reset_time.isoformat() if get_sync_service().rate_limit_reset_time else None,
        'is_rate_limited': get_sync_service()._is_rate_limited()
    })

def main():
    """Main entry point for the sync service"""
    # Initialize the sync service
    service = get_sync_service()
    logger.info("GitHub Issues Sync Service starting up...")
    
    # Get configuration
    host = os.environ.get('SYNC_SERVICE_HOST', '127.0.0.1')
    port = int(os.environ.get('SYNC_SERVICE_PORT', 5001))
    debug = os.environ.get('SYNC_SERVICE_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting sync service on {host}:{port}")
    logger.info("GitHub token: not configured (running unauthenticated)")
    logger.info(f"Monitoring {len(service.repositories)} repositories")
    
    # Start the Flask app
    try:
        if debug:
            app.run(host=host, port=port, debug=True)
        else:
            # Use Werkzeug's threaded server for production
            run_simple(host, port, app, threaded=True, use_reloader=False, use_debugger=False)
    except KeyboardInterrupt:
        logger.info("Sync service shutting down...")
    except Exception as e:
        logger.error(f"Error starting sync service: {e}")

if __name__ == '__main__':
    main()
