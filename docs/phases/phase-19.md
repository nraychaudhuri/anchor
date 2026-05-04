# anchor — Phase 19: Test coverage and integration verification

← [Phase 18: Missing tooling](phase-18.md)

## Goal

Phase 19 fills test gaps identified in the self-review and verifies (and fixes) the
`spec_exception → sidebar` integration chain. Three test categories are addressed:
the `should_question`/`free_to_change` round-trip, the spec_exception pipe handler
in the companion sidebar, and a set of targeted gap closures for edge cases in
`phase_new.py`, `story_resolver.py`, and `cer.py`. The spec_exception handler was
already present in sidebar.py; INFRA-013 became test-only (no protected file modified).

Prerequisites: Phase 18 complete and tagged cp18-missing-tooling.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-012 | Test should_question/free_to_change round-trip through --from-reconstruction | planned |
| INFRA-013 | Verify and fix spec_exception → sidebar pipe chain | planned |
| BOOTSTRAP-002 | Test bootstrap --yes non-interactive path end to end | planned |
| INFRA-014 | Close targeted test gaps: phase_new era edge case, story_resolver link-format, cer.py ID detection | planned |

---

### Story INFRA-012 — Test `should_question`/`free_to_change` round-trip through `--from-reconstruction`

**Rail:** INFRA

**Acceptance criterion:** Integration tests verify the full round-trip: reconstruction
brief with `should_question` and `free_to_change` content → `bootstrap --from-reconstruction`
→ `ideology.md` output contains both. The round-trip introduced in Phase 17 is fully
covered. Tests pass.

**Instructions:**

In `tests/pairmode/test_bootstrap.py`, add a test class
`TestFromReconstructionShouldQuestionFreeToChange`:

**Fixture** — `reconstruction_brief_with_full_ideology(tmp_path)`: write a minimal
reconstruction brief file containing:
```markdown
## Non-negotiable ideology
- We prefer local-first storage

## What must survive any implementation
- The core pipeline contract

## What you should question
- We should question whether the batch size default is appropriate
- We should question whether Redis is the right backing store

## Free to change
- File naming conventions throughout the codebase
- Log output formatting

## Comparison rubric
- Ideological alignment
```

**Tests:**
- `test_should_question_in_ideology_md`: run `bootstrap --from-reconstruction` with the
  fixture brief. Read output `docs/ideology.md`. Assert it contains
  "batch size default" or "Redis is the right backing store".
- `test_free_to_change_in_ideology_md`: same run. Assert `ideology.md` contains
  "File naming conventions" or "Log output formatting".
- `test_empty_should_question_no_crash`: brief with no `## Should-question assumptions`
  section → bootstrap completes, `ideology.md` exists, no exception.
- `test_empty_free_to_change_no_crash`: brief with no `## Free to change` section →
  same expectation.

---

### Story INFRA-013 — Verify and fix `spec_exception → sidebar` pipe chain

**Rail:** INFRA

**Acceptance criterion:** `skills/companion/scripts/sidebar.py` correctly handles the
`spec_exception` pipe message type by calling `record_spec_exception`. The pipe-to-disk
chain for conflict records is end-to-end verified by a test. Tests pass.

**Protected file justification:** This story modifies `skills/companion/scripts/sidebar.py`,
a protected file. Justification: the `spec_exception` pipe message type is produced by
the sidebar's own override prompt UI and passed via pipe back to the sidebar's own pipe
reader — but the pipe reader has no handler for it, causing all conflict records to be
silently dropped. This is a data loss bug in the core capture pipeline, not a behavioural
change to hook architecture.

**Instructions:**

**Step 1 — Read and understand sidebar.py:**
Read `skills/companion/scripts/sidebar.py` in full. Find the pipe-reader loop. Identify
the dispatch pattern (likely a dict or if/elif chain keyed on `msg["type"]`).

**Step 2 — Verify the gap:**
Confirm that `spec_exception` is not handled. If it IS handled (i.e., the reviewer was
wrong): skip to Step 5 (write the confirmation test only).

**Step 3 — Implement the handler:**
Following the exact pattern of existing message handlers in the pipe-reader (e.g., the
`file_changed` handler), add a `spec_exception` handler:
```python
elif msg_type == "spec_exception":
    # msg payload matches record_spec_exception's parameters
    record_spec_exception(
        project_dir=Path(msg.get("project_dir", ".")),
        module=msg.get("module", ""),
        file_path=msg.get("file_path", ""),
        tool=msg.get("tool", ""),
        reason=msg.get("reason", ""),
    )
```
Import `record_spec_exception` at the top of sidebar.py if not already imported.
Follow the existing import pattern for cross-skill imports.

Do not change any other logic in sidebar.py. Only add the handler and the import.

**Step 4 — Verify `record_spec_exception` signature:**
Read `skills/pairmode/scripts/spec_exception.py`. Confirm the function signature and
the payload fields it expects. Adjust the handler's keyword argument names to match.

**Step 5 — Write tests:**
In `tests/pairmode/test_spec_exception.py` (extend or create):

- `test_record_spec_exception_writes_conflict`: call `record_spec_exception` directly
  with a tmp_path project dir containing a `spec.json`, assert a conflict entry is
  appended to `spec.json["conflicts"]`.
- `test_spec_exception_handler_in_sidebar`: this test cannot unit-test the sidebar
  directly (it's a long-running process), but can verify the integration contract:
  write a pipe message of type `spec_exception` to a temp file, confirm the message
  structure matches what `record_spec_exception` expects. This is a contract test, not
  a live test.
- Add a doc note in `docs/architecture.md` in the Hook architecture section:
  "`spec_exception` pipe messages are produced by the sidebar's override prompt and
  handled by the sidebar's pipe reader to write conflict records to `spec.json`. The
  pipe message payload fields: `type` (`"spec_exception"`), `path` (overridden file
  path), `non_negotiable` (the rule violated), `override_reason` (developer-supplied
  justification), `session_id` (Claude Code session identifier)."

---

### Story BOOTSTRAP-002 — Test bootstrap `--yes` non-interactive path end to end

**Rail:** BOOTSTRAP

**Acceptance criterion:** Tests in `test_bootstrap.py` cover the `--yes` flag path
introduced in Phase 18: no prompts, all files written, rails initialized, Era 001
created, no TTY required. Tests pass.

**Instructions:**

Add a test class `TestBootstrapYesFlag` in `tests/pairmode/test_bootstrap.py`:

- `test_yes_flag_creates_all_files_without_interaction`: invoke bootstrap with
  `--yes --ideology-skip --project-name testproject --stack "Python / cli"`. Assert
  all standard scaffold files exist (CLAUDE.md, CLAUDE.build.md, docs/ideology.md,
  docs/brief.md). Assert `docs/stories/CORE/` exists (default cli rail). Assert
  `docs/eras/001-initial.md` exists.

- `test_yes_flag_overwrites_existing_files`: create a project dir with a pre-existing
  `CLAUDE.md` containing `old content`. Run bootstrap with `--yes`. Assert `CLAUDE.md`
  no longer contains `old content`.

- `test_yes_flag_with_ideology_skip_no_stdin`: run bootstrap with `--yes --ideology-skip`
  in a subprocess with `stdin=subprocess.DEVNULL`. Assert exit code 0. (This is the
  hardest test to fake with mocks; a subprocess invocation is cleaner.)

- `test_yes_flag_absent_and_no_tty_uses_defaults`: confirm that when `--yes` is not
  given and stdin is not a TTY, bootstrap still completes using defaults (via
  `--ideology-skip` or non-TTY detection). This is regression coverage for the
  pre-existing non-interactive path.

---

### Story INFRA-014 — Close targeted test gaps: `phase_new` era edge case, `story_resolver` link-format, `cer.py` ID detection

**Rail:** INFRA

**Acceptance criterion:** Three specific test gaps are closed with both the test and
(where needed) the fix. Tests pass.

**Instructions:**

**Gap 1 — `phase_new.py` era update with body-only era file:**

In `tests/pairmode/test_phase_new.py`, add:
- `test_update_era_phases_table_with_no_frontmatter`: write an era file that has body
  content but no `---` frontmatter block at all. Call `_update_era_phases_table`.
  Assert it does not crash (graceful skip or adds the row to the existing Phases table
  if the table is present).

If `_update_era_phases_table` currently crashes on this input, fix it: wrap the
frontmatter parse in a None check and skip the prepend/update if frontmatter is absent.

**Gap 2 — `story_resolver.list_phase_stories` with Markdown link-formatted IDs:**

In `tests/pairmode/test_story_resolver.py`, add:
- `test_list_phase_stories_link_formatted_id`: write a phase manifest with a Stories
  table row like:
  ```
  | [BOOTSTRAP-001](docs/stories/BOOTSTRAP/BOOTSTRAP-001.md) | title | planned |
  ```
  Assert `list_phase_stories` returns `"BOOTSTRAP-001"` (link markup stripped), not
  the raw bracket-formatted string.

Update `list_phase_stories` in `story_resolver.py` to strip Markdown link syntax from
the first column: `re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cell.strip())`.

**Gap 3 — `cer.py` does not restart CER IDs on re-run with existing entries:**

In `tests/pairmode/test_cer.py` (or create it), add:
- `test_cer_id_increments_from_existing`: write a backlog.md with CER-001 through
  CER-003 already present. Run `append_finding` (or the CLI) for a new finding.
  Assert the new finding is assigned CER-004, not CER-001.
- `test_cer_id_not_restarted_after_gap`: backlog has CER-001 and CER-003 (CER-002
  resolved). New finding → CER-004 (max + 1, not len + 1).

---

⚙️ DEVELOPER ACTION — Verify sidebar spec_exception handler in a live session

After Story INFRA-013 passes review, do a quick smoke test:
1. Start a project with the companion sidebar running.
2. Attempt to edit a protected file.
3. When the override prompt appears, provide a reason.
4. Verify the conflict is written to `spec.json["conflicts"]`.

This cannot be automated by the test suite; it requires a live Claude Code session
with the sidebar active.

Tag: `cp19-test-coverage-integration`
