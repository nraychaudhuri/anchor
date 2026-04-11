#!/usr/bin/env python3
"""Test the exact prompt that extract_incremental would generate."""
import json
import os
import sys
from pathlib import Path

# Load token
auth_file = Path.home() / ".anchor" / "auth.json"
token = json.loads(auth_file.read_text()).get("oauth_token", "")
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token

# Import sidebar
sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
import sidebar

# Build the exact prompt extract_incremental uses
projects_dir = Path.home() / ".claude" / "projects"
transcript = None
for proj in projects_dir.iterdir():
    for f in sorted(proj.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.stat().st_size > 2000:
            transcript = f
            break
    if transcript:
        break

print(f"Transcript: {transcript}")
messages = sidebar.read_last_messages(str(transcript), n=8)
print(f"Got {len(messages)} messages")
conversation = sidebar.format_messages(messages)
print(f"Conversation length: {len(conversation)} chars")
print(f"First 500 chars of conversation:\n{conversation[:500]}")
print(f"\nLast 500 chars:\n{conversation[-500:]}")

prompt = f"Recent conversation:\n{conversation}\n\nAlready captured:\n[]"
print(f"\nTotal prompt length: {len(prompt)} chars")

print("\n--- Calling call_claude with the real prompt ---")
result = sidebar.call_claude(prompt, sidebar.EXTRACTION_SYSTEM)
print(f"\nResult: {result!r}")
