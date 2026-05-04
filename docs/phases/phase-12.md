# anchor — Phase 12: Reconstruction seeding and comparison scaffolding

← [Phase 11: Brief hygiene and reconstruction workflow](phase-11.md)

## Goal

Phase 11 produced `docs/reconstruction.md` — a handoff prompt for a blank-slate agent.
Phase 12 makes that handoff actionable: a scoring template reconstruction agents fill in
when done, audit staleness detection for reconstruction.md, the ability to seed a new
pairmode project directly from a reconstruction brief, and a minor security consistency
fix carried forward from the Phase 11 audit.

Four stories:

1. Fix LOW guard condition order in reconstruct.py (12.0)
2. RECONSTRUCTION.md.j2 scoring template — what reconstruction agents produce (12.1)
3. Audit: detect stale or missing reconstruction.md (12.2)
4. Bootstrap `--from-reconstruction` flag — seed a new project from a reconstruction brief (12.3)

Prerequisites: Phase 11 complete and tagged cp11. `docs/reconstruction.md` generated for anchor.

---

### Story 12.0 — Fix LOW security finding: guard condition order in reconstruct.py

**Acceptance criterion:** The path traversal guard in `reconstruct.py` uses the same condition
order as `bootstrap.py`, `audit.py`, and `sync.py`. Tests pass.

**Instructions:**

The Phase 11 security auditor noted (LOW) that `reconstruct.py` checks `len(resolved.parts) < 3`
before `not resolved.is_dir()`, while all three sibling scripts check `not is_dir()` first.

In `skills/pairmode/scripts/reconstruct.py`, find the path traversal guard and reorder:

```python
# Before (current):
if len(resolved.parts) < 3 or not resolved.is_dir():

# After (consistent with siblings):
if not resolved.is_dir() or len(resolved.parts) < 3:
```

No other changes. Existing guard tests cover the behaviour — no new tests required.

**Tests:** Run full suite; assert existing reconstruct path traversal test still passes.

---

### Story 12.1 — RECONSTRUCTION.md.j2: scoring template for reconstruction agents

**Acceptance criterion:** `skills/pairmode/templates/RECONSTRUCTION.md.j2` exists — a template
reconstruction agents fill in when they complete their implementation, scoring themselves
against the original's comparison rubric. Tests pass.

**Instructions:**

This is the document a reconstruction agent *produces* (not the brief it *receives*).
Create `skills/pairmode/templates/RECONSTRUCTION.md.j2` with this structure:

```jinja2
# Reconstruction Report — {{ project_name }}

> Completed by a blank-slate reconstruction agent working from `docs/reconstruction.md`.
> This report scores the implementation against the original's comparison rubric.

**Reconstruction date:** {{ reconstruction_date | default("_(not set)_") }}
**Original project:** {{ project_name }}
**Stack used:** {{ stack | default("_(not specified)_") }}

---

## Ideology adherence

> For each conviction in the reconstruction brief: did this implementation express it?

{% if convictions %}
{% for conviction in convictions %}
### Conviction: {{ conviction[:80] }}{% if conviction|length > 80 %}...{% endif %}

**Expressed?** Yes / No / Partially

**How:** _(describe where and how this conviction is expressed in the implementation)_

**Deviations:** _(any deliberate departures, with justification citing another conviction)_

{% endfor %}
{% else %}
_(no convictions recorded in reconstruction brief)_
{% endif %}

---

## Constraint compliance

> For each non-negotiable constraint: how does this implementation satisfy it?

{% if constraints %}
{% for constraint in constraints %}
### {{ constraint.name }}

**Rule:** {{ constraint.rule }}

**Satisfied?** Yes / No / Conditionally

**How:** _(describe the specific design or implementation that satisfies this constraint)_

{% endfor %}
{% else %}
_(no constraints recorded in reconstruction brief)_
{% endif %}

---

## Comparison rubric scores

> For each dimension in the reconstruction brief: score and justify.

{% if comparison_dimensions %}
{% for dim in comparison_dimensions %}
### {{ dim.name }}

**Description:** {{ dim.description }}

**Score:** [ ] Exceeds original  [ ] On par  [ ] Below original  [ ] Not assessed

**Justification:** _(concrete evidence from the implementation)_

{% endfor %}
{% else %}
_(no comparison dimensions recorded in reconstruction brief)_
{% endif %}

---

## Should-question resolutions

> For each item flagged as "should question": did you improve it or keep it?

{% if should_question %}
{% for item in should_question %}
### {{ item[:80] }}{% if item|length > 80 %}...{% endif %}

**Decision:** Improved / Kept as-is / Not applicable

**Rationale:** _(if improved: what you did and which conviction supports it.
If kept: why the original approach was correct.)_

{% endfor %}
{% else %}
_(no should-question items in reconstruction brief)_
{% endif %}

---

## Divergences from original

> Significant implementation choices that differ from the original fingerprints.
> These are not defects — they are the point of the exercise.

_(list each significant divergence, the reasoning, and the conviction it expresses)_

---

## Summary verdict

**Overall alignment with ideology:** Strong / Moderate / Weak

**Recommended for:** Backport review / Stack porting / Leapfrog / Archive

**Key insight for original team:** _(one paragraph — what the original can learn from this
reconstruction, or what validates the original approach)_
```

**Tests — `tests/pairmode/test_templates.py`:**
- Render `RECONSTRUCTION.md.j2` with empty context: renders without error.
- Render; assert `## Ideology adherence` present.
- Render; assert `## Constraint compliance` present.
- Render; assert `## Comparison rubric scores` present.
- Render; assert `## Summary verdict` present.
- Render with `convictions=["We prefer X over Y"]`: conviction heading present.
- Render with `comparison_dimensions=[{"name": "Decision fidelity", "description": "desc"}]`:
  dimension name and description present.
- Render with `project_name="TestProject"`: title contains "TestProject".

---

### Story 12.2 — Audit: detect stale or missing reconstruction.md

**Acceptance criterion:** `audit.py` reports `MISSING` when `docs/reconstruction.md` is absent
and `STALE PLACEHOLDER` when it exists but contains only placeholder text. Reports clean when
real content is present. A completed scoring report (no "Generated from" footer) is not flagged.
Tests pass.

**Instructions:**

**Part A — Staleness check in `audit.py`:**

```python
RECONSTRUCTION_PLACEHOLDER_MARKER = "_(not set)_"
RECONSTRUCTION_REQUIRED_SECTIONS = [
    "## Ideology adherence",
    "## Constraint compliance",
    "## Comparison rubric scores",
    "## Summary verdict",
]

def _check_reconstruction_staleness(project_dir: Path) -> str | None:
    """None if absent, 'STALE' if generated+placeholder, 'OK' otherwise."""
```

Logic:
1. Return `None` if `docs/reconstruction.md` does not exist.
2. Read the file. If it does NOT contain the line
   `"Generated from \`docs/ideology.md\`"` in its footer, it is a filled-in scoring
   report — return `"OK"` immediately. Do not flag completed reports as stale.
3. If it IS a generated brief: split by `##` headings; check each required section for
   non-placeholder, non-empty, non-comment content (same logic as ideology staleness check).
4. All sections placeholder-only → `"STALE"`.
5. At least one real content line → `"OK"`.

Wire into `audit()`:
- `None` (absent) → MISSING finding with recommendation to run `/anchor:pairmode reconstruct`.
- `"STALE"` → STALE PLACEHOLDER finding.
- `"OK"` → no finding.

`docs/reconstruction.md` must NOT be in `SCAFFOLD_FILES` or `EXISTENCE_CHECK_FILES`.

**Part B — SKILL.md:**

Add reconstruction staleness note to the `/anchor:pairmode audit` section.

**Tests — `tests/pairmode/test_audit.py`:**
- `docs/reconstruction.md` missing: MISSING finding with reconstruct recommendation.
- Generated reconstruction.md (has footer, all placeholder sections): STALE PLACEHOLDER.
- Generated reconstruction.md with real content in one section: no finding.
- Completed scoring report (no "Generated from" footer): `_check_reconstruction_staleness`
  returns `"OK"` — not flagged as stale.
- Regression: ideology.md audit findings unaffected.

---

### Story 12.3 — Bootstrap: `--from-reconstruction` flag

**Acceptance criterion:** `bootstrap.py` accepts `--from-reconstruction PATH` which reads a
`reconstruction.md` brief and pre-populates the ideology context from it, seeding a new
pairmode project without manual TTY entry. A shared `ideology_parser.py` module replaces
duplicated parsing logic in `reconstruct.py`. Tests pass.

**Instructions:**

**Part A — Extract shared parser into `ideology_parser.py`:**

Create `skills/pairmode/scripts/ideology_parser.py` with:

```python
def parse_ideology_file(path: Path) -> dict:
    """Parse docs/ideology.md (or reconstruction.md ideology sections) into context dict.

    Returns: convictions, constraints, must_preserve, free_to_change,
             should_question, comparison_dimensions, value_hierarchy (all lists).
    """
```

Extract the existing ideology/reconstruction parsing logic from `reconstruct.py` into this
module. Update `reconstruct.py` to import and call `ideology_parser.parse_ideology_file`.

The parser handles both `docs/ideology.md` and `docs/reconstruction.md` brief sections —
the `## Non-negotiable ideology / ### Convictions` structure in reconstruction.md maps to
the same output dict as `## Core convictions` in ideology.md. The parser should detect
which format it is reading by checking the first heading.

**Part B — `--from-reconstruction` flag in bootstrap.py:**

```python
@click.option("--from-reconstruction", type=click.Path(exists=True, dir_okay=False),
              default=None,
              help="Path to a reconstruction.md brief. Pre-populates ideology context.")
```

When provided:
1. Print: `  Reading reconstruction brief: [path]`
2. Call `ideology_parser.parse_reconstruction_brief(Path(from_reconstruction))` — a
   separate function that understands the reconstruction.md brief format specifically
   (sections named `## Non-negotiable ideology`, `## What must survive`, etc.).
3. Use result as `ideology_context`. Skip TTY capture and non-TTY warning entirely.

Add `parse_reconstruction_brief(path: Path) -> dict` to `ideology_parser.py`:
- Parses reconstruction.md brief sections (different heading names from ideology.md).
- Maps `## Non-negotiable ideology / ### Convictions` → `convictions`
- Maps `## Non-negotiable ideology / ### Constraints` → `constraints`
- Maps `## What must survive any implementation` → `must_preserve`
- Maps `## What you are free to change` → `free_to_change`
- Maps `## What you should question` → `should_question`
- Maps `## Comparison rubric` → `comparison_dimensions`

**Part C — SKILL.md:**

Document `--from-reconstruction` in the bootstrap section.

**Tests — `tests/pairmode/test_bootstrap.py`:**
- `--from-reconstruction path` with conviction in file: `docs/ideology.md` output contains
  that conviction.
- `--from-reconstruction` skips ideology_capture_flow (mock to assert not called).
- Regression: `--conviction` flag still works independently.

**Tests — `tests/pairmode/test_ideology_parser.py`** (new file):
- `parse_reconstruction_brief()` with one conviction: returns list with that conviction.
- `parse_reconstruction_brief()` with one constraint block: returns dict with name/rule/rationale.
- `parse_reconstruction_brief()` with must_preserve bullets: returns list.
- `parse_reconstruction_brief()` with empty file: returns empty lists without crash.
- `parse_ideology_file()` with ideology.md format: convictions extracted correctly.
- `reconstruct.py` still works after refactor (regression via existing test_reconstruct.py).

---

### Story 12.2.1 — Fix RECONSTRUCTION_REQUIRED_SECTIONS to match brief template

**Acceptance criterion:** `_check_reconstruction_staleness` returns `"OK"` for anchor's own
`docs/reconstruction.md` (which is a generated brief with real ideology content). Tests pass.
`audit.py --project-dir .` shows no STALE PLACEHOLDER finding for `docs/reconstruction.md`.

**Instructions:**

The developer action gate after Story 12.2 revealed a bug: `RECONSTRUCTION_REQUIRED_SECTIONS`
in `audit.py` lists sections from the *scoring report template* (`## Ideology adherence`,
`## Constraint compliance`, etc.) but the generated *brief* has completely different sections
(`## Non-negotiable ideology`, `## What must survive any implementation`, etc.).
Since none of the required sections exist in the brief, the function can never find real content
and always returns `"STALE"`.

Fix: update the constants in `audit.py` to use sections that actually appear in the generated
brief template (`docs/reconstruction.md.j2`):

```python
RECONSTRUCTION_REQUIRED_SECTIONS = [
    "## Non-negotiable ideology",
    "## What must survive any implementation",
    "## Comparison rubric",
]
```

Note: `"## Instructions for the reconstruction agent"` is intentionally excluded — it always
contains hardcoded non-placeholder text (the 7-step instruction block), which would cause the
staleness check to return `"OK"` for any generated brief regardless of ideology content.

Also update any test fixtures in `test_audit.py` that construct fake reconstruction.md content
to use these corrected section names (so stale-detection tests still exercise the right paths).

**Tests:** Full suite passes. `_check_reconstruction_staleness(project_dir)` returns `"OK"` for
anchor's own `docs/reconstruction.md`.

---

⚙️  DEVELOPER ACTION — Verify audit clean after Story 12.2.1

After 12.2.1 passes review:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/audit.py --project-dir .
```

Confirm no STALE PLACEHOLDER or MISSING finding for `docs/reconstruction.md`.

Tag: `cp12-reconstruction-seeding`
