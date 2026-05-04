---
id: INFRA-023
rail: INFRA
title: Constrain hooks PIPE_PATH redirection via state.json validation (CER-009)
status: backlog
phase: ""
primary_files:
  - hooks/stop.py
  - hooks/post_tool_use.py
  - hooks/session_end.py
touches: []
---

## Acceptance criterion

The four hook scripts that read `pipe_path` from `.companion/state.json` validate the
value against an allowlist (must start with `/tmp/companion-` and end with `.pipe`)
before opening it. A crafted state.json cannot redirect pipe writes to an arbitrary path.

## Background (CER-009)

Source: Security audit cp17 (2026-04-30). Severity: LOW. No secrets in payloads; write
silently drops on ENXIO if no FIFO reader. `exit_plan_mode.py` correctly uses
`tempfile.gettempdir()`.

## Instructions

In each hook, wrap the state.json read with a pattern check (regex
`^/tmp/companion-[0-9a-f]{1,16}\.pipe$`) and fall back to the legacy default if the
value fails the pattern. Add a contract test for each hook.
