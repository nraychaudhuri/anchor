"""Utilities for reading and writing the lessons store."""

from pathlib import Path
import json
import re as _re

LESSONS_FILE = Path(__file__).parent.parent.parent.parent / "lessons" / "lessons.json"


def load_lessons() -> dict:
    """Load lessons.json and return the parsed dict."""
    if not LESSONS_FILE.exists():
        raise RuntimeError(
            f"lessons.json not found at {LESSONS_FILE}. "
            "Run '/anchor:pairmode lesson' to capture the first lesson and create it."
        )
    with open(LESSONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_lessons(data: dict) -> None:
    """Write lessons.json, enforcing the append-only invariant.

    Existing entries may only have their ``status`` field changed.
    Any attempt to modify other fields of an existing entry raises ValueError.
    New entries may be freely appended.
    """
    existing = load_lessons()
    existing_by_id = {entry["id"]: entry for entry in existing.get("lessons", [])}

    existing_ids = set(existing_by_id.keys())
    incoming_ids = {entry.get("id") for entry in data.get("lessons", [])}
    removed = existing_ids - incoming_ids
    if removed:
        raise ValueError(
            f"Append-only violation: lessons {sorted(removed)} were removed from data"
        )

    for entry in data.get("lessons", []):
        entry_id = entry.get("id")
        if entry_id in existing_by_id:
            original = existing_by_id[entry_id]
            for key, value in entry.items():
                if key == "status":
                    continue
                if original.get(key) != value:
                    raise ValueError(
                        f"Append-only violation: field '{key}' of lesson '{entry_id}' "
                        f"may not be modified (only 'status' changes are allowed)."
                    )

    with open(LESSONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def generate_lessons_md(data: dict) -> str:
    """Return a LESSONS.md string generated from *data*.

    Format:
      # Anchor Methodology Lessons

      This file is auto-generated from `lessons.json`. Edit `lessons.json` directly
      or use `/anchor:pairmode lesson` to capture a new lesson.

      No lessons captured yet.        ← when lessons list is empty

      --- (per lesson when non-empty) ---
      ## L001 — <trigger>
      **Date:** ...
      **Status:** ...
      **Learning:** ...
    """
    lines: list[str] = [
        "# Anchor Methodology Lessons",
        "",
        "This file is auto-generated from `lessons.json`. Edit `lessons.json` directly",
        "or use `/anchor:pairmode lesson` to capture a new lesson.",
        "",
    ]

    lessons = data.get("lessons", [])
    if not lessons:
        lines.append("No lessons captured yet.")
        lines.append("")
    else:
        for lesson in lessons:
            lid = lesson.get("id", "")
            trigger = lesson.get("trigger", "")
            date = lesson.get("date", "")
            learning = lesson.get("learning", "")
            status = lesson.get("status", "")

            lines.append(f"## {lid} — {trigger}")
            lines.append(f"**Date:** {date}")
            lines.append(f"**Status:** {status}")
            lines.append(f"**Learning:** {learning}")
            lines.append("")

    return "\n".join(lines)


def next_lesson_id(lessons: list[dict]) -> str:
    """Return the next lesson ID string (e.g. 'L001', 'L002').

    Uses max(existing numeric IDs) + 1 to avoid collision if any entry is absent.
    Returns 'L001' for an empty lessons list.
    """
    nums = []
    for lesson in lessons:
        m = _re.match(r"L(\d+)$", lesson.get("id", ""))
        if m:
            nums.append(int(m.group(1)))
    return f"L{(max(nums) + 1):03d}" if nums else "L001"
