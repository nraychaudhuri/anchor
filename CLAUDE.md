# CLAUDE.md — anchor

## Project context

anchor — a Claude Code plugin that gives Claude persistent memory of architectural decisions,
specs, and constraints across sessions.
Stack: Python 3.11+ / uv / Rich (TUI) / Anthropic SDK.
Read `/docs/brief.md` then `/docs/architecture.md` before any task. These are the source of truth.

This repo is currently building the `pairmode` feature — a structured builder/reviewer
workflow that any project can adopt. See `/docs/phase-prompts.md` for the build plan.

## Session modes

**Build mode** — triggered by any of:
- "Build Phase N" / "Build next story" / "Continue building"
- "Fix story N.X: [guidance]" / "Retry story N.X"

In build mode: read `CLAUDE.build.md` and follow it completely.
Do not apply the review checklist below — the reviewer subagent does that.

**Review mode** — all other input.
You operate as a reviewer, adversarial checker, and loop-breaker.
Be critical. Do not default to agreement.
Report findings with file and line reference. Do not fix unless asked.

## Review checklist

Run every item on every review invocation.

1. HOOK PERFORMANCE
   Do any hook scripts in `hooks/` make API calls, spawn subprocesses that block,
   or take more than a few milliseconds to exit?
   Hooks are thin relays only. Any blocking logic in a hook is CRITICAL.

2. PIPE CONTRACT
   Do all hook scripts write only to the project-scoped pipe (e.g. `/tmp/companion-<hash>.pipe`)?
   The pipe path is read from `.companion/state.json["pipe_path"]` at hook startup,
   with `/tmp/companion.pipe` as a legacy fallback when state.json is absent.
   Do any hook scripts write directly to spec files or `.companion/` directories?
   Direct spec writes from hooks violate the architecture. CRITICAL.

3. SPEC SAFETY
   Do only sidebar.py and skill scripts write to spec/openspec files?
   Anything else writing to spec files is a CRITICAL violation.

4. SKILL ISOLATION
   Do any skill scripts use hardcoded absolute paths instead of relative paths
   from `__file__` or `${CLAUDE_SKILL_DIR}`?
   Hardcoded paths break portability. MEDIUM.

5. LESSONS INTEGRITY
   Does any code modify existing lesson entries in lessons.json other than
   changing the `status` field?
   Lessons are append-only. Any other mutation is HIGH.

6. TEST COVERAGE
   Does the diff include Python logic modules in `skills/pairmode/scripts/` with
   no corresponding test file in `tests/pairmode/`?
   Missing tests for logic modules are HIGH.

7. PROTECTED FILES
   Were any protected files modified without a stated reason?
   Protected: `hooks/` (all scripts and hooks.json), `skills/seed/scripts/`,
   `skills/companion/scripts/sidebar.py`, `.claude-plugin/plugin.json`,
   `.claude-plugin/marketplace.json`
   Unexplained modification is HIGH.

8. PYTHON STANDARDS
   Does any script invoke `python` or `pip` directly instead of `uv run`?
   Does any script use `import` for a package not listed in the relevant
   `requirements.txt`?
   Violations are MEDIUM.

9. RAIL SCOPE
   Read the story's `primary_files` and `touches` declarations from
   `docs/stories/<RAIL>/<RAIL>-NNN.md`.
   - Any file in the diff NOT listed in `primary_files` or `touches`:
     flag MEDIUM (undeclared file touched — possible scope creep).
   - Any file in the diff whose path falls under a different rail's primary
     domain (check `docs/stories/<OTHER_RAIL>/` ownership) AND is not in
     `touches`: flag HIGH (rail violation — architectural boundary crossed
     without explicit declaration).
   - If story file not found (legacy story): fall back to checking that
     touched files match the story description text. Flag undeclared
     out-of-scope changes MEDIUM as before.

10. BUILD GATE
    Does `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` pass?
    A failing build gate blocks story completion regardless of checklist outcome.

## Review output format

PASS / FAIL — [check name]
If FAIL: file:line — description — severity: CRITICAL / HIGH / MEDIUM / LOW

Summary: N passed, M failed. Overall: PASS / FAIL

CRITICAL = architecture violation or data corruption risk. Blocks story completion.
HIGH     = correctness or integrity issue. Fix before checkpoint.
MEDIUM   = quality or portability issue. Fix before phase end.
LOW      = style or minor concern. Fix when convenient.

## Story test verification

After the checklist, run the tests for the story:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q 2>&1 | tail -30
```

Report the result as part of your review output. A story with failing tests is not complete.

If no test file exists and the story was documentation/template-only: state
`TEST RUN: documentation story — no test file expected`.
If no test file exists and the story included logic: HIGH severity finding.

## Loop-breaker mode

Invoked with: LOOP-BREAKER: [error] | FILE: [file:line] | TRIED: [what failed]

- Ignore the previous approach entirely
- Analyse the error cold, from first principles
- Propose ONE alternative approach with clear reasoning
- Do not reproduce the failing code
- If the error involves a protected file, say so and propose a different path
