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

    # ── Create users table if missing ────────────────────────────────
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email    TEXT,
        fullname TEXT,
        company  TEXT,
        password TEXT
    )''')

    # ── Create screening_batches table if missing ────────────────────
    c.execute('''
    CREATE TABLE IF NOT EXISTS screening_batches (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER NOT NULL,
        batch_name      TEXT,
        role            TEXT,
        required_skills TEXT,
        min_experience  REAL DEFAULT 0,
        custom_criteria TEXT,
        total_files     INTEGER DEFAULT 0,
        processed       INTEGER DEFAULT 0,
        status          TEXT DEFAULT 'processing',
        created_at      TEXT,
        completed_at    TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # ── Create base resumes table if missing ─────────────────────────
    c.execute('''
    CREATE TABLE IF NOT EXISTS resumes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER,
        name         TEXT,
        role_applied TEXT,
        match_score  INTEGER,
        experience   REAL,
        date         TEXT,
        status       TEXT,
        ml_pred      INTEGER,
        ml_prob      REAL,
        resume_path  TEXT
    )''')
    print("  [OK] Core tables initialized")
    print("  [OK] screening_batches table OK")

    existing = [row[1] for row in c.execute("PRAGMA table_info(resumes)").fetchall()]
    print("Current columns:", existing)

    # ── Add missing columns ──────────────────────────────────────────
    additions = [
        ("user_id",        "INTEGER"),
        ("experience",     "REAL"),
        ("role_applied",   "TEXT"),
        ("match_score",    "INTEGER"),
        ("date",           "TEXT"),
        ("resume_path",    "TEXT"),
        # Bulk screening columns
        ("batch_id",       "INTEGER"),
        ("review_status",  "TEXT DEFAULT 'pending'"),
        ("skills_json",    "TEXT"),
        ("matched_skills", "TEXT"),
        ("education",      "TEXT"),
        ("email",          "TEXT"),
        ("phone",          "TEXT"),
        ("summary",        "TEXT"),
        ("resume_text",    "TEXT"),
    ]
    for col, typ in additions:
        if col not in existing:
            c.execute(f"ALTER TABLE resumes ADD COLUMN {col} {typ}")
            print(f"  + Added column: {col} ({typ})")

    # Copy legacy match_percent → match_score if the old column exists
    if "match_percent" in existing:
        c.execute("UPDATE resumes SET match_score = match_percent WHERE match_score IS NULL")
        print("  -> Copied match_percent to match_score for legacy rows")

    conn.commit()

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

