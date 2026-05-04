# anchor — Phase 17: Correctness — fix all known bugs

← [Phase 16: Build loop integration and rail-aware review](phase-16.md)

## Goal

The self-review (Phase 16 post-checkpoint) identified six categories of correctness
issues: a policy violation in `phase_new.py` (inline parser re-implementation), a
silent data loss in `--from-reconstruction`, an ID collision risk in lessons, a
validator/creator contradiction for draft stories, missing depth guards in two entry
points, and a Jinja2 undefined inconsistency. This phase resolves all of them before
adding new features. A clean correctness baseline is required before the PR.

Prerequisites: Phase 16 complete and tagged cp16-build-loop-integration.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-006 | Fix phase_new.py canonical parser import and bootstrap era double-prepend | planned |
| INFRA-007 | Fix --from-reconstruction: include should_question and free_to_change | planned |
| LESSON-001 | Fix lesson_utils next_lesson_id collision risk; improve load_lessons error | planned |
| INFRA-008 | Fix validate_story_file draft exemption; fix era_new.py quoted id | planned |
| INFRA-009 | Fix depth guards in cer.py and phase_new.py; fix CER-008 _read_json non-dict | planned |
| INFRA-010 | Fix score.py StrictUndefined inconsistency; fix cer.py ID collision on malformed markdown | planned |

---

### Story INFRA-006 — Fix `phase_new.py` canonical parser import and bootstrap era double-prepend

**Rail:** INFRA

**Acceptance criterion:** `phase_new.py` imports `_parse_frontmatter` from
`schema_validator` instead of re-implementing it inline. `bootstrap.py`'s era
frontmatter prepend in `_initialize_rails` checks for existing `era` key via a
proper frontmatter parse before prepending, preventing double-frontmatter on
re-bootstrap. Tests pass.

**Instructions:**

**Part A — `phase_new.py` canonical parser import:**

1. Read `skills/pairmode/scripts/phase_new.py` in full. Locate the inline
   `_FRONTMATTER_RE` and `_parse_frontmatter` implementation (~lines 68–97).
2. Remove that inline implementation entirely.
3. At the top of the file (after other imports), add:
   ```python
   sys.path.insert(0, str(pathlib.Path(__file__).parent))
   from schema_validator import _parse_frontmatter
   ```
   (Check whether `sys.path.insert` is already present; if so, add only the import.)
4. Verify all call sites of `_parse_frontmatter` within `phase_new.py` now call
   the imported function. Run the existing `test_phase_new.py` tests — behavior
   must be unchanged.

**Part B — bootstrap era double-prepend guard:**

1. Read `skills/pairmode/scripts/bootstrap.py`. Find `_initialize_rails`. Locate
   the block that prepends era frontmatter to `docs/phases/001-*.md` (approximately
   lines 445–456). It currently checks `"era:" not in content`.
2. Replace the string-contains check with a proper parse:
   ```python
   existing_fm = _parse_frontmatter(content)
   if existing_fm is None or "era" not in existing_fm:
       content = '---\nera: "001"\n---\n\n' + content
       phase_file.write_text(content, encoding="utf-8")
   ```
3. Add the `schema_validator` import to bootstrap.py's sys.path block (same pattern
   as the existing imports there).

**Tests — `tests/pairmode/test_phase_new.py` and `tests/pairmode/test_bootstrap.py`:**
- All existing `test_phase_new.py` tests pass unchanged (behavior identical, just
  using imported function).
- New bootstrap test: create a phase-1 file that already has `---\nera: "001"\n---`
  frontmatter, run `_initialize_rails`, assert the file still has exactly one
  frontmatter block (no double-prepend).
- New bootstrap test: phase-1 file with no frontmatter → era frontmatter prepended.

---

### Story INFRA-007 — Fix `--from-reconstruction`: include `should_question` and `free_to_change`

**Rail:** INFRA

**Acceptance criterion:** `bootstrap.py --from-reconstruction` includes `should_question`
and `free_to_change` in the template rendering context. These ideology dimensions from
the reconstruction brief are no longer silently dropped. `ideology.md.j2` renders them
if they are present. Tests pass.

**Instructions:**

1. Read `skills/pairmode/scripts/bootstrap.py`. Find the `--from-reconstruction` branch
   where `parse_reconstruction_brief` is called and the context dict is built.
   (Approximately lines 700–750.) Confirm `should_question` and `free_to_change` are
   absent from the dict.
2. Read `ideology_parser.py` to confirm `parse_reconstruction_brief` returns both keys.
3. Add to the context dict:
   ```python
   "should_question": reco_context.get("should_question", []),
   "free_to_change":  reco_context.get("free_to_change", []),
   ```
4. Read `skills/pairmode/templates/docs/ideology.md.j2`. Verify whether it uses
   `should_question` and `free_to_change`. If sections exist for them: they will now
   render. If the sections are missing from the template: add them, matching the format
   of the existing `convictions` / `constraints` sections.

**Tests — `tests/pairmode/test_bootstrap.py`:**
- New test: write a reconstruction brief file containing:
  ```markdown
  ## Should-question assumptions
  - We should question whether batch processing is actually needed
  - We should question the current retry strategy
  ## Free to change
  - File naming conventions
  - Log formatting
  ```
  Run bootstrap with `--from-reconstruction`. Assert `docs/ideology.md` in the output
  project contains "should question whether batch processing" and "File naming conventions".
- New test: brief with no `should_question` section → `ideology.md` renders without error
  (empty list is fine).

---

### Story LESSON-001 — Fix `lesson_utils` next_lesson_id collision risk; improve load_lessons error

**Rail:** LESSON

**Acceptance criterion:** `next_lesson_id` uses `max(existing_numeric_ids) + 1` rather
than `len(lessons) + 1`, eliminating ID collision risk if any lesson were ever absent.
`load_lessons` raises a clear `RuntimeError` with actionable text when `lessons.json`
does not exist, rather than a bare `FileNotFoundError`. Tests pass.

**Instructions:**

In `skills/pairmode/scripts/lesson_utils.py`:

**`next_lesson_id` fix:**
```python
import re as _re

def next_lesson_id(lessons: list[dict]) -> str:
    nums = []
    for lesson in lessons:
        m = _re.match(r"L(\d+)$", lesson.get("id", ""))
        if m:
            nums.append(int(m.group(1)))
    return f"L{(max(nums) + 1):03d}" if nums else "L001"
```

**`load_lessons` fix:**
Wrap the file-not-found path:
```python
def load_lessons() -> list[dict]:
    if not LESSONS_FILE.exists():
        raise RuntimeError(
            f"lessons.json not found at {LESSONS_FILE}. "
            "Run '/anchor:pairmode lesson' to capture the first lesson and create it."
        )
    # ... rest of existing implementation
```

**Tests — `tests/pairmode/test_lesson_utils.py`** (or existing file):
- `next_lesson_id` with `[L001, L003]` (gap) → returns `L004`, not `L003`.
- `next_lesson_id` with empty list → `L001`.
- `next_lesson_id` with `[L001, L002, L010]` → `L011`.
- `load_lessons` when file absent → raises `RuntimeError` containing the word
  "lessons.json" and the path.
- `load_lessons` when file exists → returns list (existing behavior unchanged).

---

### Story INFRA-008 — Fix `validate_story_file` draft exemption; fix `era_new.py` quoted id

**Rail:** INFRA

**Acceptance criterion:** `validate_story_file` allows an empty `primary_files` list for
stories with `status: draft` or `status: backlog`. `era_new.py` writes `id: "NNN"` (quoted
YAML string), matching `bootstrap.py`. Tests pass.

**Instructions:**

**`validate_story_file` fix — `skills/pairmode/scripts/schema_validator.py`:**

Find the check that flags empty `primary_files`. Replace the unconditional check with:
```python
status = fm.get("status", "")
if status not in ("draft", "backlog"):
    if not fm.get("primary_files"):
        errors.append("primary_files must be non-empty for non-draft stories "
                      "(status is not 'draft' or 'backlog')")
```

**`era_new.py` fix — `skills/pairmode/scripts/era_new.py`:**

Find the frontmatter template string where the era id is written. Change:
```
id: {era_id}
```
to:
```
id: "{era_id}"
```
(Ensure the surrounding quotes are part of the written string literal, not Python
string delimiters.)

**Tests:**
- `validate_story_file` with `status: draft`, `primary_files: []` → no error.
- `validate_story_file` with `status: backlog`, `primary_files: []` → no error.
- `validate_story_file` with `status: planned`, `primary_files: []` → error.
- `validate_story_file` with `status: complete`, `primary_files: ["foo.py"]` → no error.
- `era_new.py` output: parse the written file, confirm `id` field value is the string
  `"001"` (not integer `1`).
- `validate_era_file` on `era_new.py` output → no errors.

---

### Story INFRA-009 — Fix depth guards in `cer.py` and `phase_new.py`; fix `_read_json` non-dict

**Rail:** INFRA

**Acceptance criterion:** `cer.py` and `phase_new.py` apply the standard
`len(project_path.parts) < 3` depth guard consistent with all other pairmode entry
points. `permission_scope._read_json` guards against non-dict JSON to prevent
`AttributeError` on malformed `settings.local.json`. Tests pass.

**Instructions:**

**`cer.py` depth guard:**
After `resolved = Path(project_dir).resolve()`, add:
```python
if not resolved.is_dir() or len(resolved.parts) < 3:
    click.echo("Error: --project-dir is too shallow or not a directory.", err=True)
    raise SystemExit(1)
```

**`phase_new.py` depth guard:**
Same pattern after its `Path(project_dir).resolve()` call. Check first that the guard
is not already present (it was flagged missing; add it).

**`permission_scope._read_json` non-dict guard:**
```python
def _read_json(path: _Path, *, default: object) -> dict:
    if not path.exists():
        return default  # type: ignore[return-value]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default  # type: ignore[return-value]
        return data
    except (json.JSONDecodeError, OSError):
        return default  # type: ignore[return-value]
```

**Tests:**
- `cer.py` CLI with `--project-dir /` → exits non-zero with error message.
- `cer.py` CLI with `--project-dir /tmp` → exits non-zero.
- `phase_new.py` CLI with `--project-dir /` → exits non-zero.
- `permission_scope._read_json` with a file containing `[1,2,3]` → returns `{}`.
- `permission_scope._read_json` with a file containing `"string"` → returns `{}`.
- `permission_scope._read_json` with a file containing `null` → returns `{}`.
- `permission_scope._read_json` with valid dict JSON → returns the dict (unchanged).

---

### Story INFRA-010 — Fix `score.py` StrictUndefined inconsistency; fix `cer.py` ID detection on malformed markdown

**Rail:** INFRA

**Acceptance criterion:** `score.py` uses `jinja2.Undefined` (lenient) consistent with
`reconstruct.py`, since both are read-only report generators that should never crash on
missing template variables. `cer.py` emits a clear warning when it parses a non-empty
backlog file but finds no table rows, preventing silent ID restart from CER-001. Tests pass.

**Instructions:**

**`score.py` Jinja2 fix:**
In `skills/pairmode/scripts/score.py`, in the Jinja2 Environment constructor, replace
`undefined=jinja2.StrictUndefined` with `undefined=jinja2.Undefined`.
Add a comment: `# Lenient — scoring report generation must not crash on missing brief fields.`

**`cer.py` malformed-markdown warning:**
In `skills/pairmode/scripts/cer.py`, after `_parse_entries_from_backlog` returns its
results: if the file exists and is non-trivially non-empty (more than 5 lines) but
zero rows were returned across all quadrants, emit:
```python
click.echo(
    "Warning: backlog.md exists but no table rows were parsed. "
    "The file may have non-standard formatting. "
    "Existing CER IDs may not be detected — verify before appending.",
    err=True,
)
```
Do not abort; warn and continue.

**Tests:**
- `score.py`: render a template that references an undefined variable (e.g., `{{ undefined_var }}`); assert no exception is raised and the output contains an empty string for that variable.
- `cer.py`: feed it a backlog file with 10+ lines of markdown but no `|`-delimited table rows → warning printed to stderr; process continues without error.
- `cer.py`: feed it a normal backlog file with CER-001 and CER-002 → no warning, CER-003 assigned to new finding.

---

⚙️ DEVELOPER ACTION — Update INFRA story files to reflect CER resolution

After Phase 17 passes review, update the INFRA backlog story files to reflect which
CER items are now resolved:

- `INFRA-002.md` (depth guards): mark `status: complete`
- `INFRA-004.md` (_read_json guard): mark `status: complete`

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/story_update.py \
  --story-id INFRA-002 --status complete --project-dir .
```

Note: `story_update.py` will not exist until Phase 18. After Phase 18, run the
above commands. For now, update the files manually.

Tag: `cp17-correctness-fixes`
