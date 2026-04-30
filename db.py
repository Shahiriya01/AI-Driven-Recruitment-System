# db.py
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = "hr.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Users table
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email    TEXT,
        fullname TEXT,
        company  TEXT,
        password TEXT
    )''')

    # Screening batches table — groups resumes uploaded together
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

    # Resumes table — full correct schema with user_id for tenant isolation
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
        resume_path  TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Migration: add missing columns for users upgrading from older DB
    existing = [row[1] for row in c.execute("PRAGMA table_info(resumes)").fetchall()]
    for col, typ in [
        ("role_applied", "TEXT"),
        ("match_score", "INTEGER"),
        ("experience", "REAL"),
        ("date", "TEXT"),
        ("resume_path", "TEXT"),
        ("user_id", "INTEGER"),
        # Bulk screening columns
        ("batch_id", "INTEGER"),
        ("review_status", "TEXT DEFAULT 'pending'"),
        ("skills_json", "TEXT"),
        ("matched_skills", "TEXT"),
        ("education", "TEXT"),
        ("email", "TEXT"),
        ("phone", "TEXT"),
        ("summary", "TEXT"),
        ("resume_text", "TEXT"),
    ]:
        if col not in existing:
            c.execute(f"ALTER TABLE resumes ADD COLUMN {col} {typ}")

    # If old match_percent column exists, copy its values into match_score
    if "match_percent" in existing:
        c.execute("UPDATE resumes SET match_score = match_percent WHERE match_score IS NULL")

    conn.commit()
    conn.close()

def create_user(username, email, fullname, company, password):
    conn = get_db()
    c = conn.cursor()
    hashed = generate_password_hash(password)
    try:
        c.execute(
            "INSERT INTO users (username, email, fullname, company, password) VALUES (?, ?, ?, ?, ?)",
            (username, email, fullname, company, hashed)
        )
        conn.commit()
        return True
    except Exception as e:
        print("Create user error:", e)
        return False
    finally:
        conn.close()

def check_user(username, password):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row:
        return check_password_hash(row["password"], password)
    return False

def get_user_id(username):
    """Return the integer user_id for a given username."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row["id"] if row else None