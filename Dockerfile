# ============================================================================
# hapax-agents — Main agent image
# Multi-stage: build deps, then slim runtime with system tools
# ============================================================================

# ── Stage 1: Build ──────────────────────────────────────────────────────
FROM python:3.12-slim AS build

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies (cached layer)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# ── Stage 2: Runtime ────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install uv (needed for `uv run` in CMD and docker compose run)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# System tools: git, ffmpeg, curl, Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        ffmpeg \
        curl \
        ca-certificates \
        gnupg \
        make \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install d2 (diagram tool)
RUN curl -fsSL https://d2lang.com/install.sh | sh -s --

# Install Playwright browsers
RUN npx -y playwright install --with-deps chromium

# Copy Python venv from build stage
COPY --from=build /app/.venv /app/.venv

# Copy application code
COPY agents/ agents/
COPY logos/ logos/
COPY shared/ shared/
COPY profiles/ profiles/
COPY pyproject.toml uv.lock README.md ./

# Copy entrypoint
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser && \
    mkdir -p /data && chown appuser:appuser /data && \
    chown -R appuser:appuser /app
USER appuser

# Container config
ENV HAPAX_HOME=/data
EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8050/ || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uv", "run", "python", "-m", "logos.api", "--host", "0.0.0.0"]
