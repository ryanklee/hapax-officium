# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

**hapax-officium** -- a management decision support system for a single engineering manager. Agents prepare context for 1:1s, track management practice patterns, surface stale conversations and open loops, and profile the operator's management self-awareness. A React dashboard provides the operational interface. A management instantiation of the hapax-constitution pattern.

**Demo seed system:** This repo is designed to produce, at any moment, a fully-hydrated replica of itself containing realistic synthetic data exercised through every agent and collector. The demo agent then operates against a live, functioning system -- not a static mockup. See `demo-data/` for the synthetic corpus and `scripts/bootstrap-demo.sh` for the hydration pipeline.

**Safety principle:** LLMs prepare, humans deliver. The system never generates feedback language, coaching recommendations, or evaluations of individual team members.

## Repository Layout

```
hapax-officium/
├── CLAUDE.md                    # This file
├── agents/                      # 16 agents (7 management + 5 system + 2 I/O + 2 demo)
│   ├── management_prep.py       # 1:1 prep, team snapshots, overviews
│   ├── meeting_lifecycle.py     # Meeting automation, transcript processing
│   ├── management_briefing.py   # Morning management briefing
│   ├── management_profiler.py   # Management self-awareness profiling (6 dimensions)
│   ├── management_activity.py   # Management practice metrics from DATA_DIR
│   ├── digest.py                # Content/knowledge digest from Qdrant documents
│   ├── scout.py                 # Horizon scanning for component fitness
│   ├── drift_detector.py        # Documentation drift detection and correction
│   ├── knowledge_maint.py       # Qdrant hygiene: stale pruning, near-duplicate detection
│   ├── introspect.py            # Infrastructure manifest snapshot
│   ├── ingest.py                # Document ingestion pipeline
│   ├── status_update.py         # Upward-facing status reports
│   ├── review_prep.py           # Performance review evidence aggregation
│   ├── demo.py                  # Audience-tailored system demos
│   ├── demo_eval.py             # Demo evaluation and iterative improvement loop
│   ├── system_check.py          # Health checks for 3 core services
│   └── demo_pipeline/           # Demo generation pipeline (slides, charts, diagrams)
├── shared/                      # 20 shared modules (config, notify, profile, axioms, etc.)
├── cockpit/                     # FastAPI API server (:8050) + data collectors + reactive engine
│   ├── api/                     # REST server with 32 endpoints across 8 route groups
│   ├── data/                    # 11 data collectors (management, nudges, team health, goals, etc.)
│   └── engine/                  # Reactive engine (watcher, 12 rules, executor, delivery)
├── data/                        # Local data directory (DATA_DIR, gitignored contents)
├── demo-data/                   # Synthetic seed corpus (checked in, not gitignored)
├── profiles/                    # Persistent state (gitignored: *.json, *.md, *.jsonl, *.yaml)
├── scripts/                     # Bootstrap and operational scripts
├── tests/                       # Test suite
├── officium-web/                # React SPA dashboard
├── vscode/                      # VS Code extension (TypeScript)
├── axioms/                      # Governance axioms (registry.yaml + implications)
├── docs/                        # Design documents and plans
├── agent-architecture.md        # System architecture spec
├── operations-manual.md         # Operational reference
└── pyproject.toml               # Dependencies
```

## Agents

| Agent | LLM? | Purpose |
|-------|------|---------|
| management_prep | Yes | 1:1 prep docs, team snapshots, management overviews |
| meeting_lifecycle | Yes | Meeting prep automation, transcript processing, weekly review |
| management_briefing | Yes | Morning management briefing from management data |
| management_profiler | Yes | Management self-awareness profiling (6 dimensions) |
| management_activity | No | Management practice metrics from management data (1:1 rates, feedback timing) |
| digest | Yes | Content/knowledge digest from Qdrant documents |
| scout | Yes | Horizon scanning for component fitness evaluation |
| drift_detector | Yes | Documentation drift detection and correction |
| knowledge_maint | No | Qdrant hygiene: stale pruning, near-duplicate detection |
| introspect | No | Infrastructure manifest snapshot (services, collections, models) |
| ingest | No | Document ingestion pipeline (watch mode or one-shot) |
| status_update | Yes | Upward-facing status reports from management data |
| review_prep | Yes | Performance review evidence aggregation |
| demo | Yes | Audience-tailored system demonstrations |
| demo_eval | Yes | Demo evaluation and iterative improvement loop |
| system_check | No | Health checks for 3 core services (API, Qdrant, LiteLLM) |

## API

The cockpit API (`cockpit/api/`) serves 32 endpoints across 8 route groups: data, profile, agents, nudges, demos, engine, cycle_mode, and scout. Runs on port 8050 (dev) / 8051 (Docker). The reactive engine (`cockpit/engine/`) watches DATA_DIR for changes and evaluates 12 rules to auto-cascade downstream actions (cache refresh, nudge recalculation, LLM synthesis, batched notifications). Nudges are organized into 3 categories (people, goals, operational) with 9 collectors and category-slotted attention caps (CATEGORY_SLOTS).

## Axiom Governance

3 active constitutional axioms + 1 dormant domain axiom:

| Axiom | Weight | Scope |
|-------|--------|-------|
| single_operator | 100 | constitutional |
| decision_support | 95 | constitutional |
| management_safety | 95 | constitutional |
| corporate_boundary | 90 | dormant / domain: infrastructure |

Enforced via `shared/axiom_*.py` modules. T0 violations are blocked by SDLC hooks. See `axioms/registry.yaml` for definitions.

## Build, Test, and Run

```bash
uv sync

# Run tests (all mocked, no LLM/network calls needed)
uv run pytest tests/ -q

# Run a single test file or specific test
uv run pytest tests/test_engine_rules.py -q
uv run pytest tests/test_api.py::test_health -q

# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run pyright

# Run an agent directly
uv run python -m agents.<name> [flags]

# Run cockpit API server (port 8050)
uv run python -m cockpit.api --host 127.0.0.1 --port 8050

# Frontend (React dashboard)
cd officium-web && npm install && npm run dev
```

## Demo Hydration

Bootstrap a fully warm system from the synthetic seed corpus:

```bash
# Full hydration (requires running Qdrant, LiteLLM, Ollama)
./scripts/bootstrap-demo.sh

# Data pipeline only (no LLM calls -- tests collectors, nudges, team health)
./scripts/bootstrap-demo.sh --skip-llm
```

The bootstrap script copies `demo-data/` into `data/`, ensures Qdrant collections, runs deterministic agents (activity, introspect), then LLM synthesis agents (profiler, briefing, digest, team snapshot). After completion, the cockpit API serves live management state and the dashboard shows real nudges, team health, and briefings.

## Data Directory

`data/` is the local management data directory (`DATA_DIR` in `shared/config.py`). Structure:

```
data/
├── people/              Person notes (markdown with YAML frontmatter)
├── meetings/            Meeting notes
├── coaching/            Coaching hypotheses
├── feedback/            Feedback records
├── decisions/           Decision records
├── okrs/                OKR tracking (quarterly objectives + key results)
├── goals/               SMART goals (individual development goals)
├── incidents/           Incident records
├── postmortem-actions/  Postmortem action items
├── review-cycles/       Performance review process tracking
├── status-reports/      Status reports (weekly/monthly)
├── references/          Generated artifacts (briefings, digests, status reports, snapshots)
├── 1on1-prep/           Generated 1:1 prep docs
├── briefings/           Generated briefings
├── status-updates/      Generated status reports
├── review-prep/         Generated review evidence
└── .gitkeep             Tracked; all other contents gitignored
```

Read by `shared/management_bridge.py` and `cockpit/data/management.py`. Written by `shared/vault_writer.py` and output agents.

## Reactive Engine

`cockpit/engine/` provides a filesystem-watching reactive loop. When files change in `DATA_DIR`, the engine evaluates 12 rules across all document types, executes cascading actions (cache refresh, nudge recalculation, LLM synthesis), and delivers batched notifications. Nudges are organized into 3 categories (people, goals, operational) with 9 collectors and category-slotted attention caps via CATEGORY_SLOTS.

Configuration (env vars, all optional):

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENGINE_ENABLED` | `true` | Kill switch |
| `ENGINE_DEBOUNCE_MS` | `200` | Watcher debounce window |
| `ENGINE_LLM_CONCURRENCY` | `2` | Max simultaneous LLM calls |
| `ENGINE_DELIVERY_INTERVAL_S` | `300` | Batch notification interval |
| `ENGINE_ACTION_TIMEOUT_S` | `60` | Per-action LLM timeout |

API endpoints: `GET /api/engine/status`, `GET /api/engine/recent`, `GET /api/engine/rules`.

## Key Files

| File | Purpose |
|------|---------|
| `shared/config.py` | Central config: model aliases, LiteLLM/Qdrant/Ollama clients, path constants, DATA_DIR |
| `shared/operator.py` | Operator manifest loading, system prompt generation |
| `shared/profile_store.py` | Management profile facts in Qdrant (6 dimensions) |
| `shared/context_tools.py` | On-demand management context tools for agents |
| `shared/management_bridge.py` | Management data bridge (reads DATA_DIR) |
| `shared/vault_writer.py` | Management data writer (writes DATA_DIR) |
| `cockpit/api/` | FastAPI server with routes in `routes/` |
| `cockpit/data/` | 11 data collectors (management, nudges, team health, goals, etc.) |
| `cockpit/engine/` | Reactive engine (inotify watcher, rule evaluator, phased executor) |
| `axioms/registry.yaml` | Axiom definitions (single_operator, decision_support, management_safety) |

## Infrastructure Defaults

Configured in `shared/config.py` via env vars. Defaults:

| Service | Env Var | Default |
|---------|---------|---------|
| LiteLLM | `LITELLM_API_BASE` / `LITELLM_BASE_URL` | `http://localhost:4100` |
| Qdrant | `QDRANT_URL` | `http://localhost:6433` |
| Ollama | `OLLAMA_URL` | `http://localhost:11534` |
| DATA_DIR | `HAPAX_DATA_DIR` | `./data` |

## Conventions

- Python 3.12+, managed with `uv`. Never pip.
- Type hints mandatory. Pydantic models for structured data.
- All LLM calls through LiteLLM proxy. Never direct to providers.
- Git: conventional commits, feature branches from `main`.
- pydantic-ai: uses `output_type` (not `result_type`) and `result.output` (not `result.data`).
- Tests use `unittest.mock` -- no pytest fixtures in conftest. Each test file is self-contained.
- `asyncio_mode = "auto"` in pytest config -- async tests work without `@pytest.mark.asyncio`.
- Ruff: line-length 100, double quotes. Imports sorted with `known-first-party = ["agents", "shared", "cockpit"]`.
- Safety: LLMs prepare, humans deliver. Never generate feedback language or coaching recommendations about individual team members.
