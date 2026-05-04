---
id: INFRA-018
rail: INFRA
title: SessionStart hook injects pairmode context into Claude session
status: complete
phase: "20"
primary_files:
  - hooks/session_start.py
touches:
  - hooks/hooks.json
  - tests/pairmode/test_session_start_hook.py
---

## Acceptance criterion

When a Claude Code session opens in a pairmode-bootstrapped repo, Claude receives
an `additionalContext` block listing pairmode version, current story (if any),
loaded modules, and sidebar status. If sidebar not detected, message includes
platform-appropriate attachment instructions for macOS and desktop Linux.
Tests pass.

## Protected file justification

This story adds two new files to `hooks/`: a new `hooks/session_start.py` script
and a new entry in `hooks/hooks.json`. No existing hook file is modified. The
script is a thin file reader (sub-millisecond, no API calls, no blocking I/O).
It does not write to the pipe, to spec files, or to any state. This is exactly
the intended use of a SessionStart hook in the architecture.

## Instructions

See `docs/phases/phase-20.md` — Story INFRA-018.

## Tests

See `docs/phases/phase-20.md` — Story INFRA-018.
