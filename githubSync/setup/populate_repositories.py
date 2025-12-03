#!/usr/bin/env python3
"""
Repository Data Population Script

Populates the database with all repository configurations.
Run this AFTER running setup_database.py
"""

import sqlite3
import json
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database path
DATABASE_PATH = os.getenv('DATABASE_PATH', '../data/github_issues.db')

def populate_repositories():
    """Populate database with all repository configurations"""
    
    # All repository data
    repositories = [
        ('Azure/azure-sdk-for-python', 'Azure SDK for Python', 'Azure SDK', 'Python', 1, 1, json.dumps({
            "issues": {"labels": ["Monitor - Distro", "Monitor - Exporter", "Monitor - ApplicationInsights", "OpenTelemetry"], "state": "all"},
            "pull_requests": {"labels": ["Monitor - Distro", "Monitor - Exporter", "Monitor - ApplicationInsights", "OpenTelemetry"], "state": "all"}
        })),
        ('Azure/azure-sdk-for-js', 'Azure SDK for JavaScript', 'Azure SDK', 'JavaScript', 1, 1, json.dumps({
            "issues": {"labels": ["Monitor - Distro", "Monitor - Exporter", "Monitor - ApplicationInsights", "OpenTelemetry"], "state": "all"},
            "pull_requests": {"labels": ["Monitor - Distro", "Monitor - Exporter", "Monitor - ApplicationInsights", "OpenTelemetry"], "state": "all"}
        })),
        ('Azure/azure-sdk-for-net', 'Azure SDK for .NET', 'Azure SDK', 'DotNet', 1, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('open-telemetry/opentelemetry-js', 'OpenTelemetry JavaScript', 'OpenTelemetry', 'JavaScript', 3, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('open-telemetry/opentelemetry-js-contrib', 'OpenTelemetry JavaScript Contrib', 'OpenTelemetry', 'JavaScript', 3, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('open-telemetry/opentelemetry-python', 'OpenTelemetry Python', 'OpenTelemetry', 'Python', 3, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('open-telemetry/opentelemetry-python-contrib', 'OpenTelemetry Python Contrib', 'OpenTelemetry', 'Python', 3, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('open-telemetry/opentelemetry-dotnet', 'OpenTelemetry .NET', 'OpenTelemetry', 'DotNet', 3, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('microsoft/ApplicationInsights-node.js', 'Application Insights Node.js', 'Application Insights', 'JavaScript', 2, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('microsoft/ApplicationInsights-js', 'Application Insights JavaScript', 'Application Insights', 'JavaScript', 2, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('microsoft/applicationinsights-react-js', 'Application Insights React', 'Application Insights', 'JavaScript', 2, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('microsoft/applicationinsights-react-native', 'Application Insights React Native', 'Application Insights', 'JavaScript', 2, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('microsoft/applicationinsights-angularplugin-js', 'Application Insights Angular', 'Application Insights', 'JavaScript', 2, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('microsoft/DynamicProto-JS', 'DynamicProto JavaScript', 'Application Insights', 'JavaScript', 2, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('microsoft/node-diagnostic-channel', 'Node Diagnostic Channel', 'Application Insights', 'JavaScript', 2, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('microsoft/ApplicationInsights-node.js-native-metrics', 'Application Insights Native Metrics', 'Application Insights', 'JavaScript', 2, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        })),
        ('microsoft/ApplicationInsights-dotnet', 'Application Insights .NET', 'Application Insights', 'DotNet', 2, 1, json.dumps({
            "issues": {"state": "all"},
            "pull_requests": {"state": "all"}
        }))
    ]
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Check if any repositories already exist
    cursor.execute('SELECT COUNT(*) FROM repositories')
    existing_count = cursor.fetchone()[0]
    
    if existing_count > 0:
        logger.info(f"Found {existing_count} existing repositories in database")
        logger.info("Skipping population - repositories already exist")
        conn.close()
        return
    
    logger.info("No existing repositories found - proceeding with population")
    
    # Insert all repositories
    added_count = 0
    skipped_count = 0
    for repo_data in repositories:
        try:
            cursor.execute('''
                INSERT INTO repositories 
                (repo, display_name, main_category, classification, priority, is_active, filters)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', repo_data)
            
            logger.info(f"✅ Added: {repo_data[0]} ({repo_data[2]})")
            added_count += 1
        except sqlite3.IntegrityError:
            logger.info(f"⚠️  Repository {repo_data[0]} already exists - skipping")
            skipped_count += 1
    
    conn.commit()
    conn.close()
    
    if added_count > 0:
        logger.info(f"🎉 Successfully added {added_count} new repositories")
    if skipped_count > 0:
        logger.info(f"⚠️  Skipped {skipped_count} repositories that already existed")
    if added_count == 0 and skipped_count > 0:
        logger.info("🔍 All repositories already exist - no changes made")

def main():
    """Main population function"""
    try:
        logger.info("Populating GitHub Sync Service repository data...")
        populate_repositories()
        logger.info("Repository data population completed!")
    except Exception as e:
        logger.error(f"Data population failed: {e}")
        raise

if __name__ == "__main__":
    main()