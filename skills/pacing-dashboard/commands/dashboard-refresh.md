---
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Bash(cd "$HOME/Desktop/Nick's Cursor/Pacing Dashboard" && *)
  - Bash(python3 *)
  - Bash(uv run *)
  - Read
  - Write
  - mcp__blockdata__fetch_metric_data
  - mcp__blockdata__get_metric_details
  - mcp__blockdata__list_available_metrics
---

Run the dashboard-refresh skill to update the pacing dashboard with live data and validate forecasts.

1. Load the skill from `~/skills/pacing-dashboard/skills/dashboard-refresh.md`
2. Follow all steps in order (MCP actuals → auth → read sheets → extract → format → write → validate)
3. Output file: `~/Desktop/Nick's Cursor/Pacing Dashboard/dashboard_data.js`
4. Governance: MCP actuals → /tmp/mcp_actuals.json → consumed by refresh.py and validate.py
5. Validation: `validate.py` cross-checks against Snowflake + Block Data MCP
6. Report summary when complete
