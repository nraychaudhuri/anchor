---
id: AUDIT-001
rail: AUDIT
title: Add .pairmode-overrides to suppress intentional customisation noise in audit/sync
status: planned
phase: "18"
primary_files:
  - skills/pairmode/scripts/audit.py
  - skills/pairmode/scripts/sync.py
  - skills/pairmode/templates/.pairmode-overrides.j2
touches:
  - tests/pairmode/test_audit.py
  - tests/pairmode/test_sync.py
  - SKILL.md
---

## Acceptance criterion

A `.pairmode-overrides` file at the project root lets a project declare which sections
are intentionally diverged. Audit treats declared sections as EXTRA rather than
INCONSISTENT or MISSING. `sync --yes` never overwrites declared override sections.
Tests pass.

## Instructions

See `docs/phases/phase-18.md` — Story AUDIT-001.

## Tests

See `docs/phases/phase-18.md` — Story AUDIT-001.
