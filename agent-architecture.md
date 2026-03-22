# Agent Architecture

> **Note:** This document is the canonical architecture reference. It was originally a design proposal and has been updated to reflect the current implemented state. For per-agent operational details, see `operations-manual.md` in this repo.

## Philosophy

Three tiers, one principle: Claude Code is the command center. Everything else is infrastructure it can invoke, inspect, and reconfigure.

### Internal fitness vs. external fitness

The self-regulation agents (system-check, drift-detector, introspect) evaluate the system against its own expectations: is it healthy, is it consistent, is it documented? This is **internal fitness** — necessary but insufficient.

**External fitness** asks a different question: given what exists in the wider landscape right now, is this still the right way to do things? Technology moves fast. The barrier to change is low. A component that was best-in-class six months ago may be obsolete today. The system must resist ossification by continuously evaluating itself against external alternatives — and when something better comes along with acceptable tradeoffs, adopt it, even if that means the operator's own workflows change.

This is the scout agent's purpose. Where the drift detector asks "does documentation match reality?", the scout asks "does reality match the frontier?" Every component is held loosely. Nothing is sacred except the principles:

- **Route through LiteLLM** — but if something better than LiteLLM emerges, replace it
- **Embed with nomic** — but if a better embedding model ships, switch
- **Build on Pydantic AI** — but if the framework falls behind, migrate
- **The scout itself** — if a better approach to horizon scanning exists, the scout should recommend its own replacement

```
┌──────────────────────────────────────────────────────┐
│                    TIER 1: INTERACTIVE                │
│               Claude Code (you ↔ Claude)             │
│          MCP servers · slash commands · hooks         │
│                  Full stack access                    │
│                                                      │
│          System Logos (web dashboard)                  │
│       FastAPI backend + React SPA frontend            │
│     `uv run logos` · `logos --once` (CLI)          │
├──────────────────────────────────────────────────────┤
│                  TIER 2: ON-DEMAND                    │
│            Pydantic AI agents invoked by              │
│          Claude Code or CLI or n8n trigger            │
│                                                      │
│  Implemented:                                        │
│    profiler         system-check    introspect      │
│    drift-detector   activity-analyzer briefing       │
│    scout            management-prep  meeting-lifecycle│
│    digest           knowledge-maint  ingest          │
│    status-update    review-prep      demo            │
│    simulator                                         │
├──────────────────────────────────────────────────────┤
│                TIER 3: AUTONOMOUS                     │
│         Always-running systemd services or           │
│          n8n scheduled workflows                     │
│                                                      │
│  rag-ingest       system-check timer                  │
│  knowledge-maint  briefing timer                     │
│  digest timer     scout timer                        │
└──────────────────────────────────────────────────────┘
         ▲               ▲               ▲
         │               │               │
    ┌────┴────┐   ┌──────┴──────┐  ┌─────┴─────┐
    │ Qdrant  │   │  LiteLLM    │  │ Langfuse   │
    │ memory  │   │  (all LLMs) │  │ (observe)  │
    └─────────┘   └─────────────┘  └───────────┘
```

## Tier 1: Interactive (Claude Code + System Logos + Extended Surfaces)

Claude Code is the primary interactive interface — full MCP access, slash commands, hooks, and direct agent invocation.

The **System Logos** is the operational dashboard, built as a **FastAPI API backend + React SPA frontend** (`officium-web`). It provides real-time health monitoring, agent status, nudge management, goal tracking, profile visibility, and briefing display.

- `uv run logos` launches the API server (default port 8050, Docker port 8051)
- `logos --once` produces a one-shot CLI snapshot for terminal use or piping
- The React frontend connects to the FastAPI backend and renders the dashboard in the browser

The logos API consumes data from system-check, briefing, scout, activity-analyzer, and profiler agents. Persistent state lives in `profiles/` (probes, decisions, facts).

### Extended Interactive Surfaces

> **Note:** The surfaces listed below are part of the wider Hapax system only, not part of hapax-officium. They are documented here for architectural context.

Beyond Claude Code and the Logos dashboard, the wider Hapax system includes additional LLM-enabled surfaces that route through LiteLLM for model access and Langfuse tracing. These are not agents — they are interaction points that make LLM availability ambient across the workstation.

| Surface | Tools | Purpose |
|---------|-------|---------|
| Shell LLM layer | mods, Fabric, llm plugins, shell functions | Pipe-based LLM access, NL-to-command, prompt patterns |
| Editor LLM layer | Continue.dev (VS Code) | Code completion, chat, inline edit via LiteLLM |
| Browser LLM layer | Lumos (Chrome) | Page RAG, summarization via Ollama |
| Voice input | Voxtype / faster-whisper | Push-to-talk STT feeding into existing surfaces |
| Desktop hotkeys | fuzzel + aichat + wl-copy | Selection transforms, prompt dialogs, model switching |

## Tier 2: On-Demand Agents (Pydantic AI)

These live in `agents/`. Each agent uses LiteLLM as its backend (never direct provider APIs) and logs to Langfuse.

### digest

**Trigger:** Daily 06:45 timer (`digest.timer`) or manual CLI.
**Function:** Aggregates recently-ingested RAG content + vault inbox items. LLM-synthesized content overview highlighting notable items, themes, and connections. Runs 15 minutes before briefing so the briefing agent can consume the digest.
**Model:** claude-sonnet (balanced) for synthesis.
**Output:** `profiles/digest.md` (readable), `profiles/digest.json` (structured), vault `30-system/digests/` (on `--save`).

### management-prep

**Trigger:** Manual CLI or Claude Code invocation before 1:1s or weekly reviews.
**Function:** Reads vault management data (people notes, coaching hypotheses, feedback records, meeting history) via `logos/data/management.py`, synthesizes context with one LLM call, writes preparation material to vault. Three modes: `--person "Name"` (1:1 prep), `--team-snapshot` (team state overview), `--overview` (condensed management summary).

**Boundary:** "LLM Prepares, Human Delivers." System prompt explicitly forbids drafting feedback language, generating coaching hypotheses, or suggesting what the operator should say. Focus is signal aggregation and context synthesis only.

**Model:** claude-sonnet (balanced) for prep/snapshot, claude-haiku (fast) for overview.
**Data sources:** People notes, meeting notes, coaching hypotheses, feedback records (all via `shared/management_bridge.py` reading DATA_DIR, and `logos/data/management.py`).
**Output:** Markdown written to DATA_DIR (`1on1-prep/`, `briefings/`). Also stdout/JSON.

### meeting-lifecycle

**Trigger:** Daily 06:30 timer (`meeting-prep.timer`), manual CLI, or Claude Code invocation.
**Function:** Automates meeting preparation, post-meeting processing, transcript ingestion, and weekly review. Four modes: `--prepare` (auto-generate 1:1 prep for due meetings), `--transcript FILE` (parse VTT/SRT/speaker-labeled transcripts, extract action items), `--weekly-review` (aggregate week's meeting data), `--process` (post-meeting action item extraction). Supports `--person` filter and `--dry-run`.

**Boundary:** Same as management-prep — signal aggregation only, no feedback language generation.

**Model:** claude-sonnet (balanced) for synthesis.
**Data sources:** Vault meeting notes, person notes, transcripts (via `shared/transcript_parser.py`).
**Output:** Prep docs to `10-work/1on1-prep/`, meeting summaries to vault, action items extracted to meeting notes.

### scout (horizon scanner)

**Trigger:** Weekly timer (Wednesday), or manual `uv run python -m agents.scout`.
**Function:** Evaluates external fitness of every stack component. Reads a component registry (`profiles/component-registry.yaml`) that maps each component to its role, constraints, and search strategies. For each component, performs web searches (Tavily API via urllib), collects alternatives and updates, then uses an LLM to evaluate findings against operator constraints and preferences. Produces a ranked report of recommendations.

**Recommendation tiers:**
- **Adopt**: Clear improvement, low effort, reversible. System should push toward this.
- **Evaluate**: Promising, needs deeper investigation or operator decision.
- **Monitor**: Too early or unclear tradeoffs, but worth tracking.

**Model:** claude-sonnet (via LiteLLM) for evaluation reasoning.
**Data sources:** Component registry, introspect manifest, Tavily web search.
**Output:** `profiles/scout-report.json` (structured) + `profiles/scout-report.md` (human-readable). Consumed by briefing agent on report day.

**Design principle:** The scout scans components, not architecture. Structural questions ("should we still use three tiers?") are too open-ended for automated weekly runs. Instead, the scout flags when component-level findings imply architectural shifts (e.g., "MCP now has native agent orchestration — flat orchestration may no longer be needed").

### profiler

**Trigger:** 12h timer (`profile-update.timer`), manual CLI, or `--auto` flag.
**Function:** Discovers operator data sources (config files, transcripts, shell history, git repos, Langfuse traces, Takeout structured facts, Proton Mail exports, vault management notes), extracts facts via LLM or deterministic bridges, curates into a structured 6-dimension profile (management_practice, team_leadership, decision_patterns, communication_style, attention_distribution, self_awareness). Supports interactive interview for directed discovery. `--auto` flow auto-loads pre-computed structured facts from Takeout and Proton bridges (zero LLM cost for those).
**Model:** claude-sonnet (balanced) for extraction.
**Output:** `profiles/operator.json` (structured), `profiles/operator.md` (readable). Profile injected into all agent system prompts via `shared/operator.py`.

### system-check

**Trigger:** Manual CLI or timer.
**Function:** Minimal health checks across core services (Qdrant, LiteLLM, Ollama, Docker containers, systemd timers). Zero LLM calls. Reports pass/fail per service with machine-readable JSON output.
**Model:** None (fully deterministic).
**Output:** JSON health report to stdout.

### introspect

**Trigger:** Weekly timer (`manifest-snapshot.timer`) or manual CLI.
**Function:** Deterministic infrastructure manifest generator. Enumerates Docker containers, systemd units, Qdrant collections, LiteLLM models, disk usage, network ports. Produces a complete snapshot of system state.
**Model:** None (fully deterministic).
**Output:** `profiles/manifest.json`

### drift-detector

**Trigger:** Weekly timer (`drift-detector.timer`) or manual CLI.
**Function:** Compares documentation (CLAUDE.md, README, architecture docs) against observed system reality. Uses LLM to identify discrepancies between what docs claim and what actually exists. `--fix` mode generates corrected doc fragments.
**Model:** claude-sonnet for comparison reasoning.
**Output:** `profiles/drift-report.json`, `profiles/drift-history.jsonl`

### activity-analyzer

**Trigger:** Manual CLI or consumed by briefing agent.
**Function:** Queries Langfuse traces, health history, drift history, systemd journal. Aggregates activity patterns, model usage, error rates, cost data. Zero LLM by default — pure data collection and aggregation. `--synthesize` flag adds an LLM-generated summary layer.
**Model:** None by default; claude-haiku (fast) for `--synthesize`.
**Output:** Activity data dict consumed by briefing agent, or standalone JSON/text report.

### briefing

**Trigger:** Daily 07:00 timer (`daily-briefing.timer`) or manual CLI.
**Function:** Consumes activity data (from activity-analyzer) + live health snapshot + scout report (when present). LLM-synthesized actionable morning briefing with priorities, action items, and system status. Integrates nudges and goal staleness.
**Model:** claude-sonnet for synthesis.
**Output:** `profiles/briefing.md` + vault `30-system/briefings/` (on `--save`) + ntfy notification.

### ingest (document ingestion)

**Trigger:** Manual CLI, watch mode (daemon), or one-shot invocation.
**Function:** Ingests management documents (markdown with YAML frontmatter) into the local data directory (`DATA_DIR`). Supports watch mode for continuous ingestion from a source directory and one-shot mode for individual files. Deterministic — no LLM calls.
**Model:** None (fully deterministic).
**Output:** Files written to `data/` subdirectories based on document type.

### status-update

**Trigger:** Manual CLI or Claude Code invocation.
**Function:** Generates upward-facing status reports from management data. Reads team state, recent meeting notes, and activity metrics from `DATA_DIR`, synthesizes into a structured status update suitable for skip-level or leadership consumption.
**Model:** claude-sonnet (balanced) for synthesis.
**Output:** Markdown status report written to `data/status-updates/`.

### review-prep

**Trigger:** Manual CLI or Claude Code invocation before performance review cycles.
**Function:** Aggregates evidence for performance reviews from management data. Reads person notes, meeting history, coaching hypotheses, and feedback records from `DATA_DIR`. Synthesizes a chronological evidence summary organized by theme.

**Boundary:** Same as management-prep — evidence aggregation only, no evaluative language or ratings.

**Model:** claude-sonnet (balanced) for synthesis.
**Output:** Markdown evidence document written to `data/review-prep/`.

## Tier 3: Autonomous Agents (systemd + n8n)

### rag-ingest (systemd user service)

**Behavior:** Watches a configured source directory via inotify/watchdog. New files → Docling extraction → chunk → nomic-embed-text → Qdrant `documents` collection. Handles PDF, DOCX, MD, HTML, TXT.

### system-check timer (systemd timer)

**Behavior:** Periodic invocation of the system-check agent (Tier 2). Runs deterministic checks across core services, reports results.
**Service:** `~/.config/systemd/user/system-check.timer`

### knowledge-maint (systemd timer)

**Behavior:** Weekly (Sunday 04:30). Deduplicates Qdrant vectors (cosine similarity > 0.98). Prunes stale entries from deleted source files. Validates embedding dimensions (768d). Reports stats with error counts. Dry-run by default, `--apply` for deletions. Optional `--summarize` for LLM summary.
**Service:** `~/.config/systemd/user/knowledge-maint.timer` + `knowledge-maint.service`

## Reactive Engine

The logos API process includes a reactive engine (`logos/engine/`) that watches `DATA_DIR` for filesystem changes and automatically cascades downstream work.

### Architecture

```
ChangeEvent (watchdog/inotify) → RuleRegistry → ActionPlan → PhasedExecutor → DeliveryQueue
```

- **Watcher** (`watcher.py`): watchdog inotify on `DATA_DIR`, 200ms debounce per path, self-trigger prevention via ignore set, frontmatter enrichment for `doc_type`
- **Rules** (`rules.py` + `reactive_rules.py`): Pure functions `ChangeEvent → list[Action]`. 12 rules: inbox_ingest, meeting_cascade, person_changed, coaching_changed, feedback_changed, decision_logged, okr_changed, smart_goal_changed, incident_changed, postmortem_action_changed, review_cycle_changed, status_report_changed
- **Executor** (`executor.py`): Phased async execution — Phase 0 (deterministic, fast), Phase 1 (LLM synthesis, bounded concurrency via semaphore), Phase 2 (delivery). Failed actions don't abort the plan; dependents are skipped.
- **Delivery** (`delivery.py`): Batched notification queue. Critical → immediate, High → 60s, Medium → 5min batch, Low → suppressed. Ring buffer of last 50 items for API.

### Configuration (env vars)

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENGINE_ENABLED` | `true` | Kill switch |
| `ENGINE_DEBOUNCE_MS` | `200` | Watcher debounce window |
| `ENGINE_LLM_CONCURRENCY` | `2` | Max simultaneous LLM calls |
| `ENGINE_DELIVERY_INTERVAL_S` | `300` | Batch notification interval |
| `ENGINE_ACTION_TIMEOUT_S` | `60` | Per-action LLM timeout |

### API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/engine/status` | Running/stopped, watcher active, pending actions |
| `GET /api/engine/recent` | Last 50 delivery items |
| `GET /api/engine/rules` | Registered rules and descriptions |

## Implementation Status

17 agents are implemented. All agents are within the management domain; no planned agents remain outside it.

All Tier 3 services are running as systemd timers (not n8n). n8n is used for notification workflows (briefing-push, health-relay, nudge-digest, quick-capture) but not for agent scheduling.

## Shared Infrastructure

All Tier 2 agents share:

```python
# shared/config.py
import os

LITELLM_BASE = os.getenv("LITELLM_BASE_URL", "http://localhost:4100")
LITELLM_KEY = os.getenv("LITELLM_API_KEY")
QDRANT_URL = "http://localhost:6433"
LANGFUSE_HOST = "http://localhost:3100"

# Standard model aliases — agents reference these, not raw model IDs
MODELS = {
    "fast": "claude-haiku",        # cheap, quick tasks
    "balanced": "claude-sonnet",   # default for most agents
    "reasoning": "deepseek-r1:14b",# complex reasoning via Ollama
    "coding": "qwen-coder-32b",   # code generation via Ollama
    "embedding": "nomic-embed",    # vector embeddings
    "local-fast": "qwen-7b",      # offline/privacy tasks
}
```

All agents emit OpenTelemetry traces to Langfuse. All use Qdrant for memory. All route model calls through LiteLLM. No agent calls a provider directly.

## Claude Code Integration Pattern

Claude Code invokes Tier 2 agents via shell:

```bash
uv run python -m agents.management_prep --person "Sarah Chen"
uv run python -m agents.management_briefing --save
uv run python -m agents.management_activity --json
```
Results flow back through stdout, files, or Qdrant queries.

## DATA_DIR as Operational Surface

The logos system uses `data/` (DATA_DIR) as its primary data store. All management state is represented as markdown files with YAML frontmatter, organized by document type into subdirectories.

**Data flows:**
- **Agents → DATA_DIR:** `vault_writer.py` writes briefings, prep docs, status updates to `data/` subdirectories
- **DATA_DIR → Agents:** `management_bridge.py` reads people notes, meeting notes, coaching, feedback, decisions, OKRs, goals, incidents, postmortem actions, review cycles, and status reports from DATA_DIR
- **DATA_DIR → Reactive Engine:** The filesystem watcher monitors DATA_DIR for changes and triggers downstream cascades (cache refresh, nudge recalculation, LLM synthesis)

**Key integration points:**
- `briefing.py --save` writes to `data/briefings/`
- Nudge collectors read team state from DATA_DIR to generate people, goals, and operational nudges
- Profiler reads management data from DATA_DIR for operator profile updates
- Demo seed corpus (`demo-data/`) is copied into `data/` during bootstrap

## Design Decisions (Resolved)

1. **Agent-to-agent communication:** No — flat orchestration. Claude Code orchestrates, agents never invoke each other. This avoids cascading failures and keeps the call graph auditable.

2. **State management:** Agents are stateless per-invocation. All persistent state lives in Qdrant, filesystem (`profiles/`), or cache (`profiles/`). This works well for the current 15-agent roster.

3. **Cost controls:** LiteLLM fallback chains provide implicit cost control (expensive model fails → cheaper model). Langfuse traces all calls for cost visibility. High-frequency Tier 3 tasks (system-check, knowledge-maint) use zero LLM by default.

4. **Adoption automation:** Operator confirms all adopt recommendations. No auto-apply.
