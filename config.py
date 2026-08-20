"""
config.py — Centralized path configuration for PurpleFin.

All file paths go through here so Docker volume mounts work correctly.
Override DATA_DIR via environment variable to change where mutable data lives.

Baked into image (read-only):
    SOUL_PATH  → /app/SOUL.md

Persisted via Docker volume (read-write):
    DEPOT_PATH → /app/data/DEPOT.yaml
    DB_DIR     → /app/data/db/
"""

# config.py
from pathlib import Path
import os

# Workaround for FastMCP: It auto-instantiates AsyncAnthropic if the library is installed,
# which crashes without an API key. If we are using a local provider like Ollama, provide a dummy key.
if os.environ.get("LLM_PROVIDER", "").lower() == "ollama" and not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "dummy_key_for_fastmcp_auto_init"

DATA_DIR  = Path(os.environ.get("DATA_DIR", "./data"))
SOUL_PATH = Path("SOUL.md")
DEPOT_PATH = DATA_DIR / "DEPOT.yaml" 

# Project root — where the source code lives inside the container
ROOT = Path(__file__).parent

# Mutable data dir — override with DATA_DIR env var for Docker
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Read-write (must survive container restarts)
DEPOT_PATH = DATA_DIR / "DEPOT.yaml"

# Database directory (passed to db/database.py via DB_DIR env var)
DB_DIR = DATA_DIR / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)