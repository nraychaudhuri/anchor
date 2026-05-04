"""Lesson review script for anchor pairmode.

Surfaces captured lessons grouped by affects, proposes template edits,
and writes approved updates to the templates.

Can be used as a library or as a CLI tool:
    uv run python lesson_review.py --approve L001 --approve L002 --reject L003
"""

from __future__ import annotations

from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Path constants (relative to this file — no hardcoded absolute paths)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent
_PAIRMODE_DIR = _SCRIPTS_DIR.parent
_TEMPLATES_DIR = _PAIRMODE_DIR / "templates"
_ANCHOR_ROOT = _PAIRMODE_DIR.parent.parent
_LESSONS_MD = _ANCHOR_ROOT / "lessons" / "LESSONS.md"

from skills.pairmode.scripts import lesson_utils  # noqa: E402

# ---------------------------------------------------------------------------
# Affects → template file mapping
# ---------------------------------------------------------------------------

_AFFECTS_TO_TEMPLATE: dict[str, str] = {
    "reviewer_checklist": "skills/pairmode/templates/CLAUDE.md.j2",
    "builder_agent": "skills/pairmode/templates/agents/builder.md.j2",
    "orchestrator": "skills/pairmode/templates/CLAUDE.build.md.j2",
    "checkpoint_sequence": "skills/pairmode/templates/CLAUDE.build.md.j2",
}

_ALL_TEMPLATE_FILES: list[str] = [
    "skills/pairmode/templates/CLAUDE.md.j2",
    "skills/pairmode/templates/agents/builder.md.j2",
    "skills/pairmode/templates/CLAUDE.build.md.j2",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_reviewable_lessons() -> list[dict]:
    """Return all lessons with status 'captured' or 'reviewed'."""
    data = lesson_utils.load_lessons()
    return [
        lesson
        for lesson in data.get("lessons", [])
        if lesson.get("status") in ("captured", "reviewed")
    ]


def group_lessons_by_affects(lessons: list[dict]) -> dict[str, list[dict]]:
    """Group lesson list by methodology_change.affects values.

    A lesson with affects=["all"] appears under each known affects key.
    A lesson with affects=["reviewer_checklist"] appears only under
    "reviewer_checklist".
    """
    known_affects = list(_AFFECTS_TO_TEMPLATE.keys()) + ["all"]

    groups: dict[str, list[dict]] = {}

    for lesson in lessons:
        affects_list = lesson.get("methodology_change", {}).get("affects", [])
        for affects_value in affects_list:
            if affects_value == "all":
                # Add this lesson to every known group
                for key in _AFFECTS_TO_TEMPLATE:
                    groups.setdefault(key, []).append(lesson)
            else:
                groups.setdefault(affects_value, []).append(lesson)

    return groups


def propose_template_change(lesson: dict) -> list[dict]:
    """Return a list of proposal dicts for the given lesson.

    For affects values other than "all", returns a single-element list.
    For "all", returns one proposal per known template file.

    Each proposal dict:
    {
        "lesson_id": str,
        "affects": str,
        "template_file": str,
        "description": str,
        "lesson_trigger": str,
        "lesson_learning": str,
    }
    """
    lesson_id = lesson.get("id", "")
    trigger = lesson.get("trigger", "")
    learning = lesson.get("learning", "")
    methodology_change = lesson.get("methodology_change", {})
    affects_list = methodology_change.get("affects", [])
    description = methodology_change.get("description", "")

    proposals: list[dict] = []

    for affects_value in affects_list:
        if affects_value == "all":
            for template_file in _ALL_TEMPLATE_FILES:
                proposals.append({
                    "lesson_id": lesson_id,
                    "affects": affects_value,
                    "template_file": template_file,
                    "description": description,
                    "lesson_trigger": trigger,
                    "lesson_learning": learning,
                })
        else:
            template_file = _AFFECTS_TO_TEMPLATE.get(affects_value, "")
            proposals.append({
                "lesson_id": lesson_id,
                "affects": affects_value,
                "template_file": template_file,
                "description": description,
                "lesson_trigger": trigger,
                "lesson_learning": learning,
            })

    return proposals


def apply_template_change(proposal: dict, change_text: str, templates_root: Path | None = None) -> None:
    """Append change_text as a comment block to the template file.

    Format: {# LESSON <lesson_id>: <change_text> #}

    The comment marks the location for the developer to implement manually.

    Args:
        proposal: A proposal dict from propose_template_change().
        change_text: The text describing the change to embed.
        templates_root: Optional override for the anchor repo root (used in tests).
    """
    root = templates_root if templates_root is not None else _ANCHOR_ROOT
    template_path = (root / proposal["template_file"]).resolve()
    templates_boundary = (root / "skills" / "pairmode" / "templates").resolve()
    if not str(template_path).startswith(str(templates_boundary)):
        raise ValueError(
            f"Template path {template_path} is outside templates directory"
        )
    lesson_id = proposal["lesson_id"]

    comment_block = f"\n{{# LESSON {lesson_id}: {change_text} #}}\n"
    with open(template_path, "a", encoding="utf-8") as f:
        f.write(comment_block)


def mark_lesson_status(lesson_id: str, new_status: str) -> None:
    """Update the status field on a lesson.

    Uses save_lessons() which enforces the append-only invariant
    (only the status field may be changed on existing entries).
    """
    data = lesson_utils.load_lessons()
    lessons = data.get("lessons", [])
    for lesson in lessons:
        if lesson.get("id") == lesson_id:
            lesson["status"] = new_status
            break
    lesson_utils.save_lessons(data)


def regenerate_lessons_md() -> None:
    """Reload lessons.json and write LESSONS.md."""
    data = lesson_utils.load_lessons()
    md_content = lesson_utils.generate_lessons_md(data)
    _LESSONS_MD.write_text(md_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--approve",
    "approve_ids",
    multiple=True,
    metavar="LESSON_ID",
    help="Lesson IDs to approve (may be repeated).",
)
@click.option(
    "--reject",
    "reject_ids",
    multiple=True,
    metavar="LESSON_ID",
    help="Lesson IDs to reject (may be repeated).",
)
def cli(approve_ids: tuple[str, ...], reject_ids: tuple[str, ...]) -> None:
    """Process lesson approvals and rejections, then regenerate LESSONS.md.

    Approved lessons: apply_template_change() is called with the lesson's
    own description as change_text, then status is set to 'applied'.

    Rejected lessons: status is set to 'reviewed'.
    """
    if not approve_ids and not reject_ids:
        click.echo("No lessons specified. Use --approve or --reject.")
        return

    all_lessons = load_reviewable_lessons()
    lessons_by_id = {l["id"]: l for l in all_lessons}

    approved_count = 0
    rejected_count = 0

    for lesson_id in approve_ids:
        lesson = lessons_by_id.get(lesson_id)
        if lesson is None:
            click.echo(f"WARNING: lesson {lesson_id} not found or not reviewable — skipping.")
            continue
        proposals = propose_template_change(lesson)
        for proposal in proposals:
            description = proposal["description"]
            apply_template_change(proposal, description)
            click.echo(
                f"  Annotated {proposal['template_file']} with lesson {lesson_id}.\n"
                f"  ACTION REQUIRED: Open the template and implement the change:\n"
                f"    {{# LESSON {lesson_id}: {proposal['description']} #}}"
            )
        mark_lesson_status(lesson_id, "applied")
        approved_count += 1

    for lesson_id in reject_ids:
        if lesson_id not in lessons_by_id:
            click.echo(f"WARNING: lesson {lesson_id} not found or not reviewable — skipping.")
            continue
        mark_lesson_status(lesson_id, "reviewed")
        rejected_count += 1

    regenerate_lessons_md()
    click.echo(
        f"REVIEW COMPLETE\n"
        f"  {approved_count} lesson(s) annotated — open affected templates to implement the changes.\n"
        f"  {rejected_count} lesson(s) deferred for next review cycle.\n"
        f"LESSONS.md regenerated."
    )


if __name__ == "__main__":
    cli()
