# syntax=docker/dockerfile:1.7

# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Build deps for any wheels that don't ship as binary (kept minimal).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install the project (and only its runtime deps from pyproject.toml — no dev
# extras like pytest/ruff in the runtime image).
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip
COPY pyproject.toml README.md /build/
COPY src /build/src
RUN /opt/venv/bin/pip install /build


# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    DB_PATH="/data/cryptodivlinbot.sqlite"

# Create an unprivileged user and a writable data dir.
RUN groupadd --system app \
    && useradd --system --gid app --home-dir /home/app --create-home app \
    && mkdir -p /data \
    && chown -R app:app /data

# Bring the venv from the builder.
COPY --from=builder /opt/venv /opt/venv

USER app
WORKDIR /home/app

# SQLite lives on a mounted volume so state survives container restarts.
VOLUME ["/data"]

# Lightweight health probe: import the package + Settings parser.
# Avoids hitting Telegram or CoinGecko on every check.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import cryptodivlinbot, cryptodivlinbot.config" || exit 1

# Run the bot. TELEGRAM_BOT_TOKEN comes from the environment / compose file.
CMD ["python", "-m", "cryptodivlinbot"]
