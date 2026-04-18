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
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from dataclasses import dataclass, field

try:
    from rich import box
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
except ImportError:
    os.system("pip3 install rich --break-system-packages -q")
    from rich import box
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text

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


# ── Mini session + chart ──────────────────────────────────────────────────────


@dataclass
class MiniSession:
    """State for one implementation cycle (between two stop events)."""

    modules: dict[str, str] = field(default_factory=dict)  # name -> "loaded" | "boundary"
    module_order: list[str] = field(default_factory=list)  # order of first touch
    files: list[dict] = field(default_factory=list)  # [{path, module, ts}] — last 5
    impact: list[dict] = field(default_factory=list)  # plan impact items
    plan_file: str | None = None
    active_module: str | None = None  # module of most recent file change
    status: str = ""  # shown in chart: "analyzing plan...", etc.
    started_at: str = ""


_modules_cache = None


def get_file_module(file_path: str, cwd: str) -> str | None:
    """Map a file path to its owning module using .companion/modules.json."""
    global _modules_cache
    if _modules_cache is None:
        try:
            _modules_cache = json.loads((Path(cwd) / ".companion" / "modules.json").read_text())
        except Exception:
            _modules_cache = []
    for module in _modules_cache:
        for path in module.get("paths", []):
            if path.rstrip("/") in file_path:
                return module["name"]
    return None


def build_chart(mini: MiniSession, loaded_modules: list[str]) -> Panel:
    """Build a Rich Panel showing the current mini session state."""
    lines = []

    # Module sequence with color differentiation
    if mini.module_order:
        mod_parts = []
        for name in mini.module_order:
            status = mini.modules.get(name, "loaded")
            if status == "boundary":
                mod_parts.append(f"[yellow]{name} ○[/yellow]")
            elif name == mini.active_module:
                mod_parts.append(f"[bold green]{name} ●[/bold green]")
            else:
                mod_parts.append(f"[green]{name} ●[/green]")
        # Also show loaded but untouched modules dimly
        for name in loaded_modules:
            if name not in mini.modules:
                mod_parts.append(f"[dim]{name}[/dim]")
        lines.append("  " + " ──→ ".join(mod_parts))
        lines.append("")

    # Impact section
    if mini.impact:
        adds = [i for i in mini.impact if i.get("classification") == "add"]
        modifies = [i for i in mini.impact if i.get("classification") == "modify"]
        confs = [i for i in mini.impact if i.get("classification") == "conflict"]

        if adds:
            for item in adds:
                lines.append(f"  [green]+[/green] {item.get('text', '')}")
        if modifies:
            for item in modifies:
                lines.append(f"  [yellow]~[/yellow] {item.get('text', '')}")
                existing = item.get("existing_rule")
                if existing:
                    lines.append(f"    [dim]was: {existing}[/dim]")
        if confs:
            for item in confs:
                lines.append(f"  [red]⚠[/red] {item.get('text', '')}")
                existing = item.get("existing_rule")
                if existing:
                    lines.append(f"    [dim]spec: {existing}[/dim]")
        lines.append("")

    # Files section — last 5
    if mini.files:
        for f in mini.files[-5:]:
            mod_tag = f.get("module", "")
            mod_label = f" [dim]\\[{mod_tag}][/dim]" if mod_tag else ""
            alert = " [yellow]⚠[/yellow]" if f.get("alert") else ""
            lines.append(f"  → {Path(f['path']).name}{mod_label}{alert}")

    # Status line
    if mini.status:
        lines.append("")
        lines.append(f"  [dim yellow]{mini.status}[/dim yellow]")

    content = "\n".join(lines) if lines else "[dim]waiting for file changes...[/dim]"
    return Panel(content, title="[bold]anchor[/bold]", border_style="dim", box=box.ROUNDED)


def update_mini_session(mini: MiniSession, event: dict, loaded_modules: list[str]):
    """Update mini session state from a post_tool_use event."""
    file_path = event.get("file_path", "")
    cwd = event.get("cwd", os.getcwd())
    ts = datetime.now().strftime("%H:%M:%S")

    if not file_path:
        return

    # Detect plan file — clear impact on re-edit so analysis re-triggers
    if ".claude/plans/" in file_path and file_path.endswith(".md"):
        if mini.plan_file == file_path and mini.impact:
            mini.impact = []
        mini.plan_file = file_path

    # Map file to module
    module = get_file_module(file_path, cwd)
    if module and module not in mini.modules:
        mini.module_order.append(module)
        if module in loaded_modules:
            mini.modules[module] = "loaded"
        else:
            mini.modules[module] = "boundary"

    # Track file — dedup by path, update timestamp if already seen
    is_boundary = module and module not in loaded_modules
    existing = next((f for f in mini.files if f["path"] == file_path), None)
    if existing:
        existing["ts"] = ts
    else:
        mini.files.append({
            "path": file_path,
            "module": module or "unknown",
            "ts": ts,
            "alert": is_boundary,
        })
        if len(mini.files) > 5:
            mini.files = mini.files[-5:]

    # Track active module for color differentiation
    mini.active_module = module


# ── LLM calls ─────────────────────────────────────────────────────────────────


def call_claude(prompt: str, system: str, model: str = "claude-haiku-4-5-20251001", timeout: int = 60) -> str | None:
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
            raw = loop.run_until_complete(asyncio.wait_for(_run(), timeout=timeout))
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

Return ONLY valid JSON with this structure:

{
  "items": [
    {
      "classification": "add | modify | conflict",
      "module": "which spec module this affects",
      "type": "business_rule | non_negotiable | tradeoff | decision",
      "text": "what the plan is saying",
      "existing_rule": "the spec rule this modifies/conflicts with (null for add)",
      "severity": "info | warning | violation",
      "evidence": "brief quote from the plan"
    }
  ],
  "summary": "one-line summary of what this plan means for the spec"
}

Rules:
- Stay at product/architecture level. No implementation details.
- Only flag "conflict" if the plan clearly contradicts a non-negotiable or established rule.
- "modify" means the plan refines an existing rule, not trivially restates it.
- If the plan has no spec-level impact, return empty items with a summary explaining why (e.g., "Deployment checklist — no architectural decisions or spec changes").
- severity: "info" for add, "warning" for modify, "warning" or "violation" for conflict."""


def extract_incremental(transcript_path: str, loaded_modules: list[str]) -> list[dict]:
    messages = read_last_messages(transcript_path, n=8)
    conversation = format_messages(messages)
    if not conversation.strip():
        return []

    existing_text = json.dumps([c.get("text", "") for c in captures[-15:]])
    existing_conflicts = json.dumps(
        [c.get("explanation", c.get("text", "")) for c in conflicts[-10:]]
    )
    raw = call_claude(
        f"Recent conversation:\n{conversation}\n\n"
        f"Already captured (do NOT re-extract):\n{existing_text}\n\n"
        f"Already raised as conflicts (do NOT re-raise):\n{existing_conflicts}",
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
        # Look up lineage for the existing rule's origin session
        lineage_line = ""
        if conflict.get("module") and conflict.get("existing_rule"):
            try:
                spec = load_spec(os.getcwd(), conflict["module"])
                if spec:
                    for entry in spec.get("lineage", []):
                        lineage_line = f"\n[dim]introduced: claude --resume {entry.get('session_id', '')}[/dim]"
                        break  # show most recent lineage entry
            except Exception:
                pass
        conflicts.append(conflict)
        cnum = len(conflicts)
        console.print(
            Panel(
                f"[{color}]{conflict.get('explanation', '')}[/{color}]\n\n"
                f"[dim]Existing rule:[/dim] {conflict.get('existing_rule', '')}\n"
                f"[dim]Module:[/dim] {conflict.get('module', '')}"
                f"{lineage_line}\n\n"
                f"[bold]\\[s{cnum}] snooze / \\[r{cnum}] record / \\[o{cnum}] override[/bold]",
                title=f"[bold {color}]⚠️  CONFLICT #{cnum}[/bold {color}]",
                border_style=color,
                box=box.ROUNDED,
            )
        )


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
                with lock:
                    conflicts.append(item)
                    cnum = len(conflicts)
                console.print(
                    Panel(
                        f"[{color}]Plan says:[/{color}] {item.get('text', '')}\n"
                        f"[dim]Existing rule ({item.get('type', 'rule')}):[/dim] {item.get('existing_rule', '')}\n"
                        f"[dim]Evidence:[/dim] {item.get('evidence', '')}\n\n"
                        f"[bold]\\[s{cnum}] snooze / \\[r{cnum}] record / \\[o{cnum}] override[/bold]",
                        title=f"[bold {color}]⚠️  CONFLICT #{cnum}[/bold {color}]",
                        border_style=color,
                        box=box.ROUNDED,
                    )
                )

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
    session_id = event.get("session_id", "unknown")

    # Build session summary from in-memory captures
    decisions = [c for c in captures if c.get("type") == "decision"]
    rules = [c for c in captures if c.get("type") in ("business_rule", "non_negotiable")]
    tradeoffs = [c for c in captures if c.get("type") == "tradeoff"]
    impact_conflicts = [c for c in captures if c.get("source") == "plan_impact" and c.get("classification") == "conflict"]

    summary_lines = []
    summary_lines.append(
        f"[bold]{len(captures)} captures[/bold] · "
        f"{len(decisions)} decisions · {len(rules)} rules · "
        f"{len(tradeoffs)} tradeoffs · {len(impact_conflicts)} conflicts"
    )

    # Show last few key captures
    recent = captures[-5:] if captures else []
    if recent:
        summary_lines.append("")
        for c in recent:
            icon = "•" if c.get("type") == "decision" else "📌" if c.get("type") in ("business_rule", "non_negotiable") else "⚖️" if c.get("type") == "tradeoff" else "•"
            summary_lines.append(f"  {icon} {c.get('text', '')[:80]}")

    summary_lines.append("")
    summary_lines.append(f"[dim]session:[/dim] {session_id}")
    summary_lines.append(f"[dim]resume:[/dim]  claude --resume {session_id}")
    summary_lines.append("")
    summary_lines.append("[dim]saved to incremental.json · will reconcile on next /anchor:companion[/dim]")

    console.print()
    console.print(
        Panel(
            "\n".join(summary_lines),
            title="[bold]session summary[/bold]",
            border_style="dim",
            box=box.ROUNDED,
        )
    )
    console.print()
    console.print("[bold]Session complete. You can close this terminal.[/bold]")
    console.print()
    console.print("[#d75f00]        ◉[/#d75f00]")
    console.print("[#d75f00]       ━┿━[/#d75f00]")
    console.print("[#d75f00]        │[/#d75f00]")
    console.print("[#d75f00]        │[/#d75f00]")
    console.print("[#d75f00]    ╭╴  │  ╶╮[/#d75f00]")
    console.print("[#d75f00]     ╰╮ │ ╭╯[/#d75f00]")
    console.print("[#d75f00]      ╰─┴─╯[/#d75f00]")
    console.print()
    os._exit(0)
    # Exit cleanly so the terminal shows [Process completed]
    os._exit(0)


# ── Conflict input listener ───────────────────────────────────────────────────


def conflict_input_listener():
    """
    Background thread that reads keyboard input for conflict actions.
    Accepts: s, r, o (acts on latest) or s1, r2, o3 (acts on specific conflict #)
    """
    import re
    cwd = os.getcwd()
    while True:
        try:
            key = input().strip().lower()
            # Parse action + optional number: s, r, o, s1, r2, o3
            match = re.match(r'^([sro])(\d*)$', key)
            if not match:
                continue
            action_key = match.group(1)
            num_str = match.group(2)

            with lock:
                if not conflicts:
                    continue
                if num_str:
                    idx = int(num_str) - 1  # 1-based to 0-based
                    if idx < 0 or idx >= len(conflicts):
                        console.print(f"[dim]  no conflict #{num_str}[/dim]")
                        continue
                    target = conflicts[idx]
                else:
                    idx = len(conflicts) - 1
                    target = conflicts[-1]

            if action_key == "s":
                handle_conflict_action(target, "snooze", "", cwd)
                console.print(f"[dim]  → snoozed #{idx + 1}[/dim]")
                with lock:
                    conflicts.pop(idx)

            elif action_key == "r":
                console.print("[dim]  note (enter to skip):[/dim] ", end="")
                try:
                    note = input().strip()
                except EOFError:
                    note = ""
                handle_conflict_action(target, "record", note, cwd)
                with lock:
                    conflicts.pop(idx)

            elif action_key == "o":
                console.print("[bold]Reason for override:[/bold] ", end="")
                reason = input().strip()
                handle_conflict_action(target, "override", reason, cwd)
                with lock:
                    conflicts.pop(idx)

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
    """Show the patient chart: loaded modules + non-negotiables (allergies)."""
    loaded_modules = state.get("last_loaded_modules", [])

    header_lines = []
    all_non_negs = []

    if loaded_modules:
        header_lines.append("  [dim]modules:[/dim] " + ", ".join(f"[bold]{n}[/bold]" for n in loaded_modules))

        for name in loaded_modules:
            try:
                cwd = os.getcwd()
                pointer = Path(cwd) / ".companion" / "product.json"
                ref = json.loads(pointer.read_text())
                config = json.loads(Path(ref["config"]).read_text())
                spec_p = Path(config["spec_location"]) / "openspec" / "specs" / name / "spec.json"
                if spec_p.exists():
                    spec = json.loads(spec_p.read_text())
                    for nn in spec.get("non_negotiables", []):
                        all_non_negs.append(nn if isinstance(nn, str) else str(nn))
            except Exception:
                pass

        if all_non_negs:
            header_lines.append("")
            header_lines.append("[dim]key points:[/dim]")
            for nn in all_non_negs[:8]:
                header_lines.append(f"  • {nn}")
    else:
        header_lines.append("[dim]no spec loaded — run /anchor:companion[/dim]")

    console.print(
        Panel(
            "\n".join(header_lines),
            title="[bold]Specs[/bold]",
            border_style="dim",
            box=box.ROUNDED,
        )
    )
    console.print()


def main():
    # Clear entire screen + move cursor to top — wipes shell login messages
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

    console.print()
    console.print("[#d75f00]        ◉[/#d75f00]")
    console.print("[#d75f00]       ━┿━[/#d75f00]     [bold #d75f00]Anchor[/bold #d75f00] [dim]v0.1.0[/dim]")
    console.print("[#d75f00]        │[/#d75f00]      [dim]context companion[/dim]")
    console.print("[#d75f00]        │[/#d75f00]")
    console.print("[#d75f00]    ╭╴  │  ╶╮[/#d75f00]")
    console.print("[#d75f00]     ╰╮ │ ╭╯[/#d75f00]")
    console.print("[#d75f00]      ╰─┴─╯[/#d75f00]")
    console.print()

    if not os.path.exists(PIPE_PATH):
        os.mkfifo(PIPE_PATH)

    state = get_state()
    render_startup(state)
    loaded_modules = state.get("last_loaded_modules", [])

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

    live = None
    mini = None

    def stop_live():
        nonlocal live, mini
        if live:
            try:
                live.stop()
            except Exception:
                pass
            live = None
        mini = None

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

                        if event_type == "post_tool_use":
                            # Start or update the live chart
                            if mini is None:
                                mini = MiniSession(started_at=datetime.now().strftime("%H:%M:%S"))
                            update_mini_session(mini, event, loaded_modules)

                            if live is None:
                                live = Live(build_chart(mini, loaded_modules), console=console, refresh_per_second=4)
                                live.start()
                            else:
                                live.update(build_chart(mini, loaded_modules))

                            # Plan file detection → run impact analysis inline
                            # (stop Live, analyze, restart — avoids thread/Live conflicts)
                            plan_path = event.get("file_path", "")
                            is_plan = ".claude/plans/" in plan_path and plan_path.endswith(".md")
                            if is_plan and not mini.impact:
                                if live:
                                    live.stop()
                                    live = None
                                console.print(f"[dim]{datetime.now().strftime('%H:%M:%S')} analyzing plan...[/dim]")
                                try:
                                    cwd = event.get("cwd", os.getcwd())
                                    content = Path(plan_path).read_text()[:20000]
                                    specs = load_all_specs(cwd, loaded_modules) if loaded_modules else {}
                                    # Compact spec context — only what's needed for classification
                                    compact = {}
                                    for n, s in specs.items():
                                        compact[n] = {
                                            "summary": s.get("summary", "")[:200],
                                            "business_rules": [r[:150] for r in s.get("business_rules", [])[:10]],
                                            "non_negotiables": [r[:200] for r in s.get("non_negotiables", [])],
                                        }
                                    spec_ctx = json.dumps(compact, indent=2) if compact else "{}"
                                    prompt = f"Canonical spec:\n{spec_ctx}\n\nPlan:\n{content}\n\nClassify each architectural decision."
                                    raw = call_claude(prompt, PLAN_IMPACT_SYSTEM, timeout=300)
                                    parsed = json.loads(raw) if raw else {}
                                    if isinstance(parsed, dict):
                                        mini.impact = parsed.get("items", [])
                                        mini.status = parsed.get("summary", "")
                                    elif isinstance(parsed, list):
                                        # backwards compat if model returns array
                                        mini.impact = parsed
                                except Exception as e:
                                    console.print(f"[red]  plan analysis error: {e}[/red]")
                                    log_error(f"Plan analysis error: {e}")
                                # Restart Live with updated chart
                                live = Live(build_chart(mini, loaded_modules), console=console, refresh_per_second=4)
                                live.start()

                        elif event_type == "stop":
                            stop_live()
                            # Run extraction in a thread (uses call_claude which needs the load-bearing print)
                            threading.Thread(target=handle_stop, args=(event,), daemon=True).start()

                        elif event_type == "exit_plan_mode":
                            # Persist captures — analysis already happened on plan file write
                            threading.Thread(target=handle_exit_plan_mode, args=(event,), daemon=True).start()

                        elif event_type == "refresh":
                            if live and mini:
                                live.update(build_chart(mini, loaded_modules))

                        elif event_type == "session_end":
                            stop_live()
                            console.print(f"[dim]{datetime.now().strftime('%H:%M:%S')} ← session ending...[/dim]")
                            threading.Thread(target=handle_session_end, args=(event,), daemon=True).start()

                    except json.JSONDecodeError:
                        continue

        except KeyboardInterrupt:
            stop_live()
            console.print("\n[dim]companion stopped[/dim]")
            break
        except Exception as e:
            stop_live()
            console.print(f"[red]  Pipe error: {e}[/red]")
            log_error(f"Pipe error: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()
