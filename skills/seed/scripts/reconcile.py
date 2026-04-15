#!/usr/bin/env python3
"""
Seed skill — Reconcile agent.
Reads all extraction.json files from openspec/changes/
Merges into canonical openspec/specs/<module>/spec.json files.

Two operations per module:
  1. Update summary, business_rules, non_negotiables, tradeoffs via LLM merge
  2. Append lineage entry (append-only, never rewritten)

Usage:
  python3 reconcile.py <config_path> <modules_json_path>
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── LLM call ──────────────────────────────────────────────────────────────────


def call_claude(prompt: str, system_prompt: str) -> str | None:
    try:
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
    except ImportError:
        os.system("pip3 install claude-agent-sdk anyio --break-system-packages -q")
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

    async def _run():
        parts = []
        opts = ClaudeAgentOptions(
            system_prompt=system_prompt,
            tools=[],
            max_turns=1,
            permission_mode="bypassPermissions",
            extra_args={"setting-sources": ""},
        )
        opts.model = "claude-sonnet-4-6"
        async for msg in query(prompt=prompt, options=opts):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        parts.append(block.text)
        return "".join(parts)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            raw = loop.run_until_complete(_run())
        finally:
            loop.close()
        if not raw:
            return None
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return raw.strip()
    except Exception as e:
        print(f"LLM call error: {e}", file=sys.stderr)
        return None


# ── Load extractions ───────────────────────────────────────────────────────────


def load_all_extractions(spec_location: Path) -> list[dict]:
    """Load all extraction.json AND incremental.json files from changes/, sorted by date."""
    extractions = []
    changes_dir = spec_location / "openspec" / "changes"
    if not changes_dir.exists():
        return []
    for session_dir in sorted(changes_dir.iterdir()):
        # Load transcript-mined extraction
        f = session_dir / "extraction.json"
        if f.exists():
            try:
                extractions.append(json.loads(f.read_text()))
            except Exception:
                continue

        # Load incremental captures from sidebar
        inc = session_dir / "incremental.json"
        if inc.exists():
            try:
                inc_data = json.loads(inc.read_text())
                # Convert incremental captures to extraction format
                session_id = inc_data.get("session_id", session_dir.name)
                captures = inc_data.get("captures", [])
                plan_impact = inc_data.get("plan_impact", [])
                if captures or plan_impact:
                    extractions.append({
                        "has_planning_content": True,
                        "session_purpose": "Incremental captures from companion sidebar",
                        "_session_id": session_id,
                        "_session_date": (captures[0] if captures else plan_impact[0]).get("captured_at", "")[:10],
                        "business_rules": [c for c in captures if c.get("type") in ("business_rule", "non_negotiable")],
                        "non_negotiables": [c for c in captures if c.get("type") == "non_negotiable"],
                        "decisions": [c for c in captures if c.get("type") == "decision"],
                        "tradeoffs": [c for c in captures if c.get("type") == "tradeoff"],
                        "module_hints": list({c.get("module", "") for c in plan_impact if c.get("module")}),
                        "_plan_impact": plan_impact,
                    })
            except Exception:
                continue
    extractions.sort(key=lambda x: x.get("_session_date", ""))
    return extractions


# ── Load or create spec.json ───────────────────────────────────────────────────


def load_spec(spec_location: Path, module_name: str) -> dict:
    """Load existing spec.json or return empty skeleton."""
    spec_path = spec_location / "openspec" / "specs" / module_name / "spec.json"
    if spec_path.exists():
        try:
            return json.loads(spec_path.read_text())
        except Exception:
            pass
    return {
        "module": module_name,
        "last_updated": "",
        "summary": "",
        "business_rules": [],
        "non_negotiables": [],
        "tradeoffs": [],
        "conflicts": [],
        "lineage": [],
    }


def save_spec(spec_location: Path, spec: dict):
    module_name = spec["module"]
    spec_dir = spec_location / "openspec" / "specs" / module_name
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    (spec_dir / "spec.json").write_text(json.dumps(spec, indent=2))


# ── Assign items to modules ────────────────────────────────────────────────────


def assign_to_modules(extractions: list[dict], modules: list[dict]) -> dict:
    """
    Collect all extracted items across sessions, ask LLM to assign each to a module.
    Returns dict of module_name -> list of items with lineage metadata attached.
    """
    module_names = [m["name"] for m in modules]

    all_items = []
    for extraction in extractions:
        session_id = extraction.get("_session_id", "unknown")
        session_summary = extraction.get("_session_summary", "")
        session_date = extraction.get("_session_date", "")
        project_path = extraction.get("_project_path", "")
        resume_cmd = extraction.get("_resume_cmd", f"claude --resume {session_id}")
        hints = extraction.get("module_hints", [])

        meta = {
            "session_id": session_id,
            "session_summary": session_summary,
            "session_date": session_date,
            "project_path": project_path,
            "resume_cmd": resume_cmd,
            "module_hints": hints,
        }

        for rule in extraction.get("business_rules", []):
            all_items.append(
                {
                    **meta,
                    "item_type": "business_rule",
                    "text": rule.get("text", ""),
                    "confidence": rule.get("confidence", "high"),
                }
            )
        for rule in extraction.get("non_negotiables", []):
            all_items.append(
                {
                    **meta,
                    "item_type": "non_negotiable",
                    "text": rule.get("text", ""),
                    "confidence": rule.get("confidence", "high"),
                }
            )
        for t in extraction.get("tradeoffs", []):
            all_items.append(
                {
                    **meta,
                    "item_type": "tradeoff",
                    "decision": t.get("decision", ""),
                    "reason": t.get("reason", ""),
                    "accepted_cost": t.get("accepted_cost", ""),
                }
            )
        for d in extraction.get("decisions", []):
            all_items.append(
                {
                    **meta,
                    "item_type": "decision",
                    "text": d.get("text", ""),
                    "agreement_type": d.get("agreement_type", "explicit"),
                    "confidence": d.get("confidence", "high"),
                }
            )

    if not all_items:
        return {m: [] for m in module_names}

    items_for_llm = json.dumps(
        [
            {
                "index": i,
                "type": item["item_type"],
                "text": item.get("text") or item.get("decision", ""),
                "hints": item.get("module_hints", []),
            }
            for i, item in enumerate(all_items)
        ],
        indent=2,
    )

    modules_for_llm = json.dumps(
        [{"name": m["name"], "description": m.get("description", "")} for m in modules], indent=2
    )

    system = """Assign each knowledge item to its most relevant module.
If an item spans multiple modules, assign it to the most relevant one.
If no module fits, assign to 'general'.
Return ONLY valid JSON: {"assignments": [{"index": 0, "module": "<name>"}, ...]}"""

    raw = call_claude(f"Modules:\n{modules_for_llm}\n\nItems:\n{items_for_llm}", system)

    if not raw:
        fallback = module_names[0] if module_names else "general"
        assignments = {i: fallback for i in range(len(all_items))}
    else:
        try:
            result = json.loads(raw)
            assignments = {a["index"]: a["module"] for a in result.get("assignments", [])}
        except Exception:
            fallback = module_names[0] if module_names else "general"
            assignments = {i: fallback for i in range(len(all_items))}

    by_module: dict[str, list] = {m: [] for m in module_names}
    by_module["general"] = []
    for i, item in enumerate(all_items):
        mod = assignments.get(i, "general")
        if mod not in by_module:
            by_module[mod] = []
        by_module[mod].append(item)

    return by_module


# ── Merge items into spec ──────────────────────────────────────────────────────


def merge_into_spec(spec: dict, items: list[dict], module: dict) -> tuple[dict, list[dict]]:
    """
    Operation 1: Update summary, business_rules, non_negotiables, tradeoffs via LLM.
    Returns (updated_spec, conflicts_list).
    """
    if not items:
        return spec, []

    rules = [x for x in items if x["item_type"] in ("business_rule", "decision")]
    must_nots = [x for x in items if x["item_type"] == "non_negotiable"]
    tradeoffs = [x for x in items if x["item_type"] == "tradeoff"]

    new_items_text = json.dumps(
        {
            "business_rules": [x.get("text", "") for x in rules],
            "non_negotiables": [x.get("text", "") for x in must_nots],
            "tradeoffs": [
                {
                    "decision": x.get("decision", ""),
                    "reason": x.get("reason", ""),
                    "accepted_cost": x.get("accepted_cost", ""),
                }
                for x in tradeoffs
            ],
        },
        indent=2,
    )

    current_text = json.dumps(
        {
            "summary": spec.get("summary", ""),
            "business_rules": spec.get("business_rules", []),
            "non_negotiables": spec.get("non_negotiables", []),
            "tradeoffs": spec.get("tradeoffs", []),
        },
        indent=2,
    )

    system = f"""You are updating a product module spec with new information from planning sessions.

Module: {spec['module']}
Module description: {module.get('description', '')}

Rules:
- Stay at product/architecture level. No implementation details.
- business_rules and non_negotiables are plain strings.
- Merge new items into existing ones: deduplicate, keep most specific, flag contradictions.
- If a new item contradicts an existing one, add it to conflicts instead of merging.
- Rewrite the summary to reflect the current accumulated understanding (2-4 sentences).
- Preserve existing tradeoffs unless superseded.

Return ONLY valid JSON with these exact keys:
{{
  "summary": "updated summary",
  "business_rules": ["rule 1", "rule 2"],
  "non_negotiables": ["constraint 1"],
  "tradeoffs": [{{"decision": "...", "reason": "...", "accepted_cost": "..."}}],
  "conflicts": [{{"description": "...", "version_a": {{"text": "..."}}, "version_b": {{"text": "..."}}}}]
}}"""

    prompt = f"Current spec:\n{current_text}\n\nNew items from sessions:\n{new_items_text}"
    raw = call_claude(prompt, system)

    if not raw:
        print(f"  ! {spec['module']}: LLM merge failed, keeping existing spec", file=sys.stderr)
        return spec, []

    try:
        result = json.loads(raw)
        spec["summary"] = result.get("summary", spec.get("summary", ""))
        spec["business_rules"] = result.get("business_rules", spec.get("business_rules", []))
        spec["non_negotiables"] = result.get("non_negotiables", spec.get("non_negotiables", []))
        spec["tradeoffs"] = result.get("tradeoffs", spec.get("tradeoffs", []))
        conflicts = result.get("conflicts", [])
        return spec, conflicts
    except Exception as e:
        print(f"  ! {spec['module']}: merge parse error: {e}", file=sys.stderr)
        return spec, []


def append_lineage(spec: dict, items: list[dict], extraction: dict) -> dict:
    """
    Operation 2: Append one lineage entry per session that had items for this module.
    Append-only — never rewritten.
    """
    session_id = extraction.get("_session_id", "unknown")

    # don't add duplicate lineage entries
    existing_ids = {e.get("session_id") for e in spec.get("lineage", [])}
    if session_id in existing_ids:
        return spec

    key_decisions = []
    for item in items:
        text = item.get("text") or item.get("decision", "")
        if text:
            key_decisions.append(text[:120])

    if not key_decisions:
        return spec

    entry = {
        "session_id": session_id,
        "summary": extraction.get("_session_summary", ""),
        "date": extraction.get("_session_date", ""),
        "resume": extraction.get("_resume_cmd", f"claude --resume {session_id}"),
        "what_changed": extraction.get("session_purpose", "Planning session"),
        "key_decisions": key_decisions[:5],  # cap at 5 to keep lineage readable
    }

    if "lineage" not in spec:
        spec["lineage"] = []
    spec["lineage"].append(entry)
    return spec


# ── Main reconcile ─────────────────────────────────────────────────────────────


def reconcile(config_path: str, modules_json_path: str):
    config = json.loads(Path(config_path).read_text())
    spec_location = Path(config["spec_location"])
    modules = json.loads(Path(modules_json_path).read_text())

    print(f"\nReconciling {len(modules)} modules...", file=sys.stderr)

    extractions = load_all_extractions(spec_location)
    print(f"Loaded {len(extractions)} session extractions", file=sys.stderr)

    if not extractions:
        print(
            "No extractions found — creating empty spec.json stubs for new modules only.",
            file=sys.stderr,
        )
        for module in modules:
            spec_path = spec_location / "openspec" / "specs" / module["name"] / "spec.json"
            if not spec_path.exists():
                spec = load_spec(spec_location, module["name"])
                spec["summary"] = module.get("description", "")
                save_spec(spec_location, spec)
                print(f"  ✓ {module['name']}/spec.json — created stub", file=sys.stderr)
        return

    # assign all extracted items to modules
    print("Assigning items to modules...", file=sys.stderr)
    by_module = assign_to_modules(extractions, modules)

    # build a lookup from session_id -> extraction (for lineage appending)
    extraction_by_session = {e.get("_session_id"): e for e in extractions}

    all_conflicts = []

    for module in modules:
        module_name = module["name"]
        items = by_module.get(module_name, [])
        print(f"  {module_name}: {len(items)} items", file=sys.stderr)

        spec = load_spec(spec_location, module_name)

        # seed summary from module description if empty
        if not spec.get("summary") and module.get("description"):
            spec["summary"] = module["description"]

        # Operation 1: merge rules/summary via LLM
        if items:
            spec, conflicts = merge_into_spec(spec, items, module)
            if conflicts:
                for c in conflicts:
                    c["module"] = module_name
                all_conflicts.extend(conflicts)
                spec["conflicts"] = spec.get("conflicts", []) + conflicts

        # Operation 2: append lineage per session
        sessions_for_module: dict[str, list] = {}
        for item in items:
            sid = item.get("session_id")
            if sid and sid in extraction_by_session:
                if sid not in sessions_for_module:
                    sessions_for_module[sid] = []
                sessions_for_module[sid].append(item)

        for sid, session_items in sessions_for_module.items():
            spec = append_lineage(spec, session_items, extraction_by_session[sid])

        save_spec(spec_location, spec)
        print(
            f"  ✓ {module_name}/spec.json saved — "
            f"{len(spec.get('business_rules', []))} rules, "
            f"{len(spec.get('non_negotiables', []))} constraints, "
            f"{len(spec.get('tradeoffs', []))} tradeoffs, "
            f"{len(spec.get('lineage', []))} lineage entries",
            file=sys.stderr,
        )

    # handle unassigned items
    general_items = by_module.get("general", [])
    if general_items:
        general_module = {
            "name": "general",
            "description": "Cross-cutting concerns and general project constraints.",
        }
        spec = load_spec(spec_location, "general")
        if not spec.get("summary"):
            spec["summary"] = general_module["description"]
        spec, conflicts = merge_into_spec(spec, general_items, general_module)
        if conflicts:
            for c in conflicts:
                c["module"] = "general"
            all_conflicts.extend(conflicts)
        for sid, session_items in {
            item.get("session_id"): [
                i for i in general_items if i.get("session_id") == item.get("session_id")
            ]
            for item in general_items
        }.items():
            if sid and sid in extraction_by_session:
                spec = append_lineage(spec, session_items, extraction_by_session[sid])
        save_spec(spec_location, spec)

    # write conflicts_pending.json
    if all_conflicts:
        conflicts_path = spec_location / "openspec" / "conflicts_pending.json"
        conflicts_path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now().isoformat(),
                    "total": len(all_conflicts),
                    "conflicts": all_conflicts,
                },
                indent=2,
            )
        )
        print(
            f"\n⚠️  {len(all_conflicts)} conflicts need resolution: {conflicts_path}",
            file=sys.stderr,
        )
    else:
        print("\n✓ No conflicts detected", file=sys.stderr)

    config["last_seeded"] = datetime.now().isoformat()
    Path(config_path).write_text(json.dumps(config, indent=2))

    print(
        json.dumps(
            {
                "status": "complete",
                "modules": len(modules),
                "extractions_processed": len(extractions),
                "conflicts": len(all_conflicts),
            }
        )
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 reconcile.py <config_path> <modules.json>", file=sys.stderr)
        sys.exit(1)
    reconcile(sys.argv[1], sys.argv[2])
