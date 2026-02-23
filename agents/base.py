"""
BaseAgent: handles Claude streaming + tool_use loop.
All agent classes inherit from this.
"""
import asyncio
import json
from typing import AsyncGenerator
import anthropic
from config import get_settings

MODEL = "claude-opus-4-6"


class BaseAgent:
    name: str = "base"
    system_prompt: str = "You are a helpful assistant."
    tools: list[dict] = []

    def _get_client(self) -> anthropic.AsyncAnthropic:
        return anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)

    async def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Override in subclasses to handle tool execution."""
        return json.dumps({"error": f"Tool '{tool_name}' not implemented"})

    async def stream_response(
        self, messages: list[dict], context: dict | None = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream a response from Claude, handling tool_use turns internally.
        Yields text chunks as they arrive.
        """
        client = self._get_client()
        context = context or {}

        current_messages = list(messages)

        while True:
            tool_use_block = None
            text_chunks = []

            async with client.messages.stream(
                model=MODEL,
                system=self.system_prompt,
                messages=current_messages,
                tools=self.tools if self.tools else anthropic.NOT_GIVEN,
                max_tokens=4096,
            ) as stream:
                async for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                yield event.delta.text
                                text_chunks.append(event.delta.text)
                        elif event.type == "content_block_start":
                            if hasattr(event.content_block, "type") and event.content_block.type == "tool_use":
                                tool_use_block = event.content_block

                final_message = await stream.get_final_message()

            # If no tool use, we're done
            if final_message.stop_reason != "tool_use":
                break

            # Collect ALL tool_use blocks (Claude may call multiple tools at once)
            tool_use_blocks = [
                block for block in final_message.content if block.type == "tool_use"
            ]

            if not tool_use_blocks:
                break

            # Execute all tools in parallel
            tool_results = await asyncio.gather(*[
                self.execute_tool(block.name, block.input)
                for block in tool_use_blocks
            ])

            # Add assistant turn + all tool results and loop
            current_messages = current_messages + [
                {"role": "assistant", "content": final_message.content},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                        for block, result in zip(tool_use_blocks, tool_results)
                    ],
                },
            ]
