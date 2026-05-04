"""
bootstrap.py — Pairmode scaffold generator.

Writes pairmode scaffold files from Jinja2 templates into a target project
directory.  Existing files are not overwritten without explicit user
confirmation.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(_Path(__file__).parent))

import click
import jinja2

from skills.pairmode.scripts import spec_reader as _spec_reader
from skills.pairmode.scripts import checklist_deriver as _checklist_deriver
from skills.pairmode.scripts import denylist_deriver as _denylist_deriver
import ideology_parser as _ideology_parser
from schema_validator import _parse_frontmatter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAIRMODE_VERSION = "0.1.0"

PAIRMODE_DEFAULT_RAILS = {
    "generic": ["CORE", "INFRA", "TEST"],
    "web": ["API", "UI", "DB", "AUTH", "INFRA", "TEST"],
    "cli": ["CORE", "INFRA", "TEST"],
    "pairmode": ["BOOTSTRAP", "AUDIT", "RECONSTRUCT", "LESSON", "BUILD", "TEMPLATE", "AGENT", "INFRA"],
}

TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "templates"

# Mapping: destination path (relative to project_dir) → template name
# None as the template value means the file is written from a hard-coded
# skeleton string (phase-prompts.md and checkpoints.md are plain skeletons
# that the templates directory already provides as .j2 files).
SCAFFOLD_FILES: list[tuple[str, str]] = [
    ("CLAUDE.md", "CLAUDE.md.j2"),
    ("CLAUDE.build.md", "CLAUDE.build.md.j2"),
    (".pairmode-overrides", ".pairmode-overrides.j2"),
    ("docs/brief.md", "docs/brief.md.j2"),
    ("docs/ideology.md", "docs/ideology.md.j2"),
    ("docs/reconstruction.md", "docs/reconstruction.md.j2"),
    ("docs/architecture.md", "docs/architecture.md.j2"),
    ("docs/checkpoints.md", "docs/checkpoints.md.j2"),
    ("docs/cer/backlog.md", "docs/cer/backlog.md.j2"),
]

# Agent files — skipped if they already exist, unless --force-agents is passed.
# These are treated as project-owned after first bootstrap.
AGENT_FILES: list[tuple[str, str]] = [
    (".claude/agents/builder.md", "agents/builder.md.j2"),
    (".claude/agents/reviewer.md", "agents/reviewer.md.j2"),
    (".claude/agents/loop-breaker.md", "agents/loop-breaker.md.j2"),
    (".claude/agents/security-auditor.md", "agents/security-auditor.md.j2"),
    (".claude/agents/intent-reviewer.md", "agents/intent-reviewer.md.j2"),
    (".claude/agents/reconstruction-agent.md", "agents/reconstruction-agent.md.j2"),
]

# Default deny list written into .claude/settings.json
DEFAULT_DENY: list[str] = [
    "Edit(CLAUDE.md)",
    "Write(CLAUDE.md)",
    "Edit(CLAUDE.build.md)",
    "Write(CLAUDE.build.md)",
    "Edit(.claude/agents/**)",
    "Write(.claude/agents/**)",
    "Edit(docs/architecture.md)",
    "Write(docs/architecture.md)",
    "Edit(docs/phases/**)",
    "Write(docs/phases/**)",
    "Edit(docs/brief.md)",
    "Write(docs/brief.md)",
    "Edit(docs/ideology.md)",
    "Write(docs/ideology.md)",
    "Edit(docs/reconstruction.md)",
    "Write(docs/reconstruction.md)",
    "Edit(docs/RECONSTRUCTION.md)",
    "Write(docs/RECONSTRUCTION.md)",
]

# Universal checklist items always included in templates
UNIVERSAL_CHECKLIST_ITEMS: list[dict] = [
    {
        "name": "PROTECTED FILES",
        "description": "Were any protected files modified without a stated reason?",
        "severity": "HIGH",
    },
    {
        "name": "STORY SCOPE",
        "description": "Did the builder touch files outside the stated story scope?",
        "severity": "MEDIUM",
    },
    {
        "name": "BUILD GATE",
        "description": "Does the build command pass without errors?",
        "severity": "CRITICAL",
    },
    {
        "name": "IDEOLOGY ALIGNMENT",
        "description": "Does this implementation express the project ideology? Check docs/ideology.md.",
        "severity": "HIGH",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_build_command(project_dir: pathlib.Path) -> str | None:
    """Return a build command inferred from files present in project_dir."""
    if (project_dir / "pnpm-lock.yaml").exists() or (project_dir / "pnpm-workspace.yaml").exists():
        return "pnpm build && pnpm typecheck"
    if (project_dir / "pyproject.toml").exists() or (project_dir / "uv.lock").exists():
        return "uv run pytest"
    return None


def _render_template(template_name: str, context: dict) -> str:
    loader = jinja2.FileSystemLoader(str(TEMPLATES_DIR))
    env = jinja2.Environment(
        loader=loader,
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_name)
    return template.render(**context)


def _write_file(
    dest: pathlib.Path,
    content: str,
    dry_run: bool,
    yes: bool = False,
) -> bool:
    """
    Write *content* to *dest*.

    Returns True if the file was (or would be, in dry-run mode) written.
    If the file already exists and this is not a dry-run, prompts the user
    for confirmation before overwriting (unless *yes* is True).
    """
    if dry_run:
        click.echo(f"  [dry-run] would write: {dest}")
        return True

    if dest.exists() and not yes:
        overwrite = click.confirm(
            f"  {dest} already exists. Overwrite?", default=False
        )
        if not overwrite:
            click.echo(f"  skipped: {dest}")
            return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    click.echo(f"  wrote: {dest}")
    return True


def _glob_prefix(entry: str) -> tuple[str, str] | None:
    """If *entry* is a glob pattern like ``Tool(prefix/**)`` return ``(Tool, prefix/)``.

    Returns None for non-glob entries (no ``**`` suffix).
    """
    if not entry.endswith("/**)") and not entry.endswith("/**"):
        return None
    paren = entry.index("(")
    tool = entry[:paren]
    inner = entry[paren + 1 : -1]  # strip ( and )
    if inner.endswith("/**"):
        prefix = inner[: -len("/**")] + "/"
        return tool, prefix
    return None


def _is_subsumed(entry: str, globs: list[tuple[str, str]]) -> bool:
    """Return True if *entry* is already covered by one of *globs*.

    *globs* is a list of ``(tool, prefix/)`` pairs produced by ``_glob_prefix``.
    An entry ``Tool(path)`` is subsumed when there exists a glob with the same
    tool whose prefix is a proper prefix of ``path``.
    """
    paren = entry.find("(")
    if paren == -1:
        return False
    tool = entry[:paren]
    inner = entry[paren + 1 : -1]
    for g_tool, g_prefix in globs:
        if g_tool == tool and inner.startswith(g_prefix):
            return True
    return False


def _merge_deny_list(settings_path: pathlib.Path, new_entries: list[str]) -> None:
    """
    Merge *new_entries* into the permissions.deny array in settings_path.

    Creates the file if it does not exist.  Existing entries are preserved;
    duplicates are not added.  Existing entries that are subsumed by a new
    glob pattern (e.g. ``Edit(hooks/stop.py)`` subsumed by ``Edit(hooks/**)``)
    are removed to avoid redundancy.
    """
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    permissions = data.setdefault("permissions", {})
    deny: list[str] = permissions.get("deny", [])

    # Collect glob prefixes from the incoming new_entries so we can prune
    # existing specific entries that are now subsumed.
    incoming_globs: list[tuple[str, str]] = []
    for entry in new_entries:
        gp = _glob_prefix(entry)
        if gp:
            incoming_globs.append(gp)

    # Drop existing entries that are subsumed by an incoming glob.
    deny = [e for e in deny if not _is_subsumed(e, incoming_globs)]

    for entry in new_entries:
        if entry not in deny:
            deny.append(entry)

    permissions["deny"] = deny
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


def _record_state(state_path: pathlib.Path, version: str) -> None:
    """Write pairmode_version into .companion/state.json, creating if absent."""
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    data["pairmode_version"] = version
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _load_product_json(project_dir: pathlib.Path) -> dict:
    """Load .companion/product.json if it exists; return {} otherwise."""
    product_path = project_dir / ".companion" / "product.json"
    if product_path.exists():
        try:
            return json.loads(product_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _ideology_capture_flow() -> dict:
    """Prompt the developer for ideology content. Returns template context dict."""
    convictions: list[str] = []
    for i in range(1, 4):
        value = click.prompt(
            f"\nIdeology capture — core conviction #{i}\n"
            f"What does this project believe? (e.g. \"we prefer X over Y because Z\")\n"
            f"Enter conviction or press Enter to skip",
            default="",
            show_default=False,
        ).strip()
        if not value:
            break
        convictions.append(value)

    value_hierarchy_entry = click.prompt(
        "\nValue hierarchy — top entry\n"
        "When two values conflict, which wins?\n"
        "Enter or press Enter to skip",
        default="",
        show_default=False,
    ).strip()
    value_hierarchy = [value_hierarchy_entry] if value_hierarchy_entry else []

    constraint_rule = click.prompt(
        "\nAccepted constraint — most important rule\n"
        "What must this system never do?\n"
        "Enter constraint rule or press Enter to skip",
        default="",
        show_default=False,
    ).strip()
    constraints: list[dict] = []
    if constraint_rule:
        constraints.append({
            "name": "Constraint 1",
            "rule": constraint_rule,
            "protects": "_(to be filled in)_",
            "rationale": "_(to be filled in)_",
        })

    must_preserve_entry = click.prompt(
        "\nReconstruction — what must survive any implementation?\n"
        "Enter or press Enter to skip",
        default="",
        show_default=False,
    ).strip()
    must_preserve = [must_preserve_entry] if must_preserve_entry else []

    return {
        "convictions": convictions,
        "value_hierarchy": value_hierarchy,
        "constraints": constraints,
        "must_preserve": must_preserve,
    }


# ---------------------------------------------------------------------------
# Rail initialization helpers
# ---------------------------------------------------------------------------


def _infer_project_type(stack: str, project_name: str) -> str:
    """Infer project type from stack string and project name."""
    stack_lower = stack.lower()
    name_lower = project_name.lower()

    if "pairmode" in stack_lower or "pairmode" in name_lower:
        return "pairmode"

    web_keywords = {"web", "api", "ui", "flask", "django", "fastapi", "react", "vue"}
    if any(kw in stack_lower for kw in web_keywords):
        return "web"

    cli_keywords = {"cli", "terminal", "argparse", "click", "typer"}
    if any(kw in stack_lower for kw in cli_keywords):
        return "cli"

    return "generic"


def _build_era_001_content(project_name: str, rails: list[str]) -> str:
    """Build the content of docs/eras/001-initial.md."""
    name = f"{project_name} — Initial development"
    frontmatter = (
        "---\n"
        'id: "001"\n'
        f"name: {name}\n"
        "status: active\n"
        "---\n"
    )
    strategic_intent = (
        "\n"
        "## Strategic intent\n"
        "\n"
        "_(fill in)_\n"
    )
    rails_header = (
        "\n"
        "## Rails\n"
        "\n"
        "| Rail | Primary domain |\n"
        "|------|----------------|\n"
    )
    rails_rows = "".join(f"| {rail} | _(fill in)_ |\n" for rail in rails)

    phases_table = (
        "\n"
        "## Phases\n"
        "\n"
        "| Phase | Title | Status |\n"
        "|-------|-------|--------|\n"
    )

    return frontmatter + strategic_intent + rails_header + rails_rows + phases_table


def _initialize_rails(
    project_dir: pathlib.Path,
    context: dict,
    stack: str,
    dry_run: bool,
    ideology_skip: bool,
    yes: bool = False,
) -> None:
    """Initialize rail directories and Era 001 after scaffold write."""
    project_name = context.get("project_name", "project")
    project_type = _infer_project_type(stack, project_name)
    default_rails = PAIRMODE_DEFAULT_RAILS[project_type]

    # Determine confirmed rails
    skip_prompt = ideology_skip or yes or not sys.stdin.isatty()
    if skip_prompt:
        confirmed_rails = list(default_rails)
    else:
        click.echo(f"\nRail initialization (project type: {project_type})")
        click.echo("Suggested rails: " + ", ".join(default_rails))
        user_input = click.prompt(
            "Confirm rails (enter to accept, or type comma-separated list to override)",
            default="",
            show_default=False,
        ).strip()
        if user_input:
            confirmed_rails = [r.strip().upper() for r in user_input.split(",") if r.strip()]
        else:
            confirmed_rails = list(default_rails)

    if dry_run:
        for rail in confirmed_rails:
            click.echo(f"  [dry-run] would create: docs/stories/{rail}/")
        click.echo("  [dry-run] would create: docs/eras/001-initial.md")
        return

    # Create rail directories (idempotent)
    stories_dir = project_dir / "docs" / "stories"
    for rail in confirmed_rails:
        rail_dir = stories_dir / rail
        if rail_dir.exists():
            click.echo(f"  skipped (exists): docs/stories/{rail}/")
        else:
            rail_dir.mkdir(parents=True, exist_ok=True)
            click.echo(f"  created rail dir: docs/stories/{rail}/")

    # Create docs/eras/001-initial.md (idempotent)
    eras_dir = project_dir / "docs" / "eras"
    era_path = eras_dir / "001-initial.md"
    if era_path.exists():
        click.echo(f"  skipped (exists): docs/eras/001-initial.md")
    else:
        eras_dir.mkdir(parents=True, exist_ok=True)
        era_content = _build_era_001_content(project_name, confirmed_rails)
        era_path.write_text(era_content, encoding="utf-8")
        click.echo(f"  created: docs/eras/001-initial.md")

    # Update Phase 1 manifest to set era: "001" frontmatter (if present, no era yet)
    phases_dir = project_dir / "docs" / "phases"
    phase1_candidates = list(phases_dir.glob("phase-1.md")) + list(phases_dir.glob("001-*.md"))
    for phase_file in phase1_candidates:
        try:
            content = phase_file.read_text(encoding="utf-8")
        except OSError:
            continue
        # Only prepend era frontmatter if no era field exists yet
        existing_fm = _parse_frontmatter(content)
        if existing_fm is None or "era" not in existing_fm:
            content = '---\nera: "001"\n---\n\n' + content
            phase_file.write_text(content, encoding="utf-8")
            click.echo(f"  updated: {phase_file.relative_to(project_dir)} — added era: \"001\"")
        break  # Only update the first found


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--project-dir",
    default=".",
    show_default=True,
    help="Target project directory.",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
)
@click.option("--project-name", default=None, help="Project name (prompted if omitted).")
@click.option("--stack", default=None, help="Technology stack (prompted if omitted).")
@click.option("--what", default=None, help="What the project produces (prompted if omitted; blank allowed).")
@click.option("--why", default=None, help="Why the project exists (prompted if omitted; blank allowed).")
@click.option(
    "--build-command",
    default=None,
    help="Build/test command (inferred from project files if omitted, else prompted).",
)
@click.option(
    "--phase-title",
    default=None,
    help="Title for the initial phase-1.md (prompted in TTY if omitted; blank allowed).",
)
@click.option(
    "--phase-goal",
    default=None,
    help="Goal for the initial phase-1.md (prompted in TTY if omitted; blank allowed).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would be written without writing anything.",
)
@click.option(
    "--force-agents",
    is_flag=True,
    default=False,
    help="Overwrite existing agent files in .claude/agents/ even if already present.",
)
@click.option(
    "--ideology-skip",
    is_flag=True,
    default=False,
    help="Skip guided ideology capture; write placeholder ideology.md.",
)
@click.option(
    "--conviction",
    multiple=True,
    help="Core conviction (repeatable). Bypasses TTY prompt.",
)
@click.option(
    "--constraint",
    multiple=True,
    help="Key constraint rule (repeatable). Bypasses TTY prompt.",
)
@click.option(
    "--from-reconstruction",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to a reconstruction.md brief. Pre-populates ideology context.",
)
@click.option(
    "--yes", "-y",
    is_flag=True,
    default=False,
    help="Auto-confirm all prompts. Use for non-interactive/CI invocations.",
)
def bootstrap(
    project_dir: str,
    project_name: str | None,
    stack: str | None,
    what: str | None,
    why: str | None,
    build_command: str | None,
    phase_title: str | None,
    phase_goal: str | None,
    dry_run: bool,
    force_agents: bool,
    ideology_skip: bool,
    conviction: tuple[str, ...],
    constraint: tuple[str, ...],
    from_reconstruction: str | None,
    yes: bool,
) -> None:
    """Bootstrap a pairmode scaffold into PROJECT_DIR."""

    project_path = pathlib.Path(project_dir).resolve()

    # ------------------------------------------------------------------
    # 0. Security: path traversal containment guard
    # ------------------------------------------------------------------
    if not project_path.is_dir() or len(project_path.parts) < 3:
        click.echo(
            f"error: project-dir resolves to a suspicious path: {project_path}",
            err=True,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # 1. Gather values: CLI → product.json → prompt
    # ------------------------------------------------------------------
    product = _load_product_json(project_path)

    if project_name is None:
        project_name = product.get("project_name") or click.prompt("Project name")

    if stack is None:
        stack = click.prompt("Stack (e.g. Python / FastAPI / PostgreSQL)")

    if what is None:
        what = product.get("what") or (
            click.prompt("What does this project produce? (blank to skip)", default="")
            if sys.stdin.isatty() and not yes
            else ""
        )

    if why is None:
        why = product.get("why") or (
            click.prompt("Why does this project exist? (blank to skip)", default="")
            if sys.stdin.isatty() and not yes
            else ""
        )

    # Non-TTY/--yes warning: if what or why ended up blank, inform the user how to populate them.
    if (not sys.stdin.isatty() or yes) and (not what or not why):
        click.echo(
            "warning: non-interactive mode — docs/brief.md what/why left blank.\n"
            "         Pass --what and --why flags to populate, or edit docs/brief.md after bootstrap.",
            err=True,
        )

    if build_command is None:
        inferred = _infer_build_command(project_path)
        if inferred:
            build_command = inferred
        else:
            build_command = click.prompt(
                "Build command (e.g. pnpm build && pnpm typecheck)"
            )

    if phase_title is None:
        phase_title = (
            click.prompt("Phase 1 title (blank to leave as placeholder)", default="")
            if sys.stdin.isatty() and not yes
            else ""
        )

    if phase_goal is None:
        phase_goal = (
            click.prompt("Phase 1 goal (blank to skip)", default="")
            if sys.stdin.isatty() and not yes
            else ""
        )

    # test_command is derived from build_command for now
    test_command = build_command

    # ------------------------------------------------------------------
    # 1b. Ideology context: --from-reconstruction → CLI flags → TTY prompt → non-TTY placeholder
    # ------------------------------------------------------------------
    if from_reconstruction is not None:
        click.echo(f"  Reading reconstruction brief: {from_reconstruction}")
        ideology_context: dict = _ideology_parser.parse_reconstruction_brief(
            _Path(from_reconstruction)
        )
        # Normalize constraints: parse_reconstruction_brief returns {name, rule} dicts
        # but ideology.md.j2 expects {name, rule, protects, rationale} — fill defaults.
        normalized_constraints = []
        for c in ideology_context.get("constraints", []):
            normalized_constraints.append({
                "name": c.get("name", "Unnamed constraint"),
                "rule": c.get("rule", ""),
                "protects": c.get("protects", "_(to be filled in)_"),
                "rationale": c.get("rationale", "_(to be filled in)_"),
                "override_path": c.get("override_path", "Document the exception in spec.json conflicts with a stated reason before proceeding."),
            })
        ideology_context["constraints"] = normalized_constraints
    elif conviction or constraint:
        # CLI flags provided — use them directly, skip prompting
        ideology_context = {
            "convictions": list(conviction),
            "value_hierarchy": [],
            "constraints": [
                {
                    "name": f"Constraint {i + 1}",
                    "rule": rule,
                    "protects": "_(to be filled in)_",
                    "rationale": "_(to be filled in)_",
                }
                for i, rule in enumerate(constraint)
            ],
            "must_preserve": [],
        }
    elif sys.stdin.isatty() and not ideology_skip and not yes:
        ideology_context = _ideology_capture_flow()
    else:
        ideology_context = {}
        if not ideology_skip and not yes:
            click.echo(
                "warning: non-interactive mode — docs/ideology.md will be written as "
                "placeholder.\n"
                "         Pass --conviction or --constraint flags to populate, "
                "or edit docs/ideology.md after bootstrap.",
                err=True,
            )

    # ------------------------------------------------------------------
    # 2. Derive spec-based checklist and deny list (if spec present)
    # ------------------------------------------------------------------
    companion_dir = project_path / ".companion"
    spec = _spec_reader.read_project_spec(companion_dir)

    if spec is not None:
        modules = spec["modules"]

        # Load module_paths from .companion/modules.json
        modules_json_path = companion_dir / "modules.json"
        if modules_json_path.exists():
            try:
                raw_modules = json.loads(modules_json_path.read_text(encoding="utf-8"))
                module_paths: dict[str, list[str]] = {
                    entry["name"]: entry.get("paths", [])
                    for entry in raw_modules
                    if "name" in entry
                }
            except (json.JSONDecodeError, KeyError):
                module_paths = {}
        else:
            module_paths = {}

        derived_checklist = _checklist_deriver.derive_checklist(modules)
        derived_denylist = _denylist_deriver.derive_denylist(modules, module_paths)
    else:
        derived_checklist = []
        derived_denylist = []

    # The effective deny list: spec-derived when available, static default otherwise.
    effective_deny = (
        [rule["path_pattern"] for rule in derived_denylist]
        if derived_denylist
        else DEFAULT_DENY
    )

    # ------------------------------------------------------------------
    # 3. Build template context
    # ------------------------------------------------------------------
    context: dict = {
        "project_name": project_name,
        "project_description": product.get("project_description", ""),
        "stack": stack,
        "what": what or "",
        "why": why or "",
        "core_beliefs": "",
        "accepted_tradeoffs": "",
        # brief.md.j2 expects a string; ideology.md.j2 expects a list — use separate keys.
        "must_preserve_str": "",   # newline-joined string for brief.md.j2
        "must_preserve": [],       # list form for ideology.md.j2
        "operator_contact": product.get("operator_contact", ""),
        "build_command": build_command,
        "test_command": test_command,
        "migration_command": "",
        "domain_model": "",
        "checklist_items": derived_checklist,  # spec-derived only; universal items are hardcoded in templates
        "protected_paths": [],
        "non_negotiables": [],
        # architecture.md.j2 needs these; provide empty defaults
        "module_structure": [],
        "layer_rules": [],
        # agent templates need this
        "domain_isolation_rule": "",
        # CER backlog template variables
        "cer_entries": [],
        "last_updated": datetime.date.today().isoformat(),
        # ideology.md.j2 variables — all default to empty lists (renders placeholders)
        "convictions": ideology_context.get("convictions", []),
        "value_hierarchy": ideology_context.get("value_hierarchy", []),
        "constraints": ideology_context.get("constraints", []),
        "fingerprints": [],
        "should_question": ideology_context.get("should_question", []),
        "free_to_change": ideology_context.get("free_to_change", []),
        "comparison_dimensions": [],
        # reconstruction.md.j2 variables
        "reconstruction_what": what or "",
        "reconstruction_why": why or "",
        "generated_date": datetime.date.today().isoformat(),
    }
    # Merge ideology_context must_preserve into context.
    # must_preserve (list) → ideology.md.j2; must_preserve_str (string) → brief.md.j2.
    mp_list = ideology_context.get("must_preserve", [])
    context["must_preserve"] = mp_list
    context["must_preserve_str"] = "\n".join(f"- {item}" for item in mp_list) if mp_list else ""

    # ------------------------------------------------------------------
    # 4. Render and write scaffold files
    # ------------------------------------------------------------------
    if dry_run:
        click.echo("Dry run — no files will be written.\n")

    click.echo(f"Bootstrapping pairmode scaffold into {project_path}\n")

    for dest_rel, template_name in SCAFFOLD_FILES:
        dest = project_path / dest_rel
        try:
            content = _render_template(template_name, context)
        except jinja2.TemplateError as exc:
            click.echo(f"  ERROR rendering {template_name}: {exc}", err=True)
            sys.exit(1)
        _write_file(dest, content, dry_run=dry_run, yes=yes)

    # ------------------------------------------------------------------
    # 4a. Write per-phase structure (replaces legacy docs/phase-prompts.md)
    # ------------------------------------------------------------------
    _resolved_phase_title = phase_title if phase_title else "— fill in —"
    _resolved_phase_goal = phase_goal if phase_goal else ""
    phase_index_context = {
        "project_name": project_name,
        "phases": [
            {"id": 1, "title": _resolved_phase_title, "status": "planned", "file": "phase-1.md"},
        ],
    }
    phase_one_context = {
        "project_name": project_name,
        "phase_id": 1,
        "phase_title": _resolved_phase_title,
        "prev_phase": None,
        "next_phase": None,
        "goal": _resolved_phase_goal,
        "stories": [],
        "era_id": None,
    }
    for dest_rel, template_name, ctx in [
        ("docs/phases/index.md", "docs/phases/index.md.j2", phase_index_context),
        ("docs/phases/phase-1.md", "docs/phases/phase.md.j2", phase_one_context),
    ]:
        dest = project_path / dest_rel
        try:
            content = _render_template(template_name, ctx)
        except jinja2.TemplateError as exc:
            click.echo(f"  ERROR rendering {template_name}: {exc}", err=True)
            sys.exit(1)
        _write_file(dest, content, dry_run=dry_run, yes=yes)

    for dest_rel, template_name in AGENT_FILES:
        dest = project_path / dest_rel
        if not dry_run and dest.exists() and not force_agents:
            click.echo(
                f"  skipped (project-owned): {dest} — use --force-agents to overwrite"
            )
            continue
        try:
            content = _render_template(template_name, context)
        except jinja2.TemplateError as exc:
            click.echo(f"  ERROR rendering {template_name}: {exc}", err=True)
            sys.exit(1)
        if force_agents and not dry_run:
            # Overwrite without prompting — user explicitly requested this
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            click.echo(f"  wrote: {dest}")
        else:
            _write_file(dest, content, dry_run=dry_run, yes=yes)

    # ------------------------------------------------------------------
    # 4.5. Save template context for audit/sync rendering
    # ------------------------------------------------------------------
    context_path = project_path / ".companion" / "pairmode_context.json"
    serialisable_context = {
        "project_name": context["project_name"],
        "project_description": context["project_description"],
        "stack": context["stack"],
        "what": context["what"],
        "why": context["why"],
        "operator_contact": context["operator_contact"],
        "build_command": context["build_command"],
        "test_command": context["test_command"],
        "migration_command": context["migration_command"],
        "domain_model": context["domain_model"],
        "domain_isolation_rule": context["domain_isolation_rule"],
        "checklist_items": context["checklist_items"],
        "protected_paths": context["protected_paths"],
        "non_negotiables": context["non_negotiables"],
        "module_structure": context["module_structure"],
        "layer_rules": context["layer_rules"],
    }
    if dry_run:
        click.echo(f"  [dry-run] would save template context to: {context_path}")
    else:
        context_path.parent.mkdir(parents=True, exist_ok=True)
        context_path.write_text(json.dumps(serialisable_context, indent=2) + "\n", encoding="utf-8")
        click.echo(f"Saving template context to {context_path}")

    # ------------------------------------------------------------------
    # 5. Merge deny list into .claude/settings.json
    # ------------------------------------------------------------------
    settings_path = project_path / ".claude" / "settings.json"
    if dry_run:
        click.echo(f"\n  [dry-run] would merge deny list into: {settings_path}")
    else:
        click.echo(f"\nMerging deny list into {settings_path}")
        _merge_deny_list(settings_path, effective_deny)

    # ------------------------------------------------------------------
    # 6. Write deny-rationale sidecar
    # ------------------------------------------------------------------
    rationale_path = project_path / ".claude" / "settings.deny-rationale.json"
    rationale_data: dict = {
        "generated_by": "anchor:pairmode",
        "pairmode_version": PAIRMODE_VERSION,
        "rules": [
            {
                "pattern": rule["path_pattern"],
                "module": rule["module"],
                "non_negotiable": rule["non_negotiable"],
            }
            for rule in derived_denylist
        ],
    }
    if dry_run:
        click.echo(f"  [dry-run] would write deny rationale to: {rationale_path}")
    else:
        rationale_path.parent.mkdir(parents=True, exist_ok=True)
        rationale_path.write_text(
            json.dumps(rationale_data, indent=2) + "\n", encoding="utf-8"
        )
        click.echo(f"Writing deny rationale to {rationale_path}")

    # ------------------------------------------------------------------
    # 7. Record pairmode version
    # ------------------------------------------------------------------
    state_path = project_path / ".companion" / "state.json"
    if dry_run:
        click.echo(f"  [dry-run] would record pairmode_version in: {state_path}")
    else:
        click.echo(f"Recording pairmode_version in {state_path}")
        _record_state(state_path, PAIRMODE_VERSION)

    # ------------------------------------------------------------------
    # 8. Initialize rails and Era 001
    # ------------------------------------------------------------------
    click.echo("\nInitializing rails...")
    _initialize_rails(project_path, context, stack, dry_run=dry_run, ideology_skip=ideology_skip, yes=yes)

    click.echo("\nDone." if not dry_run else "\nDry run complete.")


if __name__ == "__main__":
    bootstrap()
