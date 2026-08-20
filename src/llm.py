# src/llm.py

import os
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")  # "anthropic" | "openai" | "google" | "ollama"
CHAT_MODEL     = os.getenv("CHAT_MODEL",      "claude-haiku-4-5-20251001")
HEARTBEAT_MODEL = os.getenv("HEARTBEAT_MODEL", "claude-haiku-4-5-20251001")


async def call_llm(model: str, system: str, tools: list, messages: list, max_tokens: int) -> object:
    """
    Unified LLM call. Returns the raw response object.
    Swap provider via LLM_PROVIDER env var — no code changes needed.
    """
    if PROVIDER == "anthropic":
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic()
        return await client.messages.create(
            model      = model,
            system     = system,
            tools      = tools,
            messages   = messages,
            max_tokens = max_tokens,
        )

    elif PROVIDER == "openai":
        from openai import AsyncOpenAI
        client = AsyncOpenAI()
        # OpenAI uses a different message format — convert here
        raise NotImplementedError("OpenAI provider not yet wired up")

    elif PROVIDER == "google":
        
        raise NotImplementedError("Google provider not yet wired up")

    elif PROVIDER == "ollama":
        import ollama

        # Convert tools
        ollama_tools = []
        for tool in tools:
            if isinstance(tool, dict):
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {"type": "object", "properties": {}})
                    }
                })

        # Convert messages
        ollama_messages = []
        if system:
            ollama_messages.append({"role": "system", "content": system})

        for m in messages:
            if m["role"] == "user":
                if isinstance(m["content"], str):
                    ollama_messages.append({"role": "user", "content": m["content"]})
                elif isinstance(m["content"], list):
                    # anthropic tool_result blocks are inside a user message list
                    for block in m["content"]:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            ollama_messages.append({
                                "role": "tool",
                                "name": block.get("tool_use_id"),
                                "content": str(block.get("content", ""))
                            })
            elif m["role"] == "assistant":
                if isinstance(m["content"], str):
                    ollama_messages.append({"role": "assistant", "content": m["content"]})
                elif isinstance(m["content"], list):
                    text_content = ""
                    tool_calls = []
                    for block in m["content"]:
                        if getattr(block, 'type', None) == 'text':
                            text_content += block.text
                        elif isinstance(block, dict) and block.get('type') == 'text':
                            text_content += block['text']
                        elif getattr(block, 'type', None) == 'tool_use':
                            tool_calls.append({
                                "function": {
                                    "name": block.name,
                                    "arguments": block.input
                                }
                            })
                        elif isinstance(block, dict) and block.get('type') == 'tool_use':
                            tool_calls.append({
                                "function": {
                                    "name": block['name'],
                                    "arguments": block['input']
                                }
                            })
                    msg = {"role": "assistant", "content": text_content}
                    if tool_calls:
                        msg["tool_calls"] = tool_calls
                    ollama_messages.append(msg)

        # ollama library chat is synchronous but can be wrapped or used directly
        # (Assuming async calls by wrapping or just call it directly for now, wait it provides AsyncClient)
        from ollama import AsyncClient
        client = AsyncClient()
        return await client.chat(
            model=model,
            messages=ollama_messages,
            tools=ollama_tools if ollama_tools else None
        )

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER}")


class TextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text

class ToolUseBlock:
    def __init__(self, id, name, input_dict):
        self.type = "tool_use"
        self.id = id
        self.name = name
        self.input = input_dict

def parse_response(response) -> tuple[list, object | None]:
    """
    Extract (tool_blocks, text_block) from provider response.
    Normalises differences between provider response shapes.
    """
    if PROVIDER == "anthropic":
        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        text_block  = next((b for b in response.content if b.type == "text"), None)
        return tool_blocks, text_block

    elif PROVIDER == "ollama":
        tool_blocks = []
        text_block = None
        import uuid

        if getattr(response, "message", None) is not None:
            message = response.message
            if getattr(message, "content", None):
                text_block = TextBlock(message.content)

            if getattr(message, "tool_calls", None):
                for call in message.tool_calls:
                    function = call.function
                    tool_blocks.append(
                        ToolUseBlock(
                            id=f"toolu_{uuid.uuid4().hex[:8]}",
                            name=function.name,
                            input_dict=function.arguments
                        )
                    )
        elif isinstance(response, dict) and "message" in response:
            message = response["message"]
            if message.get("content"):
                text_block = TextBlock(message["content"])

            if message.get("tool_calls"):
                for call in message["tool_calls"]:
                    function = call["function"]
                    tool_blocks.append(
                        ToolUseBlock(
                            id=f"toolu_{uuid.uuid4().hex[:8]}",
                            name=function["name"],
                            input_dict=function["arguments"]
                        )
                    )
        return tool_blocks, text_block

    raise NotImplementedError(f"parse_response not implemented for {PROVIDER}")



# src/llm.py — add this helper function at the bottom

def get_safe_context(messages: list, max_messages: int = 10) -> list:
    """
    Safely slice message history for Anthropic API.
    Guarantees:
    1. First message has role == "user".
    2. No tool_result blocks exist without their matching tool_use blocks.
    """
    sliced = messages[-max_messages:] if len(messages) > max_messages else messages.copy()

    while sliced:
        # Rule 1: Must start with a 'user' message
        if sliced[0]["role"] != "user":
            sliced.pop(0)
            continue

        # Rule 2: Cannot start with a tool_result (means we orphaned it)
        first_content = sliced[0].get("content", [])
        has_orphaned_result = False
        
        if isinstance(first_content, list):
            for block in first_content:
                b_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                if b_type == "tool_result":
                    has_orphaned_result = True
                    break

        if has_orphaned_result:
            # Pop this invalid user message and loop again to find a clean start
            sliced.pop(0)
            continue

        # If it passes both rules, the slice is perfectly safe
        break

    return sliced