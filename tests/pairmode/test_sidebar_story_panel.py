"""Tests for the story context panel rendering logic in sidebar.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the anchor root is on sys.path so sidebar.py's _ANCHOR_ROOT insertion
# (and our own imports from skills/) work correctly.
ANCHOR_ROOT = Path(__file__).parent.parent.parent
if str(ANCHOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ANCHOR_ROOT))

# sidebar.py lives in skills/companion/scripts/.  It uses a script-block header
# that uv run processes but plain import ignores. We import the module directly;
# the Rich dependency must already be available (it is listed in sidebar.py's
# inline dependency block and installed in the uv environment).
SIDEBAR_DIR = ANCHOR_ROOT / "skills" / "companion" / "scripts"
if str(SIDEBAR_DIR) not in sys.path:
    sys.path.insert(0, str(SIDEBAR_DIR))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "sidebar",
    str(SIDEBAR_DIR / "sidebar.py"),
)
sidebar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sidebar)  # type: ignore[union-attr]

build_story_panel = sidebar.build_story_panel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def panel_text(panel) -> str:
    """Render a Rich Panel to plain text (strip markup tags)."""
    from rich.console import Console
    from io import StringIO

    buf = StringIO()
    console = Console(file=buf, highlight=False, markup=True, width=60)
    console.print(panel)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildStoryPanel:
    def test_returns_panel_object(self):
        from rich.panel import Panel

        story = {"id": "2.3", "title": "Deny list deriver"}
        result = build_story_panel(story)
        assert isinstance(result, Panel)

    def test_panel_title_is_story(self):
        story = {"id": "2.3", "title": "Deny list deriver"}
        panel = build_story_panel(story)
        # Panel title is a renderable; convert to string for check
        title_str = str(panel.title)
        assert "Story" in title_str

    def test_panel_contains_story_id(self):
        story = {"id": "2.3", "title": "Deny list deriver"}
        text = panel_text(build_story_panel(story))
        assert "2.3" in text

    def test_panel_contains_story_title(self):
        story = {"id": "2.3", "title": "Deny list deriver"}
        text = panel_text(build_story_panel(story))
        assert "Deny list deriver" in text

    def test_panel_label_format_with_title(self):
        story = {"id": "5.2", "title": "Story context panel"}
        text = panel_text(build_story_panel(story))
        # Should contain "Story 5.2" and the title
        assert "Story 5.2" in text
        assert "Story context panel" in text

    def test_panel_label_format_without_title(self):
        story = {"id": "3.1"}
        text = panel_text(build_story_panel(story))
        assert "Story 3.1" in text

    def test_no_title_key_still_renders(self):
        story = {"id": "1.0"}
        # Should not raise
        panel = build_story_panel(story)
        text = panel_text(panel)
        assert "1.0" in text

    def test_started_time_shown_when_set_at_present(self):
        story = {
            "id": "2.3",
            "title": "Deny list deriver",
            "set_at": "2026-04-20T14:32:00+00:00",
        }
        text = panel_text(build_story_panel(story))
        assert "14:32" in text

    def test_started_label_present_with_set_at(self):
        story = {
            "id": "2.3",
            "title": "Deny list deriver",
            "set_at": "2026-04-20T09:05:00+00:00",
        }
        text = panel_text(build_story_panel(story))
        assert "Started" in text

    def test_started_not_shown_when_set_at_absent(self):
        story = {"id": "2.3", "title": "Deny list deriver"}
        text = panel_text(build_story_panel(story))
        assert "Started" not in text

    def test_set_at_without_timezone_parses_ok(self):
        story = {
            "id": "4.0",
            "set_at": "2026-04-20T08:00:00",
        }
        text = panel_text(build_story_panel(story))
        assert "08:00" in text

    def test_malformed_set_at_falls_back_gracefully(self):
        story = {
            "id": "4.0",
            "set_at": "not-a-date",
        }
        # Should not raise; falls back to raw set_at string
        panel = build_story_panel(story)
        text = panel_text(panel)
        assert "4.0" in text

    def test_em_dash_separator_with_title(self):
        story = {"id": "2.3", "title": "Some title"}
        text = panel_text(build_story_panel(story))
        # The em dash (\u2014) separates id from title
        assert "\u2014" in text or "—" in text
