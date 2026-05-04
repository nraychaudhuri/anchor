# anchor — Cold-Eyes Review (CER) Backlog

*Last updated: 2026-04-30*

This file is the structured triage log for findings from external cold-eyes reviews.
Each finding is assigned to one quadrant. Findings are not deleted — resolved findings
remain in place with a resolution note.

---

## Do Now

Urgent and important. Blocks correctness, security, or the next phase.

| ID | Finding | Source | Date | Phase |
|----|---------|--------|------|-------|


| — | *(none)* | — | — | — |


---

## Do Later

Important, not urgent. Quality improvements, architectural refinements.

| ID | Finding | Source | Date | Phase |
|----|---------|--------|------|-------|
| CER-001 | reconstruct.py `parse_ideology()` compat wrapper uses NamedTemporaryFile round-trip; on SIGKILL leaves ideology.md copy in /tmp. Fix: add `parse_ideology_text(text: str)` to ideology_parser.py to eliminate temp file. reconstruct.py:33-50 | Security audit cp12 | 2026-04-24 | 12 | **RESOLVED** Phase 13 |
| CER-002 | bootstrap.py has no `--yes`/`--no-input` flag; non-interactive callers must use `input="y\n" * N` workaround. Limits CI/scripted use. Add `--yes` flag that auto-confirms all prompts. | Intent review cp13 | 2026-04-25 | 13 | **RESOLVED** Phase 18 BOOTSTRAP-001 |
| CER-003 | cer.py and phase_new.py call Path(project_dir).resolve() but do not apply the len(parts) < 3 suspicious-path depth check that all other pairmode scripts apply. Inconsistent guard discipline. | Security audit cp14 | 2026-04-25 | 14 | **RESOLVED** Phase 17 INFRA-009 |
| CER-004 | lesson_review.py uses str.startswith() for path containment instead of Path.relative_to(); vulnerable to prefix collision on unusual paths. lesson_review.py:149 | Security audit cp14 | 2026-04-25 | 14 |
| CER-005 | phase_new.py missing len(parts) < 3 depth guard; resolve() is called but shallow-path check absent. All other pairmode entry points apply this guard consistently (bootstrap, audit, sync, score, reconstruct, story_new, era_new). phase_new.py:286 | Security audit cp15 | 2026-04-27 | 15 | **RESOLVED** Phase 17 INFRA-009 |
| CER-006 | validate_story_file rejects empty primary_files list, but story_new.py writes primary_files: [] by default. Every new story file fails its own validator until primary_files is filled in. Either allow empty list for draft stories, or omit the field entirely when empty. schema_validator.py, story_new.py | Intent review cp15 | 2026-04-27 | 15 | **RESOLVED** Phase 17 INFRA-008 |
| CER-007 | era_new.py writes unquoted id field (id: 001 — YAML integer) while bootstrap.py writes quoted id (id: "001" — YAML string). Current regex-based parsers tolerate both, but a proper YAML parser (e.g., python-frontmatter, PyYAML) would return integer 1 from era_new output. Fix era_new.py to write id: "{era_id}" (quoted string). era_new.py | Intent review cp15 | 2026-04-27 | 15 | **RESOLVED** Phase 17 INFRA-008 |
| CER-008 | permission_scope.py: if settings.local.json contains valid non-object JSON (e.g., a bare array), _read_json returns it as-is and the subsequent .setdefault() call raises AttributeError. Add a guard: if the parsed value is not a dict, treat it as {}. permission_scope.py:75 | Security audit cp16 | 2026-04-28 | 16 | **RESOLVED** Phase 17 INFRA-009 |
| CER-009 | hooks/stop.py, post_tool_use.py, session_end.py: PIPE_PATH defaults to hardcoded "/tmp/companion.pipe" and is then conditionally overridden by reading pipe_path from .companion/state.json (relative path). A crafted state.json could redirect pipe writes to an arbitrary path. No secrets in payloads; write silently drops on ENXIO if no FIFO reader. LOW severity. exit_plan_mode.py correctly uses tempfile.gettempdir(). | Security audit cp17 | 2026-04-30 | 17 |
| CER-010 | story_new.py --rail input is .upper()'d but not validated against a regex before being used in path construction. A caller passing --rail "../../../etc" constructs a path that escapes project_dir. No containment check present. MEDIUM severity. story_new.py:183-185 | Security audit cp18 | 2026-04-30 | 18 |
| CER-011 | era_new.py _slugify() neutralizes "/" and "." in --name before path construction, providing effective (but informal) traversal prevention. No formal resolve().relative_to() containment check present. LOW severity — _slugify() is correct but not a formal guard. era_new.py:25-31, 114-116 | Security audit cp18 | 2026-04-30 | 18 |
| CER-012 | pairmode_status.py: ANCHOR_ROOT computed as `Path(__file__).resolve().parent.parent.parent` resolves to `<repo>/skills/`, not the anchor repo root. The constructed `start_sidebar.sh` path becomes `<repo>/skills/skills/companion/scripts/start_sidebar.sh` — a file that does not exist. Must be `parent.parent.parent.parent` (four levels up). HIGH severity — surfaced to user as broken instructions. pairmode_status.py:33 | Story review cp20 INFRA-019 | 2026-05-01 | 20 | **RESOLVED** Phase 20 INFRA-020 |


---

## Do Much Later

Not urgent, marginal value. Style, cosmetics, speculative improvements.

| ID | Finding | Source | Date | Phase |
|----|---------|--------|------|-------|


| — | *(none)* | — | — | — |


---

## Do Never

Rejected findings. Record the rejection reason so it is not re-raised.

| ID | Finding | Source | Date | Phase | Resolution |
|----|---------|--------|------|-------|------------|


| — | *(none)* | — | — | — | — |

