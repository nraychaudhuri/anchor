## Phase 9 — Bug fixes and architectural cleanup

Five targeted fixes identified at the Phase 8 checkpoint: one dead-code removal, two cer.py
correctness bugs, a phase_new.py incomplete fix from Story 8.3, a hook architecture violation,
and an overly broad deny rule that blocks the orchestrator from updating docs/checkpoints.md
at checkpoint time.

Prerequisites: Phase 8 developer action gate complete. All Phase 8 stories committed and tagged cp8.

---

### Story 9.0 — sync.py: remove orphaned dead code

**Acceptance criterion:** The orphaned `return enriched` statement at `sync.py:163` is removed.
No other dead code exists in `_load_project_context()`. Tests pass.

**Instructions:**

`sync.py` contains an orphaned `return enriched` at line 163, immediately after the real
`return context` of `_load_project_context()`. It was left when `_enrich_context_for_phase7`
was removed in Story 8.0. If reached (it cannot be under current call paths), it would raise
`NameError: name 'enriched' is not defined`.

Remove the dead `return enriched` line. Do not touch any other code.

Verify: `grep -n "return enriched" skills/pairmode/scripts/sync.py` returns no output.

Add a test to `tests/pairmode/test_sync.py`:
- Import `inspect` and `sync`; assert `"enriched" not in inspect.getsource(sync._load_project_context)`.
  (Source-level check — this dead code path cannot be exercised by a unit test.)

---

### Story 9.1 — cer.py: project_name path and table pipe corruption

**Acceptance criterion:** `cer.py` reads `project_name` from `.companion/pairmode_context.json`
(matching the path bootstrap.py writes). Finding text containing `|` characters is escaped
before being written to the backlog table. Tests pass.

**Instructions:**

**Bug 1 — Wrong project_name path (MEDIUM):**
`cer.py:append_finding()` (~line 208) reads:
```python
context_path = project_dir / "pairmode_context.json"
```
Bootstrap writes to `project_dir / ".companion" / "pairmode_context.json"`. Fix to:
```python
context_path = project_dir / ".companion" / "pairmode_context.json"
```
Update the test in `tests/pairmode/test_cer.py` that creates the context file so it writes
to the `.companion/` subdirectory to match the real path.

**Bug 2 — Pipe `|` in finding text corrupts markdown table (LOW):**
`append_finding()` stores `finding` and `reviewer` directly in the entry dict, which is then
rendered by the Jinja template as `{{ entry.finding }}` and `{{ entry.source }}` inside table
cells. A literal `|` in either field breaks the row.

Add an escape helper and apply it in `append_finding()` before building the entry dict:
```python
def _escape_table_cell(text: str) -> str:
    return text.replace("|", "\\|")
```
In `append_finding()`:
```python
entry: dict = {
    "id": new_id,
    "finding": _escape_table_cell(finding),
    "source": _escape_table_cell(reviewer),
    ...
}
```

Add tests to `tests/pairmode/test_cer.py`:
- `project_name` from `.companion/pairmode_context.json`: write context file to
  `tmp_dir / ".companion" / "pairmode_context.json"`; assert rendered backlog uses that name.
- Finding with `|` in text: call `append_finding()` with `finding="foo | bar"`;
  assert the rendered backlog row contains `foo \| bar` and not a broken table.

---

### Story 9.2 — phase_new.py: thread project_name into _create_index

**Acceptance criterion:** `_create_index()` uses the real project name (not hardcoded `"project"`)
when rendering `index.md` for the first time. Tests pass.

**Instructions:**

`phase_new.py:_create_index()` renders `docs/phases/index.md.j2` with `project_name="project"`
hardcoded (line ~113). The `_load_project_name()` function is already called in the main CLI
flow (line ~183) but its result is not passed through to `_create_index()`.

Add `project_name: str = "project"` as a parameter to `_create_index()`:
```python
def _create_index(index_path: Path, phase_id: int, phase_title: str, project_name: str = "project") -> None:
```
Replace the hardcoded `project_name="project"` in the template render call with the parameter.
Remove the comment `# project_name is unknown here; use a placeholder`.
Update all call sites to pass the project_name loaded by `_load_project_name()`.

Add tests to `tests/pairmode/test_phase_new.py`:
- `_create_index()` called with `project_name="MyProject"`: rendered index.md contains
  "MyProject" (the template uses `{{ project_name }}` in its heading).
- `_create_index()` with default fallback: renders without crash.

---

### Story 9.3 — exit_plan_mode.py: remove direct state.json write

**Acceptance criterion:** `exit_plan_mode.py` does not write to `.companion/state.json`. The
mode change is sent as a `mode_change` pipe event. The sidebar handles `mode_change` events by
updating `state["mode"]`. Tests pass.

**Instructions:**

`hooks/exit_plan_mode.py` (~lines 30–35) directly mutates `.companion/state.json`:
```python
state["mode"] = "implementation"
with open(STATE_PATH, "w") as f:
    json.dump(state, f, indent=2)
```
This violates the hook pipe contract: hooks relay events to the pipe only; state mutation is
the sidebar's responsibility.

**Part A — Hook change:**
Remove `STATE_PATH = ".companion/state.json"` and the entire state read/write block.
Add a `mode_change` pipe event using the existing `os.write(fd, ...)` pattern already in the
file for the plan event:
```python
mode_event = json.dumps({"event": "mode_change", "mode": "implementation"}) + "\n"
# write to the same fd used for the plan event
```

**Part B — Sidebar handler (new code):**
In `skills/companion/scripts/sidebar.py`, the pipe reader dispatches on `data["event"]`.
Add a new branch for `"mode_change"`:
```python
elif event_type == "mode_change":
    mode = data.get("mode", "")
    if mode:
        state["mode"] = mode
        _save_state(state)
```
(Use whatever state-save helper already exists in sidebar.py.)

This is a **protected file** modification — `hooks/exit_plan_mode.py` is in `hooks/`.
Stated reason: removing an architecture violation (direct state write from hook).

Add tests to `tests/pairmode/test_pipe_isolation.py` (or a new `tests/pairmode/test_hooks.py`):
- Read `hooks/exit_plan_mode.py` source; assert `"STATE_PATH"` and `'open(STATE_PATH, "w")'`
  do not appear (structural check that the violation has been removed).
- Assert `"mode_change"` appears in the hook source (confirms pipe event is sent).

---

### Story 9.4 — bootstrap.py DEFAULT_DENY and anchor settings: scope docs deny rules

**Acceptance criterion:** `DEFAULT_DENY` in `bootstrap.py` protects `docs/phases/**` and
`docs/brief.md` (currently unprotected). Anchor's own `.claude/settings.json` replaces blanket
`docs/**` rules with the same targeted set. The orchestrator can write to `docs/checkpoints.md`
and `docs/cer/backlog.md` without hitting a deny rule. Tests pass.

**Instructions:**

**Part A — bootstrap.py DEFAULT_DENY:**
The current `DEFAULT_DENY` list protects `docs/architecture.md` but not `docs/phases/**` or
`docs/brief.md` — the other critical docs that builders should not modify.

Add to `DEFAULT_DENY`:
```python
"Edit(docs/phases/**)",
"Write(docs/phases/**)",
"Edit(docs/brief.md)",
"Write(docs/brief.md)",
```
`docs/checkpoints.md` and `docs/cer/backlog.md` are intentionally left unprotected —
they are operational files updated by the orchestrator and cer CLI respectively.

**Part B — anchor's `.claude/settings.json`:**
Lines 21–22 of `/mnt/work/anchor/.claude/settings.json` currently read:
```json
"Edit(docs/**)",
"Write(docs/**)"
```
Replace these two lines with the targeted set (matching what Part A adds to DEFAULT_DENY plus
the existing `docs/architecture.md` entries):
```json
"Edit(docs/phases/**)",
"Write(docs/phases/**)",
"Edit(docs/architecture.md)",
"Write(docs/architecture.md)",
"Edit(docs/brief.md)",
"Write(docs/brief.md)"
```

Add tests to `tests/pairmode/test_bootstrap.py`:
- Assert `"Edit(docs/phases/**)"` and `"Write(docs/phases/**)"` are in `DEFAULT_DENY`.
- Assert `"Edit(docs/brief.md)"` and `"Write(docs/brief.md)"` are in `DEFAULT_DENY`.
- Assert `"Edit(docs/**)"` and `"Write(docs/**)"` are NOT in `DEFAULT_DENY`.
- Assert `"Edit(docs/checkpoints.md)"` and `"Edit(docs/cer/backlog.md)"` do not appear
  in `DEFAULT_DENY` (confirm operational files remain writable).

---

⚙️  DEVELOPER ACTION — Update docs/checkpoints.md after Phase 9 tags

After all Phase 9 stories pass review and cp9 is tagged (deny rule fix from 9.4 now in effect):

1. Add cp7, cp8, and cp9 entries to `docs/checkpoints.md`. Tag names:
   - cp7-phase7-templates
   - cp8-sync-tooling-fixes
   - cp9-final-cleanup

2. Verify: `grep "cp7\|cp8\|cp9" docs/checkpoints.md` shows all three.
