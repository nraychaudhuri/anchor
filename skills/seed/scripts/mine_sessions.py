#!/usr/bin/env python3
"""
Seed skill — Session miner.
Called by subagent for a batch of transcript files.
Extracts decisions, rules, tradeoffs per session.
Writes openspec/changes/<session-id>/ entries.

Fault tolerance:
  - Retries Haiku up to 3 times with 5s backoff on empty response
  - Falls back to Sonnet if Haiku fails all retries
  - Checkpoint file prevents re-mining already-processed sessions
  - Threshold: 2 messages + 500 chars (was: 4 messages)
  - Skips sessions already in openspec/changes/ (idempotent)

Usage:
  python3 mine_sessions.py <config_path> <transcript_file1> [<transcript_file2> ...]
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Transcript reading ─────────────────────────────────────────────────────────


def read_transcript(jsonl_path: Path) -> list[dict]:
    messages = []
    try:
        with open(jsonl_path) as f:
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
                        if content and role in ("user", "assistant"):
                            messages.append({"role": role, "content": content[:1000]})
                except Exception:
                    continue
    except Exception as e:
        print(f"Error reading {jsonl_path}: {e}", file=sys.stderr)
    return messages


def get_session_summary(project_dir: Path, session_id: str) -> str:
    index_path = project_dir / "sessions-index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text())
            for session in index.get("sessions", []):
                if session.get("id") == session_id:
                    return session.get("summary", session.get("firstUserMessage", ""))[:200]
        except Exception:
            pass
    return ""


def format_conversation(messages: list[dict], max_chars: int = 8000) -> str:
    lines = []
    total = 0
    for m in messages:
        line = f"{m['role'].upper()}: {m['content']}"
        total += len(line)
        if total > max_chars:
            lines.append(f"[... conversation truncated at {max_chars} chars ...]")
            break
        lines.append(line)
    return "\n\n".join(lines)


# ── LLM extraction with retry + fallback ──────────────────────────────────────

EXTRACTION_SYSTEM = """You are mining a historical Claude Code session transcript for structured knowledge.

Session ID: {session_id}
Session summary: {session_summary}

Extract from this conversation:
1. business_rules — constraints on system behavior (SHALL statements)
2. non_negotiables — absolute prohibitions (SHALL NOT)
3. tradeoffs — conscious choices with accepted costs
4. ruled_out — options explicitly rejected with reasons
5. decisions — things agreed upon (note if implicit)
6. module_hints — what part of the codebase was being discussed

Be conservative — only extract things clearly stated or agreed upon.
Keep everything at product/architecture level — no implementation details.
For implicit agreements, flag confidence as medium.

Return ONLY valid JSON:
{{
  "has_planning_content": true | false,
  "module_hints": ["<module name>"],
  "business_rules": [{{"text": "...", "evidence": "...", "confidence": "high|medium"}}],
  "non_negotiables": [{{"text": "...", "evidence": "...", "confidence": "high|medium"}}],
  "tradeoffs": [{{"decision": "...", "reason": "...", "accepted_cost": "...", "evidence": "..."}}],
  "ruled_out": [{{"option": "...", "reason": "...", "evidence": "..."}}],
  "decisions": [{{"text": "...", "evidence": "...", "agreement_type": "explicit|implicit", "confidence": "high|medium"}}],
  "session_purpose": "one line description of what this session was about"
}}

Return empty arrays for categories with nothing to extract.
Return has_planning_content: false if this session has no architectural decisions."""


def _call_sdk(conversation: str, system: str, model: str) -> str | None:
    """Single SDK call. Returns raw text or None."""
    try:
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
    except ImportError:
        os.system("pip3 install claude-agent-sdk anyio --break-system-packages -q")
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

    async def _run():
        parts = []
        opts = ClaudeAgentOptions(
            system_prompt=system, allowed_tools=[], max_turns=1, permission_mode="bypassPermissions"
        )
        opts.model = model
        async for msg in query(prompt=conversation, options=opts):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        parts.append(block.text)
        return "".join(parts)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
    except Exception as e:
        print(f"    SDK error ({model}): {e}", file=sys.stderr)
        return None


def call_claude_extract(conversation: str, session_id: str, session_summary: str) -> dict | None:
    """
    Extract planning content from a conversation.
    Retry Haiku up to 3 times with 5s backoff.
    Fall back to Sonnet if all Haiku attempts fail.
    """
    system = EXTRACTION_SYSTEM.format(
        session_id=session_id, session_summary=session_summary or "No summary available"
    )

    # Wrap transcript clearly so the model treats it as content to analyze, not instructions
    conversation = (
        "Analyze the following transcript and return ONLY the JSON extraction. "
        "Do not ask questions or request clarification — extract what you can.\n\n"
        "<transcript>\n" + conversation + "\n</transcript>"
    )

    def parse_raw(raw: str) -> dict | None:
        if not raw:
            return None
        raw = raw.strip()
        # strip markdown code fences
        if raw.startswith("```"):
            parts = raw.split("```")
            # take content between first pair of fences
            if len(parts) >= 3:
                raw = parts[1]
            else:
                raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception as e:
            print(f"    Parse error for {session_id[:8]}: {e}", file=sys.stderr)
            print(f"    Raw response (first 200 chars): {raw[:200]}", file=sys.stderr)
            return None

    # Try Haiku up to 3 times with exponential backoff
    for attempt in range(3):
        raw = _call_sdk(conversation, system, "claude-haiku-4-5-20251001")
        result = parse_raw(raw)
        if result is not None:
            return result
        if attempt < 2:
            wait = 5 * (attempt + 1)  # 5s, 10s
            print(
                f"    Haiku empty for {session_id[:8]}, retry {attempt + 1}/2 in {wait}s...",
                file=sys.stderr,
            )
            time.sleep(wait)

    # Fall back to Sonnet with 2 attempts
    print(f"    Haiku failed 3x for {session_id[:8]}, trying Sonnet...", file=sys.stderr)
    for attempt in range(2):
        raw = _call_sdk(conversation, system, "claude-sonnet-4-6")
        result = parse_raw(raw)
        if result is not None:
            print(f"    Sonnet fallback succeeded for {session_id[:8]}", file=sys.stderr)
            return result
        if attempt < 1:
            print(f"    Sonnet retry for {session_id[:8]} in 10s...", file=sys.stderr)
            time.sleep(10)

    print(f"    All models failed for {session_id[:8]}", file=sys.stderr)
    return None


# ── Checkpoint ─────────────────────────────────────────────────────────────────


def load_checkpoint(config_path: str) -> dict:
    checkpoint_path = Path(config_path).parent / "mined_sessions.json"
    if checkpoint_path.exists():
        try:
            return json.loads(checkpoint_path.read_text())
        except Exception:
            pass
    return {}


def save_checkpoint(config_path: str, checkpoint: dict):
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    (Path(config_path).parent / "mined_sessions.json").write_text(json.dumps(checkpoint, indent=2))


# ── Write change entry ─────────────────────────────────────────────────────────


def write_change_entry(
    spec_location: Path,
    session_id: str,
    session_summary: str,
    session_date: str,
    project_path: str,
    extraction: dict,
):
    changes_dir = spec_location / "openspec" / "changes" / session_id
    changes_dir.mkdir(parents=True, exist_ok=True)
    resume_cmd = f"claude --resume {session_id}"

    # proposal.md
    proposal = f"""# {extraction.get('session_purpose', 'Planning session')}

## Session
- ID: `{session_id}`
- Summary: "{session_summary}"
- Date: {session_date}
- Project: {project_path}
- Resume: `{resume_cmd}`

## Purpose
{extraction.get('session_purpose', 'Planning and architectural decisions.')}
"""
    ruled_out = extraction.get("ruled_out", [])
    if ruled_out:
        proposal += "\n## Options Considered and Rejected\n"
        for item in ruled_out:
            proposal += f"\n### {item.get('option', 'Option')}\n"
            proposal += f"**Rejected because:** {item.get('reason', '')}\n"
            if item.get("evidence"):
                proposal += f"**Evidence:** \"{item['evidence'][:200]}\"\n"
    (changes_dir / "proposal.md").write_text(proposal)

    # design.md
    design = (
        f"# Design Decisions\n\n## Session\n- Resume: `{resume_cmd}`\n- Date: {session_date}\n\n"
    )
    tradeoffs = extraction.get("tradeoffs", [])
    if tradeoffs:
        design += "## Tradeoffs\n"
        for t in tradeoffs:
            design += f"\n### {t.get('decision', 'Decision')[:60]}\n"
            design += f"**Chose:** {t.get('decision', '')}\n"
            design += f"**Because:** {t.get('reason', '')}\n"
            design += f"**Accepted cost:** {t.get('accepted_cost', '')}\n"
            if t.get("evidence"):
                design += f"**Evidence:** \"{t['evidence'][:200]}\"\n"
    decisions = extraction.get("decisions", [])
    if decisions:
        design += "\n## Decisions Made\n"
        for d in decisions:
            flag = " ⚠️ implicit" if d.get("agreement_type") == "implicit" else ""
            design += f"\n- {d.get('text', '')}{flag}\n"
            if d.get("evidence"):
                design += f"  - Evidence: \"{d['evidence'][:200]}\"\n"
            design += f"  - Confidence: {d.get('confidence', 'high')}\n"
    (changes_dir / "design.md").write_text(design)

    # extraction.json for reconciler
    extraction["_session_id"] = session_id
    extraction["_session_summary"] = session_summary
    extraction["_session_date"] = session_date
    extraction["_project_path"] = project_path
    extraction["_resume_cmd"] = resume_cmd
    (changes_dir / "extraction.json").write_text(json.dumps(extraction, indent=2))

    return changes_dir


# ── Main ───────────────────────────────────────────────────────────────────────


def mine_batch(config_path: str, transcript_paths: list[str]):
    config = json.loads(Path(config_path).read_text())
    spec_location = Path(config["spec_location"])
    checkpoint = load_checkpoint(config_path)

    results = []
    skipped = 0
    too_short = 0
    failed = 0

    for transcript_path in transcript_paths:
        tp = Path(transcript_path)
        if not tp.exists():
            continue

        session_id = tp.stem
        project_dir = tp.parent
        project_hash = project_dir.name
        project_path = "/" + project_hash.lstrip("-").replace("-", "/", 1)

        # skip if already successfully mined (checkpoint)
        if checkpoint.get(session_id, {}).get("success"):
            skipped += 1
            continue

        # skip if changes entry already on disk (idempotent re-run)
        if (spec_location / "openspec" / "changes" / session_id / "extraction.json").exists():
            checkpoint[session_id] = {"success": True, "skipped": True}
            skipped += 1
            continue

        session_date = datetime.fromtimestamp(tp.stat().st_mtime).strftime("%Y-%m-%d")
        session_summary = get_session_summary(project_dir, session_id)
        messages = read_transcript(tp)
        total_chars = sum(len(m["content"]) for m in messages)

        # threshold: 2 messages + 500 chars minimum
        if len(messages) < 2 or total_chars < 500:
            too_short += 1
            checkpoint[session_id] = {
                "success": False,
                "reason": "too_short",
                "messages": len(messages),
                "chars": total_chars,
            }
            save_checkpoint(config_path, checkpoint)
            continue

        conversation = format_conversation(messages)
        print(
            f"  Mining {session_id[:8]}... ({len(messages)} messages, {total_chars} chars)",
            file=sys.stderr,
        )

        extraction = call_claude_extract(conversation, session_id, session_summary)

        if not extraction or not extraction.get("has_planning_content"):
            reason = "no_planning_content" if extraction else "extraction_failed"
            failed += 1
            checkpoint[session_id] = {"success": False, "reason": reason}
            save_checkpoint(config_path, checkpoint)
            continue

        write_change_entry(
            spec_location, session_id, session_summary, session_date, project_path, extraction
        )

        checkpoint[session_id] = {
            "success": True,
            "mined_at": datetime.now().isoformat(),
            "rules": len(extraction.get("business_rules", [])),
            "decisions": len(extraction.get("decisions", [])),
        }
        save_checkpoint(config_path, checkpoint)
        results.append(
            {
                "session_id": session_id,
                "module_hints": extraction.get("module_hints", []),
                "has_content": True,
            }
        )
        print(
            f"  ✓ {session_id[:8]} → "
            f"{len(extraction.get('business_rules', []))} rules, "
            f"{len(extraction.get('decisions', []))} decisions",
            file=sys.stderr,
        )

    save_checkpoint(config_path, checkpoint)

    print(
        json.dumps({"mined": results, "skipped": skipped, "too_short": too_short, "failed": failed})
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: python3 mine_sessions.py <config_path> <transcript1.jsonl> ...", file=sys.stderr
        )
        sys.exit(1)
    mine_batch(sys.argv[1], sys.argv[2:])
