# Hapax System Containerization Evaluation

*Research date: 2026-03-05. Based on direct inspection of all repos, Docker infrastructure, systemd units, and runtime dependencies.*

## Executive Summary

The Hapax system has 13 Docker containers (infrastructure) and ~32K SLOC of Python agents running bare on the host via systemd. Containerizing the agents gains isolation, reproducible deployment, and resolves the docling/pydantic-ai dependency conflict. The natural system boundary: application-logic agents go in containers; host-diagnostic agents and desktop tools stay on the host.

---

## Current Deployment Topology

### Already in Docker (~/llm-stack/docker-compose.yml)

| Service | Image | Port | Memory | GPU | Profile |
|---------|-------|------|--------|-----|---------|
| qdrant | qdrant/qdrant:latest | 6333 | — | No | default |
| ollama | ollama/ollama:latest | 11434 | 20G | Yes (RTX 3090) | default |
| postgres | pgvector/pgvector:pg16 | 5432 | 4G | No | default |
| litellm | berriai/litellm | 4000 | 2G | No | default |
| clickhouse | clickhouse-server:latest | 8123 | 4G | No | full |
| redis | redis:7-alpine | internal | 512M | No | full |
| minio | minio/minio:latest | 9090 | 1G | No | full |
| langfuse-worker | langfuse-worker:3 | 3030 | 2G | No | full |
| langfuse | langfuse:3 | 3000 | 2G | No | full |
| open-webui | open-webui:main | 3080 | 2G | No | full |
| n8n | n8nio/n8n:latest | 5678 | 1G | No | full |
| ntfy | binwiederhier/ntfy:latest | 8090 | 256M | No | full |
| chatterbox | chatterbox-tts-api:latest | 4123 | 4G | Yes (RTX 3090) | tts |

Network: Bridge (`llm-stack`), all ports bound to 127.0.0.1.
Secrets: `.env` file generated from `pass` store via `generate-env.sh`.

### Running Bare on Host

| Component | Invocation | Schedule | Resource Limit |
|-----------|------------|----------|----------------|
| logos API | `uv run python -m logos.api` | Always running | — |
| health_monitor | `health-watchdog` | Every 15 min | 2G / 60% CPU |
| briefing | `briefing-watchdog` | Daily 07:00 | 2G / 60% CPU |
| digest | `digest-watchdog` | Daily 06:45 | 2G / 60% CPU |
| meeting_prep | `meeting-prep-watchdog` | Daily 06:30 | 2G / 60% CPU |
| profile_update | `profile-update-watchdog` | Every 12h | 2G / 60% CPU |
| scout | `scout-watchdog` | Weekly Wed 10:00 | 2G / 80% CPU |
| drift_detector | `drift-detector-watchdog` | Weekly Sun 03:00 | 2G / 60% CPU |
| knowledge_maint | `knowledge-maint-watchdog` | Weekly Sun 04:30 | 2G / 60% CPU |
| manifest_snapshot | `manifest-snapshot-watchdog` | Weekly Sun 02:30 | 512M / 30% CPU |
| rag-ingest | `.venv-ingest/bin/python -m agents.ingest` | Always running | 4G / 80% CPU |
| backup | `backup.sh` | Weekly Sun 02:00 | — |

### Desktop-Only (not containerizable)

| Component | Why |
|-----------|-----|
| Claude Code | MCP servers, Wayland clipboard, desktop integration |
| hapax-vscode | Runs in VS Code, corporate boundary provider routing |
| LLM hotkeys | `wl-copy`/`wl-paste`, `fuzzel`, `notify-send`, `ydotool` |

---

## Agent Dependency Analysis

### External Tool Dependencies (subprocess calls)

| Tool | Used By | Purpose | Container Compatible? |
|------|---------|---------|----------------------|
| `pass` | health_monitor, scout | GPG-encrypted secret retrieval | No — needs GPG agent, TTY |
| `docker` / `docker compose` | health_monitor | Container status checks, remediation | No — needs Docker socket |
| `systemctl --user` | health_monitor | Timer/service status, remediation | No — no systemd in container |
| `nvidia-smi` | health_monitor | GPU VRAM monitoring | No — needs GPU device access |
| `git` | profiler_sources, scout | Read git history, check remotes | Yes — mount repos read-only |
| `notify-send` | shared/notify.py | Desktop notifications (fallback) | No — needs display server |

### Network Dependencies

All agents connect to services via HTTP. Environment variables already exist for all endpoints:

| Service | Env Var | Default | Used By |
|---------|---------|---------|---------|
| LiteLLM | `LITELLM_API_BASE` | `http://localhost:4000` | All LLM agents |
| Qdrant | `QDRANT_URL` | `http://localhost:6333` | research, knowledge_maint, profiler, ingest |
| Ollama | (hardcoded) | `http://localhost:11434` | shared/config.py embed(), ingest.py |
| Langfuse | `LANGFUSE_HOST` | `http://localhost:3000` | All agents (observability) |
| ntfy | `NTFY_BASE_URL` | `http://localhost:8090` | notify.py |
| n8n | (hardcoded) | `http://localhost:5678` | health_monitor (healthz only) |
| Logos API | (hardcoded) | `http://localhost:8050` | health_monitor (healthz only) |

**Action needed:** Make Ollama URL configurable via env var in `shared/config.py`.

### Filesystem Access

| Host Path | Purpose | Mode | Size | Agents |
|-----------|---------|------|------|--------|
| `data/` | Work vault | rw | ~500MB | vault_writer, management_bridge, briefing, management_prep, meeting_lifecycle |
| `data/` | Personal vault | rw | ~200MB | vault_writer |
| `profiles/` | Operator profile data | rw | 347MB | profiler, briefing, activity_analyzer, logos API |
| `~/documents/rag-sources/` | RAG document drop zone | ro | 344MB | ingest (watches for new files) |
| `~/.cache/logos/` | Logos session state | rw | 36KB | logos API |
| `~/.cache/axiom-audit/` | Axiom audit trail | rw | 292KB | drift_detector, axiom tools |
| `~/.cache/rag-ingest/` | Dedup tracker + retry queue | rw | 20MB | ingest |
| `~/.cache/health-watchdog/` | Health alert state | rw | 8KB | health_monitor (HOST ONLY) |
| `~/.password-store/` | GPG secrets | ro | — | health_monitor (HOST ONLY) |
| `~/.gnupg/` | GPG keys | ro | — | health_monitor (HOST ONLY) |

### GPU Access

No agent needs direct GPU access. All GPU work happens via network calls:
- Embedding: Ollama HTTP API (localhost:11434)
- LLM inference: LiteLLM proxy → Ollama (Docker internal)
- TTS: Chatterbox HTTP API (localhost:4123)

---

## Containerization Decision Matrix

### Containerize (application logic)

| Agent | Reason |
|-------|--------|
| logos API | Already has Dockerfile.api. Pure HTTP service. |
| briefing | Reads profile + Langfuse, writes to vault. No host tools. |
| scout | Reads Qdrant + LiteLLM. `pass` call for Tavily key → replace with env var. |
| research | Qdrant search + LLM. Stateless. |
| profiler | Profile read/write + LLM. Stateless per invocation. |
| digest | Qdrant search + LLM + vault write. No host tools. |
| management_prep | Vault read + LLM. No host tools. |
| meeting_lifecycle | Vault read/write + LLM. No host tools. |
| code_review | LLM only. Stateless. |
| knowledge_maint | Qdrant operations. No host tools. |
| drift_detector | Reads docs + LLM comparison. `git` for repo scanning → mount repos or skip. |
| activity_analyzer | Reads Langfuse API + health history. No host tools. |
| ingest | Watches filesystem + Docling + Ollama + Qdrant. Separate image (dependency conflict). |

### Keep on Host (host diagnostics)

| Agent | Reason |
|-------|--------|
| health_monitor | Calls `docker`, `systemctl`, `nvidia-smi`, `pass`. Its purpose is diagnosing the host — containerizing it defeats the purpose. |
| introspect | Reads Docker state + systemd units to generate infrastructure manifest. |
| backup.sh | Runs `docker compose exec`, `pg_dump`, copies host paths. |

### Exclude from Container Image (optional heavy deps)

| Component | Reason |
|-----------|--------|
| demo pipeline | Pulls in playwright, moviepy, pillow, matplotlib, chatterbox. ~2GB image bloat. Occasional use only. Could be a separate `hapax-demo` image later. |

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    DOCKER NETWORK (llm-stack)            │
│                                                          │
│  [existing infrastructure]    [NEW: agents profile]      │
│   ollama (:11434)              hapax-agents (:8050)      │
│   qdrant (:6333)                - logos API            │
│   litellm (:4000)               - all application agents │
│   langfuse (:3000)              - profiles/ volume       │
│   postgres (:5432)              - vault volumes          │
│   ntfy (:8090)                                           │
│   n8n (:5678)                  hapax-ingest              │
│   ...                           - RAG watchdog           │
│                                 - docling (isolated)     │
│                                 - rag-sources/ volume    │
└──────────────────────┬──────────────────────────────────┘
                       │ volume mounts + env vars
┌──────────────────────┴──────────────────────────────────┐
│                        HOST                              │
│                                                          │
│  systemd timers → docker compose run hapax-agents \      │
│                    uv run python -m agents.<name>        │
│                                                          │
│  health_monitor   (bare, needs docker/systemctl/gpu)     │
│  introspect       (bare, reads Docker state)             │
│  backup.sh        (bare, needs docker compose exec)      │
│  Claude Code      (desktop)                              │
│  hapax-vscode     (desktop)                              │
│  LLM hotkeys      (desktop)                              │
│                                                          │
│  data/          → mounted rw into agents     │
│  data/      → mounted rw into agents     │
│  ~/documents/rag-sources/   → mounted ro into ingest     │
│  profiles/        → mounted rw into agents     │
└──────────────────────────────────────────────────────────┘
```

## Docker Compose Additions (to llm-stack/docker-compose.yml)

```yaml
hapax-agents:
  build:
    context: ../projects/ai-agents
    dockerfile: Dockerfile
  profiles: [agents]
  networks:
    - llm-stack
  volumes:
    - ${HOME}/Documents/Work:/data/vaults/work
    - ${HOME}/Documents/Personal:/data/vaults/personal
    - ${HOME}/projects/profiles:/data/profiles
    - ${HOME}/.cache/logos:/data/cache/logos
    - ${HOME}/.cache/axiom-audit:/data/cache/axiom-audit
  environment:
    - HAPAX_HOME=/data
    - WORK_VAULT_PATH=/data/vaults/work
    - PERSONAL_VAULT_PATH=/data/vaults/personal
    - LITELLM_API_BASE=http://litellm:4000
    - QDRANT_URL=http://qdrant:6333
    - OLLAMA_URL=http://ollama:11434
    - LANGFUSE_HOST=http://langfuse:3000
    - NTFY_BASE_URL=http://ntfy:8090
  env_file: .env  # API keys from generate-env.sh
  ports:
    - "127.0.0.1:8050:8050"
  mem_limit: 2g
  restart: unless-stopped
  depends_on:
    litellm:
      condition: service_healthy
    qdrant:
      condition: service_healthy

hapax-ingest:
  build:
    context: ../projects/ai-agents
    dockerfile: Dockerfile.ingest
  profiles: [agents]
  networks:
    - llm-stack
  volumes:
    - ${HOME}/documents/rag-sources:/data/rag-sources:ro
    - ${HOME}/.cache/rag-ingest:/data/cache/rag-ingest
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

## Code Changes Required

| Change | File(s) | Effort | Risk |
|--------|---------|--------|------|
| Make Ollama URL configurable via env var | `shared/config.py`, `agents/ingest.py` | Trivial | None |
| New `Dockerfile` (multi-stage, excludes demo pipeline) | `Dockerfile` | Low | Low |
| New `Dockerfile.ingest` (docling + watchdog only) | `Dockerfile.ingest` | Low | Low |
| Replace `pass` call in scout with env var | `agents/scout.py` | Trivial | None |
| Disable `notify-send` when no display | `shared/notify.py` | Trivial | None |
| Add `OLLAMA_URL` to config constants | `shared/config.py` | Trivial | None |
| Update systemd watchdogs to use `docker compose run` | `systemd/watchdogs/*` | Medium | Low |
| Add hapax-agents + hapax-ingest to compose | `llm-stack/docker-compose.yml` | Low | Low |
| Update officium-web API base URL | `officium-web/` config | Trivial | None |
| Update hapax-vscode logos URL | `vscode/` settings | Trivial | None |

## Environment Variables for Container

```bash
# Required (from generate-env.sh / pass store)
LITELLM_API_KEY=<litellm/master-key>
LANGFUSE_PUBLIC_KEY=<langfuse/public-key>
LANGFUSE_SECRET_KEY=<langfuse/secret-key>
TAVILY_API_KEY=<api/tavily>          # Scout agent only
ANTHROPIC_API_KEY=<api/anthropic>    # Direct provider fallback

# Service endpoints (Docker internal DNS)
LITELLM_API_BASE=http://litellm:4000
QDRANT_URL=http://qdrant:6333
OLLAMA_URL=http://ollama:11434
LANGFUSE_HOST=http://langfuse:3000
NTFY_BASE_URL=http://ntfy:8090

# Path configuration
HAPAX_HOME=/data
WORK_VAULT_PATH=/data/vaults/work
PERSONAL_VAULT_PATH=/data/vaults/personal

# Optional
NTFY_TOPIC=logos
OTEL_EXPORTER_OTLP_ENDPOINT=http://langfuse:3000/api/public/otel
```

## Scheduling Strategy

Systemd timers remain on the host but invoke containerized agents:

```bash
# Before (current watchdog pattern):
ExecStart=~/.local/bin/briefing-watchdog

# After (container invocation):
ExecStart=/usr/bin/docker compose -f ~/llm-stack/docker-compose.yml \
  run --rm hapax-agents uv run python -m agents.briefing --save
```

The logos API and RAG ingest run as persistent containers (`restart: unless-stopped`).
Scheduled agents run as one-shot containers (`docker compose run --rm`).

## Open Questions

1. **Demo pipeline:** Separate image (`hapax-demo`) or leave on host? If containerized, needs playwright + moviepy + GPU access for chatterbox.
2. **officium-web:** Bundle static build into hapax-agents image, or keep separate? Currently runs via `pnpm dev` on host.
3. **health_monitor container awareness:** Should health_monitor's Docker checks understand the new agent containers? (Probably yes — add to service tier list.)
4. **Git repos for drift_detector/profiler:** Mount project repos read-only into container, or skip those features in container mode?
5. **Backup script:** Should it back up the new container state? (Profiles volume is already backed up.)
