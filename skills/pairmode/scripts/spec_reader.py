"""spec_reader.py — Read all spec.json files for a project.

Reads .companion/product.json to find the spec_location, then loads every
spec.json found under <spec_location>/openspec/specs/*/spec.json.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def read_project_spec(companion_dir: Path) -> dict | None:
    """Read .companion/product.json to find spec_location, then read all
    spec.json files from <spec_location>/openspec/specs/*/spec.json.

    Returns None if no spec is found (missing product.json).
    Returns dict with keys:
      modules: list of spec dicts (full spec.json content per module)
      spec_location: Path
    """
    product_json = companion_dir / "product.json"
    if not product_json.exists():
        logger.debug("No product.json found at %s", product_json)
        return None

    try:
        product = json.loads(product_json.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read product.json: %s", exc)
        return None

    config_path_str = product.get("config")
    if not config_path_str:
        logger.warning("product.json has no 'config' key")
        return None

    config_path = Path(config_path_str)
    if not config_path.exists():
        logger.warning("Config file not found: %s", config_path)
        return None

    try:
        config = json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read config file %s: %s", config_path, exc)
        return None

    spec_location_str = config.get("spec_location")
    if not spec_location_str:
        logger.warning("Config has no 'spec_location' key")
        return None

    spec_location = Path(spec_location_str)
    specs_dir = spec_location / "openspec" / "specs"

    modules: list[dict] = []

    if specs_dir.exists():
        for spec_file in sorted(specs_dir.glob("*/spec.json")):
            try:
                spec_data = json.loads(spec_file.read_text())
                modules.append(spec_data)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Skipping malformed spec file %s: %s", spec_file, exc)

    return {
        "modules": modules,
        "spec_location": spec_location,
    }
