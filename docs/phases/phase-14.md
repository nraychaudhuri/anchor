# anchor — Phase 14: Reconstruction agent tooling

← [Phase 13: CER cleanup and end-to-end reconstruction verification](phase-13.md)

## Goal

Phase 12 created `RECONSTRUCTION.md.j2` — the scoring report template reconstruction agents
fill in after completing their implementation. Phase 14 gives the reconstruction agent
everything it needs to actually do that work:

1. A `score.py` script that renders `RECONSTRUCTION.md.j2` pre-populated from a
   reconstruction brief, outputting a partially-filled scoring report the agent can complete.
2. A `reconstruction-agent.md.j2` agent definition template — a structured agent doc that
   the original project bootstraps into `.claude/agents/` for any downstream reconstruction
   team to use. The agent knows how to use the brief, fill in the scoring report, and hand
   back findings.
3. Wire `reconstruction-agent.md.j2` into `bootstrap.py` so it is generated alongside the
   other agent files.

Three stories:

1. `score.py` — render pre-populated RECONSTRUCTION.md scoring report (14.0)
2. `reconstruction-agent.md.j2` — agent definition template (14.1)
3. Wire reconstruction agent into bootstrap scaffold (14.2)

Prerequisites: Phase 13 complete and tagged cp13-cer-cleanup-e2e.

---

### Story 14.0 — `score.py`: render pre-populated RECONSTRUCTION.md scoring report

**Acceptance criterion:** `skills/pairmode/scripts/score.py` exists. Running it against a
project directory reads `docs/reconstruction.md` (the brief) and writes
`docs/RECONSTRUCTION.md` pre-populated with the conviction headings, constraint names, and
comparison rubric dimensions extracted from the brief — ready for the reconstruction agent to
fill in scores and justifications. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/score.py` as a Click CLI:

```python
@click.command()
@click.option("--project-dir", default=".", type=click.Path(exists=True, file_okay=False),
              help="Root of the reconstructed project.")
@click.option("--brief", default=None, type=click.Path(exists=False, dir_okay=False),
              # exists=False: existence checked manually after resolution so the
              # --brief containment guard (Story 14.3) runs before any filesystem access.
              help="Path to reconstruction.md brief. Defaults to <project-dir>/docs/reconstruction.md.")
@click.option("--force", is_flag=True, default=False,
              help="Overwrite existing docs/RECONSTRUCTION.md without prompting.")
def score(project_dir, brief, force):
    """Render a pre-populated RECONSTRUCTION.md scoring report from the reconstruction brief."""
```

Logic:
1. Resolve `project_dir`. Apply path traversal guard (`not resolved.is_dir() or len(resolved.parts) < 3`).
2. If `--brief` not given, default to `<project_dir>/docs/reconstruction.md`. Abort with a clear
   message if the brief file does not exist.
3. Call `ideology_parser.parse_reconstruction_brief(brief_path)` to get context.
4. Extract `project_name` from brief frontmatter or first heading (`# Reconstruction Brief — ProjectName`).
5. Add `reconstruction_date` to context as today's ISO date.
6. Load `RECONSTRUCTION.md.j2` from the templates directory
   (`Path(__file__).parent.parent / "templates" / "RECONSTRUCTION.md.j2"`).
7. Render the template with the extracted context.
8. Write to `<project_dir>/docs/RECONSTRUCTION.md`.
   - If the file already exists and `--force` is not set, prompt: "docs/RECONSTRUCTION.md already exists. Overwrite? [y/N]". Abort if user declines.
9. Print: `  Written docs/RECONSTRUCTION.md — fill in scores and justifications, then share with the original team.`

The output file (`docs/RECONSTRUCTION.md`) is capital — distinct from `docs/reconstruction.md`
(the brief). Add `docs/RECONSTRUCTION.md` to the DEFAULT_DENY list in `bootstrap.py` (same
pattern as `docs/reconstruction.md`):
```python
"Edit(docs/RECONSTRUCTION.md)",
"Write(docs/RECONSTRUCTION.md)",
```

**SKILL.md:** Add a `/anchor:pairmode score` section documenting the command, inputs, and outputs.

**Tests — `tests/pairmode/test_score.py`** (new file):
- `score` with valid brief: `docs/RECONSTRUCTION.md` is created.
- Output contains conviction heading from brief (e.g., `### Conviction: ...`).
- Output contains comparison rubric dimension name from brief.
- Output contains `## Summary verdict`.
- `--force` overwrites existing file without prompting.
- Existing file without `--force`: prompts; abort on "n" leaves file unchanged.
- Path traversal guard: non-directory or too-shallow path → non-zero exit.
- Missing brief file (no `--brief`, no `docs/reconstruction.md`): non-zero exit with message.

---

### Story 14.1 — `reconstruction-agent.md.j2`: agent definition template

**Acceptance criterion:** `skills/pairmode/templates/agents/reconstruction-agent.md.j2` exists.
It is a complete agent definition that a reconstruction agent can use to guide its work: reading
the brief, building, scoring, and handing back findings. Tests pass.

**Instructions:**

Create `skills/pairmode/templates/agents/reconstruction-agent.md.j2` with this structure:

```jinja2
---
description: Reconstruction agent for {{ project_name }}. Works from docs/reconstruction.md to produce a competing implementation and RECONSTRUCTION.md scoring report.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Reconstruction Agent — {{ project_name }}

You are a blank-slate reconstruction agent. You have been given:
- `docs/reconstruction.md` — the ideology brief for {{ project_name }}
- `docs/RECONSTRUCTION.md` — a partially-filled scoring report (run `/anchor:pairmode score` to generate it)

Your job is to produce a complete, working implementation of {{ project_name }} that expresses
the ideology in `docs/reconstruction.md`, then fill in `docs/RECONSTRUCTION.md` with honest
scores and justifications.

## Phase 1 — Read the brief

Read `docs/reconstruction.md` in full before writing any code. Pay particular attention to:
- **Non-negotiable ideology / Convictions** — these are the aesthetic and architectural beliefs
  you must express, not just implement. Every significant design decision should be traceable
  to one of these convictions.
- **Non-negotiable ideology / Constraints** — hard rules that must never be violated.
- **What must survive any implementation** — the core interfaces and behaviors the original
  team considers load-bearing.
- **What you are free to change** — explicit permission to diverge. Use it.
- **What you should question** — the original team's own doubts. These are invitations to improve.
- **Comparison rubric** — how your implementation will be evaluated.

## Phase 2 — Plan before building

Before writing any code, write a brief plan (can be inline notes):
- Which convictions are most constraining for your architecture choices?
- Where will you deliberately diverge? Which conviction supports each divergence?
- Which "should question" items will you improve?

## Phase 3 — Build

Build the implementation. As you work:
- If you make a design choice that diverges from the fingerprints, note it.
- If you improve something from the "should question" list, note how and why.
- You are not trying to clone the original — you are expressing the same ideology.

## Phase 4 — Fill in the scoring report

When your implementation is complete, fill in `docs/RECONSTRUCTION.md`:
- For each conviction: did you express it? Where? Any deliberate departures?
- For each constraint: how does your implementation satisfy it?
- For each rubric dimension: honest score with concrete evidence.
- For each "should question" item: what did you do and why?
- Divergences section: list significant differences from the original fingerprints.
- Summary verdict: overall alignment, recommended use, key insight for the original team.

## Constraints

- Do not ask the original team for implementation details — work only from the brief.
- Do not read the original codebase unless it is explicitly provided alongside this brief.
- Your divergences are the point of the exercise. Do not apologise for them.
- The scoring report must be honest. A "Below original" score with good justification is
  more valuable than an inflated score.
```

**Tests — `tests/pairmode/test_templates.py`:**
- Render `agents/reconstruction-agent.md.j2` with `project_name="TestProject"`: renders without error.
- Output contains `## Phase 1 — Read the brief`.
- Output contains `## Phase 4 — Fill in the scoring report`.
- Output contains `TestProject` in the title.
- Output contains `allowed-tools` frontmatter line.

---

### Story 14.2 — Wire reconstruction agent into bootstrap scaffold

**Acceptance criterion:** `bootstrap.py` generates `.claude/agents/reconstruction-agent.md`
as part of the standard scaffold (alongside builder.md, reviewer.md, etc.). Agent files
respect the existing skip-if-present / `--force-agents` logic. Tests pass.

**Instructions:**

In `bootstrap.py`, add `reconstruction-agent.md.j2` to the `AGENT_TEMPLATES` list (or
equivalent structure) alongside the existing five agent templates:

```python
("agents/reconstruction-agent.md.j2", ".claude/agents/reconstruction-agent.md"),
```

The agent file is subject to the same skip-if-present / `--force-agents` logic as all other
agent files — do not overwrite on re-bootstrap unless `--force-agents` is passed.

**SKILL.md:** Update the bootstrap outputs list to include `reconstruction-agent.md`.

**Tests — `tests/pairmode/test_bootstrap.py`:**
- Fresh bootstrap: `.claude/agents/reconstruction-agent.md` is created.
- Re-bootstrap without `--force-agents`: existing reconstruction-agent.md is not overwritten.
- Re-bootstrap with `--force-agents`: reconstruction-agent.md is overwritten.
- Content of generated file contains `## Phase 1 — Read the brief`.

---

### Story 14.3 — Fix MEDIUM security finding: constrain `--brief` path in score.py

**Acceptance criterion:** When `--brief` is supplied, `score.py` verifies that the resolved
brief path is contained within `project_dir` (the resolved project directory). An out-of-scope
`--brief` path aborts with a clear error. Tests pass.

**Instructions:**

The Phase 14 security auditor noted (MEDIUM) that `score.py` accepts `--brief` pointing to
any readable file on the filesystem, inconsistent with the sibling guard discipline where all
read paths are derived from the resolved project directory.

After resolving `brief_path` from the `--brief` option (or the default), add a containment
check:

```python
# If --brief was explicitly supplied (not the default), ensure it is within project_dir
if brief_option is not None:
    try:
        brief_path.resolve().relative_to(resolved)
    except ValueError:
        click.echo(f"Error: --brief path must be within the project directory ({resolved})", err=True)
        raise SystemExit(1)
```

Note: the default path (`resolved / "docs" / "reconstruction.md"`) is always within
`project_dir` by construction, so the guard only applies to an explicitly supplied `--brief`.
The Click option name in the function signature may differ — read the code and adjust.

No other changes.

**Tests — `tests/pairmode/test_score.py`:**
- `--brief` pointing outside `project_dir` (e.g., a file in a sibling temp dir): non-zero exit
  with error message mentioning `project directory`.
- `--brief` pointing to a file inside `project_dir`: still works (regression).

---

⚙️ DEVELOPER ACTION — Re-bootstrap anchor after Story 14.3

After 14.3 passes review, re-bootstrap anchor's own pairmode scaffold to generate
`.claude/agents/reconstruction-agent.md`:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/bootstrap.py \
  --project-dir . --force-agents --yes
git add .claude/agents/reconstruction-agent.md && git commit -m "docs: add reconstruction-agent.md from Phase 14 scaffold update"
```

Tag: `cp14-reconstruction-agent-tooling`
