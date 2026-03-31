# Cross-Project Awareness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish bidirectional documentation-level awareness between hapaxromana and hapax-containerization, with drift detection to enforce consistency.

**Architecture:** A byte-identical boundary document lives in both repos. Both CLAUDE.md files cross-reference it. The wider system's drift-detector gains a new check comparing the two copies.

**Tech Stack:** Markdown, Python (drift_detector.py), bash (filecmp)

---

## Task 1: Write the shared boundary document

**Files:**
- Create: `~/projects/hapax-containerization/docs/cross-project-boundary.md`

**Step 1: Write the boundary document**

Create `docs/cross-project-boundary.md` with these sections:

```markdown
# Cross-Project Boundary: Hapax System ↔ Management Cockpit

This document defines the relationship between the wider hapax system and the
containerized management cockpit. It must be byte-identical in both repos:

- `~/projects/hapaxromana/docs/cross-project-boundary.md`
- `~/projects/hapax-containerization/docs/cross-project-boundary.md`

Any divergence is a high-severity drift item detected by the wider system's
drift-detector agent (weekly Sunday 03:00).

## Project Identities

**Wider Hapax System** (`hapaxromana` + `ai-agents`): A personal executive
function platform for a single operator. Covers all domains — management,
personal knowledge, health monitoring, audio capture, content sync, creative
production. 28+ agents across sync, RAG, analysis, and automation.

**Management Cockpit** (`hapax-containerization`): A management-only decision
support system extracted from the wider system in March 2026. Purpose-built
for team leadership — 1:1 prep, coaching tracking, management self-awareness
profiling, actionable nudges. 8 agents, all management-scoped. Safety
principle: LLMs prepare, humans deliver.

## Shared Lineage

Both projects share the same origin codebase. The management cockpit was
extracted via a deliberate conversion that:

- Removed 22 agents outside management scope
- Renamed 5 agents for management clarity
- Added 1 management-specific agent (management_activity)
- Regrounded axioms from personal/neurodivergent context to management decision theory
- Removed all personal context (executive function, neurodivergent-friendly designs)
- Rewrote the demo pipeline for management-only content

The extraction is documented in:
- `hapax-containerization/docs/plans/2026-03-06-management-conversion-design.md`
- `hapax-containerization/docs/plans/2026-03-06-management-conversion-plan.md`

## Axiom Correspondence

Containerization's axioms are a fork-with-rename of the wider system's axioms.
Same constitutional principles, different grounding language.

| Wider System (hapaxromana) | Containerization | Weight | Notes |
|---------------------------|------------------|--------|-------|
| single_user | single_operator | 100 | Same semantics, role-generic language |
| executive_function | decision_support | 95 | Regrounded: neurodivergent-friendly design → decision-support theory |
| management_governance | management_safety | 95 | Elevated: domain axiom → constitutional scope |
| corporate_boundary | corporate_boundary | 90 | Unchanged, dormant in both |

All T0 blocking implications are preserved. Only the grounding text differs.

## Agent Roster Divergence

### Present in both (identical or renamed)

| Wider System | Containerization | Change |
|-------------|------------------|--------|
| management_prep | management_prep | Identical |
| meeting_lifecycle | meeting_lifecycle | Identical |
| briefing | management_briefing | Renamed, management-focused |
| profiler | management_profiler | Renamed, 13 → 6 dimensions |
| demo, demo_eval | demo, demo_eval | Ported with adaptation |
| health_monitor | system_check | Rewritten: 75 checks → 4, no auto-fix |

### Only in containerization

| Agent | Purpose |
|-------|---------|
| management_activity | Vault-based management practice metrics (no LLM) |

### Only in wider system (22 agents removed from containerization)

Sync agents (7): gdrive_sync, gcalendar_sync, gmail_sync, youtube_sync,
chrome_sync, claude_code_sync, obsidian_sync.

Analysis agents (5): research, code_review, introspect, drift_detector, scout.

Content agents (4): digest, knowledge_maint, ingest, activity_analyzer.

Audio agents (3): audio_processor, hapax_daimonion, audio_recorder (systemd).

Other (3): query, profiler_sources, demo pipeline differences.

## Shared Modules

18 modules in `shared/` exist in both repos. Containerization is a strict
subset — it has no unique shared modules.

Key shared modules: config.py, operator.py, profile_store.py,
management_bridge.py, notify.py, vault_writer.py, axiom_*.py,
context_tools.py, langfuse_client.py, langfuse_config.py.

The wider system has 18 additional shared modules not present in
containerization (google_auth.py, calendar_context.py, health_*.py,
capacity.py, dimensions.py, email_utils.py, service_*.py, etc.).

## Shared Infrastructure (Current State)

Both systems currently share these services on the same host:

| Service | Port | Shared Resource |
|---------|------|-----------------|
| Qdrant | 6333 | Collections: profile-facts, documents, axiom-precedents |
| LiteLLM | 4000 | Model routing, cost tracking |
| Langfuse | 3000 | Traces from both systems merged |
| PostgreSQL | 5432 | Shared database |
| Obsidian vault | — | data/ read by both |

## Isolation Trajectory

The management cockpit is moving toward full resource isolation — its own
infrastructure stack with no shared services. The mechanism is not yet
designed. Until isolation is complete, both systems read/write the same
Qdrant collections and Langfuse traces.

## Boundary Rules

Changes in one repo that may affect the other:

- **Shared module APIs**: Function signatures and class interfaces in shared/
  modules used by both repos. A breaking change in one breaks the other.
- **Axiom semantics**: Redefining what a constitutional axiom means affects
  both systems' governance.
- **Qdrant collection schemas**: Field names, vector dimensions, payload
  structure changes affect both readers.
- **Vault structure**: Path changes in data/ that
  management_bridge.py reads.
- **Profile dimensions**: The 6 management dimensions in profile_store.py
  are used by both systems' profilers.
- **Operator manifest**: operator.json structure changes affect both
  operator.py implementations.
```

**Step 2: Commit in containerization repo**

```bash
cd ~/projects/hapax-containerization
git add docs/cross-project-boundary.md
git commit -m "docs: add cross-project boundary document"
```

---

## Task 2: Copy boundary document to hapaxromana

**Files:**
- Create: `~/projects/hapaxromana/docs/cross-project-boundary.md`

**Step 1: Copy the byte-identical file**

```bash
cp ~/projects/hapax-containerization/docs/cross-project-boundary.md \
   ~/projects/hapaxromana/docs/cross-project-boundary.md
```

**Step 2: Verify byte-identical**

```bash
diff ~/projects/hapaxromana/docs/cross-project-boundary.md \
     ~/projects/hapax-containerization/docs/cross-project-boundary.md
```

Expected: no output (files identical)

**Step 3: Commit in hapaxromana**

```bash
cd ~/projects/hapaxromana
git add docs/cross-project-boundary.md
git commit -m "docs: add cross-project boundary document (shared with hapax-containerization)"
```

---

## Task 3: Update hapax-containerization CLAUDE.md

**Files:**
- Modify: `~/projects/hapax-containerization/CLAUDE.md`

**Step 1: Add relationship section**

Add before the `## Build, Test, and Run` section:

```markdown
## Relationship to Wider Hapax System

This project was extracted from the wider hapax system (`~/projects/hapaxromana/` + `~/projects/ai-agents/ `) in March 2026. It shares constitutional axioms (renamed for management context) and several shared modules. The systems currently share infrastructure (Qdrant, LiteLLM, Langfuse) but are moving toward full isolation. See `docs/cross-project-boundary.md` for the full boundary specification. That document must be byte-identical to the copy in hapaxromana.
```

**Step 2: Commit**

```bash
cd ~/projects/hapax-containerization
git add CLAUDE.md
git commit -m "docs: add wider hapax system relationship to CLAUDE.md"
```

---

## Task 4: Update hapaxromana CLAUDE.md

**Files:**
- Modify: `~/projects/hapaxromana/CLAUDE.md`

**Step 1: Add related project reference**

Find the `## Related Repos` section (around line 21). Add a new entry for hapax-containerization:

```markdown
- `~/projects/hapax-containerization/` — Management-only cockpit. Extracted from this system in March 2026. Same constitutional axioms with management-scoped grounding. See `docs/cross-project-boundary.md` for boundary spec (must be byte-identical to the copy here).
```

**Step 2: Commit**

```bash
cd ~/projects/hapaxromana
git add CLAUDE.md
git commit -m "docs: add hapax-containerization to related repos"
```

---

## Task 5: Add drift detection check to drift_detector

**Files:**
- Modify: `~/projects/agents/drift_detector.py`

**Step 1: Add the cross-project boundary check function**

Add a new function after the existing check functions (after `check_screen_context_drift`, around line 443):

```python
def check_cross_project_boundary() -> list[DriftItem]:
    """Compare cross-project boundary doc between hapaxromana and containerization.

    The boundary document must be byte-identical in both repos.
    Any divergence is high-severity.
    """
    items: list[DriftItem] = []
    hapaxromana_path = Path.home() / "projects" / "hapaxromana" / "docs" / "cross-project-boundary.md"
    containerization_path = Path.home() / "projects" / "hapax-containerization" / "docs" / "cross-project-boundary.md"

    if not hapaxromana_path.exists():
        items.append(DriftItem(
            severity="high",
            category="missing_doc",
            doc_file=str(hapaxromana_path),
            doc_claim="Cross-project boundary document should exist",
            reality="File not found",
            suggestion=f"Copy from {containerization_path}",
        ))
        return items

    if not containerization_path.exists():
        items.append(DriftItem(
            severity="high",
            category="missing_doc",
            doc_file=str(containerization_path),
            doc_claim="Cross-project boundary document should exist",
            reality="File not found",
            suggestion=f"Copy from {hapaxromana_path}",
        ))
        return items

    hapaxromana_content = hapaxromana_path.read_bytes()
    containerization_content = containerization_path.read_bytes()

    if hapaxromana_content != containerization_content:
        items.append(DriftItem(
            severity="high",
            category="config_mismatch",
            doc_file="docs/cross-project-boundary.md",
            doc_claim="Boundary document must be byte-identical in both repos",
            reality="Files differ between hapaxromana and hapax-containerization",
            suggestion="Diff the two files, reconcile changes, and copy the updated version to both repos",
        ))

    return items
```

**Step 2: Call the check in detect_drift()**

Find the `detect_drift()` function (around line 446). Add the call alongside the other deterministic checks:

```python
boundary_drift = check_cross_project_boundary()
```

And merge results into the final items list where the other results are merged.

**Step 3: Run existing drift_detector tests**

```bash
cd ~/projects/ai-agents && uv run pytest tests/test_drift_detector.py -v --tb=short 2>&1 | tail -20
```

Expected: Existing tests still pass. The new check doesn't need a dedicated test — it's a simple file comparison that the drift-detector's existing framework handles.

**Step 4: Commit**

```bash
cd ~/projects/ai-agents
git add agents/drift_detector.py
git commit -m "feat: add cross-project boundary drift check (hapaxromana ↔ containerization)"
```

---

## Task 6: Verify end-to-end

**Step 1: Verify boundary docs are identical**

```bash
diff ~/projects/hapaxromana/docs/cross-project-boundary.md \
     ~/projects/hapax-containerization/docs/cross-project-boundary.md
echo "Exit code: $?"
```

Expected: no output, exit code 0

**Step 2: Verify CLAUDE.md references**

```bash
grep -l "cross-project-boundary" ~/projects/hapaxromana/CLAUDE.md \
     ~/projects/hapax-containerization/CLAUDE.md
```

Expected: both files listed

**Step 3: Verify drift check exists**

```bash
grep -n "check_cross_project_boundary" ~/projects/agents/drift_detector.py
```

Expected: function definition + call site
