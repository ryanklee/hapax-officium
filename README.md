# hapax-officium

A management cockpit that demos itself — designed to be forked and grown into your own.

Engineering management is high-context, high-stakes work where dropping a thread means a person feels unseen. This system exists because the developer who built it has ADHD — and the cognitive overhead of tracking 1:1 cadence, coaching follow-ups, feedback staleness, and open loops across a team was consuming capacity that should go toward the actual relational work of management.

hapax-officium is a decision support system for a single engineering manager. 16 LLM-powered agents prepare context for 1:1s, generate morning briefings, track management practice patterns, surface stale conversations, and profile the operator's management self-awareness across 6 dimensions. A reactive engine watches the filesystem for changes and cascades downstream work — nudge recalculation, cache refresh, LLM synthesis — without being asked.

**The point is to fork it.** This isn't a SaaS product or a framework you integrate with. It's a working system you clone, seed with your own management data, and evolve. The synthetic demo corpus shows you how the data works. Replace it with your real team, your real 1:1 cadence, your real coaching patterns — and the system becomes yours. Every manager's practice is different; every fork should diverge. The architecture (filesystem-as-bus, reactive engine, axiom governance) stays; the agents, nudge thresholds, and domain knowledge grow in whatever direction your management practice needs.

**Safety principle:** LLMs prepare, humans deliver. The system never generates feedback language, coaching recommendations, or evaluations of individual team members. This boundary is a [constitutional axiom](https://github.com/ryanklee/hapax-constitution) enforced at commit time, not a prompt instruction.

## The self-demonstrating system

Most projects ask you to watch a screencast. This one bootstraps a live replica of itself and demos it to you.

```bash
./scripts/bootstrap-demo.sh
```

This copies a synthetic seed corpus (3 teams, 8 people, full management state) into the data directory, creates Qdrant collections, runs deterministic agents in parallel, then chains LLM synthesis agents: profiler → briefing → digest → team snapshot. After ~2 minutes, the cockpit API serves live management state — real nudges, real team health scores, real briefings generated from realistic synthetic data.

The demo agent goes further. It profiles the audience (who are you presenting to?), generates a tailored demonstration against the live system, and the demo_eval agent critiques and iterates on the result. The system doesn't just run — it explains itself, to whoever is asking, at their level.

The system also introspects. `introspect` snapshots its own infrastructure state. `health_monitor` checks itself every 15 minutes and auto-fixes what it can. `dev_story` queries its own development history — correlating git commits with Claude Code conversation transcripts to reconstruct why decisions were made. `knowledge_maint` prunes its own knowledge base for staleness and near-duplicates.

This isn't observability bolted on. Self-knowledge is the architecture.

## Quick start

```bash
git clone git@github.com:ryanklee/hapax-officium.git
cd hapax-officium
uv sync

# Run tests (all mocked, no infrastructure needed)
uv run pytest tests/ -q

# Bootstrap the demo system (requires Qdrant, LiteLLM, Ollama)
./scripts/bootstrap-demo.sh

# Or data pipeline only — no LLM calls, still exercises collectors and nudges
./scripts/bootstrap-demo.sh --skip-llm

# Start the cockpit API
uv run python -m cockpit.api --host 127.0.0.1 --port 8050
```

## How it works

**Filesystem-as-bus.** All management state lives as markdown files with YAML frontmatter in `data/`. Person notes, meeting records, coaching hypotheses, feedback, OKRs, goals, incidents — all human-readable, all versioned by git. Agents read and write these files. The reactive engine watches via inotify.

**Reactive engine.** When files change, 12 rules evaluate and produce phased actions: deterministic work first (unlimited concurrency), then LLM work (semaphore-bounded, max 2). A person note updated? Nudges recalculate. A meeting transcript dropped in? Context refreshes. A coaching hypothesis written? The briefing regenerates. No manual triggering.

**Nudges.** 9 collectors across 3 categories (people, goals, operational) generate attention-prioritized nudges. Category-slotted caps prevent any single domain from monopolizing the operator's attention. Delivered via push notification, not a dashboard that requires checking.

**Axiom governance.** Three constitutional axioms constrain the system:

| Axiom | Weight | What it means |
|-------|--------|--------------|
| single_operator | 100 | One user. No auth, no roles, no multi-user features. |
| decision_support | 95 | Zero-config agents. Actionable errors. Automated routines. |
| management_safety | 95 | Never generate feedback language or coaching recommendations about individuals. |

## Agents

| Agent | LLM? | What it does |
|-------|------|-------------|
| `management_prep` | Yes | 1:1 prep docs, team snapshots, management overviews |
| `meeting_lifecycle` | Yes | Meeting prep, transcript processing, weekly review |
| `management_briefing` | Yes | Morning management briefing from management data |
| `management_profiler` | Yes | Management self-awareness profiling (6 dimensions) |
| `management_activity` | No | Practice metrics: 1:1 rates, feedback timing, coaching frequency |
| `digest` | Yes | Content/knowledge digest from Qdrant documents |
| `scout` | Yes | Horizon scanning for component fitness evaluation |
| `drift_detector` | Yes | Documentation drift detection and correction |
| `knowledge_maint` | No | Qdrant hygiene: stale pruning, near-duplicate detection |
| `introspect` | No | Infrastructure manifest snapshot |
| `ingest` | No | Document ingestion pipeline |
| `status_update` | Yes | Upward-facing status reports |
| `review_prep` | Yes | Performance review evidence aggregation |
| `demo` | Yes | Audience-tailored system demonstrations |
| `demo_eval` | Yes | Demo evaluation and iterative improvement |
| `system_check` | No | Health checks for core services |

```bash
uv run python -m agents.<name> [flags]
```

## Project structure

```
hapax-officium/
├── agents/           16 agents + demo_pipeline package
├── shared/           20 shared modules (config, data bridge, profile, axioms, frontmatter)
├── cockpit/          FastAPI API (32 endpoints) + 11 data collectors + reactive engine
├── data/             Management data directory — the filesystem bus (gitignored contents)
├── demo-data/        Synthetic seed corpus (checked in — this is the demo's source material)
├── officium-web/     React SPA dashboard
├── vscode/           VS Code extension
├── axioms/           Governance axioms (registry + implications)
├── tests/            Test suite
└── docs/             Design documents and plans
```

## Infrastructure

The cockpit requires three services:

| Service | Purpose | Default |
|---------|---------|---------|
| Qdrant | Vector DB (768d, nomic-embed) | localhost:6333 |
| LiteLLM | LLM gateway (model routing + Langfuse tracing) | localhost:4000 |
| Ollama | Local inference (embeddings) | localhost:11434 |

## Related

A management-domain instantiation of the [hapax-constitution](https://github.com/ryanklee/hapax-constitution) pattern. See [hapax-council](https://github.com/ryanklee/hapax-council) for the full personal operating environment — 26+ agents, voice daemon, sync pipeline, and the same governance architecture at larger scale.

## License

Apache 2.0 — see [LICENSE](LICENSE).
