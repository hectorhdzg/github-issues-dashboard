#!/usr/bin/env python3
"""
Script to set up repository configuration for deployment environments.
This script handles the initial repository setup and data population for deployed instances.
"""

import sqlite3
import json
import logging
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DeploymentRepositoryManager:
    """Manages repository configuration for deployment environments"""
    
    def __init__(self, db_path="data/github_issues.db"):
        self.db_path = db_path
        self.repositories_config = {
            # Azure SDK repositories
            "Azure/azure-sdk-for-js": {
                "display_name": "Azure SDK for JavaScript",
                "main_category": "nodejs",
                "classification": "azure",
                "priority": 1,
                "is_active": True
            },
            "Azure/azure-sdk-for-python": {
                "display_name": "Azure SDK for Python", 
                "main_category": "python",
                "classification": "azure",
                "priority": 2,
                "is_active": True
            },
            "Azure/azure-sdk-for-net": {
                "display_name": "Azure SDK for .NET",
                "main_category": "dotnet", 
                "classification": "azure",
                "priority": 3,
                "is_active": True
            },
            "Azure/azure-sdk-for-java": {
                "display_name": "Azure SDK for Java",
                "main_category": "java",
                "classification": "azure", 
                "priority": 4,
                "is_active": True
            },
            
            # OpenTelemetry repositories
            "open-telemetry/opentelemetry-js": {
                "display_name": "OpenTelemetry JavaScript",
                "main_category": "nodejs",
                "classification": "opentelemetry",
                "priority": 10,
                "is_active": True
            },
            "open-telemetry/opentelemetry-js-contrib": {
                "display_name": "OpenTelemetry JavaScript Contrib",
                "main_category": "nodejs", 
                "classification": "opentelemetry",
                "priority": 11,
                "is_active": True
            },
            "open-telemetry/opentelemetry-python": {
                "display_name": "OpenTelemetry Python",
                "main_category": "python",
                "classification": "opentelemetry",
                "priority": 12,
                "is_active": True
            },
            "open-telemetry/opentelemetry-python-contrib": {
                "display_name": "OpenTelemetry Python Contrib",
                "main_category": "python",
                "classification": "opentelemetry", 
                "priority": 13,
                "is_active": True
            },
            "open-telemetry/opentelemetry-dotnet": {
                "display_name": "OpenTelemetry .NET",
                "main_category": "dotnet",
                "classification": "opentelemetry",
                "priority": 14,
                "is_active": True
            },
            "open-telemetry/opentelemetry-java": {
                "display_name": "OpenTelemetry Java",
                "main_category": "java",
                "classification": "opentelemetry",
                "priority": 15,
                "is_active": True
            },
            
            # Microsoft Application Insights repositories
            "microsoft/ApplicationInsights-js": {
                "display_name": "Application Insights JavaScript",
                "main_category": "browser",
                "classification": "microsoft",
                "priority": 20,
                "is_active": True
            },
            "microsoft/ApplicationInsights-node.js": {
                "display_name": "Application Insights Node.js",
                "main_category": "nodejs",
                "classification": "microsoft",
                "priority": 21,
                "is_active": True
            },
            "microsoft/ApplicationInsights-dotnet": {
                "display_name": "Application Insights .NET",
                "main_category": "dotnet",
                "classification": "microsoft",
                "priority": 22,
                "is_active": True
            },
            "microsoft/ApplicationInsights-Java": {
                "display_name": "Application Insights Java",
                "main_category": "java",
                "classification": "microsoft",
                "priority": 23,
                "is_active": True
            },
            "microsoft/applicationinsights-react-js": {
                "display_name": "Application Insights React",
                "main_category": "browser",
                "classification": "microsoft",
                "priority": 24,
                "is_active": True
            },
            "microsoft/applicationinsights-react-native": {
                "display_name": "Application Insights React Native",
                "main_category": "browser",
                "classification": "microsoft",
                "priority": 25,
                "is_active": True
            },
            "microsoft/applicationinsights-angularplugin-js": {
                "display_name": "Application Insights Angular",
                "main_category": "browser", 
                "classification": "microsoft",
                "priority": 26,
                "is_active": True
            },
            "microsoft/DynamicProto-JS": {
                "display_name": "DynamicProto JavaScript",
                "main_category": "browser",
                "classification": "microsoft",
                "priority": 27,
                "is_active": True
            },
            "microsoft/node-diagnostic-channel": {
                "display_name": "Node Diagnostic Channel",
                "main_category": "nodejs",
                "classification": "microsoft",
                "priority": 28,
                "is_active": True
            },
            "microsoft/ApplicationInsights-node.js-native-metrics": {
                "display_name": "Application Insights Native Metrics",
                "main_category": "nodejs",
                "classification": "microsoft",
                "priority": 29,
                "is_active": True
            }
        }
    
    def ensure_database_directory(self):
        """Ensure the database directory exists"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Database directory ensured: {db_dir}")
    
    def create_database_schema(self):
        """Create the database schema if it doesn't exist"""
        try:
            self.ensure_database_directory()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create repositories table
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
            
            # Create issues table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS issues (
                    repo TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT,
                    closed_at TEXT,
                    author TEXT,
                    assignee TEXT,
                    labels TEXT,
                    milestone TEXT,
                    comments_count INTEGER DEFAULT 0,
                    body TEXT,
                    html_url TEXT,
                    PRIMARY KEY (repo, number)
                )
            ''')
            
            # Create pull_requests table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pull_requests (
                    repo TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT,
                    closed_at TEXT,
                    merged_at TEXT,
                    author TEXT,
                    assignee TEXT,
                    labels TEXT,
                    milestone TEXT,
                    comments_count INTEGER DEFAULT 0,
                    body TEXT,
                    html_url TEXT,
                    draft BOOLEAN DEFAULT FALSE,
                    merged BOOLEAN DEFAULT FALSE,
                    mergeable_state TEXT,
                    base_ref TEXT,
                    head_ref TEXT,
                    assignees TEXT,
                    requested_reviewers TEXT,
                    PRIMARY KEY (repo, number)
                )
            ''')
            
            # Create sync_metadata table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create repo_sync_metadata table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS repo_sync_metadata (
                    repo TEXT PRIMARY KEY,
                    last_sync_at TIMESTAMP,
                    sync_status TEXT,
                    issues_count INTEGER DEFAULT 0,
                    prs_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database schema created successfully")
            
        except Exception as e:
            logger.error(f"Error creating database schema: {e}")
            raise
    
    def populate_repositories(self, force_update=False):
        """Populate the repositories table with the configured repositories"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for repo_name, config in self.repositories_config.items():
                try:
                    # Check if repository already exists
                    cursor.execute('SELECT repo FROM repositories WHERE repo = ?', (repo_name,))
                    exists = cursor.fetchone()
                    
                    if exists and not force_update:
                        logger.info(f"Repository {repo_name} already exists, skipping")
                        continue
                    
                    if exists and force_update:
                        # Update existing repository
                        cursor.execute('''
                            UPDATE repositories 
                            SET display_name = ?, main_category = ?, classification = ?, 
                                priority = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE repo = ?
                        ''', (
                            config['display_name'],
                            config['main_category'], 
                            config['classification'],
                            config['priority'],
                            config['is_active'],
                            repo_name
                        ))
                        logger.info(f"Updated repository: {repo_name}")
                    else:
                        # Insert new repository
                        cursor.execute('''
                            INSERT INTO repositories 
                            (repo, display_name, main_category, classification, priority, is_active)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            repo_name,
                            config['display_name'],
                            config['main_category'],
                            config['classification'], 
                            config['priority'],
                            config['is_active']
                        ))
                        logger.info(f"Added repository: {repo_name}")
                        
                except Exception as e:
                    logger.error(f"Error processing repository {repo_name}: {e}")
                    continue
            
            conn.commit()
            conn.close()
            logger.info("Repository population completed")
            
        except Exception as e:
            logger.error(f"Error populating repositories: {e}")
            raise
    
    def get_repository_summary(self):
        """Get a summary of configured repositories and their data status"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all repositories with data counts
            cursor.execute('''
                SELECT 
                    r.repo,
                    r.display_name,
                    r.main_category,
                    r.classification,
                    r.priority,
                    r.is_active,
                    COALESCE(i.issues_count, 0) as issues_count,
                    COALESCE(p.prs_count, 0) as prs_count
                FROM repositories r
                LEFT JOIN (
                    SELECT repo, COUNT(*) as issues_count 
                    FROM issues 
                    GROUP BY repo
                ) i ON r.repo = i.repo
                LEFT JOIN (
                    SELECT repo, COUNT(*) as prs_count 
                    FROM pull_requests 
                    GROUP BY repo
                ) p ON r.repo = p.repo
                ORDER BY 
                    CASE r.classification 
                        WHEN 'azure' THEN 1 
                        WHEN 'opentelemetry' THEN 2 
                        WHEN 'microsoft' THEN 3 
                        ELSE 4 
                    END,
                    r.priority ASC
            ''')
            
            repositories = cursor.fetchall()
            conn.close()
            
            # Create summary
            summary = {
                'total_configured': len(repositories),
                'active_repos': len([r for r in repositories if r['is_active']]),
                'repos_with_data': len([r for r in repositories if r['issues_count'] > 0 or r['prs_count'] > 0]),
                'total_issues': sum(r['issues_count'] for r in repositories),
                'total_prs': sum(r['prs_count'] for r in repositories),
                'by_category': {},
                'repositories': []
            }
            
            # Group by category
            for repo in repositories:
                category = repo['main_category']
                if category not in summary['by_category']:
                    summary['by_category'][category] = {
                        'count': 0,
                        'issues': 0,
                        'prs': 0,
                        'repos': []
                    }
                
                summary['by_category'][category]['count'] += 1
                summary['by_category'][category]['issues'] += repo['issues_count']
                summary['by_category'][category]['prs'] += repo['prs_count']
                summary['by_category'][category]['repos'].append(repo['repo'])
                
                summary['repositories'].append({
                    'repo': repo['repo'],
                    'display_name': repo['display_name'], 
                    'category': repo['main_category'],
                    'classification': repo['classification'],
                    'priority': repo['priority'],
                    'is_active': bool(repo['is_active']),
                    'issues_count': repo['issues_count'],
                    'prs_count': repo['prs_count'],
                    'has_data': repo['issues_count'] > 0 or repo['prs_count'] > 0
                })
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting repository summary: {e}")
            raise
    
    def export_configuration(self, output_file="repository_config.json"):
        """Export current repository configuration to JSON"""
        try:
            summary = self.get_repository_summary()
            
            with open(output_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            logger.info(f"Repository configuration exported to {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Error exporting configuration: {e}")
            raise
    
    def import_configuration(self, config_file="repository_config.json"):
        """Import repository configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Import repositories from the config
            for repo_data in config.get('repositories', []):
                self.repositories_config[repo_data['repo']] = {
                    'display_name': repo_data['display_name'],
                    'main_category': repo_data['category'],
                    'classification': repo_data['classification'],
                    'priority': repo_data['priority'],
                    'is_active': repo_data['is_active']
                }
            
            # Populate the database
            self.populate_repositories(force_update=True)
            logger.info(f"Repository configuration imported from {config_file}")
            
        except Exception as e:
            logger.error(f"Error importing configuration: {e}")
            raise

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup repository configuration for deployment')
    parser.add_argument('--db-path', default='data/github_issues.db', help='Database file path')
    parser.add_argument('--action', choices=['setup', 'summary', 'export', 'import'], 
                       default='setup', help='Action to perform')
    parser.add_argument('--config-file', help='Configuration file for import/export')
    parser.add_argument('--force-update', action='store_true', 
                       help='Force update existing repositories')
    
    args = parser.parse_args()
    
    manager = DeploymentRepositoryManager(args.db_path)
    
    try:
        if args.action == 'setup':
            logger.info("Setting up deployment repositories...")
            manager.create_database_schema()
            manager.populate_repositories(force_update=args.force_update)
            
        elif args.action == 'summary':
            summary = manager.get_repository_summary()
            print(f"\n=== Repository Summary ===")
            print(f"Total configured: {summary['total_configured']}")
            print(f"Active repositories: {summary['active_repos']}")
            print(f"Repositories with data: {summary['repos_with_data']}")
            print(f"Total issues: {summary['total_issues']}")
            print(f"Total PRs: {summary['total_prs']}")
            
            print(f"\n=== By Category ===")
            for category, data in summary['by_category'].items():
                print(f"{category}: {data['count']} repos, {data['issues']} issues, {data['prs']} PRs")
            
        elif args.action == 'export':
            config_file = args.config_file or 'repository_config.json'
            manager.export_configuration(config_file)
            
        elif args.action == 'import':
            if not args.config_file:
                print("Error: --config-file required for import action")
                sys.exit(1)
            manager.import_configuration(args.config_file)
        
        logger.info(f"Action '{args.action}' completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to complete action '{args.action}': {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
