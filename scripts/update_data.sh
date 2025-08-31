#!/bin/zsh
# scripts/update_data.sh
set -e

# Go to the project
cd "$HOME/Desktop/market_pulse_pro_discovery_universe"

# Activate your virtualenv
source .venv/bin/activate

# Rebuild the daily 50-ticker universe (safe to run repeatedly)
python seed_universe.py || true

# Pull news + sentiment + attention (6 sources)
python run_once.py

# Write a timestamp to a log
echo "[OK] $(date)" >> logs/update.log