"""Convert markdown to Google Docs API batchUpdate requests.

Uses mistune to parse markdown into an AST, then generates:
1. Plain text content
2. Formatting requests (updateTextStyle, updateParagraphStyle, createParagraphBullets)

The algorithm:
1. Walk the AST, accumulating plain text and format ranges
2. Generate one insertText request with all text
3. Generate formatting requests sorted by descending index (to preserve positions)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FormatRange:
    """A range of text with formatting to apply."""
    start: int
    end: int
    format_type: str
    text: str = ""  # Actual text content for two-pass matching
    data: dict = field(default_factory=dict)


@dataclass
class ParagraphRange:
    """A paragraph range for paragraph-level formatting."""
    start: int
    end: int
    style_type: str
    data: dict = field(default_factory=dict)


@dataclass
class BulletRange:
    """A range for bullet/numbered list formatting."""
    start: int
    end: int
    bullet_preset: str


@dataclass
class TableSpec:
    """Specification for a table to insert."""
    insert_index: int
    rows: int
    cols: int
    cells: list[list[str]]
    header_rows: int = 1


class MarkdownToDocsConverter:
    """Converts markdown to Google Docs API requests."""

    # URL regex for auto-linkifying bare URLs
    # Use greedy matching to capture full URL, then lookahead for terminator
    URL_PATTERN = re.compile(
        r'(?<!["\(])\b(https?://[^\s<>\[\]]+)(?<![.,;:!?])'
    )

    def __init__(self, base_index: int = 1, base_font_family: str | None = None):
        """Initialize converter.

        Args:
            base_index: Starting index in the document (1 for start, or end_index for append)
            base_font_family: Optional font family to apply to all text (e.g., 'Inter')
        """
        self.base_index = base_index
        self.base_font_family = base_font_family
        self.text_parts: list[str] = []
        self.format_ranges: list[FormatRange] = []
        self.paragraph_ranges: list[ParagraphRange] = []
        self.bullet_ranges: list[BulletRange] = []
        self.tables: list[TableSpec] = []
        self.current_pos = 0

        # Stack for nested formatting (bold inside italic, etc.)
        self._format_stack: list[tuple[str, int]] = []

        # Track list state
        self._in_list = False
        self._list_type: str | None = None
        self._list_start_pos = 0

    def convert(self, markdown: str) -> dict:
        """Convert markdown to Google Docs API request body.

        Args:
            markdown: The markdown text to convert

        Returns:
            Dict with 'requests' key containing list of API requests
        """
        # Parse markdown with table plugin enabled
        try:
            from mistune import Markdown
            from mistune.plugins.table import table
        except ImportError as err:
            raise ImportError(
                "mistune is required for markdown conversion. Install with: pip install mistune"
            ) from err

        md = Markdown(renderer=None)
        table(md)  # Enable table parsing
        tokens = md(markdown)

        # Process tokens
        self._process_tokens(tokens)

        # Generate requests
        return self._generate_requests()

    def _process_tokens(self, tokens: list[dict]) -> None:
        """Process AST tokens recursively."""
        for token in tokens:
            token_type = token.get("type", "")
            handler = getattr(self, f"_handle_{token_type}", None)
            if handler:
                handler(token)
            elif "children" in token:
                self._process_tokens(token["children"])

    def _handle_paragraph(self, token: dict) -> None:
        """Handle paragraph token."""
        start_pos = self.current_pos
        if "children" in token:
            self._process_tokens(token["children"])
        # Add newline after paragraph
        self._append_text("\n")
        # Record paragraph range for potential styling
        self.paragraph_ranges.append(ParagraphRange(
            start=start_pos,
            end=self.current_pos,
            style_type="NORMAL_TEXT",
        ))

    def _handle_heading(self, token: dict) -> None:
        """Handle heading token (# to ######)."""
        level = token.get("attrs", {}).get("level", 1)
        start_pos = self.current_pos

        if "children" in token:
            self._process_tokens(token["children"])

        self._append_text("\n")

        # Map markdown heading levels to Google Docs
        heading_map = {
            1: "HEADING_1",
            2: "HEADING_2",
            3: "HEADING_3",
            4: "HEADING_4",
            5: "HEADING_5",
            6: "HEADING_6",
        }
        style = heading_map.get(level, "HEADING_6")

        self.paragraph_ranges.append(ParagraphRange(
            start=start_pos,
            end=self.current_pos,
            style_type=style,
        ))

    def _handle_text(self, token: dict) -> None:
        """Handle plain text token."""
        raw = token.get("raw", "")
        self._append_text(raw)

    def _handle_strong(self, token: dict) -> None:
        """Handle bold (**text**)."""
        start_pos = self.current_pos
        parts_start = len(self.text_parts)
        if "children" in token:
            self._process_tokens(token["children"])
        text = "".join(self.text_parts[parts_start:])
        self.format_ranges.append(FormatRange(
            start=start_pos,
            end=self.current_pos,
            format_type="bold",
            text=text,
        ))

    def _handle_emphasis(self, token: dict) -> None:
        """Handle italic (*text*)."""
        start_pos = self.current_pos
        parts_start = len(self.text_parts)
        if "children" in token:
            self._process_tokens(token["children"])
        text = "".join(self.text_parts[parts_start:])
        self.format_ranges.append(FormatRange(
            start=start_pos,
            end=self.current_pos,
            format_type="italic",
            text=text,
        ))

    def _handle_link(self, token: dict) -> None:
        """Handle link [text](url)."""
        start_pos = self.current_pos
        url = token.get("attrs", {}).get("url", "")

        parts_start = len(self.text_parts)
        if "children" in token:
            self._process_tokens(token["children"])

        if url:
            text = "".join(self.text_parts[parts_start:])
            self.format_ranges.append(FormatRange(
                start=start_pos,
                end=self.current_pos,
                format_type="link",
                text=text,
                data={"url": url},
            ))

    def _handle_codespan(self, token: dict) -> None:
        """Handle inline code (`code`)."""
        start_pos = self.current_pos
        raw = token.get("raw", "")
        self._append_text(raw)
        self.format_ranges.append(FormatRange(
            start=start_pos,
            end=self.current_pos,
            format_type="code",
            text=raw,
        ))

    def _handle_block_code(self, token: dict) -> None:
        """Handle fenced code block (```code```)."""
        start_pos = self.current_pos
        raw = token.get("raw", "")
        # Ensure code block ends with newline
        if raw and not raw.endswith("\n"):
            raw += "\n"
        self._append_text(raw)

        self.format_ranges.append(FormatRange(
            start=start_pos,
            end=self.current_pos,
            format_type="code_block",
            text=raw,
        ))

    def _handle_list(self, token: dict) -> None:
        """Handle unordered or ordered list."""
        ordered = token.get("attrs", {}).get("ordered", False)
        self._list_type = "ordered" if ordered else "unordered"
        self._in_list = True
        self._list_start_pos = self.current_pos

        if "children" in token:
            self._process_tokens(token["children"])

        # Record bullet range for entire list
        bullet_preset = (
            "NUMBERED_DECIMAL_ALPHA_ROMAN" if ordered
            else "BULLET_DISC_CIRCLE_SQUARE"
        )
        self.bullet_ranges.append(BulletRange(
            start=self._list_start_pos,
            end=self.current_pos,
            bullet_preset=bullet_preset,
        ))

        self._in_list = False
        self._list_type = None

    def _handle_list_item(self, token: dict) -> None:
        """Handle list item (- item or 1. item)."""
        if "children" in token:
            self._process_tokens(token["children"])

    def _handle_block_text(self, token: dict) -> None:
        """Handle block text (used inside list items)."""
        if "children" in token:
            self._process_tokens(token["children"])
        # Add newline after list item text
        self._append_text("\n")

    def _handle_softbreak(self, token: dict) -> None:
        """Handle soft line break."""
        self._append_text(" ")

    def _handle_linebreak(self, token: dict) -> None:
        """Handle hard line break."""
        self._append_text("\n")

    def _handle_blank_line(self, token: dict) -> None:
        """Handle blank line between elements."""
        self._append_text("\n")

    def _handle_thematic_break(self, token: dict) -> None:
        """Handle horizontal rule (---)."""
        self._append_text("\n────────────────────\n")

    def _handle_block_quote(self, token: dict) -> None:
        """Handle block quote (> text)."""
        start_pos = self.current_pos
        if "children" in token:
            self._process_tokens(token["children"])
        # Apply italic styling to quotes
        self.format_ranges.append(FormatRange(
            start=start_pos,
            end=self.current_pos,
            format_type="italic",
        ))

    def _handle_table(self, token: dict) -> None:
        """Handle markdown table."""
        rows = []
        children = token.get("children", [])

        for child in children:
            child_type = child.get("type", "")
            if child_type == "table_head":
                # table_head contains table_cell directly (the header row)
                header_cells = []
                for cell_token in child.get("children", []):
                    if cell_token.get("type") == "table_cell":
                        cell_text = self._extract_text(cell_token)
                        header_cells.append(cell_text)
                if header_cells:
                    rows.append(header_cells)
            elif child_type == "table_body":
                # table_body contains table_row which contains table_cell
                for row_token in child.get("children", []):
                    if row_token.get("type") == "table_row":
                        row_cells = []
                        for cell_token in row_token.get("children", []):
                            if cell_token.get("type") == "table_cell":
                                cell_text = self._extract_text(cell_token)
                                row_cells.append(cell_text)
                        if row_cells:
                            rows.append(row_cells)

        if rows:
            num_rows = len(rows)
            num_cols = max(len(row) for row in rows) if rows else 0

            # Pad rows to have consistent column count
            for row in rows:
                while len(row) < num_cols:
                    row.append("")

            # Detect multi-row headers: row 0 is always a header; subsequent
            # rows with empty first cell but non-empty content are also headers
            header_rows = 1
            for i in range(1, len(rows)):
                if not rows[i][0].strip() and any(cell.strip() for cell in rows[i][1:]):
                    header_rows += 1
                else:
                    break

            # Remove preceding newline if present (from blank_line before table)
            if self.text_parts and self.text_parts[-1].endswith("\n"):
                self.text_parts[-1] = self.text_parts[-1][:-1]
                self.current_pos -= 1

            self.tables.append(TableSpec(
                insert_index=self.current_pos,
                rows=num_rows,
                cols=num_cols,
                cells=rows,
                header_rows=header_rows,
            ))
            # Reserve space for table - marker gets deleted, trailing \n provides spacing
            self._append_text(f"__TABLE_{len(self.tables) - 1}__\n\n")

    def _extract_text(self, token: dict) -> str:
        """Extract plain text from a token tree."""
        if token.get("type") == "text":
            return token.get("raw", "")
        text_parts = []
        for child in token.get("children", []):
            text_parts.append(self._extract_text(child))
        return "".join(text_parts)

    @staticmethod
    def _utf16_len(text: str) -> int:
        """Return the number of UTF-16 code units for a string.

        Google Docs API uses UTF-16 code unit indices. Characters above U+FFFF
        (e.g. emojis like 🟡🟢🔴) require 2 code units (a surrogate pair),
        while Python's len() counts them as 1.
        """
        return len(text.encode("utf-16-le")) // 2

    def _append_text(self, text: str) -> None:
        """Append text and update position using UTF-16 code units."""
        self.text_parts.append(text)
        self.current_pos += self._utf16_len(text)

    def _slice_text_by_utf16(self, utf16_start: int, utf16_end: int) -> str:
        """Slice the full text using UTF-16 code unit positions."""
        full_text = "".join(self.text_parts)
        result = []
        pos = 0
        for ch in full_text:
            ch_len = self._utf16_len(ch)
            if pos >= utf16_end:
                break
            if pos >= utf16_start:
                result.append(ch)
            pos += ch_len
        return "".join(result)

    def _auto_linkify_urls(self) -> None:
        """Find bare URLs in text and add link formatting."""
        full_text = "".join(self.text_parts)

        # Build Python position -> UTF-16 position mapping
        py_to_utf16 = []
        utf16_pos = 0
        for ch in full_text:
            py_to_utf16.append(utf16_pos)
            utf16_pos += self._utf16_len(ch)
        py_to_utf16.append(utf16_pos)  # position after last char

        # Collect existing link ranges as (start, end) tuples (UTF-16)
        existing_link_ranges = [
            (fr.start, fr.end)
            for fr in self.format_ranges
            if fr.format_type == "link"
        ]

        def overlaps_existing_link(start: int, end: int) -> bool:
            """Check if UTF-16 range [start, end) overlaps any existing link."""
            for link_start, link_end in existing_link_ranges:
                if start < link_end and link_start < end:
                    return True
            return False

        for match in self.URL_PATTERN.finditer(full_text):
            # Convert Python string positions to UTF-16 positions
            utf16_start = py_to_utf16[match.start()]
            utf16_end = py_to_utf16[match.end()]
            if overlaps_existing_link(utf16_start, utf16_end):
                continue
            url = match.group(1)
            self.format_ranges.append(FormatRange(
                start=utf16_start,
                end=utf16_end,
                format_type="link",
                text=url,
                data={"url": url},
            ))

    def _get_heading_ranges(self) -> list[tuple[int, int]]:
        """Get all heading paragraph ranges as (start, end) tuples."""
        return [
            (pr.start, pr.end)
            for pr in self.paragraph_ranges
            if pr.style_type.startswith("HEADING_")
        ]

    def _split_bullet_range_around_headings(
        self, br_start: int, br_end: int, heading_ranges: list[tuple[int, int]]
    ) -> list[tuple[int, int]]:
        """Split a bullet range to exclude heading paragraphs.

        Returns list of (start, end) tuples representing non-heading portions.

        Google Docs applies createParagraphBullets to entire paragraphs that
        intersect with the range. To prevent headings from getting bullets:
        1. Exclude headings that overlap with the bullet range
        2. Exclude headings that start at the bullet range end (adjacent)
        3. Exclude headings that end at the bullet range start (adjacent)
        """
        # Filter to headings that overlap OR are adjacent to this bullet range.
        # h_start <= br_end: heading starts at or before bullet end (covers h_start == br_end)
        # h_end >= br_start: heading ends at or after bullet start (covers h_end == br_start)
        overlapping = [
            (h_start, h_end)
            for h_start, h_end in heading_ranges
            if h_start <= br_end and h_end >= br_start
        ]

        if not overlapping:
            return [(br_start, br_end)]

        # Sort by start position
        overlapping.sort(key=lambda x: x[0])

        # Build non-overlapping segments, ensuring we don't touch any heading
        result = []
        current_start = br_start

        for h_start, h_end in overlapping:
            # Add segment before this heading (if any content exists before it)
            # End 1 character before heading to avoid boundary effects
            if current_start < h_start:
                # Don't include the character right before the heading (usually a newline)
                # to prevent Google Docs from applying bullets to the heading
                seg_end = h_start - 1 if h_start > current_start + 1 else h_start
                if current_start < seg_end:
                    result.append((current_start, seg_end))
            # Move past this heading
            if current_start <= h_end:
                current_start = h_end

        # Add remaining segment after last heading (if any)
        if current_start < br_end:
            result.append((current_start, br_end))

        return result

    def _generate_requests(self) -> dict:
        """Generate Google Docs API requests."""
        requests = []

        # Auto-linkify bare URLs (but not in table markers)
        self._auto_linkify_urls()

        full_text = "".join(self.text_parts)
        if not full_text:
            return {"requests": []}

        # Check if we have tables - if so, we need a different approach
        if self.tables:
            return self._generate_requests_with_tables()

        # Simple case: no tables
        # 1. Insert all text at once
        requests.append({
            "insertText": {
                "location": {"index": self.base_index},
                "text": full_text,
            }
        })

        # Adjust all ranges by base_index
        def adjust(idx: int) -> int:
            return idx + self.base_index

        # 2. Apply bullet lists FIRST - descending order, excluding headings
        heading_ranges = self._get_heading_ranges()
        for br in sorted(self.bullet_ranges, key=lambda x: -x.start):
            # Split bullet range to exclude any heading paragraphs
            segments = self._split_bullet_range_around_headings(
                br.start, br.end, heading_ranges
            )
            # Apply bullets to each non-heading segment (in descending order)
            for seg_start, seg_end in sorted(segments, key=lambda x: -x[0]):
                requests.append({
                    "createParagraphBullets": {
                        "range": {
                            "startIndex": adjust(seg_start),
                            "endIndex": adjust(seg_end),
                        },
                        "bulletPreset": br.bullet_preset,
                    }
                })

        # 3. Apply paragraph styles (headings) AFTER bullets
        # Also explicitly remove bullets from headings
        for pr in sorted(self.paragraph_ranges, key=lambda x: -x.start):
            if pr.style_type != "NORMAL_TEXT":
                adj_start = adjust(pr.start)
                adj_end = adjust(pr.end)

                # First remove any bullets that might have been applied
                requests.append({
                    "deleteParagraphBullets": {
                        "range": {
                            "startIndex": adj_start,
                            "endIndex": adj_end,
                        },
                    }
                })

                # Then apply heading style
                requests.append({
                    "updateParagraphStyle": {
                        "range": {
                            "startIndex": adj_start,
                            "endIndex": adj_end,
                        },
                        "paragraphStyle": {
                            "namedStyleType": pr.style_type,
                            "spaceAbove": {"magnitude": 10, "unit": "PT"},
                            "spaceBelow": {"magnitude": 0, "unit": "PT"},
                        },
                        "fields": "namedStyleType,spaceAbove,spaceBelow",
                    }
                })

        # 4. Apply base font to all text (before specific text styles override)
        if self.base_font_family:
            requests.append({
                "updateTextStyle": {
                    "range": {
                        "startIndex": self.base_index,
                        "endIndex": self.base_index + self.current_pos,
                    },
                    "textStyle": {
                        "weightedFontFamily": {"fontFamily": self.base_font_family},
                    },
                    "fields": "weightedFontFamily",
                }
            })

        # 5. Apply text formatting - descending order
        requests.extend(self._generate_text_style_requests(self.base_index))

        return {"requests": requests}

    def _generate_text_style_requests(self, base_index: int) -> list[dict]:
        """Generate text style requests (bold, italic, links, code)."""
        requests = []

        def adjust(idx: int) -> int:
            return idx + base_index

        for fr in sorted(self.format_ranges, key=lambda x: -x.start):
            if fr.format_type == "bold":
                requests.append({
                    "updateTextStyle": {
                        "range": {
                            "startIndex": adjust(fr.start),
                            "endIndex": adjust(fr.end),
                        },
                        "textStyle": {"bold": True},
                        "fields": "bold",
                    }
                })
            elif fr.format_type == "italic":
                requests.append({
                    "updateTextStyle": {
                        "range": {
                            "startIndex": adjust(fr.start),
                            "endIndex": adjust(fr.end),
                        },
                        "textStyle": {"italic": True},
                        "fields": "italic",
                    }
                })
            elif fr.format_type == "link":
                requests.append({
                    "updateTextStyle": {
                        "range": {
                            "startIndex": adjust(fr.start),
                            "endIndex": adjust(fr.end),
                        },
                        "textStyle": {
                            "link": {"url": fr.data.get("url", "")},
                        },
                        "fields": "link",
                    }
                })
            elif fr.format_type == "code":
                # Inline code: monospace font + green color, clear bold/italic
                requests.append({
                    "updateTextStyle": {
                        "range": {
                            "startIndex": adjust(fr.start),
                            "endIndex": adjust(fr.end),
                        },
                        "textStyle": {
                            "weightedFontFamily": {"fontFamily": "Roboto Mono"},
                            "foregroundColor": {
                                "color": {"rgbColor": {"red": 0.0, "green": 0.5, "blue": 0.0}}
                            },
                            "bold": False,
                            "italic": False,
                        },
                        "fields": "weightedFontFamily,foregroundColor,bold,italic",
                    }
                })
            elif fr.format_type == "code_block":
                # Code blocks: monospace font + green color, clear bold/italic
                requests.append({
                    "updateTextStyle": {
                        "range": {
                            "startIndex": adjust(fr.start),
                            "endIndex": adjust(fr.end),
                        },
                        "textStyle": {
                            "weightedFontFamily": {"fontFamily": "Roboto Mono"},
                            "foregroundColor": {
                                "color": {"rgbColor": {"red": 0.0, "green": 0.5, "blue": 0.0}}
                            },
                            "bold": False,
                            "italic": False,
                        },
                        "fields": "weightedFontFamily,foregroundColor,bold,italic",
                    }
                })

        return requests

    def _generate_requests_with_tables(self) -> dict:
        """Generate phase 1 request: insert text with table markers.

        Tables are processed separately by the CLI to ensure correct positioning.
        Formatting is applied in phase 2 after reading the document.
        """
        full_text = "".join(self.text_parts)

        # Just insert text - tables are handled by CLI
        self._needs_phase2 = True

        requests = [{
            "insertText": {
                "location": {"index": self.base_index},
                "text": full_text,
            }
        }]

        # Apply base font + size to all inserted text (11pt = Google Docs default).
        # Table cells override to 10pt in _generate_table_cell_requests.
        if self.base_font_family:
            requests.append({
                "updateTextStyle": {
                    "range": {
                        "startIndex": self.base_index,
                        "endIndex": self.base_index + self.current_pos,
                    },
                    "textStyle": {
                        "weightedFontFamily": {"fontFamily": self.base_font_family},
                        "fontSize": {"magnitude": 11, "unit": "PT"},
                    },
                    "fields": "weightedFontFamily,fontSize",
                }
            })

            # Set line spacing on all paragraphs to prevent text overlap.
            # Without this, body text inherits the document's default paragraph
            # style which may have insufficient line spacing for 11pt text.
            # Phase 2 heading styles will override their own paragraphs.
            requests.append({
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": self.base_index,
                        "endIndex": self.base_index + self.current_pos,
                    },
                    "paragraphStyle": {
                        "lineSpacing": 115,
                        "spaceAbove": {"magnitude": 0, "unit": "PT"},
                        "spaceBelow": {"magnitude": 0, "unit": "PT"},
                    },
                    "fields": "lineSpacing,spaceAbove,spaceBelow",
                }
            })

        # Shrink empty paragraphs (from markdown blank lines) to near-invisible.
        # Blank lines are needed in markdown for correct parsing (e.g., before
        # lists), but they create unwanted vertical gaps in the Google Doc.
        # Setting font to 1pt and line spacing to 100% collapses them.
        prev_char = ""
        utf16_pos = 0
        for char in full_text:
            char_units = len(char.encode("utf-16-le")) // 2
            if char == "\n" and prev_char == "\n":
                ep_start = self.base_index + utf16_pos
                ep_end = ep_start + 1
                requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": ep_start, "endIndex": ep_end},
                        "textStyle": {"fontSize": {"magnitude": 1, "unit": "PT"}},
                        "fields": "fontSize",
                    }
                })
                requests.append({
                    "updateParagraphStyle": {
                        "range": {"startIndex": ep_start, "endIndex": ep_end},
                        "paragraphStyle": {
                            "lineSpacing": 100,
                            "spaceAbove": {"magnitude": 0, "unit": "PT"},
                            "spaceBelow": {"magnitude": 0, "unit": "PT"},
                        },
                        "fields": "lineSpacing,spaceAbove,spaceBelow",
                    }
                })
            prev_char = char
            utf16_pos += char_units

        return {"requests": requests}

    def needs_formatting_pass(self) -> bool:
        """Check if a second pass is needed to apply formatting."""
        return getattr(self, "_needs_phase2", False)

    def generate_formatting_requests(self, doc_body: list[dict]) -> dict:
        """Generate formatting requests by searching the document for text content.

        This is phase 2 of the two-pass approach for documents with tables.
        Instead of calculating positions, we search for the actual text content
        in the document body.

        Args:
            doc_body: The 'body.content' list from the Google Docs API response

        Returns:
            Dict with 'requests' key containing formatting requests
        """
        requests = []

        # Build a map of document text positions
        # Each entry: (start_index, end_index, text_content)
        text_positions = []
        for elem in doc_body:
            if "paragraph" in elem:
                for e in elem["paragraph"].get("elements", []):
                    if "textRun" in e:
                        start = e.get("startIndex", 0)
                        end = e.get("endIndex", 0)
                        content = e["textRun"].get("content", "")
                        text_positions.append((start, end, content))

        # Build full document text with position mapping
        # Use UTF-16 offsets (not Python char index) since Docs API uses UTF-16 indices.
        # Emojis and other non-BMP chars are 2 UTF-16 code units but 1 Python char.
        doc_text = ""
        doc_pos_to_actual = {}  # doc_text position -> actual document index
        for start, _end, content in sorted(text_positions, key=lambda x: x[0]):
            utf16_offset = 0
            for char in content:
                doc_pos_to_actual[len(doc_text)] = start + utf16_offset
                doc_text += char
                utf16_offset += len(char.encode("utf-16-le")) // 2

        # Track which ranges we've already formatted (to handle duplicates)
        formatted_ranges: set[tuple[int, int]] = set()

        # Helper to find text in document and return actual position
        def find_text_position(text: str, start_after: int = 0, whole_line: bool = False) -> tuple[int, int] | None:
            """Find text in document, return (start_index, end_index) or None.

            Args:
                text: Text to search for.
                start_after: Only match at document positions >= this value.
                whole_line: If True, only match when text occupies an entire line
                    (preceded by newline/start and followed by newline/end).
                    Use for heading searches to avoid matching substrings.
            """
            if not text:
                return None

            # Search for the text in doc_text
            search_start = 0
            for actual_start in sorted(doc_pos_to_actual.keys()):
                if doc_pos_to_actual[actual_start] >= start_after:
                    search_start = actual_start
                    break

            pos = doc_text.find(text, search_start)
            while pos >= 0:
                if whole_line:
                    before_ok = (pos == 0 or doc_text[pos - 1] == '\n')
                    after_pos = pos + len(text)
                    after_ok = (after_pos >= len(doc_text) or doc_text[after_pos] == '\n')
                    if not (before_ok and after_ok):
                        pos = doc_text.find(text, pos + 1)
                        continue
                break

            if pos < 0:
                return None

            # Get actual document positions
            if pos not in doc_pos_to_actual:
                return None
            actual_start = doc_pos_to_actual[pos]
            # Find end position
            end_pos = pos + len(text) - 1
            if end_pos not in doc_pos_to_actual:
                # Approximate end position using UTF-16 length
                actual_end = actual_start + MarkdownToDocsConverter._utf16_len(text)
            else:
                actual_end = doc_pos_to_actual[end_pos] + 1

            return (actual_start, actual_end)

        # --- Phase 2a: Apply heading styles first and collect their positions ---
        # Heading positions are needed so format-range search can skip matches
        # inside heading text (e.g., "Adjusted Operating Income" appears in
        # the heading "Overview: Adjusted Operating Income & Rule of 40").
        heading_doc_ranges: set[tuple[int, int]] = set()
        last_heading_pos = 0
        for pr in self.paragraph_ranges:
            if pr.style_type == "NORMAL_TEXT":
                continue

            heading_text = self._slice_text_by_utf16(pr.start, pr.end).strip()
            if not heading_text:
                continue

            pos_range = find_text_position(heading_text, last_heading_pos, whole_line=True)
            if pos_range is None:
                continue

            start, end = pos_range
            last_heading_pos = start + 1
            heading_doc_ranges.add((start, end))
            # Extend to include the newline for paragraph styling
            end = end + 1

            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {
                        "namedStyleType": pr.style_type,
                        "spaceAbove": {"magnitude": 10, "unit": "PT"},
                        "spaceBelow": {"magnitude": 0, "unit": "PT"},
                    },
                    "fields": "namedStyleType,spaceAbove,spaceBelow",
                }
            })

        # --- Phase 2b: Apply text formatting (bold, italic, links, code) ---
        # Process in document order; skip matches inside heading paragraphs.
        last_pos = 0
        for fr in sorted(self.format_ranges, key=lambda x: x.start):
            if not fr.text:
                continue

            pos_range = find_text_position(fr.text, last_pos)

            # Skip matches that land inside a heading paragraph
            while pos_range and any(
                h_start <= pos_range[0] < h_end
                for h_start, h_end in heading_doc_ranges
            ):
                pos_range = find_text_position(fr.text, pos_range[1])

            if pos_range is None:
                continue

            start, end = pos_range

            # Skip if already formatted at this position
            if (start, end) in formatted_ranges:
                continue
            formatted_ranges.add((start, end))

            # Update last_pos to prevent matching same text twice
            last_pos = start + 1

            if fr.format_type == "bold":
                requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "textStyle": {"bold": True},
                        "fields": "bold",
                    }
                })
            elif fr.format_type == "italic":
                requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "textStyle": {"italic": True},
                        "fields": "italic",
                    }
                })
            elif fr.format_type == "link":
                requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "textStyle": {"link": {"url": fr.data.get("url", "")}},
                        "fields": "link",
                    }
                })
            elif fr.format_type in ("code", "code_block"):
                # Check if this code is at the start of a bullet list item
                # If so, skip green color to prevent green bullet glyphs
                is_bullet_start = any(
                    br.start == fr.start or br.start == fr.start - 1
                    for br in self.bullet_ranges
                )

                if is_bullet_start and fr.format_type == "code":
                    # Only apply monospace font, no green color
                    requests.append({
                        "updateTextStyle": {
                            "range": {"startIndex": start, "endIndex": end},
                            "textStyle": {
                                "weightedFontFamily": {"fontFamily": "Roboto Mono"},
                                "bold": False,
                                "italic": False,
                            },
                            "fields": "weightedFontFamily,bold,italic",
                        }
                    })
                else:
                    requests.append({
                        "updateTextStyle": {
                            "range": {"startIndex": start, "endIndex": end},
                            "textStyle": {
                                "weightedFontFamily": {"fontFamily": "Roboto Mono"},
                                "foregroundColor": {
                                    "color": {"rgbColor": {"red": 0.0, "green": 0.5, "blue": 0.0}}
                                },
                                "bold": False,
                                "italic": False,
                            },
                            "fields": "weightedFontFamily,foregroundColor,bold,italic",
                        }
                    })

        # Collect code block ranges to exclude from bullet searches
        code_block_ranges = set()
        for fr in self.format_ranges:
            if fr.format_type == "code_block":
                pos_range = find_text_position(fr.text, 0)
                if pos_range:
                    code_block_ranges.add(pos_range)

        def is_in_code_block(pos: int) -> bool:
            """Check if position is inside a code block."""
            for cb_start, cb_end in code_block_ranges:
                if cb_start <= pos < cb_end:
                    return True
            return False

        # Apply bullet lists - find the list item text and apply bullets
        # Process in document order to handle duplicates correctly
        bullet_last_pos = 0
        for br in sorted(self.bullet_ranges, key=lambda x: x.start):
            # Get the bullet text content (using UTF-16 positions)
            bullet_text = self._slice_text_by_utf16(br.start, br.end)
            if not bullet_text.strip():
                continue

            # Find the first line of the bullet to locate it
            first_line = bullet_text.split("\n")[0]
            if not first_line.strip():
                continue

            # Search from last position to find the right occurrence
            pos_range = find_text_position(first_line.strip(), bullet_last_pos)
            if pos_range is None:
                continue

            start, _ = pos_range

            # Skip if this text is inside a code block
            if is_in_code_block(start):
                # Try to find next occurrence
                pos_range = find_text_position(first_line.strip(), start + 1)
                if pos_range is None:
                    continue
                start, _ = pos_range
                if is_in_code_block(start):
                    continue

            # Calculate end based on bullet text length (UTF-16 units)
            end = start + MarkdownToDocsConverter._utf16_len(bullet_text)
            bullet_last_pos = start + 1

            requests.append({
                "createParagraphBullets": {
                    "range": {"startIndex": start, "endIndex": end},
                    "bulletPreset": br.bullet_preset,
                }
            })

        return {"requests": requests}

    def _generate_table_cell_requests(self, table: TableSpec, table_index: int) -> list[dict]:
        """Generate requests to populate table cells and apply formatting.

        After insertTable creates the table structure, each cell contains an empty
        paragraph. We process cells in REVERSE order (last cell first) so that
        inserting content into earlier cells doesn't shift the indices of later cells.

        For each cell in reverse order:
        1. Reset paragraph style to NORMAL_TEXT (+ CENTER alignment for non-leftmost)
        2. Insert text content (if any)
        3. Apply text styling (font; bold + white text for header row)
        Then: apply black background to all header row cells.
        """
        requests = []
        rows = table.rows
        cols = table.cols
        table_start = table_index + 1  # Table element (after \n inserted by Docs API)
        cell_font = self.base_font_family or "Inter"

        # Detect pacing columns: scan ALL header rows for "Pacing"
        pacing_cols: set[int] = set()
        for hr in range(table.header_rows):
            if hr < len(table.cells):
                for c in range(len(table.cells[hr])):
                    if "Pacing" in table.cells[hr][c]:
                        pacing_cols.add(c)

        # Process cells in reverse order (last cell to first)
        for r in range(rows - 1, -1, -1):
            for c in range(cols - 1, -1, -1):
                # Cell index formula for Google Docs tables:
                # When inserting a table after text, Google Docs adds an empty paragraph,
                # so the actual table starts 1 index later than the insertion point.
                # Cell content index = insertion_point + 1 (empty para) + 3 (table+row+cell headers)
                #                    + row * (cols * 2 + 1) + col * 2
                cell_index = table_index + 4 + r * (cols * 2 + 1) + c * 2
                cell_text = table.cells[r][c] if r < len(table.cells) and c < len(table.cells[r]) else ""

                # 1. Reset cell to NORMAL_TEXT; center-align all columns except leftmost
                para_style: dict = {"namedStyleType": "NORMAL_TEXT"}
                fields = "namedStyleType"
                if c > 0:
                    para_style["alignment"] = "CENTER"
                    fields += ",alignment"
                requests.append({
                    "updateParagraphStyle": {
                        "range": {
                            "startIndex": cell_index,
                            "endIndex": cell_index + 1,
                        },
                        "paragraphStyle": para_style,
                        "fields": fields,
                    }
                })

                # 2. Insert text content
                if cell_text:
                    requests.append({
                        "insertText": {
                            "location": {"index": cell_index},
                            "text": cell_text,
                        }
                    })

                    text_end = cell_index + MarkdownToDocsConverter._utf16_len(cell_text)

                    # 3. Apply text styling
                    if r < table.header_rows:
                        # Header row: bold + white text + font + 10pt
                        requests.append({
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": cell_index,
                                    "endIndex": text_end,
                                },
                                "textStyle": {
                                    "bold": True,
                                    "foregroundColor": {
                                        "color": {
                                            "rgbColor": {"red": 1.0, "green": 1.0, "blue": 1.0}
                                        }
                                    },
                                    "weightedFontFamily": {"fontFamily": cell_font},
                                    "fontSize": {"magnitude": 10, "unit": "PT"},
                                },
                                "fields": "bold,foregroundColor,weightedFontFamily,fontSize",
                            }
                        })
                    else:
                        # Data rows: font + 10pt
                        requests.append({
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": cell_index,
                                    "endIndex": text_end,
                                },
                                "textStyle": {
                                    "weightedFontFamily": {"fontFamily": cell_font},
                                    "fontSize": {"magnitude": 10, "unit": "PT"},
                                },
                                "fields": "weightedFontFamily,fontSize",
                            }
                        })

        # Black background for all header rows
        requests.append({
            "updateTableCellStyle": {
                "tableRange": {
                    "tableCellLocation": {
                        "tableStartLocation": {"index": table_start},
                        "rowIndex": 0,
                        "columnIndex": 0,
                    },
                    "rowSpan": table.header_rows,
                    "columnSpan": cols,
                },
                "tableCellStyle": {
                    "backgroundColor": {
                        "color": {
                            "rgbColor": {"red": 0.0, "green": 0.0, "blue": 0.0}
                        }
                    }
                },
                "fields": "backgroundColor",
            }
        })

        # Light gray background (#F3F3F3) for pacing columns (data rows only)
        for c in sorted(pacing_cols):
            if rows > table.header_rows:
                requests.append({
                    "updateTableCellStyle": {
                        "tableRange": {
                            "tableCellLocation": {
                                "tableStartLocation": {"index": table_start},
                                "rowIndex": table.header_rows,
                                "columnIndex": c,
                            },
                            "rowSpan": rows - table.header_rows,
                            "columnSpan": 1,
                        },
                        "tableCellStyle": {
                            "backgroundColor": {
                                "color": {
                                    "rgbColor": {
                                        "red": 0.9529412,
                                        "green": 0.9529412,
                                        "blue": 0.9529412,
                                    }
                                }
                            }
                        },
                        "fields": "backgroundColor",
                    }
                })

        # Condense table: reduce cell padding for tighter layout
        requests.append({
            "updateTableCellStyle": {
                "tableRange": {
                    "tableCellLocation": {
                        "tableStartLocation": {"index": table_start},
                        "rowIndex": 0,
                        "columnIndex": 0,
                    },
                    "rowSpan": rows,
                    "columnSpan": cols,
                },
                "tableCellStyle": {
                    "paddingTop": {"magnitude": 1, "unit": "PT"},
                    "paddingBottom": {"magnitude": 1, "unit": "PT"},
                    "paddingLeft": {"magnitude": 3, "unit": "PT"},
                    "paddingRight": {"magnitude": 3, "unit": "PT"},
                },
                "fields": "paddingTop,paddingBottom,paddingLeft,paddingRight",
            }
        })

        return requests


def convert_markdown_to_docs_requests(
    markdown: str, base_index: int = 1, base_font_family: str | None = None,
) -> dict:
    """Convenience function to convert markdown to Docs API requests.

    Args:
        markdown: The markdown text to convert
        base_index: Starting index in the document
        base_font_family: Optional font family to apply to all text (e.g., 'Inter')

    Returns:
        Dict with 'requests' key for batchUpdate
    """
    converter = MarkdownToDocsConverter(base_index=base_index, base_font_family=base_font_family)
    return converter.convert(markdown)
