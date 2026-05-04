---
id: INFRA-024
rail: INFRA
title: Validate story_new.py --rail input against rail-name regex (CER-010)
status: backlog
phase: ""
primary_files:
  - skills/pairmode/scripts/story_new.py
touches: []
---

## Acceptance criterion

`story_new.py` validates `--rail` against the canonical rail-name regex (uppercase ASCII,
no path separators) BEFORE constructing any path. A caller passing `--rail "../../../etc"`
is rejected with a clear error. A `resolve().relative_to(project_dir)` containment check
is also added as defence in depth.

## Background (CER-010)

Source: Security audit cp18 (2026-04-30). Severity: MEDIUM. Currently `--rail` input is
`.upper()`'d but not validated against a regex before being used in path construction.
`story_new.py:183-185`.

## Instructions

Define `_RAIL_RE = re.compile(r'^[A-Z][A-Z0-9]{0,15}$')`. Validate at CLI entry. Add
containment check before write. Add unit test for traversal rejection.
