#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
from __future__ import annotations
"""
validate_rollups.py

Verify aggregation integrity in the master pacing sheet:
- Brand-level GP (Cash + Square + Proto + TIDAL) sums to Block GP
- Cash sub-products (Ex-Commerce + Commerce) sum to Cash App total
- Lending + Non-Lending sums to Cash Ex-Commerce
- Brand deltas vs forecast sum to Block delta
- Brand WoW sums to Block WoW
- US + Intl GPV sums to Global GPV

Tolerances are scaled to absorb sheet display rounding without masking real
discrepancies. Any check exceeding tolerance is flagged FAIL.

Usage:
    python3 validate_rollups.py SHEET_JSON

Output:
    Prints a markdown-formatted report to stdout. Exit code 0 if all checks
    pass within tolerance, 1 if any check fails.
"""
import json
import sys
import re

# Tolerance: any residual at/below this absolute $M is treated as rounding
# noise. Scale chosen so brand-level rollups (~$3B Block GP) tolerate the
# combined display rounding from 4 brands and parent (each ~$0.5M).
TOL_DOLLARS_M = 2.0       # most $M roll-ups
TOL_DOLLARS_GPV_M = 200.0 # GPV roll-ups at $20B+ scale (display in $0.1B)


def parse_dollar(s):
    """Parse a dollar string like '$1,009M', '($24M)', '$23.1B' to millions."""
    if s is None or s == "":
        return None
    s = str(s).strip()
    if s in ("--", "nm", "-"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.replace("(", "").replace(")", "").replace("$", "").replace(",", "").replace(" ", "")
    suffix = s[-1] if s and s[-1] in ("M", "B", "K") else ""
    if suffix:
        s = s[:-1]
    try:
        v = float(s)
    except ValueError:
        return None
    if suffix == "B":
        v *= 1000
    elif suffix == "K":
        v /= 1000
    return -v if neg else v


def cell(rows, r, c):
    if r >= len(rows) or c >= len(rows[r]):
        return None
    return rows[r][c]


def fmt(v):
    if v is None:
        return "<none>"
    return f"{v:>+9.2f}M" if v < 0 else f"{v:>9.2f}M"


def check(label, parts, total, tol):
    """Run one roll-up check. Returns (status, line, residual)."""
    s = sum(p for p in parts if p is not None)
    if total is None:
        return ("SKIP", f"  {label}: total not reported", 0.0)
    diff = s - total
    status = "PASS" if abs(diff) <= tol else "FAIL"
    return (status, f"  {label}: sum={s:.2f}M, reported={total:.2f}M, diff={diff:+.2f}M (tol ±{tol}M) [{status}]", diff)


def main():
    if len(sys.argv) != 2:
        print("Usage: validate_rollups.py SHEET_JSON", file=sys.stderr)
        sys.exit(2)

    with open(sys.argv[1]) as f:
        sheet = json.load(f)
    rows = sheet["values"]

    # Sheet column indices (Q2 layout, vintage 2026-04-27):
    # 11 = current-month Pacing, 17 = Q-Pacing, 23 = month delta vs OL $,
    # 22 = Q delta vs OL $, 25 = month WoW $, 28 = Q WoW $.
    APRIL_COL = 11
    Q_COL = 17
    MONTH_DELTA_COL = 23
    Q_DELTA_COL = 22
    MONTH_WOW_COL = 25
    Q_WOW_COL = 28

    # Sheet rows for value lines (these are stable in the master sheet):
    BLOCK_GP, CASH_GP, SQUARE_GP, PROTO_GP, TIDAL_GP = 12, 16, 20, 24, 28
    CASH_EXC, COMMERCE_GP = 117, 121
    LENDING_GP, NONLENDING_GP = 126, 130
    GLOBAL_GPV, US_GPV, INTL_GPV = 96, 100, 104

    def v(row, col):
        return parse_dollar(cell(rows, row, col))

    results = []
    fail_count = 0

    print("# Roll-up integrity report\n")

    # 1. Brand → Block GP (April)
    print("## GP roll-up: brand-level → Block")
    for label, col, tol in [("April Pacing", APRIL_COL, TOL_DOLLARS_M),
                            ("Q-quarter Pacing", Q_COL, TOL_DOLLARS_M)]:
        parts = [v(CASH_GP, col), v(SQUARE_GP, col), v(PROTO_GP, col), v(TIDAL_GP, col)]
        total = v(BLOCK_GP, col)
        s, line, _ = check(label, parts, total, tol)
        print(line)
        results.append((s, f"GP brands → Block ({label})"))
        if s == "FAIL": fail_count += 1
    print()

    # 2. Cash sub-products → Cash total
    print("## Cash sub-product roll-up: Ex-Commerce + Commerce → Cash App")
    for label, col in [("April Pacing", APRIL_COL), ("Q-quarter Pacing", Q_COL)]:
        parts = [v(CASH_EXC, col), v(COMMERCE_GP, col)]
        total = v(CASH_GP, col)
        s, line, _ = check(label, parts, total, TOL_DOLLARS_M)
        print(line)
        results.append((s, f"Cash sub-products → Cash ({label})"))
        if s == "FAIL": fail_count += 1
    print()

    # 3. Lending + Non-Lending → Cash Ex-Commerce
    print("## Cash Ex-Commerce decomposition: Lending + Non-Lending")
    for label, col in [("April Pacing", APRIL_COL), ("Q-quarter Pacing", Q_COL)]:
        parts = [v(LENDING_GP, col), v(NONLENDING_GP, col)]
        total = v(CASH_EXC, col)
        s, line, _ = check(label, parts, total, TOL_DOLLARS_M)
        print(line)
        results.append((s, f"Lending + Non-Lending → Cash Ex-Comm ({label})"))
        if s == "FAIL": fail_count += 1
    print()

    # 4. Delta vs forecast roll-up
    print("## Delta vs forecast roll-up: brand deltas → Block delta")
    for label, col in [("April $", MONTH_DELTA_COL), ("Q-quarter $", Q_DELTA_COL)]:
        parts = [v(CASH_GP, col), v(SQUARE_GP, col), v(PROTO_GP, col), v(TIDAL_GP, col)]
        total = v(BLOCK_GP, col)
        s, line, _ = check(label, parts, total, TOL_DOLLARS_M)
        print(line)
        results.append((s, f"Brand Δ → Block Δ ({label})"))
        if s == "FAIL": fail_count += 1
    print()

    # 5. WoW roll-up
    print("## WoW roll-up: brand WoW → Block WoW")
    for label, col in [("April $", MONTH_WOW_COL), ("Q-quarter $", Q_WOW_COL)]:
        parts = [v(CASH_GP, col), v(SQUARE_GP, col), v(PROTO_GP, col), v(TIDAL_GP, col)]
        total = v(BLOCK_GP, col)
        s, line, _ = check(label, parts, total, TOL_DOLLARS_M)
        print(line)
        results.append((s, f"Brand WoW → Block WoW ({label})"))
        if s == "FAIL": fail_count += 1
    print()

    # 6. GPV: US + Intl → Global
    print("## Square GPV roll-up: US + Intl → Global")
    for label, col in [("April Pacing", APRIL_COL), ("Q-quarter Pacing", Q_COL)]:
        parts = [v(US_GPV, col), v(INTL_GPV, col)]
        total = v(GLOBAL_GPV, col)
        s, line, _ = check(label, parts, total, TOL_DOLLARS_GPV_M)
        print(line)
        results.append((s, f"US + Intl → Global GPV ({label})"))
        if s == "FAIL": fail_count += 1
    print()

    # Summary
    n = len(results)
    passed = sum(1 for s, _ in results if s == "PASS")
    skipped = sum(1 for s, _ in results if s == "SKIP")
    print(f"## Summary\n")
    print(f"- Total checks: {n}")
    print(f"- Passed: {passed}")
    print(f"- Skipped: {skipped}")
    print(f"- Failed: {fail_count}")
    print(f"- Result: **{'PASS' if fail_count == 0 else 'FAIL'}**")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
