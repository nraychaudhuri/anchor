---
id: INFRA-016
rail: INFRA
title: Final pre-PR audit — full test suite, security pass, open CER review
status: planned
phase: "20"
primary_files: []
touches: []
---

## Acceptance criterion

Gate story — no code changes. All tests pass. No CRITICAL or HIGH security findings.
All CER Do Later items either resolved or have a corresponding backlog story file.
Do Now is empty. PAIRMODE.md "What pairmode changed in anchor core" table verified
against actual hook files. On pass: tagged `pr-candidate-v0.1`.

## Instructions

See `docs/phases/phase-20.md` — Story INFRA-016.

## Tests

Gate story — runs full suite + security audit. No new tests.
