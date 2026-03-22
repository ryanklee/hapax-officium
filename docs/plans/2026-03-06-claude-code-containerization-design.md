# Claude Code Containerization Design

## Goal

Package Claude Code with all Hapax customizations into a container image (`hapax-dev`) so that the entire development environment — agents, cockpit, and Claude Code with its skills, hooks, agents, rules, and MCP servers — is portable and reproducible from a single `docker compose` invocation.

## Why

The Hapax system has accumulated significant Claude Code customization:

- **11 custom skills** (slash commands): `/status`, `/briefing`, `/axiom-check`, `/axiom-review`, `/axiom-sweep`, `/deploy-check`, `/weekly-review`, `/vram`, `/ingest`, `/studio`, `/demo`
- **3 custom agents**: operator-voice (decision feedback), infra-check (infrastructure verification), convention-guard (convention compliance)
- **5 hook scripts**: axiom scan (PreToolUse), axiom commit scan (PreToolUse/Bash), axiom audit trail (PostToolUse), session context injection (SessionStart), session summary (Stop)
- **2 custom rules**: axioms.md, system-context.md
- **4 global rules**: environment, toolchain, models, music-production
- **MCP servers**: qdrant, docker, git, postgres, desktop-commander, midi, midi-files
- **Plugin ecosystem**: superpowers, compound-engineering, gemini-tools, code-review, and ~20 more enabled plugins

All of this currently lives across `~/.claude/`, `~/projects/hapax-system/`, and global rules files, symlinked together by `hapax-system/install.sh`. None of it is version-controlled with the containerization project. If the host machine dies, rebuilding this environment requires manual reconstruction.

## Architecture

### Third image: `hapax-dev`

```
hapax-agents (runtime)     — agents + logos API, runs headless
hapax-ingest (runtime)     — RAG ingestion, runs headless
hapax-dev    (interactive) — Claude Code + full Hapax customization, interactive terminal
```

`hapax-dev` is NOT based on `hapax-agents`. It's a separate image optimized for interactive development, not headless agent execution. It shares the same Python codebase but adds Claude Code and its configuration layer.

### Image contents

```
hapax-dev/
├── Claude Code CLI (@anthropic-ai/claude-code via npm)
├── Node.js 22 + pnpm
├── Python 3.12 + uv
├── System tools (git, curl, jq, rg, d2, make)
├── /home/operator/.claude/
│   ├── settings.json          (hooks, enabled plugins, permissions)
│   ├── mcp_servers.json       (adapted for container networking)
│   ├── commands/              (skill markdown files, copied not symlinked)
│   ├── agents/                (custom agent definitions)
│   └── rules/                 (all rule files)
├── /app/hapax-system/
│   └── hooks/scripts/         (hook scripts, adapted for container paths)
├── /app/ai-agents/             (full agent codebase)
│   ├── agents/
│   ├── logos/
│   ├── shared/
│   └── ...
└── /app/axioms/               (axiom registry from hapaxromana)
```

### What runs inside the container

```
User terminal
  └─> docker compose run hapax-dev
        └─> claude (Claude Code CLI)
              ├─> MCP: qdrant (connects to qdrant container)
              ├─> MCP: git (operates on mounted project)
              ├─> MCP: postgres (connects to postgres container)
              ├─> MCP: filesystem, sequential-thinking, memory, context7, tavily
              ├─> Hooks: axiom-scan, axiom-audit, session-context, etc.
              ├─> Skills: /status, /briefing, /axiom-check, etc.
              └─> Agents: operator-voice, infra-check, convention-guard
```

### What does NOT go in the container

| Component | Why excluded |
|-----------|-------------|
| Docker MCP server | Would require Docker-in-Docker or socket mounting; agents container handles runtime |
| desktop-commander MCP | No desktop environment in container |
| midi / midi-files MCP | No MIDI hardware accessible |
| `/studio` skill | Checks ALSA/MIDI hardware |
| GPU-specific checks in `/vram` | No nvidia-smi; could be adapted to query Ollama API |
| Playwright browsers | Too heavy for dev image; available in hapax-agents if needed |

## Component Adaptation

### hapax-system inclusion

The `hapax-system` repo (currently at `~/projects/hapax-system/`) is pulled into this repository as a tracked directory at `hapax-system/`. Not a git submodule — a direct copy that becomes canonical here, same as ai-agents.

```
hapax-containerization/
├── ai-agents/            (already here)
├── hapax-system/        (NEW — pulled from ~/projects/hapax-system/)
│   ├── hooks/scripts/
│   ├── skills/
│   ├── agents/
│   ├── rules/
│   ├── install.sh       (adapted for container paths)
│   └── README.md
```

### Hook script adaptation

All hooks currently use `$HOME/projects/ai-agents` and `$HOME/.cache/axiom-audit`. In the container:

| Variable | Host value | Container value |
|----------|-----------|-----------------|
| `$HOME` | `~` | `/home/hapax` |
| agents dir | `$HOME/projects/ai-agents` | `/app/ai-agents` |
| audit dir | `$HOME/.cache/axiom-audit` | `/data/.cache/axiom-audit` (volume) |
| health history | `$HOME/projects/profiles/health-history.jsonl` | `/app/profiles/health-history.jsonl` (volume) |

Adaptation strategy: Introduce env vars at the top of each script with sensible container defaults:

```bash
HAPAX_AGENTS_DIR="${HAPAX_AGENTS_DIR:-/app/ai-agents}"
HAPAX_AUDIT_DIR="${HAPAX_AUDIT_DIR:-/data/.cache/axiom-audit}"
```

**session-context.sh** changes:
- Axiom loading: use `$HAPAX_AGENTS_DIR` instead of `$HOME/projects/ai-agents`
- Health history: use `$HAPAX_AGENTS_DIR/profiles/health-history.jsonl`
- Docker container count: skip (or query via API if Docker socket mounted)
- GPU status: skip (or query Ollama API for loaded models)
- Axiom pending precedents: use `$HAPAX_AUDIT_DIR` parent for cockpit state

**axiom-scan.sh** and **axiom-commit-scan.sh**: No path changes needed — they operate on stdin (piped tool input) and `git diff` in the current directory. Only need `axiom-patterns.sh` accessible, which it is via `SCRIPT_DIR`.

**axiom-audit.sh** changes:
- `AUDIT_DIR` uses `$HAPAX_AUDIT_DIR` env var
- `aichat` for cross-file check: use `$LITELLM_API_BASE` or skip if no local model available

**session-summary.sh**: Use `$HAPAX_AUDIT_DIR`.

### Skill adaptation

| Skill | Adaptation needed |
|-------|------------------|
| `/status` | Change path: `cd /app/ai-agents && uv run python -m agents.health_monitor` |
| `/briefing` | Change path + use env vars for API keys |
| `/axiom-check` | Change path to `/app/ai-agents` |
| `/axiom-review` | Change path |
| `/axiom-sweep` | Change paths to scan `/app/ai-agents` |
| `/deploy-check` | Change path; tests + health + axiom scan |
| `/weekly-review` | Change path |
| `/ingest` | Use `QDRANT_URL` env var; skip systemd check |
| `/vram` | Rewrite: query `OLLAMA_URL/api/ps` instead of nvidia-smi |
| `/studio` | Exclude or stub (no MIDI hardware) |

### MCP server adaptation

**Keep (adapted):**

| Server | Adaptation |
|--------|-----------|
| qdrant | `QDRANT_URL` → `http://qdrant:6333` (container network) |
| git | Works as-is on mounted project directories |
| postgres | Connection string via env var, container hostname |
| context7 | Works as-is (external API) |
| memory | Works as-is (needs qdrant connection adapted) |
| sequential-thinking | Works as-is |
| filesystem | Works as-is |
| tavily | Works as-is (external API, needs TAVILY_API_KEY) |

**Exclude:**

| Server | Reason |
|--------|--------|
| docker | No Docker-in-Docker |
| desktop-commander | No desktop |
| midi | No MIDI hardware |
| midi-files | No MIDI hardware |

Container `mcp_servers.json`:

```json
{
  "mcpServers": {
    "qdrant": {
      "command": "uvx",
      "args": ["mcp-server-qdrant"],
      "env": {
        "QDRANT_URL": "http://qdrant:6333",
        "COLLECTION_NAME": "claude-memory",
        "EMBEDDING_MODEL": "nomic-embed-text",
        "EMBEDDING_PROVIDER": "ollama",
        "OLLAMA_URL": "http://ollama:11434"
      }
    },
    "git": {
      "command": "uvx",
      "args": ["mcp-server-git", "--repository", "."]
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "DATABASE_URL": "${POSTGRES_URL}"
      }
    }
  }
}
```

Plugin MCP servers (context7, playwright, etc.) are installed by Claude Code's plugin system at first run. The enabled plugins in `settings.json` handle this automatically.

### settings.json adaptation

The container `settings.json` has:
- All hook commands pointing to `/app/hapax-system/hooks/scripts/`
- Same `enabledPlugins` list (plugins install themselves on first run)
- `skipDangerousModePermissionPrompt: true` preserved

### Custom agents

The three custom agents (operator-voice, infra-check, convention-guard) are markdown files — no path dependencies. Copy directly to `/home/operator/.claude/agents/`.

One consideration: `operator-voice` specifies `model: opus` and `infra-check`/`convention-guard` specify `model: haiku`. These route through the Anthropic API directly (Claude Code's own model access), not through LiteLLM. This works in-container as long as `ANTHROPIC_API_KEY` is set.

### Rules

All 6 rule files are static markdown. Copy to `/home/operator/.claude/rules/`:
- `environment.md` — adapt: container context instead of Pop!_OS desktop
- `toolchain.md` — works as-is
- `models.md` — works as-is (LiteLLM routing)
- `music-production.md` — keep for context (Claude Code may discuss music topics)
- `axioms.md` — works as-is (from hapax-system)
- `system-context.md` — adapt: container service hostnames

## Dockerfile.dev

```dockerfile
FROM node:22-slim AS base

WORKDIR /app

# System tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl jq make ca-certificates gnupg python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

# uv for Python project management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# d2 diagram tool
RUN curl -fsSL https://d2lang.com/install.sh | sh -s --

# ripgrep
RUN curl -LO https://github.com/BurntSushi/ripgrep/releases/download/14.1.1/ripgrep_14.1.1-1_amd64.deb \
    && dpkg -i ripgrep_14.1.1-1_amd64.deb && rm ripgrep_14.1.1-1_amd64.deb

# Create non-root user
RUN useradd -m -s /bin/bash hapax
USER hapax
WORKDIR /home/hapax

# Claude Code configuration
COPY --chown=hapax:hapax hapax-system/ /app/hapax-system/
COPY --chown=hapax:hapax claude-config/settings.json /home/operator/.claude/settings.json
COPY --chown=hapax:hapax claude-config/mcp_servers.json /home/operator/.claude/mcp_servers.json
COPY --chown=hapax:hapax claude-config/rules/ /home/operator/.claude/rules/
COPY --chown=hapax:hapax hapax-system/agents/ /home/operator/.claude/agents/
COPY --chown=hapax:hapax hapax-system/skills/ /tmp/skills-src/

# Install skills as commands (flat copy, no symlinks in image)
RUN mkdir -p /home/operator/.claude/commands && \
    for d in /tmp/skills-src/*/; do \
      name="$(basename "$d")"; \
      [ -f "$d/SKILL.md" ] && cp "$d/SKILL.md" "/home/operator/.claude/commands/$name.md"; \
    done && rm -rf /tmp/skills-src

# Agent codebase
COPY --chown=hapax:hapax ai-agents/  /app/ai-agents/ 
WORKDIR /app/ai-agents
RUN uv sync --frozen --no-dev

# Axiom registry
COPY --chown=hapax:hapax axioms/ /app/axioms/

# Environment
ENV HAPAX_HOME=/data
ENV HAPAX_AGENTS_DIR=/app/ai-agents
ENV HAPAX_AUDIT_DIR=/data/.cache/axiom-audit
ENV QDRANT_URL=http://qdrant:6333
ENV OLLAMA_URL=http://ollama:11434
ENV LITELLM_API_BASE=http://litellm:4000
ENV LANGFUSE_HOST=http://langfuse:3000
ENV NTFY_BASE_URL=http://ntfy:8090

WORKDIR /workspace
ENTRYPOINT ["claude"]
```

## Docker Compose service

```yaml
hapax-dev:
  build:
    context: ..
    dockerfile: Dockerfile.dev
  profiles: [dev]
  stdin_open: true
  tty: true
  environment:
    - ANTHROPIC_API_KEY
    - LITELLM_API_KEY
    - LANGFUSE_PUBLIC_KEY
    - LANGFUSE_SECRET_KEY
    - TAVILY_API_KEY
  volumes:
    - hapax-data:/data
    - ${WORKSPACE:-./workspace}:/workspace
  networks:
    - llm-stack
  depends_on:
    - qdrant
    - ollama
    - litellm
```

Usage:

```bash
# Interactive Claude Code session with full Hapax customization
WORKSPACE=~/projects/my-project docker compose --profile dev run hapax-dev

# Or work on the agents codebase itself
WORKSPACE=. docker compose --profile dev run hapax-dev
```

## New directory structure

```
hapax-containerization/
├── ai-agents/                    (existing)
├── hapax-system/                (NEW — copied from ~/projects/hapax-system/)
│   ├── hooks/scripts/           (6 scripts, adapted for container paths)
│   ├── skills/                  (11 skills, adapted paths)
│   ├── agents/                  (3 agent definitions)
│   ├── rules/                   (2 rule files)
│   ├── install.sh               (for host-side use, kept for reference)
│   └── README.md
├── claude-config/               (NEW — container-specific Claude Code config)
│   ├── settings.json            (hooks pointing to /app/hapax-system/...)
│   ├── mcp_servers.json         (container networking)
│   └── rules/                   (4 global rules, adapted)
│       ├── environment.md
│       ├── toolchain.md
│       ├── models.md
│       └── music-production.md
├── Dockerfile.dev               (NEW)
├── llm-stack/
│   └── docker-compose.yml       (add hapax-dev service)
├── hapax-mgmt-web/
├── docs/
└── axioms/                      (existing, from hapaxromana)
```

## Decisions

1. **Separate image, not extension of hapax-agents.** The dev image needs an interactive shell, Claude Code CLI, and user home directory. The agents image is optimized for headless execution. Merging them would bloat the runtime image.

2. **Copy hapax-system into repo, not submodule.** This repo is the canonical home now. Same pattern as ai-agents.

3. **Non-root user `hapax`.** Claude Code writes to `~/.claude/` at runtime (conversation history, plugin cache). Needs a real home directory.

4. **Plugins install on first run.** The ~20 enabled plugins from marketplace repos install themselves when Claude Code starts and sees them in `enabledPlugins`. First launch will be slower; subsequent runs use cached plugins in the volume.

5. **`/workspace` mount point.** The user mounts whatever project they want to work on. Claude Code operates on the mounted directory, with full Hapax context available.

6. **No Docker-in-Docker.** The dev container doesn't manage other containers. Use `hapax-agents` and `hapax-ingest` for runtime. If Docker access is truly needed, the user can mount the Docker socket explicitly.

## Open questions

1. **Plugin caching.** Marketplace plugins (~100MB) download on first run. Should we bake them into the image, or let them cache in a volume? Volume is simpler but slower first boot.

2. **Claude Code version pinning.** `npm install -g @anthropic-ai/claude-code` gets latest. Should we pin a version for reproducibility?

3. **Project-level CLAUDE.md.** Each project has its own CLAUDE.md. The mounted workspace carries its own. Do we also want a default CLAUDE.md baked into the image for when no project is mounted?

4. **Conversation persistence.** Claude Code stores conversation history in `~/.claude/projects/`. Should this directory be in the volume so conversations persist across container restarts?
