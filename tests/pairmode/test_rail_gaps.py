"""Tests for Story 16.4 — _check_rail_gaps and rail gap prompting in sync_project."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills.pairmode.scripts.sync import _check_rail_gaps, sync_project, SyncResult
from skills.pairmode.scripts.bootstrap import PAIRMODE_DEFAULT_RAILS


# ---------------------------------------------------------------------------
# Tests for _check_rail_gaps (pure function, no I/O)
# ---------------------------------------------------------------------------


class TestCheckRailGaps:
    """_check_rail_gaps returns missing default rails."""

    def test_no_stories_dir_returns_empty(self, tmp_path: Path) -> None:
        """When docs/stories/ does not exist, returns [] without crashing."""
        result = _check_rail_gaps(tmp_path, "")
        assert result == []

    def test_present_rail_not_returned(self, tmp_path: Path) -> None:
        """A rail that already has a directory is not reported as missing."""
        stories_dir = tmp_path / "docs" / "stories"
        # Create all default generic rails
        for rail in PAIRMODE_DEFAULT_RAILS["generic"]:
            (stories_dir / rail).mkdir(parents=True)

        result = _check_rail_gaps(tmp_path, "")
        assert result == [], f"All present rails should be absent from result, got: {result}"

    def test_missing_default_rail_returned(self, tmp_path: Path) -> None:
        """A default rail without a directory is returned as missing."""
        stories_dir = tmp_path / "docs" / "stories"
        stories_dir.mkdir(parents=True)
        # Add only the first generic rail, leave the rest absent
        generic_rails = PAIRMODE_DEFAULT_RAILS["generic"]
        (stories_dir / generic_rails[0]).mkdir()

        result = _check_rail_gaps(tmp_path, "")
        # The remaining generic rails should be in the result
        for rail in generic_rails[1:]:
            assert rail in result, f"Expected missing rail {rail} in result {result}"

    def test_all_rails_missing_returns_all(self, tmp_path: Path) -> None:
        """When docs/stories/ exists but has no subdirs, all default rails are returned."""
        stories_dir = tmp_path / "docs" / "stories"
        stories_dir.mkdir(parents=True)

        result = _check_rail_gaps(tmp_path, "")
        generic_defaults = PAIRMODE_DEFAULT_RAILS["generic"]
        for rail in generic_defaults:
            assert rail in result

    def test_stack_influences_rails(self, tmp_path: Path) -> None:
        """A 'web' stack uses web default rails, not generic."""
        stories_dir = tmp_path / "docs" / "stories"
        stories_dir.mkdir(parents=True)

        result = _check_rail_gaps(tmp_path, "web react")
        web_defaults = PAIRMODE_DEFAULT_RAILS["web"]
        for rail in web_defaults:
            assert rail in result

    def test_extra_dirs_not_removed(self, tmp_path: Path) -> None:
        """Non-default rail directories in docs/stories/ are ignored (not flagged)."""
        stories_dir = tmp_path / "docs" / "stories"
        stories_dir.mkdir(parents=True)
        # Add a non-default rail dir
        (stories_dir / "CUSTOM-RAIL").mkdir()

        result = _check_rail_gaps(tmp_path, "")
        # CUSTOM-RAIL should not appear in results
        assert "CUSTOM-RAIL" not in result

    def test_case_insensitive_matching(self, tmp_path: Path) -> None:
        """Rail directories with different casing are still matched."""
        stories_dir = tmp_path / "docs" / "stories"
        generic_rails = PAIRMODE_DEFAULT_RAILS["generic"]
        # Create the first rail in lowercase
        (stories_dir / generic_rails[0].lower()).mkdir(parents=True)

        result = _check_rail_gaps(tmp_path, "")
        # The lowercase dir should count as present for the uppercase rail
        assert generic_rails[0] not in result


# ---------------------------------------------------------------------------
# Integration tests: sync_project prompts for missing rails
# ---------------------------------------------------------------------------


def _make_project_with_stories(tmp_path: Path) -> None:
    """Set up a minimal project with docs/stories/ directory."""
    (tmp_path / "docs" / "stories").mkdir(parents=True)


class TestSyncRailGapPrompting:
    """sync_project prompts for missing default rails and creates directories on accept."""

    def test_accepting_creates_rail_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When user accepts, the rail directory is created under docs/stories/."""
        _make_project_with_stories(tmp_path)
        # Confirm all prompts (file creation + rail gaps)
        import skills.pairmode.scripts.sync as sync_mod
        monkeypatch.setattr(sync_mod.click, "confirm", lambda *a, **kw: True)

        result = sync_project(tmp_path, yes=False)

        # At least the first generic rail should be created
        first_rail = PAIRMODE_DEFAULT_RAILS["generic"][0]
        assert (tmp_path / "docs" / "stories" / first_rail).is_dir(), (
            f"Expected {first_rail} directory to be created"
        )

    def test_declining_leaves_directory_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When user declines, the rail directory is NOT created."""
        _make_project_with_stories(tmp_path)
        import skills.pairmode.scripts.sync as sync_mod
        monkeypatch.setattr(sync_mod.click, "confirm", lambda *a, **kw: False)

        sync_project(tmp_path, yes=False)

        # None of the default generic rails should be created
        for rail in PAIRMODE_DEFAULT_RAILS["generic"]:
            assert not (tmp_path / "docs" / "stories" / rail).is_dir(), (
                f"Rail {rail} should not be created when user declines"
            )

    def test_yes_flag_creates_all_missing_rails(self, tmp_path: Path) -> None:
        """With yes=True, all missing default rails are created automatically."""
        _make_project_with_stories(tmp_path)

        result = sync_project(tmp_path, yes=True)

        for rail in PAIRMODE_DEFAULT_RAILS["generic"]:
            assert (tmp_path / "docs" / "stories" / rail).is_dir(), (
                f"Expected {rail} to be created with yes=True"
            )

    def test_created_rails_appear_in_applied(self, tmp_path: Path) -> None:
        """Created rail directories appear in result.applied."""
        _make_project_with_stories(tmp_path)

        result = sync_project(tmp_path, yes=True)

        first_rail = PAIRMODE_DEFAULT_RAILS["generic"][0]
        applied_text = " ".join(result.applied)
        assert first_rail in applied_text, (
            f"Expected {first_rail} in applied list, got: {result.applied}"
        )

    def test_no_stories_dir_skips_rail_check(self, tmp_path: Path) -> None:
        """When docs/stories/ does not exist, no rail gap prompts are shown."""
        # Empty project — no docs/stories/
        result = sync_project(tmp_path, yes=True)

        # No rail directories should be created (the gap check is skipped)
        assert not (tmp_path / "docs" / "stories").exists() or not any(
            (tmp_path / "docs" / "stories" / rail).is_dir()
            for rail in PAIRMODE_DEFAULT_RAILS["generic"]
        ), "No rail dirs should be created when docs/stories/ does not exist pre-sync"

    def test_rail_added_to_active_era(self, tmp_path: Path) -> None:
        """When a rail is created, it is added to the active era's Rails table."""
        _make_project_with_stories(tmp_path)

        # Create a minimal active era file
        eras_dir = tmp_path / "docs" / "eras"
        eras_dir.mkdir(parents=True)
        era_file = eras_dir / "001-initial.md"
        era_file.write_text(
            "---\nid: \"001\"\nname: Initial\nstatus: active\n---\n\n"
            "## Rails\n\n"
            "| Rail | Primary domain |\n"
            "|------|----------------|\n",
            encoding="utf-8",
        )

        sync_project(tmp_path, yes=True)

        era_content = era_file.read_text(encoding="utf-8")
        first_rail = PAIRMODE_DEFAULT_RAILS["generic"][0]
        assert f"| {first_rail} |" in era_content, (
            f"Expected {first_rail} to be added to era Rails table"
        )

    def test_already_present_rails_not_prompted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If all default rails already exist, the rail gap prompt is never triggered."""
        _make_project_with_stories(tmp_path)
        for rail in PAIRMODE_DEFAULT_RAILS["generic"]:
            (tmp_path / "docs" / "stories" / rail).mkdir(parents=True)

        prompt_calls: list[str] = []
        import skills.pairmode.scripts.sync as sync_mod

        original_confirm = sync_mod.click.confirm

        def tracking_confirm(text: str, **kw):
            if "Add rail" in text:
                prompt_calls.append(text)
            return False

        monkeypatch.setattr(sync_mod.click, "confirm", tracking_confirm)

        sync_project(tmp_path, yes=False)

        assert prompt_calls == [], (
            f"Should not prompt for rails that already exist, got prompts: {prompt_calls}"
        )
