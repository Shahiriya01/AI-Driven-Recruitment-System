"""
test_insert.py — simulate what /screen does to verify DB insert works.
"""
import sys
sys.path.insert(0, ".")
from db import init_db, get_db
from datetime import date

# Re-init DB (applies migration if needed)
init_db()

# Test insert
conn = get_db()
try:
    conn.execute(
        """INSERT INTO resumes
           (name, role_applied, match_score, date, status, ml_pred, ml_prob, resume_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("Test Candidate", "Software Engineer", 75, date.today().isoformat(),
         "Eligible", 1, 0.82, "uploads/test.pdf")
    )
    conn.commit()
    print("INSERT successful!")
except Exception as e:
    print("INSERT failed:", e)

# Verify
rows = conn.execute("SELECT * FROM resumes").fetchall()
print(f"Total records in resumes: {len(rows)}")
for r in rows:
    print(dict(r))
conn.close()
