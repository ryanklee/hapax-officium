# Management Cockpit: Total Conversion Design

> **Purpose:** Convert the containerized Hapax system from a personal executive function platform with a management domain into a purpose-built management support system.

**Date:** 2026-03-06
**Status:** Design
**Scope:** Architecture, agents, logos API, frontend, axiom governance, Docker images, Claude Code configuration

---

## 1. The Conversion

### Current Shape

```
Personal executive function system (shell)
  ├── Management domain (subset — 2 agents, 1 collector, 1 axiom)
  ├── Infrastructure domain (health, introspect, scout, drift, knowledge_maint)
  ├── Knowledge domain (ingest, research, digest, profiler)
  ├── Music/creative domain (music-production rules, sample metadata)
  └── Executive function (cross-cutting — zero-config, proactive alerts, automation)
```

The management surface is a domain inside a personal system. The `management_governance` axiom constrains what the management domain can do. Most system components serve infrastructure monitoring, operator self-knowledge, or personal productivity.

### Target Shape

```
Management support system (the whole thing)
  ├── People state (team members, 1:1s, coaching, feedback, cognitive load)
  ├── Management preparation (1:1 prep, meeting lifecycle, weekly reviews)
  ├── Management self-awareness (manager's own patterns and tendencies)
  ├── Management briefing (team activity signals, goal momentum)
  ├── Demo (self-demoing capability)
  └── Safety boundary: LLMs prepare, humans deliver
```

Management stops being a domain inside a personal system. It becomes the system's reason for existing. Everything that doesn't serve management function is removed. The `management_governance` axiom's T0 blocks become the product's core safety specification.

### What This Is Not

This is not pruning personal features from a broader system. It is a **purpose inversion** — redefining what the system is for, then deriving what stays from that new purpose. Components are evaluated by one question: *would an engineering manager use this to manage their team better?*

---

## 2. Axiom Architecture

### Current Registry (4 axioms)

| Axiom | Weight | Scope | Type |
|-------|--------|-------|------|
| single_user | 100 | constitutional | hardcoded |
| executive_function | 95 | constitutional | hardcoded |
| corporate_boundary | 90 | domain: infrastructure | softcoded |
| management_governance | 85 | domain: management | softcoded |

### Converted Registry (3 active, 1 dormant)

#### `single_operator` (weight: 100, constitutional, hardcoded)

**Renamed from** `single_user`. Text change:

> This system is built for and operated by a single manager. All architectural decisions must respect and leverage that constraint. No multi-operator features, role management, sharing capabilities, or administrative interfaces.

**Rationale:** The constraint remains structurally identical — one person builds and operates this system. Removing the operator's name makes it a product design principle rather than a biographical fact. All T0 implications (su-auth-001 through su-admin-001) remain binding without modification.

**Preserved implications (T0):**
- su-auth-001: No identity management code
- su-privacy-001: No privacy controls or consent mechanisms
- su-security-001: No multi-tenant security or rate limiting
- su-feature-001: No collaboration or multi-operator features
- su-admin-001: No administrative interfaces or role assignment

#### `decision_support` (weight: 95, constitutional, hardcoded)

**Renamed from** `executive_function`. Text change:

> This system supports high-stakes people management decisions. The operator's time and attention are the scarcest resources. The system must minimize friction, surface actionable items proactively, automate routine preparation, and never require the operator to remember, check, or manually trigger what can be automated.

**Rationale:** The original axiom's implications (zero-config, proactive alerts, automation, error context, state persistence) are universally valuable and *more* critical for management than for development. Management decisions are high-cognitive-load, high-stakes work. The axiom is regrounded in decision support theory rather than personal neurodivergence.

Every implication from `executive_function` remains binding. The 5 T0 blocks are preserved verbatim:
- ex-init-001: Zero configuration beyond environment variables
- ex-err-001: Error messages include specific next actions
- ex-routine-001: Recurring tasks automated, not manual
- ex-attention-001: Critical alerts via external channels, not logs
- ex-alert-004: Proactive surfacing of actionable items
- ex-routine-007: Maintenance agents run autonomously on schedules

The 29 lighter implications (T1-T3) are preserved without change. They apply equally to management tooling.

#### `management_safety` (weight: 95, constitutional, hardcoded)

**Elevated from** `management_governance` (was: domain, softcoded, weight 85). Text change:

> This system aggregates signals and prepares context for the operator's relational work with their team. It never substitutes for human judgment in people decisions. LLMs prepare, humans deliver. The system surfaces patterns and open loops. It never generates feedback language, coaching hypotheses, or recommendations about individual team members.

**Rationale:** When management IS the system's purpose, this axiom is no longer a domain constraint — it's the product's safety specification. Elevated to constitutional scope and hardcoded type because:
1. The boundary "LLMs prepare, humans deliver" is the most important design decision in the system
2. Violating it would make the system actively harmful (AI-generated feedback language)
3. It should not be possible to soften or override this without constitutional amendment

Weight elevated to 95 (equal to decision_support) because both are equally foundational. The supremacy clause resolves conflicts: if decision_support says "automate routine tasks" and management_safety says "don't generate feedback language," management_safety wins for people-facing outputs.

**All implications preserved:**
- mg-boundary-001 (T0): Never generate feedback language, performance evaluations, or coaching recommendations
- mg-boundary-002 (T0): Never suggest what to say to a team member
- mg-cadence-001 (T1): 1:1 cadence is primary staleness signal
- mg-selfreport-001 (T1): Cognitive load from operator self-report only
- mg-deterministic-001 (T1): Management state collection fully deterministic, zero LLM calls
- mg-prep-001 (T2): Prep agents focus on signal aggregation, not recommendations
- mg-bridge-001 (T1): Work/home data boundary respected

#### `corporate_boundary` (weight: 90, domain, softcoded) — DORMANT

Status changed to `dormant`. The axiom applies to the Obsidian plugin operating across a corporate network boundary. The containerized management cockpit runs on the home network. If deployed to corporate devices in the future, this axiom reactivates.

No implications changed. Not enforced in hooks until reactivated.

### Axiom Enforcement Changes

**Current hooks scan for:** single_operator code patterns (class definitions for identity management, role scaffolding, multi-tenant infrastructure)

**Converted hooks add scanning for:** feedback language generation patterns for `management_safety` enforcement:

```
# mg-boundary-001: Feedback language generation
generate.*feedback
draft.*feedback
suggest.*to_say
FeedbackGenerator
CoachingRecommender
PerformanceReview
write.*evaluation
compose.*message.*team
recommend.*for.*person
```

The `axiom-scan.sh` PreToolUse hook adds these patterns. The existing single_operator patterns remain unchanged.

---

## 3. Agent Architecture

### Inventory: 14 → 5 agents + demo

| Agent | Current Function | Verdict | Rationale |
|-------|-----------------|---------|-----------|
| management_prep | 1:1 prep, team snapshots, overviews | **Keep** | Pure management. No change needed. |
| meeting_lifecycle | Cadence detection, extraction, weekly review | **Keep** | Pure management. No change needed. |
| briefing | Infrastructure telemetry + goal momentum | **Transform** | Strip infra. Add team activity signals. |
| profiler | Operator self-knowledge from dev behavior | **Transform** | Reframe as management self-awareness. |
| activity_analyzer | System telemetry + goal tracking | **Transform** | Strip system telemetry. Add team metrics. |
| demo | Audience-tailored presentations | **Keep** | Self-demoing requirement. |
| scout | Infrastructure component evaluation | **Remove** | No management function. |
| digest | Knowledge base content tracking | **Remove** | No management function. |
| knowledge_maint | Qdrant hygiene | **Remove** | Infrastructure only. |
| drift_detector | Doc/reality alignment | **Remove** | Infrastructure only. |
| code_review | LLM-powered code review | **Remove** | Developer tool. |
| research | RAG-powered research assistant | **Remove** | Generic utility. |
| health_monitor | Infrastructure health checks | **Reduce** | Keep only management system self-check. |
| introspect | System inventory manifest | **Remove** | Infrastructure only. |
| ingest | RAG ingestion pipeline | **Remove** | No management function. |

### Agent Transformations

#### briefing → management_briefing

**Current data sources:** Langfuse LLM usage, health history, drift status, service events, scout report, digest, goal momentum, intention-practice gaps.

**Converted data sources:**
- Team state from `management.py` collector (stale 1:1s, overdue coaching, high cognitive load, feedback follow-ups)
- Meeting cadence analysis (who's overdue, who's coming up)
- Coaching experiment status (which experiments need check-ins)
- Goal momentum (operator's management goals, not infrastructure goals)
- Management attention distribution (from 1:1 note recency and length patterns)

**Removed data sources:** Langfuse costs, health uptime, drift items, service events, scout findings, digest content.

**LLM synthesis prompt reframed:** "You are generating a morning management briefing. Surface patterns and open loops in the operator's people management work. CRITICAL: Do not generate feedback language, coaching recommendations, or suggestions for what to say to anyone."

#### profiler → management_profiler

**Current dimensions (14):** identity, technical_skills, music_production, hardware, software_preferences, communication_style, decision_patterns, philosophy, knowledge_domains, workflow, neurocognitive_profile, management_practice, team_leadership, relationships.

**Converted dimensions (6):**
- `management_practice` — how the operator manages (cadence habits, delegation patterns, meeting conduct)
- `team_leadership` — leadership style, growth orientation, risk tolerance in people decisions
- `decision_patterns` — speed, risk tolerance, information requirements before deciding
- `communication_style` — directness, feedback delivery patterns, written vs verbal preferences
- `attention_distribution` — which team members get more/less focus (from 1:1 frequency/length patterns)
- `self_awareness` — operator's stated vs actual management patterns (intention-practice gaps)

**Removed dimensions:** identity, technical_skills, music_production, hardware, software_preferences, philosophy, knowledge_domains, workflow, neurocognitive_profile, relationships.

**Data sources changed:**
- Remove: shell history, git commits, config files, Claude Code transcripts, platform exports
- Add: 1:1 note patterns (frequency, length, rescheduling), feedback delivery timing, decision logs, coaching experiment history, meeting note characteristics

**Safety constraint:** The profiler profiles *the operator's management behavior*, not team members. It answers "how do I tend to manage?" — never "how is Person X performing?" This is constrained by management_safety:
- mg-boundary-001 applies: profiler must not generate evaluations of team members
- Profiling team members' behavior would cross the line into performance assessment
- The system surfaces patterns in the *operator's* behavior only

#### activity_analyzer → management_activity

**Current function:** System telemetry (Langfuse calls, health runs, drift items, systemd journal) + goal momentum tracking.

**Converted function:**
- 1:1 completion rates over rolling windows (7d, 30d)
- Feedback delivery timing (days between observation and delivery)
- Coaching experiment check-in frequency
- Career conversation recency per team member
- Management goal momentum (operator's stated management goals)

**Removed:** All system telemetry (Langfuse, health, drift, systemd).

#### health_monitor → system_check

**Current function:** 15 checks across 9 groups (profiles, disk, queues, budget, capacity, qdrant, endpoints, secrets, axioms).

**Converted function:** Minimal self-check that the management system is running:
- Logos API responding
- Vault directory accessible and readable
- Qdrant reachable (if used for management data)
- LiteLLM reachable (for management_prep synthesis)

**Removed:** GPU checks, Docker container checks, systemd timer checks, disk usage, budget tracking, capacity planning, most endpoint checks.

### Demo Pipeline

The demo pipeline stays. It currently supports audience types including "leadership" and "team-member," which are directly management-relevant. The system should be able to explain itself.

**Audience types (4):** family, team-member, leadership, technical-peer. The "leadership" and "team-member" archetypes are directly management-relevant. Custom personas can be loaded via YAML overlay.

**Dependencies by output format:**
- `markdown-only`: No heavy deps. Produces Marp markdown + screenshots + diagrams. **Default for management cockpit.**
- `slides`: Adds Marp CLI (via npx) for PDF generation. Lightweight.
- `video`: Adds moviepy + ffmpeg. Heavy. Exclude from container image.
- TTS: Requires chatterbox service (:4123). Exclude from container image.

**Screenshot pipeline:** Requires playwright + running cockpit web. Can be included in container since cockpit web runs alongside. Known-good routes: `/` (dashboard), `/chat` (chat — will be removed), `/demos` (demo listing).

**Diagram rendering:** D2 CLI with Pillow fallback. Lightweight, keep.

**Chart rendering:** Matplotlib. Lightweight, keep.

**Recommendation:** Default to `--format markdown-only` in the management cockpit container. Produces ~5-15 MB output with no heavy dependencies. Screenshots work if cockpit web is running. PDF slides available via npx if node is present.

---

## 4. Logos API

### Current Surface (~30 endpoints across 6 route groups)

```
/api/health, /api/gpu, /api/briefing, /api/scout, /api/drift, /api/cost,
/api/goals, /api/readiness, /api/accommodations, /api/manual, /api/nudges,
/api/agents, /api/management, /api/profile/*, /api/chat/*, /api/copilot,
/api/agents/*/run, /api/accommodations/*
```

### Converted Surface (~12 endpoints)

#### Data Routes

| Endpoint | Source | Purpose |
|----------|--------|---------|
| `GET /api/team` | management.py collector | Team member states, 1:1 recency, cognitive load, coaching status |
| `GET /api/team/health` | team_health.py collector | Larson classification per team (innovating/repaying/treading/falling) |
| `GET /api/briefing` | management_briefing agent output | Morning management briefing |
| `GET /api/nudges` | nudges.py (management subset) | Stale 1:1s, overdue coaching, feedback follow-ups, high load, team state |
| `GET /api/goals` | operator.json (management goals only) | Management goal staleness |
| `GET /api/status` | system_check agent | Is the management system healthy? |

#### Agent Routes

| Endpoint | Purpose |
|----------|---------|
| `POST /api/agents/{name}/run` | Invoke management_prep, meeting_lifecycle, management_briefing, management_profiler, management_activity |
| `DELETE /api/agents/runs/current` | Cancel running agent |
| `GET /api/agents/runs/current` | Execution status |

#### Profile Routes (reframed)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/profile` | Management self-awareness dimensions |
| `GET /api/profile/{dimension}` | Facts for one management dimension |
| `POST /api/profile/correct` | Correct a management self-awareness fact |

#### Demo Routes

| Endpoint | Purpose |
|----------|---------|
| `GET /api/demos` | List available demos |
| `GET /api/demos/{id}` | Retrieve demo content |

#### Removed Endpoints

- `/api/health` — infrastructure (replaced by minimal `/api/status`)
- `/api/gpu` — infrastructure
- `/api/scout` — infrastructure
- `/api/drift` — infrastructure
- `/api/cost` — infrastructure/personal
- `/api/readiness` — personal executive function
- `/api/accommodations` — personal neurocognitive
- `/api/manual` — operations manual
- `/api/chat/*` — chat sessions + interview mode (personal discovery)
- `/api/copilot` — executive copilot (personal)
- `/api/profile/facts/pending`, `/api/profile/facts/flush` — interview pipeline (personal)

### Data Collectors

#### Keep (2)

- **management.py** — Vault scanner for PersonState, CoachingState, FeedbackState. Reads `10-work/people/` in Obsidian vault. 100% management. No change.
- **team_health.py** — Larson four-state classification from management.py output. 100% management. No change.

#### Transform (2)

- **nudges.py** — Currently mixes personal + management nudges. Remove personal nudge categories (health, briefing-age, readiness, profile, scout, drift, momentum, emergence, sufficiency). Keep management categories: stale 1:1s, overdue coaching, feedback follow-ups, high cognitive load, team falling-behind, career conversation staleness, growth vector gaps.
- **goals.py** — Currently tracks all operator goals. Reframe to track management-specific goals only. Filter by domain or tag.

#### Remove (10+)

health.py, gpu.py, infrastructure.py, briefing.py (replaced by management_briefing), scout.py, drift.py, cost.py, readiness.py, momentum.py, emergence.py, knowledge_sufficiency.py, accommodations.py

---

## 5. Frontend (cockpit-web)

### Current Layout

**Three pages:** Dashboard, Chat, Demos

**Dashboard:** CopilotBanner + MainPanel (NudgeList + AgentGrid + OutputPane) + Sidebar (12 panels)

**Sidebar panels (12):** health, vram, containers, briefing, readiness, goals, cost, scout, drift, management, accommodations, timers

### Converted Layout

**Two pages:** Dashboard, Demos

**Dashboard:** MainPanel (ManagementNudges + AgentGrid + OutputPane) + Sidebar (4 panels)

**Sidebar panels (4):**
1. **Team** (was: ManagementPanel) — people count, stale 1:1s, high cognitive load, coaching/feedback counts. Elevated to primary position.
2. **Briefing** (was: BriefingPanel) — management morning briefing. Reframed content.
3. **Goals** (was: GoalsPanel) — management goal staleness only.
4. **Status** (new, minimal) — is the management system running? Green/yellow/red dot.

**Removed panels (8):** health, vram, containers, readiness, cost, scout, drift, accommodations, timers

**Removed pages (1):** Chat (interview/chat is personal executive function)

**Kept pages (1):** Demos (self-demoing requirement)

**AgentGrid:** Shows 5 management agents + demo instead of 13+ agents.

**NudgeList:** Shows only management nudges (stale 1:1s, overdue coaching, feedback follow-ups, high load alerts, team state warnings).

**CopilotBanner:** Removed (personal executive function).

---

## 6. Shared Modules

### Keep (11)

| Module | Reason |
|--------|--------|
| config.py | Model aliases, LiteLLM/Qdrant clients, embedding, path constants |
| langfuse_client.py | Observability tracing for LLM calls |
| notify.py | Unified notifications (ntfy for management alerts) |
| vault_writer.py | Obsidian vault egress (management prep writes to vault) |
| vault_utils.py | YAML frontmatter parsing, vault helpers |
| management_bridge.py | Vault → management facts extraction |
| axiom_registry.py | Axiom governance engine |
| axiom_patterns.py | T0 violation pattern matching |
| axiom_precedents.py | Precedent database |
| axiom_tools.py | Axiom compliance tooling |
| cli.py | Shared CLI utilities |

### Transform (3)

| Module | Change |
|--------|--------|
| profile_store.py | Reduce to 6 management dimensions (from 14). Remove personal dimension support. |
| operator.py | Filter to management goals only. Remove non-management metadata. |
| context_tools.py | Keep (used by management_prep). Constraint categories narrowed to management-relevant. Profile search uses management dimensions only. Sufficiency lookup unchanged. |

### Remove (15)

health_analysis.py, health_history.py, health_correlator.py, incidents.py, alert_state.py, capacity.py, service_graph.py, service_tiers.py, threshold_tuner.py, sufficiency_probes.py, context_tools.py, email_utils.py, takeout/ and proton/ directories

Note: `transcript_parser.py` is kept — used by meeting_lifecycle.

---

## 7. Claude Code Configuration (hapax-system)

### Skills

| Skill | Verdict | Rationale |
|-------|---------|-----------|
| `/axiom-check` | **Keep, reframe** | Governance still applies — check converted axioms |
| `/axiom-review` | **Keep** | Review management precedents |
| `/weekly-review` | **Transform** | Aggregate team metrics, not infrastructure data |
| `/demo` | **Keep** | Self-demoing |
| `/briefing` | **Remove** | Becomes agent-only (management_briefing) |
| `/status` | **Remove** | Infrastructure monitoring |
| `/vram` | **Remove** | GPU monitoring |
| `/ingest` | **Remove** | RAG pipeline |
| `/studio` | **Remove** | Music production |
| `/deploy-check` | **Remove** | Developer workflow |
| `/axiom-sweep` | **Remove** | Code repo scanning (developer) |

### Agents

| Agent | Verdict | Rationale |
|-------|---------|-----------|
| operator-voice | **Remove** | Personal developer voice. No management analog without redesign. |
| convention-guard | **Remove** | Code convention enforcement. Developer tool. |
| infra-check | **Remove** | Infrastructure verification. |

### Rules

| Rule | Verdict | Rationale |
|------|---------|-----------|
| models.md | **Keep** | Model selection still applies |
| music-production.md | **Remove** | Personal/hobby |
| toolchain.md | **Remove** | Developer conventions |
| environment.md | **Remove** | Infrastructure environment |
| *management-context.md* | **Create** | Team boundaries, data policies, management safety constraints |

### Hooks

All 5 hooks redesigned:

| Hook | Current | Converted |
|------|---------|-----------|
| session-context.sh (SessionStart) | Load axiom count, branch, health, Docker, GPU | Load team state summary, stale 1:1 count, overdue items, axiom count |
| axiom-scan.sh (PreToolUse) | Scan for single_operator code patterns | Add feedback language generation patterns for management_safety |
| axiom-commit-scan.sh (PreToolUse) | Scan commits for T0 violations | Same patterns as axiom-scan.sh |
| axiom-audit.sh (PostToolUse) | Log tool usage to audit trail | Log tool usage + flag any people-data access |
| session-summary.sh (Stop) | Summarize axiom violations | Summarize management safety boundary status |

### MCP Servers

| Server | Verdict | Rationale |
|--------|---------|-----------|
| qdrant | **Keep if used** | Could store management precedents, team decision history |
| git | **Keep** | Decision/meeting history tracking |
| postgres | **Keep** | Query team/management data if stored |
| context7 | **Keep** | Library documentation lookup |
| memory | **Keep** | Persistent conversation memory |
| sequential-thinking | **Keep** | Structured reasoning |
| filesystem | **Keep** | File operations |
| playwright | **Remove** | Browser automation (dev/demo only) |
| tavily | **Remove** | Web search (scout dependency, removed) |
| docker | **Remove** | Container management (infrastructure) |
| desktop-commander | **Remove** | System command execution |

---

## 8. Docker Images

### Current (3 images)

| Image | Size | Purpose |
|-------|------|---------|
| hapax-agents | 3.53 GB | 14 agents + logos API |
| hapax-ingest | 12.7 GB | RAG ingestion (docling + watchdog) |
| hapax-dev | 2.03 GB | Interactive Claude Code |

### Converted (2 images)

| Image | Est. Size | Purpose |
|-------|-----------|---------|
| **management-cockpit** | ~1.2 GB | 5 agents + logos API + demo (HTML/markdown mode) |
| **management-dev** | ~1.5 GB | Claude Code with management-focused configuration |

**hapax-ingest removed entirely.** RAG pipeline has no management function.

**Size reduction rationale:**
- Fewer Python dependencies (no docling, no playwright, no moviepy, no chatterbox)
- Fewer agents (5 vs 14)
- Fewer shared modules (13 vs 28)
- Demo in lightweight mode (HTML/markdown only, no video rendering)

### Compose Service Changes

```yaml
services:
  management-cockpit:
    build:
      context: ../ai-agents
      dockerfile: Dockerfile
    ports:
      - "127.0.0.1:8051:8050"
    environment:
      - LITELLM_API_BASE=http://litellm:4000
      - LITELLM_API_KEY=${LITELLM_API_KEY}
      - QDRANT_URL=http://qdrant:6333
      - OLLAMA_URL=http://ollama:11434
      - LANGFUSE_HOST=http://langfuse:3000
      - NTFY_BASE_URL=http://ntfy:8090
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - AXIOMS_PATH=/app/axioms
    volumes:
      - management_data:/data
      - /path/to/obsidian/vault:/vault        # Read-write: management_prep writes 1:1 prep, meeting_lifecycle writes weekly reviews
      - ../axioms:/app/axioms:ro
    networks:
      - llm-stack
    profiles:
      - management
```

### Vault Mount

The management system reads team data from the Obsidian vault's `10-work/` directory and writes back to it:

**Reads from:**
- `10-work/people/*.md` — person notes with frontmatter (team, role, cadence, cognitive-load, etc.)
- `10-work/` (recursive) — coaching notes (type: coaching), feedback notes (type: feedback)
- `10-work/meetings/*.md` — meeting notes with dates and attendees

**Writes to:**
- `10-work/1on1-prep/{slug}-{date}.md` — generated 1:1 preparation documents
- `10-work/meetings/{date}-{slug}.md` — structured meeting notes from transcripts
- `10-work/coaching/{slug}.md` — coaching hypothesis starters (from meeting extraction)
- `10-work/feedback/{slug}.md` — feedback record starters (from meeting extraction)
- `10-work/decisions/{slug}.md` — decision starters (from meeting extraction)
- `30-system/weekly-reviews/{year}-W{week}.md` — weekly review pre-population
- `30-system/management-overview.md` — dashboard overview

The vault mount must be **read-write**. Obsidian Sync handles propagation to other devices.

---

## 9. Data Model Summary

### Input Data (from Obsidian vault)

The system reads structured markdown files with YAML frontmatter:

**Person notes** (`10-work/people/{name}.md`):
- Fields: team, role, cadence (weekly/biweekly/monthly), cognitive-load (1-5), growth-vector, feedback-style, relationship, career-goal-3y, current-gaps, skill-level, will-signal, team-type

**Coaching notes** (`10-work/people/{name}/coaching/`):
- Fields: hypothesis, status (testing/confirmed/retired), start-date, check-in-interval, last-check-in

**Feedback records** (`10-work/people/{name}/feedback/`):
- Fields: type (reinforcing/adjusting), status (pending/delivered/closed), observed-date, follow-up-date

**Meeting notes** (`10-work/people/{name}/meetings/`):
- Fields: date, type (1on1/team/sync), action-items, decisions, themes

### Computed State (deterministic, zero LLM)

**PersonState:** name, team, role, cadence, cognitive_load, growth_vector, feedback_style, last_1on1, days_since_1on1, stale_1on1, coaching_active, career_goal_3y, current_gaps, skill_level, will_signal, team_type

**CoachingState:** person, hypothesis, status, start_date, days_since_checkin, overdue

**FeedbackState:** person, type, status, observed_date, follow_up_date, days_until_followup, overdue

**TeamHealthSnapshot:** teams grouped by name, per-team avg cognitive load, stale 1:1 count, Larson state (innovating/repaying-debt/treading-water/falling-behind)

**ManagementNudge:** category (stale-1on1/overdue-coaching/feedback-followup/high-load/team-state/career-convo), priority (0-100), person/team name, actionable text, days_overdue

### Staleness Thresholds

| Signal | Threshold | Nudge Priority |
|--------|-----------|---------------|
| Weekly 1:1 stale | > 10 days since last | 70 (high) |
| Biweekly 1:1 stale | > 18 days since last | 70 (high) |
| Monthly 1:1 stale | > 40 days since last | 70 (high) |
| Coaching check-in overdue | past check-in-by date | 55 (medium) |
| Feedback follow-up overdue | past follow-up-by date | 65 (high) |
| High cognitive load | >= 4 on 1-5 scale | 60 (medium) |
| Team falling-behind (Larson) | avg load >= 4 OR > 50% stale 1:1s | 75 (high) |
| Team treading-water | moderate load, no active coaching | 55 (medium) |
| Career convo stale | > 180 days since last | 50 (medium) |
| No growth vector | growth_vector empty | 40 (medium) |

### LLM-Synthesized Outputs (bounded by management_safety)

**ManagementPrep:** signal aggregation for a specific person — patterns, open loops, state summary. Explicitly constrained: no feedback language, no coaching recommendations, no suggestions for what to say.

**ManagementBriefing:** morning synthesis of team state — who needs attention, what's overdue, goal momentum. Constrained: patterns and open loops only.

**ManagementProfile:** facts about the operator's own management patterns — not about team members.

---

## 10. What Gets Deleted

### Agents (9 removed)

- `agents/scout.py` + `agents/scout_components.py`
- `agents/digest.py`
- `agents/knowledge_maint.py`
- `agents/drift_detector.py`
- `agents/code_review.py`
- `agents/research.py`
- `agents/introspect.py`
- `agents/ingest.py`
- `agents/profiler_sources.py` (replaced by management-specific sources)

### Cockpit Collectors (10+ removed)

- `logos/data/health.py`
- `logos/data/gpu.py`
- `logos/data/infrastructure.py`
- `logos/data/scout.py`
- `logos/data/drift.py`
- `logos/data/cost.py`
- `logos/data/readiness.py`
- `logos/data/momentum.py`
- `logos/data/emergence.py`
- `logos/data/knowledge_sufficiency.py`
- `cockpit/accommodations.py`

### Cockpit Routes (4 route files removed/gutted)

- `logos/api/routes/chat.py` — entire file removed
- `logos/api/routes/profile.py` — gutted to 3 management-profile endpoints
- `logos/api/routes/copilot.py` — entire file removed
- `logos/api/routes/accommodations.py` — entire file removed

### Shared Modules (15 removed)

- `shared/health_analysis.py`, `health_history.py`, `health_correlator.py`
- `shared/incidents.py`, `alert_state.py`, `capacity.py`
- `shared/service_graph.py`, `service_tiers.py`, `threshold_tuner.py`
- `shared/sufficiency_probes.py`, `email_utils.py`
- `shared/takeout/`, `shared/proton/`
- `shared/interview.py` (if exists)

Note: `shared/transcript_parser.py` is **kept** — it is imported by meeting_lifecycle for VTT/SRT/speaker-labeled transcript parsing.

### Frontend Components (20+ removed)

- `components/sidebar/`: HealthPanel, VramPanel, ContainersPanel, CostPanel, ScoutPanel, DriftPanel, AccommodationPanel, TimersPanel, FreshnessPanel, HealthHistoryChart
- `components/dashboard/CopilotBanner.tsx`
- `components/chat/`: entire directory (ChatProvider, ChatInput, MessageList, AssistantMessage, UserMessage, SystemMessage, StreamingMessage, StatusBar, ToolCallMessage)
- `pages/ChatPage.tsx`
- `components/layout/ManualDrawer.tsx`
- `hooks/useInputHistory.ts`

### Claude Code Customizations (8 skills, 3 agents, 3 rules removed)

- Skills: briefing, status, vram, ingest, studio, deploy-check, axiom-sweep
- Agents: operator-voice, convention-guard, infra-check
- Rules: music-production.md, toolchain.md, environment.md

### Docker Image (1 removed)

- `hapax-ingest` image and all `Dockerfile.ingest` configuration

### Qdrant Collections (2 removed, 1 transformed)

- Remove: `samples` (music metadata), `documents` (RAG)
- Transform: `profile-facts` (reduce to 6 management dimensions)
- Keep: `claude-memory` (if used by Claude Code)

---

## 11. Migration Path

This conversion can be done in the containerization workspace without affecting the live system. The workspace already contains snapshots of all source code.

### Phase 1: Axiom Amendment

1. Update `axioms/registry.yaml` — rename axioms, change weights/scopes/types
2. Update `axioms/implications/` — rename files, add management_safety patterns
3. Update `axioms/precedents/seed/` — add conversion precedent documenting the decision
4. Update `hapax-system/hooks/scripts/axiom-scan.sh` — add feedback language patterns
5. Update `hapax-system/rules/` — remove personal rules, create management-context.md

### Phase 2: Agent Conversion

1. Transform `agents/briefing.py` → `agents/management_briefing.py`
2. Transform `agents/profiler.py` → `agents/management_profiler.py`
3. Transform `agents/activity_analyzer.py` → `agents/management_activity.py`
4. Reduce `agents/health_monitor.py` → `agents/system_check.py`
5. Delete removed agents
6. Update `agents/__init__.py` or module references

### Phase 3: Logos API

1. Transform `logos/data/nudges.py` — remove personal nudge categories
2. Transform `logos/data/goals.py` — management goals only
3. Remove personal collectors and routes
4. Update `logos/api/main.py` — remove personal route registrations
5. Update `logos/api/routes/data.py` — remove personal data endpoints

### Phase 4: Frontend

1. Remove Chat page and all chat components
2. Remove personal sidebar panels
3. Elevate ManagementPanel to primary sidebar position
4. Remove CopilotBanner
5. Update AgentGrid to show management agents only
6. Update Sidebar.tsx — 4 panels instead of 12

### Phase 5: Docker and Config

1. Update Dockerfile — fewer deps, renamed image
2. Remove Dockerfile.ingest
3. Update docker-compose.yml — management-cockpit service
4. Update Claude Code config (settings.json, mcp_servers.json, rules, skills)
5. Update entrypoint

### Phase 6: Cleanup

1. Delete removed source files
2. Update tests — remove tests for deleted components
3. Update CLAUDE.md for the new system purpose
4. Update pyproject.toml — remove unused dependencies

---

## 12. What Remains

After conversion, the system is:

**A containerized management cockpit** that reads your Obsidian vault, surfaces patterns in your team's state, prepares context for 1:1s and meetings, alerts you when things go stale, reflects your own management patterns back to you, and demos itself to stakeholders.

**5 agents:** management_prep, meeting_lifecycle, management_briefing, management_profiler, management_activity

**1 demo pipeline** (HTML/markdown mode)

**1 system check** (is the cockpit running?)

**~12 API endpoints** serving a React dashboard with 4 sidebar panels

**3 axioms** enforcing: single operator, decision support quality, management safety

**Core safety boundary:** LLMs prepare, humans deliver. The system never generates feedback language, coaching recommendations, or suggestions for what to say to team members.
