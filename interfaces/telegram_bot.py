"""
telegram_bot.py — PlumFin Telegram interface.

Replaces stdin chat_loop with Telegram DMs.
Runs alongside heartbeat_loop concurrently, mirroring discord_bot.py exactly.

Setup (2 minutes):
    1. Open Telegram → message @BotFather → /newbot → copy the token
    2. Message your new bot once, then run:
         curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
       Copy your numeric user ID from the response.
    3. Add to .env:
         TELEGRAM_BOT_TOKEN=...
         TELEGRAM_USER_ID=...

pip install python-telegram-bot>=20.0
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastmcp import Client
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, ContextTypes, MessageHandler, filters

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# then absolute imports work fine
from config import SOUL_PATH, DEPOT_PATH, DATA_DIR
from loop import run_react
from heartbeat import run_heartbeat
from db.database import init_databases, log_message, get_history_db

load_dotenv()

BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER = int(os.getenv("TELEGRAM_USER_ID", "0"))

HEARTBEAT_INTERVAL = 60 * 60 * 2  # 2 hours

# ── Shared state ──────────────────────────────────────────────────────────────
_messages: list[dict] = []
_tools:    list[dict] = []
_system:   str        = ""
_depot:    dict       = {}
_mcp:      Client     = None  # set in main() before bot starts
_app:      Application = None  # set in main()


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_recent_messages(hours: int = 4) -> list[dict]:
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with get_history_db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE timestamp > ? ORDER BY id", (cutoff,)
        ).fetchall()
    return [{"role": r["role"], "content": json.loads(r["content"])} for r in rows]


def build_system(soul: str, depot: dict) -> str:
    base = (
        soul
        + "\n\n## Your Current Depot\n"
        + "```yaml\n"
        + yaml.dump(depot, allow_unicode=True)
        + "\n```"
    )
    if not depot.get("holdings"):
        base += (
            "\n\n## Startup Task\n"
            "The depot is empty. On your very first response, greet the user warmly "
            "and ask them to share their holdings — company name or ticker, quantity, "
            "and optionally the price they paid. Do not show any market analysis until "
            "at least one position has been added."
        )
    return base


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
async def send_message(text: str, chat_id: int | None = None):
    """Push message to the user — splits at 4000 chars for Telegram's 4096 char limit."""
    if _app is None:
        return
    target = chat_id or ALLOWED_USER
    for chunk in [text[i : i + 4000] for i in range(0, len(text), 4000)]:
        await _app.bot.send_message(
            chat_id=target,
            text=chunk,
            parse_mode="Markdown",
        )


# ── Telegram handler ──────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return
    if not update.message or not update.message.text:
        return

    user_input = update.message.text.strip()
    if not user_input:
        return

    _messages.append({"role": "user", "content": user_input})
    log_message("user", user_input, source="chat")

    # Show typing indicator while the agent thinks
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    reply = await run_react(_mcp, _system, _tools, _messages, _depot)
    await send_message(reply, chat_id=update.effective_chat.id)


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
            await send_message(f"💜 *Heartbeat Update*\n{summary}")
        await asyncio.sleep(HEARTBEAT_INTERVAL)


# ── Entry point ───────────────────────────────────────────────────────────────
async def main():
    global _messages, _tools, _system, _depot, _mcp, _app

    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")
    if not ALLOWED_USER:
        raise RuntimeError("TELEGRAM_USER_ID is not set in .env")

    init_databases()

    soul   = SOUL_PATH.read_text()
    _depot = yaml.safe_load(DEPOT_PATH.read_text()) if DEPOT_PATH.exists() else {"holdings": []}
    _system = build_system(soul, _depot)

    _messages = load_recent_messages(hours=4)
    if _messages:
        print(f"[telegram] loaded {len(_messages)} messages from history")

    _app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )
    _app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async with Client("mcp/finance_server.py") as mcp:
        _mcp   = mcp
        _tools = await get_tools(mcp)
        print(f"[mcp] connected — {len(_tools)} tools: {[t['name'] for t in _tools]}")

        async with _app:
            await _app.start()
            await _app.updater.start_polling(drop_pending_updates=True)
            print(f"[telegram] bot running — waiting for messages from user {ALLOWED_USER}")

            await heartbeat_loop()  # runs forever; ctrl+c to stop

            await _app.updater.stop()
            await _app.stop()


if __name__ == "__main__":
    asyncio.run(main())