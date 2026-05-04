"""
phase_new.py — Lazy phase scaffolding for pairmode projects.

Creates a new per-phase prompt file and updates docs/phases/index.md.
Running it twice with the same phase ID is idempotent (warns, does not overwrite).
"""

from __future__ import annotations

import glob as _glob
import json
import re
import sys
from pathlib import Path

# Insert anchor repo root and scripts dir so sibling imports work when run as CLI
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import click
import jinja2

from schema_validator import _parse_frontmatter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_project_name(project_dir: Path) -> str:
    """Read project_name from pairmode_context.json, falling back to 'project'."""
    ctx_path = project_dir / ".companion" / "pairmode_context.json"
    try:
        return json.loads(ctx_path.read_text()).get("project_name", "project")
    except Exception:
        return "project"


def _load_env() -> jinja2.Environment:
    """Return a Jinja2 environment pointing at the canonical templates dir."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        keep_trailing_newline=True,
    )


def _read_phase_title(phase_file: Path, phase_id: int) -> str:
    """Extract the phase title from an existing phase file.

    Tries to match a ``# Phase N: <title>`` heading first, then falls back to
    ``### Story`` heading extraction.  If nothing matches, returns the generic
    fallback ``"Phase N"``.
    """
    try:
        text = phase_file.read_text(encoding="utf-8")
    except OSError:
        return f"Phase {phase_id}"

    # Try: # <project> — Phase N: <title>  OR  # Phase N: <title>
    m = re.search(r"#\s+.*Phase\s+\d+[:\s]+(.+)", text)
    if m:
        return m.group(1).strip()

    # Fallback
    return f"Phase {phase_id}"


def _detect_active_era(project_dir: Path) -> str | None:
    """Scan docs/eras/*.md for active era(s). Return era id or None."""
    eras_dir = project_dir / "docs" / "eras"
    if not eras_dir.is_dir():
        return None

    era_files = sorted(_glob.glob(str(eras_dir / "*.md")))
    active: list[tuple[str, str]] = []  # list of (filename, era_id)

    for era_path_str in era_files:
        era_path = Path(era_path_str)
        try:
            text = era_path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        if fm is None:
            continue
        if fm.get("status") == "active":
            era_id = fm.get("id", "")
            active.append((era_path.name, era_id))

    if not active:
        return None
    if len(active) == 1:
        return active[0][1]

    # Multiple active eras: warn, use highest ID (last in sorted order)
    click.echo(
        f"Warning: {len(active)} active eras found. Using the most recently created.",
        err=False,
    )
    # sorted by filename which starts with NNN-; last entry has highest ID
    return active[-1][1]


def _update_era_phases_table(project_dir: Path, era_id: str, phase_id: int, phase_title: str) -> None:
    """Append a row to the Phases table in the era's .md file."""
    eras_dir = project_dir / "docs" / "eras"
    if not eras_dir.is_dir():
        return

    # Find the era file by matching its id frontmatter field
    era_files = sorted(_glob.glob(str(eras_dir / "*.md")))
    target_file: Path | None = None
    for era_path_str in era_files:
        era_path = Path(era_path_str)
        try:
            text = era_path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        if fm is None:
            continue
        if fm.get("id") == era_id:
            target_file = era_path
            break

    if target_file is None:
        return

    content = target_file.read_text(encoding="utf-8")
    # Find the Phases table and append a row
    # Table row format: | NNN | Phase title | Status |
    row = f"| {phase_id} | {phase_title} | planned |"
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []
    in_phases_section = False
    in_phases_table = False
    inserted = False

    for line in lines:
        new_lines.append(line)
        stripped = line.strip()

        if stripped == "## Phases":
            in_phases_section = True
            continue

        if in_phases_section and not in_phases_table:
            if stripped.startswith("|"):
                in_phases_table = True
            continue

        if in_phases_table and not inserted:
            if not stripped.startswith("|"):
                # Left the table — insert before this line
                new_lines.insert(-1, row + "\n")
                inserted = True

    if not inserted:
        # Table runs to end of file or we're still in it
        if in_phases_table:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(row + "\n")

    target_file.write_text("".join(new_lines), encoding="utf-8")


def _append_index_row(index_path: Path, phase_id: int, phase_title: str) -> None:
    """Append a new row to the phases table in an existing index.md."""
    content = index_path.read_text(encoding="utf-8")
    row = f"| {phase_id} | {phase_title} | planned | [phase-{phase_id}.md](phase-{phase_id}.md) |"

    # Find the end of the table and append
    lines = content.splitlines(keepends=True)
    new_lines = []
    table_found = False
    inserted = False

    for line in lines:
        new_lines.append(line)
        # Detect table rows (lines starting with |)
        if line.startswith("|") and not inserted:
            table_found = True
        elif table_found and not line.startswith("|") and not inserted:
            # We just left the table — insert before this blank line
            new_lines.insert(-1, row + "\n")
            inserted = True

    if not inserted:
        # Table runs to end of file
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(row + "\n")

    index_path.write_text("".join(new_lines), encoding="utf-8")


def _create_index(index_path: Path, phase_id: int, phase_title: str, project_name: str = "project") -> None:
    """Create a brand-new index.md from the index template."""
    env = _load_env()
    tmpl = env.get_template("docs/phases/index.md.j2")
    phases = [
        {
            "id": phase_id,
            "title": phase_title,
            "status": "planned",
            "file": f"phase-{phase_id}.md",
        }
    ]
    content = tmpl.render(project_name=project_name, phases=phases)
    index_path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command("phase_new")
@click.option(
    "--project-dir",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False),
    help="Root directory of the target project.",
)
@click.option(
    "--phase-id",
    required=True,
    type=int,
    help="Integer phase number (e.g. 3).",
)
@click.option(
    "--title",
    default=None,
    help="Phase title. Prompted if omitted.",
)
@click.option(
    "--goal",
    default=None,
    help="Phase goal. Prompted if omitted (blank is acceptable).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would be written without writing any files.",
)
def phase_new(
    project_dir: str,
    phase_id: int,
    title: str | None,
    goal: str | None,
    dry_run: bool,
) -> None:
    """Create a new phase-N.md scaffold and update docs/phases/index.md."""
    project_path = Path(project_dir).resolve()

    if not project_path.is_dir() or len(project_path.parts) < 3:
        click.echo("Error: --project-dir is too shallow or not a directory.", err=True)
        raise SystemExit(1)

    phases_dir = project_path / "docs" / "phases"

    # 1. Ensure docs/phases/ exists (skip in dry-run)
    if not dry_run:
        phases_dir.mkdir(parents=True, exist_ok=True)

    # 2. Idempotency check
    phase_file = phases_dir / f"phase-{phase_id}.md"
    if phase_file.exists():
        click.echo(
            f"Warning: phase-{phase_id}.md already exists. Skipping (idempotent).",
            err=False,
        )
        return

    # 3. Prompt for missing values
    if title is None:
        title = click.prompt(f"Phase {phase_id} title", default="")
    if goal is None:
        goal = click.prompt(f"Phase {phase_id} goal (blank is OK)", default="")

    # 4. Load project_name from context
    project_name = _load_project_name(project_path)

    # 5. Detect active era
    era_id = _detect_active_era(project_path)

    # 6. Determine prev_phase
    prev_phase = None
    if phase_id > 1:
        prev_file = phases_dir / f"phase-{phase_id - 1}.md"
        if prev_file.exists():
            prev_title = _read_phase_title(prev_file, phase_id - 1)
            prev_phase = {"id": phase_id - 1, "title": prev_title}

    # 7. Render phase-N.md
    env = _load_env()
    phase_tmpl = env.get_template("docs/phases/phase.md.j2")
    rendered = phase_tmpl.render(
        project_name=project_name,
        phase_id=phase_id,
        phase_title=title,
        goal=goal,
        prev_phase=prev_phase,
        next_phase=None,
        stories=[],
        era_id=era_id,
    )

    # 8. Write or preview phase-N.md
    if dry_run:
        rel = phase_file.relative_to(project_path)
        click.echo(f"[DRY RUN] Would write: {rel}")
        click.echo("--- content preview (first 20 lines) ---")
        for line in rendered.splitlines()[:20]:
            click.echo(line)
    else:
        phase_file.write_text(rendered, encoding="utf-8")
        click.echo(f"Created {phase_file.relative_to(project_path)}")
        # Update era Phases table if an active era was found
        if era_id:
            _update_era_phases_table(project_path, era_id, phase_id, title or f"Phase {phase_id}")

    # 9. Update or create index.md
    index_path = phases_dir / "index.md"
    if index_path.exists():
        if dry_run:
            rel = index_path.relative_to(project_path)
            click.echo(f"[DRY RUN] Would update: {rel}")
        else:
            _append_index_row(index_path, phase_id, title or f"Phase {phase_id}")
            click.echo(f"Updated {index_path.relative_to(project_path)}")
    else:
        if dry_run:
            # Render index for preview
            index_env = _load_env()
            index_tmpl = index_env.get_template("docs/phases/index.md.j2")
            phases_list = [
                {
                    "id": phase_id,
                    "title": title or f"Phase {phase_id}",
                    "status": "planned",
                    "file": f"phase-{phase_id}.md",
                }
            ]
            index_rendered = index_tmpl.render(project_name=project_name, phases=phases_list)
            rel = index_path.relative_to(project_path)
            click.echo(f"[DRY RUN] Would write: {rel}")
            click.echo("--- content preview (first 20 lines) ---")
            for line in index_rendered.splitlines()[:20]:
                click.echo(line)
        else:
            _create_index(index_path, phase_id, title or f"Phase {phase_id}", project_name)
            click.echo(f"Created {index_path.relative_to(project_path)}")


if __name__ == "__main__":
    phase_new()
