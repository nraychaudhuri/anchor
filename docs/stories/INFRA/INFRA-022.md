---
id: INFRA-022
rail: INFRA
title: Replace str.startswith path containment in lesson_review.py with Path.relative_to (CER-004)
status: backlog
phase: ""
primary_files:
  - skills/pairmode/scripts/lesson_review.py
touches: []
---

## Acceptance criterion

`lesson_review.py:149` uses `Path.relative_to()` for containment instead of `str.startswith()`.
Test added that proves a prefix-collision input (e.g. project dir `/tmp/foo` and a candidate
`/tmp/foobar/x`) is rejected.

## Background (CER-004)

Source: Security audit cp14 (2026-04-25). Severity: not specified, treated as LOW.
`str.startswith` containment is vulnerable to prefix collision on unusual paths.

## Instructions

Replace the startswith check with `candidate.resolve().relative_to(base.resolve())` inside
a try/except ValueError, and add a unit test demonstrating the prefix-collision case.
