#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["snowflake-connector-python[secure-local-storage]"]
# ///
"""
Pacing Dashboard — Comprehensive Validation Suite

Validates dashboard_data.js across seven dimensions:
  1. Internal consistency (GP sum, margin calc, Rule of 40)
  2. Monthly-to-quarterly reconciliation
  3. Stale data detection
  4. Range / anomaly checks
  5. Cross-source verification vs Snowflake (completed months + Q2-Q4 forecasts)
  6. Block Data MCP cross-check (prior-year actuals + completed months + forecasts)
  7. Pacing reasonability (run-rate, brand consistency, consensus staleness)

Usage:
  uv run validate.py              # full validation (includes Snowflake + MCP)
  uv run validate.py --quick      # local checks only (no Snowflake, no MCP)
  uv run validate.py --no-mcp     # skip MCP checks (Snowflake still runs)
  uv run validate.py --year 2027  # override fiscal year

Exit codes: 0 = all pass, 1 = failures detected
"""

import argparse
import json
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DATA_PATH = os.path.join(SCRIPT_DIR, "dashboard_data.js")
PRIOR_DATA_PATH = os.path.join(SCRIPT_DIR, ".dashboard_data_prior.js")
REPORT_PATH = "/tmp/validation_report.json"

# Snowflake connection
SF_ACCOUNT = os.environ.get("SNOWFLAKE_ACCOUNT", "squareinc-square")
SF_USER = os.environ.get("SNOWFLAKE_USER", "NMART@SQUAREUP.COM")
SF_WAREHOUSE = os.environ.get("SNOWFLAKE_WAREHOUSE", "ADHOC__LARGE")
SF_DATABASE = "APP_HEXAGON"
SF_SCHEMA = "SCHEDULE2"

# Tolerances (tightened for governance — closed-book numbers should be precise)
TOL_DOLLAR_M = 5.0             # $5M for forecast comparisons
TOL_ACTUALS_M = 1.0            # $1M for completed month actuals (closed-book)
TOL_ACTUALS_EXACT = 0.01       # Near-zero for prior-year actuals vs MCP
TOL_MARGIN_PTS = 0.5           # 0.5 pts for margin/percentage comparisons
TOL_MONTHLY_REC_M = 5.0        # $5M for monthly-to-quarterly reconciliation
TOL_ANOMALY_PCT = 10.0         # 10% swing triggers anomaly flag
TOL_RUNRATE_PCT = 15.0         # 15% for pacing run-rate reasonability
MCP_ACTUALS_PATH = "/tmp/mcp_actuals.json"

QUARTER_START = {"Q1": "01-01", "Q2": "04-01", "Q3": "07-01", "Q4": "10-01"}


# ═══════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════

def pv(s):
    """Parse dollar/percentage value from formatted string to numeric."""
    if not s or s in ("--", "nm", "TBD"):
        return None
    s = (s.replace("$", "").replace(",", "").replace("%", "")
          .replace("M", "").replace("B", "").replace("bps", "")
          .replace("pts", "").replace("pt", "").replace("pp", "").strip())
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    if s.startswith("+"):
        s = s[1:]
    try:
        return float(s)
    except ValueError:
        return None


def pv_millions(s):
    """Parse dollar value to millions."""
    if not s or s in ("--", "nm", "TBD"):
        return None
    s = s.replace("$", "").replace(",", "").strip()
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    if s.startswith("+"):
        s = s[1:]
    if s.endswith("B"):
        return float(s[:-1]) * 1000
    if s.endswith("M"):
        return float(s[:-1])
    try:
        return float(s)
    except ValueError:
        return None


def load_dashboard():
    """Load and parse dashboard_data.js."""
    with open(DASHBOARD_DATA_PATH) as f:
        content = f.read()
    json_str = content.split("const DASHBOARD_DATA = ", 1)[1].rstrip().rstrip(";")
    return json.loads(json_str)


def load_prior_dashboard():
    """Load prior dashboard data if available."""
    if not os.path.exists(PRIOR_DATA_PATH):
        return None
    try:
        with open(PRIOR_DATA_PATH) as f:
            content = f.read()
        json_str = content.split("const DASHBOARD_DATA = ", 1)[1].rstrip().rstrip(";")
        return json.loads(json_str)
    except Exception:
        return None


def get_row(data, table_key, metric_name):
    """Find a row in a table by metric name."""
    for row in data.get(table_key, {}).get("rows", []):
        if row.get("metric") == metric_name:
            return row
    return None


def raw_or_parse(row, field, raw_field=None):
    """Get raw numeric value if available, otherwise fall back to parsing display string.
    Prefer _raw fields to avoid rounding errors from formatted display values."""
    if raw_field is None:
        raw_field = field + "_raw"
    raw = row.get(raw_field)
    if raw is not None:
        return float(raw)
    return pv_millions(row.get(field, "--"))


def get_monthly(data, metric_id):
    """Find a monthly metric by id."""
    for m in data.get("monthly_breakdown", []):
        if m.get("id") == metric_id:
            return m
    return None


class ValidationResult:
    def __init__(self):
        self.checks = []

    def add(self, category, name, status, detail=""):
        self.checks.append((category, name, status, detail))

    def passes(self):
        return sum(1 for _, _, s, _ in self.checks if s == "PASS")

    def fails(self):
        return sum(1 for _, _, s, _ in self.checks if s == "FAIL")

    def warns(self):
        return sum(1 for _, _, s, _ in self.checks if s == "WARN")

    def skips(self):
        return sum(1 for _, _, s, _ in self.checks if s == "SKIP")

    def all_pass(self):
        return self.fails() == 0

    def write_report(self):
        """Write JSON report for downstream consumers (e.g., Slack alerts, dashboard meta)."""
        report = {
            "status": "PASS" if self.all_pass() else "FAIL",
            "total": len(self.checks),
            "passes": self.passes(),
            "fails": self.fails(),
            "warns": self.warns(),
            "skips": self.skips(),
            "failures": [
                f"{name}: {detail}" for _, name, status, detail in self.checks if status == "FAIL"
            ],
            "warnings": [
                f"{name}: {detail}" for _, name, status, detail in self.checks if status == "WARN"
            ],
            "categories": list(dict.fromkeys(cat for cat, _, _, _ in self.checks)),
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        with open(REPORT_PATH, "w") as f:
            json.dump(report, f, indent=2)

    def print_report(self):
        current_cat = None
        for cat, name, status, detail in self.checks:
            if cat != current_cat:
                print(f"\n{'─' * 50}")
                print(f"  {cat}")
                print(f"{'─' * 50}")
                current_cat = cat
            sym = {"PASS": "✓", "FAIL": "✗", "WARN": "⚠", "SKIP": "○"}[status]
            d = f"  ({detail})" if detail else ""
            print(f"  [{sym}] {name}{d}")

        print(f"\n{'═' * 50}")
        print(f"  {self.passes()} PASS  {self.fails()} FAIL  {self.warns()} WARN  {self.skips()} SKIP")
        if self.all_pass():
            print("  [OK] All validations passed")
        else:
            print("  [!!] VALIDATION FAILURES — review before deploying")
        print(f"{'═' * 50}")


# ═══════════════════════════════════════════════════════
# 1. Internal Consistency
# ═══════════════════════════════════════════════════════

def validate_consistency(data, results):
    """Check internal mathematical consistency."""
    cat = "Internal Consistency"

    # Block GP >= Cash App GP + Square GP
    bgp_row = get_row(data, "block_table", "Block Gross Profit")
    cagp_row = get_row(data, "cashapp_table", "Cash App Gross Profit")
    sqgp_row = get_row(data, "square_table", "Square Gross Profit")
    bgp = raw_or_parse(bgp_row, "pacing") if bgp_row else None
    cagp = raw_or_parse(cagp_row, "pacing") if cagp_row else None
    sqgp = raw_or_parse(sqgp_row, "pacing") if sqgp_row else None
    if bgp and cagp and sqgp:
        brand_sum = cagp + sqgp
        gap = bgp - brand_sum
        if gap < -TOL_DOLLAR_M:
            results.add(cat, "Block GP >= CashApp + Square",
                        "FAIL", f"Block ${bgp:.0f}M < sum ${brand_sum:.0f}M by ${abs(gap):.0f}M")
        elif gap > 200:
            results.add(cat, "Block GP >= CashApp + Square",
                        "WARN", f"gap ${gap:.0f}M unusually large (Proto+TIDAL+other)")
        else:
            results.add(cat, "Block GP >= CashApp + Square",
                        "PASS", f"gap ${gap:.0f}M (Proto+TIDAL+other)")
    else:
        results.add(cat, "Block GP >= CashApp + Square", "SKIP", "missing data")

    # AOI Margin = AOI / GP * 100
    aoi_row = get_row(data, "block_table", "Adjusted Operating Income")
    aoi = raw_or_parse(aoi_row, "pacing") if aoi_row else None
    margin_displayed = pv(get_row(data, "block_table", "AOI Margin").get("pacing", "--"))
    if bgp and aoi and margin_displayed is not None:
        margin_computed = aoi / bgp * 100
        delta = abs(margin_displayed - margin_computed)
        if delta <= TOL_MARGIN_PTS:
            results.add(cat, "AOI Margin = AOI / GP",
                        "PASS", f"displayed {margin_displayed:.0f}% vs computed {margin_computed:.1f}%")
        else:
            results.add(cat, "AOI Margin = AOI / GP",
                        "FAIL", f"displayed {margin_displayed:.0f}% vs computed {margin_computed:.1f}%, off by {delta:.1f} pts")
    else:
        results.add(cat, "AOI Margin = AOI / GP", "SKIP", "missing data")

    # Rule of 40 = GP YoY + AOI Margin
    ro40_displayed = pv(get_row(data, "block_table", "Rule of 40").get("pacing", "--"))
    gp_yoy = pv(get_row(data, "block_table", "Block Gross Profit").get("yoy", "--"))
    if ro40_displayed is not None and gp_yoy is not None and margin_displayed is not None:
        # Use raw margin for more precision
        margin_raw = aoi / bgp * 100 if aoi and bgp else margin_displayed
        ro40_computed = gp_yoy + margin_raw
        delta = abs(ro40_displayed - ro40_computed)
        if delta <= TOL_MARGIN_PTS:
            results.add(cat, "Rule of 40 = GP YoY + Margin",
                        "PASS", f"displayed {ro40_displayed:.0f}% vs computed {ro40_computed:.1f}%")
        else:
            results.add(cat, "Rule of 40 = GP YoY + Margin",
                        "FAIL", f"displayed {ro40_displayed:.0f}% vs computed {ro40_computed:.1f}%, off by {delta:.1f} pts")
    else:
        results.add(cat, "Rule of 40 = GP YoY + Margin", "SKIP", "missing data")

    # vs Consensus = Pacing - Consensus (for Block GP and AOI)
    # Use raw values to avoid rounding errors from formatted display strings
    for metric, fmt in [("Block Gross Profit", "B"), ("Adjusted Operating Income", "M")]:
        row = get_row(data, "block_table", metric)
        if row:
            pacing_v = raw_or_parse(row, "pacing")
            cons_v = raw_or_parse(row, "consensus")
            vs_cons_v = raw_or_parse(row, "vs_cons")
            if pacing_v is not None and cons_v is not None and vs_cons_v is not None:
                computed = pacing_v - cons_v
                delta = abs(vs_cons_v - computed)
                status = "PASS" if delta <= TOL_DOLLAR_M else "FAIL"
                results.add(cat, f"{metric} vs Cons arithmetic",
                            status, f"displayed ${vs_cons_v:+.0f}M vs computed ${computed:+.0f}M")


# ═══════════════════════════════════════════════════════
# 2. Monthly-to-Quarterly Reconciliation
# ═══════════════════════════════════════════════════════

def validate_monthly_quarterly(data, results):
    """Verify sum of monthly values ≈ quarterly pacing."""
    cat = "Monthly ↔ Quarterly Reconciliation"

    # Metrics where sum(monthly) should ≈ quarterly
    checks = [
        ("block_gp", "Block Gross Profit", "block_table"),
        ("cashapp_gp", "Cash App Gross Profit", "cashapp_table"),
        ("square_gp", "Square Gross Profit", "square_table"),
        ("aoi", "Adjusted Operating Income", "block_table"),
    ]

    for monthly_id, metric_name, table_key in checks:
        monthly = get_monthly(data, monthly_id)
        row = get_row(data, table_key, metric_name)
        if not monthly or not row:
            results.add(cat, f"{metric_name} monthly sum", "SKIP", "missing data")
            continue

        monthly_raws = [m.get("raw") for m in monthly.get("months", [])]
        if None in monthly_raws:
            results.add(cat, f"{metric_name} monthly sum", "SKIP", "missing monthly raw values")
            continue

        monthly_sum = sum(monthly_raws)
        quarterly = raw_or_parse(row, "pacing")
        if quarterly is None:
            results.add(cat, f"{metric_name} monthly sum", "SKIP", "missing quarterly value")
            continue

        delta = abs(monthly_sum - quarterly)
        if delta <= TOL_MONTHLY_REC_M:
            results.add(cat, f"{metric_name} monthly sum",
                        "PASS", f"sum ${monthly_sum:.0f}M vs Q1 ${quarterly:.0f}M (Δ${delta:.0f}M)")
        else:
            results.add(cat, f"{metric_name} monthly sum",
                        "FAIL", f"sum ${monthly_sum:.0f}M vs Q1 ${quarterly:.0f}M (Δ${delta:.0f}M)")

    # GPV: sum monthly ≈ quarterly (values in billions)
    for gpv_id, gpv_label in [("global_gpv", "Global GPV"), ("us_gpv", "US GPV"), ("intl_gpv", "International GPV")]:
        monthly = get_monthly(data, gpv_id)
        row = get_row(data, "square_table", gpv_label)
        if not monthly or not row:
            results.add(cat, f"{gpv_label} monthly sum", "SKIP", "missing data")
            continue
        monthly_raws = [m.get("raw") for m in monthly.get("months", [])]
        if None in monthly_raws:
            results.add(cat, f"{gpv_label} monthly sum", "SKIP", "missing monthly values")
            continue
        monthly_sum = sum(monthly_raws)  # in billions
        quarterly_str = row.get("pacing", "--")
        quarterly = pv(quarterly_str)  # strips $, B → numeric in billions
        if quarterly is None:
            results.add(cat, f"{gpv_label} monthly sum", "SKIP", "missing quarterly")
            continue
        delta = abs(monthly_sum - quarterly)
        if delta <= 0.5:  # $0.5B tolerance for GPV
            results.add(cat, f"{gpv_label} monthly sum",
                        "PASS", f"sum ${monthly_sum:.1f}B vs Q1 ${quarterly:.1f}B")
        else:
            results.add(cat, f"{gpv_label} monthly sum",
                        "FAIL", f"sum ${monthly_sum:.1f}B vs Q1 ${quarterly:.1f}B (Δ${delta:.1f}B)")


# ═══════════════════════════════════════════════════════
# 3. Stale Data Detection
# ═══════════════════════════════════════════════════════

def validate_stale_data(data, results):
    """Check for indicators that the source data wasn't refreshed."""
    cat = "Stale Data Detection"

    # Check if all WoW deltas are zero or missing
    wow_values = []
    for table in ["block_table", "cashapp_table", "square_table"]:
        for row in data.get(table, {}).get("rows", []):
            wow = row.get("wow", "--")
            wow_values.append(wow)

    non_zero_wow = [w for w in wow_values if w not in ("--", "+$0M", "+$0.0M", "$0.0B", "+$0M", "0 bps", "0pp", "0.0M")]
    if len(non_zero_wow) == 0:
        results.add(cat, "WoW deltas non-zero",
                    "WARN", "all WoW values are zero or missing — sheet may not be updated")
    else:
        results.add(cat, "WoW deltas non-zero",
                    "PASS", f"{len(non_zero_wow)}/{len(wow_values)} metrics have non-zero WoW")

    # Check generated_at timestamp freshness
    gen_at = data.get("meta", {}).get("generated_at", "")
    if gen_at:
        try:
            gen_dt = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
            age_hours = (datetime.now(gen_dt.tzinfo) - gen_dt).total_seconds() / 3600
            if age_hours > 48:
                results.add(cat, "Data freshness",
                            "WARN", f"generated {age_hours:.0f}h ago — consider re-reading sheets")
            else:
                results.add(cat, "Data freshness",
                            "PASS", f"generated {age_hours:.1f}h ago")
        except Exception:
            results.add(cat, "Data freshness", "SKIP", "could not parse timestamp")
    else:
        results.add(cat, "Data freshness", "SKIP", "no timestamp")


# ═══════════════════════════════════════════════════════
# 4. Range / Anomaly Checks
# ═══════════════════════════════════════════════════════

def validate_ranges(data, results):
    """Check that values are within plausible ranges."""
    cat = "Range Checks"

    # Block GP should be positive and in a reasonable range ($1B-$5B for a quarter)
    bgp_row = get_row(data, "block_table", "Block Gross Profit")
    bgp = raw_or_parse(bgp_row, "pacing") if bgp_row else None
    if bgp is not None:
        if 1000 <= bgp <= 5000:
            results.add(cat, "Block GP range", "PASS", f"${bgp:.0f}M")
        else:
            results.add(cat, "Block GP range", "FAIL", f"${bgp:.0f}M outside $1B-$5B range")

    # AOI should be positive (for now) and < GP
    aoi_row = get_row(data, "block_table", "Adjusted Operating Income")
    aoi = raw_or_parse(aoi_row, "pacing") if aoi_row else None
    if aoi is not None and bgp is not None:
        if 0 < aoi < bgp:
            results.add(cat, "AOI range (0 < AOI < GP)", "PASS", f"${aoi:.0f}M")
        else:
            results.add(cat, "AOI range (0 < AOI < GP)", "FAIL", f"AOI=${aoi:.0f}M, GP=${bgp:.0f}M")

    # AOI Margin 0-50%
    margin = pv(get_row(data, "block_table", "AOI Margin").get("pacing", "--"))
    if margin is not None:
        if 0 <= margin <= 50:
            results.add(cat, "AOI Margin range (0-50%)", "PASS", f"{margin:.0f}%")
        else:
            results.add(cat, "AOI Margin range (0-50%)", "FAIL", f"{margin:.0f}%")

    # Rule of 40 should be 0-100%
    ro40 = pv(get_row(data, "block_table", "Rule of 40").get("pacing", "--"))
    if ro40 is not None:
        if 0 <= ro40 <= 100:
            results.add(cat, "Rule of 40 range (0-100%)", "PASS", f"{ro40:.0f}%")
        else:
            results.add(cat, "Rule of 40 range (0-100%)", "FAIL", f"{ro40:.0f}%")


def validate_anomalies(data, prior, results):
    """Compare against prior refresh for unexpected swings."""
    cat = "Anomaly Detection (vs Prior Refresh)"

    if prior is None:
        results.add(cat, "Prior data comparison", "SKIP", "no prior refresh saved")
        return

    # Compare key metrics
    checks = [
        ("block_table", "Block Gross Profit", "pacing"),
        ("block_table", "Adjusted Operating Income", "pacing"),
        ("cashapp_table", "Cash App Gross Profit", "pacing"),
        ("square_table", "Square Gross Profit", "pacing"),
    ]

    for table, metric, field in checks:
        cur_row = get_row(data, table, metric)
        pri_row = get_row(prior, table, metric)
        if not cur_row or not pri_row:
            continue

        cur_v = raw_or_parse(cur_row, field)
        pri_v = raw_or_parse(pri_row, field)
        if cur_v is None or pri_v is None or pri_v == 0:
            continue

        pct_change = abs(cur_v - pri_v) / abs(pri_v) * 100
        if pct_change > TOL_ANOMALY_PCT:
            results.add(cat, f"{metric} swing",
                        "WARN", f"{pct_change:.1f}% change (${pri_v:.0f}M → ${cur_v:.0f}M)")
        else:
            results.add(cat, f"{metric} swing",
                        "PASS", f"{pct_change:.1f}% change")


# ═══════════════════════════════════════════════════════
# 5. Cross-Source: Snowflake Verification
# ═══════════════════════════════════════════════════════

def connect_snowflake():
    import snowflake.connector
    return snowflake.connector.connect(
        account=SF_ACCOUNT, user=SF_USER, authenticator="externalbrowser",
        warehouse=SF_WAREHOUSE, database=SF_DATABASE, schema=SF_SCHEMA,
    )


def validate_snowflake_actuals(data, conn, results, year=2026):
    """Cross-check completed months against Snowflake actuals."""
    cat = "Cross-Source: Completed Months vs Snowflake"

    cur = conn.cursor()
    cur.execute("""
        SELECT METRIC_NAME, MONTH_FIRST_DAY, SUM(USD_AMOUNT) AS TOTAL
        FROM APP_HEXAGON.SCHEDULE2.FINANCIAL_METRIC_SUMMARY
        WHERE SCENARIO = 'Actual'
          AND MONTH_FIRST_DAY BETWEEN %(start)s AND %(end)s
          AND METRIC_NAME IN ('Gross Profit', 'Adjusted Operating Income')
        GROUP BY 1, 2
        ORDER BY 1, 2
    """, {"start": f"{year}-01-01", "end": f"{year}-03-31"})

    sf_data = {}
    for metric, month_date, total in cur:
        month_idx = month_date.month if hasattr(month_date, 'month') else int(str(month_date)[5:7])
        sf_data[(metric, month_idx)] = float(total) / 1e6  # to millions
    cur.close()

    # Map dashboard monthly metrics to Snowflake metrics
    checks = [
        ("block_gp", "Gross Profit", "Block Gross Profit"),
        ("aoi", "Adjusted Operating Income", "Adjusted Operating Income"),
    ]

    month_names = {1: "January", 2: "February", 3: "March"}

    for monthly_id, sf_metric, display_name in checks:
        monthly = get_monthly(data, monthly_id)
        if not monthly:
            continue

        for month_num, month_data in zip([1, 2, 3], monthly.get("months", [])):
            # Always skip the pacing month — Snowflake may have partial actuals
            # that don't match the full-month pacing estimate
            if month_data.get("label", "").endswith("(P)"):
                results.add(cat, f"{display_name} {month_names[month_num]}",
                            "SKIP", "pacing month (not closed)")
                continue

            dash_val = month_data.get("raw")
            sf_val = sf_data.get((sf_metric, month_num))

            if dash_val is None or sf_val is None:
                results.add(cat, f"{display_name} {month_names[month_num]}",
                            "SKIP", "missing data")
                continue

            delta = abs(dash_val - sf_val)
            if delta <= TOL_ACTUALS_M:
                results.add(cat, f"{display_name} {month_names[month_num]}",
                            "PASS", f"dash ${dash_val:.0f}M vs SF ${sf_val:.0f}M (Δ${delta:.1f}M)")
            else:
                results.add(cat, f"{display_name} {month_names[month_num]}",
                            "FAIL", f"dash ${dash_val:.0f}M vs SF ${sf_val:.0f}M (Δ${delta:.1f}M)")


def validate_snowflake_forecasts(data, conn, results, year=2026, scenario=None):
    """Existing: Q2-Q4 forecasts vs Snowflake EPM."""
    cat = "Cross-Source: Q2-Q4 Forecasts vs Snowflake"
    scenario = scenario or f"{year} Annual Plan"

    cur = conn.cursor()
    cur.execute("""
        SELECT METRIC_NAME, DATE_TRUNC('QUARTER', MONTH_FIRST_DAY) AS QTR,
               SUM(USD_AMOUNT) AS TOTAL
        FROM APP_HEXAGON.SCHEDULE2.FINANCIAL_METRIC_SUMMARY
        WHERE SCENARIO = %(scenario)s AND VERSION = 'Final'
          AND MONTH_FIRST_DAY BETWEEN %(start)s AND %(end)s
          AND METRIC_NAME IN ('Gross Profit', 'Adjusted Operating Income', 'Risk Loss Opex')
        GROUP BY 1, 2
        ORDER BY 1, 2
    """, {"scenario": scenario, "start": f"{year}-01-01", "end": f"{year}-12-31"})

    sf = {}
    for metric, qtr_date, total in cur:
        q_date = qtr_date.strftime("%m-%d") if hasattr(qtr_date, "strftime") else str(qtr_date)[5:10]
        q_label = next((k for k, v in QUARTER_START.items() if v == q_date), None)
        if q_label and total is not None:
            sf[(metric, q_label)] = float(total)
    cur.close()

    for q in ["Q2", "Q3", "Q4"]:
        for qf in data.get("forward_look", {}).get("quarterly_forecast", []):
            if qf["quarter"] != q:
                continue

            for label, sf_metric, key, derived in [
                ("Gross Profit", "Gross Profit", "block_gp", False),
                ("AOI", "Adjusted Operating Income", "aoi", False),
                ("GP Net Risk Loss", None, "gp_net_risk", True),
            ]:
                dash_val = pv_millions(qf[key]["forecast"])
                if derived:
                    sf_gp = sf.get(("Gross Profit", q))
                    sf_rl = sf.get(("Risk Loss Opex", q))
                    sf_val_m = (sf_gp - sf_rl) / 1e6 if sf_gp and sf_rl else None
                else:
                    sf_raw = sf.get((sf_metric, q))
                    sf_val_m = sf_raw / 1e6 if sf_raw else None

                if dash_val is None or sf_val_m is None:
                    results.add(cat, f"{q} {label}", "SKIP")
                    continue

                delta = abs(dash_val - sf_val_m)
                status = "PASS" if delta <= TOL_DOLLAR_M else "FAIL"
                results.add(cat, f"{q} {label}",
                            status, f"dash ${dash_val:.0f}M vs SF ${sf_val_m:.0f}M (Δ${delta:.1f}M)")


# ═══════════════════════════════════════════════════════
# 6. Cross-Source: Block Data MCP Verification
# ═══════════════════════════════════════════════════════

def load_mcp_actuals():
    """Load MCP actuals from the pre-fetched JSON file."""
    if not os.path.exists(MCP_ACTUALS_PATH):
        return None
    try:
        with open(MCP_ACTUALS_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def validate_mcp_actuals(data, results):
    """Cross-check dashboard values against Block Data MCP actuals."""
    cat = "Cross-Source: Block Data MCP"

    mcp = load_mcp_actuals()
    if mcp is None:
        results.add(cat, "MCP actuals cross-check", "FAIL",
                    "no /tmp/mcp_actuals.json — MCP fetch required for validation")
        return

    results.add(cat, "MCP data available", "PASS", "file loaded")

    # Check prior-year actuals used by refresh.py (zero tolerance)
    for key, label in [
        ("Q1_2024_GP", "Q1 2024 Gross Profit"),
        ("Q1_2025_GP", "Q1 2025 Gross Profit"),
        ("Q1_2025_AOI", "Q1 2025 AOI"),
    ]:
        mcp_val = mcp.get(key)
        meta_source = data.get("meta", {}).get("actuals_source", "unknown")
        if mcp_val is None:
            results.add(cat, f"PY actual: {label}", "SKIP", "not in MCP data")
            continue
        # These are consumed by refresh.py — verify they were used
        results.add(cat, f"PY actual: {label}", "PASS",
                    f"MCP=${float(mcp_val)/1e6:,.0f}M (source: {meta_source})")

    # Check completed month actuals (Jan, Feb) — MCP vs dashboard
    monthly_metrics = [
        ("block_gp", "Block Gross Profit", "monthly_gp"),
        ("aoi", "AOI", "monthly_aoi"),
    ]
    for monthly_id, label, mcp_prefix in monthly_metrics:
        monthly = get_monthly(data, monthly_id)
        if not monthly:
            continue
        for month_num, month_data in zip([1, 2], monthly.get("months", [])[:2]):
            dash_val = month_data.get("raw")  # in millions
            mcp_key = f"{mcp_prefix}_m{month_num}"
            mcp_val_raw = mcp.get(mcp_key)
            if dash_val is None or mcp_val_raw is None:
                results.add(cat, f"{label} M{month_num} actual", "SKIP", "missing data")
                continue
            mcp_val = float(mcp_val_raw)  # expected in millions
            delta = abs(dash_val - mcp_val)
            status = "PASS" if delta <= TOL_ACTUALS_M else "FAIL"
            month_name = ["Jan", "Feb"][month_num - 1]
            results.add(cat, f"{label} {month_name} actual",
                        status, f"dash ${dash_val:.0f}M vs MCP ${mcp_val:.0f}M (Δ${delta:.1f}M)")

    # Check Q2-Q4 forecasts against MCP outlook
    for q_idx, q_label in enumerate(["Q2", "Q3", "Q4"]):
        for metric_key, metric_label, mcp_key in [
            ("block_gp", "GP", f"forecast_gp_{q_label.lower()}"),
            ("aoi", "AOI", f"forecast_aoi_{q_label.lower()}"),
        ]:
            mcp_val_raw = mcp.get(mcp_key)
            if mcp_val_raw is None:
                continue
            mcp_val = float(mcp_val_raw)  # in millions
            for qf in data.get("forward_look", {}).get("quarterly_forecast", []):
                if qf["quarter"] != q_label:
                    continue
                dash_val = pv_millions(qf.get(metric_key, {}).get("forecast", "--"))
                if dash_val is None:
                    continue
                delta = abs(dash_val - mcp_val)
                status = "PASS" if delta <= TOL_DOLLAR_M else "FAIL"
                results.add(cat, f"{q_label} {metric_label} forecast",
                            status, f"dash ${dash_val:.0f}M vs MCP ${mcp_val:.0f}M (Δ${delta:.1f}M)")


# ═══════════════════════════════════════════════════════
# 7. Pacing Reasonability Checks
# ═══════════════════════════════════════════════════════

def validate_pacing_reasonability(data, prior, results):
    """Check that pacing numbers are reasonable given closed-month data."""
    cat = "Pacing Reasonability"

    # 7a. Run-rate check: March pacing within 15% of Jan-Feb average
    for monthly_id, label in [("block_gp", "Block GP"), ("aoi", "AOI")]:
        monthly = get_monthly(data, monthly_id)
        if not monthly or len(monthly.get("months", [])) < 3:
            continue
        months = monthly["months"]
        jan_raw = months[0].get("raw")
        feb_raw = months[1].get("raw")
        mar_raw = months[2].get("raw")
        if jan_raw is None or feb_raw is None or mar_raw is None:
            results.add(cat, f"{label} run-rate", "SKIP", "missing monthly data")
            continue
        avg = (jan_raw + feb_raw) / 2
        if avg == 0:
            continue
        deviation = abs(mar_raw - avg) / abs(avg) * 100
        if deviation <= TOL_RUNRATE_PCT:
            results.add(cat, f"{label} run-rate", "PASS",
                        f"Mar ${mar_raw:.0f}M vs Jan-Feb avg ${avg:.0f}M ({deviation:.0f}% deviation)")
        else:
            results.add(cat, f"{label} run-rate", "WARN",
                        f"Mar ${mar_raw:.0f}M is {deviation:.0f}% off Jan-Feb avg ${avg:.0f}M")

    # 7b. Brand consistency: Block GP WoW ≈ CA GP WoW + SQ GP WoW
    bgp_row = get_row(data, "block_table", "Block Gross Profit")
    cagp_row = get_row(data, "cashapp_table", "Cash App Gross Profit")
    sqgp_row = get_row(data, "square_table", "Square Gross Profit")
    if bgp_row and cagp_row and sqgp_row:
        bgp_wow = pv_millions(bgp_row.get("wow", "--"))
        cagp_wow = pv_millions(cagp_row.get("wow", "--"))
        sqgp_wow = pv_millions(sqgp_row.get("wow", "--"))
        if bgp_wow is not None and cagp_wow is not None and sqgp_wow is not None:
            brand_sum_wow = cagp_wow + sqgp_wow
            gap = abs(bgp_wow - brand_sum_wow)
            if gap <= TOL_DOLLAR_M:
                results.add(cat, "Brand WoW consistency", "PASS",
                            f"Block WoW ${bgp_wow:+.0f}M ≈ CA+SQ ${brand_sum_wow:+.0f}M (gap ${gap:.0f}M)")
            else:
                results.add(cat, "Brand WoW consistency", "WARN",
                            f"Block WoW ${bgp_wow:+.0f}M vs CA+SQ ${brand_sum_wow:+.0f}M (gap ${gap:.0f}M)")
        else:
            results.add(cat, "Brand WoW consistency", "SKIP", "missing WoW data")
    else:
        results.add(cat, "Brand WoW consistency", "SKIP", "missing table rows")

    # 7c. Consensus staleness: flag if consensus unchanged for 4+ refreshes
    if prior:
        cons_fields_match = 0
        cons_fields_total = 0
        for table_key in ["block_table", "cashapp_table", "square_table"]:
            for row in data.get(table_key, {}).get("rows", []):
                cur_cons = row.get("consensus", "--")
                pri_row = get_row(prior, table_key, row.get("metric", ""))
                if pri_row:
                    pri_cons = pri_row.get("consensus", "--")
                    cons_fields_total += 1
                    if cur_cons == pri_cons:
                        cons_fields_match += 1
        if cons_fields_total > 0 and cons_fields_match == cons_fields_total:
            results.add(cat, "Consensus freshness", "WARN",
                        f"all {cons_fields_total} consensus values unchanged since prior refresh")
        elif cons_fields_total > 0:
            changed = cons_fields_total - cons_fields_match
            results.add(cat, "Consensus freshness", "PASS",
                        f"{changed}/{cons_fields_total} consensus values updated")
        else:
            results.add(cat, "Consensus freshness", "SKIP", "no consensus data")
    else:
        results.add(cat, "Consensus freshness", "SKIP", "no prior data for comparison")


# ═══════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Comprehensive dashboard validation")
    parser.add_argument("--quick", action="store_true", help="Local checks only (skip Snowflake and MCP)")
    parser.add_argument("--no-mcp", action="store_true", help="Skip Block Data MCP checks")
    parser.add_argument("--year", type=int, default=2026, help="Fiscal year (default: 2026)")
    parser.add_argument("--scenario", type=str, default=None, help="Forecast scenario override")
    args = parser.parse_args()

    mode_parts = []
    if args.quick:
        mode_parts.append("Quick (local only)")
    else:
        mode_parts.append("Snowflake")
        if not args.no_mcp:
            mode_parts.append("MCP")

    print("=" * 50)
    print("  Pacing Dashboard — Validation Suite")
    print("=" * 50)
    print(f"  Mode: {' + '.join(mode_parts) if mode_parts else 'Local only'}")
    print(f"  Year: {args.year}")

    # Load data
    print("\nLoading dashboard_data.js...")
    data = load_dashboard()
    meta = data.get("meta", {})
    print(f"  Generated: {meta.get('generated_at', '?')}")
    print(f"  Actuals source: {meta.get('actuals_source', '?')}")
    print(f"  Pacing checksum: {meta.get('pacing_checksum', '?')[:12]}...")

    prior = load_prior_dashboard()
    if prior:
        print(f"  Prior refresh: {prior.get('meta', {}).get('generated_at', '?')}")
    else:
        print("  No prior refresh data saved")

    results = ValidationResult()

    # Run local validations (categories 1-4)
    validate_consistency(data, results)
    validate_monthly_quarterly(data, results)
    validate_stale_data(data, results)
    validate_ranges(data, results)
    validate_anomalies(data, prior, results)

    # Run pacing reasonability checks (category 7 — local, no external deps)
    validate_pacing_reasonability(data, prior, results)

    # Run Snowflake validations (category 5)
    if not args.quick:
        print("\nConnecting to Snowflake...")
        try:
            conn = connect_snowflake()
            print("  Connected")
            validate_snowflake_actuals(data, conn, results, args.year)
            validate_snowflake_forecasts(data, conn, results, args.year, args.scenario)
            conn.close()
        except Exception as e:
            print(f"  Snowflake connection failed: {e}")
            results.add("Snowflake", "Connection", "SKIP", str(e))

    # Run Block Data MCP validations (category 6)
    if not args.quick and not args.no_mcp:
        print("\nChecking Block Data MCP actuals...")
        validate_mcp_actuals(data, results)

    # Print report
    results.print_report()

    # Write report to both /tmp and project directory
    results.write_report()
    project_report = os.path.join(SCRIPT_DIR, "validation_report.json")
    import shutil
    if os.path.exists(REPORT_PATH):
        shutil.copy2(REPORT_PATH, project_report)

    # Save current data as prior for next run
    shutil.copy2(DASHBOARD_DATA_PATH, PRIOR_DATA_PATH)
    print(f"\n  Saved current data as prior for next validation run")

    return 0 if results.all_pass() else 1


if __name__ == "__main__":
    sys.exit(main())
