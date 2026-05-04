#!/usr/bin/env python3
"""SessionStart hook — injects pairmode context into Claude's session."""
import json
import sys
from pathlib import Path


def _pipe_active(pipe_path: str) -> bool:
    return bool(pipe_path) and Path(pipe_path).exists()


def main() -> None:
    state_path = Path(".companion/state.json")
    if not state_path.exists():
        return

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    pairmode_version = state.get("pairmode_version")
    if not pairmode_version:
        return  # not a pairmode repo; emit nothing

    lines: list[str] = [f"Pairmode v{pairmode_version} is active in this repo."]

    # Current story
    story = state.get("current_story")
    if isinstance(story, dict):
        sid = story.get("id", "")
        title = story.get("title", "")
        status = story.get("status", "")
        lines.append(f"Current story: {sid} — {title} [{status}]")
    else:
        lines.append("No active story. Set one with: story_context.py --set RAIL-NNN")

    # Loaded modules
    modules = state.get("last_loaded_modules", [])
    if modules:
        lines.append(f"Loaded modules: {', '.join(modules)}")

    # Sidebar
    pipe_path = state.get("pipe_path", "")
    if _pipe_active(pipe_path):
        lines.append(f"Companion sidebar: active (pipe: {pipe_path})")
    else:
        project_dir = Path(".").resolve()
        anchor_root = Path(__file__).resolve().parent.parent
        start_sh = anchor_root / "skills" / "companion" / "scripts" / "start_sidebar.sh"
        sidebar_log = project_dir / ".companion" / "sidebar.log"
        lines.append("Companion sidebar: not detected")
        lines.append("  To start (macOS / desktop Linux):")
        lines.append(f"    bash {start_sh}")
        if sidebar_log.exists():
            lines.append("  If already running in background, attach with:")
            lines.append(f"    tail -f {sidebar_log}")

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }))


if __name__ == "__main__":
    main()
