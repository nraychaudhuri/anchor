"""
story_update.py — Update a story file's status and sync to phase manifests.

Public API:
  update_story_status(story_id, project_dir, status)
      Update the frontmatter status field in the story file.
      Returns the story file Path. Raises FileNotFoundError if not found.
      Raises ValueError for invalid story ID format or project_dir.

  update_phase_story_status(story_id, project_dir, status)
      Find all phase manifests containing story_id in their Stories table.
      Update the status column in each matching row.
      Returns list of updated phase file paths.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Insert anchor repo root so sibling imports work when run as CLI
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import click

# ---------------------------------------------------------------------------
# Story ID parsing
# ---------------------------------------------------------------------------

_STORY_ID_RE = re.compile(r'^([A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*)-(\d+)$')


def _parse_story_id(story_id: str) -> tuple[str, str]:
    """Split 'RAIL-NNN' into (rail, story_id).

    Rail may contain hyphens between upper-case segments (e.g. MULTI-PART-003).
    Uses _STORY_ID_RE to validate the full string before any path construction,
    preventing path-traversal via crafted story IDs like '/etc/passwd-001'.
    Raises ValueError on invalid format.
    """
    m = _STORY_ID_RE.match(story_id)
    if not m:
        raise ValueError(
            f"Invalid story ID format: {story_id!r}. "
            "Expected RAIL-NNN (e.g. BOOTSTRAP-003)."
        )
    rail = m.group(1)
    return rail, story_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def update_story_status(story_id: str, project_dir: Path, status: str) -> Path:
    """Update frontmatter status field in the story file.

    Returns the story file path. Raises FileNotFoundError if not found.
    Raises ValueError for invalid story ID format or unsafe project_dir.
    """
    # Path traversal guard
    resolved = Path(project_dir).resolve()
    if not resolved.is_dir() or len(resolved.parts) < 3:
        raise ValueError(f"project_dir too shallow: {resolved}")

    # Parse story_id to extract rail
    rail, _seq = _parse_story_id(story_id)

    story_path = resolved / "docs" / "stories" / rail / f"{story_id}.md"
    try:
        story_path.resolve().relative_to(resolved)
    except ValueError:
        raise FileNotFoundError(
            f"Story path {story_path} is outside project directory {resolved}"
        )
    if not story_path.exists():
        raise FileNotFoundError(f"Story file not found: {story_path}")

    text = story_path.read_text(encoding="utf-8")

    # Locate frontmatter block (between first --- and second ---)
    # and replace status field within it only
    frontmatter_re = re.compile(r'^(---\s*\n)(.*?)(\n?---\s*(\n|$))', re.DOTALL)
    m = frontmatter_re.match(text)
    if m:
        fm_open = m.group(1)
        fm_body = m.group(2)
        fm_close = m.group(3)
        rest = text[m.end():]

        # Replace status line within frontmatter body only
        new_fm_body = re.sub(
            r'^status:[ \t]*.*$',
            f'status: {status}',
            fm_body,
            flags=re.MULTILINE,
        )
        new_text = fm_open + new_fm_body + fm_close + rest
    else:
        # No frontmatter — just write the file as-is (no-op)
        new_text = text

    story_path.write_text(new_text, encoding="utf-8")
    return story_path


def update_phase_story_status(story_id: str, project_dir: Path, status: str) -> list[Path]:
    """Find all phase manifests containing story_id in their Stories table.

    Update the status column (third pipe-delimited cell) in each matching row.
    Returns list of updated phase file paths.
    """
    resolved = Path(project_dir).resolve()
    phases_dir = resolved / "docs" / "phases"

    if not phases_dir.is_dir():
        return []

    updated: list[Path] = []

    for phase_path in sorted(phases_dir.glob("*.md")):
        text = phase_path.read_text(encoding="utf-8")
        new_text = _update_story_row_in_phase(text, story_id, status)
        if new_text != text:
            phase_path.write_text(new_text, encoding="utf-8")
            updated.append(phase_path)

    return updated


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]+\)')


def _strip_link(cell: str) -> str:
    """Strip Markdown link syntax from a table cell value."""
    return _LINK_RE.sub(r'\1', cell.strip())


def _update_story_row_in_phase(text: str, story_id: str, status: str) -> str:
    """Update the status column in any Stories table row matching story_id.

    Returns the (possibly modified) text.
    """
    # Locate the ## Stories section
    stories_section_re = re.compile(r'^##\s+Stories\s*$', re.MULTILINE)
    section_match = stories_section_re.search(text)
    if not section_match:
        return text

    section_start = section_match.start()
    # Find the next ## heading after the Stories section (or end of file)
    next_section_re = re.compile(r'^##\s+', re.MULTILINE)
    next_m = next_section_re.search(text, section_match.end())
    section_end = next_m.start() if next_m else len(text)

    section_text = text[section_start:section_end]

    # Process table rows line by line
    lines = section_text.splitlines(keepends=True)
    modified_lines: list[str] = []
    header_seen = False
    separator_seen = False

    for line in lines:
        stripped = line.strip()

        if not stripped.startswith('|'):
            modified_lines.append(line)
            continue

        # Parse table row
        parts = stripped.split('|')
        # parts[0] is empty (before first |), parts[-1] may be empty (after last |)
        # Cell values are parts[1], parts[2], ...
        if len(parts) < 3:
            modified_lines.append(line)
            continue

        if not header_seen:
            header_seen = True
            modified_lines.append(line)
            continue

        if not separator_seen:
            separator_seen = True
            modified_lines.append(line)
            continue

        # Data row — check first column
        first_col_raw = parts[1]
        first_col = _strip_link(first_col_raw)

        if first_col == story_id:
            # The row format is: | story_id | title | status |
            # After splitting on '|': parts[0]='', parts[1]=id, parts[2]=title,
            # parts[3]=status, parts[4]='' (trailing)
            # We need at least 4 non-empty-index parts (indices 1,2,3) → len(parts) > 3
            if len(parts) > 3:
                # Preserve original spacing style within the status cell
                old_status_cell = parts[3]
                leading_spaces = len(old_status_cell) - len(old_status_cell.lstrip())
                trailing_spaces = len(old_status_cell) - len(old_status_cell.rstrip())
                new_cell = (
                    ' ' * leading_spaces
                    + status
                    + ' ' * trailing_spaces
                )
                parts[3] = new_cell
            else:
                # Not enough columns — can't update status; skip
                modified_lines.append(line)
                continue

            # Reconstruct the line, preserving original newline character(s)
            newline_suffix = ''
            if line.endswith('\r\n'):
                newline_suffix = '\r\n'
            elif line.endswith('\n'):
                newline_suffix = '\n'
            elif line.endswith('\r'):
                newline_suffix = '\r'

            new_row = '|'.join(parts)
            modified_lines.append(new_row + newline_suffix)
        else:
            modified_lines.append(line)

    new_section = ''.join(modified_lines)
    return text[:section_start] + new_section + text[section_end:]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--story-id",
    required=True,
    help="Story ID to update (e.g. BOOTSTRAP-003).",
)
@click.option(
    "--status",
    required=True,
    type=click.Choice(["draft", "planned", "in-progress", "complete", "backlog"]),
)
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(exists=True, file_okay=False),
)
def story_update(story_id: str, status: str, project_dir: str) -> None:
    """Update a story file's status and sync the change to any phase manifest."""
    try:
        update_story_status(story_id, Path(project_dir), status)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"  Updated {story_id}: status → {status}")

    updated_phases = update_phase_story_status(story_id, Path(project_dir), status)
    if updated_phases:
        for p in updated_phases:
            rel = p.relative_to(Path(project_dir).resolve())
            click.echo(f"  Phase manifest updated: {rel}")
    else:
        click.echo("  no phase manifest found")


if __name__ == "__main__":
    story_update()
