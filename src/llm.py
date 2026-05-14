# src/llm.py

import os
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")  # "anthropic" | "openai" | "google"
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

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER}")


def parse_response(response) -> tuple[list, object | None]:
    """
    Extract (tool_blocks, text_block) from provider response.
    Normalises differences between provider response shapes.
    """
    if PROVIDER == "anthropic":
        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        text_block  = next((b for b in response.content if b.type == "text"), None)
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