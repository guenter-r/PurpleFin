# 💜 PurpleFin

A personal finance agent that monitors your stock portfolio and delivers concise, data-driven insights — with a distinctly British sense of humour. Runs as a Docker container and talks to you via Telegram or Discord.
Built with tinkering and Claude.

---

## What it does

- **Monitors your portfolio** continuously via a heartbeat that checks for price movements, volatility, and news
- **Chats with you** over Telegram or Discord — ask about your holdings, add/remove positions, request analysis
- **Never gives buy/sell advice** — it assesses, flags, and informs. The decisions are yours
- **Persists everything** — depot, message history, and tool cache survive container restarts

---

## What's coming soon

- **Heartbeat during trading hours only** — monitoring will respect market hours to avoid noise outside sessions
- **Portfolio optimization** — rules-based suggestions for rebalancing and risk exposure
- **Ticker lookup for non-US markets** — proper support for European and international symbols like VOW3.DE
- **Ollama / local model support** — run fully offline with Gemma or other local models, no API key required


## Quick start

### 1. Clone the repo

```bash
git clone https://github.com/guenter-r/purplefin.git
cd purplefin
mkdir -p data
```

### 2. Configure credentials

Create `data/.env` with your credentials:

```env
ANTHROPIC_API_KEY=sk-ant-...
INTERFACE=telegram           # or discord

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_USER_ID=...

# Discord (if using discord interface)
# DISCORD_BOT_TOKEN=...
# DISCORD_USER_ID=...
```

### 3. Seed your depot (optional)

```bash
cp DEPOT.example.yaml data/DEPOT.yaml
```

Edit `data/DEPOT.yaml` with your actual holdings — or leave it empty and tell the agent what you hold on first run.

### 4. Build and run

```bash
docker compose build
docker compose up -d
```

That's it. The agent starts, connects to Telegram/Discord, and begins monitoring.

---

## Telegram setup (2 minutes)

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token
2. Message your new bot once, then run:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```
3. Copy your numeric user ID from the response
4. Add both to `data/.env`

---

## Project structure

```
purplefin/
├── interfaces/
│   ├── telegram_bot.py     # Telegram DM interface
│   └── discord_bot.py      # Discord DM interface
├── mcp/
│   └── finance_server.py   # MCP tool server (prices, news, indicators)
├── skills/
│   └── manage_position.py  # Add/remove portfolio positions
├── src/
│   ├── llm.py              # LLM abstraction (Anthropic / OpenAI / Google)
│   └── mcp_utils.py        # Tool execution with caching
├── db/
│   └── database.py         # SQLite history + cache
├── data/                   # Persistent volume (gitignored)
│   ├── .env
│   ├── DEPOT.yaml
│   ├── SOULD.md
│   └── db/
│       ├── history.db
│       └── cache.db
├── entrypoint.py           # Container entry point
├── heartbeat.py            # Portfolio monitoring loop
├── loop.py                 # ReAct loop
├── config.py               # Path and env config
├── Dockerfile
└── docker-compose.yml
```

---

## Configuration

All config lives in `data/.env`. The following variables are supported:

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required |
| `INTERFACE` | `telegram` | `telegram`, `discord`, or `cli` |
| `TELEGRAM_BOT_TOKEN` | — | Required for Telegram |
| `TELEGRAM_USER_ID` | — | Your Telegram numeric user ID |
| `DISCORD_BOT_TOKEN` | — | Required for Discord |
| `DISCORD_USER_ID` | — | Your Discord numeric user ID |
| `CHAT_MODEL` | `claude-haiku-4-5-20251001` | Model for chat responses |
| `HEARTBEAT_MODEL` | `claude-haiku-4-5-20251001` | Model for heartbeat checks |
| `DATA_DIR` | `data` | Path to persistent data directory |

---

## Depot format

```yaml
# data/DEPOT.yaml
currency: EUR
holdings:
  - symbol: AAPL
    name: Apple Inc.
    shares: 10
    avg_buy_price: 165.00
  - symbol: VOW3.DE
    name: Volkswagen AG
    shares: 50
    avg_buy_price: 89.00
```

Positions are updated automatically when you tell the agent to add or remove shares.

---

## Available tools

| Tool | Description |
|---|---|
| `get_prices` | Current price for any ticker |
| `get_portfolio_summary` | Full depot overview with P&L |
| `get_indicators` | RSI, MACD, moving averages |
| `get_technical_indicators` | Extended technical analysis |
| `get_news` | Recent news for a ticker |
| `get_daily_summary` | Daily market summary |
| `manage_position` | Add, adjust, or remove a holding |

---

## Local development (without Docker)

```bash
python -m venv purple_env
source purple_env/bin/activate  # or purple_env\Scripts\activate on Windows
pip install -r requirements.txt

# Run CLI mode
INTERFACE=cli python entrypoint.py
```

---

## License

MIT
