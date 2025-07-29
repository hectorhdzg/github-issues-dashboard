import sqlite3
import os

db_path = 'c:/Scripts/GitHub-Issues-Dashboard/github_issues.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print('Tables:', tables)
    
    if tables:
        cursor.execute("PRAGMA table_info(issues)")
        columns = cursor.fetchall()
        print('Columns:', columns)
        
        cursor.execute("SELECT COUNT(*) FROM issues")
        count = cursor.fetchall()
        print('Row count:', count)
    
    conn.close()
else:
    print('Database file does not exist')
