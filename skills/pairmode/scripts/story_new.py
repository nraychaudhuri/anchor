"""
story_new.py — Create a new story file on a named rail.

Creates a properly-formatted story file in docs/stories/<RAIL>/<RAIL>-NNN.md
with the next sequence number.  If the rail directory does not exist, the user
is prompted before it is created.  Optionally appends a row to a phase manifest.
"""

from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

# Insert anchor repo root so sibling imports work when run as CLI
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import click

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_sequence(rail_dir: Path, rail: str) -> int:
    """Return the next sequence number for stories in *rail_dir*."""
    pattern = str(rail_dir / f"{rail}-*.md")
    existing = glob.glob(pattern)
    nums: list[int] = []
    for p in existing:
        m = re.search(rf"{re.escape(rail)}-(\d+)\.md$", Path(p).name)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def _story_frontmatter(story_id: str, rail: str, title: str, phase: str | None) -> str:
    """Return YAML frontmatter block for a new story file."""
    phase_val = phase if phase is not None else "backlog"
    return (
        "---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        f"title: {title}\n"
        f"status: draft\n"
        f"phase: \"{phase_val}\"\n"
        "primary_files:\n"
        "touches:\n"
        "---\n"
    )


def _story_body() -> str:
    """Return the default Markdown body for a new story file."""
    return (
        "\n"
        "## Acceptance criterion\n\n"
        "_(fill in)_\n\n"
        "## Instructions\n\n"
        "_(fill in)_\n\n"
        "## Tests\n\n"
        "_(fill in)_\n"
    )


def _find_era(project_dir: Path) -> Path | None:
    """Return the path to the most-recently active era file, or None."""
    eras_dir = project_dir / "docs" / "eras"
    if not eras_dir.is_dir():
        return None
    candidates = sorted(eras_dir.glob("*.md"))
    if not candidates:
        return None
    return candidates[-1]


def _add_rail_to_era(era_path: Path, rail: str) -> None:
    """Append a row for *rail* to the Rails table in *era_path*."""
    content = era_path.read_text(encoding="utf-8")

    # Try to find an existing Rails table and append to it
    # Table header pattern: | Rail | …
    table_pattern = re.compile(r"(\|.*Rail.*\|.*\n\|[-| ]+\|\n)((\|.*\|\n)*)", re.IGNORECASE)
    m = table_pattern.search(content)
    if m:
        new_row = f"| {rail} | _(fill in primary domain)_ |\n"
        # Check if rail already listed
        if f"| {rail} |" in content:
            return
        insert_pos = m.end()
        new_content = content[:insert_pos] + new_row + content[insert_pos:]
        era_path.write_text(new_content, encoding="utf-8")
    else:
        # Append a new Rails section at the end
        if f"| {rail} |" in content:
            return
        addition = (
            f"\n\n## Rails\n\n"
            f"| Rail | Primary domain |\n"
            f"|------|----------------|\n"
            f"| {rail} | _(fill in primary domain)_ |\n"
        )
        era_path.write_text(content.rstrip() + addition, encoding="utf-8")


def _append_to_phase(project_dir: Path, phase: str, story_id: str, title: str) -> bool:
    """Append a story row to the phase manifest.  Returns True if successful."""
    phase_glob = str(project_dir / "docs" / "phases" / f"{phase}-*.md")
    matches = glob.glob(phase_glob)
    # Also try plain phase-N.md format
    if not matches:
        phase_glob2 = str(project_dir / "docs" / "phases" / f"phase-{phase}.md")
        if Path(phase_glob2).exists():
            matches = [phase_glob2]
    if not matches:
        return False

    phase_path = Path(matches[0])
    content = phase_path.read_text(encoding="utf-8")

    new_row = f"| {story_id} | {title} | draft |"

    # Find a Stories table (## Stories section with a markdown table)
    stories_section = re.search(r"(## Stories\s*\n)(.*?)(\n##|\Z)", content, re.DOTALL)
    if stories_section:
        section_body = stories_section.group(2)
        # Check if there's a table already
        table_m = re.search(r"(\|.*\|\n\|[-| ]+\|\n)((\|.*\|\n)*)", section_body)
        if table_m:
            # Insert after the last row in the table
            table_end = stories_section.start(2) + table_m.end()
            new_content = content[:table_end] + new_row + "\n" + content[table_end:]
            phase_path.write_text(new_content, encoding="utf-8")
            return True
        else:
            # No table yet — add one
            table = (
                "| Story ID | Title | Status |\n"
                "|----------|-------|--------|\n"
                f"{new_row}\n"
            )
            insert_at = stories_section.start(2)
            new_content = content[:insert_at] + table + "\n" + content[insert_at:]
            phase_path.write_text(new_content, encoding="utf-8")
            return True
    else:
        # No ## Stories section — append one
        addition = f"\n\n## Stories\n\n| Story ID | Title | Status |\n|----------|-------|--------|\n{new_row}\n"
        phase_path.write_text(content.rstrip() + addition, encoding="utf-8")
        return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option("--rail", required=True, help="Rail name (e.g. BOOTSTRAP, AUDIT). Case-insensitive; stored uppercase.")
@click.option("--title", required=True, help="Story title.")
@click.option("--phase", default=None, help="Phase number (NNN) to assign this story to.")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Root directory of the target project.",
)
def story_new(rail: str, title: str, phase: str | None, project_dir: str) -> None:
    """Create a new story file on the specified rail."""

    resolved = Path(project_dir).resolve()

    # Path traversal guard
    if not resolved.is_dir() or len(resolved.parts) < 3:
        click.echo(
            f"error: project-dir resolves to a suspicious path: {resolved}",
            err=True,
        )
        sys.exit(1)

    # Normalize rail
    rail = rail.upper()

    rail_dir = resolved / "docs" / "stories" / rail

    # Check / create rail directory
    if not rail_dir.is_dir():
        answer = click.prompt(
            f"Rail {rail} does not exist. Create it? [Y/n]",
            default="Y",
            show_default=False,
        )
        if answer.strip().lower() == "n":
            click.echo("Aborted.")
            sys.exit(0)

        rail_dir.mkdir(parents=True, exist_ok=True)

        # Add rail to current era if one exists
        era_path = _find_era(resolved)
        if era_path is not None:
            _add_rail_to_era(era_path, rail)

    # Determine next sequence number
    seq = _next_sequence(rail_dir, rail)
    story_id = f"{rail}-{seq:03d}"

    # Write story file
    story_path = rail_dir / f"{story_id}.md"
    content = _story_frontmatter(story_id, rail, title, phase) + _story_body()
    story_path.write_text(content, encoding="utf-8")

    click.echo(f"  Created {story_id}: {title}")

    # Validate the newly created story file (non-fatal warnings only)
    from schema_validator import validate_story_file as _vsf  # noqa: PLC0415
    errors = _vsf(story_path)
    for e in errors:
        click.echo(f"  ⚠  validation: {e}", err=True)

    # Optionally append to phase manifest
    if phase is not None:
        added = _append_to_phase(resolved, phase, story_id, title)
        if added:
            click.echo(f"  Added to Phase {phase}")
        else:
            click.echo(
                f"  Warning: could not find phase manifest for phase '{phase}'",
                err=True,
            )


if __name__ == "__main__":
    story_new()
