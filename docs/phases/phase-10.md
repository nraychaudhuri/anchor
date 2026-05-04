## Phase 10 — Ideology Capture Infrastructure

Pairmode's highest-value use is as an ideology capture system: a way to preserve the intent of
a working prototype in a form that can generate any implementation. Today pairmode captures
what (brief.md) and how (architecture.md), but not **why the builder made the tradeoffs they
made**, what they believe about software, or what a reconstruction agent must preserve versus
what it is free to improve.

Phase 10 builds the infrastructure for that capture. Six stories, in dependency order:

1. The template and scaffold integration (10.0)
2. The brief.md upgrade (10.1)
3. The reviewer enforcement hook (10.2)
4. The intent-reviewer's ideology drift check (10.3)
5. Guided capture at bootstrap time (10.4)
6. Automated staleness detection in audit (10.5)

Prerequisites: Phase 9 complete and tagged cp9. All Phase 9 bugs resolved.

---

### Story 10.0 — ideology.md.j2: template creation and bootstrap integration

**Acceptance criterion:** `skills/pairmode/templates/docs/ideology.md.j2` exists with the
full section structure (core convictions, value hierarchy, accepted constraints, prototype
fingerprints, reconstruction guidance, comparison basis). Bootstrap writes `docs/ideology.md`
to new projects. Existing projects with `docs/ideology.md` present are not overwritten without
confirmation. Tests pass.

**Instructions:**

The template already exists at `skills/pairmode/templates/docs/ideology.md.j2` — it was
written as part of the Phase 10 planning. Read it before starting. Do not recreate it;
wire it into bootstrap.

**Part A — Add to bootstrap SCAFFOLD_FILES:**

In `skills/pairmode/scripts/bootstrap.py`, add to the `SCAFFOLD_FILES` list:

```python
("docs/ideology.md", "docs/ideology.md.j2"),
```

Position it after `("docs/brief.md", "docs/brief.md.j2")`.

The template context must include `project_name` at minimum. All other ideology variables
(`convictions`, `value_hierarchy`, `constraints`, `fingerprints`, `must_preserve`,
`should_question`, `free_to_change`, `comparison_dimensions`) default to empty lists —
bootstrap writes a well-formed placeholder document, not a blank file.

**Part B — Protect in DEFAULT_DENY:**

Add to `DEFAULT_DENY` in `bootstrap.py`:

```python
"Edit(docs/ideology.md)",
"Write(docs/ideology.md)",
```

Ideology is an operator document. Builders must not modify it mid-story.

**Part C — Add to SKILL.md outputs:**

Update the bootstrap Outputs section in `skills/pairmode/SKILL.md` to list `docs/ideology.md`.

**Tests — `tests/pairmode/test_bootstrap.py`:**
- Bootstrap renders `docs/ideology.md` from the template; file exists in output.
- `docs/ideology.md` contains `## Core convictions` heading.
- `docs/ideology.md` contains `## Reconstruction guidance` heading.
- `docs/ideology.md` contains `### Must preserve` subheading.
- Bootstrap on existing project with `docs/ideology.md` present: prompts for confirmation
  before overwriting (does not overwrite silently).
- `"Edit(docs/ideology.md)"` appears in `DEFAULT_DENY`.

**Tests — `tests/pairmode/test_templates.py`:**
- Render `docs/ideology.md.j2` with empty context: renders without error; all six `##`
  sections present; placeholder strings contain `_(not yet specified`.
- Render with `project_name="TestProject"`: title contains "TestProject".
- Render with `convictions=["We prefer X over Y"]`: convictions section contains that string,
  not the placeholder.

---

### Story 10.1 — brief.md.j2: positive ideology sections

**Acceptance criterion:** `docs/brief.md.j2` has three new sections — `## Core beliefs`,
`## Accepted tradeoffs`, and `## What a second implementation must preserve` — with Jinja2
variables and placeholder text. The existing sections are unchanged. Tests pass.

**Instructions:**

**Part A — Add to `docs/brief.md.j2`:**

After `## Why it exists` and before `## Constraints`, insert:

```jinja2
---

## Core beliefs

> What does this project believe? State convictions as positive claims.
> These are the values that shaped the design — what the project prefers and why.

{{ core_beliefs if core_beliefs else "_(not yet specified — what does this project believe about how software should be built? What does it value over what?)_" }}

---

## Accepted tradeoffs

> Decisions that had a real cost. What was given up, and why the exchange was worth it.
> A second implementation should understand what alternatives were considered and rejected.

{{ accepted_tradeoffs if accepted_tradeoffs else "_(not yet specified — what did the project explicitly give up? What was the rationale?)_" }}
```

After `## Not in scope` and before `## Operator contact`, insert:

```jinja2
---

## What a second implementation must preserve

> The irreducible requirements. An implementation that violates these is not this project.
> Everything else is negotiable.

{{ must_preserve if must_preserve else "_(not yet specified — which values, constraints, or behaviors must survive across any implementation of this project?)_" }}
```

**Part B — Add variables to bootstrap context:**

In `bootstrap.py`, add to the template context dict:

```python
"core_beliefs": "",
"accepted_tradeoffs": "",
"must_preserve": "",
```

**Part C — Audit section coverage:**

`docs/brief.md` is in `SCAFFOLD_FILES` in `audit.py` (added in Story 8.6). Extend the
expected sections list so audit checks for `## Core beliefs` and
`## What a second implementation must preserve`. If either heading is absent: MISSING section.
If present but containing only placeholder text: STALE PLACEHOLDER.

**Tests — `tests/pairmode/test_templates.py`:**
- Render `docs/brief.md.j2` with empty context: `## Core beliefs` present;
  `## Accepted tradeoffs` present; `## What a second implementation must preserve` present.
- Render with `core_beliefs="We prefer X."`: section body contains that text, not placeholder.
- Render with empty `core_beliefs`: placeholder contains `_(not yet specified`.
- Existing headings still present: `## What this project produces`, `## Why it exists`,
  `## Constraints`, `## Not in scope`.

**Tests — `tests/pairmode/test_audit.py`:**
- `docs/brief.md` missing `## Core beliefs` → MISSING section finding.
- `docs/brief.md` with `## Core beliefs` containing placeholder text → STALE PLACEHOLDER.
- `docs/brief.md` with `## Core beliefs` containing real content → clean.

---

### Story 10.2 — reviewer.md.j2: ideology alignment checklist item

**Acceptance criterion:** `skills/pairmode/templates/agents/reviewer.md.j2` contains a new
checklist item **IDEOLOGY ALIGNMENT** as item 5, after DOCUMENTATION CURRENCY. Tests pass.

**Instructions:**

**Part A — Add checklist item to `reviewer.md.j2`:**

After the `**4. DOCUMENTATION CURRENCY**` block, add:

```markdown
**5. IDEOLOGY ALIGNMENT**

Before running this check, read `docs/ideology.md` in full. If the file does not exist,
skip this check and record: `IDEOLOGY ALIGNMENT — SKIPPED: docs/ideology.md not found (LOW)`.

Check three things in sequence:

**5a. Conviction consistency**
For each conviction in `## Core convictions`: does the diff introduce any pattern that
contradicts it?
- PASS: Diff is neutral or aligned with all stated convictions.
- FAIL (MEDIUM): Diff contradicts a conviction without justification in the story spec.

**5b. Constraint rationale preservation**
For each constraint in `## Accepted constraints` touched or adjacently affected by the diff:
does the implementation respect the rationale, not just the rule letter?
- PASS: Constrained areas respected. If modified, story spec stated a reason.
- FAIL (HIGH): Diff creates a path that routes around the constraint's intent.

**5c. Fingerprint awareness**
For each entry in `## Prototype fingerprints` marked "No" or "Conditional" under
"Free to change?": is any such pattern altered by this diff?
- PASS: No fingerprint-marked patterns changed, or change matches stated changeability.
- FAIL (LOW): Pattern marked "No" changed without acknowledgment in story spec.

**Result:**
- Any HIGH (5b) → FAIL — IDEOLOGY ALIGNMENT (HIGH)
- Any MEDIUM (5a), no HIGH → FAIL — IDEOLOGY ALIGNMENT (MEDIUM)
- Only LOW (5c) → PASS with note
- `docs/ideology.md` absent → PASS with note (LOW)
```

**Part B — Add to UNIVERSAL_CHECKLIST_ITEMS in bootstrap.py:**

```python
{
    "name": "IDEOLOGY ALIGNMENT",
    "description": "Does this implementation express the project ideology? Check docs/ideology.md.",
    "severity": "HIGH",
},
```

**Tests — `tests/pairmode/test_templates.py`:**
- Render `agents/reviewer.md.j2`; assert `IDEOLOGY ALIGNMENT` present.
- Render; assert `5a.`, `5b.`, `5c.` sub-checks present.
- Render; assert `docs/ideology.md` referenced.
- Render; assert `DOCUMENTATION CURRENCY` still present (regression).
- Render; assert `PROTECTED FILES`, `STORY SCOPE`, `BUILD GATE` still present (regression).

**Tests — `tests/pairmode/test_bootstrap.py`:**
- `UNIVERSAL_CHECKLIST_ITEMS` contains entry with `"name": "IDEOLOGY ALIGNMENT"`.

---

### Story 10.3 — intent-reviewer.md.j2: ideology drift check

**Acceptance criterion:** `skills/pairmode/templates/agents/intent-reviewer.md.j2` includes
an **IDEOLOGY DRIFT** section in its review output format. Tests pass.

**Instructions:**

**Part A — Add ideology reading step:**

In `## Before reviewing`, add after the last numbered step:

```markdown
6. Read `docs/ideology.md` in full. Note core convictions, value hierarchy, and accepted
   constraints. You will check phase-level drift against these after reviewing individual
   stories. If the file does not exist, note its absence and skip the ideology drift check.
```

**Part B — Add ideology drift to design pivot detection:**

In `## Design pivot detection`, add:

```markdown
**Ideology drift** — Accumulated choices across the phase that trend away from a stated
conviction or undermine a stated constraint. Individual stories may each be fine; the phase
as a whole may be drifting. Look for:
- A conviction stated in `docs/ideology.md` absent from every implementation choice in this
  phase (never expressed, possibly forgotten)
- A constraint respected in isolation but whose surrounding code makes future violations
  more likely
- A prototype fingerprint marked "No" quietly eroded across multiple stories
```

**Part C — Add IDEOLOGY DRIFT to output format:**

After `DOWNSTREAM RISKS`, add:

```markdown
IDEOLOGY DRIFT
  [If docs/ideology.md exists and drift detected:]
  Conviction: "[conviction text]"
    Finding: [how the phase trends against this conviction]
    Severity: HIGH / MEDIUM / LOW

  [If no drift:]
  No ideology drift detected. Phase is consistent with docs/ideology.md.

  [If docs/ideology.md absent:]
  docs/ideology.md not found — ideology drift check skipped.
  Recommendation: run ideology capture for this project (Phase 10 bootstrap).
```

Add to `RECOMMENDED DOC EDITS`:

```markdown
  docs/ideology.md:
    [If any conviction proved unworkable or needs refinement]
    Section "[name]": [exact change — add, update, or mark outdated]
    [If ideology held: "No ideology.md edits recommended."]
```

**Tests — `tests/pairmode/test_templates.py`:**
- Render `agents/intent-reviewer.md.j2`; assert `IDEOLOGY DRIFT` present in output format.
- Render; assert step 6 (`docs/ideology.md`) present in `## Before reviewing`.
- Render; assert `Ideology drift` present in design pivot detection.
- Render; assert `docs/ideology.md` in `RECOMMENDED DOC EDITS`.
- Regression: `STORY ALIGNMENT`, `PIVOTS AND CONCERNS`, `DOWNSTREAM RISKS`,
  `RECOMMENDED DOC EDITS` all still present.

---

### Story 10.4 — Bootstrap: guided ideology capture mode

**Acceptance criterion:** Bootstrap in TTY mode prompts for core convictions, value hierarchy,
and constraints before writing `docs/ideology.md`. Non-TTY writes a placeholder with a
warning. `--ideology-skip`, `--conviction`, `--constraint` flags work correctly. Tests pass.

**Known gap (intent review finding):** When `_ideology_capture_flow()` returns a non-empty
`must_preserve` list and it is merged into the shared context dict, `brief.md.j2` receives a
Python list where it expects a string, rendering as `['item']` instead of `item`. This only
affects the TTY interactive path. Fix: join the list to a string before populating the
brief.md context, or use separate keys. See architecture.md "Pairmode non-negotiables".

**Instructions:**

**Part A — `_ideology_capture_flow()` in `bootstrap.py`:**

```python
def _ideology_capture_flow() -> dict:
    """Prompt the developer for ideology content. Returns template context dict."""
```

Four prompts, each skippable with blank input:

**Prompt 1 — Convictions (repeat up to 3):**
```
Ideology capture — core conviction #1
What does this project believe? (e.g. "we prefer X over Y because Z")
Enter conviction or press Enter to skip:
```
Stop when blank input received or 3 convictions collected.

**Prompt 2 — Value hierarchy:**
```
Value hierarchy — top entry
When two values conflict, which wins?
Enter or press Enter to skip:
```

**Prompt 3 — Key constraint:**
```
Accepted constraint — most important rule
What must this system never do?
Enter constraint rule or press Enter to skip:
```

**Prompt 4 — Must preserve:**
```
Reconstruction — what must survive any implementation?
Enter or press Enter to skip:
```

Return dict with keys: `convictions` (list), `value_hierarchy` (list), `constraints` (list of
dicts with `name` and `rule`), `must_preserve` (list). Empty lists for blank answers.

**Part B — Wire into main flow:**

After context-building, before scaffold file writes:

```python
if sys.stdin.isatty() and not ideology_skip:
    ideology_context = _ideology_capture_flow()
else:
    ideology_context = {}
    if not ideology_skip and not any([conviction, constraint]):
        click.echo(
            "warning: non-interactive mode — docs/ideology.md will be written as "
            "placeholder.\n"
            "         Pass --conviction or --constraint flags to populate, "
            "or edit docs/ideology.md after bootstrap.",
            err=True,
        )
```

Merge `ideology_context` into template context before rendering `docs/ideology.md.j2`.

**Part C — CLI flags:**

```python
@click.option("--ideology-skip", is_flag=True, default=False,
              help="Skip guided ideology capture; write placeholder ideology.md.")
@click.option("--conviction", multiple=True,
              help="Core conviction (repeatable). Bypasses TTY prompt.")
@click.option("--constraint", multiple=True,
              help="Key constraint rule (repeatable). Bypasses TTY prompt.")
```

When `--conviction` or `--constraint` flags passed, use them instead of prompting.

**Part D — SKILL.md:**

Update bootstrap section with new flags and note about TTY guided capture.

**Tests — `tests/pairmode/test_bootstrap.py`:**
- `--ideology-skip`: ideology.md written with placeholders; no prompt raised.
- `--conviction "we prefer X over Y"`: ideology.md contains that conviction.
- `--constraint "never write state from hooks"`: ideology.md contains that constraint.
- Multiple `--conviction` flags: all appear in rendered ideology.md.
- Non-TTY without flags: warning to stderr; ideology.md written with placeholder.
- `_ideology_capture_flow()` with all-empty input: returns dict with empty lists, no crash.

---

### Story 10.5 — Audit: detect stale ideology

**Acceptance criterion:** `audit.py` reports `STALE PLACEHOLDER` when `docs/ideology.md`
exists but all sections are placeholder-only. Reports `MISSING` when absent. Reports clean
when at least one section has real content. Tests pass.

**Instructions:**

**Part A — Staleness check in `audit.py`:**

```python
IDEOLOGY_PLACEHOLDER_MARKER = "_(not yet specified"
IDEOLOGY_REQUIRED_SECTIONS = [
    "## Core convictions",
    "## Value hierarchy",
    "## Accepted constraints",
    "## Prototype fingerprints",
    "## Reconstruction guidance",
    "## Comparison basis",
]

def _check_ideology_staleness(project_dir: Path) -> str | None:
    """None if absent, 'STALE' if all placeholder, 'OK' if real content found."""
```

Logic:
1. Return `None` if `docs/ideology.md` does not exist.
2. Split file into sections by `##` headings.
3. For each required section: check whether body contains any non-placeholder, non-empty,
   non-HTML-comment line.
4. Placeholder: line strips to start with `_(not yet specified`.
5. HTML comment lines (inside `<!-- -->`) are ignored.
6. All required sections placeholder-only → `"STALE"`.
7. At least one section with real content → `"OK"`.

Wire into `audit()`:
- Absent → MISSING finding.
- `"STALE"` → STALE PLACEHOLDER finding with recommendation to run guided ideology capture.
- `"OK"` → no finding.

Ensure `docs/ideology.md` is NOT in `SCAFFOLD_FILES` or `EXISTENCE_CHECK_FILES` — its
comparison is handled entirely by `_check_ideology_staleness()`.

**Part B — Audit output:**

```
STALE PLACEHOLDER
  ⚠ docs/ideology.md: all sections contain placeholder text
    Recommendation: run bootstrap in TTY to trigger guided ideology capture,
    or edit docs/ideology.md directly.
```

**Part C — SKILL.md:**

Add STALE PLACEHOLDER note to the `## /anchor:pairmode audit` section.

**Tests — `tests/pairmode/test_audit.py`:**
- `docs/ideology.md` missing: MISSING finding.
- All placeholder sections: STALE PLACEHOLDER finding.
- One section with real content: no staleness finding.
- Fully populated: no staleness finding.
- `_check_ideology_staleness()` mixed file: returns `"OK"`.
- Regression: other findings unaffected.

---

⚙️  DEVELOPER ACTION — Populate anchor's own ideology.md after Phase 10 bootstrap

After Story 10.0 passes review:

1. Bootstrap writes `docs/ideology.md` to anchor (or copy template and fill in directly).
2. Populate `## Core convictions` with anchor's beliefs about AI-assisted development.
3. Populate `## Accepted constraints` with rationale for each DEFAULT_DENY entry.
4. Populate `## Reconstruction guidance` with what must survive any re-implementation.
5. Run audit: confirm no STALE PLACEHOLDER finding.
6. Tag: `cp10-ideology-infrastructure`
