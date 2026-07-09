#!/bin/zsh
# Runs the daily budget sync. Invoked by launchd on a schedule.
# Pulls latest code first so the sheet always uses the newest logic,
# then syncs yesterday->today to catch late-posting transactions.
set -e
REPO="$HOME/Desktop/projects/personal-finance-apps"
LOG="$HOME/Library/Logs/daily-budget.log"

cd "$REPO"
echo "=== $(date '+%Y-%m-%d %H:%M:%S') run start ===" >> "$LOG"
git pull --ff-only origin master >> "$LOG" 2>&1 || echo "git pull skipped/failed" >> "$LOG"
/opt/homebrew/bin/python3 budget_sync.py "yesterday to today" >> "$LOG" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') run end ===" >> "$LOG"
