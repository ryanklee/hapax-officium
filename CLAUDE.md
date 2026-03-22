# CLAUDE.md

**hapax-officium** — Management decision support for a single engineering manager. Agents prepare context for 1:1s, track management practice patterns, surface stale conversations, and profile the operator's management self-awareness.

Shared conventions (uv, ruff, testing, git workflow, pydantic-ai) are in the workspace `CLAUDE.md` — this file covers officium-specific details only.

**Safety principle:** LLMs prepare, humans deliver. Never generate feedback language, coaching recommendations, or evaluations of individual team members.

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

FastAPI on `:8050`. 32 endpoints across 8 route groups: data, profile, agents, nudges, demos, engine, cycle_mode, scout.

## Terrain UI (officium-web)

Depth-stratified terrain adapted from council hapax-logos for management domain.

**5 regions** × 3 depths (surface/stratum/core):

| Region | Key | Position | Domain | Surface Shows |
|--------|-----|----------|--------|---------------|
| Outlook | O | Top bar | Strategy | Briefing headline + nudge count + OKR risk |
| Assembly | A | Left col | Team | Report count + stale 1:1s + high load |
| Cadence | C | Center | Rhythm | Review status + status report freshness |
| Chronicle | H | Right col | Events | Open incidents + missing postmortems |
| Foundation | F | Bottom bar | Infra | Agent count + cycle mode |

**Sidebar** preserved alongside terrain (right edge). Same auto-expand, priority scoring, status dots.

**Investigation overlay** (`/` key): 4 tabs — Chat, Query, Prep, Output. Agent execution → Output tab.

**Stimmung**: `useStimmung()` derives per-region stance from management data pressure.

**Keyboard**: O/A/C/H/F regions, / investigate, Ctrl+P palette, Escape cascade. Old dashboard at `/legacy`.

## Reactive Engine

`logos/engine/` watches `DATA_DIR` for changes, evaluates 12 rules, executes cascading actions. Nudges: 3 categories (people, goals, operational), 9 collectors, category-slotted attention caps.

| Variable | Default | Purpose |
|----------|---------|---------||
| `ENGINE_ENABLED` | `true` | Kill switch |
| `ENGINE_DEBOUNCE_MS` | `200` | Watcher debounce |
| `ENGINE_LLM_CONCURRENCY` | `2` | Max simultaneous LLM calls |
| `ENGINE_DELIVERY_INTERVAL_S` | `300` | Batch notification interval |
| `ENGINE_ACTION_TIMEOUT_S` | `60` | Per-action timeout |

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
|------|---------||
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
|---------|---------|---------||
| LiteLLM | `LITELLM_API_BASE` | `http://localhost:4100` |
| Qdrant | `QDRANT_URL` | `http://localhost:6433` |
| Ollama | `OLLAMA_URL` | `http://localhost:11534` |
| DATA_DIR | `HAPAX_DATA_DIR` | `./data` |
