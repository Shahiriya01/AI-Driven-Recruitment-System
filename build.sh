#!/usr/bin/env bash
# ============================================================
#  Render Build Script
#  Runs during each deploy on Render's free tier
# ============================================================

set -o errexit  # Exit on error

echo "=== Installing dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Creating required directories ==="
mkdir -p uploads models

echo "=== Training ML model ==="
python model_training.py

echo "=== Running database migrations ==="
python migrate_db.py

echo "=== Build complete ==="
