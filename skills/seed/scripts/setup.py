#!/usr/bin/env python3
"""
Seed skill — Step 0: Write product config from CLI args.
Called by Claude after gathering answers from the developer in chat.

Usage:
  python setup.py \
    --product "AgentLink" \
    --spec-location "/path/to/product-spec" \
    --project-hashes "hash1,hash2,hash3" \
    --cwd "/current/working/directory"
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

COMPANION_DIR = Path.home() / ".companion" / "products"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", required=True, help="Product name")
    parser.add_argument("--spec-location", required=True, help="Canonical spec path")
    parser.add_argument(
        "--project-hashes",
        required=True,
        help="Comma-separated project hashes from ~/.claude/projects/",
    )
    parser.add_argument("--cwd", required=True, help="Current working directory")
    args = parser.parse_args()

    cwd = Path(args.cwd)
    spec_location = args.spec_location
    product_name = args.product
    project_hashes = [h.strip() for h in args.project_hashes.split(",") if h.strip()]

    # build project list from hashes
    claude_projects_dir = Path.home() / ".claude" / "projects"
    projects = []
    for h in project_hashes:
        project_dir = claude_projects_dir / h
        sessions = len(list(project_dir.glob("*.jsonl"))) if project_dir.exists() else 0
        # reconstruct path from hash: strip leading dash, replace - with /
        abs_path = "/" + h.lstrip("-").replace("-", "/", 1)
        projects.append({"path": abs_path, "hash": h, "sessions": sessions})

    # write global config
    COMPANION_DIR.mkdir(parents=True, exist_ok=True)
    product_slug = product_name.lower().replace(" ", "-")
    product_dir = COMPANION_DIR / product_slug
    product_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "product": product_name,
        "spec_location": spec_location,
        "projects": projects,
        "created_at": datetime.now().isoformat(),
        "last_seeded": None,
    }

    config_path = product_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2))

    # write local pointer
    local_pointer = cwd / ".companion" / "product.json"
    local_pointer.parent.mkdir(parents=True, exist_ok=True)
    local_pointer.write_text(
        json.dumps({"product": product_name, "config": str(config_path)}, indent=2)
    )

    # create spec location directory
    Path(spec_location).mkdir(parents=True, exist_ok=True)

    print(f"CONFIG_PATH={config_path}")
    print(f"PRODUCT={product_name}")
    total_sessions = sum(p["sessions"] for p in projects)
    print(f"TOTAL_SESSIONS={total_sessions}")
    print(f"TOTAL_PROJECTS={len(projects)}")


if __name__ == "__main__":
    main()
