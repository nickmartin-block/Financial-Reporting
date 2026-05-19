# Sandbox

Scratchpad for **net-new files in development** before they're ready to live in their canonical location. This folder solves the testing-before-shipping problem without recreating the stale-duplicate problem we cleaned up in May 2026.

## Two failure modes this is designed to avoid

The previous `~/skills/skills-staging/` directory drifted because:
- Files lived in both staging AND canonical locations simultaneously
- No promotion ritual — copies were made, not moves
- Edits happened directly in canonical, bypassing staging

This folder eliminates both modes by design.

## Rules

1. **Sandbox is for new files only.** If a canonical version of the file already exists somewhere in this repo, do not create a sandbox copy. Use a git branch for changes to existing files.
2. **Promote via `git mv`, never `cp`.** When a sandbox file is ready, move it into its canonical location in the same commit. The sandbox copy ceases to exist. Example:
   ```
   git mv sandbox/new-skill.md skills/weekly-reporting/skills/new-skill.md
   git commit -m "promote new-skill from sandbox to weekly-reporting"
   ```
3. **No copies, ever.** A file lives in `sandbox/` or in its canonical location — never both.
4. **Existing-file changes go on a branch.** Don't drop a modified copy of an existing canonical file into `sandbox/`. Use `git checkout -b experiment-foo`, iterate, merge or discard.

## Testing while in sandbox

Files in `sandbox/` are not loaded by any agent or skill — they're inert until promoted. To test before promotion:

- For a draft skill or command: temporarily reference it by full path (e.g., `~/Desktop/Nick's Cursor/Corporate-Financial-Reporting/sandbox/draft-foo.md`) from your invocation
- For a draft script: run it directly via Python or shell; do not import it from `~/skills/<workflow>/`
- When validated, promote with `git mv` and the live agent pipeline picks it up automatically (via the workflow symlinks)

## Audit

`audit-skills-drift.py` at the repo root scans for:
- Files in `sandbox/` that are byte-identical to a non-sandbox file (failed promotion left a copy)
- Files outside `sandbox/` with a duplicate-by-name in `sandbox/` (sandbox copy lingered after promotion)

Run on demand: `python3 audit-skills-drift.py`
