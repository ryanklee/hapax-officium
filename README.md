# hapax-officium

A management decision support system for a single engineering manager, designed to be forked and grown into your own practice.

## Problem

Engineering management is executive function work at scale. Tracking 1:1 cadence across a team, maintaining context for each person's growth trajectory, remembering coaching follow-ups, noticing when feedback has gone stale, surfacing open loops before they become dropped balls — these are context processing tasks that every manager performs and every manager struggles with as the team grows. They produce no deliverables, resist tooling (the state lives in the manager's head), and compound silently when neglected.

hapax-officium externalizes this work into infrastructure. 16 agents prepare context for 1:1s, generate morning briefings, track management practice patterns, surface stale conversations, and profile the operator's management self-awareness across 6 dimensions. A reactive engine watches the filesystem for changes and cascades downstream work — nudge recalculation, cache refresh, LLM synthesis — without being asked.

**Safety principle.** LLMs prepare context; humans deliver words to other humans. The system never generates feedback language, coaching recommendations, or evaluations of individual team members. This boundary is enforced as a constitutional axiom with commit-time hooks — structural enforcement, not a prompt instruction. The distinction matters: a prompt instruction degrades under context pressure; a commit hook blocks the code from existing.

## Design intent

This is not a SaaS product, a framework, or a library. It is a working system you clone, seed with your own management data, and evolve. The synthetic demo corpus shows how the data works. Replace it with your real team, your real 1:1 cadence, your real coaching patterns, and the system becomes yours. Every manager's practice is different; every fork should diverge. The architecture stays (filesystem-as-bus, reactive engine, axiom governance); the agents, nudge thresholds, and domain knowledge grow in whatever direction your practice needs.

## Self-demonstrating capability

```bash
./scripts/bootstrap-demo.sh
```

This copies a synthetic seed corpus (3 teams, 8 people, full management state) into the data directory, creates Qdrant collections, runs deterministic agents in parallel, then chains LLM synthesis agents: profiler, briefing, digest, team snapshot. After approximately 2 minutes, the cockpit API serves live management state — real nudges, real team health scores, real briefings generated from realistic synthetic data.

The demo agent profiles the audience (who are you presenting to?), generates a tailored demonstration against the live system, and the demo_eval agent critiques and iterates on the result.

The system also introspects: `health_monitor` checks itself every 15 minutes and auto-fixes what it can. `dev_story` queries its own development history, correlating git commits with Claude Code transcripts to reconstruct why decisions were made. `knowledge_maint` prunes its own knowledge base for staleness and near-duplicates.

## Architecture

**Filesystem-as-bus.** All management state lives as markdown files with YAML frontmatter in `data/`. Person notes, meeting records, coaching hypotheses, feedback, OKRs, goals, incidents — human-readable, versioned by git. Agents read and write these files. The reactive engine watches via inotify.

**Reactive engine.** When files change, 12 rules evaluate and produce phased actions: deterministic work first (unlimited concurrency), then LLM work (semaphore-bounded, max 2). Person note updated — nudges recalculate. Meeting transcript dropped in — context refreshes. Coaching hypothesis written — the briefing regenerates. No manual triggering.

**Nudges.** 9 collectors across 3 categories (people, goals, operational) generate attention-prioritized nudges. Category-slotted caps prevent any single domain from monopolizing the operator's attention budget. Delivered via push notification.

**Axiom governance.** Three constitutional axioms constrain the system:

| Axiom | Weight | Constraint |
|-------|--------|------------|
| `single_operator` | 100 | One user. No auth, no roles, no multi-user features. |
| `decision_support` | 95 | Zero-config agents. Actionable errors. Automated routines. |
| `management_safety` | 95 | Never generate feedback language or coaching recommendations about individuals. |

These axioms produce derived implications at graduated enforcement tiers (T0: block, T1: review, T2: warn), each classified by interpretive canon (textualist, purposivist, absurdity, omitted-case) and enforcement mode (prohibition or sufficiency). See [hapax-constitution](https://github.com/ryanklee/hapax-constitution) for the full governance architecture.

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
| Qdrant | Vector DB (768d nomic-embed-text) | localhost:6333 |
| LiteLLM | LLM gateway with model routing and tracing | localhost:4000 |
| Ollama | Local inference (embeddings, optional chat) | localhost:11434 |

## Project structure

```
hapax-officium/
├── agents/           16 agents + demo_pipeline package
├── shared/           25 shared modules (config, data bridge, profile, axioms, frontmatter)
├── cockpit/          FastAPI API (32 endpoints) + 11 data collectors + reactive engine
├── data/             Management state directory — the filesystem bus (gitignored contents)
├── demo-data/        Synthetic seed corpus (checked in)
├── officium-web/     React SPA dashboard
├── vscode/           VS Code extension
├── axioms/           Governance axioms (registry + implications)
├── tests/            Test suite
└── docs/             Design documents and plans
```

## Related

hapax-officium is a management-domain instantiation of the [hapax-constitution](https://github.com/ryanklee/hapax-constitution) pattern — a governance architecture for LLM agent systems using constitutional axioms, filesystem-as-bus coordination, and a reactive engine.

[hapax-council](https://github.com/ryanklee/hapax-council) is the full personal operating environment: 26+ agents, voice daemon, RAG sync pipeline, and the same governance architecture at broader scope.

## License

Apache 2.0 — see [LICENSE](LICENSE).
