"""
schema_validator.py — Validate story, era, and phase manifest files.

All three formats use YAML frontmatter (delimited by ---) followed by Markdown body.
This module parses frontmatter with stdlib only (re + a minimal YAML subset via
the standard `re` module and simple key/value extraction). Full YAML parsing is not
needed because the frontmatter schemas are shallow key/value structures.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(
    r"^\s*---\s*\n(.*?)\n?---\s*(\n|$)",
    re.DOTALL,
)

_YAML_SCALAR_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$')
_YAML_LIST_ITEM_RE = re.compile(r'^\s+-\s+(.+)$')


def _parse_frontmatter(text: str) -> dict[str, Any] | None:
    """
    Extract and parse the YAML frontmatter block from *text*.

    Returns a dict of top-level keys, or None if no valid frontmatter block
    is found.  Only supports the subset of YAML used by our schemas:
      - scalar string values (quoted or unquoted)
      - block sequences (list items starting with '  - ')

    This is intentionally minimal — it is NOT a general YAML parser.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None

    raw = m.group(1)
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in raw.splitlines():
        # Skip blank lines inside frontmatter
        if not line.strip():
            continue

        # Check if this is a list item
        list_m = _YAML_LIST_ITEM_RE.match(line)
        if list_m and current_key is not None and current_list is not None:
            current_list.append(list_m.group(1).strip())
            continue

        # Check if this is a new scalar or list-start key
        scalar_m = _YAML_SCALAR_RE.match(line)
        if scalar_m:
            # Flush previous list if any
            if current_key is not None and current_list is not None:
                result[current_key] = current_list

            key = scalar_m.group(1)
            value_raw = scalar_m.group(2).strip()

            if value_raw == "" or value_raw is None:
                # Start of a block sequence
                current_key = key
                current_list = []
                result[key] = current_list  # will be populated by list items
            else:
                current_key = key
                current_list = None
                # Strip optional quotes
                if (value_raw.startswith('"') and value_raw.endswith('"')) or (
                    value_raw.startswith("'") and value_raw.endswith("'")
                ):
                    value_raw = value_raw[1:-1]
                result[key] = value_raw

    return result


# ---------------------------------------------------------------------------
# Public validators
# ---------------------------------------------------------------------------

VALID_STORY_STATUSES = {"draft", "planned", "in-progress", "complete", "backlog"}
VALID_ERA_STATUSES = {"active", "complete"}

REQUIRED_STORY_FIELDS = ("id", "rail", "title", "status", "phase", "primary_files")
REQUIRED_ERA_FIELDS = ("id", "name", "status")


def validate_story_file(path: Path) -> list[str]:
    """Return list of validation errors, empty if valid."""
    errors: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Cannot read file: {exc}"]

    fm = _parse_frontmatter(text)
    if fm is None:
        return ["Missing or malformed YAML frontmatter block"]

    for field in REQUIRED_STORY_FIELDS:
        # primary_files emptiness is checked separately with status awareness
        if field == "primary_files":
            if field not in fm or fm[field] is None:
                errors.append(f"Missing required field: '{field}'")
        else:
            if field not in fm or fm[field] in (None, "", []):
                errors.append(f"Missing required field: '{field}'")

    if "status" in fm and fm["status"] not in VALID_STORY_STATUSES:
        errors.append(
            f"Invalid status '{fm['status']}'; must be one of "
            f"{sorted(VALID_STORY_STATUSES)}"
        )

    if "primary_files" in fm and not isinstance(fm["primary_files"], list):
        errors.append("Field 'primary_files' must be a list")

    status = fm.get("status", "")
    if status not in ("draft", "backlog"):
        if not fm.get("primary_files"):
            errors.append("primary_files must be non-empty for non-draft stories "
                          "(status is not 'draft' or 'backlog')")

    return errors


def validate_era_file(path: Path) -> list[str]:
    """Return list of validation errors, empty if valid."""
    errors: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Cannot read file: {exc}"]

    fm = _parse_frontmatter(text)
    if fm is None:
        return ["Missing or malformed YAML frontmatter block"]

    for field in REQUIRED_ERA_FIELDS:
        if field not in fm or fm[field] in (None, ""):
            errors.append(f"Missing required field: '{field}'")

    if "status" in fm and fm["status"] not in VALID_ERA_STATUSES:
        errors.append(
            f"Invalid status '{fm['status']}'; must be one of "
            f"{sorted(VALID_ERA_STATUSES)}"
        )

    return errors


def validate_phase_manifest(path: Path) -> list[str]:
    """Return list of validation errors, empty if valid."""
    errors: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Cannot read file: {exc}"]

    fm = _parse_frontmatter(text)
    if fm is None:
        return ["Missing or malformed YAML frontmatter block"]

    if "era" not in fm or fm["era"] in (None, ""):
        errors.append("Missing required field: 'era'")

    return errors
