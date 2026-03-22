# Project Consolidation Design

## Goal

Simplify the development surface by consolidating 16 repos down to 10, eliminating code duplication between ai-agents and hapax-containerization, and containerizing the RAG sync pipeline to replace 8 systemd timers with a single container.

## Current State (16 repos)

```
~/projects/
├── ai-agents/               28 agents, logos API, shared modules (ORIGIN)
├── hapax-containerization/  Management cockpit demo seed (COPIES 15 agents from ai-agents)
├── hapax-mgmt-web/             React SPA dashboard
├── hapaxromana/             Architecture specs, axioms (no code)
├── hapax-system/            Claude Code config (skills, rules, hooks)
├── vscode/            VS Code extension
├── obsidian-hapax/          Obsidian plugin
├── distro-work/             OS troubleshooting working directory
├── sample-search/           Experimental CLAP audio search
├── tabbyAPI/                ExLLaMA inference fork (external)
├── rag-pipeline/            DEPRECATED — absorbed into ai-agents
├── mcp-server-midi/         Python MIDI MCP server — NOT NEEDED
├── midi-mcp-server/         TypeScript MIDI MCP server — NOT NEEDED
├── audio-gen/               Stale, no git history
├── tabbyapi/                Empty .venv directory
└── docs/                    Empty directory
```

**Problems:**
1. hapax-containerization duplicates 15 agents + shared modules from ai-agents. Changes don't flow automatically — drift detector catches some, but it's structural debt.
2. Six repos are dead/deprecated/empty.
3. No containerized sync pipeline — 8 separate systemd timers manage RAG ingestion independently.

## Target State (10 repos)

```
~/projects/
├── ai-agents/               All Python code + Dockerfiles + production compose
├── hapax-mgmt/             Demo seed system (renamed from hapax-containerization)
├── hapax-mgmt-web/            React SPA + Dockerfile (unchanged)
├── hapaxromana/            Architecture specs (unchanged)
├── hapax-system/           Claude Code config (unchanged)
├── vscode/           VS Code extension (unchanged)
├── obsidian-hapax/         Obsidian plugin (unchanged)
├── distro-work/            OS working directory (unchanged)
├── sample-search/          Experimental audio search (unchanged)
└── tabbyAPI/               ExLLaMA inference fork (unchanged)
```

**Deleted:**
- `rag-pipeline` — deprecated, code in ai-agents
- `mcp-server-midi` — not needed
- `midi-mcp-server` — not needed
- `audio-gen` — stale, no version control
- `tabbyapi` — empty .venv
- `docs` — empty

## Design Decisions

### D1: ai-agents owns all Dockerfiles (C1 pattern)

Dockerfiles live next to the code they package. ai-agents gets:

- `Dockerfile.logos-api` — FastAPI logos API server (:8050)
- `Dockerfile.sync-pipeline` — RAG sync pipeline (cron-scheduled, replaces 8 systemd timers)
- `docker-compose.yml` — production compose wiring both services + cockpit-web

cockpit-web retains its own Dockerfile (already exists, different toolchain).

### D2: hapax-mgmt is thin orchestration for the demo seed

Renamed from hapax-containerization. Contains:

- `demo-data/` — synthetic management data corpus (checked into git)
- `scripts/bootstrap-demo.sh` — demo hydration pipeline
- `docker-compose.yml` — demo-specific compose that references ai-agents images
- `CLAUDE.md` — demo system documentation

**No duplicated Python code.** Demo compose pulls images built from ai-agents. The demo system exercises the full 28-agent roster (not just the 15 management agents previously ported).

### D3: Single sync-pipeline container replaces 8 systemd timers

One container, one cron daemon, one set of logs. Replaces:

| Systemd Timer | Schedule | Agent |
|---------------|----------|-------|
| gdrive-sync | 2h | gdrive_sync |
| gcalendar-sync | 30m | gcalendar_sync |
| gmail-sync | 1h | gmail_sync |
| youtube-sync | 6h | youtube_sync |
| claude-code-sync | 2h | claude_code_sync |
| obsidian-sync | 30m | obsidian_sync |
| chrome-sync | 1h | chrome_sync |
| audio-processor | 30m | audio_processor |

Container internals:
- Base image: Python 3.12-slim + uv + ffmpeg (for audio_processor)
- Entrypoint: crond foreground
- Crontab generated from schedule config
- Volume mounts for filesystem-coupled agents:
  - Google OAuth token (read-only)
  - Obsidian vault (read-only)
  - Chrome profile (read-only)
  - Claude Code transcripts (read-only)
  - Audio recordings (read-only)
- Network access to Qdrant, LiteLLM, Ollama (via docker network or host)
- Health endpoint or healthcheck command for monitoring
- Logs to stdout (docker logs)

### D4: Host-bound components stay on host

These cannot be meaningfully containerized:

| Component | Why |
|-----------|-----|
| Claude Code | IS the operator interface |
| hapax-system | Configures Claude Code |
| hapax-vscode | VS Code extension |
| hapax_voice | Mic + screen + speaker + wake word |
| audio_recorder | Continuous ffmpeg mic capture |
| bt-keepalive | Bluetooth audio stream |
| LLM hotkey scripts | Wayland compositor integration |
| vram-watchdog | GPU management via nvidia-smi |
| cycle-mode | Systemd timer orchestration |
| health-monitor | Monitors Docker + systemd + host services |

### D5: Dependency splitting for container images

The current pyproject.toml has ~50 dependencies including heavy audio/video/vision packages. Container images should only install what they need:

**logos-api image needs:**
fastapi, uvicorn, pydantic, pydantic-ai[litellm], qdrant-client, pyyaml, sse-starlette, watchdog, jinja2, httpx, langfuse, ollama

**sync-pipeline image needs:**
qdrant-client, pydantic, pyyaml, google-api-python-client, google-auth-oauthlib, httpx, ollama, langfuse, faster-whisper, silero-vad, soundfile, torchaudio (audio_processor only)

**Not needed in any container:**
playwright, moviepy, pillow, matplotlib, kokoro, piper-tts, pyaudio, google-genai, mediapipe, opencv-python-headless, pipecat-ai, panns-inference, pyannote-audio

This suggests splitting pyproject.toml into dependency groups or using separate requirements files per Dockerfile.

### D6: Production compose topology

```yaml
# ai-agents/ docker-compose.yml
services:
  logos-api:
    build:
      context: .
      dockerfile: Dockerfile.logos-api
    ports:
      - "127.0.0.1:8050:8050"
    volumes:
      - ./data:/app/data
    environment:
      - LITELLM_BASE_URL=http://host.docker.internal:4000
      - QDRANT_URL=http://host.docker.internal:6333
    restart: unless-stopped

  sync-pipeline:
    build:
      context: .
      dockerfile: Dockerfile.sync-pipeline
    volumes:
      - ./data:/app/data
      - ~/.config/hapax/google-token.json:/app/secrets/google-token.json:ro
      - data/:/mnt/vault-personal:ro
      - data/:/mnt/vault-work:ro
      - ~/.claude:/mnt/claude:ro
      - ~/.config/google-chrome:/mnt/chrome:ro
      - ~/recordings:/mnt/audio:ro
    environment:
      - LITELLM_BASE_URL=http://host.docker.internal:4000
      - QDRANT_URL=http://host.docker.internal:6333
      - OLLAMA_URL=http://host.docker.internal:11434
    restart: unless-stopped

  cockpit-web:
    image: cockpit-web:latest  # built from cockpit-web repo
    ports:
      - "127.0.0.1:8052:80"
    restart: unless-stopped
```

This compose sits alongside llm-stack's compose. They share the same Docker network for service discovery, or use host.docker.internal for simplicity.

### D7: Cycle mode integration

The dev/prod cycle mode currently modifies systemd timer schedules via drop-in overrides. With the sync pipeline containerized, cycle mode needs to also adjust the container's cron schedule. Options:

- **Environment variable:** `CYCLE_MODE=dev` → container reads it and applies different cron intervals
- **Config file mount:** cycle-mode script writes a schedule config, container watches it

Environment variable is simpler. Container entrypoint selects crontab based on `$CYCLE_MODE`.

## Migration Path

### Phase 1: Cleanup (low risk)
1. Delete dead repos (audio-gen, tabbyapi, docs, rag-pipeline, mcp-server-midi, midi-mcp-server)
2. Rename hapax-containerization → hapax-mgmt
3. Update all cross-references (CLAUDE.md files, hapaxromana, hapax-system rules)

### Phase 2: ai-agents containerization (medium risk)
4. Add dependency groups to pyproject.toml (logos-api, sync-pipeline, dev)
5. Create Dockerfile.logos-api (extract from existing hapax-containerization Dockerfile)
6. Create Dockerfile.sync-pipeline with crontab
7. Create docker-compose.yml in ai-agents root
8. Add cycle-mode awareness to sync-pipeline entrypoint
9. Test: build images, verify logos-api serves, verify sync agents run on schedule

### Phase 3: hapax-mgmt thinning (medium risk)
10. Remove duplicated Python code from hapax-mgmt
11. Update hapax-mgmt compose to reference ai-agents images
12. Update bootstrap-demo.sh to work with the new image structure
13. Verify demo hydration pipeline end-to-end

### Phase 4: Systemd timer migration (low risk, reversible)
14. Disable 8 sync-related systemd timers
15. Start sync-pipeline container
16. Monitor for 48h, verify all sync agents run correctly
17. Remove systemd timer unit files from ai-agents/ systemd/units/

## Risks

- **Volume mount complexity:** The sync pipeline needs 5+ read-only mounts. If paths change (Chrome profile location, vault reorganization), the compose file must be updated.
- **Audio processor GPU access:** faster-whisper may need GPU. If so, sync-pipeline container needs nvidia-container-toolkit runtime. Alternatively, audio_processor stays on host.
- **Google OAuth token refresh:** The token file is written by the agent during refresh. If mounted read-only, the container can't refresh expired tokens. May need read-write mount or a separate token refresh mechanism.
- **Demo system scope expansion:** Exercising all 28 agents in the demo means demo-data must cover non-management agent inputs (RAG documents, audio samples, etc.). This is additional work.

## Out of Scope

- Containerizing host-bound components (voice, audio recorder, hotkeys)
- Merging ai-agents + cockpit-web into a monorepo (different toolchains, kept separate)
- Migrating llm-stack services (already containerized, working well)
- Changes to hapaxromana, hapax-system, hapax-vscode, obsidian-hapax, distro-work, sample-search, tabbyAPI
