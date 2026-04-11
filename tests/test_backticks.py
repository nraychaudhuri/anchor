#!/usr/bin/env python3
"""Isolate the backticks failure."""
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

SYSTEM = "Reply with just OK."

tests = [
    ("single backtick", "USER: run `ls -la`\n\nASSISTANT: ok"),
    ("triple backticks bash", "USER: run\n```bash\nls -la\n```\n\nASSISTANT: ok"),
    ("triple backticks no lang", "USER: run\n```\nls -la\n```\n\nASSISTANT: ok"),
    ("escaped backticks", "USER: run \\`ls -la\\`\n\nASSISTANT: ok"),
]

for name, prompt in tests:
    print(f"\n--- {name} (len={len(prompt)}) ---")
    result = sidebar.call_claude(prompt, SYSTEM)
    print(f"Result: {result!r}")
