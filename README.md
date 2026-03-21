# hapax-officium

A management decision support system for a single engineering manager, designed to be forked and adapted to individual practice.

## Background

Engineering management involves substantial context processing: tracking 1:1 cadence across a team, maintaining context for each person's growth trajectory, remembering coaching follow-ups, noticing when feedback has gone stale, surfacing open loops before they become missed commitments. These tasks produce no deliverables, resist tooling (the state lives in the manager's head), and compound when neglected.

hapax-officium externalizes this work into infrastructure. 17 agents prepare context for 1:1s, generate morning briefings, track management practice patterns, surface stale conversations, and profile the operator's management self-awareness across 6 dimensions. A reactive engine watches the filesystem for changes and cascades downstream work — nudge recalculation, cache refresh, LLM synthesis — without operator intervention.

**Safety boundary.** LLMs prepare context; humans deliver words to other humans. The system does not generate feedback language, coaching recommendations, or evaluations of individual team members. This boundary is enforced as a constitutional axiom with commit-time hooks — structural enforcement at the point where code enters the repository, not a prompt instruction subject to context-pressure degradation.

## Design intent

This is a working system, not a SaaS product, framework, or library. Clone, seed with management data, and evolve. The synthetic demo corpus demonstrates data flow. Replace it with real team data and the system adapts. The architecture stays (filesystem-as-bus, reactive engine, axiom governance); the agents, nudge thresholds, and domain knowledge diverge per fork.

## Self-demonstrating capability

```bash
./scripts/bootstrap-demo.sh
```

This copies a synthetic seed corpus (3 teams, 8 people, full management state) into the data directory, creates Qdrant collections, runs deterministic agents in parallel, then chains LLM synthesis agents: profiler, briefing, digest, team snapshot. After approximately 2 minutes, the cockpit API serves live management state — nudges, team health scores, and briefings generated from the synthetic data.

The demo agent profiles the audience, generates a tailored demonstration against the live system, and the demo_eval agent critiques and iterates on the result. `system_check` runs health checks across core services, and `knowledge_maint` prunes the knowledge base for staleness and near-duplicates.

## Architecture

**Filesystem-as-bus.** All management state lives as markdown files with YAML frontmatter in `data/`. Person notes, meeting records, coaching hypotheses, feedback, OKRs, goals, incidents — human-readable, versioned by git. Agents read and write these files; the reactive engine watches via inotify. No message broker, no shared database, no RPC. Trades transactional consistency for debuggability (`cat`, `grep`, `git log`). At single-operator scale, the consistency trade-off has no practical cost. See [hapax-constitution](https://github.com/ryanklee/hapax-constitution) for the full architectural pattern.

**Reactive engine.** When files change, inotify fires, 12 rules evaluate, and phased actions execute — deterministic work first (unlimited concurrency), then LLM work (semaphore-bounded, max 2). Person note updated — nudges recalculate. Meeting transcript added — context refreshes. Coaching hypothesis written — the briefing regenerates. Self-trigger prevention ensures engine-written files do not create infinite loops.

**Nudges.** 9 collectors across 3 categories (people, goals, operational) generate prioritized attention signals delivered via push notification. Examples: "1:1 with Alex overdue by 3 weeks," "Coaching follow-up for Jordan pending," "Q1 OKR check-in window closes Friday." Category-slotted caps prevent any single domain from dominating (at most N people nudges, M goal nudges per cycle).

**Axiom governance.** Three constitutional axioms constrain the system:

| Axiom | Weight | Constraint |
|-------|--------|------------|
| `single_operator` | 100 | One user. No auth, no roles, no multi-user features. |
| `decision_support` | 95 | Zero-config agents. Actionable errors. Automated routines. |
| `management_safety` | 95 | No generated feedback language or coaching recommendations about individuals. |

Each axiom produces derived implications — concrete constraints enforced at graduated tiers: T0 blocks code from existing (commit hook), T1 requires operator review, T2 warns. Each implication carries an interpretive canon (textualist, purposivist, absurdity, or omitted-case) and a mode (prohibition or sufficiency). See [hapax-constitution](https://github.com/ryanklee/hapax-constitution) for the full governance architecture.

## Agents

| Agent | LLM | Purpose |
|-------|-----|---------|
| `management_prep` | Yes | 1:1 prep docs, team snapshots, management overviews |
| `meeting_lifecycle` | Yes | Meeting prep, transcript processing, weekly review |
| `management_briefing` | Yes | Morning briefing synthesized from management state |
| `management_profiler` | Yes | Management self-awareness profiling across 6 dimensions |
| `management_activity` | No | Practice metrics: 1:1 rates, feedback timing, coaching frequency |
| `digest` | Yes | Content and knowledge digest from Qdrant documents |
| `scout` | Yes | Horizon scanning for component fitness evaluation |
| `drift_detector` | Yes | Documentation drift detection and correction |
| `knowledge_maint` | No | Qdrant hygiene: stale pruning, near-duplicate detection |
| `introspect` | No | Infrastructure manifest snapshot |
| `ingest` | No | Document ingestion pipeline |
| `status_update` | Yes | Upward-facing status reports |
| `review_prep` | Yes | Performance review evidence aggregation |
| `demo` | Yes | Audience-tailored system demonstrations |
| `demo_eval` | Yes | Demo critique and iterative improvement |
| `simulator` | Yes | Temporal simulation of management scenarios |
| `system_check` | No | Health checks for core services |

```bash
uv run python -m agents.<name> [flags]
```

## Quick start

```bash
git clone git@github.com:ryanklee/hapax-officium.git
cd hapax-officium
uv sync

# Run tests (all mocked, no infrastructure needed)
uv run pytest tests/ -q

# Bootstrap the demo system (requires Qdrant, LiteLLM, Ollama)
./scripts/bootstrap-demo.sh

# Data pipeline only — no LLM calls, exercises collectors and nudges
./scripts/bootstrap-demo.sh --skip-llm

# Start the cockpit API
uv run python -m cockpit.api --host 127.0.0.1 --port 8050
```

## Infrastructure

The cockpit requires three services:

| Service | Purpose | Default |
|---------|---------|---------|
| Qdrant | Vector DB (768d nomic-embed-text) | localhost:6433 |
| LiteLLM | LLM gateway with model routing and tracing | localhost:4100 |
| Ollama | Local inference (embeddings, optional chat) | localhost:11434 |

## Project structure

```
hapax-officium/
├── agents/           17 agents + 2 agent packages (demo_pipeline, simulator_pipeline)
├── shared/           33 shared modules (config, data bridge, profile, axioms, frontmatter)
├── cockpit/          FastAPI API (32 endpoints) + 11 data collectors + reactive engine
├── data/             Management state directory — the filesystem bus (gitignored contents)
├── demo-data/        Synthetic seed corpus (checked in)
├── officium-web/     React SPA dashboard
├── vscode/           VS Code extension
├── axioms/           Governance axioms (registry + implications)
├── tests/            Test suite
└── docs/             Design documents and plans
```

## Part of the Hapax Research Project

Supporting software for a research project implementing Clark & Brennan's (1991) conversational grounding theory in a voice AI system. Extracted from hapax-council; shares governance architecture and infrastructure but not experiment code. See [hapax-council](https://github.com/ryanklee/hapax-council) for the research context.

| Repository | Role |
|-----------|------|
| [hapax-council](https://github.com/ryanklee/hapax-council) | Primary research artifact — voice daemon, grounding system, experiment infrastructure |
| [hapax-constitution](https://github.com/ryanklee/hapax-constitution) | Governance specification — axioms, implications, canons |
| **hapax-officium** (this repo) | Supporting software — management decision support |
| [hapax-watch](https://github.com/ryanklee/hapax-watch) | Research instrument — Wear OS biometric companion |
| [cockpit-mcp](https://github.com/ryanklee/cockpit-mcp) | Infrastructure — MCP server for Claude Code |

## License

Apache 2.0 — see [LICENSE](LICENSE).
