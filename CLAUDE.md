# CLAUDE.md

**hapax-officium** — Management decision support for a single engineering manager. Agents prepare context for 1:1s, track management practice patterns, surface stale conversations, and profile the operator's management self-awareness.

Shared conventions (uv, ruff, testing, git workflow, pydantic-ai) are in the workspace `CLAUDE.md` — this file covers officium-specific details only.

**Sister surfaces:** the [vscode extension](vscode/CLAUDE.md) is the operator-facing reading surface for officium data; [`hapax-mcp`](https://github.com/ryanklee/hapax-mcp) provides the same Logos API to Claude Code via MCP. **Spec dependency:** governance axioms come from [`hapax-constitution`](https://github.com/ryanklee/hapax-constitution) via the `hapax-sdlc[demo]` package; see `axioms/registry.yaml` for the locally extended set.

**Safety principle:** LLMs prepare, humans deliver. Never generate feedback language, coaching recommendations, or evaluations of individual team members.

## Quick Start

```bash
uv sync --all-extras
uv run officium-api              # Start API on :8050 (or: uv run python -m logos.api)
uv run pytest tests/ -q          # Run tests
uv run ruff check . && uv run ruff format .  # Lint + format
uv run pyright                   # Type check
docker compose up -d             # Infrastructure (LiteLLM, Qdrant, etc.)
```

**Demo seed system:** Produces a fully-hydrated replica with realistic synthetic data. `demo-data/` for the corpus, `scripts/bootstrap-demo.sh` for hydration (`--skip-llm` for data pipeline only).

## Agents

| Agent | LLM? | Purpose |
|-------|------|---------|
| management_prep | Yes | 1:1 prep docs, team snapshots, management overviews |
| meeting_lifecycle | Yes | Meeting prep automation, transcript processing |
| management_briefing | Yes | Morning management briefing |
| management_profiler | Yes | Management self-awareness profiling (6 dimensions) |
| management_activity | No | Management practice metrics from DATA_DIR |
| digest | Yes | Content/knowledge digest from Qdrant documents |
| scout | Yes | Horizon scanning for component fitness |
| drift_detector | Yes | Documentation drift detection and correction |
| knowledge_maint | No | Qdrant hygiene: stale pruning, near-duplicate detection |
| introspect | No | Infrastructure manifest snapshot |
| ingest | No | Document ingestion pipeline |
| status_update | Yes | Upward-facing status reports |
| review_prep | Yes | Performance review evidence aggregation |
| demo | Yes | Audience-tailored system demonstrations |
| demo_eval | Yes | Demo evaluation and iterative improvement loop |
| system_check | No | Health checks for 3 core services |
| simulator | Yes | Temporal simulation of management scenarios |

## Logos API

FastAPI on `:8050`. 34 endpoints across 8 route groups: data, profile, agents, nudges, demos, engine, working_mode, scout.

The canonical mode endpoint is `/api/working-mode` (returns `research`/`rnd`); `/api/cycle-mode` is a deprecated alias kept during the migration window. Officium intentionally omits council's `fortress` mode (no studio surface). The mode file is shared workspace-wide at `~/.cache/hapax/working-mode`. To bridge officium tools through `hapax-mcp`, run a second mcp instance with `LOGOS_BASE_URL=http://localhost:8050/api` (the default points at council).

## Reactive Engine

`logos/engine/` watches `DATA_DIR` for changes, evaluates 12 rules, executes cascading actions. Nudges: 3 categories (people, goals, operational), 9 collectors, category-slotted attention caps.

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENGINE_ENABLED` | `true` | Kill switch |
| `ENGINE_DEBOUNCE_MS` | `200` | Watcher debounce |
| `ENGINE_LLM_CONCURRENCY` | `2` | Max simultaneous LLM calls |
| `ENGINE_DELIVERY_INTERVAL_S` | `300` | Batch notification interval |
| `ENGINE_ACTION_TIMEOUT_S` | `60` | Per-action timeout |
| `ENGINE_SYNTHESIS_ENABLED` | `true` | Enable/disable synthesis |
| `ENGINE_SYNTHESIS_QUIET_S` | `180` | Quiet period before synthesis |
| `ENGINE_PROFILER_INTERVAL_S` | `86400` | Profiler run interval |

## Axiom Governance

3 active constitutional axioms + 1 dormant:

| Axiom | Weight | Scope |
|-------|--------|-------|
| single_operator | 100 | constitutional |
| decision_support | 95 | constitutional |
| management_safety | 95 | constitutional |
| corporate_boundary | 90 | dormant / domain |

## SDLC Pipeline

Same pattern as council. Management_safety is primary review focus. Scripts in `scripts/`, workflows in `.github/workflows/`. Protected paths: `agents/system_check.py`, `shared/axiom_*`, `shared/config.py`, `axioms/`, `logos/engine/`, `.github/`.

## Key Paths

| Path | Purpose |
|------|---------|
| `shared/config.py` | Central config, DATA_DIR, model aliases |
| `shared/management_bridge.py` | Reads DATA_DIR |
| `shared/vault_writer.py` | Writes DATA_DIR |
| `shared/profile_store.py` | Management profile facts in Qdrant (6 dimensions) |
| `logos/api/routes/` | REST endpoints |
| `logos/engine/` | Reactive engine |
| `axioms/registry.yaml` | Axiom definitions |
| `data/` | Local management data (DATA_DIR, gitignored) |

## Infrastructure Defaults

| Service | Env Var | Default |
|---------|---------|---------|
| LiteLLM | `LITELLM_API_BASE` | `http://localhost:4100` |
| Qdrant | `QDRANT_URL` | `http://localhost:6433` |
| Ollama | `OLLAMA_URL` | `http://localhost:11534` |
| DATA_DIR | `HAPAX_DATA_DIR` | `./data` |

> Subject to the workspace CLAUDE.md rotation policy: `hapax-council/docs/superpowers/specs/2026-04-13-claude-md-excellence-design.md`.
