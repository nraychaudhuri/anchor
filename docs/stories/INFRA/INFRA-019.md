---
id: INFRA-019
rail: INFRA
title: pairmode_status.py — print pairmode state and sidebar attachment
status: complete
phase: "20"
primary_files:
  - skills/pairmode/scripts/pairmode_status.py
touches:
  - tests/pairmode/test_pairmode_status.py
---

## Acceptance criterion

`skills/pairmode/scripts/pairmode_status.py` is a Click CLI. Running it from a
project root prints a formatted status block: pairmode version, active era,
current story, loaded modules, and sidebar status with attachment instructions
for macOS and desktop Linux. Running it in a non-pairmode repo exits cleanly
with a message. Tests pass.

## Instructions

See `docs/phases/phase-20.md` — Story INFRA-019.

## Tests

See `docs/phases/phase-20.md` — Story INFRA-019.
