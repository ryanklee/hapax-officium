<!-- hapax-sdlc:preamble:begin -->

# hapax-officium

This repository is a constituent of the Hapax operating environment. It is not a product, not a service, and not seeking contributors. It is research infrastructure published as artifact.

Authorship is indeterminate by design: this codebase is co-produced by Hapax (the system itself), Claude Code, and the operator (OTO). Per the Hapax Manifesto, unsettled contribution is a feature of the work, not a concealment.

## What this is, not what it does

Constituent of the Hapax operating environment. Management decision-support apparatus for a single operator's professional practice. Filesystem-as-bus data model. Research infrastructure published as artifact.

## Constitutional position

- Single-operator system; no auth, no roles, no contributor onboarding (axiom: `single_user`)
- No issues, no discussions, no PRs accepted; refusal is the artifact (see `CONTRIBUTING.md`)
- License: PolyForm Strict 1.0.0 (source-available, non-distribution, non-modification)
- Citation: see `CITATION.cff`; archival DOI: see `.zenodo.json`

## Linked artifacts

- Manifesto: https://hapax.weblog.lol/hapax-manifesto-v0
- Refusal Brief: https://hapax.weblog.lol/refusal-brief
- Cohort Disparity Disclosure: https://hapax.weblog.lol/cohort-disparity-disclosure
- Constitution: https://github.com/ryanklee/hapax-constitution

## Inter-repo position

Management-domain runtime. Logos API on :8050. Consumes the constitution and the management_governance + management_safety domain axioms.

<!-- hapax-sdlc:preamble:end -->
<!-- hapax-sdlc:preamble:end -->


# hapax-officium

Supporting software for a research project implementing Clark & Brennan's (1991) conversational grounding theory in a production voice AI system. See [hapax-council](https://github.com/ryanklee/hapax-council) for the primary research artifact and experiment design.

## Role in the research project

This system was extracted from hapax-council when the management-domain agents proved independently usable. It serves two functions within the research project:

1. A second instantiation of the axiom governance architecture ([hapax-constitution](https://github.com/ryanklee/hapax-constitution)), demonstrating that the governance framework generalizes across domains. Council instantiates 5 axioms; officium instantiates 3, regrounded in management vocabulary (`single_operator`, `decision_support`, `management_safety`).

2. Operational infrastructure for the operator. 17 agents prepare context for 1:1s, generate briefings, track management practice patterns, and surface stale conversations. A reactive engine watches the filesystem and cascades downstream work without operator intervention.

The management safety axiom (`management_safety`, weight 95) enforces a structural boundary: LLMs prepare context; humans deliver words to other humans. The system does not generate feedback language, coaching recommendations, or evaluations of individual team members. This constraint is enforced at the commit boundary via T0 hooks.

## Architecture

**Filesystem-as-bus.** All management state lives as markdown files with YAML frontmatter in `data/`. Agents read and write these files; the reactive engine watches via inotify. See [hapax-constitution](https://github.com/ryanklee/hapax-constitution) for the architectural pattern specification.

**Reactive engine.** inotify watcher, 12 rules, phased execution (deterministic first, then LLM-bounded at max 2 concurrent). Person note updated, nudges recalculate. Meeting transcript added, briefing regenerates.

**Logos API.** FastAPI on `:8050`. 32 endpoints across 8 route groups.

## Agents

| Agent | LLM | Function |
|-------|-----|----------|
| `management_prep` | Yes | 1:1 prep, team snapshots, overviews |
| `meeting_lifecycle` | Yes | Meeting prep, transcript processing |
| `management_briefing` | Yes | Morning briefing from management state |
| `management_profiler` | Yes | Self-awareness profiling (6 dimensions) |
| `management_activity` | No | Practice metrics: 1:1 rates, feedback timing |
| `digest` | Yes | Knowledge digest from Qdrant |
| `scout` | Yes | Component fitness evaluation |
| `drift_detector` | Yes | Documentation drift detection |
| `knowledge_maint` | No | Qdrant hygiene |
| `ingest` | No | Document ingestion |
| `status_update` | Yes | Upward-facing status reports |
| `review_prep` | Yes | Performance review evidence |
| `demo` | Yes | System demonstrations |
| `demo_eval` | Yes | Demo critique and iteration |
| `simulator` | Yes | Temporal scenario simulation |
| `system_check` | No | Service health checks |
| `introspect` | No | Infrastructure manifest |

## Infrastructure

| Service | Default | Purpose |
|---------|---------|---------|
| Qdrant | localhost:6433 | Vector DB (768d nomic-embed) |
| LiteLLM | localhost:4100 | LLM gateway |
| Ollama | localhost:11434 | Local inference |

## Project structure

```
hapax-officium/
├── agents/           17 agents + demo_pipeline + simulator_pipeline
├── shared/           33 modules (config, data bridge, profile, axioms)
├── logos/             FastAPI API + reactive engine
├── data/              Management state (filesystem bus, gitignored)
├── demo-data/         Synthetic seed corpus
├── axioms/            Governance (3 active axioms)
├── tests/             Test suite
└── docs/              Design documents and plans
```

## Ecosystem

| Repository | Role |
|-----------|------|
| [hapax-council](https://github.com/ryanklee/hapax-council) | Primary research artifact — voice daemon, grounding system, experiment infrastructure |
| [hapax-constitution](https://github.com/ryanklee/hapax-constitution) | Governance specification — axioms, implications, canons, precedents |
| **hapax-officium** (this repo) | Supporting software — management decision support |
| [hapax-watch](https://github.com/ryanklee/hapax-watch) | Research instrument — Wear OS biometric companion |
| [hapax-mcp](https://github.com/ryanklee/hapax-mcp) | Infrastructure — MCP server for Claude Code |

## License

Apache 2.0 — see [LICENSE](LICENSE).
