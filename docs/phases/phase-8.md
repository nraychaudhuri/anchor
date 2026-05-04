## Phase 8 — Sync confirmation, template coherence, and tooling bug fixes

Cold-eyes review after Phase 7 dogfooding identified four categories of defect: (1) sync.py
applies all changes without confirmation, making it destructive on projects with hand-authored
content; (2) templates still reference the legacy `docs/phase-prompts.md` throughout, leaving
new projects with broken orchestrator instructions; (3) `cer.py` and `phase_new.py` have
correctness bugs found only through manual use; (4) SKILL.md documentation is inaccurate in
several places, including references to flags that don't exist.

Prerequisites: Phase 7 developer action gate complete. All Phase 7 stories committed.

---

### Story 8.0 — sync.py: confirmation gate before writing

**Acceptance criterion:** `sync.py` presents a per-change confirmation prompt before writing any
file. A `--yes` flag bypasses prompts (for scripted use). Destructive overwrites of INCONSISTENT
sections are shown as diffs, not just section names. Tests pass.

**Instructions:**

`sync.py` currently writes all MISSING and INCONSISTENT changes without any user interaction.
This caused hand-authored content to be silently overwritten during Phase 7 dogfooding.

Add a `--yes / -y` flag (default: False) to the `sync` click command.

For **MISSING** files (new files to create): prompt with:
```
  Create docs/brief.md (file missing)? [y/N]
```
Skip if `--yes`.

For **INCONSISTENT** sections (overwrite canonical body): show a minimal inline diff before
prompting. Use `difflib.unified_diff` between the current section body and the canonical body,
limited to 10 lines of context. Prompt with:
```
  Update section '## review checklist' in CLAUDE.md? [y/N]
  (--- current  +++ canonical)
  [diff lines]
```
Skip if `--yes`.

For **MISSING sections** (append to existing file): prompt with:
```
  Append section '### 4. CER backlog review' to CLAUDE.build.md? [y/N]
```
Skip if `--yes`.

Changes declined by the user are skipped (not written) but still appear in the sync summary
under a new `skipped` list.

Update `SyncResult` dataclass to add `skipped: list[SyncItem]`.

Update `format_sync_output()` to print skipped items:
```
Skipped (user declined):
  ✗ CLAUDE.md: section '## review checklist' (user declined)
```

Add tests to `tests/pairmode/test_sync.py`:
- With `--yes`: all changes applied without prompts (existing behaviour).
- Without `--yes`: confirmation prompt is shown for each MISSING file; accepting applies it.
- Without `--yes`: confirmation prompt shown for INCONSISTENT section with diff; declining skips it.
- Declined items appear in `result.skipped`, not `result.applied`.
- `format_sync_output()` includes a skipped section when items were declined.

---

### Story 8.1 — Template migration: remove legacy phase-prompts.md references

**Acceptance criterion:** No template file references `docs/phase-prompts.md` as a file to read
at session start. All orchestrator and agent templates use `docs/phases/phase-N.md` (with a
legacy fallback note for projects that have not migrated). Tests pass.

**Instructions:**

The following templates currently reference `docs/phase-prompts.md` as the authoritative phase
document. New projects bootstrapped after Phase 7 do not have this file; the orchestrator
instructions are broken for them.

Files to update:

1. `skills/pairmode/templates/CLAUDE.build.md.j2` — the `## Before the first build loop`
   section currently reads:
   ```
   3. Read the current phase file from `docs/phases/phase-N.md` (or `docs/phase-prompts.md` for
      legacy projects that have not migrated to per-phase files).
   ```
   This is already correct. Check the remainder of the file for any other `phase-prompts.md`
   references (e.g. in the checkpoint sequence, intent-review step, loop-breaker section) and
   update them to: "`docs/phases/phase-N.md` (or `docs/phase-prompts.md` for legacy projects)".

2. `skills/pairmode/templates/agents/intent-reviewer.md.j2` — multiple references to
   `docs/phase-prompts.md` as the file to read and to produce edits to. Update all to:
   "`docs/phases/phase-N.md` (or `docs/phase-prompts.md` for legacy projects)".

3. `skills/pairmode/templates/docs/brief.md.j2` — the portability footer lists
   `docs/phase-prompts.md`. Update to:
   `Current phase file from docs/phases/ (or docs/phase-prompts.md for legacy projects)`.

Do NOT modify any anchor project files directly (CLAUDE.build.md, intent-reviewer.md, etc.) —
only the `.j2` templates. Anchor's hand-authored files will be updated separately via sync.

Add tests to `tests/pairmode/test_templates.py`:
- Render `CLAUDE.build.md.j2`; assert `docs/phase-prompts.md` does not appear as a standalone
  read instruction (i.e., it only appears in parenthetical legacy notes if at all).
- Render `agents/intent-reviewer.md.j2`; assert any `phase-prompts.md` reference is
  parenthetical / fallback only, not a primary instruction.

---

### Story 8.2 — cer.py bug fixes

**Acceptance criterion:** `--reviewer` is the correct flag (matching the CLI); SKILL.md uses
`--reviewer` consistently. Interactive finding input correctly accumulates multiline text. IDs
use the correct sequential numbering. `project_name` is read from `pairmode_context.json` when
available. Tests pass.

**Instructions:**

Fix four bugs identified in the cold-eyes review:

**Bug 1 — `--source` vs `--reviewer` in SKILL.md (H6):**
`SKILL.md` line documents `--source TEXT` but the CLI defines `--reviewer`. Update `SKILL.md`
to use `--reviewer` throughout. No code change needed.

**Bug 2 — Interactive multiline input exits immediately (H7):**
`_prompt_finding()` uses `click.prompt(default="")` in a loop. `click.prompt` with
`default=""` returns immediately on empty input, so the first Enter exits before any text is
entered. Replace with `input()` in a loop:
```python
def _prompt_finding() -> str:
    print("Enter finding (blank line to finish):")
    lines = []
    while True:
        line = input()
        if line == "" and lines:
            break
        if line:
            lines.append(line)
    return "\n".join(lines)
```

**Bug 3 — `project_name` parsed from file header instead of context.json (M6):**
`cer.py` currently guesses project_name by splitting the backlog.md `# Heading — ...` line on
em-dash. Replace with: read `pairmode_context.json` if present, use `project_name` key; fall
back to heading parse; fall back to `"Project"`.

**Bug 4 — Quadrant value inconsistency in SKILL.md (L3):**
`SKILL.md` mixes long-form (`do_now`) and short-form (`now`) quadrant values in the same
section. Standardise on short-form (`now`, `later`, `much_later`, `never`) throughout, matching
the CLI.

Add tests to `tests/pairmode/test_cer.py`:
- Interactive multiline finding: simulate input with multiple lines; assert all lines captured.
- `project_name` from `pairmode_context.json`: create context file, run cer, assert header uses
  correct name.
- `project_name` fallback: no context file; assert heading-parse fallback works.

---

### Story 8.3 — phase_new.py: project_name from context and --dry-run

**Acceptance criterion:** `phase_new.py` reads `project_name` from `pairmode_context.json` when
present. A `--dry-run` flag prints what would be written without writing. Tests pass.

**Instructions:**

**Fix 1 — `project_name` hardcoded (H2):**
`phase_new.py` passes `project_name="project"` to the template. Replace with:
```python
def _load_project_name(project_dir: Path) -> str:
    ctx_path = project_dir / ".companion" / "pairmode_context.json"
    try:
        return json.loads(ctx_path.read_text()).get("project_name", "project")
    except Exception:
        return "project"
```
Pass the result as `project_name` to all template renders.

**Fix 2 — Add `--dry-run` flag:**
Add `--dry-run` (default: False) to the `phase_new` click command. When True: print each file
that would be written with its content, but do not write to disk. Output format:
```
[DRY RUN] Would write: docs/phases/phase-3.md
--- content preview (first 20 lines) ---
...
[DRY RUN] Would update: docs/phases/index.md
```

Add tests to `tests/pairmode/test_phase_new.py`:
- `project_name` from context.json renders in `phase-N.md` heading.
- `project_name` fallback when context.json absent: renders `"project"`.
- `--dry-run`: no files written; output contains "Would write".

---

### Story 8.4 — Bootstrap fixes: phase-1 prompts and non-TTY what/why

**Acceptance criterion:** Bootstrap prompts for `phase_title` and `goal` when creating
`docs/phases/phase-1.md`. `what` and `why` are not silently skipped in non-TTY — they are
passed through as empty strings with a visible warning. Bootstrap shows a global summary of
files to write before writing any of them. Tests pass.

**Instructions:**

**Fix 1 — phase-1.md has placeholder title and empty goal (H3):**
Add `--phase-title` (default: None) and `--phase-goal` (default: None) options to the
`bootstrap` click command. When running in TTY mode and these are absent, prompt for them
(blank input is acceptable). When non-TTY, use empty strings. Pass to the phase-1.md render.

**Fix 2 — Non-TTY silently drops what/why (H4):**
Currently: if `sys.stdin.isatty()` is False, `what` and `why` are silently set to `""` with no
user indication. Add a warning line:
```
  warning: non-interactive mode — docs/brief.md what/why left blank.
           Pass --what and --why flags to populate, or edit docs/brief.md after bootstrap.
```
Print this to stderr when `what` or `why` ends up blank after the TTY check.

**Fix 3 — SKILL.md global confirmation claim (C1):**
Update `SKILL.md` bootstrap section to accurately describe the per-file confirmation behaviour:
"Bootstrap prompts before overwriting each file that already exists. On a fresh project, all
scaffold files are written immediately. Use `--dry-run` to preview the file list first."
Note: `--dry-run` does not yet exist for bootstrap; if it is not added in this story, remove
the reference. Adding a `--dry-run` flag to bootstrap is optional in this story.

Add tests to `tests/pairmode/test_bootstrap.py`:
- Bootstrap with `--phase-title "My Phase"`: `docs/phases/phase-1.md` contains "My Phase".
- Bootstrap without `--phase-title` in non-TTY: `phase-1.md` renders with empty title (no crash).
- Bootstrap in non-TTY with no `--what`: warning printed to stderr.
- Bootstrap in non-TTY with `--what "something"`: no warning; brief.md has "something".

---

### Story 8.5 — SKILL.md accuracy pass

**Acceptance criterion:** Every flag documented in SKILL.md exists in the corresponding CLI.
The bootstrap Outputs section lists the actual files written. Commands section lists all
reachable commands. Tests pass.

**Instructions:**

Update `skills/pairmode/SKILL.md`:

1. **Bootstrap Outputs (M1):** Replace the current list with the actual files bootstrap now
   writes: `CLAUDE.md`, `CLAUDE.build.md`, `docs/brief.md`, `docs/architecture.md`,
   `docs/checkpoints.md`, `docs/phases/index.md`, `docs/phases/phase-1.md`,
   `docs/cer/backlog.md`, `.claude/settings.json`, `.companion/state.json`. Remove
   `docs/phase-prompts.md`. Agent files listed with the caveat: "skipped if already exist
   unless `--force-agents` is passed."

2. **phase-new command (M7):** Remove `--dry-run` from the inputs/flags list if Story 8.3 has
   not implemented it yet. Add it back (with correct description) once 8.3 is merged.

3. **cer command (H6, L3):** Update `--source` → `--reviewer` throughout. Standardise quadrant
   values to short-form (`now`, `later`, `much_later`, `never`) everywhere in the section.

4. **Dispatcher note (C3):** Add a note at the top of the commands section explaining that
   `phase-new` and `cer` are invoked via CLI directly (not via the pairmode skill dispatcher),
   and include the correct `PYTHONPATH=... uv run python` invocation for each.

Add a test to `tests/pairmode/test_skill_md.py` (new file):
- Parse SKILL.md and for each `--flag` mentioned in a code block, verify the corresponding
  script (`scripts/phase_new.py`, `scripts/cer.py`, `scripts/bootstrap.py`) defines that flag.
  This is a documentation accuracy test, not a functional test.

---

### Story 8.6 — Audit section comparison for Phase 7 files

**Acceptance criterion:** `audit.py` performs section-level comparison (not just file existence)
for `docs/brief.md`, `docs/phases/index.md`, and `docs/cer/backlog.md`. The three templates
have stable headings that can be audited. Tests pass.

**Instructions:**

Currently `docs/brief.md`, `docs/phases/index.md`, and `docs/cer/backlog.md` are only checked
for file existence (`EXISTENCE_CHECK_FILES`). If a file is present but contains raw template
markers (e.g. `_(not yet specified)_`) or is missing a canonical section, audit passes silently.

Move these three files from `EXISTENCE_CHECK_FILES` to the standard `SCAFFOLD_FILES` audit list
(the list that drives section-level comparison). This means:
- `docs/brief.md` → audit compares sections against `docs/brief.md.j2` rendered with context.
- `docs/phases/index.md` → audit compares sections against `docs/phases/index.md.j2`.
- `docs/cer/backlog.md` → audit compares sections against `docs/cer/backlog.md.j2`.

For all three, INCONSISTENT findings for sections that contain placeholder text (e.g. a brief.md
`## What this project produces` section whose only content is `_(not yet specified)_`) should be
labelled `STALE PLACEHOLDER` rather than INCONSISTENT, to distinguish "needs filling in" from
"has drifted from template."

Add tests to `tests/pairmode/test_audit.py`:
- `docs/brief.md` present but with placeholder `what`/`why` → reported as STALE PLACEHOLDER.
- `docs/brief.md` present and fully populated → reported clean.
- `docs/phases/index.md` present and matches rendered template → clean.

---

### Story 8.7 — Per-phase file policy: migrate Phase 8 and document in architecture.md

**Acceptance criterion:** Phase 8 spec content lives in `docs/phases/phase-8.md`, not in
`docs/phase-prompts.md`. `docs/architecture.md` documents the per-phase file policy and updates
the template tree. The monolithic `docs/phase-prompts.md` receives a redirect stub for Phase 8.
Tests pass.

**Instructions:**

**Part A — Migrate Phase 8 to its own file:**

Create `docs/phases/phase-8.md`. Move the Phase 8 content (everything from the
`## Phase 8 —` heading through the end of the last story) from `docs/phase-prompts.md` into
`docs/phases/phase-8.md`.

In `docs/phase-prompts.md`, replace the moved content with a single redirect line:
```
## Phase 8 — See docs/phases/phase-8.md
```

Update `docs/phases/index.md` to add Phase 8 as a row in the phases table
(status: in_progress, title matching the Phase 8 heading).

**Part B — Document the per-phase policy in architecture.md:**

Add a `## Phase documentation policy` section to `docs/architecture.md`:

```
## Phase documentation policy

Each phase gets its own file: `docs/phases/phase-N.md`.

- New phases are always created as `docs/phases/phase-N.md` using `phase_new.py`.
- The monolithic `docs/phase-prompts.md` is the legacy format for Phases 1–7.
  It is not extended with new phase content.
- The `docs/phases/index.md` table is the canonical list of all phases and their status.
- Phase files are the source of truth for the builder/reviewer loop. The orchestrator reads
  the current phase file directly; it does not parse phase-prompts.md for new projects.

When reviewing or building, read only the current phase file — not the entire monolithic doc.
This keeps token usage proportional to phase scope, not project history.
```

**Part C — Update architecture.md template tree:**

The template tree in `architecture.md` currently lists `docs/phase-prompts.md.j2`. Update it
to reflect the actual Phase 7 template output:

```
docs/
  brief.md.j2
  architecture.md.j2
  checkpoints.md.j2
  phases/
    index.md.j2
    phase.md.j2       ← per-phase scaffold; generated by phase_new.py
  cer/
    backlog.md.j2
```

Remove `phase-prompts.md.j2` from the tree (it still exists as a template for legacy audit
comparison but is no longer a primary bootstrap output).

Add tests to `tests/pairmode/test_architecture_policy.py` (new file):
- `docs/phases/phase-8.md` exists in the repo.
- `docs/architecture.md` contains the string "Per-phase file policy" or "Phase documentation policy".
- `docs/phases/index.md` contains a row referencing phase-8.
- `docs/phase-prompts.md` Phase 8 section contains a redirect, not the full spec.

Note: H2 (phase_new.py project_name) is covered by Story 8.3. M6 (cer.py project_name) is
covered by Story 8.2. This story covers the structural migration and policy documentation only.


---

### Story 8.8 — Documentation currency: README update step in checkpoint sequence

**Acceptance criterion:** `CLAUDE.build.md.j2` includes a README/docs review step in the
checkpoint sequence. The step explicitly lists what to check and blocks tagging if README is
stale. The reviewer template flags a stale README as a MEDIUM finding. Tests pass.

**Instructions:**

**Part A — Add checkpoint step to `CLAUDE.build.md.j2`:**

Insert a new step **4** (before the current step 4 "CER backlog review"; renumber CER to 5,
tag to 6, report to 7):

```
### 4. Documentation review

Before tagging, verify that documentation reflects what was shipped this phase.

Check each of the following:
- `README.md` — does it reflect all user-facing changes from this phase?
  Look for: new commands/flags, changed behaviour, new workflow steps, updated status.
- `docs/brief.md` — still accurate? Update if project goals or constraints changed.
- Any doc file explicitly referenced in this phase's spec.

If README is stale: update it inline (do not spawn a subagent — this is a write task,
not a review task). Mark `Doc updates: [list of changes]` in the step 7 report.

If no user-facing changes shipped this phase: mark `Doc updates: none` and proceed.
```

Update the step 7 report block to show the renumbered steps and confirm
`Doc updates:` is already present (it was added in Story 7.6 — verify it is still there).

**Part B — Add to reviewer template (`agents/reviewer.md.j2`):**

Add a new universal checklist item after BUILD GATE:

```
4. DOCUMENTATION CURRENCY
   Does README.md reflect user-facing changes introduced in this story?
   New commands, flags, workflows, or changed behaviour not reflected in README is MEDIUM.
   Internal refactors with no user-facing change: exempt.
```

**Part C — Update anchor's own `CLAUDE.build.md`:**

Apply the same checkpoint step insertion to `/mnt/work/anchor/CLAUDE.build.md` directly
(since anchor's orchestrator file is hand-authored and not synced from template automatically).
Renumber: documentation review = 4, CER backlog = 5, tag = 6, report = 7.

Add tests to `tests/pairmode/test_templates.py`:
- Render `CLAUDE.build.md.j2`; assert "Documentation review" step heading is present.
- Render `CLAUDE.build.md.j2`; assert "README" appears in the checkpoint sequence section.
- Render `agents/reviewer.md.j2`; assert "DOCUMENTATION CURRENCY" is in the checklist.
- Regression: assert CER backlog review, build gate, security audit, intent review, and tag
  steps are all still present after renumbering.


---

⚙️  DEVELOPER ACTION — Verify pipe isolation and restart sidebars

After all Phase 8 stories pass review:

1. Restart all running sidebars by stopping them and re-running `start_sidebar.sh` from each
   project's root directory. Confirm each sidebar window shows a project-specific pipe path
   in its startup output (or check `/tmp/companion-*.pipe` — one per running project).

2. Open two simultaneous Claude sessions on different projects and verify that file-change
   events appear only in the correct project's sidebar window.

3. Test `s/r/o` key selection in the sidebar: trigger an override event (edit a protected file),
   confirm the sidebar presents the action panel, and verify that pressing `s`, `r`, or `o`
   registers correctly. If keys are not registering, the likely cause is that the sidebar
   terminal does not have keyboard focus — the sidebar must be in an interactive terminal
   (not a background process or tmux pane without focus).

Confirm these three checks before saying "Continue building Phase 9".
