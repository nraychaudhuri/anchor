---
id: INFRA-011
rail: INFRA
title: Integrate schema_validator into story_new.py and era_new.py creation flow
status: planned
phase: "18"
primary_files:
  - skills/pairmode/scripts/story_new.py
  - skills/pairmode/scripts/era_new.py
touches:
  - tests/pairmode/test_story_new.py
  - tests/pairmode/test_era_new.py
---

## Acceptance criterion

`story_new.py` calls `validate_story_file` after writing the new story file and prints
any validation errors as warnings (non-fatal). `era_new.py` calls `validate_era_file`
the same way. Creation always exits 0 unless the file could not be written. Tests pass.

## Instructions

See `docs/phases/phase-18.md` — Story INFRA-011.

## Tests

See `docs/phases/phase-18.md` — Story INFRA-011.
