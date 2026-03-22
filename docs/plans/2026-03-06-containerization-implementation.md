# Hapax Agent Containerization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Containerize Tier 2 agents + logos API into two Docker images (`hapax-agents`, `hapax-ingest`) that boot cold with no pre-existing data.

**Architecture:** Two images join the existing `llm-stack` Docker network. An entrypoint script bootstraps Qdrant collections and Ollama models before launching the main process. Systemd timers on the host invoke containerized agents via `docker compose run --rm`.

**Tech Stack:** Python 3.12, uv, Docker multi-stage builds, Qdrant REST API, Ollama HTTP API, bash entrypoint.

**Design doc:** `docs/plans/2026-03-06-containerization-design.md`

---

### Task 1: Add OLLAMA_URL env var to shared/config.py

**Files:**
- Modify: `shared/config.py:22-23,110-116`
- Test: `tests/test_config_ollama_url.py`

**Step 1: Write the failing test**

Create `tests/test_config_ollama_url.py`:

```python
"""Test OLLAMA_URL env var support in shared/config."""
from unittest.mock import patch


def test_ollama_url_default():
    """OLLAMA_URL defaults to localhost:11434."""
    with patch.dict("os.environ", {}, clear=False):
        import importlib
        import shared.config as cfg
        importlib.reload(cfg)
        assert cfg.OLLAMA_URL == "http://localhost:11434"


def test_ollama_url_from_env():
    """OLLAMA_URL reads from environment."""
    with patch.dict("os.environ", {"OLLAMA_URL": "http://ollama:11434"}):
        import importlib
        import shared.config as cfg
        importlib.reload(cfg)
        assert cfg.OLLAMA_URL == "http://ollama:11434"


def test_ollama_client_uses_url():
    """_get_ollama_client passes OLLAMA_URL to Client constructor."""
    with patch.dict("os.environ", {"OLLAMA_URL": "http://ollama:11434"}):
        import importlib
        import shared.config as cfg
        importlib.reload(cfg)
        cfg._ollama_client = None  # reset singleton
        with patch("ollama.Client") as mock_client:
            cfg._get_ollama_client()
            mock_client.assert_called_once_with(host="http://ollama:11434", timeout=120)
```

**Step 2: Run test to verify it fails**

Run: `cd ai-agents && uv run pytest tests/test_config_ollama_url.py -v`
Expected: FAIL — `OLLAMA_URL` attribute doesn't exist on module.

**Step 3: Write minimal implementation**

In `shared/config.py`, add after line 22 (`QDRANT_URL`):

```python
OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://localhost:11434")
```

Update `_get_ollama_client()` (around line 115):

```python
def _get_ollama_client():
    """Return a singleton Ollama client (avoids per-call HTTP client creation)."""
    global _ollama_client
    if _ollama_client is None:
        import ollama
        _ollama_client = ollama.Client(host=OLLAMA_URL, timeout=120)
    return _ollama_client
```

**Step 4: Run test to verify it passes**

Run: `cd ai-agents && uv run pytest tests/test_config_ollama_url.py -v`
Expected: 3 passed.

**Step 5: Run existing tests to verify no regressions**

Run: `cd ai-agents && uv run pytest tests/ -q -x`
Expected: All pass.

**Step 6: Commit**

```bash
cd ai-agents && git add shared/config.py tests/test_config_ollama_url.py
git commit -m "feat: add OLLAMA_URL env var to shared/config.py"
```

---

### Task 2: Add OLLAMA_URL env var to agents/ingest.py

**Files:**
- Modify: `agents/ingest.py:28,119-124`
- Test: `tests/test_ingest_ollama_url.py`

**Step 1: Write the failing test**

Create `tests/test_ingest_ollama_url.py`:

```python
"""Test OLLAMA_URL env var support in ingest.py."""
from unittest.mock import patch


def test_ingest_ollama_url_default():
    """Ingest OLLAMA_URL defaults to localhost:11434."""
    with patch.dict("os.environ", {}, clear=False):
        import importlib
        import agents.ingest as ing
        importlib.reload(ing)
        assert ing.OLLAMA_URL == "http://localhost:11434"


def test_ingest_ollama_url_from_env():
    """Ingest OLLAMA_URL reads from environment."""
    with patch.dict("os.environ", {"OLLAMA_URL": "http://ollama:11434"}):
        import importlib
        import agents.ingest as ing
        importlib.reload(ing)
        assert ing.OLLAMA_URL == "http://ollama:11434"


def test_ingest_embed_uses_ollama_url():
    """embed() creates client with configured OLLAMA_URL."""
    with patch.dict("os.environ", {"OLLAMA_URL": "http://ollama:11434"}):
        import importlib
        import agents.ingest as ing
        importlib.reload(ing)
        with patch("ollama.Client") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.embed.return_value = {"embeddings": [[0.1] * 768]}
            ing.embed("test text")
            mock_cls.assert_called_with(host="http://ollama:11434")
```

**Step 2: Run test to verify it fails**

Run: `cd ai-agents && uv run pytest tests/test_ingest_ollama_url.py -v`
Expected: FAIL — ingest.py doesn't have `OLLAMA_URL` constant or use `ollama.Client(host=...)`.

**Step 3: Write minimal implementation**

In `agents/ingest.py`, add after line 28 (after `QDRANT_URL`):

```python
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
```

Update the `embed()` function (around line 119-124):

```python
def embed(text: str, prefix: str = "search_document") -> list[float]:
    """Generate embedding via Ollama with nomic prefix."""
    import ollama
    client = ollama.Client(host=OLLAMA_URL)
    prefixed = f"{prefix}: {text}" if prefix else text
    result = client.embed(model=EMBEDDING_MODEL, input=prefixed)
    return result["embeddings"][0]
```

**Step 4: Run test to verify it passes**

Run: `cd ai-agents && uv run pytest tests/test_ingest_ollama_url.py -v`
Expected: 3 passed.

**Step 5: Commit**

```bash
cd ai-agents && git add agents/ingest.py tests/test_ingest_ollama_url.py
git commit -m "feat: add OLLAMA_URL env var to agents/ingest.py"
```

---

### Task 3: Remove pass fallback from scout.py

**Files:**
- Modify: `agents/scout.py:527-543`
- Test: `tests/test_scout.py` (verify existing tests still pass)

**Step 1: Write the failing test**

Create `tests/test_scout_no_pass.py`:

```python
"""Test that scout no longer shells out to pass for TAVILY_API_KEY."""
from unittest.mock import patch


def test_scout_does_not_call_pass():
    """Scout should not call subprocess for pass store."""
    import agents.scout as scout
    # Grep the source for 'pass' subprocess call
    import inspect
    source = inspect.getsource(scout)
    assert "pass\", \"show\"" not in source, "scout.py still contains pass subprocess call"


def test_scout_exits_without_tavily_key():
    """Scout exits cleanly when TAVILY_API_KEY is not set."""
    with patch.dict("os.environ", {"TAVILY_API_KEY": ""}, clear=False):
        import importlib
        import agents.scout as scout
        importlib.reload(scout)
        assert scout.TAVILY_API_KEY == ""
```

**Step 2: Run test to verify it fails**

Run: `cd ai-agents && uv run pytest tests/test_scout_no_pass.py -v`
Expected: First test FAILs — source still contains the pass call.

**Step 3: Write minimal implementation**

In `agents/scout.py`, replace lines 527-543 with:

```python
    if not TAVILY_API_KEY and not args.dry_run:
        print("Error: TAVILY_API_KEY not set", file=sys.stderr)
        print("Set TAVILY_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)
```

Remove the `global TAVILY_API_KEY` and the `subprocess.run(["pass", ...])` block entirely.

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_scout_no_pass.py tests/test_scout.py -v`
Expected: All pass.

**Step 5: Commit**

```bash
cd ai-agents && git add agents/scout.py tests/test_scout_no_pass.py
git commit -m "feat: remove pass store fallback from scout, use env var only"
```

---

### Task 4: Add display check to notify-send in shared/notify.py

**Files:**
- Modify: `shared/notify.py:286-300`
- Test: `tests/test_notify_display.py`

**Step 1: Write the failing test**

Create `tests/test_notify_display.py`:

```python
"""Test that notify-send is skipped when no display server is available."""
from unittest.mock import patch


def test_send_desktop_skips_without_display():
    """_send_desktop returns False immediately when no DISPLAY or WAYLAND_DISPLAY."""
    with patch.dict("os.environ", {}, clear=True):
        from shared.notify import _send_desktop
        with patch("subprocess.run") as mock_run:
            result = _send_desktop("title", "message")
            assert result is False
            mock_run.assert_not_called()


def test_send_desktop_runs_with_display():
    """_send_desktop attempts notify-send when DISPLAY is set."""
    with patch.dict("os.environ", {"DISPLAY": ":0"}, clear=True):
        from shared.notify import _send_desktop
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = _send_desktop("title", "message")
            mock_run.assert_called_once()


def test_send_desktop_runs_with_wayland():
    """_send_desktop attempts notify-send when WAYLAND_DISPLAY is set."""
    with patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-0"}, clear=True):
        from shared.notify import _send_desktop
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = _send_desktop("title", "message")
            mock_run.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd ai-agents && uv run pytest tests/test_notify_display.py -v`
Expected: First test FAILs — `_send_desktop` still calls `subprocess.run` without display check.

**Step 3: Write minimal implementation**

In `shared/notify.py`, update `_send_desktop()` at line 286:

```python
def _send_desktop(title: str, message: str, *, priority: str = "default") -> bool:
    """Send notification via notify-send (desktop only)."""
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return False
    urgency = _DESKTOP_URGENCY.get(priority, "normal")
    cmd = [
        "notify-send",
        f"--urgency={urgency}",
        "--app-name=LLM Stack",
        title,
        message,
    ]
    try:
        result = subprocess.run(cmd, timeout=5, capture_output=True)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_notify_display.py -v`
Expected: 3 passed.

**Step 5: Run existing tests**

Run: `cd ai-agents && uv run pytest tests/ -q -x`
Expected: All pass.

**Step 6: Commit**

```bash
cd ai-agents && git add shared/notify.py tests/test_notify_display.py
git commit -m "feat: skip notify-send when no display server available"
```

---

### Task 5: Fix hardcoded URLs in shared/capacity.py and shared/health_correlator.py

**Files:**
- Modify: `shared/capacity.py:107,112`
- Modify: `shared/health_correlator.py:91`
- Test: `tests/test_hardcoded_urls.py`

**Step 1: Write the failing test**

Create `tests/test_hardcoded_urls.py`:

```python
"""Test that shared modules don't have hardcoded localhost URLs for containerized services."""
import inspect


def test_capacity_no_hardcoded_qdrant_url():
    """capacity.py should not hardcode localhost:6333."""
    import shared.capacity as cap
    source = inspect.getsource(cap)
    assert "localhost:6333" not in source, "capacity.py still has hardcoded Qdrant URL"


def test_health_correlator_no_hardcoded_langfuse_url():
    """health_correlator.py should not hardcode localhost:3000."""
    import shared.health_correlator as hc
    source = inspect.getsource(hc)
    assert "localhost:3000" not in source, "health_correlator.py still has hardcoded Langfuse URL"
```

**Step 2: Run test to verify it fails**

Run: `cd ai-agents && uv run pytest tests/test_hardcoded_urls.py -v`
Expected: Both FAIL.

**Step 3: Write minimal implementation**

In `shared/capacity.py`, replace lines 107 and 112. Add import at top:

```python
from shared.config import QDRANT_URL
```

Then replace the hardcoded URLs:

```python
        resp = urlopen(f"{QDRANT_URL}/collections", timeout=3)
        # ...
                resp2 = urlopen(f"{QDRANT_URL}/collections/{name}", timeout=3)
```

In `shared/health_correlator.py`, replace line 91. Add to the import block:

```python
import os
```

Then replace the hardcoded URL:

```python
    langfuse_host = os.environ.get("LANGFUSE_HOST", "http://localhost:3000")
    url = f"{langfuse_host.rstrip('/')}/api/public/traces?limit=50"
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_hardcoded_urls.py -v`
Expected: 2 passed.

**Step 5: Run existing tests**

Run: `cd ai-agents && uv run pytest tests/ -q -x`
Expected: All pass.

**Step 6: Commit**

```bash
cd ai-agents && git add shared/capacity.py shared/health_correlator.py tests/test_hardcoded_urls.py
git commit -m "fix: replace hardcoded localhost URLs in capacity and health_correlator"
```

---

### Task 6: Add TAVILY_API_KEY to generate-env.sh

**Files:**
- Modify: `llm-stack/generate-env.sh:44`

**Step 1: Add the new variable**

In `llm-stack/generate-env.sh`, add after line 44 (`TELEGRAM_CHAT_ID`):

```bash
TAVILY_API_KEY=$(pass show api/tavily)
```

**Step 2: Verify the script is syntactically valid**

Run: `bash -n llm-stack/generate-env.sh`
Expected: No output (no syntax errors).

**Step 3: Commit**

```bash
git add llm-stack/generate-env.sh
git commit -m "feat: add TAVILY_API_KEY to generate-env.sh"
```

---

### Task 7: Create entrypoint.sh

**Files:**
- Create: `entrypoint.sh`
- Test: Manual review (bash script, tested via Docker build in Task 10)

**Step 1: Write the entrypoint script**

Create `entrypoint.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-nomic-embed-text-v2-moe}"
EMBED_DIMS=768

COLLECTIONS=("documents" "samples" "claude-memory")

# ── Wait for Qdrant ──────────────────────────────────────────────────────
echo "entrypoint: waiting for Qdrant at $QDRANT_URL ..."
for i in $(seq 1 30); do
    if curl -sf "${QDRANT_URL}/healthz" >/dev/null 2>&1; then
        echo "entrypoint: Qdrant ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "entrypoint: ERROR — Qdrant not ready after 30s" >&2
        exit 1
    fi
    sleep 1
done

# ── Create Qdrant collections (idempotent) ───────────────────────────────
for coll in "${COLLECTIONS[@]}"; do
    HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
        -X PUT "${QDRANT_URL}/collections/${coll}" \
        -H "Content-Type: application/json" \
        -d "{\"vectors\":{\"size\":${EMBED_DIMS},\"distance\":\"Cosine\"}}" \
        2>/dev/null || echo "000")

    case "$HTTP_CODE" in
        200) echo "entrypoint: created collection '${coll}'" ;;
        409) echo "entrypoint: collection '${coll}' already exists" ;;
        *)   echo "entrypoint: WARNING — failed to create '${coll}' (HTTP ${HTTP_CODE})" >&2 ;;
    esac
done

# ── Pull Ollama embedding model (idempotent) ─────────────────────────────
echo "entrypoint: ensuring Ollama model '${EMBEDDING_MODEL}' ..."

# Check if model is already available
if curl -sf "${OLLAMA_URL}/api/tags" 2>/dev/null | grep -q "\"${EMBEDDING_MODEL}\""; then
    echo "entrypoint: model '${EMBEDDING_MODEL}' already present"
else
    echo "entrypoint: pulling '${EMBEDDING_MODEL}' (this may take a few minutes) ..."
    curl -sf -X POST "${OLLAMA_URL}/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"${EMBEDDING_MODEL}\",\"stream\":false}" \
        >/dev/null 2>&1 \
        && echo "entrypoint: model '${EMBEDDING_MODEL}' pulled successfully" \
        || echo "entrypoint: WARNING — failed to pull '${EMBEDDING_MODEL}'" >&2
fi

# ── Hand off to CMD ──────────────────────────────────────────────────────
exec "$@"
```

**Step 2: Make it executable**

Run: `chmod +x entrypoint.sh`

**Step 3: Verify syntax**

Run: `bash -n entrypoint.sh`
Expected: No output.

**Step 4: Commit**

```bash
cd ai-agents && git add entrypoint.sh
git commit -m "feat: add entrypoint.sh for Qdrant + Ollama bootstrap"
```

---

### Task 8: Create Dockerfile for hapax-agents

**Files:**
- Create: `Dockerfile`
- Reference: `Dockerfile.api` (existing, for comparison)

**Step 1: Write the Dockerfile**

Create `Dockerfile`:

```dockerfile
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
COPY pyproject.toml uv.lock ./
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
COPY cockpit/ cockpit/
COPY shared/ shared/
COPY profiles/ profiles/
COPY pyproject.toml uv.lock ./

# Copy entrypoint
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Container config
ENV HAPAX_HOME=/data
EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8050/')" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uv", "run", "python", "-m", "cockpit.api", "--host", "0.0.0.0"]
```

**Step 2: Verify it parses**

Run: `cd ai-agents && docker build --check -f Dockerfile .` (or just check syntax visually — Docker doesn't have `--check`).

**Step 3: Commit**

```bash
cd ai-agents && git add Dockerfile
git commit -m "feat: add Dockerfile for hapax-agents image"
```

---

### Task 9: Create Dockerfile.ingest for hapax-ingest

**Files:**
- Create: `Dockerfile.ingest`

**Step 1: Write the Dockerfile**

Create `Dockerfile.ingest`:

```dockerfile
# ============================================================================
# hapax-ingest — Isolated RAG ingestion image
# Separate from hapax-agents due to docling/pydantic-ai huggingface-hub conflict
# ============================================================================

FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install system deps for docling
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies directly (no pyproject.toml — avoids huggingface-hub conflict)
RUN uv pip install --system \
    "docling>=2.75.0" \
    "ollama>=0.6.1" \
    "watchdog>=6.0.0" \
    "qdrant-client>=1.17.0"

# Copy only the ingest agent
COPY agents/__init__.py agents/
COPY agents/ingest.py agents/

# Copy entrypoint
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Container config
ENV HAPAX_HOME=/data

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "-m", "agents.ingest"]
```

**Step 2: Commit**

```bash
cd ai-agents && git add Dockerfile.ingest
git commit -m "feat: add Dockerfile.ingest for isolated RAG pipeline"
```

---

### Task 10: Add hapax-agents and hapax-ingest to docker-compose.yml

**Files:**
- Modify: `llm-stack/docker-compose.yml` (add services before `volumes:` block)

**Step 1: Add the services**

In `llm-stack/docker-compose.yml`, add before the `volumes:` block (before line 382):

```yaml
  # ===================== AGENTS =====================

  # --- Hapax Agents + Logos API ---
  hapax-agents:
    build:
      context: ../projects/ai-agents
      dockerfile: Dockerfile
    container_name: hapax-agents
    restart: unless-stopped
    logging: *default-logging
    ports:
      - "127.0.0.1:8050:8050"
    volumes:
      - ${HOME}/Documents/Work:/data/Documents/Work
      - ${HOME}/Documents/Personal:/data/Documents/Personal
      - ${HOME}/projects/profiles:/app/profiles
      - ${HOME}/.cache/cockpit:/data/.cache/cockpit
      - ${HOME}/.cache/axiom-audit:/data/.cache/axiom-audit
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - HAPAX_HOME=/data
      - LITELLM_API_BASE=http://litellm:4000
      - LITELLM_API_KEY=${LITELLM_MASTER_KEY}
      - QDRANT_URL=http://qdrant:6333
      - OLLAMA_URL=http://ollama:11434
      - LANGFUSE_HOST=http://langfuse:3000
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
      - NTFY_BASE_URL=http://ntfy:80
      - TAVILY_API_KEY=${TAVILY_API_KEY:-}
    mem_limit: 4g
    depends_on:
      litellm:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    profiles:
      - agents

  # --- Hapax RAG Ingest (isolated — docling/pydantic-ai conflict) ---
  hapax-ingest:
    build:
      context: ../projects/ai-agents
      dockerfile: Dockerfile.ingest
    container_name: hapax-ingest
    restart: unless-stopped
    logging: *default-logging
    volumes:
      - ${HOME}/documents/rag-sources:/data/documents/rag-sources:ro
      - ${HOME}/.cache/rag-ingest:/data/.cache/rag-ingest
    environment:
      - HAPAX_HOME=/data
      - QDRANT_URL=http://qdrant:6333
      - OLLAMA_URL=http://ollama:11434
    mem_limit: 4g
    cpus: 0.8
    depends_on:
      qdrant:
        condition: service_healthy
    profiles:
      - agents
```

**Step 2: Validate compose file**

Run: `cd llm-stack && docker compose --profile agents config --quiet`
Expected: No output (valid config). May warn about missing `.env` — that's fine in the snapshot repo.

**Step 3: Commit**

```bash
git add llm-stack/docker-compose.yml
git commit -m "feat: add hapax-agents and hapax-ingest to docker-compose.yml"
```

---

### Task 11: Rewrite systemd watchdog scripts

**Files:**
- Modify: `systemd/watchdogs/briefing-watchdog`
- Modify: `systemd/watchdogs/scout-watchdog`
- Modify: `systemd/watchdogs/digest-watchdog`
- Modify: `systemd/watchdogs/drift-watchdog`
- Modify: `systemd/watchdogs/knowledge-maint-watchdog`
- Modify: `systemd/watchdogs/meeting-prep-watchdog`

**Step 1: Create a shared helper pattern**

Each watchdog follows the same pattern. The `docker compose run --rm` invocation replaces the direct `uv run` call. Notification is still handled by the agent itself (via `--notify` flags or shared.notify inside the container).

Rewrite each watchdog. Example — `briefing-watchdog`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Daily briefing generator — runs agent in container
COMPOSE_FILE="$HOME/llm-stack/docker-compose.yml"
DC="docker compose -f $COMPOSE_FILE --profile agents"

REPORT=$($DC run --rm hapax-agents \
    uv run python -m agents.briefing --hours 24 --save --json 2>/dev/null)

# Notify via container (pass JSON via stdin)
echo "$REPORT" | $DC run --rm -i hapax-agents \
    uv run python -c "
import sys, json
from shared.notify import send_notification
r = json.load(sys.stdin)
headline = r.get('headline', 'Briefing generated')
high = [a for a in r.get('action_items', []) if a.get('priority') == 'high']
body = headline
if high:
    body += f'\n{len(high)} high-priority action(s) need attention'
priority = 'high' if high else 'default'
send_notification('Daily Briefing', body, priority=priority, tags=['clipboard'])
" 2>/dev/null || true
```

Apply the same pattern to all 6 watchdogs:

- **scout-watchdog**: `$DC run --rm hapax-agents uv run python -m agents.scout --save --notify`
- **digest-watchdog**: `$DC run --rm hapax-agents uv run python -m agents.digest --hours 24 --save --json`
- **drift-watchdog**: `$DC run --rm hapax-agents uv run python -m agents.drift_detector --json`
- **knowledge-maint-watchdog**: `$DC run --rm hapax-agents uv run python -m agents.knowledge_maint --apply --save --json`
- **meeting-prep-watchdog**: `$DC run --rm hapax-agents uv run python -m agents.meeting_lifecycle --prepare --save --json`

Key changes in each:
1. Remove `cd ~/projects/ai-agents` and `eval "$(<.envrc)"`
2. Replace `$UV run python -m agents.<name>` with `$DC run --rm hapax-agents uv run python -m agents.<name>`
3. Replace inline `notify-send` fallbacks with container-based `shared.notify` calls
4. Remove hardcoded paths to `$UV` and `$PROFILES` — container handles paths internally

**Step 2: Commit**

```bash
cd ai-agents && git add systemd/watchdogs/
git commit -m "feat: rewrite watchdog scripts for containerized agent invocation"
```

---

### Task 12: Build and smoke-test the images

**Files:**
- No new files — integration test of prior tasks

**Step 1: Build hapax-agents image**

Run: `cd ai-agents && docker build -f Dockerfile -t hapax-agents .`
Expected: Build succeeds. May take 5-10 minutes on first run (Playwright browsers, Node.js, d2).

**Step 2: Build hapax-ingest image**

Run: `cd ai-agents && docker build -f Dockerfile.ingest -t hapax-ingest .`
Expected: Build succeeds. Docling pull may take a few minutes.

**Step 3: Smoke-test entrypoint (requires running Qdrant + Ollama)**

Run against the live stack:

```bash
docker run --rm --network llm-stack \
    -e QDRANT_URL=http://qdrant:6333 \
    -e OLLAMA_URL=http://ollama:11434 \
    hapax-agents echo "bootstrap complete"
```

Expected: Entrypoint creates collections, pulls model (or confirms they exist), then prints "bootstrap complete".

**Step 4: Smoke-test logos API**

```bash
docker run --rm --network llm-stack \
    -e QDRANT_URL=http://qdrant:6333 \
    -e OLLAMA_URL=http://ollama:11434 \
    -e LITELLM_API_BASE=http://litellm:4000 \
    -e HAPAX_HOME=/data \
    -p 127.0.0.1:8050:8050 \
    hapax-agents &

sleep 5
curl -s http://127.0.0.1:8050/ && echo "API responding"
docker stop $(docker ps -q --filter ancestor=hapax-agents)
```

Expected: API responds on `:8050`.

**Step 5: Run test suite inside container**

```bash
cd ai-agents && docker run --rm hapax-agents uv run pytest tests/ -q -x
```

Expected: All tests pass inside the container.

**Step 6: Commit (no files changed — just verification)**

No commit needed. All prior tasks are already committed.

---

### Task 13: Final commit and update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (update to reflect containerized state)

**Step 1: Update CLAUDE.md**

Update the "Build, Test, and Run" section to include the new Docker commands:

```bash
# Build agent images
cd ai-agents && docker build -f Dockerfile -t hapax-agents .
cd ai-agents && docker build -f Dockerfile.ingest -t hapax-ingest .

# Run full stack with agents
cd llm-stack && docker compose --profile full --profile agents up -d

# Run a one-shot agent in the container
docker compose -f ~/llm-stack/docker-compose.yml --profile agents \
    run --rm hapax-agents uv run python -m agents.briefing --hours 24 --save
```

Update "Key Files to Modify" to mark completed items.

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for containerized deployment"
```
