# Changelog

All notable changes to anchor are documented here. This project loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Pairmode-specific
changes are marked `[pairmode]`; modifications to anchor core are marked `[core]`.

## [Unreleased]

### Added [pairmode]
- Phase 17: correctness fixes across the pairmode skill — story status lifecycle,
  manifest-aware orchestration, schema_validator integration tightening.
- Phase 18: missing tooling — `story_update.py` (canonical story status updater),
  `.pairmode-overrides` support, bootstrap `--yes` non-interactive flag,
  `spec_exception` sidebar handler integration.
- Phase 19: test coverage and integration verification — closed gaps in
  `phase_new`, `story_resolver` link-format handling, CER ID detection,
  bootstrap `--yes` end-to-end coverage, `spec_exception` pipe contract tests.
- Phase 20: PR readiness — `README.md`, `docs/pipe-architecture.md`,
  `docs/pairmode/PAIRMODE.md`, `CHANGELOG.md`, `CONTRIBUTING.md`,
  SessionStart hook (`hooks/session_start.py`), `pairmode_status.py` CLI,
  pre-PR audit gate, and a paused git-history review.

### Changed [core]
- `hooks/{stop,post_tool_use,exit_plan_mode,session_end}.py`: pipe path is now
  project-scoped via `.companion/state.json["pipe_path"]` with fallback to
  `/tmp/companion.pipe`. Backwards-compatible. See `docs/pipe-architecture.md`.
- `.claude-plugin/plugin.json`: added `pairmode` skill entry. The marketplace
  manifest is unchanged.

## [pairmode v0.0.x] — Phases 1-16 (anchor era2 branch)

### Added [pairmode]
- Phase 1-7: core scaffold, spec-derived deny-list generation, lessons store,
  `audit` and `sync` commands, companion enhancements, audit noise reduction,
  template coherence pass.
- Phase 8-9: sync confirmation prompt, tooling fixes, dead-code cleanup,
  formal pipe contract definition.
- Phase 10: ideology capture — guided prompt flow, non-interactive mode,
  reconstruction-brief seeding.
- Phase 11-12: reconstruction workflow, blank-slate seeding,
  `RECONSTRUCTION.md.j2` scoring template.
- Phase 13: CER (Critical Engineering Review) cleanup, end-to-end
  reconstruction verification.
- Phase 14: reconstruction agent tooling, `score.py` for filling the
  `RECONSTRUCTION.md` template.
- Phase 15: rails, eras, discrete story files under `docs/stories/<RAIL>/`,
  `schema_validator.py`, `story_new.py`, `era_new.py`.
- Phase 16: `permission_scope.py` (story-scoped allow rules),
  `story_resolver.py`, manifest-aware `CLAUDE.build.md`, rail-violation
  detection in the reviewer checklist, sync rail-gap detection.

### Notes
- All changes through Phase 16 are additive to anchor core. Hook files were
  not modified until the Phase 8 pipe-scoping change (which retained legacy
  fallback behavior).
- The lessons store (`lessons/lessons.json`) is append-only. Existing entries
  may only have their `status` field updated.
