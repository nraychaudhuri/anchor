# Anchor Pairmode — Phase Prompts

This file contains the complete build instructions for the pairmode feature.
The build orchestrator reads this file in full before starting any story.

---

## Phase 1 — Pairmode Skill Scaffold

**Goal:** Create the static scaffold — directory structure, SKILL.md with four commands, Jinja2
templates, and a bootstrap.py that renders static templates. By end of phase,
`/anchor:pairmode bootstrap` works but uses static templates with no spec derivation.

---

### Story 1.1 — Skill directory and SKILL.md

**Acceptance criterion:** `skills/pairmode/SKILL.md` exists with all four commands documented,
and the directory structure matches the architecture spec.

**Instructions:**

Create the following directory structure:
```
skills/pairmode/
  SKILL.md
  requirements.txt
  scripts/
    __init__.py  (empty)
  templates/
    agents/
    docs/
```

`requirements.txt` should include: `jinja2`, `click`

`SKILL.md` frontmatter:
```yaml
---
name: anchor:pairmode
description: Bootstrap, audit, sync, and manage pairmode methodology for this project.
allowed-tools: AskUserQuestion, Bash, Read, Write
---
```

The skill body should define four commands clearly:
- `/anchor:pairmode bootstrap` — scaffold a new or existing project with pairmode
- `/anchor:pairmode audit` — compare project against current canonical methodology
- `/anchor:pairmode sync` — apply delta from audit non-destructively
- `/anchor:pairmode lesson` — capture a lesson learned from this session
- `/anchor:pairmode review` — surface accumulated lessons, propose template updates

Each command section should describe: when to use it, inputs it expects, what it does,
and what it outputs.

For bootstrap: it reads `.companion/product.json` and the project's Anchor spec if available,
then generates the scaffold. It always confirms before writing files.

For audit: it reads `.companion/state.json` for `pairmode_version`, compares against
current canonical templates and applicable lessons.

For sync: it applies the delta from audit, preserving project-specific content.

For lesson: it prompts the user for trigger/problem/learning/methodology_change, writes
to `anchor/lessons/lessons.json` (in the anchor repo, not the project).

For review: it groups captured lessons by `affects` field, proposes specific template
updates, and writes approved updates to the templates.

---

### Story 1.2 — Static CLAUDE.md and CLAUDE.build.md templates

**Acceptance criterion:** `skills/pairmode/templates/CLAUDE.md.j2` and
`skills/pairmode/templates/CLAUDE.build.md.j2` render correctly with test context data
and produce output structurally identical to the canonical versions in cora/radar.

**Instructions:**

Create `templates/CLAUDE.md.j2`. Template variables:
- `{{ project_name }}` — project name
- `{{ project_description }}` — one-line description
- `{{ stack }}` — technology stack
- `{{ domain_model }}` — tenant/domain model description
- `{{ build_command }}` — how to build (e.g. `pnpm build`, `uv run pytest`)
- `{{ test_command }}` — how to run tests
- `{{ checklist_items }}` — list of dicts with `name`, `description`, `severity`
- `{{ protected_paths }}` — list of protected file patterns

The template should produce the canonical CLAUDE.md structure:
- Project context block (name, description, stack, domain model)
- Session modes section (Build mode / Review mode — verbatim from cora pattern)
- Review checklist (rendered from checklist_items)
- Review output format (severity definitions — these are universal, not templated)
- Loop-breaker mode section (universal — not templated)

Universal checklist items that must always appear regardless of checklist_items input:
- PROTECTED FILES (severity HIGH)
- STORY SCOPE (severity MEDIUM)
- BUILD GATE verification section

Create `templates/CLAUDE.build.md.j2`. Template variables:
- `{{ project_name }}`
- `{{ build_command }}`
- `{{ test_command }}`
- `{{ migration_command }}` — optional, empty string if not applicable

The template should produce the canonical CLAUDE.build.md structure matching cora's version
exactly, with the project-specific commands substituted in.

Write a test at `tests/pairmode/test_templates.py` that renders both templates with sample
context data and asserts that key structural elements are present in the output
(session modes section, review checklist header, build loop steps, checkpoint sequence).

---

### Story 1.3 — Static agent templates

**Acceptance criterion:** All five agent templates exist and render correctly with test context.

**Instructions:**

Create these templates in `skills/pairmode/templates/agents/`:
- `builder.md.j2`
- `reviewer.md.j2`
- `loop-breaker.md.j2`
- `security-auditor.md.j2`
- `intent-reviewer.md.j2`

Template variables (shared across all agent templates):
- `{{ project_name }}`
- `{{ build_command }}`
- `{{ test_command }}`
- `{{ protected_paths }}` — list of strings
- `{{ domain_isolation_rule }}` — the primary isolation invariant (e.g. "filter by workspace_id")
- `{{ checklist_items }}` — for reviewer template

Each agent template should produce output structurally identical to the cora equivalents.
The builder and reviewer templates are the most critical — they encode the methodology.

**Builder template requirements:**
- Frontmatter with `name: builder`, `description`, `tools: [Read, Write, Edit, Glob, Grep, Bash]`, `model: sonnet`
- "Before writing anything" section: read architecture.md, read story text, check protected files
- Implementation rules section (layer rules, isolation, testing — rendered from project context)
- Developer Action gates handling
- Completion report format (BUILT: Story N.X, Files changed, Tests, Build gate)
- BUILDER STUCK format for two-attempt failures

**Reviewer template requirements:**
- Frontmatter with `name: reviewer`, `description`
- "Before reviewing" section: read architecture.md, read story spec, run git diff HEAD
- Checklist section (rendered from checklist_items + universal items)
- Test run section
- PASS/FAIL decision logic (verbatim from cora — this is canonical)
- Commit format on PASS
- Revert + report format on FAIL
- "What you must not do" section

Add tests to `tests/pairmode/test_templates.py` covering agent template rendering.

---

### Story 1.4 — Static docs templates

**Acceptance criterion:** Three docs templates exist and render correctly.

**Instructions:**

Create in `skills/pairmode/templates/docs/`:
- `architecture.md.j2`
- `phase-prompts.md.j2`
- `checkpoints.md.j2`

`architecture.md.j2` template variables:
- `{{ project_name }}`, `{{ project_description }}`, `{{ stack }}`
- `{{ domain_model }}` — tenant/isolation model description
- `{{ module_structure }}` — list of dicts with `name`, `description`, `paths`
- `{{ layer_rules }}` — list of dicts with `layer`, `may_import`, `may_not_import`
- `{{ build_command }}`, `{{ test_command }}`
- `{{ protected_paths }}`
- `{{ non_negotiables }}` — list of strings (from spec, if available)

`phase-prompts.md.j2` is a minimal skeleton template. It generates a file with:
- Header and instructions
- Phase 1 section with a placeholder story 1.1 that prompts the developer to
  fill in the actual stories. Include a comment explaining the story format.

`checkpoints.md.j2` generates a minimal skeleton with:
- Header
- Placeholder for cp1 tag and acceptance criteria

These are intentionally sparse — the developer fills them in. The templates just provide
the correct structure so nothing is forgotten.

Add tests to `tests/pairmode/test_templates.py`.

---

### Story 1.5 — bootstrap.py with static rendering

**Acceptance criterion:** Running `uv run python skills/pairmode/scripts/bootstrap.py --help`
succeeds. Running it against a test project directory renders all templates and writes
the scaffold files correctly. Existing files are not overwritten without user confirmation.

**Instructions:**

Create `skills/pairmode/scripts/bootstrap.py`.

Use `click` for CLI. Entry point: `bootstrap` command with options:
- `--project-dir` (default: current directory)
- `--project-name` (optional, will prompt if missing)
- `--stack` (optional, will prompt if missing)
- `--build-command` (optional, default inferred from project files: pnpm → `pnpm build && pnpm typecheck`, uv → `uv run pytest`, else prompt)
- `--dry-run` (print what would be written, do not write)

Bootstrap reads (in order, later overrides earlier):
1. CLI flags
2. `.companion/product.json` if it exists (for project_name, spec_location)
3. Prompt for any missing required values

Bootstrap writes these files to `--project-dir` if they don't exist
(confirms before overwriting if they do):
- `CLAUDE.md` (from CLAUDE.md.j2)
- `CLAUDE.build.md` (from CLAUDE.build.md.j2)
- `.claude/agents/builder.md`
- `.claude/agents/reviewer.md`
- `.claude/agents/loop-breaker.md`
- `.claude/agents/security-auditor.md`
- `.claude/agents/intent-reviewer.md`
- `docs/architecture.md` (from docs/architecture.md.j2)
- `docs/phase-prompts.md` (skeleton)
- `docs/checkpoints.md` (skeleton)

After writing, bootstrap also merges the deny list into the project's
`.claude/settings.json`. If the file doesn't exist, creates it. If it exists,
merges the `permissions.deny` array without removing existing entries.

Record `pairmode_version: "0.1.0"` in `.companion/state.json` (creates if absent).

Context passed to all templates:
- `project_name`, `stack`, `build_command`, `test_command`
- `domain_model`: empty string at this stage (Phase 2 will derive from spec)
- `checklist_items`: universal items only (PROTECTED FILES, STORY SCOPE, BUILD GATE)
- `protected_paths`: empty list at this stage (Phase 2 will derive from spec)
- `non_negotiables`: empty list at this stage

Create `tests/pairmode/test_bootstrap.py` with tests that:
- Run bootstrap against a temporary directory
- Assert all expected files are created
- Assert settings.json has the deny list merged correctly
- Assert state.json has pairmode_version set
- Assert dry-run produces output but writes no files

---

## Phase 2 — Spec-Derived Generation

**Goal:** bootstrap.py reads the project's Anchor spec and derives the reviewer checklist
and deny list from it. Protected file comments link back to non-negotiables.

---

### Story 2.1 — Spec reader module

**Acceptance criterion:** `spec_reader.py` reads all spec.json files from a project's
openspec directory and returns a structured data object. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/spec_reader.py`.

```python
def read_project_spec(companion_dir: Path) -> dict | None:
    """
    Reads .companion/product.json["config"] to find the config file path,
    then reads config["spec_location"] to locate the openspec directory,
    then reads all spec.json files from <spec_location>/openspec/specs/*/spec.json.
    Returns None if product.json is missing or has no 'config' key.
    Returns dict with keys:
      modules: list of spec dicts (full spec.json content per module)
      spec_location: Path
    """
```

The function should handle:
- Missing `.companion/product.json` gracefully (return None)
- Missing spec files gracefully (return dict with empty modules list)
- Malformed JSON in spec files (log warning, skip that module)

Create `tests/pairmode/test_spec_reader.py` with tests using temporary directory fixtures
that create the expected file structure.

---

### Story 2.2 — Checklist deriver

**Acceptance criterion:** `checklist_deriver.py` takes a list of spec modules and returns
a list of checklist items. Each non-negotiable becomes a CRITICAL item. Each business rule
becomes a HIGH item. Universal items are appended. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/checklist_deriver.py`.

```python
def derive_checklist(modules: list[dict]) -> list[dict]:
    """
    Returns list of dicts:
      { "name": str, "description": str, "severity": str, "source": str, "module": str }
    source is "non_negotiable", "business_rule", or "universal"
    module is the spec module name, or "universal"
    """
```

Deduplication: if the same rule text appears in multiple modules, merge them
(list all module names in the `module` field).

Universal items are NOT included in the `derive_checklist()` output. They are added by the
templates themselves via hardcoded Jinja2 code. The deriver returns only spec-derived items
(non-negotiables as CRITICAL, business rules as HIGH). The templates append PROTECTED FILES,
STORY SCOPE, and BUILD GATE after the spec-derived items in every rendered output.

Create `tests/pairmode/test_checklist_deriver.py`.

---

### Story 2.3 — Deny list deriver

**Acceptance criterion:** `denylist_deriver.py` takes a list of spec modules and returns
a list of deny rules. Each rule includes an inline comment linking to the non-negotiable.
Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/denylist_deriver.py`.

```python
def derive_denylist(modules: list[dict], module_paths: dict[str, list[str]]) -> list[dict]:
    """
    modules: list of spec.json dicts.
    module_paths: mapping of module name → list of path strings (from .companion/modules.json).
    Returns list of dicts:
      { "path_pattern": str, "non_negotiable": str, "module": str }
    path_pattern is suitable for settings.json deny array (e.g. "Edit(src/services/auth/**)")
    """
```

Derivation logic:
- For each module, read its `paths` list (from modules.json, not spec.json — pass separately)
- For each non-negotiable that mentions protection, isolation, or "must never":
  - Map the relevant module paths to Edit() and Write() deny rules
  - Set non_negotiable to the full text of the non-negotiable
- Also add deny rules for any path containing "auth", "schema", or "engine" in its path
  if the non-negotiable mentions those concepts

The deriver does NOT generate comments in the JSON (settings.json doesn't support comments).
Instead, return the structured data — bootstrap.py will write both the settings.json deny
array and a companion `settings.deny-rationale.json` file that maps each rule to its source.

Create `tests/pairmode/test_denylist_deriver.py`.

---

### Story 2.4 — Wire spec derivation into bootstrap.py

**Acceptance criterion:** When a project has an Anchor spec (`.companion/product.json` exists
and spec files are present), bootstrap.py uses derived checklist and deny list instead of
the static defaults. Without a spec, it falls back to universal items only. Tests pass.

**Instructions:**

Update `skills/pairmode/scripts/bootstrap.py` to:
1. After reading project context, call `spec_reader.read_project_spec()`
2. If spec found: call `checklist_deriver.derive_checklist(modules)` and
   `denylist_deriver.derive_denylist(modules, module_paths)`
3. If no spec: use universal defaults

Edge case: if spec is present but no deny rules are derived (e.g. no module paths
registered in modules.json), bootstrap falls back to DEFAULT_DENY. A spec with no
path mappings is treated the same as no spec for deny-list purposes.
4. Pass derived data to templates

IMPORTANT: Pass only spec-derived items in `checklist_items`. Do NOT include universal items
(PROTECTED FILES, STORY SCOPE, BUILD GATE) — the templates add those themselves via hardcoded
Jinja2. Including them in `checklist_items` will cause duplication in rendered output.

Also write `settings.deny-rationale.json` alongside `settings.json` in `.claude/`:
```json
{
  "generated_by": "anchor:pairmode",
  "pairmode_version": "0.1.0",
  "rules": [
    {
      "pattern": "Edit(src/services/auth/**)",
      "module": "auth-and-security",
      "non_negotiable": "Auth must never call billing directly — events only"
    }
  ]
}
```

Update `tests/pairmode/test_bootstrap.py` with spec-derived scenarios.

---

### Story 2.5 — Phase 2 test coverage pass

**Acceptance criterion:** `uv run pytest tests/pairmode/ -x -q` passes with no failures.
Coverage includes spec reader, checklist deriver, deny list deriver, and bootstrap integration.

**Instructions:**

Review all tests written in Stories 2.1–2.4. Fill any gaps:
- Edge cases: empty spec, spec with no non-negotiables, spec with conflicting module paths
- Integration test: create a full mock project with `.companion/product.json` and
  spec files, run bootstrap end-to-end, assert all outputs are correct

No new production code in this story — tests only.

---

## Phase 3 — Lessons System

**Goal:** Capture and review methodology lessons. Lessons live in the anchor repo and
inform future bootstraps.

---

### Story 3.1 — Lessons store

**Acceptance criterion:** `lessons/lessons.json` exists with the correct schema.
`lessons/LESSONS.md` exists and is auto-generated from lessons.json. An empty lessons.json
produces a valid LESSONS.md.

**Instructions:**

Create `lessons/lessons.json`:
```json
{
  "version": "1.0.0",
  "lessons": []
}
```

Create `skills/pairmode/scripts/lesson_utils.py` with:
```python
LESSONS_FILE = Path(__file__).parent.parent.parent.parent / "lessons" / "lessons.json"

def load_lessons() -> dict
def save_lessons(data: dict) -> None   # validates append-only invariant
def generate_lessons_md(data: dict) -> str
def next_lesson_id(data: dict) -> str  # returns "L001", "L002", etc.
```

`save_lessons` must enforce the append-only invariant:
- Existing entries may only have their `status` field changed
- Any attempt to modify other fields of an existing entry raises ValueError
- New entries may be appended freely

Create `lessons/LESSONS.md` with:
```markdown
# Anchor Methodology Lessons

This file is auto-generated from lessons.json. Edit lessons.json directly.

No lessons captured yet.
```

Create `tests/pairmode/test_lesson_utils.py` covering:
- Load/save round-trip
- Append-only invariant enforcement (assert ValueError on modification)
- LESSONS.md generation with one and multiple lessons
- next_lesson_id sequencing

---

### Story 3.2 — Lesson capture command

**Acceptance criterion:** `/anchor:pairmode lesson` command is documented in SKILL.md
and `lesson.py` captures a lesson interactively and writes it to lessons.json.
LESSONS.md is regenerated after capture. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/lesson.py`.

The capture flow (invoked by the skill):
1. Ask user for trigger (what situation caused this lesson)
2. Ask user for problem (what went wrong or what was surprising)
3. Ask user for learning (what was learned)
4. Ask user for methodology_change (what should change — free text)
5. Ask user for affects (which template areas: reviewer_checklist, builder_agent,
   orchestrator, checkpoint_sequence, all)
6. Ask user for applies_to tags (all, typescript, python, monorepo, etc.)
7. Confirm the lesson before writing
8. Write to lessons.json with status: "captured"
9. Regenerate LESSONS.md
10. Output the lesson ID

Lesson schema:
```json
{
  "id": "L001",
  "date": "YYYY-MM-DD",
  "source_project": "project name or 'unknown'",
  "trigger": "...",
  "problem": "...",
  "learning": "...",
  "methodology_change": {
    "affects": ["reviewer_checklist"],
    "description": "..."
  },
  "applies_to": ["all"],
  "status": "captured"
}
```

Update `SKILL.md` with the lesson command instructions.

Create `tests/pairmode/test_lesson_capture.py`.

---

### Story 3.3 — Lesson review command

**Acceptance criterion:** `/anchor:pairmode review` surfaces captured lessons grouped by
`affects`, proposes specific template edits, and writes approved updates to the templates.
Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/lesson_review.py`.

Review flow:
1. Load all lessons with status "captured" or "reviewed"
2. Group by `affects` field
3. For each group, propose a specific template change:
   - "reviewer_checklist": propose adding/modifying a checklist item in CLAUDE.md.j2
   - "builder_agent": propose a change to builder.md.j2
   - "orchestrator": propose a change to CLAUDE.build.md.j2
   - "checkpoint_sequence": propose a change to the checkpoint section
4. Present each proposal to the user (show lesson trigger + proposed change)
5. User approves or rejects each
6. Write approved changes to the template files
7. Update lesson status to "applied" for approved lessons, "reviewed" for rejected
8. Regenerate LESSONS.md

Update `SKILL.md` with the review command instructions.

Create `tests/pairmode/test_lesson_review.py` (mock user input for testing).

---

## Phase 4 — Audit and Sync

**Goal:** Compare existing projects against the current canonical methodology and apply
updates non-destructively. First real-world validation: audit cora, radar, and forqsite.

---

### Story 4.1 — audit.py

**Acceptance criterion:** `audit.py` produces a structured diff of a project against
canonical templates + applicable lessons. Output matches the format defined in architecture.

**Instructions:**

Create `skills/pairmode/scripts/audit.py`.

Import pattern: audit.py may call `lesson_utils.load_lessons()` directly. Use the same
relative-import workaround already established in other pairmode scripts (sys.path insertion
or PYTHONPATH). Do not introduce a new import pattern without aligning with lesson.py and
bootstrap.py. The pattern is: at the top of the script, insert the anchor repo root into
sys.path before importing sibling modules.

Audit logic:
1. Read project's `.companion/state.json` for `pairmode_version`
2. Load canonical templates at current version
3. Load applicable lessons (filter by `applies_to` matching project type)
4. Compare project's CLAUDE.md, CLAUDE.build.md, and agent files against canonical
5. Produce structured diff:
   - MISSING: items in canonical not in project (with lesson reference if applicable)
   - INCONSISTENT: items present but diverged from canonical
   - EXTRA: project-specific items not in canonical (preserve these)

```python
def audit_project(project_dir: Path, applies_to: str = "all") -> AuditResult:
    """
    Returns AuditResult with:
      missing: list[AuditItem]
      inconsistent: list[AuditItem]
      extra: list[AuditItem]
      pairmode_version: str | None
      canonical_version: str
    """
```

AuditItem: `{ "file": str, "section": str, "description": str, "lesson_id": str | None }`

Output format:
```
AUDIT: <project_name> vs pairmode v<version>

MISSING
  ✗ <description>  (<lesson_id if applicable>)

INCONSISTENT
  ~ <file>: <description>

EXTRA (project-specific, keep as-is)
  ✓ <description>

RECOMMENDATION
  Run /anchor:pairmode sync to apply missing/inconsistent items
  Project-specific items will be preserved
```

Create `tests/pairmode/test_audit.py`.

---

### Story 4.2 — /anchor:pairmode audit command

**Acceptance criterion:** SKILL.md documents the audit command. Running it against a
project produces the audit output and optionally offers to run sync.

**Instructions:**

Update `SKILL.md` with audit command instructions:
1. Check for `.companion/state.json` in current directory
2. Run `uv run python ${CLAUDE_SKILL_DIR}/scripts/audit.py --project-dir $(pwd)`
3. Display the output
4. If there are MISSING or INCONSISTENT items, ask: "Run sync to apply these changes?"

---

### Story 4.3 — sync.py

**Acceptance criterion:** `sync.py` applies the delta from an audit result to a project
non-destructively. Project-specific content is preserved. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/sync.py`.

Sync logic:
1. Run audit to get the delta (or accept a pre-computed AuditResult)
2. For each MISSING item: add it to the appropriate file
3. For each INCONSISTENT item: update it to match canonical
4. Never touch EXTRA items
5. Record sync event in `.companion/state.json`:
   ```json
   {
     "pairmode_version": "0.1.0",
     "last_sync": "2026-04-17",
     "lessons_applied": ["L001", "L002"]
   }
   ```

The hardest part is merging checklist items into CLAUDE.md — implement a section-aware
merge that locates the review checklist section and inserts/updates items without
disrupting surrounding content.

Create `tests/pairmode/test_sync.py`.

---

### Story 4.4 — /anchor:pairmode sync command + SKILL.md update

**Acceptance criterion:** SKILL.md documents the sync command. Running it applies the
delta and confirms what was changed.

**Instructions:**

Update `SKILL.md` with sync command instructions.

After sync completes, output:
```
SYNC COMPLETE — <project_name>
Applied:
  ✓ <description of each change>
Preserved:
  → <project-specific items kept>
State updated: .companion/state.json
```

---

### Story 4.5 — Audit/sync test coverage pass

**Acceptance criterion:** Full test pass. Edge cases covered.

**Instructions:**

Review all tests from Stories 4.1–4.4. Fill gaps:
- Sync idempotency: running sync twice produces the same result as running it once
- Audit of a project with no pairmode_version (unversioned)
- Sync when CLAUDE.md doesn't exist (should create it)
- Preservation of project-specific checklist items during sync

No new production code — tests only.

---

⚙️ DEVELOPER ACTION — Run audit against sibling repos

Before Phase 5, run `/anchor:pairmode audit` against:
- `/mnt/work/cora`
- `/mnt/work/radar`
- `/mnt/work/forqsite`

Document the findings. Use the output to identify any gaps in the audit logic
(things the audit missed that you can see manually). File those as lessons with
`/anchor:pairmode lesson` before proceeding.

Confirm this is done before saying "Continue building Phase 5".

---

## Phase 5 — Companion Enhancements

**Goal:** Make the companion sidebar story-aware and capture permission overrides as spec decisions.

---

### Story 5.1 — Story context in state.json

**Acceptance criterion:** `.companion/state.json` supports a `current_story` field.
The companion skill writes it when the user selects modules. Tests cover the schema change.

**Instructions:**

Update the state.json schema (document in `skills/companion/SKILL.md` and architecture.md)
to include:
```json
{
  "last_loaded_modules": ["module-name"],
  "current_story": {
    "id": "2.3",
    "title": "optional title",
    "set_at": "ISO timestamp"
  }
}
```

`current_story` is optional — companion sessions without pairmode active have no story context.

Update the companion SKILL.md to describe this new field.

The companion skill should detect if the project has pairmode active
(check for `.claude/settings.deny-rationale.json`) and if so, ask the user
"Which story are you working on?" after module selection (optional — user can skip).

Write the story ID to state.json if provided.

---

### Story 5.2 — Story context panel in sidebar

**Acceptance criterion:** When `current_story` is set in state.json, the sidebar displays
a story context panel showing the current story ID and title.

**Instructions:**

Update `skills/companion/scripts/sidebar.py`.

Add a story context panel below the specs panel in the sidebar layout:
```
╭──────────────── Story ─────────────────╮
│  Story 2.3 — Deny list deriver         │
│  Started: 14:32                        │
╰────────────────────────────────────────╯
```

The sidebar reads `current_story` from state.json on startup and on each pipe message
that includes a `type: "state_update"` event.

If `current_story` is not set, the panel is hidden.

---

### Story 5.3 — Module boundary detection

**Acceptance criterion:** When a builder modifies files in multiple modules during a single
session, the sidebar displays a module boundary alert. The detection uses the existing
module path mappings from modules.json.

**Instructions:**

Update `hooks/post_tool_use.py` to include the modified file path in its pipe message:
```json
{ "type": "file_changed", "path": "/abs/path/to/file.py", "tool": "Edit" }
```

Update `skills/companion/scripts/sidebar.py` to track which modules have been touched
in the current session (by matching file paths against module paths in modules.json).

If files from more than one module have been touched and `current_story` is set,
add a warning to the sidebar:
```
⚠ Multi-module: auth-and-security, decision-ledger
  Story scope may be exceeded
```

---

### Story 5.4 — Permission override capture

**Acceptance criterion:** When a protected file is edited (file path matches a pattern in
`.claude/settings.deny-rationale.json`), the sidebar displays a prompt asking for an
override reason. The prompt is non-blocking — the edit has already happened.

**Instructions:**

Update `hooks/post_tool_use.py` to check if the modified file matches any pattern in
`.claude/settings.deny-rationale.json`. If it does, include in the pipe message:
```json
{
  "type": "file_changed",
  "path": "/abs/path",
  "tool": "Edit",
  "protected": true,
  "protection_rule": "Edit(src/services/auth/**)",
  "non_negotiable": "Auth must never call billing directly"
}
```

The sidebar handles `protected: true` by displaying an override capture prompt:
```
╭─────────── Protected File Override ───────────╮
│  src/services/auth/middleware.ts was modified  │
│  Rule: Auth must never call billing directly   │
│                                                │
│  Reason for override (or press s to skip):     │
╰───────────────────────────────────────────────╯
```

If the user provides a reason, write a `spec_exception` message to the pipe.
If the user skips (presses s), no record is written.

> **As-built note (Phase 5 security audit):** The hook annotation approach described
> above was not implemented. Protected-file classification was moved to the sidebar
> (`_check_protected()` function) so the hook remains a zero-I/O thin relay. The pipe
> message from the hook contains only `path` and `tool`. The sidebar enriches the event
> with `protected`, `protection_rule`, and `non_negotiable` before calling
> `display_override_prompt()`.

---

### Story 5.5 — Spec exception recording

**Acceptance criterion:** When a spec exception is captured, it is written to the
spec's `conflicts` array with the override reason and session lineage. Tests pass.

**Instructions:**

The sidebar handles `type: "spec_exception"` pipe messages by calling a new function
`record_spec_exception()` in the sidebar script:

```python
def record_spec_exception(
    project_dir: Path,
    file_path: str,
    non_negotiable: str,
    override_reason: str,
    session_id: str
) -> None:
    """
    Finds the relevant spec module (by matching file_path against module paths),
    appends to its conflicts array:
    {
      "file": file_path,
      "non_negotiable": non_negotiable,
      "override_reason": override_reason,
      "date": today,
      "session_id": session_id,
      "status": "open"
    }
    """
```

Create `tests/pairmode/test_spec_exception.py`.

> **As-built note:** `record_spec_exception()` was extracted into a standalone module at
> `skills/pairmode/scripts/spec_exception.py` and imported by sidebar.py. This keeps
> spec-write logic in the pairmode skill layer and makes the function independently testable.

---

### Story 5.6 — Phase 5 test coverage pass

**Acceptance criterion:** Full test pass. All Phase 5 logic has test coverage.

**Instructions:**

Tests only. Cover:
- state.json story context read/write
- Module boundary detection with mock module paths
- Protected file detection from deny-rationale.json
- Spec exception recording with mock spec files
- Sidebar story panel rendering (assert output contains story ID)

---

## Phase 6 — Audit Noise, SKILL.md Completeness, and End-to-End Validation

**Goal:** Fix the two filed audit bugs (L001, L002), repair all SKILL.md invocation gaps, and
add an end-to-end smoke test that validates the full bootstrap → audit → sync roundtrip.

---

### Story 6.1 — Fix L001: suppress INCONSISTENT when pairmode_context.json is absent

**Acceptance criterion:** When `audit.py` is run against a project with no `pairmode_context.json`,
the audit output emits a prominent warning and suppresses all INCONSISTENT findings. MISSING and
EXTRA findings are unaffected. `sync.py` also skips the INCONSISTENT pass when context is missing.
Tests pass.

**Instructions:**

Update `skills/pairmode/scripts/audit.py`:

1. Extend `_load_project_context` to return a tuple `(context: dict, context_found: bool)`.
   When `pairmode_context.json` exists and parses successfully, return `(context, True)`.
   When it is absent or unparseable, return `(fallback_dict, False)`.

2. Add `context_missing: bool = False` to the `AuditResult` dataclass.

3. In `audit_project`, capture whether the context file was found. When `context_missing` is `True`,
   skip the INCONSISTENT comparison loop entirely — do not add any items to `result.inconsistent`.
   MISSING and EXTRA logic is unaffected.

4. In `format_audit_output`, after the header line, when `result.context_missing` is `True`, emit:
   ```
   WARNING: No pairmode_context.json found — INCONSISTENT comparison disabled.
     Template body comparison requires a context file to be meaningful.
     Run /anchor:pairmode bootstrap to generate pairmode_context.json, then re-audit.
   ```
   This warning replaces the INCONSISTENT section entirely.

5. In `skills/pairmode/scripts/sync.py`, after calling `audit_project()`, check
   `audit_result.context_missing`. If `True`, skip the INCONSISTENT pass and emit:
   `"Skipping INCONSISTENT patch: no pairmode_context.json — run bootstrap first."`
   Do NOT write any files based on empty-context INCONSISTENT findings.

Add tests to `tests/pairmode/test_audit.py`:
- `audit_project` returns `context_missing=True` and empty `inconsistent` when context file absent.
- `format_audit_output` contains the warning string when `context_missing=True`.
- MISSING and EXTRA still populate correctly when `context_missing=True`.

Add a test to `tests/pairmode/test_sync.py`:
- When `pairmode_context.json` is absent, `sync_project` does not write any INCONSISTENT patches
  (`applied` list contains no INCONSISTENT entries).

Mark L001 status as `applied` in `lessons/lessons.json` after this story passes review.

---

### Story 6.2 — Fix L002: skip separator-keyed sections from INCONSISTENT output

**Acceptance criterion:** Section keys that start with `---` (matching `^-+(__\d+)?$`) are
silently skipped from MISSING, EXTRA, and INCONSISTENT reporting. `_split_sections` is unchanged —
filtering happens in the comparison loop. Tests pass.

**Instructions:**

Update `skills/pairmode/scripts/audit.py`:

1. Add a helper near `_normalise`:
   ```python
   def _is_separator_key(key: str) -> bool:
       return bool(re.match(r'^-+(__\d+)?$', key))
   ```

2. In the MISSING loop: `if _is_separator_key(key): continue`
3. In the EXTRA loop: `if _is_separator_key(key): continue`
4. In the INCONSISTENT loop: `if _is_separator_key(key): continue`

Add tests to `tests/pairmode/test_audit.py`:
- Unit test `_is_separator_key`: `True` for `"---"`, `"---__0"`, `"---__1"`, `"----"`;
  `False` for `"## session modes"`, `"__preamble__0"`.
- Integration test: project file with `---` separators produces no INCONSISTENT items
  with `---`-keyed sections.
- Legitimate `##`-headed section differences still produce INCONSISTENT items.

Mark L002 status as `applied` in `lessons/lessons.json` after this story passes review.

---

### Story 6.3 — Fix SKILL.md invocation gaps and bootstrap.py sys.path guard

**Acceptance criterion:** All CLI invocations in `skills/pairmode/SKILL.md` use
`PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/..."`.
`bootstrap.py` has a `sys.path` self-insertion guard matching the pattern in `audit.py` and
`sync.py`. The broken `PYTHONPATH=/path/to/anchor` placeholder in `skills/companion/SKILL.md`
is replaced with a working invocation. Tests pass.

**Instructions:**

**Part A — bootstrap.py sys.path guard:**

Add before the sibling imports at the top of `skills/pairmode/scripts/bootstrap.py`:
```python
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).parent.parent.parent.parent))
```
This matches the pattern in `audit.py` line 20 and `sync.py` line 20 exactly.

**Part B — pairmode SKILL.md bootstrap command block:**

In `skills/pairmode/SKILL.md`, add a **"CLI invocation:"** block to the bootstrap section:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/bootstrap.py" \
  --project-dir "$(pwd)"
```
Note: bootstrap is interactive; `--project-dir` is the only required flag. Omit
`--project-name`, `--stack`, etc. to be prompted.

**Part C — pairmode SKILL.md lesson and lesson_review invocations:**

Replace the existing CLI invocation blocks:
- lesson.py: `uv run python skills/pairmode/scripts/lesson.py ...` →
  `PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/lesson.py" ...`
- lesson_review.py: same pattern for lesson_review.py.

**Part D — companion SKILL.md Step 2.5 fix:**

In `skills/companion/SKILL.md`, find the story-write bash block that contains
`PYTHONPATH=/path/to/anchor`. Remove the broken `PYTHONPATH=` prefix line. The
`sys.path.insert` inside the `-c` script already handles the import path correctly.
The corrected block should have no leading `PYTHONPATH=...` prefix.

**Part E — audit and sync prerequisite note:**

In `skills/pairmode/SKILL.md`, add one sentence after the "Inputs:" bullet list in both
the `/anchor:pairmode audit` and `/anchor:pairmode sync` sections:
> Note: `pairmode_context.json` (created by `/anchor:pairmode bootstrap`) must exist for
> INCONSISTENT results to be meaningful. See Story 6.1 for details.

**Tests:**

Add to `tests/pairmode/test_bootstrap.py`:
- Test that running `bootstrap.py --help` via subprocess with `cwd` set to an unrelated
  temp directory (no PYTHONPATH set externally) exits with code 0. This verifies the
  `sys.path` guard enables the sibling imports without external env setup.

---

### Story 6.4 — End-to-end smoke test: bootstrap → audit → sync roundtrip

**Acceptance criterion:** `tests/pairmode/test_e2e_roundtrip.py` exercises the full pairmode
adoption flow against a temporary directory and asserts coherent output at each stage. All
existing tests continue to pass.

**Instructions:**

Create `tests/pairmode/test_e2e_roundtrip.py` with a test class `TestFullAdoptionJourney`.

The test exercises this flow:

1. **Bootstrap a fresh project:**
   - Create a temp directory `project_dir`.
   - Call `bootstrap.main` via Click's `CliRunner` with `["--project-dir", str(project_dir)]`
     and simulate interactive prompts (project name, stack, etc.) OR use `--dry-run` first to
     verify output, then re-run without `--dry-run`.
   - Assert all scaffold files exist: `CLAUDE.md`, `CLAUDE.build.md`,
     `.claude/agents/builder.md`, `.claude/settings.json`, etc.
   - Assert `pairmode_context.json` exists at `.companion/pairmode_context.json`.
   - Assert `state.json` contains `pairmode_version`.
   - Assert `settings.deny-rationale.json` exists.

2. **Audit immediately after bootstrap — expect clean result:**
   - Call `audit_project(project_dir)`.
   - Assert `result.missing` is empty.
   - Assert `result.inconsistent` is empty.
   - Assert `result.context_missing` is `False`.

3. **Simulate drift — delete one canonical `##`-headed section from CLAUDE.md:**
   - Read `project_dir / "CLAUDE.md"`, remove one complete `##` section (content between
     two consecutive `##` headers), write back.
   - Call `audit_project(project_dir)` again.
   - Assert the missing section appears in `result.missing`.
   - Assert `result.context_missing` is `False`.

4. **Sync — apply the drift:**
   - Call `sync_project(project_dir)`.
   - Assert `SyncResult.applied` is non-empty.
   - Read `project_dir / "CLAUDE.md"` and assert the removed section text is restored.

5. **Post-sync audit — expect clean again:**
   - Call `audit_project(project_dir)` a third time.
   - Assert `result.missing` is empty.
   - Assert `result.inconsistent` is empty.

6. **Audit without context file — expect L001 behavior:**
   - Delete `project_dir / ".companion" / "pairmode_context.json"`.
   - Call `audit_project(project_dir)`.
   - Assert `result.context_missing` is `True`.
   - Assert `result.inconsistent` is empty (suppressed).
   - Assert `format_audit_output(result)` contains `"No pairmode_context.json found"`.

---

### Story 6.5 — lesson_review output clarity: distinguish annotation from implementation

**Acceptance criterion:** After `/anchor:pairmode review`, the CLI output clearly distinguishes
"template annotated — action required" from a completed implementation. Tests assert the new
output format. SKILL.md is updated to describe this distinction.

**Instructions:**

Update `skills/pairmode/scripts/lesson_review.py`:

In the `cli` function, after calling `apply_template_change` for each approved lesson, change
the echo to:
```python
click.echo(
    f"  Annotated {proposal['template_file']} with lesson {lesson_id}.\n"
    f"  ACTION REQUIRED: Open the template and implement the change:\n"
    f"    {{# LESSON {lesson_id}: {proposal['description']} #}}"
)
```

Change the end-of-run summary to:
```
REVIEW COMPLETE
  N lesson(s) annotated — open affected templates to implement the changes.
  M lesson(s) deferred for next review cycle.
LESSONS.md regenerated.
```

In `skills/pairmode/SKILL.md`, update the `/anchor:pairmode review` section to note:
> "Applying" a lesson writes a Jinja2 comment block marking the change location. The developer
> must open the annotated template to implement the actual change. Lesson status is set to
> `applied` once the annotation is written, not once the template change is implemented.

Update `tests/pairmode/test_lesson_review.py`:
- Assert CLI output for an approved lesson contains `"ACTION REQUIRED"`.
- Assert end-of-run summary contains `"REVIEW COMPLETE"`.

---

### Story 6.6 — Phase 6 test coverage pass

**Acceptance criterion:** Full test pass. All Phase 6 logic has test coverage. `tests/pairmode/`
passes cleanly.

**Instructions:**

Tests only. Verify coverage for:
- `_is_separator_key` (Story 6.2)
- `context_missing` flag in AuditResult and format_audit_output (Story 6.1)
- sync skips INCONSISTENT when context missing (Story 6.1)
- bootstrap.py `--help` subprocess test (Story 6.3)
- Full roundtrip bootstrap → audit → sync (Story 6.4)
- lesson_review ACTION REQUIRED output (Story 6.5)

Add any missing tests. Do not modify non-test files.

---

### ⚙️ DEVELOPER ACTION — Mark L001 and L002 lessons as applied

After stories 6.1 and 6.2 pass review, run:
```bash
PYTHONPATH=/mnt/work/anchor uv run python skills/pairmode/scripts/lesson_review.py \
  --approve L001 \
  --approve L002
```

Confirm `lessons/lessons.json` shows `"status": "applied"` for both L001 and L002 before
proceeding to Phase 7. As of the Phase 6 checkpoint, this action has NOT been run yet.
The lesson_review.py `--approve` flow is the only permitted way to update lesson status
(it enforces the append-only invariant). Do not edit lessons.json directly.

---

## Phase 7 — docs/brief.md, Per-Phase Prompts, and CER Backlog

**Goal:** Introduce three structural improvements to the pairmode methodology: (1) a
`docs/brief.md` canonical source for operator intent, separate from `docs/architecture.md`;
(2) per-phase prompt files at `docs/phases/phase-N.md` that replace the monolithic
`docs/phase-prompts.md` for new projects; and (3) a Cold Eyes Review (CER) backlog system
with four-quadrant triage. All three are integrated into bootstrap, audit, and sync.

Prerequisites: L003 is resolved in Story 7.0 before any bootstrap integration work begins.
L006 (audit override markers) is deferred to Phase 8. L007 is already applied (commit 0518c2f).

---

### Story 7.0 — Bootstrap skip-by-default for existing agent files (L003)

**Acceptance criterion:** Bootstrap skips `.claude/agents/` files that already exist, by
default. A `--force-agents` flag overwrites them. `SKILL.md` documents that agent files are
project-owned after first bootstrap. Tests pass.

**Instructions:**

In `skills/pairmode/scripts/bootstrap.py`, split `SCAFFOLD_FILES` into two lists:

```python
SCAFFOLD_FILES = [...]         # always written (CLAUDE.md, CLAUDE.build.md, docs/)
AGENT_FILES = [                # skipped if already exist, unless --force-agents
    (".claude/agents/builder.md", "agents/builder.md.j2"),
    (".claude/agents/reviewer.md", "agents/reviewer.md.j2"),
    (".claude/agents/loop-breaker.md", "agents/loop-breaker.md.j2"),
    (".claude/agents/security-auditor.md", "agents/security-auditor.md.j2"),
    (".claude/agents/intent-reviewer.md", "agents/intent-reviewer.md.j2"),
]
```

Add `--force-agents` flag to the `bootstrap` click command (default: False).

When writing agent files: if the destination exists and `--force-agents` is False, skip with
a message `"  skipped (project-owned): {dest} — use --force-agents to overwrite"`. If
`--force-agents` is True, overwrite without prompting (same as current behaviour).

Update `skills/pairmode/SKILL.md` bootstrap section:
- Document `--force-agents` flag.
- Add a note: "Agent files in `.claude/agents/` are treated as project-owned after first
  bootstrap. Bootstrap will not overwrite them on subsequent runs unless `--force-agents` is
  passed explicitly."

Add tests to `tests/pairmode/test_bootstrap.py`:
- Agent files are skipped when they already exist (no `--force-agents`).
- Agent files are overwritten when `--force-agents` is passed.
- Non-agent scaffold files (CLAUDE.md, docs/) are still written/prompted as before.

---

### Story 7.1 — docs/brief.md template and bootstrap integration

**Acceptance criterion:** `skills/pairmode/templates/docs/brief.md.j2` exists and renders
correctly. Bootstrap writes `docs/brief.md` to new projects. `CLAUDE.md.j2` lists
`docs/brief.md` as the first read-before-any-task document, before `docs/architecture.md`.
Tests pass.

**Instructions:**

Create `skills/pairmode/templates/docs/brief.md.j2`.

Template variables:
- `{{ project_name }}` — project name
- `{{ project_description }}` — one-line description
- `{{ stack }}` — technology stack
- `{{ what }}` — what is being built (output, deliverable)
- `{{ why }}` — why it is being built (motivation, problem being solved)
- `{{ operator_contact }}` — optional; who owns this project / who to ask

The template must produce a document covering:
- What this project produces (the output, not the how)
- Why it exists (motivation, problem solved, stakeholder need)
- Any explicit constraints the operator has placed on scope or approach
- A "not in scope" section (for things that might seem related but are intentional omissions)

`docs/brief.md` is intentionally short — one page. It is not a design document. Design lives in
`docs/architecture.md`. `docs/brief.md` answers "what and why"; `docs/architecture.md` answers
"how and why we built it this way."

Update `skills/pairmode/templates/CLAUDE.md.j2`:

Replace the current `## Project context` section (or `## Read before any task` if already
updated) with a `## Read before any task` section that lists in order:
1. `docs/brief.md` — what and why (operator intent)
2. `docs/architecture.md` — how and architectural decisions
3. Current phase file from `docs/phases/` (see Story 7.2); or `docs/phase-prompts.md` for
   legacy projects that have not migrated

Include the portability statement: "These three documents should be sufficient for any model or
toolchain to cold-start this project and reproduce a valid variant without prior session context."

Update `skills/pairmode/scripts/bootstrap.py` to:
1. Add `docs/brief.md` to the list of files written to the project.
2. Add `what` and `why` fields to the bootstrap context (read from `product.json` if present;
   prompt if missing, allowing blank).
3. Update `pairmode_context.json` to include `what` and `why` keys.

Add tests to `tests/pairmode/test_templates.py`:
- Render `brief.md.j2` with sample context; assert "not in scope" section is present.
- Render `brief.md.j2` with `what=""` and `why=""` — empty fields render gracefully, no crash.
- Render `CLAUDE.md.j2`; assert "docs/brief.md" appears before "docs/architecture.md".
- Render `CLAUDE.md.j2`; assert the portability statement is present.

---

### Story 7.2 — Per-phase prompt file templates

**Acceptance criterion:** `skills/pairmode/templates/docs/phases/index.md.j2` and
`skills/pairmode/templates/docs/phases/phase.md.j2` exist and render correctly. Bootstrap writes
`docs/phases/index.md` and `docs/phases/phase-1.md` to new projects. `phase.md.j2` renders
correct prev/next navigation links. Tests pass.

**Instructions:**

Create `skills/pairmode/templates/docs/phases/index.md.j2`.

Template variables:
- `{{ project_name }}`
- `{{ phases }}` — list of dicts: `{ "id": int, "title": str, "status": str, "file": str }`
  where status is one of: `planned`, `in_progress`, `complete`

Render a table of phases with columns: Phase, Title, Status, Link. Start with one placeholder
row for Phase 1 (status: planned, title: "— fill in —").

Create `skills/pairmode/templates/docs/phases/phase.md.j2`.

Template variables:
- `{{ project_name }}`
- `{{ phase_id }}` — integer
- `{{ phase_title }}` — string
- `{{ prev_phase }}` — optional dict `{ "id": int, "title": str }` (None for Phase 1)
- `{{ next_phase }}` — optional dict `{ "id": int, "title": str }` (None for last phase)
- `{{ goal }}` — one paragraph describing the phase goal
- `{{ stories }}` — list of dicts: `{ "id": str, "title": str }` (bodies are blank stubs)

Render:
- Navigation header: `← Phase N-1: Title | Phase N+1: Title →` (omit edges at boundaries)
- Phase goal paragraph
- For each story: `### Story N.X — Title` with `**Acceptance criterion:**` and
  `**Instructions:**` placeholders
- A `### CP-N Cold-eyes checklist` section at the bottom (blank — developer fills in)

Update `skills/pairmode/scripts/bootstrap.py` to:
1. Write `docs/phases/index.md` from `index.md.j2` with one placeholder Phase 1 entry.
2. Write `docs/phases/phase-1.md` from `phase.md.j2` with `goal=""` and `stories=[]`.
3. Do NOT write or modify the legacy `docs/phase-prompts.md` for new bootstraps. New projects
   get the per-phase structure. Existing projects with `docs/phase-prompts.md` are unaffected
   (audit will report the phase files as MISSING, not modify phase-prompts.md).

Add tests to `tests/pairmode/test_templates.py`:
- `index.md.j2` renders with one phase; assert phase ID and status columns are present.
- `phase.md.j2` with both `prev_phase` and `next_phase` renders both navigation links.
- `phase.md.j2` with `prev_phase=None` omits the left navigation link.
- `phase.md.j2` with `stories=[]` produces correct stubs section without crashing.
- Bootstrap writes `docs/phases/index.md` and `docs/phases/phase-1.md` to a new project.
- Bootstrap does NOT write `docs/phase-prompts.md` to a new project (no such file created).

---

### Story 7.3 — CER backlog template and bootstrap integration

**Acceptance criterion:** `skills/pairmode/templates/docs/cer/backlog.md.j2` exists and renders
four triage quadrants. Bootstrap writes `docs/cer/backlog.md` to new projects. Tests pass.

**Instructions:**

The Cold Eyes Review (CER) backlog is a structured triage log for findings from external reviews
(a different model, a peer, an IDE without project context). Findings are triaged into four
quadrants adapted from Covey's time management matrix:

- **Do Now** — Urgent and important. Blocks correctness, security, or the next phase. Address
  before the next checkpoint.
- **Do Later** — Important, not urgent. Quality improvements, architectural refinements,
  documentation gaps that compound if ignored. Address before project end.
- **Do Much Later** — Not urgent, marginal value. Style, cosmetics, speculative improvements.
  Address if convenient.
- **Do Never** — Rejected findings. Not applicable, out of scope, or explicitly accepted as a
  known tradeoff. Record the rejection reason so it is not re-raised.

Create `skills/pairmode/templates/docs/cer/backlog.md.j2`.

Template variables:
- `{{ project_name }}`
- `{{ last_updated }}` — ISO date string
- `{{ cer_entries }}` — list of dicts:
  ```
  {
    "id": "CER-001",
    "quadrant": "do_now" | "do_later" | "do_much_later" | "do_never",
    "finding": "description",
    "source": "reviewer name or tool",
    "date": "YYYY-MM-DD",
    "resolution": "optional; required for do_never",
    "phase": "optional phase number"
  }
  ```

Render four sections (one per quadrant), each listing its entries as a Markdown table with
columns: ID, Finding, Source, Date, Phase. For `do_never`, add a Resolution column. Empty
quadrant tables show a "*(none)*" placeholder row.

Update `skills/pairmode/scripts/bootstrap.py` to:
1. Add `docs/cer/backlog.md` to the list of files written.
2. Render it with `cer_entries=[]` and `last_updated` set to today.

Add tests to `tests/pairmode/test_templates.py`:
- Render `backlog.md.j2` with no entries; assert all four quadrant section headings are present.
- Render with one entry per quadrant; assert each entry appears under the correct heading.

Add a test to `tests/pairmode/test_bootstrap.py`:
- Bootstrap writes `docs/cer/backlog.md` to a new project.

---

### Story 7.4 — phase_new.py: lazy phase scaffolding

**Acceptance criterion:** `phase_new.py` creates a new per-phase prompt file and updates
`docs/phases/index.md`. Running it twice with the same phase ID is idempotent (warns, does not
overwrite). Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/phase_new.py`.

Use `click`. Entry point: `phase_new` with options:
- `--project-dir` (default: current directory)
- `--phase-id` (required; integer)
- `--title` (optional; prompted if missing)
- `--goal` (optional; prompted if missing; blank is acceptable)

Behavior:
1. Resolve `project_dir / "docs" / "phases"`. Create if missing.
2. Check if `phase-N.md` already exists. If so: print a warning and exit 0 (idempotent).
3. Determine `prev_phase` by checking if `phase-(N-1).md` exists and reading its title from
   its first `# Phase` or `### Story` heading. If N=1 or the prior file does not exist,
   `prev_phase=None`.
4. Render `phase.md.j2` with `phase_id=N`, `phase_title`, `goal`, `prev_phase`,
   `next_phase=None`, `stories=[]`.
5. Write `docs/phases/phase-N.md`.
6. If `docs/phases/index.md` exists, append a new row to the phases table (status: planned).
   If it does not exist, create it from `index.md.j2` with this phase as the only entry.
7. Write updated `docs/phases/index.md`.

Use the `sys.path.insert` self-import guard at the top (same pattern as `audit.py` line 20).

Add tests to `tests/pairmode/test_phase_new.py`:
- Fresh project: creates both `phase-1.md` and `index.md`.
- Running twice with same phase ID: warns, does not overwrite, exits 0.
- Phase 3 after phases 1 and 2 exist: `prev_phase` is populated from phase-2.md title.
- `docs/phases/` directory is created if it does not exist.
- Phase N where N-1 exists but has no `# Phase` heading: graceful fallback, `prev_phase`
  title is "Phase N-1" rather than crashing.

---

### Story 7.5 — cer.py: CER triage CLI

**Acceptance criterion:** `cer.py` appends a finding to `docs/cer/backlog.md` in the correct
quadrant. Running against a project with no `docs/cer/backlog.md` creates the file first. IDs
are sequential across quadrants. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/cer.py`.

Use `click`. Entry point: `cer` with options:
- `--project-dir` (default: current directory)
- `--reviewer` (optional; defaults to `"external"`)
- `--finding` (optional; if provided, skips the interactive prompt)
- `--quadrant` (optional; one of `now`, `later`, `much_later`, `never`; skips prompt if provided)
- `--resolution` (optional; required when `--quadrant never`)
- `--phase` (optional; integer, phase number this finding is associated with)

Non-interactive flow (all required flags provided):
- Validate. Exit 1 with an error message if `--quadrant never` and `--resolution` is missing.
- Write directly without prompts.

Interactive flow (some flags missing):
1. Prompt for finding description (multiline; end with a blank line).
2. Show the four quadrant choices and prompt for selection.
3. If `never`: prompt for resolution reason.
4. Confirm before writing.

In both flows:
1. If `docs/cer/backlog.md` does not exist: render `backlog.md.j2` with `cer_entries=[]` and
   write it first.
2. Read the existing backlog.md, determine the next CER-NNN ID (sequential across all
   quadrants; start at CER-001 if empty).
3. Insert the new entry under the correct quadrant section table.
4. Update the `last_updated` header line.
5. Write back.

Use the `sys.path.insert` guard.

Add tests to `tests/pairmode/test_cer.py`:
- Non-interactive: appends entry to the correct quadrant section.
- `--quadrant never` with no `--resolution`: exits 1.
- IDs are sequential (CER-001, CER-002, ...) across multiple calls.
- Running against a project without `backlog.md` creates the file.
- Multiple calls accumulate entries correctly.
- `backlog.md` exists but has unexpected content: graceful error, not a crash.

---

### Story 7.6 — Orchestrator template updates for brief.md and CER

**Acceptance criterion:** `CLAUDE.build.md.j2` reads `docs/brief.md` first in the pre-loop read
list and includes a "CER backlog review" step in the checkpoint sequence that blocks on open
"Do Now" entries. Tests pass.

**Instructions:**

Update `skills/pairmode/templates/CLAUDE.build.md.j2`.

**Part A — Before the first build loop:**

In `## Before the first build loop`, update the numbered list to lead with:
1. Read `docs/brief.md` in full (operator intent — what and why).
2. Read `docs/architecture.md` in full.
3. Read the current phase file from `docs/phases/phase-N.md` (or `docs/phase-prompts.md` for
   legacy projects that have not migrated to per-phase files).
4. Run `git log --oneline -20` to identify the most recently completed story.
5. Identify the next story. Check for a ⚙️  DEVELOPER ACTION gate.

**Part B — Checkpoint sequence, CER backlog step:**

Insert a new step **4** between intent review (step 3) and tagging (existing step 4). Renumber
the existing tag and report steps to 5 and 6.

New step 4:

```
### 4. CER backlog review

Check `docs/cer/backlog.md` for any "Do Now" entries without a resolution.

If open "Do Now" entries exist:
  Stop. Report:

    CHECKPOINT BLOCKED — Open CER findings
    The following "Do Now" items must be resolved before tagging:
      [list each: CER-NNN — finding text]

    Options: fix the issue (update backlog.md resolution), or re-triage to a lower
    quadrant with an explicit reason.

If no open "Do Now" entries (or backlog.md does not exist): proceed to step 5.
```

**Part C — Checkpoint report:**

In the step 6 report block, add a `CER backlog:` line after `Intent review:`:
```
CER backlog:  [N open Do Now / clean]
```

Add tests to `tests/pairmode/test_templates.py`:
- Render `CLAUDE.build.md.j2`; assert "docs/brief.md" appears before "docs/architecture.md"
  in the before-the-first-build-loop section.
- Render `CLAUDE.build.md.j2`; assert "CER backlog review" heading is present.
- Render `CLAUDE.build.md.j2`; assert the checkpoint report block contains "CER backlog:".
- Regression: assert all pre-Phase-7 checkpoint lines still present (build gate, security
  audit, intent review, git tag) — no regressions from CER step insertion.

---

### Story 7.7 — Audit and sync integration for Phase 7 files

**Acceptance criterion:** `audit.py` reports MISSING for `docs/brief.md`, `docs/phases/index.md`,
and `docs/cer/backlog.md` when absent. `sync.py` creates them when MISSING. `SKILL.md` documents
the new `phase_new` and `cer` commands with correct CLI invocations. Tests pass.

**Instructions:**

**Part A — audit.py: file-existence checks:**

Add to the MISSING check list in `audit.py`:
- `docs/brief.md` (description: "Operator intent — what and why; see Story 7.1")
- `docs/phases/index.md` (description: "Per-phase prompt index; see Story 7.2")
- `docs/cer/backlog.md` (description: "CER triage backlog; see Story 7.3")

These are file-existence checks only. If the file is present, it is not flagged (no section
comparison). If absent, it is MISSING.

**Part B — sync.py: create missing Phase 7 files:**

For each of the three new MISSING files, add a handler that renders the appropriate template
and writes the file. Use `pairmode_context.json` as context. Fall back to blank defaults for
keys absent from context (`what`, `why` → empty strings; `cer_entries` → empty list;
`phases` → one Phase 1 placeholder; `last_updated` → today).

**Part C — SKILL.md: new command blocks:**

Add a `/anchor:pairmode phase-new` command block covering: when to use (lazy phase scaffolding),
inputs (phase-id, optional title/goal), what it does, outputs.

Add a `/anchor:pairmode cer` command block covering: when to use (after a CER session to record
findings), inputs, what it does, outputs.

Add CLI invocation blocks:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/phase_new.py" \
  --project-dir "$(pwd)" --phase-id N

PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/cer.py" \
  --project-dir "$(pwd)"
```

Add tests to `tests/pairmode/test_audit.py`:
- `audit_project` reports `docs/brief.md` MISSING when absent.
- `audit_project` reports `docs/phases/index.md` MISSING when absent.
- `audit_project` reports `docs/cer/backlog.md` MISSING when absent.
- With all three files present, none are reported MISSING.

Add tests to `tests/pairmode/test_sync.py`:
- `sync_project` creates `docs/brief.md` when MISSING.
- `sync_project` creates `docs/phases/index.md` when MISSING.
- `sync_project` creates `docs/cer/backlog.md` when MISSING.
- Roundtrip: bootstrap fresh project → delete `docs/brief.md` → audit reports MISSING →
  sync creates it → audit reports clean.

Note: Story 7.7 audit checks are file-existence only. Templates from Stories 7.1–7.3 must
exist before these tests pass. Build stories in order.

---

⚙️  DEVELOPER ACTION — Sync managed projects with Phase 7 artifacts

After all Phase 7 stories pass review, run `/anchor:pairmode sync` against each managed
project to pick up `docs/brief.md`, `docs/phases/`, and `docs/cer/backlog.md`.

For each project's `docs/brief.md`: populate the `what` and `why` fields from that project's
existing operator intent documentation. The brief is the canonical one-page summary; existing
project-specific source documents remain in place alongside it.

Confirm this action is complete before saying "Continue building Phase 8".

---


## Phase 8 — See docs/phases/phase-8.md
