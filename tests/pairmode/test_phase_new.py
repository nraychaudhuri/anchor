"""Tests for skills/pairmode/scripts/phase_new.py."""

from __future__ import annotations

import json
import pathlib

from click.testing import CliRunner

from skills.pairmode.scripts.phase_new import (
    phase_new,
    _read_phase_title,
    _create_index,
    _detect_active_era,
    _update_era_phases_table,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(args: list[str], input: str | None = None) -> "click.testing.Result":
    runner = CliRunner()
    return runner.invoke(phase_new, args, input=input, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFreshProject:
    """Fresh project: creates both phase-1.md and index.md."""

    def test_creates_phase_file(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Getting Started",
                "--goal", "Bootstrap the project",
            ]
        )
        assert result.exit_code == 0, result.output
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        assert phase_file.exists()
        content = phase_file.read_text()
        assert "Getting Started" in content

    def test_creates_index_file(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Getting Started",
                "--goal", "Bootstrap the project",
            ]
        )
        assert result.exit_code == 0, result.output
        index_file = tmp_path / "docs" / "phases" / "index.md"
        assert index_file.exists()
        content = index_file.read_text()
        assert "Getting Started" in content
        assert "phase-1.md" in content
        assert "planned" in content

    def test_goal_in_phase_file(self, tmp_path: pathlib.Path) -> None:
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Alpha",
                "--goal", "Do the alpha things",
            ]
        )
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert "Do the alpha things" in content


class TestIdempotent:
    """Running twice with same phase ID warns and does not overwrite."""

    def test_warns_on_second_run(self, tmp_path: pathlib.Path) -> None:
        args = [
            "--project-dir", str(tmp_path),
            "--phase-id", "1",
            "--title", "Alpha",
            "--goal", "First goal",
        ]
        invoke(args)
        result = invoke(args)
        assert result.exit_code == 0
        assert "already exists" in result.output or "Warning" in result.output

    def test_does_not_overwrite(self, tmp_path: pathlib.Path) -> None:
        args = [
            "--project-dir", str(tmp_path),
            "--phase-id", "1",
            "--title", "Alpha",
            "--goal", "First goal",
        ]
        invoke(args)
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        original = phase_file.read_text()

        # Second run with different title — file must stay unchanged
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Changed Title",
                "--goal", "Different goal",
            ]
        )
        assert phase_file.read_text() == original


class TestPrevPhase:
    """Phase 3 after phases 1 and 2 exist: prev_phase populated from phase-2.md."""

    def test_prev_phase_populated(self, tmp_path: pathlib.Path) -> None:
        # Create phase 1
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Phase One",
                "--goal", "",
            ]
        )
        # Create phase 2
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "2",
                "--title", "Phase Two",
                "--goal", "",
            ]
        )
        # Create phase 3
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "3",
                "--title", "Phase Three",
                "--goal", "",
            ]
        )
        content = (tmp_path / "docs" / "phases" / "phase-3.md").read_text()
        # Should reference phase 2 as previous
        assert "Phase Two" in content or "phase-2.md" in content

    def test_no_prev_phase_when_n_is_1(self, tmp_path: pathlib.Path) -> None:
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Solo Phase",
                "--goal", "",
            ]
        )
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        # No backward nav link expected
        assert "phase-0.md" not in content


class TestDirCreation:
    """docs/phases/ directory is created if it does not exist."""

    def test_creates_phases_dir(self, tmp_path: pathlib.Path) -> None:
        assert not (tmp_path / "docs").exists()
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Hello",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0
        assert (tmp_path / "docs" / "phases").is_dir()
        assert (tmp_path / "docs" / "phases" / "phase-1.md").exists()


class TestPrevPhaseNoHeading:
    """Phase N where N-1 exists but has no # Phase heading: graceful fallback."""

    def test_graceful_fallback(self, tmp_path: pathlib.Path) -> None:
        phases_dir = tmp_path / "docs" / "phases"
        phases_dir.mkdir(parents=True)
        # Write a phase-1.md with no # Phase heading
        (phases_dir / "phase-1.md").write_text(
            "Some content without a phase heading.\n", encoding="utf-8"
        )
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "2",
                "--title", "Second Phase",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0
        content = (phases_dir / "phase-2.md").read_text()
        # Should fall back to "Phase 1" rather than crashing
        assert "Phase 1" in content

    def test_read_phase_title_fallback(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "no_heading.md"
        f.write_text("No heading here\n", encoding="utf-8")
        title = _read_phase_title(f, 5)
        assert title == "Phase 5"

    def test_read_phase_title_with_heading(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "phase.md"
        f.write_text("# MyProject — Phase 2: The Real Deal\n\nContent\n", encoding="utf-8")
        title = _read_phase_title(f, 2)
        assert title == "The Real Deal"


class TestProjectNameFromContext:
    """project_name is read from pairmode_context.json when present."""

    def test_project_name_from_context_renders_in_phase_file(
        self, tmp_path: pathlib.Path
    ) -> None:
        # Write context file
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir()
        ctx = {"project_name": "myawesome"}
        (companion_dir / "pairmode_context.json").write_text(
            json.dumps(ctx), encoding="utf-8"
        )

        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "First",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert "myawesome" in content

    def test_project_name_fallback_when_context_absent(
        self, tmp_path: pathlib.Path
    ) -> None:
        # No .companion directory at all
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "First",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert "project" in content


class TestCreateIndex:
    """_create_index() threads project_name into the rendered index.md."""

    def test_project_name_in_rendered_index(self, tmp_path: pathlib.Path) -> None:
        index_path = tmp_path / "index.md"
        _create_index(index_path, phase_id=1, phase_title="First Phase", project_name="MyProject")
        content = index_path.read_text()
        assert "MyProject" in content

    def test_default_fallback_renders_without_crash(self, tmp_path: pathlib.Path) -> None:
        index_path = tmp_path / "index.md"
        # Call with default project_name — must not raise
        _create_index(index_path, phase_id=1, phase_title="First Phase")
        assert index_path.exists()
        content = index_path.read_text()
        assert "First Phase" in content


class TestDryRun:
    """--dry-run prints what would be written without writing files."""

    def test_dry_run_no_files_written(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "2",
                "--title", "Second Phase",
                "--goal", "Do things",
                "--dry-run",
            ]
        )
        assert result.exit_code == 0, result.output
        # No files should have been written
        assert not (tmp_path / "docs").exists()

    def test_dry_run_output_contains_would_write(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "3",
                "--title", "Third Phase",
                "--goal", "",
                "--dry-run",
            ]
        )
        assert result.exit_code == 0, result.output
        assert "Would write" in result.output

    def test_dry_run_with_existing_index_shows_would_update(
        self, tmp_path: pathlib.Path
    ) -> None:
        # Create index first (non-dry-run)
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "First",
                "--goal", "",
            ]
        )
        # Now dry-run for phase 2
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "2",
                "--title", "Second",
                "--goal", "",
                "--dry-run",
            ]
        )
        assert result.exit_code == 0, result.output
        assert "Would write" in result.output or "Would update" in result.output
        # phase-2.md must not exist
        assert not (tmp_path / "docs" / "phases" / "phase-2.md").exists()


# ---------------------------------------------------------------------------
# Era detection helpers
# ---------------------------------------------------------------------------

ERA_ACTIVE_CONTENT = """\
---
id: 001
name: Foundation
status: active
---

## Strategic intent

Building the foundation.

## Rails

| Rail | Primary domain |
|------|----------------|

## Phases

| Phase | Title | Status |
|-------|-------|--------|
"""

ERA_COMPLETE_CONTENT = """\
---
id: 001
name: Foundation
status: complete
---

## Phases

| Phase | Title | Status |
|-------|-------|--------|
"""


def _write_era(eras_dir: pathlib.Path, filename: str, content: str) -> pathlib.Path:
    eras_dir.mkdir(parents=True, exist_ok=True)
    p = eras_dir / filename
    p.write_text(content, encoding="utf-8")
    return p


class TestDetectActiveEra:
    """_detect_active_era() helper tests."""

    def test_returns_none_when_no_eras_dir(self, tmp_path: pathlib.Path) -> None:
        result = _detect_active_era(tmp_path)
        assert result is None

    def test_returns_none_when_no_active_era(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        _write_era(eras_dir, "001-foundation.md", ERA_COMPLETE_CONTENT)
        result = _detect_active_era(tmp_path)
        assert result is None

    def test_returns_era_id_for_single_active(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)
        result = _detect_active_era(tmp_path)
        assert result == "001"

    def test_multiple_active_returns_highest(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        active1 = ERA_ACTIVE_CONTENT
        active2 = active1.replace("id: 001", "id: 002").replace("name: Foundation", "name: Second")
        _write_era(eras_dir, "001-foundation.md", active1)
        _write_era(eras_dir, "002-second.md", active2)
        result = _detect_active_era(tmp_path)
        assert result == "002"


class TestUpdateErasPhasesTable:
    """_update_era_phases_table() helper tests."""

    def test_appends_row_to_phases_table(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        era_file = _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)
        _update_era_phases_table(tmp_path, "001", 3, "My Phase")
        content = era_file.read_text()
        assert "| 3 | My Phase | planned |" in content

    def test_no_crash_when_era_not_found(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)
        # Trying to update era 002 which doesn't exist — must not raise
        _update_era_phases_table(tmp_path, "002", 1, "Whatever")

    def test_update_era_phases_table_with_no_frontmatter(self, tmp_path: pathlib.Path) -> None:
        """Era file with body content but no frontmatter block must not crash.

        _update_era_phases_table should gracefully skip or add the row if a
        Phases table is present.  It must never raise an exception.
        """
        eras_dir = tmp_path / "docs" / "eras"
        eras_dir.mkdir(parents=True, exist_ok=True)
        body_only_content = (
            "## Strategic intent\n\nBuilding the foundation.\n\n"
            "## Phases\n\n"
            "| Phase | Title | Status |\n"
            "|-------|-------|--------|\n"
        )
        era_file = eras_dir / "001-foundation.md"
        era_file.write_text(body_only_content, encoding="utf-8")

        # Must not raise regardless of whether it inserts the row
        _update_era_phases_table(tmp_path, "001", 3, "My Phase")
        # Era file still readable after the call
        assert era_file.exists()


class TestEraFrontmatterInPhaseFile:
    """Phase file gets era frontmatter when active era exists."""

    def test_phase_has_era_frontmatter_when_active_era(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)

        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "First Phase",
                "--goal", "Do things",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert 'era: "001"' in content

    def test_phase_has_empty_stories_table(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)

        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "First Phase",
                "--goal", "",
            ]
        )
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        # Stories table header present
        assert "| ID | Title | Status |" in content
        # No extra story rows beyond separator
        assert "|----|-------|--------|" in content

    def test_era_phases_table_updated(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        era_file = _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)

        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "5",
                "--title", "Fifth Phase",
                "--goal", "",
            ]
        )
        era_content = era_file.read_text()
        assert "| 5 | Fifth Phase | planned |" in era_content

    def test_no_era_frontmatter_when_no_active_era(self, tmp_path: pathlib.Path) -> None:
        # No eras directory at all
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Solo Phase",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert "era:" not in content
        # Frontmatter block should be absent — file must not start with ---
        assert not content.startswith("---")


# ---------------------------------------------------------------------------
# Tests: depth guard
# ---------------------------------------------------------------------------


class TestDepthGuard:
    """phase_new depth guard rejects too-shallow project directories."""

    def test_project_dir_root_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            phase_new,
            ["--project-dir", "/", "--phase-id", "1", "--title", "T", "--goal", ""],
            catch_exceptions=False,
        )
        assert result.exit_code != 0
        assert "too shallow" in result.output.lower()

    def test_project_dir_tmp_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            phase_new,
            ["--project-dir", "/tmp", "--phase-id", "1", "--title", "T", "--goal", ""],
            catch_exceptions=False,
        )
        assert result.exit_code != 0
