"""
tests/pairmode/test_story_update.py — Tests for story_update.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Insert scripts dir so the module can be imported directly
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from story_update import (
    _parse_story_id,
    update_story_status,
    update_phase_story_status,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal project layout."""
    project = tmp_path / "myproject"
    project.mkdir()
    (project / "docs" / "stories").mkdir(parents=True)
    (project / "docs" / "phases").mkdir(parents=True)
    return project


def _make_story(project: Path, rail: str, story_id: str, status: str = "draft") -> Path:
    rail_dir = project / "docs" / "stories" / rail
    rail_dir.mkdir(parents=True, exist_ok=True)
    story_path = rail_dir / f"{story_id}.md"
    story_path.write_text(
        f"---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        f"title: Test story\n"
        f"status: {status}\n"
        f"phase: \"1\"\n"
        f"primary_files:\n"
        f"touches:\n"
        f"---\n"
        f"\n"
        f"## Acceptance criterion\n\n"
        f"_(fill in)_\n",
        encoding="utf-8",
    )
    return story_path


def _make_phase(project: Path, filename: str, rows: list[tuple[str, str, str]]) -> Path:
    """Create a phase manifest with a Stories table.

    rows: list of (story_id, title, status) tuples.
    """
    phase_path = project / "docs" / "phases" / filename
    table_header = "| Story ID | Title | Status |\n|----------|-------|--------|\n"
    rows_text = "".join(f"| {sid} | {title} | {st} |\n" for sid, title, st in rows)
    content = (
        "---\n"
        "id: phase-1\n"
        "---\n\n"
        "## Overview\n\nA phase.\n\n"
        "## Stories\n\n"
        + table_header
        + rows_text
        + "\n## Notes\n\nSome notes.\n"
    )
    phase_path.write_text(content, encoding="utf-8")
    return phase_path


# ---------------------------------------------------------------------------
# _parse_story_id security / format tests
# ---------------------------------------------------------------------------


def test_parse_story_id_rejects_absolute_path_component():
    with pytest.raises(ValueError):
        _parse_story_id("/etc/passwd-001")


def test_parse_story_id_rejects_relative_traversal():
    with pytest.raises(ValueError):
        _parse_story_id("../../etc-001")


def test_parse_story_id_rejects_lowercase():
    with pytest.raises(ValueError):
        _parse_story_id("lowercase-001")


def test_parse_story_id_accepts_simple_rail():
    rail, sid = _parse_story_id("INFRA-001")
    assert rail == "INFRA"
    assert sid == "INFRA-001"


def test_parse_story_id_accepts_multi_segment_rail():
    rail, sid = _parse_story_id("BOOTSTRAP-003")
    assert rail == "BOOTSTRAP"
    assert sid == "BOOTSTRAP-003"


def test_containment_guard_fires_on_escape(tmp_path):
    """Secondary containment guard rejects paths that escape project_dir."""
    import re
    import unittest.mock as mock
    # Monkeypatch _STORY_ID_RE to allow a path-separator-containing ID
    fake_re = re.compile(r'^(.+)-(\d+)$')
    project_dir = tmp_path / "project" / "subdir"
    project_dir.mkdir(parents=True)
    with mock.patch("story_update._STORY_ID_RE", fake_re):
        with pytest.raises((FileNotFoundError, ValueError)):
            update_story_status("../../evil-001", project_dir, "complete")


# ---------------------------------------------------------------------------
# update_story_status tests
# ---------------------------------------------------------------------------


def test_story_status_updated_in_frontmatter(tmp_path):
    project = _make_project(tmp_path)
    story_path = _make_story(project, "BOOTSTRAP", "BOOTSTRAP-001", status="draft")

    returned = update_story_status("BOOTSTRAP-001", project, "in-progress")
    assert returned == story_path

    text = story_path.read_text(encoding="utf-8")
    assert "status: in-progress" in text
    # Old status should not appear
    assert "status: draft" not in text


def test_story_status_all_transitions(tmp_path):
    project = _make_project(tmp_path)
    _make_story(project, "BOOTSTRAP", "BOOTSTRAP-001", status="draft")

    for new_status in ("planned", "in-progress", "complete", "backlog", "draft"):
        update_story_status("BOOTSTRAP-001", project, new_status)
        text = (project / "docs" / "stories" / "BOOTSTRAP" / "BOOTSTRAP-001.md").read_text()
        assert f"status: {new_status}" in text


def test_story_not_found_raises_file_not_found_error(tmp_path):
    project = _make_project(tmp_path)
    with pytest.raises(FileNotFoundError):
        update_story_status("BOOTSTRAP-999", project, "complete")


def test_invalid_story_id_format_no_hyphen(tmp_path):
    project = _make_project(tmp_path)
    with pytest.raises(ValueError):
        update_story_status("BOOTSTRAP", project, "complete")


def test_invalid_story_id_format_last_segment_not_digits(tmp_path):
    project = _make_project(tmp_path)
    with pytest.raises(ValueError):
        update_story_status("BOOTSTRAP-ABC", project, "complete")


def test_body_content_preserved_after_status_update(tmp_path):
    project = _make_project(tmp_path)
    _make_story(project, "BOOTSTRAP", "BOOTSTRAP-001", status="draft")

    update_story_status("BOOTSTRAP-001", project, "complete")
    text = (project / "docs" / "stories" / "BOOTSTRAP" / "BOOTSTRAP-001.md").read_text()
    assert "## Acceptance criterion" in text
    assert "_(fill in)_" in text


# ---------------------------------------------------------------------------
# update_phase_story_status tests
# ---------------------------------------------------------------------------


def test_phase_manifest_status_column_updated(tmp_path):
    project = _make_project(tmp_path)
    _make_story(project, "BOOTSTRAP", "BOOTSTRAP-001")
    _make_phase(
        project,
        "phase-001.md",
        [("BOOTSTRAP-001", "My story", "draft"), ("BOOTSTRAP-002", "Other", "planned")],
    )

    updated = update_phase_story_status("BOOTSTRAP-001", project, "complete")
    assert len(updated) == 1

    text = updated[0].read_text(encoding="utf-8")
    # BOOTSTRAP-001 row should have complete
    assert "| BOOTSTRAP-001 | My story | complete |" in text
    # BOOTSTRAP-002 row should be unchanged
    assert "| BOOTSTRAP-002 | Other | planned |" in text


def test_only_matching_row_updated_multiple_rows(tmp_path):
    project = _make_project(tmp_path)
    _make_phase(
        project,
        "phase-001.md",
        [
            ("RAIL-001", "Story one", "draft"),
            ("RAIL-002", "Story two", "draft"),
            ("RAIL-003", "Story three", "draft"),
        ],
    )

    update_phase_story_status("RAIL-002", project, "complete")
    text = (project / "docs" / "phases" / "phase-001.md").read_text()
    assert "| RAIL-001 | Story one | draft |" in text
    assert "| RAIL-002 | Story two | complete |" in text
    assert "| RAIL-003 | Story three | draft |" in text


def test_two_phase_manifests_both_updated(tmp_path):
    project = _make_project(tmp_path)
    _make_phase(project, "phase-001.md", [("SHARED-001", "A", "draft")])
    _make_phase(project, "phase-002.md", [("SHARED-001", "A", "planned")])

    updated = update_phase_story_status("SHARED-001", project, "in-progress")
    assert len(updated) == 2

    for p in updated:
        text = p.read_text(encoding="utf-8")
        assert "in-progress" in text


def test_returns_empty_list_when_no_phase_contains_story(tmp_path):
    project = _make_project(tmp_path)
    _make_phase(project, "phase-001.md", [("OTHER-001", "Other", "draft")])

    result = update_phase_story_status("MISSING-001", project, "complete")
    assert result == []


def test_returns_empty_list_when_no_phases_dir(tmp_path):
    project = tmp_path / "noPhases"
    project.mkdir()
    (project / "docs" / "stories").mkdir(parents=True)
    # No phases dir

    result = update_phase_story_status("BOOTSTRAP-001", project, "complete")
    assert result == []


def test_phase_manifest_with_link_syntax_in_id_cell(tmp_path):
    """Story IDs wrapped in Markdown links should still match."""
    project = _make_project(tmp_path)
    phase_path = project / "docs" / "phases" / "phase-001.md"
    phase_path.write_text(
        "---\nid: phase-1\n---\n\n"
        "## Stories\n\n"
        "| Story ID | Title | Status |\n"
        "|----------|-------|--------|\n"
        "| [LINK-001](../stories/LINK/LINK-001.md) | A linked story | draft |\n",
        encoding="utf-8",
    )

    updated = update_phase_story_status("LINK-001", project, "complete")
    assert len(updated) == 1
    text = updated[0].read_text(encoding="utf-8")
    assert "complete" in text
    assert "draft" not in text


# ---------------------------------------------------------------------------
# CLI integration via Click test runner
# ---------------------------------------------------------------------------


def test_cli_updates_story_and_phase(tmp_path):
    from click.testing import CliRunner
    from story_update import story_update

    project = _make_project(tmp_path)
    _make_story(project, "BOOTSTRAP", "BOOTSTRAP-001", status="draft")
    _make_phase(project, "phase-001.md", [("BOOTSTRAP-001", "My story", "draft")])

    runner = CliRunner()
    result = runner.invoke(
        story_update,
        [
            "--story-id", "BOOTSTRAP-001",
            "--status", "complete",
            "--project-dir", str(project),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Updated BOOTSTRAP-001: status → complete" in result.output
    assert "Phase manifest updated:" in result.output

    story_text = (project / "docs" / "stories" / "BOOTSTRAP" / "BOOTSTRAP-001.md").read_text()
    assert "status: complete" in story_text


def test_cli_no_phase_manifest_found(tmp_path):
    from click.testing import CliRunner
    from story_update import story_update

    project = _make_project(tmp_path)
    _make_story(project, "BOOTSTRAP", "BOOTSTRAP-001", status="draft")
    # No phase manifest

    runner = CliRunner()
    result = runner.invoke(
        story_update,
        [
            "--story-id", "BOOTSTRAP-001",
            "--status", "planned",
            "--project-dir", str(project),
        ],
    )
    assert result.exit_code == 0
    assert "no phase manifest found" in result.output
