#!/usr/bin/env python3
"""Capture stderr from the CLI subprocess to see the real error."""
import asyncio
import json
import os
import sys
from pathlib import Path

auth_file = Path.home() / ".anchor" / "auth.json"
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = json.loads(auth_file.read_text())["oauth_token"]

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

stderr_lines = []


def capture_stderr(line: str):
    stderr_lines.append(line.rstrip())


async def run(prompt: str):
    opts = ClaudeAgentOptions(
        system_prompt="Reply briefly.",
        setting_sources=[],
        allowed_tools=[],
        max_turns=1,
        permission_mode="bypassPermissions",
        stderr=capture_stderr,
    )
    opts.model = "claude-haiku-4-5-20251001"
    parts = []
    async for msg in query(prompt=prompt, options=opts):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
    return "".join(parts)


# The one that fails
prompt = "echo `foo`"
print(f"Prompt: {prompt!r}")
stderr_lines.clear()
try:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run(prompt))
    finally:
        loop.close()
    print(f"SUCCESS: {result!r}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")

print("\n=== CAPTURED STDERR ===")
for line in stderr_lines:
    print(f"  {line}")
print(f"(total lines: {len(stderr_lines)})")
