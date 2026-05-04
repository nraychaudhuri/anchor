# anchor — Phase 15: Rails, eras, and story structure — foundation

← [Phase 14: Reconstruction agent tooling](phase-14.md)

## Goal

Introduce rails, eras, and discrete story files as first-class artifacts in the pairmode
methodology. Currently stories live embedded in phase docs — hard to move, hard to scan,
impossible to pre-authorize. Phase 15 establishes:

- **Rails** — named architectural lanes that declare a story's primary domain. Rail prefix
  + 3-digit sequence gives every story a stable, portable ID (`BOOTSTRAP-003`, `AUDIT-007`).
- **Era documents** — strategic containers above phases. An era defines a period of development
  with a unified intent; phases and rails belong to an era.
- **Story files** — individual Markdown files with structured frontmatter (`primary_files`,
  `touches`, `status`). Phase docs become manifests that reference story IDs; story content
  lives in `docs/stories/<RAIL>/RAIL-NNN.md`.
- **Tooling** — `story_new.py` and `era_new.py` scripts; updated `phase_new.py` manifest
  format; bootstrap rail suggestion and confirmation.

Rails for the pairmode project itself are defined here as a concrete example of the output:

| Rail | Primary domain |
|------|----------------|
| BOOTSTRAP | bootstrap.py, ideology capture |
| AUDIT | audit.py, sync.py, cer.py |
| RECONSTRUCT | reconstruct.py, score.py, ideology_parser.py |
| LESSON | lesson.py, lesson_review.py |
| BUILD | CLAUDE.build.md, phase_new.py, story_new.py, era_new.py, cer.py |
| TEMPLATE | templates/, agents/ templates |
| AGENT | .claude/agents/ rendered files |
| INFRA | story_context.py, spec_exception.py, security guards, shared utils |

Prerequisites: Phase 14 complete and tagged cp14-reconstruction-agent-tooling.

---

### Story 15.0 — Directory structure and file format schemas

**Acceptance criterion:** `docs/stories/` and `docs/eras/` directories exist in the pairmode
templates scaffold. Story file format, era file format, and phase manifest format are documented
and validated by tests. Tests pass.

**Instructions:**

**Part A — Directory stubs in the pairmode templates scaffold:**

Add to `skills/pairmode/templates/docs/`:
- `stories/.gitkeep` — creates the stories root in bootstrapped projects
- `eras/.gitkeep` — creates the eras root in bootstrapped projects

These are empty sentinel files so the directories are created on bootstrap even before any
stories or eras exist.

**Part B — Story file format:**

A story file lives at `docs/stories/<RAIL>/<RAIL>-NNN.md`. Frontmatter fields:

```yaml
---
id: RAIL-NNN
rail: RAIL
title: Short descriptive title
status: draft | planned | in-progress | complete | backlog
phase: "NNN"   # three-digit phase number, or "backlog" if unassigned
primary_files:
  - relative/path/to/primary/file.py
touches:
  - relative/path/to/secondary/file.py   # optional; omit if none
---
```

Body sections (same content as today's embedded stories):
```markdown
## Acceptance criterion
...

## Instructions
...

## Tests
...
```

**Part C — Era file format:**

An era file lives at `docs/eras/NNN-kebab-name.md`. Frontmatter fields:

```yaml
---
id: "NNN"
name: Human-readable era name
status: active | complete
---
```

Body:

```markdown
## Strategic intent

One paragraph describing the focus of this era.

## Rails

| Rail | Primary domain |
|------|----------------|
| RAIL | what this rail covers |

## Phases

| Phase | Title |
|-------|-------|
| NNN | Phase title |
```

**Part D — Phase manifest format:**

Phase manifests add a frontmatter block to the existing phase doc format:

```yaml
---
era: "NNN"
---
```

And the Stories section becomes a reference table instead of embedded story text:

```markdown
## Stories

| ID | Title | Status |
|----|-------|--------|
| RAIL-NNN | Story title | planned |
```

Full story content is no longer embedded. The phase doc contains goal, era reference, and
the story reference table only.

**Part E — Schema validator:**

Create `skills/pairmode/scripts/schema_validator.py` with:

```python
def validate_story_file(path: Path) -> list[str]:
    """Return list of validation errors, empty if valid."""

def validate_era_file(path: Path) -> list[str]:
    """Return list of validation errors, empty if valid."""

def validate_phase_manifest(path: Path) -> list[str]:
    """Return list of validation errors, empty if valid."""
```

Use `python-frontmatter` (add to `requirements.txt` if not present) or parse YAML manually
with stdlib `re` — check what's already available before adding a dependency.

**Tests — `tests/pairmode/test_schema_validator.py`** (new file):
- Valid story file: returns empty error list.
- Story file missing `id` field: error detected.
- Story file missing `primary_files`: error detected.
- Story file with invalid `status` value: error detected.
- Valid era file: returns empty error list.
- Era file missing `status`: error detected.
- Valid phase manifest (has `era` frontmatter): returns empty error list.
- Phase manifest missing `era` frontmatter: error detected.

---

### Story 15.1 — `story_new.py`: create story files with rail assignment

**Acceptance criterion:** `skills/pairmode/scripts/story_new.py` exists. Running it creates
a properly-formatted story file in the correct rail directory with the next sequence number.
If the specified rail does not exist, it prompts before creating it. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/story_new.py` as a Click CLI:

```python
@click.command()
@click.option("--rail", required=True, help="Rail name (e.g. BOOTSTRAP, AUDIT). Case-insensitive; stored uppercase.")
@click.option("--title", required=True, help="Story title.")
@click.option("--phase", default=None, help="Phase number (NNN) to assign this story to.")
@click.option("--project-dir", default=".", type=click.Path(exists=True, file_okay=False))
def story_new(rail, title, phase, project_dir):
    """Create a new story file on the specified rail."""
```

Logic:
1. Resolve `project_dir`. Apply standard path traversal guard.
2. Normalize rail name to uppercase.
3. Check if `<project_dir>/docs/stories/<RAIL>/` exists.
   - If not: prompt `"Rail <RAIL> does not exist. Create it? [Y/n] "`. Abort on `n`.
   - If creating: mkdir the directory. If a current era exists (`docs/eras/`), add the rail
     to the era's Rails table.
4. Scan existing `<RAIL>-NNN.md` files in the directory. Next sequence = max existing + 1,
   padded to 3 digits (`001`, `002`, ...). Start at `001` if none exist.
5. Write `<project_dir>/docs/stories/<RAIL>/<RAIL>-NNN.md` with frontmatter and section stubs.
6. If `--phase` given: open `<project_dir>/docs/phases/<phase>-*.md` (glob for the file),
   find the `## Stories` table, and append a row `| <RAIL>-NNN | <title> | draft |`.
7. Print: `  Created <RAIL>-NNN: <title>` (and `  Added to Phase <phase>` if applicable).

**SKILL.md:** Add `/anchor:pairmode story` section documenting the command.

**Tests — `tests/pairmode/test_story_new.py`** (new file):
- Creates story file at correct path with correct ID.
- Sequence increments: second story on same rail gets `002`.
- New rail prompt: declining aborts, no directory created.
- New rail prompt: accepting creates directory and story.
- `--phase` flag: story row added to phase manifest.
- `primary_files` defaults to empty list in frontmatter (not omitted).
- Path traversal guard: too-shallow project_dir → non-zero exit.

---

### Story 15.2 — `era_new.py`: create era documents

**Acceptance criterion:** `skills/pairmode/scripts/era_new.py` exists. Running it creates a
properly-formatted era document in `docs/eras/` with the next sequential ID. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/era_new.py` as a Click CLI:

```python
@click.command()
@click.option("--name", required=True, help="Era name (human-readable, e.g. 'Ideology capture').")
@click.option("--goal", default="", help="Strategic intent paragraph.")
@click.option("--project-dir", default=".", type=click.Path(exists=True, file_okay=False))
def era_new(name, goal, project_dir):
    """Create a new era document."""
```

Logic:
1. Resolve `project_dir`. Apply path traversal guard.
2. Create `docs/eras/` if it does not exist.
3. Scan existing `NNN-*.md` files. Next ID = max + 1, padded to 3 digits. Start at `001`.
4. Slugify `name` (lowercase, hyphens) for the filename: `docs/eras/<NNN>-<slug>.md`.
5. Write the era file with frontmatter and section stubs (Rails table empty, Phases table empty).
6. Print: `  Created era <NNN>: <name>` at `docs/eras/<NNN>-<slug>.md`.

**Tests — `tests/pairmode/test_era_new.py`** (new file):
- Era file created at correct path with correct ID.
- ID increments correctly for second era.
- `docs/eras/` created if absent.
- `--goal` populates Strategic intent section.
- Path traversal guard.

---

### Story 15.3 — Updated `phase_new.py`: manifest format with era reference

**Acceptance criterion:** `phase_new.py` writes the new manifest format: frontmatter with
`era` reference, Goal section, and an empty Stories table. If a current active era exists,
it is auto-detected and referenced. The era's Phases table is updated. Tests pass.

**Instructions:**

Update `skills/pairmode/scripts/phase_new.py`:

1. After resolving project_dir, detect the current active era:
   - Scan `docs/eras/*.md` for a file with `status: active`.
   - If exactly one found: use its `id` as the era reference.
   - If none found: era field is omitted (null era — phases before Era structure was added).
   - If multiple active: warn and use the most recently created (highest ID).

2. Write phase doc in new manifest format:

```markdown
---
era: "NNN"
---

# anchor — Phase NNN: <title>

← [Phase NNN-1: <prev title>](phase-NNN-1.md)

## Goal

<goal>

## Stories

| ID | Title | Status |
|----|-------|--------|

---

### CP-NNN Cold-eyes checklist

— developer fills in after phase completion —
```

3. If an active era was found, append the new phase to that era's Phases table.

**Tests — `tests/pairmode/test_phase_new.py`** (new or updated file):
- Phase file has `era` frontmatter when active era exists.
- Phase file has empty Stories table.
- Era Phases table updated when active era found.
- No era present: phase file created without `era` frontmatter (no crash).

---

### Story 15.4 — Bootstrap: rail suggestion, confirmation, and Era 001

**Acceptance criterion:** `bootstrap.py` suggests rails at bootstrap time, prompts for
confirmation, creates rail directories, and initializes `docs/eras/001-initial.md`. Tests pass.

**Instructions:**

**Part A — Rail defaults by project type:**

Add to `bootstrap.py` near the top:

```python
PAIRMODE_DEFAULT_RAILS = {
    "generic": ["CORE", "INFRA", "TEST"],
    "web": ["API", "UI", "DB", "AUTH", "INFRA", "TEST"],
    "cli": ["CORE", "INFRA", "TEST"],
    "pairmode": ["BOOTSTRAP", "AUDIT", "RECONSTRUCT", "LESSON", "BUILD", "TEMPLATE", "AGENT", "INFRA"],
}
```

**Part B — Rail initialization after scaffold write:**

After writing scaffold files, call `_initialize_rails(project_dir, context, stack)`:

1. Infer `project_type` from `stack` string (look for web/api/ui keywords → "web"; cli/terminal
   keywords → "cli"; default → "generic").
2. Present suggestions: print suggested rails and prompt
   `"Confirm rails (enter to accept, or type comma-separated list to override): "`.
   In non-TTY or `--ideology-skip`: silently create the defaults without prompting.
3. For each confirmed rail: create `docs/stories/<RAIL>/` directory.
4. Create `docs/eras/001-initial.md` (via era_new logic or inline) with:
   - `name`: derived from `project_name` (e.g., "Initial development")
   - `status: active`
   - Rails table populated from confirmed rails.
5. Update Phase 1 manifest (`docs/phases/001-*.md` if it exists) to set `era: "001"` frontmatter.

**Part C — SKILL.md:** Document rail initialization in bootstrap section.

**Tests — `tests/pairmode/test_bootstrap.py`:**
- Bootstrap creates `docs/stories/<RAIL>/` directories for default rails.
- Bootstrap creates `docs/eras/001-initial.md`.
- Era 001 Rails table contains confirmed rails.
- `--ideology-skip`: rails created without prompting.
- Re-bootstrap: rail directories and era 001 not overwritten if they exist.

---

⚙️ DEVELOPER ACTION — Initialize anchor's own rail structure

After Story 15.4 passes review, run bootstrap in the anchor repo to initialize rails and
Era 001 for anchor's own pairmode project:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/bootstrap.py \
  --project-dir . --ideology-skip
```

When prompted for rails, enter: `BOOTSTRAP,AUDIT,RECONSTRUCT,LESSON,BUILD,TEMPLATE,AGENT,INFRA`

Then move the three existing open CER items into story files:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/story_new.py \
  --rail INFRA --title "Add --yes flag to bootstrap for non-interactive callers" --project-dir .
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/story_new.py \
  --rail INFRA --title "Add len(parts) depth guard to cer.py and phase_new.py" --project-dir .
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/story_new.py \
  --rail INFRA --title "Replace startswith with relative_to in lesson_review.py" --project-dir .
```

Update those story files with the acceptance criteria from the CER backlog, then mark them
`status: backlog` in their frontmatter.

Tag: `cp15-rails-eras-story-structure`
