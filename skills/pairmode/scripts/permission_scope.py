"""
permission_scope.py — Story-scoped allow rules lifecycle for .claude/settings.local.json.

Provides two public functions:
  write_story_permissions(story_path, project_dir)
      Read story frontmatter; add Edit/Write (and Read for touches) allow rules to
      .claude/settings.local.json; record added rules in .claude/story_scope.json.

  clear_story_permissions(project_dir)
      Read .claude/story_scope.json; remove the recorded rules from
      .claude/settings.local.json; delete story_scope.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).parent))

import schema_validator as _sv

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def write_story_permissions(story_path: _Path, project_dir: _Path) -> None:
    """Read story primary_files + touches; add Edit/Write allow rules to
    .claude/settings.local.json.  Record added rules in .claude/story_scope.json."""
    import sys as _sys

    text = story_path.read_text(encoding="utf-8")
    fm = _sv._parse_frontmatter(text)

    if fm is None:
        _sys.stderr.write(
            f"permission_scope: warning: no frontmatter found in {story_path}; "
            "writing zero rules.\n"
        )
        return

    primary_files: list[str] = fm.get("primary_files") or []
    touches: list[str] = fm.get("touches") or []

    if not primary_files and not touches:
        _sys.stderr.write(
            "permission_scope: warning: story has no primary_files or touches; "
            "writing zero rules.\n"
        )
        return

    # Deduplicate while preserving order
    seen: set[str] = set()
    new_rules: list[str] = []

    for raw in primary_files:
        safe = _safe_path(raw, project_dir)
        if safe is None:
            _sys.stderr.write(
                f"permission_scope: warning: path {raw!r} resolves outside project_dir; "
                "skipping.\n"
            )
            continue
        if raw not in seen:
            seen.add(raw)
            new_rules.append(f"Edit({raw})")
            new_rules.append(f"Write({raw})")

    for raw in touches:
        safe = _safe_path(raw, project_dir)
        if safe is None:
            _sys.stderr.write(
                f"permission_scope: warning: path {raw!r} resolves outside project_dir; "
                "skipping.\n"
            )
            continue
        if raw not in seen:
            seen.add(raw)
            new_rules.append(f"Edit({raw})")
            new_rules.append(f"Write({raw})")
        # Read rule for touches (deduplicate the Read rule itself too)
        read_rule = f"Read({raw})"
        if read_rule not in new_rules:
            new_rules.append(read_rule)

    if not new_rules:
        _sys.stderr.write(
            "permission_scope: warning: all paths were unsafe or skipped; "
            "writing zero rules.\n"
        )
        return

    settings_path = project_dir / ".claude" / "settings.local.json"
    settings = _read_json(settings_path, default={})

    permissions = settings.setdefault("permissions", {})
    allow: list[str] = permissions.setdefault("allow", [])

    existing_set = set(allow)
    actually_added: list[str] = []
    for rule in new_rules:
        if rule not in existing_set:
            allow.append(rule)
            existing_set.add(rule)
            actually_added.append(rule)

    _write_json(settings_path, settings)

    story_id: str = fm.get("id", "")
    scope_path = project_dir / ".claude" / "story_scope.json"
    _write_json(scope_path, {"story_id": story_id, "added_rules": actually_added})

    _ensure_gitignore(project_dir, ".claude/story_scope.json")


def clear_story_permissions(project_dir: _Path) -> None:
    """Read .claude/story_scope.json; remove the recorded rules from
    .claude/settings.local.json; delete story_scope.json."""
    scope_path = project_dir / ".claude" / "story_scope.json"
    if not scope_path.exists():
        return

    scope = _read_json(scope_path, default={})
    added_rules: list[str] = scope.get("added_rules", [])

    settings_path = project_dir / ".claude" / "settings.local.json"
    settings = _read_json(settings_path, default={})

    permissions = settings.get("permissions", {})
    allow: list[str] = permissions.get("allow", [])

    rules_to_remove = set(added_rules)
    new_allow = [r for r in allow if r not in rules_to_remove]

    if "permissions" in settings:
        settings["permissions"]["allow"] = new_allow
    _write_json(settings_path, settings)

    scope_path.unlink()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_path(raw: str, project_dir: _Path) -> _Path | None:
    """Resolve raw path string relative to project_dir.
    Return the resolved Path if it stays within project_dir, else None."""
    try:
        candidate = (project_dir.resolve() / raw).resolve()
        candidate.relative_to(project_dir.resolve())
        return candidate
    except (ValueError, OSError):
        return None


def _read_json(path: _Path, *, default: object) -> dict:
    if not path.exists():
        return default  # type: ignore[return-value]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default  # type: ignore[return-value]
        return data
    except (json.JSONDecodeError, OSError):
        return default  # type: ignore[return-value]


def _write_json(path: _Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _ensure_gitignore(project_dir: _Path, entry: str) -> None:
    gitignore = project_dir / ".gitignore"
    if gitignore.exists():
        lines = gitignore.read_text(encoding="utf-8").splitlines()
        if entry in lines:
            return
        gitignore.write_text(
            gitignore.read_text(encoding="utf-8").rstrip("\n") + f"\n{entry}\n",
            encoding="utf-8",
        )
    else:
        gitignore.write_text(f"{entry}\n", encoding="utf-8")
