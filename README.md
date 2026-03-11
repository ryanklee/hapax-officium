# hapax-mgmt

A management cockpit for engineering managers. LLM-powered agents prepare context for 1:1s, track management practice patterns, surface stale conversations and open loops, and profile your management self-awareness -- so you walk into every conversation prepared, not scrambling. A React dashboard and FastAPI backend provide the operational interface.

**Safety principle:** LLMs prepare, humans deliver. The system never generates feedback language, coaching recommendations, or evaluations of individual team members.

## Quick Start

```bash
# Clone and install
git clone https://github.com/ryanklee/hapax-mgmt.git
cd hapax-mgmt
uv sync

# Run tests (all mocked, no infrastructure needed)
uv run pytest tests/ -q

# Bootstrap the demo system (requires Qdrant, LiteLLM, Ollama)
./scripts/bootstrap-demo.sh

# Or bootstrap without LLM calls (data pipeline only)
./scripts/bootstrap-demo.sh --skip-llm

# Start the cockpit API
uv run python -m cockpit.api --host 127.0.0.1 --port 8050
```

## Project Structure

```
hapax-mgmt/
├── agents/              16 agents (management, system, I/O, demo)
├── shared/              Shared modules (config, data bridge, profile, axioms)
├── cockpit/             FastAPI API + data collectors + reactive engine
│   ├── api/             32 REST endpoints across 8 route groups
│   ├── data/            11 data collectors (nudges, team health, goals)
│   └── engine/          Reactive engine (filesystem watcher, 12 rules, phased executor)
├── data/                Management data directory (DATA_DIR, gitignored)
├── demo-data/           Synthetic seed corpus (checked in)
├── profiles/            Generated operational state (gitignored)
├── scripts/             Bootstrap and operational scripts
├── tests/               Test suite
├── hapax-mgmt-web/      React SPA dashboard
├── vscode/              VS Code extension
├── axioms/              Governance axioms (registry + implications)
├── docs/                Design documents and plans
├── agent-architecture.md
└── operations-manual.md
```

## Agents

| Agent | LLM? | Purpose |
|-------|------|---------|
| `management_prep` | Yes | 1:1 prep docs, team snapshots, management overviews |
| `meeting_lifecycle` | Yes | Meeting prep automation, transcript processing, weekly review |
| `management_briefing` | Yes | Morning management briefing from management data |
| `management_profiler` | Yes | Management self-awareness profiling (6 dimensions) |
| `management_activity` | No | Management practice metrics (1:1 rates, feedback timing) |
| `digest` | Yes | Content/knowledge digest from Qdrant documents |
| `scout` | Yes | Horizon scanning for component fitness evaluation |
| `drift_detector` | Yes | Documentation drift detection and correction |
| `knowledge_maint` | No | Qdrant hygiene: stale pruning, near-duplicate detection |
| `introspect` | No | Infrastructure manifest snapshot |
| `ingest` | No | Document ingestion pipeline (watch mode or one-shot) |
| `status_update` | Yes | Upward-facing status reports from management data |
| `review_prep` | Yes | Performance review evidence aggregation |
| `demo` | Yes | Audience-tailored system demonstrations |
| `demo_eval` | Yes | Demo evaluation and iterative improvement loop |
| `system_check` | No | Health checks for core services (API, Qdrant, LiteLLM) |

Run any agent:

```bash
uv run python -m agents.<name> [flags]
```

## Demo System

The repo includes a synthetic management data corpus (`demo-data/`) that models a fictional engineering manager with 3 teams, 8 people, and full management state (coaching, feedback, OKRs, goals, incidents, review cycles). The bootstrap script hydrates the system from this seed data:

```bash
# Full hydration -- copies seed data, creates Qdrant collections,
# runs deterministic agents, then LLM synthesis agents
./scripts/bootstrap-demo.sh

# Data pipeline only -- no LLM calls needed
./scripts/bootstrap-demo.sh --skip-llm
```

After bootstrap, the cockpit API serves live management state and the dashboard displays real nudges, team health, and briefings.

## Infrastructure Requirements

The management cockpit requires three external services:

| Service | Purpose | Default URL |
|---------|---------|-------------|
| **Qdrant** | Vector database (768d, nomic-embed) | `http://localhost:6433` |
| **LiteLLM** | LLM API gateway (model routing + tracing) | `http://localhost:4100` |
| **Ollama** | Local inference (embeddings) | `http://localhost:11434` |

Optional services for full observability:

| Service | Purpose | Default URL |
|---------|---------|-------------|
| Langfuse | LLM trace observability | `http://localhost:3100` |
| PostgreSQL | Database for LiteLLM + Langfuse | `localhost:5532` |
| ntfy | Push notifications | `http://localhost:8190` |

Configure via environment variables (see `shared/config.py`):

```bash
export LITELLM_API_KEY="your-key"
export LITELLM_BASE_URL="http://localhost:4100"
export QDRANT_URL="http://localhost:6433"
export OLLAMA_URL="http://localhost:11434"
```

## Architecture

The system uses a **filesystem-as-bus** architecture. All management state is stored as markdown files with YAML frontmatter in `data/` (DATA_DIR). The reactive engine watches for changes via inotify and cascades downstream actions (cache refresh, nudge recalculation, LLM synthesis, batched notifications).

Three constitutional axioms govern the system:

- **single_operator** -- built for one person, no auth or multi-user features
- **decision_support** -- zero-config agents, actionable errors, automated routines
- **management_safety** -- LLMs prepare, humans deliver; never generate feedback language

See `agent-architecture.md` for full architecture details and `operations-manual.md` for operational reference.

## License

[Apache License 2.0](LICENSE)
