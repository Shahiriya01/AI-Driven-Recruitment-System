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

    # Resumes table — full correct schema
    c.execute('''
    CREATE TABLE IF NOT EXISTS resumes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT,
        role_applied TEXT,
        match_score  INTEGER,
        date         TEXT,
        status       TEXT,
        ml_pred      INTEGER,
        ml_prob      REAL,
        resume_path  TEXT
    )''')

    # Migration: add missing columns for users upgrading from older DB
    existing = [row[1] for row in c.execute("PRAGMA table_info(resumes)").fetchall()]
    for col, typ in [("role_applied", "TEXT"), ("match_score", "INTEGER"),
                     ("date", "TEXT"), ("resume_path", "TEXT")]:
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