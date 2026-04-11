#!/usr/bin/env python3
"""Test sidebar.call_claude() in isolation to debug the LLM failure."""
import json
import os
import shutil
import sys
from pathlib import Path

# Load token from saved file
auth_file = Path.home() / ".anchor" / "auth.json"
if not auth_file.exists():
    print("ERROR: no token at ~/.anchor/auth.json")
    sys.exit(1)

token = json.loads(auth_file.read_text()).get("oauth_token", "")
if not token:
    print("ERROR: empty token")
    sys.exit(1)

os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token
print(f"Token loaded: {token[:20]}... (len={len(token)})")
print(f"claude binary: {shutil.which('claude') or 'NOT FOUND'}")
print(f"Python: {sys.executable}")

# Import sidebar's call_claude
sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
from sidebar import call_claude

# Test 1: simple prompt
print("\n--- Test 1: simple prompt ---")
result = call_claude(
    prompt="Say hello",
    system="Reply in exactly 5 words.",
)
print(f"Result: {result!r}")

# Test 2: extraction-style prompt (what the real sidebar does)
print("\n--- Test 2: extraction prompt ---")
result = call_claude(
    prompt="USER: I think we should use JWT\n\nASSISTANT: Good idea, JWT works for us",
    system='Extract decisions. Return JSON array like [{"text": "..."}].',
)
print(f"Result: {result!r}")
