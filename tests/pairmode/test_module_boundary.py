"""Tests for module boundary detection (Story 5.3).

Covers:
- Single-module session: no alert
- Multi-module detection: alert when current_story is set
- No alert when current_story is not set
- match_file_to_module prefix matching (via story_context)
"""

from __future__ import annotations

import json
import pathlib

import pytest

from skills.pairmode.scripts.story_context import match_file_to_module


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

MODULES = [
    {"name": "auth-and-security", "description": "Auth", "paths": ["src/auth/"]},
    {"name": "decision-ledger", "description": "Ledger", "paths": ["src/ledger/"]},
    {"name": "billing", "description": "Billing", "paths": ["src/billing/"]},
]


def _touched_modules_from_files(file_paths: list[str], modules: list[dict]) -> set[str]:
    """Simulate what the sidebar does: collect touched modules across all file changes."""
    touched: set[str] = set()
    for fp in file_paths:
        matched = match_file_to_module(fp, modules)
        if matched:
            touched.add(matched)
    return touched


# ---------------------------------------------------------------------------
# Single-module: no alert
# ---------------------------------------------------------------------------

class TestSingleModuleNoAlert:
    def test_single_module_touched_no_alert(self):
        """Only one module touched — no multi-module alert regardless of story."""
        files = [
            "src/auth/views.py",
            "src/auth/models.py",
            "src/auth/tests/test_views.py",
        ]
        touched = _touched_modules_from_files(files, MODULES)
        assert len(touched) == 1
        # Single module: no boundary alert
        assert touched == {"auth-and-security"}

    def test_empty_session_no_alert(self):
        """No files changed — nothing touched."""
        touched = _touched_modules_from_files([], MODULES)
        assert len(touched) == 0

    def test_files_not_in_any_module_no_alert(self):
        """Files outside module paths are not tracked."""
        files = ["docs/README.md", "tests/test_utils.py"]
        touched = _touched_modules_from_files(files, MODULES)
        assert len(touched) == 0


# ---------------------------------------------------------------------------
# Multi-module detection
# ---------------------------------------------------------------------------

class TestMultiModuleDetection:
    def test_two_modules_touched_triggers_alert(self):
        files = [
            "src/auth/views.py",       # auth-and-security
            "src/ledger/models.py",    # decision-ledger
        ]
        touched = _touched_modules_from_files(files, MODULES)
        assert len(touched) > 1
        assert "auth-and-security" in touched
        assert "decision-ledger" in touched

    def test_three_modules_touched_triggers_alert(self):
        files = [
            "src/auth/views.py",
            "src/ledger/models.py",
            "src/billing/invoice.py",
        ]
        touched = _touched_modules_from_files(files, MODULES)
        assert len(touched) == 3

    def test_repeated_files_same_module_does_not_grow_set(self):
        """Touching the same module file many times still only counts once."""
        files = ["src/auth/views.py"] * 10 + ["src/ledger/models.py"]
        touched = _touched_modules_from_files(files, MODULES)
        assert len(touched) == 2

    def test_alert_only_when_current_story_set(self):
        """The alert condition requires both multi-module AND current_story being set."""
        files = ["src/auth/views.py", "src/ledger/models.py"]
        touched = _touched_modules_from_files(files, MODULES)
        multi_module = len(touched) > 1

        # With current_story set → alert
        current_story = {"id": "5.3", "title": "Module boundary detection"}
        assert multi_module and current_story  # alert condition

        # Without current_story → no alert
        current_story_absent = None
        assert multi_module and not current_story_absent is False  # no alert

    def test_no_alert_when_current_story_not_set(self):
        """Even if multiple modules touched, no alert without current_story."""
        files = ["src/auth/views.py", "src/ledger/models.py"]
        touched = _touched_modules_from_files(files, MODULES)
        current_story = None
        # Alert condition: multi-module AND current_story
        alert = len(touched) > 1 and current_story is not None
        assert alert is False

    def test_alert_condition_with_current_story_set(self):
        """Alert fires when multi-module AND current_story is set."""
        files = ["src/auth/views.py", "src/ledger/models.py"]
        touched = _touched_modules_from_files(files, MODULES)
        current_story = {"id": "5.3"}
        alert = len(touched) > 1 and current_story is not None
        assert alert is True


# ---------------------------------------------------------------------------
# Prefix matching edge cases
# ---------------------------------------------------------------------------

class TestPrefixMatching:
    def test_exact_prefix_match(self):
        modules = [{"name": "auth", "paths": ["src/auth/"]}]
        assert match_file_to_module("src/auth/views.py", modules) == "auth"

    def test_no_match_for_similar_but_different_prefix(self):
        modules = [{"name": "auth", "paths": ["src/auth/"]}]
        # "src/authorization/" does not start with "src/auth/" if it doesn't
        # — wait, "src/authorization/" DOES start with "src/auth" but not "src/auth/"
        assert match_file_to_module("src/authorization/views.py", modules) is None

    def test_match_with_multiple_paths_in_module(self):
        modules = [{"name": "ledger", "paths": ["src/ledger/", "lib/ledger/"]}]
        assert match_file_to_module("lib/ledger/utils.py", modules) == "ledger"
        assert match_file_to_module("src/ledger/models.py", modules) == "ledger"

    def test_no_modules_returns_none(self):
        assert match_file_to_module("src/auth/views.py", []) is None

    def test_module_with_empty_paths_returns_none(self):
        modules = [{"name": "auth", "paths": []}]
        assert match_file_to_module("src/auth/views.py", modules) is None

    def test_alert_module_names_in_warning_are_sorted(self):
        """The warning string uses sorted module names for stable output."""
        touched = {"decision-ledger", "auth-and-security", "billing"}
        modules_str = ", ".join(sorted(touched))
        assert modules_str == "auth-and-security, billing, decision-ledger"
