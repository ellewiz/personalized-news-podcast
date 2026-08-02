#!/usr/bin/env bash
# Run the pipeline and push the new episode + updated feed to GitHub Pages.
# Intended to be triggered by cron/systemd-timer on weekdays.
set -euo pipefail

cd "$(dirname "$0")/.."

source .venv/bin/activate
set -a
source .env
set +a

python run.py

git add docs state
git commit -m "Publish episode $(date -u +%Y-%m-%d)"
git push origin main
