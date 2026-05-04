---
id: INFRA-012
rail: INFRA
title: Test should_question/free_to_change round-trip through --from-reconstruction
status: planned
phase: "19"
primary_files: []
touches:
  - tests/pairmode/test_bootstrap.py
---

## Acceptance criterion

Integration tests verify the full round-trip: reconstruction brief with `should_question`
and `free_to_change` content → `bootstrap --from-reconstruction` → `ideology.md` output
contains both. Tests pass.

## Instructions

See `docs/phases/phase-19.md` — Story INFRA-012.

## Tests

See `docs/phases/phase-19.md` — Story INFRA-012.
