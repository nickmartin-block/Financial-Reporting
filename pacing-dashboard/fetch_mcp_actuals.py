#!/usr/bin/env python3
"""Fetch prior-year actuals from Snowflake and write /tmp/mcp_actuals.json.

This provides the MCP cross-check data that validate.py uses to confirm
that the pacing sheet's prior-year actuals match the source of truth.
"""

import json
import os
import sys
from datetime import datetime, timezone

OUTPUT_PATH = "/tmp/mcp_actuals.json"

SF_ACCOUNT = os.environ.get("SNOWFLAKE_ACCOUNT", "squareinc-square")
SF_USER = os.environ.get("SNOWFLAKE_USER", "NMART@SQUAREUP.COM")
SF_WAREHOUSE = os.environ.get("SNOWFLAKE_WAREHOUSE", "ADHOC__LARGE")
SF_DATABASE = "APP_HEXAGON"
SF_SCHEMA = "SCHEDULE2"


def fetch():
    try:
        import snowflake.connector
    except ImportError:
        print("  ⚠ snowflake module not available — skipping MCP actuals fetch")
        return False

    try:
        conn = snowflake.connector.connect(
            account=SF_ACCOUNT, user=SF_USER, warehouse=SF_WAREHOUSE,
            database=SF_DATABASE, schema=SF_SCHEMA, authenticator="externalbrowser",
        )
    except Exception as e:
        print(f"  ⚠ Snowflake connection failed: {e}")
        return False

    cur = conn.cursor()

    # Q1 2024 Block Gross Profit (actual)
    # Q1 2025 Block Gross Profit (actual)
    # Q1 2025 Adjusted Operating Income (actual)
    cur.execute("""
        SELECT METRIC_NAME,
               DATE_TRUNC('QUARTER', MONTH_FIRST_DAY) AS QTR,
               SUM(USD_AMOUNT) AS TOTAL
        FROM FINANCIAL_METRIC_SUMMARY
        WHERE SCENARIO = 'Actual' AND VERSION = 'Final'
          AND METRIC_NAME IN ('Gross Profit', 'Adjusted Operating Income')
          AND (
            (MONTH_FIRST_DAY BETWEEN '2024-01-01' AND '2024-03-31')
            OR (MONTH_FIRST_DAY BETWEEN '2025-01-01' AND '2025-03-31')
          )
        GROUP BY 1, 2
        ORDER BY 1, 2
    """)

    results = {}
    for metric, qtr_date, total in cur:
        year = qtr_date.year if hasattr(qtr_date, "year") else int(str(qtr_date)[:4])
        if metric == "Gross Profit" and year == 2024:
            results["Q1_2024_GP"] = float(total)
        elif metric == "Gross Profit" and year == 2025:
            results["Q1_2025_GP"] = float(total)
        elif metric == "Adjusted Operating Income" and year == 2025:
            results["Q1_2025_AOI"] = float(total)

    cur.close()
    conn.close()

    required = ["Q1_2024_GP", "Q1_2025_GP", "Q1_2025_AOI"]
    missing = [k for k in required if k not in results]
    if missing:
        print(f"  ⚠ Snowflake query missing keys: {missing}")
        return False

    results["fetched_at"] = datetime.now(timezone.utc).isoformat()

    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"  ✓ MCP actuals fetched from Snowflake → {OUTPUT_PATH}")
    for k in required:
        print(f"    {k}: ${results[k]/1e6:,.0f}M")
    return True


if __name__ == "__main__":
    success = fetch()
    sys.exit(0 if success else 1)
