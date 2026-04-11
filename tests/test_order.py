#!/usr/bin/env python3
"""Does the order matter? Run the tests in different orders."""
import json
import os
import sys
from pathlib import Path

auth_file = Path.home() / ".anchor" / "auth.json"
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = json.loads(auth_file.read_text())["oauth_token"]

sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
import sidebar

SYSTEM = sidebar.EXTRACTION_SYSTEM

# Run backticks FIRST (without the medium test that caused a cleanup crash)
backticks_prompt = "USER: run this:\n```bash\nls -la\n```\n\nASSISTANT: Done"

print("=== RUN 1: backticks only, as first call ===")
result = sidebar.call_claude(backticks_prompt, SYSTEM)
print(f"Result: {result!r}")

print("\n=== RUN 2: backticks again, as second call ===")
result = sidebar.call_claude(backticks_prompt, SYSTEM)
print(f"Result: {result!r}")

print("\n=== RUN 3: backticks third time ===")
result = sidebar.call_claude(backticks_prompt, SYSTEM)
print(f"Result: {result!r}")
