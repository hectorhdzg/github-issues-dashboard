import sqlite3

conn = sqlite3.connect('github_issues.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('All tables in database:')
for table in tables:
    print(f'  {table[0]}')

print('\nRepositories table schema:')
cursor.execute('PRAGMA table_info(repositories)')
schema = cursor.fetchall()
for row in schema:
    nullable = 'NOT NULL' if row[3] else 'NULL'
    default = row[4] if row[4] is not None else 'None'
    print(f'  {row[1]} ({row[2]}) - {nullable} - Default: {default}')

print('\nSample repository data:')
cursor.execute('SELECT * FROM repositories LIMIT 5')
rows = cursor.fetchall()
columns = [row[1] for row in schema]
for row in rows:
    print(dict(zip(columns, row)))

conn.close()
