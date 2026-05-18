#!/usr/bin/env python3
"""Build the monthly flash narrative markdown from a /flash-data packet.

Consumes /tmp/flash_out_{month}.json (output of flash_data.py). Produces a
markdown file ready to insert into the Google Doc Claude tab.

Driver attribution rules:
  - Driver inclusion: abs(line_delta vs OL) >= $2M OR >= 5% of bucket total
  - Top 2-3 per bucket by abs delta, ranked desc
  - "Corp to include context" appended when bucket variance >= $20M abs OR >= 10%
  - nm rule passes through from helper formatting (variances > 1000% display as nm)

Usage:
  python3 build_narrative.py --packet /tmp/apr26_out.json --period "Apr'26" \
    --ol-label "Q2OL" --output /path/to/flash_2026_04.md
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import date
from typing import Any

# Shared formatting helper — keep precision rule + table populator in sync.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from populate_flash_table import reformat_variance  # noqa: E402

DRIVER_INCLUSION_DOLLAR_MIN = 2_000_000
DRIVER_INCLUSION_PCT_MIN = 0.05  # 5% of bucket
CORP_CONTEXT_DOLLAR_MIN = 20_000_000
CORP_CONTEXT_PCT_MIN = 0.10  # 10% variance

# Variance precision rule: |magnitude| ≤ 10 → 1 decimal; > 10 → integer.
# Applied to $M / % / pts variances. Mirrors populate_flash_table.reformat_variance.
PRECISION_RULE_THRESHOLD = 10.0


MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


def parse_period(period: str) -> tuple[str, str, int, int]:
    """Parse "Apr'26" → (month name, prior month name, month num, year)."""
    parts = period.replace("'", "").strip().split()
    mon_abbr = parts[0][:3]
    year_short = int(parts[0][-2:])
    full_year = 2000 + year_short
    abbr_to_num = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                   "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
    mnum = abbr_to_num[mon_abbr]
    prior_num = mnum - 1 if mnum > 1 else 12
    return MONTH_NAMES[mnum], MONTH_NAMES[prior_num], mnum, full_year


def quarter_of(month_num: int) -> int:
    """Return 1..4 for the given month number."""
    return (month_num - 1) // 3 + 1


def is_quarter_end(month_num: int) -> bool:
    """Return True if month is quarter-end (Mar, Jun, Sep, Dec)."""
    return month_num in (3, 6, 9, 12)


def detect_mode(month_num: int, override: str | None = None) -> str:
    """Determine 'monthly' or 'quarterly' from month number, with optional override."""
    if override in ("monthly", "quarterly"):
        return override
    return "quarterly" if is_quarter_end(month_num) else "monthly"


def get_row(table: list[list[Any]], row_offset: int) -> list[Any]:
    """Return a row's 7 data cells (skipping the label) from a 28×8 or 37×7 table."""
    return table[row_offset][1:]


def cell(row: list[Any], col: int) -> str:
    """Safe getter for a formatted cell."""
    v = row[col] if col < len(row) else ""
    return str(v) if v not in (None, "") else ""


def to_narrative_sign(s: str) -> str:
    """Convert a reformatted variance to narrative form:
    - "(X)" → "-X"
    - "X" (no leading sign) → "+X"
    - "+X" / "-X" → unchanged
    Empty / neutral tokens pass through.
    """
    s = s.strip()
    if not s or s in ("--", "nm", "N/A", "n/a", "NA"):
        return s
    if s.startswith("(") and s.endswith(")"):
        return "-" + s[1:-1]
    if s.startswith("+") or s.startswith("-"):
        return s
    return "+" + s


def combine(pct: str, dollar: str) -> str:
    """Flash format: % first, $ in parens. "+2.4%" + "+$24M" → "+2.4% (+$24M)".

    Order is pct first (per Nick's saved feedback). Either arg can be empty.
    """
    if not pct and not dollar:
        return ""
    if not dollar:
        return pct
    if not pct:
        return dollar
    return f"{pct} ({dollar})"


def variance_phrase(pct: str, dollar: str, bench: str) -> str:
    """Build "+X% (+$Y) above bench" or "-X% (-$Y) below bench".
    Direction inferred from sign. When pct and dollar disagree on sign — typical when
    base is negative (e.g. Proto GP) — fall back to dollar only since pct is unreliable.
    """
    if pct and dollar:
        pct_neg = pct.startswith("-") or pct.startswith("(")
        dollar_neg = dollar.startswith("-") or dollar.startswith("(")
        if pct_neg != dollar_neg:
            pct = ""  # drop pct, use dollar only
    body = combine(pct, dollar)
    if not body:
        return f"vs. {bench}"
    sign_indicator = pct or dollar
    is_neg = sign_indicator.startswith("-") or sign_indicator.startswith("(")
    direction = "below" if is_neg else "above"
    return f"{body} {direction} {bench}"


# Variable / Acquisition / Fixed leaf line items keyed by display name + raw_derived prefix
VARIABLE_LEAVES = [
    ("P2P", "opex_p2p"),
    ("Risk Loss", "opex_risk_loss"),
    ("Card Issuance", "opex_card_issuance"),
    ("Warehouse Financing", "opex_warehouse_financing"),
    ("Hardware Logistics", "opex_hw_logistics"),
    ("Bad Debt Expense", "opex_bad_debt"),
    ("Customer Reimbursements", "opex_customer_reimbursements"),
]
ACQUISITION_LEAVES = [
    ("Marketing", "opex_marketing"),
    ("Onboarding Costs", "opex_onboarding"),
    ("Partnership Fees", "opex_partnership_fees"),
    ("Reader Expense", "opex_reader_expense"),
    ("Sales & Marketing People", "opex_sales_marketing_people"),
]
FIXED_LEAVES = [
    ("Product Development People", "opex_prod_dev_people"),
    ("G&A People (ex. CS)", "opex_ga_people_ex_cs"),
    ("Customer Support People", "opex_customer_support_people"),
    ("Software", "opex_software"),
    ("Cloud fees", "opex_cloud_fees"),
    ("Taxes, Insurance & Other Corp", "opex_taxes_insurance"),
    ("Legal fees", "opex_legal_fees"),
    ("Other Professional Services", "opex_other_prof_services"),
    ("Rent, Facilities, Equipment", "opex_rent_facilities"),
    ("Travel & Entertainment", "opex_travel_entertainment"),
    ("Hardware Production Costs", "opex_hw_production"),
    ("Non-Cash expenses (ex. SBC)", "opex_non_cash_ex_sbc"),
]


def _half_up(x: float) -> int:
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def fmt_driver_delta(d: float) -> str:
    """Format a $ delta in $M per the ±10 rule. Explicit +/- sign, no parens.
    - |Δ| ≤ $10M → 1 decimal in $M (e.g. "+$5.8M", "-$0.5M")
    - |Δ| >  $10M → integer in $M  (e.g. "+$18M", "-$26M")
    Always $M units (matches Flash style — no $K fallback for sub-$1M values).
    """
    abs_v = abs(d)
    sign = "+" if d >= 0 else "-"
    millions = abs_v / 1_000_000
    if millions <= PRECISION_RULE_THRESHOLD:
        return f"{sign}${millions:.1f}M"
    return f"{sign}${_half_up(millions)}M"


def fmt_driver_pct(p: float) -> str:
    """Format a % delta per the ±10 rule. Explicit +/- sign.
    - |p| ≤ 10%  → 1 decimal (e.g. "+5.8%")
    - |p| >  10% → integer   (e.g. "+29%", "-26%")
    """
    pct = p * 100.0
    sign = "+" if pct >= 0 else "-"
    abs_pct = abs(pct)
    if abs_pct <= PRECISION_RULE_THRESHOLD:
        return f"{sign}{abs_pct:.1f}%"
    return f"{sign}{_half_up(abs_pct)}%"


def force_signed(s: str) -> str:
    """Force an explicit + prefix on a positive variance/rate (e.g., '22.6%' → '+22.6%').
    Leaves '--' / 'nm' / empty alone. Used on YoY rates which the sheet emits as positive
    bare numbers but Flash format wants signed.
    """
    s = s.strip()
    if not s or s in ("--", "nm", "N/A", "n/a", "NA"):
        return s
    if s.startswith(("+", "-", "(")):
        # parens means negative → convert to -X
        if s.startswith("(") and s.endswith(")"):
            return "-" + s[1:-1]
        return s
    return "+" + s


def margin_pct(numerator: float | None, denominator: float | None) -> str:
    """Compute margin as numerator/denominator, format per ±10 rule. Returns '' if undefined."""
    if numerator is None or denominator in (None, 0):
        return ""
    m = numerator / denominator * 100.0
    abs_m = abs(m)
    sign = "" if m >= 0 else "-"  # margins don't get explicit "+"; negative gets "-"
    if abs_m <= PRECISION_RULE_THRESHOLD:
        return f"{sign}{abs_m:.1f}%"
    return f"{sign}{_half_up(abs_m)}%"


def pick_drivers(raw: dict, bucket_total_actual: float, leaves: list[tuple[str, str]]) -> list[dict]:
    """Compute deltas for each leaf and pick top 2-3 that pass materiality."""
    candidates = []
    for label, prefix in leaves:
        actual = raw.get(f"{prefix}_actual")
        ol = raw.get(f"{prefix}_ol")
        if actual is None or ol is None:
            continue
        delta = actual - ol
        pct = delta / ol if ol else 0
        candidates.append({
            "label": label,
            "delta": delta,
            "pct": pct,
            "abs": abs(delta),
        })
    # Filter by materiality
    filtered = [
        c for c in candidates
        if c["abs"] >= DRIVER_INCLUSION_DOLLAR_MIN
        or (bucket_total_actual and c["abs"] / bucket_total_actual >= DRIVER_INCLUSION_PCT_MIN)
    ]
    filtered.sort(key=lambda c: c["abs"], reverse=True)
    return filtered[:3]


def bucket_commentary(bucket_name: str, raw: dict, actual_key: str, ol_key: str,
                      leaves: list[tuple[str, str]], ol_label: str) -> str:
    """Build the bullet line for one V/A/F bucket including driver commentary."""
    actual = raw.get(actual_key)
    ol = raw.get(ol_key)
    if actual is None:
        return f"- **{bucket_name}** were unavailable for this period."

    bucket_delta = actual - ol if ol is not None else None
    bucket_pct = bucket_delta / ol if (bucket_delta is not None and ol) else None

    # Format the headline. Bucket Actuals are large ($MM+) and aren't variances,
    # so they pass through as integer $M. Variance follows Flash format:
    # "+X% (+$Y) above bench" / "-X% (-$Y) below bench" — pct first, $ in parens.
    actual_fmt = f"${_half_up(actual/1_000_000)}M"
    if bucket_delta is not None:
        delta_fmt = fmt_driver_delta(bucket_delta)
        pct_fmt = fmt_driver_pct(bucket_pct) if bucket_pct is not None else ""
        direction = "below" if bucket_delta < 0 else "above"
        if pct_fmt and delta_fmt:
            variance = f"{pct_fmt} ({delta_fmt})"
        else:
            variance = pct_fmt or delta_fmt
        headline = f"**{bucket_name}** were {actual_fmt}, {variance} {direction} {ol_label}"
    else:
        headline = f"**{bucket_name}** were {actual_fmt}"

    # Driver call-outs
    drivers = pick_drivers(raw, actual, leaves) if actual else []
    if drivers:
        # Separate positive / negative for "partially offset by" framing
        bucket_dir = 1 if bucket_delta and bucket_delta >= 0 else -1
        same_dir = [d for d in drivers if (d["delta"] >= 0) == (bucket_dir > 0)]
        opp_dir = [d for d in drivers if (d["delta"] >= 0) != (bucket_dir > 0)]

        same_strs = [f"{d['label']} ({fmt_driver_delta(d['delta'])} / {fmt_driver_pct(d['pct'])})"
                     for d in same_dir]
        opp_strs = [f"{d['label']} ({fmt_driver_delta(d['delta'])} / {fmt_driver_pct(d['pct'])})"
                    for d in opp_dir]

        parts = []
        if same_strs:
            parts.append("driven by " + ", ".join(same_strs))
        if opp_strs:
            parts.append("partially offset by " + ", ".join(opp_strs))
        driver_phrase = "; ".join(parts) if parts else ""
        if driver_phrase:
            headline += f", {driver_phrase}"

    # Corp-context flag
    if bucket_delta is not None:
        corp_flag = (
            abs(bucket_delta) >= CORP_CONTEXT_DOLLAR_MIN
            or (bucket_pct is not None and abs(bucket_pct) >= CORP_CONTEXT_PCT_MIN)
        )
        if corp_flag:
            headline += ". **Corp to include context.**"
        else:
            headline += "."
    else:
        headline += "."

    return "- " + headline


def format_pct(v: float | None, *, signed: bool = False) -> str:
    if v is None:
        return ""
    pct = v * 100
    if signed:
        return f"{'+' if pct >= 0 else '-'}{abs(pct):.1f}%"
    return f"{abs(pct):.1f}%" + ("" if pct >= 0 else " (negative)")


def build_narrative(packet: dict, period: str, ol_label: str, ol_year: int, mode: str = "monthly") -> str:
    """Construct the full markdown narrative.
    mode: "monthly" — uses month name + prior-month YoY parentheticals (M-S sheet view).
          "quarterly" — uses "Q1/Q2/Q3/Q4" labels + no prior-month YoY (T-Y sheet view).
    """
    raw = packet["raw_derived"]
    flash_t = packet["flash_table_formatted"]
    month, prior_month, mnum, year = parse_period(period)
    qtr = quarter_of(mnum)
    is_quarterly = (mode == "quarterly")
    # Period label used in narrative ("April" vs "Q2")
    period_label = f"Q{qtr}" if is_quarterly else month
    # Period label with year ("April 2026" vs "Q2 2026")
    period_long = f"Q{qtr} {year}" if is_quarterly else f"{month} {year}"

    # Convenience accessors for formatted flash cells (skipping label col)
    # Row offsets (0-indexed in the 28-row table)
    F = {
        "cash_actives": 2, "cash_inflows_pa": 3, "commerce_gmv": 4,
        "sq_gpv": 5, "sq_us": 6, "sq_intl": 7,
        "block_gp": 10, "ca_gp": 11,
        "ca_commerce": 12, "ca_borrow": 13, "ca_card": 14, "ca_id": 15, "ca_bnpl": 16,
        "sq_gp": 17, "sq_us_pmt": 18, "sq_intl_pmt": 19, "sq_banking": 20, "sq_saas": 21, "sq_hw": 22,
        "tidal": 23, "proto": 24,
        "adj_opex": 25, "adj_oi": 26, "r40": 27,
    }
    # Col indices (after stripping label): 0=Actual, 1=vs OL $, 2=vs OL %, 3=vs AP $, 4=vs AP %, 5=YoY, 6=PriorMoYoY
    A, OL_D, OL_P, AP_D, AP_P, YOY, PMYOY = 0, 1, 2, 3, 4, 5, 6

    def f(metric: str, col: int) -> str:
        return cell(get_row(flash_t, F[metric]), col)

    # Variance cols: ±10 precision rule (reformat_variance) THEN convert parens → +/- sign
    # for narrative form. YoY cols: just force "+" prefix on positives.
    VARIANCE_COLS = {OL_D, OL_P, AP_D, AP_P}
    YOY_COLS = {YOY, PMYOY}

    def v(metric: str, col: int) -> str:
        """Narrative-form variance value: signed +/-, precision rule applied.
        Same rule used for YoY columns per Flash convention (e.g. '+23% YoY', '+2.0% YoY').
        """
        raw_val = f(metric, col)
        if col in VARIANCE_COLS or col in YOY_COLS:
            return to_narrative_sign(reformat_variance(raw_val))
        return raw_val

    # Primary comparison anchor: OL during the active outlook quarter (Q2/Q3/Q4),
    # AP only during Q1 (where AP == Q1's plan). The OL label is passed in via
    # --ol-label. We use OL deltas everywhere as the primary anchor; AP appears
    # supplementally on Adj Opex + R40 (per Flash convention).
    def _delta(metric: str, scenario: str) -> float:
        """scenario ∈ {'ol', 'ap'}. Returns actual - scenario_value, or 0 if missing."""
        actual = raw.get(f"{metric}_actual")
        target = raw.get(f"{metric}_{scenario}")
        if actual is None or target is None:
            return 0.0
        return actual - target

    # Brand bridge uses OL deltas (matches the primary anchor on the Block GP line).
    ca_ol_d_raw = _delta("cash_app_gp", "ol")
    sq_ol_d_raw = _delta("square_gp", "ol")
    tidal_ol_d_raw = _delta("tidal_gp", "ol")
    proto_ol_d_raw = _delta("proto_gp", "ol")
    other_brands_raw = tidal_ol_d_raw + proto_ol_d_raw
    brand_bridge = (
        f"Cash App {fmt_driver_delta(ca_ol_d_raw)}, "
        f"Square {fmt_driver_delta(sq_ol_d_raw)}, "
        f"Other Brands {fmt_driver_delta(other_brands_raw)}"
    )

    # AOI margin (vs Block GP, per Flash convention)
    aoi_margin = margin_pct(raw.get("adj_oi_actual"), raw.get("block_gp_actual"))

    # Sub-product attribution: ranked by OL delta (positive first, negatives "partially offset")
    ca_subs = [
        ("Commerce", _delta("commerce_gp", "ol")),
        ("Borrow", _delta("borrow_gp", "ol")),
        ("Cash App Card", _delta("cash_app_card_gp", "ol")),
        ("Instant Deposit", _delta("instant_deposit_gp", "ol")),
        ("Post-Purchase BNPL", _delta("post_purchase_bnpl_gp", "ol")),
    ]
    ca_pos = sorted([s for s in ca_subs if s[1] > 0], key=lambda s: s[1], reverse=True)
    ca_neg = sorted([s for s in ca_subs if s[1] < 0], key=lambda s: s[1])

    def fmt_sub(items):
        return ", ".join(f"{name} ({fmt_driver_delta(d)})" for name, d in items)

    ca_outperf = []
    if ca_pos:
        ca_outperf.append(fmt_sub(ca_pos))
    if ca_neg:
        ca_outperf.append("partially offset by " + fmt_sub(ca_neg))
    ca_outperf_phrase = "; ".join(ca_outperf)

    sq_subs = [
        ("US Payments", _delta("us_payments_gp", "ol")),
        ("INTL Payments", _delta("intl_payments_gp", "ol")),
        ("Banking", _delta("banking_gp", "ol")),
        ("SaaS", _delta("saas_gp", "ol")),
        ("Hardware", _delta("hardware_gp", "ol")),
    ]
    sq_pos = sorted([s for s in sq_subs if s[1] > 0], key=lambda s: s[1], reverse=True)
    sq_neg = sorted([s for s in sq_subs if s[1] < 0], key=lambda s: s[1])

    sq_outperf = []
    if sq_pos:
        sq_outperf.append(fmt_sub(sq_pos))
    if sq_neg:
        sq_outperf.append("partially offset by " + fmt_sub(sq_neg))
    sq_outperf_phrase = "; ".join(sq_outperf)

    # Derived metrics: Block Variable Profit (= GP - Total Variable Costs)
    #                  GAAP Operating Income (= GP - Total GAAP OpEx)
    # Both shown with margin (% of Block GP). YoY is held until opex_total_*_yoy_prior
    # gets sourced in flash_data.py (currently missing → opex_total_variable_yoy_prior is None).
    def _vp_or_oi(component_key: str, scen: str) -> float | None:
        gp = raw.get(f"block_gp_{scen}")
        opex = raw.get(f"{component_key}_{scen}")
        if gp is None or opex is None:
            return None
        return gp - opex

    vp_actual = _vp_or_oi("opex_total_variable", "actual")
    vp_ol = _vp_or_oi("opex_total_variable", "ol")
    vp_margin = margin_pct(vp_actual, raw.get("block_gp_actual"))
    vp_delta_ol = (vp_actual - vp_ol) if (vp_actual is not None and vp_ol is not None) else None
    vp_pct_ol = (vp_delta_ol / vp_ol) if (vp_delta_ol is not None and vp_ol) else None

    gaap_oi_actual = _vp_or_oi("opex_total_gaap", "actual")
    gaap_oi_margin = margin_pct(gaap_oi_actual, raw.get("block_gp_actual"))

    def fmt_dollar_M(d: float | None) -> str:
        if d is None:
            return ""
        abs_v = abs(d) / 1_000_000
        sign = "+" if d >= 0 else "-"
        if abs_v <= PRECISION_RULE_THRESHOLD:
            return f"{sign}${abs_v:.1f}M"
        return f"{sign}${_half_up(abs_v)}M"

    if vp_actual is not None:
        vp_actual_fmt = f"${_half_up(vp_actual / 1_000_000)}M"
        if vp_delta_ol is not None and vp_pct_ol is not None:
            vp_phrase = variance_phrase(fmt_driver_pct(vp_pct_ol), fmt_dollar_M(vp_delta_ol), ol_label)
            vp_margin_phrase = f" ({vp_margin} margin)" if vp_margin else ""
            vp_line = f"**Block variable profit** landed at {vp_actual_fmt} in {period_label}{vp_margin_phrase}, {vp_phrase}."
        else:
            vp_line = f"**Block variable profit** landed at {vp_actual_fmt} in {period_label}."
    else:
        vp_line = ""

    if gaap_oi_actual is not None:
        gaap_oi_fmt = f"${_half_up(gaap_oi_actual / 1_000_000)}M"
        gaap_oi_margin_phrase = f" ({gaap_oi_margin} margin)" if gaap_oi_margin else ""
        gaap_oi_line = f"**GAAP operating income** landed at {gaap_oi_fmt} in {period_label}{gaap_oi_margin_phrase}."
    else:
        gaap_oi_line = ""

    # AP-supplementary phrasing for Adj Opex (e.g. "and -$117M below AP") and R40
    adj_opex_ap_delta_raw = _delta("adj_opex", "ap")  # may need different key — fallback below
    if adj_opex_ap_delta_raw == 0 and raw.get("adj_opex_ap") is None:
        # Adj Opex AP may not exist directly; derive from GP - AOI = Adj Opex
        gp_ap = raw.get("block_gp_ap")
        oi_ap = raw.get("adj_oi_ap")
        if gp_ap is not None and oi_ap is not None:
            adj_opex_ap = gp_ap - oi_ap
            adj_opex_actual = raw.get("adj_opex_actual")
            if adj_opex_actual is not None:
                adj_opex_ap_delta_raw = adj_opex_actual - adj_opex_ap
    adj_opex_ap_phrase = ""
    if adj_opex_ap_delta_raw:
        direction = "below" if adj_opex_ap_delta_raw < 0 else "above"
        adj_opex_ap_phrase = f", and {fmt_driver_delta(adj_opex_ap_delta_raw)} {direction} AP"

    # R40 AP-supplementary: read the AP pts directly from flash table col AP_P (e.g. "+16 pts").
    # Direction is sign-aware so the narrative reads correctly when R40 underperforms AP.
    r40_ap_str = v("r40", AP_P)
    r40_ap_direction = "below" if r40_ap_str.startswith("-") else "above"

    # V/A/F bucket commentary
    var_bullet = bucket_commentary("Variable costs", raw, "opex_total_variable_actual",
                                    "opex_total_variable_ol", VARIABLE_LEAVES, ol_label)
    acq_bullet = bucket_commentary("Acquisition costs", raw, "opex_total_acquisition_actual",
                                    "opex_total_acquisition_ol", ACQUISITION_LEAVES, ol_label)
    # Fixed total is derived from total - var - acq (see flash_data.py)
    fix_bullet = bucket_commentary("Fixed costs", raw, "opex_total_fixed_actual",
                                    "opex_total_fixed_ol", FIXED_LEAVES, ol_label)

    aoi_margin_phrase = f" ({aoi_margin} margin)" if aoi_margin else ""

    # Conditional "(prior-mo YoY in {prior_month})" parenthetical — monthly only.
    def pmyoy_paren(metric: str) -> str:
        if is_quarterly:
            return ""
        return f" ({v(metric, PMYOY)} in {prior_month})"

    # Disclaimer wording: in Q1 we reference AP; in Q2+ reference the active OL.
    disclaimer_anchor = "Annual Plan" if (ol_label == "AP" or qtr == 1) else f"Q{qtr} Outlook"

    md = f"""# Block Topline Flash: {period_long}

*This flash report provides a preliminary view of month-end close results, with figures subject to further review and potential adjustment. This streamlined report includes minimal commentary, as a more comprehensive analysis of underlying drivers will be provided in the* ***Monthly Management Reporting Pack scheduled for [MRP DATE]***.

*Please note that the flash topline aligns with our externally reported guidelines, which include Cash App Pay Gross Profit within Cash App excluding Commerce. All comparisons reference {year} {disclaimer_anchor} unless otherwise noted. Variances in charts are not color coded for amounts within +/- 1%, $0.5M, or YoY comparisons.*

## {period_long} Summary

**Block gross profit** was {f("block_gp", A)} in {period_label}, growing {v("block_gp", YOY)} YoY{pmyoy_paren("block_gp")} and landing {variance_phrase(v("block_gp", OL_P), v("block_gp", OL_D), ol_label)} ({brand_bridge}).

- **Cash App gross profit** for {period_label} was {f("ca_gp", A)}, growing {v("ca_gp", YOY)} YoY{pmyoy_paren("ca_gp")} and landing {variance_phrase(v("ca_gp", OL_P), v("ca_gp", OL_D), ol_label)}. Performance against {ol_label} was driven by {ca_outperf_phrase}.
    - **Commerce GMV** was {f("commerce_gmv", A)}, {variance_phrase(v("commerce_gmv", OL_P), v("commerce_gmv", OL_D), ol_label)} and {v("commerce_gmv", YOY)} YoY{pmyoy_paren("commerce_gmv")}.
    - **Cash App Actives** landed at {f("cash_actives", A)}, {variance_phrase(v("cash_actives", OL_P), v("cash_actives", OL_D), ol_label)} and growing {v("cash_actives", YOY)} YoY{pmyoy_paren("cash_actives")}.
    - **Cash App Inflows per Active** were {f("cash_inflows_pa", A)}, {variance_phrase(v("cash_inflows_pa", OL_P), v("cash_inflows_pa", OL_D), ol_label)} and {v("cash_inflows_pa", YOY)} YoY{pmyoy_paren("cash_inflows_pa")}.
- **Square gross profit** for {period_label} was {f("sq_gp", A)}, growing {v("sq_gp", YOY)} YoY{pmyoy_paren("sq_gp")} and landing {variance_phrase(v("sq_gp", OL_P), v("sq_gp", OL_D), ol_label)}. Performance against {ol_label} was driven by {sq_outperf_phrase}.
    - **Global GPV** was {f("sq_gpv", A)}, {variance_phrase(v("sq_gpv", OL_P), v("sq_gpv", OL_D), ol_label)} and {v("sq_gpv", YOY)} YoY{pmyoy_paren("sq_gpv")}.
    - **US GPV** was {f("sq_us", A)}, {variance_phrase(v("sq_us", OL_P), v("sq_us", OL_D), ol_label)} and {v("sq_us", YOY)} YoY{pmyoy_paren("sq_us")}.
    - **INTL GPV** was {f("sq_intl", A)}, {variance_phrase(v("sq_intl", OL_P), v("sq_intl", OL_D), ol_label)} and {v("sq_intl", YOY)} YoY{pmyoy_paren("sq_intl")}.
- **TIDAL gross profit** for {period_label} was {f("tidal", A)}, {v("tidal", YOY)} YoY{pmyoy_paren("tidal")} and landed {variance_phrase(v("tidal", OL_P), v("tidal", OL_D), ol_label)}.
- **Proto gross profit** for {period_label} was {f("proto", A)}, and landed {variance_phrase(v("proto", OL_P), v("proto", OL_D), ol_label)}.

{vp_line}

**Adjusted Opex** for {period_label} was {f("adj_opex", A)} ({v("adj_opex", YOY)} YoY{', ' + v("adj_opex", PMYOY) + ' in ' + prior_month if not is_quarterly else ''}), {variance_phrase(v("adj_opex", OL_P), v("adj_opex", OL_D), ol_label)}{adj_opex_ap_phrase}.

{var_bullet}
{acq_bullet}
{fix_bullet}

{gaap_oi_line}

**Adjusted Operating Income** landed at {f("adj_oi", A)} in {period_label}{aoi_margin_phrase}, {variance_phrase(v("adj_oi", OL_P), v("adj_oi", OL_D), ol_label)} and {v("adj_oi", YOY)} YoY{pmyoy_paren("adj_oi")}.

**{period_label} Rule of 40** was {reformat_variance(f("r40", A))}, {variance_phrase(v("r40", OL_P), "", ol_label)}, and {r40_ap_str} {r40_ap_direction} AP ({v("r40", YOY)} YoY{', ' + v("r40", PMYOY) + ' in ' + prior_month if not is_quarterly else ''}).
"""

    return md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", required=True, help="Path to flash_out JSON packet")
    ap.add_argument("--period", required=True, help="Period e.g. Apr'26")
    ap.add_argument("--ol-label", required=True, help="Outlook scenario label e.g. Q2OL")
    ap.add_argument("--ol-year", type=int, default=None, help="Year for Annual Plan ref (default: derived from period)")
    ap.add_argument("--mode", choices=["monthly", "quarterly", "auto"], default="auto",
                    help="monthly: standard month view (M-S sheet cols). quarterly: QTD view (T-Y sheet cols, "
                         "Q1/Q2/Q3/Q4 labels). auto: quarterly for Mar/Jun/Sep/Dec, else monthly.")
    ap.add_argument("--output", required=True, help="Path to write markdown")
    args = ap.parse_args()

    with open(args.packet) as f:
        packet = json.load(f)

    _, _, mnum, year = parse_period(args.period)
    ol_year = args.ol_year or year
    mode = detect_mode(mnum, override=None if args.mode == "auto" else args.mode)

    md = build_narrative(packet, args.period, args.ol_label, ol_year, mode=mode)

    with open(args.output, "w") as f:
        f.write(md)

    print(f"Wrote {args.output} ({mode} mode)")
    print(f"Lines: {md.count(chr(10))}")


if __name__ == "__main__":
    main()
