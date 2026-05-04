# anchor — Phase 11: Brief hygiene and reconstruction workflow

← [Phase 10: Ideology Capture Infrastructure](phase-10.md)

## Goal

Fix must_preserve type collision; populate anchor's brief.md; build the reconstruction
document system that turns captured ideology into a handoff prompt for an independent
implementation agent.

Phase 10 shipped ideology capture but left two gaps: a type collision in the `must_preserve`
bootstrap context variable, and no mechanism for a blank-slate agent to use the ideology
artifacts to produce an independent implementation for comparison. This phase closes both.

Four stories in dependency order:

1. Fix `must_preserve` type collision (11.0)
2. Reconstruction document template (11.1)
3. Bootstrap integration — write `docs/reconstruction.md` (11.2)
4. `/anchor:pairmode reconstruct` refresh command (11.3)

Prerequisites: Phase 10 complete and tagged cp10. `docs/ideology.md` populated for anchor.

---

### Story 11.0 — Fix `must_preserve` dual-type collision in bootstrap

**Acceptance criterion:** When `_ideology_capture_flow()` returns a non-empty `must_preserve`
list, `docs/brief.md` renders the items as readable prose, not as a Python list repr.
`docs/ideology.md` continues to render the list correctly via `{% for %}`. Tests pass.

**Instructions:**

The collision: `bootstrap.py` uses a single shared context dict for all template renders.
`brief.md.j2` expects `must_preserve` as a string; `ideology.md.j2` expects it as a list.
When `_ideology_capture_flow()` returns a non-empty list and it is merged into context,
`brief.md.j2` renders `['item']` instead of `item`.

**Part A — Separate the keys in bootstrap context:**

In `bootstrap.py`, rename the brief.md key to `must_preserve_str` and keep the ideology
key as `must_preserve`. Update context construction:

```python
# For brief.md.j2 — string form
"must_preserve_str": "",

# For ideology.md.j2 — list form
"must_preserve": [],
```

When `ideology_context` is merged, derive `must_preserve_str` from the list:
```python
mp_list = ideology_context.get("must_preserve", [])
context["must_preserve"] = mp_list
context["must_preserve_str"] = "\n".join(f"- {item}" for item in mp_list) if mp_list else ""
```

**Part B — Update `docs/brief.md.j2`:**

Replace the `must_preserve` variable reference with `must_preserve_str`:

```jinja2
{{ must_preserve_str if must_preserve_str else "_(not yet specified — which values, constraints, or behaviors must survive across any implementation of this project?)_" }}
```

**Part C — Update architecture.md non-negotiable:**

Replace the Phase 10 must_preserve non-negotiable with the resolved contract:

```
- Template context uses separate keys for brief.md and ideology.md must-preserve content:
  `must_preserve_str` (newline-joined string) for `brief.md.j2`; `must_preserve` (list)
  for `ideology.md.j2`. Do not merge these back into a single key.
```

**Tests — `tests/pairmode/test_bootstrap.py`:**
- `_ideology_capture_flow()` returning `must_preserve=["item one", "item two"]`: rendered
  `brief.md` contains `- item one` and `- item two`, not `['item one', 'item two']`.
- `docs/ideology.md` still renders `must_preserve` list correctly via `{% for %}`.
- `must_preserve_str` present in bootstrap context with empty string default.
- `must_preserve` (list) present in bootstrap context with empty list default.

**Tests — `tests/pairmode/test_templates.py`:**
- Render `brief.md.j2` with `must_preserve_str="- prefer X\n- prefer Y"`: section body
  contains `prefer X`, not `['prefer X']`.
- Render `brief.md.j2` with empty `must_preserve_str`: placeholder present.
- Render `ideology.md.j2` with `must_preserve=["item"]`: `{% for %}` renders correctly.

---

⚙️  DEVELOPER ACTION — Populate anchor's `docs/brief.md` after Story 11.0

After 11.0 passes review:

1. Open `docs/brief.md` and fill in the stale placeholder sections:
   - `## What this project produces` — anchor's canonical spec + pairmode scaffold output
   - `## Why it exists` — the agent drift problem; decisions scatter without persistent memory
   - `## Core beliefs` — reference docs/ideology.md core convictions
   - `## Accepted tradeoffs` — hook-pipe-sidebar separation cost; Python-only stack
   - `## What a second implementation must preserve` — spec.json format with rationale;
     hook pipe contract; append-only lessons
2. Run audit: confirm no STALE PLACEHOLDER findings for `docs/brief.md`.
3. Commit: `docs: populate anchor docs/brief.md`

---

### Story 11.1 — Reconstruction document template

**Acceptance criterion:** `skills/pairmode/templates/docs/reconstruction.md.j2` exists with
a structured prompt that a blank-slate agent can use as its sole input to produce an
independent implementation of the project. Template renders without error with empty context.
Tests pass.

**Instructions:**

The reconstruction document is the handoff artifact that makes n-tier comparison possible.
Given this document alone (plus access to the internet and standard tools), a blank-slate
agent should be able to produce a working implementation that satisfies the project's ideology
and brief — different in form, identical in values.

Create `skills/pairmode/templates/docs/reconstruction.md.j2` with this structure:

```jinja2
# Reconstruction Brief — {{ project_name }}

> This document is the sole input for an independent reconstruction agent.
> The agent must not have access to the original source code.
> It should produce an implementation that satisfies the ideology and constraints
> recorded here — free to diverge in all other respects.

---

## What you are building

{{ reconstruction_what if reconstruction_what else "_(derive from docs/brief.md — What this project produces)_" }}

## Why it exists

{{ reconstruction_why if reconstruction_why else "_(derive from docs/brief.md — Why it exists)_" }}

---

## Non-negotiable ideology

> These convictions and constraints must be expressed in any correct implementation.
> An implementation that contradicts them is not this project.

### Convictions

{% if convictions %}
{% for conviction in convictions %}
- {{ conviction }}
{% endfor %}
{% else %}
_(no convictions recorded — populate docs/ideology.md first)_
{% endif %}

### Constraints

{% if constraints %}
{% for constraint in constraints %}
#### {{ constraint.name }}

**Rule:** {{ constraint.rule }}

**Why this constraint exists:** {{ constraint.rationale }}

{% endfor %}
{% else %}
_(no constraints recorded — populate docs/ideology.md first)_
{% endif %}

---

## What must survive any implementation

{% if must_preserve %}
{% for item in must_preserve %}
- {{ item }}
{% endfor %}
{% else %}
_(not yet specified — populate docs/ideology.md Reconstruction guidance)_
{% endif %}

---

## What you are free to change

> These are fingerprints of the original implementation, not constraints.
> You are encouraged to find better approaches.

{% if free_to_change %}
{% for item in free_to_change %}
- {{ item }}
{% endfor %}
{% else %}
_(not yet specified — populate docs/ideology.md Free to change)_
{% endif %}

---

## Comparison rubric

> After building, your implementation will be evaluated against the original on
> these dimensions. Optimise for them explicitly.

{% if comparison_dimensions %}
{% for dim in comparison_dimensions %}
- **{{ dim.name }}:** {{ dim.description }}
{% endfor %}
{% else %}
_(not yet specified — populate docs/ideology.md Comparison basis)_
{% endif %}

---

## What you should question

> The original implementation made these choices under time or knowledge constraints.
> You are encouraged to find better solutions and justify them against the convictions above.

{% if should_question %}
{% for item in should_question %}
- {{ item }}
{% endfor %}
{% else %}
_(not yet specified — populate docs/ideology.md Should question)_
{% endif %}

---

## Instructions for the reconstruction agent

1. Read this document in full before writing any code.
2. Build a working implementation that satisfies the ideology above.
3. For every non-negotiable constraint: explicitly state how your implementation satisfies it.
4. For every "should question" item: either improve on it or justify why you kept the
   original approach, citing the relevant conviction.
5. For every comparison dimension: document your approach and how it scores against the rubric.
6. Do not look at the original source code. If you have seen it, declare that before starting.
7. When done, produce a `RECONSTRUCTION.md` at your project root scoring your implementation
   against each comparison dimension.

*Generated from `docs/ideology.md` and `docs/brief.md` by `/anchor:pairmode reconstruct`.*
*Original project: {{ project_name }}*
*Generated: {{ generated_date | default("_(date not set)_") }}*
```

**Tests — `tests/pairmode/test_templates.py`:**
- Render `docs/reconstruction.md.j2` with empty context: renders without error.
- Render; assert `## What you are building` present.
- Render; assert `## Non-negotiable ideology` present.
- Render; assert `## What must survive any implementation` present.
- Render; assert `## Comparison rubric` present.
- Render; assert `## Instructions for the reconstruction agent` present.
- Render with `convictions=["We prefer X"]`: conviction appears in output.
- Render with `constraints=[{"name": "C1", "rule": "never do X", "rationale": "because Y"}]`:
  constraint name, rule, and rationale all appear.
- Render with `project_name="TestProject"`: title contains "TestProject".

---

### Story 11.2 — Bootstrap: write `docs/reconstruction.md`

**Acceptance criterion:** Bootstrap writes `docs/reconstruction.md` to new projects, populated
from ideology context. `"Edit(docs/reconstruction.md)"` and `"Write(docs/reconstruction.md)"`
added to `DEFAULT_DENY`. Existing `docs/reconstruction.md` is not silently overwritten.
Tests pass.

**Instructions:**

**Part A — Add to `SCAFFOLD_FILES` in bootstrap.py:**

```python
("docs/reconstruction.md", "docs/reconstruction.md.j2"),
```

Position after `("docs/ideology.md", "docs/ideology.md.j2")`.

**Part B — Add template context:**

The reconstruction template shares ideology variables (`convictions`, `constraints`,
`must_preserve`, `free_to_change`, `comparison_dimensions`, `should_question`) plus:

```python
"reconstruction_what": context.get("what", ""),
"reconstruction_why": context.get("why", ""),
"generated_date": datetime.date.today().isoformat(),
```

**Part C — Protect in DEFAULT_DENY:**

```python
"Edit(docs/reconstruction.md)",
"Write(docs/reconstruction.md)",
```

**Part D — Update SKILL.md:**

Add `docs/reconstruction.md` to bootstrap Outputs section.

**Tests — `tests/pairmode/test_bootstrap.py`:**
- Bootstrap renders `docs/reconstruction.md`; file exists in output.
- `docs/reconstruction.md` contains `## Non-negotiable ideology`.
- `docs/reconstruction.md` contains `## Instructions for the reconstruction agent`.
- `"Edit(docs/reconstruction.md)"` in `DEFAULT_DENY`.
- Existing `docs/reconstruction.md` prompts for confirmation (not silently overwritten).
- `--conviction "we prefer X"`: conviction appears in `docs/reconstruction.md`.

---

### Story 11.3 — `/anchor:pairmode reconstruct` command

**Acceptance criterion:** `skills/pairmode/scripts/reconstruct.py` reads `docs/ideology.md`
and `docs/brief.md` from a target project and writes (or refreshes) `docs/reconstruction.md`
without requiring a full bootstrap. `SKILL.md` documents the command. Tests pass.

**Instructions:**

**Part A — `reconstruct.py` script:**

```python
@click.command()
@click.option("--project-dir", type=click.Path(file_okay=False), default=".",
              help="Target project directory.")
@click.option("--force", is_flag=True, default=False,
              help="Overwrite existing docs/reconstruction.md without prompting.")
def reconstruct(project_dir: str, force: bool) -> None:
    """Refresh docs/reconstruction.md from ideology.md and brief.md."""
```

Logic:
1. Resolve and validate `project_dir` (same `len(parts) >= 3` + `is_dir()` guard as
   bootstrap/audit/sync).
2. Check `docs/ideology.md` exists — exit with clear error if not.
3. Parse `docs/ideology.md`: split by `##` headings; extract content from each named
   section into the appropriate context variable. Use a plain-text parser, not regex soup —
   split on `\n## `, strip, map heading to variable name.
4. Parse `docs/brief.md` (if present): extract body of `## What this project produces`
   → `reconstruction_what`; `## Why it exists` → `reconstruction_why`. If brief.md absent,
   leave both as empty strings.
5. If `docs/reconstruction.md` exists and `--force` not passed: prompt for confirmation
   using `click.confirm`.
6. Render `docs/reconstruction.md.j2` with extracted context; write to project.
7. Print: `✓ docs/reconstruction.md written.`

The section-to-variable mapping for ideology.md:
- `## Core convictions` → parse bullet lines → `convictions` (list of strings, strip `- `)
- `## Accepted constraints` → parse `### [name]` blocks for `**Rule:**` and `**Rationale:**`
  → `constraints` (list of dicts with `name`, `rule`, `rationale`)
- `## Reconstruction guidance / ### Must preserve` → parse bullets → `must_preserve` (list)
- `## Reconstruction guidance / ### Free to change` → parse bullets → `free_to_change` (list)
- `## Reconstruction guidance / ### Should question` → parse bullets → `should_question` (list)
- `## Comparison basis` → parse `- **Name:** description` lines → `comparison_dimensions`
  (list of dicts with `name`, `description`)

**Part B — SKILL.md:**

Add `/anchor:pairmode reconstruct` section documenting the command, its inputs, and outputs.

**Tests — `tests/pairmode/test_reconstruct.py`** (new file):
- Project with populated ideology.md: `docs/reconstruction.md` written; contains conviction text.
- Project with ideology.md absent: exits non-zero with clear error.
- Project with existing reconstruction.md, no `--force`: `click.confirm` called (mock it).
- Project with existing reconstruction.md, `--force`: overwrites without confirm prompt.
- Path traversal guard: `--project-dir /` exits with error.
- brief.md `## What this project produces` body appears as `reconstruction_what` in output.
- All `## Instructions` steps present in rendered output.
- `conviction` extracted from ideology.md appears in `docs/reconstruction.md`.

---

⚙️  DEVELOPER ACTION — Run reconstruct on anchor after Story 11.3

After 11.3 passes review:

1. Run: `uv run python skills/pairmode/scripts/reconstruct.py --project-dir .`
2. Review `docs/reconstruction.md` — verify it reads as a coherent handoff prompt for a
   blank-slate agent.
3. Commit: `docs: generate anchor reconstruction brief`
4. Tag: `cp11-reconstruction-workflow`
