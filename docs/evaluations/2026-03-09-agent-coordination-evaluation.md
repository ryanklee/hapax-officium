# Agent Coordination Systems Design Evaluation

**Date:** 2026-03-09
**Scope:** LLM agent coordination architecture in hapax-containerization
**System purpose:** Demo seed — produces fully-hydrated replicas with synthetic data for live system demonstrations

## Architecture Summary

The system follows a **filesystem-as-bus** pattern: agents produce markdown files with YAML frontmatter → a watchdog-based reactive engine detects changes → rules fire deterministic + LLM actions → results cascade through cache refresh → API serves dashboard. Systemd timers handle scheduled orchestration. All LLM calls route through LiteLLM for observability.

## Strengths

### 1. Clean separation of deterministic vs. LLM work

The phased executor runs cache refresh (phase 0, unlimited concurrency) before LLM synthesis (phase 1+, semaphore-bounded at 2). The system stays responsive even when LLM calls are slow or failing.

### 2. Self-trigger prevention

The watcher's `ignore_set` pattern — handlers register paths before writing, watcher skips for the debounce window — prevents the most dangerous failure mode in filesystem-as-bus architectures: infinite cascading re-evaluation.

### 3. Graceful degradation everywhere

Every LLM call is wrapped in try/except returning structurally valid fallback output. Every data collector independently catches exceptions. Partial failures don't cascade.

### 4. Single-writer safety

The single_operator axiom eliminates distributed consensus, conflict resolution, and multi-writer coordination. The filesystem is a perfectly adequate state bus for one writer.

### 5. Cognitive load management

The 7-nudge attention budget cap, priority-aware notification batching (critical=immediate, high=60s, medium/low=5min), and deterministic nudge scoring respect the operator's attention.

## Weaknesses & Risks

### 1. Three independent frontmatter regexes — silent divergence risk

`management_bridge.py:24`, `management.py:42`, and `watcher.py:31` all define `r"\A---\s*\n(.*?\n)---\s*\n?"` independently. If one changes, the others silently break. Should be a shared constant.

**Priority:** High (latent bug). **Status:** Fixed — extracted to `shared/frontmatter.py`.

### 2. No token budgets or cost controls

Only `drift_detector` uses `UsageLimits(request_limit=200)`. Every other agent has uncapped token usage. A malformed input (e.g., a very long meeting transcript) could burn significant API credits in a single `meeting_lifecycle` extraction call.

**Priority:** Medium. **Mitigation:** LiteLLM handles rate limiting but not cost capping.

### 3. Profile facts staleness is unbounded

Qdrant `profile-facts` collection is only updated when `management_profiler --auto` runs (every 6h). The management bridge reads DATA_DIR on every cache refresh (5min). Agents using semantic profile search can get facts up to 6 hours stale relative to what deterministic collectors see.

**Priority:** Low (facts change slowly).

### 4. Decisions are write-only dead storage

`vault_writer.create_decision_starter()` writes files to `DATA_DIR/decisions/`, and `_rule_decision_logged()` fires a cache refresh, but no collector reads decision files. The reactive rule is wasted work.

**Priority:** Low (feature gap, not bug).

### 5. Cache refresh is poll-based with a 5-minute window

Despite the reactive engine's filesystem watcher, the API cache also runs a 300s background refresh loop. The engine triggers cache refresh on changes, but if the engine is disabled or slow, the API can serve data up to 5 minutes stale.

**Priority:** Low (acceptable for management data).

### 6. No retry or backoff on LLM failures

The try/except pattern returns fallback output but never retries. For transient failures (network blip, LiteLLM restart, Ollama model loading), a single retry with exponential backoff would improve reliability.

**Priority:** Medium.

### 7. Scheduled agent ordering is fragile

`daily-briefing.service` declares `After=digest.service`, but no `Requires=` or `BindsTo=`. If digest fails, briefing still runs without fresh digest data. The After= is cosmetic ordering, not data dependency.

**Priority:** Low (briefing still produces useful output from management state).

## Design Questions

### Should the reactive engine replace timer-based scheduling?

Currently two orchestration mechanisms exist: systemd timers (external, cron-like) and the reactive engine (internal, event-driven). For data-change-responsive agents, the engine is correct. For periodic summary agents, timers are correct. But there's no unified visibility into "what ran, when, why" across both. A unified execution log would improve debuggability.

### Is the filesystem-as-bus the right abstraction long-term?

It works now because: single operator, low write volume, deterministic frontmatter parsing. Limitations: no transactional guarantees, no schema enforcement, the triple-regex problem. If the system grows more agents, consider SQLite. Counter-argument: markdown files are human-editable, which is a genuine feature for a management tool.

### What happens when LiteLLM is down?

All LLM agents fail simultaneously with no fallback. system_check detects this, but there's no circuit breaker — agents keep attempting and failing for the full 60s timeout. A circuit breaker that short-circuits to fallback after N consecutive failures would reduce wasted timeout budget.

## Coordination Topology

```
┌─────────────────────────────────────────────────────────────┐
│ Systemd Timers (scheduled orchestration)                    │
│  06:30 meeting-prep → 06:45 digest → 07:00 briefing        │
│  Every 6h: profiler    Weekly: scout, drift, knowledge-maint│
└──────────────┬──────────────────────────────────────────────┘
               │ subprocess via watchdog scripts
               ▼
┌─────────────────────────────────────────────────────────────┐
│ Agents (stateless per-invocation)                           │
│  LLM: prep, lifecycle, briefing, profiler, digest, scout,  │
│       drift_detector, status_update, review_prep, demo      │
│  No-LLM: activity, ingest, introspect, knowledge_maint,    │
│           system_check                                      │
│  All LLM calls → LiteLLM:4100 → Langfuse tracing           │
│  All use shared/config.py for clients, paths, models        │
└──────────┬───────────────────────┬──────────────────────────┘
           │ write DATA_DIR        │ write profiles/
           ▼                       ▼
┌──────────────────────┐  ┌──────────────────────┐
│ DATA_DIR (filesystem)│  │ profiles/ (JSON/YAML) │
│ people/ coaching/    │  │ briefing, digest,     │
│ feedback/ meetings/  │  │ operator-digest       │
│ decisions/ inbox/    │  └──────────┬────────────┘
└──────────┬───────────┘             │
           │ inotify                 │ file read
           ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Reactive Engine (event-driven orchestration)                │
│  Watcher (200ms debounce) → Rules → Phased Executor        │
│  Phase 0: cache refresh (unlimited)                         │
│  Phase 1+: LLM calls (semaphore=2, timeout=60s)            │
│  Delivery queue: critical=immediate, high=60s, batch=300s   │
└──────────────────────┬──────────────────────────────────────┘
                       │ cache refresh
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Logos API (:8050) — DataCache (300s refresh loop)         │
│  /api/management, /nudges, /briefing, /team/health, /agents │
│  /api/engine/status, /recent, /rules                        │
│  /api/agents/{name}/run (SSE streaming, single-agent lock)  │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ cockpit-web (:8052) — React SPA                             │
│  nginx reverse proxy → management-cockpit:8050              │
└─────────────────────────────────────────────────────────────┘
```

## State Domains

| Domain | Source of Truth | Freshness | Writers | Readers |
|--------|-----------------|-----------|---------|---------|
| People/Teams | DATA_DIR/people/*.md | 5min cache | agents, vault_writer | management.py, bridge |
| Coaching | DATA_DIR/coaching/*.md | 5min cache | agents, vault_writer | management.py, bridge |
| Feedback | DATA_DIR/feedback/*.md | 5min cache | agents, vault_writer | management.py, bridge |
| Profile Facts | Qdrant profile-facts | 6h (timer) | management_profiler | profile_store, agents |
| Briefing | profiles/management-briefing.json | 24h (timer) | management_briefing | cache, API |
| Nudges | Computed from ManagementSnapshot | 5min cache | (computed) | cache, API |
| Documents | Qdrant documents collection | On ingest | ingest, RAG pipeline | digest, demo |

## Verdict

Well-designed single-operator agent coordination system that makes the right tradeoffs for its constraints. The filesystem-as-bus pattern is appropriate for the write volume and human-editability requirements. The phased executor with bounded LLM concurrency is the most important architectural decision and it's done correctly. The main gaps are operational (no cost controls, no retry, fragile timer ordering) rather than architectural.
