# hapax-officium

A management decision support system for a single engineering manager, designed to be forked and grown into your own practice.

## Problem

Engineering management is executive function work at scale. Tracking 1:1 cadence across a team, maintaining context for each person's growth trajectory, remembering coaching follow-ups, noticing when feedback has gone stale, surfacing open loops before they become dropped balls — these are context processing tasks that every manager performs and every manager struggles with as the team grows. They produce no deliverables, resist tooling (the state lives in the manager's head), and compound silently when neglected.

hapax-officium externalizes this work into infrastructure. 16 agents prepare context for 1:1s, generate morning briefings, track management practice patterns, surface stale conversations, and profile the operator's management self-awareness across 6 dimensions. A reactive engine watches the filesystem for changes and cascades downstream work — nudge recalculation, cache refresh, LLM synthesis — without being asked.

**Safety principle.** LLMs prepare context; humans deliver words to other humans. The system never generates feedback language, coaching recommendations, or evaluations of individual team members. This boundary is enforced as a constitutional axiom with commit-time hooks — structural enforcement, not a prompt instruction.

A prompt instruction ("never generate feedback about individuals") degrades under context pressure — long conversations, complex queries, and tool-heavy interactions erode instruction-following. A commit-time hook blocks code that contains feedback-generation patterns from existing in the repository. The enforcement layer is where code enters the system, not where the LLM interprets instructions.

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

**Filesystem-as-bus.** All management state lives as markdown files with YAML frontmatter in `data/`. Person notes, meeting records, coaching hypotheses, feedback, OKRs, goals, incidents — human-readable, versioned by git. Agents read and write these files; the reactive engine watches via inotify. No message broker, no shared database, no RPC. Agents coordinate by producing and consuming files. Trades transactional consistency for debuggability (`cat`, `grep`, `git log`). At single-operator scale, the consistency trade-off has no practical cost. See [hapax-constitution](https://github.com/ryanklee/hapax-constitution) for the full rationale.

**Reactive engine.** When files change, inotify fires, 12 rules evaluate, and phased actions execute — deterministic work first (unlimited concurrency), then LLM work (semaphore-bounded, max 2). Person note updated — nudges recalculate. Meeting transcript added — context refreshes. Coaching hypothesis written — the briefing regenerates. Self-trigger prevention ensures engine-written files don't create infinite loops. No manual triggering required.

**Nudges.** 9 collectors across 3 categories (people, goals, operational) generate prioritized attention signals delivered via push notification. Examples: "1:1 with Alex overdue by 3 weeks," "Coaching follow-up for Jordan pending," "Q1 OKR check-in window closes Friday." Category-slotted caps prevent any single domain from dominating (at most N people nudges, M goal nudges per cycle).

**Axiom governance.** Three constitutional axioms constrain the system:

| Axiom | Weight | Constraint |
|-------|--------|------------|
| `single_operator` | 100 | One user. No auth, no roles, no multi-user features. |
| `decision_support` | 95 | Zero-config agents. Actionable errors. Automated routines. |
| `management_safety` | 95 | Never generate feedback language or coaching recommendations about individuals. |

Each axiom produces derived implications — concrete constraints like "error messages must include a next action" or "never store individual performance ratings." These are enforced at graduated tiers: T0 blocks code from existing (commit hook), T1 requires operator review, T2 warns. Each implication carries an interpretive canon (how to apply it to unforeseen cases — textualist, purposivist, absurdity, or omitted-case) and a mode (prohibition: must NOT do this; sufficiency: MUST do this). See [hapax-constitution](https://github.com/ryanklee/hapax-constitution) for the full governance architecture.

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

## Ecosystem

Three repositories compose the hapax system:

- **[hapax-constitution](https://github.com/ryanklee/hapax-constitution)** — The pattern specification. Defines the governance architecture: axioms, implications, interpretive canon, sufficiency probes, precedent store, filesystem-as-bus, reactive engine, three-tier agent model.
- **[hapax-council](https://github.com/ryanklee/hapax-council)** — Personal operating environment. 26+ agents, voice daemon, RAG pipeline, reactive cockpit. Officium was extracted from council.
- **hapax-officium** (this repo) — Management-domain extraction. Designed to be forked by engineering managers. Same architecture, scoped to management support.

The three repos share infrastructure (Qdrant, LiteLLM, Ollama, PostgreSQL) but not code. The constitution constrains both implementations; the code is independent.

## License

Apache 2.0 — see [LICENSE](LICENSE).
