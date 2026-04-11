#!/usr/bin/env python3
"""Verify the fix produces real extraction results with content that SHOULD yield data."""
import json
import os
import sys
from pathlib import Path

auth_file = Path.home() / ".anchor" / "auth.json"
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = json.loads(auth_file.read_text())["oauth_token"]

sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
import sidebar

# A realistic planning conversation with decisions + code blocks (the previously-failing case)
conversation = """USER: For authentication, let's use JWT. The token should include company_id for multi-tenant routing. Here's the structure:
```json
{
  "sub": "user123",
  "company_id": "acme"
}
```

ASSISTANT: Good choice. I'll use HS256 for signing since we're at small scale.

USER: Also — auth must never call billing directly. Use events only.

ASSISTANT: Agreed. I'll emit an AuthEvent to the event bus on successful login.

USER: And Google refresh tokens — those MUST be encrypted at rest. Never plaintext.
"""

prompt = f"Recent conversation:\n{conversation}\n\nAlready captured:\n[]"
print(f"Prompt length: {len(prompt)} chars")
print(f"Contains triple backticks: {'```' in prompt}")

print("\n--- Calling call_claude ---")
raw = sidebar.call_claude(prompt, sidebar.EXTRACTION_SYSTEM)
print(f"\nRaw result:\n{raw}")

if raw:
    try:
        parsed = json.loads(raw)
        print(f"\n--- Parsed {len(parsed)} items ---")
        for i, item in enumerate(parsed, 1):
            print(f"{i}. [{item.get('type')}] {item.get('text')}")
    except json.JSONDecodeError as e:
        print(f"\nJSON parse failed: {e}")
else:
    print("\nNo result")
