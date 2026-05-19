---
name: mrp-brand-trends
description: Generate Topline Trends by Brand commentary (Cash App, Square, Other Brands) from data packet + flux commentary. Includes driver bullets with quantitative headers.
depends-on:
  - financial-reporting
  - mrp-data-layer
allowed-tools:
  - Read
metadata:
  author: nmart
  version: "1.0"
  status: active
---

# MRP Brand Trends Skill

Generate the **Topline Trends by Brand** section of the MRP:

- Cash App detail with 4 core + 1 dynamic driver
- Square detail with 5 fixed segment drivers
- Other Brands (TIDAL, Proto, Bitkey, Bitcoin Lightning)

---

## Input

1. Data packet JSON at `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_data_YYYY_MM.json`
2. Flux commentary (passed from mrp-flux-commentary skill, or empty)

---

## Color Convention

| Color | Meaning |
|-------|---------|
| Black | Quantitative from Block Data MCP (governed) |
| `<<BLUE>>` | Nick's judgment or metrics not in MCP (data gap) |
| `<<RED>>` | Data gap — placeholder for missing data or Nick's input |
| Yellow highlight | Table placeholder |

---

## Cash App Section

### GP Summary Line

**Pattern:**
```
In [Month], **Gross Profit** landed at $[X]M (+X% YoY), above Annual Plan by +$[X]M or +X%
```

### Driver Bullet Format

```
**[Product] ([YoY%] YoY)([vs AP $], [vs AP %] versus AP)** [DRI commentary]
```

- YoY%, vs AP $, vs AP % come from the data packet (quantitative, governed)
- DRI commentary comes from flux sheet column N (qualitative)
- If column N is empty: `<<RED>>Nick to fill out -- [product] drivers<</RED>>`

### 4 Core Drivers (always shown)

1. **Borrow** — `cash_app.sub_products.borrow`
   - Sub-metrics RED (not in MCP): Originations, Drawdown Actives
2. **Commerce ex. CAP** — derived from commerce products excluding CAP
   - Sub-metrics RED: GPV, Monetization Rate
3. **Cash App Pay** — `cash_app.sub_products.cash_app_pay`
   - Sub-metrics RED: (no sub-metrics in MCP)
4. **Cash App Card** — `cash_app.sub_products.card`
   - Sub-metrics RED: Card Actives, Spend, Transactions, Monetization Rate

### Dynamic 5th Driver

Sub-product with the largest |vs_plan_dollar|, excluding the 4 core drivers above. Determined at runtime from the data packet.

### Cash Actives Section

- **Actives total + YoY:** from data packet (`cash_app.actives`)
- **vs AP:** RED (forecast not available)
- **Driver narrative:** BLUE (Nick's judgment)
- **All sub-bullets RED** (not in MCP):
  - Net Churn
  - New Actives
  - PBA (Previously Banked Actives)
  - WAU (Weekly Active Users)
  - DAU (Daily Active Users)
  - 4+NC (4+ Network Connections)
  - P2P Volume

---

## Cash App Product-to-MRP Mapping

### Cash ex. Commerce Products

| Flux Row | Product Name | MRP Section | MCP Product Code | Commentary Target |
|----------|-------------|-------------|-----------------|-------------------|
| 10 | ATM | Appendix II: GP Breakdown | 3044 | Appendix row context |
| 11 | Bitcoin Buy/Sell | Cash App Drivers -> Bitcoin (dynamic 5th) | 3041 | Driver bullet |
| 12 | Bitcoin Paid In | (not in MRP -- immaterial) | 3052 | Skip |
| 13 | Bitcoin Round Ups | (not in MRP -- immaterial) | 3054 | Skip |
| 14 | Bitcoin Withdrawal Fees | Appendix II: GP Breakdown | 3049 | Appendix row context |
| 15 | Borrow | Cash App Drivers -> Borrow | 3047 | **Driver bullet** |
| 16 | Brokerage | (inactive) | -- | Skip |
| 17 | Business Accounts | Cash App Detail | 1341 | Detail context |
| 18 | Business Accounts Instant Deposit | Cash App Detail (grouped with BA in ref MRP) | (no separate MCP code) | Detail context -- combine with row 17 |
| 19 | Cash App Card | Cash App Drivers -> Cash App Card | 3040 | **Driver bullet** |
| 20 | P2P Funded by Credit Card | (rolled into Other) | 1311 | Skip |
| 21 | Cash Card Studio | (rolled into Other) | 3045 | Skip |
| 22 | Instant Deposit | Appendix II: GP Breakdown | 1340 | Appendix row context |
| 23 | Instant Pay | (immaterial / negative) | -- | Skip |
| 24 | Interest Income | Appendix II: GP Breakdown | 3046 | Appendix row context |
| 25 | Paper Money Deposits | Appendix II: GP Breakdown | 3050 | Appendix row context |
| 26 | Verse | (inactive) | -- | Skip |
| 27 | Cash Retro | Appendix II: GP Breakdown | 3055 | Appendix row context |
| 28 | Remittances | (inactive) | -- | Skip |
| 29 | Pools | (inactive) | -- | Skip |

### Commerce Products

| Flux Row | Product Name | MRP Section | MCP Product Code | Commentary Target |
|----------|-------------|-------------|-----------------|-------------------|
| 30 | BNPL | Cash App Drivers -> Commerce ex. CAP (Core BNPL) | 3070 | **Driver bullet** |
| 31 | Gift Card | Commerce detail | 3077 | Commerce context |
| 32 | Ads (SUP-Ads) | Commerce detail | 3075 | Commerce context |
| 33 | Pay Monthly | Commerce detail | 3073 | Commerce context |
| 34 | Plus Card | Commerce detail | 3074 | Commerce context |
| 35 | Touch Pay Now | Commerce detail | 3071 | Commerce context |
| 36 | SUP in Cash | (immaterial) | -- | Skip |
| 37 | Cash App Pay | Cash App Drivers -> Cash App Pay | 1312 | **Driver bullet** |
| 38 | Other - Commerce | (zero) | -- | Skip |

### Commerce GAAP Revenue Detail (rows 40-50)

These rows break down Commerce revenue at a more granular level (BNPL by region: NA, APAC, UK). Commentary here provides context for the Commerce section but maps to the same MRP driver bullet as the GP rows above.

| Flux Row | Product | Used For |
|----------|---------|----------|
| 40 | BNPL NA | Commerce regional context |
| 41 | BNPL APAC | Commerce regional context |
| 42 | BNPL UK | Commerce regional context |
| 43 | Gift Card (Revenue) | Already covered in GP row 31 |
| 44 | Ads (Revenue) | Already covered in GP row 32 |
| 45 | Pay Monthly (Revenue) | Already covered in GP row 33 |
| 46 | Plus Card (Revenue) | Already covered in GP row 34 |
| 47 | Touch Pay Now (Revenue) | Already covered in GP row 35 |
| 48 | SUP in Cash (Revenue) | Skip |
| 49 | Cash App Pay (Revenue) | Already covered in GP row 37 |
| 50 | Whole Loan Sales | Commerce detail |

### Commerce Contra-Revenue / COGS (rows 52-54)

| Flux Row | Product | Used For |
|----------|---------|----------|
| 52 | Issuing Costs | Not in MRP narrative -- cost detail |
| 53 | Processing Costs | Not in MRP narrative -- cost detail |
| 54 | Late Fees | Not in MRP narrative -- cost detail |

---

## Square Section

### GPV Summary

- **Global GPV** growth rate + acceleration (MoM change)
- **US GPV** growth rate + MoM acceleration
- **International GPV** growth rate + MoM acceleration

### NVR / SSG / Churn

- RED (not in MCP)
- Vertical breakdown: RED

### GP Summary

**Pattern:**
```
**Square gross profit** was $[X]M in [Month] (+X% YoY), +$[X]M above Annual Plan.
```

Include Jan comparison where relevant for trend context.

### 5 Fixed Segment Drivers

1. **US Payments** — RED (US/INTL split not in MCP)
   - Note: combined Processing GP available: $202M (from `square.sub_products.processing`)
   - Flux source: Square GP Summary Row 21
2. **International Payments** — RED (same US/INTL split issue)
   - Flux source: Square GP Summary Row 22
3. **Banking** — `square.sub_products.banking`
   - Sub-metrics RED: loan volumes, GPV attach rate
   - Flux source: Square GP Summary Row 33 + Rows 36-37 (US/INTL Loans)
4. **SaaS** — `square.sub_products.saas`
   - Sub-metrics RED: GPV attach rate
   - Flux source: Square GP Summary Row 29
5. **Hardware** — `square.sub_products.hardware`
   - Note: negative GP expected
   - Flux source: Square GP Summary Row 30

### Square Product-to-MRP Mapping

| Flux Row | Product Name | MRP Section | MCP Available | Commentary Target |
|----------|-------------|-------------|--------------|-------------------|
| 11 | US GPV | Square -> US GPV Growth | Yes | **GPV narrative** |
| 12 | International GPV | Square -> INTL GPV Growth | Yes (derived) | **GPV narrative** |
| 13-18 | INTL country detail (CA, JP, AU, UK, Current, New) | Not in MRP | -- | Skip (unless context needed) |
| 20 | Total Payments GP | Square Drivers -> Payments (combined) | Yes (1010+1011) | **Driver bullet** |
| 21 | US Payments GP | Square Drivers -> US Payments | DATA GAP (split) | **Driver bullet** |
| 22 | International Payments GP | Square Drivers -> INTL Payments | DATA GAP (split) | **Driver bullet** |
| 23-28 | INTL Payments country detail | Not in MRP | -- | Skip |
| 29 | SaaS | Square Drivers -> SaaS | Yes | **Driver bullet** |
| 30 | Hardware (total) | Square Drivers -> Hardware | Yes | **Driver bullet** |
| 31-32 | Hardware US / INTL | Not separately in MRP | -- | Context for Hardware bullet |
| 33 | Total Banking | Square Drivers -> Banking | Yes | **Driver bullet** |
| 34 | Business Banking | Banking sub-split | Not in MCP | Banking context |
| 35 | Total Loans | Banking sub-split | Not in MCP | Banking context |
| 36 | Loans US | Banking -> US Loans | Not in MCP | **Banking sub-bullet** |
| 37 | Loans International | Banking -> INTL Loans | Not in MCP | **Banking sub-bullet** |

---

## Other Brands Section

- **Individual brand GP:** RED (only combined "All Other Brands" in MCP)

### Brand Paragraphs

- **TIDAL:** Use flux commentary from Other Brands GP Summary Row 10
- **Proto:** BLUE (Nick's judgment -- deal-specific context)
- **Bitkey:** Note negative GP from depreciation; use flux commentary from Row 12
- **Bitcoin Lightning:** Usually no narrative; flux commentary from Row 13 if available

### Other Brands Product-to-MRP Mapping

| Flux Row | Brand | MRP Section | MCP Available | Commentary Target |
|----------|-------|-------------|--------------|-------------------|
| 10 | TIDAL | Other Brands -> TIDAL | DATA GAP (combined only) | **Brand paragraph** |
| 11 | Proto | Other Brands -> Proto | DATA GAP | **Brand paragraph** |
| 12 | Bitkey | Other Brands -> Bitkey | DATA GAP | **Brand paragraph** |
| 13 | Bitcoin Lightning | Other Brands -> Bitcoin Lightning | DATA GAP | (usually no narrative) |

---

## Business Accounts Grouping Note

The flux sheet has two separate rows:
- Row 17: "Business Accounts" (DRI: Nate Scinta)
- Row 18: "Business Accounts Instant Deposit" (DRI: Nate Scinta)

The reference MRP groups these together as "Business Accounts" showing ~$10M (vs MCP code 1341 = ~$4M which only captures one of the two).

**When generating the Cash App Detail section:** Sum rows 17+18 from the flux sheet for the "Business Accounts" line. Flag that the MCP product code 1341 only captures part of this grouping -- the rest is Business Accounts Instant Deposit which may have a different product code or be tracked separately.

---

## Output

Markdown for the Topline Trends by Brand section (Cash App, Square, Other Brands), ready to be assembled into the full MRP file.
