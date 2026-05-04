# Anchor Methodology Lessons

This file is auto-generated from `lessons.json`. Edit `lessons.json` directly
or use `/anchor:pairmode lesson` to capture a new lesson.

## L001 — Ran audit against cora — a project with pairmode scaffold but no pairmode_context.json
**Date:** 2026-04-20
**Status:** applied
**Learning:** When audit detects no pairmode_context.json, it should emit a prominent warning: 'No pairmode_context.json found — template body comparison will show false INCONSISTENT for all variable-bearing sections. Bootstrap this project with /anchor:pairmode to fix.' MISSING and EXTRA findings remain reliable; INCONSISTENT findings require a context file to be meaningful.

## L002 — Ran audit against radar and forqsite — projects with pairmode scaffold
**Date:** 2026-04-20
**Status:** applied
**Learning:** The _split_sections output uses '---' as section keys in audit output. These entries are hard to interpret. Either: (a) skip separator-keyed sections from INCONSISTENT comparison since --- separators carry no semantic content, or (b) display the surrounding context (what section comes before/after) when reporting --- inconsistencies.

## L003 — Bootstrap dogfood on anchor — re-running after bug fixes
**Date:** 2026-04-21
**Status:** applied
**Learning:** For mature projects, templates are a starting point, not a replacement. Files that already exist should be skipped by default (same as CLAUDE.md/CLAUDE.build.md), or bootstrap should warn before overwriting hand-authored content.

## L004 — Bootstrap dogfood — builder.md Python standards section
**Date:** 2026-04-21
**Status:** applied
**Learning:** Template variables should be scoped to their semantic slot. build_command belongs in the build-gate section only; the Python standards section should hardcode 'uv run'.

## L005 — Bootstrap dogfood — reviewer.md checklist from spec non-negotiables
**Date:** 2026-04-21
**Status:** applied
**Learning:** Non-negotiables are constraints, not checklist item names. The reviewer checklist needs human-authored label + short action question, not raw spec text. checklist_deriver should either produce module-scoped labels (e.g. 'companion-skill: spec write isolation') or not populate the reviewer checklist at all — leaving that to the human.

## L006 — Dogfood audit run on anchor after clean bootstrap
**Date:** 2026-04-21
**Status:** captured
**Learning:** Audit needs a way to mark sections as intentionally overridden. Without that signal, any project that customises its scaffold will permanently live in a noisy INCONSISTENT state, eroding trust in the tool.

## L007 — Dogfood pairmode on multiple projects simultaneously — anchor + ud running at same time
**Date:** 2026-04-21
**Status:** applied
**Learning:** The pipe path must be scoped to the project directory. Each project gets its own pipe derived from an 8-char md5 hash of the project dir. The sidebar reads its own pipe only. Hooks read the pipe_path from .companion/state.json at startup.

## L008 — Phase 21 spec written, CER agent run on spec before build, found 20 issues including compile-blockers
**Date:** 2026-04-24
**Status:** captured
**Learning:** Running a cold-eyes review on the phase spec itself (not just on built code) catches architectural and correctness errors before any builder time is spent. The CER agent reading actual source files alongside the spec finds mismatches the spec author missed. This is more valuable than a post-build reviewer alone.
