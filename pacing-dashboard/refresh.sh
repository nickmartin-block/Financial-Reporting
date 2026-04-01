#!/bin/bash
# Block Pacing Dashboard — Full Refresh
# Reads all three source sheets, regenerates dashboard_data.js, validates,
# and saves a versioned snapshot.
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
SNAPSHOTS_DIR="$DASHBOARD_DIR/snapshots"

# Timestamped temp directory (avoids collisions with other processes)
TMP_DIR="/tmp/pacing_refresh_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$TMP_DIR"

echo "═══ Block Pacing Dashboard Refresh ═══"
echo "  Temp: $TMP_DIR"
echo ""

# Check auth
echo "Checking auth..."
cd "$GDRIVE" && uv run gdrive-cli.py auth status > /dev/null 2>&1 || {
    echo "ERROR: Google auth failed. Run: cd ~/skills/gdrive && uv run gdrive-cli.py auth login"
    exit 1
}
echo "  ✓ Authenticated"

# Fetch MCP actuals from Snowflake (cross-check for validation)
echo ""
echo "Fetching MCP actuals..."
python3 "$DASHBOARD_DIR/fetch_mcp_actuals.py" || echo "  ○ MCP fetch unavailable — validation will use Block Data MCP fallback"

# Read sheets (write to both timestamped dir and legacy /tmp/ paths for compatibility)
echo ""
echo "Reading pacing sheet..."
cd "$GDRIVE" && uv run gdrive-cli.py sheets read \
    1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4 \
    --sheet summary > "$TMP_DIR/pacing_sheet.json" 2>/dev/null
cp "$TMP_DIR/pacing_sheet.json" /tmp/pacing_sheet.json
echo "  ✓ Pacing sheet loaded"

echo "Reading corporate model..."
cd "$GDRIVE" && uv run gdrive-cli.py sheets read \
    1OyVIvezXnvLgoPJUWTCpLqJoOfP3na6YG3awUtdyE5M \
    --sheet "Summary P&L" > "$TMP_DIR/corp_model.json" 2>/dev/null
cp "$TMP_DIR/corp_model.json" /tmp/corp_model.json
echo "  ✓ Corporate model loaded"

echo "Reading consensus model..."
cd "$GDRIVE" && uv run gdrive-cli.py sheets read \
    1CKtWmWd8buOeHfZnUivOGGGvONoy7WQM03DBzUe8WwQ \
    --sheet "Visible Alpha Consensus Summary" > "$TMP_DIR/consensus_model.json" 2>/dev/null
cp "$TMP_DIR/consensus_model.json" /tmp/consensus_model.json
echo "  ✓ Consensus model loaded"

echo "Reading comments..."
cd "$GDRIVE" && uv run gdrive-cli.py sheets read \
    1HiiRZFv-CBA3xy2Fbr1T02xW4pgRPlbd2TQIYTNnmW8 \
    --sheet "Comments" > "$TMP_DIR/dashboard_comments.json" 2>/dev/null
cp "$TMP_DIR/dashboard_comments.json" /tmp/dashboard_comments.json
echo "  ✓ Comments loaded"

# Generate dashboard data
echo ""
echo "Generating dashboard_data.js..."
python3 "$DASHBOARD_DIR/refresh.py"

# Validate
echo ""
echo "Validating..."
cd "$DASHBOARD_DIR" && uv run validate.py
VALIDATE_RC=$?
if [ $VALIDATE_RC -ne 0 ]; then
    echo ""
    echo "⚠  Validation failed — review before deploying"
fi

# Save snapshot (only if validation passed)
if [ $VALIDATE_RC -eq 0 ]; then
    mkdir -p "$SNAPSHOTS_DIR"
    SNAP_DATE=$(date +%Y-%m-%d)
    SNAP_FILE="dashboard_data_${SNAP_DATE}.js"
    cp "$DASHBOARD_DIR/dashboard_data.js" "$SNAPSHOTS_DIR/$SNAP_FILE"

    # Update manifest (use env vars to avoid quoting issues with paths)
    export SNAP_DASHBOARD_DIR="$DASHBOARD_DIR"
    export SNAP_SNAPSHOTS_DIR="$SNAPSHOTS_DIR"
    export SNAP_DATE SNAP_FILE
    python3 << 'PYEOF'
import json, os

dashboard_dir = os.environ["SNAP_DASHBOARD_DIR"]
snapshots_dir = os.environ["SNAP_SNAPSHOTS_DIR"]
snap_date = os.environ["SNAP_DATE"]
snap_file = os.environ["SNAP_FILE"]

# Extract checksum from dashboard_data.js
data_path = os.path.join(dashboard_dir, "dashboard_data.js")
with open(data_path) as f:
    content = f.read()
js = content.split("const DASHBOARD_DATA = ", 1)[1].rstrip().rstrip(";")
data = json.loads(js)
checksum = data.get("meta", {}).get("pacing_checksum", "")

# Read validation status
val_status = "PASS"
report_path = os.path.join(dashboard_dir, "validation_report.json")
if os.path.exists(report_path):
    with open(report_path) as f:
        val_status = json.load(f).get("status", "PASS")

# Update manifest
manifest_path = os.path.join(snapshots_dir, "manifest.json")
entries = []
if os.path.exists(manifest_path):
    with open(manifest_path) as f:
        entries = json.load(f)
entries = [e for e in entries if e.get("date") != snap_date]
entries.append({"date": snap_date, "file": snap_file, "checksum": checksum, "validation": val_status})
entries.sort(key=lambda e: e["date"], reverse=True)
with open(manifest_path, "w") as f:
    json.dump(entries, f, indent=2)
PYEOF
    echo ""
    echo "  ✓ Snapshot saved: snapshots/$SNAP_FILE"
fi

echo ""
echo "═══ Done ═══"
echo "View: https://blockcell.sqprod.co/sites/nmart-pacing-dashboard/index.html"
