#!/usr/bin/env bash
set -euo pipefail

REPO="/home/manu/.openclaw/workspace"
cd "$REPO"

# Avoid noisy/generated files from frequent cron updates.
EXCLUDES=(
  "slice/web/latest.json"
  "slice/web/news.json"
  "memory/blossom-slot-state.json"
)

# Stage everything first, then unstage excluded paths.
git add -A
for p in "${EXCLUDES[@]}"; do
  git reset -q HEAD -- "$p" 2>/dev/null || true
done

# If no staged changes remain, exit quietly.
if git diff --cached --quiet; then
  echo "NO_CHANGES"
  exit 0
fi

stamp="$(TZ=America/New_York date '+%Y-%m-%d %I:%M %p ET')"
git commit -m "chore: auto-sync workspace updates (${stamp})"
git push origin main

echo "PUSHED"
