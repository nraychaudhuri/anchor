---
id: INFRA-005
rail: INFRA
title: Security fix — validate story_id format in story_update.py (HIGH path traversal)
status: planned
phase: "18"
primary_files:
  - skills/pairmode/scripts/story_update.py
touches:
  - tests/pairmode/test_story_update.py
---

## Acceptance criterion

`story_update.py` validates the `--story-id` argument using `_STORY_ID_RE` before any
file path is constructed. A crafted story_id containing an absolute path component is
rejected with a clear error before any file I/O occurs. Tests pass.

## Instructions

See `docs/phases/phase-18.md` — Story INFRA-005.

## Tests

See `docs/phases/phase-18.md` — Story INFRA-005.
