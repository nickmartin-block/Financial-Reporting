"""
mrp_data.py — MRP data layer.

Status: v0.0 scaffold (2026-05-19). Implementation in Phase 2.

Pulls in-scope MRP metrics from BDM + Snowflake, computes derivations
(Adj OpEx, V/A/F rollups, R40, GAAP OI, etc.), and emits a JSON packet
with both *_raw and *_formatted versions of every value.

Usage (planned):
    python mrp_data.py --month 2026-04 [--cache] [--out /tmp/mrp_out_2026_04.json]
"""

import sys


def main() -> int:
    print("mrp_data.py: not yet implemented. See tasks/mrp_todo.md Phase 2.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
