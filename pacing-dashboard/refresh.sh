#!/bin/bash
# Block Pacing Dashboard — Full Refresh
# Reads all three source sheets and regenerates dashboard_data.js
#
# Usage: ./refresh.sh
#
# Sources:
#   1. Master Pacing Sheet (Q1 pacing data)
#   2. Corporate Model (Q2-Q4 internal forecast)
#   3. Consensus Model (Q2-Q4 Street estimates)

set -e

GDRIVE="$HOME/skills/gdrive"
DASHBOARD_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "═══ Block Pacing Dashboard Refresh ═══"
echo ""

# Check auth
echo "Checking auth..."
cd "$GDRIVE" && uv run gdrive-cli.py auth status > /dev/null 2>&1 || {
    echo "ERROR: Google auth failed. Run: cd ~/skills/gdrive && uv run gdrive-cli.py auth login"
    exit 1
}
echo "  ✓ Authenticated"

# Read sheets
echo ""
echo "Reading pacing sheet..."
cd "$GDRIVE" && uv run gdrive-cli.py sheets read \
    1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4 \
    --sheet summary > /tmp/pacing_sheet.json 2>/dev/null
echo "  ✓ Pacing sheet loaded"

echo "Reading corporate model..."
cd "$GDRIVE" && uv run gdrive-cli.py sheets read \
    1OyVIvezXnvLgoPJUWTCpLqJoOfP3na6YG3awUtdyE5M \
    --sheet "Summary P&L" > /tmp/corp_model.json 2>/dev/null
echo "  ✓ Corporate model loaded"

echo "Reading consensus model..."
cd "$GDRIVE" && uv run gdrive-cli.py sheets read \
    1CKtWmWd8buOeHfZnUivOGGGvONoy7WQM03DBzUe8WwQ \
    --sheet "Visible Alpha Consensus Summary" > /tmp/consensus_model.json 2>/dev/null
echo "  ✓ Consensus model loaded"

# Generate dashboard data
echo ""
echo "Generating dashboard_data.js..."
python3 "$DASHBOARD_DIR/refresh.py"

# Validate forecast data against Snowflake
echo ""
echo "Validating forecast data against Snowflake..."
cd "$DASHBOARD_DIR" && uv run validate.py
VALIDATE_RC=$?
if [ $VALIDATE_RC -ne 0 ]; then
    echo ""
    echo "⚠  Validation failed — review before deploying"
fi

echo ""
echo "═══ Done ═══"
echo "View: https://blockcell.sqprod.co/sites/nmart-pacing-dashboard/index.html"
