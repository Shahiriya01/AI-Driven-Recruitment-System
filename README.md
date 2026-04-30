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
| Backend | Python 3.10+, Flask 3.0.3 |
| ML Model | scikit-learn 1.5.1 (Random Forest) |
| Resume Parsing | PyMuPDF, python-docx, Regex NLP |
| Database | SQLite |
| Frontend | HTML5, CSS3, JavaScript |
| Auth | Werkzeug password hashing |

---

## 🚀 Quick Start (One-Command Setup)

### Prerequisites

- **Python 3.10+** installed ([Download Python](https://www.python.org/downloads/))
- **pip** (comes with Python)
- **Git** (optional, for cloning)

> ⚠️ **Windows users**: Make sure to check **"Add Python to PATH"** during Python installation.

### 1. Clone the Repository

```bash
git clone https://github.com/Shahiriya01/AI-Driven-Recruitment-System.git
cd AI-Driven-Recruitment-System
```

### 2. Run the Setup Script (One-Command Setup)

The setup script will automatically:
- Create a virtual environment
- Install all dependencies with pinned versions
- Create required directories (`uploads/`, `models/`)
- Train the ML model (if not already trained)
- Run database migrations

**Windows:**
```cmd
setup.bat
```

**macOS / Linux:**
```bash
chmod +x setup.sh
./setup.sh
```

### 3. Activate the Virtual Environment

After setup, you need to activate the virtual environment in your terminal:

**Windows (Command Prompt):**
```cmd
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

> If PowerShell blocks script execution, run:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

**macOS / Linux:**
```bash
source venv/bin/activate
```

You'll see `(venv)` in your terminal prompt when the environment is active.

### 4. Run the Application

```bash
python app.py
```

The app will start on **http://127.0.0.1:5000** — open this URL in your browser.

---

## 🔧 Manual Setup (Alternative)

If you prefer to set up manually instead of using the script:

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate it (see activation commands above for your OS)

# 3. Upgrade pip
pip install --upgrade pip

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create directories
mkdir uploads models

# 6. Train the ML model
python model_training.py

# 7. Run migrations
python migrate_db.py

# 8. Start the app
python app.py
```

---

## 📁 Project Structure

```
AI-Driven-Recruitment-System/
├── app.py                  # Main Flask application & routes
├── db.py                   # Database schema & helper functions
├── model_training.py       # ML model training script
├── migrate_db.py           # Database migration utility
├── test_ml.py              # ML prediction test script
├── training_dataset.csv    # Training data for the ML model
├── requirements.txt        # Pinned Python dependencies
├── setup.bat               # Windows automated setup script
├── setup.sh                # macOS/Linux automated setup script
├── .gitignore              # Git ignore rules
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
├── uploads/                # Uploaded resumes (generated)
└── venv/                   # Virtual environment (generated, git-ignored)
```

---

## 📋 Usage

1. **Register** an account on the platform
2. **Login** with your credentials
3. **Screen a Resume** — Go to the screening page, enter the job role, required skills, minimum experience, and upload a resume (PDF, DOCX, or TXT)
4. **View Dashboard** — See all screened candidates with search, filter, and pagination
5. **Bulk Screen** — Upload multiple resumes at once for batch processing
6. **Performance** — Analyze screening trends and candidate statistics

---

## 🚢 Production Deployment

### Using Gunicorn (Linux/macOS)

```bash
# Activate venv
source venv/bin/activate

# Install Gunicorn
pip install gunicorn

# Run with Gunicorn (4 workers)
gunicorn --bind 0.0.0.0:8000 --workers 4 app:app
```

### Using Waitress (Windows)

```cmd
REM Activate venv
venv\Scripts\activate

REM Install Waitress
pip install waitress

REM Run with Waitress
waitress-serve --host=0.0.0.0 --port=8000 app:app
```

### Environment Variables for Production

Create a `.env` file (never commit this):

```env
FLASK_ENV=production
SECRET_KEY=your-production-secret-key-here
```

Update `app.py` to read from environment:

```python
app.secret_key = os.environ.get("SECRET_KEY", "fallback-dev-key")
```

### Docker Deployment (Optional)

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY . .
RUN python model_training.py
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "app:app"]
```

---

## ⚠️ Troubleshooting

| Issue | Solution |
|-------|---------|
| `ModuleNotFoundError` | Make sure your virtual environment is activated, then run `pip install -r requirements.txt` |
| ML predictions show `None` | Run `python model_training.py` to train the model |
| `InconsistentVersionWarning` for sklearn | Your scikit-learn version doesn't match the model's version. Retrain: `python model_training.py` |
| Port 5000 in use | Kill existing process or change port: add `app.run(debug=True, port=5001)` |
| `fitz` import error | Install `PyMuPDF` (not `fitz`): `pip install PyMuPDF` |
| PowerShell won't activate venv | Run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `python` command not found (macOS/Linux) | Use `python3` instead, or create an alias |
| Setup script permission denied (Linux/macOS) | Run: `chmod +x setup.sh` |

---

## 🔄 Retraining the ML Model

If you update the training data or encounter version mismatches:

```bash
# Activate venv first, then:
python model_training.py
```

This regenerates `models/model.pkl` using your current scikit-learn version.

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
