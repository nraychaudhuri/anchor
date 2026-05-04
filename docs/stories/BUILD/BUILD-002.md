---
id: BUILD-002
rail: BUILD
title: Update CLAUDE.build.md with explicit bash commands for permission_scope and story_update
status: planned
phase: "18"
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - tests/pairmode/test_templates.py
---

## Acceptance criterion

`CLAUDE.build.md` and its Jinja2 template show the exact bash commands for
`write_story_permissions`, `clear_story_permissions`, and `story_update` — not
pseudocode Python function calls. Tests pass (template rendering).

## Instructions

See `docs/phases/phase-18.md` — Story BUILD-002.

## Tests

See `docs/phases/phase-18.md` — Story BUILD-002.
