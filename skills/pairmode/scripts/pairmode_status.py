"""
pairmode_status.py — Print the current pairmode state for a project.

Reads ``.companion/state.json`` for pairmode version, current story, and
loaded modules; reads ``docs/eras/*.md`` frontmatter to identify the
active era; checks whether the configured pipe path exists to determine
sidebar status. If the sidebar is not detected, prints platform-aware
attachment instructions for macOS and desktop Linux.

Designed as a Click CLI; safe to run from any project root.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

# Insert anchor repo root and scripts dir so sibling imports work when run as CLI
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import click

from schema_validator import _parse_frontmatter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Four levels up from this file: skills/pairmode/scripts/pairmode_status.py
#   parents[0] = skills/pairmode/scripts/
#   parents[1] = skills/pairmode/
#   parents[2] = skills/
#   parents[3] = anchor repo root
ANCHOR_ROOT = Path(__file__).resolve().parents[3]

DIVIDER = "─────────────────────────────────────"

NOT_PAIRMODE_MESSAGE = (
    "Not a pairmode repo: .companion/state.json not found.\n"
    "Run /anchor:pairmode bootstrap to initialize."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_state(project_dir: Path) -> dict | None:
    """Read .companion/state.json from *project_dir*; return dict or None."""
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _active_era(project_dir: Path) -> tuple[str, str] | None:
    """Return (era_id, era_name) for the first era with status: active.

    Returns None if no eras directory, no era files, or no era has
    ``status: active`` in its frontmatter.
    """
    eras_dir = project_dir / "docs" / "eras"
    if not eras_dir.is_dir():
        return None

    pattern = str(eras_dir / "*.md")
    for path_str in sorted(glob.glob(pattern)):
        try:
            text = Path(path_str).read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        if not fm:
            continue
        status = fm.get("status")
        if isinstance(status, str) and status.strip() == "active":
            era_id = str(fm.get("id", "")).strip()
            era_name = str(fm.get("name", "")).strip()
            return era_id, era_name
    return None


def _format_story(story: object) -> str:
    """Format the current_story value into a single-line string."""
    if not isinstance(story, dict):
        return "(none set)"
    sid = str(story.get("id", "")).strip()
    if not sid:
        return "(none set)"
    title = str(story.get("title", "")).strip()
    status = str(story.get("status", "")).strip()
    parts = [sid]
    if title:
        parts.append(f"— {title}")
    if status:
        parts.append(f"[{status}]")
    return " ".join(parts)


def _format_modules(modules: object) -> str:
    """Format the last_loaded_modules list."""
    if isinstance(modules, list) and modules:
        return ", ".join(str(m) for m in modules)
    return "(none)"


def _sidebar_lines(state: dict, project_dir: Path) -> list[str]:
    """Return the list of lines describing sidebar status / attachment."""
    pipe_path = state.get("pipe_path", "")
    if isinstance(pipe_path, str) and pipe_path and Path(pipe_path).exists():
        return [
            "Sidebar: active",
            f"  Pipe:  {pipe_path}",
        ]

    start_sh = ANCHOR_ROOT / "skills" / "companion" / "scripts" / "start_sidebar.sh"
    sidebar_log = project_dir / ".companion" / "sidebar.log"
    return [
        "Sidebar: not detected",
        "",
        "To start the companion sidebar:",
        f"  macOS:         bash {start_sh}",
        f"  Linux (KDE):   bash {start_sh}",
        f"  Linux (GNOME): bash {start_sh}",
        "",
        "If the sidebar is already running as a background process:",
        f"  tail -f {sidebar_log}",
        "",
        "The sidebar launch script auto-detects your terminal emulator",
        "(Konsole, GNOME Terminal, Xfce Terminal, macOS Terminal, iTerm2).",
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Project root (defaults to current directory).",
)
def pairmode_status(project_dir: str) -> None:
    """Print pairmode status for the project at --project-dir."""
    project_path = Path(project_dir).resolve()

    state = _read_state(project_path)
    if state is None or not state.get("pairmode_version"):
        click.echo(NOT_PAIRMODE_MESSAGE)
        sys.exit(0)

    pairmode_version = state["pairmode_version"]

    # Era line
    era = _active_era(project_path)
    if era is None:
        era_line = "Era:     (none)"
    else:
        era_id, era_name = era
        if era_name:
            era_line = f"Era:     {era_id} — {era_name}"
        else:
            era_line = f"Era:     {era_id}"

    # Story line
    story_line = f"Story:   {_format_story(state.get('current_story'))}"

    # Modules line
    modules_line = f"Modules: {_format_modules(state.get('last_loaded_modules'))}"

    # Compose the block
    lines: list[str] = [
        f"Pairmode v{pairmode_version}",
        DIVIDER,
        era_line,
        story_line,
        modules_line,
        DIVIDER,
    ]
    lines.extend(_sidebar_lines(state, project_path))

    click.echo("\n".join(lines))


if __name__ == "__main__":
    pairmode_status()
