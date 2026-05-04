"""
era_new.py — Create a new era document.

Creates a properly-formatted era document in docs/eras/ with the next
sequential ID (NNN, starting at 001).
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


def _slugify(name: str) -> str:
    """Lowercase, replace spaces and non-alphanumeric with hyphens, collapse multiples."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _next_era_id(eras_dir: Path) -> int:
    """Return the next sequential era ID (1-based)."""
    pattern = str(eras_dir / "*.md")
    existing = glob.glob(pattern)
    nums: list[int] = []
    for p in existing:
        m = re.match(r"(\d{3})-", Path(p).name)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def _era_content(era_id: str, name: str, goal: str) -> str:
    """Return the full content of a new era file."""
    frontmatter = (
        "---\n"
        f'id: "{era_id}"\n'
        f"name: {name}\n"
        "status: active\n"
        "---\n"
    )
    strategic_intent = (
        "\n"
        "## Strategic intent\n"
        "\n"
    )
    if goal:
        strategic_intent += goal + "\n"
    else:
        strategic_intent += "_(fill in)_\n"

    rails_table = (
        "\n"
        "## Rails\n"
        "\n"
        "| Rail | Primary domain |\n"
        "|------|----------------|\n"
    )

    phases_table = (
        "\n"
        "## Phases\n"
        "\n"
        "| Phase | Title | Status |\n"
        "|-------|-------|--------|\n"
    )

    return frontmatter + strategic_intent + rails_table + phases_table


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option("--name", required=True, help="Era name (human-readable, e.g. 'Ideology capture').")
@click.option("--goal", default="", help="Strategic intent paragraph.")
@click.option("--project-dir", default=".", type=click.Path(exists=True, file_okay=False))
def era_new(name: str, goal: str, project_dir: str) -> None:
    """Create a new era document."""

    resolved = Path(project_dir).resolve()

    # Path traversal guard
    if not resolved.is_dir() or len(resolved.parts) < 3:
        click.echo(
            f"error: project-dir resolves to a suspicious path: {resolved}",
            err=True,
        )
        sys.exit(1)

    # Create docs/eras/ if absent
    eras_dir = resolved / "docs" / "eras"
    eras_dir.mkdir(parents=True, exist_ok=True)

    # Determine next ID
    next_id = _next_era_id(eras_dir)
    era_id = f"{next_id:03d}"

    # Build filename
    slug = _slugify(name)
    filename = f"{era_id}-{slug}.md"
    era_path = eras_dir / filename

    # Write era file
    content = _era_content(era_id, name, goal)
    era_path.write_text(content, encoding="utf-8")

    click.echo(f"  Created era {era_id}: {name}")
    click.echo(f"  at docs/eras/{filename}")

    # Validate the newly created era file (non-fatal warnings only)
    from schema_validator import validate_era_file as _vef  # noqa: PLC0415
    errors = _vef(era_path)
    for e in errors:
        click.echo(f"  ⚠  validation: {e}", err=True)


if __name__ == "__main__":
    era_new()
