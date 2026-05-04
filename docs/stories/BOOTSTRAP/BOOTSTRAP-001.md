---
id: BOOTSTRAP-001
rail: BOOTSTRAP
title: Add --yes flag to bootstrap for non-interactive callers
status: planned
phase: "18"
primary_files:
  - skills/pairmode/scripts/bootstrap.py
touches:
  - tests/pairmode/test_bootstrap.py
  - SKILL.md
---

## Acceptance criterion

`bootstrap.py` accepts `--yes` / `-y` to auto-confirm all interactive prompts. Non-interactive
callers and CI pipelines can bootstrap without piping input. Tests pass.

## Instructions

See `docs/phases/phase-18.md` — Story BOOTSTRAP-001.

## Tests

See `docs/phases/phase-18.md` — Story BOOTSTRAP-001.
