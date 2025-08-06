import sqlite3
import json
from datetime import datetime, timezone

def migrate_repositories_table():
    """Migrate the old repositories table to the new schema with metadata"""
    
    conn = sqlite3.connect('github_issues.db')
    cursor = conn.cursor()
    
    print("Starting repository table migration...")
    
    # 1. Backup existing data
    print("1. Backing up existing repository data...")
    cursor.execute("SELECT * FROM repositories")
    old_data = cursor.fetchall()
    cursor.execute("PRAGMA table_info(repositories)")
    old_columns = [row[1] for row in cursor.fetchall()]
    
    print(f"Found {len(old_data)} existing repositories")
    for i, row in enumerate(old_data):
        old_repo = dict(zip(old_columns, row))
        print(f"  {i+1}. {old_repo['repo']}")
    
    # 2. Drop the old table
    print("\n2. Dropping old repositories table...")
    cursor.execute("DROP TABLE repositories")
    
    # 3. Create new schema
    print("3. Creating new repositories table schema...")
    cursor.execute('''
        CREATE TABLE repositories (
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
    
    # 4. Define classification mapping for existing repos
    classification_mapping = {
        'Azure/azure-sdk-for-python': ('Azure SDK for Python', 'python', 'azure', 1),
        'Azure/azure-sdk-for-js': ('Azure SDK for JavaScript', 'nodejs', 'azure', 2),
        'microsoft/ApplicationInsights-node.js': ('Application Insights Node.js', 'nodejs', 'microsoft', 10),
        'microsoft/ApplicationInsights-js': ('Application Insights JavaScript', 'browser', 'microsoft', 11),
        'microsoft/applicationinsights-react-js': ('Application Insights React', 'react', 'microsoft', 12),
        'microsoft/applicationinsights-react-native': ('Application Insights React Native', 'react-native', 'microsoft', 13),
        'microsoft/applicationinsights-angularplugin-js': ('Application Insights Angular', 'angular', 'microsoft', 14),
        'microsoft/DynamicProto-JS': ('DynamicProto JavaScript', 'javascript', 'microsoft', 15),
        'microsoft/node-diagnostic-channel': ('Node Diagnostic Channel', 'nodejs', 'microsoft', 16),
        'microsoft/ApplicationInsights-node.js-native-metrics': ('Application Insights Native Metrics', 'nodejs', 'microsoft', 17),
        'open-telemetry/opentelemetry-js': ('OpenTelemetry JavaScript', 'nodejs', 'opentelemetry', 5),
        'open-telemetry/opentelemetry-js-contrib': ('OpenTelemetry JavaScript Contrib', 'nodejs', 'opentelemetry', 6),
        'open-telemetry/opentelemetry-python': ('OpenTelemetry Python', 'python', 'opentelemetry', 7),
        'open-telemetry/opentelemetry-python-contrib': ('OpenTelemetry Python Contrib', 'python', 'opentelemetry', 8),
    }
    
    # 5. Insert migrated data with metadata
    print("4. Migrating existing data with metadata...")
    migrated_count = 0
    
    for row in old_data:
        old_repo = dict(zip(old_columns, row))
        repo_name = old_repo['repo']
        
        if repo_name in classification_mapping:
            display_name, main_category, classification, priority = classification_mapping[repo_name]
            
            cursor.execute('''
                INSERT INTO repositories 
                (repo, display_name, main_category, classification, priority, is_active)
                VALUES (?, ?, ?, ?, ?, TRUE)
            ''', (repo_name, display_name, main_category, classification, priority))
            
            migrated_count += 1
            print(f"  ✓ Migrated {repo_name} -> {display_name} ({classification})")
        else:
            # Unknown repository - add with basic classification
            display_name = repo_name.split('/')[-1]  # Use repo name as display name
            cursor.execute('''
                INSERT INTO repositories 
                (repo, display_name, main_category, classification, priority, is_active)
                VALUES (?, ?, ?, ?, ?, TRUE)
            ''', (repo_name, display_name, 'other', 'other', 999))
            
            migrated_count += 1
            print(f"  ? Migrated {repo_name} -> {display_name} (unknown classification)")
    
    # 6. Add some additional Azure SDK repositories that might be missing
    print("\n5. Adding additional default repositories...")
    additional_repos = [
        ('Azure/azure-sdk-for-net', 'Azure SDK for .NET', 'dotnet', 'azure', 3),
        ('open-telemetry/opentelemetry-dotnet', 'OpenTelemetry .NET', 'dotnet', 'opentelemetry', 9),
        ('microsoft/ApplicationInsights-dotnet', 'Application Insights .NET', 'dotnet', 'microsoft', 18),
    ]
    
    for repo, display_name, main_category, classification, priority in additional_repos:
        cursor.execute('''
            INSERT OR IGNORE INTO repositories 
            (repo, display_name, main_category, classification, priority, is_active)
            VALUES (?, ?, ?, ?, ?, TRUE)
        ''', (repo, display_name, main_category, classification, priority))
        print(f"  + Added {repo} -> {display_name} ({classification})")
    
    # 7. Verify migration
    print("\n6. Verifying migration...")
    cursor.execute("SELECT COUNT(*) FROM repositories")
    total_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT classification, COUNT(*) FROM repositories GROUP BY classification ORDER BY classification")
    by_classification = cursor.fetchall()
    
    print(f"Migration complete!")
    print(f"  Total repositories: {total_count}")
    print(f"  By classification:")
    for classification, count in by_classification:
        print(f"    {classification}: {count}")
    
    # 8. Show sample of new data
    print("\n7. Sample of migrated data:")
    cursor.execute('''
        SELECT repo, display_name, main_category, classification, priority 
        FROM repositories 
        ORDER BY 
            CASE classification 
                WHEN 'azure' THEN 1 
                WHEN 'opentelemetry' THEN 2 
                WHEN 'microsoft' THEN 3 
                ELSE 4 
            END,
            priority ASC
        LIMIT 10
    ''')
    
    for row in cursor.fetchall():
        repo, display_name, main_category, classification, priority = row
        print(f"  {priority:2d}. {repo} -> {display_name} ({main_category}/{classification})")
    
    conn.commit()
    conn.close()
    print("\nMigration completed successfully!")

if __name__ == "__main__":
    migrate_repositories_table()
