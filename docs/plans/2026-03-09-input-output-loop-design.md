# Input→Output Loop Design: Management Cockpit Data Architecture

## Goal

Replace the excised Obsidian vault dependency with a complete data input→output architecture. Every management input gets analyzed and all potentially useful outputs get generated. VS Code is the primary interface (CLI in full parity).

## Architecture

Structured markdown files in `data/` are the source of truth. Same frontmatter schema as the old vault — zero data model changes. A document ingestion pipeline classifies and routes inputs. Watch folder provides automated processing; VS Code commands and CLI provide explicit invocation. Two new agents (status_update, review_prep) fill gaps identified in the EM workflow taxonomy.

### Data Directory Structure

```
data/
├── people/           # Person notes (type: person)
├── meetings/         # Meeting notes + processed transcripts (type: meeting)
├── coaching/         # Coaching hypotheses (type: coaching)
├── feedback/         # Feedback records (type: feedback)
├── decisions/        # Decision records (type: decision)
├── inbox/            # Watch folder — drop files here for processing
├── processed/        # Processed inbox items (moved after classification)
└── references/       # Articles, notes, external content with summaries
```

Git-tracked for structure. `*.md` files gitignored (personal management data).

### Document Ingestion Pipeline

When a file lands in `data/inbox/` or is submitted via VS Code/CLI, a classifier agent determines document type and routes to the appropriate processor.

**Document types:**

| Input Type | Detection Signal | Processor | Outputs |
|-----------|-----------------|-----------|---------|
| Meeting transcript | .vtt/.srt extension, speaker-turn patterns | `meeting_lifecycle --transcript` | Meeting note, action items, coaching starters, feedback starters, decision starters |
| Meeting notes (manual) | Frontmatter `type: meeting` or meeting content | Validation + filing | Filed to `data/meetings/` |
| Article/blog post | URL, long-form prose, no frontmatter | Extract takeaways, tag relevance | Filed to `data/references/` with summary |
| Person note | Frontmatter `type: person` | Validation + filing | Filed to `data/people/` |
| Feedback note | Frontmatter `type: feedback` | Validation + filing | Filed to `data/feedback/` |
| Unstructured notes | Free-form text, no clear type | LLM classification → route | Depends on classification |

**Watch folder daemon:** Lightweight Python process polls `data/inbox/` every 30 seconds. On new file: classify → process → move to `data/processed/` with timestamp → generate downstream outputs → notify via ntfy.

**CLI:** `uv run python -m agents.ingest <file>` (explicit), `uv run python -m agents.ingest --watch` (daemon).

**VS Code:** `Hapax: Process Document` command (file picker → classify → process → show results).

### Output Generation Matrix

Every input triggers a cascade of outputs.

| Input | Immediate Outputs | Downstream Effects |
|-------|-------------------|-------------------|
| Meeting transcript | Meeting note, coaching starters, feedback starters, decision records | Updates person notes (last-1on1), triggers nudge recalc, feeds next 1:1 prep |
| New person note | None | Appears in team snapshot, enables 1:1 prep, feeds briefing |
| Coaching hypothesis | None | Staleness tracking, 1:1 prep context, coaching nudges |
| Feedback record | None | Follow-up tracking, 1:1 prep context, feedback nudges |
| Decision record | None | Searchable context, appears in weekly review |
| Article/reference | Summary + relevance tags, Qdrant index | Knowledge search, briefing if management-relevant |

**Scheduled outputs (timer-driven):**

| Output | Schedule | Agent |
|--------|----------|-------|
| Morning briefing | Daily 07:00 | management_briefing |
| 1:1 prep docs | Daily 06:30 | management_prep |
| Profile update | Every 12h | management_profiler |
| Nudge refresh | Every 5min | logos API cache |
| Weekly review | Sunday evening | meeting_lifecycle |
| Activity report | On demand | management_activity |

### VS Code Extension Changes

Building into existing hapax-vscode. The extension already has vault I/O, frontmatter parsing (gray-matter), interview engine, and 7 management commands.

**New commands (8):**

| Command | Purpose | CLI Equivalent |
|---------|---------|---------------|
| `Hapax: Process Document` | File picker → classify → process | `hapax ingest <file>` |
| `Hapax: New Person Note` | Guided creation → `data/people/` | `hapax new person` |
| `Hapax: New Coaching Hypothesis` | Guided creation → `data/coaching/` | `hapax new coaching` |
| `Hapax: New Feedback Record` | Guided creation → `data/feedback/` | `hapax new feedback` |
| `Hapax: Process Transcript` | Shortcut for transcript processing | `hapax ingest --type transcript <file>` |
| `Hapax: Morning Briefing` | Run briefing agent, show in editor | `hapax briefing` |
| `Hapax: Weekly Review` | Run weekly review, show in editor | `hapax weekly-review` |
| `Hapax: Status Update` | Generate upward-facing status report | `hapax status-update` |

Guided creation: VS Code input boxes → LLM assists structuring → creates markdown file → opens in editor.

**Existing commands updated:**
- `prepare1on1` — reads from `data/people/` instead of vault
- `teamSnapshot` — reads from `data/people/` instead of vault
- `captureDecision` — writes to `data/decisions/` instead of vault/cache
- `viewProfile` — update path from `ryan-digest.json` to `operator-digest.json`

**Interview engine:** Knowledge model paths updated from vault to `data/`.

**Configuration:**
- `hapax.dataDir` — path to management data (default: `data`)
- `hapax.inboxDir` — path to watch folder (default: `data/inbox`)
- `hapax.qdrantUrl` default → `localhost:6433`
- `hapax.litellmUrl` default → `localhost:4100`

### Agent-Side Changes

**config.py** — new constant:
```python
DATA_DIR: Path = Path(os.environ.get("HAPAX_DATA_DIR",
    str(Path(__file__).resolve().parent.parent / "data")))
```

**management_bridge.py** — rehydrate to read from `DATA_DIR`:
- `generate_facts()` reads `DATA_DIR / "people/"`, `"coaching/"`, `"feedback/"`, `"meetings/"`
- Same frontmatter parsing logic, same `_make_fact` output format
- Restore `_people_facts`, `_coaching_facts`, `_feedback_facts`, `_meeting_facts`

**logos/data/management.py** — rehydrate to read from `DATA_DIR`:
- `collect_management_state()` scans `DATA_DIR` subdirectories
- Restore `_collect_people`, `_collect_coaching`, `_collect_feedback`
- Same `ManagementSnapshot` output

**vault_writer.py** — rehydrate to write to `DATA_DIR`:
- Same function signatures, same frontmatter format
- Base directory changed from `VAULT_PATH` to `DATA_DIR`

**New: agents/ingest.py** — document classifier + router:
```
uv run python -m agents.ingest <file>                    # Classify and process
uv run python -m agents.ingest --type transcript <file>  # Skip classification
uv run python -m agents.ingest --watch                   # Watch data/inbox/
```

### New Agents

**`status_update` agent:**
Generates upward-facing status reports (Lara Hogan "Week in Review" pattern). Consumes the week's meetings, coaching activity, nudge state, goal progress, team health. Produces: headline, themes from 1:1s, risks/blockers, wins, asks.

```
uv run python -m agents.status_update          # Weekly
uv run python -m agents.status_update --daily  # Daily
```

**`review_prep` agent:**
Performance review season helper. Consumes 3-12 months of meeting notes, coaching, feedback, profile facts for a specific person. Produces evidence aggregation: contributions summary, growth trajectory, development areas, evidence citations.

Safety: evidence aggregation only. Never generates evaluative language or ratings. Per `management_safety` axiom.

```
uv run python -m agents.review_prep --person "Alice" --months 6
```

### System Integration

```
INPUTS                          PROCESSING                      OUTPUTS
─────────────────               ──────────────                  ───────
VS Code guided creation ──┐
CLI `hapax new` commands ─┤     data/people/                   1:1 prep docs
                          ├──→  data/coaching/    ──→ agents   morning briefing
Watch folder (inbox/) ────┤     data/feedback/       read      nudges
                          │     data/meetings/       from      team health
VS Code Process Document ─┤     data/decisions/      data/     weekly review
CLI `hapax ingest` ───────┘     data/references/     dir       status updates
                                                               review prep
                                      ↓                        profile updates
                                management_bridge               activity report
                                management.py
                                logos API cache
                                      ↓
                                Dashboard (cockpit-web)
                                VS Code sidebar
                                ntfy notifications
```

## What This Design Does NOT Cover

- **Qdrant indexing of data/ files** — semantic search over management data. Natural future enhancement but not needed for core loop.
- **Calendar/Slack/Jira integrations** — external data source connectors. Separate project per connector.
- **Hiring pipeline agents** — sparse data, not routine enough to justify now.
- **Incident/post-mortem tracking** — needs external monitoring integration.
- **Sprint/project status aggregation** — needs project management tool connectors.
