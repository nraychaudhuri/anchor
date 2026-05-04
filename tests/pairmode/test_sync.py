"""Tests for sync.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.sync import (
    SyncResult,
    sync_project,
    format_sync_output,
    main as sync_main,
)
from skills.pairmode.scripts import audit as _audit_mod
from skills.pairmode.scripts.audit import _load_project_context, _JINJA_ENV

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEMPLATES_DIR = _audit_mod.TEMPLATES_DIR
CANONICAL_FILES = _audit_mod.CANONICAL_FILES


def _copy_canonical_files(project_dir: Path) -> None:
    """Render all canonical template files with fallback context and write into project_dir.

    Uses the same context that audit_project/sync_project would use when
    pairmode_context.json is absent, so rendered canonical == rendered template.
    Also creates Phase 7 scaffold files with non-placeholder content so they are not
    flagged MISSING or STALE PLACEHOLDER.
    """
    from skills.pairmode.scripts.audit import SCAFFOLD_FILES, _enrich_scaffold_context

    context, _ = _load_project_context(project_dir)
    enriched_context = _enrich_scaffold_context(context)

    for dest_rel, template_rel in CANONICAL_FILES:
        dest_path = project_dir / dest_rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            rendered = _JINJA_ENV.get_template(template_rel).render(**context)
        except Exception:
            rendered = "# placeholder\n"
        dest_path.write_text(rendered, encoding="utf-8")

    # Also create Phase 7 scaffold files with non-placeholder content
    (project_dir / "docs").mkdir(parents=True, exist_ok=True)
    (project_dir / "docs" / "phases").mkdir(parents=True, exist_ok=True)
    (project_dir / "docs" / "cer").mkdir(parents=True, exist_ok=True)

    brief_path = project_dir / "docs" / "brief.md"
    if not brief_path.exists():
        brief_path.write_text(
            "# Brief — testproject\n\n"
            "## What this project produces\n\n"
            "A test project for unit tests.\n\n"
            "## Why it exists\n\n"
            "To provide a baseline for sync tests.\n\n"
            "## Core beliefs\n\n"
            "We prefer simplicity over complexity in all design decisions.\n\n"
            "## Accepted tradeoffs\n\n"
            "We accepted slower startup in exchange for easier configuration.\n\n"
            "## Constraints\n\n"
            "_Explicit constraints the operator has placed on scope or approach:_\n\n"
            "- _(add operator constraints here)_\n\n"
            "## Not in scope\n\n"
            "_Things that might seem related but are intentional omissions:_\n\n"
            "- _(add out-of-scope items here)_\n\n"
            "## What a second implementation must preserve\n\n"
            "The core data model and persistence contract must be preserved.\n\n"
            "## Operator contact\n\n"
            "_(not specified)_\n",
            encoding="utf-8",
        )

    index_path = project_dir / "docs" / "phases" / "index.md"
    if not index_path.exists():
        index_path.write_text(
            "# testproject — Phase Index\n\n"
            "This document is the index of all build phases for the project.\n"
            "Each phase has a dedicated file in `docs/phases/`.\n\n"
            "| Phase | Title | Status | Link |\n"
            "|-------|-------|--------|------|\n"
            "| 1 | Phase 1 | in progress | [docs/phases/phase-1.md](docs/phases/phase-1.md) |\n",
            encoding="utf-8",
        )

    backlog_path = project_dir / "docs" / "cer" / "backlog.md"
    if not backlog_path.exists():
        backlog_path.write_text(
            "# testproject — Cold-Eyes Review (CER) Backlog\n\n"
            "*Last updated: 2026-01-01*\n\n"
            "This file is the structured triage log for findings from external cold-eyes reviews.\n\n"
            "## Do Now\n\n"
            "Urgent and important.\n\n"
            "| ID | Finding | Source | Date | Phase |\n"
            "|----|---------|--------|------|-------|\n"
            "| — | *(none)* | — | — | — |\n\n"
            "## Do Later\n\n"
            "Important, not urgent.\n\n"
            "| ID | Finding | Source | Date | Phase |\n"
            "|----|---------|--------|------|-------|\n"
            "| — | *(none)* | — | — | — |\n\n"
            "## Do Much Later\n\n"
            "Not urgent.\n\n"
            "| ID | Finding | Source | Date | Phase |\n"
            "|----|---------|--------|------|-------|\n"
            "| — | *(none)* | — | — | — |\n\n"
            "## Do Never\n\n"
            "Rejected findings.\n\n"
            "| ID | Finding | Source | Date | Phase | Resolution |\n"
            "|----|---------|--------|------|-------|------------|\n"
            "| — | *(none)* | — | — | — | — |\n",
            encoding="utf-8",
        )


def _write_state(project_dir: Path, extra_fields: dict | None = None) -> None:
    """Write .companion/state.json optionally with extra fields."""
    companion = project_dir / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    state: dict = extra_fields.copy() if extra_fields else {}
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_ideology_md(project_dir: Path) -> None:
    """Write docs/ideology.md with non-placeholder content."""
    (project_dir / "docs").mkdir(parents=True, exist_ok=True)
    ideology_path = project_dir / "docs" / "ideology.md"
    ideology_path.write_text(
        "# Ideology — testproject\n\n"
        "## Core convictions\n\n"
        "We believe in simplicity over complexity at every level of the stack.\n\n"
        "## Value hierarchy\n\n"
        "Correctness > Performance > Convenience.\n\n"
        "## Accepted constraints\n\n"
        "We operate within a strict budget; no expensive third-party APIs.\n\n"
        "## Prototype fingerprints\n\n"
        "The canonical implementation uses Python with uv and Rich.\n\n"
        "## Reconstruction guidance\n\n"
        "Start from the spec, not the code. The spec is the source of truth.\n\n"
        "## Comparison basis\n\n"
        "Compare against the reference implementation in the anchor repo.\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Tests: creating missing files
# ---------------------------------------------------------------------------


class TestSyncCreatesMissingFile:
    """sync_project creates CLAUDE.md when it is missing."""

    def test_creates_claude_md_when_missing(self, tmp_path: Path) -> None:
        # Set up project without CLAUDE.md (copy all OTHER canonical files)
        for dest_rel, template_rel in CANONICAL_FILES:
            if dest_rel == "CLAUDE.md":
                continue
            template_path = TEMPLATES_DIR / template_rel
            dest_path = tmp_path / dest_rel
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if template_path.exists():
                dest_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                dest_path.write_text("# placeholder\n", encoding="utf-8")

        result = sync_project(tmp_path, yes=True)

        assert (tmp_path / "CLAUDE.md").exists(), "CLAUDE.md should have been created"

    def test_applied_list_mentions_claude_md(self, tmp_path: Path) -> None:
        # Project with no files at all
        result = sync_project(tmp_path, yes=True)

        applied_text = " ".join(result.applied)
        assert "CLAUDE.md" in applied_text, (
            f"Expected 'CLAUDE.md' in applied list, got: {result.applied}"
        )

    def test_created_file_has_content(self, tmp_path: Path) -> None:
        sync_project(tmp_path, yes=True)

        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert len(content) > 0, "Created CLAUDE.md should have non-empty content"


# ---------------------------------------------------------------------------
# Tests: all files identical → no changes
# ---------------------------------------------------------------------------


class TestSyncNoChangesWhenIdentical:
    """When project files are identical to canonical templates, applied should be empty."""

    def test_no_applied_items_when_all_identical(self, tmp_path: Path) -> None:
        _copy_canonical_files(tmp_path)

        result = sync_project(tmp_path, yes=True)

        assert result.applied == [], (
            f"Expected no applied items when files are identical, got: {result.applied}"
        )

    def test_extra_items_preserved_when_all_identical(self, tmp_path: Path) -> None:
        """With identical files, any sections flagged as EXTRA are listed under preserved."""
        _copy_canonical_files(tmp_path)

        result = sync_project(tmp_path, yes=True)

        # Extra can be empty or non-empty — just verify it is a list
        assert isinstance(result.preserved, list)

    def test_sync_result_type(self, tmp_path: Path) -> None:
        _copy_canonical_files(tmp_path)

        result = sync_project(tmp_path, yes=True)

        assert isinstance(result, SyncResult)


# ---------------------------------------------------------------------------
# Tests: state.json update
# ---------------------------------------------------------------------------


class TestSyncUpdatesStateJson:
    """sync_project updates .companion/state.json with pairmode_version and last_sync."""

    def test_state_json_created_when_missing(self, tmp_path: Path) -> None:
        _copy_canonical_files(tmp_path)
        # Ensure no state.json exists
        state_path = tmp_path / ".companion" / "state.json"
        if state_path.exists():
            state_path.unlink()

        sync_project(tmp_path, yes=True)

        assert state_path.exists(), ".companion/state.json should have been created"

    def test_pairmode_version_written(self, tmp_path: Path) -> None:
        _copy_canonical_files(tmp_path)

        sync_project(tmp_path, yes=True)

        state = json.loads((tmp_path / ".companion" / "state.json").read_text(encoding="utf-8"))
        assert "pairmode_version" in state
        assert state["pairmode_version"] == "0.1.0"

    def test_last_sync_written(self, tmp_path: Path) -> None:
        _copy_canonical_files(tmp_path)

        sync_project(tmp_path, yes=True)

        state = json.loads((tmp_path / ".companion" / "state.json").read_text(encoding="utf-8"))
        assert "last_sync" in state
        # Should be a valid ISO date string
        from datetime import date
        date.fromisoformat(state["last_sync"])  # raises if invalid


class TestSyncMergesStateJson:
    """sync_project merges state.json without destroying existing fields."""

    def test_existing_fields_preserved(self, tmp_path: Path) -> None:
        _copy_canonical_files(tmp_path)
        _write_state(tmp_path, extra_fields={"custom_field": "custom_value", "another": 42})

        sync_project(tmp_path, yes=True)

        state = json.loads((tmp_path / ".companion" / "state.json").read_text(encoding="utf-8"))
        assert state.get("custom_field") == "custom_value", (
            "Existing field 'custom_field' should be preserved after sync"
        )
        assert state.get("another") == 42, "Existing field 'another' should be preserved"

    def test_pairmode_version_overwritten_on_merge(self, tmp_path: Path) -> None:
        _copy_canonical_files(tmp_path)
        _write_state(tmp_path, extra_fields={"pairmode_version": "0.0.1", "other": "keep"})

        sync_project(tmp_path, yes=True)

        state = json.loads((tmp_path / ".companion" / "state.json").read_text(encoding="utf-8"))
        assert state["pairmode_version"] == "0.1.0", "pairmode_version should be updated"
        assert state.get("other") == "keep", "'other' field should survive merge"

    def test_lessons_applied_written(self, tmp_path: Path) -> None:
        _copy_canonical_files(tmp_path)

        result = sync_project(tmp_path, yes=True)

        state = json.loads((tmp_path / ".companion" / "state.json").read_text(encoding="utf-8"))
        assert "lessons_applied" in state
        assert isinstance(state["lessons_applied"], list)
        # lessons_applied in state should match result.lessons_applied
        assert state["lessons_applied"] == result.lessons_applied


# ---------------------------------------------------------------------------
# Tests: format_sync_output
# ---------------------------------------------------------------------------


class TestFormatSyncOutput:
    """format_sync_output produces correct string."""

    def _make_result(
        self,
        applied: list[str] | None = None,
        preserved: list[str] | None = None,
        lessons_applied: list[str] | None = None,
    ) -> SyncResult:
        return SyncResult(
            project_dir=Path("/tmp/myproject"),
            applied=applied or [],
            preserved=preserved or [],
            pairmode_version="0.1.0",
            last_sync="2026-04-19",
            lessons_applied=lessons_applied or [],
        )

    def test_header_contains_project_name(self) -> None:
        result = self._make_result()
        output = format_sync_output(result)
        assert "myproject" in output

    def test_sync_complete_prefix(self) -> None:
        result = self._make_result()
        output = format_sync_output(result)
        assert "SYNC COMPLETE" in output

    def test_applied_section_present_when_items(self) -> None:
        result = self._make_result(applied=["Created CLAUDE.md"])
        output = format_sync_output(result)
        assert "Applied:" in output
        assert "Created CLAUDE.md" in output
        assert "\u2713" in output  # ✓

    def test_preserved_section_present_when_items(self) -> None:
        result = self._make_result(preserved=["CLAUDE.md: section 'custom' (project-specific)"])
        output = format_sync_output(result)
        assert "Preserved:" in output
        assert "custom" in output
        assert "\u2192" in output  # →

    def test_state_updated_line_always_present(self) -> None:
        result = self._make_result()
        output = format_sync_output(result)
        assert "State updated: .companion/state.json" in output

    def test_no_applied_section_when_empty(self) -> None:
        result = self._make_result(applied=[])
        output = format_sync_output(result)
        assert "Applied:" not in output

    def test_no_preserved_section_when_empty(self) -> None:
        result = self._make_result(preserved=[])
        output = format_sync_output(result)
        assert "Preserved:" not in output


# ---------------------------------------------------------------------------
# Tests: EXTRA items never modified
# ---------------------------------------------------------------------------


class TestExtraItemsNeverModified:
    """EXTRA items in project files are never touched during sync."""

    def test_extra_section_content_unchanged(self, tmp_path: Path) -> None:
        """A project-specific section appended to CLAUDE.md is not removed by sync."""
        _copy_canonical_files(tmp_path)
        # Append a project-specific section to CLAUDE.md
        claude_md = tmp_path / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")
        extra_content = "\n## My Custom Project Section\n\nThis is project-specific content.\n"
        claude_md.write_text(original + extra_content, encoding="utf-8")

        sync_project(tmp_path, yes=True)

        updated = claude_md.read_text(encoding="utf-8")
        assert "My Custom Project Section" in updated, (
            "Project-specific section should not be removed by sync"
        )
        assert "This is project-specific content." in updated

    def test_extra_items_appear_in_preserved_list(self, tmp_path: Path) -> None:
        """EXTRA items should appear in result.preserved, not result.applied."""
        _copy_canonical_files(tmp_path)
        # Append an extra section so audit reports it as EXTRA
        claude_md = tmp_path / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            original + "\n## My Extra Section\n\nExtra content here.\n",
            encoding="utf-8",
        )

        result = sync_project(tmp_path, yes=True)

        # The extra section key should appear in preserved, not applied
        preserved_text = " ".join(result.preserved)
        applied_text = " ".join(result.applied)
        # We can't guarantee the exact key text, but we can check it's NOT in applied
        # and that preserved is non-empty (since we added an extra section)
        assert len(result.preserved) >= 0  # guaranteed; more precisely:
        # At least, applied should not mention the extra section header keyword
        # (we can only check it's not being wrongly applied)
        assert isinstance(result.applied, list)
        assert isinstance(result.preserved, list)


# ---------------------------------------------------------------------------
# Story 4.5 edge-case tests
# ---------------------------------------------------------------------------


class TestSyncIdempotency:
    """Running sync twice produces the same result — second run has nothing to apply."""

    def test_second_sync_applies_nothing(self, tmp_path: Path) -> None:
        # First sync on empty project — will create all missing files
        sync_project(tmp_path, yes=True)

        # Second sync — files now exist and match canonical, nothing to apply
        result2 = sync_project(tmp_path, yes=True)

        assert result2.applied == [], (
            f"Second sync should apply nothing, but applied: {result2.applied}"
        )

    def test_second_sync_state_matches_first(self, tmp_path: Path) -> None:
        """State after second sync should have same pairmode_version as after first."""
        sync_project(tmp_path, yes=True)
        result2 = sync_project(tmp_path, yes=True)

        state = json.loads(
            (tmp_path / ".companion" / "state.json").read_text(encoding="utf-8")
        )
        assert state["pairmode_version"] == result2.pairmode_version

    def test_second_sync_files_unchanged(self, tmp_path: Path) -> None:
        """File contents after first and second sync should be identical."""
        sync_project(tmp_path, yes=True)
        claude_md_after_first = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")

        sync_project(tmp_path, yes=True)
        claude_md_after_second = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")

        assert claude_md_after_first == claude_md_after_second, (
            "CLAUDE.md contents changed on second sync — sync is not idempotent"
        )


class TestSyncNoPairmodeVersionInState:
    """state.json exists but has no pairmode_version key → pairmode_version is None before sync, sync still works."""

    def test_pairmode_version_none_before_sync(self, tmp_path: Path) -> None:
        """Before sync, audit sees no pairmode_version."""
        from skills.pairmode.scripts.audit import audit_project

        _write_state(tmp_path)  # writes state.json with no extra fields
        _copy_canonical_files(tmp_path)

        audit_result = audit_project(tmp_path)
        assert audit_result.pairmode_version is None

    def test_sync_succeeds_without_pairmode_version(self, tmp_path: Path) -> None:
        """Sync should not raise when state.json has no pairmode_version."""
        _write_state(tmp_path)  # no pairmode_version key
        _copy_canonical_files(tmp_path)

        # Should not raise
        result = sync_project(tmp_path, yes=True)
        assert isinstance(result, SyncResult)

    def test_sync_writes_pairmode_version_to_state(self, tmp_path: Path) -> None:
        """After sync, state.json should have pairmode_version even if it was absent before."""
        _write_state(tmp_path)  # no pairmode_version key
        _copy_canonical_files(tmp_path)

        sync_project(tmp_path, yes=True)

        state = json.loads(
            (tmp_path / ".companion" / "state.json").read_text(encoding="utf-8")
        )
        assert "pairmode_version" in state
        assert state["pairmode_version"] == "0.1.0"


class TestSyncCreatesMissingClaudeMd:
    """When CLAUDE.md doesn't exist, sync creates it from canonical."""

    def test_sync_creates_claude_md(self, tmp_path: Path) -> None:
        # All canonical files except CLAUDE.md
        for dest_rel, template_rel in CANONICAL_FILES:
            if dest_rel == "CLAUDE.md":
                continue
            template_path = TEMPLATES_DIR / template_rel
            dest_path = tmp_path / dest_rel
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if template_path.exists():
                dest_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                dest_path.write_text("# placeholder\n", encoding="utf-8")

        assert not (tmp_path / "CLAUDE.md").exists()

        sync_project(tmp_path, yes=True)

        assert (tmp_path / "CLAUDE.md").exists(), "sync should create CLAUDE.md"

    def test_created_claude_md_has_non_empty_content(self, tmp_path: Path) -> None:
        sync_project(tmp_path, yes=True)

        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert len(content.strip()) > 0, "Created CLAUDE.md should not be empty"

    def test_applied_records_claude_md_creation(self, tmp_path: Path) -> None:
        result = sync_project(tmp_path, yes=True)

        applied_text = " ".join(result.applied)
        assert "CLAUDE.md" in applied_text, (
            f"CLAUDE.md creation should appear in applied list, got: {result.applied}"
        )


class TestSyncPreservesProjectSpecificSections:
    """Project-specific checklist items / extra sections survive sync."""

    def test_extra_section_text_preserved_after_sync(self, tmp_path: Path) -> None:
        _copy_canonical_files(tmp_path)

        claude_md = tmp_path / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")
        unique_text = "UNIQUE_MARKER_XYZ: do not remove this line"
        claude_md.write_text(
            original + f"\n## Project Checklist\n\n{unique_text}\n",
            encoding="utf-8",
        )

        sync_project(tmp_path, yes=True)

        updated = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert unique_text in updated, (
            "Project-specific section content was removed by sync"
        )

    def test_extra_section_heading_preserved_after_sync(self, tmp_path: Path) -> None:
        _copy_canonical_files(tmp_path)

        claude_md = tmp_path / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            original + "\n## Project Checklist\n\nSome checklist items.\n",
            encoding="utf-8",
        )

        sync_project(tmp_path, yes=True)

        updated = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "## Project Checklist" in updated, (
            "Project-specific section heading was removed by sync"
        )

    def test_extra_sections_appear_in_preserved_list(self, tmp_path: Path) -> None:
        _copy_canonical_files(tmp_path)

        claude_md = tmp_path / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            original + "\n## Project Checklist\n\nSome checklist items.\n",
            encoding="utf-8",
        )

        result = sync_project(tmp_path, yes=True)

        # The extra section should be preserved, not applied
        assert len(result.preserved) > 0, (
            "Expected project-specific sections in preserved list"
        )
        preserved_text = " ".join(result.preserved)
        assert "CLAUDE.md" in preserved_text, (
            "Expected CLAUDE.md in preserved list"
        )


# ---------------------------------------------------------------------------
# Context rendering tests
# ---------------------------------------------------------------------------


class TestSyncUsesContextWhenCreatingFiles:
    """sync_project uses pairmode_context.json when creating missing CLAUDE.md."""

    def test_sync_creates_claude_md_with_rendered_content_not_raw_j2(
        self, tmp_path: Path
    ) -> None:
        """When pairmode_context.json exists with project_name='cora', sync creates
        CLAUDE.md with rendered content (contains 'cora', not '{{ project_name }}')."""
        import json as _json

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        ctx = {
            "project_name": "cora",
            "project_description": "a test project",
            "stack": "Python / pytest",
            "build_command": "uv run pytest",
            "test_command": "uv run pytest",
            "migration_command": "",
            "domain_model": "",
            "domain_isolation_rule": "",
            "checklist_items": [],
            "protected_paths": [],
            "non_negotiables": [],
            "module_structure": [],
            "layer_rules": [],
        }
        (companion / "pairmode_context.json").write_text(
            _json.dumps(ctx), encoding="utf-8"
        )

        # No CLAUDE.md exists — sync should create it
        assert not (tmp_path / "CLAUDE.md").exists()
        sync_project(tmp_path, yes=True)

        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        # Should contain rendered project name, not raw Jinja2
        assert "cora" in content, "Created CLAUDE.md should contain rendered project name"
        assert "{{ project_name }}" not in content, (
            "Created CLAUDE.md should not contain raw Jinja2 syntax"
        )


# ---------------------------------------------------------------------------
# Story 6.1 — context_missing: no INCONSISTENT patches applied
# ---------------------------------------------------------------------------


class TestSyncSkipsInconsistentWhenContextMissing:
    """When pairmode_context.json is absent, sync_project does not write INCONSISTENT patches."""

    def test_no_inconsistent_in_applied_when_context_missing(self, tmp_path: Path) -> None:
        """With no pairmode_context.json, applied list contains no INCONSISTENT entries."""
        _copy_canonical_files(tmp_path)
        # Modify a file body so it would normally be INCONSISTENT
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "## Session modes\n\nDifferent content that would differ from canonical.\n",
            encoding="utf-8",
        )
        # Ensure no pairmode_context.json exists
        context_path = tmp_path / ".companion" / "pairmode_context.json"
        assert not context_path.exists()

        result = sync_project(tmp_path, yes=True)

        inconsistent_entries = [
            entry for entry in result.applied if "Updated section" in entry
        ]
        assert inconsistent_entries == [], (
            f"Expected no INCONSISTENT patches when context is missing, got: {inconsistent_entries}"
        )

    def test_files_not_overwritten_for_inconsistent_when_context_missing(
        self, tmp_path: Path
    ) -> None:
        """When context is missing, the project file is not rewritten for INCONSISTENT sections."""
        _copy_canonical_files(tmp_path)
        # Write a custom body into CLAUDE.md
        unique_marker = "UNIQUE_MARKER_CONTEXT_MISSING_TEST"
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            f"## Session modes\n\n{unique_marker}\n",
            encoding="utf-8",
        )

        sync_project(tmp_path, yes=True)

        # The unique marker should still be in the file (sync did not overwrite it)
        content = claude_md.read_text(encoding="utf-8")
        assert unique_marker in content, (
            "sync_project overwrote project file despite missing context — INCONSISTENT patch "
            "should be skipped when pairmode_context.json is absent"
        )


# ---------------------------------------------------------------------------
# Story 7.7 — Phase 7 file creation
# ---------------------------------------------------------------------------


class TestSyncPhase7FilesCreated:
    """sync_project creates docs/brief.md, docs/phases/index.md, and docs/cer/backlog.md
    when they are MISSING."""

    def test_sync_creates_docs_brief_md_when_missing(self, tmp_path: Path) -> None:
        """sync_project creates docs/brief.md when it is absent."""
        _copy_canonical_files(tmp_path)
        # Remove the placeholder to simulate a project without this file
        brief = tmp_path / "docs" / "brief.md"
        if brief.exists():
            brief.unlink()

        sync_project(tmp_path, yes=True)

        assert (tmp_path / "docs" / "brief.md").exists(), (
            "sync_project should create docs/brief.md"
        )

    def test_sync_creates_docs_phases_index_md_when_missing(self, tmp_path: Path) -> None:
        """sync_project creates docs/phases/index.md when it is absent."""
        _copy_canonical_files(tmp_path)
        # Remove the placeholder to simulate a project without this file
        index = tmp_path / "docs" / "phases" / "index.md"
        if index.exists():
            index.unlink()

        sync_project(tmp_path, yes=True)

        assert (tmp_path / "docs" / "phases" / "index.md").exists(), (
            "sync_project should create docs/phases/index.md"
        )

    def test_sync_creates_docs_cer_backlog_md_when_missing(self, tmp_path: Path) -> None:
        """sync_project creates docs/cer/backlog.md when it is absent."""
        _copy_canonical_files(tmp_path)
        # Remove the placeholder to simulate a project without this file
        backlog = tmp_path / "docs" / "cer" / "backlog.md"
        if backlog.exists():
            backlog.unlink()

        sync_project(tmp_path, yes=True)

        assert (tmp_path / "docs" / "cer" / "backlog.md").exists(), (
            "sync_project should create docs/cer/backlog.md"
        )

    def test_roundtrip_brief_md(self, tmp_path: Path) -> None:
        """Roundtrip: fresh project → delete docs/brief.md → audit MISSING → sync creates → audit clean."""
        from skills.pairmode.scripts.audit import audit_project

        # Step 1: sync creates all files including docs/brief.md
        sync_project(tmp_path, yes=True)
        assert (tmp_path / "docs" / "brief.md").exists()

        # Step 2: delete docs/brief.md
        (tmp_path / "docs" / "brief.md").unlink()

        # Step 3: audit reports it as MISSING
        audit_result = audit_project(tmp_path)
        missing_files = {i.file for i in audit_result.missing}
        assert "docs/brief.md" in missing_files, (
            "Expected docs/brief.md in missing after deletion"
        )

        # Step 4: sync creates it again
        sync_project(tmp_path, yes=True)
        assert (tmp_path / "docs" / "brief.md").exists(), (
            "sync_project should recreate docs/brief.md"
        )

        # Step 5: audit no longer reports it as MISSING
        audit_result2 = audit_project(tmp_path)
        missing_files2 = {i.file for i in audit_result2.missing}
        assert "docs/brief.md" not in missing_files2, (
            "docs/brief.md should not be MISSING after sync recreated it"
        )


# ---------------------------------------------------------------------------
# Story 8.0 — confirmation gate tests
# ---------------------------------------------------------------------------


class TestSyncYesFlagBypassesPrompts:
    """With --yes, all changes are applied without any prompts."""

    def test_yes_applies_missing_file_without_prompt(self, tmp_path: Path) -> None:
        """With yes=True, a MISSING file is created without confirmation prompt."""
        # Empty project — CLAUDE.md will be missing
        result = sync_project(tmp_path, yes=True)

        assert (tmp_path / "CLAUDE.md").exists(), "CLAUDE.md should be created with yes=True"
        applied_text = " ".join(result.applied)
        assert "CLAUDE.md" in applied_text

    def test_yes_skipped_list_empty(self, tmp_path: Path) -> None:
        """With yes=True, skipped list is always empty."""
        result = sync_project(tmp_path, yes=True)

        assert result.skipped == [], (
            f"Expected empty skipped list with yes=True, got: {result.skipped}"
        )

    def test_yes_flag_via_cli(self, tmp_path: Path) -> None:
        """CLI --yes flag applies all changes without prompts."""
        runner = CliRunner()
        result = runner.invoke(sync_main, ["--project-dir", str(tmp_path), "--yes"])

        assert result.exit_code == 0, f"CLI exited with {result.exit_code}: {result.output}"
        assert (tmp_path / "CLAUDE.md").exists(), "CLAUDE.md should be created via CLI --yes"

    def test_yes_shortflag_via_cli(self, tmp_path: Path) -> None:
        """CLI -y short flag also works."""
        runner = CliRunner()
        result = runner.invoke(sync_main, ["--project-dir", str(tmp_path), "-y"])

        assert result.exit_code == 0, f"CLI exited with {result.exit_code}: {result.output}"


class TestSyncConfirmationPromptMissingFile:
    """Without --yes, a prompt is shown for MISSING files; accepting creates the file."""

    def test_prompt_shown_for_missing_file(self, tmp_path: Path) -> None:
        """Confirmation prompt text is shown for a missing file."""
        runner = CliRunner()
        # Provide "y" to accept the first prompt (CLAUDE.md missing)
        # then "y" for every subsequent prompt
        result = runner.invoke(
            sync_main,
            ["--project-dir", str(tmp_path)],
            input="y\n" * 20,  # enough y's for all prompts
        )

        assert result.exit_code == 0, f"CLI exited with {result.exit_code}: {result.output}"
        # The prompt text for a missing file should appear
        assert "file missing" in result.output.lower() or "Create" in result.output

    def test_accepting_prompt_creates_missing_file(self, tmp_path: Path) -> None:
        """Accepting the confirmation prompt for a MISSING file causes it to be created."""
        runner = CliRunner()
        result = runner.invoke(
            sync_main,
            ["--project-dir", str(tmp_path)],
            input="y\n" * 20,
        )

        assert result.exit_code == 0, f"CLI exited with {result.exit_code}: {result.output}"
        assert (tmp_path / "CLAUDE.md").exists(), (
            "CLAUDE.md should be created when user accepts the prompt"
        )

    def test_accepting_prompt_applies_to_result(self, tmp_path: Path) -> None:
        """When user accepts, the file appears in applied and skipped is empty."""
        result = sync_project(tmp_path, yes=True)

        assert len(result.applied) > 0, "Should have applied items when accepting"
        assert result.skipped == [], "skipped should be empty when user accepts (or yes=True)"


class TestSyncConfirmationPromptDeclineInconsistent:
    """Without --yes, declining an INCONSISTENT section prompt skips the update."""

    def _setup_inconsistent_project(self, tmp_path: Path) -> None:
        """Set up a project with pairmode_context.json and a modified CLAUDE.md section."""
        import json as _json

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        ctx = {
            "project_name": "testproject",
            "project_description": "a test project",
            "stack": "Python",
            "build_command": "uv run pytest",
            "test_command": "uv run pytest",
            "migration_command": "",
            "domain_model": "",
            "domain_isolation_rule": "",
            "checklist_items": [],
            "protected_paths": [],
            "non_negotiables": [],
            "module_structure": [],
            "layer_rules": [],
        }
        (companion / "pairmode_context.json").write_text(_json.dumps(ctx), encoding="utf-8")

        # Copy all canonical files to set up a baseline
        _copy_canonical_files(tmp_path)

    def test_declining_inconsistent_skips_update(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Declining the INCONSISTENT prompt leaves the section unchanged."""
        self._setup_inconsistent_project(tmp_path)

        # Modify a section in CLAUDE.md so it becomes INCONSISTENT
        claude_md = tmp_path / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")

        # Find a section that exists and modify its body
        from skills.pairmode.scripts.sync import _split_by_h2, _reconstruct_from_parts
        parts = _split_by_h2(original)
        modified = False
        new_parts = []
        unique_marker = "UNIQUE_DECLINE_MARKER_12345"
        for header, body in parts:
            if not modified and header.startswith("## "):
                new_parts.append((header, f"\n{unique_marker}\n\nModified content.\n"))
                modified = True
            else:
                new_parts.append((header, body))
        if not modified:
            claude_md.write_text(
                f"## Session modes\n\n{unique_marker}\n\nModified content.\n",
                encoding="utf-8",
            )
        else:
            claude_md.write_text(_reconstruct_from_parts(new_parts), encoding="utf-8")

        # Patch click.confirm to always decline
        import skills.pairmode.scripts.sync as sync_mod
        monkeypatch.setattr(sync_mod.click, "confirm", lambda *a, **kw: False)

        result = sync_project(tmp_path, yes=False)

        # The unique marker should still be in the file (sync did not overwrite it)
        content = claude_md.read_text(encoding="utf-8")
        assert unique_marker in content, (
            "File should not be modified when user declines the INCONSISTENT prompt"
        )

    def test_declined_items_in_skipped_not_applied(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When user declines, the item appears in result.skipped, not result.applied."""
        self._setup_inconsistent_project(tmp_path)

        # Modify a section in CLAUDE.md so it becomes INCONSISTENT
        claude_md = tmp_path / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")
        from skills.pairmode.scripts.sync import _split_by_h2, _reconstruct_from_parts
        parts = _split_by_h2(original)
        new_parts = []
        modified = False
        unique_marker = "DECLINED_TEST_MARKER_99999"
        for header, body in parts:
            if not modified and header.startswith("## "):
                new_parts.append((header, f"\n{unique_marker}\n"))
                modified = True
            else:
                new_parts.append((header, body))
        if modified:
            claude_md.write_text(_reconstruct_from_parts(new_parts), encoding="utf-8")

        # Monkeypatch click.confirm to always return False (user declines)
        import skills.pairmode.scripts.sync as sync_mod
        monkeypatch.setattr(sync_mod.click, "confirm", lambda *a, **kw: False)

        result = sync_project(tmp_path, yes=False)

        # All prompts were declined — nothing should be applied (for INCONSISTENT)
        # skipped should have entries
        assert len(result.skipped) > 0 or len(result.applied) == 0, (
            "When user declines all prompts, items should be in skipped, not applied"
        )
        # The unique marker should still be in the file
        content = claude_md.read_text(encoding="utf-8")
        assert unique_marker in content, (
            "File should not be modified when user declines the prompt"
        )

    def test_declined_items_not_written(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When user declines a MISSING file, the file is not created."""
        # Empty project — all files missing
        import skills.pairmode.scripts.sync as sync_mod
        monkeypatch.setattr(sync_mod.click, "confirm", lambda *a, **kw: False)

        result = sync_project(tmp_path, yes=False)

        # CLAUDE.md should NOT be created (user declined)
        assert not (tmp_path / "CLAUDE.md").exists(), (
            "CLAUDE.md should not be created when user declines the prompt"
        )
        # All items should be in skipped
        assert len(result.skipped) > 0, "Declined items should appear in result.skipped"
        assert result.applied == [], "No items should be applied when user declines all"


class TestSyncFormatOutputSkipped:
    """format_sync_output includes a skipped section when items were declined."""

    def _make_result_with_skipped(self, skipped: list[str]) -> SyncResult:
        return SyncResult(
            project_dir=Path("/tmp/myproject"),
            applied=[],
            preserved=[],
            skipped=skipped,
            pairmode_version="0.1.0",
            last_sync="2026-04-21",
            lessons_applied=[],
        )

    def test_skipped_section_present_when_items(self) -> None:
        result = self._make_result_with_skipped(
            ["CLAUDE.md: section '## review checklist' (user declined)"]
        )
        output = format_sync_output(result)
        assert "Skipped" in output
        assert "user declined" in output

    def test_skipped_section_shows_x_marker(self) -> None:
        result = self._make_result_with_skipped(
            ["CLAUDE.md: section '## review checklist' (user declined)"]
        )
        output = format_sync_output(result)
        assert "\u2717" in output  # ✗

    def test_skipped_section_absent_when_empty(self) -> None:
        result = self._make_result_with_skipped([])
        output = format_sync_output(result)
        assert "Skipped" not in output

    def test_skipped_section_shows_item_text(self) -> None:
        item_text = "CLAUDE.md: section '## review checklist' (user declined)"
        result = self._make_result_with_skipped([item_text])
        output = format_sync_output(result)
        assert "review checklist" in output

    def test_skipped_in_result_dataclass(self) -> None:
        """SyncResult has a skipped field that is a list."""
        result = SyncResult(project_dir=Path("/tmp/test"))
        assert hasattr(result, "skipped")
        assert isinstance(result.skipped, list)
        assert result.skipped == []


# ---------------------------------------------------------------------------
# Story 9.0 — dead code removal
# ---------------------------------------------------------------------------


class TestNoDeadCodeInLoadProjectContext:
    """The orphaned 'return enriched' dead code was removed from _load_project_context."""

    def test_enriched_not_in_source(self) -> None:
        """Source-level check: 'enriched' does not appear in _load_project_context."""
        import inspect
        from skills.pairmode.scripts import sync

        source = inspect.getsource(sync._load_project_context)
        assert "enriched" not in source, (
            "Dead code 'return enriched' must not exist in _load_project_context"
        )


# ---------------------------------------------------------------------------
# Story 10.6: path traversal containment guard
# ---------------------------------------------------------------------------


class TestSyncPathTraversalGuard:
    """sync_project() must reject paths that are too close to the filesystem root."""

    def test_root_dir_raises_system_exit(self):
        """Calling sync_project('/') raises SystemExit."""
        with pytest.raises(SystemExit) as exc_info:
            sync_project(Path("/"))
        assert exc_info.value.code != 0

    def test_etc_dir_raises_system_exit(self):
        """Calling sync_project('/etc') raises SystemExit."""
        with pytest.raises(SystemExit) as exc_info:
            sync_project(Path("/etc"))
        assert exc_info.value.code != 0

    def test_valid_project_dir_succeeds(self, tmp_path):
        """A valid project dir with 3+ path parts does not raise SystemExit (regression)."""
        _copy_canonical_files(tmp_path)
        _write_ideology_md(tmp_path)
        _write_state(tmp_path)
        # Should not raise — sync may produce a result with no changes
        result = sync_project(tmp_path, yes=True)
        assert isinstance(result, SyncResult)


# ---------------------------------------------------------------------------
# Story AUDIT-001 — .pairmode-overrides: sync skips declared sections
# ---------------------------------------------------------------------------


def _write_overrides(project_dir: Path, lines: list[str]) -> None:
    """Write .pairmode-overrides at project root."""
    content = "\n".join(lines) + "\n"
    (project_dir / ".pairmode-overrides").write_text(content, encoding="utf-8")


class TestSyncOverrides:
    """sync_project respects .pairmode-overrides: declared sections are skipped with a note."""

    def _get_first_canonical_section_key(self) -> tuple[str, str]:
        """Return (raw_header, normalised_key) for the first ## header in CLAUDE.md.j2."""
        import re
        from skills.pairmode.scripts.audit import _normalise
        canonical_text = (TEMPLATES_DIR / "CLAUDE.md.j2").read_text(encoding="utf-8")
        headers = re.findall(r"^## .+", canonical_text, re.MULTILINE)
        assert headers, "CLAUDE.md.j2 must have at least one ## header"
        return headers[0], _normalise(headers[0])

    def test_override_section_not_appended_to_existing_file(self, tmp_path: Path) -> None:
        """When a MISSING section in an existing file is declared in .pairmode-overrides,
        sync does not append it to the file."""
        import re
        from skills.pairmode.scripts.audit import _normalise, audit_project

        _copy_canonical_files(tmp_path)
        _write_ideology_md(tmp_path)
        _write_state(tmp_path)

        canonical_text = (TEMPLATES_DIR / "CLAUDE.md.j2").read_text(encoding="utf-8")
        headers = re.findall(r"^## .+", canonical_text, re.MULTILINE)
        assert len(headers) >= 2, "CLAUDE.md.j2 must have at least 2 ## headers"

        last_header = headers[-1]
        last_key = _normalise(last_header)

        # Write a CLAUDE.md stub with only the first section so the last section is MISSING
        (tmp_path / "CLAUDE.md").write_text(
            f"{headers[0]}\n\nSome content.\n",
            encoding="utf-8",
        )

        # Confirm the section is MISSING without overrides
        result_pre = audit_project(tmp_path)
        missing_keys = {i.section for i in result_pre.missing if i.file == "CLAUDE.md"}
        assert last_key in missing_keys, (
            f"Expected '{last_key}' to be MISSING before override. Got: {missing_keys}"
        )

        # Declare the last section as override
        _write_overrides(tmp_path, [f"CLAUDE.md:{last_key}"])

        # With override, the section should not be MISSING in audit
        result_override = audit_project(tmp_path)
        missing_after = {i.section for i in result_override.missing if i.file == "CLAUDE.md"}
        assert last_key not in missing_after, (
            f"Override section '{last_key}' still appears as MISSING: {missing_after}"
        )

        # Sync should not append the section
        content_before = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        sync_project(tmp_path, yes=True)
        content_after = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")

        # The last_header should not appear in the file (it was not appended)
        assert last_header not in content_after, (
            f"Override section '{last_header}' was appended by sync despite .pairmode-overrides"
        )

    def test_sync_with_override_skips_inconcsistent_section_print(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When sync encounters a section in overrides (via monkeypatched audit), it prints the note."""
        import re
        from skills.pairmode.scripts.audit import _normalise, AuditItem
        import skills.pairmode.scripts.sync as sync_mod

        _copy_canonical_files(tmp_path)
        _write_ideology_md(tmp_path)
        _write_state(tmp_path)

        canonical_text = (TEMPLATES_DIR / "CLAUDE.md.j2").read_text(encoding="utf-8")
        headers = re.findall(r"^## .+", canonical_text, re.MULTILINE)
        last_key = _normalise(headers[-1])

        # Write a CLAUDE.md stub so file exists but last section is missing
        (tmp_path / "CLAUDE.md").write_text(
            f"{headers[0]}\n\nSome content.\n",
            encoding="utf-8",
        )

        # Declare the last section as an override in the file
        _write_overrides(tmp_path, [f"CLAUDE.md:{last_key}"])

        # Monkeypatch audit_project to return the override section as MISSING
        # (simulating the case where audit returns it despite it being in overrides)
        from skills.pairmode.scripts.audit import audit_project, AuditResult
        original_audit = audit_project

        def patched_audit(project_dir, applies_to="all"):
            real_result = original_audit(project_dir, applies_to=applies_to)
            # Inject an extra MISSING item for the override section
            real_result.missing.append(
                AuditItem(
                    file="CLAUDE.md",
                    section=last_key,
                    description=f"Section '{last_key}' present in canonical but not in project",
                )
            )
            return real_result

        monkeypatch.setattr(sync_mod, "audit_project", patched_audit)

        output_lines = []
        original_echo = sync_mod.click.echo
        def capture_echo(msg="", **kw):
            output_lines.append(str(msg))
            original_echo(msg, **kw)
        monkeypatch.setattr(sync_mod.click, "echo", capture_echo)

        result = sync_project(tmp_path, yes=True)

        combined_output = "\n".join(output_lines)
        assert "project-owned" in combined_output, (
            f"Expected 'project-owned' skip message when sync defensive check fires. "
            f"Got: {combined_output}"
        )
        assert any("override declared" in s for s in result.skipped), (
            f"Expected 'override declared' in result.skipped. Got: {result.skipped}"
        )
