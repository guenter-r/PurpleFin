# ── PlumFin Dockerfile ────────────────────────────────────────────────────────
FROM python:3.12-slim

# Keeps Python from generating .pyc files and enables unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps (needed by some yfinance/pandas wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Mutable data lives here — depot.yaml + sqlite DBs
# Mount this directory as a volume to persist across restarts
RUN mkdir -p /app/data/db
ENV DATA_DIR=/app/data

# Default interface is Telegram; override with INTERFACE=discord or INTERFACE=cli
ENV INTERFACE=telegram

CMD ["python", "entrypoint.py"]