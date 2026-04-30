# app.py
import warnings
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, Response, stream_with_context)
import os
import re
import json
import time
import csv
import io
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
import fitz  # PyMuPDF
import docx
import joblib
import numpy as np

from db import init_db, create_user, check_user, get_db, get_user_id

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs("uploads", exist_ok=True)

app.secret_key = os.environ.get("SECRET_KEY", "12192f46fb10ac35c643fcef3fc543df8fafe3c0cadafce3b8470f8456b9b8a6")

init_db()

# Load ML model once at startup (graceful if model not yet trained)
MODEL_PATH = os.path.join("models", "model.pkl")
try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        rf_model = joblib.load(MODEL_PATH)
except Exception:
    rf_model = None

FEATURE_COLS = ["skill_match", "experience", "resume_length",
                "keyword_density", "num_skills", "education_level",
                "cert_count", "job_count"]

# Thread pool for concurrent resume processing
executor = ThreadPoolExecutor(max_workers=8)

# In-memory progress store: {batch_id: {total, processed, status, results, errors}}
batch_progress = {}
batch_progress_lock = threading.Lock()

# SQLite write lock (SQLite allows concurrent reads but serialized writes)
db_write_lock = threading.Lock()

# ----------------- Resume Utilities -----------------

def extract_text_from_pdf(path):
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text()
    return text

def extract_text_from_docx(path):
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

def extract_text_from_txt(path):
    """Read plain text file."""
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def extract_text_from_file(filepath):
    """Extract text from PDF, DOCX, or TXT file."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.pdf':
        return extract_text_from_pdf(filepath)
    elif ext in ('.docx', '.doc'):
        return extract_text_from_docx(filepath)
    elif ext == '.txt':
        return extract_text_from_txt(filepath)
    else:
        return ""

def extract_email(text):
    """Extract email address from resume text."""
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    return match.group(0) if match else None

def extract_phone(text):
    """Extract phone number from resume text."""
    match = re.search(r'[\+]?[(]?[0-9]{1,4}[)]?[-\s./0-9]{7,15}', text)
    return match.group(0).strip() if match else None

def get_education_label(level_int):
    """Convert education level integer to human label."""
    return {0: "Not Detected", 3: "Bachelor's", 4: "Master's", 5: "PhD"}.get(level_int, "Other")

def extract_name(text):
    lines = text.split("\n")
    for line in lines[:10]:
        if line.strip() and not any(x in line.lower() for x in ["@", "phone", "email", "address"]):
            return line.strip()
    return "Not Found"

def extract_experience_from_dates(text):
    """
    Calculate experience by summing work durations from date ranges in the text.
    Handles patterns like: Jan 2019 – Mar 2022, 2018-2021, 06/2017 - Present, etc.
    Returns total years as a float.
    """
    total_months = 0
    current_year  = datetime.now().year
    current_month = datetime.now().month

    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4,
        "june": 6, "july": 7, "august": 8, "september": 9,
        "october": 10, "november": 11, "december": 12,
    }

    # Pattern: "Month Year – Month Year" or "Month Year - Present"
    pattern_full = re.compile(
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"[\s,./]+(20\d{2}|19\d{2})"
        r"\s*[-–—to]+\s*"
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|present|current|now)"
        r"(?:[\s,./]+(20\d{2}|19\d{2}))?",
        re.IGNORECASE
    )

    for m in pattern_full.finditer(text):
        start_month_str = m.group(1).lower()[:3]
        start_year      = int(m.group(2))
        end_ref         = m.group(3).lower()[:3]
        end_year_str    = m.group(4)

        start_m = month_map.get(start_month_str, 1)

        if end_ref in ("pre", "cur", "now"):
            end_m = current_month
            end_y = current_year
        else:
            end_m = month_map.get(end_ref, 12)
            end_y = int(end_year_str) if end_year_str else start_year + 1

        months = (end_y - start_year) * 12 + (end_m - start_m)
        if 0 < months <= 600:   # sanity check: ≤ 50 years
            total_months += months

    # Pattern: "YYYY – YYYY" bare year ranges
    if total_months == 0:
        year_range = re.compile(r"\b(20\d{2}|19\d{2})\s*[-–—to]+\s*(20\d{2}|19\d{2}|present|current)\b", re.I)
        seen_ranges = set()
        for m in year_range.finditer(text):
            sy = int(m.group(1))
            ey_str = m.group(2).lower()
            ey = current_year if ey_str in ("present", "current") else int(ey_str)
            key = (sy, ey)
            if key not in seen_ranges and 0 < ey - sy <= 50:
                seen_ranges.add(key)
                total_months += (ey - sy) * 12

    return round(total_months / 12, 1) if total_months > 0 else 0.0


def extract_experience(text):
    """
    Multi-strategy experience extractor.
    1. Explicit "X years of experience" patterns
    2. Date-range accumulation from work history
    Returns float (e.g., 3.5).
    """
    # Strategy 1 — explicit year mentions
    explicit_patterns = [
        r"(\d+\.?\d*)\s*\+?\s*years?\s+of\s+(?:professional\s+)?experience",
        r"(\d+\.?\d*)\s*\+?\s*years?\s+(?:of\s+)?(?:work|working|industry|relevant)?\s*experience",
        r"experience\s*(?:of|:)?\s*(\d+\.?\d*)\s*\+?\s*years?",
        r"(\d+\.?\d*)\s*\+?\s*yrs?\s+(?:of\s+)?experience",
        r"over\s+(\d+\.?\d*)\s*years?\s+of",
        r"more\s+than\s+(\d+\.?\d*)\s*years?",
    ]
    for pat in explicit_patterns:
        matches = re.findall(pat, text, re.I)
        if matches:
            return max(float(m) for m in matches)

    # Strategy 2 — date range accumulation
    date_exp = extract_experience_from_dates(text)
    if date_exp > 0:
        return date_exp

    # Strategy 3 — loose fallback: bare "X years" mentions
    fallback = re.findall(r"(\d+)\s*(?:years?|yrs?)", text, re.I)
    if fallback:
        candidates = [int(x) for x in fallback if 0 < int(x) <= 50]
        if candidates:
            return float(max(candidates))

    return 0.0


def extract_skills(text):
    words = re.findall(r"[A-Za-z\+\#\.]{2,}", text)
    stopwords = {"and","the","with","for","from","this","that","are","is","in","of","to",
                 "at","by","or","an","on","as","if","it","be","do","he","she","we","us"}
    skills = list(set(w.lower() for w in words if w.lower() not in stopwords))
    return skills

def estimate_education_level(text):
    """Estimate education level: 0=none, 3=bachelor, 4=master, 5=phd"""
    t = text.lower()
    if "ph.d" in t or "phd" in t or "doctorate" in t:
        return 5
    if "master" in t or "m.sc" in t or "m.tech" in t or "mba" in t:
        return 4
    if "bachelor" in t or "b.sc" in t or "b.tech" in t or "b.e." in t or "degree" in t:
        return 3
    return 0

def estimate_cert_count(text):
    """Count rough number of certification keywords"""
    certs = re.findall(
        r"\b(certification|certified|certificate|CISSP|AWS|Azure|GCP|PMP|CPA|"
        r"Scrum|CompTIA|ITIL|CEH|CISA|CCNA|CCNP)\b",
        text, re.I
    )
    return min(len(certs), 20)  # cap at 20

def estimate_keyword_density(text, job_skills):
    """Ratio of job skill keywords to total words (proxy)"""
    words = text.lower().split()
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in [s.lower() for s in job_skills])
    return round(hits / len(words), 6)

def estimate_job_count(text):
    """Count number of job/company experience blocks"""
    matches = re.findall(
        r"\b(19|20)\d{2}\b",  # year mentions as proxy
        text
    )
    return min(max(len(matches) // 2, 1), 15)

def login_required(f):
    """Simple decorator for login protection."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ----------------- Routes -----------------

@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("home.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    msg = None
    if request.method == "POST":
        msg = "Message submitted successfully!"
    return render_template("contact.html", msg=msg)

# --- Authentication Routes ---

@app.route("/register", methods=["GET","POST"])
def register():
    msg = ""
    if request.method=="POST":
        fullname = request.form["fullname"]
        email    = request.form["email"]
        company  = request.form["company"]
        username = request.form["username"]
        password = request.form["password"]
        ok = create_user(username, email, fullname, company, password)
        if ok:
            return redirect(url_for("login"))
        else:
            msg = "Registration failed (username may exist)."
    return render_template("register.html", msg=msg)

@app.route("/login", methods=["GET","POST"])
def login():
    msg = ""
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        if check_user(username, password):
            session["user"] = username
            session["user_id"] = get_user_id(username)
            return redirect(url_for("dashboard"))
        else:
            msg = "Invalid credentials."
    return render_template("login.html", msg=msg)

@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("user_id", None)
    return redirect(url_for("home"))

# --- Dashboard & Features ---

PER_PAGE = 10  # rows per page

@app.route("/dashboard")
@login_required
def dashboard():
    uid = session.get("user_id")
    conn = get_db()

    # Full dataset for stat cards (unfiltered)
    all_records = conn.execute(
        "SELECT * FROM resumes WHERE user_id=? ORDER BY id DESC", (uid,)
    ).fetchall()
    total       = len(all_records)
    eligible    = sum(1 for r in all_records if r["status"] == "Eligible")
    not_elig    = total - eligible
    ml_selected = sum(1 for r in all_records if r["ml_pred"] == 1)
    stats = {
        "total":        total,
        "eligible":     eligible,
        "not_eligible": not_elig,
        "ml_selected":  ml_selected,
    }

    # --- Search / Filter ---
    q      = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    clauses = ["user_id=?"]
    params  = [uid]
    if q:
        clauses.append("(name LIKE ? OR role_applied LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if status in ("Eligible", "Not Eligible"):
        clauses.append("status=?")
        params.append(status)

    where = " AND ".join(clauses)
    filtered = conn.execute(
        f"SELECT * FROM resumes WHERE {where} ORDER BY id DESC", params
    ).fetchall()

    # --- Pagination ---
    page       = max(1, request.args.get("page", 1, type=int))
    total_filt = len(filtered)
    total_pages = max(1, -(-total_filt // PER_PAGE))   # ceil division
    page        = min(page, total_pages)
    start       = (page - 1) * PER_PAGE
    records     = filtered[start:start + PER_PAGE]

    conn.close()
    return render_template("dashboard.html",
                           user=session["user"],
                           records=records,
                           stats=stats,
                           q=q, status=status,
                           page=page, total_pages=total_pages,
                           total_filtered=total_filt)

@app.route("/performance")
@login_required
def performance():
    uid = session.get("user_id")
    conn = get_db()

    # Full dataset for stat widgets
    all_rows = conn.execute(
        "SELECT * FROM resumes WHERE user_id=? ORDER BY match_score DESC", (uid,)
    ).fetchall()
    total = len(all_rows)
    avg_score    = round(sum(r["match_score"] or 0 for r in all_rows) / total, 1) if total else 0
    eligible_pct = round((sum(1 for r in all_rows if r["status"] == "Eligible") / total) * 100, 1) if total else 0

    # --- Search / Filter ---
    q      = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    clauses = ["user_id=?"]
    params  = [uid]
    if q:
        clauses.append("(name LIKE ? OR role_applied LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if status in ("Eligible", "Not Eligible"):
        clauses.append("status=?")
        params.append(status)

    where = " AND ".join(clauses)
    filtered = conn.execute(
        f"SELECT * FROM resumes WHERE {where} ORDER BY match_score DESC", params
    ).fetchall()

    # --- Pagination ---
    page       = max(1, request.args.get("page", 1, type=int))
    total_filt = len(filtered)
    total_pages = max(1, -(-total_filt // PER_PAGE))
    page        = min(page, total_pages)
    start       = (page - 1) * PER_PAGE
    candidates  = filtered[start:start + PER_PAGE]

    conn.close()
    return render_template("performance.html",
                           candidates=candidates,
                           total=total,
                           avg_score=avg_score,
                           eligible_pct=eligible_pct,
                           q=q, status=status,
                           page=page, total_pages=total_pages,
                           total_filtered=total_filt)


@app.route("/screen", methods=["GET", "POST"])
@login_required
def screen():
    result = None
    if request.method == "POST":
        job_skills = request.form.get("skills", "").lower().split(",")
        job_skills = [s.strip() for s in job_skills if s.strip()]
        role = request.form.get("role", "").strip()
        try:
            min_exp = float(request.form.get("experience", 0))
        except ValueError:
            min_exp = 0

        file = request.files.get("resume")
        if not file:
            return render_template("screening.html", result=None, error="No file uploaded.")
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(filepath)

        text = extract_text_from_file(filepath)
        if not text or len(text.strip()) < 10:
            return render_template("screening.html", result=None,
                                   error="Could not extract text from the uploaded file.")

        name       = extract_name(text)
        experience = extract_experience(text)         # improved multi-strategy
        skills     = extract_skills(text)

        matched      = [s for s in job_skills if s in skills]
        match_percent = int((len(matched) / len(job_skills)) * 100) if job_skills else 0

        # Rule-based eligibility
        status = "Eligible" if experience >= min_exp else "Not Eligible"

        # --- ML Prediction ---
        ml_pred = None
        ml_prob = None
        if rf_model is not None:
            try:
                skill_match     = round(len(matched) / len(job_skills), 6) if job_skills else 0.0
                resume_length   = len(text.split())
                keyword_density = estimate_keyword_density(text, job_skills)
                num_skills      = len(skills)
                education_level = estimate_education_level(text)
                cert_count      = estimate_cert_count(text)
                job_count       = estimate_job_count(text)

                features = np.array([[skill_match, experience, resume_length,
                                      keyword_density, num_skills, education_level,
                                      cert_count, job_count]])
                ml_pred = int(rf_model.predict(features)[0])
                ml_prob = round(float(rf_model.predict_proba(features)[0][1]), 4)
            except Exception as e:
                print("ML prediction error:", e)
                # Fallback: rule-based if ML fails
                ml_pred = 1 if (match_percent >= 60 and experience >= min_exp) else 0
                ml_prob = round(match_percent / 100, 4)

        result = {
            "name":       name,
            "experience": experience,
            "skills":     skills[:15],
            "matched":    matched,
            "match":      match_percent,
            "status":     status,
            "ml_pred":    ml_pred,
            "ml_prob":    ml_prob,
        }

        # --- Insert into DB (with user_id for isolation) ---
        uid = session.get("user_id")
        try:
            conn = get_db()
            conn.execute(
                """INSERT INTO resumes
                   (user_id, name, role_applied, match_score, experience, date, status, ml_pred, ml_prob, resume_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    uid,
                    name,
                    role if role else "Not Specified",
                    match_percent,
                    experience,
                    date.today().isoformat(),
                    status,
                    ml_pred,
                    ml_prob,
                    filepath
                )
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print("DB insert error:", e)

    return render_template("screening.html", result=result)


# --- Delete APIs (owner-only) ---

@app.route("/candidate/delete/<int:candidate_id>", methods=["POST"])
@login_required
def delete_candidate(candidate_id):
    """Permanently delete a single candidate record owned by the logged-in user."""
    uid = session.get("user_id")
    conn = get_db()
    # Verify ownership before deletion
    row = conn.execute(
        "SELECT id FROM resumes WHERE id=? AND user_id=?", (candidate_id, uid)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Not found or unauthorized"}), 403
    conn.execute("DELETE FROM resumes WHERE id=? AND user_id=?", (candidate_id, uid))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/screening/delete-all", methods=["POST"])
@login_required
def delete_all_screenings():
    """Permanently delete ALL screening records for the logged-in user."""
    uid = session.get("user_id")
    conn = get_db()
    conn.execute("DELETE FROM resumes WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ==================== BULK SCREENING ====================

def process_single_resume(filepath, filename, job_skills, min_exp, batch_id, resume_id, uid):
    """Process one resume in a thread pool worker."""
    try:
        text = extract_text_from_file(filepath)
        if not text or len(text.strip()) < 10:
            raise ValueError("Could not extract text from file")

        name            = extract_name(text)
        experience      = extract_experience(text)
        skills          = extract_skills(text)
        email_addr      = extract_email(text)
        phone_num       = extract_phone(text)
        education_level = estimate_education_level(text)
        education_label = get_education_label(education_level)
        cert_count      = estimate_cert_count(text)
        job_count       = estimate_job_count(text)

        matched      = [s for s in job_skills if s in skills]
        match_percent = int((len(matched) / len(job_skills)) * 100) if job_skills else 0

        # Rule-based eligibility
        status = "Eligible" if experience >= min_exp else "Not Eligible"

        # ML Prediction
        ml_pred = None
        ml_prob = None
        if rf_model is not None:
            try:
                skill_match     = round(len(matched) / len(job_skills), 6) if job_skills else 0.0
                resume_length   = len(text.split())
                keyword_density = estimate_keyword_density(text, job_skills)
                num_skills      = len(skills)

                features = np.array([[skill_match, experience, resume_length,
                                      keyword_density, num_skills, education_level,
                                      cert_count, job_count]])
                ml_pred = int(rf_model.predict(features)[0])
                ml_prob = round(float(rf_model.predict_proba(features)[0][1]), 4)
            except Exception as e:
                print(f"ML prediction error for {filename}:", e)
                ml_pred = 1 if (match_percent >= 60 and experience >= min_exp) else 0
                ml_prob = round(match_percent / 100, 4)

        summary = text[:300].replace('\n', ' ').strip()

        # Update DB with results (thread-safe write)
        with db_write_lock:
            conn = get_db()
            conn.execute(
                """UPDATE resumes SET
                    name=?, match_score=?, experience=?, status=?,
                    ml_pred=?, ml_prob=?, skills_json=?, matched_skills=?,
                    education=?, email=?, phone=?, summary=?, resume_text=?
                WHERE id=?""",
                (
                    name, match_percent, experience, status,
                    ml_pred, ml_prob,
                    json.dumps(skills[:30]),
                    json.dumps(matched),
                    education_label, email_addr, phone_num,
                    summary, text[:5000],
                    resume_id
                )
            )
            conn.commit()
            conn.close()

        result = {
            "id": resume_id, "name": name, "filename": filename,
            "match_score": match_percent, "experience": experience,
            "status": status, "ml_pred": ml_pred, "ml_prob": ml_prob,
            "education": education_label, "email": email_addr,
            "success": True
        }

    except Exception as e:
        print(f"Error processing {filename}: {e}")
        result = {
            "id": resume_id, "filename": filename,
            "success": False, "error": str(e)
        }

    # Update progress
    with batch_progress_lock:
        prog = batch_progress.get(batch_id, {})
        prog["processed"] = prog.get("processed", 0) + 1
        if result["success"]:
            prog.setdefault("results", []).append(result)
        else:
            prog.setdefault("errors", []).append(result)

        # Check if batch is complete
        if prog["processed"] >= prog.get("total", 0):
            prog["status"] = "completed"
            with db_write_lock:
                conn = get_db()
                conn.execute(
                    """UPDATE screening_batches SET
                        processed=?, status='completed', completed_at=?
                    WHERE id=?""",
                    (prog["processed"], datetime.now().isoformat(), batch_id)
                )
                conn.commit()
                conn.close()
        else:
            with db_write_lock:
                conn = get_db()
                conn.execute(
                    "UPDATE screening_batches SET processed=? WHERE id=?",
                    (prog["processed"], batch_id)
                )
                conn.commit()
                conn.close()

        batch_progress[batch_id] = prog

    return result


@app.route("/bulk-screen")
@login_required
def bulk_screen():
    """Render the bulk screening page."""
    return render_template("bulk_screening.html")


@app.route("/api/bulk-upload", methods=["POST"])
@login_required
def bulk_upload():
    """Accept multi-file upload, create batch, start processing."""
    uid = session.get("user_id")

    role       = request.form.get("role", "").strip()
    skills_raw = request.form.get("skills", "").lower()
    job_skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
    try:
        min_exp = float(request.form.get("experience", 0))
    except ValueError:
        min_exp = 0
    custom_criteria = request.form.get("custom_criteria", "")
    batch_name = request.form.get("batch_name", f"{role} Batch")

    files = request.files.getlist("resumes")
    if not files or len(files) == 0:
        return jsonify({"success": False, "error": "No files uploaded"}), 400
    if len(files) > 100:
        return jsonify({"success": False, "error": "Maximum 100 files allowed"}), 400

    # Create batch record
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO screening_batches
           (user_id, batch_name, role, required_skills, min_experience,
            custom_criteria, total_files, processed, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'processing', ?)""",
        (uid, batch_name, role, ",".join(job_skills), min_exp,
         custom_criteria, len(files), datetime.now().isoformat())
    )
    batch_id = cursor.lastrowid
    conn.commit()

    # Create batch upload directory
    batch_dir = os.path.join(app.config["UPLOAD_FOLDER"], f"batch_{batch_id}")
    os.makedirs(batch_dir, exist_ok=True)

    # Initialize progress tracking
    with batch_progress_lock:
        batch_progress[batch_id] = {
            "total": len(files),
            "processed": 0,
            "status": "processing",
            "results": [],
            "errors": []
        }

    # Save files and create placeholder DB records, then submit to thread pool
    for f in files:
        if not f.filename:
            continue

        # Validate file extension
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ('.pdf', '.docx', '.doc', '.txt'):
            with batch_progress_lock:
                batch_progress[batch_id]["processed"] += 1
                batch_progress[batch_id]["errors"].append({
                    "filename": f.filename, "success": False,
                    "error": f"Unsupported file type: {ext}"
                })
            continue

        filepath = os.path.join(batch_dir, f.filename)
        f.save(filepath)

        # Insert placeholder record
        cursor = conn.execute(
            """INSERT INTO resumes
               (user_id, batch_id, name, role_applied, match_score, experience,
                date, status, review_status, resume_path)
               VALUES (?, ?, ?, ?, 0, 0, ?, 'Pending', 'pending', ?)""",
            (uid, batch_id, f.filename, role if role else "Not Specified",
             date.today().isoformat(), filepath)
        )
        resume_id = cursor.lastrowid
        conn.commit()

        # Submit to thread pool
        executor.submit(
            process_single_resume,
            filepath, f.filename, job_skills, min_exp, batch_id, resume_id, uid
        )

    conn.close()
    return jsonify({"success": True, "batch_id": batch_id, "total": len(files)})


@app.route("/api/batch/<int:batch_id>/progress")
@login_required
def batch_progress_sse(batch_id):
    """Server-Sent Events stream for real-time progress."""
    uid = session.get("user_id")

    # Verify batch ownership
    conn = get_db()
    batch = conn.execute(
        "SELECT * FROM screening_batches WHERE id=? AND user_id=?",
        (batch_id, uid)
    ).fetchone()
    conn.close()
    if not batch:
        return jsonify({"error": "Not found"}), 404

    def generate():
        while True:
            with batch_progress_lock:
                prog = batch_progress.get(batch_id, {
                    "total": batch["total_files"],
                    "processed": batch["processed"],
                    "status": batch["status"],
                    "results": [],
                    "errors": []
                })
            data = {
                "total": prog.get("total", 0),
                "processed": prog.get("processed", 0),
                "status": prog.get("status", "unknown"),
                "error_count": len(prog.get("errors", [])),
                "success_count": len(prog.get("results", []))
            }
            yield f"data: {json.dumps(data)}\n\n"
            if prog.get("status") == "completed":
                break
            time.sleep(0.5)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.route("/api/batch/<int:batch_id>/results")
@login_required
def batch_results_api(batch_id):
    """Return batch results as JSON with filtering and sorting."""
    uid = session.get("user_id")
    conn = get_db()

    # Verify batch ownership
    batch = conn.execute(
        "SELECT * FROM screening_batches WHERE id=? AND user_id=?",
        (batch_id, uid)
    ).fetchone()
    if not batch:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    # Build query with filters
    clauses = ["user_id=?", "batch_id=?"]
    params = [uid, batch_id]

    q = request.args.get("q", "").strip()
    if q:
        clauses.append("(name LIKE ? OR email LIKE ? OR skills_json LIKE ?)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]

    status_filter = request.args.get("status", "").strip()
    if status_filter in ("Eligible", "Not Eligible"):
        clauses.append("status=?")
        params.append(status_filter)

    review_filter = request.args.get("review", "").strip()
    if review_filter in ("pending", "reviewed", "flagged", "rejected"):
        clauses.append("review_status=?")
        params.append(review_filter)

    where = " AND ".join(clauses)

    # Sorting
    sort = request.args.get("sort", "match_desc")
    sort_map = {
        "match_desc":  "match_score DESC",
        "match_asc":   "match_score ASC",
        "exp_desc":    "experience DESC",
        "exp_asc":     "experience ASC",
        "name_asc":    "name ASC",
        "name_desc":   "name DESC",
        "ml_desc":     "ml_prob DESC",
    }
    order = sort_map.get(sort, "match_score DESC")

    records = conn.execute(
        f"SELECT * FROM resumes WHERE {where} ORDER BY {order}", params
    ).fetchall()

    # Stats
    all_in_batch = conn.execute(
        "SELECT * FROM resumes WHERE user_id=? AND batch_id=?",
        (uid, batch_id)
    ).fetchall()

    stats = {
        "total":     len(all_in_batch),
        "eligible":  sum(1 for r in all_in_batch if r["status"] == "Eligible"),
        "not_eligible": sum(1 for r in all_in_batch if r["status"] == "Not Eligible"),
        "flagged":   sum(1 for r in all_in_batch if r["review_status"] == "flagged"),
        "reviewed":  sum(1 for r in all_in_batch if r["review_status"] == "reviewed"),
        "rejected":  sum(1 for r in all_in_batch if r["review_status"] == "rejected"),
        "pending":   sum(1 for r in all_in_batch if r["review_status"] == "pending"),
        "avg_match": round(sum(r["match_score"] or 0 for r in all_in_batch) / len(all_in_batch), 1) if all_in_batch else 0,
        "ml_selected": sum(1 for r in all_in_batch if r["ml_pred"] == 1),
    }

    candidates = []
    for r in records:
        candidates.append({
            "id":            r["id"],
            "name":          r["name"],
            "email":         r["email"],
            "phone":         r["phone"],
            "role_applied":  r["role_applied"],
            "match_score":   r["match_score"] or 0,
            "experience":    r["experience"] or 0,
            "education":     r["education"],
            "status":        r["status"],
            "ml_pred":       r["ml_pred"],
            "ml_prob":       r["ml_prob"],
            "review_status": r["review_status"] or "pending",
            "skills":        json.loads(r["skills_json"]) if r["skills_json"] else [],
            "matched_skills": json.loads(r["matched_skills"]) if r["matched_skills"] else [],
            "summary":       r["summary"],
            "date":          r["date"],
        })

    conn.close()
    return jsonify({
        "success": True,
        "batch": {
            "id": batch["id"],
            "name": batch["batch_name"],
            "role": batch["role"],
            "status": batch["status"],
            "total_files": batch["total_files"],
            "created_at": batch["created_at"],
        },
        "stats": stats,
        "candidates": candidates,
        "total_filtered": len(candidates),
    })


@app.route("/api/batch/<int:batch_id>/action", methods=["POST"])
@login_required
def batch_action(batch_id):
    """Apply batch actions: mark reviewed, flag, reject."""
    uid = session.get("user_id")
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    candidate_ids = data.get("candidate_ids", [])
    action = data.get("action", "")

    if action not in ("reviewed", "flagged", "rejected", "pending"):
        return jsonify({"success": False, "error": "Invalid action"}), 400
    if not candidate_ids:
        return jsonify({"success": False, "error": "No candidates selected"}), 400

    conn = get_db()
    # Verify all candidates belong to this user and batch
    placeholders = ",".join("?" for _ in candidate_ids)
    conn.execute(
        f"""UPDATE resumes SET review_status=?
            WHERE id IN ({placeholders}) AND user_id=? AND batch_id=?""",
        [action] + candidate_ids + [uid, batch_id]
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "updated": len(candidate_ids)})


@app.route("/api/batch/<int:batch_id>/export")
@login_required
def batch_export(batch_id):
    """Export batch results as CSV or JSON."""
    uid = session.get("user_id")
    fmt = request.args.get("format", "csv")

    conn = get_db()
    # Verify batch ownership
    batch = conn.execute(
        "SELECT * FROM screening_batches WHERE id=? AND user_id=?",
        (batch_id, uid)
    ).fetchone()
    if not batch:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    # Filter parameters
    review_filter = request.args.get("review", "").strip()
    status_filter = request.args.get("status", "").strip()

    clauses = ["user_id=?", "batch_id=?"]
    params = [uid, batch_id]
    if status_filter in ("Eligible", "Not Eligible"):
        clauses.append("status=?")
        params.append(status_filter)
    if review_filter in ("pending", "reviewed", "flagged", "rejected"):
        clauses.append("review_status=?")
        params.append(review_filter)

    where = " AND ".join(clauses)
    records = conn.execute(
        f"SELECT * FROM resumes WHERE {where} ORDER BY match_score DESC", params
    ).fetchall()
    conn.close()

    if fmt == "json":
        export_data = []
        for r in records:
            export_data.append({
                "name":          r["name"],
                "email":         r["email"],
                "phone":         r["phone"],
                "role_applied":  r["role_applied"],
                "match_score":   r["match_score"],
                "experience":    r["experience"],
                "education":     r["education"],
                "status":        r["status"],
                "review_status": r["review_status"],
                "ml_prediction": "Selected" if r["ml_pred"] == 1 else "Not Selected",
                "ml_confidence": f"{(r['ml_prob'] or 0) * 100:.1f}%",
                "skills":        json.loads(r["skills_json"]) if r["skills_json"] else [],
                "matched_skills": json.loads(r["matched_skills"]) if r["matched_skills"] else [],
            })
        return Response(
            json.dumps(export_data, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}_results.json"}
        )
    else:
        # CSV export
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Name", "Email", "Phone", "Role Applied", "Match Score (%)",
            "Experience (years)", "Education", "Status", "Review Status",
            "ML Prediction", "ML Confidence", "Matched Skills"
        ])
        for r in records:
            matched = json.loads(r["matched_skills"]) if r["matched_skills"] else []
            writer.writerow([
                r["name"], r["email"], r["phone"], r["role_applied"],
                r["match_score"], r["experience"], r["education"],
                r["status"], r["review_status"],
                "Selected" if r["ml_pred"] == 1 else "Not Selected",
                f"{(r['ml_prob'] or 0) * 100:.1f}%",
                ", ".join(matched)
            ])
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}_results.csv"}
        )


@app.route("/api/candidate/<int:candidate_id>/detail")
@login_required
def candidate_detail(candidate_id):
    """Return full candidate detail as JSON for modal."""
    uid = session.get("user_id")
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM resumes WHERE id=? AND user_id=?",
        (candidate_id, uid)
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404

    return jsonify({
        "success": True,
        "candidate": {
            "id":            row["id"],
            "name":          row["name"],
            "email":         row["email"],
            "phone":         row["phone"],
            "role_applied":  row["role_applied"],
            "match_score":   row["match_score"] or 0,
            "experience":    row["experience"] or 0,
            "education":     row["education"],
            "status":        row["status"],
            "ml_pred":       row["ml_pred"],
            "ml_prob":       row["ml_prob"],
            "review_status": row["review_status"] or "pending",
            "skills":        json.loads(row["skills_json"]) if row["skills_json"] else [],
            "matched_skills": json.loads(row["matched_skills"]) if row["matched_skills"] else [],
            "summary":       row["summary"],
            "resume_text":   row["resume_text"],
            "date":          row["date"],
            "resume_path":   row["resume_path"],
        }
    })


@app.route("/api/batch/<int:batch_id>/compare", methods=["POST"])
@login_required
def compare_candidates(batch_id):
    """Return side-by-side comparison data for selected candidates."""
    uid = session.get("user_id")
    data = request.get_json()
    candidate_ids = data.get("candidate_ids", [])

    if len(candidate_ids) < 2 or len(candidate_ids) > 4:
        return jsonify({"success": False, "error": "Select 2-4 candidates"}), 400

    conn = get_db()
    placeholders = ",".join("?" for _ in candidate_ids)
    rows = conn.execute(
        f"""SELECT * FROM resumes
            WHERE id IN ({placeholders}) AND user_id=? AND batch_id=?""",
        candidate_ids + [uid, batch_id]
    ).fetchall()
    conn.close()

    candidates = []
    for r in rows:
        candidates.append({
            "id":            r["id"],
            "name":          r["name"],
            "email":         r["email"],
            "phone":         r["phone"],
            "match_score":   r["match_score"] or 0,
            "experience":    r["experience"] or 0,
            "education":     r["education"],
            "status":        r["status"],
            "ml_pred":       r["ml_pred"],
            "ml_prob":       r["ml_prob"],
            "skills":        json.loads(r["skills_json"]) if r["skills_json"] else [],
            "matched_skills": json.loads(r["matched_skills"]) if r["matched_skills"] else [],
        })

    return jsonify({"success": True, "candidates": candidates})


@app.route("/batch/<int:batch_id>")
@login_required
def batch_results_page(batch_id):
    """Render the batch results page."""
    uid = session.get("user_id")
    conn = get_db()
    batch = conn.execute(
        "SELECT * FROM screening_batches WHERE id=? AND user_id=?",
        (batch_id, uid)
    ).fetchone()
    conn.close()
    if not batch:
        return redirect(url_for("bulk_screen"))
    return render_template("batch_results.html", batch_id=batch_id, batch=batch)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)