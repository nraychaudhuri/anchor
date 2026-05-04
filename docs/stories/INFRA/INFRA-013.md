---
id: INFRA-013
rail: INFRA
title: Verify and fix spec_exception → sidebar pipe chain
status: planned
phase: "19"
primary_files:
  - skills/companion/scripts/sidebar.py
touches:
  - tests/pairmode/test_spec_exception.py
  - docs/architecture.md
---

## Acceptance criterion

`skills/companion/scripts/sidebar.py` correctly handles the `spec_exception` pipe message
type by calling `record_spec_exception`. The pipe-to-disk chain for conflict records is
end-to-end verified by a test. Tests pass.

## Protected file justification

This story modifies `skills/companion/scripts/sidebar.py`, a protected file. Justification:
the `spec_exception` pipe message type is produced by the sidebar's own override prompt UI
and passed via pipe back to the sidebar's own pipe reader — but the pipe reader has no
handler for it, causing all conflict records to be silently dropped. This is a data loss
bug in the core capture pipeline, not a behavioural change to hook architecture.

## Instructions

See `docs/phases/phase-19.md` — Story INFRA-013.

## Tests

See `docs/phases/phase-19.md` — Story INFRA-013.
