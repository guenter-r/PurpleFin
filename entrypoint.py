"""
entrypoint.py — PurpleFin container entry point.

Flow:
  1. Check data/.env for required credentials
  2. If missing → start setup UI on port 8080 (blocks until config saved, then restarts)
  3. If present → load .env and start the selected interface

  INTERFACE=telegram   (default) — Telegram DMs
  INTERFACE=discord              — Discord DMs
  INTERFACE=cli                  — stdin/stdout (local dev)
"""

import asyncio
import yaml
import os
import sys
from pathlib import Path

from config import DATA_DIR, DEPOT_PATH

ENV_PATH = DATA_DIR / ".env"

if not DEPOT_PATH.exists():
    default = Path("DEPOT.yaml")
    if default.exists():
        DEPOT_PATH.write_text(default.read_text())
    else:
        DEPOT_PATH.write_text(yaml.dump({"holdings": []}, allow_unicode=True))


def _load_env(path: Path):
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ[key.strip()] = val.strip()


def _config_is_complete() -> bool:
    """Return True only if an API key and at least one messenger token are present."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    interface = os.environ.get("INTERFACE", "telegram")
    if interface == "telegram" and not os.environ.get("TELEGRAM_BOT_TOKEN"):
        return False
    if interface == "discord" and not os.environ.get("DISCORD_BOT_TOKEN"):
        return False
    return True


# Load data/.env if it exists (config written by setup_server.py)
if ENV_PATH.exists():
    _load_env(ENV_PATH)

# Also load a root .env if present (local dev convenience)
root_env = Path(__file__).parent / ".env"
if root_env.exists():
    _load_env(root_env)

# ── Setup gate ────────────────────────────────────────────────────────────────
if not _config_is_complete():
    from setup_server import run
    run()  # blocks; on save it os.execv's back to this file
    sys.exit(0)

# ── Start bot ─────────────────────────────────────────────────────────────────
interface = os.environ.get("INTERFACE", "telegram").lower()
print(f"[purplefin] starting — interface: {interface}")

if interface == "telegram":
    from interfaces.telegram_bot import main
elif interface == "discord":
    from interfaces.discord_bot import main
elif interface == "cli":
    from main import main
else:
    print(f"[purplefin] unknown INTERFACE={interface!r}. Choose: telegram, discord, cli")
    sys.exit(1)

asyncio.run(main())