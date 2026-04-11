#!/usr/bin/env python3
"""Test if the EXTRACTION_SYSTEM prompt is what breaks things."""
import json
import os
import sys
from pathlib import Path

auth_file = Path.home() / ".anchor" / "auth.json"
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = json.loads(auth_file.read_text())["oauth_token"]

sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
import sidebar

print(f"EXTRACTION_SYSTEM length: {len(sidebar.EXTRACTION_SYSTEM)}")
print(f"EXTRACTION_SYSTEM (first 200): {sidebar.EXTRACTION_SYSTEM[:200]!r}")

# Simple prompt, varied system prompts
tests = [
    ("short system", "Reply with OK."),
    ("EXTRACTION_SYSTEM", sidebar.EXTRACTION_SYSTEM),
]

for name, system in tests:
    print(f"\n--- {name} ---")
    result = sidebar.call_claude("USER: Use JWT\n\nASSISTANT: Good", system)
    print(f"Result: {result!r}")
