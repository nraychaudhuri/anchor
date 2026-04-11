#!/usr/bin/env python3
"""Test workaround: use extra_args to actually pass --setting-sources."""
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
        tools=[],  # CORRECTLY disables all tools (passes --tools "")
        max_turns=1,
        permission_mode="bypassPermissions",
        extra_args={"setting-sources": ""},  # bypass setting_sources=[] falsy-list bug
    )
    opts.model = "claude-haiku-4-5-20251001"
    parts = []
    async for msg in query(prompt=prompt, options=opts):
        msg_type = type(msg).__name__
        if msg_type not in ("SystemMessage", "AssistantMessage", "ResultMessage", "UserMessage"):
            print(f"  [{msg_type}]")
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
    return "".join(parts)


# The failing prompt
prompt = "USER: run this:\n```bash\nls -la\n```\n\nASSISTANT: Done"
print(f"Prompt: {prompt!r}")
try:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run(prompt))
    finally:
        loop.close()
    print(f"SUCCESS: {result[:200]!r}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
