"""
db/database.py — SQLite setup and helpers for FinAgent.

Two databases:
  1. history.db  — full message log (dev/traceability only, easy to remove)
  2. cache.db    — tool result cache (prod-relevant, 30-min TTL per tool+ticker)
"""

import os, json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


# docker environment variable override for DB_DIR
DB_DIR = Path(os.getenv("DATA_DIR", "data")) / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_DB_PATH = DB_DIR / "history.db"
CACHE_DB_PATH   = DB_DIR / "cache.db"

# connections

def get_history_db() -> sqlite3.Connection:
    conn = sqlite3.connect(HISTORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_cache_db() -> sqlite3.Connection:
    conn = sqlite3.connect(CACHE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# schema init

def init_databases():
    """Create tables if they don't exist. Call once at startup."""

    # History DB — full message log
    with get_history_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                role        TEXT    NOT NULL,
                source      TEXT    NOT NULL DEFAULT 'chat',  -- 'chat' | 'heartbeat'
                content     TEXT    NOT NULL                  -- JSON or plain text
            )
        """)

    # Cache DB — tool result cache
    with get_cache_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_cache (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name   TEXT    NOT NULL,
                ticker      TEXT    NOT NULL,
                result      TEXT    NOT NULL,   -- JSON string
                fetched_at  TEXT    NOT NULL,   -- ISO8601 UTC
                UNIQUE(tool_name, ticker) ON CONFLICT REPLACE
            )
        """)

    print("[db] databases initialised.")



# history helpers

def _serialise_content(content) -> str:
    """Convert Anthropic content (str or list of blocks) to JSON string."""
    if isinstance(content, str):
        return json.dumps(content)
    # List of Pydantic blocks (tool_use, tool_result, text)
    return json.dumps([
        c if isinstance(c, dict) else c.model_dump()
        for c in content
    ])


def log_message(role: str, content, source: str = "chat"):
    """
    Append one message to the history log.
    Call this every time messages[] is appended to in main.py / heartbeat.py.
    To remove from prod: delete all log_message() calls — nothing else changes.
    """
    with get_history_db() as conn:
        conn.execute(
            "INSERT INTO messages (timestamp, role, source, content) VALUES (?, ?, ?, ?)",
            (datetime.utcnow().isoformat(), role, source, _serialise_content(content))
        )


# cache helpers

CACHE_TTL_MINUTES = 30


#  rquired in: mcp/mcp_utils.py
def _extract_ticker(block) -> str:
    """Best-effort ticker extraction from a tool call block."""
    
    # Portfolio summary covers the whole depot — use a fixed cache key
    if block.name == "get_portfolio_summary":
        return "PORTFOLIO"

    inp = dict(block.input)
    ticker = inp.get("symbol") or inp.get("ticker") or ""
    if not ticker:
        symbols = inp.get("symbols", [])
        ticker = symbols[0] if symbols else "unknown"
    return str(ticker).upper()

def get_cached_result(tool_name: str, ticker: str) -> str | None:
    """
    Return cached result if tool+ticker was fetched within the last 30 minutes.
    Returns None on cache miss or expired entry.
    """
    cutoff = (datetime.utcnow() - timedelta(minutes=CACHE_TTL_MINUTES)).isoformat()
    with get_cache_db() as conn:
        row = conn.execute(
            """
            SELECT result FROM tool_cache
            WHERE tool_name = ? AND ticker = ? AND fetched_at > ?
            """,
            (tool_name, ticker, cutoff)
        ).fetchone()
    return row["result"] if row else None


def set_cached_result(tool_name: str, ticker: str, result: str):
    """Store or overwrite a tool result in the cache."""
    with get_cache_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO tool_cache (tool_name, ticker, result, fetched_at)
            VALUES (?, ?, ?, ?)
            """,
            (tool_name, ticker, result, datetime.utcnow().isoformat())
        )


def invalidate_cache(tool_name: str, ticker: str):
    with get_cache_db() as conn:
        conn.execute(
            "DELETE FROM tool_cache WHERE tool_name = ? AND ticker = ?",  # ← tool_cache not cache
            (tool_name, ticker)
        )