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


def find_row(data, label, start=0):
    """Find row index by exact col B label match."""
    for i in range(start, len(data)):
        if len(data[i]) > 1 and str(data[i][1]).strip() == label:
            return i
    return None


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
    """Format WoW dollar delta."""
    if not s: return "--"
    v = pn(s)
    if v is None: return "--"
    return f"(${abs(v):.0f}M)" if v < 0 else f"+${v:.0f}M"

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
    cur, prior = pn(sg(row, 17)), pn(sg(row, 27))
    if cur is None or prior is None: return "--"
    d = (cur - prior) * 100
    if abs(d) < 0.5: return "0 bps"
    return f"({abs(d):.0f} bps)" if d < 0 else f"+{d:.0f} bps"

def wow_gpv(row):
    cur, prior = pn(sg(row, 17)), pn(sg(row, 27))
    if cur is None or prior is None: return "--"
    d = cur - prior
    if abs(d) < 0.05: return "$0.0B"
    return f"(${abs(d):.1f}B)" if d < 0 else f"+${d:.1f}B"


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

    # ─── PACING SHEET (Page 1) ───
    # Section 1a: GP
    bgp = pacing[12]; bgp_y = pacing[13]
    cagp = pacing[16]; cagp_y = pacing[17]
    sqgp = pacing[20]; sqgp_y = pacing[21]
    # Section 1b: AOI
    aoi_r = pacing[44]; mar = pacing[45]; aoi_yoy_r = pacing[51]; ro40 = pacing[48]
    # GP Net of Risk Loss
    gnrl = pacing[140]; gnrl_y = pacing[141]
    # Section 2: Cash App Inflows (dynamic row lookup)
    r_act = find_row(pacing, "Actives", 53)
    r_ipa = find_row(pacing, "Inflows per Active", 53)
    r_mon = find_row(pacing, "Monetization rate", 53)
    # Section 4: Square GPV (dynamic row lookup)
    r_gg = find_row(pacing, "Global GPV", 90)
    r_ug = find_row(pacing, "US GPV", 90)
    r_ig = find_row(pacing, "International GPV", 90)

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

    # ─── CORP MODEL (Q2-Q4 Internal Forecast) ───
    # Row 10=GP, Row 11=GP YoY, Row 15=Risk Loss, Row 76=AOI, Row 107=Rule of 40
    # Cols 107-109 = Q2,Q3,Q4 forecast; Cols 101-104 = PY Q1-Q4 actuals
    corp_gp = [pn(sg(corp[10], c)) for c in [107, 108, 109]]
    corp_gp_yoy = [sg(corp[11], c) for c in [107, 108, 109]]
    corp_aoi = [pn(sg(corp[76], c)) for c in [107, 108, 109]]
    corp_risk = [pn(sg(corp[15], c)) for c in [107, 108, 109]]
    corp_gp_py = [pn(sg(corp[10], c)) for c in [102, 103, 104]]
    corp_risk_py = [pn(sg(corp[15], c)) for c in [102, 103, 104]]

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

    # ─── CONSENSUS MODEL ───
    # Row 21=GP (cols 3-5=Q2-Q4), Row 22=GP YoY, Row 25=GP NRL, Row 26=NRL YoY
    # Row 36=AOI, Row 37=AOI Margin, Row 44=Rule of 40
    cons_gp_m = [pn(sg(cons[21], c)) for c in [3, 4, 5]]
    cons_gp_yoy = [sg(cons[22], c) for c in [3, 4, 5]]
    cons_aoi_m = [pn(sg(cons[36], c)) for c in [3, 4, 5]]
    cons_aoi_margin = [pn(sg(cons[37], c)) for c in [3, 4, 5]]
    cons_gnrl_m = [pn(sg(cons[25], c)) for c in [3, 4, 5]]
    cons_gnrl_yoy = [sg(cons[26], c) for c in [3, 4, 5]]

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
            "forecast": fB(gnrl_q1), "yoy": fpg(sg(gnrl_y, 17)),
            "consensus": fB(gnrl_c), "cons_yoy": fpg(sg(gnrl_y, 21)),
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
                "consensus": fB(con_gnrl), "cons_yoy": fpg(cons_gnrl_yoy[i]),
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
            "aoi": {"value": fM(aoi_q1), "margin": fm(sg(mar, 17)), "vs_cons_dollar": fdD(aoi_vs)}
        },
        "block_scorecard": [
            {"label": "Block Gross Profit", "q1_pacing": fB(bgp_q1),
             "secondary": f"{fp(sg(bgp_y, 17))} YoY",
             "badge": f"{fdD(bgp_vs)} vs Cons", "signal": sig(pd(bgp_q1, bgp_c)),
             "wow": fwd(sg(bgp, 28))},
            {"label": "Adjusted Operating Income", "q1_pacing": fM(aoi_q1),
             "secondary": f"{fm(sg(mar, 17))} margin",
             "badge": f"{fdD(aoi_vs)} vs Cons", "signal": sig(pd(aoi_q1, aoi_c)),
             "wow": fwd(sg(aoi_r, 28))},
            {"label": "Rule of 40", "q1_pacing": sg(ro40, 17) or "--",
             "secondary": "",
             "badge": f"+{ro40_v - ro40_a:.0f} vs AP" if ro40_v and ro40_a else "--",
             "signal": sig(ro40_v - ro40_a if ro40_v and ro40_a else None),
             "wow": fwp(sg(ro40, 28))}
        ],
        "block_table": {
            "columns": ["Metric", "Q1 Pacing", "WoW Δ", "YoY Growth", "Q1 AP",
                         "Q1 Guidance", "Q1 Consensus", "Cons YoY", "vs. Cons"],
            "rows": [
                {"metric": "Block Gross Profit", "pacing": fB(bgp_q1), "wow": fwd(sg(bgp, 28)),
                 "yoy": fp(sg(bgp_y, 17)), "ap": fB(pn(sg(bgp, 18))),
                 "guidance": fB(pn(sg(bgp, 20))), "consensus": fB(bgp_c),
                 "cons_yoy": fp(sg(bgp_y, 21)), "vs_cons": fdD(bgp_vs),
                 "signal": sig(pd(bgp_q1, bgp_c))},
                {"metric": "Adjusted Operating Income", "pacing": fM(aoi_q1),
                 "wow": fwd(sg(aoi_r, 28)), "yoy": fp(sg(aoi_yoy_r, 17)),
                 "ap": fM(pn(sg(aoi_r, 18))), "guidance": fM(pn(sg(aoi_r, 20))),
                 "consensus": fM(aoi_c), "cons_yoy": fp(sg(aoi_yoy_r, 21)),
                 "vs_cons": fdD(aoi_vs), "signal": sig(pd(aoi_q1, aoi_c))},
                {"metric": "AOI Margin", "pacing": fm(sg(mar, 17)), "wow": "--", "yoy": "--",
                 "ap": fm(sg(mar, 18)), "guidance": fm(sg(mar, 20)),
                 "consensus": fm(sg(mar, 21)), "cons_yoy": "--", "vs_cons": "--",
                 "signal": "neutral"},
                {"metric": "Rule of 40", "pacing": sg(ro40, 17) or "--",
                 "wow": fwp(sg(ro40, 28)), "yoy": "--",
                 "ap": sg(ro40, 18) or "--", "guidance": sg(ro40, 20) or "--",
                 "consensus": sg(ro40, 21) or "--", "cons_yoy": "--",
                 "vs_cons": f"+{ro40_v - ro40_c:.0f} pts" if ro40_v and ro40_c else "--",
                 "signal": "neutral"},
                {"metric": "GP Net of Risk Loss", "pacing": fB(gnrl_q1), "wow": "--",
                 "yoy": fpg(sg(gnrl_y, 17)), "ap": fB(gnrl_ap), "guidance": "--",
                 "consensus": fB(gnrl_c), "cons_yoy": fpg(sg(gnrl_y, 21)),
                 "vs_cons": fdD(gnrl_vs), "signal": sig(pd(gnrl_q1, gnrl_c))}
            ]
        },
        "brand_scorecard": [
            {"label": "Cash App Actives", "q1_pacing": fac(sg(act, 17)),
             "secondary": f"{fp(sg(act_y, 17))} YoY",
             "badge": f"{fp(sg(act_d, 17))} vs AP",
             "signal": "green", "wow": wow_actives(act)},
            {"label": "Square Global GPV", "q1_pacing": sg(gg, 17),
             "secondary": f"{fpg(sg(gg_y, 17))} YoY",
             "badge": f"{fp(sg(gg_d, 17))} vs AP",
             "signal": "blue", "wow": wow_gpv(gg)}
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
        "forward_look": {
            "available": True, "note": "",
            "quarterly_forecast": qf,
            "growth_comparisons": {}
        }
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


if __name__ == "__main__":
    main()
