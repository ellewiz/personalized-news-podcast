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

# Retry a couple of times before giving up: a transient API error or network
# blip on one run usually clears on the next.
#
# This loop was originally added for a SIGSEGV-on-fork crash, on the
# assumption that run.py was dying. It wasn't — only a forked child died,
# and Python swallowed it, so every episode published and this loop never
# actually fired for that bug. It's since been fixed at the root (run.py
# warms platform.platform()'s caches before any network I/O; see the
# fork-crash entry in the README). Kept as a general safety net.
MAX_ATTEMPTS=3
attempt=1
until python run.py; do
  if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    echo "run.py failed $MAX_ATTEMPTS times — giving up for today." >&2
    osascript -e 'display notification "Episode did not publish after 3 attempts — check logs/publish.error.log" with title "Podcast: publish failed" sound name "Basso"' 2>/dev/null || true
    exit 1
  fi
  echo "run.py failed (attempt $attempt/$MAX_ATTEMPTS) — retrying in 5s..." >&2
  attempt=$((attempt + 1))
  sleep 5
done

git add docs state
git commit -m "Publish episode $(date -u +%Y-%m-%d)"

# Pull again immediately before pushing: something else (e.g. a manual commit,
# or someone else's push) may have landed on the remote while this ran.
git pull --no-rebase --no-edit origin main
git push origin main
