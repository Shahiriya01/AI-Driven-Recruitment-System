@echo off
REM ============================================================
REM  NextGen HR — Automated Setup Script (Windows)
REM  Creates virtual environment, installs deps, trains model
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo  ========================================
echo   NextGen HR - Environment Setup
echo  ========================================
echo.

REM ── Step 1: Check Python is available ──────────────────────
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo         Download it from https://www.python.org/downloads/
    echo         Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Show Python version
for /f "delims=" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Found %PYVER%

REM ── Step 2: Create virtual environment ─────────────────────
if exist venv (
    echo [OK] Virtual environment already exists — skipping creation.
) else (
    echo [..] Creating virtual environment...
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
)

REM ── Step 3: Activate virtual environment ───────────────────
echo [..] Activating virtual environment...
call venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)
echo [OK] Virtual environment activated.

REM ── Step 4: Upgrade pip ────────────────────────────────────
echo [..] Upgrading pip...
python -m pip install --upgrade pip >nul 2>nul
echo [OK] pip upgraded.

REM ── Step 5: Install dependencies ───────────────────────────
echo [..] Installing dependencies from requirements.txt...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install some dependencies.
    echo         Check the error messages above.
    pause
    exit /b 1
)
echo [OK] All dependencies installed.

REM ── Step 6: Create required directories ────────────────────
if not exist uploads mkdir uploads
if not exist models mkdir models
echo [OK] Directories ready.

REM ── Step 7: Train ML model (if not already trained) ────────
if exist models\model.pkl (
    echo [OK] ML model already exists — skipping training.
) else (
    if exist training_dataset.csv (
        echo [..] Training ML model...
        python model_training.py
        if %ERRORLEVEL% neq 0 (
            echo [WARN] Model training failed. The app will still run but ML predictions will be disabled.
        ) else (
            echo [OK] ML model trained successfully.
        )
    ) else (
        echo [WARN] training_dataset.csv not found — skipping model training.
        echo        ML predictions will be disabled until you train the model.
    )
)

REM ── Step 8: Run database migrations ────────────────────────
echo [..] Running database migrations...
python migrate_db.py
echo [OK] Database ready.

REM ── Done ───────────────────────────────────────────────────
echo.
echo  ========================================
echo   Setup Complete!
echo  ========================================
echo.
echo  To start the application:
echo.
echo    1. Activate the virtual environment:
echo       venv\Scripts\activate
echo.
echo    2. Run the app:
echo       python app.py
echo.
echo    3. Open in browser:
echo       http://127.0.0.1:5000
echo.
pause
