---
name: financial-reporting-weekly
description: Weekly financial report sub-agent for Block FP&A. Reads the master Google Sheet, creates a new dated tab in the weekly report Google Doc, populates tables and metric fact lines, and inserts placeholders for missing data and driver context. Use when Nick says "data is ready, run the weekly report." Must be loaded with the financial-reporting skill (global recipe).
depends-on: [financial-reporting, gdrive]
allowed-tools: [Bash(uv:*), Read]
metadata:
  author: nmart
  version: "1.0.0"
  status: "beta"
---

# Weekly Report Sub-Agent

## Prerequisites
Before running any step, verify auth: `cd ~/skills/gdrive && uv run gdrive-cli.py auth status`
If not authenticated, run `uv run gdrive-cli.py auth login` and stop.

## Trigger
Manual only. Nick will say: **"data is ready, run the weekly report."**
Never self-initiate. Never run on a schedule.

## Inputs
- **Master Google Sheet:** `1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4`
  https://docs.google.com/spreadsheets/d/1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4/edit
- **Weekly Report Google Doc:** `1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0`
  https://docs.google.com/document/d/1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0/edit

## Workflow

**Step 1 — Load and internalize the global recipe**
The `financial-reporting` skill is already loaded via `depends-on`. Confirm all style rules,
metric formats, comparison points, and deviation handling are active. These may not be overridden.

**Step 2 — Determine the comparison point**
Identify the current quarter and apply the correct forecast label:

| Quarter | Comparison Point |
|---------|-----------------|
| Q1      | AP              |
| Q2      | Q2OL            |
| Q3      | Q3OL            |
| Q4      | Q4OL            |

Use this label wherever `[Forecast]` appears in metric format templates.

**Step 3 — Read the master Google Sheet**
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py read 1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4
```
- Identify all metrics (rows) and time periods (columns)
- Note which periods are closed (actuals) vs. open (pacing)
- Note available benchmarks: internal forecast, consensus, guidance

**Step 4 — Review prior weeks in the report Doc**
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs tabs 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0
```
Read the most recent 2–3 tabs (e.g., '3/3', '2/24', '2/17') to understand:
- Section structure and order
- Level of detail in fact lines
- Table placement vs. narrative blocks

**Step 5 — Create a new tab for this week**
Label the new tab with this Tuesday's date (e.g., '3/10').
Use the prior week's tab as the structural template — copy the layout exactly.

**Step 6 — Populate the report**
For each section:
1. Copy updated data tables from the Sheet into the Doc (exact values, no reformatting beyond global recipe rules)
2. For each metric, write a fact line using the correct format:
   - **Pacing:** `[Metric] is pacing to [Value] in [Period] ([+/-]% YoY), [+/-]% ([+/-$]) [above/below] [Forecast]`
   - **Actuals:** `[Metric] landed at [Value] ([+/-]% YoY), [+/-]% ([+/-$]) [above/below] [Forecast]`
3. After any fact line where driver context is needed, insert on a new line:
   **Nick to fill out** — formatted in red (hex #ea4335) in the Google Doc
4. For any missing data, insert:
   `[DATA MISSING: {metric} | {period}]`

**Step 7 — Report back**
List:
- Which sections were populated successfully
- Which have `[DATA MISSING]` flags and what is missing
- Which have **Nick to fill out** (red) placeholders inserted

## What This Agent Does NOT Do
- Fill in drivers, narrative, or explanations — that is Nick's job
- Estimate or infer missing data
- Override any global recipe rule
- Self-trigger or run automatically

## Metrics in Scope
Populate fact lines for all of the following (source from Sheet):
- Block gross profit
- Square gross profit
- Cash App gross profit
- Square GPV
- Cash App Inflows
- Cash App Monthly Actives
- Cash App monetization rate
- Commerce Inflows
- Commerce monetization rate
- Adjusted Operating Income (AOI)
- Pacing vs. AP / consensus / guidance (where applicable)
