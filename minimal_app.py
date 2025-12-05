"""
Minimal GitHub Issues Dashboard with Basic Sync API
Combines dashboard frontend with essential sync API endpoints.
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment configuration
IS_AZURE = bool(os.environ.get('WEBSITE_SITE_NAME'))
DATABASE_PATH = os.environ.get('DATABASE_PATH', '/tmp/github_issues.db' if IS_AZURE else 'data/github_issues.db')

# Initialize Flask application
app = Flask(__name__, 
           template_folder="templates",
           static_folder="static")
CORS(app)

def init_database():
    """Initialize database with basic schema"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Create basic repositories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repositories (
                repo TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                main_category TEXT NOT NULL,
                classification TEXT NOT NULL,
                priority INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create basic issues table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY,
                repo TEXT NOT NULL,
                number INTEGER NOT NULL,
                title TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                UNIQUE(repo, number)
            )
        ''')
        
        # Add sample repository if none exist
        cursor.execute("SELECT COUNT(*) FROM repositories")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT OR IGNORE INTO repositories 
                (repo, display_name, main_category, classification, priority) 
                VALUES (?, ?, ?, ?, ?)
            ''', ('Microsoft/ApplicationInsights-dotnet', 'Application Insights .NET', 'Azure SDK', 'Core Service', 1))
            
            # Add sample issues
            sample_issues = [
                (1, 'Sample Issue 1', 'open', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z'),
                (2, 'Sample Issue 2', 'closed', '2024-01-02T00:00:00Z', '2024-01-02T00:00:00Z'),
            ]
            
            for number, title, state, created, updated in sample_issues:
                cursor.execute('''
                    INSERT OR IGNORE INTO issues 
                    (repo, number, title, state, created_at, updated_at) 
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ('Microsoft/ApplicationInsights-dotnet', number, title, state, created, updated))
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {DATABASE_PATH}")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

# Routes
@app.route("/")
def index():
    """Serve the main dashboard"""
    return render_template("dashboard.html")

@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "GitHub Issues Dashboard"
    })

@app.route("/api/issues")
def get_issues():
    """Get all issues from database"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT i.repo, i.number, i.title, i.state, i.created_at, i.updated_at,
                   r.display_name, r.main_category
            FROM issues i
            LEFT JOIN repositories r ON i.repo = r.repo
            ORDER BY i.updated_at DESC
            LIMIT 100
        ''')
        
        issues = []
        for row in cursor.fetchall():
            issues.append({
                "repo": row[0],
                "number": row[1],
                "title": row[2],
                "state": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "display_name": row[6] or row[0],
                "category": row[7] or "Unknown"
            })
        
        conn.close()
        return jsonify({"issues": issues, "total": len(issues)})
        
    except Exception as e:
        logger.error(f"Error fetching issues: {e}")
        return jsonify({"error": str(e), "issues": [], "total": 0}), 500

@app.route("/api/repositories")
def get_repositories():
    """Get all repositories"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT repo, display_name, main_category, classification, 
                   priority, is_active, created_at
            FROM repositories
            ORDER BY priority, display_name
        ''')
        
        repos = []
        for row in cursor.fetchall():
            repos.append({
                "repo": row[0],
                "display_name": row[1],
                "main_category": row[2],
                "classification": row[3],
                "priority": row[4],
                "is_active": bool(row[5]),
                "created_at": row[6]
            })
        
        conn.close()
        return jsonify({"repositories": repos, "total": len(repos)})
        
    except Exception as e:
        logger.error(f"Error fetching repositories: {e}")
        return jsonify({"error": str(e), "repositories": [], "total": 0}), 500

@app.route("/api/stats")
def get_stats():
    """Get basic statistics"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Count issues by state
        cursor.execute("SELECT state, COUNT(*) FROM issues GROUP BY state")
        issue_stats = dict(cursor.fetchall())
        
        # Count repositories
        cursor.execute("SELECT COUNT(*) FROM repositories WHERE is_active = 1")
        active_repos = cursor.fetchone()[0]
        
        conn.close()
        return jsonify({
            "issues": issue_stats,
            "repositories": {"active": active_repos},
            "last_updated": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Initialize database on startup
    init_database()
    
    # Start the app
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting GitHub Issues Dashboard on port {port}")
    logger.info(f"Database: {DATABASE_PATH}")
    logger.info(f"Azure environment: {IS_AZURE}")
    
    app.run(host="0.0.0.0", port=port, debug=False)