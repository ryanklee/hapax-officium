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

Management-domain runtime. Logos API on `:8050`. Consumes the constitution and the management_governance + management_safety domain axioms.

<!-- hapax-sdlc:preamble:end -->

## Description

Management decision-support runtime extracted from [hapax-council](https://github.com/ryanklee/hapax-council) when the management-domain agents proved independently usable. Two roles within the workspace:

1. A second instantiation of the axiom-governance pattern from [hapax-constitution](https://github.com/ryanklee/hapax-constitution), regrounded in management vocabulary (`single_operator`, `decision_support`, `management_safety`).
2. Operational infrastructure for the operator's management practice: 17 agents prepare context for 1:1s, generate briefings, track practice patterns, and surface stale conversations. A reactive engine watches the filesystem and cascades downstream work.

The `management_safety` axiom (weight 95, constitutional) constrains output: the system does not generate feedback language, coaching recommendations, or evaluations of individual team members. LLMs prepare context; humans deliver words. T0 commit hooks enforce the constraint.

## Architecture

**Filesystem-as-bus.** All management state lives as markdown files with YAML frontmatter under `data/` (gitignored). Agents read and write these files; the reactive engine watches via inotify. The pattern is specified in [hapax-constitution](https://github.com/ryanklee/hapax-constitution).

**Reactive engine** (`logos/engine/`). inotify watcher with 200 ms debounce, 12 rules, two-phase execution: deterministic collectors first (parallel, ~2 s), then LLM phase bounded at max 2 concurrent. Person-note edits recompute nudges; meeting transcripts trigger briefing regeneration.

**Logos API.** FastAPI on `:8050`. 33 live endpoints across 8 route groups: `data`, `profile`, `agents`, `nudges`, `demos`, `engine`, `working_mode`, `scout`. The `/api/working-mode` endpoint is canonical; `/api/cycle-mode` is a deprecated alias kept during the migration window. Officium intentionally omits council's `fortress` mode (no studio surface).

**Profile store.** Qdrant collection `profile-facts` (768-dim, `nomic-embed-text-v2-moe`) indexes operator self-awareness facts across six management dimensions (see below).

## Agents

| Agent | LLM | Function |
|-------|-----|----------|
| `management_prep` | Yes | 1:1 prep, team snapshots, management overviews |
| `meeting_lifecycle` | Yes | Meeting prep automation, transcript processing |
| `management_briefing` | Yes | Morning briefing assembled from management state |
| `management_profiler` | Yes | Self-awareness profiling across 6 dimensions; runs daily |
| `management_activity` | No | Practice metrics from `data/`: 1:1 cadence, feedback timing |
| `digest` | Yes | Knowledge digest from Qdrant `documents` collection |
| `scout` | Yes | Component fitness horizon scan |
| `drift_detector` | Yes | Documentation drift detection |
| `knowledge_maint` | No | Qdrant hygiene: stale pruning, near-duplicate detection |
| `ingest` | No | Document ingestion pipeline |
| `status_update` | Yes | Upward-facing status reports |
| `review_prep` | Yes | Performance review evidence aggregation |
| `demo` | Yes | Audience-tailored system demonstrations |
| `demo_eval` | Yes | Demo evaluation and iterative improvement |
| `simulator` | Yes | Temporal simulation of management scenarios |
| `system_check` | No | Health checks for 3 core services |
| `introspect` | No | Infrastructure manifest snapshot |

## Six management dimensions

The `management_profiler` agent classifies extracted facts along six dimensions; the dimensions are also the search axes used by `ProfileStore` (`shared/profile_store.py`):

| Dimension | Scope |
|-----------|-------|
| `management_practice` | 1:1 structure, cadence, delegation, escalation handling |
| `team_leadership` | Team health, cognitive-load distribution, culture |
| `decision_patterns` | Framing, input collection, commitment, communication of decisions |
| `communication_style` | Voice, tone, information density across briefings and meetings |
| `attention_distribution` | Time and focus allocation across people, goals, incidents |
| `self_awareness` | Metacognition, blindspot tracking, feedback solicitation, adaptation |

The dimensions replace the 13-dimension scheme used in council (which spans health, audio, perception, etc.); officium scopes to management only.

## Axioms

`axioms/registry.yaml` defines 3 active axioms plus 1 dormant. Domain extensions of [hapax-constitution](https://github.com/ryanklee/hapax-constitution) are imported via the `hapax-sdlc[demo]` package.

| Axiom | Weight | Scope |
|-------|--------|-------|
| `single_operator` | 100 | constitutional |
| `decision_support` | 95 | constitutional |
| `management_safety` | 95 | constitutional |
| `corporate_boundary` | 90 | dormant / domain |

`management_safety` is the primary review focus during PR axiom-gate runs.

## Sister surfaces

The same logos API is reachable through three independent surfaces:

| Surface | Path | Default endpoint |
|---------|------|------------------|
| `officium-web` | `officium-web/` (React 19 + Vite + Tailwind) | `:5173` dev / production reverse proxy |
| VS Code extension | `vscode/` (TypeScript, esbuild) | `:8050` over HTTP |
| MCP server | `hapax-mcp` repo (`LOGOS_BASE_URL=http://localhost:8050/api`) | stdio transport to Claude Code |

The web app and the VS Code extension speak the same `:8050` API. There is no Tauri shell in this repo at present.

## Quick start

```bash
uv sync --all-extras
cd officium-web && pnpm install && cd ..
cd vscode && pnpm install && cd ..
docker compose up -d                   # LiteLLM, Qdrant, Ollama, optional Langfuse
./scripts/bootstrap-demo.sh            # Seed data/ from demo-data/ (synthetic)
uv run officium-api                    # API on :8050
```

The data directory is reseeded by `bootstrap-demo.sh`; pass `--skip-llm` for the deterministic-only pipeline. Tests: `uv run pytest tests/ -q`.

## Configuration

| Service | Default | Env var |
|---------|---------|---------|
| LiteLLM | `http://localhost:4100` | `LITELLM_API_BASE` |
| Qdrant | `http://localhost:6433` | `QDRANT_URL` |
| Ollama | `http://localhost:11534` | `OLLAMA_URL` |
| Data dir | `./data` | `HAPAX_DATA_DIR` |
| Reactive engine | enabled | `ENGINE_ENABLED`, `ENGINE_DEBOUNCE_MS` (200), `ENGINE_LLM_CONCURRENCY` (2), `ENGINE_DELIVERY_INTERVAL_S` (300), `ENGINE_ACTION_TIMEOUT_S` (60) |

The workspace-shared mode file at `~/.cache/hapax/working-mode` carries the operator's working mode (`research`/`rnd`); officium reads it and accepts the same values via `/api/working-mode`.

## Project layout

```
hapax-officium/
├── agents/             17 agents + demo_pipeline + simulator_pipeline
├── shared/             config, data bridge, profile store, axioms (33 modules)
├── logos/              FastAPI API + reactive engine
├── data/               Management state (gitignored, filesystem bus)
├── demo-data/          Synthetic seed corpus
├── officium-web/       React + Vite + Tailwind frontend
├── vscode/             VS Code extension (TypeScript)
├── axioms/             Governance (3 active + 1 dormant)
├── tests/              ~22k LOC across ~100 test files
└── docs/               Design documents and plans
```

## CI

| Workflow | Trigger | Effect |
|----------|---------|--------|
| `ci.yml` | push main, PR | ruff + pyright + pytest + web-build + vscode-build + gitleaks + bandit |
| `sdlc-triage.yml` | issue events | classify L/M/S complexity |
| `sdlc-implement.yml` | dispatch | LLM agent implementation on `agent/*` branches |
| `sdlc-review.yml` | PR ready | adversarial review (3 rounds, then human label) |
| `sdlc-axiom-gate.yml` | PR review approved | axiom compliance gate; auto-merge on pass |
| `claude-review.yml` | PR open / sync | Claude Code PR review |
| `auto-fix.yml` | CI failure | auto-fix attempts (3-attempt circuit breaker) |
| `codebase-map.yml` | nightly 04:00 UTC | regenerate `codebase-map.json` |
| `dependabot-auto-merge.yml` | Dependabot PR | auto-merge minor/patch bumps |

## Working-mode migration

`/api/cycle-mode` and the `cycle_mode_set` aliases are deprecated as of PR #66 (2026-04-13). `shared/cycle_mode.py` is a re-export shim emitting `DeprecationWarning`; `/api/working-mode` is canonical. The shim is slated for deletion per `hapax-council/docs/officium-design-language.md` §9.

## Ecosystem

| Repository | Role |
|-----------|------|
| [hapax-council](https://github.com/ryanklee/hapax-council) | Primary research artifact — voice daemon, grounding system, experiment infrastructure |
| [hapax-constitution](https://github.com/ryanklee/hapax-constitution) | Governance specification — axioms, implications, canons, precedents |
| **hapax-officium** (this repo) | Management decision support |
| [hapax-watch](https://github.com/ryanklee/hapax-watch) | Wear OS biometric companion |
| [hapax-phone](https://github.com/ryanklee/hapax-phone) | Android health + context companion |
| [hapax-mcp](https://github.com/ryanklee/hapax-mcp) | MCP server bridging the logos APIs to Claude Code |

## License

PolyForm Strict 1.0.0 — see [LICENSE](LICENSE).
