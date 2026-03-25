#!/usr/bin/env python3
"""
Block Pacing Dashboard — Data Refresh Script

Reads three Google Sheets via gdrive-cli and generates dashboard_data.js
with live metrics for the pacing dashboard.

Sources:
  1. Master Pacing Sheet (Q1 pacing, WoW, AP, Guidance, Consensus)
  2. Corporate Model (Q2-Q4 internal forecast)
  3. Consensus Model (Q2-Q4 Street estimates)

Usage:
  cd ~/skills/gdrive && uv run gdrive-cli.py sheets read <ID> --sheet <TAB> > /tmp/<file>.json
  Then: python3 ~/Desktop/Nick's\ Cursor/Pacing\ Dashboard/refresh.py
"""

import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "dashboard_data.js")

# Sheet IDs
PACING_SHEET_ID = "1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4"
CORP_MODEL_ID = "1OyVIvezXnvLgoPJUWTCpLqJoOfP3na6YG3awUtdyE5M"
CONSENSUS_MODEL_ID = "1CKtWmWd8buOeHfZnUivOGGGvONoy7WQM03DBzUe8WwQ"

# Sheet tabs
PACING_TAB = "summary"
CORP_TAB = "Summary P&L"
CONSENSUS_TAB = "Visible Alpha Consensus Summary"

# ─── Temp file paths (written by gdrive-cli before this script runs) ───
PACING_JSON = "/tmp/pacing_sheet.json"
CORP_JSON = "/tmp/corp_model.json"
CONSENSUS_JSON = "/tmp/consensus_model.json"
COMMENTARY_JSON = "/tmp/commentary.json"  # Optional: written by skill from Innercore doc
COMMENTS_JSON = "/tmp/dashboard_comments.json"  # Comments sheet
COMMENTS_SHEET_ID = "1HiiRZFv-CBA3xy2Fbr1T02xW4pgRPlbd2TQIYTNnmW8"

# ─── Q1 2025 Historical Actuals (from Snowflake, fixed) ───
# Source: APP_HEXAGON.SCHEDULE2.FINANCIAL_METRIC_SUMMARY, scenario='Actual', Q1 2024/2025
Q1_2024_GP = 2094472510.10       # Block Gross Profit Q1 2024 (USD)
Q1_2025_GP = 2289603216.33       # Block Gross Profit Q1 2025 (USD)
Q1_2025_AOI = 466268762.99       # Adjusted Operating Income Q1 2025 (USD)
Q1_2025_MARGIN = Q1_2025_AOI / Q1_2025_GP * 100        # 20.37%
Q1_2025_GP_GROWTH = (Q1_2025_GP - Q1_2024_GP) / Q1_2024_GP * 100  # 9.32%
Q1_2025_RO40 = Q1_2025_GP_GROWTH + Q1_2025_MARGIN      # 29.68%


# ═══════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════

def sg(row, idx):
    """Safe get cell value."""
    if idx < len(row):
        v = row[idx]
        if v is None:
            return ""
        s = str(v).strip()
        if s in ("", "#N/A", "#REF!", "#VALUE!", "#DIV/0!", "--"):
            return ""
        return s
    return ""


def pn(s):
    """Parse numeric value from formatted string."""
    if not s or s in ("--", "nm", ""):
        return None
    s = (s.replace(",", "").replace("$", "").replace("%", "")
          .replace("M", "").replace("B", "").replace("bps", "")
          .replace("pts", "").replace("pt", "").strip())
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return None


def find_row(data, label, start=0, col=1):
    """Find row index by exact label match in the given column."""
    for i in range(start, len(data)):
        if len(data[i]) > col and str(data[i][col]).strip() == label:
            return i
    return None


def require_row(data, label, sheet_name, start=0, col=1):
    """Find row index or abort with a clear error."""
    idx = find_row(data, label, start, col)
    if idx is None:
        print(f"ERROR: Could not find label '{label}' (col {col}) in {sheet_name}. "
              f"The sheet structure may have changed.")
        sys.exit(1)
    return idx


# ─── Formatting ───

def fB(v):
    """Format millions as $X.XXB."""
    if v is None: return "--"
    return f"${v / 1000:.2f}B"

def fM(v):
    """Format millions as $XXXM or $X.XM."""
    if v is None: return "--"
    return f"${v:.0f}M" if abs(v) >= 10 else f"${v:.1f}M"

def fdD(v):
    """Dollar delta with sign."""
    if v is None: return "--"
    return f"(${abs(v):.0f}M)" if v < 0 else f"+${v:.0f}M"

def fp(s):
    """Format percentage with sign. >=10% no decimal, <10% one decimal."""
    if not s or s in ("--", "nm"): return s or "--"
    v = pn(s)
    if v is None: return s
    t = f"{abs(v):.0f}%" if abs(v) >= 10 else f"{abs(v):.1f}%"
    return f"({t})" if v < 0 else f"+{t}"

def fpg(s):
    """Format percentage — GPV style: keep 1 decimal for 10-15% range."""
    if not s or s in ("--", "nm"): return s or "--"
    v = pn(s)
    if v is None: return s
    av = abs(v)
    t = f"{av:.1f}%" if av < 15 else f"{av:.0f}%"
    return f"({t})" if v < 0 else f"+{t}"

def fm(s):
    """Format margin percentage (no sign)."""
    if not s: return "--"
    v = pn(s)
    return f"{v:.0f}%" if v is not None else s

def fbps(s):
    """Format basis points."""
    if not s: return "--"
    v = pn(s)
    if v is None: return s
    if abs(v) < 0.5: return "0 bps"
    return f"({abs(v):.0f} bps)" if v < 0 else f"+{v:.0f} bps"

def fac(s):
    """Format actives (always 1 decimal)."""
    if not s: return "--"
    v = pn(s)
    return f"{v:.1f}M" if v is not None else s

def fwd(s):
    """Format WoW dollar delta — keep .1f for sub-$10M precision."""
    if not s: return "--"
    v = pn(s)
    if v is None: return "--"
    av = abs(v)
    if av < 0.05: return "+$0M"
    t = f"${av:.1f}M" if av < 10 else f"${av:.0f}M"
    return f"({t})" if v < 0 else f"+{t}"

def fwp(s):
    """Format WoW percentage delta."""
    if not s: return "--"
    v = pn(s)
    if v is None: return "--"
    if abs(v) < 0.05: return "0pp"
    return f"({abs(v):.1f}pp)" if v < 0 else f"+{v:.1f}pp"

def fmt_yoy(v):
    """Format YoY from numeric value."""
    if v is None: return "--"
    av = abs(v)
    t = f"{av:.0f}%" if av >= 10 else f"{av:.1f}%"
    return f"({t})" if v < 0 else f"+{t}"

def fmt_margin(v):
    """Format margin from numeric value."""
    if v is None: return "--"
    return f"{v:.0f}%"

def fmt_margin_delta(a, b):
    """Format margin delta in pts."""
    if a is None or b is None: return "--"
    d = a - b
    if abs(d) < 0.5: return "0 pts"
    return f"({abs(d):.0f} pts)" if d < 0 else f"+{d:.0f} pts"

def sig(d):
    """Signal color from delta percentage."""
    if d is None: return "neutral"
    return "green" if d > 0.5 else ("red" if d < -0.5 else "neutral")

def pd(a, b):
    """Percentage delta."""
    if a is None or b is None or b == 0: return None
    return (a - b) / abs(b) * 100

def gd(y1, y2):
    """Growth delta in pts from strings."""
    a, b = pn(y1), pn(y2)
    if a is None or b is None: return "--"
    d = a - b
    if abs(d) < 0.5: return "0 pts"
    return f"({abs(d):.0f} pts)" if d < 0 else f"+{d:.0f} pts"

def gd_v(a, b):
    """Growth delta in pts from numeric values."""
    if a is None or b is None: return "--"
    d = a - b
    if abs(d) < 0.5: return "0 pts"
    return f"({abs(d):.0f} pts)" if d < 0 else f"+{d:.0f} pts"


# ─── WoW Helpers (use col 28 if available, else compute from col 17 - col 27) ───

def wow_dollar(row):
    raw = sg(row, 28)
    if raw: return fwd(raw)
    cur, prior = pn(sg(row, 17)), pn(sg(row, 27))
    if cur is None or prior is None: return "--"
    d = cur - prior
    return f"(${abs(d):.1f}M)" if d < 0 else f"+${d:.1f}M"

def wow_actives(row):
    cur, prior = pn(sg(row, 17)), pn(sg(row, 27))
    if cur is None or prior is None: return "--"
    d = cur - prior
    if abs(d) < 0.05: return "0.0M"
    return f"({abs(d):.1f}M)" if d < 0 else f"+{d:.1f}M"

def wow_dollar_plain(row):
    cur, prior = pn(sg(row, 17)), pn(sg(row, 27))
    if cur is None or prior is None: return "--"
    d = cur - prior
    if abs(d) < 0.5: return "$0"
    return f"(${abs(d):,.0f})" if d < 0 else f"+${d:,.0f}"

def wow_pct(row):
    """Format WoW for percentage metrics (monetization rate) in bps."""
    # Prefer col 28 (pre-computed delta)
    raw28 = sg(row, 28)
    if raw28:
        v = pn(raw28)
        if v is not None:
            bps = round(v) if "bps" in raw28 else round(v * 100)
            if abs(bps) < 1: return "0 bps"
            return f"({abs(bps)} bps)" if bps < 0 else f"+{bps} bps"
    # Fallback: compute from cols 17/27 with unit detection
    cur_raw, prior_raw = sg(row, 17), sg(row, 27)
    cur, prior = pn(cur_raw), pn(prior_raw)
    if cur is None or prior is None: return "--"
    # Col 27 may store as decimal (0.0179) while col 17 is percentage (1.79%)
    if "%" not in prior_raw and prior < 1 and cur > 1:
        prior = prior * 100
    d = (cur - prior) * 100  # percentage points → bps
    if abs(d) < 0.5: return "0 bps"
    return f"({abs(d):.0f} bps)" if d < 0 else f"+{d:.0f} bps"

def wow_gpv(row):
    """Format GPV WoW in millions for better precision."""
    # Prefer col 28 (pre-computed delta, already in millions)
    raw = sg(row, 28)
    if raw:
        v = pn(raw)
        if v is not None:
            if abs(v) < 0.5: return "+$0M"
            return f"(${abs(v):.0f}M)" if v < 0 else f"+${v:.0f}M"
    # Fallback: compute from pacing values (in billions → convert to millions)
    cur, prior = pn(sg(row, 17)), pn(sg(row, 27))
    if cur is None or prior is None: return "--"
    d = (cur - prior) * 1000
    if abs(d) < 0.5: return "+$0M"
    return f"(${abs(d):.0f}M)" if d < 0 else f"+${d:.0f}M"


# ═══════════════════════════════════════════════════════
# Main Extraction
# ═══════════════════════════════════════════════════════

def main():
    # Load data
    for path, name in [(PACING_JSON, "pacing"), (CORP_JSON, "corp model"), (CONSENSUS_JSON, "consensus")]:
        if not os.path.exists(path):
            print(f"ERROR: {path} not found. Run gdrive-cli sheets read for {name} first.")
            sys.exit(1)

    with open(PACING_JSON) as f:
        pacing = json.load(f)["values"]
    with open(CORP_JSON) as f:
        corp = json.load(f)["values"]
    with open(CONSENSUS_JSON) as f:
        cons = json.load(f)["values"]

    # ─── PACING SHEET (Page 1) — all label-based lookups ───
    # Section 1a: GP
    r_bgp = require_row(pacing, "Block gross profit", "pacing")
    bgp = pacing[r_bgp]; bgp_y = pacing[r_bgp + 1]
    r_cagp = require_row(pacing, "Cash App gross profit", "pacing")
    cagp = pacing[r_cagp]; cagp_y = pacing[r_cagp + 1]
    r_sqgp = require_row(pacing, "Square gross profit", "pacing")
    sqgp = pacing[r_sqgp]; sqgp_y = pacing[r_sqgp + 1]
    # Section 1b: AOI
    r_aoi = require_row(pacing, "Adjusted operating income", "pacing")
    aoi_r = pacing[r_aoi]; mar = pacing[r_aoi + 1]
    r_aoi_yoy = require_row(pacing, "Adj OI YoY %", "pacing")
    aoi_yoy_r = pacing[r_aoi_yoy]
    r_ro40 = require_row(pacing, "Rule of 40", "pacing")
    ro40 = pacing[r_ro40]
    # GP Net of Risk Loss
    r_gnrl = require_row(pacing, "Block Gross Profit Net of Risk Loss", "pacing")
    gnrl = pacing[r_gnrl]; gnrl_y = pacing[r_gnrl + 1]
    # Section 2: Cash App Inflows (label-based lookup)
    r_act = require_row(pacing, "Actives", "pacing", start=53)
    r_ipa = require_row(pacing, "Inflows per Active", "pacing", start=53)
    r_mon = require_row(pacing, "Monetization rate", "pacing", start=53)
    # Section 4: Square GPV (label-based lookup)
    r_gg = require_row(pacing, "Global GPV", "pacing", start=90)
    r_ug = require_row(pacing, "US GPV", "pacing", start=90)
    r_ig = require_row(pacing, "International GPV", "pacing", start=90)

    act = pacing[r_act]; act_y = pacing[r_act + 1]; act_d = pacing[r_act + 2]
    ipa = pacing[r_ipa]; ipa_y = pacing[r_ipa + 1]
    mon = pacing[r_mon]; mon_y = pacing[r_mon + 1]
    gg = pacing[r_gg]; gg_y = pacing[r_gg + 1]; gg_d = pacing[r_gg + 2]
    ug = pacing[r_ug]; ug_y = pacing[r_ug + 1]
    ig = pacing[r_ig]; ig_y = pacing[r_ig + 1]

    # Parse key values
    bgp_q1 = pn(sg(bgp, 17)); bgp_c = pn(sg(bgp, 21))
    bgp_vs = bgp_q1 - bgp_c if bgp_q1 and bgp_c else None
    aoi_q1 = pn(sg(aoi_r, 17)); aoi_c = pn(sg(aoi_r, 21))
    aoi_vs = aoi_q1 - aoi_c if aoi_q1 and aoi_c else None
    ro40_v = pn(sg(ro40, 17)); ro40_a = pn(sg(ro40, 18)); ro40_c = pn(sg(ro40, 21))
    # Guidance deltas (Block table only)
    bgp_guide = pn(sg(bgp, 20))
    bgp_vs_guide = bgp_q1 - bgp_guide if bgp_q1 and bgp_guide else None
    aoi_guide = pn(sg(aoi_r, 20))
    aoi_vs_guide = aoi_q1 - aoi_guide if aoi_q1 and aoi_guide else None
    mar_guide = pn(sg(mar, 20))
    q1_mar_pacing = pn(sg(mar, 17))
    ro40_guide = pn(sg(ro40, 20))

    # AOI Margin & Rule of 40 — YoY and Cons YoY (computed from raw values)
    # Raw pacing margin = AOI / GP (in millions, from pacing sheet)
    raw_margin_pacing = aoi_q1 / bgp_q1 * 100 if aoi_q1 and bgp_q1 else None
    raw_margin_cons = aoi_c / bgp_c * 100 if aoi_c and bgp_c else None
    # YoY: raw margin vs Q1 2025 actual margin
    margin_yoy = raw_margin_pacing - Q1_2025_MARGIN if raw_margin_pacing else None
    margin_cons_yoy = raw_margin_cons - Q1_2025_MARGIN if raw_margin_cons else None
    margin_vs_cons = raw_margin_pacing - raw_margin_cons if raw_margin_pacing and raw_margin_cons else None
    # Margin WoW: col 17 vs col 27 (col 27 may be decimal form)
    mar_prior_raw = sg(mar, 27)
    mar_prior = pn(mar_prior_raw)
    if mar_prior is not None and "%" not in mar_prior_raw and mar_prior < 1 and q1_mar_pacing and q1_mar_pacing > 1:
        mar_prior = mar_prior * 100
    margin_wow = q1_mar_pacing - mar_prior if q1_mar_pacing is not None and mar_prior is not None else None
    # Rule of 40 YoY
    ro40_yoy = ro40_v - Q1_2025_RO40 if ro40_v is not None else None
    ro40_cons_yoy = ro40_c - Q1_2025_RO40 if ro40_c is not None else None

    cagp_q1 = pn(sg(cagp, 17)); cagp_c = pn(sg(cagp, 21))
    cagp_vs = cagp_q1 - cagp_c if cagp_q1 and cagp_c else None
    sqgp_q1 = pn(sg(sqgp, 17)); sqgp_c = pn(sg(sqgp, 21))
    sqgp_vs = sqgp_q1 - sqgp_c if sqgp_q1 and sqgp_c else None
    act_q1 = pn(sg(act, 17)); act_c = pn(sg(act, 20))
    ipa_q1 = pn(sg(ipa, 17)); ipa_c = pn(sg(ipa, 20))
    mon_q1 = pn(sg(mon, 17)); mon_c = pn(sg(mon, 20))
    gg_q1 = pn(sg(gg, 17)); gg_c = pn(sg(gg, 20))
    ug_q1 = pn(sg(ug, 17)); ug_c = pn(sg(ug, 20))
    ig_q1 = pn(sg(ig, 17)); ig_c = pn(sg(ig, 20))
    gnrl_q1 = pn(sg(gnrl, 17)); gnrl_c = pn(sg(gnrl, 21))
    gnrl_vs = gnrl_q1 - gnrl_c if gnrl_q1 and gnrl_c else None
    gnrl_ap = pn(sg(gnrl, 18))

    # ─── MONTHLY BREAKDOWN (interactive chart + table) ───
    CY = [11, 12, 13]  # 2026 Actual (Jan, Feb) / Pacing (Mar)
    PL = [5, 6, 7]     # 2026 Annual Plan
    PY = [2, 3, 4]     # 2025 Prior Year Actual
    MLABELS = ["January", "February", "March (P)"]

    def build_monthly(mid, label, row, chart_type, unit, fmt_val, fmt_delta,
                      margin_row=None):
        """Build a monthly metric object with raw values for charting."""
        m = {"id": mid, "label": label, "chart_type": chart_type, "unit": unit, "months": []}
        for ml, cy, pl, py in zip(MLABELS, CY, PL, PY):
            cv = pn(sg(row, cy)); pv = pn(sg(row, pl)); pyv = pn(sg(row, py))
            delta = cv - pv if cv is not None and pv is not None else None
            yoy_v = ((cv - pyv) / pyv * 100) if cv and pyv and pyv != 0 else None
            plan_yoy_v = ((pv - pyv) / pyv * 100) if pv and pyv and pyv != 0 else None
            mo = {
                "label": ml,
                "value": fmt_val(cv) if callable(fmt_val) else (sg(row, cy) or "--"),
                "raw": round(cv, 2) if cv is not None else None,
                "plan_raw": round(pv, 2) if pv is not None else None,
                "vs_plan": fmt_delta(delta),
                "yoy": fmt_yoy(yoy_v), "yoy_raw": round(yoy_v, 1) if yoy_v is not None else None,
                "plan_yoy": fmt_yoy(plan_yoy_v), "plan_yoy_raw": round(plan_yoy_v, 1) if plan_yoy_v is not None else None,
            }
            if margin_row:
                mv = pn(sg(margin_row, cy)); mpv = pn(sg(margin_row, pl))
                mo["margin"] = fm(sg(margin_row, cy))
                mo["margin_raw"] = round(mv, 1) if mv is not None else None
                mo["plan_margin"] = fm(sg(margin_row, pl))
                mo["plan_margin_raw"] = round(mpv, 1) if mpv is not None else None
            m["months"].append(mo)
        return m

    monthly = []

    # Block Gross Profit
    monthly.append(build_monthly("block_gp", "Block Gross Profit", bgp, "yoy", "M", fM, fdD))

    # Cash App Gross Profit
    monthly.append(build_monthly("cashapp_gp", "Cash App Gross Profit", cagp, "yoy", "M", fM, fdD))

    # Square Gross Profit
    monthly.append(build_monthly("square_gp", "Square Gross Profit", sqgp, "yoy", "M", fM, fdD))

    # Cash App Actives
    def _fac_v(v): return fac(f"{v}M") if v is not None else "--"
    def _fd_act(v):
        if v is None: return "--"
        return f"({abs(v):.1f}M)" if v < 0 else f"+{v:.1f}M"
    monthly.append(build_monthly("actives", "Cash App Actives", act, "yoy", "M_users", _fac_v, _fd_act))

    # Global / US / International GPV
    def _fgpv(v): return f"${v:.1f}B" if v is not None else "--"
    def _fd_gpv(v):
        if v is None: return "--"
        return f"(${abs(v):.1f}B)" if v < 0 else f"+${v:.1f}B"
    for gpv_row, gpv_id, gpv_label in [
        (gg, "global_gpv", "Global GPV"), (ug, "us_gpv", "US GPV"), (ig, "intl_gpv", "International GPV")
    ]:
        monthly.append(build_monthly(gpv_id, gpv_label, gpv_row, "yoy", "B", _fgpv, _fd_gpv))

    # Inflows per Active
    def _fipa(v): return f"${v:,.0f}" if v is not None else "--"
    def _fd_ipa(v):
        if v is None: return "--"
        return f"(${abs(v):,.0f})" if v < 0 else f"+${v:,.0f}"
    monthly.append(build_monthly("ipa", "Inflows per Active", ipa, "yoy", "$", _fipa, _fd_ipa))

    # Monetization Rate
    def _fmon(v): return f"{v:.2f}%" if v is not None else "--"
    def _fd_mon(v):
        if v is None: return "--"
        bps = round(v * 100)
        if abs(bps) < 1: return "0 bps"
        return f"({abs(bps)} bps)" if bps < 0 else f"+{bps} bps"
    monthly.append(build_monthly("monetization", "Monetization Rate", mon, "yoy", "%", _fmon, _fd_mon))

    # Adjusted Operating Income (margin chart type)
    monthly.append(build_monthly("aoi", "Adjusted Operating Income", aoi_r, "margin", "M", fM, fdD,
                                 margin_row=mar))

    # ─── CORP MODEL (Q2-Q4 Internal Forecast) — label-based lookups ───
    # Cols 107-109 = Q2,Q3,Q4 forecast; Cols 102-104 = PY Q2-Q4 actuals
    rc_gp = require_row(corp, "Gross Profit", "corp model")
    rc_gp_yoy = require_row(corp, "YoY Gross Profit Growth %", "corp model")
    rc_risk = require_row(corp, "Risk Loss", "corp model")
    rc_aoi = require_row(corp, "Adjusted Operating Income (Loss)", "corp model")
    corp_gp = [pn(sg(corp[rc_gp], c)) for c in [107, 108, 109]]
    corp_gp_yoy = [sg(corp[rc_gp_yoy], c) for c in [107, 108, 109]]
    corp_aoi = [pn(sg(corp[rc_aoi], c)) for c in [107, 108, 109]]
    corp_risk = [pn(sg(corp[rc_risk], c)) for c in [107, 108, 109]]
    corp_gp_py = [pn(sg(corp[rc_gp], c)) for c in [102, 103, 104]]
    corp_risk_py = [pn(sg(corp[rc_risk], c)) for c in [102, 103, 104]]

    corp_gp_m = [v / 1e6 if v else None for v in corp_gp]
    corp_aoi_m = [v / 1e6 if v else None for v in corp_aoi]
    corp_gnrl_m = [(g - r) / 1e6 if g and r else None for g, r in zip(corp_gp, corp_risk)]

    corp_gnrl_yoy = []
    for i in range(3):
        cy = corp_gp[i] - corp_risk[i] if corp_gp[i] and corp_risk[i] else None
        py = corp_gp_py[i] - corp_risk_py[i] if corp_gp_py[i] and corp_risk_py[i] else None
        corp_gnrl_yoy.append((cy - py) / py * 100 if cy and py and py != 0 else None)

    # Corp AOI margin = AOI / GP * 100
    corp_aoi_margin = []
    for a, g in zip(corp_aoi, corp_gp):
        corp_aoi_margin.append(a / g * 100 if a and g and g != 0 else None)

    # ─── CONSENSUS MODEL — label-based lookups (col 1 has friendly names) ───
    rn_gp = require_row(cons, "Block Gross Profit", "consensus", col=1)
    rn_aoi = require_row(cons, "Adjusted Operating Income (Loss)", "consensus", col=1)
    rn_gnrl = require_row(cons, "Block Gross Profit (Less Risk Loss)", "consensus", col=1)
    cons_gp_m = [pn(sg(cons[rn_gp], c)) for c in [3, 4, 5]]
    cons_gp_yoy = [sg(cons[rn_gp + 1], c) for c in [3, 4, 5]]
    cons_aoi_m = [pn(sg(cons[rn_aoi], c)) for c in [3, 4, 5]]
    cons_aoi_margin = [pn(sg(cons[rn_aoi + 1], c)) for c in [3, 4, 5]]
    cons_gnrl_m = [pn(sg(cons[rn_gnrl], c)) for c in [3, 4, 5]]
    cons_gnrl_yoy = [sg(cons[rn_gnrl + 1], c) for c in [3, 4, 5]]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ─── BUILD FORWARD LOOK ───
    qf = []

    # Q1 from pacing sheet
    q1_aoi_margin = pn(sg(mar, 17))
    q1_cons_aoi_margin = pn(sg(mar, 21))
    qf.append({
        "quarter": "Q1",
        "block_gp": {
            "forecast": fB(bgp_q1), "yoy": fp(sg(bgp_y, 17)),
            "consensus": fB(bgp_c), "cons_yoy": fp(sg(bgp_y, 21)),
            "delta_dollar": fdD(bgp_vs), "delta_growth": gd(sg(bgp_y, 17), sg(bgp_y, 21))
        },
        "aoi": {
            "forecast": fM(aoi_q1), "margin": fmt_margin(q1_aoi_margin),
            "consensus": fM(aoi_c), "cons_margin": fmt_margin(q1_cons_aoi_margin),
            "delta_dollar": fdD(aoi_vs), "delta_margin": fmt_margin_delta(q1_aoi_margin, q1_cons_aoi_margin)
        },
        "gp_net_risk": {
            "forecast": fB(gnrl_q1), "yoy": fp(sg(gnrl_y, 17)),
            "consensus": fB(gnrl_c), "cons_yoy": fp(sg(gnrl_y, 21)),
            "delta_dollar": fdD(gnrl_vs), "delta_growth": gd(sg(gnrl_y, 17), sg(gnrl_y, 21))
        }
    })

    # Q2-Q4 from corp + consensus
    for i, q in enumerate(["Q2", "Q3", "Q4"]):
        int_gp = corp_gp_m[i]; con_gp = cons_gp_m[i]
        gp_delta = int_gp - con_gp if int_gp and con_gp else None
        int_gp_yoy = pn(corp_gp_yoy[i]); con_gp_yoy = pn(cons_gp_yoy[i])

        int_aoi = corp_aoi_m[i]; con_aoi = cons_aoi_m[i]
        aoi_delta = int_aoi - con_aoi if int_aoi and con_aoi else None

        int_gnrl = corp_gnrl_m[i]; con_gnrl = cons_gnrl_m[i]
        gnrl_delta = int_gnrl - con_gnrl if int_gnrl and con_gnrl else None
        con_gnrl_yoy_v = pn(cons_gnrl_yoy[i])

        qf.append({
            "quarter": q,
            "block_gp": {
                "forecast": fB(int_gp), "yoy": fmt_yoy(int_gp_yoy),
                "consensus": fB(con_gp), "cons_yoy": fmt_yoy(con_gp_yoy),
                "delta_dollar": fdD(gp_delta), "delta_growth": gd_v(int_gp_yoy, con_gp_yoy)
            },
            "aoi": {
                "forecast": fM(int_aoi), "margin": fmt_margin(corp_aoi_margin[i]),
                "consensus": fM(con_aoi), "cons_margin": fmt_margin(cons_aoi_margin[i]),
                "delta_dollar": fdD(aoi_delta),
                "delta_margin": fmt_margin_delta(corp_aoi_margin[i], cons_aoi_margin[i])
            },
            "gp_net_risk": {
                "forecast": fB(int_gnrl), "yoy": fmt_yoy(corp_gnrl_yoy[i]),
                "consensus": fB(con_gnrl), "cons_yoy": fp(cons_gnrl_yoy[i]),
                "delta_dollar": fdD(gnrl_delta),
                "delta_growth": gd_v(corp_gnrl_yoy[i], con_gnrl_yoy_v)
            }
        })

    # ─── BUILD FULL OUTPUT ───
    out = {
        "meta": {
            "generated_at": now, "quarter": "Q1", "year": 2026,
            "current_month": "March",
            "sheet_id": PACING_SHEET_ID,
            "is_placeholder": False
        },
        "takeaways": {
            "gp": {"value": fB(bgp_q1), "yoy": fp(sg(bgp_y, 17)), "vs_cons_dollar": fdD(bgp_vs)},
            "aoi": {"value": fM(aoi_q1), "margin": fm(sg(mar, 17)), "vs_cons_dollar": fdD(aoi_vs)},
            "additional": json.load(open(COMMENTARY_JSON)) if os.path.exists(COMMENTARY_JSON) else []
        },
        "block_scorecard": [
            {"label": "Block Gross Profit", "q1_pacing": fB(bgp_q1),
             "secondary": f"{fp(sg(bgp_y, 17))} YoY",
             "badge": f"{fdD(bgp_vs)} vs Cons", "accent": "black",
             "signal": sig(pd(bgp_q1, bgp_c)),
             "wow": fwd(sg(bgp, 28))},
            {"label": "Adjusted Operating Income", "q1_pacing": fM(aoi_q1),
             "secondary": f"{fm(sg(mar, 17))} margin",
             "badge": f"{fdD(aoi_vs)} vs Cons", "accent": "black",
             "signal": sig(pd(aoi_q1, aoi_c)),
             "wow": fwd(sg(aoi_r, 28))},
            {"label": "Rule of 40", "q1_pacing": sg(ro40, 17) or "--",
             "secondary": "",
             "badge": f"+{ro40_v - ro40_a:.0f} vs AP" if ro40_v and ro40_a else "--",
             "accent": "black",
             "signal": sig(ro40_v - ro40_a if ro40_v and ro40_a else None),
             "wow": fwp(sg(ro40, 28))}
        ],
        "block_table": {
            "columns": ["Metric", "Q1 Pacing", "WoW Δ", "YoY Growth", "Q1 AP",
                         "Q1 Guidance", "vs. Guide", "Q1 Consensus", "Cons YoY", "vs. Cons"],
            "rows": [
                {"metric": "Block Gross Profit", "pacing": fB(bgp_q1), "wow": fwd(sg(bgp, 28)),
                 "yoy": fp(sg(bgp_y, 17)), "ap": fB(pn(sg(bgp, 18))),
                 "guidance": fB(bgp_guide), "vs_guide": fdD(bgp_vs_guide),
                 "consensus": fB(bgp_c),
                 "cons_yoy": fp(sg(bgp_y, 21)), "vs_cons": fdD(bgp_vs),
                 "signal": sig(pd(bgp_q1, bgp_c))},
                {"metric": "Adjusted Operating Income", "pacing": fM(aoi_q1),
                 "wow": fwd(sg(aoi_r, 28)), "yoy": fp(sg(aoi_yoy_r, 17)),
                 "ap": fM(pn(sg(aoi_r, 18))), "guidance": fM(aoi_guide),
                 "vs_guide": fdD(aoi_vs_guide),
                 "consensus": fM(aoi_c), "cons_yoy": fp(sg(aoi_yoy_r, 21)),
                 "vs_cons": fdD(aoi_vs), "signal": sig(pd(aoi_q1, aoi_c))},
                {"metric": "AOI Margin", "pacing": fm(sg(mar, 17)),
                 "wow": (f"+{margin_wow:.0f} pts" if margin_wow is not None and margin_wow >= 0.5
                         else (f"({abs(margin_wow):.0f} pts)" if margin_wow is not None and margin_wow <= -0.5
                         else ("0 pts" if margin_wow is not None else "--"))),
                 "yoy": (f"+{margin_yoy:.0f} pts" if margin_yoy is not None and margin_yoy >= 0.5
                         else (f"({abs(margin_yoy):.0f} pts)" if margin_yoy is not None and margin_yoy <= -0.5
                         else ("0 pts" if margin_yoy is not None else "--"))),
                 "ap": fm(sg(mar, 18)), "guidance": fm(sg(mar, 20)),
                 "vs_guide": fmt_margin_delta(q1_mar_pacing, mar_guide),
                 "consensus": fm(sg(mar, 21)),
                 "cons_yoy": (f"+{margin_cons_yoy:.0f} pts" if margin_cons_yoy is not None and margin_cons_yoy >= 0.5
                              else (f"({abs(margin_cons_yoy):.0f} pts)" if margin_cons_yoy is not None and margin_cons_yoy <= -0.5
                              else ("0 pts" if margin_cons_yoy is not None else "--"))),
                 "vs_cons": (f"+{margin_vs_cons:.0f} pts" if margin_vs_cons is not None and margin_vs_cons >= 0.5
                             else (f"({abs(margin_vs_cons):.0f} pts)" if margin_vs_cons is not None and margin_vs_cons <= -0.5
                             else ("0 pts" if margin_vs_cons is not None else "--"))),
                 "signal": "neutral"},
                {"metric": "Rule of 40", "pacing": sg(ro40, 17) or "--",
                 "wow": fwp(sg(ro40, 28)),
                 "yoy": (f"+{ro40_yoy:.0f} pts" if ro40_yoy is not None and ro40_yoy >= 0.5
                         else (f"({abs(ro40_yoy):.0f} pts)" if ro40_yoy is not None and ro40_yoy <= -0.5
                         else ("0 pts" if ro40_yoy is not None else "--"))),
                 "ap": sg(ro40, 18) or "--", "guidance": sg(ro40, 20) or "--",
                 "vs_guide": (f"+{ro40_v - ro40_guide:.0f} pts" if ro40_v and ro40_guide and ro40_v >= ro40_guide
                              else (f"({abs(ro40_v - ro40_guide):.0f} pts)" if ro40_v and ro40_guide else "--")),
                 "consensus": sg(ro40, 21) or "--",
                 "cons_yoy": (f"+{ro40_cons_yoy:.0f} pts" if ro40_cons_yoy is not None and ro40_cons_yoy >= 0.5
                              else (f"({abs(ro40_cons_yoy):.0f} pts)" if ro40_cons_yoy is not None and ro40_cons_yoy <= -0.5
                              else ("0 pts" if ro40_cons_yoy is not None else "--"))),
                 "vs_cons": f"+{ro40_v - ro40_c:.0f} pts" if ro40_v and ro40_c else "--",
                 "signal": "neutral"},
                {"metric": "GP Net of Risk Loss", "pacing": fB(gnrl_q1), "wow": "--",
                 "yoy": fp(sg(gnrl_y, 17)), "ap": fB(gnrl_ap), "guidance": "--",
                 "vs_guide": "--",
                 "consensus": fB(gnrl_c), "cons_yoy": fp(sg(gnrl_y, 21)),
                 "vs_cons": fdD(gnrl_vs), "signal": sig(pd(gnrl_q1, gnrl_c))}
            ]
        },
        "brand_scorecard": [
            {"label": "Cash App Actives", "q1_pacing": fac(sg(act, 17)),
             "secondary": f"{fp(sg(act_y, 17))} YoY",
             "badge": f"{fp(sg(act_d, 17))} vs AP", "accent": "green",
             "signal": sig(pn(sg(act_d, 17))), "wow": wow_actives(act)},
            {"label": "Square Global GPV", "q1_pacing": sg(gg, 17),
             "secondary": f"{fpg(sg(gg_y, 17))} YoY",
             "badge": f"{fp(sg(gg_d, 17))} vs AP", "accent": "blue",
             "signal": sig(pn(sg(gg_d, 17))), "wow": wow_gpv(gg)}
        ],
        "cashapp_table": {
            "columns": ["Metric", "Q1 Pacing", "WoW Δ", "YoY Growth", "Q1 Consensus", "vs. Cons"],
            "rows": [
                {"metric": "Cash App Gross Profit", "pacing": fB(cagp_q1),
                 "wow": wow_dollar(cagp), "yoy": fp(sg(cagp_y, 17)),
                 "consensus": fB(cagp_c), "vs_comp": fdD(cagp_vs),
                 "signal": sig(pd(cagp_q1, cagp_c))},
                {"metric": "Cash App Actives", "pacing": fac(sg(act, 17)),
                 "wow": wow_actives(act), "yoy": fp(sg(act_y, 17)),
                 "consensus": fac(sg(act, 20)),
                 "vs_comp": f"{(act_q1 - act_c):+.1f}M" if act_q1 and act_c else "--",
                 "signal": sig(pd(act_q1, act_c))},
                {"metric": "Inflows per Active",
                 "pacing": f"${ipa_q1:,.0f}" if ipa_q1 else "--",
                 "wow": wow_dollar_plain(ipa), "yoy": fp(sg(ipa_y, 17)),
                 "consensus": f"${ipa_c:,.0f}" if ipa_c else "--",
                 "vs_comp": (f"+${ipa_q1 - ipa_c:,.0f}" if ipa_q1 and ipa_c and ipa_q1 >= ipa_c
                             else (f"(${abs(ipa_q1 - ipa_c):,.0f})" if ipa_q1 and ipa_c else "--")),
                 "signal": sig(pd(ipa_q1, ipa_c))},
                {"metric": "Monetization Rate", "pacing": sg(mon, 17) or "--",
                 "wow": wow_pct(mon), "yoy": fbps(sg(mon_y, 17)),
                 "consensus": sg(mon, 20) or "--",
                 "vs_comp": (f"+{(mon_q1 - mon_c) * 100:.0f} bps" if mon_q1 and mon_c and mon_q1 >= mon_c
                             else (f"({abs(mon_q1 - mon_c) * 100:.0f} bps)" if mon_q1 and mon_c else "--")),
                 "signal": sig((mon_q1 - mon_c) * 100 if mon_q1 and mon_c else None)}
            ]
        },
        "square_table": {
            "columns": ["Metric", "Q1 Pacing", "WoW Δ", "YoY Growth", "Q1 Consensus", "vs. Cons"],
            "rows": [
                {"metric": "Square Gross Profit", "pacing": fM(sqgp_q1),
                 "wow": wow_dollar(sqgp), "yoy": fp(sg(sqgp_y, 17)),
                 "consensus": fM(sqgp_c), "vs_comp": fdD(sqgp_vs),
                 "signal": sig(pd(sqgp_q1, sqgp_c))},
                {"metric": "Global GPV", "pacing": sg(gg, 17) or "--",
                 "wow": wow_gpv(gg), "yoy": fpg(sg(gg_y, 17)),
                 "consensus": sg(gg, 20) or "--",
                 "vs_comp": (f"+${gg_q1 - gg_c:.1f}B" if gg_q1 and gg_c and gg_q1 >= gg_c
                             else (f"(${abs(gg_q1 - gg_c):.1f}B)" if gg_q1 and gg_c else "--")),
                 "signal": sig(pd(gg_q1, gg_c))},
                {"metric": "US GPV", "pacing": sg(ug, 17) or "--",
                 "wow": wow_gpv(ug), "yoy": fp(sg(ug_y, 17)),
                 "consensus": sg(ug, 20) or "--",
                 "vs_comp": (f"+${ug_q1 - ug_c:.1f}B" if ug_q1 and ug_c and ug_q1 >= ug_c
                             else (f"(${abs(ug_q1 - ug_c):.1f}B)" if ug_q1 and ug_c else "--")),
                 "signal": sig(pd(ug_q1, ug_c))},
                {"metric": "International GPV", "pacing": sg(ig, 17) or "--",
                 "wow": wow_gpv(ig), "yoy": fpg(sg(ig_y, 17)),
                 "consensus": sg(ig, 20) or "--",
                 "vs_comp": (f"+${ig_q1 - ig_c:.1f}B" if ig_q1 and ig_c and ig_q1 >= ig_c
                             else (f"(${abs(ig_q1 - ig_c):.1f}B)" if ig_q1 and ig_c else "--")),
                 "signal": sig(pd(ig_q1, ig_c))}
            ]
        },
        "monthly_breakdown": monthly,
        "forward_look": {
            "available": True, "note": "",
            "quarterly_forecast": qf,
            "growth_comparisons": {}
        },
        "comments": load_comments()
    }

    # Write JS
    js = (f"// Dashboard data — generated {now}\n"
          f"// Source: pacing sheet + corp model + consensus model\n"
          f"const DASHBOARD_DATA = {json.dumps(out, indent=2)};\n")

    with open(OUTPUT_PATH, "w") as f:
        f.write(js)

    # Report
    print(f"✓ dashboard_data.js generated — {now}")
    print(f"  Output: {OUTPUT_PATH}")
    print()
    print("  Block Scorecard:")
    for c in out["block_scorecard"]:
        print(f"    {c['label']}: {c['q1_pacing']} | {c['badge']} [{c['signal']}]")
    print()
    print("  Forward Look (AOI):")
    for q in qf:
        m = q["aoi"]
        print(f"    {q['quarter']}'26: {m['forecast']} ({m['margin']}) vs {m['consensus']} ({m['cons_margin']}) | ${m['delta_dollar']} | {m['delta_margin']}")
    print()
    print("  Forward Look (GP NRL):")
    for q in qf:
        m = q["gp_net_risk"]
        print(f"    {q['quarter']}'26: {m['forecast']} ({m['yoy']}) vs {m['consensus']} ({m['cons_yoy']}) | {m['delta_dollar']}")


def load_comments():
    """Read comments from the Dashboard Comments sheet."""
    if not os.path.exists(COMMENTS_JSON):
        return []
    try:
        with open(COMMENTS_JSON) as f:
            data = json.load(f)
        raw = data.get("values", data) if isinstance(data, dict) else data
        if not raw or len(raw) < 2:
            return []
        # rows[0] is header: [Timestamp, Page, Author, Comment]
        comments = []
        for row in raw[1:]:
            if len(row) >= 4 and row[3]:
                comments.append({
                    "timestamp": str(row[0]),
                    "page": str(row[1]),
                    "author": str(row[2]),
                    "comment": str(row[3])
                })
        comments.reverse()  # most recent first
        return comments
    except Exception:
        return []


if __name__ == "__main__":
    main()
