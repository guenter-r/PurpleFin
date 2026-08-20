import asyncio
import os
from src.llm import call_llm

async def main():
    try:
        messages = [{"role": "user", "content": "Hello, this is a test. Are you working?"}]
        response = await call_llm(model="claude-3-haiku-20240307", system="You are a helpful assistant.", tools=[], messages=messages, max_tokens=100)
        print("Anthropic call successful.")
        print(response)
    except Exception as e:
        print(f"Error testing Anthropic: {e}")

if __name__ == "__main__":
    asyncio.run(main())
