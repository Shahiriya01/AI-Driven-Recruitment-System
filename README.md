# 🤖 AI-Driven Recruitment System — NextGen HR

An AI-powered candidate screening platform built with **Flask**, **scikit-learn**, and **NLP-based resume parsing**. Upload resumes, automatically extract skills, experience, and education — then let the ML model rank and predict the best candidates for your open roles.

---

## ✨ Features

- **AI Resume Screening** — Upload PDF / DOCX / TXT resumes and get instant analysis
- **ML Prediction** — Random Forest model predicts candidate eligibility with probability scores
- **Bulk Screening** — Upload up to 100 resumes at once with real-time SSE progress tracking
- **Smart Parsing** — Extracts name, email, phone, skills, experience (multi-strategy), education level, and certifications
- **Interactive Dashboard** — Search, filter, paginate, and manage screened candidates
- **Performance Analytics** — Visual insights into screening results and match scores
- **Multi-Tenant Isolation** — Each HR user only sees their own data
- **Secure Authentication** — Registration & login with hashed passwords

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask |
| ML Model | scikit-learn (Random Forest) |
| Resume Parsing | PyMuPDF, python-docx, Regex NLP |
| Database | SQLite |
| Frontend | HTML5, CSS3, JavaScript |
| Auth | Werkzeug password hashing |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+** installed ([Download Python](https://www.python.org/downloads/))
- **pip** (comes with Python)
- **Git** (optional, for cloning)

### 1. Clone the Repository

```bash
git clone https://github.com/Shahiriya01/AI-Driven-Recruitment-System.git
cd AI-Driven-Recruitment-System
```

### 2. Create a Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Train the ML Model

The ML model must be trained before first use:

```bash
python model_training.py
```

This creates `models/model.pkl` using the provided `training_dataset.csv`.

### 5. Run the Application

```bash
python app.py
```

The app will start on **http://127.0.0.1:5000** — open this URL in your browser.

---

## 📁 Project Structure

```
AI-Driven-Recruitment-System/
├── app.py                  # Main Flask application & routes
├── db.py                   # Database schema & helper functions
├── model_training.py       # ML model training script
├── migrate_db.py           # Database migration utility
├── training_dataset.csv    # Training data for the ML model
├── requirements.txt        # Python dependencies
├── static/
│   └── css/
│       └── style.css       # Application styling
├── templates/
│   ├── base.html           # Base layout template
│   ├── home.html           # Landing page
│   ├── login.html          # Login page
│   ├── register.html       # Registration page
│   ├── dashboard.html      # Main dashboard
│   ├── screening.html      # Single resume screening
│   ├── bulk_screening.html # Bulk resume upload
│   ├── batch_results.html  # Bulk screening results
│   ├── performance.html    # Analytics & performance
│   ├── about.html          # About page
│   └── contact.html        # Contact page
├── models/                 # Trained ML model (generated)
└── uploads/                # Uploaded resumes (generated)
```

---

## 📋 Usage

1. **Register** an account on the platform
2. **Login** with your credentials
3. **Screen a Resume** — Go to the screening page, enter the job role, required skills, minimum experience, and upload a resume
4. **View Dashboard** — See all screened candidates with search, filter, and pagination
5. **Bulk Screen** — Upload multiple resumes at once for batch processing
6. **Performance** — Analyze screening trends and candidate statistics

---

## ⚠️ Troubleshooting

| Issue | Solution |
|-------|---------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` inside your virtual environment |
| ML predictions show `None` | Run `python model_training.py` to train the model first |
| Port 5000 in use | Change the port: `python app.py` and edit the `app.run()` call, or kill the existing process |
| `fitz` import error | Make sure you installed `PyMuPDF` (not `fitz`): `pip install PyMuPDF` |

---

## 📄 License

This project is for educational purposes — built as a final year project.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request
