"""
discord_bot.py — PlumFin Discord interface.

Replaces stdin chat_loop with Discord DMs.
Runs alongside heartbeat_loop concurrently, mirroring main.py exactly.

Setup:
    pip install discord.py
    Add to .env:
        DISCORD_BOT_TOKEN=...
        DISCORD_USER_ID=...
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import discord
import yaml
from dotenv import load_dotenv
from fastmcp import Client

# from loop import run_react
# from heartbeat import run_heartbeat
# from db.database import init_databases, log_message, get_history_db
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# then absolute imports work fine
from config import SOUL_PATH, DEPOT_PATH, DATA_DIR
from loop import run_react
from heartbeat import run_heartbeat
from db.database import init_databases, log_message, get_history_db

load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALLOWED_USER = int(os.getenv("DISCORD_USER_ID", "0"))
HEARTBEAT_INTERVAL = 60 * 60 * 2  # seconds * minutes * hours

# SOUL_PATH = Path("SOUL.md")
# DEPOT_PATH = Path("DEPOT.yaml")

# ── Shared state ──────────────────────────────────────────────────────────────
_dm_channel = None
_messages = []
_tools = []
_system = ""
_depot = {}
_mcp = None  # set in main() before bot starts

# ── Discord setup ─────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_recent_messages(hours: int = 4) -> list[dict]:
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with get_history_db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE timestamp > ? ORDER BY id", (cutoff,)
        ).fetchall()
    return [{"role": r["role"], "content": json.loads(r["content"])} for r in rows]


def build_system(soul: str, depot: dict) -> str:
    return (
        soul
        + "\n\n## Your Current Depot\n"
        + "```yaml\n"
        + yaml.dump(depot, allow_unicode=True)
        + "\n```"
    )


async def get_tools(mcp: Client) -> list:
    tools = await mcp.list_tools()
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.inputSchema,
        }
        for t in tools
    ]


# ── Outbound helper ───────────────────────────────────────────────────────────
async def send_dm(text: str):
    """Push message to your DM — splits at 1900 chars for Discord's 2000 char limit."""
    if _dm_channel:
        for chunk in [text[i : i + 1900] for i in range(0, len(text), 1900)]:
            await _dm_channel.send(chunk)


# ── Discord events ────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    global _dm_channel
    print(f"[discord] Logged in as {bot.user}")
    try:
        user = await bot.fetch_user(ALLOWED_USER)
        _dm_channel = await user.create_dm()
        print(f"[discord] DM channel ready for {user}")
    except Exception as e:
        print(f"[discord] Could not open DM channel: {e}")


@bot.event
async def on_message(message: discord.Message):
    global _dm_channel

    if message.author.bot:
        return
    if message.author.id != ALLOWED_USER:
        return
    if not isinstance(message.channel, discord.DMChannel):
        return

    _dm_channel = message.channel
    user_input = message.content.strip()
    if not user_input:
        return

    _messages.append({"role": "user", "content": user_input})
    log_message("user", user_input, source="chat")

    async with message.channel.typing():
        reply = await run_react(_mcp, _system, _tools, _messages, _depot)

    await send_dm(reply)


# ── Heartbeat loop ────────────────────────────────────────────────────────────
async def heartbeat_loop():
    await asyncio.sleep(10)  # let bot connect first
    while True:
        print("\n[heartbeat] running portfolio check...")
        summary = await run_heartbeat(_mcp, _system, _tools, _messages, _depot)
        if summary:
            _messages.append({"role": "assistant", "content": f"[Heartbeat] {summary}"})
            log_message("assistant", f"[Heartbeat] {summary}", source="heartbeat")
            print(f"\n[heartbeat] {summary}\n")
            await send_dm(f"💜 **Heartbeat Update**\n{summary}")
        await asyncio.sleep(HEARTBEAT_INTERVAL)


# ── Entry point ───────────────────────────────────────────────────────────────
async def main():
    global _messages, _tools, _system, _depot, _mcp

    init_databases()

    soul = SOUL_PATH.read_text()
    if not DEPOT_PATH.exists():
        DEPOT_PATH.write_text(yaml.dump({"holdings": []}, allow_unicode=True))
    _depot = yaml.safe_load(DEPOT_PATH.read_text()) or {}
    # _depot = yaml.safe_load(DEPOT_PATH.read_text())
    _system = build_system(soul, _depot)

    _messages = load_recent_messages(hours=4)
    if _messages:
        print(f"[discord] loaded {len(_messages)} messages from history")

    async with Client("mcp/finance_server.py") as mcp:
        _mcp = mcp
        _tools = await get_tools(mcp)
        print(f"[mcp] connected — {len(_tools)} tools: {[t['name'] for t in _tools]}")

        await asyncio.gather(
            bot.start(BOT_TOKEN),
            heartbeat_loop(),
        )


if __name__ == "__main__":
    asyncio.run(main())
