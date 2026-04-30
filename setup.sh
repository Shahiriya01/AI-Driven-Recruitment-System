#!/usr/bin/env bash
# ============================================================
#  NextGen HR — Automated Setup Script (macOS / Linux)
#  Creates virtual environment, installs deps, trains model
# ============================================================

set -e

echo ""
echo " ========================================"
echo "  NextGen HR - Environment Setup"
echo " ========================================"
echo ""

# ── Step 1: Check Python is available ──────────────────────
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python is not installed or not in PATH."
    echo "        Install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

PYVER=$($PYTHON_CMD --version 2>&1)
echo "[OK] Found $PYVER"

# Check Python version >= 3.10
PY_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo "[ERROR] Python 3.10+ is required. Found $PYVER"
    exit 1
fi

# ── Step 2: Create virtual environment ─────────────────────
if [ -d "venv" ]; then
    echo "[OK] Virtual environment already exists — skipping creation."
else
    echo "[..] Creating virtual environment..."
    $PYTHON_CMD -m venv venv
    echo "[OK] Virtual environment created."
fi

# ── Step 3: Activate virtual environment ───────────────────
echo "[..] Activating virtual environment..."
source venv/bin/activate
echo "[OK] Virtual environment activated."

# ── Step 4: Upgrade pip ────────────────────────────────────
echo "[..] Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "[OK] pip upgraded."

# ── Step 5: Install dependencies ───────────────────────────
echo "[..] Installing dependencies from requirements.txt..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install some dependencies."
    exit 1
fi
echo "[OK] All dependencies installed."

# ── Step 6: Create required directories ────────────────────
mkdir -p uploads models
echo "[OK] Directories ready."

# ── Step 7: Train ML model (if not already trained) ────────
if [ -f "models/model.pkl" ]; then
    echo "[OK] ML model already exists — skipping training."
else
    if [ -f "training_dataset.csv" ]; then
        echo "[..] Training ML model..."
        python model_training.py && echo "[OK] ML model trained successfully." || \
            echo "[WARN] Model training failed. App will run but ML predictions will be disabled."
    else
        echo "[WARN] training_dataset.csv not found — skipping model training."
        echo "       ML predictions will be disabled until you train the model."
    fi
fi

# ── Step 8: Run database migrations ────────────────────────
echo "[..] Running database migrations..."
python migrate_db.py
echo "[OK] Database ready."

# ── Done ───────────────────────────────────────────────────
echo ""
echo " ========================================"
echo "  Setup Complete!"
echo " ========================================"
echo ""
echo " To start the application:"
echo ""
echo "   1. Activate the virtual environment:"
echo "      source venv/bin/activate"
echo ""
echo "   2. Run the app:"
echo "      python app.py"
echo ""
echo "   3. Open in browser:"
echo "      http://127.0.0.1:5000"
echo ""
