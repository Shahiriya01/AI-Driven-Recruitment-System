# app.py
from flask import Flask, render_template, request, redirect, url_for, session
import os
import re
from datetime import date
import fitz  # PyMuPDF
import docx
import joblib
import numpy as np

from db import init_db, create_user, check_user, get_db

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs("uploads", exist_ok=True)

app.secret_key = "12192f46fb10ac35c643fcef3fc543df8fafe3c0cadafce3b8470f8456b9b8a6"

init_db()

# Load ML model once at startup (graceful if model not yet trained)
MODEL_PATH = os.path.join("models", "model.pkl")
try:
    rf_model = joblib.load(MODEL_PATH)
except Exception:
    rf_model = None

FEATURE_COLS = ["skill_match", "experience", "resume_length",
                "keyword_density", "num_skills", "education_level",
                "cert_count", "job_count"]

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

def extract_name(text):
    lines = text.split("\n")
    for line in lines[:10]:
        if line.strip() and not any(x in line.lower() for x in ["@", "phone", "email", "address"]):
            return line.strip()
    return "Not Found"

def extract_experience(text):
    match = re.findall(r"(\d+)\s*(years|year|yrs)", text, re.I)
    if match:
        return max(int(m[0]) for m in match)
    return 0

def extract_skills(text):
    words = re.findall(r"[A-Za-z\+\#\.]{2,}", text)
    stopwords = {"and","the","with","for","from","this","that","are","is","in","of","to"}
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
        email = request.form["email"]
        company = request.form["company"]
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
            return redirect(url_for("dashboard"))
        else:
            msg = "Invalid credentials."
    return render_template("login.html", msg=msg)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

# --- Dashboard & Features ---

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    records = conn.execute("SELECT * FROM resumes ORDER BY id DESC").fetchall()
    total     = len(records)
    eligible  = sum(1 for r in records if r["status"] == "Eligible")
    not_elig  = total - eligible
    ml_selected = sum(1 for r in records if r["ml_pred"] == 1)
    conn.close()
    stats = {
        "total":       total,
        "eligible":    eligible,
        "not_eligible": not_elig,
        "ml_selected": ml_selected,
    }
    return render_template("dashboard.html", user=session["user"], records=records, stats=stats)

@app.route("/performance")
def performance():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    candidates = conn.execute("SELECT * FROM resumes ORDER BY match_score DESC").fetchall()
    total = len(candidates)
    avg_score = round(sum(r["match_score"] for r in candidates) / total, 1) if total else 0
    eligible_pct = round((sum(1 for r in candidates if r["status"] == "Eligible") / total) * 100, 1) if total else 0
    conn.close()
    return render_template("performance.html",
                           candidates=candidates,
                           total=total,
                           avg_score=avg_score,
                           eligible_pct=eligible_pct)


@app.route("/screen", methods=["GET", "POST"])
def screen():
    if "user" not in session:
        return redirect(url_for("login"))

    result = None
    if request.method == "POST":
        job_skills = request.form.get("skills", "").lower().split(",")
        job_skills = [s.strip() for s in job_skills if s.strip()]
        role = request.form.get("role", "").strip()
        try:
            min_exp = int(request.form.get("experience", 0))
        except ValueError:
            min_exp = 0

        file = request.files.get("resume")
        if not file:
            return render_template("screening.html", result=None, error="No file uploaded.")
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(filepath)

        if file.filename.lower().endswith(".pdf"):
            text = extract_text_from_pdf(filepath)
        else:
            text = extract_text_from_docx(filepath)

        name       = extract_name(text)
        experience = extract_experience(text)
        skills     = extract_skills(text)

        matched = [s for s in job_skills if s in skills]
        match_percent = int((len(matched) / len(job_skills)) * 100) if job_skills else 0
        status = "Eligible" if experience >= min_exp else "Not Eligible"

        # --- ML Prediction ---
        ml_pred = None
        ml_prob = None
        if rf_model is not None:
            try:
                skill_match      = round(len(matched) / len(job_skills), 6) if job_skills else 0.0
                resume_length    = len(text.split())
                keyword_density  = estimate_keyword_density(text, job_skills)
                num_skills       = len(skills)
                education_level  = estimate_education_level(text)
                cert_count       = estimate_cert_count(text)
                job_count        = estimate_job_count(text)

                features = np.array([[skill_match, experience, resume_length,
                                      keyword_density, num_skills, education_level,
                                      cert_count, job_count]])
                ml_pred = int(rf_model.predict(features)[0])
                ml_prob = round(float(rf_model.predict_proba(features)[0][1]), 4)
            except Exception as e:
                print("ML prediction error:", e)

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

        # --- Insert into DB ---
        try:
            conn = get_db()
            conn.execute(
                """INSERT INTO resumes
                   (name, role_applied, match_score, date, status, ml_pred, ml_prob, resume_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    role if role else "Not Specified",
                    match_percent,
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


if __name__ == "__main__":
    app.run(debug=True)