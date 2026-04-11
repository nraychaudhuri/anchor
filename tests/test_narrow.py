#!/usr/bin/env python3
"""Narrow down which combination fails."""
import asyncio
import json
import os
from pathlib import Path

auth_file = Path.home() / ".anchor" / "auth.json"
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = json.loads(auth_file.read_text())["oauth_token"]

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

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


async def run(prompt: str, system: str):
    opts = ClaudeAgentOptions(
        system_prompt=system,
        setting_sources=[],
        allowed_tools=[],
        disallowed_tools=[],
        max_turns=1,
        permission_mode="bypassPermissions",
    )
    opts.model = "claude-haiku-4-5-20251001"
    parts = []
    async for msg in query(prompt=prompt, options=opts):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
    return "".join(parts)


def test(name: str, prompt: str, system: str):
    print(f"\n--- {name} ---")
    print(f"  prompt: {prompt!r}")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run(prompt, system))
        finally:
            loop.close()
        print(f"  SUCCESS: {result[:80]!r}")
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {str(e)[:100]}")


SIMPLE = "Reply briefly."
CODE_FENCE_PROMPT = "USER: run this:\n```bash\nls -la\n```\n\nASSISTANT: Done"
SINGLE_BACKTICK_PROMPT = "say hello to `foo`"

# 4 combinations
test("single backtick + SIMPLE system", SINGLE_BACKTICK_PROMPT, SIMPLE)
test("single backtick + EXTRACTION_SYSTEM", SINGLE_BACKTICK_PROMPT, EXTRACTION_SYSTEM)
test("code fence + SIMPLE system", CODE_FENCE_PROMPT, SIMPLE)
test("code fence + EXTRACTION_SYSTEM", CODE_FENCE_PROMPT, EXTRACTION_SYSTEM)
