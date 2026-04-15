#!/usr/bin/env python3
"""Test reconcile.py's call_claude to verify it doesn't hang."""
import json
import os
import sys
import time
from pathlib import Path

auth_file = Path.home() / ".anchor" / "auth.json"
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = json.loads(auth_file.read_text())["oauth_token"]

# Import reconcile's call_claude
reconcile_dir = Path(__file__).parent.parent / "skills" / "seed" / "scripts"
sys.path.insert(0, str(reconcile_dir))
from reconcile import call_claude

# A prompt similar to what reconcile actually sends
SYSTEM = """You are merging extracted knowledge into a canonical spec.
Return ONLY valid JSON with the merged result. No explanation."""

PROMPT = """Existing spec:
{"module": "auth", "business_rules": ["All endpoints require JWT"], "non_negotiables": ["Auth never calls billing directly"]}

New extraction:
{"business_rules": [{"text": "JWT must include company_id"}], "non_negotiables": []}

Merge the new extraction into the existing spec. Return the updated spec JSON."""

print("Calling reconcile.call_claude (should return in <30s, not 300s)...")
start = time.time()
result = call_claude(PROMPT, SYSTEM)
elapsed = time.time() - start

print(f"Elapsed: {elapsed:.1f}s")
print(f"Result: {result!r}")

if elapsed > 60:
    print("\n✗ FAILED: took too long — SDK is likely spawning a full agent")
    sys.exit(1)
elif result and "company_id" in result:
    print("\n✓ PASSED: returned merged spec in reasonable time")
else:
    print(f"\n? UNCLEAR: returned in {elapsed:.1f}s but result may not be right")
