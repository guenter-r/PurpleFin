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

    elif PROVIDER == "ollama":
        from ollama import AsyncClient
        client = AsyncClient()

        # Convert Anthropic-style tools to Ollama format
        ollama_tools = []
        for t in tools:
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t.get("input_schema", {})
                }
            })

        # Convert Anthropic-style messages to Ollama format
        ollama_messages = []
        if system:
            ollama_messages.append({"role": "system", "content": system})

        for msg in messages:
            if isinstance(msg["content"], str):
                ollama_messages.append({"role": msg["role"], "content": msg["content"]})
            elif isinstance(msg["content"], list):
                if msg["role"] == "assistant":
                    content_str = ""
                    tool_calls = []
                    for block in msg["content"]:
                        # Handle Dict objects or Anthropic ToolUseBlock/TextBlock objects
                        b_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                        if b_type == "text":
                            b_text = block.get("text") if isinstance(block, dict) else getattr(block, "text", "")
                            content_str += b_text
                        elif b_type == "tool_use":
                            b_id = block.get("id") if isinstance(block, dict) else getattr(block, "id", "")
                            b_name = block.get("name") if isinstance(block, dict) else getattr(block, "name", "")
                            b_input = block.get("input") if isinstance(block, dict) else getattr(block, "input", {})
                            tool_calls.append({
                                "function": {
                                    "name": b_name,
                                    "arguments": b_input
                                }
                            })
                    msg_dict = {"role": "assistant", "content": content_str}
                    if tool_calls:
                        msg_dict["tool_calls"] = tool_calls
                    ollama_messages.append(msg_dict)
                elif msg["role"] == "user":
                    for block in msg["content"]:
                        b_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                        if b_type == "tool_result":
                            b_content = block.get("content") if isinstance(block, dict) else getattr(block, "content", "")
                            ollama_messages.append({
                                "role": "tool",
                                "content": str(b_content)
                            })

        # Determine any extra options (like max_tokens mapped to num_predict for ollama)
        options = {"num_predict": max_tokens} if max_tokens else None

        response = await client.chat(
            model=model,
            messages=ollama_messages,
            tools=ollama_tools,
            options=options
        )

        # loop.py expects `response.content` to exist and be a list of blocks,
        # just like Anthropic API. Let's mock it so loop.py works.
        class MockTextBlock:
            def __init__(self, text):
                self.type = "text"
                self.text = text

        class MockToolUseBlock:
            def __init__(self, id, name, input_dict):
                self.type = "tool_use"
                self.id = id
                self.name = name
                self.input = input_dict

        content = []
        if response.message.content:
            content.append(MockTextBlock(text=response.message.content))
        if response.message.tool_calls:
            import uuid
            for i, call in enumerate(response.message.tool_calls):
                content.append(
                    MockToolUseBlock(
                        id=f"call_{uuid.uuid4().hex[:8]}_{i}",
                        name=call.function.name,
                        input_dict=call.function.arguments
                    )
                )
        response.content = content

        return response

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

    elif PROVIDER == "ollama":
        class MockTextBlock:
            def __init__(self, text):
                self.type = "text"
                self.text = text

        class MockToolUseBlock:
            def __init__(self, id, name, input_dict):
                self.type = "tool_use"
                self.id = id
                self.name = name
                self.input = input_dict

        tool_blocks = []
        if response.message.tool_calls:
            import uuid
            for i, call in enumerate(response.message.tool_calls):
                tool_blocks.append(
                    MockToolUseBlock(
                        id=f"call_{uuid.uuid4().hex[:8]}_{i}",
                        name=call.function.name,
                        input_dict=call.function.arguments
                    )
                )

        text_block = MockTextBlock(text=response.message.content) if response.message.content else None
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