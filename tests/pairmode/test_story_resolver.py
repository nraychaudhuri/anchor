"""Tests for story_resolver.py"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Insert scripts directory so story_resolver (and its schema_validator dep) can be imported
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from story_resolver import resolve_story, list_phase_stories  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_story_file(tmp_path: Path, story_id: str, rail: str, **extra_fm) -> Path:
    """Create a minimal story file under tmp_path/docs/stories/RAIL/."""
    story_dir = tmp_path / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"

    primary_files = extra_fm.get("primary_files", [])
    touches = extra_fm.get("touches", [])
    title = extra_fm.get("title", "Test Story Title")
    status = extra_fm.get("status", "planned")
    phase = extra_fm.get("phase", "16")

    fm_lines = [
        "---",
        f"id: {story_id}",
        f"rail: {rail}",
        f"title: {title}",
        f"status: {status}",
        f"phase: {phase}",
    ]
    if primary_files:
        fm_lines.append("primary_files:")
        for pf in primary_files:
            fm_lines.append(f"  - {pf}")
    if touches:
        fm_lines.append("touches:")
        for t in touches:
            fm_lines.append(f"  - {t}")
    fm_lines.append("---")
    fm_lines.append("")
    fm_lines.append("## Body content")
    fm_lines.append("")
    fm_lines.append("This is the story body.")

    story_path.write_text("\n".join(fm_lines), encoding="utf-8")
    return story_path


def _make_phase_manifest(tmp_path: Path, stories: list[tuple[str, str, str]]) -> Path:
    """Create a minimal phase manifest with a Stories table.

    stories is a list of (id, title, status) tuples.
    """
    phase_path = tmp_path / "phase-16.md"
    lines = [
        "---",
        "id: 16",
        "title: Test Phase",
        "status: active",
        "---",
        "",
        "## Overview",
        "",
        "Some overview text.",
        "",
        "## Stories",
        "",
        "| ID | Title | Status |",
        "|----|-------|--------|",
    ]
    for story_id, title, status in stories:
        lines.append(f"| {story_id} | {title} | {status} |")
    lines.append("")
    phase_path.write_text("\n".join(lines), encoding="utf-8")
    return phase_path


# ---------------------------------------------------------------------------
# resolve_story tests
# ---------------------------------------------------------------------------

class TestResolveStory:

    def test_finds_and_parses_story_file(self, tmp_path):
        _make_story_file(tmp_path, "BOOTSTRAP-003", "BOOTSTRAP")
        result = resolve_story("BOOTSTRAP-003", tmp_path)
        assert result["id"] == "BOOTSTRAP-003"
        assert result["rail"] == "BOOTSTRAP"
        assert result["title"] == "Test Story Title"
        assert result["status"] == "planned"
        assert result["phase"] == "16"

    def test_raises_file_not_found_for_unknown_id(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_story("BOOTSTRAP-999", tmp_path)

    def test_returns_correct_primary_files_list(self, tmp_path):
        _make_story_file(
            tmp_path, "AUDIT-007", "AUDIT",
            primary_files=["skills/pairmode/scripts/foo.py", "tests/pairmode/test_foo.py"],
            touches=["docs/architecture.md"],
        )
        result = resolve_story("AUDIT-007", tmp_path)
        assert result["primary_files"] == [
            "skills/pairmode/scripts/foo.py",
            "tests/pairmode/test_foo.py",
        ]
        assert result["touches"] == ["docs/architecture.md"]

    def test_primary_files_defaults_to_empty_list(self, tmp_path):
        _make_story_file(tmp_path, "BOOTSTRAP-001", "BOOTSTRAP")
        result = resolve_story("BOOTSTRAP-001", tmp_path)
        assert result["primary_files"] == []
        assert result["touches"] == []

    def test_body_contains_content_after_frontmatter(self, tmp_path):
        _make_story_file(tmp_path, "BOOTSTRAP-002", "BOOTSTRAP")
        result = resolve_story("BOOTSTRAP-002", tmp_path)
        assert "story body" in result["body"]
        # Body should not contain frontmatter keys
        assert "id: BOOTSTRAP-002" not in result["body"]

    def test_invalid_story_id_no_hyphen_raises_value_error(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_story("NOHYPHEN", tmp_path)

    def test_invalid_story_id_hyphen_not_followed_by_digits_raises_value_error(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_story("BOOTSTRAP-abc", tmp_path)

    def test_invalid_story_id_lowercase_raises_value_error(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_story("bootstrap-003", tmp_path)


# ---------------------------------------------------------------------------
# list_phase_stories tests
# ---------------------------------------------------------------------------

class TestListPhaseStories:

    def test_returns_story_ids_in_order(self, tmp_path):
        stories = [
            ("BOOTSTRAP-001", "Story One", "done"),
            ("BOOTSTRAP-002", "Story Two", "planned"),
            ("AUDIT-001", "Audit One", "planned"),
        ]
        phase_path = _make_phase_manifest(tmp_path, stories)
        result = list_phase_stories(phase_path)
        assert result == ["BOOTSTRAP-001", "BOOTSTRAP-002", "AUDIT-001"]

    def test_returns_empty_list_for_legacy_phase_without_stories_table(self, tmp_path):
        phase_path = tmp_path / "phase-old.md"
        phase_path.write_text(
            "---\nid: 5\ntitle: Old Phase\nstatus: done\n---\n\n## Overview\n\nSome text.\n",
            encoding="utf-8",
        )
        result = list_phase_stories(phase_path)
        assert result == []

    def test_returns_single_story(self, tmp_path):
        stories = [("BOOTSTRAP-010", "Only Story", "planned")]
        phase_path = _make_phase_manifest(tmp_path, stories)
        result = list_phase_stories(phase_path)
        assert result == ["BOOTSTRAP-010"]

    def test_empty_stories_table(self, tmp_path):
        phase_path = tmp_path / "phase-empty.md"
        phase_path.write_text(
            "---\nid: 17\ntitle: Empty Phase\nstatus: planned\n---\n\n## Stories\n\n| ID | Title | Status |\n|----|-------|--------|\n",
            encoding="utf-8",
        )
        result = list_phase_stories(phase_path)
        assert result == []

    def test_list_phase_stories_link_formatted_id(self, tmp_path):
        """Story IDs formatted as Markdown links are stripped to bare IDs."""
        phase_path = tmp_path / "phase-link.md"
        phase_path.write_text(
            "---\nid: 20\ntitle: Link Phase\nstatus: active\n---\n\n"
            "## Stories\n\n"
            "| ID | Title | Status |\n"
            "|----|-------|--------|\n"
            "| [BOOTSTRAP-001](docs/stories/BOOTSTRAP/BOOTSTRAP-001.md) | Bootstrap init | planned |\n"
            "| [AUDIT-002](docs/stories/AUDIT/AUDIT-002.md) | Audit check | complete |\n",
            encoding="utf-8",
        )
        result = list_phase_stories(phase_path)
        assert result == ["BOOTSTRAP-001", "AUDIT-002"]
