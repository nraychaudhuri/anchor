# Pairmode — Standalone Contribution Guide

This document is written for an upstream anchor maintainer reviewing the era2 pull request.
It is self-contained: no external context is needed to evaluate what pairmode adds, what
it changed in core anchor files, and whether those changes are safe to accept.

---

## What pairmode is

Pairmode is a structured builder/reviewer workflow methodology shipped as a new anchor skill
(`/anchor:pairmode`). Stories are specced before building — each story lives in a discrete
file with YAML frontmatter declaring which files it owns (`primary_files`) and which it
touches (`touches`). Before each story build, permission pre-scoping writes a
`.claude/story_scope.json` that pre-authorizes declared file edits, eliminating mid-build
approval prompts without permanently widening permissions. A reviewer subagent runs a
fixed checklist after each build and either commits or reverts. A five-step checkpoint
sequence gates each phase: tests, security audit, intent review, documentation currency
check, and a tagging step. The methodology is self-hosting: the anchor repo itself was
built using pairmode from Phase 1 onward.

---

## What pairmode adds to anchor

All additions are new files. No existing anchor files were deleted.

**New skill — `skills/pairmode/`**

- `SKILL.md` — skill manifest and CLI reference
- `scripts/bootstrap.py` — generate pairmode scaffold from spec or reconstruction brief
- `scripts/audit.py` — diff project against canonical templates; detect structural drift
- `scripts/sync.py` — apply audit delta non-destructively; prompts before overwriting
- `scripts/lesson.py` — capture a lesson learned into `lessons/lessons.json`
- `scripts/lesson_review.py` — surface lessons, propose template updates
- `scripts/story_context.py` — read/write current story in `.companion/state.json`; pairmode detection
- `scripts/spec_exception.py` — record protected-file overrides into `spec.json` conflicts
- `scripts/reconstruct.py` — refresh `docs/reconstruction.md` from `ideology.md` and `brief.md`
- `scripts/ideology_parser.py` — shared parser for `ideology.md` and `reconstruction.md`
- `scripts/score.py` — render pre-populated `RECONSTRUCTION.md` scoring report
- `scripts/story_new.py` — create story files on named rails
- `scripts/era_new.py` — create era documents
- `scripts/schema_validator.py` — validate story/era/phase manifest frontmatter
- `scripts/permission_scope.py` — story-scoped allow rules for `.claude/settings.local.json`
- `scripts/story_resolver.py` — resolve story IDs to story file content; parse phase manifests
- `scripts/story_update.py` — update story and phase manifest status fields
- `scripts/pairmode_status.py` — print current pairmode state and sidebar attachment status
- `templates/` — Jinja2 templates for scaffold generation (CLAUDE.md, agents, docs, CER)

**New tests — `tests/pairmode/`**

Over 1000 unit tests covering all pairmode scripts. Each script has a corresponding test
file. Tests are pytest-only; no other framework is used.

**New docs — `docs/`**

- `docs/phases/` — per-phase build manifests (phases 1 through 20)
- `docs/stories/` — discrete story files organized by rail
- `docs/eras/` — era documents (strategic containers above phases)
- `docs/cer/` — Constraints and Exceptions Register backlog
- `docs/pipe-architecture.md` — rationale for project-scoped pipe path change (see below)
- `docs/pairmode/PAIRMODE.md` — this file

**New lessons store — `lessons/`**

- `lessons/lessons.json` — global methodology lessons (append-only)
- `lessons/LESSONS.md` — human-readable summary, auto-generated

**Updated plugin manifest — `.claude-plugin/plugin.json`**

The `pairmode` skill entry was added to register the new skill with Claude Code.

---

## What pairmode changed in anchor core

These are the only existing anchor files that were modified. All other changes are
new-file additions.

| File | Change | Reason |
|------|--------|--------|
| `hooks/stop.py` | Pipe path read from `.companion/state.json["pipe_path"]` at startup; falls back to `/tmp/companion.pipe` when `state.json` is absent | Multi-project concurrency: prevent cross-project pipe contamination when two anchor-enabled projects are open simultaneously |
| `hooks/post_tool_use.py` | Same | Same |
| `hooks/exit_plan_mode.py` | Same | Same |
| `hooks/session_end.py` | Same | Same |
| `hooks/hooks.json` | Added new `SessionStart` entry pointing to `hooks/session_start.py` (additive — no existing entry modified) | INFRA-018: inject pairmode context into Claude's session at startup so the developer doesn't need to ask whether pairmode is active |
| `.claude-plugin/plugin.json` | Added `pairmode` skill entry | Register the new `/anchor:pairmode` skill |
| `skills/companion/SKILL.md` | Added `current_story` state field documentation; updated CLI invocations to use `uv run` consistently | Pairmode tracks the active story in companion state; CLI uniformity for `uv`-based environments |
| `skills/companion/scripts/sidebar.py` | Multiple additive changes during pairmode work: (a) story-context panel; (b) module-boundary detection; (c) permission-override capture and `spec_exception` handler that writes conflict records to `spec.json` (Story INFRA-013); (d) state.json writes from session_end and exit_plan_mode hooks were rerouted through pipe messages (`mode_change`, state-field events) so the sidebar remains the sole writer to `.companion/state.json`; (e) per-project pipe path indirection mirroring the hook changes | Sidebar must surface live spec context to the developer during planning; preserve the architectural rule that only the sidebar writes spec/state files (hooks are thin relays) |
| `skills/companion/scripts/start_sidebar.sh`, `launch_sidebar.sh`, `launch_sidebar.command` | Pipe path now derived from `.companion/state.json` (with `/tmp/companion.pipe` legacy fallback) | Same multi-project pipe scoping as the hooks |
| `tests/test_live_chart.py`, `tests/test_plan_impact.py`, `tests/debug_pipe.py`, `tests/simulate_planning.py` | Deleted (Story INFRA-021) | Four single-author manual diagnostic scripts that pre-dated pairmode, were not pytest tests, and had zero references in the codebase. `test_live_chart.py` called `os.chdir(tmpdir)` at module-import time, contaminating pytest's cwd and causing three unrelated tests to fail; `test_plan_impact.py` `sys.exit(1)`'d on missing `~/.anchor/auth.json` |

The hook change is backwards-compatible: when `.companion/state.json` is absent (any
project that has not run `/anchor:companion` to establish a `state.json`), the hooks fall
back to the original `/tmp/companion.pipe` path and behave exactly as before.

See `docs/pipe-architecture.md` for the full rationale, the multi-project contamination
scenario that motivated the change, and notes on an alternative env-variable approach
that avoids touching `state.json` entirely if the upstream maintainer prefers it.

---

## What pairmode did NOT change

- `skills/seed/` — all seed scripts are unchanged
- `.claude-plugin/marketplace.json` — unchanged
- Any existing files in `docs/` (only new files were added to `docs/`)
- `lessons/` did not exist before pairmode; the directory and its contents are entirely new

---

## Design decisions

| Decision | Rationale |
|----------|-----------|
| Rails over flat story IDs | Enforces architectural lane ownership; cross-rail touches must be declared explicitly in `touches`, making scope creep visible at spec time rather than review time |
| Eras as strategic containers | Intent-scoped (not version/release-scoped); supports solo developers who do not release on a fixed schedule and need a coarser grouping above phases |
| Permission pre-scoping per story | Eliminates mid-build approval prompts without permanently widening permissions; `story_scope.json` is ephemeral and gitignored |
| Reviewer as subagent, not rule set | Can apply judgment to ambiguous cases; can run the full test suite; commit-or-revert removes the human bottleneck for routine stories while preserving human review for anything flagged |
| Five-step checkpoint (not just tests) | Security audit and intent review catch classes of problems tests cannot: API key exposure in committed files, design pivots that contradict the spec, architectural drift that accumulates across phases |
| Project-scoped pipe path via `state.json` | The companion skill already writes `state.json` at session start; reading the pipe path from there requires no new infrastructure and avoids shell environment plumbing. An env-variable alternative exists if the upstream maintainer prefers not to extend `state.json` — see `docs/pipe-architecture.md` |
| Lessons append-only | Immutability ensures lessons survive across context compaction and agent restarts; status is the only mutable field |
| `schema_validator.py` as canonical frontmatter parser | Centralizes YAML frontmatter parsing so changes to the schema propagate to all callers without reimplementation; imported by `story_resolver.py`, `permission_scope.py`, `era_new.py`, and `story_new.py` |

---

## Known limitations and open work

- **Solo-developer optimized.** No multi-developer story assignment, no pipe collision
  avoidance between developers on the same project, no lock file for concurrent story edits.

- **Sidebar required for real-time conflict detection.** Pairmode functions without the
  sidebar — stories build, the reviewer runs, tests pass — but protected-file conflict
  detection and the `spec_exception` override prompt are only active when the companion
  sidebar process is running.

- **`lesson_review.py` annotates but does not implement.** The review script identifies
  lessons that suggest template changes and adds annotation comments to the relevant
  templates. The developer must open the templates and apply the changes manually.

- **Story status updates require bash invocations.** Phase 18 introduced `story_update.py`
  to reduce friction (`uv run python skills/pairmode/scripts/story_update.py --story-id
  RAIL-NNN --status complete --project-dir .`), but orchestrators that call it still require
  a manual shell step or explicit orchestrator integration.

- **Bootstrap does not validate generated deny-list rules against the live spec.** The
  deny list is generated at bootstrap time from the spec's `non_negotiables`; if
  `non_negotiables` change after bootstrap, the deny list does not auto-update. Running
  `/anchor:pairmode audit` and then `/anchor:pairmode sync` surfaces the drift and applies
  the delta non-destructively.

---

## Running the tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All 1000+ pairmode tests run in under 15 seconds on a standard laptop.

To run the full test suite (pairmode plus any other tests in the repo):

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q
```

Tests require Python 3.11+ and `uv`. Install `uv` with:

```bash
curl -Lsf https://astral.sh/uv/install.sh | sh
```
