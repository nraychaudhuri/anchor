#!/usr/bin/env python3
"""Isolate whether the failure is size, content, or specific characters."""
import json
import os
import sys
from pathlib import Path

auth_file = Path.home() / ".anchor" / "auth.json"
token = json.loads(auth_file.read_text()).get("oauth_token", "")
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token

sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
import sidebar

SYSTEM = sidebar.EXTRACTION_SYSTEM

tests = [
    ("short", "USER: Use JWT\n\nASSISTANT: Good"),
    ("medium (benign 750 chars)", "USER: " + "Let's discuss the architecture. " * 20 + "\n\nASSISTANT: Agreed."),
    ("with backticks", "USER: Run this:\n```bash\nls -la\n```\n\nASSISTANT: Done"),
    ("with slash commands", "USER: /anchor:companion start\n\nASSISTANT: Started"),
    ("with angle brackets", "USER: <command-message>test</command-message>\n\nASSISTANT: ok"),
]

for name, prompt in tests:
    print(f"\n--- {name} (len={len(prompt)}) ---")
    result = sidebar.call_claude(prompt, SYSTEM)
    print(f"Result: {result!r}")
