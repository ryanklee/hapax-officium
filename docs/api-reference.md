# Logos API Reference

Logos REST API. Serves cached management data, agent execution,
nudge actions, profile inspection, demo management, reactive engine status,
cycle mode control, and scout decision tracking.

**Base URL:** `http://localhost:8050` (dev) / `http://localhost:8051` (Docker)

**Authentication:** None. Single-operator system.

**CORS:** Allows `localhost:5173` (Vite dev) and `localhost:8050`.

**Cache:** Data endpoints return an `X-Cache-Age` header (seconds since last refresh).

---

## Root

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | API identity and version |

Returns `{"name": "logos-api", "version": "0.2.0"}`.

---

## Data (tag: `data`)

Prefix: `/api`

All data endpoints return the latest cached collector results. Clients poll
at 5-minute cadence. Each response includes an `X-Cache-Age` header.

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/api/briefing` | Latest management briefing | Briefing object or null |
| GET | `/api/management` | Full management state (people, coaching, feedback, meetings, decisions) | Management dataclass as JSON |
| GET | `/api/nudges` | Active nudges across all categories | List of nudge objects |
| GET | `/api/goals` | Goal tracking data | List of goal objects |
| GET | `/api/agents` | Registered agent metadata | List of agent descriptors |
| GET | `/api/team/health` | Team health summary (Larson states) | Team health object |
| GET | `/api/okrs` | OKR tracking data (quarterly objectives + key results) | List of OKR objects |
| GET | `/api/smart-goals` | SMART goals (individual development goals) | List of SMART goal objects |
| GET | `/api/incidents` | Incident records | List of incident objects |
| GET | `/api/postmortem-actions` | Postmortem action items | List of action objects |
| GET | `/api/review-cycles` | Performance review cycle tracking | List of review cycle objects |
| GET | `/api/status-reports` | Status reports (weekly/monthly) | List of status report objects |
| GET | `/api/status` | Minimal health check | `{"healthy": true}` |

---

## Profile (tag: `profile`)

Prefix: `/api/profile`

Management self-awareness profile with 6 dimensions: `management_practice`,
`team_leadership`, `decision_patterns`, `communication_style`,
`attention_distribution`, `self_awareness`.

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/api/profile` | Summary of all dimensions with fact counts | `{dimensions, missing, total_facts, version, updated_at}` |
| GET | `/api/profile/{dimension}` | Facts for one dimension | `{name, summary, facts: [{key, value, confidence, source}]}` |
| POST | `/api/profile/correct` | Correct or delete a profile fact | `{status, result}` |

**POST /api/profile/correct** request body:

```json
{
  "dimension": "management_practice",
  "key": "meeting_cadence",
  "value": "weekly"
}
```

Set `value` to `"DELETE"` to remove a fact.

---

## Agents (tag: `agents`)

Prefix: `/api/agents`

Run agents as subprocesses with SSE streaming output. Only one agent can run
at a time.

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| POST | `/api/agents/{name}/run` | Start an agent (SSE stream) | SSE events: `output`, `done`, `error` |
| GET | `/api/agents/runs/current` | Status of running agent | `{running, agent_name?, pid?, elapsed_s?}` |
| DELETE | `/api/agents/runs/current` | Cancel running agent | `{status: "cancelled"}` |

**POST /api/agents/{name}/run** request body:

```json
{
  "flags": ["--person", "Sarah Chen"]
}
```

Returns a Server-Sent Events stream. Each SSE event has `event` (output/done/error)
and JSON `data`. Returns 409 if another agent is already running.

---

## Nudges (tag: `nudges`)

Prefix: `/api/nudges`

Act on or dismiss nudges. Nudges are identified by `source_id`.

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| POST | `/api/nudges/{source_id}/act` | Record that the operator executed a nudge | `{status, source_id, action}` |
| POST | `/api/nudges/{source_id}/dismiss` | Dismiss a nudge | `{status, source_id, action}` |

Returns 404 if the `source_id` does not match any cached nudge.

---

## Demos (tag: `demos`)

Prefix: `/api/demos`

Browse and manage generated demo outputs.

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/api/demos` | List all demos (newest first) | List of demo summary objects |
| GET | `/api/demos/{demo_id}` | Metadata and file listing for one demo | Demo detail object |
| GET | `/api/demos/{demo_id}/files/{file_path}` | Serve a file from demo output | File download |
| DELETE | `/api/demos/{demo_id}` | Delete a demo and all its files | `{deleted: "<demo_id>"}` |

---

## Engine (tag: `engine`)

Prefix: `/api/engine`

Reactive engine status. The engine watches DATA_DIR for filesystem changes
and evaluates 12 rules to cascade actions (cache refresh, nudge recalculation,
LLM synthesis, batched notifications).

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/api/engine/status` | Engine status summary | `{running, enabled, rules_count, pending_delivery}` |
| GET | `/api/engine/recent` | Recent delivery items | List of delivery item objects |
| GET | `/api/engine/rules` | Registered rule descriptions | List of rule description objects |

---

## Cycle Mode (tag: `system`)

Prefix: `/api`

Switch between `dev` (reduced timer frequencies) and `prod` scheduling modes.

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/api/cycle-mode` | Current mode and switch timestamp | `{mode: "dev"|"prod", switched_at}` |
| PUT | `/api/cycle-mode` | Switch mode (runs `hapax-mode` script) | `{mode, switched_at}` |

**PUT /api/cycle-mode** request body:

```json
{
  "mode": "dev"
}
```

---

## Scout (tag: `scout`)

Prefix: `/api`

Record and retrieve decisions on scout-surfaced component evaluations.

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| POST | `/api/scout/{component}/decide` | Record a decision on a component | `{component, decision, timestamp, notes}` |
| GET | `/api/scout/decisions` | List all recorded decisions | `{decisions: [...]}` |

**POST /api/scout/{component}/decide** request body:

```json
{
  "decision": "adopted",
  "notes": "Replacing current solution in Q2"
}
```

Valid `decision` values: `adopted`, `deferred`, `dismissed`.

---

## SPA Hosting

When `logos/api/static/` exists (built SPA), the server also serves:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/app/{path}` | SPA catch-all (returns index.html) |
| GET | `/static/{path}` | Static asset serving |

---

## Endpoint Summary

32 endpoints across 8 route groups:

| Group | Count | Prefix |
|-------|-------|--------|
| Data | 13 | `/api` |
| Profile | 3 | `/api/profile` |
| Agents | 3 | `/api/agents` |
| Nudges | 2 | `/api/nudges` |
| Demos | 4 | `/api/demos` |
| Engine | 3 | `/api/engine` |
| Cycle Mode | 2 | `/api` |
| Scout | 2 | `/api` |

---

## curl Examples

Health check:

```bash
curl http://localhost:8050/api/status
```

Get team health with cache age:

```bash
curl -v http://localhost:8050/api/team/health 2>&1 | grep -E '(X-Cache-Age|^\{)'
```

Get all nudges:

```bash
curl -s http://localhost:8050/api/nudges | jq '.[] | {source_id, category, summary}'
```

Management profile summary:

```bash
curl -s http://localhost:8050/api/profile | jq '{total_facts, dimensions: [.dimensions[].name]}'
```

Get facts for a specific dimension:

```bash
curl -s http://localhost:8050/api/profile/decision_patterns | jq '.facts'
```

Run an agent with SSE streaming:

```bash
curl -N http://localhost:8050/api/agents/management_prep/run \
  -H 'Content-Type: application/json' \
  -d '{"flags": ["--person", "Sarah Chen"]}'
```

Check if an agent is running:

```bash
curl http://localhost:8050/api/agents/runs/current
```

Dismiss a nudge:

```bash
curl -X POST http://localhost:8050/api/nudges/stale-1on1-marcus-johnson/dismiss
```

Switch to dev mode:

```bash
curl -X PUT http://localhost:8050/api/cycle-mode \
  -H 'Content-Type: application/json' \
  -d '{"mode": "dev"}'
```

Record a scout decision:

```bash
curl -X POST http://localhost:8050/api/scout/react-router/decide \
  -H 'Content-Type: application/json' \
  -d '{"decision": "deferred", "notes": "Revisit after v7 stable release"}'
```

List all demos:

```bash
curl -s http://localhost:8050/api/demos | jq '.[].id'
```

Engine status:

```bash
curl -s http://localhost:8050/api/engine/status | jq .
```
