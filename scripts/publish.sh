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

# python run.py occasionally crashes with a SIGSEGV during fork() — a known
# macOS bug where Apple's Network.framework corrupts state across fork() in
# a process that has already made network calls (same root cause as the
# ffmpeg fork crash documented in podcast/tts.py). It's intermittent and not
# a bug in this codebase, so retry a couple of times before giving up.
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
