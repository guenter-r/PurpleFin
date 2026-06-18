# CLAUDE.md

Guidance for Claude when working in this repository.

## What this project is

PurpleFin is a personal finance agent that monitors a stock portfolio and
delivers concise, data-driven insights with a dry British wit. It runs as a
Docker container and talks to the user over Telegram or Discord. Python only.

## Hard rules — never violate

- **Never give buy/sell/hold advice.** The agent assesses, flags, and informs;
  investment decisions belong to the user. Any new feature must preserve this.
- **Never commit secrets.** All credentials live in `data/.env`, which is
  gitignored. Do not add real keys, tokens, or portfolio data to tracked files.
- Keep the British-humour persona consistent in any user-facing copy.

## Architecture / where things live

- `entrypoint.py` — container entry point; boots the chosen interface.
- `loop.py` — the ReAct loop (reasoning + tool calls).
- `heartbeat.py` — background portfolio monitoring (price moves, volatility, news).
- `interfaces/telegram_bot.py`, `interfaces/discord_bot.py` — chat interfaces.
- `mcp/finance_server.py` — MCP tool server (prices, news, indicators).
- `skills/manage_position.py` — add/adjust/remove portfolio holdings.
- `src/llm.py` — LLM abstraction (Anthropic / OpenAI / Google).
- `src/mcp_utils.py` — tool execution with caching.
- `db/database.py` — SQLite history + tool cache.
- `config.py` — paths and env config.
- `data/` — persistent volume, gitignored (`.env`, `DEPOT.yaml`, db files).

## Conventions

- **Adding a tool:** implement it in `mcp/finance_server.py` following the
  structure and error handling of the existing tools, then register it so the
  agent can call it. Update the "Available tools" table in `README.md`.
- **Portfolio changes** go through `skills/manage_position.py`, never by
  editing `DEPOT.yaml` directly in code.
- **Models** are configured via env (`CHAT_MODEL`, `HEARTBEAT_MODEL`); don't
  hardcode model strings in logic.
- Match the existing code style; keep functions small and single-purpose.

## Testing constraints

- The agent's live credentials (`ANTHROPIC_API_KEY`, bot tokens) are not
  available in CI, so you cannot run the bot end-to-end here. Prefer adding or
  running unit tests that don't require live API or chat credentials.
- Local dev (no Docker): `INTERFACE=cli python entrypoint.py`.

## Out of scope

- Do not change the Docker release workflow or push images.
- Do not alter the depot file format without an explicit request.
