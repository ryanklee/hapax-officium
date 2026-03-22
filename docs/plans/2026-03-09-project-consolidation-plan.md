# Project Consolidation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Simplify the development surface from 16 repos to 10, eliminate code duplication, and containerize the RAG sync pipeline as a single container replacing 8 systemd timers.

**Architecture:** ai-agents becomes the single Python source of truth with Dockerfiles for logos-api and sync-pipeline. hapax-containerization is renamed to hapax-mgmt and stripped of duplicated Python code, retaining only demo-data, bootstrap scripts, and compose overrides. Six dead/deprecated repos are deleted.

**Tech Stack:** Python 3.12, Docker, uv, cron, FastAPI, Qdrant, LiteLLM

---

## Phase 1: Cleanup

### Task 1: Delete dead repos

**Context:** Six repos under `~/projects/` are dead, deprecated, empty, or no longer needed. They add cognitive load and clutter. None have upstream remotes that need preserving (except rag-pipeline which has a GitHub remote but is explicitly deprecated).

**Files:**
- Delete: `~/projects/audio-gen/` (stale, no git history)
- Delete: `~/projects/tabbyapi/` (empty .venv directory, NOT tabbyAPI)
- Delete: `~/projects/docs/` (empty directory)
- Delete: `~/projects/rag-pipeline/` (deprecated, absorbed into ai-agents)
- Delete: `~/projects/mcp-server-midi/` (not needed)
- Delete: `~/projects/midi-mcp-server/` (not needed)

**Step 1: Verify each repo's state before deletion**

```bash
# Confirm audio-gen has no git history
cd ~/projects/audio-gen && git status 2>&1 || echo "NOT A GIT REPO"

# Confirm tabbyapi is just an empty venv
ls -la ~/projects/tabbyapi/

# Confirm docs is empty
ls -la ~/projects/docs/

# Confirm rag-pipeline CLAUDE.md says deprecated
head -5 ~/projects/rag-pipeline/CLAUDE.md

# Confirm MIDI servers are standalone (no other project depends on them)
grep -r "mcp-server-midi\|midi-mcp-server" ~/projects/*/CLAUDE.md 2>/dev/null
```

**Step 2: Delete the repos**

```bash
rm -rf ~/projects/audio-gen
rm -rf ~/projects/tabbyapi
rm -rf ~/projects/docs
rm -rf ~/projects/rag-pipeline
rm -rf ~/projects/mcp-server-midi
rm -rf ~/projects/midi-mcp-server
```

**Step 3: Verify deletion**

```bash
ls ~/projects/
# Should show: ai-agents, cockpit-web, distro-work, hapax-containerization,
#              hapax-system, hapax-vscode, hapaxromana, obsidian-hapax,
#              sample-search, tabbyAPI
# (10 repos, down from 16)
```

No git commit needed — these are separate repos, not files in the current project.

---

### Task 2: Rename hapax-containerization → hapax-mgmt

**Context:** The repo name `hapax-containerization` is misleading — it's specifically the management cockpit demo seed, not a general containerization project. Renaming to `hapax-mgmt` clarifies its purpose.

**Files:**
- Rename: `~/projects/hapax-containerization/` → `~/projects/hapax-mgmt/`
- Modify: `~/projects/hapax-mgmt/CLAUDE.md`

**Step 1: Rename the directory**

```bash
mv ~/projects/hapax-containerization ~/projects/hapax-mgmt
```

**Step 2: Update CLAUDE.md header and self-references**

Open `~/projects/hapax-mgmt/CLAUDE.md`. Replace occurrences of `hapax-containerization` with `hapax-mgmt`. The key line is at the top identifying the project, plus any self-references in the body. Do a global find-replace.

**Step 3: Update git remote (if GitHub remote exists)**

```bash
cd ~/projects/hapax-mgmt
git remote -v
# If remote exists, update it:
# gh repo rename hapax-mgmt  (if using GitHub CLI)
# or: git remote set-url origin <new-url>
```

**Step 4: Verify**

```bash
cd ~/projects/hapax-mgmt && pwd
# ~/projects/hapax-mgmt

git status
# Should show modified CLAUDE.md
```

**Step 5: Commit**

```bash
cd ~/projects/hapax-mgmt
git add CLAUDE.md
git commit -m "refactor: rename hapax-containerization → hapax-mgmt

Clarifies this repo's purpose as the management cockpit demo seed system,
not a general containerization project."
```

---

### Task 3: Update cross-project references to hapax-containerization

**Context:** Several files in other repos reference `hapax-containerization` by name. These need updating to `hapax-mgmt`. The key files are in `hapaxromana/`.

**Files:**
- Modify: `~/projects/hapaxromana/CLAUDE.md` (line mentioning hapax-containerization)
- Modify: `~/projects/hapaxromana/docs/cross-project-boundary.md` (multiple references)
- Modify: `~/projects/hapaxromana/docs/document-registry.yaml` (repo entry)

**Step 1: Find all references**

```bash
grep -rn "hapax-containerization" ~/projects/hapaxromana/ --include="*.md" --include="*.yaml" --include="*.yml"
```

**Step 2: Update hapaxromana/CLAUDE.md**

Find the line:
```
| `~/projects/hapax-containerization/` | Management cockpit demo seed system. ...
```
Replace with:
```
| `~/projects/hapax-mgmt/` | Management cockpit demo seed system. ...
```

**Step 3: Update hapaxromana/docs/cross-project-boundary.md**

Replace all occurrences of `hapax-containerization` with `hapax-mgmt`.

**Step 4: Update hapaxromana/docs/document-registry.yaml**

Replace the repo key and path:
```yaml
  hapax-mgmt:
    path: ~/projects/hapax-mgmt
```

And update any file paths referencing `hapax-containerization`.

**Step 5: Check for references in hapaxromana/docs/plans/**

```bash
grep -rn "hapax-containerization" ~/projects/hapaxromana/docs/plans/
```

These are historical plan documents — update them too for consistency, or leave them as historical records. Prefer updating since they're referenced by drift-detector.

**Step 6: Commit in hapaxromana**

```bash
cd ~/projects/hapaxromana
git add -A
git commit -m "refactor: update hapax-containerization → hapax-mgmt references

Reflects rename of the management cockpit demo seed repo."
```

---

### Task 4: Update Claude Code memory and project mapping

**Context:** Claude Code's auto-memory directory is keyed to the project path. After renaming, the old memory path is stale and a new one will be created automatically. The old memory content should be migrated.

**Files:**
- Read: `~/.claude/projects/-home-user-projects-hapax-containerization/memory/MEMORY.md`
- Create: `~/.claude/projects/-home-user-projects-hapax-mgmt/memory/MEMORY.md`

**Step 1: Check if Claude auto-creates the directory**

```bash
ls ~/.claude/projects/ | grep hapax
```

**Step 2: Copy memory files to new project path**

```bash
mkdir -p ~/.claude/projects/-home-user-projects-hapax-mgmt/memory/
cp ~/.claude/projects/-home-user-projects-hapax-containerization/memory/* \
   ~/.claude/projects/-home-user-projects-hapax-mgmt/memory/
```

**Step 3: Update the memory file contents**

Open `~/.claude/projects/-home-user-projects-hapax-mgmt/memory/MEMORY.md` and replace references to `hapax-containerization` with `hapax-mgmt`.

No git commit needed — this is Claude Code internal state, not repo content.

---

## Phase 2: ai-agents Containerization

### Task 5: Add dependency groups to ai-agents pyproject.toml

**Context:** The current `pyproject.toml` in `~/projects/ai-agents/ ` has a single flat dependency list (~50 packages including heavy audio/video/vision deps). Container images should only install what they need. We'll add dependency groups so Dockerfiles can install subsets.

**Files:**
- Modify: `~/projects/pyproject.toml`

**Step 1: Read current pyproject.toml**

```bash
cat ~/projects/pyproject.toml
```

**Step 2: Restructure dependencies into groups**

Keep the base `dependencies` list minimal (shared by all deployables), then add optional dependency groups. The structure:

```toml
[project]
dependencies = [
    # Core — needed by everything
    "pydantic>=2.12.5",
    "pyyaml>=6.0",
    "httpx>=0.28.0",
    "qdrant-client>=1.17.0",
    "ollama>=0.6.1",
    "langfuse>=3.14.5",
    "jinja2>=3.1",
]

[project.optional-dependencies]
logos-api = [
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "pydantic-ai[litellm]>=1.63.0",
    "sse-starlette>=2.0.0",
    "watchdog>=6.0.0",
]
sync-pipeline = [
    "google-api-python-client>=2.100.0",
    "google-auth-oauthlib>=1.2.0",
    "faster-whisper>=1.1.0",
    "silero-vad>=5.1",
    "soundfile>=0.13.0",
    "torchaudio>=2.0.0",
]
host = [
    # Only needed on host (not in containers)
    "pydantic-ai[litellm]>=1.63.0",
    "playwright>=1.49.0",
    "moviepy>=2.0.0",
    "pillow>=11.0.0",
    "matplotlib>=3.9",
    "kokoro>=0.9.0",
    "piper-tts>=1.2.0",
    "pyaudio>=0.2.14",
    "google-genai>=1.0.0",
    "mediapipe>=0.10.0",
    "opencv-python-headless>=4.10.0",
    "pipecat-ai[silero,openai]>=0.0.50",
    "pyannote-audio>=3.3.0",
    "panns-inference>=0.1.1",
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "sse-starlette>=2.0.0",
    "watchdog>=6.0.0",
    "google-api-python-client>=2.100.0",
    "google-auth-oauthlib>=1.2.0",
    "faster-whisper>=1.1.0",
    "silero-vad>=5.1",
    "soundfile>=0.13.0",
    "torchaudio>=2.0.0",
]
```

The `host` group includes everything — it's what `uv sync --all-extras` installs on the development machine. The logos-api and sync-pipeline groups are for Docker builds.

**Important:** `uv sync` on host should still install everything. Verify:

```bash
cd ~/projects/ai-agents
uv sync --all-extras
uv run pytest tests/ -q --tb=short
```

**Step 3: Verify tests still pass**

```bash
cd ~/projects/ai-agents
uv run pytest tests/ -q
```

Expected: All tests pass (1524+).

**Step 4: Commit**

```bash
cd ~/projects/ai-agents
git add pyproject.toml uv.lock
git commit -m "refactor: split dependencies into groups for container builds

logos-api, sync-pipeline, and host groups allow Dockerfiles
to install only what they need."
```

---

### Task 6: Create Dockerfile.logos-api in ai-agents

**Context:** This Dockerfile builds the logos API image. It's based on the existing Dockerfile in `hapax-containerization/Dockerfile` but simplified — no Playwright, no d2, no Node.js (those were for the demo agent). Uses the `logos-api` dependency group.

**Files:**
- Create: `~/projects/Dockerfile.logos-api`

**Step 1: Write the Dockerfile**

```dockerfile
# ============================================================================
# logos-api — FastAPI management logos API server
# ============================================================================

# ── Stage 1: Build ──────────────────────────────────────────────────────
FROM python:3.12-slim AS build

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --extra logos-api

# ── Stage 2: Runtime ────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python venv from build stage
COPY --from=build /app/.venv /app/.venv

# Copy application code
COPY agents/ agents/
COPY cockpit/ cockpit/
COPY shared/ shared/
COPY pyproject.toml uv.lock README.md ./

# Create data and profiles directories
RUN mkdir -p /app/data /app/profiles

# Non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8050/ || exit 1

CMD ["uv", "run", "python", "-m", "cockpit.api", "--host", "0.0.0.0", "--port", "8050"]
```

**Step 2: Build and verify**

```bash
cd ~/projects/ai-agents
docker build -f Dockerfile.logos-api -t logos-api:test .
```

Expected: Build succeeds. Image should be significantly smaller than the current all-in-one image (no Playwright, Node.js, d2, Chromium).

**Step 3: Smoke test**

```bash
docker run --rm -p 127.0.0.1:8050:8050 \
    -e QDRANT_URL=http://host.docker.internal:6333 \
    -e LITELLM_BASE_URL=http://host.docker.internal:4000 \
    logos-api:test
```

In another terminal:
```bash
curl -s http://localhost:8050/ | head -5
# Should return JSON or HTML indicating the API is running
```

Stop the container with Ctrl+C.

**Step 4: Commit**

```bash
cd ~/projects/ai-agents
git add Dockerfile.logos-api
git commit -m "feat: add Dockerfile.logos-api for containerized API server

Multi-stage build using logos-api dependency group.
No Playwright, Node, or demo dependencies — minimal image."
```

---

### Task 7: Create sync-pipeline crontab and entrypoint

**Context:** The sync-pipeline container runs 8 agents on cron schedules, replacing 8 systemd timers. It needs a crontab file and an entrypoint script. The entrypoint must support cycle-mode switching (dev vs prod schedules).

**Files:**
- Create: `~/projects/ai-agents/ sync-pipeline/crontab.prod`
- Create: `~/projects/ai-agents/ sync-pipeline/crontab.dev`
- Create: `~/projects/ai-agents/ sync-pipeline/entrypoint.sh`

**Step 1: Create the sync-pipeline directory**

```bash
mkdir -p ~/projects/ai-agents/ sync-pipeline
```

**Step 2: Write the production crontab**

`~/projects/ai-agents/ sync-pipeline/crontab.prod`:

```cron
# Sync pipeline — production schedule
# Logs go to stdout via the wrapper script

# Google Calendar — every 30 minutes
*/30 * * * * /app/sync-pipeline/run-agent.sh gcalendar_sync --auto
# Obsidian vault — every 30 minutes
*/30 * * * * /app/sync-pipeline/run-agent.sh obsidian_sync --auto
# Gmail — every hour
0 * * * * /app/sync-pipeline/run-agent.sh gmail_sync --auto
# Chrome — every hour
15 * * * * /app/sync-pipeline/run-agent.sh chrome_sync --auto
# Google Drive — every 2 hours
0 */2 * * * /app/sync-pipeline/run-agent.sh gdrive_sync --auto
# Claude Code transcripts — every 2 hours
30 */2 * * * /app/sync-pipeline/run-agent.sh claude_code_sync --auto
# Audio processor — every 30 minutes
*/30 * * * * /app/sync-pipeline/run-agent.sh audio_processor --process
# YouTube — every 6 hours
0 */6 * * * /app/sync-pipeline/run-agent.sh youtube_sync --auto
```

**Step 3: Write the dev crontab (reduced frequency)**

`~/projects/ai-agents/ sync-pipeline/crontab.dev`:

```cron
# Sync pipeline — dev schedule (reduced frequency)

# Google Calendar — every 2 hours
0 */2 * * * /app/sync-pipeline/run-agent.sh gcalendar_sync --auto
# Obsidian vault — every 2 hours
30 */2 * * * /app/sync-pipeline/run-agent.sh obsidian_sync --auto
# Gmail — every 4 hours
0 */4 * * * /app/sync-pipeline/run-agent.sh gmail_sync --auto
# Chrome — every 4 hours
15 */4 * * * /app/sync-pipeline/run-agent.sh chrome_sync --auto
# Google Drive — every 6 hours
0 */6 * * * /app/sync-pipeline/run-agent.sh gdrive_sync --auto
# Claude Code transcripts — every 6 hours
30 */6 * * * /app/sync-pipeline/run-agent.sh claude_code_sync --auto
# Audio processor — every 2 hours
0 */2 * * * /app/sync-pipeline/run-agent.sh audio_processor --process
# YouTube — every 12 hours
0 */12 * * * /app/sync-pipeline/run-agent.sh youtube_sync --auto
```

**Step 4: Write the agent runner wrapper**

`~/projects/ai-agents/ sync-pipeline/run-agent.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Run an agent and log output to stdout with timestamps.
# Usage: run-agent.sh <agent_module> [flags...]

AGENT="$1"
shift

echo "[$(date -Iseconds)] sync-pipeline: starting ${AGENT}"
cd /app
/app/.venv/bin/python -m "agents.${AGENT}" "$@" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date -Iseconds)] sync-pipeline: ${AGENT} completed successfully"
else
    echo "[$(date -Iseconds)] sync-pipeline: ${AGENT} FAILED (exit ${EXIT_CODE})" >&2
fi

exit $EXIT_CODE
```

**Step 5: Write the entrypoint**

`~/projects/ai-agents/ sync-pipeline/entrypoint.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

CYCLE_MODE="${CYCLE_MODE:-prod}"
CRONTAB_FILE="/app/sync-pipeline/crontab.${CYCLE_MODE}"

if [ ! -f "$CRONTAB_FILE" ]; then
    echo "entrypoint: ERROR — no crontab for cycle mode '${CYCLE_MODE}'" >&2
    echo "entrypoint: expected ${CRONTAB_FILE}" >&2
    exit 1
fi

echo "entrypoint: sync-pipeline starting in '${CYCLE_MODE}' mode"
echo "entrypoint: installing crontab from ${CRONTAB_FILE}"

# Install crontab for the appuser
crontab "$CRONTAB_FILE"

echo "entrypoint: cron schedule:"
crontab -l

# Run cron in foreground
echo "entrypoint: starting crond..."
exec cron -f
```

**Step 6: Make scripts executable**

```bash
chmod +x ~/projects/ai-agents/ sync-pipeline/entrypoint.sh
chmod +x ~/projects/ai-agents/ sync-pipeline/run-agent.sh
```

**Step 7: Commit**

```bash
cd ~/projects/ai-agents
git add sync-pipeline/
git commit -m "feat: add sync-pipeline crontab and entrypoint

Production and dev schedules for 8 RAG sync agents.
Entrypoint selects crontab based on CYCLE_MODE env var."
```

---

### Task 8: Create Dockerfile.sync-pipeline in ai-agents

**Context:** This Dockerfile builds the sync-pipeline image. It needs ffmpeg (for audio_processor), the sync-pipeline dependency group, and cron.

**Files:**
- Create: `~/projects/Dockerfile.sync-pipeline`

**Step 1: Write the Dockerfile**

```dockerfile
# ============================================================================
# sync-pipeline — RAG sync agents on cron schedule
# Replaces 8 systemd timers with a single container
# ============================================================================

# ── Stage 1: Build ──────────────────────────────────────────────────────
FROM python:3.12-slim AS build

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --extra sync-pipeline

# ── Stage 2: Runtime ────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# System dependencies: cron, ffmpeg (audio_processor), curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
        cron \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python venv from build stage
COPY --from=build /app/.venv /app/.venv

# Copy application code
COPY agents/ agents/
COPY shared/ shared/
COPY pyproject.toml uv.lock README.md ./

# Copy sync-pipeline config
COPY sync-pipeline/ sync-pipeline/
RUN chmod +x sync-pipeline/entrypoint.sh sync-pipeline/run-agent.sh

# Create data directory
RUN mkdir -p /app/data /app/profiles

# Non-root user — note: cron on Debian needs root to install crontab,
# so entrypoint runs as root, installs crontab, then cron runs jobs as appuser
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser && \
    chown -R appuser:appuser /app

ENV CYCLE_MODE=prod

HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
    CMD pgrep cron > /dev/null || exit 1

ENTRYPOINT ["/app/sync-pipeline/entrypoint.sh"]
```

**Step 2: Build and verify**

```bash
cd ~/projects/ai-agents
docker build -f Dockerfile.sync-pipeline -t sync-pipeline:test .
```

Expected: Build succeeds.

**Step 3: Smoke test (verify cron starts)**

```bash
docker run --rm -e CYCLE_MODE=prod sync-pipeline:test &
sleep 3
# Should see entrypoint log messages about crontab installation
docker stop $(docker ps -q --filter ancestor=sync-pipeline:test)
```

**Step 4: Commit**

```bash
cd ~/projects/ai-agents
git add Dockerfile.sync-pipeline
git commit -m "feat: add Dockerfile.sync-pipeline for containerized RAG sync

Replaces 8 systemd timers with one container running cron.
Includes ffmpeg for audio_processor. Cycle mode via CYCLE_MODE env."
```

---

### Task 9: Create docker-compose.yml in ai-agents

**Context:** This compose file wires together logos-api, sync-pipeline, and cockpit-web. It connects to the existing llm-stack services (Qdrant, LiteLLM, Ollama) running on the host.

**Files:**
- Create: `~/projects/ai-agents/ docker-compose.yml`

**Step 1: Write the compose file**

```yaml
# ============================================================================
# Hapax Agent Services
# Runs alongside ~/llm-stack/docker-compose.yml (infrastructure)
# ============================================================================

services:
  logos-api:
    build:
      context: .
      dockerfile: Dockerfile.logos-api
    container_name: hapax-logos-api
    ports:
      - "127.0.0.1:8050:8050"
    volumes:
      - ./data:/app/data
      - ./profiles:/app/profiles
    environment:
      - QDRANT_URL=http://host.docker.internal:6333
      - LITELLM_BASE_URL=http://host.docker.internal:4000
      - LITELLM_API_KEY=${LITELLM_API_KEY:-changeme}
      - OLLAMA_URL=http://host.docker.internal:11434
      - ENGINE_ENABLED=${ENGINE_ENABLED:-true}
    restart: unless-stopped

  sync-pipeline:
    build:
      context: .
      dockerfile: Dockerfile.sync-pipeline
    container_name: hapax-sync-pipeline
    volumes:
      - ./data:/app/data
      - ./profiles:/app/profiles
      # Filesystem-coupled agent mounts (read-only)
      - ${GOOGLE_TOKEN_PATH:-~/.config/hapax/google-token.json}:/app/secrets/google-token.json:ro
      - ${VAULT_PERSONAL:-data/}:/mnt/vault-personal:ro
      - ${VAULT_WORK:-data/}:/mnt/vault-work:ro
      - ${CLAUDE_DIR:-~/.claude}:/mnt/claude:ro
      - ${CHROME_DIR:-~/.config/google-chrome}:/mnt/chrome:ro
      - ${AUDIO_DIR:-~/recordings}:/mnt/audio:ro
    environment:
      - QDRANT_URL=http://host.docker.internal:6333
      - LITELLM_BASE_URL=http://host.docker.internal:4000
      - LITELLM_API_KEY=${LITELLM_API_KEY:-changeme}
      - OLLAMA_URL=http://host.docker.internal:11434
      - CYCLE_MODE=${CYCLE_MODE:-prod}
      # Google OAuth paths inside container
      - GOOGLE_TOKEN_PATH=/app/secrets/google-token.json
      # Vault paths inside container
      - VAULT_PERSONAL=/mnt/vault-personal
      - VAULT_WORK=/mnt/vault-work
      - CLAUDE_TRANSCRIPT_DIR=/mnt/claude
      - CHROME_PROFILE_DIR=/mnt/chrome
      - AUDIO_SOURCE_DIR=/mnt/audio
    restart: unless-stopped

  cockpit-web:
    build:
      context: ${COCKPIT_WEB_DIR:-../cockpit-web}
    container_name: hapax-cockpit-web
    ports:
      - "127.0.0.1:8052:80"
    restart: unless-stopped
```

**Step 2: Create a .env.example**

```bash
cat > ~/projects/ai-agents/ .env.example << 'EOF'
# Hapax Agent Services — environment variables
# Copy to .env and adjust paths as needed

LITELLM_API_KEY=changeme
CYCLE_MODE=prod

# Sync pipeline volume mounts (defaults work for standard install)
# GOOGLE_TOKEN_PATH=~/.config/hapax/google-token.json
# VAULT_PERSONAL=data/
# VAULT_WORK=data/
# CLAUDE_DIR=~/.claude
# CHROME_DIR=~/.config/google-chrome
# AUDIO_DIR=~/recordings

# cockpit-web build context (relative to this compose file)
# COCKPIT_WEB_DIR=../cockpit-web
EOF
```

**Step 3: Verify compose config parses**

```bash
cd ~/projects/ai-agents
docker compose config --quiet
```

Expected: No errors.

**Step 4: Commit**

```bash
cd ~/projects/ai-agents
git add docker-compose.yml .env.example
git commit -m "feat: add docker-compose.yml for agent services

Wires logos-api, sync-pipeline, and cockpit-web.
Connects to llm-stack infrastructure on host."
```

---

### Task 10: Test full compose stack

**Context:** Build all images and verify they start correctly together. This is an integration test — all three services should come up and the logos-api should respond to requests.

**Step 1: Build all images**

```bash
cd ~/projects/ai-agents
docker compose build
```

Expected: All three services build successfully.

**Step 2: Start the stack**

```bash
cd ~/projects/ai-agents
docker compose up -d
```

**Step 3: Verify services are running**

```bash
docker compose ps
# All three should show "Up" status

# Logos API health
curl -s http://localhost:8050/ | head -5

# Cockpit web
curl -s -o /dev/null -w "%{http_code}" http://localhost:8052/

# Sync pipeline cron
docker compose logs sync-pipeline | head -10
# Should show entrypoint messages about crontab installation
```

**Step 4: Stop the stack**

```bash
docker compose down
```

No commit needed — this is verification only.

---

## Phase 3: hapax-mgmt Thinning

### Task 11: Remove duplicated Python from hapax-mgmt

**Context:** `hapax-mgmt` (formerly hapax-containerization) currently contains full copies of `agents/`, `shared/`, `cockpit/`, `tests/`, `pyproject.toml`, and `uv.lock` inside its the ai-agents/ subdirectory. Now that ai-agents has its own Dockerfiles, this duplication is no longer needed. hapax-mgmt should retain only demo-specific content.

**Files:**
- Delete: `~/projects/hapax-mgmt/agents/`
- Delete: `~/projects/hapax-mgmt/shared/`
- Delete: `~/projects/hapax-mgmt/cockpit/`
- Delete: `~/projects/hapax-mgmt/tests/`
- Delete: `~/projects/hapax-mgmt/pyproject.toml`
- Delete: `~/projects/hapax-mgmt/ai-agents/ uv.lock`
- Delete: `~/projects/hapax-mgmt/Dockerfile`
- Delete: `~/projects/hapax-mgmt/entrypoint.sh`
- Delete: `~/projects/hapax-mgmt/ai-agents/ README.md`
- Keep: `~/projects/hapax-mgmt/demo-data/`
- Keep: `~/projects/hapax-mgmt/scripts/`
- Keep: `~/projects/hapax-mgmt/data/` (gitignored runtime data)
- Keep: `~/projects/hapax-mgmt/profiles/` (gitignored runtime data)

**Step 1: Inventory what's in hapax-mgmt/ai-agents/ **

```bash
ls ~/projects/hapax-mgmt/ai-agents/ 
```

**Step 2: Remove duplicated code directories**

```bash
cd ~/projects/hapax-mgmt
rm -rf ai-agents/ agents ai-agents/ shared ai-agents/ cockpit tests
rm -f pyproject.toml ai-agents/ uv.lock ai-agents/ README.md
rm -f Dockerfile entrypoint.sh
rm -f ai-agents/ promptfooconfig.yaml
rm -rf ai-agents/ n8n-workflows ai-agents/ systemd
```

**Step 3: Verify what remains**

```bash
ls -la ~/projects/hapax-mgmt/ai-agents/ 
# Should show only: demo-data/, scripts/, data/, profiles/, CLAUDE.md, docs/
```

**Step 4: Restructure — move demo-data and scripts to repo root**

The the ai-agents/ subdirectory no longer makes sense as an organizational layer. Move the remaining content up:

```bash
cd ~/projects/hapax-mgmt
mv ai-agents/ demo-data ./demo-data
mv ai-agents/ scripts ./scripts
mv ai-agents/ data ./data 2>/dev/null || true
mv profiles ./profiles 2>/dev/null || true
# Keep CLAUDE.md content — merge into root CLAUDE.md or delete
rm -rf ai-agents/ 
```

**Step 5: Update .gitignore**

Ensure `data/` and `profiles/` contents remain gitignored at the new paths.

**Step 6: Commit**

```bash
cd ~/projects/hapax-mgmt
git add -A
git commit -m "refactor: remove duplicated Python code from hapax-mgmt

hapax-mgmt is now a thin orchestration layer:
- demo-data/ — synthetic seed corpus
- scripts/ — bootstrap and demo scripts
- docker-compose.yml — demo compose referencing ai-agents images
No more duplicated agents, shared modules, or cockpit code."
```

---

### Task 12: Create demo compose in hapax-mgmt

**Context:** hapax-mgmt needs a docker-compose.yml that references images built from ai-agents (not local code). This compose file is demo-specific — it may override environment variables, set up demo-data volumes, etc.

**Files:**
- Create: `~/projects/hapax-mgmt/docker-compose.yml`
- Delete: `~/projects/hapax-mgmt/llm-stack/` (if it exists — was a reference copy)

**Step 1: Remove old reference copies**

```bash
cd ~/projects/hapax-mgmt
rm -rf llm-stack/ hapax-mgmt-web/ hapax-system/ vscode/ claude-config/
rm -rf axioms/ domains/ knowledge/ research/
rm -f agent-architecture.md operations-manual.md Dockerfile.dev entrypoint-dev.sh
```

**Step 2: Write the demo compose**

```yaml
# ============================================================================
# hapax-mgmt — Management Cockpit Demo Seed
#
# Requires: ai-agents images built first
#   cd ~/projects/ai-agents && docker compose build
#
# Usage:
#   ./scripts/bootstrap-demo.sh   # Hydrate demo data
#   docker compose up -d           # Start demo stack
# ============================================================================

services:
  logos-api:
    image: hapax-logos-api:latest
    container_name: hapax-mgmt-logos-api
    ports:
      - "127.0.0.1:8060:8050"
    volumes:
      - ./data:/app/data
      - ./profiles:/app/profiles
    environment:
      - QDRANT_URL=http://host.docker.internal:6333
      - LITELLM_BASE_URL=http://host.docker.internal:4000
      - LITELLM_API_KEY=${LITELLM_API_KEY:-changeme}
      - OLLAMA_URL=http://host.docker.internal:11434
      - ENGINE_ENABLED=false  # Demo doesn't need reactive engine
    restart: unless-stopped

  cockpit-web:
    image: hapax-cockpit-web:latest
    container_name: hapax-mgmt-cockpit-web
    ports:
      - "127.0.0.1:8062:80"
    restart: unless-stopped
```

Note: demo uses different ports (8060/8062) to avoid conflicting with production (8050/8052).

**Step 3: Update bootstrap-demo.sh**

Read and update `~/projects/hapax-mgmt/scripts/bootstrap-demo.sh` to:
1. Copy `demo-data/` to `data/` (was `demo-data/` to `data/`)
2. Run agents via `docker compose run logos-api uv run python -m agents.<name>` instead of local `uv run`
3. Adjust paths for the new flat structure

This script needs careful updating — read it first, understand the current flow, then adapt paths.

**Step 4: Commit**

```bash
cd ~/projects/hapax-mgmt
git add -A
git commit -m "feat: add demo compose referencing ai-agents images

Demo stack on ports 8060/8062 to avoid production conflict.
Bootstrap script updated for new flat repo structure."
```

---

### Task 13: Update hapax-mgmt CLAUDE.md

**Context:** CLAUDE.md needs to reflect the new structure — no more duplicated code, just demo orchestration.

**Files:**
- Modify: `~/projects/hapax-mgmt/CLAUDE.md`

**Step 1: Rewrite CLAUDE.md**

The new CLAUDE.md should describe:
- What hapax-mgmt is (management cockpit demo seed system)
- The new structure (demo-data/, scripts/, docker-compose.yml)
- How to build (requires ai-agents images)
- How to run (bootstrap-demo.sh → docker compose up)
- Relationship to ai-agents (source of truth for all Python code)

Keep it concise. Remove all references to agents, shared modules, logos API internals — those are documented in CLAUDE.md.

**Step 2: Commit**

```bash
cd ~/projects/hapax-mgmt
git add CLAUDE.md
git commit -m "docs: rewrite CLAUDE.md for thin demo orchestration layer"
```

---

### Task 14: Verify demo hydration end-to-end

**Context:** The demo bootstrap pipeline must work with the new structure. This is a manual integration test.

**Step 1: Build ai-agents images**

```bash
cd ~/projects/ai-agents
docker compose build logos-api
# Tag for demo compose
docker tag hapax-logos-api:latest hapax-logos-api:latest
```

**Step 2: Build cockpit-web image**

```bash
cd ~/projects/cockpit-web
docker build -t hapax-cockpit-web:latest .
```

**Step 3: Run bootstrap**

```bash
cd ~/projects/hapax-mgmt
./scripts/bootstrap-demo.sh --skip-llm
```

Expected: Demo data copied to `data/`, deterministic agents run, basic validation passes.

**Step 4: Start demo stack**

```bash
cd ~/projects/hapax-mgmt
docker compose up -d
```

**Step 5: Verify**

```bash
# API responds with management data
curl -s http://localhost:8060/api/management | python3 -m json.tool | head -20

# Web UI loads
curl -s -o /dev/null -w "%{http_code}" http://localhost:8062/

# Nudges present
curl -s http://localhost:8060/api/nudges | python3 -m json.tool | head -20
```

**Step 6: Stop demo stack**

```bash
cd ~/projects/hapax-mgmt
docker compose down
```

No commit needed — this is verification only.

---

## Phase 4: Systemd Timer Migration

### Task 15: Document current systemd timer state

**Context:** Before disabling timers, capture their current state for rollback reference. This phase is reversible — if the container fails, timers can be re-enabled.

**Step 1: Capture current timer state**

```bash
# List all hapax-related timers
systemctl --user list-timers | grep -E "gdrive|gcalendar|gmail|youtube|claude-code|obsidian|chrome|audio"

# Save state for rollback
systemctl --user list-timers --all > ~/backups/systemd-timers-before-migration.txt
```

**Step 2: Verify sync agents are currently running via timers**

```bash
# Check last run times
for timer in gdrive-sync gcalendar-sync gmail-sync youtube-sync claude-code-sync obsidian-sync chrome-sync audio-processor; do
    echo "=== $timer ==="
    systemctl --user status "$timer.timer" 2>/dev/null | head -5
done
```

No commit needed — this is documentation only.

---

### Task 16: Start sync-pipeline container and disable timers

**Context:** Start the containerized sync pipeline, then disable the corresponding systemd timers. Keep the timer unit files for rollback — just stop and disable them.

**Step 1: Start the sync-pipeline container**

```bash
cd ~/projects/ai-agents
docker compose up -d sync-pipeline
```

**Step 2: Verify cron is running**

```bash
docker compose logs sync-pipeline
# Should show crontab installation and crond startup
```

**Step 3: Disable systemd timers (one at a time, reversible)**

```bash
for timer in gdrive-sync gcalendar-sync gmail-sync youtube-sync claude-code-sync obsidian-sync chrome-sync audio-processor; do
    echo "Disabling $timer..."
    systemctl --user stop "$timer.timer" 2>/dev/null || true
    systemctl --user disable "$timer.timer" 2>/dev/null || true
done
```

**Step 4: Verify timers are disabled**

```bash
systemctl --user list-timers | grep -E "gdrive|gcalendar|gmail|youtube|claude-code|obsidian|chrome|audio"
# Should return empty (no active timers for these)
```

**Step 5: Monitor for first cron execution**

```bash
# Wait for the first 30-minute cron jobs to fire
docker compose logs -f sync-pipeline
# After ~30 minutes, should see gcalendar_sync and obsidian_sync run
```

No commit needed — this is operational, not code.

---

### Task 17: Monitor and validate (48h observation)

**Context:** Run the sync-pipeline container for 48 hours and verify all 8 agents execute successfully at their scheduled times.

**Step 1: Check logs after 24h**

```bash
cd ~/projects/ai-agents
docker compose logs sync-pipeline --since 24h | grep -E "starting|completed|FAILED"
```

Expected: All 8 agents should have run at least once. No FAILED entries.

**Step 2: Verify Qdrant collections were updated**

```bash
# Check document counts in Qdrant
for coll in documents claude-memory; do
    echo "=== $coll ==="
    curl -s http://localhost:6333/collections/$coll | python3 -m json.tool | grep points_count
done
```

**Step 3: Compare with pre-migration state**

Verify Qdrant point counts are growing (sync is working) and not stale (sync has stopped).

**Step 4: If all good after 48h, clean up systemd units**

```bash
# Remove the now-unnecessary timer and service files
# (Only if migration is confirmed working)
cd ~/projects/ai-agents
# These files are in systemd/units/ — note them for the commit
```

**Step 5: Commit cleanup if applicable**

```bash
cd ~/projects/ai-agents
git add -A
git commit -m "chore: remove sync-related systemd timer units

These timers are replaced by the sync-pipeline container.
Remaining timers (health-monitor, briefing, etc.) stay on host."
```

---

## Rollback Procedures

### If sync-pipeline container fails

```bash
# Re-enable systemd timers
for timer in gdrive-sync gcalendar-sync gmail-sync youtube-sync claude-code-sync obsidian-sync chrome-sync audio-processor; do
    systemctl --user enable --now "$timer.timer"
done

# Stop the container
cd ~/projects/ai-agents
docker compose stop sync-pipeline
```

### If rename breaks Claude Code memory

```bash
# Copy memory back
cp ~/.claude/projects/-home-user-projects-hapax-mgmt/memory/* \
   ~/.claude/projects/-home-user-projects-hapax-containerization/memory/
# Rename back
mv ~/projects/hapax-mgmt ~/projects/hapax-containerization
```
