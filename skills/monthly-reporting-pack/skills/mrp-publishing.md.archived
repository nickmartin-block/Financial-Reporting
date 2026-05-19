---
name: MRP Publishing Pipeline
description: Converts the MRP markdown to a formatted Google Doc with colors, table styling, and proper typography.
---

# MRP Publishing Pipeline

Converts the MRP markdown file into a fully formatted Google Doc.

## Prerequisites

- MRP markdown file at `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_YYYY_MM.md`
- gdrive CLI authenticated (`cd ~/skills/gdrive && uv run gdrive-cli.py auth status`)
- Shared infrastructure:
  - `~/skills/weekly-reporting/gdrive/scripts/markdown_converter.py`
  - `~/skills/weekly-reporting/gdrive/scripts/color_markers.py`
  - `~/skills/gdrive/gdrive-cli.py`

## Configuration

| Setting | Value |
|---------|-------|
| Drive parent folder | `1uykSB8IQ_pzyUypv6CvzRC9ZWWzNDpN1` (2026 folder) |
| Month subfolder pattern | `M-YY` (e.g., `2-26` for February 2026) |
| Doc naming | `[Month] [Year]  - Monthly Management Reporting Pack` |
| Font | Inter |
| Body font size | 10pt |
| H1 | Inter, 20pt, black (title 22pt) |
| H2 | Inter, 16pt, black |
| H3 | Inter, 14pt, black |

## Publishing Steps

### Step 1: Create or find the month subfolder

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py search "M-YY" --parent 1uykSB8IQ_pzyUypv6CvzRC9ZWWzNDpN1 --mime-type "application/vnd.google-apps.folder"
```

If not found, create it:
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py mkdir "M-YY" --parent 1uykSB8IQ_pzyUypv6CvzRC9ZWWzNDpN1
```

### Step 2: Create the Google Doc

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py create doc "[Month] [Year]  - Monthly Management Reporting Pack" --parent <subfolder_id>
```

Save the returned doc ID.

### Step 3: Insert markdown

```bash
cat "~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_YYYY_MM.md" | cd ~/skills/gdrive && uv run gdrive-cli.py docs insert-markdown <doc_id> --font Inter
```

The markdown converter automatically handles:
- Headings (H1/H2/H3 with proper styles)
- Bold/italic text
- Bullet lists with nesting
- Tables with:
  - Header rows: black background, white text, bold
  - Data cells: center-aligned (except first column: left-aligned)
  - Cell padding: 1pt top/bottom, 3pt left/right
  - "Pacing" columns: light gray background (#F3F3F3)

### Step 4: Fix font size

The default markdown converter uses 11pt. The MRP uses 10pt Inter. Apply a global font size override:

```bash
# Get doc endIndex, then apply 10pt Inter to entire body
cd ~/skills/gdrive && uv run gdrive-cli.py docs get <doc_id>
```

Build a batchUpdate request to set font size to 10pt for all NORMAL_TEXT paragraphs (not headings).

### Step 5: Fix bullet nesting

The markdown converter flattens all nested bullets to L0. Fix by identifying sections with parent/child bullet relationships and applying the three-step pattern:

1. `deleteParagraphBullets` for the section range (clears existing bullets)
2. `insertText` with `\t` at each child paragraph's startIndex (in **reverse order** to preserve indices)
3. `createParagraphBullets` with `BULLET_DISC_CIRCLE_SQUARE` for the full range (endIndex shifts by # of tabs inserted)

**Process sections in reverse document order** (bottom-to-top) so tab insertions in later sections don't shift earlier sections' indices.

**Sections requiring nesting (positions are dynamic — read doc first):**

| Section | L0 (parent) items | L1 (child) items |
|---------|-------------------|------------------|
| **Gross Profit** | Cash App GP, Square GP | Actives, Inflows, MonRate, Global GPV, US GPV, INTL GPV |
| **Cash App Drivers** | Borrow, Commerce ex, Cash App Pay, Card, Bitcoin | Borrow Originations, Borrow Drawdown, Commerce GPV, Commerce MonRate, Card Actives, Card Spend, Card Txns, Card MonRate |
| **Square GPV** | US GPV Growth, INTL GPV Growth | Food & Bev, Retail, Health & Beauty, Services & Other |
| **Square Product Drivers** | US Payments, INTL Payments, Banking, SaaS, Hardware | US Loan Vol, INTL Loan Vol, Credit GPV Attach, Banking GPV Attach, Square One GPV Attach |

**How to find positions:** Read the doc with `docs get`, scan for paragraph startIndex values by matching text content. The parent items are often NORMAL_TEXT (not already bullets) while child items are existing L0 bullets.

### Step 5.5: Fix heading formatting

The markdown converter sets `bold: false` on heading text runs. Fix by:

1. **Set all headings to bold:** `updateTextStyle` with `{bold: true}` and `fields: 'bold'` for every HEADING_1/2/3 range.

2. **Set heading font sizes:** `updateTextStyle` with the correct `fontSize` for each heading level. H1 = 20pt (title 22pt), H2 = 16pt, H3 = 14pt. Important: only update fontSize in batch requests. Do NOT set weightedFontFamily as this overwrites bold formatting from the markdown converter.

3. **Delete any empty headings:** Scan for HEADING paragraphs with empty text and delete with `deleteContentRange`.

### Step 6: Apply color markers

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs get <doc_id> | python3 ~/skills/weekly-reporting/gdrive/scripts/color_markers.py <tab_id> --colors RED,BLUE,WARN | uv run gdrive-cli.py docs batch-update <doc_id>
```

This processes the marker types:
- `«RED»...«/RED»` -> Red text (#EA4335) -- data gap (metric missing from MCP)
- `«BLUE»...«/BLUE»` -> Blue text (#4285F4) -- Nick's judgment (pacing, watchpoints, guidance, consensus)
- `«WARN»...«/WARN»` -> markers stripped (replaced by yellow highlight in the next step)

### Step 6.5: Apply yellow highlighting to table placeholders

Find all paragraphs containing `[TABLE` text. Apply yellow background (#FFF29A) with dark amber foreground (#594600). This replaces the WARN markers that were stripped in Step 6.

### Step 7: Apply conditional table formatting (deferred)

When tables are rendered (not metric inventories), apply conditional coloring on vs. AP columns:
- Revenue/GP rows: positive = green text, negative = red text
- Cost rows: negative = green text (favorable underspend), positive = red text (unfavorable overspend)
- Zero or dash = black (no coloring)

Currently deferred — tables are metric inventories (bullet lists) until more data is available.

### Step 8: Verify structure

Confirm the published doc has:
- [ ] Heading count: H1=10, H2=5, H3=4 (no empty headings)
- [ ] All headings bold, H2/H3 in black
- [ ] Bullet nesting: L1 items present in Gross Profit, Cash App Drivers, Square GPV, Square Drivers
- [ ] No remaining raw color markers (0 `«` characters)
- [ ] Font is Inter throughout, body 10pt, H1 18pt (title 22pt)

## Output

The published Google Doc ID and URL. Save to the MRP data packet or output for reference.
