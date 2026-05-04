# Anchor — The IDE for Intent

Code is cheap to generate. Intent is scarce. Agents drift without it: constraints agreed
on two sessions ago are invisible today, modules accumulate contradictory assumptions, and
every new session starts from zero. Anchor makes intent persistent. It captures what you
are building and why — automatically, as you work — and makes that record the source of
truth for every agent and every session.

## Status

Alpha. Under active development. Core workflows are functional and used in production on
this repo. The API and scaffold format may change without notice. See Known Limitations.

## What anchor does

Anchor provides two complementary layers.

**Memory layer** (`/anchor:seed` + `/anchor:companion`): `/anchor:seed` reads your
codebase and historical Claude Code transcripts to build a canonical spec — structured JSON
records of decisions, rules, tradeoffs, and lineage for each module. `/anchor:companion`
loads that spec at session start, detects drift between new decisions and established rules,
and runs a sidebar process that captures decisions made during the session into the spec
automatically.

**Process layer** (`/anchor:pairmode`): Bootstraps and manages a structured
builder/reviewer methodology on any project. Produces a full scaffold — CLAUDE.md, agent
docs, permission settings, phase specs, and a CER backlog — and enforces the build loop at
every commit. Generates `docs/ideology.md` (a conviction and constraint record that
survives across implementations) and `docs/reconstruction.md` (a handoff prompt that seeds
an independent agent to produce a competing implementation of the same project from
ideology alone).

Used together, the memory layer supplies the spec; the process layer enforces it.

## Installation

```bash
# Install as a Claude Code plugin from the plugin directory
claude code plugin install path/to/anchor

# Or clone and install locally
git clone https://github.com/halfhorse/anchor
claude code plugin install ./anchor
```

Requirements: Claude Code, Python 3.11+, uv.

The plugin registers three skills: `/anchor:seed`, `/anchor:companion`,
and `/anchor:pairmode`. Marketplace installation is available for registered users.

## Quick start

### New project

```bash
# 1. Bootstrap pairmode on your project — generates scaffold from your spec
/anchor:pairmode bootstrap

# 2. Create your first story on a named rail
uv run python skills/pairmode/scripts/story_new.py --rail CORE --title "Initial data model"

# 3. Tell the builder which story to work on, then build
# In Claude Code: "Build story CORE-001"
```

The bootstrap command asks for your project name, tech stack, and key modules. It writes
CLAUDE.md, CLAUDE.build.md, agent prompt templates, and an initial phase file. Pairmode
is active immediately.

### Existing project with session history

```bash
# 1. Mine existing transcripts and build the canonical spec
/anchor:seed

# 2. Start the companion sidebar to begin capturing new decisions
/anchor:companion

# 3. Bootstrap pairmode on top of the populated spec
/anchor:pairmode bootstrap
```

If you have prior Claude Code sessions, `/anchor:seed` extracts decisions from them before
bootstrap. The spec it produces seeds the pairmode scaffold so that generated rules and
checklists reflect your actual project history.

## The three skills

| Skill | What it does | Key command | Key output |
|-------|-------------|-------------|-----------|
| `/anchor:seed` | Mine transcripts, build canonical spec | `/anchor:seed` | `openspec/specs/<module>/spec.json` |
| `/anchor:companion` | Load spec, capture decisions, detect drift | `/anchor:companion` | Updated `spec.json`, sidebar process |
| `/anchor:pairmode` | Scaffold and enforce structured build loop | `/anchor:pairmode bootstrap` | CLAUDE.md, agent docs, phase files, deny list |

## Use case scenarios

### Scenario A: New project with build loop

You are starting a Python API service. The codebase is empty.

1. Run `/anchor:pairmode bootstrap`. Answer the prompts: project name `invoicing-api`,
   stack `Python/FastAPI/PostgreSQL`, modules `api`, `billing`, `auth`.
2. Anchor writes CLAUDE.md, CLAUDE.build.md, initial ideology, and a phase-1 spec file.
   The deny list in `.claude/settings.json` is generated from your declared non-negotiables:
   "no direct database writes outside the repository layer."
3. You create story `BILLING-001: Add invoice creation endpoint` via `story_new.py`.
4. You invoke the builder subagent: "Build story BILLING-001."
5. The builder implements the endpoint. When it tries to write raw SQL in the route handler,
   the deny list blocks the write and the sidebar surfaces the conflict: the route handler
   is not in the repository layer.
6. You invoke the reviewer subagent. It checks the implementation against the checklist,
   confirms the constraint was respected, and commits with the story tag.
7. The spec gains a new lineage entry. The constraint held.

### Scenario B: Returning developer

You have been away from a project for three months. The spec and methodology are already
in place.

1. Run `/anchor:pairmode audit`. It compares your project scaffold against the current
   canonical pairmode templates and reports drift: your CLAUDE.build.md is missing the
   permission-scope step added in Phase 16.
2. Run `/anchor:pairmode sync`. It offers to apply the delta non-destructively. You accept.
3. Run `/anchor:companion`. The sidebar loads the spec. You see that the last session added
   three lineage entries to the `billing` module. The current story was `BILLING-007`.
4. You check `docs/phases/phase-3.md`. BILLING-007 is complete. The next planned story is
   BILLING-008. You set the story: `story_context.py --set BILLING-008`.
5. You pick up where you left off. The full constraint record is intact. Nothing was lost.

## The build loop

1. Write the story spec in `docs/stories/<RAIL>/<RAIL>-NNN.md` with frontmatter and
   acceptance criterion.
2. Invoke the builder subagent: "Build story RAIL-NNN." The builder reads the spec,
   implements, and runs tests.
3. Invoke the reviewer subagent. It runs the review checklist and the test suite.
4. On PASS: the reviewer commits with the story tag. On FAIL: the builder fixes and
   the reviewer re-runs.
5. If the builder is stuck after two attempts: invoke the loop-breaker.
6. After each phase: run the 5-step checkpoint sequence (test suite, security audit,
   intent review, documentation update, checkpoint tag).

## The canonical spec format

```json
{
  "module": "billing",
  "summary": "Handles invoice creation, payment tracking, and revenue reporting.",
  "business_rules": [
    "An invoice may not be marked paid unless a corresponding payment record exists."
  ],
  "non_negotiables": [
    "No direct database writes outside the repository layer."
  ],
  "tradeoffs": [
    {
      "decision": "Synchronous payment confirmation",
      "reason": "Simplicity at current scale; async adds infrastructure complexity.",
      "accepted_cost": "Slower response on payment endpoints."
    }
  ],
  "conflicts": [],
  "lineage": [
    {
      "session_id": "abc123",
      "summary": "Defined repository layer boundary and payment confirmation strategy.",
      "date": "2026-01-15",
      "resume": "claude --resume abc123"
    }
  ]
}
```

Each module has one `spec.json`. `non_negotiables` never auto-resolve — they require a
developer decision to override. `lineage` is append-only.

## Known limitations

- Alpha software. Internal APIs and scaffold formats may change without notice.
- Optimized for solo developers. No multi-developer story assignment or concurrent session
  coordination.
- The companion sidebar must be running for real-time drift detection and automatic spec
  updates. Pairmode functions without it, but decisions are not captured live.
- `lesson_review.py` annotates templates with improvement suggestions but does not apply
  them. The developer must open the template and implement the change manually.
- Story status updates and some orchestrator steps require manual bash invocations.
  `story_update.py` (introduced in Phase 18) reduces friction but does not fully automate
  the status lifecycle.
- The reconstruction workflow (ideology extraction and competing implementation seeding)
  requires a populated spec and works best after several sessions of decision capture.

## Requirements and License

**Requirements:**
- Claude Code (any version with plugin support)
- Python 3.11+
- uv (Python package manager)

**License:** MIT. See LICENSE file.

**Contact:** david@halfhorse.com
