"""
populate_block_pl.py — populate the Block P&L Overview table (Test tab Table 2, 30x7).

Status: v0.0 scaffold (2026-05-19). Implementation in Phase 3.

Reads the JSON packet emitted by mrp_data.py, builds Docs API batchUpdate
requests targeting each cell's startIndex inside Table 2 of the Test tab,
and applies values + colors + bold + Roboto 10pt formatting.

Safety: refuses to write if the target tab ID matches the MRP tab
(t.ea3bz9hprpol) — only the Test tab (t.3mz1duijrdf1) is writable.

Usage (planned):
    python populate_block_pl.py --doc <DOC_ID> --tab <TAB_ID> --packet /tmp/mrp_out_2026_04.json
"""

import sys


def main() -> int:
    print("populate_block_pl.py: not yet implemented. See tasks/mrp_todo.md Phase 3.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
