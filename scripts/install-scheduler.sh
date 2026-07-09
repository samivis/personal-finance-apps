#!/bin/zsh
# One-time installer for the scheduled budget sync (macOS launchd).
# Run this ONCE on the always-on machine (the Mac mini).
set -e
REPO="$HOME/Desktop/projects/personal-finance-apps"
PLIST_SRC="$REPO/scripts/com.svisai.dailybudget.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.svisai.dailybudget.plist"

echo "Checking required config (certs + webhook)..."
missing=0
for f in "$HOME/.config/daily-budget/webhook.json" \
         "$HOME/.bank-mcp/config.json" \
         "$HOME/.bank-mcp/keys/teller/certificate.pem" \
         "$HOME/.bank-mcp/keys/teller/private_key.pem"; do
  if [[ ! -f "$f" ]]; then echo "  MISSING: $f"; missing=1; fi
done
if [[ $missing -eq 1 ]]; then
  echo ""
  echo "Copy the missing files from your other Mac before scheduling. e.g.:"
  echo "  scp -r <othermac>:~/.bank-mcp ~/ "
  echo "  scp -r <othermac>:~/.config/daily-budget ~/.config/"
  exit 1
fi

chmod +x "$REPO/scripts/run_scheduled.sh"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cp "$PLIST_SRC" "$PLIST_DST"

# reload cleanly
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "Installed. It will run at 9am, 3pm, 9pm daily."
echo "Test-fire now:  launchctl start com.svisai.dailybudget"
echo "Watch logs:     tail -f ~/Library/Logs/daily-budget.log"
