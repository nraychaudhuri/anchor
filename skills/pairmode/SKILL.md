---
name: anchor:pairmode
description: Bootstrap, audit, sync, and manage pairmode methodology for this project.
allowed-tools: AskUserQuestion, Bash, Read, Write
---

# anchor:pairmode

Manage the pairmode methodology lifecycle for a project — from initial scaffolding through ongoing
audit, sync, and lesson capture.

---

## Commands

### `/anchor:pairmode bootstrap`

**When to use:** When starting pairmode on a new or existing project for the first time, or when
re-scaffolding a project after a major methodology revision.

**Inputs expected:**
- `.companion/product.json` in the target project — used to populate project-specific values in
  the scaffold (project name, description, tech stack, team conventions).
- The project's Anchor spec (`openspec/specs/`) if available — used to derive non-negotiables
  for the deny list in `.claude/settings.json`.
- Target project root path (prompted if not provided).

**What it does:**
1. Reads `.companion/product.json` from the target project.
2. Reads the project's Anchor spec if available; falls back to blank-slate defaults if not.
3. Renders all Jinja2 templates in `skills/pairmode/templates/` against the project context.
4. Generates the deny list in `.claude/settings.json` from spec non-negotiables, each rule
   annotated with a comment linking it to the source non-negotiable.
5. Writes scaffold files immediately on a fresh project. For each file that already exists,
   prompts for confirmation before overwriting that individual file.
6. Records `pairmode_version` in `.companion/state.json` for future audit comparisons.

**Outputs:**
- `CLAUDE.md` — project methodology guide (root)
- `CLAUDE.build.md` — build orchestrator instructions (root)
- `docs/brief.md` — project brief
- `docs/ideology.md` — intent and conviction record
- `docs/reconstruction.md` — reconstruction brief for independent agent
- `docs/architecture.md` — architecture reference
- `docs/checkpoints.md` — checkpoint tag commands
- `docs/phases/index.md` — phase index table
- `docs/phases/phase-1.md` — initial phase scaffold
- `docs/cer/backlog.md` — cold-eyes review triage backlog
- `.claude/settings.json` — permissions file with spec-derived deny list
- `.companion/state.json` — companion state with `pairmode_version` set
- `.claude/agents/builder.md`, `reviewer.md`, `loop-breaker.md`, `security-auditor.md`,
  `intent-reviewer.md` — skipped if they already exist unless `--force-agents` is passed.
- `.claude/agents/reconstruction-agent.md` — skipped if already exists unless `--force-agents` is passed.

**Orchestrator workflow — permission pre-writing:**
After bootstrapping, the build orchestrator (`CLAUDE.build.md`) manages permissions around
each story build loop:
- Before spawning the builder: calls `permission_scope.write_story_permissions(story_path, project_dir)`
  to write story-scoped allow rules to `.claude/settings.local.json`. This pre-authorizes all
  edits declared in the story's `primary_files` and `touches` fields so the builder session
  does not prompt mid-build.
- After the reviewer commits or reverts: calls `permission_scope.clear_story_permissions(project_dir)`
  to remove those allow rules, restoring the project's default deny posture.

Story commits use the format: `feat(story-RAIL-NNN)` (e.g., `feat(story-BOOTSTRAP-003)`).

**CLI invocation:**
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/bootstrap.py" \
  --project-dir "$(pwd)"
```
Note: `--project-dir` is the only required flag. Other values (project name, stack, etc.) are read from `.companion/product.json` or prompted interactively.

**Agent file ownership:**
Agent files in `.claude/agents/` are treated as project-owned after first bootstrap. Bootstrap will not overwrite them on subsequent runs unless `--force-agents` is passed explicitly. This preserves project-specific customisations made to agent definitions after initial scaffolding.

**Rail initialization:**
After writing scaffold files, bootstrap infers the project type from the stack string and suggests a set of default rails:

| Project type | Inferred when stack or name contains | Default rails |
|---|---|---|
| `pairmode` | "pairmode" | BOOTSTRAP, AUDIT, RECONSTRUCT, LESSON, BUILD, TEMPLATE, AGENT, INFRA |
| `web` | "web", "api", "ui", "flask", "django", "fastapi", "react", "vue" | API, UI, DB, AUTH, INFRA, TEST |
| `cli` | "cli", "terminal", "argparse", "click", "typer" | CORE, INFRA, TEST |
| `generic` | (default) | CORE, INFRA, TEST |

In TTY mode (without `--ideology-skip`), bootstrap prompts:
```
Confirm rails (enter to accept, or type comma-separated list to override):
```
In non-TTY mode or with `--ideology-skip`, rails are created from defaults without prompting.

For each confirmed rail, bootstrap creates `docs/stories/<RAIL>/`. Bootstrap also creates `docs/eras/001-initial.md` with the confirmed rails in its Rails table and sets `status: active`. If `docs/phases/phase-1.md` exists without an `era` frontmatter field, bootstrap prepends `era: "001"` to its frontmatter.

Rail initialization is idempotent: existing rail directories and `docs/eras/001-initial.md` are not overwritten on re-bootstrap.

To overwrite existing agent files:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/bootstrap.py" \
  --project-dir "$(pwd)" --force-agents
```

**Ideology capture (TTY mode):**
When bootstrap is run interactively (TTY), it automatically prompts for ideology content before
writing `docs/ideology.md`:
1. Up to 3 core convictions (each skippable with blank input)
2. Top value hierarchy entry (skippable)
3. Most important constraint rule (skippable)
4. Must-preserve reconstruction element (skippable)

In non-TTY mode, `docs/ideology.md` is written as a placeholder with a warning. Pass `--conviction`
or `--constraint` flags to populate it non-interactively.

**Flags:**
- `--project-dir PATH` — target project root (default: current directory)
- `--project-name NAME` — project name (read from `product.json` or prompted if omitted)
- `--stack TEXT` — technology stack (prompted if omitted)
- `--what TEXT` — what the project produces (prompted in TTY; blank left as-is in non-TTY with warning)
- `--why TEXT` — why the project exists (prompted in TTY; blank left as-is in non-TTY with warning)
- `--build-command TEXT` — build/test command (inferred from project files or prompted if omitted)
- `--phase-title TEXT` — title for the initial `docs/phases/phase-1.md` (prompted in TTY if omitted; blank allowed)
- `--phase-goal TEXT` — goal for the initial `docs/phases/phase-1.md` (prompted in TTY if omitted; blank allowed)
- `--dry-run` — print what would be written without writing anything
- `--force-agents` — overwrite existing agent files in `.claude/agents/` (default: skip if present)
- `--ideology-skip` — skip guided ideology capture; write placeholder `docs/ideology.md`
- `--conviction TEXT` — core conviction (repeatable); bypasses TTY prompt, populates ideology.md directly
- `--constraint TEXT` — key constraint rule (repeatable); bypasses TTY prompt, populates ideology.md directly
- `--from-reconstruction PATH` — path to a `reconstruction.md` brief; pre-populates ideology context from it, seeding a new pairmode project without manual TTY entry
- `--yes` / `-y` — auto-confirm all prompts (file overwrites, rail confirmation, ideology capture). Use for non-interactive or CI invocations where no stdin is available.

**Pre-populating from a reconstruction brief:**
```bash
# Pass a reconstruction.md brief to pre-populate ideology context
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/bootstrap.py" \
  --project-dir "$(pwd)" --from-reconstruction path/to/reconstruction.md
```

---

### `/anchor:pairmode audit`

**When to use:** Compare a project's current pairmode scaffold against the canonical methodology
to see what's drifted, missing, or project-specific.

**Inputs:**
- Current directory (used as project-dir)
- Optional: project type tag for lesson filtering (defaults to "all")

Note: `pairmode_context.json` (created by `/anchor:pairmode bootstrap`) must exist for INCONSISTENT results to be meaningful.

**What it does:**
1. Check for `.companion/state.json` in current directory (reads `pairmode_version`).
2. Run: `PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/audit.py" --project-dir "$(pwd)"`
3. Display the output (MISSING / INCONSISTENT / EXTRA sections).
4. If there are MISSING or INCONSISTENT items, ask: "Run sync to apply these changes?"
   - If yes → run sync (documented in sync command below)
   - If no → display the output and stop

**Output format:**
```
AUDIT: <project_name> vs pairmode v<version>

MISSING
  ✗ <file>: <description>

STALE PLACEHOLDER
  ⚠ docs/ideology.md: all sections contain placeholder text
    Recommendation: run bootstrap in TTY to trigger guided ideology capture,
    or edit docs/ideology.md directly.

INCONSISTENT
  ~ <file>: <description>

EXTRA (project-specific, keep as-is)
  ✓ <file>: <description>

RECOMMENDATION
  Run /anchor:pairmode sync to apply missing/inconsistent items
  Project-specific items will be preserved
```

**Ideology staleness detection:**
`docs/ideology.md` is checked separately from scaffold files (not in `SCAFFOLD_FILES` or
`EXISTENCE_CHECK_FILES`). The check uses `_check_ideology_staleness()`:
- `docs/ideology.md` absent → `MISSING` finding
- All required sections contain only placeholder text (`_(not yet specified…`) → `STALE PLACEHOLDER`
  finding with recommendation to run guided ideology capture
- At least one section has real content → clean (no finding)

**Reconstruction staleness detection:**
- Detects missing or stale `docs/reconstruction.md` (run `/anchor:pairmode reconstruct` to fix).
- `docs/reconstruction.md` absent → `MISSING` finding
- File contains the generated-brief footer (`Generated from \`docs/ideology.md\``) and all
  required scoring sections are placeholder-only → `STALE PLACEHOLDER` finding
- Completed scoring report (no generated footer) → clean (no finding)

**Suppressing intentional customisation noise with `.pairmode-overrides`:**
Projects may declare sections that are intentionally diverged from the canonical templates
by placing a `.pairmode-overrides` file at the project root. Sections declared in this file
are treated as EXTRA (project-owned) rather than INCONSISTENT or MISSING. Sync will never
overwrite or append a declared override section.

File format — one entry per line: `<relative-file-path>:<normalised-section-key>`
The section key is the lowercased, stripped header text (e.g. `## Review checklist` → `review checklist`).
Lines starting with `#` are comments; blank lines are ignored. Example:
```
CLAUDE.md:review checklist
.claude/agents/reviewer.md:checklist
```

Bootstrap creates an empty `.pairmode-overrides` from `templates/.pairmode-overrides.j2` so
the format is documented for the project owner from day one.

**Outputs:**
- A human-readable audit report printed to the session, summarizing all deltas and recommended
  actions. No files are written.

---

### `/anchor:pairmode sync`

**When to use:** Apply missing or inconsistent items from an audit result to bring a project's
pairmode scaffold up to date with the current canonical methodology.

**Inputs:**
- Current directory (used as project-dir)
- Optional: project type tag for lesson filtering (defaults to "all")

Note: `pairmode_context.json` (created by `/anchor:pairmode bootstrap`) must exist for INCONSISTENT results to be meaningful.

**What it does:**
1. Run audit to get current delta: `PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/audit.py" --project-dir "$(pwd)"`
2. Display the audit result
3. If no MISSING or INCONSISTENT items: report "Already up to date" and stop
4. Otherwise, confirm with user before applying changes
5. Run: `PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/sync.py" --project-dir "$(pwd)"`
6. Display sync output

**Output format:**
```
SYNC COMPLETE — <project_name>

Applied:
  ✓ <description of each change>

Preserved:
  → <project-specific items kept>

State updated: .companion/state.json
```

**What it never does:**
- Never overwrites project-specific content (EXTRA items)
- Never modifies hooks/ or spec files
- Never runs without showing audit output first

---

### `/anchor:pairmode lesson`

**When to use:** At the end of a session (or any time) when a meaningful methodology insight has
emerged — a workflow problem solved, a pattern discovered, a failure mode identified.

**Inputs expected (prompted interactively via AskUserQuestion, or as CLI arguments):**
- **trigger** — what situation or event prompted this lesson.
- **problem** — what went wrong or was inefficient.
- **learning** — the insight or corrective pattern.
- **methodology_change** — how the methodology (templates, process, tooling) should change as
  a result.
- **affects** — which components are affected (e.g. `reviewer_checklist`, `builder_agent`).
- **applies_to** — which project types this applies to (e.g. `all`, `python`, `typescript`).
- **source_project** — (optional) the project that produced this lesson; defaults to `unknown`.

**What it does:**
1. Loads the current `anchor/lessons/lessons.json`.
2. Generates the next sequential lesson ID (L001, L002, …).
3. Constructs a lesson entry with `id`, `date` (today), `source_project`, `trigger`, `problem`,
   `learning`, `methodology_change` (with `affects` and `description`), `applies_to`, and
   `status: captured`.
4. Appends the entry to `anchor/lessons/lessons.json` via `lesson_utils.save_lessons()`, which
   enforces the append-only invariant (existing entries may only have `status` changed).
5. Calls `lesson_utils.generate_lessons_md()` and writes the result to `lessons/LESSONS.md`.
6. Returns the captured lesson dict and prints a confirmation with the lesson `id`.

**Lesson schema written to lessons.json:**
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

**CLI invocation (for testing and direct use):**
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/lesson.py" \
  --trigger "Builder skipped tests" \
  --problem "Tests failed after story was marked done." \
  --learning "Always run tests before marking a story done." \
  --methodology-change "Add test gate to builder checklist." \
  --affects reviewer_checklist \
  --affects builder_agent \
  --applies-to all \
  --source-project my-project
```

**Outputs:**
- New entry appended to `anchor/lessons/lessons.json`.
- `lessons/LESSONS.md` regenerated from the updated lessons store.
- Confirmation message with the lesson `id` printed to stdout.

---

### `/anchor:pairmode review`

**When to use:** When enough lessons have accumulated to warrant a methodology update cycle —
typically before a major bootstrap or sync campaign across projects.

**Inputs expected:**
- `anchor/lessons/lessons.json` — must exist with at least one lesson with `status: captured`
  or `status: reviewed`.
- User approval or rejection for each proposed template change (handled via AskUserQuestion
  in the skill; `lesson_review.py` provides the underlying logic).

**What it does:**
1. Calls `load_reviewable_lessons()` — loads all lessons with `status: captured` or
   `status: reviewed` from `anchor/lessons/lessons.json`.
2. Calls `group_lessons_by_affects()` — groups lessons by the `methodology_change.affects`
   values. A lesson with `affects: ["all"]` appears under every known affects key
   (`reviewer_checklist`, `builder_agent`, `orchestrator`, `checkpoint_sequence`).
3. For each lesson, calls `propose_template_change()` to produce a proposal dict:
   - `lesson_id` — the lesson's ID
   - `affects` — the specific affects value for this proposal
   - `template_file` — relative path to the template to edit (see mapping below)
   - `description` — the methodology change description from the lesson
   - `lesson_trigger` — copied from lesson for context
   - `lesson_learning` — copied from lesson for context
4. Presents each proposed change to the user (via AskUserQuestion) with the source
   lesson and rationale.
5. For approved lessons: calls `apply_template_change(proposal, change_text)` which
   appends a Jinja2 comment block `{# LESSON <id>: <change_text> #}` to the template
   file, then marks the lesson `status: applied`.
6. For rejected lessons: marks the lesson `status: reviewed` (for future consideration).
7. Calls `regenerate_lessons_md()` to write an updated `lessons/LESSONS.md`.

**Affects → template file mapping:**

| affects value         | template file                                         |
|-----------------------|-------------------------------------------------------|
| `reviewer_checklist`  | `skills/pairmode/templates/CLAUDE.md.j2`              |
| `builder_agent`       | `skills/pairmode/templates/agents/builder.md.j2`      |
| `orchestrator`        | `skills/pairmode/templates/CLAUDE.build.md.j2`        |
| `checkpoint_sequence` | `skills/pairmode/templates/CLAUDE.build.md.j2`        |
| `all`                 | all three template files (one proposal per file)      |

---

### `/anchor:pairmode reconstruct`

**When to use:** After populating `docs/ideology.md`, or any time the ideology evolves and
`docs/reconstruction.md` needs refreshing without a full bootstrap.

**Inputs expected:**
- `docs/ideology.md` in the target project (required).
- `docs/brief.md` (optional — used for what/why context).
- Target project root path (defaults to current directory).

**What it does:**
1. Reads and parses `docs/ideology.md` to extract convictions, constraints, must-preserve
   items, free-to-change items, should-question items, and comparison dimensions.
2. Reads `docs/brief.md` (if present) for what/why context.
3. Renders `docs/reconstruction.md` — the handoff prompt for a blank-slate reconstruction agent.
4. Prompts for confirmation if `docs/reconstruction.md` already exists (use `--force` to skip).

**Outputs:**
- `docs/reconstruction.md` at the target project root.

**CLI invocation:**
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/reconstruct.py" \
  --project-dir "$(pwd)"
```

**Flags:**
- `--project-dir PATH` — target project root (default: current directory)
- `--force` — overwrite existing `docs/reconstruction.md` without prompting

---

### `/anchor:pairmode score`

**When to use:** After completing a reconstruction implementation, to render a pre-populated
scoring report ready to fill in.

**What it does:**
1. Reads `docs/reconstruction.md` (or `--brief PATH`) to extract convictions, constraints, and rubric dimensions.
2. Renders `RECONSTRUCTION.md.j2` with those values pre-filled.
3. Writes `docs/RECONSTRUCTION.md` — the scoring report for the reconstruction agent to complete.

**CLI invocation:**
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/score.py" \
  --project-dir "$(pwd)"
```

**Flags:**
- `--project-dir PATH` — root of the reconstructed project (default: current directory)
- `--brief PATH` — path to reconstruction.md brief (default: `<project-dir>/docs/reconstruction.md`)
- `--force` — overwrite existing `docs/RECONSTRUCTION.md` without prompting

---

### `/anchor:pairmode phase-new`

> **Note:** `phase-new` is invoked directly via CLI, not through the pairmode skill dispatcher.
> Correct invocation:
> ```bash
> PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/phase_new.py" \
>   --project-dir "$(pwd)" --phase-id N
> ```

**When to use:** When starting a new build phase and you want to lazy-scaffold the phase
file without interrupting the flow. Run this instead of manually creating a phase file
from scratch.

**Inputs expected:**
- `--phase-id N` — the phase number (required).
- `--title TEXT` — optional phase title (defaults to "Phase N").
- `--goal TEXT` — optional one-line goal for the phase (defaults to empty).

**What it does:**
1. Renders `skills/pairmode/templates/docs/phases/phase.md.j2` with the provided phase ID,
   title, and goal, plus project context from `.companion/pairmode_context.json` if present.
2. Writes the rendered file to `docs/phases/phase-N.md` in the target project.
3. Updates `docs/phases/index.md` if it exists — appends the new phase row to the phase
   table. If `docs/phases/index.md` does not exist, it is created first.
4. Reports the file path written and the index row added.

**Outputs:**
- `docs/phases/phase-N.md` — scaffolded phase file with placeholder story slots.
- `docs/phases/index.md` — updated with the new phase row (created if absent).

**CLI invocation:**
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/phase_new.py" \
  --project-dir "$(pwd)" --phase-id N
```

Optional flags:
- `--phase-id N` — phase number (required)
- `--title TEXT` — phase title (default: "Phase N")
- `--goal TEXT` — phase goal summary (default: empty)
- `--dry-run` — print what would be written without writing anything

---

### `/anchor:pairmode cer`

> **Note:** `cer` is invoked directly via CLI, not through the pairmode skill dispatcher.
> Correct invocation:
> ```bash
> PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/cer.py" \
>   --project-dir "$(pwd)"
> ```

**When to use:** After a Cold-Eyes Review (CER) session to record findings in the project's
structured triage backlog. Run this once per review session to capture the findings before
they are forgotten.

**Inputs expected:**
- Findings from the CER session (provided interactively or via file).
- Each finding needs: finding text, quadrant (`now` / `later` / `much_later` /
  `never`), source reviewer name, and an optional phase reference.

**What it does:**
1. Reads existing `docs/cer/backlog.md` if present; creates it from template if absent.
2. Prompts for each new finding: text, quadrant, source, and phase.
3. Assigns the next sequential CER finding ID (CER-001, CER-002, …).
4. Appends each finding to the appropriate quadrant table in `docs/cer/backlog.md`.
5. Updates the `last_updated` date at the top of the file.

**Outputs:**
- `docs/cer/backlog.md` — updated with new findings in the appropriate quadrant tables.
  Existing findings are never removed or modified.

**CLI invocation:**
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/cer.py" \
  --project-dir "$(pwd)"
```

Optional flags:
- `--project-dir PATH` — target project root (default: current directory)
- `--finding TEXT` — finding text (repeatable; if omitted, prompts interactively)
- `--quadrant QUADRANT` — one of `now`, `later`, `much_later`, `never`
- `--reviewer TEXT` — reviewer name or identifier
- `--phase TEXT` — phase reference (e.g. "Phase 3")

**Template comment format written by `apply_template_change`:**
```
{# LESSON L001: <change_text> #}
```
This marks the location for the developer to implement the change manually. The comment
is appended to the end of the template file.

> **Note:** "Applying" a lesson writes a Jinja2 comment block that marks the change location. The developer must open the annotated template to implement the actual change. Lesson `status` is set to `applied` once the annotation is written — not once the template change is implemented. Always review annotated templates after running this command.

**CLI invocation (for direct use / automation):**
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/lesson_review.py" \
  --approve L001 \
  --approve L002 \
  --reject L003
```
- `--approve LESSON_ID` (repeatable): apply_template_change is called with the lesson's
  own description as change_text, then status is set to `applied`.
- `--reject LESSON_ID` (repeatable): status is set to `reviewed`.
- After processing all flags, `regenerate_lessons_md()` is called automatically.

**Outputs:**
- Jinja2 comment blocks appended to affected template files in `skills/pairmode/templates/`.
- Updated `status` fields in `anchor/lessons/lessons.json` (via `lesson_utils.save_lessons()`,
  which enforces the append-only invariant).
- `lessons/LESSONS.md` regenerated from the updated lessons store.
- A review summary printed to stdout.

---

### `/anchor:pairmode story`

> **Note:** `story` is invoked directly via CLI, not through the pairmode skill dispatcher.
> Correct invocation:
> ```bash
> PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/story_new.py" \
>   --project-dir "$(pwd)" --rail BOOTSTRAP --title "My story title"
> ```

**When to use:** When starting a new story on a named rail. Creates a structured story file
with frontmatter and section stubs, and optionally registers the story in a phase manifest.

**Inputs expected:**
- `--rail RAIL` — rail name (case-insensitive; stored uppercase). E.g. `BOOTSTRAP`, `AUDIT`.
- `--title TEXT` — story title (required).
- `--phase NNN` — optional phase number. When provided, appends a story row to the phase manifest.
- `--project-dir PATH` — target project root (default: current directory).

**What it does:**
1. Resolves and validates `project_dir` (path traversal guard: rejects paths with fewer than
   3 components).
2. Normalizes the rail name to uppercase.
3. Checks if `<project_dir>/docs/stories/<RAIL>/` exists.
   - If not: prompts `"Rail <RAIL> does not exist. Create it? [Y/n]"`. Aborts on `n`.
   - If creating: creates the directory. If a current era exists in `docs/eras/`, adds the
     rail to the era's Rails table.
4. Scans existing `<RAIL>-NNN.md` files in the rail directory. Next sequence = max existing + 1,
   zero-padded to 3 digits (`001`, `002`, …). Starts at `001` if none exist.
5. Writes `<project_dir>/docs/stories/<RAIL>/<RAIL>-NNN.md` with frontmatter and section stubs.
6. If `--phase` given: opens `<project_dir>/docs/phases/phase-<NNN>.md` (or glob for
   `<NNN>-*.md`), finds or creates the `## Stories` table, and appends a row
   `| <RAIL>-NNN | <title> | draft |`.
7. Prints: `  Created <RAIL>-NNN: <title>` (and `  Added to Phase <NNN>` if applicable).

**Story file format written:**
```yaml
---
id: RAIL-NNN
rail: RAIL
title: Story title
status: draft
phase: "NNN"
primary_files:
touches:
---
```
Followed by `## Acceptance criterion`, `## Instructions`, and `## Tests` section stubs.

**Flags:**
- `--rail RAIL` — rail name (required)
- `--title TEXT` — story title (required)
- `--phase NNN` — phase number to register this story in (optional)
- `--project-dir PATH` — target project root (default: current directory)
