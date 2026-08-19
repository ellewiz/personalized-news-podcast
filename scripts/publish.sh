#!/usr/bin/env bash
# Run the pipeline and push the new episode + updated feed to GitHub Pages.
# Intended to be triggered by cron/systemd-timer on weekdays.
set -euo pipefail

cd "$(dirname "$0")/.."

git pull --no-rebase --no-edit origin main

source .venv/bin/activate
set -a
source .env
set +a

python run.py

git add docs state
git commit -m "Publish episode $(date -u +%Y-%m-%d)"

# Pull again immediately before pushing: something else (e.g. a manual commit,
# or someone else's push) may have landed on the remote while this ran.
git pull --no-rebase --no-edit origin main
git push origin main
