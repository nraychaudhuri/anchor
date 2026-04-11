#!/usr/bin/env python3
"""Single isolated call with a backtick — prove or disprove the hypothesis."""
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


prompt = "say hello to `foo`"
print(f"Prompt: {prompt!r}")
try:
    result = asyncio.run(run(prompt))
    print(f"SUCCESS: {result!r}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
