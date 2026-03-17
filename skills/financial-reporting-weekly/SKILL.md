---
name: financial-reporting-weekly
description: Weekly financial report domain knowledge for Block FP&A. Defines section structure, table specs, emoji logic, and 3/10 canonical reference. Depends on financial-reporting global recipe.
depends-on: [financial-reporting, gdrive]
metadata:
  author: nmart
  version: "2.0.0"
  status: "active"
---

# Weekly Performance Digest — Domain Knowledge

This skill defines WHAT goes in the report. The agent handles HOW to execute it.
All style, formatting, and number rules come from the global recipe (`financial-reporting`).

---

## Canonical Reference: 3/10 Tab

The 3/10 tab (`t.kock4ypqjpk6`) in the Weekly Report Doc is the gold standard.
Every new tab must mirror its structure: section order, heading names, table layout, fact line style.
Do not read the 3/10 tab at runtime — the structure is fully defined here.

---

## Inputs

- **Master Google Sheet:** `1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4`
- **Weekly Report Google Doc:** `1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0`
- **Sheet tab to read:** `summary` (use `--sheet summary` — do not read `--all-sheets`)

---

## Emoji Logic

Apply to each metric's **delta vs. [Forecast]** only — never to YoY:

| Delta vs. [Forecast] | Emoji |
|----------------------|-------|
| > +0.5%              | 🟢    |
| −0.5% to +0.5%       | 🟡    |
| < −0.5%              | 🔴    |

- Month-level metrics → use monthly pacing delta
- Quarter-level metrics → use QTD pacing delta
- bps metrics (monetization rate) → same thresholds in bps

---

## Report Structure

Five sections, in this order:

1. **Summary**
2. **Overview: Gross Profit Performance**
3. **Overview: Adjusted Operating Income & Rule of 40**
4. **Overview: Inflows Framework**
5. **Overview: Square GPV**

Each Overview section: table first, then fact lines beneath it.

---

## Section 1 — Summary

The Summary is a narrative block of emoji-prefixed fact lines. Mirror the 3/10 Summary exactly in structure and flow:

- Opens with **Topline** (Block GP QTD and monthly pacing, above/below [Forecast] and guidance)
- Then **Square GPV** block (global + US + International sub-lines)
- Then individual Cash App metric lines (Cash ex-Commerce GP, Lending, Non-Lending)
- Then **Inflows Framework** block (Actives, Inflows per active, Monetization rate, Commerce lines, Proto)
- Closes with **Profitability** (AOI QTD and monthly, Rule of 40)

After each major block where driver context would normally follow, insert `Nick to fill out` on a new line (will be colored red by the agent in a later step).

---

## Section 2 — Overview: Gross Profit Performance

**Table columns:** Metric | Jan'26 Actual | Feb'26 Actual | Mar'26 Pacing | Q1'26 Pacing | Q1 AP | Q1 Guidance | Q1 Consensus

Omit Guidance or Consensus columns if unavailable for that metric. Use `--` for N/A cells.

**Table row groups:**
- Block gross profit / YoY Growth (%) / Delta vs. AP (%)
- Cash App gross profit / YoY Growth (%) / Delta vs. AP (%)
- Square gross profit / YoY Growth (%) / Delta vs. AP (%)
- Proto gross profit / YoY Growth (%) / Delta vs. AP (%)
- TIDAL gross profit / YoY Growth (%) / Delta vs. AP (%)

Separate each group with a blank row.

**Fact lines (after table):** One per brand — Block GP, Cash App GP, Square GP, Proto GP, TIDAL GP — plus a QTD summary line for Block. Mirror 3/10 wording and order.

---

## Section 3 — Overview: Adjusted Operating Income & Rule of 40

**Table columns:** Metric | Jan'26 Actual | Feb'26 Actual | Mar'26 Pacing | Q1'26 Pacing | Q1 AP | Q1 Guidance | Q1 Consensus

**Table row groups:**
- Gross profit / YoY Growth (%) / Delta vs. AP (%)
- Adjusted operating income / Margin (%) / Delta vs. AP (%)
- Rule of 40 / Delta vs. AP (pts)

**Fact lines (after table):** Monthly AOI (value, margin, delta vs. AP), Rule of 40 for the month, QTD AOI (value, margin, vs. guidance and consensus), QTD Rule of 40.

---

## Section 4 — Overview: Inflows Framework

Two sub-sections: **Cash App (Ex Commerce)** and **Commerce**. Each has its own table and fact lines.

**Cash App (Ex Commerce) table columns:** Metric | Jan'26 Actual | Feb'26 Actual | Mar'26 Pacing | Q1'26 Pacing | Q1 AP | Q1 Consensus

**Cash App row groups:**
- Actives / YoY Growth (%) / Delta vs. AP (%)
- Inflows per Active / YoY Growth (%) / Delta vs. AP (%)
- Monetization rate / YoY Growth (bps) / Delta vs. AP (bps)

**Commerce table columns:** Metric | Jan'26 Actual | Feb'26 Actual | Mar'26 Pacing | Q1'26 Pacing | Q1 AP

**Commerce row groups:**
- Inflows / YoY Growth (%) / Delta vs. AP (%)
- Monetization rate / YoY Growth (bps) / Delta vs. AP (bps)

---

## Section 5 — Overview: Square GPV

**Table columns:** Metric | Jan'26 Actual | Feb'26 Actual | Mar'26 Pacing | Q1'26 Pacing | Q1 AP | Q1 Consensus

**Table row groups:**
- Global GPV / YoY Growth (%) / Delta vs. AP (%)
- US GPV / YoY Growth (%) / Delta vs. AP (%)
- International GPV / YoY Growth (%) / Delta vs. AP (%)

**Fact lines (after table):** Global GPV, US GPV, International GPV monthly pacing lines, QTD summary line, GPV-to-GP spread note.

---

## Metrics in Scope

Populate emoji, fact line, and table for:
- Block gross profit
- Cash App gross profit
- Square gross profit
- Proto gross profit
- TIDAL gross profit
- Cash App Monthly Actives
- Cash App Inflows per Active
- Cash App monetization rate (ex-Commerce)
- Commerce Inflows
- Commerce monetization rate
- Adjusted Operating Income (AOI)
- Rule of 40
- Square GPV (Global, US, International)
- Pacing vs. AP / consensus / guidance where available
