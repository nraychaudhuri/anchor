"""Lesson capture script for anchor pairmode.

Captures a methodology lesson, appends it to lessons.json, and regenerates LESSONS.md.

Can be used as a library (via capture_lesson()) or as a CLI tool.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Path constants (relative to this file — no hardcoded absolute paths)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent
_PAIRMODE_DIR = _SCRIPTS_DIR.parent
_ANCHOR_ROOT = _PAIRMODE_DIR.parent.parent
_LESSONS_MD = _ANCHOR_ROOT / "lessons" / "LESSONS.md"

# lesson_utils is in the same scripts/ directory
from skills.pairmode.scripts import lesson_utils  # noqa: E402


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def capture_lesson(
    trigger: str,
    problem: str,
    learning: str,
    methodology_change_description: str,
    affects: list[str],
    applies_to: list[str],
    source_project: str = "unknown",
) -> dict:
    """Capture a lesson and persist it.

    Writes the lesson to lessons.json (via lesson_utils), regenerates LESSONS.md,
    and returns the lesson dict that was written.
    """
    data = lesson_utils.load_lessons()

    lesson_id = lesson_utils.next_lesson_id(data.get("lessons", []))
    today = date.today().isoformat()

    lesson = {
        "id": lesson_id,
        "date": today,
        "source_project": source_project,
        "trigger": trigger,
        "problem": problem,
        "learning": learning,
        "methodology_change": {
            "affects": affects,
            "description": methodology_change_description,
        },
        "applies_to": applies_to,
        "status": "captured",
    }

    data["lessons"].append(lesson)
    lesson_utils.save_lessons(data)

    md_content = lesson_utils.generate_lessons_md(data)
    _LESSONS_MD.write_text(md_content, encoding="utf-8")

    return lesson


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option("--trigger", required=True, help="What situation prompted this lesson.")
@click.option("--problem", required=True, help="What went wrong or was inefficient.")
@click.option("--learning", required=True, help="The insight or corrective pattern.")
@click.option(
    "--methodology-change",
    "methodology_change",
    required=True,
    help="How the methodology should change as a result.",
)
@click.option(
    "--affects",
    multiple=True,
    default=["all"],
    show_default=True,
    help="Which components are affected (repeat for multiple).",
)
@click.option(
    "--applies-to",
    "applies_to",
    multiple=True,
    default=["all"],
    show_default=True,
    help="Which project types this lesson applies to (repeat for multiple).",
)
@click.option(
    "--source-project",
    "source_project",
    default="unknown",
    show_default=True,
    help="Name of the project that produced this lesson.",
)
def cli(
    trigger: str,
    problem: str,
    learning: str,
    methodology_change: str,
    affects: tuple[str, ...],
    applies_to: tuple[str, ...],
    source_project: str,
) -> None:
    """Capture a methodology lesson and append it to lessons.json."""
    lesson = capture_lesson(
        trigger=trigger,
        problem=problem,
        learning=learning,
        methodology_change_description=methodology_change,
        affects=list(affects),
        applies_to=list(applies_to),
        source_project=source_project,
    )
    click.echo(f"Lesson captured: {lesson['id']}")
    click.echo(json.dumps(lesson, indent=2))


if __name__ == "__main__":
    cli()
