#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "rich>=13.0.0",
#   "claude-agent-sdk>=0.1.0",
#   "anyio>=4.0.0",
# ]
# ///
"""
Context Companion — sidebar process.
Runs in a tmux pane. Started manually by developer when they want the chart.

Single view that switches between:
  PLANNING    — shows live captures + conflict alerts
  IMPLEMENTATION — shows UML delta + spec violations

Conflict actions:
  s = snooze     (drop, nothing written)
  r = record     (write to conflicts_pending.json)
  o = override   (require reason, update spec, archive old rule)
"""
import asyncio
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
except ImportError:
    os.system("pip3 install rich --break-system-packages -q")
    from rich import box
    from rich.console import Console
    from rich.panel import Panel

PIPE_PATH = "/tmp/companion.pipe"
STATE_PATH = ".companion/state.json"

console = Console()
lock = threading.Lock()

# session state
captures = []  # planning mode captures
uml_deltas = []  # implementation mode file changes
conflicts = []  # pending conflict alerts

# ── Capture persistence ──────────────────────────────────────────────────────

_spec_location = None


def get_spec_location():
    global _spec_location
    if _spec_location is None:
        try:
            pointer = Path(os.getcwd()) / ".companion" / "product.json"
            ref = json.loads(pointer.read_text())
            config = json.loads(Path(ref["config"]).read_text())
            _spec_location = Path(config["spec_location"])
        except Exception:
            pass
    return _spec_location


def persist_capture(item: dict, session_id: str):
    """Append a capture to <spec_location>/openspec/changes/<session-id>/incremental.json."""
    spec_loc = get_spec_location()
    if not spec_loc or not session_id:
        return
    changes_dir = spec_loc / "openspec" / "changes" / session_id
    changes_dir.mkdir(parents=True, exist_ok=True)
    inc_path = changes_dir / "incremental.json"

    data = {"session_id": session_id, "captures": [], "plan_impact": []}
    if inc_path.exists():
        try:
            data = json.loads(inc_path.read_text())
        except Exception:
            pass

    source = item.get("source", "incremental")
    if source == "plan_impact":
        data.setdefault("plan_impact", []).append(item)
    else:
        data.setdefault("captures", []).append(item)

    inc_path.write_text(json.dumps(data, indent=2))


# ── LLM calls ─────────────────────────────────────────────────────────────────


def call_claude(prompt: str, system: str, model: str = "claude-haiku-4-5-20251001") -> str | None:
    try:
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
    except ImportError as e:
        console.print(f"[red]  SDK import failed: {e}[/red]")
        return None

    # Track state across the async iterator so we can recover after cleanup errors
    collected = {"parts": [], "result_msg": None}

    async def _run():
        opts = ClaudeAgentOptions(
            system_prompt=system,
            # tools=[] → passes --tools "" (disables all tools).
            # setting_sources=[] is a no-op due to SDK falsy-check bug, so use extra_args instead.
            tools=[],
            max_turns=1,
            permission_mode="bypassPermissions",
            hooks=None,
            agents=None,
            extra_args={"setting-sources": ""},
        )
        opts.model = model
        async for msg in query(prompt=prompt, options=opts):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        collected["parts"].append(block.text)
            elif type(msg).__name__ == "ResultMessage":
                collected["result_msg"] = msg

        return "".join(collected["parts"])

    def _finalize(raw: str | None) -> str | None:
        if not raw:
            return None
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return raw.strip()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            raw = loop.run_until_complete(asyncio.wait_for(_run(), timeout=60))
        finally:
            loop.close()
        console.print(f"[dim]  final parts: {len(collected['parts'])}, result_msg: {collected['result_msg'] is not None}[/dim]")
        return _finalize(raw)
    except asyncio.TimeoutError:
        console.print("[yellow]  timeout — skipping[/yellow]")
        return None
    except Exception as e:
        # The query may have completed successfully even if cleanup throws.
        # If we collected any assistant text, return it instead of failing.
        if collected["parts"]:
            console.print(
                f"[yellow]  cleanup error ({type(e).__name__}), but got {len(collected['parts'])} parts — using them[/yellow]"
            )
            return _finalize("".join(collected["parts"]))
        console.print(f"[red]  LLM error: {type(e).__name__}: {e!r}[/red]")
        log_error(f"LLM error: {e}")
        return None


# ── Transcript reading ─────────────────────────────────────────────────────────


def read_last_messages(transcript_path: str, n: int = 8) -> list[dict]:
    if not transcript_path or not os.path.exists(transcript_path):
        return []
    messages = []
    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    obj_type = obj.get("type", "")
                    if obj_type in ("user", "assistant"):
                        msg = obj.get("message", {})
                        role = msg.get("role", "") or obj_type
                        content = msg.get("content", "")
                        if isinstance(content, list):
                            content = " ".join(
                                c.get("text", "")
                                for c in content
                                if isinstance(c, dict) and c.get("type") == "text"
                            )
                        if content:
                            messages.append({"role": role, "content": content[:600]})
                except Exception:
                    continue
    except Exception:
        pass
    return messages[-n:]


def format_messages(messages: list[dict]) -> str:
    return "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)


# ── Load spec ─────────────────────────────────────────────────────────────────


def load_spec(cwd: str, module_name: str) -> dict | None:
    try:
        pointer = Path(cwd) / ".companion" / "product.json"
        ref = json.loads(pointer.read_text())
        config = json.loads(Path(ref["config"]).read_text())
        spec_path = Path(config["spec_location"]) / "openspec" / "specs" / module_name / "spec.json"
        if spec_path.exists():
            return json.loads(spec_path.read_text())
    except Exception:
        pass
    return None


def load_all_specs(cwd: str, module_names: list[str]) -> dict:
    """Load spec.json for each module. Returns dict of name -> spec."""
    specs = {}
    for name in module_names:
        spec = load_spec(cwd, name)
        if spec:
            specs[name] = spec
    return specs


# ── Planning: incremental extraction ──────────────────────────────────────────

EXTRACTION_SYSTEM = """You are the Historian in a context companion system.
Extract new knowledge from the recent planning conversation.

Return ONLY valid JSON array. Return [] if nothing new.
Keep everything at product/architecture level — no implementation details.

[
  {
    "type": "business_rule | non_negotiable | tradeoff | decision | conflict",
    "text": "concise statement",
    "evidence": "brief quote",
    "confidence": "high | medium | low",
    "agreement_type": "explicit | implicit | null",
    "accepted_cost": "only for tradeoffs"
  }
]"""


PLAN_IMPACT_SYSTEM = """You are analyzing a finalized plan against an existing canonical spec.
The plan was just approved and will drive implementation.
Your job: tell the developer what THIS PLAN MEANS for the spec.

For each architectural decision or rule in the plan, classify it as:
- "add": new rule/constraint/tradeoff not in the spec
- "modify": changes or refines an existing spec rule (include what the spec currently says)
- "conflict": directly contradicts a non-negotiable or existing rule

Return ONLY a JSON array. Return [] if the plan is purely tactical (no spec-level impact).

[
  {
    "classification": "add | modify | conflict",
    "module": "which spec module this affects",
    "type": "business_rule | non_negotiable | tradeoff | decision",
    "text": "what the plan is saying",
    "existing_rule": "the spec rule this modifies/conflicts with (null for add)",
    "severity": "info | warning | violation",
    "evidence": "brief quote from the plan"
  }
]

Rules:
- Stay at product/architecture level. No implementation details.
- Only flag "conflict" if the plan clearly contradicts a non-negotiable or established rule.
- "modify" means the plan refines an existing rule, not trivially restates it.
- If the plan is just "implement feature X using tool Y", that's tactical — return [].
- severity: "info" for add, "warning" for modify, "warning" or "violation" for conflict."""


def extract_incremental(transcript_path: str, loaded_modules: list[str]) -> list[dict]:
    messages = read_last_messages(transcript_path, n=8)
    conversation = format_messages(messages)
    if not conversation.strip():
        return []

    existing_text = json.dumps([c["text"] for c in captures[-10:]])
    raw = call_claude(
        f"Recent conversation:\n{conversation}\n\nAlready captured:\n{existing_text}",
        EXTRACTION_SYSTEM,
    )
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


# ── Planning: conflict check against spec ────────────────────────────────────


def check_conflicts(new_items: list[dict], specs: dict) -> list[dict]:
    """
    Compare new captures against loaded specs.
    Return list of conflicts needing developer attention.
    """
    if not new_items or not specs:
        return []

    all_rules = []
    for module_name, spec in specs.items():
        for rule in spec.get("business_rules", []):
            all_rules.append({"module": module_name, "type": "rule", "text": rule})
        for rule in spec.get("non_negotiables", []):
            all_rules.append({"module": module_name, "type": "non_negotiable", "text": rule})

    if not all_rules:
        return []

    system = """You check whether new planning decisions conflict with existing spec rules.

Return ONLY valid JSON array of conflicts found. Return [] if no conflicts.
[
  {
    "new_item": "what was just decided",
    "existing_rule": "the rule it conflicts with",
    "module": "which module",
    "rule_type": "rule | non_negotiable",
    "severity": "warning | violation",
    "explanation": "brief explanation of the conflict"
  }
]"""

    prompt = f"""New decisions/rules from this conversation:
{json.dumps([{"type": i["type"], "text": i["text"]} for i in new_items], indent=2)}

Existing spec rules:
{json.dumps(all_rules, indent=2)}"""

    raw = call_claude(prompt, system)
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


# ── Implementation: UML delta ─────────────────────────────────────────────────


def check_file_against_spec(file_path: str, cwd: str, loaded_modules: list[str]) -> dict | None:
    """
    Check which module a file belongs to and whether writing it
    violates any spec rules.
    Returns alert dict or None.
    """
    if not file_path or not loaded_modules:
        return None

    specs = load_all_specs(cwd, loaded_modules)
    if not specs:
        return None

    # find which module owns this file
    try:
        pointer = Path(cwd) / ".companion" / "product.json"
        ref = json.loads(pointer.read_text())
        config = json.loads(Path(ref["config"]).read_text())
        modules = json.loads((Path(cwd) / ".companion" / "modules.json").read_text())
    except Exception:
        return None

    owning_module = None
    for module in modules:
        for path in module.get("paths", []):
            if path.rstrip("/") in file_path:
                owning_module = module["name"]
                break
        if owning_module:
            break

    # check if file crosses into a non-loaded module
    if owning_module and owning_module not in loaded_modules:
        return {
            "type": "boundary_crossing",
            "file": file_path,
            "module": owning_module,
            "message": f"File belongs to {owning_module} — not in current session context",
            "severity": "warning",
        }

    # check non-negotiables: try to read the file and check
    if owning_module and owning_module in specs:
        non_negs = specs[owning_module].get("non_negotiables", [])
        if non_negs:
            try:
                file_content = Path(cwd, file_path).read_text()[:2000]
                system = """Check if this file content violates any non-negotiable spec rules.
Return ONLY valid JSON. Return null if no violations.
{
  "violation": "which rule",
  "evidence": "what in the file suggests the violation",
  "severity": "warning | violation"
}"""
                prompt = (
                    f"Non-negotiables:\n{json.dumps(non_negs)}\n\nFile content:\n{file_content}"
                )
                raw = call_claude(prompt, system)
                if raw and raw != "null":
                    result = json.loads(raw)
                    if result:
                        result["file"] = file_path
                        result["module"] = owning_module
                        result["type"] = "spec_violation"
                        return result
            except Exception:
                pass

    return None


# ── Conflict actions ──────────────────────────────────────────────────────────


def handle_conflict_action(conflict: dict, action: str, reason: str, cwd: str):
    """
    snooze  — drop, nothing written
    record  — write to conflicts_pending.json
    override — require reason, update spec, archive old rule
    """
    if action == "snooze":
        return

    if action == "record":
        try:
            pointer = Path(cwd) / ".companion" / "product.json"
            ref = json.loads(pointer.read_text())
            config = json.loads(Path(ref["config"]).read_text())
            spec_loc = Path(config["spec_location"])
            cp_path = spec_loc / "openspec" / "conflicts_pending.json"
            pending = []
            if cp_path.exists():
                data = json.loads(cp_path.read_text())
                pending = data.get("conflicts", [])
            entry = {**conflict, "recorded_at": datetime.now().isoformat(), "status": "pending"}
            if reason:
                entry["note"] = reason
            pending.append(entry)
            cp_path.write_text(
                json.dumps(
                    {
                        "generated_at": datetime.now().isoformat(),
                        "total": len(pending),
                        "conflicts": pending,
                    },
                    indent=2,
                )
            )
            if reason:
                console.print(f"[dim]  → recorded with note: {reason[:80]}[/dim]")
            else:
                console.print("[dim]  → recorded in conflicts_pending.json[/dim]")
        except Exception as e:
            log_error(f"Record conflict error: {e}")

    elif action == "override":
        if not reason.strip():
            console.print("[red]  Override requires a reason.[/red]")
            return
        try:
            module_name = conflict.get("module")
            if not module_name:
                return
            pointer = Path(cwd) / ".companion" / "product.json"
            ref = json.loads(pointer.read_text())
            config = json.loads(Path(ref["config"]).read_text())
            spec_loc = Path(config["spec_location"])
            spec_path = spec_loc / "openspec" / "specs" / module_name / "spec.json"
            if not spec_path.exists():
                return
            spec = json.loads(spec_path.read_text())

            # archive old rule
            old_rule = conflict.get("existing_rule", "")
            if "archived_rules" not in spec:
                spec["archived_rules"] = []
            spec["archived_rules"].append(
                {
                    "rule": old_rule,
                    "archived_at": datetime.now().isoformat(),
                    "reason": reason,
                    "replaced_by": conflict.get("new_item", ""),
                }
            )

            # remove old rule from active lists
            for key in ("business_rules", "non_negotiables"):
                if old_rule in spec.get(key, []):
                    spec[key].remove(old_rule)

            # add new rule
            new_item = conflict.get("new_item", "")
            if new_item:
                rule_type = conflict.get("rule_type", "rule")
                if rule_type == "non_negotiable":
                    spec.setdefault("non_negotiables", []).append(new_item)
                else:
                    spec.setdefault("business_rules", []).append(new_item)

            # append lineage entry
            spec.setdefault("lineage", []).append(
                {
                    "type": "override",
                    "old_rule": old_rule,
                    "new_rule": new_item,
                    "reason": reason,
                    "overridden_at": datetime.now().isoformat(),
                }
            )

            spec["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            spec_path.write_text(json.dumps(spec, indent=2))
            console.print(f"[green]  → spec updated · {module_name}[/green]")
        except Exception as e:
            log_error(f"Override error: {e}")


# ── Rendering ─────────────────────────────────────────────────────────────────


def render_planning(ts: str, new_captures: list[dict], new_conflicts: list[dict]):
    """Render only the NEW captures from this extraction, not the full history."""
    if new_captures:
        decisions = [c for c in new_captures if c.get("type") == "decision"]
        rules = [c for c in new_captures if c.get("type") in ("business_rule", "non_negotiable")]
        tradeoffs = [c for c in new_captures if c.get("type") == "tradeoff"]
        ruled_out = [c for c in new_captures if c.get("type") == "ruled_out"]

        if decisions:
            for c in decisions:
                flag = " [yellow]?[/yellow]" if c.get("agreement_type") == "implicit" else ""
                console.print(f"  [green]•[/green] {c.get('text', '')}{flag}")
                if c.get("agreement_type") == "implicit":
                    console.print("    [dim]implicit — confirm?[/dim]")

        if rules:
            for c in rules:
                icon = "🔒" if c.get("type") == "non_negotiable" else "📌"
                console.print(f"  {icon} {c.get('text', '')}")

        if tradeoffs:
            for c in tradeoffs:
                console.print(f"  [yellow]⚖️[/yellow]  {c.get('text', '')}")
                if c.get("accepted_cost"):
                    console.print(f"    [dim]cost: {c['accepted_cost']}[/dim]")

        if ruled_out:
            for c in ruled_out:
                console.print(f"  [dim]❌ {c.get('text', '')}[/dim]")

        console.print()

    # conflicts get their own prominent block
    for conflict in new_conflicts:
        severity = conflict.get("severity", "warning")
        color = "red" if severity == "violation" else "yellow"
        console.print(
            Panel(
                f"[{color}]{conflict.get('explanation', '')}[/{color}]\n\n"
                f"[dim]Existing rule:[/dim] {conflict.get('existing_rule', '')}\n"
                f"[dim]Module:[/dim] {conflict.get('module', '')}\n\n"
                f"[bold]Action: \\[s]nooze / \\[r]ecord / \\[o]verride[/bold]",
                title=f"[bold {color}]⚠️  CONFLICT[/bold {color}]",
                border_style=color,
                box=box.ROUNDED,
            )
        )
        conflicts.append(conflict)


def render_plan_impact(adds: list[dict], modifies: list[dict], confs: list[dict]):
    """Render the spec-impact analysis after plan-complete.

    Three buckets:
      - adds: new rules/decisions introduced by the plan (green)
      - modifies: changes/refinements to existing spec rules (yellow)
      - confs: conflicts with existing rules / non-negotiables (red)
    """
    ts = datetime.now().strftime("%H:%M:%S")
    console.print(f"\n[bold]{ts} ✓ plan complete · impact analysis[/bold]\n")

    if adds:
        # group by module
        by_mod: dict[str, list[dict]] = {}
        for item in adds:
            by_mod.setdefault(item.get("module", "unknown"), []).append(item)
        for mod, items in by_mod.items():
            console.print(f"[bold green]+ adds to {mod}[/bold green]")
            for item in items:
                console.print(f"  [green]•[/green] [{item.get('type', 'decision')}] {item.get('text', '')}")

    if modifies:
        by_mod = {}
        for item in modifies:
            by_mod.setdefault(item.get("module", "unknown"), []).append(item)
        for mod, items in by_mod.items():
            console.print(f"\n[bold yellow]~ modifies {mod}[/bold yellow]")
            for item in items:
                console.print(f"  [yellow]•[/yellow] {item.get('text', '')}")
                existing = item.get("existing_rule")
                if existing:
                    console.print(f"    [dim]was:[/dim] {existing}")

    if confs:
        by_mod = {}
        for item in confs:
            by_mod.setdefault(item.get("module", "unknown"), []).append(item)
        for mod, items in by_mod.items():
            console.print(f"\n[bold red]⚠ conflicts with {mod}[/bold red]")
            for item in items:
                severity = item.get("severity", "warning")
                color = "red" if severity == "violation" else "yellow"
                console.print(
                    Panel(
                        f"[{color}]Plan says:[/{color}] {item.get('text', '')}\n"
                        f"[dim]Existing rule ({item.get('type', 'rule')}):[/dim] {item.get('existing_rule', '')}\n"
                        f"[dim]Evidence:[/dim] {item.get('evidence', '')}\n\n"
                        f"[bold]Action: \\[s]nooze / \\[r]ecord / \\[o]verride[/bold]",
                        title=f"[bold {color}]⚠️  CONFLICT[/bold {color}]",
                        border_style=color,
                        box=box.ROUNDED,
                    )
                )
                # Also add to global conflicts list so the input listener can act on it
                with lock:
                    conflicts.append(item)

    console.print()


def render_implementation(file_path: str, alert: dict | None):
    """Append implementation mode output."""
    ts = datetime.now().strftime("%H:%M:%S")

    with lock:
        uml_deltas.append({"ts": ts, "file": file_path, "alert": alert})

    console.print(f"[dim]{ts} → {file_path}[/dim]")

    if alert:
        severity = alert.get("severity", "warning")
        color = "red" if severity == "violation" else "yellow"
        atype = alert.get("type", "")

        if atype == "boundary_crossing":
            console.print(f"  [yellow]⚠️  boundary: {alert['message']}[/yellow]")
        elif atype == "spec_violation":
            console.print(
                Panel(
                    f"[{color}]{alert.get('evidence', '')}[/{color}]\n\n"
                    f"[dim]Rule violated:[/dim] {alert.get('violation', '')}\n"
                    f"[dim]Module:[/dim] {alert.get('module', '')}\n\n"
                    f"[bold]Action: \\[s]nooze / \\[r]ecord / \\[o]verride[/bold]",
                    title=f"[bold {color}]⚠️  SPEC VIOLATION[/bold {color}]",
                    border_style=color,
                    box=box.ROUNDED,
                )
            )
            conflicts.append(alert)
        console.print()


# ── Event handlers ────────────────────────────────────────────────────────────


def handle_stop(event: dict):
    transcript = event.get("transcript_path")
    loaded_modules = event.get("loaded_modules", [])
    cwd = event.get("cwd", os.getcwd())

    ts = datetime.now().strftime("%H:%M:%S")
    console.print(f"[dim]{ts} ← stop event, extracting...[/dim]")

    new_items = extract_incremental(transcript, loaded_modules)
    if not new_items:
        console.print("[dim]  · nothing new[/dim]")
        return

    session_id = event.get("session_id", "")
    added = 0
    for item in new_items:
        if isinstance(item, dict) and item.get("type"):
            item["captured_at"] = datetime.now().isoformat()
            item["source"] = "incremental"
            with lock:
                captures.append(item)
            persist_capture(item, session_id)
            added += 1

    if not added:
        console.print("[dim]  · nothing new[/dim]")
        return

    ts = datetime.now().strftime("%H:%M:%S")
    console.print(f"[dim]{ts} ✓ {added} capture(s)[/dim]")

    # check new captures against spec
    new_conflicts = []
    if loaded_modules:
        specs = load_all_specs(cwd, loaded_modules)
        new_conflicts = check_conflicts(new_items, specs)

    render_planning(ts, new_items, new_conflicts)


def handle_post_tool_use(event: dict):
    file_path = event.get("file_path", "")
    loaded_modules = event.get("loaded_modules", [])
    cwd = event.get("cwd", os.getcwd())

    if not file_path:
        return

    alert = check_file_against_spec(file_path, cwd, loaded_modules)
    render_implementation(file_path, alert)


def handle_exit_plan_mode(event: dict):
    ts = datetime.now().strftime("%H:%M:%S")
    plan = (event.get("plan", "") or "").strip()
    loaded_modules = event.get("loaded_modules", []) or []
    cwd = event.get("cwd", os.getcwd())

    if not plan:
        console.print(
            f"\n[dim]{ts} ← plan complete (no plan content) · implementation mode active[/dim]\n"
        )
        return

    console.print(f"\n[dim]{ts} ← plan complete, analyzing impact on spec...[/dim]")

    # Load spec context for the prompt
    specs = load_all_specs(cwd, loaded_modules) if loaded_modules else {}
    if specs:
        compact_specs = {
            name: {
                "summary": s.get("summary", ""),
                "business_rules": s.get("business_rules", []),
                "non_negotiables": s.get("non_negotiables", []),
                "tradeoffs": s.get("tradeoffs", []),
            }
            for name, s in specs.items()
        }
        spec_context = json.dumps(compact_specs, indent=2)
    else:
        spec_context = "{}"

    prompt = (
        f"Canonical spec (loaded modules):\n{spec_context}\n\n"
        f"Finalized plan:\n{plan}\n\n"
        "Classify each architectural decision in the plan against the spec."
    )

    raw = call_claude(prompt, PLAN_IMPACT_SYSTEM)
    try:
        items = json.loads(raw) if raw else []
    except Exception:
        items = []

    if not isinstance(items, list) or not items:
        console.print("[dim]  · no spec-level impact[/dim]")
        console.print("[dim]  Implementation mode active. Watching file changes.[/dim]\n")
        return

    # Save each item to captures and persist to disk
    session_id = event.get("session_id", "")
    for item in items:
        if isinstance(item, dict):
            item["captured_at"] = datetime.now().isoformat()
            item["source"] = "plan_impact"
            with lock:
                captures.append(item)
            persist_capture(item, session_id)

    # Bucket by classification
    adds = [i for i in items if isinstance(i, dict) and i.get("classification") == "add"]
    modifies = [i for i in items if isinstance(i, dict) and i.get("classification") == "modify"]
    confs = [i for i in items if isinstance(i, dict) and i.get("classification") == "conflict"]

    render_plan_impact(adds, modifies, confs)
    console.print("[dim]  Implementation mode active. Watching file changes.[/dim]\n")


def handle_session_end(event: dict):
    transcript = event.get("transcript_path")
    session_id = event.get("session_id", "unknown")
    cwd = event.get("cwd", os.getcwd())

    console.print("\n[dim]Session ending — running final extraction...[/dim]")

    # run mine_sessions.py on this session's transcript
    if transcript:
        try:
            import subprocess

            pointer = Path(cwd) / ".companion" / "product.json"
            ref = json.loads(pointer.read_text())
            config_path = ref["config"]
            skill_path = Path(__file__).parent.parent.parent / "seed" / "scripts" / "mine_sessions.py"
            if skill_path.exists():
                result = subprocess.run(
                    ["uv", "run", "python", str(skill_path), config_path, transcript],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                console.print(f"[dim]  mining: {result.stdout.strip()[:100]}[/dim]")

                # run reconcile
                reconcile_path = skill_path.parent / "reconcile.py"
                modules_path = Path(cwd) / ".companion" / "modules.json"
                if reconcile_path.exists() and modules_path.exists():
                    result2 = subprocess.run(
                        ["uv", "run", "python", str(reconcile_path), config_path, str(modules_path)],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    console.print(f"[dim]  reconcile: {result2.stderr.strip()[-200:]}[/dim]")
                    console.print("[bold green]✓ Spec updated[/bold green]")
        except Exception as e:
            console.print(f"[red]  Session end error: {e}[/red]")
            log_error(f"Session end processing error: {e}")
            console.print(f"[dim red]  extraction failed: {e}[/dim red]")

    console.print("[dim]companion: session closed[/dim]\n")


# ── Conflict input listener ───────────────────────────────────────────────────


def conflict_input_listener():
    """
    Background thread that reads keyboard input for conflict actions.
    s = snooze, r = record, o = override (prompts for reason)
    """
    cwd = os.getcwd()
    while True:
        try:
            key = input().strip().lower()
            with lock:
                if not conflicts:
                    continue
                latest = conflicts[-1]

            if key == "s":
                handle_conflict_action(latest, "snooze", "", cwd)
                console.print("[dim]  → snoozed[/dim]")
                with lock:
                    conflicts.pop()

            elif key == "r":
                console.print("[dim]  note (enter to skip):[/dim] ", end="")
                try:
                    note = input().strip()
                except EOFError:
                    note = ""
                handle_conflict_action(latest, "record", note, cwd)
                with lock:
                    conflicts.pop()

            elif key == "o":
                console.print("[bold]Reason for override:[/bold] ", end="")
                reason = input().strip()
                handle_conflict_action(latest, "override", reason, cwd)
                with lock:
                    conflicts.pop()

        except EOFError:
            break
        except Exception:
            continue


# ── Logging ───────────────────────────────────────────────────────────────────


def log_error(msg: str):
    try:
        with open(".companion/errors.log", "a") as f:
            f.write(f"{datetime.now().isoformat()} {msg}\n")
    except Exception:
        pass


# ── Main loop ─────────────────────────────────────────────────────────────────


def get_state() -> dict:
    try:
        return json.loads(open(STATE_PATH).read())
    except Exception:
        return {}


def render_startup(state: dict):
    """Show header + loaded spec context on sidebar startup."""
    loaded_modules = state.get("last_loaded_modules", [])

    # build header content
    header_lines = []

    if loaded_modules:
        header_lines.append("")
        header_lines.append("[dim]Loaded context:[/dim]")
        for name in loaded_modules:
            # try to read summary from spec.json
            summary = ""
            try:
                cwd = os.getcwd()
                pointer = Path(cwd) / ".companion" / "product.json"
                ref = json.loads(pointer.read_text())
                config = json.loads(Path(ref["config"]).read_text())
                spec_p = Path(config["spec_location"]) / "openspec" / "specs" / name / "spec.json"
                if spec_p.exists():
                    spec = json.loads(spec_p.read_text())
                    summary = spec.get("summary", "")[:80]
            except Exception:
                pass
            if summary:
                header_lines.append(f"  [bold]{name}[/bold]")
                header_lines.append(f"  [dim]{summary}[/dim]")
            else:
                header_lines.append(f"  [bold]{name}[/bold]")
    else:
        header_lines.append("[dim]no spec loaded — run /companion[/dim]")

    console.print(
        Panel(
            "\n".join(header_lines),
            title="[bold]context companion[/bold]",
            border_style="dim",
            box=box.ROUNDED,
        )
    )
    console.print("[dim]s=snooze  r=record  o=override  (conflicts only)[/dim]\n")


def main():
    if not os.path.exists(PIPE_PATH):
        os.mkfifo(PIPE_PATH)

    state = get_state()
    render_startup(state)

    # Diagnostics: verify env for LLM calls
    import shutil
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    console.print(
        f"[dim]token: {'set (' + str(len(token)) + ' chars)' if token else 'NOT SET'} | "
        f"claude: {shutil.which('claude') or 'NOT FOUND'}[/dim]"
    )

    # start conflict input listener
    t = threading.Thread(target=conflict_input_listener, daemon=True)
    t.start()

    while True:
        try:
            with open(PIPE_PATH) as pipe:
                for line in pipe:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        event_type = event.get("event")
                        ts = datetime.now().strftime("%H:%M:%S")

                        if event_type == "stop":
                            threading.Thread(target=handle_stop, args=(event,), daemon=True).start()

                        elif event_type == "exit_plan_mode":
                            console.print(
                                f"[dim]{ts} ← plan complete, running deep extraction...[/dim]"
                            )
                            threading.Thread(
                                target=handle_exit_plan_mode, args=(event,), daemon=True
                            ).start()

                        elif event_type == "post_tool_use":
                            threading.Thread(
                                target=handle_post_tool_use, args=(event,), daemon=True
                            ).start()

                        elif event_type == "session_end":
                            console.print(f"[dim]{ts} ← session ending...[/dim]")
                            threading.Thread(
                                target=handle_session_end, args=(event,), daemon=True
                            ).start()

                    except json.JSONDecodeError:
                        continue

        except KeyboardInterrupt:
            console.print("\n[dim]companion stopped[/dim]")
            break
        except Exception as e:
            console.print(f"[red]  Pipe error: {e}[/red]")
            log_error(f"Pipe error: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()
