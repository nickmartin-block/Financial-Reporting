#!/bin/bash
# Lightweight comment-only refresh — runs independently of full data refresh
# Can be scheduled via cron for near-real-time comment visibility

set -e

GDRIVE="$HOME/skills/gdrive"
DASHBOARD_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Refreshing comments..."

cd "$GDRIVE" && uv run gdrive-cli.py sheets read \
    1HiiRZFv-CBA3xy2Fbr1T02xW4pgRPlbd2TQIYTNnmW8 \
    --sheet "Sheet1" > /tmp/dashboard_comments.json 2>/dev/null

cd "$GDRIVE" && uv run gdrive-cli.py sheets read \
    1HiiRZFv-CBA3xy2Fbr1T02xW4pgRPlbd2TQIYTNnmW8 \
    --sheet "Directory" > /tmp/dashboard_directory.json 2>/dev/null

python3 "$DASHBOARD_DIR/refresh_comments.py"

echo "Done."
