import sys
sys.path.insert(0, ".")
from app import extract_text_from_pdf, extract_experience, extract_skills, estimate_keyword_density, estimate_education_level, estimate_cert_count, estimate_job_count
import joblib
import numpy as np

filepath = "uploads/RIYA SHAHI resume.pdf"
text = extract_text_from_pdf(filepath)
job_skills = ["python", "django", "sql", "machine learning", "flask"]

name = "Riya Shahi"
experience = extract_experience(text)
skills = extract_skills(text)
matched = [s for s in job_skills if s in skills]
match_percent = int((len(matched) / len(job_skills)) * 100) if job_skills else 0

skill_match     = round(len(matched) / len(job_skills), 6) if job_skills else 0.0
resume_length   = len(text.split())
keyword_density = estimate_keyword_density(text, job_skills)
num_skills      = len(skills)
education_level = estimate_education_level(text)
cert_count      = estimate_cert_count(text)
job_count       = estimate_job_count(text)

print(f"Experience extracted: {experience}")
print(f"Matched skills: {matched}")
print(f"Skill match: {skill_match}")
print(f"Resume length: {resume_length}")
print(f"Keyword density: {keyword_density}")
print(f"Num skills: {num_skills}")
print(f"Education level: {education_level}")
print(f"Cert count: {cert_count}")
print(f"Job count: {job_count}")

features = np.array([[skill_match, experience, resume_length,
                      keyword_density, num_skills, education_level,
                      cert_count, job_count]])

rf_model = joblib.load("models/model.pkl")
ml_pred = int(rf_model.predict(features)[0])
ml_prob = round(float(rf_model.predict_proba(features)[0][1]), 4)

print(f"ML Pred: {ml_pred}")
print(f"ML Prob: {ml_prob}")
