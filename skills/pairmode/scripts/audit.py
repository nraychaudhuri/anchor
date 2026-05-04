"""
audit.py — Pairmode project auditor.

Compares a project directory against canonical pairmode templates, producing
a structured diff of missing, inconsistent, and extra sections.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import click
import jinja2

# Insert anchor repo root so sibling imports work when run as CLI
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from skills.pairmode.scripts import lesson_utils  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAIRMODE_VERSION = "0.1.0"

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Canonical files to audit (dest path in project → template path relative to TEMPLATES_DIR)
CANONICAL_FILES: list[tuple[str, str]] = [
    ("CLAUDE.md", "CLAUDE.md.j2"),
    ("CLAUDE.build.md", "CLAUDE.build.md.j2"),
    (".claude/agents/builder.md", "agents/builder.md.j2"),
    (".claude/agents/reviewer.md", "agents/reviewer.md.j2"),
    (".claude/agents/loop-breaker.md", "agents/loop-breaker.md.j2"),
    (".claude/agents/security-auditor.md", "agents/security-auditor.md.j2"),
    (".claude/agents/intent-reviewer.md", "agents/intent-reviewer.md.j2"),
]

# Scaffold files: Phase 7 docs that receive full section-level comparison.
# These are distinguished from CANONICAL_FILES only in that INCONSISTENT findings
# on them may be labelled STALE PLACEHOLDER when the project body is placeholder-only.
SCAFFOLD_FILES: list[tuple[str, str]] = [
    ("docs/brief.md", "docs/brief.md.j2"),
    ("docs/phases/index.md", "docs/phases/index.md.j2"),
    ("docs/cer/backlog.md", "docs/cer/backlog.md.j2"),
]

# File-existence checks: kept as an alias for backwards-compat with sync.py callers.
# Now empty — Phase 7 files moved to SCAFFOLD_FILES for section-level comparison.
EXISTENCE_CHECK_FILES: list[tuple[str, str, str]] = []

# Sentinel placeholder patterns (normalised, stripped). A section body consisting
# solely of one of these patterns (or empty) is classified as STALE PLACEHOLDER.
_PLACEHOLDER_PATTERNS: frozenset[str] = frozenset(
    [
        "_(not yet specified)_",
        "*(none)*",
        "— fill in —",
        "-- fill in --",
        "",
    ]
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class AuditItem:
    file: str
    section: str
    description: str
    lesson_id: str | None = None


@dataclass
class AuditResult:
    project_name: str
    project_dir: Path
    missing: list[AuditItem] = field(default_factory=list)
    inconsistent: list[AuditItem] = field(default_factory=list)
    extra: list[AuditItem] = field(default_factory=list)
    pairmode_version: str | None = None
    canonical_version: str = "0.1.0"
    context_missing: bool = False


# ---------------------------------------------------------------------------
# Jinja2 environment for rendering templates
# ---------------------------------------------------------------------------

_JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    undefined=jinja2.Undefined,  # silently replaces unknown vars with ""
    keep_trailing_newline=True,
)


IDEOLOGY_PLACEHOLDER_MARKER = "_(not yet specified"
IDEOLOGY_REQUIRED_SECTIONS = [
    "## Core convictions",
    "## Value hierarchy",
    "## Accepted constraints",
    "## Prototype fingerprints",
    "## Reconstruction guidance",
    "## Comparison basis",
]

RECONSTRUCTION_PLACEHOLDER_MARKER = "_(not set)_"
RECONSTRUCTION_REQUIRED_SECTIONS = [
    "## Non-negotiable ideology",
    "## What must survive any implementation",
    "## Comparison rubric",
]


def _strip_html_comments(text: str) -> str:
    """Remove HTML comments (<!-- ... -->) from text."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def _check_ideology_staleness(project_dir: Path) -> str | None:
    """None if absent, 'STALE' if all placeholder, 'OK' if real content found."""
    ideology_path = project_dir / "docs" / "ideology.md"
    if not ideology_path.exists():
        return None

    text = ideology_path.read_text(encoding="utf-8")
    text = _strip_html_comments(text)

    # Split text into sections by ## headings
    # For each required section, find its body and check for real content
    found_real_content = False

    for section_header in IDEOLOGY_REQUIRED_SECTIONS:
        # Find the section in the text (case-insensitive match on normalised form)
        pattern = re.compile(
            r"^" + re.escape(section_header) + r"\s*$(.+?)(?=^##|\Z)",
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        match = pattern.search(text)
        if not match:
            # Section missing entirely — count as placeholder, continue
            continue

        body = match.group(1)
        # Check each non-empty line that is not a placeholder
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        for line in lines:
            if not line.startswith(IDEOLOGY_PLACEHOLDER_MARKER):
                found_real_content = True
                break
        if found_real_content:
            break

    if found_real_content:
        return "OK"
    return "STALE"


def _check_reconstruction_staleness(project_dir: Path) -> str | None:
    """None if absent, 'STALE' if generated+placeholder, 'OK' otherwise."""
    reconstruction_path = project_dir / "docs" / "reconstruction.md"
    if not reconstruction_path.exists():
        return None

    text = reconstruction_path.read_text(encoding="utf-8")

    # If the file does NOT contain the generated-brief footer, it is a filled-in
    # scoring report — treat as OK immediately without flagging.
    generated_footer = "Generated from `docs/ideology.md`"
    if generated_footer not in text:
        return "OK"

    # It is a generated brief. Check whether required scoring sections exist and
    # have real (non-placeholder) content.
    found_real_content = False

    for section_header in RECONSTRUCTION_REQUIRED_SECTIONS:
        pattern = re.compile(
            r"^" + re.escape(section_header) + r"\s*$(.+?)(?=^##|\Z)",
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        match = pattern.search(text)
        if not match:
            # Section missing entirely — count as placeholder, continue
            continue

        body = match.group(1)
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        for line in lines:
            # Skip Jinja2 comments, placeholder text, and horizontal rules
            if line.startswith("{#"):
                continue
            if line.startswith("_"):
                continue
            if re.match(r"^-{3,}$", line):
                continue
            if line.startswith(">"):
                continue
            # Found a real content line
            found_real_content = True
            break
        if found_real_content:
            break

    if found_real_content:
        return "OK"
    return "STALE"


def _load_project_context(project_dir: Path) -> tuple[dict, bool]:
    """Load the saved bootstrap context, or return a minimal empty context.

    Returns:
        (context, context_found) where context_found is True when
        pairmode_context.json exists and parses successfully.
    """
    context_path = project_dir / ".companion" / "pairmode_context.json"
    if context_path.exists():
        try:
            return json.loads(context_path.read_text(encoding="utf-8")), True
        except (json.JSONDecodeError, OSError):
            pass
    # Fallback: empty context (renders template variables as empty strings)
    fallback = {
        "project_name": project_dir.name,
        "project_description": "",
        "stack": "",
        "build_command": "",
        "test_command": "",
        "migration_command": "",
        "domain_model": "",
        "domain_isolation_rule": "",
        "checklist_items": [],
        "protected_paths": [],
        "non_negotiables": [],
        "module_structure": [],
        "layer_rules": [],
    }
    return fallback, False


# ---------------------------------------------------------------------------
# Section splitting helpers
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^(##+ .+|---)$", re.MULTILINE)


def _split_sections(text: str) -> dict[str, str]:
    """Split a markdown document into sections keyed by header (or index).

    Splits on lines that are ``##`` headers or ``---`` separators.
    Returns an ordered dict mapping a normalised key to the section body.
    """
    parts = _SECTION_RE.split(text)
    sections: dict[str, str] = {}
    key_counter = 0

    i = 0
    while i < len(parts):
        chunk = parts[i].strip()
        if not chunk:
            i += 1
            continue

        # Check if this chunk is a separator/header (it came from a split match)
        if _SECTION_RE.fullmatch(chunk.strip()):
            header = chunk.strip()
            body = parts[i + 1].strip() if (i + 1) < len(parts) else ""
            key = _normalise(header)
            # Avoid key collisions by appending a counter if needed
            if key in sections:
                key = f"{key}__{key_counter}"
                key_counter += 1
            sections[key] = body
            i += 2
        else:
            # Preamble before first header
            key = f"__preamble__{key_counter}"
            key_counter += 1
            sections[key] = chunk
            i += 1

    return sections


def _normalise(text: str) -> str:
    """Lowercase and collapse whitespace for fuzzy comparison."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _is_stale_placeholder(body: str) -> bool:
    """Return True when *body* consists solely of placeholder text (or is empty).

    Strips leading/trailing whitespace, then checks whether the result matches
    any sentinel pattern in _PLACEHOLDER_PATTERNS, or consists only of table rows
    that themselves contain only placeholder cell values.

    Also matches extended "not yet specified" placeholders of the form
    ``_(not yet specified — ...)_`` used by brief.md and ideology.md templates.
    """
    stripped = body.strip()
    if stripped in _PLACEHOLDER_PATTERNS:
        return True
    # Extended placeholder: starts with _(not yet specified (covers —- variants)
    if stripped.startswith("_(not yet specified"):
        return True
    # Handle multi-line bodies: split into non-empty lines and check each
    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    if not lines:
        return True
    # If every non-empty line is a placeholder pattern or extended placeholder, treat as stale
    if all(
        ln in _PLACEHOLDER_PATTERNS or ln.startswith("_(not yet specified")
        for ln in lines
    ):
        return True
    return False


def _is_separator_key(key: str) -> bool:
    """Return True when *key* represents a ``---`` separator line (not a real section)."""
    return bool(re.match(r'^-+(__\d+)?$', key))


# ---------------------------------------------------------------------------
# Lessons helpers
# ---------------------------------------------------------------------------


def _load_applicable_lessons(applies_to: str) -> list[dict]:
    """Load lessons that apply to *applies_to* or to 'all'."""
    try:
        data = lesson_utils.load_lessons()
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    lessons = data.get("lessons", [])
    result = []
    for lesson in lessons:
        lesson_applies = lesson.get("applies_to", [])
        if "all" in lesson_applies or applies_to in lesson_applies:
            result.append(lesson)
    return result


def _find_lesson_for_file(lessons: list[dict], file_path: str) -> str | None:
    """Return the first lesson ID whose methodology_change.affects matches *file_path*."""
    for lesson in lessons:
        mc = lesson.get("methodology_change", {})
        affects = mc.get("affects", [])
        # affects may be a list (current schema) or legacy string
        if isinstance(affects, str):
            affects = [affects]
        for affect in affects:
            if affect.lower() in file_path.lower() or file_path.lower() in affect.lower():
                return lesson.get("id")
    return None


# ---------------------------------------------------------------------------
# Overrides helpers
# ---------------------------------------------------------------------------


def _load_overrides(project_dir: Path) -> set[tuple[str, str]]:
    """Return set of (relative_file_path, normalised_section_key) pairs.

    Parses ``project_dir / ".pairmode-overrides"``. Blank lines and lines
    starting with ``#`` are skipped. Each valid line is split on ``:``
    (max one split) into ``(file_path, section_key)``; both parts are
    stripped of leading/trailing whitespace.
    """
    overrides_path = project_dir / ".pairmode-overrides"
    if not overrides_path.exists():
        return set()

    result: set[tuple[str, str]] = set()
    try:
        text = overrides_path.read_text(encoding="utf-8")
    except OSError:
        return result

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        file_path, section_key = stripped.split(":", 1)
        result.add((file_path.strip(), section_key.strip()))

    return result


# ---------------------------------------------------------------------------
# Core audit logic
# ---------------------------------------------------------------------------


def _read_template_sections(template_rel_path: str, context: dict | None = None) -> dict[str, str]:
    """Render a template with context, then split into sections."""
    if context is None:
        context = {}
    try:
        rendered = _JINJA_ENV.get_template(template_rel_path).render(**context)
    except (jinja2.TemplateNotFound, jinja2.TemplateError):
        return {}
    return _split_sections(rendered)


def _read_project_sections(project_dir: Path, rel_path: str) -> dict[str, str] | None:
    """Read a project file and split into sections. Returns None if file missing."""
    full_path = project_dir / rel_path
    if not full_path.exists():
        return None
    text = full_path.read_text(encoding="utf-8")
    return _split_sections(text)


def audit_project(project_dir: Path, applies_to: str = "all") -> AuditResult:
    """
    Audits the project at project_dir against canonical pairmode templates.
    applies_to: project type for lesson filtering ("all", "python", "typescript", etc.)
    """
    project_dir = Path(project_dir).resolve()

    # Security: path traversal containment guard
    if not project_dir.is_dir() or len(project_dir.parts) < 3:
        click.echo(
            f"error: project-dir resolves to a suspicious path: {project_dir}",
            err=True,
        )
        sys.exit(1)

    # Load saved template context (for rendering templates before comparison)
    context, context_found = _load_project_context(project_dir)

    # Read pairmode_version from .companion/state.json
    pairmode_version: str | None = None
    state_path = project_dir / ".companion" / "state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            pairmode_version = state.get("pairmode_version")
        except (json.JSONDecodeError, OSError):
            pairmode_version = None

    # Derive project name
    project_name = project_dir.name

    result = AuditResult(
        project_name=project_name,
        project_dir=project_dir,
        pairmode_version=pairmode_version,
        canonical_version=PAIRMODE_VERSION,
        context_missing=not context_found,
    )

    # Load applicable lessons
    lessons = _load_applicable_lessons(applies_to)

    # Load overrides: sections intentionally diverged from canonical templates
    overrides = _load_overrides(project_dir)

    # Set of scaffold-file destination paths for stale-placeholder labelling
    scaffold_dests = {d for d, _t in SCAFFOLD_FILES}

    # Combine canonical + scaffold files into one pass
    all_files: list[tuple[str, str]] = list(CANONICAL_FILES) + list(SCAFFOLD_FILES)

    # Compare each file
    for dest_rel, template_rel in all_files:
        # Scaffold files need the enriched context (with Phase 7 defaults)
        file_context = context
        if dest_rel in scaffold_dests:
            file_context = _enrich_scaffold_context(context)

        canonical_sections = _read_template_sections(template_rel, file_context)
        project_sections = _read_project_sections(project_dir, dest_rel)

        if project_sections is None:
            # Entire file is missing — all canonical sections → MISSING
            for section_key, section_body in canonical_sections.items():
                if _is_separator_key(section_key):
                    continue
                if (dest_rel, section_key) in overrides:
                    continue  # Intentionally diverged — skip
                lesson_id = _find_lesson_for_file(lessons, dest_rel)
                result.missing.append(
                    AuditItem(
                        file=dest_rel,
                        section=section_key,
                        description=f"File missing entirely; section '{section_key}' not found",
                        lesson_id=lesson_id,
                    )
                )
            continue

        # File exists — compare section by section
        canonical_keys = set(canonical_sections.keys())
        project_keys = set(project_sections.keys())

        # Sections in canonical but not in project → MISSING
        for key in canonical_keys - project_keys:
            if _is_separator_key(key):
                continue
            if (dest_rel, key) in overrides:
                continue  # Intentionally diverged — skip
            lesson_id = _find_lesson_for_file(lessons, dest_rel)
            result.missing.append(
                AuditItem(
                    file=dest_rel,
                    section=key,
                    description=f"Section '{key}' present in canonical but not in project",
                    lesson_id=lesson_id,
                )
            )

        # Sections in project but not in canonical → EXTRA
        for key in project_keys - canonical_keys:
            if _is_separator_key(key):
                continue
            result.extra.append(
                AuditItem(
                    file=dest_rel,
                    section=key,
                    description=f"Section '{key}' is project-specific (not in canonical template)",
                )
            )

        # Sections in both → check content
        # For scaffold files (Phase 7 docs): only flag STALE PLACEHOLDER (never INCONSISTENT).
        #   Body content in scaffold files is inherently project-specific so body-level
        #   drift detection would produce false positives. We only warn when the body is
        #   entirely placeholder text, signalling the user hasn't filled it in yet.
        # For canonical files: full body comparison when context file is present.
        if dest_rel in scaffold_dests:
            # Stale-placeholder check runs even when context_missing (body is in project file)
            for key in canonical_keys & project_keys:
                if _is_separator_key(key):
                    continue
                if (dest_rel, key) in overrides:
                    continue  # Intentionally diverged — skip
                if _is_stale_placeholder(project_sections[key]):
                    result.inconsistent.append(
                        AuditItem(
                            file=dest_rel,
                            section=key,
                            description=(
                                f"STALE PLACEHOLDER — section '{key}' contains only placeholder text"
                            ),
                        )
                    )
        elif not result.context_missing:
            for key in canonical_keys & project_keys:
                if _is_separator_key(key):
                    continue
                if (dest_rel, key) in overrides:
                    continue  # Intentionally diverged — skip
                canonical_body = _normalise(canonical_sections[key])
                project_body = _normalise(project_sections[key])
                if canonical_body != project_body:
                    result.inconsistent.append(
                        AuditItem(
                            file=dest_rel,
                            section=key,
                            description=f"Section '{key}' content differs from canonical template",
                        )
                    )
                # else: consistent — nothing to add

    # Ideology staleness check — handled separately from SCAFFOLD_FILES
    ideology_status = _check_ideology_staleness(project_dir)
    if ideology_status is None:
        result.missing.append(
            AuditItem(
                file="docs/ideology.md",
                section="__file__",
                description="File missing entirely — run bootstrap to generate docs/ideology.md",
            )
        )
    elif ideology_status == "STALE":
        result.inconsistent.append(
            AuditItem(
                file="docs/ideology.md",
                section="__content__",
                description=(
                    "STALE PLACEHOLDER — all sections contain placeholder text"
                ),
            )
        )
    # "OK" → no finding

    # Reconstruction staleness check — handled separately from SCAFFOLD_FILES
    reconstruction_status = _check_reconstruction_staleness(project_dir)
    if reconstruction_status is None:
        result.missing.append(
            AuditItem(
                file="docs/reconstruction.md",
                section="__file__",
                description=(
                    "docs/reconstruction.md is missing — run /anchor:pairmode reconstruct to generate it"
                ),
            )
        )
    elif reconstruction_status == "STALE":
        result.inconsistent.append(
            AuditItem(
                file="docs/reconstruction.md",
                section="__content__",
                description=(
                    "STALE PLACEHOLDER — docs/reconstruction.md exists but contains only placeholder content"
                ),
            )
        )
    # "OK" → no finding

    return result


def _enrich_scaffold_context(context: dict) -> dict:
    """Add Phase 7 template defaults for keys absent from pairmode_context.json."""
    from datetime import date

    enriched = dict(context)
    enriched.setdefault("what", "")
    enriched.setdefault("why", "")
    enriched.setdefault("core_beliefs", "")
    enriched.setdefault("accepted_tradeoffs", "")
    enriched.setdefault("must_preserve", "")
    enriched.setdefault("operator_contact", "")
    enriched.setdefault("cer_entries", [])
    enriched.setdefault(
        "phases",
        [{"id": 1, "title": "Phase 1", "status": "in progress", "file": "docs/phases/phase-1.md"}],
    )
    enriched.setdefault("last_updated", date.today().isoformat())
    return enriched


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_audit_output(result: AuditResult) -> str:
    """Returns the human-readable audit report string."""
    lines: list[str] = []
    lines.append(f"AUDIT: {result.project_name} vs pairmode v{result.canonical_version}")
    lines.append("")

    if result.context_missing:
        lines.append(
            "WARNING: No pairmode_context.json found — INCONSISTENT comparison disabled."
        )
        lines.append(
            "  Template body comparison requires a context file to be meaningful."
        )
        lines.append(
            "  Run /anchor:pairmode bootstrap to generate pairmode_context.json, then re-audit."
        )
        lines.append("")

    if result.missing:
        lines.append("MISSING")
        for item in result.missing:
            lesson_tag = f"  ({item.lesson_id})" if item.lesson_id else ""
            lines.append(f"  \u2717 {item.file}: {item.description}{lesson_tag}")
        lines.append("")

    # Separate ideology and reconstruction stale-placeholder from other inconsistent items
    ideology_stale = [
        i for i in result.inconsistent
        if i.file == "docs/ideology.md" and "STALE PLACEHOLDER" in i.description
    ]
    reconstruction_stale = [
        i for i in result.inconsistent
        if i.file == "docs/reconstruction.md" and "STALE PLACEHOLDER" in i.description
    ]
    other_inconsistent = [
        i for i in result.inconsistent
        if not (i.file == "docs/ideology.md" and "STALE PLACEHOLDER" in i.description)
        and not (i.file == "docs/reconstruction.md" and "STALE PLACEHOLDER" in i.description)
    ]

    if ideology_stale or reconstruction_stale:
        lines.append("STALE PLACEHOLDER")
        if ideology_stale:
            lines.append(
                "  \u26a0 docs/ideology.md: all sections contain placeholder text"
            )
            lines.append(
                "    Recommendation: run bootstrap in TTY to trigger guided ideology capture,"
            )
            lines.append("    or edit docs/ideology.md directly.")
        if reconstruction_stale:
            lines.append(
                "  \u26a0 docs/reconstruction.md: exists but contains only placeholder content"
            )
            lines.append(
                "    Recommendation: run /anchor:pairmode reconstruct to regenerate it."
            )
        lines.append("")

    if other_inconsistent:
        lines.append("INCONSISTENT")
        for item in other_inconsistent:
            lines.append(f"  ~ {item.file}: {item.description}")
        lines.append("")

    if result.extra:
        lines.append("EXTRA (project-specific, keep as-is)")
        for item in result.extra:
            lines.append(f"  \u2713 {item.file}: {item.description}")
        lines.append("")

    lines.append("RECOMMENDATION")
    lines.append(
        "  Run /anchor:pairmode sync to apply missing/inconsistent items"
    )
    lines.append("  Project-specific items will be preserved")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--project-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to the project directory to audit.",
)
@click.option(
    "--applies-to",
    default="all",
    show_default=True,
    help="Project type for lesson filtering (e.g. 'python', 'typescript', 'all').",
)
def main(project_dir: Path, applies_to: str) -> None:
    """Audit a project directory against canonical pairmode templates."""
    result = audit_project(project_dir, applies_to=applies_to)
    click.echo(format_audit_output(result))


if __name__ == "__main__":
    main()
