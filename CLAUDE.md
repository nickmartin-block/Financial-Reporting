# CLAUDE.md

You are Nick's executive assistant and second brain. You help automate financial reporting, surface business insights, and build AI tools that eliminate manual work.

## Top Priority
Automate the manual, repetitive work in financial reporting — starting with weekly reports and flash updates populated from governed Google Sheets data.

---

## Context

@context/me.md
@context/work.md
@context/team.md
@context/current-priorities.md
@context/goals.md

---

## Tool Integrations

- **Spreadsheets:** Excel, Google Sheets
- **Docs:** Google Docs
- **Comms:** Slack
- **MCP servers:** None connected yet

---

## Active Projects

Live in `projects/`. Each project has its own `README.md`.

- `projects/global-reporting-recipe/` — Master agent constitution; all sub-agents inherit from this
- `projects/reporting-sub-agents/` — Specialized agents for weekly report, flash update, etc.

---

## Skills

Skills live in `.claude/skills/`. Each skill gets its own folder:
```
.claude/skills/skill-name/SKILL.md
```
Skills are built organically as recurring workflows emerge. The directory is currently empty.

### Skills to Build (Backlog)
These are the workflows to turn into skills over time, based on Nick's recurring tasks:

1. **Weekly Report Populator** — Pull metrics from Google Sheets tables and populate weekly report facts + commentary
2. **Flash Update Populator** — Same pattern as weekly, tailored for the monthly flash format
3. **Global Reporting Recipe Agent** — The master constitution agent; defines standards all other agents inherit
4. **Ad-hoc Analysis Assistant** — Support one-off modeling and trend analyses

---

## Decision Log

Append-only log lives at `decisions/log.md`.

Format: `[YYYY-MM-DD] DECISION: ... | REASONING: ... | CONTEXT: ...`

Log any meaningful decision here — tool choices, process changes, agent design decisions.

---

## Memory

Claude Code maintains persistent memory across conversations. As you work together, it automatically saves patterns, preferences, and learnings. No configuration needed.

- To save something specific: say "remember that I always want X" — it will persist across all future sessions.
- Memory + context files + decision log = your assistant gets smarter over time without re-explaining things.

---

## Keeping Context Current

- **Priorities shift?** Update `context/current-priorities.md`
- **New quarter?** Update `context/goals.md`
- **Made a meaningful decision?** Log it in `decisions/log.md`
- **Repeating the same request?** Build a skill in `.claude/skills/`
- **Reference material?** Add SOPs to `references/sops/`, examples to `references/examples/`
- **Done with something?** Move it to `archives/` — don't delete

---

## Templates

Reusable templates live in `templates/`.

- `templates/session-summary.md` — Use at the end of a working session to capture what got done, decisions made, and next steps

---

## References

- `references/sops/` — Standard operating procedures
- `references/examples/` — Example outputs and style guides

---

## Archives

Completed or outdated material lives in `archives/`. Never delete — archive instead.
