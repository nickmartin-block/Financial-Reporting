---
name: gdrive
description: Google Drive CLI tool for agent use. Provides read/write access to Google Drive, Docs, Sheets, Slides, comments, sharing, and revisions. Always invoked via `cd ~/skills/gdrive && uv run gdrive-cli.py <command>`. Load this skill whenever any task involves reading from or writing to Google Drive, Docs, or Sheets.
allowed-tools: [Bash(uv:*)]
metadata:
  author: nmart
  version: "1.0.0"
  status: "stable"
---

# gdrive Skill

## Invocation Pattern
All commands follow this pattern:
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py <command> [args] [options]
```

All output is JSON.

## Auth

Always check auth before any operation in a new session.

```bash
uv run gdrive-cli.py auth status       # Check status — look for "valid": true, "expired": false
uv run gdrive-cli.py auth login        # Authenticate (opens browser)
uv run gdrive-cli.py auth login --force  # Re-authenticate
uv run gdrive-cli.py auth logout       # Remove credentials
```

---

## Drive (files & folders)

```bash
# Search
uv run gdrive-cli.py search "query"
uv run gdrive-cli.py search "query" --limit 20
uv run gdrive-cli.py search "query" --mime-type "application/vnd.google-apps.spreadsheet"
uv run gdrive-cli.py search "query" --parent <folder_id>
uv run gdrive-cli.py search "query" --raw-query   # pass raw Drive API query string

# List folder contents
uv run gdrive-cli.py list                         # root
uv run gdrive-cli.py list <folder_id>

# Read a file (Docs → text, Sheets → array of rows, other → export as text)
uv run gdrive-cli.py read <file_id>
uv run gdrive-cli.py read <file_id> --all-tabs    # all tabs for Docs/Sheets
uv run gdrive-cli.py read <file_id> --tab t.abc123  # specific Doc tab by ID

# File metadata
uv run gdrive-cli.py info <file_id>

# Download to local path
uv run gdrive-cli.py download <file_id> --dest /path/to/dest

# Export Google Workspace file
# formats: pdf, docx, txt, html, xlsx, csv, pptx, odt, ods
uv run gdrive-cli.py export <file_id> --dest /path --format pdf

# Upload local file
uv run gdrive-cli.py upload /local/path
uv run gdrive-cli.py upload /local/path --name "File Name" --parent <folder_id>
uv run gdrive-cli.py upload /local/path --convert-to doc   # convert to Google Doc/Sheet/Slides

# Create Google Workspace file
uv run gdrive-cli.py create doc "Document Name" --parent <folder_id>
uv run gdrive-cli.py create sheet "Sheet Name"
uv run gdrive-cli.py create slides "Presentation Name"

# Folder operations
uv run gdrive-cli.py mkdir "Folder Name" --parent <folder_id>

# File management
uv run gdrive-cli.py rename <file_id> "New Name"
uv run gdrive-cli.py copy <file_id> --name "Copy Name" --parent <folder_id>
uv run gdrive-cli.py move <file_id> --to <folder_id>
uv run gdrive-cli.py trash <file_id>
```

---

## Docs

```bash
# List tabs in a multi-tab Doc
uv run gdrive-cli.py docs tabs <doc_id>

# Read full Doc JSON (structure + content)
uv run gdrive-cli.py docs get <doc_id>

# Append plain text to end of Doc
uv run gdrive-cli.py docs append <doc_id> "text to append"

# Insert plain text at a specific index
uv run gdrive-cli.py docs insert <doc_id> "text" --index 42

# Replace text (all occurrences, case-sensitive)
uv run gdrive-cli.py docs replace <doc_id> --find "old text" --replace "new text"

# Insert markdown with rich formatting (reads from stdin)
# Supports: headings, bold, italic, links, code, bullets, numbered lists, tables
echo "# Heading\n\n**Bold** text" | uv run gdrive-cli.py docs insert-markdown <doc_id>
echo "## Section" | uv run gdrive-cli.py docs insert-markdown <doc_id> --at-index 342
echo "content" | uv run gdrive-cli.py docs insert-markdown <doc_id> --tab t.abc123

# Suggest edit (requires Playwriter Chrome extension — browser automation)
uv run gdrive-cli.py docs suggest-edit <doc_id> --find "old" --replace "new"
uv run gdrive-cli.py docs suggest-edit <doc_id> --find "old" --replace "new" --tab t.abc123 --occurrence 2

# Raw batchUpdate (reads JSON from stdin)
echo '{"requests": [...]}' | uv run gdrive-cli.py docs batch-update <doc_id>

# Insert image (requires image-webapp setup)
uv run gdrive-cli.py docs insert-image <doc_id> /path/to/image.png
uv run gdrive-cli.py docs insert-image <doc_id> /path/to/image.png --tab t.abc123
```

**Tab IDs** are returned by `docs tabs` as `"tabId": "t.abc123"`. Always use `docs tabs` first on multi-tab Docs.

---

## Sheets

```bash
# Metadata
uv run gdrive-cli.py sheets get <spreadsheet_id>
uv run gdrive-cli.py sheets tabs <spreadsheet_id>
uv run gdrive-cli.py sheets named-ranges <spreadsheet_id>

# Read values
uv run gdrive-cli.py sheets read <spreadsheet_id>                          # default tab, all columns
uv run gdrive-cli.py sheets read <spreadsheet_id> --sheet "Sheet1"
uv run gdrive-cli.py sheets read <spreadsheet_id> --range "Sheet1!A1:D10"
uv run gdrive-cli.py sheets read <spreadsheet_id> --all-sheets             # all visible tabs
uv run gdrive-cli.py sheets read <spreadsheet_id> --named-range "MyRange"

# Write values (JSON array of rows)
uv run gdrive-cli.py sheets write <spreadsheet_id> --range "Sheet1!A1" --values '[["a","b"],["c","d"]]'

# Append rows
uv run gdrive-cli.py sheets append <spreadsheet_id> --range "Sheet1" --values '[["new","row"]]'

# Clear range (keeps formatting)
uv run gdrive-cli.py sheets clear <spreadsheet_id> --range "Sheet1!A2:Z"

# Raw batchUpdate (reads JSON from stdin)
echo '{"requests": [...]}' | uv run gdrive-cli.py sheets batch-update <spreadsheet_id>
```

**Range syntax note:** zsh may escape `!` in ranges as `\!`. The CLI strips this automatically.

---

## Slides

```bash
# Metadata
uv run gdrive-cli.py slides get <presentation_id>      # full JSON
uv run gdrive-cli.py slides list <presentation_id>     # slide list with objectIds

# Read content
uv run gdrive-cli.py slides read <presentation_id>                     # all slides
uv run gdrive-cli.py slides read <presentation_id> --slide <objectId>  # specific slide
uv run gdrive-cli.py slides notes <presentation_id>                    # speaker notes
uv run gdrive-cli.py slides page <presentation_id> <page_objectId>

# Edit
uv run gdrive-cli.py slides add-slide <presentation_id>
uv run gdrive-cli.py slides delete-slide <presentation_id> <objectId>
uv run gdrive-cli.py slides duplicate-slide <presentation_id> <objectId>
uv run gdrive-cli.py slides add-text <presentation_id> <slide_objectId> "text"
uv run gdrive-cli.py slides replace <presentation_id> --find "old" --replace "new"
uv run gdrive-cli.py slides insert-image <presentation_id> <slide_objectId> /path/to/image.png

# Export
uv run gdrive-cli.py slides export-pdf <presentation_id> --dest /path/to/output.pdf

# Raw batchUpdate (reads JSON from stdin)
echo '{"requests": [...]}' | uv run gdrive-cli.py slides batch-update <presentation_id>
```

---

## Comments

```bash
uv run gdrive-cli.py comments list <file_id>
uv run gdrive-cli.py comments add <file_id> "comment text"
uv run gdrive-cli.py comments reply <file_id> <comment_id> "reply text"
uv run gdrive-cli.py comments delete <file_id> <comment_id>
```

---

## Sharing & Permissions

```bash
uv run gdrive-cli.py share list <file_id>
uv run gdrive-cli.py share add <file_id> --email user@example.com --role writer
# roles: owner, organizer, fileOrganizer, writer, commenter, reader
# types: user, group, domain, anyone
uv run gdrive-cli.py share remove <file_id> <permission_id>
```

---

## Revisions

```bash
uv run gdrive-cli.py revisions list <file_id>
uv run gdrive-cli.py revisions get <file_id> <revision_id>
```

---

## Error Handling

All commands output JSON. On error, the output includes `"error"` and `"type"` keys. Always check for these before using output values.

```json
{"error": "File not found", "type": "HttpError"}
```

If auth fails mid-workflow, run `auth status` to diagnose, then `auth login` to re-authenticate.
