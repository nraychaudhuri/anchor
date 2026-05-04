# anchor — Phase 13: CER cleanup and end-to-end reconstruction verification

← [Phase 12: Reconstruction seeding and comparison scaffolding](phase-12.md)

## Goal

Phase 12 shipped `ideology_parser.py` and `--from-reconstruction`. Two loose ends remain:

1. CER-001: the `parse_ideology()` compat wrapper in `reconstruct.py` routes through a
   `NamedTemporaryFile`, which leaks ideology.md content to `/tmp` on abnormal exit. Adding
   `parse_ideology_text(text: str)` to `ideology_parser.py` eliminates the temp file entirely.

2. No integration test covers the full `--from-reconstruction` path against real content.
   The unit tests mock or stub the parser; we want one test that runs `bootstrap` against
   anchor's own `docs/reconstruction.md` and asserts that the resulting `docs/ideology.md`
   contains recognisable ideology content — proving the round-trip works end-to-end.

Two stories:

1. Fix CER-001: add `parse_ideology_text()` to `ideology_parser.py` (13.0)
2. End-to-end integration test for `--from-reconstruction` (13.1)

Prerequisites: Phase 12 complete and tagged cp12-reconstruction-seeding.

---

### Story 13.0 — Fix CER-001: `parse_ideology_text()` helper in ideology_parser.py

**Acceptance criterion:** `ideology_parser.py` exposes `parse_ideology_text(text: str) -> dict`.
The `parse_ideology()` compat wrapper in `reconstruct.py` uses it instead of the
`NamedTemporaryFile` round-trip. No temp file is created. Tests pass.

**Instructions:**

Add to `skills/pairmode/scripts/ideology_parser.py`:

```python
def parse_ideology_text(text: str) -> dict:
    """Parse ideology.md text (already read) into a context dict.

    Equivalent to parse_ideology_file but accepts the content directly,
    avoiding any disk I/O.
    """
```

Refactor so both `parse_ideology_file` and `parse_ideology_text` share the same
implementation. The simplest approach: have `parse_ideology_file` read the file and call
`parse_ideology_text`. Alternatively, extract a private `_parse_ideology_impl(text)` that
both call.

Update `reconstruct.py` — replace the `parse_ideology()` compat wrapper body:

```python
# Before:
def parse_ideology(text: str) -> dict:
    import tempfile, os
    with tempfile.NamedTemporaryFile(...) as tmp:
        ...
    try:
        return _ideology_parser.parse_ideology_file(Path(tmp_path))
    finally:
        os.unlink(tmp_path)

# After:
def parse_ideology(text: str) -> dict:
    """Parse ideology.md text; kept for backward compatibility."""
    return _ideology_parser.parse_ideology_text(text)
```

Remove `import tempfile` and `import os` from the wrapper (remove from the module top-level
too if they are no longer used elsewhere in `reconstruct.py`).

**Tests — `tests/pairmode/test_ideology_parser.py`:**
- `parse_ideology_text()` with ideology.md format text: returns convictions list.
- `parse_ideology_text()` and `parse_ideology_file()` return identical output for the same content.
- Regression: `reconstruct.parse_ideology()` still returns correct dict (existing test passes unchanged).

---

### Story 13.1 — End-to-end integration test for `--from-reconstruction`

**Acceptance criterion:** A test runs `bootstrap --from-reconstruction` against anchor's own
`docs/reconstruction.md` and asserts the round-trip produces a populated `docs/ideology.md`
containing real conviction content. Tests pass.

**Instructions:**

Add a test to `tests/pairmode/test_bootstrap.py` (or a new
`tests/pairmode/test_e2e_reconstruction.py` if the test file would be large):

```python
# integration — reads anchor's own docs/reconstruction.md
def test_from_reconstruction_e2e_against_anchor_brief():
    ...
```

The test must:
1. Locate anchor's own `docs/reconstruction.md`:
   `Path(__file__).parents[2] / "docs" / "reconstruction.md"`.
   Skip with `pytest.skip` if the file does not exist (stripped clone).
2. Read the file; extract one conviction from the `## Non-negotiable ideology / ### Convictions`
   section so we know what to assert against.
3. Create a temp project directory.
4. Run `bootstrap` via `CliRunner`:
   `["--project-dir", str(tmpdir), "--from-reconstruction", str(brief_path), "--yes"]`
5. Assert exit code 0.
6. Read `<tmpdir>/docs/ideology.md`.
7. Assert the conviction text (or a recognisable substring) is present in the output.
8. Assert the standard ideology.md sections exist: `## Core convictions`,
   `## Accepted constraints`, `## Reconstruction guidance`.

Use `CliRunner(mix_stderr=False)` consistent with the existing bootstrap tests.

**Tests:** Full suite passes. The e2e test passes against the live `docs/reconstruction.md`.

---

⚙️ DEVELOPER ACTION — Verify audit clean after Story 13.1

After 13.1 passes review:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/audit.py --project-dir .
```

If STALE PLACEHOLDER is reported for `docs/reconstruction.md`, regenerate it:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/reconstruct.py --project-dir . --force
git add docs/reconstruction.md && git commit -m "docs: regenerate reconstruction.md for cp13 gate"
```

Tag: `cp13-cer-cleanup-e2e`
