# Data Architecture

This document describes the data storage topology, flow patterns, and lifecycle
for the management cockpit system. All claims are derived from code in
`shared/` and `cockpit/`.

## 1. Data Storage Topology

The system uses three storage systems with clearly separated responsibilities.

### Filesystem (DATA_DIR)

Markdown files with YAML frontmatter. This is the **source of truth** for all
management state. Default path: `data/`. Override via
`HAPAX_DATA_DIR` environment variable.

- Written by agents (`shared/vault_writer.py`), the operator (manual edits),
  and the ingest pipeline (`agents/ingest.py`).
- Read by collectors (`logos/data/*.py`) and the management bridge
  (`shared/management_bridge.py`).
- Watched by the reactive engine (`logos/engine/`) via inotify.

### Qdrant (Vector Database)

Derived and indexed data. Qdrant stores embeddings for semantic search; it is
never the source of truth. Connection configured via `QDRANT_URL` (default
`http://localhost:6433`). All vectors are 768-dimensional, embedded via
`nomic-embed-text-v2-moe` through Ollama.

### PostgreSQL

Used exclusively by Langfuse for LLM trace storage. No application data is
stored in PostgreSQL. The cockpit system does not read from or write to
PostgreSQL.

## 2. Filesystem-as-Bus Pattern

DATA_DIR functions as a state bus. The reactive loop works as follows:

```
 Writer (agent, operator, ingest)
   |
   v
 DATA_DIR  (markdown + YAML frontmatter)
   |
   | inotify (filesystem watcher, 200ms debounce)
   v
 Reactive Engine  (evaluates 12 rules against ChangeEvent)
   |
   v
 Action Plan  (phase 0: deterministic, phase 1+: LLM, semaphore=2)
   |
   v
 Collectors recompute  -->  ManagementSnapshot / Nudges
   |                              |
   v                              v
 LLM agents                 Logos API --> Dashboard
 (briefing, profiler)
   |
   v
 Qdrant (profile-facts)  +  DATA_DIR/references/ (generated artifacts)
```

**Self-trigger prevention:** Handlers that write back to DATA_DIR accept an
`ignore_fn` callable. Before each write, they call `ignore_fn(path)` so the
watcher suppresses the resulting filesystem event and avoids infinite loops.

**Phased execution:** The engine executor groups actions by phase number. Phase
0 actions (deterministic: cache refresh, file routing) run without concurrency
limits. Phase 1+ actions (LLM calls: meeting extraction, synthesis) run behind
a semaphore (`ENGINE_LLM_CONCURRENCY`, default 2).

**Batched delivery:** Notifications from completed actions are queued and
delivered at intervals (`ENGINE_DELIVERY_INTERVAL_S`, default 300 seconds).

## 3. Document Types

All documents are markdown files with `---`-delimited YAML frontmatter. The
`type` field in frontmatter identifies the document type. Parsing uses a single
canonical regex in `shared/frontmatter.py`.

### person

**Directory:** `people/`
**Key frontmatter fields:** `name`, `team`, `role`, `cadence` (weekly|biweekly|monthly), `status` (active|inactive), `cognitive-load` (low|moderate|medium|high|critical), `growth-vector`, `feedback-style`, `last-1on1` (ISO date), `coaching-active` (bool), `career-goal-3y`, `current-gaps`, `current-focus`, `last-career-convo` (ISO date), `team-type`, `interaction-mode`, `skill-level`, `will-signal`, `domains` (list), `relationship`
**Read by:** `logos/data/management.py` (PersonState), `logos/data/team_health.py` (TeamState), `shared/management_bridge.py` (profile facts)
**Nudges produced:** Stale 1:1 (priority 70), high cognitive load (priority 60), stale career conversation (priority 50, >180 days), missing growth vector (priority 40), team falling behind (priority 75, via team_health aggregation)
**Inactive filter:** Documents with `status: inactive` are excluded from all processing.

### coaching

**Directory:** `coaching/`
**Key frontmatter fields:** `title`, `person`, `status` (active|completed|abandoned), `check-in-by` (ISO date), `type: coaching`
**Read by:** `logos/data/management.py` (CoachingState), `shared/management_bridge.py`
**Nudges produced:** Overdue coaching check-in (priority 55, when `check-in-by` is past)

### feedback

**Directory:** `feedback/`
**Key frontmatter fields:** `title`, `person`, `direction` (given|received), `category` (growth|recognition|correction), `follow-up-by` (ISO date), `followed-up` (bool), `type: feedback`
**Read by:** `logos/data/management.py` (FeedbackState), `shared/management_bridge.py`
**Nudges produced:** Overdue feedback follow-up (priority 65, when `follow-up-by` is past and `followed-up` is false)

### meeting

**Directory:** `meetings/`
**Key frontmatter fields:** `title`, `date` (ISO date), `type: meeting`
**Read by:** `shared/management_bridge.py` (last 20 by filename, descending)
**Nudges produced:** None directly. Triggers `meeting_cascade` reactive rule which extracts decisions, coaching starters, and feedback records via LLM.

### decision

**Directory:** `decisions/`
**Key frontmatter fields:** `type: decision`, `date` (ISO date), `meeting_ref` (optional)
**Read by:** `shared/management_bridge.py` (not currently collected by cockpit/data)
**Nudges produced:** None. Triggers `decision_logged` reactive rule (cache refresh only).

### okr

**Directory:** `okrs/`
**Key frontmatter fields:** `objective`, `scope` (team|individual), `team`, `person`, `quarter`, `status` (active|scored|archived), `score`, `scored-at`, `key-results` (list of dicts with: `id`, `description`, `target`, `current`, `unit`, `direction`, `confidence` (0-1), `last-updated`)
**Read by:** `logos/data/okrs.py` (OKRState), `shared/management_bridge.py`
**Nudges produced:** At-risk KRs (priority 75, confidence < 0.5), stale KRs (priority 50, not updated in 14+ days)
**Archived filter:** Documents with `status: archived` are excluded from bridge facts.

### goal

**Directory:** `goals/`
**Key frontmatter fields:** `person`, `specific`, `status` (active|completed|abandoned), `framework` (smart), `category`, `created`, `target-date` (ISO date), `last-reviewed` (ISO date), `review-cadence` (monthly|quarterly), `linked-okr`, `measurable`, `achievable`, `relevant`, `time-bound`
**Read by:** `logos/data/smart_goals.py` (SmartGoalState), `shared/management_bridge.py`
**Nudges produced:** Overdue goal (priority 70, past `target-date`), review overdue (priority 45, monthly >35 days or quarterly >100 days since `last-reviewed`)

### incident

**Directory:** `incidents/`
**Key frontmatter fields:** `title`, `severity` (sev1|sev2|sev3), `status` (detected|mitigated|postmortem-complete|closed), `detected` (ISO datetime), `mitigated` (ISO datetime), `duration-minutes`, `impact`, `root-cause`, `owner`, `teams-affected` (list)
**Read by:** `logos/data/incidents.py` (IncidentState), `shared/management_bridge.py`
**Nudges produced:** Open incident (priority 90 for sev1, 80 otherwise), missing postmortem (priority 65, for closed sev1/sev2 without postmortem-complete status)

### postmortem-action

**Directory:** `postmortem-actions/`
**Key frontmatter fields:** `title`, `incident-ref`, `owner`, `status` (open|in-progress|completed|wont-fix), `priority` (low|medium|high), `due-date` (ISO date), `completed-date` (ISO date)
**Read by:** `logos/data/postmortem_actions.py` (PostmortemActionState), `shared/management_bridge.py`
**Nudges produced:** Overdue action (priority 70, past `due-date` while status is open or in-progress)

### review-cycle

**Directory:** `review-cycles/`
**Key frontmatter fields:** `person`, `cycle`, `status` (not-started|in-progress|calibration|complete), `self-assessment-due` (ISO date), `self-assessment-received` (bool), `peer-feedback-requested` (int), `peer-feedback-received` (int), `review-due` (ISO date), `calibration-date` (ISO date), `delivered` (bool)
**Read by:** `logos/data/review_cycles.py` (ReviewCycleState), `shared/management_bridge.py`
**Nudges produced:** Overdue review (priority 75, past `review-due` and not delivered), peer feedback gap (priority 55, requested > received)
**Note:** Tracks process state only, never review content (management safety axiom).

### status-report

**Directory:** `status-reports/`
**Key frontmatter fields:** `date` (ISO date), `cadence` (weekly|monthly|pi), `direction` (upward|lateral), `generated` (bool), `edited` (bool), `type: status-report`
**Read by:** `logos/data/status_reports.py` (StatusReportState)
**Nudges produced:** Status report overdue (priority 55, weekly >9 days stale, monthly >35 days, pi >80 days)

### Generated artifact types (references/)

These are output-only documents written by agents to `DATA_DIR/references/`,
`DATA_DIR/1on1-prep/`, `DATA_DIR/briefings/`, `DATA_DIR/status-updates/`, and
`DATA_DIR/review-prep/`. Types include `briefing`, `digest`, `nudges`, `goals`,
`prep`, `team-snapshot`, `overview`, `prompt`. They are not read by collectors
or the management bridge; they exist for operator consumption and API serving.

## 4. Data Flow Diagram

```
                    WRITES                                READS
                    ------                                -----

  Operator (manual edits)  --.
  meeting_lifecycle agent  --+--> DATA_DIR/
  ingest agent             --'    people/            --> management.py collector
  vault_writer.py          ---    coaching/           --> management.py collector
                                  feedback/           --> management.py collector
                                  meetings/           --> management_bridge.py
                                  decisions/          --> management_bridge.py
                                  okrs/               --> okrs.py collector
                                  goals/              --> smart_goals.py collector
                                  incidents/          --> incidents.py collector
                                  postmortem-actions/ --> postmortem_actions.py collector
                                  review-cycles/      --> review_cycles.py collector
                                  status-reports/     --> status_reports.py collector
                                       |
                                       | inotify
                                       v
                                  Reactive Engine (12 rules)
                                       |
                              +--------+--------+
                              |                 |
                         Phase 0            Phase 1+
                     (deterministic)      (LLM, sem=2)
                              |                 |
                       cache.refresh()    meeting extraction
                              |           briefing synthesis
                              v                 |
                       ManagementSnapshot       v
                       TeamHealthSnapshot   Qdrant (profile-facts)
                       OKRSnapshot          DATA_DIR/references/
                       SmartGoalSnapshot
                       IncidentSnapshot
                       PostmortemActionSnapshot
                       ReviewCycleSnapshot
                       StatusReportSnapshot
                              |
                              v
                       9 nudge collectors
                              |
                              v
                       Nudge list (category-slotted, cap=7)
                              |
                              v
                       Logos API (:8050) --> Dashboard
```

## 5. Qdrant Collections

Four collections, all using cosine distance with 768-dimensional vectors
(nomic-embed-text-v2-moe).

### profile-facts

**Purpose:** Semantic search over operator management profile facts (6
dimensions: management_practice, team_leadership, decision_patterns,
communication_style, attention_distribution, self_awareness).
**Written by:** `shared/profile_store.py` via `management_profiler` agent. Facts
are generated by `shared/management_bridge.py` from DATA_DIR, then embedded and
upserted with deterministic UUIDs (uuid5 from dimension+key).
**Read by:** `shared/profile_store.py` search method, consumed by context tools
for LLM agents (briefing, prep, demo).
**Lifecycle:** Full reindex on each profiler run. Stale points (dimension+key
pairs no longer in the profile) are cleaned up automatically.

### claude-memory

**Purpose:** Persistent conversational memory for Claude Code sessions.
**Written by:** Claude Code MCP memory server.
**Read by:** Claude Code MCP memory server.
**Lifecycle:** Managed externally by the MCP server.

### documents

**Purpose:** RAG document chunks for content retrieval. Payloads include
`source_service` and `source_platform` metadata.
**Written by:** Ingest agent, sync pipeline agents (gdrive, gmail, obsidian,
chrome, youtube, claude_code).
**Read by:** Digest agent, research agent, context tools.
**Lifecycle:** Knowledge maintenance agent runs weekly: prunes stale documents,
detects near-duplicates, reports collection statistics.

### axiom-precedents

**Purpose:** Governance precedent storage for axiom compliance decisions.
**Written by:** Axiom governance engine (`shared/axiom_*.py`) when precedents
are recorded.
**Read by:** Axiom governance engine for precedent-based reasoning.
**Lifecycle:** Grows monotonically. No automated pruning.

## 6. Data Lifecycle

### Entry

Data enters the system through three paths:

1. **Manual creation:** Operator creates or edits markdown files directly in
   DATA_DIR subdirectories.
2. **Agent output:** Agents write via `shared/vault_writer.py` (briefings,
   digests, prep docs, coaching starters, feedback starters, decision records).
3. **Inbox ingestion:** Files dropped into `DATA_DIR/inbox/` are classified by
   the ingest agent, routed to the appropriate subdirectory, and the original
   moved to `DATA_DIR/processed/`.

### Processing

When a file is written or modified, the reactive engine evaluates it against 12
rules. Each rule checks the subdirectory and event type (created/modified).
Matched rules produce an ActionPlan with phased actions:

- **Phase 0 (deterministic):** Cache refresh triggers all collectors to re-scan
  their respective DATA_DIR subdirectories and recompute snapshots, nudges, and
  team health.
- **Phase 1+ (LLM):** Meeting extraction, briefing synthesis, profile indexing.
  Throttled by semaphore (default concurrency 2).

### Staleness Thresholds

These thresholds are enforced by deterministic collectors and nudge producers.
No LLM calls are involved in staleness detection.

| Signal | Threshold | Nudge Priority |
|--------|-----------|----------------|
| Weekly 1:1 | 10 days | 70 (high) |
| Biweekly 1:1 | 17 days | 70 (high) |
| Monthly 1:1 | 35 days | 70 (high) |
| Default 1:1 (no cadence) | 14 days | 70 (high) |
| Coaching check-in | past `check-in-by` | 55 (medium) |
| Feedback follow-up | past `follow-up-by` | 65 (high) |
| Career conversation | 180 days | 50 (medium) |
| OKR key result update | 14 days | 50 (medium) |
| SMART goal target date | past `target-date` | 70 (high) |
| SMART goal review (monthly) | 35 days | 45 (medium) |
| SMART goal review (quarterly) | 100 days | 45 (medium) |
| Postmortem action due date | past `due-date` | 70 (high) |
| Review cycle due date | past `review-due` | 75 (high) |
| Status report (weekly) | 9 days | 55 (medium) |
| Status report (monthly) | 35 days | 55 (medium) |
| Status report (PI) | 80 days | 55 (medium) |

### Aging and Cleanup

- **Profile facts:** Fully reindexed on each profiler run; stale points are
  automatically deleted from Qdrant.
- **Documents collection:** Weekly knowledge maintenance agent prunes stale
  entries and deduplicates near-matches.
- **Filesystem:** No automatic deletion. Meeting files older than the 20-file
  window are excluded from bridge facts but remain on disk. Generated artifacts
  in `references/` accumulate indefinitely.
- **Axiom precedents:** Never pruned. Monotonically growing.
