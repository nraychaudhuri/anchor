"""
sync.py — Pairmode project syncer.

Applies the delta from an audit result to a project non-destructively.
Project-specific content (EXTRA items) is always preserved.
"""

from __future__ import annotations

import difflib
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import click
import jinja2

# Insert anchor repo root so sibling imports work when run as CLI
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from skills.pairmode.scripts.audit import audit_project, AuditResult, AuditItem  # noqa: E402
from skills.pairmode.scripts.audit import (  # noqa: E402
    TEMPLATES_DIR,
    CANONICAL_FILES,
    EXISTENCE_CHECK_FILES,
    SCAFFOLD_FILES,
    PAIRMODE_VERSION,
    _split_sections,
    _normalise,
    _enrich_scaffold_context,
    _load_project_context as _audit_load_project_context,
    _load_overrides,
)
from skills.pairmode.scripts.bootstrap import (  # noqa: E402
    PAIRMODE_DEFAULT_RAILS,
    _infer_project_type,
)
from skills.pairmode.scripts.story_new import _add_rail_to_era, _find_era  # noqa: E402

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class SyncResult:
    project_dir: Path
    applied: list[str] = field(default_factory=list)
    preserved: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    pairmode_version: str = PAIRMODE_VERSION
    last_sync: str = field(default_factory=lambda: date.today().isoformat())
    lessons_applied: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rail gap detection
# ---------------------------------------------------------------------------


def _check_rail_gaps(project_dir: Path, stack: str) -> list[str]:
    """Return list of default rails for this stack not present in docs/stories/.

    If docs/stories/ does not exist, returns empty list (project pre-dates rail
    structure). This function has no I/O side effects.
    """
    stories_dir = project_dir / "docs" / "stories"
    if not stories_dir.is_dir():
        return []

    project_type = _infer_project_type(stack, "")
    default_rails = PAIRMODE_DEFAULT_RAILS.get(project_type, PAIRMODE_DEFAULT_RAILS["generic"])

    present = {p.name.upper() for p in stories_dir.iterdir() if p.is_dir()}
    return [rail for rail in default_rails if rail.upper() not in present]


# ---------------------------------------------------------------------------
# Section-aware merge helpers
# ---------------------------------------------------------------------------


def _header_from_key(key: str) -> str:
    """Convert a normalised section key back to a best-effort header.

    Keys derived from ``## Foo bar`` headers will have the form ``## foo bar``.
    We just title-case words after the leading ``#`` markers.
    """
    return key


def _split_by_h2(text: str) -> list[tuple[str, str]]:
    """Split text into (header_line, section_body) pairs.

    The first tuple's header_line may be empty (preamble content).
    Each section_body does NOT include the trailing newline before the next header.
    """
    lines = text.splitlines(keepends=True)
    parts: list[tuple[str, str]] = []
    current_header = ""
    current_body_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            # Flush previous section
            parts.append((current_header, "".join(current_body_lines)))
            current_header = line.rstrip("\n")
            current_body_lines = []
        else:
            current_body_lines.append(line)

    # Flush final section
    parts.append((current_header, "".join(current_body_lines)))
    return parts


def _reconstruct_from_parts(parts: list[tuple[str, str]]) -> str:
    """Reconstruct a file from (header_line, body) pairs."""
    chunks: list[str] = []
    for header, body in parts:
        if header:
            chunks.append(header + "\n")
        if body:
            chunks.append(body)
    return "".join(chunks)


def _replace_section_in_file(project_text: str, section_key: str, canonical_body: str) -> str:
    """Locate the section identified by section_key in project_text and replace its body.

    section_key is the normalised form produced by _normalise(header_line).
    canonical_body is the raw body text from the canonical template.
    If the section is not found (shouldn't happen for INCONSISTENT), the text is returned unchanged.
    """
    parts = _split_by_h2(project_text)
    new_parts: list[tuple[str, str]] = []
    replaced = False

    for header, body in parts:
        if not replaced and _normalise(header) == section_key:
            # Ensure canonical_body ends with a newline for clean reconstruction
            new_body = canonical_body if canonical_body.endswith("\n") else canonical_body + "\n"
            new_parts.append((header, new_body))
            replaced = True
        else:
            new_parts.append((header, body))

    return _reconstruct_from_parts(new_parts)


def _append_section_to_file(project_text: str, header_key: str, canonical_body: str) -> str:
    """Append a new section to the end of project_text.

    header_key is the normalised form. We try to reconstruct an approximate header
    from the key (e.g. ``## foo bar`` → ``## Foo bar``).
    """
    # Reconstruct a plausible header from the normalised key
    # Keys look like: "## foo bar" or "__preamble__0"
    if header_key.startswith("__"):
        # Preamble — just append the canonical body directly
        if not project_text.endswith("\n"):
            project_text += "\n"
        return project_text + "\n" + canonical_body
    else:
        # Try to recover something readable from the key
        # The key was normalised from the actual template header
        header_text = header_key  # Already in "## ..." form
        if not project_text.endswith("\n"):
            project_text += "\n"
        body_text = canonical_body if canonical_body.endswith("\n") else canonical_body + "\n"
        return project_text + "\n" + header_text + "\n" + body_text


# ---------------------------------------------------------------------------
# Template content helper
# ---------------------------------------------------------------------------

_JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    undefined=jinja2.Undefined,  # silently replaces unknown vars with ""
    keep_trailing_newline=True,
)


def _load_project_context(project_dir: Path) -> dict:
    """Load the saved bootstrap context, or return a minimal empty context."""
    context, _ = _audit_load_project_context(project_dir)
    return context


def _render_template(template_rel: str, context: dict) -> str:
    """Render a Jinja2 template with context. Returns empty string on failure."""
    try:
        return _JINJA_ENV.get_template(template_rel).render(**context)
    except (jinja2.TemplateNotFound, jinja2.TemplateError):
        return ""


def _get_template_text(template_rel: str) -> str:
    """Return raw text content of a template file."""
    path = TEMPLATES_DIR / template_rel
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _dest_to_template(dest_rel: str) -> str | None:
    """Look up the template path for a given destination relative path."""
    for d, t in CANONICAL_FILES:
        if d == dest_rel:
            return t
    # Check scaffold files (Phase 7 docs with section-level comparison)
    for d, t in SCAFFOLD_FILES:
        if d == dest_rel:
            return t
    # Also check existence-check files (now empty, kept for compat)
    for d, t, _desc in EXISTENCE_CHECK_FILES:
        if d == dest_rel:
            return t
    return None


# ---------------------------------------------------------------------------
# Diff helper
# ---------------------------------------------------------------------------


def _make_diff(current_body: str, canonical_body: str, n: int = 10) -> str:
    """Return a unified diff between current_body and canonical_body, limited to n context lines."""
    current_lines = current_body.splitlines(keepends=True)
    canonical_lines = canonical_body.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            current_lines,
            canonical_lines,
            fromfile="current",
            tofile="canonical",
            n=n,
        )
    )
    return "".join(diff_lines)


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------


def sync_project(project_dir: Path, applies_to: str = "all", yes: bool = False) -> SyncResult:
    """
    Runs audit, then applies MISSING and INCONSISTENT items.
    Never modifies EXTRA items.
    Returns SyncResult describing what was changed and what was preserved.

    When yes=False, the user is prompted before each change. Declined changes
    are recorded in result.skipped.
    """
    project_dir = Path(project_dir).resolve()

    # Security: path traversal containment guard
    if not project_dir.is_dir() or len(project_dir.parts) < 3:
        click.echo(
            f"error: project-dir resolves to a suspicious path: {project_dir}",
            err=True,
        )
        sys.exit(1)

    result = SyncResult(project_dir=project_dir)

    # Load saved template context for rendering when creating/patching files
    context = _load_project_context(project_dir)

    # Load overrides: sections intentionally diverged from canonical templates
    overrides = _load_overrides(project_dir)

    # Run audit to get the delta
    audit = audit_project(project_dir, applies_to=applies_to)

    # Collect lesson IDs from MISSING items
    for item in audit.missing:
        if item.lesson_id and item.lesson_id not in result.lessons_applied:
            result.lessons_applied.append(item.lesson_id)

    # Group MISSING items by file
    missing_by_file: dict[str, list[AuditItem]] = {}
    for item in audit.missing:
        missing_by_file.setdefault(item.file, []).append(item)

    # Group INCONSISTENT items by file
    inconsistent_by_file: dict[str, list[AuditItem]] = {}
    for item in audit.inconsistent:
        inconsistent_by_file.setdefault(item.file, []).append(item)

    # Build scaffold-file set for quick lookup (Phase 7 docs with section-level comparison)
    scaffold_dests = {d for d, _t in SCAFFOLD_FILES}

    # Process files with MISSING items
    for dest_rel, items in missing_by_file.items():
        template_rel = _dest_to_template(dest_rel)
        if template_rel is None:
            continue

        # Scaffold files use enriched context with Phase 7 defaults
        if dest_rel in scaffold_dests:
            enriched_context = _enrich_scaffold_context(context)
            rendered_text = _render_template(template_rel, enriched_context) or _get_template_text(template_rel)
            project_path = project_dir / dest_rel
            if not project_path.exists():
                if not yes:
                    confirmed = click.confirm(
                        f"Create {dest_rel} (file missing)?",
                        default=False,
                    )
                    if not confirmed:
                        result.skipped.append(
                            f"{dest_rel} (file missing) (user declined)"
                        )
                        continue
                project_path.parent.mkdir(parents=True, exist_ok=True)
                project_path.write_text(rendered_text, encoding="utf-8")
                result.applied.append(f"Created {dest_rel} (file was missing)")
            else:
                # File exists but is missing some sections — append them
                canonical_sections = _split_sections(rendered_text)
                project_text = project_path.read_text(encoding="utf-8")
                changed = False
                for item in items:
                    section_key = item.section
                    if (dest_rel, section_key) in overrides:
                        click.echo(
                            f"  (skipped: .pairmode-overrides declares this section as project-owned)"
                        )
                        result.skipped.append(
                            f"{dest_rel}: section '{section_key}' (override declared)"
                        )
                        continue
                    if section_key in canonical_sections:
                        canonical_body = canonical_sections[section_key]
                        if not yes:
                            confirmed = click.confirm(
                                f"Append section '{section_key}' to {dest_rel}?",
                                default=False,
                            )
                            if not confirmed:
                                result.skipped.append(
                                    f"{dest_rel}: section '{section_key}' (user declined)"
                                )
                                continue
                        project_text = _append_section_to_file(
                            project_text, section_key, canonical_body
                        )
                        result.applied.append(
                            f"Appended section '{section_key}' to {dest_rel}"
                        )
                        changed = True
                if changed:
                    project_path.write_text(project_text, encoding="utf-8")
            continue

        rendered_text = _render_template(template_rel, context) or _get_template_text(template_rel)
        project_path = project_dir / dest_rel

        if not project_path.exists():
            # File is entirely missing — create it with rendered canonical content
            if not yes:
                confirmed = click.confirm(
                    f"Create {dest_rel} (file missing)?",
                    default=False,
                )
                if not confirmed:
                    result.skipped.append(
                        f"{dest_rel} (file missing) (user declined)"
                    )
                    continue
            project_path.parent.mkdir(parents=True, exist_ok=True)
            project_path.write_text(rendered_text, encoding="utf-8")
            result.applied.append(f"Created {dest_rel} (file was missing)")
        else:
            # File exists but is missing some sections — append them
            canonical_sections = _split_sections(rendered_text)
            project_text = project_path.read_text(encoding="utf-8")
            changed = False
            for item in items:
                section_key = item.section
                if (dest_rel, section_key) in overrides:
                    click.echo(
                        f"  (skipped: .pairmode-overrides declares this section as project-owned)"
                    )
                    result.skipped.append(
                        f"{dest_rel}: section '{section_key}' (override declared)"
                    )
                    continue
                if section_key in canonical_sections:
                    canonical_body = canonical_sections[section_key]
                    if not yes:
                        confirmed = click.confirm(
                            f"Append section '{section_key}' to {dest_rel}?",
                            default=False,
                        )
                        if not confirmed:
                            result.skipped.append(
                                f"{dest_rel}: section '{section_key}' (user declined)"
                            )
                            continue
                    project_text = _append_section_to_file(
                        project_text, section_key, canonical_body
                    )
                    result.applied.append(
                        f"Appended section '{section_key}' to {dest_rel}"
                    )
                    changed = True
            if changed:
                project_path.write_text(project_text, encoding="utf-8")

    # Process files with INCONSISTENT items (skipped when context file is absent)
    if audit.context_missing:
        click.echo(
            "Skipping INCONSISTENT patch: no pairmode_context.json — run bootstrap first.",
            err=True,
        )
        inconsistent_by_file = {}

    for dest_rel, items in inconsistent_by_file.items():
        template_rel = _dest_to_template(dest_rel)
        if template_rel is None:
            continue

        # Scaffold files use enriched context with Phase 7 defaults
        render_context = _enrich_scaffold_context(context) if dest_rel in scaffold_dests else context
        rendered_text = _render_template(template_rel, render_context) or _get_template_text(template_rel)
        canonical_sections = _split_sections(rendered_text)
        project_path = project_dir / dest_rel

        if not project_path.exists():
            # Shouldn't happen (inconsistent means file exists), but handle gracefully
            if not yes:
                confirmed = click.confirm(
                    f"Create {dest_rel} (file missing)?",
                    default=False,
                )
                if not confirmed:
                    result.skipped.append(
                        f"{dest_rel} (file missing) (user declined)"
                    )
                    continue
            project_path.parent.mkdir(parents=True, exist_ok=True)
            project_path.write_text(rendered_text, encoding="utf-8")
            result.applied.append(f"Created {dest_rel} (file was missing during inconsistent pass)")
            continue

        project_text = project_path.read_text(encoding="utf-8")
        changed = False
        for item in items:
            section_key = item.section
            if (dest_rel, section_key) in overrides:
                click.echo(
                    f"  (skipped: .pairmode-overrides declares this section as project-owned)"
                )
                result.skipped.append(
                    f"{dest_rel}: section '{section_key}' (override declared)"
                )
                continue
            if section_key in canonical_sections:
                canonical_body = canonical_sections[section_key]
                if not yes:
                    # Show diff before prompting
                    # Extract current body for this section
                    parts = _split_by_h2(project_text)
                    current_body = ""
                    for header, body in parts:
                        if _normalise(header) == section_key:
                            current_body = body
                            break
                    diff_text = _make_diff(current_body, canonical_body)
                    if diff_text:
                        click.echo(f"  (--- current  +++ canonical)")
                        click.echo(diff_text, nl=False)
                    confirmed = click.confirm(
                        f"Update section '{section_key}' in {dest_rel}?",
                        default=False,
                    )
                    if not confirmed:
                        result.skipped.append(
                            f"{dest_rel}: section '{section_key}' (user declined)"
                        )
                        continue
                project_text = _replace_section_in_file(project_text, section_key, canonical_body)
                result.applied.append(
                    f"Updated section '{section_key}' in {dest_rel} to match canonical"
                )
                changed = True
        if changed:
            project_path.write_text(project_text, encoding="utf-8")

    # Record EXTRA items as preserved
    for item in audit.extra:
        result.preserved.append(
            f"{item.file}: section '{item.section}' (project-specific)"
        )

    # Rail gap check: prompt to add default rails missing from docs/stories/
    stack = context.get("stack", "")
    missing_rails = _check_rail_gaps(project_dir, stack)
    for rail in missing_rails:
        click.echo(f"  \u26a0 Standard rail {rail} not in this project.")
        if not yes:
            confirmed = click.confirm(f"Add rail {rail}?", default=False)
        else:
            confirmed = True
        if confirmed:
            rail_dir = project_dir / "docs" / "stories" / rail
            rail_dir.mkdir(parents=True, exist_ok=True)
            era_path = _find_era(project_dir)
            if era_path is not None:
                _add_rail_to_era(era_path, rail)
            result.applied.append(f"Created rail directory docs/stories/{rail}/")

    # Update .companion/state.json
    state_path = project_dir / ".companion" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)

    existing_state: dict = {}
    if state_path.exists():
        try:
            existing_state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing_state = {}

    # Merge — do not overwrite other fields
    existing_state["pairmode_version"] = result.pairmode_version
    existing_state["last_sync"] = result.last_sync
    existing_state["lessons_applied"] = result.lessons_applied

    state_path.write_text(json.dumps(existing_state, indent=2), encoding="utf-8")

    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_sync_output(result: SyncResult) -> str:
    """Human-readable sync report."""
    lines: list[str] = []
    lines.append(f"SYNC COMPLETE — {result.project_dir.name}")
    lines.append("")

    if result.applied:
        lines.append("Applied:")
        for change in result.applied:
            lines.append(f"  \u2713 {change}")
        lines.append("")

    if result.preserved:
        lines.append("Preserved:")
        for item in result.preserved:
            lines.append(f"  \u2192 {item}")
        lines.append("")

    if result.skipped:
        lines.append("Skipped (user declined):")
        for item in result.skipped:
            lines.append(f"  \u2717 {item}")
        lines.append("")

    lines.append("State updated: .companion/state.json")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--project-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to the project directory to sync.",
)
@click.option(
    "--applies-to",
    default="all",
    show_default=True,
    help="Project type for lesson filtering (e.g. 'python', 'typescript', 'all').",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Apply all changes without prompting for confirmation.",
)
def main(project_dir: Path, applies_to: str, yes: bool) -> None:
    """Sync a project directory against canonical pairmode templates."""
    result = sync_project(project_dir, applies_to=applies_to, yes=yes)
    click.echo(format_sync_output(result))


if __name__ == "__main__":
    main()
