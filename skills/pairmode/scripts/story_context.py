"""story_context.py — Read/write current story context in .companion/state.json.

Provides helpers for:
- Detecting whether a project has pairmode active
  (by checking for .claude/settings.deny-rationale.json)
- Reading and writing the current_story field in .companion/state.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running directly with: uv run python skills/pairmode/scripts/story_context.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


def is_pairmode_active(project_dir: Path) -> bool:
    """Return True if the project has pairmode active.

    Pairmode is considered active when
    .claude/settings.deny-rationale.json exists in the project root.
    """
    return (project_dir / ".claude" / "settings.deny-rationale.json").exists()


def read_state(companion_dir: Path) -> dict:
    """Read .companion/state.json, returning an empty dict if missing or malformed."""
    state_path = companion_dir / "state.json"
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def write_state(companion_dir: Path, state: dict) -> None:
    """Write state dict to .companion/state.json (pretty-printed)."""
    state_path = companion_dir / "state.json"
    state_path.write_text(json.dumps(state, indent=2))


def set_current_story(
    companion_dir: Path,
    story_id: str,
    title: str | None = None,
) -> dict:
    """Write current_story into .companion/state.json.

    Creates state.json if it does not exist.  Existing keys are preserved.
    Returns the updated state dict.

    Args:
        companion_dir: Path to the .companion directory.
        story_id: Story identifier, e.g. "2.3".
        title: Optional human-readable story title.

    Returns:
        The updated state dict (also written to disk).
    """
    state = read_state(companion_dir)
    entry: dict = {
        "id": story_id,
        "set_at": datetime.now(timezone.utc).isoformat(),
    }
    if title is not None:
        entry["title"] = title
    state["current_story"] = entry
    write_state(companion_dir, state)
    return state


def clear_current_story(companion_dir: Path) -> dict:
    """Remove current_story from state.json if present.

    Returns the updated state dict.
    """
    state = read_state(companion_dir)
    state.pop("current_story", None)
    write_state(companion_dir, state)
    return state


def get_current_story(companion_dir: Path) -> dict | None:
    """Return the current_story dict from state.json, or None if not set."""
    state = read_state(companion_dir)
    return state.get("current_story")


def match_file_to_module(file_path: str, modules: list[dict]) -> str | None:
    """Return the module name whose paths contain the given file path as a prefix.

    Iterates over each module entry in *modules* (list of dicts with ``name``
    and ``paths`` keys).  A module matches when any of its ``paths`` entries is
    a prefix of *file_path* (simple string prefix matching, no filesystem ops).

    Args:
        file_path: Absolute or relative path of the file that was changed.
        modules: List of module dicts, each with ``name`` (str) and ``paths``
                 (list[str]) keys, as found in ``.companion/modules.json``.

    Returns:
        The module name if a match is found, otherwise ``None``.
    """
    for module in modules:
        for path in module.get("paths", []):
            if file_path.startswith(path):
                return module.get("name")
    return None
