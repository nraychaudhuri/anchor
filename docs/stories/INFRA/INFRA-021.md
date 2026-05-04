---
id: INFRA-021
rail: INFRA
title: Remove orphan upstream dev scripts from tests/ (cwd contamination)
status: complete
phase: "20"
primary_files:
  - tests/test_live_chart.py
  - tests/test_plan_impact.py
  - tests/debug_pipe.py
  - tests/simulate_planning.py
touches:
  - docs/pairmode/PAIRMODE.md
---

## Acceptance criterion

Four orphan dev scripts at `tests/` root are deleted. `pytest tests/` runs cleanly
with no collection errors. PAIRMODE.md "What pairmode changed in anchor core"
documents the deletion.

## Instructions

See `docs/phases/phase-20.md` — Story INFRA-021.

## Tests

No new tests. The acceptance criterion is "pytest runs cleanly."
