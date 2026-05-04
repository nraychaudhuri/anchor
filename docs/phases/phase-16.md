# anchor — Phase 16: Build loop integration and rail-aware review

← [Phase 15: Rails, eras, and story structure — foundation](phase-15.md)

## Goal

Phase 15 established the structural artifacts (story files, era docs, phase manifests, rails).
Phase 16 wires them into the active build loop and review pipeline:

1. **`permission_scope.py`** — before spawning the builder, write story-scoped `allow` rules
   from the story's `primary_files` and `touches` declarations to `.claude/settings.local.json`.
   After the reviewer commits or reverts, clean them up. In-scope edits require no prompting.
   Out-of-scope edits still prompt — which is now a signal, not noise.

2. **`story_resolver.py`** — orchestrator helper that resolves a story ID (`BOOTSTRAP-003`)
   to its file path, reads it, and returns full content for the builder.

3. **Updated `CLAUDE.build.md`** — orchestrator now reads phase manifests, resolves story IDs,
   pre-writes permissions, and cleans up after each story.

4. **Rail violation detection** — reviewer and intent-reviewer get an explicit rail scope check:
   did the builder touch files outside the declared `primary_files` and `touches`? Did it cross
   into another rail's primary domain without declaration?

5. **Sync: new standard rail prompting** — when syncing, detect pairmode default rails that
   the project does not have and offer to add them.

Prerequisites: Phase 15 complete and tagged cp15-rails-eras-story-structure.

---

### Story 16.0 — `permission_scope.py`: story-scoped allow rules lifecycle

**Acceptance criterion:** `skills/pairmode/scripts/permission_scope.py` exists with
`write_story_permissions(story_path, project_dir)` and `clear_story_permissions(project_dir)`.
Permissions are written to `.claude/settings.local.json` before a build session and removed
cleanly after. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/permission_scope.py`:

```python
def write_story_permissions(story_path: Path, project_dir: Path) -> None:
    """Read story primary_files + touches; add Edit/Write allow rules to
    .claude/settings.local.json. Record added rules in .claude/story_scope.json."""

def clear_story_permissions(project_dir: Path) -> None:
    """Read .claude/story_scope.json; remove the recorded rules from
    .claude/settings.local.json; delete story_scope.json."""
```

Implementation details:

**`write_story_permissions`:**
1. Read story frontmatter from `story_path`. Import `schema_validator` and call
   `schema_validator._parse_frontmatter(text)` — do not re-implement the parser inline.
   `schema_validator.py` is the canonical frontmatter parser for all pairmode scripts.
2. Collect all paths: `primary_files` + `touches` (deduplicated).
3. For each path, generate two rules: `Edit(<path>)` and `Write(<path>)`.
   Also generate `Read(<path>)` for `touches` entries only.
4. Read `.claude/settings.local.json` (start from `{}` if absent).
5. Merge generated rules into `permissions.allow` (no duplicates).
6. Write `settings.local.json` back.
7. Write `.claude/story_scope.json` with the list of rules that were added:
   ```json
   {"story_id": "RAIL-NNN", "added_rules": ["Edit(path/to/file)", ...]}
   ```
8. Add `.claude/story_scope.json` to `.gitignore` if not already present.

**`clear_story_permissions`:**
1. If `.claude/story_scope.json` does not exist: no-op, return.
2. Read the `added_rules` list from `story_scope.json`.
3. Read `.claude/settings.local.json`.
4. Remove any entries from `permissions.allow` that appear in `added_rules`.
5. Write `settings.local.json` back.
6. Delete `story_scope.json`.

**Edge cases:**
- `write_story_permissions` is idempotent: calling twice does not duplicate rules.
- If `settings.local.json` has no `permissions` key, create it.
- If `permissions.allow` does not exist, create it as an empty list before merging.
- If `primary_files` and `touches` are both empty (story not yet filled in): emit a warning
  to stderr and write zero rules — do not crash or write an empty `story_scope.json`.

**Tests — `tests/pairmode/test_permission_scope.py`** (new file):
- `write_story_permissions` adds `Edit(file)` and `Write(file)` for each primary file.
- `write_story_permissions` adds `Read(file)` for `touches` entries.
- `write_story_permissions` is idempotent (no duplicate rules on second call).
- `write_story_permissions` merges with existing rules without removing them.
- `clear_story_permissions` removes only the story-scoped rules; existing rules unaffected.
- `clear_story_permissions` with no `story_scope.json`: no-op, no error.
- `story_scope.json` created on write, deleted on clear.
- `settings.local.json` created from scratch if absent.

---

### Story 16.1 — `story_resolver.py`: resolve story IDs to content

**Acceptance criterion:** `skills/pairmode/scripts/story_resolver.py` exists with
`resolve_story(story_id, project_dir)` which finds and reads the story file for a given ID.
`list_phase_stories(phase_path)` parses a phase manifest and returns ordered story IDs.
Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/story_resolver.py`:

```python
def resolve_story(story_id: str, project_dir: Path) -> dict:
    """Find and read the story file for a given ID (e.g. 'BOOTSTRAP-003').

    Returns dict with keys: id, rail, title, status, phase, primary_files,
    touches, body (full markdown body below frontmatter).

    Raises FileNotFoundError if the story file does not exist.
    """

def list_phase_stories(phase_path: Path) -> list[str]:
    """Parse a phase manifest and return story IDs in order.

    Reads the ## Stories table and returns IDs from the ID column.
    Returns empty list if no Stories table found (legacy phase format).
    """
```

Implementation:
- `resolve_story`: parse `story_id` to extract rail and sequence
  (`BOOTSTRAP-003` → rail=`BOOTSTRAP`, seq=`003`). Find the file at
  `project_dir / "docs" / "stories" / rail / f"{story_id}.md"`.
  Parse frontmatter and body separately.
- `list_phase_stories`: scan the phase doc for the `## Stories` table. Extract
  IDs from the first column. Skip the header row and separator row.

**Tests — `tests/pairmode/test_story_resolver.py`** (new file):
- `resolve_story` finds and parses a story file correctly.
- `resolve_story` raises `FileNotFoundError` for unknown ID.
- `resolve_story` returns correct `primary_files` list.
- `list_phase_stories` returns story IDs in order from a manifest.
- `list_phase_stories` returns empty list for a legacy phase doc (no Stories table).
- Invalid story ID format (no hyphen): raises `ValueError`.

---

### Story 16.2 — Updated `CLAUDE.build.md`: manifest-aware orchestrator

**Acceptance criterion:** `CLAUDE.build.md` describes the updated build loop: reading story
IDs from phase manifests, resolving to story files, pre-writing permissions before the builder,
and cleaning up after the reviewer. A developer following these instructions gets autonomous
in-scope builds without mid-session prompts. Tests pass (doc-only story; validate via template
test that the updated agent templates render correctly).

**Instructions:**

Update `CLAUDE.build.md` — replace the "Before the first build loop" and "Build loop" sections:

**Before the first build loop (updated):**

```markdown
1. Read `/docs/brief.md` and `/docs/architecture.md`.
2. Read the current phase file `docs/phases/NNN-name.md`.
3. Run `git log --oneline -20` to identify the last completed story.
   A story is complete if a commit with `story-<RAIL>-NNN` exists.
4. Read the phase manifest's ## Stories table. Identify the first story
   with status `planned` (or no matching commit).
5. Resolve that story ID to its full content:
   `docs/stories/<RAIL>/<RAIL>-NNN.md`
6. Check for ⚙️ DEVELOPER ACTION gates before that story. Block if present.
```

**Build loop Step 1 (updated — before spawning builder):**

```markdown
Before spawning the builder:
1. Run permission_scope.write_story_permissions(story_path, project_dir)
   to write story-scoped allow rules to .claude/settings.local.json.
   This pre-authorizes all edits within the story's declared scope.
   The builder session will not prompt for edits to declared files.
```

**Build loop Step 2 (updated — after reviewer):**

```markdown
After the reviewer commits or reverts:
1. Run permission_scope.clear_story_permissions(project_dir)
   to remove story-scoped allow rules from .claude/settings.local.json.
2. Update the story file status to `complete` (if committed) or leave
   as `planned` (if reverted).
3. Update the phase manifest Stories table status column.
```

Also update the commit message format guidance: story commits now use
`feat(story-RAIL-NNN)` format (e.g., `feat(story-BOOTSTRAP-003)`).

**SKILL.md:** Update `/anchor:pairmode bootstrap` and add a note about the build loop
permission pre-writing in the orchestrator workflow section.

No new test file. The doc changes are validated by the build process itself.

---

### Story 16.3 — Rail violation detection in reviewer and intent-reviewer

**Acceptance criterion:** The reviewer checklist (CLAUDE.md) and the reviewer/intent-reviewer
agent templates have an explicit rail scope check. A diff that touches files outside the story's
declared `primary_files` and `touches` is flagged MEDIUM. A diff that crosses into another
rail's primary domain without declaration is flagged HIGH. Tests (template rendering) pass.

**Instructions:**

**Part A — Update CLAUDE.md reviewer checklist item 9:**

Replace the current STORY SCOPE check:

```markdown
9. RAIL SCOPE
   Read the story's `primary_files` and `touches` declarations from
   `docs/stories/<RAIL>/<RAIL>-NNN.md`.
   - Any file in the diff NOT listed in `primary_files` or `touches`:
     flag MEDIUM (undeclared file touched — possible scope creep).
   - Any file in the diff whose path falls under a different rail's primary
     domain (check `docs/stories/<OTHER_RAIL>/` ownership) AND is not in
     `touches`: flag HIGH (rail violation — architectural boundary crossed
     without explicit declaration).
   - If story file not found (legacy story): fall back to checking that
     touched files match the story description text. Flag undeclared
     out-of-scope changes MEDIUM as before.
```

**Part B — Update `agents/reviewer.md.j2` and `agents/intent-reviewer.md.j2`:**

Add to the reviewer template's checklist section:

```
10. RAIL SCOPE (new stories only — skip if story has no story file)
    Read story primary_files and touches. Flag any diff file outside both lists
    as MEDIUM. Flag any diff file in another rail's primary domain as HIGH.
```

Add to the intent-reviewer template's pivot detection section:

```
- Cross-rail file touches: did the builder modify files outside the story's
  declared rail(s)? If yes and no design pivot note was provided, flag as
  an undocumented pivot.
```

**Tests — `tests/pairmode/test_templates.py`:**
- `agents/reviewer.md.j2` renders and contains "RAIL SCOPE".
- `agents/intent-reviewer.md.j2` renders and contains "Cross-rail".

---

### Story 16.4 — Sync: prompt for new standard rails

**Acceptance criterion:** `sync.py` detects pairmode default rails absent from the project
and prompts to add them. Tests pass.

**Instructions:**

In `sync.py`, after existing sync checks, add a rail gap check:

```python
def _check_rail_gaps(project_dir: Path, stack: str) -> list[str]:
    """Return list of default rails for this stack not present in docs/stories/."""
```

Logic:
1. If `docs/stories/` does not exist: return empty (project pre-dates rail structure).
2. Determine `project_type` from stack using the same inference as `bootstrap.py`.
3. Load `PAIRMODE_DEFAULT_RAILS[project_type]` (import from bootstrap.py).
4. Check which of those rails do NOT have a directory under `docs/stories/`.
5. Return the missing ones.

In `sync()` (or `audit()`):
- Call `_check_rail_gaps`. For each missing rail:
  - Print: `  ⚠ Standard rail <RAIL> not in this project.`
  - Prompt: `"Add rail <RAIL>? [y/N] "`. If yes: create `docs/stories/<RAIL>/` and add to
    current active era's Rails table.

**Tests — `tests/pairmode/test_sync.py`** (or new `test_rail_gaps.py`):
- Missing default rail returned by `_check_rail_gaps`.
- Present rail not returned.
- `docs/stories/` absent: returns empty (no crash).
- Sync prompts for missing rail; accepting creates directory.
- Declining leaves directory absent.

---

### Story 16.5 — Security fix: path containment guard in `permission_scope.py`

**Acceptance criterion:** `write_story_permissions` validates each path from `primary_files`
and `touches` against `project_dir` before generating allow rules. Any path that resolves
outside `project_dir` (absolute paths, `..` traversal, `~` home expansion) is rejected with
a warning and skipped — it does not become an allow rule. Tests pass.

**Instructions:**

In `skills/pairmode/scripts/permission_scope.py`, add a `_safe_path` helper and call it
before generating each allow rule:

```python
def _safe_path(raw: str, project_dir: _Path) -> _Path | None:
    """Resolve raw path string relative to project_dir.
    Return the resolved Path if it stays within project_dir, else None."""
    try:
        candidate = (project_dir / raw).resolve()
        candidate.relative_to(project_dir.resolve())
        return candidate
    except (ValueError, OSError):
        return None
```

In `write_story_permissions`, replace the raw-string path loop with:

```python
for raw in primary_files:
    if _safe_path(raw, project_dir) is None:
        sys.stderr.write(
            f"permission_scope: warning: path '{raw}' is outside project_dir; skipping.\n"
        )
        continue
    if raw not in seen:
        seen.add(raw)
        new_rules.append(f"Edit({raw})")
        new_rules.append(f"Write({raw})")

for raw in touches:
    safe = _safe_path(raw, project_dir)
    if safe is None:
        sys.stderr.write(
            f"permission_scope: warning: path '{raw}' is outside project_dir; skipping.\n"
        )
        continue
    if raw not in seen:
        seen.add(raw)
        new_rules.append(f"Edit({raw})")
        new_rules.append(f"Write({raw})")
    read_rule = f"Read({raw})"
    if read_rule not in new_rules:
        new_rules.append(read_rule)
```

**Tests — `tests/pairmode/test_permission_scope.py`** (extend existing file):
- Traversal path in `primary_files` (`../../etc/passwd`): skipped, no allow rule generated,
  warning written to stderr.
- Absolute path in `primary_files` (`/etc/passwd`): skipped, no allow rule generated.
- Valid relative path alongside traversal path: valid path produces rules; traversal skipped.
- All-traversal story: zero rules written, no `story_scope.json` created (because `new_rules`
  is empty after filtering — keep the existing empty-list guard behavior).

---

⚙️ DEVELOPER ACTION — Verify no stale permissions after Phase 16

After Story 16.0 passes review, confirm `.claude/story_scope.json` is absent (no leftover
story permissions from the build):

```bash
ls .claude/story_scope.json 2>/dev/null && echo "PRESENT — run clear" || echo "Clean"
```

If present: `PATH=$HOME/.local/bin:$PATH uv run python -c "
import sys; sys.path.insert(0, 'skills/pairmode/scripts')
from permission_scope import clear_story_permissions
from pathlib import Path
clear_story_permissions(Path('.'))
print('Cleared')
"`

Tag: `cp16-build-loop-integration`
