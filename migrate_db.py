"""
migrate_db.py — One-shot migration to bring hr.db up to the current schema.
Safe to run multiple times (idempotent).
"""
import sqlite3

DB_PATH = "hr.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # ── Initialize schema using the single source of truth ───────────
    from db import init_db
    init_db()
    print("  [OK] Core tables initialized and columns updated via db.py")

    # ── Back-fill user_id for orphan records ─────────────────────────
    orphans = c.execute("SELECT COUNT(*) FROM resumes WHERE user_id IS NULL").fetchone()[0]
    if orphans > 0:
        # Assign orphan records to the first registered user (if any)
        first_user = c.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
        if first_user:
            uid = first_user[0]
            c.execute("UPDATE resumes SET user_id=? WHERE user_id IS NULL", (uid,))
            conn.commit()
            print(f"  -> Assigned {orphans} orphan record(s) to user_id={uid}")
        else:
            print(f"  WARNING: {orphans} orphan records exist but no users found to assign them to.")

    # ── Back-fill review_status for existing records ─────────────────
    c.execute("UPDATE resumes SET review_status='pending' WHERE review_status IS NULL")
    conn.commit()

    # ── Verify ───────────────────────────────────────────────────────
    final_cols = [row[1] for row in c.execute("PRAGMA table_info(resumes)").fetchall()]
    count = c.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
    batch_count = c.execute("SELECT COUNT(*) FROM screening_batches").fetchone()[0]
    print(f"\nFinal columns: {final_cols}")
    print(f"Total resume records: {count}")
    print(f"Total batch records: {batch_count}")
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()

