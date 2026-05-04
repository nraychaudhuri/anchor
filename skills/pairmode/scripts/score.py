"""
score.py — Render a pre-populated RECONSTRUCTION.md scoring report from the reconstruction brief.

Reads docs/reconstruction.md (the brief) and writes docs/RECONSTRUCTION.md pre-populated
with conviction headings, constraint names, and comparison rubric dimensions extracted
from the brief — ready for the reconstruction agent to fill in.
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import click
import jinja2

import ideology_parser as _ideology_parser

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Root of the reconstructed project.",
)
@click.option(
    "--brief",
    default=None,
    type=click.Path(exists=False, dir_okay=False),
    help="Path to reconstruction.md brief. Defaults to <project-dir>/docs/reconstruction.md.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing docs/RECONSTRUCTION.md without prompting.",
)
def score(project_dir: str, brief: str | None, force: bool) -> None:
    """Render a pre-populated RECONSTRUCTION.md scoring report from the reconstruction brief."""

    resolved = Path(project_dir).resolve()

    # Path traversal guard (same pattern as bootstrap/reconstruct)
    if not resolved.is_dir() or len(resolved.parts) < 3:
        click.echo(
            f"error: project-dir resolves to a suspicious path: {resolved}",
            err=True,
        )
        sys.exit(1)

    # Resolve brief path
    if brief is not None:
        brief_path = Path(brief).resolve()
    else:
        brief_path = resolved / "docs" / "reconstruction.md"

    # If --brief was explicitly supplied, ensure it is within project_dir
    if brief is not None:
        try:
            brief_path.relative_to(resolved)
        except ValueError:
            click.echo(
                f"Error: --brief path must be within the project directory ({resolved})",
                err=True,
            )
            raise SystemExit(1)

    if not brief_path.exists():
        click.echo(
            f"error: brief not found: {brief_path}\n"
            "Run /anchor:pairmode reconstruct first, or pass --brief PATH.",
            err=True,
        )
        sys.exit(1)

    # Parse the reconstruction brief
    context = _ideology_parser.parse_reconstruction_brief(brief_path)

    # Extract project_name from brief heading: # Reconstruction Brief — ProjectName
    brief_text = brief_path.read_text(encoding="utf-8")
    project_name = resolved.name  # fallback
    for line in brief_text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            rest = re.sub(r"^#\s+", "", line)
            # Strip common prefixes like "Reconstruction Brief — "
            rest = re.sub(r"^Reconstruction\s+Brief\s*[—\-–]\s*", "", rest, flags=re.IGNORECASE).strip()
            if rest:
                project_name = rest
            break

    context["project_name"] = project_name
    context["reconstruction_date"] = datetime.date.today().isoformat()

    # Load and render the RECONSTRUCTION.md.j2 template
    template_dir = Path(__file__).parent.parent / "templates"
    loader = jinja2.FileSystemLoader(str(template_dir))
    env = jinja2.Environment(
        loader=loader,
        # Lenient — scoring report generation must not crash on missing brief fields.
        undefined=jinja2.Undefined,
        keep_trailing_newline=True,
    )
    template = env.get_template("RECONSTRUCTION.md.j2")
    rendered = template.render(**context)

    # Determine output path
    output_path = resolved / "docs" / "RECONSTRUCTION.md"

    # Check for existing file
    if output_path.exists() and not force:
        answer = click.prompt(
            "docs/RECONSTRUCTION.md already exists. Overwrite? [y/N] ",
            default="",
            show_default=False,
            prompt_suffix="",
        )
        if answer.strip() not in ("y", "Y"):
            click.echo("Aborted.")
            sys.exit(0)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    click.echo(
        "  Written docs/RECONSTRUCTION.md — fill in scores and justifications,"
        " then share with the original team."
    )


if __name__ == "__main__":
    score()
