"""spec_exception.py — Record a spec exception (protected-file override) into spec.json.

When a developer overrides a protected file, this module appends a conflict entry
to the relevant module's spec.json conflicts array, creating an audit trail.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path

# Allow running directly with: uv run python skills/pairmode/scripts/spec_exception.py
# or with PYTHONPATH=/mnt/work/anchor set
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from skills.pairmode.scripts import spec_reader  # noqa: E402
from skills.pairmode.scripts.story_context import match_file_to_module  # noqa: E402

logger = logging.getLogger(__name__)


def record_spec_exception(
    project_dir: Path,
    file_path: str,
    non_negotiable: str,
    override_reason: str,
    session_id: str,
) -> None:
    """Record a spec exception in the relevant module's spec.json conflicts array.

    Finds which module owns the file by consulting .companion/modules.json,
    then appends a conflict entry to that module's spec.json.

    Args:
        project_dir: Root directory of the project (where .companion/ lives).
        file_path: Path of the file that was overridden.
        non_negotiable: The non-negotiable rule that was violated.
        override_reason: Developer-supplied reason for the override.
        session_id: Session lineage identifier.
    """
    companion_dir = project_dir / ".companion"

    # --- Load modules list ---------------------------------------------------
    modules_json = companion_dir / "modules.json"
    if not modules_json.exists():
        logger.warning("modules.json not found at %s — cannot record spec exception", modules_json)
        return

    try:
        modules = json.loads(modules_json.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read modules.json: %s", exc)
        return

    # --- Identify owning module ---------------------------------------------
    module_name = match_file_to_module(file_path, modules)
    if not module_name:
        logger.warning(
            "file %r does not match any module in modules.json — skipping exception record",
            file_path,
        )
        return

    # --- Locate spec via two-hop path ---------------------------------------
    spec_result = spec_reader.read_project_spec(companion_dir)
    if spec_result is None:
        logger.warning(
            "Could not resolve spec location from product.json — skipping exception record"
        )
        return

    spec_location: Path = spec_result["spec_location"]

    # --- Path traversal guard -----------------------------------------------
    # Resolve spec_location and assert it is absolute before use.
    try:
        spec_location = spec_location.resolve()
    except OSError as exc:
        logger.warning("Failed to resolve spec_location %s: %s", spec_location, exc)
        return

    if not spec_location.is_absolute():
        logger.warning(
            "spec_location %s did not resolve to an absolute path — skipping", spec_location
        )
        return

    specs_root = (spec_location / "openspec" / "specs").resolve()
    try:
        spec_path = (spec_location / "openspec" / "specs" / module_name / "spec.json").resolve()
    except OSError as exc:
        logger.warning("Failed to resolve spec_path: %s", exc)
        return

    if not str(spec_path).startswith(str(specs_root) + "/") and spec_path != specs_root:
        logger.warning(
            "spec_path %s is outside specs boundary %s — skipping", spec_path, specs_root
        )
        return
    # -------------------------------------------------------------------------

    if not spec_path.exists():
        logger.warning("spec.json not found at %s — skipping exception record", spec_path)
        return

    # --- Read existing spec -------------------------------------------------
    try:
        spec = json.loads(spec_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read spec file %s: %s", spec_path, exc)
        return

    # --- Build conflict entry -----------------------------------------------
    conflict_entry = {
        "file": file_path,
        "non_negotiable": non_negotiable,
        "override_reason": override_reason,
        "date": date.today().isoformat(),
        "session_id": session_id,
        "status": "open",
    }

    spec.setdefault("conflicts", []).append(conflict_entry)

    # --- Write back ---------------------------------------------------------
    try:
        spec_path.write_text(json.dumps(spec, indent=2))
        logger.info(
            "Recorded spec exception for %r in module %r at %s",
            file_path,
            module_name,
            spec_path,
        )
    except OSError as exc:
        logger.warning("Failed to write spec file %s: %s", spec_path, exc)
