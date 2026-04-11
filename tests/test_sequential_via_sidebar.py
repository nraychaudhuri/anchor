#!/usr/bin/env python3
"""Run 5 sequential calls via sidebar.call_claude to see if it breaks."""
import json
import os
import sys
from pathlib import Path

auth_file = Path.home() / ".anchor" / "auth.json"
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = json.loads(auth_file.read_text())["oauth_token"]

sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
import sidebar

for i in range(1, 6):
    prompt = f"Test call #{i}: say hello briefly"
    print(f"\n--- Call {i} ---")
    result = sidebar.call_claude(prompt, "Reply with just OK.")
    print(f"Result: {result!r}")
