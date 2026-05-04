"""
ideology_parser.py — Shared parsing logic for ideology.md and reconstruction.md briefs.

Extracted from reconstruct.py so that bootstrap.py and reconstruct.py can both use
the same parsing logic without duplication.
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IDEOLOGY_PLACEHOLDER_MARKER = "_(not yet specified"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_html_comments(text: str) -> str:
    """Remove HTML comments (<!-- ... -->) from text."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def _extract_top_level_sections(text: str) -> dict[str, str]:
    """Split text by ## headings, returning {heading_text: body_text} mapping."""
    parts = re.split(r"^(##\s+[^\n]+)$", text, flags=re.MULTILINE)
    sections: dict[str, str] = {}
    i = 0
    while i < len(parts):
        chunk = parts[i]
        if re.match(r"^##\s+", chunk):
            heading = chunk.strip()
            body = parts[i + 1] if (i + 1) < len(parts) else ""
            sections[heading] = body
            i += 2
        else:
            i += 1
    return sections


def _extract_subsections(text: str) -> dict[str, str]:
    """Split text by ### headings, returning {heading_text: body_text} mapping."""
    parts = re.split(r"^(###\s+[^\n]+)$", text, flags=re.MULTILINE)
    sections: dict[str, str] = {}
    i = 0
    while i < len(parts):
        chunk = parts[i]
        if re.match(r"^###\s+", chunk):
            heading = chunk.strip()
            body = parts[i + 1] if (i + 1) < len(parts) else ""
            sections[heading] = body
            i += 2
        else:
            i += 1
    return sections


def _bullet_lines(body: str) -> list[str]:
    """Extract bullet lines from body, skipping placeholders and empty lines."""
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(IDEOLOGY_PLACEHOLDER_MARKER):
            continue
        if stripped.startswith("- "):
            lines.append(stripped[2:])
        elif stripped.startswith("-"):
            lines.append(stripped[1:].strip())
    return lines


def _find_section(sections: dict[str, str], keyword: str) -> str:
    """Return body for section whose heading contains keyword (case-insensitive)."""
    keyword_lower = keyword.lower()
    for heading, body in sections.items():
        if keyword_lower in heading.lower():
            return body
    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_ideology_text(text: str) -> dict:
    """Parse ideology.md text (already read) into a context dict.

    Equivalent to parse_ideology_file but accepts the content directly,
    avoiding any disk I/O.

    Returns: convictions, constraints, must_preserve, free_to_change,
             should_question, comparison_dimensions, value_hierarchy (all lists).
    """
    text = _strip_html_comments(text)

    # Extract project_name from first line: # Ideology — ProjectName
    project_name = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            rest = re.sub(r"^#\s+", "", line)
            rest = re.sub(r"^[Ii]deology\s*[—\-–]\s*", "", rest).strip()
            project_name = rest
            break

    top_sections = _extract_top_level_sections(text)

    # --- Core convictions ---
    convictions_body = _find_section(top_sections, "core convictions")
    convictions = _bullet_lines(convictions_body)

    # --- Value hierarchy ---
    value_hierarchy_body = _find_section(top_sections, "value hierarchy")
    value_hierarchy = _bullet_lines(value_hierarchy_body)

    # --- Accepted constraints ---
    constraints_body = _find_section(top_sections, "accepted constraints")
    constraints = []
    constraint_subsections = _extract_subsections(constraints_body)
    for sub_heading, sub_body in constraint_subsections.items():
        name = re.sub(r"^###\s*", "", sub_heading).strip()
        if name.startswith("_(not yet specified"):
            continue
        rule = ""
        rationale = ""
        for line in sub_body.splitlines():
            stripped = line.strip()
            if stripped.startswith("**Rule:**"):
                rule = stripped[len("**Rule:**"):].strip()
            elif stripped.startswith("**Rationale:**"):
                rationale = stripped[len("**Rationale:**"):].strip()
        constraints.append({"name": name, "rule": rule, "rationale": rationale})

    # --- Reconstruction guidance ---
    reconstruction_body = _find_section(top_sections, "reconstruction guidance")
    recon_subsections = _extract_subsections(reconstruction_body)

    must_preserve_body = _find_section(recon_subsections, "must preserve")
    must_preserve = _bullet_lines(must_preserve_body)

    should_question_body = _find_section(recon_subsections, "should question")
    should_question = _bullet_lines(should_question_body)

    free_to_change_body = _find_section(recon_subsections, "free to change")
    free_to_change = _bullet_lines(free_to_change_body)

    # --- Comparison basis ---
    comparison_body = _find_section(top_sections, "comparison basis")
    comparison_dimensions = []
    for line in comparison_body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(IDEOLOGY_PLACEHOLDER_MARKER):
            continue
        # Match both: "- **Name:** desc" (colon inside bold) and "- **Name**: desc" (colon outside)
        m = re.match(r"^-\s+\*\*(.+?):?\*\*:?\s*(.+)$", stripped)
        if m:
            name = m.group(1).rstrip(":")
            comparison_dimensions.append({"name": name, "description": m.group(2)})

    return {
        "project_name": project_name,
        "convictions": convictions,
        "value_hierarchy": value_hierarchy,
        "constraints": constraints,
        "must_preserve": must_preserve,
        "should_question": should_question,
        "free_to_change": free_to_change,
        "comparison_dimensions": comparison_dimensions,
    }


def parse_ideology_file(path: Path) -> dict:
    """Parse docs/ideology.md into context dict.

    Reads the file and delegates to parse_ideology_text.

    Returns: convictions, constraints, must_preserve, free_to_change,
             should_question, comparison_dimensions, value_hierarchy (all lists).
    """
    text = path.read_text(encoding="utf-8")
    return parse_ideology_text(text)


def parse_reconstruction_brief(path: Path) -> dict:
    """Parse a reconstruction.md brief into an ideology context dict.

    Maps reconstruction.md sections to the same keys returned by parse_ideology_file:
    - ## Non-negotiable ideology / ### Convictions  → convictions (list of strings)
    - ## Non-negotiable ideology / ### Constraints  → constraints (list of dicts with name/rule)
    - ## What must survive any implementation       → must_preserve (list of strings)
    - ## What you are free to change               → free_to_change (list of strings)
    - ## What you should question                  → should_question (list of strings)
    - ## Comparison rubric                          → comparison_dimensions (list of dicts or strings)

    Returns a dict with the same keys as parse_ideology_file (value_hierarchy is always []).
    """
    text = path.read_text(encoding="utf-8")
    text = _strip_html_comments(text)

    top_sections = _extract_top_level_sections(text)

    # --- Convictions and Constraints (nested under "Non-negotiable ideology") ---
    ideology_body = _find_section(top_sections, "non-negotiable ideology")
    ideology_subsections = _extract_subsections(ideology_body)

    convictions_body = _find_section(ideology_subsections, "convictions")
    convictions = _bullet_lines(convictions_body)

    constraints_body = _find_section(ideology_subsections, "constraints")
    constraints = []
    # Constraints in reconstruction.md use #### sub-sub-headings
    constraint_parts = re.split(r"^(####\s+[^\n]+)$", constraints_body, flags=re.MULTILINE)
    ci = 0
    while ci < len(constraint_parts):
        chunk = constraint_parts[ci]
        if re.match(r"^####\s+", chunk):
            name = re.sub(r"^####\s*", "", chunk).strip()
            body = constraint_parts[ci + 1] if (ci + 1) < len(constraint_parts) else ""
            rule = ""
            for line in body.splitlines():
                stripped = line.strip()
                if stripped.startswith("**Rule:**"):
                    rule = stripped[len("**Rule:**"):].strip()
                    break
            if name and not name.startswith("_("):
                constraints.append({"name": name, "rule": rule})
            ci += 2
        else:
            ci += 1

    # If no #### found, fall back to bullet-style constraint blocks
    if not constraints:
        # Parse bullet-style: "- **Name:** rule text"
        for line in constraints_body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("_("):
                continue
            m = re.match(r"^-\s+\*\*(.+?)\*\*:\s*(.+)$", stripped)
            if m:
                constraints.append({"name": m.group(1), "rule": m.group(2)})

    # --- Must preserve ---
    must_preserve_body = _find_section(top_sections, "what must survive")
    must_preserve = _bullet_lines(must_preserve_body)

    # --- Free to change ---
    free_to_change_body = _find_section(top_sections, "free to change")
    free_to_change = _bullet_lines(free_to_change_body)

    # --- Should question ---
    should_question_body = _find_section(top_sections, "should question")
    should_question = _bullet_lines(should_question_body)

    # --- Comparison dimensions ---
    comparison_body = _find_section(top_sections, "comparison rubric")
    comparison_dimensions = []
    for line in comparison_body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("_("):
            continue
        m = re.match(r"^-\s+\*\*(.+?)\*\*:\s*(.+)$", stripped)
        if m:
            comparison_dimensions.append({"name": m.group(1), "description": m.group(2)})
        elif stripped.startswith("- "):
            comparison_dimensions.append(stripped[2:])
        elif stripped.startswith("-"):
            comparison_dimensions.append(stripped[1:].strip())

    return {
        "project_name": "",
        "convictions": convictions,
        "value_hierarchy": [],
        "constraints": constraints,
        "must_preserve": must_preserve,
        "should_question": should_question,
        "free_to_change": free_to_change,
        "comparison_dimensions": comparison_dimensions,
    }
