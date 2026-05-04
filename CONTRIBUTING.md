# Contributing to anchor

This guide covers the day-to-day mechanics of contributing to anchor — running
tests, capturing lessons, proposing methodology changes, and filing CERs.
For the architectural context behind these workflows, read `docs/architecture.md`
first; for the pairmode methodology specifically, read `docs/pairmode/PAIRMODE.md`.

## Running tests

The pairmode test suite is the primary gate for any change to a pairmode script
or template:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

To run the full repository test suite (including any non-pairmode tests):

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q
```

All Python execution uses `uv run`. Do not invoke bare `python` or `pip` —
declare new dependencies in the relevant `requirements.txt` (or `pyproject.toml`)
and let `uv` resolve them.

## Adding a lesson

Lessons capture a methodology improvement: something that surfaced during a
build, review, or post-mortem and that should change how future work is done.

```bash
/anchor:pairmode lesson
```

The skill walks you through:
- the triggering situation (what happened that prompted the lesson),
- what was learned,
- what should change in the methodology (templates, checks, conventions),
- which projects the lesson applies to (this repo, all anchor projects, etc.).

The lesson is appended to `lessons/lessons.json`. Existing entries are never
edited except to update the `status` field (`open`, `applied`, `superseded`).
The append-only invariant is enforced by review.

## Proposing a template change

Template changes follow a four-step path: lesson, review, annotation,
implementation.

1. **Capture a lesson** for the underlying motivation (see above).
2. **Run `/anchor:pairmode review`.** This surfaces open lessons and proposes
   which templates or scripts they imply changes to.
3. **Annotate the relevant template.** `lesson_review.py` does not edit
   templates directly — it leaves a comment block at the top of the affected
   `.j2` file describing the proposed change and the lesson IDs that motivate it.
4. **Implement the change** as a normal pairmode story:
   - Create a story file under `docs/stories/<RAIL>/<RAIL>-NNN.md` with
     `primary_files` listing the templates and scripts being modified.
   - Update the template, run the test suite, and commit with the standard
     `feat(story-RAIL-NNN):` prefix.

## Filing a CER

A CER (Critical Engineering Review) is a structured note about a finding that
is not yet a story — for example, a security concern, an architectural smell,
or a follow-up surfaced by a build that should not block the current phase.

```bash
uv run python skills/pairmode/scripts/cer.py
```

The CER script appends to `docs/cer/backlog.md` under one of three sections
(Do Now, Do Later, Do Much Later). Findings move to a story file when they are
ready to be built, using `story_new.py` with `status: backlog` if not yet
scheduled. The Do Now section must be empty before tagging a phase.

## Story and phase conventions

- **Rails.** Each story belongs to one rail (e.g., `INFRA`, `BUILD`, `BOOTSTRAP`,
  `AUDIT`). Story IDs are `RAIL-NNN` with a 3-digit sequence. New rails are
  defined per project at bootstrap.
- **Story files.** Live at `docs/stories/<RAIL>/<RAIL>-NNN.md` with YAML
  frontmatter (`id`, `rail`, `title`, `status`, `phase`, `primary_files`,
  `touches`). Phase docs reference story IDs in a `## Stories` table; the full
  story content lives in the individual file.
- **Commit format.** `feat(story-RAIL-NNN): one-line description`. Other
  conventional prefixes (`fix`, `docs`, `chore`) are accepted when appropriate.
- **Checkpoint sequence.** Each phase ends with a 5-step checkpoint: full test
  run, security audit, intent review, documentation currency check, and tag.
  See `CLAUDE.build.md` for the canonical sequence.

## Protected files

These files are working and must not be modified without a stated reason in the
story spec. Unexplained modifications are flagged HIGH severity at review.

- `hooks/` — all existing hook scripts and `hooks.json` (hooks must remain
  thin relays; any logic added here is a CRITICAL violation).
- `skills/seed/scripts/` — all seed scripts.
- `skills/companion/scripts/sidebar.py` — companion sidebar.
- `.claude-plugin/plugin.json` — plugin manifest.
- `.claude-plugin/marketplace.json` — marketplace registration.
- `lessons/lessons.json` — append-only lessons store.

To justify a modification: state the reason in the story file under a
`Protected file justification` section, and have the reviewer confirm the
justification matches the actual diff. The sidebar's override-prompt flow
also records justifications as `spec_exception` conflict entries on the
relevant module spec.

## Pipe architecture

Hooks communicate with the companion sidebar through a project-scoped pipe;
see `docs/pipe-architecture.md` for the design, the legacy fallback, and the
files this fork modifies relative to upstream anchor.
