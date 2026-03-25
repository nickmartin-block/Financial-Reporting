#!/usr/bin/env python3
"""Lightweight comment refresh — reads Comments sheet + Directory and generates JS data files."""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COMMENTS_JSON = "/tmp/dashboard_comments.json"
DIRECTORY_JSON = "/tmp/dashboard_directory.json"
COMMENTS_OUT = os.path.join(SCRIPT_DIR, "comments_data.js")
DIRECTORY_OUT = os.path.join(SCRIPT_DIR, "directory_data.js")

def main():
    comments = []
    if os.path.exists(COMMENTS_JSON):
        with open(COMMENTS_JSON) as f:
            data = json.load(f)
        raw = data.get("values", data) if isinstance(data, dict) else data
        if raw and len(raw) >= 2:
            for row in raw[1:]:
                if len(row) >= 4 and row[3]:
                    comments.append({
                        "timestamp": str(row[0]),
                        "page": str(row[1]),
                        "author": str(row[2]),
                        "comment": str(row[3])
                    })
    comments.reverse()

    js = f"// Comments data — auto-refreshed\nvar DASHBOARD_COMMENTS = {json.dumps(comments)};\n"
    with open(COMMENTS_OUT, "w") as f:
        f.write(js)
    print(f"✓ comments_data.js — {len(comments)} comments")

    # Directory
    directory = []
    if os.path.exists(DIRECTORY_JSON):
        with open(DIRECTORY_JSON) as f:
            data = json.load(f)
        raw = data.get("values", data) if isinstance(data, dict) else data
        if raw and len(raw) >= 2:
            for row in raw[1:]:
                if len(row) >= 2 and row[0] and row[1]:
                    directory.append({"name": str(row[0]), "alias": str(row[1])})

    djs = f"// Directory data — auto-refreshed\nvar DASHBOARD_DIRECTORY = {json.dumps(directory)};\n"
    with open(DIRECTORY_OUT, "w") as f:
        f.write(djs)
    print(f"✓ directory_data.js — {len(directory)} people")

if __name__ == "__main__":
    main()
