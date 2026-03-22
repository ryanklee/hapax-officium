# Hapax Agent Containerization Design

*Approved: 2026-03-06. Based on evaluation in `docs/containerization-evaluation.md` plus cold-start audit and codebase verification.*

## Goal

Move Tier 2 agents and the logos API from bare-metal systemd into Docker containers alongside the existing `llm-stack` infrastructure. The system must boot cold — no pre-existing data in databases, caches, or vaults.

## Two Images

### hapax-agents

Main image. Contains all 13 application-logic agents, the logos API, and the demo pipeline. Built from `Dockerfile`.

**Includes:**
- All agents: briefing, scout, profiler, digest, management_prep, meeting_lifecycle, code_review, research, knowledge_maint, drift_detector, activity_analyzer, query, demo pipeline
- Logos API server (`:8050`)
- System tools: `git`, `ffmpeg`, `d2`, Node.js/`npx` (for marp-cli), Playwright + Chromium

**Excludes:**
- health_monitor (needs docker CLI on host, systemctl, nvidia-smi, pass)
- introspect (reads Docker state + systemd for manifest generation)
- backup.sh (needs `docker compose exec`, `pg_dump`, host paths)

**Default command:** Logos API (`uv run python -m cockpit.api --host 0.0.0.0`)

### hapax-ingest

Isolated image for RAG ingestion. Separate because docling requires `huggingface-hub<1` while pydantic-ai requires `>=1.3.4` — they cannot coexist.

**Includes:** `agents/ingest.py` + deps (`docling`, `ollama`, `watchdog`, `qdrant-client`). Does not use `pyproject.toml` — has its own minimal dep list.

**Default command:** RAG watchdog (`python agents/ingest.py`)

## Entrypoint Bootstrap

Both images share an `entrypoint.sh` pattern that runs before the main process:

1. **Wait for Qdrant** — curl loop against Qdrant healthcheck endpoint until ready.
2. **Create Qdrant collections** — `documents`, `samples`, `claude-memory` (768-dim, cosine distance) via `PUT /collections/{name}` REST API. Idempotent — skips if collection exists (409 response).
3. **Pull Ollama embedding model** — `nomic-embed-text-v2-moe` via `POST /api/pull` REST API. Skips if already present.
4. **`exec "$@"`** — hands off to CMD.

Collections `profile-facts` and `axiom-precedents` are not created by the entrypoint — they have `ensure_collection()` methods in their respective Python modules that handle creation on first use.

## Docker Compose Integration

Both services added to `llm-stack/docker-compose.yml` under the `agents` profile. They join the default `llm-stack` network implicitly — no explicit `networks` stanza.

### hapax-agents service

```yaml
hapax-agents:
  build:
    context: ../projects/ai-agents
    dockerfile: Dockerfile
  profiles: [agents]
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
    - QDRANT_URL=http://qdrant:6333
    - OLLAMA_URL=http://ollama:11434
    - LANGFUSE_HOST=http://langfuse:3000
    - NTFY_BASE_URL=http://ntfy:80
  env_file: .env
  mem_limit: 4g
  restart: unless-stopped
  depends_on:
    litellm:
      condition: service_healthy
    qdrant:
      condition: service_healthy
```

### hapax-ingest service

```yaml
hapax-ingest:
  build:
    context: ../projects/ai-agents
    dockerfile: Dockerfile.ingest
  profiles: [agents]
  volumes:
    - ${HOME}/documents/rag-sources:/data/documents/rag-sources:ro
    - ${HOME}/.cache/rag-ingest:/data/.cache/rag-ingest
  environment:
    - HAPAX_HOME=/data
    - QDRANT_URL=http://qdrant:6333
    - OLLAMA_URL=http://ollama:11434
  mem_limit: 4g
  cpus: 0.8
  restart: unless-stopped
  depends_on:
    qdrant:
      condition: service_healthy
```

### Scheduled agents

Systemd timers remain on the host. Watchdog scripts rewritten to invoke containerized agents:

```bash
# Before:
cd ~/projects/ai-agents && eval "$(<.envrc)"
uv run python -m agents.briefing --hours 24 --save

# After:
docker compose -f ~/llm-stack/docker-compose.yml --profile agents \
  run --rm hapax-agents uv run python -m agents.briefing --hours 24 --save
```

One-shot containers (`--rm`), inherit the same image/env/volumes as the persistent service.

## Volume Layout

```
Host Path                              Container Path                 Mode
──────────────────────────────────────────────────────────────────────────────
# hapax-agents
data/                      /data/Documents/Work/           rw
data/                  /data/Documents/Personal/       rw
~/projects/profiles/         /app/profiles/                  rw
~/.cache/cockpit/                      /data/.cache/cockpit/           rw
~/.cache/axiom-audit/                  /data/.cache/axiom-audit/       rw
/var/run/docker.sock                   /var/run/docker.sock            ro

# hapax-ingest
~/documents/rag-sources/               /data/documents/rag-sources/    ro
~/.cache/rag-ingest/                   /data/.cache/rag-ingest/        rw
```

`HAPAX_HOME=/data` drives all path derivation. `PROFILES_DIR` is the exception — defined relative to source code (`Path(__file__).parent.parent / "profiles"`), resolves to `/app/profiles/` inside the image.

All host-side directories can start empty. Agents create cache dirs and vault subdirectories on first write.

## Dockerfile Strategy

### hapax-agents (multi-stage)

```
Stage 1 (build):
  FROM python:3.12-slim
  Install uv
  COPY pyproject.toml uv.lock
  uv sync --frozen --no-dev

Stage 2 (runtime):
  FROM python:3.12-slim
  Install system packages: git, ffmpeg, curl, nodejs/npm
  Install d2 (binary download from GitHub releases)
  Install Playwright: npx playwright install --with-deps chromium
  COPY --from=build /app/.venv
  COPY agents/ cockpit/ shared/ profiles/
  COPY entrypoint.sh
  ENTRYPOINT ["./entrypoint.sh"]
  CMD ["uv", "run", "python", "-m", "cockpit.api", "--host", "0.0.0.0"]
```

### hapax-ingest (single stage)

```
FROM python:3.12-slim
Install uv
Install deps directly: docling, ollama, watchdog, qdrant-client
COPY agents/ingest.py
COPY entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "agents/ingest.py"]
```

No `pyproject.toml` — avoids pulling in pydantic-ai and the huggingface-hub conflict.

## Code Changes Required

### Add OLLAMA_URL env var

**`shared/config.py`:**
```python
OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://localhost:11434")
```
Update `_get_ollama_client()`:
```python
_ollama_client = ollama.Client(host=OLLAMA_URL, timeout=120)
```

**`agents/ingest.py`:**
```python
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
```
Pass to its own `ollama.Client()` / `ollama.embed()` calls.

### Remove pass fallback from scout

**`agents/scout.py`:** Remove the `subprocess.run(["pass", "show", "api/tavily"])` fallback. Keep the existing `os.environ.get("TAVILY_API_KEY")` check. If no env var, log warning and skip Tavily searches.

### Display check for notify-send

**`shared/notify.py`:** In `_send_desktop()`, check for `DISPLAY` or `WAYLAND_DISPLAY` env var before attempting `notify-send`. If neither set, return `False` immediately.

### Fix hardcoded URLs in shared modules

**`shared/capacity.py`:** Replace `http://localhost:6333` with `QDRANT_URL` imported from `shared.config`.

**`shared/health_correlator.py`:** Replace `http://localhost:3000` with `LANGFUSE_HOST` env var (`os.environ.get("LANGFUSE_HOST", "http://localhost:3000")`).

### Update generate-env.sh

**`llm-stack/generate-env.sh`:** Add:
```bash
TAVILY_API_KEY=$(pass show api/tavily)
```

### Rewrite systemd watchdogs

**`systemd/watchdogs/*`:** Each watchdog script rewritten from direct `uv run` invocation to `docker compose run --rm hapax-agents ...`.

## Accepted Degradations

These features work on the host but degrade in the container. Accepted by design:

| Feature | Impact | Mitigation |
|---------|--------|------------|
| `systemctl --user list-timers` in cockpit | Timer status unavailable in logos dashboard | health_monitor (on host) writes timer data to shared cache |
| `notify-send` desktop notifications | Silent skip in container | ntfy push notifications remain primary channel |
| `sufficiency_probes.py` systemctl checks | Returns empty in container | Non-critical — sufficiency checks are advisory |
| CORS origins hardcoded to localhost | Works through port mapping | Document that access pattern must preserve localhost URLs |

## Cold Start Guarantees

The system boots from zero state:

| Component | Cold Start Behavior |
|-----------|-------------------|
| Qdrant | Entrypoint creates `documents`, `samples`, `claude-memory` collections |
| Ollama | Entrypoint pulls `nomic-embed-text-v2-moe` |
| PostgreSQL | `init-db.sql` creates databases + pgvector on first start |
| profiles/ | Git-tracked YAML files baked into image; all other files created on first agent run |
| Cache dirs | Created by agents via `mkdir(parents=True, exist_ok=True)` on first write |
| Vault dirs | Created by `vault_writer._ensure_dirs()` on first write |
| RAG sources | Empty directory; watchdog waits for files to appear |

## Not Changed

- `logos/api/app.py` CORS origins — localhost URLs work through port mapping
- `agents/health_monitor.py` hardcoded URLs — stays on host, not containerized
- `agents/introspect.py` hardcoded URLs — stays on host
- `shared/sufficiency_probes.py` systemctl calls — graceful degradation accepted
- `pyproject.toml` dependency list — demo pipeline deps stay in main list (included in image)
