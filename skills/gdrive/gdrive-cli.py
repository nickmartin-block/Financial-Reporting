#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "google-api-python-client>=2.174.0",
#     "google-auth-httplib2>=0.2.0",
#     "google-auth-oauthlib>=1.2.1",
#     "click>=8.0.0",
#     "mistune>=3.0.0",
#     "websockets>=13.0",
# ]
# ///
"""Google Drive CLI for agent skills."""
from __future__ import annotations

import builtins
import itertools
import json
import platform as _platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from scripts import auth
from scripts.services import get_drive_service, get_docs_service, get_sheets_service, get_slides_service


def output_json(data: dict | list) -> None:
    """Print data as JSON to stdout."""
    click.echo(json.dumps(data, indent=2, default=str))


def _sanitize_range(range_str: str) -> str:
    """Remove shell-escape artifacts from a Sheets range string.

    zsh history expansion can turn Sheet1!A1 into Sheet1\\!A1.
    The Google Sheets API rejects the backslash, so strip it.
    """
    if not range_str:
        return range_str
    return range_str.replace("\\!", "!")


def handle_error(e: Exception) -> None:
    """Handle errors with JSON output."""
    output_json({"error": str(e), "type": type(e).__name__})
    sys.exit(1)


IMAGE_WEBAPP_URL_PATH = Path.home() / ".config" / "gdrive-skill" / "image-webapp-url.txt"

def _get_image_webapp_url() -> str:
    """Get the configured image inserter web app URL."""
    if not IMAGE_WEBAPP_URL_PATH.exists():
        raise RuntimeError(
            "Image webapp URL not configured. One-time setup needed:\n"
            "1. Deploy the image-inserter-webapp.js as a Google Apps Script web app\n"
            "2. Run: gdrive-cli.py config set-image-webapp <URL>"
        )
    url = IMAGE_WEBAPP_URL_PATH.read_text().strip()
    if not (url.startswith("https://script.google.com/macros/s/") or url.startswith("https://script.google.com/a/macros/")):
        raise RuntimeError(
            f"Image webapp URL must be a Google Apps Script URL "
            f"(https://script.google.com/macros/s/...), got: {url}"
        )
    return url


def _read_doc_text(doc_id: str, tab_id: str | None = None) -> str:
    """Read the plain text content of a Google Doc.

    If *tab_id* is given, only that tab's text is returned.
    """
    docs = get_docs_service()
    doc = docs.documents().get(documentId=doc_id, includeTabsContent=True).execute()
    parts: list[str] = []
    for tab in doc.get("tabs", []):
        if tab_id and tab.get("tabProperties", {}).get("tabId") != tab_id:
            continue
        body = tab.get("documentTab", {}).get("body", {})
        for element in body.get("content", []):
            if "paragraph" in element:
                for elem in element["paragraph"].get("elements", []):
                    tr = elem.get("textRun")
                    if tr:
                        parts.append(tr.get("content", ""))
            elif "table" in element:
                for row in element["table"].get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        for cel in cell.get("content", []):
                            if "paragraph" in cel:
                                for elem in cel["paragraph"].get("elements", []):
                                    tr = elem.get("textRun")
                                    if tr:
                                        parts.append(tr.get("content", ""))
                        parts.append("\n")
    return "".join(parts)


def _expand_quote_from_doc(
    doc_id: str, quote: str, target_len: int = 60, tab_id: str | None = None,
) -> str:
    """Expand a short quote by reading surrounding text from the document.

    If the quote is already long enough or not found, returns the original.
    Adds surrounding words from the document to make the quote more unique
    for the find-and-select mechanism.
    """
    if len(quote) >= target_len:
        return quote
    try:
        full_text = _read_doc_text(doc_id, tab_id=tab_id)
        idx = full_text.find(quote)
        if idx == -1:
            return quote
        # Expand symmetrically to reach target_len
        expand = (target_len - len(quote)) // 2
        start = max(0, idx - expand)
        end = min(len(full_text), idx + len(quote) + expand)
        # Snap to word boundaries
        while start > 0 and full_text[start] not in (" ", "\n"):
            start -= 1
        if start > 0:
            start += 1  # skip the space
        while end < len(full_text) and full_text[end] not in (" ", "\n"):
            end += 1
        expanded = full_text[start:end].strip()
        # Don't cross paragraph boundaries
        if "\n" in expanded:
            # Keep the segment that contains the original quote
            for segment in expanded.split("\n"):
                if quote in segment:
                    return segment.strip()
        return expanded
    except Exception:
        return quote


# ---------------------------------------------------------------------------
# Shared CDP / Playwriter helpers
# ---------------------------------------------------------------------------

_RELAY_URL = "http://localhost:19988"
_RELAY_WS = "ws://localhost:19988/cdp"
_ARTIFACTORY_TGZ = (
    "https://global.block-artifacts.com/artifactory/"
    "npmjs-cache/playwriter/-/playwriter-0.0.80.tgz"
)


def _ensure_relay() -> None:
    """Start the Playwriter relay if not running."""
    import shutil
    import subprocess
    import time as _time
    import urllib.request

    try:
        urllib.request.urlopen(f"{_RELAY_URL}/", timeout=3)
        return  # Already running
    except Exception:
        pass

    if not shutil.which("playwriter"):
        click.echo("Installing playwriter CLI from JFrog...", err=True)
        import tempfile
        tgz = Path(tempfile.gettempdir()) / "playwriter-0.0.80.tgz"
        try:
            urllib.request.urlretrieve(_ARTIFACTORY_TGZ, str(tgz))
            subprocess.run(
                ["npm", "i", "-g", "--offline", str(tgz)],
                capture_output=True, timeout=60,
            )
        except Exception:
            pass

    if not shutil.which("playwriter"):
        raise RuntimeError(
            "playwriter CLI not found. Install it:\n"
            "  npm i -g playwriter\n"
            "Then install the Chrome extension:\n"
            "  https://chromewebstore.google.com/detail/playwriter-mcp/"
            "jfeammnjpkecdekppnclgkkffahnhfhe"
        )

    click.echo("Starting Playwriter relay...", err=True)
    subprocess.Popen(
        ["playwriter", "serve", "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _time.sleep(3)


def _get_relay_doc_target(doc_id: str, tab_id: str | None = None) -> dict:
    """Ensure relay is running, discover tabs, and return the target for *doc_id*.

    If *tab_id* is given, prefer a Chrome tab whose URL contains ``tab=<tab_id>``.

    Raises RuntimeError if the relay is unreachable, no tabs are enabled, or the
    target document is not open in any Playwriter-enabled tab.
    """
    import urllib.request

    _ensure_relay()

    try:
        resp = urllib.request.urlopen(f"{_RELAY_URL}/json/list", timeout=5)
        targets = json.loads(resp.read())
    except Exception as exc:
        raise RuntimeError(
            "Playwriter relay not reachable at localhost:19988.\n"
            "Setup:\n"
            "1. Install the Playwriter Chrome extension:\n"
            "   https://chromewebstore.google.com/detail/playwriter-mcp/"
            "jfeammnjpkecdekppnclgkkffahnhfhe\n"
            "2. Click the extension icon on a Chrome tab (turns green)\n"
            "3. The relay auto-starts when you run this command"
        ) from exc

    pages = [t for t in targets if t["type"] == "page"]
    if not pages:
        raise RuntimeError(
            "No Playwriter-enabled Chrome tabs found.\n"
            "Click the Playwriter extension icon on a Chrome tab (turns green)."
        )

    doc_url_prefix = f"https://docs.google.com/document/d/{doc_id}/"
    doc_pages = [p for p in pages if doc_url_prefix in p.get("url", "")]

    if not doc_pages:
        raise RuntimeError(
            f"Google Doc {doc_id} is not open in any Playwriter-enabled Chrome tab.\n"
            "Open the document in Chrome and click the Playwriter extension icon."
        )

    # Prefer a tab whose URL matches the requested tab_id
    if tab_id:
        for p in doc_pages:
            if f"tab={tab_id}" in p.get("url", ""):
                return p
        # Doc is open but on a different tab — _ensure_doc_tab will handle switching

    return doc_pages[0]


def _find_bar_has_match(status: str | None) -> bool:
    """Return True if the find-bar status text indicates at least one match.

    The status looks like ``"1 of 5"``; we check whether the count before
    ``" of "`` is not ``"0"``.
    """
    if not status:
        return False
    count = status.split(" of ")[0] if " of " in str(status) else "0"
    return count != "0"


_cdp_msg_id = itertools.count(1)


async def _cdp_call(ws, sid, method, params=None):
    """Send a CDP command and wait for its response."""
    import asyncio

    mid = next(_cdp_msg_id)
    payload = {"id": mid, "method": method, "sessionId": sid}
    if params:
        payload["params"] = params
    await ws.send(json.dumps(payload))
    for _ in range(30):
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if msg.get("id") == mid:
            return msg
    return None


async def _js_eval(ws, sid, expr):
    """Evaluate a JS expression in the target page and return the value."""
    r = await _cdp_call(ws, sid, "Runtime.evaluate", {"expression": expr})
    return r.get("result", {}).get("result", {}).get("value") if r else None


async def _type_text(ws, sid, text):
    """Type *text* character-by-character via CDP key events."""
    import asyncio

    for ch in text:
        await _cdp_call(ws, sid, "Input.dispatchKeyEvent", {
            "type": "keyDown", "key": ch, "text": ch,
        })
        await _cdp_call(ws, sid, "Input.dispatchKeyEvent", {
            "type": "keyUp", "key": ch,
        })
        await asyncio.sleep(0.03)


async def _raw_key(ws, sid, key, code, vk, modifiers=0):
    """Send key via CDP rawKeyDown — Chrome's native input pipeline."""
    await _cdp_call(ws, sid, "Input.dispatchKeyEvent", {
        "type": "rawKeyDown", "key": key, "code": code,
        "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk,
        "modifiers": modifiers,
    })
    await _cdp_call(ws, sid, "Input.dispatchKeyEvent", {
        "type": "keyUp", "key": key, "code": code,
        "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk,
        "modifiers": modifiers,
    })


async def _mouse_click(ws, sid, x, y):
    """Click at (x, y) via CDP mouse events."""
    import asyncio

    await _cdp_call(ws, sid, "Input.dispatchMouseEvent", {
        "type": "mouseMoved", "x": x, "y": y,
    })
    await asyncio.sleep(0.1)
    await _cdp_call(ws, sid, "Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": x, "y": y,
        "button": "left", "clickCount": 1,
    })
    await asyncio.sleep(0.05)
    await _cdp_call(ws, sid, "Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": x, "y": y,
        "button": "left", "clickCount": 1,
    })


async def _attach_to_target(ws, target):
    """Attach to a CDP target and return the session ID."""
    import asyncio

    await ws.send(json.dumps({
        "id": 1, "method": "Target.attachToTarget",
        "params": {"targetId": target["id"], "flatten": True},
    }))
    for _ in range(10):
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        if msg.get("id") == 1:
            return msg["result"]["sessionId"]
        if msg.get("method") == "Target.attachedToTarget":
            return msg["params"]["sessionId"]
    raise RuntimeError("Failed to attach to Chrome tab via CDP")


def _resolve_tab_title(doc_id: str, tab_id: str) -> str | None:
    """Resolve a tab ID to its title via the Docs API."""
    try:
        docs = get_docs_service()
        doc = docs.documents().get(documentId=doc_id, includeTabsContent=True).execute()
        for tab in doc.get("tabs", []):
            if tab.get("tabProperties", {}).get("tabId") == tab_id:
                return tab["tabProperties"]["title"]
    except Exception:
        pass
    return None


async def _click_doc_tab(ws, sid, tab_title: str):
    """Click the tab with *tab_title* in the Docs sidebar via JS."""
    import asyncio

    safe_title = json.dumps(tab_title)
    clicked = await _js_eval(ws, sid, (
        "(()=>{"
        "const items=document.querySelectorAll('[role=\"treeitem\"]');"
        "for(const el of items){"
        f"if(el.getAttribute('aria-label')&&"
        f"el.getAttribute('aria-label').startsWith({safe_title}))"
        "{el.click();return 'ok';}"
        "}"
        "return null;})()"
    ))
    if clicked == "ok":
        await asyncio.sleep(3)
        # Focus the editor on the new tab
        await _js_eval(ws, sid, (
            "(document.querySelector('.kix-appview-editor')"
            "||document.body).click();"
        ))
        await asyncio.sleep(1)
        return True
    return False


async def _ensure_doc_tab(ws, sid, doc_id: str, tab_id: str | None):
    """Switch to the correct Google Doc tab if *tab_id* is specified.

    Resolves the tab ID to a tab title via the Docs API, then clicks the
    matching ``role="treeitem"`` element in the Docs tab sidebar.  Returns
    the resolved tab title for later re-checks via ``_recheck_doc_tab``.
    """
    if not tab_id:
        return None
    current_url = await _js_eval(ws, sid, "window.location.href")
    if current_url and f"tab={tab_id}" in current_url:
        # Already on the right tab — still resolve title for re-checks
        return _resolve_tab_title(doc_id, tab_id)

    tab_title = _resolve_tab_title(doc_id, tab_id)
    if not tab_title:
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit?tab={tab_id}"
        raise RuntimeError(
            f"Could not resolve tab {tab_id} to a title.\n"
            f"Please navigate to: {doc_url}\n"
            "Then retry the command."
        )

    if await _click_doc_tab(ws, sid, tab_title):
        return tab_title

    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit?tab={tab_id}"
    raise RuntimeError(
        f"Could not find tab '{tab_title}' in the tab bar.\n"
        f"Please navigate to: {doc_url}\n"
        "Then retry the command."
    )


async def _recheck_doc_tab(ws, sid, tab_id: str | None, tab_title: str | None):
    """Re-click the doc tab and refocus editor if a shortcut shifted it.

    Only acts when the URL shows a different tab — zero overhead otherwise.
    """
    if not tab_id or not tab_title:
        return
    current_url = await _js_eval(ws, sid, "window.location.href")
    if current_url and f"tab={tab_id}" in current_url:
        return
    await _click_doc_tab(ws, sid, tab_title)


async def _get_find_bar_status(ws, sid):
    """Read the find-bar match count text (e.g. ``'1 of 5'``)."""
    return await _js_eval(ws, sid, (
        "(()=>{"
        "const s=document.querySelector('.docs-findinput-count');"
        "return s?s.textContent:'';"
        "})()"
    ))


# CDP modifier flags — macOS uses Cmd (Meta=4), Linux/Windows use Ctrl (2)
_MOD = 4 if _platform.system() == "Darwin" else 2
_ALT = 1
_SHIFT = 8


# ---------------------------------------------------------------------------
# Browser automation: inline comments
# ---------------------------------------------------------------------------

def _create_inline_comment_via_browser(
    doc_id: str, content: str, quote: str, tab_id: str | None = None,
    occurrence: int = 1, after: str | None = None,
) -> dict:
    """Create an inline-anchored comment by automating the Google Docs UI via CDP.

    Connects to the Playwriter Chrome extension's CDP relay at localhost:19988.
    Uses CDP rawKeyDown events for keyboard shortcuts (Cmd+F, Escape, Cmd+Alt+M)
    which go through Chrome's native input pipeline — required for Google Docs'
    canvas-based editor to properly handle find-and-select.

    If the initial quote is not found in the document, automatically expands it
    by reading surrounding text from the Docs API and retrying with a longer match.

    Prerequisites:
      1. Install the Playwriter Chrome extension from the Chrome Web Store
      2. Click the extension icon on any Chrome tab (icon turns green)
    """
    import asyncio

    import websockets

    # Pre-validate: verify the quote exists in the document
    try:
        doc_text = _read_doc_text(doc_id, tab_id=tab_id)
        if quote not in doc_text:
            raise RuntimeError(
                f"Quote not found in document: '{quote}'\n"
                "The --quote value must be an exact substring of text in the document."
            )
    except RuntimeError:
        raise
    except Exception:
        pass  # If we can't read the doc, proceed and let the find bar handle it

    target = _get_relay_doc_target(doc_id, tab_id=tab_id)

    async def _run() -> dict:
        async with websockets.connect(_RELAY_WS) as ws:
            sid = await _attach_to_target(ws, target)
            tab_title = await _ensure_doc_tab(ws, sid, doc_id, tab_id)

            # Dismiss any stale comment drafts
            await _js_eval(ws, sid, (
                "document.querySelectorAll('[data-tooltip=\"Discard comment\"]')"
                ".forEach(b=>{if(b.getBoundingClientRect().width>0)b.click()});"
            ))
            await asyncio.sleep(0.5)

            # Focus the editor
            await _js_eval(ws, sid, (
                "(document.querySelector('.kix-appview-editor')"
                "||document.body).click();"
            ))
            await asyncio.sleep(0.3)

            # Clear stale find bar text — prevents Cmd+F from shifting tabs
            await _raw_key(ws, sid, "f", "KeyF", 70, modifiers=_MOD)
            await asyncio.sleep(0.5)
            await _raw_key(ws, sid, "a", "KeyA", 65, modifiers=_MOD)
            await asyncio.sleep(0.1)
            await _raw_key(ws, sid, "Backspace", "Backspace", 8)
            await asyncio.sleep(0.1)
            await _raw_key(ws, sid, "Escape", "Escape", 27)
            await asyncio.sleep(0.5)

            # Re-ensure correct tab after clearing find bar
            await _recheck_doc_tab(ws, sid, tab_id, tab_title)

            # Position cursor at anchor text so find bar starts nearby
            if after:
                await _raw_key(ws, sid, "f", "KeyF", 70, modifiers=_MOD)
                await asyncio.sleep(0.5)
                await _raw_key(ws, sid, "a", "KeyA", 65, modifiers=_MOD)
                await asyncio.sleep(0.1)
                await _type_text(ws, sid, after)
                await asyncio.sleep(1.5)
                await _raw_key(ws, sid, "Escape", "Escape", 27)
                await asyncio.sleep(0.5)
            elif occurrence > 1:
                await _raw_key(ws, sid, "ArrowUp", "ArrowUp", 38, modifiers=_MOD)
                await asyncio.sleep(0.5)

            # Open Find bar, type quote
            async def _find_text_on_tab(text: str) -> str | None:
                """Open find bar, type text, return status. Retries once if tab shifts."""
                for attempt in range(2):
                    await _raw_key(ws, sid, "f", "KeyF", 70, modifiers=_MOD)
                    await asyncio.sleep(1)
                    # Clear any stale text in find bar
                    await _raw_key(ws, sid, "a", "KeyA", 65, modifiers=_MOD)
                    await asyncio.sleep(0.1)
                    await _type_text(ws, sid, text)
                    await asyncio.sleep(1.5)
                    # Check if Cmd+F shifted us to the wrong tab
                    cur = await _js_eval(ws, sid, "window.location.href")
                    if tab_id and cur and f"tab={tab_id}" not in cur:
                        # Tab shifted — close find bar, switch back, retry
                        await _raw_key(ws, sid, "Escape", "Escape", 27)
                        await asyncio.sleep(0.3)
                        await _recheck_doc_tab(ws, sid, tab_id, tab_title)
                        if attempt == 0:
                            continue
                    return await _get_find_bar_status(ws, sid)
                return None

            _dialog_check_js = (
                "document.querySelector('[aria-label=\"Comment draft\"]')"
                "?'open':'closed'"
            )
            _post_btn_js = (
                "(()=>{"
                "const btns=document.querySelectorAll("
                "'[data-tooltip=\"Post Comment\"]');"
                "for(const b of btns){"
                "const r=b.getBoundingClientRect();"
                "if(r.width>0)return JSON.stringify("
                "{x:r.x+r.width/2,y:r.y+r.height/2});}"
                "return null;})()"
            )

            comment_posted = False
            for _comment_attempt in range(2):
                # --- Find text and open comment dialog ---
                status = await _find_text_on_tab(quote)
                found = _find_bar_has_match(status)

                if not found:
                    expanded = _expand_quote_from_doc(doc_id, quote, tab_id=tab_id)
                    if expanded != quote:
                        await _raw_key(ws, sid, "a", "KeyA", 65, modifiers=_MOD)
                        await asyncio.sleep(0.1)
                        await _type_text(ws, sid, expanded)
                        await asyncio.sleep(1.5)
                        status = await _get_find_bar_status(ws, sid)
                        found = _find_bar_has_match(status)

                if not found:
                    raise RuntimeError(
                        f"Text not found in document: '{quote}' (find status: {status})"
                    )

                # Advance to Nth occurrence (Enter = next match in find bar)
                if occurrence > 1:
                    for _ in range(occurrence - 1):
                        await _raw_key(ws, sid, "Return", "Enter", 13)
                        await asyncio.sleep(0.3)
                    await asyncio.sleep(0.5)

                # Escape to close find bar — preserves selection
                await _raw_key(ws, sid, "Escape", "Escape", 27)
                await asyncio.sleep(0.5)

                # Cmd+Alt+M to open comment dialog
                await _raw_key(ws, sid, "m", "KeyM", 77, modifiers=_MOD | _ALT)
                await asyncio.sleep(2)

                if await _js_eval(ws, sid, _dialog_check_js) != "open":
                    if _comment_attempt == 0:
                        continue  # retry
                    raise RuntimeError("Comment dialog did not open")

                # Type comment content
                await _type_text(ws, sid, content)
                await asyncio.sleep(0.5)

                # --- Submit: Cmd+Enter first, mouse click fallback ---
                await _raw_key(ws, sid, "Return", "Enter", 13, modifiers=_MOD)
                await asyncio.sleep(2)

                if await _js_eval(ws, sid, _dialog_check_js) == "closed":
                    comment_posted = True
                    break

                # Mouse click fallback
                post_pos = await _js_eval(ws, sid, _post_btn_js)
                if post_pos:
                    pos = json.loads(post_pos)
                    await _mouse_click(ws, sid, pos["x"], pos["y"])
                    await asyncio.sleep(2)

                if await _js_eval(ws, sid, _dialog_check_js) == "closed":
                    comment_posted = True
                    break

                # Cancel and retry the full cycle
                await _raw_key(ws, sid, "Escape", "Escape", 27)
                await asyncio.sleep(1)
                # Dismiss any stale drafts
                await _js_eval(ws, sid, (
                    "document.querySelectorAll('[data-tooltip=\"Discard comment\"]')"
                    ".forEach(b=>{if(b.getBoundingClientRect().width>0)b.click()});"
                ))
                await asyncio.sleep(0.5)

            if not comment_posted:
                raise RuntimeError(
                    "Comment could not be posted after 2 attempts. "
                    "The comment dialog failed to submit."
                )

        # Verify comment was actually created via Drive API (retry for propagation delay)
        import time as _time
        drive = get_drive_service()
        match = []
        for _verify in range(3):
            if _verify > 0:
                _time.sleep(2)
            comments_resp = drive.comments().list(
                fileId=doc_id,
                fields="comments(id,content,createdTime,anchor)",
            ).execute().get("comments", [])
            now = datetime.now(timezone.utc)
            match = [
                c for c in comments_resp
                if content in c.get("content", "")
                and c.get("anchor")
                and (now - datetime.fromisoformat(
                    c["createdTime"].replace("Z", "+00:00")
                )).total_seconds() < 30
            ]
            if match:
                break
        if not match:
            raise RuntimeError(
                "Comment was not created — Post Comment button click may have "
                "missed. Please retry."
            )
        return {
            "status": "ok",
            "method": "browser_automation",
            "inline": True,
            "comment": match[0],
        }

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Browser automation: suggested edits
# ---------------------------------------------------------------------------

def _create_suggested_edit_via_browser(
    doc_id: str, find_text: str, replace_text: str, tab_id: str | None = None,
    occurrence: int = 1, after: str | None = None,
) -> dict:
    """Create a suggested edit by automating the Google Docs UI via CDP.

    Switches to Suggesting mode, finds and selects the target text, types the
    replacement (which Docs records as a suggestion), then switches back to
    Editing mode.  Reuses the same Playwriter CDP relay as inline comments.

    Prerequisites:
      1. Install the Playwriter Chrome extension from the Chrome Web Store
      2. Click the extension icon on any Chrome tab (icon turns green)
    """
    import asyncio

    import websockets

    # Pre-validate: verify the find text exists in the document
    try:
        doc_text = _read_doc_text(doc_id, tab_id=tab_id)
        if find_text not in doc_text:
            raise RuntimeError(
                f"Text not found in document: '{find_text}'\n"
                "The --find value must be an exact substring of text in the document."
            )
    except RuntimeError:
        raise
    except Exception:
        pass

    target = _get_relay_doc_target(doc_id, tab_id=tab_id)

    async def _run() -> dict:
        async with websockets.connect(_RELAY_WS) as ws:
            sid = await _attach_to_target(ws, target)
            tab_title = await _ensure_doc_tab(ws, sid, doc_id, tab_id)

            # Focus the editor
            await _js_eval(ws, sid, (
                "(document.querySelector('.kix-appview-editor')"
                "||document.body).click();"
            ))
            await asyncio.sleep(0.5)

            # Clear stale find bar text before entering suggesting mode —
            # stale text from previous operations can cause Cmd+F to shift tabs
            await _raw_key(ws, sid, "f", "KeyF", 70, modifiers=_MOD)
            await asyncio.sleep(0.5)
            await _raw_key(ws, sid, "a", "KeyA", 65, modifiers=_MOD)
            await asyncio.sleep(0.1)
            await _raw_key(ws, sid, "Backspace", "Backspace", 8)
            await asyncio.sleep(0.1)
            await _raw_key(ws, sid, "Escape", "Escape", 27)
            await asyncio.sleep(0.5)

            # Re-ensure correct tab (clearing find bar might have shifted it)
            await _recheck_doc_tab(ws, sid, tab_id, tab_title)

            # Switch to Suggesting mode: Cmd+Shift+Option+X
            await _raw_key(ws, sid, "x", "KeyX", 88, modifiers=_MOD | _ALT | _SHIFT)
            await asyncio.sleep(1.5)

            try:
                # Position cursor at anchor text so find bar starts nearby
                if after:
                    await _raw_key(ws, sid, "f", "KeyF", 70, modifiers=_MOD)
                    await asyncio.sleep(0.5)
                    await _raw_key(ws, sid, "a", "KeyA", 65, modifiers=_MOD)
                    await asyncio.sleep(0.1)
                    await _type_text(ws, sid, after)
                    await asyncio.sleep(1.5)
                    await _raw_key(ws, sid, "Escape", "Escape", 27)
                    await asyncio.sleep(0.5)
                elif occurrence > 1:
                    await _raw_key(ws, sid, "ArrowUp", "ArrowUp", 38, modifiers=_MOD)
                    await asyncio.sleep(0.5)

                # Open find bar, clear stale text, type search
                for _attempt in range(2):
                    await _raw_key(ws, sid, "f", "KeyF", 70, modifiers=_MOD)
                    await asyncio.sleep(1)
                    await _raw_key(ws, sid, "a", "KeyA", 65, modifiers=_MOD)
                    await asyncio.sleep(0.5)
                    await _type_text(ws, sid, find_text)
                    await asyncio.sleep(2)
                    # Check if Cmd+F shifted tabs
                    cur = await _js_eval(ws, sid, "window.location.href")
                    if tab_id and cur and f"tab={tab_id}" not in cur:
                        await _raw_key(ws, sid, "Escape", "Escape", 27)
                        await asyncio.sleep(0.3)
                        await _recheck_doc_tab(ws, sid, tab_id, tab_title)
                        if _attempt == 0:
                            continue
                    break

                # Verify match
                status = await _get_find_bar_status(ws, sid)
                if not _find_bar_has_match(status):
                    await _raw_key(ws, sid, "Escape", "Escape", 27)
                    raise RuntimeError(
                        f"Text not found in document: '{find_text}' "
                        f"(find status: {status})"
                    )

                # Advance to Nth occurrence (Enter = next match in find bar)
                if occurrence > 1:
                    for _ in range(occurrence - 1):
                        await _raw_key(ws, sid, "Return", "Enter", 13)
                        await asyncio.sleep(0.3)
                    await asyncio.sleep(0.5)

                # Escape — selection preserved via rawKeyDown
                await _raw_key(ws, sid, "Escape", "Escape", 27)
                await asyncio.sleep(1)

                # Type replacement — in Suggesting mode this creates a suggestion
                await _type_text(ws, sid, replace_text)
                await asyncio.sleep(1.5)
            finally:
                # Always switch back to Editing mode: Cmd+Shift+Option+Z
                await _raw_key(ws, sid, "z", "KeyZ", 90, modifiers=_MOD | _ALT | _SHIFT)
                await asyncio.sleep(0.5)

        return {"status": "ok", "method": "browser_automation", "suggestion": True}

    return asyncio.run(_run())


def _insert_image_via_webapp(target_id: str, local_path: str, target: str = "docs",
                              slide_index: int = 0, tab_id: str | None = None,
                              cleanup: bool = True) -> dict:
    """Upload image to Drive and insert via Apps Script web app."""
    import urllib.request
    from googleapiclient.http import MediaFileUpload

    drive = get_drive_service()
    webapp_url = _get_image_webapp_url()
    creds = auth.require_auth()

    # Upload image to Drive
    local_file = Path(local_path)
    media = MediaFileUpload(str(local_file), resumable=True)
    file_meta = {"name": f"_temp_image_{local_file.name}"}
    uploaded = drive.files().create(
        body=file_meta,
        media_body=media,
        fields="id,name",
        supportsAllDrives=True,
    ).execute()
    drive_file_id = uploaded["id"]

    try:
        # Call the web app
        payload = {"docId": target_id, "driveFileId": drive_file_id, "target": target}
        if target == "slides":
            payload["slideIndex"] = slide_index
        if tab_id:
            payload["tabId"] = tab_id

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webapp_url,
            data=data,
            headers={
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    finally:
        if cleanup:
            try:
                drive.files().delete(fileId=drive_file_id).execute()
            except Exception:
                pass

    return {
        "status": result.get("status", "ok"),
        "target": target,
        "targetId": target_id,
        "imageName": local_file.name,
    }


@click.group()
def cli():
    """Google Drive CLI for agent skills."""
    pass


# =============================================================================
# Auth commands
# =============================================================================

@cli.group()
def auth_cmd():
    """Authentication commands."""
    pass


@auth_cmd.command("login")
@click.option("--force", is_flag=True, help="Force re-authentication")
def auth_login(force: bool):
    """Authenticate with Google OAuth."""
    try:
        result = auth.login(force=force)
        output_json(result)
    except Exception as e:
        handle_error(e)


@auth_cmd.command("status")
def auth_status():
    """Check authentication status."""
    output_json(auth.get_auth_status())


@auth_cmd.command("logout")
def auth_logout():
    """Remove stored credentials."""
    output_json(auth.logout())


# Alias 'auth' group
cli.add_command(auth_cmd, name="auth")


# =============================================================================
# Search command
# =============================================================================

@cli.command()
@click.argument("query")
@click.option("--limit", default=10, help="Maximum results")
@click.option("--mime-type", default="", help="Filter by MIME type")
@click.option("--drive-id", default="", help="Search in specific shared drive")
@click.option("--parent", default="", help="Search within folder ID")
@click.option("--raw-query", is_flag=True, help="Treat query as raw Drive API query")
def search(query: str, limit: int, mime_type: str, drive_id: str, parent: str, raw_query: bool):
    """Search for files in Google Drive."""
    try:
        service = get_drive_service()
        
        # Build query
        if raw_query:
            q = query
        else:
            # Simple text search in name and content
            q = f"fullText contains '{query}'"
        
        if mime_type:
            q += f" and mimeType='{mime_type}'"
        if parent:
            q += f" and '{parent}' in parents"
        
        # Build request params
        params = {
            "q": q,
            "pageSize": min(limit, 100),
            "fields": "files(id,name,mimeType,webViewLink,modifiedTime,parents)",
        }
        
        if drive_id:
            params["driveId"] = drive_id
            params["corpora"] = "drive"
            params["includeItemsFromAllDrives"] = True
            params["supportsAllDrives"] = True
        else:
            params["corpora"] = "allDrives"
            params["includeItemsFromAllDrives"] = True
            params["supportsAllDrives"] = True
        
        result = service.files().list(**params).execute()
        files = result.get("files", [])
        
        output_json({
            "count": len(files),
            "files": files,
        })
    except Exception as e:
        handle_error(e)


# =============================================================================
# List command
# =============================================================================

@cli.command("list")
@click.argument("folder_id", required=False, default=None)
@click.option("--limit", default=50, help="Maximum results")
def list_cmd(folder_id: str | None, limit: int):
    """List contents of a folder in Google Drive."""
    try:
        service = get_drive_service()
        
        # Use 'root' if no folder ID provided
        parent_id = folder_id if folder_id else "root"
        
        params = {
            "q": f"'{parent_id}' in parents and trashed = false",
            "pageSize": min(limit, 100),
            "fields": "files(id,name,mimeType,modifiedTime)",
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        }
        
        result = service.files().list(**params).execute()
        files = result.get("files", [])
        
        output_json({
            "files": files,
        })
    except Exception as e:
        handle_error(e)


# =============================================================================
# Read command
# =============================================================================

@cli.command()
@click.argument("file_id")
@click.option("--format", "output_format", default="auto",
              type=click.Choice(["auto", "markdown", "text", "html", "raw"]),
              help="Output format")
@click.option("--all-tabs", is_flag=True, help="For Docs/Sheets: read all tabs")
@click.option("--tab", "tab_id", default="", help="For Docs: read specific tab by ID (e.g., t.abc123)")
def read(file_id: str, output_format: str, all_tabs: bool, tab_id: str):
    """Read a file from Google Drive."""
    try:
        drive = get_drive_service()
        
        # Get file metadata
        file_meta = drive.files().get(
            fileId=file_id,
            fields="id,name,mimeType,webViewLink",
            supportsAllDrives=True,
        ).execute()
        
        mime_type = file_meta.get("mimeType", "")
        content = None
        
        # Handle Google Docs
        if mime_type == "application/vnd.google-apps.document":
            docs_svc = get_docs_service()
            doc = docs_svc.documents().get(
                documentId=file_id,
                includeTabsContent=True,
            ).execute()
            content = _extract_doc_text(doc, include_all_tabs=all_tabs, tab_id=tab_id)
            
        # Handle Google Sheets
        elif mime_type == "application/vnd.google-apps.spreadsheet":
            sheets = get_sheets_service()
            if all_tabs:
                # Get all sheets
                meta = sheets.spreadsheets().get(
                    spreadsheetId=file_id,
                    fields="sheets(properties(sheetId,title,index,hidden))",
                ).execute()
                
                visible_tabs = [
                    s.get("properties", {})
                    for s in meta.get("sheets", [])
                    if not s.get("properties", {}).get("hidden", False)
                ]
                
                ranges_to_fetch = [f"'{t.get('title')}'!A:ZZ" for t in visible_tabs]
                batch_result = sheets.spreadsheets().values().batchGet(
                    spreadsheetId=file_id,
                    ranges=ranges_to_fetch,
                ).execute()
                
                by_title = {}
                for value_range in batch_result.get("valueRanges", []):
                    full_range = value_range.get("range", "")
                    sheet_title = full_range.split("!", 1)[0].strip("'")
                    by_title[sheet_title] = value_range.get("values", [])
                
                content = [
                    {"title": t.get("title"), "values": by_title.get(t.get("title"), [])}
                    for t in visible_tabs
                ]
            else:
                result = sheets.spreadsheets().values().get(
                    spreadsheetId=file_id,
                    range="A:ZZ",
                ).execute()
                content = result.get("values", [])
            
        # Handle other files - export or download
        else:
            # Try to export as text
            try:
                content = drive.files().export(
                    fileId=file_id,
                    mimeType="text/plain",
                ).execute().decode("utf-8")
            except Exception:
                # Fall back to download
                content = drive.files().get_media(
                    fileId=file_id,
                ).execute().decode("utf-8", errors="replace")
        
        output_json({
            "file": file_meta,
            "content": content,
            "format": output_format,
        })
    except Exception as e:
        handle_error(e)


def _extract_body_text(body: dict) -> str:
    """Extract plain text from a document body."""
    text_parts = []
    content = body.get("content", [])
    
    for element in content:
        if "paragraph" in element:
            para = element["paragraph"]
            for elem in para.get("elements", []):
                if "textRun" in elem:
                    text_parts.append(elem["textRun"].get("content", ""))
        elif "table" in element:
            table = element["table"]
            for row in table.get("tableRows", []):
                row_texts = []
                for cell in row.get("tableCells", []):
                    cell_text = ""
                    for cell_content in cell.get("content", []):
                        if "paragraph" in cell_content:
                            for elem in cell_content["paragraph"].get("elements", []):
                                if "textRun" in elem:
                                    cell_text += elem["textRun"].get("content", "").strip()
                    row_texts.append(cell_text)
                text_parts.append(" | ".join(row_texts) + "\n")
    
    return "".join(text_parts)


def _find_tab_by_id(tabs: list[dict], target_id: str) -> dict | None:
    """Recursively search for a tab by ID in a list of tabs."""
    for tab in tabs:
        props = tab.get("tabProperties", {})
        if props.get("tabId") == target_id:
            return tab
        child_tabs = tab.get("childTabs", [])
        if child_tabs:
            found = _find_tab_by_id(child_tabs, target_id)
            if found:
                return found
    return None


def _flatten_all_tabs(tabs: list[dict]) -> list[dict]:
    """Recursively flatten all tabs (including nested child tabs) into a flat list."""
    result = []
    for tab in tabs:
        result.append(tab)
        child_tabs = tab.get("childTabs", [])
        if child_tabs:
            result.extend(_flatten_all_tabs(child_tabs))
    return result


def _get_tab_body(doc: dict, tab_id: str = "") -> dict:
    """Get the body dict for a specific tab, or the first/default tab.

    Always expects a document fetched with includeTabsContent=True.
    Falls back to doc["body"] for legacy format.
    """
    tabs = doc.get("tabs", [])
    if tabs:
        if tab_id:
            target = _find_tab_by_id(tabs, tab_id)
            if target:
                return target.get("documentTab", {}).get("body", {})
            return {}
        return tabs[0].get("documentTab", {}).get("body", {})
    return doc.get("body", {})


def _extract_doc_text(doc: dict, include_all_tabs: bool = False, tab_id: str = "") -> str | dict:
    """Extract plain text from a Google Doc.

    If tab_id is provided, returns content from that specific tab.
    If include_all_tabs is True and the doc has tabs, returns a dict with tab contents.
    Otherwise returns a string with the first tab's content.
    """
    tabs = doc.get("tabs", [])

    if tabs:
        if tab_id:
            target_tab = _find_tab_by_id(tabs, tab_id)
            if target_tab:
                props = target_tab.get("tabProperties", {})
                body = target_tab.get("documentTab", {}).get("body", {})
                return {
                    "tabId": props.get("tabId"),
                    "title": props.get("title"),
                    "content": _extract_body_text(body),
                }
            else:
                all_tabs = _flatten_all_tabs(tabs)
                return {
                    "error": f"Tab '{tab_id}' not found",
                    "available_tabs": [
                        {"tabId": t.get("tabProperties", {}).get("tabId"), "title": t.get("tabProperties", {}).get("title")}
                        for t in all_tabs
                    ],
                }

        if include_all_tabs:
            all_tabs = _flatten_all_tabs(tabs)
            return [
                {
                    "tabId": t.get("tabProperties", {}).get("tabId"),
                    "title": t.get("tabProperties", {}).get("title"),
                    "content": _extract_body_text(t.get("documentTab", {}).get("body", {})),
                }
                for t in all_tabs
            ]
        else:
            first_tab = tabs[0]
            return _extract_body_text(first_tab.get("documentTab", {}).get("body", {}))

    body = doc.get("body", {})
    return _extract_body_text(body)


# =============================================================================
# Download command
# =============================================================================

@cli.command()
@click.argument("file_id")
@click.option("--dest", required=True, help="Destination path")
def download(file_id: str, dest: str):
    """Download a file from Google Drive."""
    try:
        drive = get_drive_service()
        
        # Get file metadata
        file_meta = drive.files().get(
            fileId=file_id,
            fields="id,name,mimeType",
            supportsAllDrives=True,
        ).execute()
        
        dest_path = Path(dest)
        if dest_path.is_dir():
            dest_path = dest_path / file_meta["name"]
        
        mime_type = file_meta.get("mimeType", "")
        
        # Handle Google Workspace files - export
        export_map = {
            "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
            "application/vnd.google-apps.spreadsheet": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
            "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
        }
        
        if mime_type in export_map:
            export_mime, ext = export_map[mime_type]
            if not dest_path.suffix:
                dest_path = dest_path.with_suffix(ext)
            content = drive.files().export(fileId=file_id, mimeType=export_mime).execute()
        else:
            content = drive.files().get_media(fileId=file_id).execute()
        
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(content if isinstance(content, bytes) else content.encode())
        
        output_json({
            "status": "ok",
            "path": str(dest_path),
            "size": len(content),
            "file": file_meta,
        })
    except Exception as e:
        handle_error(e)


# =============================================================================
# Upload command
# =============================================================================

@cli.command()
@click.argument("local_path", type=click.Path(exists=True))
@click.option("--name", default="", help="Name for the file in Drive (default: local filename)")
@click.option("--parent", default="", help="Parent folder ID")
@click.option("--mime-type", default="", help="MIME type (auto-detected if not provided)")
@click.option("--convert-to", type=click.Choice(["doc", "sheet", "slides", ""]), default="",
              help="Convert to Google Workspace format")
def upload(local_path: str, name: str, parent: str, mime_type: str, convert_to: str):
    """Upload a local file to Google Drive."""
    try:
        from googleapiclient.http import MediaFileUpload
        
        drive = get_drive_service()
        local_file = Path(local_path)
        
        file_name = name if name else local_file.name
        
        file_metadata = {"name": file_name}
        if parent:
            file_metadata["parents"] = [parent]
        
        # Handle conversion to Google Workspace format
        convert_map = {
            "doc": "application/vnd.google-apps.document",
            "sheet": "application/vnd.google-apps.spreadsheet",
            "slides": "application/vnd.google-apps.presentation",
        }
        if convert_to:
            file_metadata["mimeType"] = convert_map[convert_to]
        
        media = MediaFileUpload(
            str(local_file),
            mimetype=mime_type if mime_type else None,
            resumable=True,
        )
        
        result = drive.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,name,mimeType,webViewLink,size",
            supportsAllDrives=True,
        ).execute()
        
        output_json({
            "status": "ok",
            "file": result,
        })
    except Exception as e:
        handle_error(e)


# =============================================================================
# Export command
# =============================================================================

@cli.command()
@click.argument("file_id")
@click.option("--dest", required=True, help="Destination path")
@click.option("--format", "export_format", required=True,
              type=click.Choice(["pdf", "docx", "txt", "html", "xlsx", "csv", "pptx", "odt", "ods"]),
              help="Export format")
def export(file_id: str, dest: str, export_format: str):
    """Export a Google Workspace file to a different format."""
    try:
        drive = get_drive_service()
        
        # Map format to MIME type
        format_map = {
            "pdf": ("application/pdf", ".pdf"),
            "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
            "txt": ("text/plain", ".txt"),
            "html": ("text/html", ".html"),
            "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
            "csv": ("text/csv", ".csv"),
            "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
            "odt": ("application/vnd.oasis.opendocument.text", ".odt"),
            "ods": ("application/vnd.oasis.opendocument.spreadsheet", ".ods"),
        }
        
        export_mime, ext = format_map[export_format]
        
        # Get file metadata
        file_meta = drive.files().get(
            fileId=file_id,
            fields="id,name,mimeType",
            supportsAllDrives=True,
        ).execute()
        
        dest_path = Path(dest)
        if dest_path.is_dir():
            base_name = Path(file_meta["name"]).stem
            dest_path = dest_path / f"{base_name}{ext}"
        elif not dest_path.suffix:
            dest_path = dest_path.with_suffix(ext)
        
        content = drive.files().export(
            fileId=file_id,
            mimeType=export_mime,
        ).execute()
        
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(content if isinstance(content, bytes) else content.encode())
        
        output_json({
            "status": "ok",
            "path": str(dest_path),
            "size": len(content),
            "format": export_format,
            "file": file_meta,
        })
    except Exception as e:
        handle_error(e)


# =============================================================================
# Rename command
# =============================================================================

@cli.command()
@click.argument("file_id")
@click.argument("new_name")
def rename(file_id: str, new_name: str):
    """Rename a file in Google Drive."""
    try:
        drive = get_drive_service()
        
        result = drive.files().update(
            fileId=file_id,
            body={"name": new_name},
            fields="id,name,webViewLink",
            supportsAllDrives=True,
        ).execute()
        
        output_json({
            "status": "ok",
            "file": result,
        })
    except Exception as e:
        handle_error(e)


# =============================================================================
# Info command
# =============================================================================

@cli.command()
@click.argument("file_id")
def info(file_id: str):
    """Get file metadata."""
    try:
        drive = get_drive_service()
        
        file_meta = drive.files().get(
            fileId=file_id,
            fields="*",
            supportsAllDrives=True,
        ).execute()
        
        output_json(file_meta)
    except Exception as e:
        handle_error(e)


# =============================================================================
# Mkdir command
# =============================================================================

@cli.command()
@click.argument("name")
@click.option("--parent", default="", help="Parent folder ID")
def mkdir(name: str, parent: str):
    """Create a new folder in Google Drive."""
    try:
        drive = get_drive_service()
        
        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        
        if parent:
            file_metadata["parents"] = [parent]
        
        folder = drive.files().create(
            body=file_metadata,
            fields="id,name,webViewLink",
            supportsAllDrives=True,
        ).execute()
        
        output_json(folder)
    except Exception as e:
        handle_error(e)


# =============================================================================
# Create command (for Docs/Sheets)
# =============================================================================

@cli.command()
@click.argument("doc_type", metavar="TYPE", type=click.Choice(["doc", "sheet", "slides"]))
@click.argument("name")
@click.option("--parent", default="", help="Parent folder ID")
def create(doc_type: str, name: str, parent: str):
    """Create a new Google Doc, Sheet, or Slides presentation."""
    try:
        drive = get_drive_service()

        mime_types = {
            "doc": "application/vnd.google-apps.document",
            "sheet": "application/vnd.google-apps.spreadsheet",
            "slides": "application/vnd.google-apps.presentation",
        }
        
        file_metadata = {
            "name": name,
            "mimeType": mime_types[doc_type],
        }
        
        if parent:
            file_metadata["parents"] = [parent]
        
        result = drive.files().create(
            body=file_metadata,
            fields="id,name,mimeType,webViewLink",
            supportsAllDrives=True,
        ).execute()
        
        output_json(result)
    except Exception as e:
        handle_error(e)


# =============================================================================
# Docs commands
# =============================================================================

@cli.group()
def docs():
    """Google Docs operations."""
    pass


@docs.command("append")
@click.argument("doc_id")
@click.argument("text")
def docs_append(doc_id: str, text: str):
    """Append plain text to a Google Doc (no formatting)."""
    try:
        docs_service = get_docs_service()

        # Get current doc length
        doc = docs_service.documents().get(documentId=doc_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1

        requests = [{
            "insertText": {
                "location": {"index": end_index},
                "text": text,
            }
        }]

        result = docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()

        output_json({"status": "ok", "result": result})
    except Exception as e:
        handle_error(e)


@docs.command("insert")
@click.argument("doc_id")
@click.argument("text")
@click.option("--index", default=1, help="Insert position (1-based)")
def docs_insert(doc_id: str, text: str, index: int):
    """Insert text at a position in a Google Doc."""
    try:
        docs_service = get_docs_service()

        requests = [{
            "insertText": {
                "location": {"index": index},
                "text": text,
            }
        }]

        result = docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()

        output_json({"status": "ok", "result": result})
    except Exception as e:
        handle_error(e)


@docs.command("replace")
@click.argument("doc_id")
@click.option("--find", required=True, help="Text to find")
@click.option("--replace", "replace_text", required=True, help="Replacement text")
def docs_replace(doc_id: str, find: str, replace_text: str):
    """Replace text in a Google Doc."""
    try:
        docs_service = get_docs_service()

        requests = [{
            "replaceAllText": {
                "containsText": {"text": find, "matchCase": True},
                "replaceText": replace_text,
            }
        }]

        result = docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()

        output_json({"status": "ok", "result": result})
    except Exception as e:
        handle_error(e)


@docs.command("suggest-edit")
@click.argument("doc_id")
@click.option("--find", required=True, help="Exact text to find and replace in the document.")
@click.option("--replace", "replace_text", required=True, help="Suggested replacement text.")
@click.option("--tab", default=None, help="Tab ID for multi-tab docs (e.g. t.0).")
@click.option("--occurrence", default=1, type=int, help="Which occurrence to target (1=first, 2=second, etc).")
@click.option("--after", default=None, help="Unique anchor text to position cursor before searching. Finds target text nearest to this anchor.")
def docs_suggest_edit(doc_id: str, find: str, replace_text: str, tab: str | None, occurrence: int, after: str | None):
    """Suggest an edit in a Google Doc via browser automation.

    Switches to Suggesting mode, finds the text, replaces it (creating a
    suggestion), then switches back. Requires the Playwriter Chrome extension.
    """
    try:
        result = _create_suggested_edit_via_browser(doc_id, find, replace_text, tab_id=tab, occurrence=occurrence, after=after)
        output_json(result)
    except Exception as e:
        output_json({"error": str(e), "type": type(e).__name__})
        sys.exit(1)


@docs.command("get")
@click.argument("document_id")
@click.option("--include-tabs/--no-include-tabs", default=True,
              help="Include content from all tabs (default: true)")
def docs_get(document_id: str, include_tabs: bool):
    """Get full Google Doc JSON (structure, styles, content)."""
    try:
        docs_service = get_docs_service()
        doc = docs_service.documents().get(
            documentId=document_id,
            includeTabsContent=include_tabs,
        ).execute()
        output_json(doc)
    except Exception as e:
        handle_error(e)


@docs.command("tabs")
@click.argument("document_id")
def docs_tabs(document_id: str):
    """List all tabs in a Google Doc."""
    try:
        docs_service = get_docs_service()
        doc = docs_service.documents().get(
            documentId=document_id,
            includeTabsContent=True,
        ).execute()
        
        def extract_tabs(tabs, depth=0):
            """Recursively extract tab info including child tabs."""
            result = []
            for tab in tabs:
                props = tab.get("tabProperties", {})
                tab_info = {
                    "tabId": props.get("tabId"),
                    "title": props.get("title"),
                    "index": props.get("index"),
                    "depth": depth,
                }
                result.append(tab_info)
                # Handle nested child tabs
                child_tabs = tab.get("childTabs", [])
                if child_tabs:
                    result.extend(extract_tabs(child_tabs, depth + 1))
            return result
        
        tabs = extract_tabs(doc.get("tabs", []))
        
        output_json({
            "documentId": document_id,
            "title": doc.get("title"),
            "tabs": tabs,
        })
    except Exception as e:
        handle_error(e)


@docs.command("extract-tables")
@click.argument("document_id")
@click.option("--tab", "tab_id", default="", help="Target a specific tab by ID (e.g., t.abc123)")
def docs_extract_tables(document_id: str, tab_id: str):
    """Extract all tables from a Google Doc tab as structured JSON.

    Returns an array of tables, each with:
    - heading: nearest preceding heading text
    - rows: array of arrays of cell text values (first row is the header)

    Example:
        uv run gdrive-cli.py docs extract-tables <doc-id> --tab t.abc123
    """
    try:
        docs_service = get_docs_service()
        doc = docs_service.documents().get(
            documentId=document_id,
            includeTabsContent=True,
        ).execute()

        if tab_id and not _find_tab_by_id(doc.get("tabs", []), tab_id):
            all_tabs = _flatten_all_tabs(doc.get("tabs", []))
            output_json({
                "error": f"Tab '{tab_id}' not found",
                "available_tabs": [
                    {"tabId": t.get("tabProperties", {}).get("tabId"),
                     "title": t.get("tabProperties", {}).get("title")}
                    for t in all_tabs
                ],
            })
            sys.exit(1)

        tab_body = _get_tab_body(doc, tab_id)
        content = tab_body.get("content", [])

        tables = []
        last_heading = ""

        for element in content:
            if "paragraph" in element:
                para = element["paragraph"]
                named_style = para.get("paragraphStyle", {}).get("namedStyleType", "")
                if named_style.startswith("HEADING_"):
                    heading_text = ""
                    for elem in para.get("elements", []):
                        if "textRun" in elem:
                            heading_text += elem["textRun"].get("content", "").strip()
                    if heading_text:
                        last_heading = heading_text

            elif "table" in element:
                table_elem = element["table"]
                rows = []
                for row in table_elem.get("tableRows", []):
                    row_cells = []
                    for cell in row.get("tableCells", []):
                        cell_text = ""
                        for cell_content in cell.get("content", []):
                            if "paragraph" in cell_content:
                                for elem in cell_content["paragraph"].get("elements", []):
                                    if "textRun" in elem:
                                        cell_text += elem["textRun"].get("content", "").strip()
                        row_cells.append(cell_text)
                    rows.append(row_cells)

                tables.append({
                    "index": len(tables),
                    "heading": last_heading,
                    "rows": rows,
                })

        output_json({
            "documentId": document_id,
            "tabId": tab_id or "(default)",
            "tableCount": len(tables),
            "tables": tables,
        })
    except Exception as e:
        handle_error(e)


@docs.command("batch-update")
@click.argument("document_id")
def docs_batch_update(document_id: str):
    """Apply raw Docs batchUpdate requests. Reads JSON from stdin."""
    try:
        docs_service = get_docs_service()

        # Read request body from stdin
        body_json = sys.stdin.read()
        body = json.loads(body_json)

        result = docs_service.documents().batchUpdate(
            documentId=document_id,
            body=body,
        ).execute()

        output_json({"status": "ok", "result": result})
    except Exception as e:
        handle_error(e)


@docs.command("insert-markdown")
@click.argument("document_id")
@click.option("--at-index", type=int, default=None, help="Insert at a specific document index (use 'docs get' to find indices)")
@click.option("--tab", "tab_id", default="", help="Target a specific tab by ID (e.g., t.abc123)")
@click.option("--font", "font_family", default=None, help="Base font family for all text (e.g., 'Inter', 'Roboto')")
def docs_insert_markdown(document_id: str, at_index: int | None, tab_id: str, font_family: str | None):
    """Insert markdown content with rich formatting into a Google Doc.

    Reads markdown from stdin and converts to Google Docs formatting:
    - # Heading → HEADING_1, ## → HEADING_2, etc.
    - **bold** → bold text
    - *italic* → italic text
    - [text](url) → clickable links
    - Bare URLs → auto-linkified
    - `code` → monospace with gray background
    - ```code blocks``` → monospace block
    - - bullets → bullet list
    - 1. numbered → numbered list
    - | tables | → Google Docs tables

    Without --at-index, appends to the end of the document.
    Use --at-index 1 to insert at the beginning.

    Example:
        echo "# Title\\n\\n**Bold** with [link](https://example.com)" | \\
          uv run gdrive-cli.py docs insert-markdown <doc-id>

        echo "## New Section" | \\
          uv run gdrive-cli.py docs insert-markdown <doc-id> --at-index 342
    """
    try:
        from scripts.markdown_converter import MarkdownToDocsConverter

        docs_service = get_docs_service()

        # Read markdown from stdin
        markdown_content = sys.stdin.read()
        if not markdown_content.strip():
            output_json({"error": "No markdown content provided on stdin"})
            sys.exit(1)

        # Always fetch with includeTabsContent to support all tabs
        doc = docs_service.documents().get(
            documentId=document_id,
            includeTabsContent=True,
        ).execute()

        # Validate tab_id if provided
        if tab_id and not _find_tab_by_id(doc.get("tabs", []), tab_id):
            all_tabs = _flatten_all_tabs(doc.get("tabs", []))
            output_json({
                "error": f"Tab '{tab_id}' not found",
                "available_tabs": [
                    {"tabId": t.get("tabProperties", {}).get("tabId"), "title": t.get("tabProperties", {}).get("title")}
                    for t in all_tabs
                ],
            })
            sys.exit(1)

        tab_body = _get_tab_body(doc, tab_id)

        content = tab_body.get("content") or []
        if at_index is not None:
            base_index = at_index
        elif not content:
            base_index = 1
        else:
            base_index = content[-1].get("endIndex", 2) - 1

        # Convert markdown to Docs API requests
        converter = MarkdownToDocsConverter(base_index=base_index, base_font_family=font_family)
        request_body = converter.convert(markdown_content)

        if not request_body.get("requests"):
            output_json({"status": "ok", "message": "No content to insert"})
            return

        _LOCATION_KEYS = {
            "location", "range", "endOfSegmentLocation",
            "startLocation", "endLocation", "tableStartLocation",
        }

        def inject_tab_id(requests: list[dict], tid: str) -> list[dict]:
            """Recursively inject tabId into all location/range objects in requests."""
            if not tid:
                return requests

            def _inject(obj):
                if isinstance(obj, builtins.dict):
                    for key, val in obj.items():
                        if key in _LOCATION_KEYS and isinstance(val, builtins.dict):
                            val["tabId"] = tid
                        _inject(val)
                elif isinstance(obj, builtins.list):
                    for item in obj:
                        _inject(item)

            for req in requests:
                _inject(req)
            return requests

        def refetch_tab_body():
            """Re-fetch the document and return the correct body content list."""
            refreshed = docs_service.documents().get(
                documentId=document_id,
                includeTabsContent=True,
            ).execute()
            return _get_tab_body(refreshed, tab_id).get("content", [])

        total_requests = 0

        # Check if we need multi-pass table handling
        if converter.needs_formatting_pass():
            # Multi-pass approach for documents with tables

            # Phase 1a: Insert text + apply base font/size
            phase1_requests = request_body["requests"]
            inject_tab_id(phase1_requests, tab_id)
            docs_service.documents().batchUpdate(
                documentId=document_id,
                body={"requests": phase1_requests},
            ).execute()
            total_requests += len(phase1_requests)

            # Phase 1b: Process each table separately by finding markers in actual document
            for table_spec in converter.tables:
                doc_body = refetch_tab_body()

                # Find the marker in the document
                marker_start = None
                marker_end = None
                for elem in doc_body:
                    if "paragraph" in elem:
                        for e in elem["paragraph"].get("elements", []):
                            if "textRun" in e:
                                text = e["textRun"].get("content", "")
                                if "__TABLE_" in text and "__\n" in text:
                                    marker_start = e.get("startIndex")
                                    marker_end = e.get("endIndex")
                                    break
                        if marker_start is not None:
                            break

                if marker_start is None:
                    continue

                # Delete marker and insert table
                table_requests = [
                    {
                        "deleteContentRange": {
                            "range": {
                                "startIndex": marker_start,
                                "endIndex": marker_end,
                            }
                        }
                    },
                    {
                        "insertTable": {
                            "rows": table_spec.rows,
                            "columns": table_spec.cols,
                            "location": {"index": marker_start},
                        }
                    },
                ]

                # Add cell content requests
                cell_requests = converter._generate_table_cell_requests(table_spec, marker_start)
                table_requests.extend(cell_requests)

                inject_tab_id(table_requests, tab_id)
                docs_service.documents().batchUpdate(
                    documentId=document_id,
                    body={"requests": table_requests},
                ).execute()
                total_requests += len(table_requests)

            # Phase 2: Apply formatting by searching the document
            doc_body = refetch_tab_body()
            formatting_body = converter.generate_formatting_requests(doc_body)

            if formatting_body.get("requests"):
                inject_tab_id(formatting_body["requests"], tab_id)
                docs_service.documents().batchUpdate(
                    documentId=document_id,
                    body=formatting_body,
                ).execute()
                total_requests += len(formatting_body.get("requests", []))
        else:
            # Simple case: no tables, single batch
            inject_tab_id(request_body["requests"], tab_id)
            docs_service.documents().batchUpdate(
                documentId=document_id,
                body=request_body,
            ).execute()
            total_requests = len(request_body.get("requests", []))

        if at_index is not None:
            inserted_at = f"index {at_index}"
        elif base_index == 1:
            inserted_at = "start"
        else:
            inserted_at = "end"

        output_json({
            "status": "ok",
            "documentId": document_id,
            "insertedAt": inserted_at,
            "tabId": tab_id or None,
            "requestCount": total_requests,
        })
    except Exception as e:
        handle_error(e)


@docs.command("insert-image")
@click.argument("doc_id")
@click.argument("local_path", type=click.Path(exists=True))
@click.option("--tab", "tab_id", default=None, help="Tab ID to insert into (for multi-tab docs)")
@click.option("--keep-drive-file", is_flag=True, help="Don't delete the temp Drive file after insertion")
def docs_insert_image(doc_id: str, local_path: str, tab_id: str | None, keep_drive_file: bool):
    """Insert a local image into a Google Doc (no public URL needed).

    Uses an Apps Script web app to insert the image as a blob.
    Requires one-time setup: deploy image-inserter-webapp.js and run
    'config set-image-webapp <URL>'.
    """
    try:
        result = _insert_image_via_webapp(doc_id, local_path, target="docs", tab_id=tab_id, cleanup=not keep_drive_file)
        output_json(result)
    except Exception as e:
        handle_error(e)


# =============================================================================
# Sheets commands
# =============================================================================

@cli.group()
def sheets():
    """Google Sheets operations."""
    pass


@sheets.command("get")
@click.argument("spreadsheet_id")
@click.option("--include-grid-data/--no-include-grid-data", default=False,
              help="Include cell values and formatting (can be large)")
def sheets_get(spreadsheet_id: str, include_grid_data: bool):
    """Get spreadsheet structure and metadata."""
    try:
        sheets_service = get_sheets_service()
        
        result = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            includeGridData=include_grid_data,
        ).execute()
        
        output_json(result)
    except Exception as e:
        handle_error(e)


@sheets.command("tabs")
@click.argument("spreadsheet_id")
def sheets_tabs(spreadsheet_id: str):
    """List all tabs/sheets in a spreadsheet."""
    try:
        sheets_service = get_sheets_service()
        meta = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields=(
                "sheets("
                "properties(sheetId,title,index,hidden,"
                "gridProperties(rowCount,columnCount))"
                ")"
            ),
        ).execute()

        tabs = []
        for s in meta.get("sheets", []):
            p = s.get("properties", {})
            grid = p.get("gridProperties", {}) or {}
            tabs.append({
                "sheetId": p.get("sheetId"),
                "title": p.get("title"),
                "index": p.get("index"),
                "hidden": p.get("hidden", False),
                "rowCount": grid.get("rowCount"),
                "columnCount": grid.get("columnCount"),
            })

        output_json({
            "spreadsheetId": spreadsheet_id,
            "tabs": tabs,
        })
    except Exception as e:
        handle_error(e)


@sheets.command("named-ranges")
@click.argument("spreadsheet_id")
def sheets_named_ranges(spreadsheet_id: str):
    """List named ranges in a spreadsheet."""
    try:
        sheets_service = get_sheets_service()
        meta = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="namedRanges(namedRangeId,name,range)",
        ).execute()

        output_json({
            "spreadsheetId": spreadsheet_id,
            "namedRanges": meta.get("namedRanges", []),
        })
    except Exception as e:
        handle_error(e)


@sheets.command("read")
@click.argument("spreadsheet_id")
@click.option("--range", "range_", default="", help="Range to read (e.g., Sheet1!A1:D10)")
@click.option("--sheet", default="", help="Sheet/tab name (alternative to range)")
@click.option("--all-sheets", is_flag=True, help="Read all visible tabs in the spreadsheet")
@click.option("--named-range", default="", help="Read a named range")
def sheets_read(spreadsheet_id: str, range_: str, sheet: str, all_sheets: bool, named_range: str):
    """Read values from a spreadsheet."""
    try:
        sheets_service = get_sheets_service()
        range_ = _sanitize_range(range_)

        # Validate mutually exclusive options
        if all_sheets and (range_ or sheet or named_range):
            raise click.UsageError("--all-sheets cannot be combined with --range, --sheet, or --named-range")
        if named_range and (range_ or sheet):
            raise click.UsageError("--named-range cannot be combined with --range or --sheet")
        
        # Case 1: Read all sheets
        if all_sheets:
            meta = sheets_service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields="sheets(properties(sheetId,title,index,hidden))",
            ).execute()
            
            tabs = [
                s.get("properties", {})
                for s in meta.get("sheets", [])
                if not s.get("properties", {}).get("hidden", False)
            ]
            
            ranges_to_fetch = [f"'{t.get('title')}'!A:ZZ" for t in tabs]
            
            batch_result = sheets_service.spreadsheets().values().batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=ranges_to_fetch,
            ).execute()
            
            by_title = {}
            for value_range in batch_result.get("valueRanges", []):
                full_range = value_range.get("range", "")
                sheet_title = full_range.split("!", 1)[0].strip("'")
                by_title[sheet_title] = {
                    "range": full_range,
                    "values": value_range.get("values", []),
                }
            
            sheets_output = []
            for t in tabs:
                title = t.get("title")
                sheets_output.append({
                    "sheetId": t.get("sheetId"),
                    "title": title,
                    "index": t.get("index"),
                    "data": by_title.get(title, {"range": f"'{title}'!A:ZZ", "values": []}),
                })
            
            output_json({
                "spreadsheetId": spreadsheet_id,
                "sheets": sheets_output,
            })
            return
        
        # Case 2: Named range
        if named_range:
            result = sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=named_range,
            ).execute()
            output_json({
                "namedRange": named_range,
                "range": result.get("range"),
                "values": result.get("values", []),
            })
            return
        
        # Case 3: Single range (original behavior)
        if not range_ and sheet:
            range_ = sheet
        elif not range_:
            range_ = "A:ZZ"  # Default to all columns
        
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_,
        ).execute()
        
        output_json({
            "range": result.get("range"),
            "values": result.get("values", []),
        })
    except Exception as e:
        handle_error(e)


@sheets.command("write")
@click.argument("spreadsheet_id")
@click.option("--range", "range_", required=True, help="Range to write (e.g., Sheet1!A1)")
@click.option("--values", required=True, help="JSON array of rows")
def sheets_write(spreadsheet_id: str, range_: str, values: str):
    """Write values to a spreadsheet."""
    try:
        sheets_service = get_sheets_service()
        values_data = json.loads(values)
        range_ = _sanitize_range(range_)

        result = sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_,
            valueInputOption="USER_ENTERED",
            body={"values": values_data},
        ).execute()
        
        output_json({"status": "ok", "result": result})
    except Exception as e:
        handle_error(e)


@sheets.command("append")
@click.argument("spreadsheet_id")
@click.option("--range", "range_", required=True, help="Range/sheet to append to")
@click.option("--values", required=True, help="JSON array of rows")
def sheets_append(spreadsheet_id: str, range_: str, values: str):
    """Append rows to a spreadsheet."""
    try:
        sheets_service = get_sheets_service()
        range_ = _sanitize_range(range_)
        values_data = json.loads(values)
        
        result = sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values_data},
        ).execute()
        
        output_json({"status": "ok", "result": result})
    except Exception as e:
        handle_error(e)


@sheets.command("clear")
@click.argument("spreadsheet_id")
@click.option("--range", "range_", required=True, help="Range to clear (e.g., Sheet1!A2:Z)")
def sheets_clear(spreadsheet_id: str, range_: str):
    """Clear values from a range (keeps formatting)."""
    try:
        sheets_service = get_sheets_service()
        range_ = _sanitize_range(range_)
        
        result = sheets_service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=range_,
            body={},
        ).execute()
        
        output_json({
            "status": "ok",
            "clearedRange": result.get("clearedRange"),
        })
    except Exception as e:
        handle_error(e)


@sheets.command("batch-update")
@click.argument("spreadsheet_id")
def sheets_batch_update(spreadsheet_id: str):
    """Apply raw batchUpdate requests. Reads JSON from stdin."""
    try:
        sheets_service = get_sheets_service()
        
        # Read request body from stdin
        body_json = sys.stdin.read()
        body = json.loads(body_json)
        
        result = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body,
        ).execute()
        
        output_json({"status": "ok", "result": result})
    except Exception as e:
        handle_error(e)


def _extract_slide_text(page: dict) -> dict:
    """Extract text content from a slide page.

    Returns dict with objectId, title placeholder text, and body text from shapes.
    """
    result = {
        "objectId": page.get("objectId"),
        "texts": [],
    }

    for element in page.get("pageElements", []):
        shape = element.get("shape")
        if not shape:
            continue

        text_content = shape.get("text")
        if not text_content:
            continue

        # Extract text from textElements
        text_parts = []
        for text_element in text_content.get("textElements", []):
            text_run = text_element.get("textRun")
            if text_run:
                content = text_run.get("content", "")
                if content.strip():
                    text_parts.append(content)

        if text_parts:
            placeholder = shape.get("placeholder", {})
            text_info = {
                "objectId": element.get("objectId"),
                "shapeType": shape.get("shapeType"),
                "text": "".join(text_parts),
            }
            if placeholder:
                text_info["placeholderType"] = placeholder.get("type")
            result["texts"].append(text_info)

    return result


# =============================================================================
# Slides commands
# =============================================================================

@cli.group()
def slides():
    """Google Slides operations."""
    pass


@slides.command("get")
@click.argument("presentation_id")
def slides_get(presentation_id: str):
    """Get full presentation JSON (structure, slides, elements)."""
    try:
        slides_service = get_slides_service()
        presentation = slides_service.presentations().get(
            presentationId=presentation_id,
        ).execute()
        output_json(presentation)
    except Exception as e:
        handle_error(e)


@slides.command("list")
@click.argument("presentation_id")
def slides_list(presentation_id: str):
    """List all slides in a presentation with basic info."""
    try:
        slides_service = get_slides_service()
        presentation = slides_service.presentations().get(
            presentationId=presentation_id,
            fields="presentationId,title,slides(objectId,slideProperties)"
        ).execute()

        slides_data = []
        for idx, slide in enumerate(presentation.get("slides", [])):
            slide_info = {
                "index": idx,
                "objectId": slide.get("objectId"),
                "layoutObjectId": slide.get("slideProperties", {}).get("layoutObjectId"),
                "masterObjectId": slide.get("slideProperties", {}).get("masterObjectId"),
            }
            slides_data.append(slide_info)

        output_json({
            "presentationId": presentation.get("presentationId"),
            "title": presentation.get("title"),
            "slideCount": len(slides_data),
            "slides": slides_data,
        })
    except Exception as e:
        handle_error(e)


@slides.command("page")
@click.argument("presentation_id")
@click.argument("page_id")
def slides_page(presentation_id: str, page_id: str):
    """Get a specific page/slide by its object ID."""
    try:
        slides_service = get_slides_service()
        page = slides_service.presentations().pages().get(
            presentationId=presentation_id,
            pageObjectId=page_id,
        ).execute()
        output_json(page)
    except Exception as e:
        handle_error(e)


@slides.command("read")
@click.argument("presentation_id")
@click.option("--slide", "slide_id", default="", help="Read specific slide by object ID")
@click.option("--all-slides", is_flag=True, help="Read text from all slides")
def slides_read(presentation_id: str, slide_id: str, all_slides: bool):
    """Read text content from presentation slides."""
    try:
        slides_service = get_slides_service()

        if slide_id:
            # Get specific slide
            page = slides_service.presentations().pages().get(
                presentationId=presentation_id,
                pageObjectId=slide_id,
            ).execute()

            slide_text = _extract_slide_text(page)
            output_json({
                "presentationId": presentation_id,
                "slide": slide_text,
            })
        else:
            # Get all slides (default) or when --all-slides specified
            presentation = slides_service.presentations().get(
                presentationId=presentation_id,
            ).execute()

            slides_content = []
            for idx, slide in enumerate(presentation.get("slides", [])):
                slide_text = _extract_slide_text(slide)
                slide_text["index"] = idx
                slides_content.append(slide_text)

            output_json({
                "presentationId": presentation_id,
                "title": presentation.get("title"),
                "slideCount": len(slides_content),
                "slides": slides_content,
            })
    except Exception as e:
        handle_error(e)


@slides.command("notes")
@click.argument("presentation_id")
@click.option("--slide", "slide_id", default="", help="Get notes for specific slide")
def slides_notes(presentation_id: str, slide_id: str):
    """Read speaker notes from slides."""
    try:
        slides_service = get_slides_service()

        # Get full presentation to access notes
        presentation = slides_service.presentations().get(
            presentationId=presentation_id,
        ).execute()

        def extract_notes_text(notes_page: dict) -> str:
            """Extract text from speaker notes shape."""
            if not notes_page:
                return ""

            speaker_notes_id = notes_page.get("notesProperties", {}).get("speakerNotesObjectId")
            if not speaker_notes_id:
                return ""

            for element in notes_page.get("pageElements", []):
                if element.get("objectId") == speaker_notes_id:
                    shape = element.get("shape", {})
                    text_content = shape.get("text", {})
                    text_parts = []
                    for text_element in text_content.get("textElements", []):
                        text_run = text_element.get("textRun")
                        if text_run:
                            text_parts.append(text_run.get("content", ""))
                    return "".join(text_parts)
            return ""

        if slide_id:
            # Find specific slide and its notes
            for idx, slide in enumerate(presentation.get("slides", [])):
                if slide.get("objectId") == slide_id:
                    notes_page = slide.get("slideProperties", {}).get("notesPage")
                    notes_text = extract_notes_text(notes_page)
                    output_json({
                        "presentationId": presentation_id,
                        "slideObjectId": slide_id,
                        "slideIndex": idx,
                        "notes": notes_text,
                    })
                    return

            # Slide not found
            output_json({
                "error": f"Slide '{slide_id}' not found",
                "availableSlides": [s.get("objectId") for s in presentation.get("slides", [])],
            })
        else:
            # Get notes for all slides
            notes_data = []
            for idx, slide in enumerate(presentation.get("slides", [])):
                notes_page = slide.get("slideProperties", {}).get("notesPage")
                notes_text = extract_notes_text(notes_page)
                notes_data.append({
                    "slideIndex": idx,
                    "slideObjectId": slide.get("objectId"),
                    "notes": notes_text,
                })

            output_json({
                "presentationId": presentation_id,
                "title": presentation.get("title"),
                "slides": notes_data,
            })
    except Exception as e:
        handle_error(e)


@slides.command("batch-update")
@click.argument("presentation_id")
def slides_batch_update(presentation_id: str):
    """Apply raw Slides batchUpdate requests. Reads JSON from stdin.

    Example:
        echo '{"requests": [...]}' | uv run gdrive-cli.py slides batch-update <id>

    See references/slides-api.md for request types and examples.
    """
    try:
        slides_service = get_slides_service()

        # Read request body from stdin
        body_json = sys.stdin.read()
        body = json.loads(body_json)

        result = slides_service.presentations().batchUpdate(
            presentationId=presentation_id,
            body=body,
        ).execute()

        output_json({"status": "ok", "result": result})
    except Exception as e:
        handle_error(e)


@slides.command("add-slide")
@click.argument("presentation_id")
@click.option("--layout", default="BLANK",
              type=click.Choice([
                  "BLANK", "CAPTION_ONLY", "TITLE", "TITLE_AND_BODY",
                  "TITLE_AND_TWO_COLUMNS", "TITLE_ONLY", "SECTION_HEADER",
                  "SECTION_TITLE_AND_DESCRIPTION", "ONE_COLUMN_TEXT",
                  "MAIN_POINT", "BIG_NUMBER"
              ]),
              help="Slide layout (default: BLANK)")
@click.option("--index", default=-1, type=int, help="Insert position (default: end)")
def slides_add_slide(presentation_id: str, layout: str, index: int):
    """Add a new slide to the presentation."""
    try:
        slides_service = get_slides_service()

        # Get current slide count if inserting at end
        if index < 0:
            presentation = slides_service.presentations().get(
                presentationId=presentation_id,
                fields="slides.objectId"
            ).execute()
            index = len(presentation.get("slides", []))

        requests = [{
            "createSlide": {
                "insertionIndex": index,
                "slideLayoutReference": {
                    "predefinedLayout": layout
                }
            }
        }]

        result = slides_service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": requests},
        ).execute()

        # Extract created slide info
        create_response = result.get("replies", [{}])[0].get("createSlide", {})

        output_json({
            "status": "ok",
            "slideObjectId": create_response.get("objectId"),
            "insertionIndex": index,
            "layout": layout,
        })
    except Exception as e:
        handle_error(e)


@slides.command("delete-slide")
@click.argument("presentation_id")
@click.argument("slide_id")
def slides_delete_slide(presentation_id: str, slide_id: str):
    """Delete a slide from the presentation."""
    try:
        slides_service = get_slides_service()

        requests = [{
            "deleteObject": {
                "objectId": slide_id
            }
        }]

        slides_service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": requests},
        ).execute()

        output_json({
            "status": "ok",
            "message": f"Deleted slide {slide_id}",
        })
    except Exception as e:
        handle_error(e)


@slides.command("duplicate-slide")
@click.argument("presentation_id")
@click.argument("slide_id")
def slides_duplicate_slide(presentation_id: str, slide_id: str):
    """Duplicate an existing slide."""
    try:
        slides_service = get_slides_service()

        requests = [{
            "duplicateObject": {
                "objectId": slide_id
            }
        }]

        result = slides_service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": requests},
        ).execute()

        # Extract duplicated slide info
        duplicate_response = result.get("replies", [{}])[0].get("duplicateObject", {})

        output_json({
            "status": "ok",
            "sourceSlideId": slide_id,
            "newSlideId": duplicate_response.get("objectId"),
        })
    except Exception as e:
        handle_error(e)


@slides.command("add-text")
@click.argument("presentation_id")
@click.argument("slide_id")
@click.argument("text")
@click.option("--x", default=100, type=float, help="X position in points (default: 100)")
@click.option("--y", default=100, type=float, help="Y position in points (default: 100)")
@click.option("--width", default=400, type=float, help="Width in points (default: 400)")
@click.option("--height", default=100, type=float, help="Height in points (default: 100)")
@click.option("--font-size", default=18, type=float, help="Font size in points (default: 18)")
def slides_add_text(presentation_id: str, slide_id: str, text: str,
                    x: float, y: float, width: float, height: float, font_size: float):
    """Add a text box with content to a slide."""
    try:
        import uuid
        slides_service = get_slides_service()

        # Generate unique object ID for the text box
        text_box_id = f"textbox_{uuid.uuid4().hex[:8]}"

        requests = [
            {
                "createShape": {
                    "objectId": text_box_id,
                    "shapeType": "TEXT_BOX",
                    "elementProperties": {
                        "pageObjectId": slide_id,
                        "size": {
                            "height": {"magnitude": height, "unit": "PT"},
                            "width": {"magnitude": width, "unit": "PT"}
                        },
                        "transform": {
                            "scaleX": 1,
                            "scaleY": 1,
                            "translateX": x,
                            "translateY": y,
                            "unit": "PT"
                        }
                    }
                }
            },
            {
                "insertText": {
                    "objectId": text_box_id,
                    "insertionIndex": 0,
                    "text": text
                }
            },
            {
                "updateTextStyle": {
                    "objectId": text_box_id,
                    "textRange": {"type": "ALL"},
                    "style": {
                        "fontSize": {"magnitude": font_size, "unit": "PT"}
                    },
                    "fields": "fontSize"
                }
            }
        ]

        slides_service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": requests},
        ).execute()

        output_json({
            "status": "ok",
            "textBoxId": text_box_id,
            "slideId": slide_id,
            "position": {"x": x, "y": y},
            "size": {"width": width, "height": height},
        })
    except Exception as e:
        handle_error(e)


@slides.command("replace")
@click.argument("presentation_id")
@click.option("--find", required=True, help="Text to find")
@click.option("--replace", "replace_text", required=True, help="Replacement text")
@click.option("--match-case/--no-match-case", default=True, help="Case-sensitive match (default: true)")
def slides_replace(presentation_id: str, find: str, replace_text: str, match_case: bool):
    """Replace all occurrences of text in the presentation."""
    try:
        slides_service = get_slides_service()

        requests = [{
            "replaceAllText": {
                "containsText": {
                    "text": find,
                    "matchCase": match_case
                },
                "replaceText": replace_text
            }
        }]

        result = slides_service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": requests},
        ).execute()

        # Extract replacement count
        replace_response = result.get("replies", [{}])[0].get("replaceAllText", {})

        output_json({
            "status": "ok",
            "occurrencesChanged": replace_response.get("occurrencesChanged", 0),
            "find": find,
            "replaceText": replace_text,
        })
    except Exception as e:
        handle_error(e)


@slides.command("export-pdf")
@click.argument("presentation_id")
@click.option("--dest", required=True, help="Destination path for PDF")
def slides_export_pdf(presentation_id: str, dest: str):
    """Export presentation as PDF for visual inspection.

    The exported PDF can be read by multimodal AI for visual analysis
    of slide layouts, formatting, and visual elements.
    """
    try:
        drive = get_drive_service()

        # Get file metadata
        file_meta = drive.files().get(
            fileId=presentation_id,
            fields="id,name,mimeType",
            supportsAllDrives=True,
        ).execute()

        dest_path = Path(dest)
        if dest_path.is_dir():
            base_name = Path(file_meta["name"]).stem
            dest_path = dest_path / f"{base_name}.pdf"
        elif not dest_path.suffix:
            dest_path = dest_path.with_suffix(".pdf")

        # Export as PDF
        content = drive.files().export(
            fileId=presentation_id,
            mimeType="application/pdf",
        ).execute()

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(content if isinstance(content, bytes) else content.encode())

        output_json({
            "status": "ok",
            "path": str(dest_path),
            "size": len(content),
            "presentationId": presentation_id,
            "name": file_meta.get("name"),
            "hint": "Use the Read tool to view this PDF for visual analysis of slide content and layout.",
        })
    except Exception as e:
        handle_error(e)


@slides.command("insert-image")
@click.argument("presentation_id")
@click.argument("local_path", type=click.Path(exists=True))
@click.option("--slide-index", default=0, type=int, help="Slide index to insert on (default: 0, first slide)")
@click.option("--keep-drive-file", is_flag=True, help="Don't delete the temp Drive file after insertion")
def slides_insert_image(presentation_id: str, local_path: str, slide_index: int, keep_drive_file: bool):
    """Insert a local image into a Google Slides presentation (no public URL needed).

    Uses an Apps Script web app to insert the image as a blob.
    Requires one-time setup: deploy image-inserter-webapp.js and run
    'config set-image-webapp <URL>'.
    """
    try:
        result = _insert_image_via_webapp(
            presentation_id, local_path, target="slides",
            slide_index=slide_index, cleanup=not keep_drive_file,
        )
        output_json(result)
    except Exception as e:
        handle_error(e)


# =============================================================================
# Trash command
# =============================================================================

@cli.command()
@click.argument("file_id")
def trash(file_id: str):
    """Move a file to trash."""
    try:
        drive = get_drive_service()
        
        result = drive.files().update(
            fileId=file_id,
            body={"trashed": True},
            supportsAllDrives=True,
        ).execute()
        
        output_json({
            "status": "ok",
            "message": f"File {file_id} moved to trash",
            "file": {"id": result.get("id"), "name": result.get("name")},
        })
    except Exception as e:
        handle_error(e)


# =============================================================================
# Copy command
# =============================================================================

@cli.command()
@click.argument("file_id")
@click.option("--name", default="", help="Name for the copy (default: 'Copy of <original>')")
@click.option("--parent", default="", help="Folder ID to place the copy in")
def copy(file_id: str, name: str, parent: str):
    """Copy a file in Google Drive."""
    try:
        drive = get_drive_service()
        
        body = {}
        if name:
            body["name"] = name
        if parent:
            body["parents"] = [parent]
        
        result = drive.files().copy(
            fileId=file_id,
            body=body if body else None,
            fields="id,name,webViewLink",
            supportsAllDrives=True,
        ).execute()
        
        output_json(result)
    except Exception as e:
        handle_error(e)


# =============================================================================
# Move command
# =============================================================================

@cli.command()
@click.argument("file_id")
@click.option("--to", "folder_id", required=True, help="Destination folder ID")
def move(file_id: str, folder_id: str):
    """Move a file to a different folder."""
    try:
        drive = get_drive_service()
        
        # Get current parents
        file_meta = drive.files().get(
            fileId=file_id,
            fields="id,name,parents",
            supportsAllDrives=True,
        ).execute()
        
        current_parents = ",".join(file_meta.get("parents", []))
        
        # Move file: remove old parents, add new parent
        updated = drive.files().update(
            fileId=file_id,
            addParents=folder_id,
            removeParents=current_parents,
            fields="id,name,parents,webViewLink",
            supportsAllDrives=True,
        ).execute()
        
        output_json({"status": "ok", "file": updated})
    except Exception as e:
        handle_error(e)


# =============================================================================
# Revisions commands
# =============================================================================

@cli.group()
def revisions():
    """File revisions and version history."""
    pass


@revisions.command("list")
@click.argument("file_id")
def revisions_list(file_id: str):
    """List revisions of a file."""
    try:
        drive = get_drive_service()
        result = drive.revisions().list(
            fileId=file_id,
            fields=(
                "revisions("
                "id,"
                "modifiedTime,"
                "keepForever,"
                "lastModifyingUser(displayName,emailAddress),"
                "originalFilename,"
                "md5Checksum,"
                "size"
                ")"
            ),
        ).execute()

        output_json({
            "fileId": file_id,
            "revisions": result.get("revisions", []),
        })
    except Exception as e:
        handle_error(e)


@revisions.command("get")
@click.argument("file_id")
@click.argument("revision_id")
def revisions_get(file_id: str, revision_id: str):
    """Get metadata for a specific revision."""
    try:
        drive = get_drive_service()
        result = drive.revisions().get(
            fileId=file_id,
            revisionId=revision_id,
            fields="*",
        ).execute()

        output_json(result)
    except Exception as e:
        handle_error(e)


# =============================================================================
# Share commands
# =============================================================================

@cli.group()
def share():
    """Sharing and permissions."""
    pass


@share.command("list")
@click.argument("file_id")
def share_list(file_id: str):
    """List permissions on a file."""
    try:
        drive = get_drive_service()
        
        result = drive.permissions().list(
            fileId=file_id,
            fields="permissions(id,type,role,emailAddress,displayName)",
            supportsAllDrives=True,
        ).execute()
        
        output_json({"permissions": result.get("permissions", [])})
    except Exception as e:
        handle_error(e)


@share.command("add")
@click.argument("file_id")
@click.option("--email", default="", help="Email address for user/group sharing")
@click.option("--type", "perm_type", default="user", 
              type=click.Choice(["user", "group", "domain", "anyone"]))
@click.option("--role", default="reader",
              type=click.Choice(["owner", "organizer", "fileOrganizer", "writer", "commenter", "reader"]))
@click.option("--domain", default="", help="Domain for domain-wide sharing")
def share_add(file_id: str, email: str, perm_type: str, role: str, domain: str):
    """Add permission to a file."""
    try:
        drive = get_drive_service()
        
        permission = {"type": perm_type, "role": role}
        if email:
            permission["emailAddress"] = email
        if domain:
            permission["domain"] = domain
        
        result = drive.permissions().create(
            fileId=file_id,
            body=permission,
            supportsAllDrives=True,
            sendNotificationEmail=False,
        ).execute()
        
        output_json({"status": "ok", "permission": result})
    except Exception as e:
        handle_error(e)


@share.command("remove")
@click.argument("file_id")
@click.argument("permission_id")
def share_remove(file_id: str, permission_id: str):
    """Remove a permission from a file."""
    try:
        drive = get_drive_service()
        
        drive.permissions().delete(
            fileId=file_id,
            permissionId=permission_id,
            supportsAllDrives=True,
        ).execute()
        
        output_json({"status": "ok", "message": f"Removed permission {permission_id}"})
    except Exception as e:
        handle_error(e)


# =============================================================================
# Comments commands
# =============================================================================

@cli.group()
def comments():
    """Comments on files."""
    pass


@comments.command("list")
@click.argument("file_id")
def comments_list(file_id: str):
    """List comments on a file."""
    try:
        drive = get_drive_service()
        
        result = drive.comments().list(
            fileId=file_id,
            fields="comments(id,content,author,createdTime,resolved,replies,quotedFileContent,anchor)",
        ).execute()
        
        output_json({"comments": result.get("comments", [])})
    except Exception as e:
        handle_error(e)


@comments.command("add")
@click.argument("file_id")
@click.argument("content")
@click.option("--quote", default=None, help="Exact text from the document to anchor the comment to.")
@click.option("--tab", default=None, help="Tab ID for multi-tab docs (e.g. t.0).")
@click.option("--occurrence", default=1, type=int, help="Which occurrence to target (1=first, 2=second, etc).")
@click.option("--after", default=None, help="Unique anchor text to position cursor before searching. Finds target text nearest to this anchor.")
def comments_add(file_id: str, content: str, quote: str | None, tab: str | None, occurrence: int, after: str | None):
    """Add a comment to a file. Use --quote to anchor it to specific text in Google Docs."""
    try:
        if quote:
            # Try browser automation for inline-anchored comments
            try:
                result = _create_inline_comment_via_browser(file_id, content, quote, tab_id=tab, occurrence=occurrence, after=after)
                output_json(result)
                return
            except Exception as browser_err:
                click.echo(
                    f"Browser automation unavailable ({browser_err}), "
                    "falling back to Drive API (comment will appear in sidebar only).",
                    err=True,
                )

        # Drive API path: no --quote, or browser automation fallback
        drive = get_drive_service()
        body = {"content": content}
        if quote:
            body["quotedFileContent"] = {"mimeType": "text/plain", "value": quote}

        result = drive.comments().create(
            fileId=file_id,
            body=body,
            fields="id,content,author,createdTime,quotedFileContent,anchor",
        ).execute()

        output_json({"status": "ok", "comment": result})
    except Exception as e:
        handle_error(e)


@comments.command("delete")
@click.argument("file_id")
@click.argument("comment_id")
def comments_delete(file_id: str, comment_id: str):
    """Delete a comment from a file."""
    try:
        drive = get_drive_service()
        drive.comments().delete(fileId=file_id, commentId=comment_id).execute()
        output_json({"status": "ok", "deleted": comment_id})
    except Exception as e:
        handle_error(e)


@comments.command("reply")
@click.argument("file_id")
@click.argument("comment_id")
@click.argument("content")
def comments_reply(file_id: str, comment_id: str, content: str):
    """Reply to a comment."""
    try:
        drive = get_drive_service()
        
        result = drive.replies().create(
            fileId=file_id,
            commentId=comment_id,
            body={"content": content},
            fields="id,content,author,createdTime",
        ).execute()
        
        output_json({"status": "ok", "reply": result})
    except Exception as e:
        handle_error(e)


# =============================================================================
# Config commands
# =============================================================================

@cli.group()
def config():
    """Configuration commands."""
    pass


@config.command("set-image-webapp")
@click.argument("url")
def config_set_image_webapp(url: str):
    """Set the image inserter web app URL (one-time setup)."""
    IMAGE_WEBAPP_URL_PATH.parent.mkdir(parents=True, exist_ok=True)
    IMAGE_WEBAPP_URL_PATH.write_text(url.strip())
    output_json({
        "status": "ok",
        "message": "Image webapp URL saved",
        "path": str(IMAGE_WEBAPP_URL_PATH),
    })


if __name__ == "__main__":
    cli()

