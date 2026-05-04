"""Tests for skills/pairmode/scripts/permission_scope.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure the scripts directory is on sys.path so the module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"))

import permission_scope as ps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STORY_TEMPLATE = """\
---
id: RAIL-001
rail: RAIL
title: Test story
status: planned
phase: 1
primary_files:
  - src/foo.py
  - src/bar.py
touches:
  - docs/readme.md
---

Story body here.
"""

STORY_NO_FILES = """\
---
id: RAIL-002
rail: RAIL
title: Empty story
status: draft
phase: 1
primary_files:
touches:
---
"""


def _write_story(tmp_path: Path, content: str = STORY_TEMPLATE) -> Path:
    story = tmp_path / "story.md"
    story.write_text(content)
    return story


def _read_settings(tmp_path: Path) -> dict:
    p = tmp_path / ".claude" / "settings.local.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def _read_scope(tmp_path: Path) -> dict | None:
    p = tmp_path / ".claude" / "story_scope.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


# ---------------------------------------------------------------------------
# Tests — write_story_permissions
# ---------------------------------------------------------------------------


def test_write_adds_edit_write_for_primary_files(tmp_path):
    story = _write_story(tmp_path)
    ps.write_story_permissions(story, tmp_path)

    settings = _read_settings(tmp_path)
    allow = settings["permissions"]["allow"]
    assert "Edit(src/foo.py)" in allow
    assert "Write(src/foo.py)" in allow
    assert "Edit(src/bar.py)" in allow
    assert "Write(src/bar.py)" in allow


def test_write_adds_read_for_touches(tmp_path):
    story = _write_story(tmp_path)
    ps.write_story_permissions(story, tmp_path)

    allow = _read_settings(tmp_path)["permissions"]["allow"]
    assert "Read(docs/readme.md)" in allow
    # touches also get Edit and Write
    assert "Edit(docs/readme.md)" in allow
    assert "Write(docs/readme.md)" in allow


def test_write_is_idempotent(tmp_path):
    story = _write_story(tmp_path)
    ps.write_story_permissions(story, tmp_path)
    ps.write_story_permissions(story, tmp_path)

    allow = _read_settings(tmp_path)["permissions"]["allow"]
    # No duplicate rules
    assert len(allow) == len(set(allow))


def test_write_merges_with_existing_rules(tmp_path):
    # Pre-populate settings.local.json with an unrelated rule
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings = {"permissions": {"allow": ["Read(existing/file.py)"]}}
    (claude_dir / "settings.local.json").write_text(json.dumps(settings))

    story = _write_story(tmp_path)
    ps.write_story_permissions(story, tmp_path)

    allow = _read_settings(tmp_path)["permissions"]["allow"]
    assert "Read(existing/file.py)" in allow
    assert "Edit(src/foo.py)" in allow


def test_write_creates_settings_from_scratch(tmp_path):
    # No .claude dir at all
    story = _write_story(tmp_path)
    ps.write_story_permissions(story, tmp_path)

    settings = _read_settings(tmp_path)
    assert "permissions" in settings
    assert isinstance(settings["permissions"]["allow"], list)
    assert len(settings["permissions"]["allow"]) > 0


def test_write_creates_story_scope_json(tmp_path):
    story = _write_story(tmp_path)
    ps.write_story_permissions(story, tmp_path)

    scope = _read_scope(tmp_path)
    assert scope is not None
    assert scope["story_id"] == "RAIL-001"
    assert isinstance(scope["added_rules"], list)
    assert "Edit(src/foo.py)" in scope["added_rules"]


def test_write_empty_story_emits_warning_no_crash(tmp_path, capsys):
    story = _write_story(tmp_path, STORY_NO_FILES)
    ps.write_story_permissions(story, tmp_path)

    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
    # No story_scope.json written
    assert _read_scope(tmp_path) is None


# ---------------------------------------------------------------------------
# Tests — clear_story_permissions
# ---------------------------------------------------------------------------


def test_clear_removes_story_rules(tmp_path):
    # Pre-populate with an existing rule + story rules
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings = {"permissions": {"allow": ["Read(existing/file.py)", "Edit(src/foo.py)"]}}
    (claude_dir / "settings.local.json").write_text(json.dumps(settings))
    scope = {"story_id": "RAIL-001", "added_rules": ["Edit(src/foo.py)"]}
    (claude_dir / "story_scope.json").write_text(json.dumps(scope))

    ps.clear_story_permissions(tmp_path)

    allow = _read_settings(tmp_path)["permissions"]["allow"]
    assert "Edit(src/foo.py)" not in allow
    assert "Read(existing/file.py)" in allow


def test_clear_leaves_existing_rules_intact(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings = {"permissions": {"allow": ["Read(keep.py)", "Edit(remove.py)"]}}
    (claude_dir / "settings.local.json").write_text(json.dumps(settings))
    scope = {"story_id": "RAIL-001", "added_rules": ["Edit(remove.py)"]}
    (claude_dir / "story_scope.json").write_text(json.dumps(scope))

    ps.clear_story_permissions(tmp_path)

    allow = _read_settings(tmp_path)["permissions"]["allow"]
    assert "Read(keep.py)" in allow
    assert "Edit(remove.py)" not in allow


def test_clear_no_scope_file_is_noop(tmp_path):
    """clear_story_permissions with no story_scope.json: no-op, no error."""
    ps.clear_story_permissions(tmp_path)  # should not raise


def test_clear_deletes_scope_file(tmp_path):
    story = _write_story(tmp_path)
    ps.write_story_permissions(story, tmp_path)

    assert _read_scope(tmp_path) is not None
    ps.clear_story_permissions(tmp_path)
    assert _read_scope(tmp_path) is None


def test_roundtrip_write_then_clear(tmp_path):
    """Full roundtrip: write adds rules; clear removes them leaving no extra rules."""
    # Pre-existing rule
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings = {"permissions": {"allow": ["Read(preexisting.py)"]}}
    (claude_dir / "settings.local.json").write_text(json.dumps(settings))

    story = _write_story(tmp_path)
    ps.write_story_permissions(story, tmp_path)
    ps.clear_story_permissions(tmp_path)

    allow = _read_settings(tmp_path)["permissions"]["allow"]
    assert allow == ["Read(preexisting.py)"]
    assert _read_scope(tmp_path) is None


def test_gitignore_entry_added(tmp_path):
    story = _write_story(tmp_path)
    ps.write_story_permissions(story, tmp_path)

    gitignore = (tmp_path / ".gitignore").read_text()
    assert ".claude/story_scope.json" in gitignore


def test_gitignore_not_duplicated(tmp_path):
    story = _write_story(tmp_path)
    ps.write_story_permissions(story, tmp_path)
    ps.write_story_permissions(story, tmp_path)  # second call

    gitignore = (tmp_path / ".gitignore").read_text()
    assert gitignore.count(".claude/story_scope.json") == 1


# ---------------------------------------------------------------------------
# Tests — path containment guard (_safe_path / write_story_permissions)
# ---------------------------------------------------------------------------


def _make_story(tmp_path: Path, primary_files: list, touches: list | None = None) -> Path:
    touches_yaml = ""
    if touches:
        touches_yaml = "touches:\n" + "".join(f"  - {t}\n" for t in touches)
    else:
        touches_yaml = "touches:\n"
    primary_yaml = "primary_files:\n" + "".join(f"  - {p}\n" for p in primary_files)
    content = f"""\
---
id: RAIL-099
rail: RAIL
title: Guard test
status: planned
phase: 1
{primary_yaml}{touches_yaml}---

Body.
"""
    story = tmp_path / "story.md"
    story.write_text(content)
    return story


def test_traversal_path_in_primary_skipped(tmp_path, capsys):
    story = _make_story(tmp_path, primary_files=["../../etc/passwd"])
    ps.write_story_permissions(story, tmp_path)

    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()

    settings = _read_settings(tmp_path)
    allow = settings.get("permissions", {}).get("allow", [])
    assert not any("etc/passwd" in r for r in allow)


def test_absolute_path_in_primary_skipped(tmp_path, capsys):
    story = _make_story(tmp_path, primary_files=["/etc/passwd"])
    ps.write_story_permissions(story, tmp_path)

    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()

    settings = _read_settings(tmp_path)
    allow = settings.get("permissions", {}).get("allow", [])
    assert not any("etc/passwd" in r for r in allow)


def test_valid_path_alongside_traversal(tmp_path, capsys):
    story = _make_story(tmp_path, primary_files=["../../etc/passwd", "src/good.py"])
    ps.write_story_permissions(story, tmp_path)

    settings = _read_settings(tmp_path)
    allow = settings.get("permissions", {}).get("allow", [])
    # Valid path should produce rules
    assert "Edit(src/good.py)" in allow
    assert "Write(src/good.py)" in allow
    # Traversal path should not appear
    assert not any("etc/passwd" in r for r in allow)


def test_all_traversal_no_scope_file_created(tmp_path, capsys):
    story = _make_story(tmp_path, primary_files=["../../etc/passwd", "/etc/hosts"])
    ps.write_story_permissions(story, tmp_path)

    # No story_scope.json should be created
    assert _read_scope(tmp_path) is None


# ---------------------------------------------------------------------------
# Tests — _read_json non-dict guard
# ---------------------------------------------------------------------------


def test_read_json_list_returns_default(tmp_path):
    p = tmp_path / "data.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    result = ps._read_json(p, default={})
    assert result == {}


def test_read_json_string_returns_default(tmp_path):
    p = tmp_path / "data.json"
    p.write_text('"string"', encoding="utf-8")
    result = ps._read_json(p, default={})
    assert result == {}


def test_read_json_null_returns_default(tmp_path):
    p = tmp_path / "data.json"
    p.write_text("null", encoding="utf-8")
    result = ps._read_json(p, default={})
    assert result == {}


def test_read_json_valid_dict_returns_dict(tmp_path):
    p = tmp_path / "data.json"
    data = {"key": "value", "num": 42}
    p.write_text(json.dumps(data), encoding="utf-8")
    result = ps._read_json(p, default={})
    assert result == data
