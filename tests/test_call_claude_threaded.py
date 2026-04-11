#!/usr/bin/env python3
"""Test call_claude from a non-main thread (mimics sidebar behavior)."""
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

# Import sidebar's call_claude
sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
from sidebar import call_claude

result = {"value": None, "error": None}


def worker():
    try:
        result["value"] = call_claude(prompt="Say hello", system="Reply in 5 words.")
    except Exception as e:
        result["error"] = repr(e)


print("\n--- Running call_claude in a thread (like sidebar does) ---")
t = threading.Thread(target=worker)
t.start()
t.join(timeout=40)

if t.is_alive():
    print("HUNG: thread did not complete in 40s")
elif result["error"]:
    print(f"ERROR: {result['error']}")
else:
    print(f"SUCCESS: {result['value']!r}")
