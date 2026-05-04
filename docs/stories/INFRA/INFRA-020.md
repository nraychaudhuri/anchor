---
id: INFRA-020
rail: INFRA
title: Fix pairmode_status.py ANCHOR_ROOT computation (CER-012)
status: complete
phase: "20"
primary_files:
  - skills/pairmode/scripts/pairmode_status.py
touches:
  - tests/pairmode/test_pairmode_status.py
  - docs/cer/backlog.md
---

## Acceptance criterion

`skills/pairmode/scripts/pairmode_status.py` correctly resolves the anchor repo root.
The `start_sidebar.sh` instruction printed for missing-sidebar scenarios points to a
real existing file. A test asserts the printed path resolves to an existing file.
Tests pass.

## Instructions

See `docs/phases/phase-20.md` — Story INFRA-020.

## Tests

See `docs/phases/phase-20.md` — Story INFRA-020.
