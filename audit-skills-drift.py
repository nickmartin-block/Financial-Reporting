#!/usr/bin/env python3
"""
audit-skills-drift.py — detect duplicate-but-divergent files and stale sandbox copies.

Run from anywhere:
    python3 ~/Desktop/Nick's\\ Cursor/Corporate-Financial-Reporting/audit-skills-drift.py

Or `cd Corporate-Financial-Reporting && python3 audit-skills-drift.py`.

What it checks:
1. Files in `sandbox/` that are byte-identical to a file in the canonical tree
   (failed promotion — sandbox copy was left behind).
2. Files in `sandbox/` with the same basename as a file in the canonical tree but
   divergent content (sandbox draft still in progress, or stale relative to canonical).
3. Files that exist in `~/skills/<workflow>/` AND `Corporate-FR/skills/<workflow>/`
   with the same relative path but as separate real files (not symlinks). These are
   candidates for symlink consolidation.

Exit code 0 = clean, 1 = drift detected.
"""
from __future__ import annotations
import hashlib
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SANDBOX = REPO_ROOT / "sandbox"
CANONICAL_SUBDIRS = ["skills", "finance-copilot", "pacing-dashboard"]
SKILLS_ROOT = Path.home() / "skills"

# Workflows expected to be symlinked into Corporate-FR (~/skills/<workflow>/ → Corporate-FR/skills/<workflow>/)
SYMLINKED_WORKFLOWS = [
    "weekly-reporting",
    "monthly-reporting-pack",
    "audit",
    "pacing-dashboard",
    "monthly-flash",
    "board-narrative",
]


def md5_of(path: Path) -> str | None:
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except (OSError, IsADirectoryError):
        return None


def all_files_under(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file() and not any(part.startswith(".git") for part in p.parts)]


def check_sandbox_drift() -> list[str]:
    """Find sandbox files that duplicate or shadow canonical files."""
    issues: list[str] = []
    if not SANDBOX.exists():
        return issues

    # Collect all canonical files (everything outside sandbox/)
    canonical_files = []
    for sub in CANONICAL_SUBDIRS:
        canonical_files.extend(all_files_under(REPO_ROOT / sub))
    # Also include root-level files
    canonical_files.extend([p for p in REPO_ROOT.iterdir() if p.is_file()])

    canonical_by_basename: dict[str, list[Path]] = {}
    for p in canonical_files:
        canonical_by_basename.setdefault(p.name, []).append(p)

    for sb_file in all_files_under(SANDBOX):
        if sb_file.name == "README.md" and sb_file.parent == SANDBOX:
            continue  # the sandbox README itself
        sb_hash = md5_of(sb_file)
        matches = canonical_by_basename.get(sb_file.name, [])
        for canon in matches:
            canon_hash = md5_of(canon)
            if sb_hash == canon_hash:
                rel_sb = sb_file.relative_to(REPO_ROOT)
                rel_cn = canon.relative_to(REPO_ROOT)
                issues.append(f"DUPLICATE: {rel_sb} is identical to {rel_cn} — promote ritual failed, delete sandbox copy")
            else:
                rel_sb = sb_file.relative_to(REPO_ROOT)
                rel_cn = canon.relative_to(REPO_ROOT)
                issues.append(f"SHADOW: {rel_sb} has same basename as {rel_cn} but differs — likely in-progress or stale")
    return issues


def check_workflow_symlinks() -> list[str]:
    """Find ~/skills/<workflow>/ files that diverge from Corporate-FR/skills/<workflow>/."""
    issues: list[str] = []
    for workflow in SYMLINKED_WORKFLOWS:
        live = SKILLS_ROOT / workflow
        canon = REPO_ROOT / "skills" / workflow
        if not live.exists() and not canon.exists():
            continue
        if not live.exists():
            issues.append(f"MISSING: ~/skills/{workflow}/ does not exist — Corporate-FR has it but live tree doesn't")
            continue
        if not canon.exists():
            issues.append(f"MISSING: Corporate-FR/skills/{workflow}/ does not exist — live tree has it but canonical doesn't")
            continue
        # If live is a symlink that resolves to canonical, perfect
        if live.is_symlink():
            resolved = live.resolve()
            if resolved == canon.resolve():
                continue
            else:
                issues.append(f"SYMLINK MISMATCH: ~/skills/{workflow}/ symlink points to {resolved}, expected {canon}")
                continue
        # Otherwise both are real directories — check for byte-level drift
        live_files = {p.relative_to(live): md5_of(p) for p in all_files_under(live)}
        canon_files = {p.relative_to(canon): md5_of(p) for p in all_files_under(canon)}
        all_rel = set(live_files) | set(canon_files)
        diverged = []
        for rel in sorted(all_rel):
            lh = live_files.get(rel)
            ch = canon_files.get(rel)
            if lh is None:
                diverged.append(f"  - canonical-only: {rel}")
            elif ch is None:
                diverged.append(f"  - live-only:      {rel}")
            elif lh != ch:
                diverged.append(f"  - DIVERGED:       {rel}")
        if diverged:
            issues.append(f"DUAL-COPY: ~/skills/{workflow}/ vs Corporate-FR/skills/{workflow}/ — not symlinked, content drift:")
            issues.extend(diverged)
    return issues


def main() -> int:
    print("=== Sandbox drift ===")
    sb = check_sandbox_drift()
    if sb:
        for issue in sb:
            print(f"  {issue}")
    else:
        print("  clean")

    print("\n=== Workflow symlinks ===")
    wf = check_workflow_symlinks()
    if wf:
        for issue in wf:
            print(f"  {issue}")
    else:
        print("  clean")

    total = len(sb) + len(wf)
    print(f"\n=== Summary: {total} issue(s) ===")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
