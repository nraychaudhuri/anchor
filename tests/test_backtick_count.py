#!/usr/bin/env python3
"""How many backticks in a row breaks it?"""
import asyncio
import json
import os
from pathlib import Path

auth_file = Path.home() / ".anchor" / "auth.json"
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = json.loads(auth_file.read_text())["oauth_token"]

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query


async def run(prompt: str):
    opts = ClaudeAgentOptions(
        system_prompt="Reply briefly.",
        setting_sources=[],
        allowed_tools=[],
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


def test(n: int):
    ticks = "`" * n
    prompt = f"echo {ticks}foo{ticks}"
    print(f"\n--- {n} backtick(s): {prompt!r} ---")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run(prompt))
        finally:
            loop.close()
        print(f"  SUCCESS: {result[:60]!r}")
    except Exception as e:
        print(f"  FAILED: {str(e)[:80]}")


for n in [1, 2, 3, 4]:
    test(n)
