#!/usr/bin/env python3
"""Test extract_incremental — the actual function the sidebar calls on stop events."""
import json
import os
import shutil
import sys
import threading
from pathlib import Path

# Load token
auth_file = Path.home() / ".anchor" / "auth.json"
token = json.loads(auth_file.read_text()).get("oauth_token", "")
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token
print(f"Token: {token[:20]}... | claude: {shutil.which('claude')}")

# Import sidebar
sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
import sidebar

# Find a real transcript file to use
projects_dir = Path.home() / ".claude" / "projects"
transcript = None
for proj in projects_dir.iterdir():
    for f in sorted(proj.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.stat().st_size > 2000:
            transcript = f
            break
    if transcript:
        break

if not transcript:
    print("ERROR: no transcript file found")
    sys.exit(1)

print(f"Using transcript: {transcript}")

result = {"value": None, "error": None}


def worker():
    try:
        print("  calling extract_incremental...")
        result["value"] = sidebar.extract_incremental(str(transcript), ["finance-twin"])
        print(f"  returned: {result['value']!r}")
    except Exception as e:
        import traceback
        result["error"] = traceback.format_exc()


print("\n--- Running extract_incremental in a thread ---")
t = threading.Thread(target=worker)
t.start()
t.join(timeout=60)

if t.is_alive():
    print("HUNG: thread did not complete in 60s")
elif result["error"]:
    print(f"ERROR:\n{result['error']}")
else:
    print(f"SUCCESS: {result['value']!r}")
