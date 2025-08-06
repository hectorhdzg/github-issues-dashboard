#!/usr/bin/env python3
"""
Populate test data for GitHub Issues Dashboard
This script adds sample data so you can see the dashboard working
"""

import sqlite3
import json
from datetime import datetime, timezone

def create_sample_data():
    """Create sample GitHub issues and PRs data"""
    
    # Connect to database
    conn = sqlite3.connect('github_issues.db')
    cursor = conn.cursor()
    
    # Create table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS github_issues (
            id INTEGER PRIMARY KEY,
            number INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT,
            state TEXT NOT NULL DEFAULT 'open',
            author TEXT,
            assignees TEXT,
            labels TEXT,
            milestone TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            closed_at TIMESTAMP,
            url TEXT,
            html_url TEXT,
            api_url TEXT,
            repository_name TEXT NOT NULL,
            is_pull_request BOOLEAN DEFAULT 0,
            pr_url TEXT,
            UNIQUE(repository_name, number, is_pull_request)
        )
    ''')
    
    # Sample repositories
    repositories = [
        'open-telemetry/opentelemetry-js',
        'open-telemetry/opentelemetry-python',
        'microsoft/ApplicationInsights-dotnet',
        'microsoft/ApplicationInsights-Java',
        'open-telemetry/opentelemetry-browser-extension'
    ]
    
    # Sample issues and PRs
    sample_data = [
        # OpenTelemetry JS
        {
            'number': 4856, 'title': 'Memory leak in trace exports',
            'body': 'We are experiencing memory leaks when exporting traces...', 
            'state': 'open', 'author': 'user1', 'repository_name': 'open-telemetry/opentelemetry-js',
            'is_pull_request': False, 'labels': '["bug", "memory-leak"]'
        },
        {
            'number': 4857, 'title': 'Fix: Handle undefined spans gracefully',
            'body': 'This PR fixes the issue where undefined spans cause crashes...', 
            'state': 'open', 'author': 'contributor1', 'repository_name': 'open-telemetry/opentelemetry-js',
            'is_pull_request': True, 'labels': '["fix", "pr"]'
        },
        {
            'number': 4850, 'title': 'Performance improvement for batching',
            'body': 'Closed: Implemented batch optimization', 
            'state': 'closed', 'author': 'maintainer1', 'repository_name': 'open-telemetry/opentelemetry-js',
            'is_pull_request': False, 'labels': '["enhancement", "performance"]'
        },
        
        # OpenTelemetry Python
        {
            'number': 3245, 'title': 'Add support for custom propagators',
            'body': 'Feature request to add support for custom propagation...', 
            'state': 'open', 'author': 'user2', 'repository_name': 'open-telemetry/opentelemetry-python',
            'is_pull_request': False, 'labels': '["enhancement", "feature-request"]'
        },
        {
            'number': 3246, 'title': 'feat: Custom propagator implementation',
            'body': 'This PR implements the custom propagator feature...', 
            'state': 'open', 'author': 'contributor2', 'repository_name': 'open-telemetry/opentelemetry-python',
            'is_pull_request': True, 'labels': '["feature", "pr"]'
        },
        
        # ApplicationInsights .NET
        {
            'number': 2844, 'title': 'NullReferenceException in TelemetryClient',
            'body': 'Getting null reference exception when calling TrackEvent...', 
            'state': 'open', 'author': 'user3', 'repository_name': 'microsoft/ApplicationInsights-dotnet',
            'is_pull_request': False, 'labels': '["bug", "dotnet"]'
        },
        {
            'number': 2845, 'title': 'Update dependencies to latest versions',
            'body': 'This PR updates all dependencies to their latest stable versions...', 
            'state': 'closed', 'author': 'maintainer2', 'repository_name': 'microsoft/ApplicationInsights-dotnet',
            'is_pull_request': True, 'labels': '["dependencies", "maintenance"]'
        },
        
        # ApplicationInsights Java
        {
            'number': 3234, 'title': 'Spring Boot 3 compatibility issue',
            'body': 'The agent is not working with Spring Boot 3...', 
            'state': 'open', 'author': 'user4', 'repository_name': 'microsoft/ApplicationInsights-Java',
            'is_pull_request': False, 'labels': '["bug", "spring-boot", "java"]'
        },
        {
            'number': 3220, 'title': 'Documentation updates for v3.5',
            'body': 'Closed: Updated documentation for the new release', 
            'state': 'closed', 'author': 'maintainer3', 'repository_name': 'microsoft/ApplicationInsights-Java',
            'is_pull_request': False, 'labels': '["documentation"]'
        },
        
        # Browser Extension
        {
            'number': 145, 'title': 'Add dark mode support',
            'body': 'Feature request for dark mode in the extension UI...', 
            'state': 'open', 'author': 'user5', 'repository_name': 'open-telemetry/opentelemetry-browser-extension',
            'is_pull_request': False, 'labels': '["enhancement", "ui"]'
        }
    ]
    
    # Insert sample data
    for item in sample_data:
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute('''
            INSERT OR REPLACE INTO github_issues 
            (number, title, body, state, author, repository_name, is_pull_request, 
             labels, created_at, updated_at, 
             html_url, url, api_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item['number'], item['title'], item['body'], item['state'], 
            item['author'], item['repository_name'], item['is_pull_request'],
            item['labels'], now, now,
            f"https://github.com/{item['repository_name']}/{'pull' if item['is_pull_request'] else 'issues'}/{item['number']}",
            f"https://api.github.com/repos/{item['repository_name']}/{'pulls' if item['is_pull_request'] else 'issues'}/{item['number']}",
            f"https://api.github.com/repos/{item['repository_name']}/{'pulls' if item['is_pull_request'] else 'issues'}/{item['number']}"
        ))
    
    conn.commit()
    
    # Show summary
    cursor.execute('SELECT COUNT(*) FROM github_issues WHERE is_pull_request = 0')
    issues_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM github_issues WHERE is_pull_request = 1')
    prs_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM github_issues WHERE state = "open"')
    open_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM github_issues WHERE state = "closed"')
    closed_count = cursor.fetchone()[0]
    
    print(f"✅ Sample data created successfully!")
    print(f"📊 Summary:")
    print(f"   - Issues: {issues_count}")
    print(f"   - Pull Requests: {prs_count}")
    print(f"   - Open: {open_count}")
    print(f"   - Closed: {closed_count}")
    print(f"   - Total items: {issues_count + prs_count}")
    
    conn.close()

if __name__ == '__main__':
    print("🚀 Creating sample data for GitHub Issues Dashboard...")
    create_sample_data()
    print("🎉 Ready to test your dashboard!")
    print("   Start the services with: python start_all.py")
    print("   Or manually: python sync_service.py & python app.py")
