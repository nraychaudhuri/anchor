"""Tests for skills/pairmode/scripts/story_context.py."""

from __future__ import annotations

import json
import pathlib

import pytest

from skills.pairmode.scripts.story_context import (
    clear_current_story,
    get_current_story,
    is_pairmode_active,
    match_file_to_module,
    read_state,
    set_current_story,
    write_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_companion_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    companion = tmp_path / ".companion"
    companion.mkdir()
    return companion


# ---------------------------------------------------------------------------
# is_pairmode_active
# ---------------------------------------------------------------------------

class TestIsPairmodeActive:
    def test_returns_false_when_deny_rationale_missing(self, tmp_path):
        assert is_pairmode_active(tmp_path) is False

    def test_returns_true_when_deny_rationale_present(self, tmp_path):
        dot_claude = tmp_path / ".claude"
        dot_claude.mkdir()
        (dot_claude / "settings.deny-rationale.json").write_text("{}")
        assert is_pairmode_active(tmp_path) is True

    def test_returns_false_when_dot_claude_missing(self, tmp_path):
        # No .claude directory at all
        assert is_pairmode_active(tmp_path) is False

    def test_returns_false_when_dot_claude_exists_but_file_absent(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        assert is_pairmode_active(tmp_path) is False


# ---------------------------------------------------------------------------
# read_state / write_state
# ---------------------------------------------------------------------------

class TestReadWriteState:
    def test_read_returns_empty_dict_when_no_state_json(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        result = read_state(companion)
        assert result == {}

    def test_read_returns_empty_dict_on_malformed_json(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        (companion / "state.json").write_text("not valid json {{{")
        result = read_state(companion)
        assert result == {}

    def test_write_creates_state_json(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(companion, {"pairmode_version": "1.0"})
        state_path = companion / "state.json"
        assert state_path.exists()
        data = json.loads(state_path.read_text())
        assert data["pairmode_version"] == "1.0"

    def test_read_after_write_round_trip(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        original = {"last_loaded_modules": ["auth", "billing"], "pairmode_version": "2.0"}
        write_state(companion, original)
        result = read_state(companion)
        assert result == original

    def test_write_pretty_prints_json(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(companion, {"k": "v"})
        raw = (companion / "state.json").read_text()
        # Pretty-printed JSON contains newlines
        assert "\n" in raw


# ---------------------------------------------------------------------------
# set_current_story
# ---------------------------------------------------------------------------

class TestSetCurrentStory:
    def test_writes_current_story_with_id(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        state = set_current_story(companion, "2.3")
        assert state["current_story"]["id"] == "2.3"

    def test_writes_current_story_with_title(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        state = set_current_story(companion, "2.3", title="Add denylist deriver")
        assert state["current_story"]["title"] == "Add denylist deriver"

    def test_current_story_without_title_has_no_title_key(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        state = set_current_story(companion, "1.1")
        assert "title" not in state["current_story"]

    def test_set_at_is_iso_timestamp(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        state = set_current_story(companion, "3.0")
        set_at = state["current_story"]["set_at"]
        # Should be parseable as ISO 8601
        from datetime import datetime
        dt = datetime.fromisoformat(set_at)
        assert dt.year >= 2024

    def test_persists_to_disk(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "4.1", title="Some story")
        # Read raw from disk
        raw = json.loads((companion / "state.json").read_text())
        assert raw["current_story"]["id"] == "4.1"
        assert raw["current_story"]["title"] == "Some story"

    def test_preserves_existing_state_keys(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        # Pre-populate state.json with existing data
        write_state(companion, {"last_loaded_modules": ["auth"], "pairmode_version": "1.0"})
        state = set_current_story(companion, "2.1")
        assert state["last_loaded_modules"] == ["auth"]
        assert state["pairmode_version"] == "1.0"
        assert state["current_story"]["id"] == "2.1"

    def test_overwrites_previous_current_story(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "1.0")
        state = set_current_story(companion, "2.0", title="New story")
        assert state["current_story"]["id"] == "2.0"
        assert state["current_story"]["title"] == "New story"

    def test_creates_companion_dir_state_when_no_prior_state_json(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        # No state.json yet
        assert not (companion / "state.json").exists()
        set_current_story(companion, "5.1")
        assert (companion / "state.json").exists()


# ---------------------------------------------------------------------------
# get_current_story
# ---------------------------------------------------------------------------

class TestGetCurrentStory:
    def test_returns_none_when_no_state_json(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        assert get_current_story(companion) is None

    def test_returns_none_when_current_story_not_set(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(companion, {"last_loaded_modules": ["auth"]})
        assert get_current_story(companion) is None

    def test_returns_current_story_when_set(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "3.2", title="A story")
        result = get_current_story(companion)
        assert result is not None
        assert result["id"] == "3.2"
        assert result["title"] == "A story"


# ---------------------------------------------------------------------------
# clear_current_story (state.json not modified when story is skipped)
# ---------------------------------------------------------------------------

class TestClearCurrentStory:
    def test_removes_current_story_when_present(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "2.3")
        state = clear_current_story(companion)
        assert "current_story" not in state

    def test_noop_when_current_story_not_set(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(companion, {"last_loaded_modules": ["auth"]})
        state = clear_current_story(companion)
        assert "current_story" not in state
        # Other keys preserved
        assert state["last_loaded_modules"] == ["auth"]

    def test_state_on_disk_has_no_current_story_after_clear(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        set_current_story(companion, "1.0")
        clear_current_story(companion)
        raw = json.loads((companion / "state.json").read_text())
        assert "current_story" not in raw

    def test_skip_does_not_modify_story_field(self, tmp_path):
        """Simulates user skipping story prompt — state.json must not have current_story."""
        companion = make_companion_dir(tmp_path)
        write_state(companion, {"last_loaded_modules": ["billing"]})
        # Simulate skip: do not call set_current_story at all
        raw = json.loads((companion / "state.json").read_text())
        assert "current_story" not in raw
        assert raw["last_loaded_modules"] == ["billing"]


# ---------------------------------------------------------------------------
# Schema round-trip (full current_story schema)
# ---------------------------------------------------------------------------

class TestCurrentStorySchemaRoundTrip:
    def test_full_schema_round_trip(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        state = set_current_story(companion, "2.3", title="Add denylist deriver")
        # Re-read from disk
        reread = read_state(companion)
        story = reread["current_story"]
        assert story["id"] == "2.3"
        assert story["title"] == "Add denylist deriver"
        assert "set_at" in story
        # Verify it can be serialised back to JSON without error
        assert json.dumps(reread)

# ---------------------------------------------------------------------------
# match_file_to_module
# ---------------------------------------------------------------------------

class TestMatchFileToModule:
    def _modules(self):
        return [
            {"name": "auth-and-security", "description": "Auth", "paths": ["src/auth/"]},
            {"name": "decision-ledger", "description": "Ledger", "paths": ["src/ledger/", "lib/ledger/"]},
            {"name": "billing", "description": "Billing", "paths": ["src/billing/"]},
        ]

    def test_returns_module_name_for_exact_prefix_match(self):
        modules = self._modules()
        assert match_file_to_module("src/auth/views.py", modules) == "auth-and-security"

    def test_returns_module_name_for_nested_path(self):
        modules = self._modules()
        assert match_file_to_module("src/ledger/models/account.py", modules) == "decision-ledger"

    def test_returns_module_name_for_second_path_entry(self):
        modules = self._modules()
        assert match_file_to_module("lib/ledger/util.py", modules) == "decision-ledger"

    def test_returns_none_when_no_module_matches(self):
        modules = self._modules()
        assert match_file_to_module("src/unrelated/file.py", modules) is None

    def test_returns_none_for_empty_modules_list(self):
        assert match_file_to_module("src/auth/views.py", []) is None

    def test_returns_none_for_empty_file_path(self):
        modules = self._modules()
        assert match_file_to_module("", modules) is None

    def test_does_not_match_partial_directory_name(self):
        # "src/auth" should NOT match "src/authorize/views.py" if module path is "src/auth/"
        modules = [{"name": "auth-and-security", "paths": ["src/auth/"]}]
        # "src/authorize/views.py" does not start with "src/auth/" — no match
        assert match_file_to_module("src/authorize/views.py", modules) is None

    def test_matches_first_module_when_multiple_could_match(self):
        # Module list order determines which wins — first match wins
        modules = [
            {"name": "first", "paths": ["src/"]},
            {"name": "second", "paths": ["src/auth/"]},
        ]
        assert match_file_to_module("src/auth/views.py", modules) == "first"

    def test_module_with_no_paths_key_is_skipped(self):
        modules = [
            {"name": "no-paths"},
            {"name": "auth-and-security", "paths": ["src/auth/"]},
        ]
        assert match_file_to_module("src/auth/views.py", modules) == "auth-and-security"


    def test_state_json_schema_includes_last_loaded_modules(self, tmp_path):
        companion = make_companion_dir(tmp_path)
        write_state(companion, {
            "last_loaded_modules": ["auth", "billing"],
            "current_story": {
                "id": "2.3",
                "title": "optional title",
                "set_at": "2026-04-20T00:00:00+00:00",
            },
        })
        state = read_state(companion)
        assert state["last_loaded_modules"] == ["auth", "billing"]
        assert state["current_story"]["id"] == "2.3"
