"""
setup_server.py — PurpleFin first-run setup UI.

Serves a configuration form on port 8080.
Writes credentials to data/.env, then restarts as the main bot.

pip install fastapi uvicorn
"""

import os
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from config import DATA_DIR

ENV_PATH = DATA_DIR / ".env"

REQUIRED_KEYS = ["ANTHROPIC_API_KEY"]

app = FastAPI(docs_url=None, redoc_url=None)

# ── HTML ──────────────────────────────────────────────────────────────────────

SETUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>PurpleFin · Setup</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet" />
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:        #0c0b12;
    --surface:   #13111e;
    --border:    #2a2640;
    --border-hi: #4a4070;
    --plum:      #7c3aed;
    --plum-glow: rgba(124, 58, 237, 0.25);
    --gold:      #c9a84c;
    --gold-dim:  rgba(201, 168, 76, 0.15);
    --text:      #e8e3f5;
    --muted:     #7c748e;
    --success:   #34d399;
    --error:     #f87171;
  }

  html { height: 100%; }

  body {
    min-height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    background-image:
      radial-gradient(ellipse 60% 50% at 20% 0%, rgba(124,58,237,0.08) 0%, transparent 70%),
      radial-gradient(ellipse 40% 30% at 80% 100%, rgba(201,168,76,0.05) 0%, transparent 60%);
  }

  .card {
    width: 100%;
    max-width: 520px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 48px;
    position: relative;
    animation: fadeUp 0.5s ease both;
  }

  .card::before {
    content: '';
    position: absolute;
    top: 0; left: 48px; right: 48px;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--gold), transparent);
    opacity: 0.6;
  }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .wordmark {
    font-family: 'Cormorant Garamond', serif;
    font-size: 28px;
    font-weight: 400;
    letter-spacing: 0.02em;
    color: var(--text);
    margin-bottom: 4px;
    display: flex;
    align-items: baseline;
    gap: 2px;
  }

  .wordmark span {
    color: var(--gold);
    font-style: italic;
  }

  .subtitle {
    color: var(--muted);
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 40px;
  }

  .section-label {
    font-size: 10px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--gold);
    margin-bottom: 16px;
    margin-top: 32px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--gold-dim);
  }

  .field {
    margin-bottom: 20px;
  }

  label {
    display: block;
    font-size: 11px;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin-bottom: 6px;
    text-transform: uppercase;
  }

  input[type="text"],
  input[type="password"] {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 10px 14px;
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }

  input[type="text"]:focus,
  input[type="password"]:focus {
    border-color: var(--plum);
    box-shadow: 0 0 0 3px var(--plum-glow);
  }

  .hint {
    font-size: 11px;
    color: var(--muted);
    margin-top: 6px;
    line-height: 1.6;
  }

  .hint a {
    color: var(--plum);
    text-decoration: none;
  }

  .hint a:hover { text-decoration: underline; }

  /* Interface toggle */
  .toggle-group {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 24px;
  }

  .toggle-option {
    position: relative;
  }

  .toggle-option input[type="radio"] {
    position: absolute;
    opacity: 0;
    width: 0;
  }

  .toggle-option label {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 14px;
    border: 1px solid var(--border);
    border-radius: 2px;
    cursor: pointer;
    transition: all 0.2s;
    text-transform: none;
    letter-spacing: 0;
    font-size: 13px;
    color: var(--muted);
  }

  .toggle-option label .icon { font-size: 20px; }
  .toggle-option label .name { color: var(--text); font-weight: 500; }
  .toggle-option label .desc { font-size: 10px; }

  .toggle-option input:checked + label {
    border-color: var(--plum);
    background: var(--plum-glow);
    color: var(--text);
  }

  /* Conditional sections */
  .iface-section { display: none; }
  .iface-section.active { display: block; }

  .steps {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 16px;
    margin-bottom: 20px;
    counter-reset: step;
  }

  .steps li {
    list-style: none;
    counter-increment: step;
    padding: 6px 0 6px 28px;
    position: relative;
    font-size: 12px;
    line-height: 1.6;
    color: var(--muted);
  }

  .steps li::before {
    content: counter(step);
    position: absolute;
    left: 0;
    width: 18px;
    height: 18px;
    background: var(--gold-dim);
    border: 1px solid var(--gold);
    border-radius: 50%;
    font-size: 10px;
    color: var(--gold);
    display: flex;
    align-items: center;
    justify-content: center;
    top: 7px;
  }

  .steps li code {
    background: rgba(124,58,237,0.15);
    border: 1px solid var(--border);
    padding: 1px 6px;
    border-radius: 2px;
    color: var(--plum);
    font-size: 11px;
  }

  button[type="submit"] {
    width: 100%;
    margin-top: 32px;
    padding: 14px;
    background: var(--plum);
    color: #fff;
    border: none;
    border-radius: 2px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
    position: relative;
    overflow: hidden;
  }

  button[type="submit"]:hover { background: #6d28d9; }
  button[type="submit"]:active { transform: scale(0.99); }

  button[type="submit"].loading {
    color: transparent;
    pointer-events: none;
  }

  button[type="submit"].loading::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent 20%, rgba(255,255,255,0.2) 50%, transparent 80%);
    background-size: 200% 100%;
    animation: shimmer 1s infinite;
  }

  @keyframes shimmer {
    from { background-position: 200% 0; }
    to   { background-position: -200% 0; }
  }

  .message {
    margin-top: 16px;
    padding: 12px 16px;
    border-radius: 2px;
    font-size: 12px;
    line-height: 1.6;
    display: none;
  }

  .message.success {
    display: block;
    background: rgba(52, 211, 153, 0.1);
    border: 1px solid rgba(52, 211, 153, 0.3);
    color: var(--success);
  }

  .message.error {
    display: block;
    background: rgba(248, 113, 113, 0.1);
    border: 1px solid rgba(248, 113, 113, 0.3);
    color: var(--error);
  }
</style>
</head>
<body>
<div class="card">
  <div class="wordmark">Purple<span>Fin</span></div>
  <div class="subtitle">First-run configuration</div>

  <form id="setup-form">

    <!-- API Key -->
    <div class="section-label">Anthropic</div>
    <div class="field">
      <label for="api-key">API Key</label>
      <input type="password" id="api-key" name="anthropic_api_key"
             placeholder="sk-ant-..." autocomplete="off" required />
      <div class="hint">
        Get yours at <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a>
      </div>
    </div>

    <!-- Interface -->
    <div class="section-label">Messenger</div>
    <div class="toggle-group">
      <div class="toggle-option">
        <input type="radio" id="iface-telegram" name="interface" value="telegram" checked />
        <label for="iface-telegram">
          <span class="icon">✈️</span>
          <span class="name">Telegram</span>
          <span class="desc">Recommended</span>
        </label>
      </div>
      <div class="toggle-option">
        <input type="radio" id="iface-discord" name="interface" value="discord" />
        <label for="iface-discord">
          <span class="icon">🎮</span>
          <span class="name">Discord</span>
          <span class="desc">Alternative</span>
        </label>
      </div>
    </div>

    <!-- Telegram fields -->
    <div class="iface-section active" id="section-telegram">
      <div class="section-label">Telegram setup</div>
      <ol class="steps">
        <li>Open Telegram and message <code>@BotFather</code></li>
        <li>Send <code>/newbot</code> and follow the prompts to name your bot</li>
        <li>Copy the token BotFather gives you into the field below</li>
        <li>Start a conversation with your new bot, then paste this into your browser:<br/>
          <code>api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code><br/>
          Copy the numeric <code>from.id</code> value — that's your user ID</li>
      </ol>
      <div class="field">
        <label for="tg-token">Bot Token</label>
        <input type="password" id="tg-token" name="telegram_bot_token"
               placeholder="123456:ABC-DEF..." autocomplete="off" />
      </div>
      <div class="field">
        <label for="tg-user">Your Telegram User ID</label>
        <input type="text" id="tg-user" name="telegram_user_id"
               placeholder="123456789" autocomplete="off" />
      </div>
    </div>

    <!-- Discord fields -->
    <div class="iface-section" id="section-discord">
      <div class="section-label">Discord setup</div>
      <ol class="steps">
        <li>Go to <code>discord.com/developers/applications</code> → New Application</li>
        <li>Bot tab → Add Bot → copy the token below</li>
        <li>Enable Developer Mode in Discord settings → right-click your username → Copy ID</li>
      </ol>
      <div class="field">
        <label for="dc-token">Bot Token</label>
        <input type="password" id="dc-token" name="discord_bot_token"
               placeholder="MTk4..." autocomplete="off" />
      </div>
      <div class="field">
        <label for="dc-user">Your Discord User ID</label>
        <input type="text" id="dc-user" name="discord_user_id"
               placeholder="123456789012345678" autocomplete="off" />
      </div>
    </div>

    <button type="submit" id="submit-btn">Launch PurpleFin</button>
  </form>

  <div class="message" id="message"></div>
</div>

<script>
  // Toggle messenger sections
  document.querySelectorAll('input[name="interface"]').forEach(radio => {
    radio.addEventListener('change', () => {
      document.querySelectorAll('.iface-section').forEach(s => s.classList.remove('active'));
      document.getElementById('section-' + radio.value).classList.add('active');
    });
  });

  // Submit
  document.getElementById('setup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('submit-btn');
    const msg = document.getElementById('message');
    btn.classList.add('loading');
    msg.className = 'message';

    const data = new FormData(e.target);
    try {
      const res = await fetch('/setup', { method: 'POST', body: data });
      const json = await res.json();
      if (res.ok) {
        msg.className = 'message success';
        msg.textContent = '✓ Config saved. PurpleFin is starting — check your messenger in a few seconds.';
        btn.textContent = 'Done';
        btn.disabled = true;
      } else {
        msg.className = 'message error';
        msg.textContent = json.detail || 'Something went wrong.';
        btn.classList.remove('loading');
      }
    } catch {
      msg.className = 'message error';
      msg.textContent = 'Could not reach the setup server.';
      btn.classList.remove('loading');
    }
  });
</script>
</body>
</html>"""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def get_setup():
    return SETUP_HTML


@app.post("/setup")
async def post_setup(
    anthropic_api_key:  str = Form(...),
    interface:          str = Form("telegram"),
    telegram_bot_token: str = Form(""),
    telegram_user_id:   str = Form(""),
    discord_bot_token:  str = Form(""),
    discord_user_id:    str = Form(""),
):
    from fastapi import HTTPException

    if not anthropic_api_key.strip():
        raise HTTPException(status_code=400, detail="Anthropic API key is required.")

    if interface == "telegram":
        if not telegram_bot_token.strip():
            raise HTTPException(status_code=400, detail="Telegram bot token is required.")
        if not telegram_user_id.strip():
            raise HTTPException(status_code=400, detail="Telegram user ID is required.")
    elif interface == "discord":
        if not discord_bot_token.strip():
            raise HTTPException(status_code=400, detail="Discord bot token is required.")
        if not discord_user_id.strip():
            raise HTTPException(status_code=400, detail="Discord user ID is required.")

    lines = [
        f"ANTHROPIC_API_KEY={anthropic_api_key.strip()}",
        f"INTERFACE={interface.strip()}",
        f"TELEGRAM_BOT_TOKEN={telegram_bot_token.strip()}",
        f"TELEGRAM_USER_ID={telegram_user_id.strip()}",
        f"DISCORD_BOT_TOKEN={discord_bot_token.strip()}",
        f"DISCORD_USER_ID={discord_user_id.strip()}",
    ]
    ENV_PATH.write_text("\n".join(lines) + "\n")

    # Restart the process as entrypoint.py — replaces this server with the bot
    import threading
    def _restart():
        import time; time.sleep(1)  # let the HTTP response return first
        os.execv(sys.executable, [sys.executable, str(Path(__file__).parent / "entrypoint.py")])
    threading.Thread(target=_restart, daemon=True).start()

    return {"ok": True}


# ── Runner ────────────────────────────────────────────────────────────────────

def run():
    print("[setup] No config found — open http://localhost:8080 to configure PurpleFin")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
