#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["snowflake-connector-python[secure-local-storage]"]
# ///
"""
Pacing Dashboard — Forecast Validation

Validates Q2-Q4 forecast values in dashboard_data.js against the EPM/Hyperion
source of truth in Snowflake (financial_metric_summary table).

Usage:
  uv run validate.py                     # default: 2026 Annual Plan
  uv run validate.py --scenario "Q2 Outlook"  # override scenario
  uv run validate.py --year 2027         # override fiscal year

Exit codes: 0 = all pass, 1 = validation failure
"""

import argparse
import getpass
import json
import os
import sys
from datetime import datetime

import snowflake.connector

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DATA_PATH = os.path.join(SCRIPT_DIR, "dashboard_data.js")

# Snowflake connection
SF_ACCOUNT = os.environ.get("SNOWFLAKE_ACCOUNT", "squareinc-square")
SF_USER = os.environ.get("SNOWFLAKE_USER", "NMART@SQUAREUP.COM")
SF_WAREHOUSE = os.environ.get("SNOWFLAKE_WAREHOUSE", "ADHOC__LARGE")
SF_DATABASE = "APP_HEXAGON"
SF_SCHEMA = "SCHEDULE2"

# Tolerance for validation (in millions USD)
# Dashboard formats as $X.XXB (±$5M rounding) or $XXXM (±$0.5M rounding)
TOLERANCE_M = 5.0

QUARTER_START = {"Q1": "01-01", "Q2": "04-01", "Q3": "07-01", "Q4": "10-01"}

VALIDATION_SQL = """
SELECT
  METRIC_NAME,
  DATE_TRUNC('QUARTER', MONTH_FIRST_DAY) AS QUARTER,
  SUM(USD_AMOUNT) AS TOTAL_USD
FROM APP_HEXAGON.SCHEDULE2.FINANCIAL_METRIC_SUMMARY
WHERE SCENARIO = %(scenario)s
  AND VERSION = 'Final'
  AND MONTH_FIRST_DAY BETWEEN %(start_date)s AND %(end_date)s
  AND METRIC_NAME IN ('Gross Profit', 'Adjusted Operating Income', 'Risk Loss Opex')
GROUP BY 1, 2
ORDER BY 1, 2
"""


# ─── Snowflake ───

def connect_snowflake():
    """Connect to Snowflake using SSO (externalbrowser) auth."""
    return snowflake.connector.connect(
        account=SF_ACCOUNT,
        user=SF_USER,
        authenticator="externalbrowser",
        warehouse=SF_WAREHOUSE,
        database=SF_DATABASE,
        schema=SF_SCHEMA,
    )


def fetch_snowflake_data(conn, year, scenario):
    """Fetch GP, AOI, Risk Loss from financial_metric_summary."""
    cur = conn.cursor()
    cur.execute(VALIDATION_SQL, {
        "scenario": scenario,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
    })

    results = {}
    for metric_name, quarter_date, total_usd in cur:
        q_date = quarter_date.strftime("%m-%d") if hasattr(quarter_date, "strftime") else str(quarter_date)[5:10]
        q_label = next((k for k, v in QUARTER_START.items() if v == q_date), None)
        if q_label and total_usd is not None:
            results[(metric_name, q_label)] = float(total_usd)

    cur.close()
    return results


# ─── Dashboard parsing ───

def parse_dollar_value(s):
    """Parse '$3.08B' or '$484M' to millions."""
    if not s or s == "--":
        return None
    s = s.replace("$", "").replace(",", "").strip()
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    if s.endswith("B"):
        return float(s[:-1]) * 1000
    if s.endswith("M"):
        return float(s[:-1])
    return float(s)


def load_dashboard_forecasts():
    """Parse dashboard_data.js and extract Q2-Q4 forecast values (in $M)."""
    with open(DASHBOARD_DATA_PATH) as f:
        content = f.read()

    json_str = content.split("const DASHBOARD_DATA = ", 1)[1].rstrip().rstrip(";")
    data = json.loads(json_str)

    forecasts = {}
    for qf in data.get("forward_look", {}).get("quarterly_forecast", []):
        q = qf["quarter"]
        if q == "Q1":
            continue  # Q1 is pacing data, not forecast — skip

        gp = parse_dollar_value(qf["block_gp"]["forecast"])
        if gp is not None:
            forecasts[("Gross Profit", q)] = gp

        aoi = parse_dollar_value(qf["aoi"]["forecast"])
        if aoi is not None:
            forecasts[("Adjusted Operating Income", q)] = aoi

        gnrl = parse_dollar_value(qf["gp_net_risk"]["forecast"])
        if gnrl is not None:
            forecasts[("GP Net Risk Loss", q)] = gnrl

    return forecasts, data.get("meta", {}).get("generated_at", "unknown")


# ─── Validation ───

def validate(year, scenario):
    print("=" * 50)
    print("  Forecast Validation")
    print("=" * 50)
    print(f"  Scenario:  {scenario}")
    print(f"  Year:      {year}")
    print(f"  Tolerance: ${TOLERANCE_M:.0f}M")
    print()

    # Load dashboard data
    print("Loading dashboard_data.js...")
    dashboard, generated_at = load_dashboard_forecasts()
    print(f"  Generated: {generated_at}")

    # Connect to Snowflake
    print("Connecting to Snowflake...")
    try:
        conn = connect_snowflake()
    except Exception as e:
        print(f"  ERROR: Snowflake connection failed: {e}")
        return 1
    print("  Connected")

    print("Fetching reference data...")
    snowflake_data = fetch_snowflake_data(conn, year, scenario)
    conn.close()
    print(f"  Retrieved {len(snowflake_data)} metric-quarter values")
    print()

    # Compare Q2-Q4
    results = []
    all_pass = True

    for q in ["Q2", "Q3", "Q4"]:
        print(f"--- {q} ---")

        for label, sf_metric, derived in [
            ("Gross Profit", "Gross Profit", False),
            ("Adjusted Operating Income", "Adjusted Operating Income", False),
            ("GP Net Risk Loss", None, True),
        ]:
            dash_val = dashboard.get((label, q))

            if derived:
                sf_gp = snowflake_data.get(("Gross Profit", q))
                sf_rl = snowflake_data.get(("Risk Loss Opex", q))
                sf_val_m = (sf_gp - sf_rl) / 1e6 if sf_gp is not None and sf_rl is not None else None
            else:
                sf_raw = snowflake_data.get((sf_metric, q))
                sf_val_m = sf_raw / 1e6 if sf_raw is not None else None

            if dash_val is None or sf_val_m is None:
                status = "SKIP"
                delta = None
            else:
                delta = abs(dash_val - sf_val_m)
                status = "PASS" if delta <= TOLERANCE_M else "FAIL"

            if status == "FAIL":
                all_pass = False

            sym = {"PASS": "+", "FAIL": "X", "SKIP": "o"}[status]
            d_str = f"${dash_val:,.0f}M" if dash_val is not None else "n/a"
            s_str = f"${sf_val_m:,.0f}M" if sf_val_m is not None else "n/a"
            delta_str = f"  delta ${delta:.1f}M" if delta is not None else ""

            print(f"  [{sym}] {label:<35} Dash: {d_str:<12} SF: {s_str:<12}{delta_str}")

            results.append((label, q, status, delta))

        print()

    # Summary
    pass_n = sum(1 for _, _, s, _ in results if s == "PASS")
    fail_n = sum(1 for _, _, s, _ in results if s == "FAIL")
    skip_n = sum(1 for _, _, s, _ in results if s == "SKIP")

    print(f"Results: {pass_n} PASS, {fail_n} FAIL, {skip_n} SKIP")

    if all_pass:
        print("[OK] All forecast values validated successfully")
    else:
        print("[!!] VALIDATION FAILURES DETECTED - review before deploying")

    return 0 if all_pass else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate pacing dashboard forecasts against Snowflake")
    parser.add_argument("--year", type=int, default=2026, help="Fiscal year (default: 2026)")
    parser.add_argument("--scenario", type=str, default=None, help="Scenario override (default: '{year} Annual Plan')")
    args = parser.parse_args()

    scenario = args.scenario or f"{args.year} Annual Plan"
    sys.exit(validate(args.year, scenario))
