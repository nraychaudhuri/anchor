#!/usr/bin/env python3
"""Test handle_exit_plan_mode — full plan-impact analysis flow.

Creates a self-contained temporary spec so the conflict-detection path
is actually exercised, then calls the real handle_exit_plan_mode.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

auth_file = Path.home() / ".anchor" / "auth.json"
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = json.loads(auth_file.read_text())["oauth_token"]

sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
import sidebar

# A plan that should trigger all three classifications:
#   - add: rate-limit middleware (not in spec)
#   - modify: refresh token encryption method (upgrade from what spec says)
#   - conflict: auth calling billing directly (violates non-negotiable)
PLAN = """# Plan: Add trial-enforcement middleware to auth service

## Context
Finance team wants to enforce trial limits at login time.

## Changes
1. Add new rate-limit middleware defaulting to 100 requests/minute per user.
2. Store Google refresh tokens using Fernet symmetric encryption at rest (upgrade from the current plaintext base64 encoding the spec mentions).
3. In the auth service, call the billing service's `/trial-status` HTTP endpoint directly on every login to check trial validity. This gives freshest state with no event-bus lag.

## Non-goals
- No change to JWT signing algorithm.
"""

# A spec that defines non-negotiables the plan should violate
AUTH_SPEC = {
    "module": "auth-and-security",
    "summary": "JWT, OAuth, MFA, rate limiting, MCP token generation. All API access requires authentication.",
    "business_rules": [
        "All API endpoints except /public require a valid JWT",
        "JWT must include company_id for multi-tenant routing",
        "Google refresh tokens must be base64-encoded and stored in the users table",
    ],
    "non_negotiables": [
        "Auth must never call billing directly — events only",
        "Google refresh tokens must never be stored in plaintext or logs",
    ],
    "tradeoffs": [],
    "conflicts": [],
    "lineage": [],
}

# Set up a temp workspace
tmp = Path(tempfile.mkdtemp(prefix="anchor-plan-test-"))
try:
    # Build the spec dir structure the sidebar expects
    spec_location = tmp / "product-spec"
    spec_dir = spec_location / "openspec" / "specs" / "auth-and-security"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.json").write_text(json.dumps(AUTH_SPEC, indent=2))

    # .companion/product.json → config.json → spec_location pointer
    companion_dir = tmp / ".companion"
    companion_dir.mkdir()
    config_path = companion_dir / "config.json"
    config_path.write_text(json.dumps({
        "product": "anchor-test",
        "spec_location": str(spec_location),
    }))
    (companion_dir / "product.json").write_text(json.dumps({"config": str(config_path)}))

    # Sanity: load_spec should now work
    loaded = sidebar.load_spec(str(tmp), "auth-and-security")
    print(f"Spec loaded: {loaded is not None}")
    assert loaded is not None, "Spec did not load — test setup is wrong"

    # Clear any leftover captures from previous runs in same process
    sidebar.captures.clear()

    event = {
        "event": "exit_plan_mode",
        "transcript_path": "",
        "session_id": "test-session",
        "cwd": str(tmp),
        "plan": PLAN,
        "loaded_modules": ["auth-and-security"],
    }

    print("\n--- Calling handle_exit_plan_mode ---")
    sidebar.handle_exit_plan_mode(event)

    print(f"\n--- Captures collected: {len(sidebar.captures)} ---")
    for i, c in enumerate(sidebar.captures, 1):
        cls = c.get("classification", "?")
        mod = c.get("module", "?")
        print(f"{i}. [{cls}] [{mod}] {c.get('text', '')}")

    # Verify at least one conflict was detected (the auth→billing direct call)
    confs = [c for c in sidebar.captures if c.get("classification") == "conflict"]
    adds = [c for c in sidebar.captures if c.get("classification") == "add"]
    print(f"\n--- Buckets: {len(adds)} adds, {len(confs)} conflicts ---")

    if confs:
        print("\n✓ TEST PASSED: conflict detected against non-negotiable")
    else:
        print("\n✗ TEST FAILED: expected at least one conflict (auth→billing)")
        sys.exit(1)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
