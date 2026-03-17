import sqlite3

conn = sqlite3.connect("hr.db")
conn.row_factory = sqlite3.Row

# List tables
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

# Check resumes schema
cols = conn.execute("PRAGMA table_info(resumes)").fetchall()
print("Resumes columns:", [c[1] for c in cols])

# Check record count
count = conn.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
print("Record count in resumes:", count)

# Show first 3 records if any
if count > 0:
    rows = conn.execute("SELECT * FROM resumes LIMIT 3").fetchall()
    for r in rows:
        print(dict(r))

conn.close()
