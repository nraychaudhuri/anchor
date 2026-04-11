#!/usr/bin/env python3
"""Run 5 sequential SDK calls in one process to see if/when it breaks."""
import asyncio
import json
import os
from pathlib import Path

auth_file = Path.home() / ".anchor" / "auth.json"
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = json.loads(auth_file.read_text())["oauth_token"]

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query


async def run(prompt: str):
    opts = ClaudeAgentOptions(
        system_prompt="Reply with just OK.",
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


def call_once(n: int, prompt: str):
    """Mirror sidebar.call_claude: new event loop per call."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run(prompt))
    finally:
        loop.close()


for i in range(1, 6):
    prompt = f"Test call #{i}: say hello briefly"
    print(f"\n--- Call {i} ---")
    try:
        result = call_once(i, prompt)
        print(f"SUCCESS: {result!r}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
