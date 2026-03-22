# Management Logos — Operations Manual

*Operational reference for the hapax-officium logos system.*

---

## Getting Started

### 1. Verify Infrastructure

The logos system depends on external Docker services. Start them:

```bash
docker compose up -d
```

Core services for the logos system:

| Service | Host Port | Purpose |
|---------|-----------|---------|
| Qdrant | 6433 | Vector database (768d, nomic-embed) |
| Ollama | 11434 | Local LLM inference (GPU) |
| PostgreSQL | 5532 | pgvector for LiteLLM + Langfuse |
| LiteLLM | 4100 | API gateway, model routing + tracing |

Additional services available via Docker Compose profiles:

| Service | Host Port | Profile | Purpose |
|---------|-----------|---------|---------|
| ClickHouse | 8223 | full | OLAP for Langfuse |
| Redis | internal | full | Langfuse cache |
| MinIO | 9190/9191 | full | Object storage |
| Langfuse Worker | 3130 | full | Async trace processing |
| Langfuse | 3100 | full | LLM observability |
| ntfy | 8190 | full | Push notifications |
| Chatterbox | 4223 | tts | Voice cloning TTS |
| officium-web | 8052 | management | React dashboard |
| management-logos | 8051 | management | Logos API container |

Run the system check to confirm the stack is reachable:

```bash
uv run python -m agents.system_check
```

This checks 3 core services (API, Qdrant, LiteLLM). Common fixes:

| Symptom | Fix |
|---------|-----|
| Docker containers down | `docker compose up -d` |
| Ollama models missing | `docker compose exec ollama ollama pull nomic-embed-text` |
| Qdrant collections missing | Created automatically on first agent run |

### 2. Run Your First Agent

All agents run the same way:

```bash
uv run python -m agents.<name> [flags]
```

Try the briefing:

```bash
uv run python -m agents.management_briefing --save
```

### 3. Start the Logos API

```bash
uv run python -m logos.api --host 127.0.0.1 --port 8050
```

The API serves 32 endpoints across 8 route groups. In Docker, the API container exposes port 8051 and the React dashboard runs on port 8052.

### 4. First-Day Checklist

- [ ] Verify `system_check` passes for all 3 services
- [ ] Generate a briefing with `--save`
- [ ] Start the logos API and browse the endpoints
- [ ] Review nudges via the API or dashboard
- [ ] Run `management_prep --team-snapshot` to see team state

---

## Agent Reference

### All Agents

| Agent | LLM? | Flags |
|-------|------|-------|
| management_prep | Yes | `--person NAME`, `--team-snapshot`, `--overview`, `--save` |
| meeting_lifecycle | Yes | `--prepare`, `--transcript FILE`, `--weekly-review` |
| management_briefing | Yes | `--save` |
| management_profiler | Yes | `--auto`, `--digest` |
| management_activity | No | `--json`, `--days N` |
| digest | Yes | `--save`, `--hours N` |
| scout | Yes | (none) |
| drift_detector | Yes | `--fix`, `--json` |
| knowledge_maint | No | `--summarize` |
| introspect | No | `--save` |
| ingest | No | `--watch`, `--stats` |
| status_update | Yes | (none) |
| review_prep | Yes | (none) |
| demo | Yes | `--audience NAME`, `--duration Nm`, `--voice` |
| system_check | No | (none) |

### Agent Details

**management_prep** — Prepares context for 1:1s, team snapshots, and management overviews. Reads person notes from DATA_DIR, aggregates signals (stale 1:1s, open loops, coaching status, Larson state), and produces structured talking points. Never generates feedback language.

```bash
uv run python -m agents.management_prep --person "Sarah Chen"
uv run python -m agents.management_prep --team-snapshot
uv run python -m agents.management_prep --overview --save
```

**meeting_lifecycle** — Automates meeting preparation, transcript processing, and weekly review. Parses VTT/SRT/speaker-labeled transcripts, extracts action items, updates meeting records in DATA_DIR.

```bash
uv run python -m agents.meeting_lifecycle --prepare
uv run python -m agents.meeting_lifecycle --transcript ~/Downloads/meeting.vtt
uv run python -m agents.meeting_lifecycle --weekly-review
```

**management_briefing** — Morning management briefing synthesized from management data. Use `--save` to persist output to DATA_DIR.

```bash
uv run python -m agents.management_briefing --save
```

**management_profiler** — Builds the operator's management self-awareness profile across 6 dimensions. Use `--auto` for incremental update from all sources, `--digest` to update from recent digest content.

```bash
uv run python -m agents.management_profiler --auto
uv run python -m agents.management_profiler --digest
```

**management_activity** — Deterministic management practice metrics (no LLM calls). Computes 1:1 rates, feedback timing, coaching frequency from DATA_DIR files.

```bash
uv run python -m agents.management_activity --json
uv run python -m agents.management_activity --days 30
```

**digest** — Aggregates recently ingested content from Qdrant into a summary. Use `--hours` to control the lookback window.

```bash
uv run python -m agents.digest --save
uv run python -m agents.digest --hours 48 --save
```

**scout** — Horizon scanning agent. Evaluates stack components against the external landscape for fitness, deprecation risks, and better alternatives.

```bash
uv run python -m agents.scout
```

**drift_detector** — Compares documentation claims against actual system state. Use `--fix` to auto-correct drift.

```bash
uv run python -m agents.drift_detector
uv run python -m agents.drift_detector --fix
uv run python -m agents.drift_detector --json
```

**knowledge_maint** — Qdrant hygiene: stale vector pruning, near-duplicate detection, collection statistics. No LLM calls.

```bash
uv run python -m agents.knowledge_maint --summarize
```

**introspect** — Infrastructure manifest snapshot. Captures current state of services, collections, and models. Use `--save` to persist.

```bash
uv run python -m agents.introspect --save
```

**ingest** — Document ingestion pipeline. Processes files into Qdrant. Use `--watch` for continuous mode, `--stats` for pipeline statistics.

```bash
uv run python -m agents.ingest --stats
uv run python -m agents.ingest --watch
```

**status_update** — Generates upward-facing status reports from management data.

```bash
uv run python -m agents.status_update
```

**review_prep** — Performance review evidence aggregation from management data.

```bash
uv run python -m agents.review_prep
```

**demo** — Audience-tailored system demonstrations. Generates a live walkthrough script.

```bash
uv run python -m agents.demo --audience "VP Engineering" --duration 15m
uv run python -m agents.demo --audience "New EM" --duration 10m --voice "logos dashboard overview"
```

**system_check** — Health checks for 3 core services (logos API, Qdrant, LiteLLM). No LLM calls.

```bash
uv run python -m agents.system_check
```

---

## Common Workflows

### Morning Routine

1. Check the briefing (generate if needed):
   ```bash
   uv run python -m agents.management_briefing --save
   ```
2. Start the logos API and review nudges — the system surfaces what needs attention.
3. Check which 1:1s are coming up and run prep:
   ```bash
   uv run python -m agents.management_prep --person "Sarah Chen"
   ```

### Preparing for a 1:1

1. Run management prep for the person:
   ```bash
   uv run python -m agents.management_prep --person "Marcus Johnson"
   ```
2. The agent reads the person's note (frontmatter: cognitive-load, last-1on1, coaching status), recent meetings, coaching notes, and feedback records from DATA_DIR.
3. It returns talking points and open loops. It never generates feedback language or coaching recommendations — it surfaces patterns for you to interpret.

### After a 1:1

1. Process the transcript:
   ```bash
   uv run python -m agents.meeting_lifecycle --transcript ~/Downloads/meeting.vtt
   ```
2. Update coaching or feedback records in DATA_DIR as needed.
3. The reactive engine picks up changes and cascades downstream updates (nudge recalculation, cache refresh).

### Team Snapshot Before a Leadership Meeting

```bash
uv run python -m agents.management_prep --team-snapshot
```

This aggregates all person notes, assesses Larson state (falling-behind, repaying-debt, innovating), flags capacity risks, and identifies stale 1:1s.

### Weekly Review

```bash
uv run python -m agents.meeting_lifecycle --weekly-review
uv run python -m agents.management_prep --team-snapshot
```

Review goals and OKRs in DATA_DIR. Check management activity metrics:

```bash
uv run python -m agents.management_activity --days 7 --json
```

### System Maintenance

Run periodically to keep the system healthy:

```bash
# Check documentation drift
uv run python -m agents.drift_detector

# Qdrant hygiene
uv run python -m agents.knowledge_maint --summarize

# Infrastructure snapshot
uv run python -m agents.introspect --save

# Core service health
uv run python -m agents.system_check
```

### Running a Demo

Bootstrap a fully hydrated demo environment from the synthetic seed corpus:

```bash
# Full hydration (requires running Qdrant, LiteLLM, Ollama)
./scripts/bootstrap-demo.sh

# Data pipeline only (no LLM calls)
./scripts/bootstrap-demo.sh --skip-llm
```

The bootstrap script copies `demo-data/` into `data/`, creates Qdrant collections, runs deterministic agents in parallel (management_activity, introspect), then runs LLM agents sequentially (management_profiler, management_briefing, digest, team snapshot).

Then generate a tailored demo walkthrough:

```bash
uv run python -m agents.demo --audience "VP Engineering" --duration 15m --voice "logos dashboard"
```

Demo data: 40 seed files across 15 directories, 8 people (7 active), 3 teams (Platform, Product, Data).

---

## Data Model

### DATA_DIR

All management state lives in `data/` as markdown files with YAML frontmatter. This is the filesystem-as-bus architecture — agents and collectors read/write these files, and the reactive engine watches for changes.

Subdirectories:

| Directory | Document Type | Key Frontmatter |
|-----------|--------------|-----------------|
| `people/` | person | `status`, `team`, `role`, `cognitive-load`, `last-1on1` |
| `coaching/` | coaching | `person`, `status`, `created` |
| `feedback/` | feedback | `person`, `direction`, `date` |
| `meetings/` | meeting | `type`, `participants`, `date` |
| `decisions/` | decision | `status`, `date`, `stakeholders` |
| `references/` | (reference docs) | varies |
| `okrs/` | okr | `quarter`, `status`, `key-results` |
| `goals/` | goal | `person`, `status`, `target-date` |
| `incidents/` | incident | `severity`, `status`, `date` |
| `postmortem-actions/` | postmortem-action | `incident`, `owner`, `status` |
| `review-cycles/` | review-cycle | `cycle`, `status`, `due-date` |
| `status-reports/` | status-report | `period`, `date` |

Frontmatter keys are kebab-case. The `type:` field in frontmatter must match the document type exactly.

### Reactive Engine

The engine watches DATA_DIR for changes (via inotify) and evaluates 12 rules to auto-cascade downstream actions:

1. `inbox_ingest` — new files in inbox
2. `meeting_cascade` — meeting changes trigger prep refresh
3. `person_changed` — person note updates cascade to nudges
4. `coaching_changed` — coaching note updates
5. `feedback_changed` — feedback record updates
6. `decision_logged` — new decisions
7. `okr_changed` — OKR updates
8. `smart_goal_changed` — goal updates
9. `incident_changed` — incident updates
10. `postmortem_action_changed` — postmortem action updates
11. `review_cycle_changed` — review cycle updates
12. `status_report_changed` — status report updates

Execution is phased: deterministic work (phase 0, unlimited concurrency) runs before LLM work (phase 1+, semaphore=2).

### Nudges

9 collectors organized into 3 categories with attention caps:

| Category | Slots | Purpose |
|----------|-------|---------|
| people | 3 | Stale 1:1s, coaching gaps, capacity risks |
| goals | 2 | OKR drift, goal deadlines |
| operational | 2 | System health, process gaps |

MAX_VISIBLE = 7. The system shows at most 7 nudges total, distributed across category slots.

### Management Profiler

6 dimensions of operator management self-awareness:

1. `management_practice` — cadence discipline, meeting habits
2. `team_leadership` — how you lead across the team
3. `decision_patterns` — decision-making approach and speed
4. `communication_style` — communication patterns
5. `attention_distribution` — where you spend your attention
6. `self_awareness` — accuracy of self-assessment

Profile facts stored as vectors in Qdrant's `profile-facts` collection.

---

## Axiom Governance

3 active constitutional axioms + 1 dormant domain axiom:

| Axiom | Weight | Status | Core Principle |
|-------|--------|--------|----------------|
| `single_operator` | 100 | active | No auth, no multi-user, no collaboration features |
| `decision_support` | 95 | active | Zero-config agents, actionable errors, automated routines |
| `management_safety` | 95 | active | LLMs prepare, humans deliver — never generate feedback language |
| `corporate_boundary` | 90 | dormant | Retained for reference; not currently enforced |

T0 violations are blocked by SDLC hooks. Key implications:

- **single_operator**: No authentication, authorization, multi-user features, or collaboration code.
- **decision_support**: Agents must run with zero config beyond env vars. Error messages must include next actions. Recurring tasks must be automated.
- **management_safety**: Never generate feedback language, performance evaluations, or coaching recommendations for individual team members. Never draft language for people conversations.

Axiom definitions live in `axioms/registry.yaml`.

---

## Logos API

Start locally:

```bash
uv run python -m logos.api --host 127.0.0.1 --port 8050
```

In Docker, the management-logos container exposes port 8051.

32 endpoints across 8 route groups:

| Group | Purpose |
|-------|---------|
| data | Management data access (people, meetings, coaching, etc.) |
| profile | Management profiler dimensions and facts |
| agents | Agent execution and status |
| nudges | Nudge listing, dismissal, category state |
| demos | Demo generation and management |
| engine | Reactive engine status and control |
| cycle_mode | Dev/prod cycle mode switching |
| (health) | System health and readiness |

---

## Monitoring

### LLM Traces

All LLM calls route through LiteLLM (port 4100) and trace to Langfuse (port 3100). Open http://localhost:3100 to browse traces, filter by model, and inspect per-generation costs.

### System Health

```bash
uv run python -m agents.system_check
```

Checks 3 core services: logos API, Qdrant, LiteLLM.

### GPU/VRAM

The RTX 3090 has 24GB VRAM. Only one large model loads at a time. Ollama auto-unloads idle models after 5 minutes.

```bash
nvidia-smi --query-gpu=memory.used,memory.total,memory.free --format=csv,noheader,nounits
```

Common model sizes:
- `nomic-embed-text` (~0.5GB) — always needed for embedding
- `qwen2.5-coder:32b` (~18GB) — coding tasks
- `deepseek-r1:14b` (~9GB) — reasoning, can coexist with smaller models

---

## Key Files

| File | Purpose |
|------|---------|
| `shared/config.py` | Central config: model aliases, LiteLLM/Qdrant/Ollama clients, DATA_DIR |
| `shared/management_bridge.py` | Reads management data from DATA_DIR |
| `shared/vault_writer.py` | Writes management data to DATA_DIR |
| `shared/operator.py` | Operator manifest loading, system prompt generation |
| `shared/profile_store.py` | Management profile facts in Qdrant (6 dimensions) |
| `shared/context_tools.py` | On-demand management context tools for agents |
| `logos/api/` | FastAPI server with routes in `routes/` |
| `logos/engine/` | Reactive engine (inotify watcher, rule evaluator, phased executor) |
| `logos/data/` | Data collectors (management, nudges, agents) |
| `demo-data/` | Synthetic seed corpus (checked into git) |
| `data/` | Live management data (gitignored) |
| `axioms/registry.yaml` | Axiom definitions |

---

## Quick Reference

### Essential Commands

```bash
# Run any agent
uv run python -m agents.<name> [flags]

# Logos API (local)
uv run python -m logos.api --host 127.0.0.1 --port 8050

# Docker services
docker compose up -d                          # Core services
docker compose --profile full up -d           # All services including Langfuse
docker compose --profile management up -d     # Logos API + web dashboard
docker compose ps                             # Status

# Tests
uv run pytest tests/ -q

# Demo bootstrap
./scripts/bootstrap-demo.sh
./scripts/bootstrap-demo.sh --skip-llm        # Data pipeline only
```

### Model Aliases (via LiteLLM at localhost:4100)

| Alias | Model | When to Use |
|-------|-------|-------------|
| `fast` | claude-haiku | Cheap quick tasks |
| `balanced` | claude-sonnet | Default for most agents |
| `reasoning` | deepseek-r1:14b | Complex reasoning (local) |
| `coding` | qwen-coder-32b | Code generation (local) |
| `local-fast` | qwen-7b | Lightweight local tasks |

### Key Paths

| Path | What |
|------|------|
| `agents/` | Agent implementations |
| `shared/` | Shared modules (config, bridge, profile, axioms) |
| `logos/` | FastAPI API server + data collectors + reactive engine |
| `data/` | Live management data (DATA_DIR) |
| `demo-data/` | Synthetic seed corpus |
| `officium-web/` | React dashboard (SPA) |
| `axioms/` | Axiom governance definitions |

---

## Principles

1. **LLMs prepare, humans deliver.** The system aggregates signals and surfaces patterns. It never makes people decisions for you. It never generates feedback language.
2. **Single operator, single machine.** No auth, no multi-user, no collaboration features. This constraint simplifies everything.
3. **Route through LiteLLM.** Universal observability. If a model call does not go through the proxy, it is invisible.
4. **Filesystem as bus.** DATA_DIR markdown files with YAML frontmatter are the state bus. The reactive engine watches for changes and cascades downstream actions.
5. **Evidence before assertions.** The system states epistemic confidence. "I don't know" is better than speculation.
