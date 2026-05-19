#!/usr/bin/env python3
"""MRP data layer — Block P&L Overview (Test tab Table 2, 30x7).

Consumed by /mrp-data. Claude pulls raw values from BDM via MCP and
passes them in as a JSON dict keyed by metric name with per-month
sub-dicts. This helper computes:

  - QTD aggregations (qtd_actuals, qtd_pace, qtd_ol, qtd_yoy_prior)
  - Derivations (Other Variable, Software & Cloud, Other Fixed,
    Total Fixed Costs, GAAP OI, Adj OpEx, Rule of 40, Adj EBITDA margin)
  - Variances ($, %) and YoY %
  - Formatting (currency / percent / points / +/-10 precision / nm rule)

Outputs a JSON packet at /tmp/mrp_out_{YYYY_MM}.json with one entry per row,
each carrying cell-addressable raw + formatted values plus row-polarity
hints the populator uses for green/red coloring.

Table 3 (Standardized P&L Double Click, 45x4) is added in Phase 6.

Usage:
    python3 mrp_data.py --month 2026-04 --raw /tmp/mrp_raw_2026_04.json \\
                        --out /tmp/mrp_out_2026_04.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass, field
from typing import Any

NM_THRESHOLD = 10.0  # |variance %| > 1000% renders as "nm"
SMALL = 10  # |magnitude| <= 10 -> 1 decimal; > 10 -> integer (the ±10 rule)
EMPTY = ""


# ============================================================
# Formatting
# ============================================================

def fmt_actual(v: float | None, scale: str = "auto") -> str:
    """Currency / count / rate formatter.

    scale:
      auto      -> $ with M/B scaling, parens for negatives
      count     -> "58.3M" for actives
      pct       -> "27%" (rate, 1 decimal; integer if magnitude > 10)
      pts       -> not used here; deltas only
    """
    if v is None or v == EMPTY:
        return EMPTY
    if scale == "count":
        return f"{v / 1_000_000:.1f}M"
    if scale == "pct":
        v_pct = v * 100
        if abs(v_pct) > SMALL:
            return f"{v_pct:.0f}%" if v >= 0 else f"({abs(v_pct):.0f}%)"
        return f"{v_pct:.1f}%" if v >= 0 else f"({abs(v_pct):.1f}%)"
    # auto $ scaling
    abs_v = abs(v)
    if abs_v >= 1_000_000_000:
        out = f"${abs_v/1_000_000_000:.2f}B"
    elif abs_v >= 10_000_000:
        out = f"${round(abs_v/1_000_000):,.0f}M"
    elif abs_v >= 100_000:
        out = f"${abs_v/1_000_000:.1f}M"
    else:
        out = f"${abs_v:,.0f}"
    return f"({out})" if v < 0 else out


def fmt_delta_dollar(v: float | None) -> str:
    """Dollar variance with +/-10 rule + parens for negative."""
    if v is None or v == EMPTY:
        return EMPTY
    abs_v_m = abs(v) / 1_000_000  # magnitude in millions for the +/-10 test
    abs_v = abs(v)
    if abs_v >= 1_000_000_000:
        s = f"${abs_v/1_000_000_000:.2f}B"
    elif abs_v_m > SMALL:
        s = f"${round(abs_v/1_000_000):,.0f}M"
    else:
        s = f"${abs_v/1_000_000:.1f}M"
    return f"({s})" if v < 0 else s


def fmt_pct(v: float | None, *, apply_nm: bool = True) -> str:
    """Variance percent (v is decimal: 0.058 -> 5.8% or 6%).
    Applies nm rule when |v| > 1000% and +/-10 precision rule.
    Negative wrapped in parens.
    """
    if v is None or v == EMPTY:
        return EMPTY
    if apply_nm and abs(v) > NM_THRESHOLD:
        return "nm"
    v_pct = v * 100
    abs_pct = abs(v_pct)
    if abs_pct > SMALL:
        s = f"{abs_pct:.0f}%"
    else:
        s = f"{abs_pct:.1f}%"
    return f"({s})" if v < 0 else s


def fmt_pts(v: float | None) -> str:
    """Margin / Rule-of-40 delta in points (e.g., +5.8 pts, -2 pts)."""
    if v is None or v == EMPTY:
        return EMPTY
    pts = v * 100  # decimal -> points
    sign = "+" if pts >= 0 else "-"
    abs_pts = abs(pts)
    if abs_pts > SMALL:
        return f"{sign}{abs_pts:.0f} pts"
    return f"{sign}{abs_pts:.1f} pts"


# ============================================================
# Math
# ============================================================

def safe_div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def yoy(curr: float | None, prior: float | None) -> float | None:
    """YoY as decimal (0.226 = 22.6%)."""
    if curr is None or prior is None or prior == 0:
        return None
    return (curr - prior) / abs(prior)


def variance(actual: float | None, plan: float | None) -> float | None:
    """Actual - Plan in $ (signed)."""
    if actual is None or plan is None:
        return None
    return actual - plan


def rule_of_40(gp: float | None, oi: float | None, gp_prior: float | None) -> float | None:
    """R40 = GP YoY + AOI margin (both decimals). Returned as decimal."""
    g = yoy(gp, gp_prior)
    m = safe_div(oi, gp)
    if g is None or m is None:
        return None
    return g + m


# ============================================================
# Period anchors
# ============================================================

def month_end(year: int, month: int) -> str:
    if month == 12:
        nxt = dt.date(year + 1, 1, 1)
    else:
        nxt = dt.date(year, month + 1, 1)
    return (nxt - dt.timedelta(days=1)).isoformat()


def quarter_of(month: int) -> int:
    return (month - 1) // 3 + 1


def quarter_months(year: int, quarter: int) -> list[str]:
    start_m = (quarter - 1) * 3 + 1
    return [f"{year}-{start_m + i:02d}" for i in range(3)]


def compute_anchors(report_month: str) -> dict:
    """report_month: 'YYYY-MM'. Returns full anchor dict."""
    y, m = map(int, report_month.split("-"))
    q = quarter_of(m)

    # Closed vs remaining months in quarter
    q_months = quarter_months(y, q)
    closed = [mm for mm in q_months if mm <= report_month]
    remaining = [mm for mm in q_months if mm > report_month]

    # OL label
    ol_label = "AP" if q == 1 else f"Q{q}OL"
    ol_scenario = f"{y} Annual Plan" if q == 1 else f"Q{q} Outlook"

    return {
        "report_month": report_month,
        "year": y,
        "month": m,
        "quarter": f"Q{q}",
        "quarter_months": q_months,
        "qtd_closed_months": closed,
        "qtd_remaining_months": remaining,
        "yoy_prior_month": f"{y-1}-{m:02d}",
        "yoy_prior_quarter_months": quarter_months(y - 1, q),
        "ol_label": ol_label,
        "ol_scenario": ol_scenario,
        "ap_scenario": f"{y} Annual Plan",
    }


# ============================================================
# Raw lookups + period computations
# ============================================================

def get_monthly(raw: dict, metric: str, month: str, scenario: str = "actual") -> float | None:
    """Look up a single month value from the raw packet.

    Schema:
      raw[metric]['monthly'][month][scenario]
    where scenario in {'actual','ol','ap','yoy_prior_actual'}.
    Returns None if any layer missing.
    """
    m = raw.get(metric, {}).get("monthly", {}).get(month, {})
    v = m.get(scenario)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def sum_months(raw: dict, metric: str, months: list[str], scenario: str) -> float | None:
    """Sum a metric across months; returns None if any month missing."""
    total = 0.0
    seen = 0
    for mm in months:
        v = get_monthly(raw, metric, mm, scenario)
        if v is None:
            return None
        total += v
        seen += 1
    return total if seen else None


def fetch_periods(raw: dict, metric: str, anchors: dict) -> dict:
    """Compute all six anchor values for one metric. Returns dict with keys:
        actual, ol, qtd_actuals, qtd_pace, qtd_ol, qtd_yoy_prior, yoy_prior, ap
    Any value may be None when raw data is missing.
    """
    rm = anchors["report_month"]
    yoy_m = anchors["yoy_prior_month"]
    q_months = anchors["quarter_months"]
    closed = anchors["qtd_closed_months"]
    remaining = anchors["qtd_remaining_months"]
    yoy_q_months = anchors["yoy_prior_quarter_months"]

    actual = get_monthly(raw, metric, rm, "actual")
    ol = get_monthly(raw, metric, rm, "ol")
    ap = get_monthly(raw, metric, rm, "ap")
    yoy_prior = get_monthly(raw, metric, yoy_m, "actual")

    qtd_actuals = sum_months(raw, metric, closed, "actual")
    qtd_ol_remaining = sum_months(raw, metric, remaining, "ol") if remaining else 0.0
    qtd_pace = (qtd_actuals + qtd_ol_remaining) if (qtd_actuals is not None and qtd_ol_remaining is not None) else None
    qtd_ol = sum_months(raw, metric, q_months, "ol")
    qtd_yoy_prior = sum_months(raw, metric, yoy_q_months, "actual")

    return {
        "actual": actual, "ol": ol, "ap": ap, "yoy_prior": yoy_prior,
        "qtd_actuals": qtd_actuals, "qtd_pace": qtd_pace,
        "qtd_ol": qtd_ol, "qtd_yoy_prior": qtd_yoy_prior,
    }


# ============================================================
# Row schema
# ============================================================

@dataclass
class CellSpec:
    """A single cell: raw value + display string + optional polarity for coloring."""
    raw: Any
    formatted: str
    col_kind: str  # 'actual' | 'yoy_pct' | 'vs_ol_dollar' | 'pts'


@dataclass
class RowSpec:
    """One row of Table 2 (Block P&L Overview).
    cells = 6 data cells (after the label):
        [actual, yoy_pct, vs_ol_dollar, qtd_actual_or_pace, qtd_yoy_pct, qtd_vs_ol_dollar]
    """
    row_idx: int           # 0-indexed within data rows of the table
    label: str
    cells: list[CellSpec] = field(default_factory=list)
    is_section_header: bool = False
    is_total: bool = False
    is_gap: bool = False
    polarity: str = "revenue"   # 'revenue' (pos=good) | 'cost' (neg=good) | 'rate' (pos=good)
    notes: str | None = None

    def to_json(self) -> dict:
        return {
            "row_idx": self.row_idx,
            "label": self.label,
            "is_section_header": self.is_section_header,
            "is_total": self.is_total,
            "is_gap": self.is_gap,
            "polarity": self.polarity,
            "notes": self.notes,
            "cells": [
                {"col": i + 1, "raw": c.raw, "formatted": c.formatted, "kind": c.col_kind}
                for i, c in enumerate(self.cells)
            ],
        }


def cells_for_metric(p: dict, scale: str = "auto") -> list[CellSpec]:
    """Build the 6 data cells for a metric given its period dict from fetch_periods.

    Cols: [actual, yoy_pct, vs_ol_dollar, qtd_pace, qtd_yoy_pct, qtd_vs_ol_dollar]
    """
    actual = p["actual"]
    yoy_pct = yoy(actual, p["yoy_prior"])
    vs_ol = variance(actual, p["ol"])
    qtd_pace = p["qtd_pace"]
    qtd_yoy_pct = yoy(qtd_pace, p["qtd_yoy_prior"])
    qtd_vs_ol = variance(qtd_pace, p["qtd_ol"])

    return [
        CellSpec(actual, fmt_actual(actual, scale=scale), "actual"),
        CellSpec(yoy_pct, fmt_pct(yoy_pct), "yoy_pct"),
        CellSpec(vs_ol, fmt_delta_dollar(vs_ol), "vs_ol_dollar"),
        CellSpec(qtd_pace, fmt_actual(qtd_pace, scale=scale), "actual"),
        CellSpec(qtd_yoy_pct, fmt_pct(qtd_yoy_pct), "yoy_pct"),
        CellSpec(qtd_vs_ol, fmt_delta_dollar(qtd_vs_ol), "vs_ol_dollar"),
    ]


def cells_for_rate(p: dict) -> list[CellSpec]:
    """Cells for a rate metric (AOI margin). YoY and vs OL are pt deltas, not $/%."""
    actual = p["actual"]
    yoy_pts = variance(actual, p["yoy_prior"])
    vs_ol_pts = variance(actual, p["ol"])
    qtd_actual = safe_div(p.get("qtd_pace_oi"), p.get("qtd_pace_gp")) if False else p["qtd_actuals"]
    # Note: AOI margin QTD is computed at the call site (R25 below), since
    # margin needs to be re-derived from QTD AOI / QTD GP, not summed.
    return [
        CellSpec(actual, fmt_actual(actual, scale="pct"), "actual"),
        CellSpec(yoy_pts, fmt_pts(yoy_pts), "pts"),
        CellSpec(vs_ol_pts, fmt_pts(vs_ol_pts), "pts"),
        CellSpec(None, EMPTY, "actual"),    # placeholder; filled by caller
        CellSpec(None, EMPTY, "pts"),
        CellSpec(None, EMPTY, "pts"),
    ]


def gap_row(row_idx: int, label: str, n_cells: int = 6, polarity: str = "revenue", notes: str = "DATA GAP") -> RowSpec:
    cells = [CellSpec(None, "[GAP]", "actual") for _ in range(n_cells)]
    return RowSpec(row_idx=row_idx, label=label, cells=cells, is_gap=True, polarity=polarity, notes=notes)


def section_row(row_idx: int, label: str, n_cells: int = 6) -> RowSpec:
    cells = [CellSpec(None, EMPTY, "actual") for _ in range(n_cells)]
    return RowSpec(row_idx=row_idx, label=label, cells=cells, is_section_header=True)


# ============================================================
# Block P&L Overview (Table 2) builder
# ============================================================

def build_block_pl_overview(raw: dict, anchors: dict) -> list[RowSpec]:
    """Build the 28 data rows of Test tab Table 2 (Block P&L Overview).
    Rows are 0-indexed; R00 and R01 are headers (not built here)."""
    rows: list[RowSpec] = []

    def metric_row(idx: int, label: str, metric: str, polarity: str = "revenue", is_total: bool = False) -> RowSpec:
        periods = fetch_periods(raw, metric, anchors)
        cells = cells_for_metric(periods)
        return RowSpec(row_idx=idx, label=label, cells=cells, polarity=polarity, is_total=is_total)

    # --- Gross Profit (R02-R09) ---
    rows.append(metric_row(2, "Gross profit", "block_gp", "revenue", is_total=True))
    rows.append(metric_row(3, "Cash App", "cash_app_gp", "revenue"))
    rows.append(metric_row(4, "Square", "square_gp", "revenue"))
    rows.append(metric_row(5, "Other Brands", "other_brands_gp", "revenue"))
    rows.append(metric_row(6, "TIDAL", "tidal_gp", "revenue"))
    # Bitcoin Lightning / Bitkey: best-effort fetch; render as GAP if not in raw
    if "bitcoin_lightning_gp" in raw:
        rows.append(metric_row(7, "Bitcoin Lightning", "bitcoin_lightning_gp", "revenue"))
    else:
        rows.append(gap_row(7, "Bitcoin Lightning", polarity="revenue",
                            notes="BDM segment label not yet verified"))
    if "bitkey_gp" in raw:
        rows.append(metric_row(8, "Bitkey", "bitkey_gp", "revenue"))
    else:
        rows.append(gap_row(8, "Bitkey", polarity="revenue",
                            notes="BDM segment label not yet verified"))
    rows.append(metric_row(9, "Proto", "proto_gp", "revenue"))

    # --- Variable Operational Costs (R10-R13) ---
    rows.append(metric_row(10, "Variable Operational Costs", "variable_opex_total", "cost", is_total=True))
    rows.append(metric_row(11, "P2P marketing", "p2p_opex", "cost"))
    rows.append(metric_row(12, "Risk loss", "risk_loss_opex", "cost"))
    # Other variable = Total Variable Op Costs - P2P - Risk Loss (residual; matches MRP convention)
    rows.append(derived_subtract_row(
        idx=13, label="Other variable",
        positive=["variable_opex_total"],
        negative=["p2p_opex", "risk_loss_opex"],
        raw=raw, anchors=anchors, polarity="cost",
    ))

    # --- Acquisition Costs (R14) ---
    rows.append(metric_row(14, "Acquisition Costs (incl. S&M people)", "acquisition_costs_total", "cost", is_total=True))

    # --- Fixed Costs (R15-R20) ---
    # Fixed Costs = GAAP OpEx - Variable - Acquisition (Flash v2.0 fix; do NOT use BDM rollup)
    rows.append(derived_subtract_row(
        idx=15, label="Fixed Costs",
        positive=["gaap_opex_total"],
        negative=["variable_opex_total", "acquisition_costs_total"],
        raw=raw, anchors=anchors, polarity="cost", is_total=True,
    ))
    rows.append(metric_row(16, "Product development people", "prod_dev_people_opex", "cost"))
    rows.append(metric_row(17, "G&A people (ex. CS)", "ga_people_ex_cs_opex", "cost"))
    rows.append(metric_row(18, "Customer support (people)", "cs_people_opex", "cost"))
    # Software & Cloud = software_fees + cloud_fees
    rows.append(derived_sum_row(
        idx=19, label="Software & cloud",
        components=["software_fees_opex", "cloud_fees_opex"],
        raw=raw, anchors=anchors, polarity="cost",
    ))
    # Other Fixed = Total Fixed - PD People - G&A People - CS People - Software & Cloud
    rows.append(derived_subtract_row(
        idx=20, label="Other Fixed",
        positive_rowdata=lambda: rows[13].cells,  # not used; computed differently
        positive_compute=lambda: derived_subtract_value(  # Fixed Costs raw
            positive=["gaap_opex_total"],
            negative=["variable_opex_total", "acquisition_costs_total"],
            raw=raw, anchors=anchors,
        ),
        negative_compute=lambda: sum_compute(
            ["prod_dev_people_opex", "ga_people_ex_cs_opex", "cs_people_opex",
             "software_fees_opex", "cloud_fees_opex"],
            raw=raw, anchors=anchors,
        ),
        raw=raw, anchors=anchors, polarity="cost",
    ))

    # --- GAAP totals (R21-R22) ---
    rows.append(metric_row(21, "GAAP OpEx", "gaap_opex_total", "cost", is_total=True))
    # GAAP OI = Block GP - GAAP OpEx
    rows.append(derived_subtract_row(
        idx=22, label="GAAP Operating income",
        positive=["block_gp"], negative=["gaap_opex_total"],
        raw=raw, anchors=anchors, polarity="revenue", is_total=True,
    ))

    # --- Adjusted (R23-R26) ---
    # Adj OpEx = Block GP - Adj OI (identity)
    rows.append(derived_subtract_row(
        idx=23, label="Adjusted Opex",
        positive=["block_gp"], negative=["adj_oi"],
        raw=raw, anchors=anchors, polarity="cost", is_total=True,
    ))
    rows.append(metric_row(24, "Adjusted Operating Income", "adj_oi", "revenue", is_total=True))

    # R25 % Margin (AOI margin) — special: rate row, deltas in pts
    rows.append(build_aoi_margin_row(25, raw, anchors))

    # R26 Rule of 40 — special: rate row, deltas in pts
    rows.append(build_rule_of_40_row(26, raw, anchors))

    # --- EBITDA (R27-R28) ---
    if "adj_ebitda" in raw:
        rows.append(metric_row(27, "Adjusted EBITDA", "adj_ebitda", "revenue", is_total=True))
        rows.append(build_ebitda_margin_row(28, raw, anchors))
    else:
        rows.append(gap_row(27, "Adjusted EBITDA", polarity="revenue",
                            notes="Adj EBITDA metric not in raw; verify BDM path or derive Adj OI + D&A"))
        rows.append(gap_row(28, "% Margin", polarity="rate",
                            notes="Depends on Adj EBITDA"))

    # R29 People (headcount) — confirmed GAP
    rows.append(gap_row(29, "People", polarity="revenue",
                        notes="Headcount not in BDM"))

    return rows


# ============================================================
# Derivation helpers
# ============================================================

def sum_compute(components: list[str], raw: dict, anchors: dict) -> dict:
    """Sum multiple metrics across all six anchors. Returns the same period dict shape."""
    result = {"actual": None, "ol": None, "ap": None, "yoy_prior": None,
              "qtd_actuals": None, "qtd_pace": None, "qtd_ol": None, "qtd_yoy_prior": None}
    for k in result:
        total = 0.0
        all_present = True
        for c in components:
            v = fetch_periods(raw, c, anchors)[k]
            if v is None:
                all_present = False
                break
            total += v
        result[k] = total if all_present else None
    return result


def derived_sum_row(idx: int, label: str, components: list[str],
                    raw: dict, anchors: dict, polarity: str) -> RowSpec:
    periods = sum_compute(components, raw, anchors)
    cells = cells_for_metric(periods)
    return RowSpec(row_idx=idx, label=label, cells=cells, polarity=polarity,
                   notes=f"Derived: sum of {', '.join(components)}")


def derived_subtract_value(positive: list[str], negative: list[str],
                           raw: dict, anchors: dict) -> dict:
    """Compute (sum of positive) - (sum of negative) across all anchors."""
    pos = sum_compute(positive, raw, anchors)
    neg = sum_compute(negative, raw, anchors)
    out = {}
    for k in pos:
        if pos[k] is None or neg[k] is None:
            out[k] = None
        else:
            out[k] = pos[k] - neg[k]
    return out


def derived_subtract_row(idx: int, label: str,
                         positive=None, negative=None,
                         positive_compute=None, negative_compute=None,
                         positive_rowdata=None,
                         raw: dict | None = None, anchors: dict | None = None,
                         polarity: str = "revenue", is_total: bool = False) -> RowSpec:
    """Derived = sum(positive) - sum(negative). Either pass component-name lists
    or pre-computed period dicts via *_compute callables."""
    if positive_compute is not None:
        pos = positive_compute()
        neg = negative_compute() if negative_compute else {k: 0.0 for k in pos}
        out = {k: (pos[k] - neg[k]) if (pos[k] is not None and neg[k] is not None) else None for k in pos}
    else:
        out = derived_subtract_value(positive or [], negative or [], raw, anchors)

    cells = cells_for_metric(out)
    notes_parts = []
    if positive:
        notes_parts.append("+ " + " + ".join(positive))
    if negative:
        notes_parts.append("- " + " - ".join(negative))
    return RowSpec(row_idx=idx, label=label, cells=cells, polarity=polarity, is_total=is_total,
                   notes="Derived: " + " ".join(notes_parts) if notes_parts else "Derived")


def build_aoi_margin_row(idx: int, raw: dict, anchors: dict) -> RowSpec:
    """R25 AOI margin. Display rate; YoY + vs OL as pts.
    Margins are computed at each anchor as AOI / GP.
    QTD margin = QTD_AOI / QTD_GP (derived from sums)."""
    gp = fetch_periods(raw, "block_gp", anchors)
    oi = fetch_periods(raw, "adj_oi", anchors)

    def m(k):
        return safe_div(oi[k], gp[k])

    actual = m("actual")
    yoy_p = m("yoy_prior")
    ol_p = m("ol")
    qtd_pace_gp = gp["qtd_pace"]
    qtd_pace_oi = oi["qtd_pace"]
    qtd_pace_margin = safe_div(qtd_pace_oi, qtd_pace_gp)
    qtd_yoy = safe_div(oi["qtd_yoy_prior"], gp["qtd_yoy_prior"])
    qtd_ol_margin = safe_div(oi["qtd_ol"], gp["qtd_ol"])

    cells = [
        CellSpec(actual, fmt_actual(actual, scale="pct"), "actual"),
        CellSpec(variance(actual, yoy_p), fmt_pts(variance(actual, yoy_p)), "pts"),
        CellSpec(variance(actual, ol_p), fmt_pts(variance(actual, ol_p)), "pts"),
        CellSpec(qtd_pace_margin, fmt_actual(qtd_pace_margin, scale="pct"), "actual"),
        CellSpec(variance(qtd_pace_margin, qtd_yoy), fmt_pts(variance(qtd_pace_margin, qtd_yoy)), "pts"),
        CellSpec(variance(qtd_pace_margin, qtd_ol_margin), fmt_pts(variance(qtd_pace_margin, qtd_ol_margin)), "pts"),
    ]
    return RowSpec(row_idx=idx, label="% Margin", cells=cells, polarity="rate",
                   notes="Adj OI / Block GP, deltas in pts")


def build_rule_of_40_row(idx: int, raw: dict, anchors: dict) -> RowSpec:
    """R26 Rule of 40 = GP YoY + AOI margin. All anchors. Deltas in pts."""
    gp = fetch_periods(raw, "block_gp", anchors)
    oi = fetch_periods(raw, "adj_oi", anchors)

    def r40(gp_v, oi_v, gp_prior):
        return rule_of_40(gp_v, oi_v, gp_prior)

    actual = r40(gp["actual"], oi["actual"], gp["yoy_prior"])
    # For YoY R40 comparison, denom is prior-year R40:
    #   PY R40 = (prior_year_gp - py-1_gp)/|py-1_gp| + prior_year_aoi_margin
    # py-1 GP isn't currently fetched (raw schema doesn't include it). Leave None for v1.
    yoy_p = None  # TODO: fetch py-1 GP for PY R40 computation
    ol_p = r40(gp["ol"], oi["ol"], gp["yoy_prior"])  # use same yoy_prior as actual baseline
    qtd_pace = r40(gp["qtd_pace"], oi["qtd_pace"], gp["qtd_yoy_prior"])
    qtd_yoy_p = None  # TODO: PY QTD R40
    qtd_ol = r40(gp["qtd_ol"], oi["qtd_ol"], gp["qtd_yoy_prior"])

    cells = [
        CellSpec(actual, fmt_actual(actual, scale="pct"), "actual"),
        CellSpec(variance(actual, yoy_p), fmt_pts(variance(actual, yoy_p)), "pts"),
        CellSpec(variance(actual, ol_p), fmt_pts(variance(actual, ol_p)), "pts"),
        CellSpec(qtd_pace, fmt_actual(qtd_pace, scale="pct"), "actual"),
        CellSpec(variance(qtd_pace, qtd_yoy_p), fmt_pts(variance(qtd_pace, qtd_yoy_p)), "pts"),
        CellSpec(variance(qtd_pace, qtd_ol), fmt_pts(variance(qtd_pace, qtd_ol)), "pts"),
    ]
    return RowSpec(row_idx=idx, label="Rule of 40", cells=cells, polarity="rate", is_total=True,
                   notes="GP YoY% + AOI margin; PY R40 (YoY pts delta) requires py-1 GP — not in v1")


def build_ebitda_margin_row(idx: int, raw: dict, anchors: dict) -> RowSpec:
    """R28 Adj EBITDA margin = Adj EBITDA / Block GP. Rate row; pts deltas."""
    gp = fetch_periods(raw, "block_gp", anchors)
    ebitda = fetch_periods(raw, "adj_ebitda", anchors)

    def m(k):
        return safe_div(ebitda[k], gp[k])

    actual = m("actual")
    yoy_p = m("yoy_prior")
    ol_p = m("ol")
    qtd_pace_m = safe_div(ebitda["qtd_pace"], gp["qtd_pace"])
    qtd_yoy = safe_div(ebitda["qtd_yoy_prior"], gp["qtd_yoy_prior"])
    qtd_ol_m = safe_div(ebitda["qtd_ol"], gp["qtd_ol"])

    cells = [
        CellSpec(actual, fmt_actual(actual, scale="pct"), "actual"),
        CellSpec(variance(actual, yoy_p), fmt_pts(variance(actual, yoy_p)), "pts"),
        CellSpec(variance(actual, ol_p), fmt_pts(variance(actual, ol_p)), "pts"),
        CellSpec(qtd_pace_m, fmt_actual(qtd_pace_m, scale="pct"), "actual"),
        CellSpec(variance(qtd_pace_m, qtd_yoy), fmt_pts(variance(qtd_pace_m, qtd_yoy)), "pts"),
        CellSpec(variance(qtd_pace_m, qtd_ol_m), fmt_pts(variance(qtd_pace_m, qtd_ol_m)), "pts"),
    ]
    return RowSpec(row_idx=idx, label="% Margin", cells=cells, polarity="rate",
                   notes="Adj EBITDA / Block GP")


# ============================================================
# Main packet assembly + CLI
# ============================================================

# ============================================================
# Stnd P&L Double Click (Table 3) builder
# ============================================================

def cells_for_metric_t3(p: dict, scale: str = "auto") -> list[CellSpec]:
    """3 cells for a Table 3 metric: [actual, yoy_pct, vs_ol_dollar]. No QTD."""
    actual = p["actual"]
    yoy_pct = yoy(actual, p["yoy_prior"])
    vs_ol = variance(actual, p["ol"])
    return [
        CellSpec(actual, fmt_actual(actual, scale=scale), "actual"),
        CellSpec(yoy_pct, fmt_pct(yoy_pct), "yoy_pct"),
        CellSpec(vs_ol, fmt_delta_dollar(vs_ol), "vs_ol_dollar"),
    ]


def gap_row_t3(idx: int, label: str, polarity: str = "cost", notes: str = "DATA GAP") -> RowSpec:
    cells = [CellSpec(None, "[GAP]", "actual") for _ in range(3)]
    return RowSpec(row_idx=idx, label=label, cells=cells, is_gap=True, polarity=polarity, notes=notes)


def section_row_t3(idx: int, label: str) -> RowSpec:
    cells = [CellSpec(None, EMPTY, "actual") for _ in range(3)]
    return RowSpec(row_idx=idx, label=label, cells=cells, is_section_header=True)


def build_stnd_pl_double_click(raw: dict, anchors: dict) -> list[RowSpec]:
    """43 data rows of Test tab Table 3 (Standardized P&L Double Click)."""
    rows: list[RowSpec] = []

    def metric_t3(idx: int, label: str, metric: str, polarity: str = "cost",
                  is_total: bool = False) -> RowSpec:
        periods = fetch_periods(raw, metric, anchors)
        cells = cells_for_metric_t3(periods)
        return RowSpec(row_idx=idx, label=label, cells=cells, polarity=polarity, is_total=is_total)

    # Variable Operational Costs section
    rows.append(section_row_t3(2, "Variable Operational Costs"))
    rows.append(metric_t3(3, "P2P", "p2p_opex"))
    rows.append(metric_t3(4, "Risk Loss", "risk_loss_opex"))
    rows.append(metric_t3(5, "Card Issuance", "card_issuance_opex"))
    rows.append(metric_t3(6, "Warehouse Financing", "warehouse_financing_opex"))
    rows.append(metric_t3(7, "Hardware Logistics", "hw_logistics_opex"))
    rows.append(metric_t3(8, "Bad Debt Expense", "bad_debt_opex"))
    rows.append(metric_t3(9, "Customer Reimbursements", "customer_reimbursements_opex"))

    # Acquisition Costs section
    rows.append(section_row_t3(10, "Acquisition Costs"))
    # R11 Marketing (Non-People) = Marketing + Onboarding + Partnership + Reader
    rows.append(derived_sum_row_t3(
        idx=11, label="Marketing (Non-People)",
        components=["marketing_opex", "onboarding_opex", "partnership_fees_opex", "reader_expense_opex"],
        raw=raw, anchors=anchors, polarity="cost",
    ))
    rows.append(metric_t3(12, "Sales & Marketing (People)", "sm_people_opex"))

    # Fixed Costs section
    rows.append(section_row_t3(13, "Fixed Costs"))
    rows.append(metric_t3(14, "Product Development People", "prod_dev_people_opex"))
    rows.append(metric_t3(15, "G&A People (ex. CS)", "ga_people_ex_cs_opex"))
    rows.append(metric_t3(16, "Customer Support People", "cs_people_opex"))
    rows.append(metric_t3(17, "Software", "software_fees_opex"))
    rows.append(metric_t3(18, "Cloud fees", "cloud_fees_opex"))
    rows.append(metric_t3(19, "Taxes, Insurance & Other Corp", "taxes_insurance_other_opex"))
    rows.append(metric_t3(20, "Legal fees", "legal_fees_opex"))
    rows.append(metric_t3(21, "Other Professional Services", "other_pro_services_opex"))
    rows.append(metric_t3(22, "Rent, Facilities, Equipment", "rent_facilities_equipment_opex"))
    rows.append(metric_t3(23, "Travel & Entertainment", "travel_entertainment_opex"))
    rows.append(metric_t3(24, "Hardware Production Costs", "hardware_production_opex"))
    rows.append(metric_t3(25, "Non-Cash expenses (ex. SBC)", "non_cash_excl_sbc_opex"))

    # GAAP OpEx subtotal
    rows.append(metric_t3(26, "GAAP OpEx", "gaap_opex_total", is_total=True))

    # Total FTE Personnel Costs (incl. SBC) — BDM subtotal; per-function are GAP
    rows.append(metric_t3(27, "Total FTE Personnel Costs (incl. SBC)", "total_personnel_cost_opex", is_total=True))
    for idx, fn_label in [(28, "Product Development"), (29, "S&M"), (30, "G&A"),
                          (31, "Customer Support"), (32, "Compliance")]:
        rows.append(gap_row_t3(idx, fn_label, polarity="cost",
                               notes="Function-level Personnel not in BDM"))

    # Total Contractors (subtotal + per-function: all GAP — BDM doesn't expose contractors)
    rows.append(gap_row_t3(33, "Total Contractors", polarity="cost",
                           notes="Contractors metrics not in BDM"))
    for idx, fn_label in [(34, "Product Development"), (35, "S&M"), (36, "G&A"),
                          (37, "Customer Support"), (38, "Compliance")]:
        rows.append(gap_row_t3(idx, fn_label, polarity="cost",
                               notes="Function-level Contractors not in BDM"))

    # SBC subtotal — single metric available
    rows.append(metric_t3(39, "SBC", "sbc_opex", is_total=True))
    # Per-function SBC: GAP
    for idx, fn_label in [(40, "Product Development"), (41, "S&M"), (42, "G&A"),
                          (43, "Customer Support"), (44, "Compliance")]:
        rows.append(gap_row_t3(idx, fn_label, polarity="cost",
                               notes="Function-level SBC not in BDM"))

    return rows


def derived_sum_row_t3(idx: int, label: str, components: list[str],
                       raw: dict, anchors: dict, polarity: str) -> RowSpec:
    """Like derived_sum_row but returns 3-cell Table 3 cells."""
    periods = sum_compute(components, raw, anchors)
    cells = cells_for_metric_t3(periods)
    return RowSpec(row_idx=idx, label=label, cells=cells, polarity=polarity,
                   notes=f"Derived: sum of {', '.join(components)}")


# ============================================================
# Cash App detail (Table 5) builder — 31x5 layout
# Cols: [label, Actual, $ vs. Q2OL, % vs. Q2OL, YoY % Growth]
# ============================================================

def cells_for_metric_t5(p: dict, scale: str = "auto") -> list[CellSpec]:
    """4 cells for a $-valued Table 5 row: [actual, vs_ol_dollar, vs_ol_pct, yoy_pct]."""
    actual = p.get("actual")
    ol = p.get("ol")
    yoy_prior = p.get("yoy_prior")
    vs_ol_dol = variance(actual, ol)
    vs_ol_pct = yoy(actual, ol)  # (actual - ol) / abs(ol) — same shape as YoY
    yoy_pct = yoy(actual, yoy_prior)
    return [
        CellSpec(actual, fmt_actual(actual, scale=scale), "actual"),
        CellSpec(vs_ol_dol, fmt_delta_dollar(vs_ol_dol), "vs_ol_dollar"),
        CellSpec(vs_ol_pct, fmt_pct(vs_ol_pct), "vs_ol_pct"),
        CellSpec(yoy_pct, fmt_pct(yoy_pct), "yoy_pct"),
    ]


def cells_for_actives_t5(p: dict) -> list[CellSpec]:
    """Actives row: [count, [GAP], [GAP], yoy_pct]. No outlook metric in BDM."""
    actual = p.get("actual")
    yoy_pct = yoy(actual, p.get("yoy_prior"))
    return [
        CellSpec(actual, fmt_actual(actual, scale="count"), "actual"),
        CellSpec(None, "[GAP]", "vs_ol_dollar"),
        CellSpec(None, "[GAP]", "vs_ol_pct"),
        CellSpec(yoy_pct, fmt_pct(yoy_pct), "yoy_pct"),
    ]


def cells_for_rate_t5(actual: float | None, ol: float | None,
                      yoy_prior: float | None) -> list[CellSpec]:
    """Rate row (e.g., % Margin): [rate, '', pts_vs_ol, pts_yoy].
    Col 2 ($ vs OL) is empty for rates; cols 3+4 carry pts deltas."""
    vs_ol_pts = variance(actual, ol)
    yoy_pts = variance(actual, yoy_prior)
    return [
        CellSpec(actual, fmt_actual(actual, scale="pct"), "actual"),
        CellSpec(None, EMPTY, "vs_ol_dollar"),
        CellSpec(vs_ol_pts, fmt_pts(vs_ol_pts), "pts"),
        CellSpec(yoy_pts, fmt_pts(yoy_pts), "pts"),
    ]


def gap_row_t5(idx: int, label: str, polarity: str = "revenue",
               is_total: bool = False, notes: str = "DATA GAP") -> RowSpec:
    cells = [CellSpec(None, "[GAP]", "actual") for _ in range(4)]
    return RowSpec(row_idx=idx, label=label, cells=cells, is_gap=True,
                   polarity=polarity, is_total=is_total, notes=notes)


def section_row_t5(idx: int, label: str) -> RowSpec:
    cells = [CellSpec(None, EMPTY, "actual") for _ in range(4)]
    return RowSpec(row_idx=idx, label=label, cells=cells, is_section_header=True)


def fetch_periods_t5(raw: dict, metric: str, report_month: str, yoy_month: str) -> dict:
    """Table 5 needs only actual/ol/yoy_prior (no QTD)."""
    return {
        "actual": get_monthly(raw, metric, report_month, "actual"),
        "ol": get_monthly(raw, metric, report_month, "ol"),
        "yoy_prior": get_monthly(raw, metric, yoy_month, "actual"),
    }


def sum_periods_t5(periods_list: list[dict]) -> dict:
    """Sum a list of period dicts; None propagates per key."""
    out = {"actual": 0.0, "ol": 0.0, "yoy_prior": 0.0}
    present = {k: True for k in out}
    for p in periods_list:
        for k in out:
            v = p.get(k)
            if v is None:
                present[k] = False
            else:
                out[k] += v
    return {k: (out[k] if present[k] else None) for k in out}


def build_cash_app_detail(raw: dict, report_month: str = "2026-04",
                          yoy_month: str = "2025-04") -> list[RowSpec]:
    """29 data rows of Test tab Table 5 (Cash App detail).
    Rows 0,1 are header rows (April 2026 / column titles); built externally if needed."""
    rows: list[RowSpec] = []

    def metric_row(idx: int, label: str, metric: str,
                   polarity: str = "revenue", is_total: bool = False, scale: str = "auto") -> RowSpec:
        p = fetch_periods_t5(raw, metric, report_month, yoy_month)
        return RowSpec(row_idx=idx, label=label, cells=cells_for_metric_t5(p, scale=scale),
                       polarity=polarity, is_total=is_total)

    def actives(idx: int, label: str, metric: str) -> RowSpec:
        p = fetch_periods_t5(raw, metric, report_month, yoy_month)
        return RowSpec(row_idx=idx, label=label, cells=cells_for_actives_t5(p),
                       polarity="revenue",
                       notes="No outlook metric in BDM; vs Q2OL cols render [GAP]")

    def derived(idx: int, label: str, positive: list[str], negative: list[str],
                polarity: str = "revenue", is_total: bool = False) -> RowSpec:
        pos = sum_periods_t5([fetch_periods_t5(raw, m, report_month, yoy_month) for m in positive])
        neg = sum_periods_t5([fetch_periods_t5(raw, m, report_month, yoy_month) for m in negative]) \
              if negative else {"actual": 0.0, "ol": 0.0, "yoy_prior": 0.0}
        per = {k: (pos[k] - neg[k]) if (pos[k] is not None and neg[k] is not None) else None
               for k in ["actual", "ol", "yoy_prior"]}
        cells = cells_for_metric_t5(per)
        note = f"Derived: + {' + '.join(positive)}" + (f" - {' - '.join(negative)}" if negative else "")
        return RowSpec(row_idx=idx, label=label, cells=cells, polarity=polarity,
                       is_total=is_total, notes=note)

    # Cash App sub-product metric names (R05-R12, in order)
    CA_CORE_METRICS = ["ca_atm_gp", "ca_btc_buy_sell_gp", "ca_btc_withdrawal_fees_gp",
                       "ca_business_accounts_gp", "ca_card_gp", "ca_instant_deposit_gp",
                       "ca_interest_income_gp", "ca_paper_money_gp"]
    # Afterpay BNPL sub-products (R20-R23) — the items rolled into R19 Afterpay subtotal
    AP_BNPL_METRICS = ["ap_core_bnpl_gp", "ap_gift_card_gp", "ap_pay_monthly_gp", "ap_plus_card_gp"]

    # R02 Cash App Actives
    rows.append(actives(2, "Cash App Actives", "ca_total_actives"))
    # R03 Primary Banking Actives
    rows.append(actives(3, "Primary Banking Actives", "ca_primary_banking_actives"))
    # R04 Core Cash App = subtotal of R05-R12 (per MRP convention — 8 itemized core CA products)
    rows.append(derived(4, "Core Cash App", positive=CA_CORE_METRICS, negative=[]))
    # R05-R12 Cash App sub-products
    rows.append(metric_row(5, "ATM", "ca_atm_gp"))
    rows.append(metric_row(6, "Bitcoin Buy/Sell", "ca_btc_buy_sell_gp"))
    rows.append(metric_row(7, "Bitcoin Withdrawal Fees", "ca_btc_withdrawal_fees_gp"))
    rows.append(metric_row(8, "Business Accounts", "ca_business_accounts_gp"))
    rows.append(metric_row(9, "Cash App Card", "ca_card_gp"))
    rows.append(metric_row(10, "Instant Deposit", "ca_instant_deposit_gp"))
    rows.append(metric_row(11, "Interest Income", "ca_interest_income_gp"))
    rows.append(metric_row(12, "Paper Money Deposits", "ca_paper_money_gp"))
    # R13 Lending = subtotal of R14+R15 (per MRP convention — has values, not just header)
    rows.append(derived(13, "Lending", positive=["ca_borrow_gp", "ca_post_purchase_gp"], negative=[]))
    # R14 Borrow
    rows.append(metric_row(14, "Borrow", "ca_borrow_gp"))
    # R15 Post-Purchase (= 3055 Cash Retro per Nick)
    rows.append(metric_row(15, "Post-Purchase", "ca_post_purchase_gp"))
    # R16 Cash App Pay
    rows.append(metric_row(16, "Cash App Pay", "ca_pay_gp"))
    # R17 Other** (EDM 'Other - Cash App' topline sum)
    rows.append(metric_row(17, "Other**", "ca_other_gp"))
    # R18 Cash App GAAP GP = R04 (Core) + R13 (Lending) + R16 (CA Pay) + R17 (Other)
    rows.append(derived(18, "Cash App GAAP Gross Profit",
                        positive=CA_CORE_METRICS + ["ca_borrow_gp", "ca_post_purchase_gp",
                                                     "ca_pay_gp", "ca_other_gp"],
                        negative=[], is_total=True))
    # R19 Afterpay = subtotal of R20+R21+R22+R23 (BNPL items only — excludes R24, R25 per MRP)
    rows.append(derived(19, "Afterpay", positive=AP_BNPL_METRICS, negative=[]))
    # R20-R25 Afterpay sub-products
    rows.append(metric_row(20, "Core BNPL", "ap_core_bnpl_gp"))
    rows.append(metric_row(21, "Gift Card", "ap_gift_card_gp"))
    rows.append(metric_row(22, "Pay Monthly", "ap_pay_monthly_gp"))
    rows.append(metric_row(23, "Plus Card", "ap_plus_card_gp"))
    rows.append(metric_row(24, "Commerce Other*", "ap_commerce_other_gp"))
    rows.append(metric_row(25, "SUP Ads", "ap_sup_ads_gp"))
    # R26 Commerce GAAP GP = sum of R20-R25 (NOT afterpay_total metric — slight reconciliation
    # diff of ~$0.6M with brand metric due to 3059 Pre-purchase BNPL not appearing on table)
    rows.append(derived(26, "Commerce GAAP Gross Profit",
                        positive=AP_BNPL_METRICS + ["ap_commerce_other_gp", "ap_sup_ads_gp"],
                        negative=[], is_total=True))
    # R27 Total GAAP GP = R18 + R26 (cross-check: equals cash_app_brand_total_gp within rounding)
    rows.append(derived(27, "Total GAAP Gross Profit",
                        positive=CA_CORE_METRICS + ["ca_borrow_gp", "ca_post_purchase_gp",
                                                     "ca_pay_gp", "ca_other_gp"] +
                                 AP_BNPL_METRICS + ["ap_commerce_other_gp", "ap_sup_ads_gp"],
                        negative=[], is_total=True))
    # R28 Variable Opex — GAP (no per-brand metric in BDM; manual MRP uses Hyperion direct)
    rows.append(gap_row_t5(28, "Variable Opex", polarity="cost",
                           notes="BDM has no per-brand Variable Opex; manual MRP $265M (Apr'26) via Hyperion"))
    # R29 Variable Profit — GAP (depends on Variable Opex)
    rows.append(gap_row_t5(29, "Variable Profit", polarity="revenue", is_total=True,
                           notes="Depends on Variable Opex (GAP); manual MRP $388M (Apr'26)"))
    # R30 % Margin — GAP rate row (depends on Variable Profit). Uses rate-row cell layout
    # (col 2 empty, cols 3+4 pts deltas) when populated.
    rows.append(gap_row_t5(30, "% Margin", polarity="rate",
                           notes="Depends on Variable Profit (GAP); manual MRP 59.4% (Apr'26)"))

    return rows


# ============================================================
# Square detail (Table 6) builder — 20x5 layout
# Cols: [label, Actual, $ vs. Q2OL, % vs. Q2OL, YoY % Growth]
# ============================================================

def partial_gap_cells_t5(p: dict, gap_cols: tuple[int, ...], scale: str = "auto") -> list[CellSpec]:
    """4 cells for Table 5/6 where specific columns render [GAP].
    gap_cols are packet indices (1=$vsOL, 2=%vsOL most commonly)."""
    cells = cells_for_metric_t5(p, scale=scale)
    for col_idx in gap_cols:
        kind = cells[col_idx].col_kind
        cells[col_idx] = CellSpec(None, "[GAP]", kind)
    return cells


def _prior_month(yyyy_mm: str) -> str:
    y, m = map(int, yyyy_mm.split("-"))
    if m == 1:
        return f"{y - 1}-12"
    return f"{y}-{m - 1:02d}"


def build_square_detail(raw: dict, report_month: str = "2026-04",
                        yoy_month: str = "2025-04") -> list[RowSpec]:
    """18 data rows of Test tab Table 6 (Square detail).
    Row 0,1 = doc headers; not built here.

    NVA family (R02-R04) reports one month in arrears (35-day attribution lag).
    Those rows pull from `report_month − 1` and `yoy_month − 1`. See
    `feedback_nva_one_month_lag` memory.
    """
    rows: list[RowSpec] = []
    nva_report_month = _prior_month(report_month)
    nva_yoy_month = _prior_month(yoy_month)

    def metric_row(idx: int, label: str, metric: str,
                   polarity: str = "revenue", is_total: bool = False, scale: str = "auto") -> RowSpec:
        p = fetch_periods_t5(raw, metric, report_month, yoy_month)
        return RowSpec(row_idx=idx, label=label, cells=cells_for_metric_t5(p, scale=scale),
                       polarity=polarity, is_total=is_total)

    def partial_row(idx: int, label: str, metric: str,
                    polarity: str = "revenue", scale: str = "auto",
                    gap_cols: tuple[int, ...] = (1, 2),
                    note: str = "vs Q2OL cols GAP — no outlook metric in BDM",
                    rm: str | None = None, ym: str | None = None):
        p = fetch_periods_t5(raw, metric, rm or report_month, ym or yoy_month)
        return RowSpec(row_idx=idx, label=label, cells=partial_gap_cells_t5(p, gap_cols, scale=scale),
                       polarity=polarity, notes=note)

    def derived(idx: int, label: str, positive: list[str], negative: list[str],
                polarity: str = "revenue", is_total: bool = False) -> RowSpec:
        pos = sum_periods_t5([fetch_periods_t5(raw, m, report_month, yoy_month) for m in positive])
        neg = sum_periods_t5([fetch_periods_t5(raw, m, report_month, yoy_month) for m in negative]) \
              if negative else {"actual": 0.0, "ol": 0.0, "yoy_prior": 0.0}
        per = {k: (pos[k] - neg[k]) if (pos[k] is not None and neg[k] is not None) else None
               for k in ["actual", "ol", "yoy_prior"]}
        cells = cells_for_metric_t5(per)
        note = f"Derived: + {' + '.join(positive)}" + (f" - {' - '.join(negative)}" if negative else "")
        return RowSpec(row_idx=idx, label=label, cells=cells, polarity=polarity,
                       is_total=is_total, notes=note)

    # R02-R04 NVA family (no outlook in BDM; one-month lag — see feedback_nva_one_month_lag)
    nva_note = (f"vs Q2OL cols GAP — no outlook metric in BDM. "
                f"Actual + YoY from {nva_report_month} / {nva_yoy_month} (one-month lag per attribution rule).")
    rows.append(partial_row(2, "New Volume Added*", "sq_nva_total",
                            rm=nva_report_month, ym=nva_yoy_month, note=nva_note))
    rows.append(partial_row(3, "Self-Onboard", "sq_nva_self_onboarded",
                            rm=nva_report_month, ym=nva_yoy_month, note=nva_note))
    rows.append(partial_row(4, "Sales", "sq_nva_sales",
                            rm=nva_report_month, ym=nva_yoy_month, note=nva_note))
    # R05-R07 GPV (no outlook in BDM)
    rows.append(partial_row(5, "GPV", "sq_gpv_total"))
    rows.append(partial_row(6, "U.S. GPV", "sq_gpv_us"))
    rows.append(partial_row(7, "International GPV", "sq_gpv_intl"))
    # R08 section header
    rows.append(section_row_t5(8, "Gross profit by product"))
    # R09-R10 US/Intl Payments — no country dim on pnl_gross_profit_*; vs OL cols GAP
    rows.append(partial_row(9, "U.S. Payments", "sq_us_payments",
                            note="Derived as Processing - Intl entity GP (BDM has no country split). vs Q2OL cols GAP."))
    rows.append(partial_row(10, "International Payments", "sq_intl_payments",
                            note="Intl entity GP proxy (BDM has no Payments-by-country metric). vs Q2OL cols GAP."))
    # R11 SaaS
    rows.append(metric_row(11, "SaaS", "sq_saas_gp"))
    # R12 Banking = R13 + R14 (derived subtotal)
    rows.append(derived(12, "Banking", positive=["sq_loans_gp", "sq_biz_banking_gp"], negative=[],
                        is_total=True))
    # R13 Loans (= Capital)
    rows.append(metric_row(13, "Loans", "sq_loans_gp"))
    # R14 Business Banking (= Banking ex-Capital)
    rows.append(metric_row(14, "Business Banking", "sq_biz_banking_gp"))
    # R15 Hardware
    rows.append(metric_row(15, "Hardware", "sq_hardware_gp"))
    # R16 Total Gross Profit (brand-level)
    rows.append(metric_row(16, "Total Gross Profit", "sq_brand_total_gp", is_total=True))
    # R17-R19 Variable Opex / Profit / Margin — GAP (no per-brand Variable Opex in BDM)
    rows.append(gap_row_t5(17, "Variable Opex", polarity="cost",
                           notes="BDM has no per-brand Variable Opex; manual MRP $23M (Apr'26) via Hyperion"))
    rows.append(gap_row_t5(18, "Variable Profit", polarity="revenue", is_total=True,
                           notes="Depends on Variable Opex (GAP); manual MRP $340M (Apr'26)"))
    rows.append(gap_row_t5(19, "% Margin", polarity="rate",
                           notes="Depends on Variable Profit (GAP); manual MRP 93.6% (Apr'26)"))

    return rows


# ============================================================
# Main packet assembly + CLI
# ============================================================

def assemble_packet(raw: dict, report_month: str,
                    cash_app_raw: dict | None = None,
                    square_raw: dict | None = None) -> dict:
    anchors = compute_anchors(report_month)
    block_rows = build_block_pl_overview(raw, anchors)
    stnd_rows = build_stnd_pl_double_click(raw, anchors)

    all_rows = block_rows + stnd_rows
    cash_app_block = None
    if cash_app_raw is not None:
        ca_rows = build_cash_app_detail(
            cash_app_raw,
            report_month=report_month,
            yoy_month=anchors["yoy_prior_month"],
        )
        cash_app_block = {"table_index": 5, "rows": [r.to_json() for r in ca_rows]}
        all_rows = all_rows + ca_rows

    square_block = None
    if square_raw is not None:
        sq_rows = build_square_detail(
            square_raw,
            report_month=report_month,
            yoy_month=anchors["yoy_prior_month"],
        )
        square_block = {"table_index": 6, "rows": [r.to_json() for r in sq_rows]}
        all_rows = all_rows + sq_rows

    gaps = list({r.label for r in all_rows if r.is_gap})
    packet = {
        "meta": {
            "report_month": report_month,
            "quarter": anchors["quarter"],
            "ol_label": anchors["ol_label"],
            "ol_scenario": anchors["ol_scenario"],
            "ap_scenario": anchors["ap_scenario"],
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "qtd_pace_contingency_note": "Automated qtd_pace = qtd_actuals + Q2OL_remaining. "
                                          "Manual MRP applies a judgment contingency (~$20M for Apr'26). "
                                          "Layer 2 validation flags the divergence.",
        },
        "anchors": anchors,
        "block_pl_overview": {
            "table_index": 2,
            "rows": [r.to_json() for r in block_rows],
        },
        "stnd_pl_double_click": {
            "table_index": 3,
            "rows": [r.to_json() for r in stnd_rows],
        },
        "gaps": gaps,
    }
    if cash_app_block is not None:
        packet["cash_app_detail"] = cash_app_block
    if square_block is not None:
        packet["square_detail"] = square_block
    return packet


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MRP data layer helper")
    p.add_argument("--month", required=True, help="Report month YYYY-MM")
    p.add_argument("--raw", required=True, help="Path to raw JSON input (Tables 2+3)")
    p.add_argument("--cash-app-raw", default=None,
                   help="Optional path to raw JSON for Cash App detail (Table 5)")
    p.add_argument("--square-raw", default=None,
                   help="Optional path to raw JSON for Square detail (Table 6)")
    p.add_argument("--out", required=True, help="Path to output JSON packet")
    args = p.parse_args(argv)

    with open(args.raw) as f:
        raw = json.load(f)

    cash_app_raw = None
    if args.cash_app_raw:
        with open(args.cash_app_raw) as f:
            cash_app_raw = json.load(f)
    square_raw = None
    if args.square_raw:
        with open(args.square_raw) as f:
            square_raw = json.load(f)

    packet = assemble_packet(raw, args.month, cash_app_raw=cash_app_raw, square_raw=square_raw)

    with open(args.out, "w") as f:
        json.dump(packet, f, indent=2, default=str)

    n_t2 = len(packet["block_pl_overview"]["rows"])
    n_t3 = len(packet["stnd_pl_double_click"]["rows"])
    n_t5 = len(packet["cash_app_detail"]["rows"]) if "cash_app_detail" in packet else 0
    n_t6 = len(packet["square_detail"]["rows"]) if "square_detail" in packet else 0
    n_gaps = len(packet["gaps"])
    extras = []
    if n_t5: extras.append(f"Cash App {n_t5} rows")
    if n_t6: extras.append(f"Square {n_t6} rows")
    extras_str = (", " + ", ".join(extras)) if extras else ""
    print(f"Wrote {args.out}: Block P&L {n_t2} rows, Stnd P&L {n_t3} rows{extras_str}, {n_gaps} unique gaps")
    if packet["gaps"]:
        print("Gaps: " + ", ".join(sorted(packet["gaps"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
