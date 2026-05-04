---
id: BUILD-001
rail: BUILD
title: Add story_update.py to update story and phase manifest status
status: planned
phase: "18"
primary_files:
  - skills/pairmode/scripts/story_update.py
touches:
  - tests/pairmode/test_story_update.py
---

## Acceptance criterion

`skills/pairmode/scripts/story_update.py` exists as a Click CLI and a set of importable
functions. Running it updates a story file's frontmatter `status` field and the
corresponding row in any phase manifest `## Stories` table. Tests pass.

## Instructions

See `docs/phases/phase-18.md` — Story BUILD-001.

## Tests

See `docs/phases/phase-18.md` — Story BUILD-001.
