#!/usr/bin/env python3
"""Test: claude_agent_sdk with OAuth token from a standalone script"""
import asyncio
import os
import shutil

TOKEN = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
print(f"Token: {TOKEN[:20]}..." if TOKEN else "No token set")
print(f"Claude binary: {shutil.which('claude') or 'NOT FOUND'}")

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query


async def main():
    opts = ClaudeAgentOptions(
        system_prompt="Reply in exactly 5 words.",
        allowed_tools=[],
        max_turns=1,
        permission_mode="bypassPermissions",
    )
    opts.model = "claude-haiku-4-5-20251001"

    print("\nCalling claude_agent_sdk.query()...")
    async for msg in query(prompt="Say hello", options=opts):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(f"SUCCESS: {block.text}")


if __name__ == "__main__":
    asyncio.run(main())
