"""
story_resolver.py — Resolve story IDs to content and parse phase manifests.

Public API:
  resolve_story(story_id, project_dir)
      Find and read the story file for a given ID (e.g. 'BOOTSTRAP-003').
      Returns dict with keys: id, rail, title, status, phase, primary_files,
      touches, body.
      Raises FileNotFoundError if story file does not exist.
      Raises ValueError if story_id format is invalid.

  list_phase_stories(phase_path)
      Parse a phase manifest and return story IDs in order.
      Returns empty list if no Stories table found (legacy phase format).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import schema_validator as _sv

# ---------------------------------------------------------------------------
# Story ID parsing
# ---------------------------------------------------------------------------

# Valid story ID: one or more uppercase letters, a hyphen, then one or more digits.
# e.g. BOOTSTRAP-003, AUDIT-007
_STORY_ID_RE = re.compile(r'^([A-Z]+)-(\d+)$')


def _parse_story_id(story_id: str) -> tuple[str, str]:
    """Split 'RAIL-NNN' into (rail, seq). Raises ValueError on invalid format."""
    m = _STORY_ID_RE.match(story_id)
    if not m:
        raise ValueError(
            f"Invalid story ID format: {story_id!r}. "
            "Expected format: RAIL-NNN (e.g. BOOTSTRAP-003)."
        )
    return m.group(1), m.group(2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_story(story_id: str, project_dir: Path) -> dict:
    """Find and read the story file for a given ID (e.g. 'BOOTSTRAP-003').

    Returns dict with keys: id, rail, title, status, phase, primary_files,
    touches, body (full markdown body below frontmatter).

    Raises FileNotFoundError if the story file does not exist.
    Raises ValueError if story_id format is invalid.
    """
    rail, _seq = _parse_story_id(story_id)

    story_path = project_dir / "docs" / "stories" / rail / f"{story_id}.md"
    if not story_path.exists():
        raise FileNotFoundError(
            f"Story file not found: {story_path}"
        )

    text = story_path.read_text(encoding="utf-8")
    fm = _sv._parse_frontmatter(text)
    if fm is None:
        fm = {}

    # Extract body: everything after the closing --- of the frontmatter block
    body = _extract_body(text)

    return {
        "id": fm.get("id", story_id),
        "rail": fm.get("rail", rail),
        "title": fm.get("title", ""),
        "status": fm.get("status", ""),
        "phase": fm.get("phase", ""),
        "primary_files": fm.get("primary_files") or [],
        "touches": fm.get("touches") or [],
        "body": body,
    }


def list_phase_stories(phase_path: Path) -> list[str]:
    """Parse a phase manifest and return story IDs in order.

    Reads the ## Stories table and returns IDs from the ID column.
    Returns empty list if no Stories table found (legacy phase format).
    """
    text = phase_path.read_text(encoding="utf-8")
    return _parse_stories_table(text)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Matches the closing --- of a frontmatter block
_FRONTMATTER_CLOSE_RE = re.compile(r'^\s*---\s*$', re.MULTILINE)


def _extract_body(text: str) -> str:
    """Return everything after the closing --- of the frontmatter block."""
    # The frontmatter block starts with --- and ends with another ---
    # Find the second --- occurrence
    stripped = text.lstrip()
    if not stripped.startswith('---'):
        # No frontmatter at all; entire text is body
        return text

    # Find end of opening ---
    first_close = stripped.find('\n')
    if first_close == -1:
        return ""

    rest = stripped[first_close + 1:]

    # Find the closing ---
    m = _FRONTMATTER_CLOSE_RE.search(rest)
    if not m:
        # Malformed frontmatter — return full text
        return text

    body_start = m.end()
    return rest[body_start:]


def _parse_stories_table(text: str) -> list[str]:
    """Extract story IDs from the ## Stories table in a phase manifest."""
    # Locate the ## Stories section
    stories_section_re = re.compile(r'^##\s+Stories\s*$', re.MULTILINE)
    m = stories_section_re.search(text)
    if not m:
        return []

    # Everything after ## Stories heading
    section_text = text[m.end():]

    # Find pipe-delimited table rows
    # Skip header row (contains 'ID') and separator row (contains '---')
    ids: list[str] = []
    in_table = False
    header_seen = False
    separator_seen = False

    for line in section_text.splitlines():
        stripped = line.strip()

        # Stop at the next ## heading (start of a new section)
        if stripped.startswith('##'):
            break

        if not stripped.startswith('|'):
            # Non-table lines between table rows are fine; stop if we leave the table
            if in_table and stripped:
                break
            continue

        in_table = True
        # Parse first column of the pipe-delimited row
        parts = [p.strip() for p in stripped.split('|')]
        # parts[0] is empty (before first |), parts[1] is first column
        if len(parts) < 2:
            continue

        first_col = parts[1].strip()

        # Skip header row
        if not header_seen:
            header_seen = True
            continue

        # Skip separator row (all dashes)
        if not separator_seen:
            separator_seen = True
            continue

        # This is a data row — strip Markdown link syntax [TEXT](URL) → TEXT
        if first_col:
            first_col = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', first_col)
            ids.append(first_col)

    return ids
