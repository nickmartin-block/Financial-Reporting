---
name: board-narrative
description: Review, refine, and gap-check board pre-read narratives. Pass a mode (gaps, refine, review, draft) and the section or doc link. Calibrates to Q4 2025 board pre-read voice.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Edit
  - Write
  - Bash
  - Agent
  - WebFetch
metadata:
  author: nmart
  version: "2.0"
  status: active
---

# /board-narrative — Board Pre-read Voice & Gap Detection

## Step 1 — Load references

Read these in parallel:

1. **Global recipe (formatting, style, terminology — governs everything):**
   ```
   /Users/nmart/skills/weekly-reporting/skills/financial-reporting.md
   ```
   This is the authoritative source for all number formatting, rounding, sign conventions, product names, terminology, dash usage, and punctuation. Every word in the narrative must comply.

2. **Source folder index:**
   ```
   /Users/nmart/Desktop/Nick's Cursor/q1-2026-source/INDEX.md
   ```

3. **Voice reference (skim Financial Summary + first 2 Watchpoints to recalibrate):**
   ```
   /Users/nmart/Desktop/Nick's Cursor/q1-2026-source/04-q4-2025-board-preread.md
   ```
   Read lines 0-50 to recalibrate on voice. Read more if needed for specific sections.

4. **Skill definition (for voice rules and modes):**
   ```
   /Users/nmart/skills/board-narrative/SKILL.md
   ```

## Step 2 — Determine mode

Parse the user's input to determine which mode to run:

| Input | Mode | What to do |
|-------|------|------------|
| `/board-narrative gaps` | Gap Detection | Read the draft doc (user provides link or pastes content). Cross-reference against ALL source docs in the source folder. Output numbered list of missing topics, thin sections, stale numbers, investor risk areas. |
| `/board-narrative refine` | Refinement | User provides a section. Rewrite to match voice calibration. Show original vs. refined side by side. |
| `/board-narrative review` | Full Review | Full pass on complete draft. Section-by-section voice assessment + gap detection + rewrites. |
| `/board-narrative draft` | Draft Assist | User provides topic + key points + numbers. Draft from scratch in established voice, pulling from source docs. |
| `/board-narrative audit` | Audit | User provides a section draft (pasted or via Google Doc link). Run every check in the Audit Framework (SKILL.md). Output pass/fail table + specific callouts + suggested rewrite if needed. |
| `/board-narrative` (no mode) | Interactive | Ask Nick which mode he wants, or if he just wants to chat about the narrative. |

## Step 3 — Execute

### For Gap Detection:
1. Read every source doc listed in INDEX.md (use agents in parallel for speed)
2. Read the current draft (user provides Google Doc link — use gdrive skill to read)
3. Build a checklist of topics/numbers/decisions from source docs
4. Compare against draft content
5. Output gaps as a numbered list with source references

### For Refinement:
1. Read the section Nick provides
2. Apply every rule from the Voice Calibration section of SKILL.md
3. Specifically check for:
   - Missing benchmark comparisons (vs. AP, consensus, Outlook, LRP)
   - Vague attribution (replace with specific drivers)
   - Missing offsetting dynamics
   - Sentences without numbers
   - Hedging language that should be direct
   - Em dashes (replace with commas, parentheses, or new sentences)
4. Present original and refined version in parallel blocks

### For Full Review:
1. Run gap detection first
2. Then refine each section that falls below the voice standard
3. Output a summary scorecard: section name, voice match (good/needs work), completeness (complete/gaps), specific notes

### For Draft Assist:
1. Gather Nick's inputs (topic, key points, numbers, framing preference)
2. Pull relevant context from source docs
3. Draft in the established voice
4. Flag any numbers that came from source docs vs. Nick's input
5. Flag any assumptions and ask Nick to confirm

### For Audit:
1. Read the Audit Framework section from SKILL.md
2. Read the draft section Nick provides (pasted text or Google Doc via gdrive)
3. Read the corresponding section from BOTH reference docs (Q4 2025 and Q1 2025 pre-reads) to compare framing
4. Run every check in the framework against the draft
5. Output the audit table format defined in SKILL.md
6. For any check that fails, provide a specific callout with the exact text that needs to change and why
7. If 3+ checks fail, draft a full rewrite of the section
8. Always note which reference doc (Q4 or Q1) informed each callout — this helps Nick understand whether the standard comes from the most recent doc or the same-quarter-last-year comp

## Step 1.5 — Load Q1 2025 reference (for audit mode)

For audit mode, also read the Q1 2025 pre-read to compare same-quarter framing:
```
/Users/nmart/Desktop/Nick's Cursor/q1-2026-source/05-q1-2025-board-preread.txt
```
This is critical for Q1-specific patterns: how actives softness was framed in Q1 2025, how the macro environment was handled, how forward guidance was positioned when growth was decelerating.

## Important Rules

- **Never fabricate numbers.** If you don't have a figure, say "[TBD — need X from source]"
- **Always cite source docs** when pulling specific figures for gap detection
- **Respect MNPI sensitivity** — flag if content needs special handling
- **No structure imposition** — follow whatever structure Nick has chosen for this quarter
- **Use gdrive to read Google Doc links:**
  ```bash
  cd ~/skills/gdrive && uv run gdrive-cli.py read {DOC_ID}
  ```
