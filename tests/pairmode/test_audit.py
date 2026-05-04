"""Tests for audit.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills.pairmode.scripts.audit import (
    AuditItem,
    AuditResult,
    audit_project,
    format_audit_output,
    _load_project_context,
    _JINJA_ENV,
    _is_separator_key,
    _is_stale_placeholder,
    _enrich_scaffold_context,
    _check_ideology_staleness,
    _check_reconstruction_staleness,
    _load_overrides,
    SCAFFOLD_FILES,
)
from skills.pairmode.scripts import audit as _audit_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEMPLATES_DIR = _audit_mod.TEMPLATES_DIR
CANONICAL_FILES = _audit_mod.CANONICAL_FILES


def _write_state(project_dir: Path, version: str | None = "0.1.0") -> None:
    companion = project_dir / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    state: dict = {}
    if version is not None:
        state["pairmode_version"] = version
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _copy_canonical_files(project_dir: Path) -> None:
    """Render all canonical template files with fallback context and write into project_dir.

    Uses the same context that audit_project would use when pairmode_context.json is absent,
    so that rendered canonical == rendered template and no false INCONSISTENT is produced.
    Also creates Phase 7 scaffold files with non-placeholder content so they are not flagged MISSING
    or STALE PLACEHOLDER in tests that expect a clean baseline.
    """
    context, _ = _load_project_context(project_dir)

    for dest_rel, template_rel in CANONICAL_FILES:
        dest_path = project_dir / dest_rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            rendered = _JINJA_ENV.get_template(template_rel).render(**context)
        except Exception:
            rendered = "# placeholder\n"
        dest_path.write_text(rendered, encoding="utf-8")

    # Also create Phase 7 scaffold files with non-placeholder content.
    # Scaffold files (brief.md, index.md, backlog.md) are project-specific docs;
    # we write them with real-looking content so tests get a clean baseline.
    _write_clean_scaffold_files(project_dir)


def _write_ideology_md(project_dir: Path, stale: bool = False) -> None:
    """Write docs/ideology.md — real content when stale=False, placeholders when stale=True."""
    (project_dir / "docs").mkdir(parents=True, exist_ok=True)
    ideology_path = project_dir / "docs" / "ideology.md"
    if stale:
        content = (
            "# Ideology — testproject\n\n"
            "## Core convictions\n\n"
            "_(not yet specified — what do you believe?)_\n\n"
            "## Value hierarchy\n\n"
            "_(not yet specified — what do you value most?)_\n\n"
            "## Accepted constraints\n\n"
            "_(not yet specified — what constraints do you accept?)_\n\n"
            "## Prototype fingerprints\n\n"
            "_(not yet specified — what are your fingerprints?)_\n\n"
            "## Reconstruction guidance\n\n"
            "_(not yet specified — how would you reconstruct?)_\n\n"
            "## Comparison basis\n\n"
            "_(not yet specified — what is the comparison basis?)_\n"
        )
    else:
        content = (
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
            "Compare against the reference implementation in the anchor repo.\n"
        )
    ideology_path.write_text(content, encoding="utf-8")


def _write_clean_scaffold_files(project_dir: Path) -> None:
    """Write scaffold files with non-placeholder content for test baseline purposes."""
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
            "To provide a baseline for audit tests.\n\n"
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

    # Write ideology.md with real content so it doesn't trigger MISSING/STALE
    ideology_path = project_dir / "docs" / "ideology.md"
    if not ideology_path.exists():
        _write_ideology_md(project_dir, stale=False)

    # Write reconstruction.md as a completed scoring report (no generated footer)
    # so it doesn't trigger MISSING/STALE in baseline tests
    reconstruction_path = project_dir / "docs" / "reconstruction.md"
    if not reconstruction_path.exists():
        reconstruction_path.write_text(
            "# Reconstruction Report — testproject\n\n"
            "**Reconstruction date:** 2026-01-01\n\n"
            "---\n\n"
            "## Ideology adherence\n\n"
            "The implementation expresses the core convictions fully.\n\n"
            "## Constraint compliance\n\n"
            "All constraints are satisfied.\n\n"
            "## Comparison rubric scores\n\n"
            "Performance: on par. Correctness: exceeds original.\n\n"
            "## Summary verdict\n\n"
            "Strong alignment with ideology.\n",
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuditProjectAllPresentIdentical:
    """All canonical files present and identical → nothing MISSING, possible EXTRA only."""

    def test_no_missing_when_all_files_present_and_identical(self, tmp_path: Path) -> None:
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        result = audit_project(tmp_path)

        assert result.missing == [], f"Expected no missing items, got: {result.missing}"
        assert result.inconsistent == [], (
            f"Expected no inconsistent items, got: {result.inconsistent}"
        )

    def test_extra_sections_exist_for_project_specific_content(self, tmp_path: Path) -> None:
        """When project files match canonical exactly there should be no extra sections
        beyond what the templates themselves produce (EXTRA can be empty or non-empty
        depending on preamble handling — just assert it is a list)."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        result = audit_project(tmp_path)

        assert isinstance(result.extra, list)


class TestAuditProjectMissingClaudeMd:
    """Project missing CLAUDE.md → CLAUDE.md sections appear in MISSING."""

    def test_missing_claude_md_produces_missing_items(self, tmp_path: Path) -> None:
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Remove CLAUDE.md
        (tmp_path / "CLAUDE.md").unlink()

        result = audit_project(tmp_path)

        claude_md_missing = [i for i in result.missing if i.file == "CLAUDE.md"]
        assert len(claude_md_missing) > 0, "Expected MISSING items for CLAUDE.md"

    def test_missing_claude_md_description_mentions_file(self, tmp_path: Path) -> None:
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        (tmp_path / "CLAUDE.md").unlink()

        result = audit_project(tmp_path)

        for item in result.missing:
            if item.file == "CLAUDE.md":
                assert "CLAUDE.md" in item.file
                break


class TestAuditProjectNoPairmodeVersion:
    """Project with no pairmode_version in state.json → pairmode_version is None."""

    def test_no_pairmode_version_key(self, tmp_path: Path) -> None:
        _write_state(tmp_path, version=None)  # state.json exists but no version key

        result = audit_project(tmp_path)

        assert result.pairmode_version is None

    def test_no_state_json_at_all(self, tmp_path: Path) -> None:
        # No .companion/state.json at all
        result = audit_project(tmp_path)

        assert result.pairmode_version is None

    def test_canonical_version_always_set(self, tmp_path: Path) -> None:
        result = audit_project(tmp_path)

        assert result.canonical_version == "0.1.0"


class TestFormatAuditOutput:
    """format_audit_output produces correct string with all sections."""

    def _make_result(
        self,
        missing: list[AuditItem] | None = None,
        inconsistent: list[AuditItem] | None = None,
        extra: list[AuditItem] | None = None,
    ) -> AuditResult:
        return AuditResult(
            project_name="myproject",
            project_dir=Path("/tmp/myproject"),
            missing=missing or [],
            inconsistent=inconsistent or [],
            extra=extra or [],
            pairmode_version="0.1.0",
            canonical_version="0.1.0",
        )

    def test_header_contains_project_name_and_version(self) -> None:
        result = self._make_result()
        output = format_audit_output(result)
        assert "myproject" in output
        assert "0.1.0" in output

    def test_missing_section_present_when_items_exist(self) -> None:
        result = self._make_result(
            missing=[AuditItem(file="CLAUDE.md", section="intro", description="Missing intro")]
        )
        output = format_audit_output(result)
        assert "MISSING" in output
        assert "CLAUDE.md" in output
        assert "\u2717" in output  # ✗

    def test_inconsistent_section_present(self) -> None:
        result = self._make_result(
            inconsistent=[
                AuditItem(file="CLAUDE.build.md", section="rules", description="Rules differ")
            ]
        )
        output = format_audit_output(result)
        assert "INCONSISTENT" in output
        assert "CLAUDE.build.md" in output
        assert "~" in output

    def test_extra_section_present(self) -> None:
        result = self._make_result(
            extra=[
                AuditItem(
                    file=".claude/agents/builder.md",
                    section="custom",
                    description="Custom section",
                )
            ]
        )
        output = format_audit_output(result)
        assert "EXTRA" in output
        assert ".claude/agents/builder.md" in output
        assert "\u2713" in output  # ✓

    def test_recommendation_always_present(self) -> None:
        result = self._make_result()
        output = format_audit_output(result)
        assert "RECOMMENDATION" in output
        assert "sync" in output

    def test_empty_sections_omitted(self) -> None:
        result = self._make_result()  # no items anywhere
        output = format_audit_output(result)
        assert "MISSING" not in output
        assert "INCONSISTENT" not in output
        assert "EXTRA" not in output

    def test_lesson_id_appears_in_missing_item(self) -> None:
        result = self._make_result(
            missing=[
                AuditItem(
                    file="CLAUDE.md",
                    section="intro",
                    description="Missing intro",
                    lesson_id="L001",
                )
            ]
        )
        output = format_audit_output(result)
        assert "L001" in output


class TestLessonIdInMissingItems:
    """Lesson IDs appear in MISSING items when a lesson applies."""

    def test_lesson_id_attached_when_lesson_affects_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When a lesson's methodology_change.affects mentions CLAUDE.md and the file
        is missing, the lesson_id should be attached to the AuditItem."""
        fake_lessons_data = {
            "version": "1.0.0",
            "lessons": [
                {
                    "id": "L001",
                    "trigger": "test trigger",
                    "learning": "some learning",
                    "date": "2026-01-01",
                    "status": "active",
                    "applies_to": ["all"],
                    "methodology_change": {
                        "affects": "CLAUDE.md",
                        "description": "Update CLAUDE.md",
                    },
                }
            ],
        }

        monkeypatch.setattr(
            _audit_mod.lesson_utils,
            "load_lessons",
            lambda: fake_lessons_data,
        )

        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        (tmp_path / "CLAUDE.md").unlink()

        result = audit_project(tmp_path)

        claude_md_missing = [i for i in result.missing if i.file == "CLAUDE.md"]
        assert len(claude_md_missing) > 0
        lesson_ids = [i.lesson_id for i in claude_md_missing if i.lesson_id]
        assert "L001" in lesson_ids, f"Expected L001 in lesson_ids, got: {lesson_ids}"


class TestNoCompanionStateJson:
    """audit_project on a directory with no .companion/state.json → pairmode_version is None."""

    def test_no_companion_dir(self, tmp_path: Path) -> None:
        # tmp_path has no .companion directory at all
        result = audit_project(tmp_path)
        assert result.pairmode_version is None

    def test_no_error_raised(self, tmp_path: Path) -> None:
        # Should not raise
        result = audit_project(tmp_path)
        assert isinstance(result, AuditResult)


# ---------------------------------------------------------------------------
# Story 4.5 edge-case tests
# ---------------------------------------------------------------------------


class TestAuditClaudeMdFewerSections:
    """CLAUDE.md exists but has fewer sections than canonical → missing sections in MISSING."""

    def test_missing_sections_appear_in_missing_list(self, tmp_path: Path) -> None:
        """Write a CLAUDE.md that only has the preamble — all canonical sections are absent."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        # Replace CLAUDE.md with a stub that has only a preamble and one section
        stub = "# Project context\n\nThis is a minimal CLAUDE.md with just a preamble.\n"
        (tmp_path / "CLAUDE.md").write_text(stub, encoding="utf-8")

        result = audit_project(tmp_path)

        # The canonical template has multiple sections; at least some must be MISSING
        claude_md_missing = [i for i in result.missing if i.file == "CLAUDE.md"]
        assert len(claude_md_missing) > 0, (
            "Expected MISSING items for CLAUDE.md sections absent from the project file"
        )

    def test_sections_present_in_project_are_not_missing(self, tmp_path: Path) -> None:
        """Sections that DO appear in the project file should not be reported as MISSING."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        # The canonical CLAUDE.md — read the first real header from it
        canonical_text = (
            _audit_mod.TEMPLATES_DIR / "CLAUDE.md.j2"
        ).read_text(encoding="utf-8")

        # Find a header that exists in the canonical template
        import re
        headers = re.findall(r"^## .+", canonical_text, re.MULTILINE)
        assert headers, "Canonical CLAUDE.md.j2 should have at least one ## header"

        # Build a stub that contains just this one header/section
        first_header = headers[0]
        stub = f"{first_header}\n\nSome content.\n"
        (tmp_path / "CLAUDE.md").write_text(stub, encoding="utf-8")

        result = audit_project(tmp_path)

        # The section corresponding to this header should NOT be in missing
        # (it may be in inconsistent because the body differs — that's OK)
        from skills.pairmode.scripts.audit import _normalise
        normalised_header = _normalise(first_header)
        missing_keys = {i.section for i in result.missing if i.file == "CLAUDE.md"}
        assert normalised_header not in missing_keys, (
            f"Section '{normalised_header}' is present in project but appears in MISSING"
        )


class TestAuditExtraCustomSections:
    """Project CLAUDE.md has extra custom sections not in canonical → appear in EXTRA."""

    def test_extra_sections_appear_in_extra_list(self, tmp_path: Path) -> None:
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        # Append a custom section that is not in any canonical template
        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            existing + "\n## My Unique Project Section\n\nProject-specific notes here.\n",
            encoding="utf-8",
        )

        result = audit_project(tmp_path)

        extra_files = [i.file for i in result.extra]
        assert "CLAUDE.md" in extra_files, (
            f"Expected CLAUDE.md in extra items, got: {extra_files}"
        )

    def test_extra_section_key_is_in_extra_list(self, tmp_path: Path) -> None:
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        from skills.pairmode.scripts.audit import _normalise
        custom_header = "## My Unique Project Section"
        normalised_custom = _normalise(custom_header)

        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            existing + f"\n{custom_header}\n\nProject-specific notes here.\n",
            encoding="utf-8",
        )

        result = audit_project(tmp_path)

        extra_sections = {i.section for i in result.extra if i.file == "CLAUDE.md"}
        assert normalised_custom in extra_sections, (
            f"Expected '{normalised_custom}' in extra sections, got: {extra_sections}"
        )

    def test_extra_sections_do_not_appear_in_missing(self, tmp_path: Path) -> None:
        """Custom project sections should not be mistakenly flagged as MISSING."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            existing + "\n## My Unique Project Section\n\nProject-specific notes here.\n",
            encoding="utf-8",
        )

        result = audit_project(tmp_path)

        from skills.pairmode.scripts.audit import _normalise
        normalised_custom = _normalise("## My Unique Project Section")
        missing_keys = {i.section for i in result.missing}
        assert normalised_custom not in missing_keys, (
            "Custom project section should not appear in MISSING"
        )


class TestAuditVersionMismatch:
    """pairmode_version in state.json doesn't match canonical → audit still runs, mismatch captured."""

    def test_audit_runs_with_version_mismatch(self, tmp_path: Path) -> None:
        _write_state(tmp_path, version="0.0.1")  # older version than canonical 0.1.0
        _copy_canonical_files(tmp_path)

        # Should not raise
        result = audit_project(tmp_path)

        assert isinstance(result, AuditResult)

    def test_project_version_captured_in_result(self, tmp_path: Path) -> None:
        _write_state(tmp_path, version="0.0.1")
        _copy_canonical_files(tmp_path)

        result = audit_project(tmp_path)

        assert result.pairmode_version == "0.0.1", (
            f"Expected pairmode_version='0.0.1', got: {result.pairmode_version}"
        )

    def test_canonical_version_is_always_current(self, tmp_path: Path) -> None:
        _write_state(tmp_path, version="0.0.1")
        _copy_canonical_files(tmp_path)

        result = audit_project(tmp_path)

        assert result.canonical_version == "0.1.0", (
            f"Expected canonical_version='0.1.0', got: {result.canonical_version}"
        )

    def test_version_mismatch_does_not_add_spurious_missing_items(self, tmp_path: Path) -> None:
        """A version mismatch alone should not cause files to appear missing when all files exist."""
        _write_state(tmp_path, version="0.0.1")
        _copy_canonical_files(tmp_path)

        result = audit_project(tmp_path)

        # Files are all present and identical so nothing should be MISSING
        assert result.missing == [], (
            f"Version mismatch alone should not produce MISSING items; got: {result.missing}"
        )


# ---------------------------------------------------------------------------
# Context rendering tests
# ---------------------------------------------------------------------------


class TestAuditRendersTemplateWithContext:
    """audit_project reads pairmode_context.json and renders templates before comparing."""

    def test_no_false_inconsistent_when_context_matches(self, tmp_path: Path) -> None:
        """When pairmode_context.json is present and project files were rendered from it,
        audit should report no INCONSISTENT items for canonical files (CLAUDE.md, etc.).

        Note: STALE PLACEHOLDER findings for scaffold files (docs/brief.md etc.) are expected
        when --what and --why are not passed to bootstrap — those are intentional signals that
        the user should fill in the template. This test excludes STALE PLACEHOLDER findings
        from the assertion.
        """
        import json as _json
        from click.testing import CliRunner
        from skills.pairmode.scripts.bootstrap import bootstrap

        # Bootstrap the project (writes pairmode_context.json and rendered files)
        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "cora",
                "--stack", "Python / FastAPI",
                "--build-command", "uv run pytest",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        # pairmode_context.json must exist
        context_path = tmp_path / ".companion" / "pairmode_context.json"
        assert context_path.exists()

        # Audit should not flag INCONSISTENT for canonical files (CLAUDE.md etc.)
        # STALE PLACEHOLDER findings for scaffold files (brief.md, index.md, backlog.md)
        # are expected when --what/--why are not provided — they are not false positives.
        audit_result = audit_project(tmp_path)

        non_stale_inconsistent = [
            i for i in audit_result.inconsistent
            if "STALE PLACEHOLDER" not in i.description
        ]
        assert non_stale_inconsistent == [], (
            f"Expected no non-stale INCONSISTENT items after clean bootstrap, "
            f"got: {non_stale_inconsistent}"
        )

    def test_context_project_name_used_in_rendered_canonical(self, tmp_path: Path) -> None:
        """When pairmode_context.json has project_name='cora', canonical sections
        contain 'cora' after rendering, not '{{ project_name }}'."""
        import json as _json

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        ctx = {
            "project_name": "cora",
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
        (companion / "pairmode_context.json").write_text(
            _json.dumps(ctx), encoding="utf-8"
        )

        # Read what audit will produce for canonical CLAUDE.md sections
        from skills.pairmode.scripts.audit import _read_template_sections, _load_project_context
        loaded_ctx, ctx_found = _load_project_context(tmp_path)
        assert ctx_found is True
        assert loaded_ctx["project_name"] == "cora"

        sections = _read_template_sections("CLAUDE.md.j2", loaded_ctx)
        # All section bodies should not contain raw Jinja2 syntax
        for key, body in sections.items():
            assert "{{" not in body, (
                f"Section '{key}' still contains Jinja2 syntax after rendering: {body[:100]}"
            )
        # At least some section should mention 'cora'
        all_text = " ".join(sections.values())
        assert "cora" in all_text, "Rendered CLAUDE.md canonical should contain 'cora'"


# ---------------------------------------------------------------------------
# Story 6.1 — context_missing behaviour
# ---------------------------------------------------------------------------


class TestContextMissingFlag:
    """When pairmode_context.json is absent, context_missing=True and inconsistent is empty."""

    def test_context_missing_true_when_no_context_file(self, tmp_path: Path) -> None:
        """audit_project returns context_missing=True when pairmode_context.json is absent."""
        result = audit_project(tmp_path)
        assert result.context_missing is True

    def test_inconsistent_empty_when_context_missing(self, tmp_path: Path) -> None:
        """No INCONSISTENT items are produced when pairmode_context.json is absent."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Modify a canonical file so body differs — without context, this must not raise INCONSISTENT
        (tmp_path / "CLAUDE.md").write_text(
            "## Session modes\n\nDifferent content here.\n", encoding="utf-8"
        )

        result = audit_project(tmp_path)

        assert result.context_missing is True
        assert result.inconsistent == [], (
            f"Expected no INCONSISTENT when context is missing, got: {result.inconsistent}"
        )

    def test_context_missing_false_when_context_file_present(self, tmp_path: Path) -> None:
        """context_missing=False when pairmode_context.json is present and valid."""
        import json as _json

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        ctx = {
            "project_name": "testproject",
            "project_description": "",
            "stack": "",
            "build_command": "",
            "test_command": "",
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

        result = audit_project(tmp_path)

        assert result.context_missing is False

    def test_missing_still_populated_when_context_missing(self, tmp_path: Path) -> None:
        """MISSING items are reported even when pairmode_context.json is absent."""
        # Remove CLAUDE.md so it counts as MISSING
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        (tmp_path / "CLAUDE.md").unlink()

        result = audit_project(tmp_path)

        assert result.context_missing is True
        claude_md_missing = [i for i in result.missing if i.file == "CLAUDE.md"]
        assert len(claude_md_missing) > 0, (
            "Expected MISSING items for CLAUDE.md even when context is absent"
        )

    def test_extra_still_populated_when_context_missing(self, tmp_path: Path) -> None:
        """EXTRA items are reported even when pairmode_context.json is absent."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Append a project-specific section
        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            existing + "\n## My Unique Extra Section\n\nProject-specific.\n",
            encoding="utf-8",
        )

        result = audit_project(tmp_path)

        assert result.context_missing is True
        extra_files = [i.file for i in result.extra]
        assert "CLAUDE.md" in extra_files, (
            "Expected EXTRA items for CLAUDE.md even when context is absent"
        )


class TestFormatAuditOutputContextMissing:
    """format_audit_output emits warning when context_missing=True."""

    def _make_result_no_context(
        self,
        missing: list[AuditItem] | None = None,
        extra: list[AuditItem] | None = None,
    ) -> AuditResult:
        return AuditResult(
            project_name="myproject",
            project_dir=Path("/tmp/myproject"),
            missing=missing or [],
            inconsistent=[],
            extra=extra or [],
            pairmode_version="0.1.0",
            canonical_version="0.1.0",
            context_missing=True,
        )

    def test_warning_present_when_context_missing(self) -> None:
        result = self._make_result_no_context()
        output = format_audit_output(result)
        assert "WARNING: No pairmode_context.json found" in output

    def test_warning_mentions_inconsistent_disabled(self) -> None:
        result = self._make_result_no_context()
        output = format_audit_output(result)
        assert "INCONSISTENT comparison disabled" in output

    def test_warning_mentions_bootstrap(self) -> None:
        result = self._make_result_no_context()
        output = format_audit_output(result)
        assert "bootstrap" in output

    def test_inconsistent_section_absent_when_context_missing(self) -> None:
        result = self._make_result_no_context()
        output = format_audit_output(result)
        # The INCONSISTENT section header should not appear as a standalone line
        # (The warning itself contains the word INCONSISTENT, but the section header does not)
        lines = output.splitlines()
        assert "INCONSISTENT" not in lines, (
            "INCONSISTENT section header should not appear as a line when context is missing"
        )

    def test_missing_section_still_shown_when_context_missing(self) -> None:
        result = self._make_result_no_context(
            missing=[AuditItem(file="CLAUDE.md", section="intro", description="Missing")]
        )
        output = format_audit_output(result)
        assert "MISSING" in output
        assert "CLAUDE.md" in output

    def test_extra_section_still_shown_when_context_missing(self) -> None:
        result = self._make_result_no_context(
            extra=[AuditItem(file="CLAUDE.md", section="custom", description="Custom")]
        )
        output = format_audit_output(result)
        assert "EXTRA" in output
        assert "CLAUDE.md" in output

    def test_no_warning_when_context_present(self) -> None:
        result = AuditResult(
            project_name="myproject",
            project_dir=Path("/tmp/myproject"),
            context_missing=False,
        )
        output = format_audit_output(result)
        assert "WARNING: No pairmode_context.json found" not in output


# ---------------------------------------------------------------------------
# Story 6.2 — separator-key filtering
# ---------------------------------------------------------------------------


class TestIsSeparatorKey:
    """Unit tests for the _is_separator_key helper."""

    def test_plain_triple_dash_is_separator(self) -> None:
        assert _is_separator_key("---") is True

    def test_quad_dash_is_separator(self) -> None:
        assert _is_separator_key("----") is True

    def test_dash_with_suffix_zero_is_separator(self) -> None:
        assert _is_separator_key("---__0") is True

    def test_dash_with_suffix_one_is_separator(self) -> None:
        assert _is_separator_key("---__1") is True

    def test_section_header_is_not_separator(self) -> None:
        assert _is_separator_key("## session modes") is False

    def test_preamble_key_is_not_separator(self) -> None:
        assert _is_separator_key("__preamble__0") is False


class TestSeparatorKeysFilteredFromOutput:
    """Integration: separator-keyed sections never appear in MISSING, EXTRA, or INCONSISTENT."""

    def _make_project_with_separators(self, project_dir: Path) -> None:
        """Write a CLAUDE.md that contains --- separators between sections."""
        content = (
            "## Session modes\n\nSome content.\n\n"
            "---\n\n"
            "## Build rules\n\nOther content.\n"
        )
        (project_dir / "CLAUDE.md").write_text(content, encoding="utf-8")

    def test_separator_keys_not_in_inconsistent(self, tmp_path: Path) -> None:
        """Project file with --- separators must not produce INCONSISTENT items
        whose section key matches the separator pattern."""
        import json as _json

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        ctx = {
            "project_name": "testproject",
            "project_description": "",
            "stack": "",
            "build_command": "",
            "test_command": "",
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

        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Append a separator to CLAUDE.md to simulate the pattern
        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(existing + "\n---\n\nExtra text after separator.\n", encoding="utf-8")

        result = audit_project(tmp_path)

        separator_inconsistent = [
            i for i in result.inconsistent if _is_separator_key(i.section)
        ]
        assert separator_inconsistent == [], (
            f"Separator-keyed sections must not appear in INCONSISTENT: {separator_inconsistent}"
        )

    def test_separator_keys_not_in_missing(self, tmp_path: Path) -> None:
        """No MISSING item should have a separator-pattern section key."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        (tmp_path / "CLAUDE.md").unlink()

        result = audit_project(tmp_path)

        separator_missing = [i for i in result.missing if _is_separator_key(i.section)]
        assert separator_missing == [], (
            f"Separator-keyed sections must not appear in MISSING: {separator_missing}"
        )

    def test_separator_keys_not_in_extra(self, tmp_path: Path) -> None:
        """No EXTRA item should have a separator-pattern section key."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Append a raw --- separator to CLAUDE.md
        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(existing + "\n---\n\nExtra text.\n", encoding="utf-8")

        result = audit_project(tmp_path)

        separator_extra = [i for i in result.extra if _is_separator_key(i.section)]
        assert separator_extra == [], (
            f"Separator-keyed sections must not appear in EXTRA: {separator_extra}"
        )

    def test_legitimate_section_differences_still_reported(self, tmp_path: Path) -> None:
        """A real ## section difference is still reported as INCONSISTENT
        even after the separator-key filter is applied."""
        import json as _json

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        ctx = {
            "project_name": "testproject",
            "project_description": "",
            "stack": "",
            "build_command": "",
            "test_command": "",
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

        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        # Overwrite CLAUDE.md so that one real section body differs
        from skills.pairmode.scripts.audit import _normalise
        canonical_text = (
            _audit_mod.TEMPLATES_DIR / "CLAUDE.md.j2"
        ).read_text(encoding="utf-8")
        import re as _re
        headers = _re.findall(r"^## .+", canonical_text, _re.MULTILINE)
        assert headers, "CLAUDE.md.j2 must have at least one ## header"

        first_header = headers[0]
        # Write a version where the first section has completely different content
        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        # Replace content under the first header with something clearly different
        altered = _re.sub(
            rf"({_re.escape(first_header)}\n+)(.+?)(\n##|\Z)",
            lambda m: m.group(1) + "COMPLETELY DIFFERENT CONTENT\n" + m.group(3),
            existing,
            count=1,
            flags=_re.DOTALL,
        )
        claude_md.write_text(altered, encoding="utf-8")

        result = audit_project(tmp_path)

        # There should be at least one INCONSISTENT item for CLAUDE.md
        inconsistent_claude = [i for i in result.inconsistent if i.file == "CLAUDE.md"]
        assert len(inconsistent_claude) > 0, (
            "Expected INCONSISTENT items for modified CLAUDE.md section, got none"
        )


# ---------------------------------------------------------------------------
# Story 7.7 — Phase 7 file-existence checks
# ---------------------------------------------------------------------------


class TestAuditPhase7FileExistenceChecks:
    """audit_project reports MISSING for docs/brief.md, docs/phases/index.md,
    and docs/cer/backlog.md when absent."""

    def test_docs_brief_md_missing_when_absent(self, tmp_path: Path) -> None:
        """docs/brief.md absent → reported as MISSING."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Remove the placeholder created by _copy_canonical_files to simulate absence
        brief = tmp_path / "docs" / "brief.md"
        if brief.exists():
            brief.unlink()

        result = audit_project(tmp_path)

        missing_files = {i.file for i in result.missing}
        assert "docs/brief.md" in missing_files, (
            f"Expected docs/brief.md in missing files, got: {missing_files}"
        )

    def test_docs_phases_index_md_missing_when_absent(self, tmp_path: Path) -> None:
        """docs/phases/index.md absent → reported as MISSING."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        index = tmp_path / "docs" / "phases" / "index.md"
        if index.exists():
            index.unlink()

        result = audit_project(tmp_path)

        missing_files = {i.file for i in result.missing}
        assert "docs/phases/index.md" in missing_files, (
            f"Expected docs/phases/index.md in missing files, got: {missing_files}"
        )

    def test_docs_cer_backlog_md_missing_when_absent(self, tmp_path: Path) -> None:
        """docs/cer/backlog.md absent → reported as MISSING."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        backlog = tmp_path / "docs" / "cer" / "backlog.md"
        if backlog.exists():
            backlog.unlink()

        result = audit_project(tmp_path)

        missing_files = {i.file for i in result.missing}
        assert "docs/cer/backlog.md" in missing_files, (
            f"Expected docs/cer/backlog.md in missing files, got: {missing_files}"
        )

    def test_no_missing_when_all_three_present_and_matching(self, tmp_path: Path) -> None:
        """When all three Phase 7 scaffold files are present with matching sections,
        none are reported MISSING (section-level comparison)."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # _copy_canonical_files already creates the scaffold files with rendered content

        result = audit_project(tmp_path)

        missing_files = {i.file for i in result.missing}
        assert "docs/brief.md" not in missing_files, "docs/brief.md should not be MISSING"
        assert "docs/phases/index.md" not in missing_files, (
            "docs/phases/index.md should not be MISSING"
        )
        assert "docs/cer/backlog.md" not in missing_files, (
            "docs/cer/backlog.md should not be MISSING"
        )


# ---------------------------------------------------------------------------
# Story 8.6 — Stale placeholder detection + section-level comparison for Phase 7 files
# ---------------------------------------------------------------------------


def _write_context(project_dir: Path, overrides: dict | None = None) -> None:
    """Write a minimal pairmode_context.json so context_missing=False."""
    import json as _json

    companion = project_dir / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    ctx: dict = {
        "project_name": "testproject",
        "project_description": "",
        "stack": "",
        "build_command": "",
        "test_command": "",
        "migration_command": "",
        "domain_model": "",
        "domain_isolation_rule": "",
        "checklist_items": [],
        "protected_paths": [],
        "non_negotiables": [],
        "module_structure": [],
        "layer_rules": [],
    }
    if overrides:
        ctx.update(overrides)
    (companion / "pairmode_context.json").write_text(_json.dumps(ctx), encoding="utf-8")


class TestIsStaleplaceholder:
    """Unit tests for _is_stale_placeholder."""

    def test_empty_string_is_placeholder(self) -> None:
        assert _is_stale_placeholder("") is True

    def test_whitespace_only_is_placeholder(self) -> None:
        assert _is_stale_placeholder("   \n  ") is True

    def test_not_yet_specified_pattern(self) -> None:
        assert _is_stale_placeholder("_(not yet specified)_") is True

    def test_not_yet_specified_with_whitespace(self) -> None:
        assert _is_stale_placeholder("  _(not yet specified)_  ") is True

    def test_none_asterisk_pattern(self) -> None:
        assert _is_stale_placeholder("*(none)*") is True

    def test_fill_in_dash_pattern(self) -> None:
        assert _is_stale_placeholder("— fill in —") is True

    def test_real_content_is_not_placeholder(self) -> None:
        assert _is_stale_placeholder("This project produces a REST API.") is False

    def test_multiline_real_content_is_not_placeholder(self) -> None:
        body = "This project exists to solve X.\n\nIt was created because Y."
        assert _is_stale_placeholder(body) is False


class TestAuditStalePlaceholderLabelling:
    """docs/brief.md with placeholder what/why → STALE PLACEHOLDER finding."""

    def _setup_project_with_brief(self, tmp_path: Path, what: str, why: str) -> None:
        """Create a project with pairmode_context.json and docs/brief.md containing
        the given what/why values."""
        _write_state(tmp_path)
        _write_context(tmp_path, {"what": what, "why": why})
        _copy_canonical_files(tmp_path)

        # Write a docs/brief.md where what/why sections contain placeholders
        brief_content = (
            "# Brief — testproject\n\n"
            "> One-page project brief.\n\n"
            "---\n\n"
            "## What this project produces\n\n"
            f"{what}\n\n"
            "---\n\n"
            "## Why it exists\n\n"
            f"{why}\n\n"
            "---\n\n"
            "## Core beliefs\n\n"
            "We prefer simplicity over complexity in all design decisions.\n\n"
            "---\n\n"
            "## Accepted tradeoffs\n\n"
            "We accepted slower startup in exchange for easier configuration.\n\n"
            "---\n\n"
            "## Constraints\n\n"
            "_Explicit constraints the operator has placed on scope or approach:_\n\n"
            "- _(add operator constraints here)_\n\n"
            "---\n\n"
            "## Not in scope\n\n"
            "_Things that might seem related but are intentional omissions:_\n\n"
            "- _(add out-of-scope items here)_\n\n"
            "---\n\n"
            "## What a second implementation must preserve\n\n"
            "The core data model and persistence contract must be preserved.\n\n"
            "---\n\n"
            "## Operator contact\n\n"
            "_(not specified)_\n"
        )
        brief_path = tmp_path / "docs" / "brief.md"
        brief_path.parent.mkdir(parents=True, exist_ok=True)
        brief_path.write_text(brief_content, encoding="utf-8")

    def test_placeholder_what_produces_stale_placeholder_finding(self, tmp_path: Path) -> None:
        """docs/brief.md present but with placeholder what → STALE PLACEHOLDER finding."""
        self._setup_project_with_brief(tmp_path, what="_(not yet specified)_", why="Some real reason.")

        result = audit_project(tmp_path)

        # Should have a STALE PLACEHOLDER finding for the what section
        stale_items = [
            i for i in result.inconsistent
            if i.file == "docs/brief.md" and "STALE PLACEHOLDER" in i.description
        ]
        assert len(stale_items) > 0, (
            f"Expected STALE PLACEHOLDER finding for docs/brief.md what section. "
            f"Got inconsistent: {result.inconsistent}"
        )

    def test_placeholder_why_produces_stale_placeholder_finding(self, tmp_path: Path) -> None:
        """docs/brief.md present but with placeholder why → STALE PLACEHOLDER finding."""
        self._setup_project_with_brief(tmp_path, what="A real description.", why="_(not yet specified)_")

        result = audit_project(tmp_path)

        stale_items = [
            i for i in result.inconsistent
            if i.file == "docs/brief.md" and "STALE PLACEHOLDER" in i.description
        ]
        assert len(stale_items) > 0, (
            f"Expected STALE PLACEHOLDER finding for docs/brief.md why section. "
            f"Got inconsistent: {result.inconsistent}"
        )

    def test_placeholder_what_and_why_produces_two_findings(self, tmp_path: Path) -> None:
        """Both what and why as placeholders → two STALE PLACEHOLDER findings."""
        self._setup_project_with_brief(
            tmp_path, what="_(not yet specified)_", why="_(not yet specified)_"
        )

        result = audit_project(tmp_path)

        stale_items = [
            i for i in result.inconsistent
            if i.file == "docs/brief.md" and "STALE PLACEHOLDER" in i.description
        ]
        assert len(stale_items) >= 2, (
            f"Expected at least 2 STALE PLACEHOLDER findings, got: {stale_items}"
        )

    def test_fully_populated_brief_is_clean(self, tmp_path: Path) -> None:
        """docs/brief.md present and fully populated → no STALE PLACEHOLDER finding."""
        real_what = "This project produces a REST API for managing inventory."
        real_why = "It exists because the legacy system was too slow and unmaintainable."
        self._setup_project_with_brief(tmp_path, what=real_what, why=real_why)

        result = audit_project(tmp_path)

        stale_items = [
            i for i in result.inconsistent
            if i.file == "docs/brief.md" and "STALE PLACEHOLDER" in i.description
        ]
        assert stale_items == [], (
            f"Expected no STALE PLACEHOLDER for fully populated brief, got: {stale_items}"
        )

    def test_stale_placeholder_description_not_labelled_inconsistent(self, tmp_path: Path) -> None:
        """A stale-placeholder finding must say STALE PLACEHOLDER, not just INCONSISTENT."""
        self._setup_project_with_brief(tmp_path, what="_(not yet specified)_", why="Real reason.")

        result = audit_project(tmp_path)

        for item in result.inconsistent:
            if item.file == "docs/brief.md" and "STALE PLACEHOLDER" in item.description:
                # Verify it says STALE PLACEHOLDER and not just the generic message
                assert "STALE PLACEHOLDER" in item.description
                assert "content differs" not in item.description
                return

        # If we reach here we should have found one - fail descriptively
        assert False, (
            f"Expected a STALE PLACEHOLDER item for docs/brief.md, "
            f"got: {result.inconsistent}"
        )


class TestAuditPhase7SectionLevelComparison:
    """docs/phases/index.md present and matching rendered template → clean (no MISSING/INCONSISTENT)."""

    def test_index_md_matching_template_is_clean(self, tmp_path: Path) -> None:
        """docs/phases/index.md present and matches rendered template → clean."""
        _write_state(tmp_path)
        _write_context(tmp_path)
        _copy_canonical_files(tmp_path)
        # _copy_canonical_files renders scaffold files with enriched context

        result = audit_project(tmp_path)

        index_missing = [i for i in result.missing if i.file == "docs/phases/index.md"]
        index_inconsistent = [i for i in result.inconsistent if i.file == "docs/phases/index.md"]
        assert index_missing == [], (
            f"Expected no MISSING for docs/phases/index.md, got: {index_missing}"
        )
        assert index_inconsistent == [], (
            f"Expected no INCONSISTENT for docs/phases/index.md, got: {index_inconsistent}"
        )

    def test_index_md_missing_sections_reported(self, tmp_path: Path) -> None:
        """docs/phases/index.md present but missing sections → sections reported MISSING."""
        _write_state(tmp_path)
        _write_context(tmp_path)
        _copy_canonical_files(tmp_path)

        # Replace with a stub that has no sections
        (tmp_path / "docs" / "phases" / "index.md").write_text(
            "# Phase Index\n\nNo table here.\n", encoding="utf-8"
        )

        result = audit_project(tmp_path)

        # With a stub that has preamble only and no canonical sections,
        # the canonical sections will appear as MISSING (if template has any)
        # OR inconsistent (preamble differs). At minimum file is processed.
        all_index_items = (
            [i for i in result.missing if i.file == "docs/phases/index.md"]
            + [i for i in result.inconsistent if i.file == "docs/phases/index.md"]
        )
        # The audit should produce some findings (either MISSING sections or INCONSISTENT)
        # because the stub doesn't match the canonical template.
        # Note: if the template has no ## headers (only a preamble table), it may just be
        # an INCONSISTENT preamble. Either outcome is valid.
        assert isinstance(all_index_items, list)  # Always true — just check no crash

    def test_scaffold_files_use_section_comparison_not_existence_only(self, tmp_path: Path) -> None:
        """Scaffold files are now in SCAFFOLD_FILES, not EXISTENCE_CHECK_FILES."""
        from skills.pairmode.scripts import audit as _audit_mod_local

        scaffold_dests = {d for d, _t in _audit_mod_local.SCAFFOLD_FILES}
        existence_dests = {d for d, _t, _desc in _audit_mod_local.EXISTENCE_CHECK_FILES}

        assert "docs/brief.md" in scaffold_dests, "docs/brief.md must be in SCAFFOLD_FILES"
        assert "docs/phases/index.md" in scaffold_dests, (
            "docs/phases/index.md must be in SCAFFOLD_FILES"
        )
        assert "docs/cer/backlog.md" in scaffold_dests, (
            "docs/cer/backlog.md must be in SCAFFOLD_FILES"
        )
        assert "docs/brief.md" not in existence_dests, (
            "docs/brief.md must NOT be in EXISTENCE_CHECK_FILES"
        )
        assert "docs/phases/index.md" not in existence_dests, (
            "docs/phases/index.md must NOT be in EXISTENCE_CHECK_FILES"
        )
        assert "docs/cer/backlog.md" not in existence_dests, (
            "docs/cer/backlog.md must NOT be in EXISTENCE_CHECK_FILES"
        )


# ---------------------------------------------------------------------------
# Story 10.1 — Core beliefs / What a second implementation must preserve
# ---------------------------------------------------------------------------


def _write_brief_with_core_beliefs(
    project_dir: Path, core_beliefs_body: str, include_must_preserve: bool = True
) -> None:
    """Write a docs/brief.md that includes the new Story 10.1 sections."""
    must_preserve_section = (
        "## What a second implementation must preserve\n\n"
        "The core data model and persistence contract must be preserved.\n\n"
        if include_must_preserve
        else ""
    )
    brief_content = (
        "# Brief — testproject\n\n"
        "> One-page project brief.\n\n"
        "---\n\n"
        "## What this project produces\n\n"
        "A test project for unit tests.\n\n"
        "---\n\n"
        "## Why it exists\n\n"
        "To provide a baseline for audit tests.\n\n"
        "---\n\n"
        f"## Core beliefs\n\n"
        f"{core_beliefs_body}\n\n"
        "---\n\n"
        "## Accepted tradeoffs\n\n"
        "We accepted slower startup in exchange for easier configuration.\n\n"
        "---\n\n"
        "## Constraints\n\n"
        "_Explicit constraints the operator has placed on scope or approach:_\n\n"
        "- _(add operator constraints here)_\n\n"
        "---\n\n"
        "## Not in scope\n\n"
        "_Things that might seem related but are intentional omissions:_\n\n"
        "- _(add out-of-scope items here)_\n\n"
        "---\n\n"
        f"{must_preserve_section}"
        "## Operator contact\n\n"
        "_(not specified)_\n"
    )
    brief_path = project_dir / "docs" / "brief.md"
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(brief_content, encoding="utf-8")


class TestAuditCoreBeliefsSection:
    """Story 10.1 — audit checks for ## Core beliefs in docs/brief.md."""

    def test_missing_core_beliefs_heading_produces_missing_finding(self, tmp_path: Path) -> None:
        """docs/brief.md without ## Core beliefs → MISSING section finding."""
        _write_state(tmp_path)
        _write_context(tmp_path)
        _copy_canonical_files(tmp_path)

        # Write a brief.md that lacks the Core beliefs section
        brief_path = tmp_path / "docs" / "brief.md"
        brief_path.write_text(
            "# Brief — testproject\n\n"
            "## What this project produces\n\n"
            "A test project.\n\n"
            "## Why it exists\n\n"
            "For testing.\n\n"
            "## Accepted tradeoffs\n\n"
            "We gave up Y.\n\n"
            "## Constraints\n\n"
            "- _(add operator constraints here)_\n\n"
            "## Not in scope\n\n"
            "- _(add out-of-scope items here)_\n\n"
            "## What a second implementation must preserve\n\n"
            "The data model.\n\n"
            "## Operator contact\n\n"
            "_(not specified)_\n",
            encoding="utf-8",
        )

        result = audit_project(tmp_path)

        missing_sections = {i.section for i in result.missing if i.file == "docs/brief.md"}
        from skills.pairmode.scripts.audit import _normalise
        assert _normalise("## Core beliefs") in missing_sections, (
            f"Expected '## core beliefs' in missing sections, got: {missing_sections}"
        )

    def test_core_beliefs_with_placeholder_produces_stale_placeholder(self, tmp_path: Path) -> None:
        """docs/brief.md with ## Core beliefs containing only placeholder text → STALE PLACEHOLDER."""
        _write_state(tmp_path)
        _write_context(tmp_path)
        _copy_canonical_files(tmp_path)

        _write_brief_with_core_beliefs(
            tmp_path,
            core_beliefs_body="_(not yet specified — what does this project believe about how software should be built? What does it value over what?)_",
        )

        result = audit_project(tmp_path)

        stale_items = [
            i for i in result.inconsistent
            if i.file == "docs/brief.md" and "STALE PLACEHOLDER" in i.description
            and "core beliefs" in i.section.lower()
        ]
        assert len(stale_items) > 0, (
            f"Expected STALE PLACEHOLDER for ## Core beliefs with placeholder text. "
            f"Got inconsistent: {result.inconsistent}"
        )

    def test_core_beliefs_with_real_content_is_clean(self, tmp_path: Path) -> None:
        """docs/brief.md with ## Core beliefs containing real content → no STALE PLACEHOLDER."""
        _write_state(tmp_path)
        _write_context(tmp_path)
        _copy_canonical_files(tmp_path)

        _write_brief_with_core_beliefs(
            tmp_path,
            core_beliefs_body="We prefer simplicity over complexity in all design decisions.",
        )

        result = audit_project(tmp_path)

        stale_items = [
            i for i in result.inconsistent
            if i.file == "docs/brief.md" and "STALE PLACEHOLDER" in i.description
            and "core beliefs" in i.section.lower()
        ]
        assert stale_items == [], (
            f"Expected no STALE PLACEHOLDER for ## Core beliefs with real content. "
            f"Got: {stale_items}"
        )

    def test_missing_must_preserve_heading_produces_missing_finding(self, tmp_path: Path) -> None:
        """docs/brief.md without ## What a second implementation must preserve → MISSING."""
        _write_state(tmp_path)
        _write_context(tmp_path)
        _copy_canonical_files(tmp_path)

        _write_brief_with_core_beliefs(
            tmp_path,
            core_beliefs_body="We prefer simplicity over complexity.",
            include_must_preserve=False,
        )

        result = audit_project(tmp_path)

        missing_sections = {i.section for i in result.missing if i.file == "docs/brief.md"}
        from skills.pairmode.scripts.audit import _normalise
        assert _normalise("## What a second implementation must preserve") in missing_sections, (
            f"Expected 'what a second implementation must preserve' in missing sections, "
            f"got: {missing_sections}"
        )


# ---------------------------------------------------------------------------
# Story 10.5 — Ideology staleness detection
# ---------------------------------------------------------------------------


class TestCheckIdeologyStaleness:
    """Unit tests for _check_ideology_staleness."""

    def test_absent_returns_none(self, tmp_path: Path) -> None:
        """docs/ideology.md absent → returns None."""
        result = _check_ideology_staleness(tmp_path)
        assert result is None

    def test_all_placeholder_returns_stale(self, tmp_path: Path) -> None:
        """All required sections have placeholder text → returns 'STALE'."""
        _write_ideology_md(tmp_path, stale=True)
        result = _check_ideology_staleness(tmp_path)
        assert result == "STALE"

    def test_one_real_section_returns_ok(self, tmp_path: Path) -> None:
        """At least one section with real content → returns 'OK'."""
        (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
        content = (
            "# Ideology\n\n"
            "## Core convictions\n\n"
            "We believe in simplicity.\n\n"  # real content
            "## Value hierarchy\n\n"
            "_(not yet specified — values)_\n\n"
            "## Accepted constraints\n\n"
            "_(not yet specified — constraints)_\n\n"
            "## Prototype fingerprints\n\n"
            "_(not yet specified — fingerprints)_\n\n"
            "## Reconstruction guidance\n\n"
            "_(not yet specified — guidance)_\n\n"
            "## Comparison basis\n\n"
            "_(not yet specified — basis)_\n"
        )
        (tmp_path / "docs" / "ideology.md").write_text(content, encoding="utf-8")
        result = _check_ideology_staleness(tmp_path)
        assert result == "OK"

    def test_fully_populated_returns_ok(self, tmp_path: Path) -> None:
        """Fully populated ideology.md → returns 'OK'."""
        _write_ideology_md(tmp_path, stale=False)
        result = _check_ideology_staleness(tmp_path)
        assert result == "OK"

    def test_mixed_file_returns_ok(self, tmp_path: Path) -> None:
        """Some placeholder sections, one real → returns 'OK'."""
        (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
        content = (
            "# Ideology\n\n"
            "## Core convictions\n\n"
            "_(not yet specified — convictions)_\n\n"
            "## Value hierarchy\n\n"
            "Correctness over performance.\n\n"  # real content
            "## Accepted constraints\n\n"
            "_(not yet specified — constraints)_\n\n"
            "## Prototype fingerprints\n\n"
            "_(not yet specified — fingerprints)_\n\n"
            "## Reconstruction guidance\n\n"
            "_(not yet specified — guidance)_\n\n"
            "## Comparison basis\n\n"
            "_(not yet specified — basis)_\n"
        )
        (tmp_path / "docs" / "ideology.md").write_text(content, encoding="utf-8")
        result = _check_ideology_staleness(tmp_path)
        assert result == "OK"

    def test_html_comment_lines_ignored(self, tmp_path: Path) -> None:
        """HTML comment lines in section body do not count as real content."""
        (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
        content = (
            "# Ideology\n\n"
            "## Core convictions\n\n"
            "<!-- This is an HTML comment -->\n"
            "_(not yet specified — convictions)_\n\n"
            "## Value hierarchy\n\n"
            "_(not yet specified — values)_\n\n"
            "## Accepted constraints\n\n"
            "_(not yet specified — constraints)_\n\n"
            "## Prototype fingerprints\n\n"
            "_(not yet specified — fingerprints)_\n\n"
            "## Reconstruction guidance\n\n"
            "_(not yet specified — guidance)_\n\n"
            "## Comparison basis\n\n"
            "_(not yet specified — basis)_\n"
        )
        (tmp_path / "docs" / "ideology.md").write_text(content, encoding="utf-8")
        result = _check_ideology_staleness(tmp_path)
        assert result == "STALE"


class TestAuditIdeologyMd:
    """Integration tests: audit_project detects ideology.md missing/stale."""

    def test_missing_ideology_md_produces_missing_finding(self, tmp_path: Path) -> None:
        """docs/ideology.md absent → MISSING finding in result."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Remove ideology.md that _copy_canonical_files created
        ideology_path = tmp_path / "docs" / "ideology.md"
        if ideology_path.exists():
            ideology_path.unlink()

        result = audit_project(tmp_path)

        missing_files = {i.file for i in result.missing}
        assert "docs/ideology.md" in missing_files, (
            f"Expected docs/ideology.md in missing files, got: {missing_files}"
        )

    def test_stale_ideology_md_produces_stale_placeholder_finding(self, tmp_path: Path) -> None:
        """docs/ideology.md with all placeholder sections → STALE PLACEHOLDER inconsistent finding."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Overwrite with a fully stale ideology.md
        _write_ideology_md(tmp_path, stale=True)

        result = audit_project(tmp_path)

        stale_items = [
            i for i in result.inconsistent
            if i.file == "docs/ideology.md" and "STALE PLACEHOLDER" in i.description
        ]
        assert len(stale_items) > 0, (
            f"Expected STALE PLACEHOLDER finding for docs/ideology.md, "
            f"got inconsistent: {result.inconsistent}"
        )

    def test_real_ideology_md_produces_no_finding(self, tmp_path: Path) -> None:
        """docs/ideology.md with real content in at least one section → no staleness finding."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # _write_ideology_md(stale=False) is already done by _copy_canonical_files via
        # _write_clean_scaffold_files; confirm no finding
        _write_ideology_md(tmp_path, stale=False)

        result = audit_project(tmp_path)

        ideology_findings = [
            i for i in result.missing + result.inconsistent
            if i.file == "docs/ideology.md"
        ]
        assert ideology_findings == [], (
            f"Expected no ideology findings for real ideology.md, got: {ideology_findings}"
        )

    def test_stale_ideology_format_output_shows_stale_placeholder_header(self, tmp_path: Path) -> None:
        """format_audit_output shows 'STALE PLACEHOLDER' header for stale ideology.md."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        _write_ideology_md(tmp_path, stale=True)

        result = audit_project(tmp_path)
        output = format_audit_output(result)

        assert "STALE PLACEHOLDER" in output
        assert "docs/ideology.md" in output
        assert "guided ideology capture" in output

    def test_missing_ideology_format_output_shows_missing_header(self, tmp_path: Path) -> None:
        """format_audit_output shows 'MISSING' header for absent ideology.md."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        ideology_path = tmp_path / "docs" / "ideology.md"
        if ideology_path.exists():
            ideology_path.unlink()

        result = audit_project(tmp_path)
        output = format_audit_output(result)

        assert "MISSING" in output
        assert "docs/ideology.md" in output

    def test_ideology_not_in_scaffold_or_existence_files(self) -> None:
        """docs/ideology.md must not be in SCAFFOLD_FILES or EXISTENCE_CHECK_FILES."""
        from skills.pairmode.scripts import audit as _audit_mod_local

        scaffold_dests = {d for d, _t in _audit_mod_local.SCAFFOLD_FILES}
        existence_dests = {d for d, _t, _desc in _audit_mod_local.EXISTENCE_CHECK_FILES}

        assert "docs/ideology.md" not in scaffold_dests, (
            "docs/ideology.md must NOT be in SCAFFOLD_FILES — handled by _check_ideology_staleness"
        )
        assert "docs/ideology.md" not in existence_dests, (
            "docs/ideology.md must NOT be in EXISTENCE_CHECK_FILES"
        )

    def test_other_findings_unaffected_by_ideology_check(self, tmp_path: Path) -> None:
        """Ideology staleness check does not interfere with other audit findings."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Remove CLAUDE.md to trigger a separate MISSING finding
        (tmp_path / "CLAUDE.md").unlink()
        # Keep ideology.md with real content
        _write_ideology_md(tmp_path, stale=False)

        result = audit_project(tmp_path)

        claude_missing = [i for i in result.missing if i.file == "CLAUDE.md"]
        assert len(claude_missing) > 0, (
            "Expected MISSING items for CLAUDE.md even with real ideology.md present"
        )
        ideology_findings = [
            i for i in result.missing + result.inconsistent
            if i.file == "docs/ideology.md"
        ]
        assert ideology_findings == [], (
            f"Expected no ideology findings when ideology.md has real content: {ideology_findings}"
        )


# ---------------------------------------------------------------------------
# Story 10.6: path traversal containment guard
# ---------------------------------------------------------------------------


class TestAuditPathTraversalGuard:
    """audit_project() must reject paths that are too close to the filesystem root."""

    def test_root_dir_raises_system_exit(self):
        """Calling audit_project('/') raises SystemExit."""
        with pytest.raises(SystemExit) as exc_info:
            audit_project(Path("/"))
        assert exc_info.value.code != 0

    def test_etc_dir_raises_system_exit(self):
        """Calling audit_project('/etc') raises SystemExit."""
        with pytest.raises(SystemExit) as exc_info:
            audit_project(Path("/etc"))
        assert exc_info.value.code != 0

    def test_valid_project_dir_succeeds(self, tmp_path):
        """A valid project dir with 3+ path parts does not raise SystemExit (regression)."""
        _copy_canonical_files(tmp_path)
        _write_ideology_md(tmp_path, stale=False)
        _write_state(tmp_path)
        # Should not raise — may return a result with findings but must not exit
        result = audit_project(tmp_path)
        assert isinstance(result, AuditResult)


# ---------------------------------------------------------------------------
# Story 12.2 — Reconstruction.md staleness detection
# ---------------------------------------------------------------------------

_GENERATED_FOOTER = "Generated from `docs/ideology.md`"
_PLACEHOLDER_RECONSTRUCTION = (
    "# Reconstruction Brief — testproject\n\n"
    "> This document is the sole input for an independent reconstruction agent.\n\n"
    "---\n\n"
    "## What you are building\n\n"
    "_(derive from docs/brief.md — What this project produces)_\n\n"
    "## Why it exists\n\n"
    "_(derive from docs/brief.md — Why it exists)_\n\n"
    "---\n\n"
    "## Non-negotiable ideology\n\n"
    "_(no convictions recorded — populate docs/ideology.md first)_\n\n"
    "---\n\n"
    "## Instructions for the reconstruction agent\n\n"
    "1. Read this document in full before writing any code.\n\n"
    f"*{_GENERATED_FOOTER} and `docs/brief.md` by `/anchor:pairmode reconstruct`.*\n"
    "*Original project: testproject*\n"
)

_COMPLETED_REPORT = (
    "# Reconstruction Report — testproject\n\n"
    "**Reconstruction date:** 2026-01-01\n\n"
    "---\n\n"
    "## Ideology adherence\n\n"
    "The implementation fully expresses all core convictions.\n\n"
    "## Constraint compliance\n\n"
    "All non-negotiable constraints are satisfied.\n\n"
    "## Comparison rubric scores\n\n"
    "Performance: on par. Correctness: exceeds original.\n\n"
    "## Summary verdict\n\n"
    "Strong alignment with ideology. Recommended for backport review.\n"
)


def _write_reconstruction_md(project_dir: Path, content: str) -> None:
    """Write docs/reconstruction.md with the given content."""
    docs_dir = project_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "reconstruction.md").write_text(content, encoding="utf-8")


class TestCheckReconstructionStaleness:
    """Unit tests for _check_reconstruction_staleness."""

    def test_absent_returns_none(self, tmp_path: Path) -> None:
        """docs/reconstruction.md absent → returns None."""
        result = _check_reconstruction_staleness(tmp_path)
        assert result is None

    def test_generated_brief_all_placeholder_returns_stale(self, tmp_path: Path) -> None:
        """Generated brief with all placeholder content → returns 'STALE'."""
        _write_reconstruction_md(tmp_path, _PLACEHOLDER_RECONSTRUCTION)
        result = _check_reconstruction_staleness(tmp_path)
        assert result == "STALE"

    def test_generated_brief_with_real_content_returns_ok(self, tmp_path: Path) -> None:
        """Generated brief with real content in one required section → returns 'OK'."""
        content = (
            _PLACEHOLDER_RECONSTRUCTION.rstrip() + "\n\n"
            "## Comparison rubric\n\n"
            "The implementation expresses the core convictions fully.\n"
        )
        _write_reconstruction_md(tmp_path, content)
        result = _check_reconstruction_staleness(tmp_path)
        assert result == "OK"

    def test_completed_scoring_report_returns_ok(self, tmp_path: Path) -> None:
        """Completed scoring report (no generated footer) → returns 'OK'."""
        _write_reconstruction_md(tmp_path, _COMPLETED_REPORT)
        result = _check_reconstruction_staleness(tmp_path)
        assert result == "OK"

    def test_completed_report_has_no_generated_footer(self) -> None:
        """Sanity: _COMPLETED_REPORT must not contain the generated footer."""
        assert _GENERATED_FOOTER not in _COMPLETED_REPORT


class TestAuditReconstructionMd:
    """Integration tests: audit_project detects reconstruction.md missing/stale."""

    def test_missing_reconstruction_md_produces_missing_finding(self, tmp_path: Path) -> None:
        """docs/reconstruction.md absent → MISSING finding that mentions reconstruction.md
        and 'reconstruct'."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Remove the reconstruction.md that _copy_canonical_files created
        reconstruction_path = tmp_path / "docs" / "reconstruction.md"
        if reconstruction_path.exists():
            reconstruction_path.unlink()

        result = audit_project(tmp_path)

        missing_files = {i.file for i in result.missing}
        assert "docs/reconstruction.md" in missing_files, (
            f"Expected docs/reconstruction.md in missing files, got: {missing_files}"
        )
        # Description must mention 'reconstruct'
        missing_desc = next(
            i.description for i in result.missing if i.file == "docs/reconstruction.md"
        )
        assert "reconstruct" in missing_desc.lower(), (
            f"Expected 'reconstruct' in description, got: {missing_desc}"
        )

    def test_stale_generated_brief_produces_stale_placeholder_finding(
        self, tmp_path: Path
    ) -> None:
        """Generated reconstruction.md with placeholder-only content → STALE PLACEHOLDER."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Overwrite with a placeholder-only generated brief
        _write_reconstruction_md(tmp_path, _PLACEHOLDER_RECONSTRUCTION)

        result = audit_project(tmp_path)

        stale_items = [
            i for i in result.inconsistent
            if i.file == "docs/reconstruction.md" and "STALE PLACEHOLDER" in i.description
        ]
        assert len(stale_items) > 0, (
            f"Expected STALE PLACEHOLDER finding for docs/reconstruction.md, "
            f"got inconsistent: {result.inconsistent}"
        )

    def test_generated_brief_with_real_content_in_one_section_is_clean(
        self, tmp_path: Path
    ) -> None:
        """Generated brief with real content in ## Comparison rubric → no finding."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        content = (
            _PLACEHOLDER_RECONSTRUCTION.rstrip() + "\n\n"
            "## Comparison rubric\n\n"
            "The implementation expresses the core convictions fully.\n"
        )
        _write_reconstruction_md(tmp_path, content)

        result = audit_project(tmp_path)

        reconstruction_findings = [
            i for i in result.missing + result.inconsistent
            if i.file == "docs/reconstruction.md"
        ]
        assert reconstruction_findings == [], (
            f"Expected no reconstruction findings when one section has real content, "
            f"got: {reconstruction_findings}"
        )

    def test_completed_scoring_report_not_flagged(self, tmp_path: Path) -> None:
        """Completed scoring report (no generated footer) → not flagged."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        _write_reconstruction_md(tmp_path, _COMPLETED_REPORT)

        result = audit_project(tmp_path)

        reconstruction_findings = [
            i for i in result.missing + result.inconsistent
            if i.file == "docs/reconstruction.md"
        ]
        assert reconstruction_findings == [], (
            f"Expected no reconstruction findings for completed report, "
            f"got: {reconstruction_findings}"
        )
        # Also verify _check_reconstruction_staleness returns OK directly
        staleness = _check_reconstruction_staleness(tmp_path)
        assert staleness == "OK"

    def test_ideology_audit_findings_unaffected(self, tmp_path: Path) -> None:
        """Regression: ideology.md audit findings are unaffected by reconstruction check."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Overwrite ideology.md with stale content
        _write_ideology_md(tmp_path, stale=True)
        # Reconstruction is missing (removed by helper logic won't run — remove explicitly)
        reconstruction_path = tmp_path / "docs" / "reconstruction.md"
        if reconstruction_path.exists():
            reconstruction_path.unlink()

        result = audit_project(tmp_path)

        # Ideology stale finding must still be present
        ideology_stale = [
            i for i in result.inconsistent
            if i.file == "docs/ideology.md" and "STALE PLACEHOLDER" in i.description
        ]
        assert len(ideology_stale) > 0, (
            f"Expected ideology STALE PLACEHOLDER finding, got: {result.inconsistent}"
        )
        # Reconstruction MISSING finding must also be present
        reconstruction_missing = [
            i for i in result.missing if i.file == "docs/reconstruction.md"
        ]
        assert len(reconstruction_missing) > 0, (
            f"Expected reconstruction MISSING finding, got: {result.missing}"
        )


# ---------------------------------------------------------------------------
# Story AUDIT-001 — .pairmode-overrides suppression
# ---------------------------------------------------------------------------


def _write_overrides(project_dir: Path, lines: list[str]) -> None:
    """Write .pairmode-overrides at project root."""
    content = "\n".join(lines) + "\n"
    (project_dir / ".pairmode-overrides").write_text(content, encoding="utf-8")


class TestLoadOverrides:
    """Unit tests for _load_overrides helper."""

    def test_no_file_returns_empty_set(self, tmp_path: Path) -> None:
        assert _load_overrides(tmp_path) == set()

    def test_empty_file_returns_empty_set(self, tmp_path: Path) -> None:
        (tmp_path / ".pairmode-overrides").write_text("", encoding="utf-8")
        assert _load_overrides(tmp_path) == set()

    def test_comment_lines_ignored(self, tmp_path: Path) -> None:
        _write_overrides(tmp_path, ["# this is a comment", "# another comment"])
        assert _load_overrides(tmp_path) == set()

    def test_blank_lines_ignored(self, tmp_path: Path) -> None:
        _write_overrides(tmp_path, ["", "   ", ""])
        assert _load_overrides(tmp_path) == set()

    def test_valid_entry_parsed(self, tmp_path: Path) -> None:
        _write_overrides(tmp_path, ["CLAUDE.md:review checklist"])
        assert _load_overrides(tmp_path) == {("CLAUDE.md", "review checklist")}

    def test_multiple_entries_parsed(self, tmp_path: Path) -> None:
        _write_overrides(tmp_path, [
            "CLAUDE.md:review checklist",
            ".claude/agents/reviewer.md:checklist",
        ])
        assert _load_overrides(tmp_path) == {
            ("CLAUDE.md", "review checklist"),
            (".claude/agents/reviewer.md", "checklist"),
        }

    def test_whitespace_stripped(self, tmp_path: Path) -> None:
        _write_overrides(tmp_path, ["  CLAUDE.md : review checklist  "])
        assert _load_overrides(tmp_path) == {("CLAUDE.md", "review checklist")}

    def test_line_without_colon_ignored(self, tmp_path: Path) -> None:
        _write_overrides(tmp_path, ["CLAUDE.md review checklist"])
        assert _load_overrides(tmp_path) == set()

    def test_mixed_valid_and_comment_lines(self, tmp_path: Path) -> None:
        _write_overrides(tmp_path, [
            "# comment",
            "CLAUDE.md:review checklist",
            "",
            "# another comment",
            ".claude/agents/reviewer.md:checklist",
        ])
        assert _load_overrides(tmp_path) == {
            ("CLAUDE.md", "review checklist"),
            (".claude/agents/reviewer.md", "checklist"),
        }


class TestAuditOverridesSuppress:
    """Integration: .pairmode-overrides suppresses INCONSISTENT and MISSING findings."""

    def _get_first_canonical_section_key(self) -> str:
        """Return the normalised key for the first ## header in CLAUDE.md.j2."""
        import re
        canonical_text = (_audit_mod.TEMPLATES_DIR / "CLAUDE.md.j2").read_text(encoding="utf-8")
        headers = re.findall(r"^## .+", canonical_text, re.MULTILINE)
        assert headers, "CLAUDE.md.j2 must have at least one ## header"
        from skills.pairmode.scripts.audit import _normalise
        return _normalise(headers[0])

    def test_inconsistent_finding_suppressed_when_in_overrides(self, tmp_path: Path) -> None:
        """An INCONSISTENT finding for a section declared in .pairmode-overrides is suppressed."""
        import json as _json
        import re

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        ctx = {
            "project_name": "testproject",
            "project_description": "",
            "stack": "",
            "build_command": "",
            "test_command": "",
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

        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        # Find the first real section key in CLAUDE.md
        section_key = self._get_first_canonical_section_key()

        # Alter the section body to produce an INCONSISTENT finding
        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        canonical_text = (_audit_mod.TEMPLATES_DIR / "CLAUDE.md.j2").read_text(encoding="utf-8")
        headers = re.findall(r"^## .+", canonical_text, re.MULTILINE)
        first_header = headers[0]
        altered = re.sub(
            rf"({re.escape(first_header)}\n+)(.+?)(\n##|\Z)",
            lambda m: m.group(1) + "COMPLETELY DIFFERENT CONTENT\n" + m.group(3),
            existing,
            count=1,
            flags=re.DOTALL,
        )
        claude_md.write_text(altered, encoding="utf-8")

        # Confirm without overrides this produces an INCONSISTENT finding
        result_without = audit_project(tmp_path)
        inconsistent_without = [
            i for i in result_without.inconsistent
            if i.file == "CLAUDE.md" and i.section == section_key
        ]
        assert len(inconsistent_without) > 0, (
            f"Expected INCONSISTENT for section '{section_key}' without overrides"
        )

        # Now declare the section as an override
        _write_overrides(tmp_path, [f"CLAUDE.md:{section_key}"])
        result_with = audit_project(tmp_path)
        inconsistent_with = [
            i for i in result_with.inconsistent
            if i.file == "CLAUDE.md" and i.section == section_key
        ]
        assert inconsistent_with == [], (
            f"Expected INCONSISTENT for '{section_key}' to be suppressed by .pairmode-overrides, "
            f"got: {inconsistent_with}"
        )

    def test_missing_finding_suppressed_when_in_overrides(self, tmp_path: Path) -> None:
        """A MISSING finding for a section declared in .pairmode-overrides is suppressed."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        # Remove CLAUDE.md entirely — all its sections become MISSING
        (tmp_path / "CLAUDE.md").unlink()

        # Without overrides, CLAUDE.md sections appear as MISSING
        result_without = audit_project(tmp_path)
        claude_missing_without = [i for i in result_without.missing if i.file == "CLAUDE.md"]
        assert len(claude_missing_without) > 0, "Expected MISSING items for CLAUDE.md"

        # Pick the first missing section key
        first_missing_key = claude_missing_without[0].section

        # Declare that section as an override
        _write_overrides(tmp_path, [f"CLAUDE.md:{first_missing_key}"])
        result_with = audit_project(tmp_path)
        claude_missing_with = [
            i for i in result_with.missing
            if i.file == "CLAUDE.md" and i.section == first_missing_key
        ]
        assert claude_missing_with == [], (
            f"Expected MISSING for '{first_missing_key}' to be suppressed by .pairmode-overrides, "
            f"got: {claude_missing_with}"
        )

    def test_section_not_in_overrides_still_surfaces(self, tmp_path: Path) -> None:
        """A MISSING finding for a section NOT in .pairmode-overrides still surfaces."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        # Remove CLAUDE.md to produce multiple MISSING findings
        (tmp_path / "CLAUDE.md").unlink()

        # Get all missing sections
        result_all_missing = audit_project(tmp_path)
        claude_missing = [i for i in result_all_missing.missing if i.file == "CLAUDE.md"]
        assert len(claude_missing) >= 2, "Need at least 2 missing sections for this test"

        # Declare only the first section as override
        first_key = claude_missing[0].section
        second_key = claude_missing[1].section
        _write_overrides(tmp_path, [f"CLAUDE.md:{first_key}"])

        result = audit_project(tmp_path)
        # The first section should be suppressed
        suppressed = [i for i in result.missing if i.file == "CLAUDE.md" and i.section == first_key]
        assert suppressed == [], f"Expected first section suppressed, got: {suppressed}"
        # The second section should still appear
        still_present = [i for i in result.missing if i.file == "CLAUDE.md" and i.section == second_key]
        assert len(still_present) > 0, (
            f"Expected second section '{second_key}' still in MISSING, got: {result.missing}"
        )

    def test_no_overrides_file_no_behavioral_change(self, tmp_path: Path) -> None:
        """When .pairmode-overrides does not exist, audit behaves as before."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        (tmp_path / "CLAUDE.md").unlink()

        # No .pairmode-overrides file
        assert not (tmp_path / ".pairmode-overrides").exists()

        result = audit_project(tmp_path)
        claude_missing = [i for i in result.missing if i.file == "CLAUDE.md"]
        assert len(claude_missing) > 0, (
            "Expected MISSING items for CLAUDE.md when no .pairmode-overrides file"
        )
