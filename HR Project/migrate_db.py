"""
migrate_db.py — Run once to bring hr.db up to the new resumes schema.
Adds missing columns if they don't already exist.
"""
import sqlite3

conn = sqlite3.connect("hr.db")
c = conn.cursor()

existing = [row[1] for row in c.execute("PRAGMA table_info(resumes)").fetchall()]
print("Existing columns:", existing)

migrations = [
    ("role_applied", "TEXT"),
    ("match_score",  "INTEGER"),
    ("date",         "TEXT"),
    ("resume_path",  "TEXT"),
]

for col, typ in migrations:
    if col not in existing:
        c.execute(f"ALTER TABLE resumes ADD COLUMN {col} {typ}")
        print(f"  Added column: {col}")
    else:
        print(f"  Column already exists: {col}")

# If the old column was named match_percent, copy its data into match_score
if "match_percent" in existing and "match_score" in [row[1] for row in c.execute("PRAGMA table_info(resumes)").fetchall()]:
    c.execute("UPDATE resumes SET match_score = match_percent WHERE match_score IS NULL")
    print("  Copied match_percent -> match_score for existing rows")

conn.commit()
conn.close()

# Verify
conn2 = sqlite3.connect("hr.db")
final_cols = [row[1] for row in conn2.execute("PRAGMA table_info(resumes)").fetchall()]
print("Final columns:", final_cols)
conn2.close()
print("Migration complete.")
