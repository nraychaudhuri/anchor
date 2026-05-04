"""
reconstruct.py — Refresh docs/reconstruction.md from ideology.md and brief.md.

Reads docs/ideology.md and docs/brief.md from a target project and writes (or
refreshes) docs/reconstruction.md without requiring a full bootstrap.
"""

from __future__ import annotations

import datetime
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
# Ideology parsing (delegates to shared ideology_parser module)
# ---------------------------------------------------------------------------

def parse_ideology(text: str) -> dict:
    """Parse ideology.md text into a context dict for the reconstruction template.

    Delegates to ideology_parser; kept here for backward compatibility with
    any callers that import directly from reconstruct.
    """
    return _ideology_parser.parse_ideology_text(text)


# ---------------------------------------------------------------------------
# brief.md parsing
# ---------------------------------------------------------------------------

def parse_brief(text: str) -> dict[str, str]:
    """Extract reconstruction_what and reconstruction_why from brief.md."""
    top_sections = _ideology_parser._extract_top_level_sections(text)

    what = ""
    why = ""
    for heading, body in top_sections.items():
        heading_lower = heading.lower()
        if "what this project produces" in heading_lower:
            body = body.strip()
            if body and not body.startswith("_(not yet specified"):
                what = body
        elif "why it exists" in heading_lower:
            body = body.strip()
            if body and not body.startswith("_(not yet specified"):
                why = body

    return {"reconstruction_what": what, "reconstruction_why": why}


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def _render_reconstruction(context: dict) -> str:
    """Render the reconstruction.md.j2 template with context."""
    loader = jinja2.FileSystemLoader(str(TEMPLATES_DIR))
    env = jinja2.Environment(
        loader=loader,
        undefined=jinja2.Undefined,
        keep_trailing_newline=True,
    )
    template = env.get_template("docs/reconstruction.md.j2")
    return template.render(**context)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--project-dir",
    type=click.Path(file_okay=False),
    default=".",
    help="Target project directory.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing docs/reconstruction.md without prompting.",
)
def reconstruct(project_dir: str, force: bool) -> None:
    """Refresh docs/reconstruction.md from ideology.md and brief.md."""

    resolved = Path(project_dir).resolve()

    # Path traversal guard (same as bootstrap/audit/sync)
    if not resolved.is_dir() or len(resolved.parts) < 3:
        click.echo(
            f"error: project-dir resolves to a suspicious path: {resolved}",
            err=True,
        )
        sys.exit(1)

    # Check ideology.md exists
    ideology_path = resolved / "docs" / "ideology.md"
    if not ideology_path.exists():
        click.echo(
            "error: docs/ideology.md not found in project. "
            "Run /anchor:pairmode bootstrap first, or create docs/ideology.md manually.",
            err=True,
        )
        sys.exit(1)

    # Parse ideology.md
    ideology_ctx = _ideology_parser.parse_ideology_file(ideology_path)

    # Parse brief.md (optional)
    brief_path = resolved / "docs" / "brief.md"
    brief_ctx = {"reconstruction_what": "", "reconstruction_why": ""}
    if brief_path.exists():
        brief_text = brief_path.read_text(encoding="utf-8")
        brief_ctx = parse_brief(brief_text)

    # Build full render context
    context = {
        **ideology_ctx,
        **brief_ctx,
        "generated_date": datetime.date.today().isoformat(),
    }

    # Check if output already exists
    output_path = resolved / "docs" / "reconstruction.md"
    if output_path.exists() and not force:
        overwrite = click.confirm("docs/reconstruction.md already exists. Overwrite?")
        if not overwrite:
            sys.exit(0)

    # Render and write
    content = _render_reconstruction(context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    click.echo("✓ docs/reconstruction.md written.")


if __name__ == "__main__":
    reconstruct()
