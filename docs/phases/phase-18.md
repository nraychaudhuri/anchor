# anchor — Phase 18: Missing tooling — story lifecycle, overrides, --yes, orchestrator clarity

← [Phase 17: Correctness — fix all known bugs](phase-17.md)

## Goal

Phase 17 fixed correctness issues. Phase 18 adds the tooling that was specced but
never implemented: `story_update.py` to close the story lifecycle loop, an override
mechanism to silence intentional audit divergences, the `--yes` flag for non-interactive
bootstrap, validator integration into the creation flow, and explicit bash commands in
the orchestrator so agents stop guessing at invocation syntax.

Prerequisites: Phase 17 complete and tagged cp17-correctness-fixes.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-001 | Add story_update.py to update story and phase manifest status | planned |
| AUDIT-001 | Add .pairmode-overrides: suppress intentional customisation noise in audit/sync | planned |
| BOOTSTRAP-001 | Add --yes flag to bootstrap for non-interactive callers (CER-002) | planned |
| INFRA-011 | Integrate schema_validator into story_new.py and era_new.py creation flow | planned |
| BUILD-002 | Update CLAUDE.build.md: explicit bash commands for permission_scope and story_update | planned |
| INFRA-005 | Security fix: validate story_id format in story_update.py (HIGH — path traversal) | planned |

---

### Story BUILD-001 — Add `story_update.py` to update story and phase manifest status

**Rail:** BUILD

**Acceptance criterion:** `skills/pairmode/scripts/story_update.py` exists as a Click
CLI and a set of importable functions. Running it updates a story file's frontmatter
`status` field and the corresponding row in any phase manifest `## Stories` table.
Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/story_update.py`:

```python
@click.command()
@click.option("--story-id", required=True,
    help="Story ID to update (e.g. BOOTSTRAP-003).")
@click.option("--status", required=True,
    type=click.Choice(["draft","planned","in-progress","complete","backlog"]))
@click.option("--project-dir", default=".", type=click.Path(exists=True, file_okay=False))
def story_update(story_id, status, project_dir):
    """Update a story file's status and sync the change to any phase manifest."""
```

**Public functions (importable):**

```python
def update_story_status(story_id: str, project_dir: Path, status: str) -> Path:
    """Update frontmatter status field in the story file.
    Returns the story file path. Raises FileNotFoundError if not found."""

def update_phase_story_status(story_id: str, project_dir: Path, status: str) -> list[Path]:
    """Find all phase manifests containing story_id in their Stories table.
    Update the status column in each matching row.
    Returns list of updated phase file paths."""
```

**Implementation details:**

`update_story_status`:
1. Apply path traversal guard on `project_dir`.
2. Parse story_id to extract rail (same as story_resolver: split on last hyphen+digits).
   Raise `ValueError` for invalid format.
3. Find `project_dir / "docs" / "stories" / rail / f"{story_id}.md"`.
   Raise `FileNotFoundError` if absent.
4. Read file text. Locate frontmatter block (between first `---` and second `---`).
   Replace `^status: .*$` (within frontmatter only) using a targeted regex replace.
   Write back.

`update_phase_story_status`:
1. Glob `project_dir / "docs" / "phases" / "*.md"` for all phase files.
2. For each: scan for `## Stories` table. Within the table, find any row whose first
   column matches `story_id` exactly (strip whitespace, case-sensitive).
3. Replace the `status` column value (third `|`-delimited cell) in that row.
4. Write updated content back. Return list of modified file paths.

`story_update` CLI:
1. Calls `update_story_status` then `update_phase_story_status`.
2. Prints:
   ```
     Updated RAIL-NNN: status → complete
     Phase manifest updated: docs/phases/017-correctness-fixes.md
   ```
   (Or "no phase manifest found" if no table row matches.)

**Tests — `tests/pairmode/test_story_update.py`** (new file):
- Story file status updated in frontmatter.
- Phase manifest status column updated for the correct row.
- Story not found → `FileNotFoundError`.
- Invalid story ID format → `ValueError`.
- Story in a phase manifest with multiple rows: only the matching row is updated.
- Two phase manifests both contain the story ID: both are updated.
- Status transitions: draft → planned → in-progress → complete all work correctly.
- `update_phase_story_status` returns empty list when no phase manifest contains the ID.

---

### Story AUDIT-001 — Add `.pairmode-overrides`: suppress intentional customisation noise in audit/sync

**Rail:** AUDIT

**Acceptance criterion:** A `.pairmode-overrides` file at the project root lets a project
declare which CLAUDE.md / agent file sections are intentionally diverged from the canonical
template. Audit treats declared sections as EXTRA (project-owned) rather than INCONSISTENT
or MISSING. `sync --yes` never overwrites declared override sections. Tests pass.

**Instructions:**

**File format — `.pairmode-overrides`:**
```
# Sections intentionally diverged from canonical pairmode templates.
# One entry per line: <relative-file-path>:<normalised-section-key>
# Lines starting with # are comments.
# Example:
CLAUDE.md:review checklist
.claude/agents/reviewer.md:checklist
```

The section key is the lowercased, stripped header text (same normalisation used
internally by audit — e.g., `## Review checklist` → `review checklist`).

**`audit.py` changes:**

Add a helper:
```python
def _load_overrides(project_dir: Path) -> set[tuple[str, str]]:
    """Return set of (relative_file_path, normalised_section_key) pairs."""
```

In the audit loop, before emitting an INCONSISTENT or MISSING finding for a
`(file, section_key)` pair:
```python
if (relative_file, section_key) in overrides:
    continue  # Intentionally diverged — skip
```

**`sync.py` changes:**

After loading overrides, before prompting the user to apply a section change:
if the section is in overrides, skip it with a note:
```
  (skipped: .pairmode-overrides declares this section as project-owned)
```

**Template — `skills/pairmode/templates/.pairmode-overrides.j2`:**
An empty file with only a comment block explaining the format. Bootstrapped projects
get this file pre-created so developers know it exists.

**`SKILL.md`:** Add a note under `/anchor:pairmode audit` about `.pairmode-overrides`.

**Tests — `tests/pairmode/test_audit.py`** (extend existing):
- INCONSISTENT finding suppressed when section is in `.pairmode-overrides`.
- MISSING finding suppressed when section is in `.pairmode-overrides`.
- Section NOT in `.pairmode-overrides` → finding still surfaces.
- No `.pairmode-overrides` file → no behavioral change.

**Tests — `tests/pairmode/test_sync.py`** (extend existing):
- Sync with a section in `.pairmode-overrides` → section skipped, message printed.

---

### Story BOOTSTRAP-001 — Add `--yes` flag to bootstrap for non-interactive callers (CER-002)

**Rail:** BOOTSTRAP

**Acceptance criterion:** `bootstrap.py` accepts `--yes` / `-y` to auto-confirm all
interactive prompts: file overwrites, rail confirmation, and any remaining ideology
prompts not already suppressed by `--ideology-skip`. Non-interactive callers and CI
pipelines can now bootstrap without piping input. Tests pass.

**Instructions:**

Add to `bootstrap.py` CLI:
```python
@click.option("--yes", "-y", is_flag=True, default=False,
    help="Auto-confirm all prompts. Use for non-interactive/CI invocations.")
```

Thread `yes: bool` through the call stack.

Replace each interactive confirmation in bootstrap:

1. File-write confirmation loop (the "already exists. Overwrite? [y/N]" prompt):
   ```python
   if dest.exists() and not yes:
       if not click.confirm(f"  {dest} already exists. Overwrite?", default=False):
           continue
   ```

2. Rail confirmation prompt in `_initialize_rails`:
   ```python
   if ideology_skip or yes or not sys.stdin.isatty():
       confirmed_rails = default_rails
   else:
       raw = click.prompt("Confirm rails (enter to accept, or type comma-separated list to override)", default="")
       confirmed_rails = [r.strip().upper() for r in raw.split(",")] if raw.strip() else default_rails
   ```

3. Any remaining `click.prompt` calls for ideology fields: when `yes=True`, use the
   default value (empty string / empty list) without prompting.

Update `_initialize_rails` signature to accept `yes: bool` and pass it through.

**SKILL.md:** Document `--yes` flag in the bootstrap section.

**Tests — `tests/pairmode/test_bootstrap.py`:**
- Bootstrap with `--yes`: all files written, no prompts, no stdin required.
- Bootstrap with `--yes` on existing project: files overwritten without prompt.
- Bootstrap with `--yes --ideology-skip`: completes fully non-interactively.
- Existing tests without `--yes` still pass (behavior unchanged when flag absent).

---

### Story INFRA-011 — Integrate `schema_validator` into `story_new.py` and `era_new.py` creation flow

**Rail:** INFRA

**Acceptance criterion:** `story_new.py` calls `validate_story_file` after writing
the new story file and prints any validation errors as warnings (non-fatal). `era_new.py`
calls `validate_era_file` the same way. Creation always exits 0 unless the file could
not be written. Tests pass.

**Instructions:**

**`story_new.py`:**
After writing the story file and printing `Created <RAIL>-NNN: <title>`, add:
```python
from schema_validator import validate_story_file as _vsf
errors = _vsf(story_path)
for e in errors:
    click.echo(f"  ⚠  validation: {e}", err=True)
```
(schema_validator is already importable via the sys.path insert in story_new.py.)

**`era_new.py`:**
Same pattern using `validate_era_file`.

**Expectation:** With Story 17.3's draft exemption in place, newly created story
files (which have `status: draft` and empty `primary_files`) should produce no
validation warnings. This test confirms the two fixes compose correctly.

**Tests:**
- `story_new.py` creates a story; no validation warnings printed (draft + empty
  primary_files is now valid per Story 17.3).
- `era_new.py` creates an era; no validation warnings printed.
- If a test monkeypatches the validator to return a fake error, the warning is
  printed to stderr and exit code is still 0.

---

### Story BUILD-002 — Update `CLAUDE.build.md`: explicit bash commands for permission_scope and story_update

**Rail:** BUILD

**Acceptance criterion:** `CLAUDE.build.md` and its Jinja2 template show the exact bash
commands the orchestrator should run for `write_story_permissions`,
`clear_story_permissions`, and `story_update` — not pseudocode Python function calls.
An orchestrator agent following these instructions can execute them without inferring
syntax. Tests pass (template rendering).

**Instructions:**

Read `CLAUDE.build.md` and `skills/pairmode/templates/CLAUDE.build.md.j2`.

**Replace Build loop Step 1 permission_scope pseudocode** with:

```markdown
Before spawning the builder, pre-authorize edits within the story's declared scope:

```bash
PATH=$HOME/.local/bin:$PATH uv run python -c "
import sys, pathlib
sys.path.insert(0, str(pathlib.Path('skills/pairmode/scripts').resolve()))
from permission_scope import write_story_permissions
from pathlib import Path
write_story_permissions(Path('docs/stories/RAIL/RAIL-NNN.md'), Path('.'))
"
```

Replace RAIL/RAIL-NNN with the current story's ID. After this runs, the builder
session will not prompt for edits to any file declared in primary_files or touches.
```

**Replace Build loop Step 3 post-reviewer section** with:

```markdown
After the reviewer commits or reverts:

1. Clean up story-scoped allow rules:
```bash
PATH=$HOME/.local/bin:$PATH uv run python -c "
import sys, pathlib
sys.path.insert(0, str(pathlib.Path('skills/pairmode/scripts').resolve()))
from permission_scope import clear_story_permissions
from pathlib import Path
clear_story_permissions(Path('.'))
"
```

2. If the reviewer committed (PASS): update the story status to complete:
```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/story_update.py \
  --story-id RAIL-NNN --status complete --project-dir .
```

3. If the reviewer reverted (FAIL): leave the story status as `planned`.
```

Apply identical changes to `skills/pairmode/templates/CLAUDE.build.md.j2`.

**Tests — `tests/pairmode/test_templates.py`:**
- `CLAUDE.build.md.j2` renders and contains "write_story_permissions".
- `CLAUDE.build.md.j2` renders and contains "clear_story_permissions".
- `CLAUDE.build.md.j2` renders and contains "story_update.py".

---

### Story INFRA-005 — Security fix: validate story_id format in story_update.py (HIGH — path traversal)

**Rail:** INFRA

**Protected file justification:** N/A — `story_update.py` is a new file added in Phase 18,
not a protected file.

**Acceptance criterion:** `story_update.py` validates the `--story-id` argument using
`_STORY_ID_RE` before any file path is constructed. A crafted story_id containing an
absolute path component (e.g., `/etc/passwd-001`) is rejected with a clear error before
any file I/O occurs. Tests pass.

**Background:** Security audit cp18 found that `_parse_story_id` in `story_update.py`
constructs `rail = '-'.join(parts[:-1])` without validating against the existing
`_STORY_ID_RE = re.compile(r'^([A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*)-(\d+)$')`. A
story_id like `/etc/passwd-001` produces `rail = "/etc/passwd"` which Python pathlib
interprets as an absolute path, bypassing `project_dir` containment entirely.

**Instructions:**

In `skills/pairmode/scripts/story_update.py`, in `_parse_story_id`:

```python
def _parse_story_id(story_id: str) -> tuple[str, str]:
    m = _STORY_ID_RE.match(story_id)
    if not m:
        raise ValueError(
            f"Invalid story ID format: {story_id!r}. "
            "Expected RAIL-NNN (e.g. BOOTSTRAP-003)."
        )
    rail = m.group(1)
    return rail, story_id
```

This replaces the manual split-and-join logic entirely. The regex already anchors the
full string and only allows `[A-Z][A-Z0-9]*` segments, preventing any path separator
or absolute path component from passing.

Also add a containment check on `story_path` in `update_story_status` after construction:

```python
story_path = resolved / "docs" / "stories" / rail / f"{story_id}.md"
try:
    story_path.resolve().relative_to(resolved)
except ValueError:
    raise FileNotFoundError(
        f"Story path {story_path} is outside project directory {resolved}"
    )
```

**Tests — `tests/pairmode/test_story_update.py`:**
- `_parse_story_id` with `/etc/passwd-001` → raises `ValueError`.
- `_parse_story_id` with `../../etc-001` → raises `ValueError`.
- `_parse_story_id` with `INFRA-001` → returns `("INFRA", "INFRA-001")` (still works).
- `update_story_status` with a crafted story_id that somehow passes regex → containment
  guard raises `FileNotFoundError` (test via monkeypatching `_STORY_ID_RE` to allow
  a path-like value, then confirming the secondary guard fires).

---

⚙️ DEVELOPER ACTION — Mark resolved CER items in backlog

After Phase 18 passes review, update `docs/cer/backlog.md`:
- CER-002 (`--yes` flag): add `**RESOLVED** Phase 18` to its row.
- Update INFRA backlog stories:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/story_update.py \
  --story-id INFRA-001 --status complete --project-dir .
```

Tag: `cp18-missing-tooling`
