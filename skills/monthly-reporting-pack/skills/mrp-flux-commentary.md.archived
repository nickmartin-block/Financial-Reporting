---
name: mrp-flux-commentary
description: Read flux commentary workbook (6 tabs) and map DRI driver narratives to MRP sections. Merges qualitative text into the quantitative framework.
depends-on:
  - financial-reporting
  - mrp-data-layer
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Read
metadata:
  author: nmart
  version: "1.0"
  status: active
---

# MRP Flux Commentary Skill

Read DRI driver narratives from the flux commentary workbook and map them to MRP sections. This skill bridges the qualitative layer (FP&A DRI text) with the quantitative framework (Block Data MCP metrics).

---

## Flux Commentary Sheet

- **Sheet ID:** `1qE80DGUNen0VIjisvUEhjVhjzWKwlY4LobCT1r4qvEw`
- **6 Tabs:** Cash App GP Summary, Square GP Summary, Other Brands GP Summary, Opex Summary, Personnel Summary, People Summary

### Sheet Structure (all tabs follow this pattern)

- **Header row:** Row 9 (Cash App/Square/Other Brands) or Row 9 (Opex/Personnel/People)
- **Column F:** "Actuals Commentary Y/N" -- flags products breaching threshold (+/-$2M or 5% for GP, +/-$500k or 5% for OpEx)
- **Column G:** Current Month Actual
- **Column H:** Latest Budget (AP)
- **Column I:** vs. Latest Budget $
- **Column J:** vs. Latest Budget %
- **Column K:** YoY Month (prior year actual)
- **Column L:** vs. YoY Month $
- **Column M:** vs. YoY Month %
- **Column N:** DRI Commentary -- the qualitative text to extract
  - Cash App/Square/Other Brands tabs: "Strat F&S Commentary"
  - Opex tab: "Strat F&S / Opex Team Commentary"
  - Personnel/People tabs: "WFP Commentary"

### Read Ranges

```bash
# GP tabs
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1qE80DGUNen0VIjisvUEhjVhjzWKwlY4LobCT1r4qvEw --range "Cash App GP Summary!A9:N69"
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1qE80DGUNen0VIjisvUEhjVhjzWKwlY4LobCT1r4qvEw --range "Square GP Summary!A9:N41"
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1qE80DGUNen0VIjisvUEhjVhjzWKwlY4LobCT1r4qvEw --range "Other Brands GP Summary!A9:N16"

# Cost tabs
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1qE80DGUNen0VIjisvUEhjVhjzWKwlY4LobCT1r4qvEw --range "Opex Summary!A9:N63"
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1qE80DGUNen0VIjisvUEhjVhjzWKwlY4LobCT1r4qvEw --range "Personnel Summary!A9:N43"
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1qE80DGUNen0VIjisvUEhjVhjzWKwlY4LobCT1r4qvEw --range "People Summary!A9:N23"
```

---

## Column N Extraction Logic

For each tab, read column N and extract rows where:
- Column N is non-empty (has commentary text)
- Column F = "Yes" (meets threshold) OR the product maps to a core MRP driver

---

## MRP Section -> Flux Source Mapping (Reverse Index)

This is the primary lookup: for each red placeholder in the MRP, where does the commentary come from?

### Block Financial Overview

| Placeholder | Flux Source |
|-------------|-----------|
| Growth composition context | No direct flux source -- synthesize from Cash App + Square GP data |
| GP expected to land at... | No direct flux source -- Q1 pacing context from Nick |
| AOI expected to land at... | No direct flux source -- Q1 pacing context from Nick |

### Watchpoints

| Placeholder | Flux Source |
|-------------|-----------|
| Watchpoint 1-3 | No flux source -- Nick fills manually each month |

### Gross Profit

| Placeholder | Flux Source |
|-------------|-----------|
| Cash App outperformance drivers | Aggregate: top commentary from Cash App GP Summary col N where F="Yes" |
| Square outperformance drivers | Aggregate: Square GP Summary -> Total Payments + SaaS + Banking + Hardware commentary |

### Operating Expenses

| Placeholder | Flux Source |
|-------------|-----------|
| Adjusted OpEx context | People Summary + Opex Summary -> Fixed Costs commentary |
| Variable cost drivers | Opex Summary -> Cash App + Commerce + Square variable cost rows |
| Acquisition cost drivers | Opex Summary -> Marketing + Onboarding + Partnership rows |
| Fixed cost drivers | Opex Summary -> All Functions Fixed Costs rows |

### Cash App Drivers (4 core + 1 dynamic)

| Driver | Flux Source Tab | Flux Row(s) | Commentary Column |
|--------|----------------|------------|------------------|
| Borrow | Cash App GP Summary | Row 15 (Borrow) | N |
| Commerce ex. CAP | Cash App GP Summary | Row 30 (BNPL) + Row 31-35 (Gift Card, Ads, Pay Monthly, Plus Card, Touch Pay Now) | N |
| Cash App Pay | Cash App GP Summary | Row 37 (Cash App Pay) | N |
| Cash App Card | Cash App GP Summary | Row 19 (Cash App Card) | N |
| Dynamic 5th (largest |$ delta vs AP|) | Cash App GP Summary | Determined at runtime from data packet | N |

Additional Cash App context:

| Topic | Flux Source |
|-------|-----------|
| Actives drivers | No flux source -- DATA GAP |
| P2P volume | No flux source -- DATA GAP |

### Square Drivers (5 fixed segments)

| Driver | Flux Source Tab | Flux Row(s) | Commentary Column |
|--------|----------------|------------|------------------|
| US Payments | Square GP Summary | Row 21 (US Payments GP) | N |
| International Payments | Square GP Summary | Row 22 (INTL Payments GP) | N |
| Banking | Square GP Summary | Row 33 (Total Banking) + Row 36-37 (US/INTL Loans) | N |
| SaaS | Square GP Summary | Row 29 (SaaS) | N |
| Hardware | Square GP Summary | Row 30 (Hardware total) | N |

Additional Square context:

| Topic | Flux Source |
|-------|-----------|
| US GPV drivers (NVR, SSG) | Square GP Summary Row 11 (US GPV) -- commentary may include NVR/SSG |
| INTL GPV drivers | Square GP Summary Row 12 (INTL GPV) |

### Other Brands

| Brand | Flux Source Tab | Flux Row | Commentary Column |
|-------|----------------|---------|------------------|
| TIDAL | Other Brands GP Summary | Row 10 | N |
| Proto | Other Brands GP Summary | Row 11 | N |
| Bitkey | Other Brands GP Summary | Row 12 | N |

### Opex Summary -> MRP Sections

| Flux Rows | BU | P&L Grouping | MRP Section | Commentary Target |
|-----------|-----|-------------|-------------|-------------------|
| 10-20 | Cash App | Variable Operational Costs | OpEx -> Variable costs | Variable cost drivers |
| 21-23 | Cash App | Acquisition Costs | OpEx -> Acquisition costs | Acquisition drivers |
| 24-27 | Commerce | Variable Operational Costs | OpEx -> Variable costs | Variable cost drivers |
| 28-30 | Commerce | Acquisition Costs | OpEx -> Acquisition costs | Acquisition drivers |
| 31-42 | Square | Variable / Acquisition | OpEx -> Variable / Acquisition | Drivers |
| 43-54 | All Functions | Fixed Costs | OpEx -> Fixed costs | **Fixed cost drivers** |

**Key OpEx rows for MRP narrative:**
- Row 15 (CA Risk Loss) + Row 24 (Commerce Risk Loss) + Row 33 (Sq Risk Loss) -> MRP "Risk loss" line
- Row 16 (Borrow Underwriting) -> context for Borrow driver
- Row 43 (Software & Cloud total) -> MRP "Software" + "Cloud" lines
- Row 48 (D&A and Other Non-Cash) -> MRP "Non-Cash expenses" line
- Rows 22-23 (CA Marketing + Onboarding) + Rows 28-29 (Commerce Marketing) + Row 43 (Square Marketing) -> MRP "Marketing" line

### Personnel Summary -> MRP Sections

Maps to the Operating Expenses narrative and People by Function table.

| BU | P&L Grouping | Functions | MRP Section |
|----|-------------|-----------|-------------|
| Cash App, Commerce, Square | Customer Support People | All | OpEx -> CS People line |
| Cash App, Commerce, Square, Emerging, Foundational | Sales & Marketing (People) | All | OpEx -> S&M People line |
| Block | Product Development People | Design, Engineering, Business, Hardware, Foundational, Risk, NonGAAP, Sales | OpEx -> PD People line |
| Block | G&A People (ex. CS) | Design, Engineering, Business, Hardware, Foundational, Risk, NonGAAP, Sales | OpEx -> G&A People line |

### People Summary -> MRP Sections

Block-level compensation breakdown -- provides context for overall people cost narrative.

| Grouping | MRP Use |
|----------|---------|
| Salary | People cost context |
| Taxes & Program Fees | People cost context |
| Benefits | People cost context |
| Commissions | People cost context |
| SBC | OpEx -> Non-cash SBC context |
| Contractors | People cost context |
| Cash Grants | People cost context |
| Travel & Entertainment | OpEx -> T&E context |

---

## Narrative Generation Procedure

### Step 1 -- Read Flux Sheet

Read column N from all 6 tabs using the ranges defined above. Extract rows where:
- Column N is non-empty (has commentary text)
- Column F = "Yes" (meets threshold) OR the product maps to a core MRP driver

### Step 2 -- Read Data Packet

Load `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_data_YYYY_MM.json` for quantitative values.

### Step 3 -- Assemble Driver Commentary

For each MRP section with a red placeholder, build the replacement text:

**Pattern for driver bullets:**
```
**[Product Name] ([YoY%] YoY)([vs AP $], [vs AP %] versus AP)** [DRI commentary from column N]
```

- YoY%, vs AP $, vs AP % come from the data packet (quantitative, governed)
- DRI commentary comes from column N (qualitative, from flux sheet)
- If column N is empty for a product, keep the red placeholder: `<<RED>>Nick to fill out -- [product] drivers<</RED>>`

**Pattern for section-level summaries (Gross Profit, OpEx):**
Synthesize from the individual product commentaries. Lead with the headline number (from data packet), then summarize the top 2-3 drivers citing the DRI commentary.

### Step 4 -- Handle Missing Commentary

For products where column N is empty:
- If the product is a core driver (Borrow, Card, etc.): `<<RED>>Nick to fill out -- [product] drivers<</RED>>`
- If the product is a detail/appendix row: leave as-is (no red placeholder needed for appendix rows)

### Step 5 -- Handle Products Not in MCP

Some products have flux commentary but no MCP metric. For these:
- Use the flux sheet's own quantitative columns (G-M) as a secondary source
- Mark quantitative from flux as `<<BLUE>>[from flux sheet -- not governed]<</BLUE>>` to distinguish from MCP data
- This is a stopgap until the metric is added to Block Data MCP

### Step 6 -- Output

Write the updated MRP markdown with commentary filled in. Color convention:
- **Black text:** Quantitative from Block Data MCP
- **`<<BLUE>>`Blue text`<</BLUE>>`:** Metrics not in MCP (data gap)
- **`<<RED>>`Red text`<</RED>>`:** Qualitative that still needs Nick's input (no flux commentary available)
- **Yellow highlight:** Table placeholder (future phase)

Commentary sourced from the flux sheet replaces red placeholders and renders as black text.

---

## Strat Fin DRI Reference

Each product has an assigned DRI in column E ("Strat Fin. DRI"). This is useful for:
- Knowing who to ask if commentary is missing
- Understanding ownership for follow-up questions

Key DRIs (from March 2026 sheet):

**Cash App:**
- Borrow: Gloria Mi
- Cash App Card: Shawn Luo
- Instant Deposit: Larry Liao
- Bitcoin Buy/Sell: Jonathan Gross
- Interest Income: Wendy Huang
- Business Accounts: Nate Scinta
- Cash Retro: Linda Zhang
- Commerce (BNPL/Ads/Gift Card/Pay Monthly/Plus Card): Jodie Lynn (Corp) + regional DRIs

**Square:**
- US GPV / US Payments: Nick Palermo
- International (GPV + Payments): Dennis Chau
- SaaS: Thomas Reinholm
- Banking / Loans: Linda Zhang (US + INTL)
- Hardware: Jacob Bajada
- Business Banking: Spencer Corpuz

**Other Brands:**
- TIDAL: Katherine Li
- Proto / Bitkey: Jason Lee
- Bitcoin Lightning: John Glance

**OpEx (Fixed Costs):**
- Software: Allen Lu
- Cloud: Luke Ilijevski
- Taxes, Insurance: Ashley Yoon, Chelsea Jang
- Litigation & Professional Services: Chelsea Jang
- Rent, Facilities: Chelsea Jang
- T&E: Grace Pak
- Hardware Production: Allen Lu
- D&A / Non-Cash: Nick Martin
