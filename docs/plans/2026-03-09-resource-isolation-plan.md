# Resource Isolation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate all shared resources between the management cockpit and the wider hapax system, giving each its own infrastructure stack.

**Architecture:** Offset all Docker host ports by +100, prefix container/volume/network names with `mgmt-`, excise Obsidian vault dependencies, remove out-of-scope services (Open WebUI, n8n). Ollama stays shared (single GPU constraint). Code changes are minimal — config defaults and vault stubs.

**Tech Stack:** Docker Compose, Python, bash

---

## Task 1: Isolate Docker Compose infrastructure

**Files:**
- Modify: `~/projects/hapax-containerization/llm-stack/docker-compose.yml`

**Step 1: Rename Docker network**

Change the network name from `llm-stack` to `mgmt-cockpit`:

```yaml
networks:
  default:
    name: mgmt-cockpit
```

Also update the management-cockpit service's explicit network reference:

```yaml
    networks:
      - mgmt-cockpit
```

**Step 2: Prefix all container names with `mgmt-`**

Every `container_name:` value gets `mgmt-` prefix:

| Old | New |
|-----|-----|
| `qdrant` | `mgmt-qdrant` |
| `ollama` | `mgmt-ollama` |
| `postgres` | `mgmt-postgres` |
| `litellm` | `mgmt-litellm` |
| `clickhouse` | `mgmt-clickhouse` |
| `redis` | `mgmt-redis` |
| `minio` | `mgmt-minio` |
| `langfuse-worker` | `mgmt-langfuse-worker` |
| `langfuse` | `mgmt-langfuse` |

**Step 3: Offset all host ports**

| Service | Old Host Port | New Host Port |
|---------|--------------|---------------|
| Qdrant REST | 6333 | 6433 |
| Qdrant gRPC | 6334 | 6434 |
| Ollama | 11434 | 11434 (shared) |
| PostgreSQL | 5432 | 5532 |
| LiteLLM | 4000 | 4100 |
| ClickHouse HTTP | 8123 | 8223 |
| ClickHouse native | 9000 | 9100 |
| Langfuse Worker | 3030 | 3130 |
| Langfuse | 3000 | 3100 |
| MinIO API | 9090 | 9190 |
| MinIO Console | 9091 | 9191 |
| ntfy | 8090 | 8190 |
| Chatterbox | 4123 | 4223 |
| Logos API | 8051 | 8051 (unchanged) |

Internal container ports stay the same. Only the `127.0.0.1:XXXX:YYYY` host mapping changes.

Example for Qdrant:
```yaml
  qdrant:
    container_name: mgmt-qdrant
    ports:
      - "127.0.0.1:6433:6333"
      - "127.0.0.1:6434:6334"
```

Example for LiteLLM:
```yaml
  litellm:
    container_name: mgmt-litellm
    ports:
      - "127.0.0.1:4100:4000"
```

**Step 4: Prefix all Docker volume names with `mgmt_`**

```yaml
volumes:
  mgmt_qdrant_data:
  mgmt_ollama_data:
  mgmt_postgres_data:
  mgmt_clickhouse_data:
  mgmt_clickhouse_logs:
  mgmt_redis_data:
  mgmt_minio_data:
  mgmt_ntfy_cache:
  mgmt_hapax_data:
  mgmt_hapax_claude_home:
  mgmt_management_data:
```

Update all `volumes:` references in each service to use the `mgmt_` prefix. For example:

```yaml
  qdrant:
    volumes:
      - mgmt_qdrant_data:/qdrant/storage
```

**Step 5: Remove Open WebUI and n8n services**

Delete the entire `open-webui:` service block (lines 276-310 approximately) and the entire `n8n:` service block (lines 312-336 approximately). Also remove the `open_webui_data:` and `n8n_data:` entries from volumes.

**Step 6: Remove vault mount from management-cockpit service**

In the `management-cockpit:` service, remove the vault volume line:

```yaml
      - ${VAULT_PATH:-/path/to/vault}:/vault
```

**Step 7: Update management-cockpit environment for new ports**

The management-cockpit service uses Docker service names internally, so no port changes needed there. But update the ntfy base URL port since ntfy internal port is 80:

```yaml
      - NTFY_BASE_URL=http://ntfy:80
```

This is already correct. No change needed.

**Step 8: Update hapax-dev environment for new host ports**

In the `hapax-dev:` service, the internal Docker URLs don't change (they use service names). No edits needed since it connects via `http://litellm:4000`, `http://qdrant:6333`, etc. internally.

**Step 9: Commit**

```bash
cd ~/projects/hapax-containerization
git add llm-stack/docker-compose.yml
git commit -m "feat: isolate Docker stack — offset ports, prefix names, remove Open WebUI + n8n"
```

---

## Task 2: Update generate-env.sh

**Files:**
- Modify: `~/projects/hapax-containerization/llm-stack/generate-env.sh`

**Step 1: Remove out-of-scope secrets**

Remove these lines (services no longer in compose):
```bash
N8N_ENCRYPTION_KEY=$(pass show n8n/encryption-key)
WEBUI_SECRET_KEY=$(pass show webui/secret-key)
TELEGRAM_CHAT_ID=$(pass show telegram/chat-id)
```

**Step 2: Remove Obsidian vault path**

Remove:
```bash
OBSIDIAN_VAULT_PATH=data/
```

**Step 3: Update ntfy port**

Change:
```bash
NTFY_BASE_URL=http://127.0.0.1:8190
```

**Step 4: Commit**

```bash
cd ~/projects/hapax-containerization
git add llm-stack/generate-env.sh
git commit -m "feat: clean generate-env.sh — remove out-of-scope secrets and vault path"
```

---

## Task 3: Update config.py default ports

**Files:**
- Modify: `~/projects/hapax-containerization/shared/config.py`

**Step 1: Update default port values**

Change the default URLs in the environment variable fallbacks:

```python
LITELLM_BASE: str = os.environ.get(
    "LITELLM_API_BASE",
    os.environ.get("LITELLM_BASE_URL", "http://localhost:4100"),
)
LITELLM_KEY: str = os.environ.get("LITELLM_API_KEY", "changeme")
QDRANT_URL: str = os.environ.get("QDRANT_URL", "http://localhost:6433")
OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://localhost:11434")
```

Only `LITELLM_BASE` and `QDRANT_URL` change. Ollama stays at 11434 (shared).

**Step 2: Remove vault path constants**

Remove lines 28-32:

```python
WORK_VAULT_PATH: Path = Path(os.environ.get("WORK_VAULT_PATH", str(Path.home() / "Documents" / "Work")))
PERSONAL_VAULT_PATH: Path = Path(os.environ.get("PERSONAL_VAULT_PATH", str(Path.home() / "Documents" / "Personal")))

# Backwards compat — most agents write to the work vault
VAULT_PATH: Path = WORK_VAULT_PATH
```

**Step 3: Commit**

```bash
cd ~/projects/hapax-containerization
git add shared/config.py
git commit -m "feat: update config defaults — isolated ports, remove vault paths"
```

---

## Task 4: Update langfuse_config.py default port

**Files:**
- Modify: `~/projects/hapax-containerization/shared/langfuse_config.py`

**Step 1: Update default Langfuse host**

Change line 11:

```python
HOST = os.environ.get("LANGFUSE_HOST", "http://localhost:3100")
```

**Step 2: Commit**

```bash
cd ~/projects/hapax-containerization
git add shared/langfuse_config.py
git commit -m "feat: update langfuse default port to 3100"
```

---

## Task 5: Update langfuse_client.py default port

**Files:**
- Modify: `~/projects/hapax-containerization/shared/langfuse_client.py`

**Step 1: Update default Langfuse host**

Change line 18:

```python
LANGFUSE_HOST: str = os.environ.get("LANGFUSE_HOST", "http://localhost:3100")
```

**Step 2: Commit**

```bash
cd ~/projects/hapax-containerization
git add shared/langfuse_client.py
git commit -m "feat: update langfuse_client default port to 3100"
```

---

## Task 6: Stub vault reads in management_bridge.py

**Files:**
- Modify: `~/projects/hapax-containerization/shared/management_bridge.py`

**Step 1: Replace vault-reading implementation with stubs**

Replace the entire file content with:

```python
"""management_bridge.py — Management data source bridge.

Data source: TBD (vault excised, VS Code + Qdrant integration pending).
Returns empty results until a new data source is implemented.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from shared.config import PROFILES_DIR

log = logging.getLogger("management_bridge")
FACTS_OUTPUT = PROFILES_DIR / "management-structured-facts.json"


def _make_fact(dimension: str, key: str, value: str, evidence: str) -> dict:
    """Create a ProfileFact-compatible dict."""
    return {
        "dimension": dimension,
        "key": key,
        "value": value,
        "confidence": 0.90,
        "source": "management-vault",
        "evidence": evidence,
    }


def generate_facts(vault_path: Path | None = None) -> list[dict]:
    """Generate ProfileFact dicts from management data.

    Returns empty list — data source not yet implemented.
    """
    log.info("management_bridge: no data source configured (vault excised)")
    return []


def save_facts(facts: list[dict]) -> Path:
    """Save generated facts to the profiles directory."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    FACTS_OUTPUT.write_text(
        json.dumps(facts, indent=2, default=str),
        encoding="utf-8",
    )
    log.info("Saved %d management facts to %s", len(facts), FACTS_OUTPUT.name)
    return FACTS_OUTPUT
```

This preserves `_make_fact` and `save_facts` (used by other code) but stubs `generate_facts` to return `[]`. The four vault-scanning private functions (`_people_facts`, `_coaching_facts`, `_feedback_facts`, `_meeting_facts`) are removed along with the `VAULT_PATH` import and `_parse_frontmatter`.

**Step 2: Commit**

```bash
cd ~/projects/hapax-containerization
git add shared/management_bridge.py
git commit -m "feat: stub management_bridge — vault excised, data source TBD"
```

---

## Task 7: Stub vault writes in vault_writer.py

**Files:**
- Modify: `~/projects/hapax-containerization/shared/vault_writer.py`

**Step 1: Replace vault-writing implementation with no-op stubs**

Replace the entire file content with:

```python
"""shared/vault_writer.py — Vault egress (stubbed).

Vault excised from management cockpit. All write functions are no-ops
that log a warning and return None. Preserved for API compatibility —
callers check return value for None already.

Data egress will be reimplemented when VS Code integration is built.
"""
from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger(__name__)
_STUB_MSG = "vault_writer: vault excised — write operation skipped"


def write_to_vault(
    folder: str,
    filename: str,
    content: str,
    frontmatter: dict | None = None,
) -> Path | None:
    _log.info(_STUB_MSG)
    return None


def write_briefing_to_vault(briefing_md: str) -> Path | None:
    _log.info(_STUB_MSG)
    return None


def write_digest_to_vault(digest_md: str) -> Path | None:
    _log.info(_STUB_MSG)
    return None


def write_nudges_to_vault(nudges: list[dict]) -> Path | None:
    _log.info(_STUB_MSG)
    return None


def write_goals_to_vault(goals: list[dict]) -> Path | None:
    _log.info(_STUB_MSG)
    return None


def write_1on1_prep_to_vault(person_name: str, prep_md: str) -> Path | None:
    _log.info(_STUB_MSG)
    return None


def write_team_snapshot_to_vault(snapshot_md: str) -> Path | None:
    _log.info(_STUB_MSG)
    return None


def write_management_overview_to_vault(overview_md: str) -> Path | None:
    _log.info(_STUB_MSG)
    return None


def create_coaching_starter(person: str, observation: str) -> Path | None:
    _log.info(_STUB_MSG)
    return None


def create_fb_record_starter(person: str, fb_moment) -> Path | None:
    _log.info(_STUB_MSG)
    return None


def create_decision_starter(decision_text: str, meeting_ref: str) -> Path | None:
    _log.info(_STUB_MSG)
    return None


def write_bridge_prompt_to_vault(prompt_name: str, prompt_md: str) -> Path | None:
    _log.info(_STUB_MSG)
    return None
```

Every function preserves its signature and returns `None` (callers already handle this). The `VAULT_PATH` import is removed.

**Step 2: Commit**

```bash
cd ~/projects/hapax-containerization
git add shared/vault_writer.py
git commit -m "feat: stub vault_writer — all writes become no-ops"
```

---

## Task 8: Stub vault reads in logos/data/management.py

**Files:**
- Modify: `~/projects/hapax-containerization/logos/data/management.py`

**Step 1: Replace vault-reading implementation with stubs**

Replace the entire file content with:

```python
"""Management state collector — stubbed.

Vault excised from management cockpit. Returns empty ManagementSnapshot.
Data source will be reimplemented with VS Code + Qdrant integration.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

_log = logging.getLogger(__name__)


@dataclass
class PersonState:
    """State of a single team member."""
    name: str
    team: str = ""
    role: str = ""
    cadence: str = ""
    status: str = "active"
    cognitive_load: int | None = None
    growth_vector: str = ""
    feedback_style: str = ""
    last_1on1: str = ""
    coaching_active: bool = False
    stale_1on1: bool = False
    days_since_1on1: int | None = None
    file_path: Path | None = None
    career_goal_3y: str = ""
    current_gaps: str = ""
    current_focus: str = ""
    last_career_convo: str = ""
    team_type: str = ""
    interaction_mode: str = ""
    skill_level: str = ""
    will_signal: str = ""
    domains: list[str] = field(default_factory=lambda: ["management"])
    relationship: str = ""


@dataclass
class CoachingState:
    """State of a coaching hypothesis."""
    title: str
    person: str = ""
    status: str = "active"
    check_in_by: str = ""
    overdue: bool = False
    days_overdue: int = 0
    file_path: Path | None = None


@dataclass
class FeedbackState:
    """State of a feedback record."""
    title: str
    person: str = ""
    direction: str = "given"
    category: str = "growth"
    follow_up_by: str = ""
    followed_up: bool = False
    overdue: bool = False
    days_overdue: int = 0
    file_path: Path | None = None


@dataclass
class ManagementSnapshot:
    """Aggregated management state."""
    people: list[PersonState] = field(default_factory=list)
    coaching: list[CoachingState] = field(default_factory=list)
    feedback: list[FeedbackState] = field(default_factory=list)
    stale_1on1_count: int = 0
    overdue_coaching_count: int = 0
    overdue_feedback_count: int = 0
    high_load_count: int = 0
    active_people_count: int = 0


def collect_management_state() -> ManagementSnapshot:
    """Collect management state.

    Returns empty snapshot — vault data source excised.
    """
    _log.info("management: no data source configured (vault excised)")
    return ManagementSnapshot()
```

Preserves all dataclass types (used by API routes and other callers) but `collect_management_state()` returns empty. Removes `VAULT_PATH` import, `_parse_frontmatter`, all `_collect_*` and `_find_typed_notes` functions, and staleness computation.

**Step 2: Commit**

```bash
cd ~/projects/hapax-containerization
git add logos/data/management.py
git commit -m "feat: stub management collector — vault excised, returns empty snapshot"
```

---

## Task 9: Remove vault check from system_check.py

**Files:**
- Modify: `~/projects/hapax-containerization/agents/system_check.py`

**Step 1: Remove check_vault_access function**

Delete the `check_vault_access` function (lines 71-78):

```python
async def check_vault_access() -> CheckResult:
    """Check if the vault directory is accessible."""
    vault = Path(os.environ.get("VAULT_PATH", "/vault"))
    people = vault / "10-work" / "people"
    if people.is_dir():
        count = len(list(people.glob("*.md")))
        return CheckResult("vault_access", True, f"{count} people notes found")
    return CheckResult("vault_access", False, f"{people} not found")
```

**Step 2: Remove from ALL_CHECKS**

Change line 101:

```python
ALL_CHECKS = [check_cockpit_api, check_qdrant, check_litellm]
```

Remove `check_vault_access` from the list. Now 3 checks instead of 4.

**Step 3: Update module docstring**

Change line 4:
```python
Zero LLM calls. Checks the 3 services needed for the management system:
logos API, Qdrant, and LiteLLM.
```

**Step 4: Commit**

```bash
cd ~/projects/hapax-containerization
git add agents/system_check.py
git commit -m "feat: remove vault health check from system_check (3 checks remain)"
```

---

## Task 10: Update system_check default ports

**Files:**
- Modify: `~/projects/hapax-containerization/agents/system_check.py`

**Step 1: Update default Qdrant URL**

Change line 83 (after vault removal, line numbers shift):

```python
    url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6433")
```

**Step 2: Update default LiteLLM URL**

Change line in `check_litellm`:

```python
    url = os.environ.get("LITELLM_API_BASE", "http://127.0.0.1:4100")
```

**Step 3: Update default ntfy URL**

Change in `_notify_failures`:

```python
    ntfy_url = os.environ.get("NTFY_BASE_URL", "http://127.0.0.1:8190")
```

**Step 4: Commit**

```bash
cd ~/projects/hapax-containerization
git add agents/system_check.py
git commit -m "feat: update system_check default ports to isolated stack"
```

---

## Task 11: Fix vault references in remaining agent files

**Files:**
- Modify: `~/projects/hapax-containerization/agents/management_profiler.py`
- Modify: `~/projects/hapax-containerization/agents/management_briefing.py`
- Modify: `~/projects/hapax-containerization/agents/management_prep.py`
- Modify: `~/projects/hapax-containerization/agents/management_activity.py`
- Modify: `~/projects/hapax-containerization/agents/meeting_lifecycle.py`
- Modify: `~/projects/hapax-containerization/agents/demo_pipeline/research.py`
- Modify: `~/projects/hapax-containerization/logos/data/agents.py`
- Modify: `~/projects/hapax-containerization/logos/data/team_health.py`
- Modify: `~/projects/hapax-containerization/shared/notify.py`

**Step 1: Audit and fix each file**

For every file in the list above, search for:
- `from shared.config import.*VAULT` — remove the vault import
- `VAULT_PATH` usage — replace with empty stubs or remove
- `vault` references in docstrings/comments — update to reflect excision
- Any `os.environ.get("VAULT_PATH"` — remove

Each file needs individual attention. The common patterns:
- Files that import `VAULT_PATH` from config: the import will break after Task 3 removes it. Remove the import and any code that uses it.
- Files that reference vault in comments only: update comments.
- Files that pass vault paths to management_bridge: already safe since management_bridge.generate_facts() now ignores its argument.

**Step 2: Run full test suite**

```bash
cd ~/projects/hapax-containerization/ai-agents && uv run pytest tests/ -q 2>&1 | tail -20
```

Fix any import errors or test failures caused by removed `VAULT_PATH`.

**Step 3: Commit**

```bash
cd ~/projects/hapax-containerization
git add ai-agents/ 
git commit -m "feat: remove vault references from all agent and cockpit files"
```

---

## Task 12: Fix vault references in test files

**Files:**
- Modify: `~/projects/hapax-containerization/tests/test_management.py`
- Modify: `~/projects/hapax-containerization/tests/test_management_bridge.py`
- Modify: `~/projects/hapax-containerization/tests/test_team_health.py`
- Modify: `~/projects/hapax-containerization/tests/test_management_prep.py`
- Modify: `~/projects/hapax-containerization/tests/test_meeting_lifecycle.py`
- Modify: `~/projects/hapax-containerization/tests/test_notify.py`

**Step 1: Update tests for stubbed modules**

Tests that mock vault reads need updating:
- `test_management_bridge.py` — test that `generate_facts()` returns `[]`
- `test_management.py` — test that `collect_management_state()` returns empty `ManagementSnapshot`
- `test_team_health.py` — update if it depends on vault-based management state
- Other test files — remove vault path mocks, update expectations

**Step 2: Run test suite**

```bash
cd ~/projects/hapax-containerization/ai-agents && uv run pytest tests/ -q
```

All tests must pass.

**Step 3: Commit**

```bash
cd ~/projects/hapax-containerization
git add tests/
git commit -m "fix: update tests for vault excision and port isolation"
```

---

## Task 13: Update boundary document in both repos

**Files:**
- Modify: `~/projects/hapax-containerization/docs/cross-project-boundary.md`
- Modify: `~/projects/hapaxromana/docs/cross-project-boundary.md`

**Step 1: Update Shared Infrastructure section**

Replace the "Shared Infrastructure (Current State)" section with:

```markdown
## Infrastructure (Isolated)

Each system runs its own infrastructure stack. No shared services, databases,
collections, or traces.

| Service | Wider System | Management Cockpit |
|---------|-------------|-------------------|
| Qdrant | localhost:6333 | localhost:6433 |
| LiteLLM | localhost:4000 | localhost:4100 |
| Langfuse | localhost:3000 | localhost:3100 |
| PostgreSQL | localhost:5432 | localhost:5532 |
| Ollama | localhost:11434 | localhost:11434 (shared — single GPU) |

Ollama is the one shared service — stateless inference with auto-managed
model loading. Both stacks point at the same instance. Not a data store.
```

**Step 2: Update Isolation Trajectory section**

Replace with:

```markdown
## Isolation Status

Infrastructure isolation completed March 2026. Each system has its own
Qdrant collections, LiteLLM proxy, Langfuse traces, and PostgreSQL databases.
Ollama remains shared (single GPU constraint, stateless inference).

Data source isolation in progress — the management cockpit's vault dependency
has been excised. VS Code + Qdrant integration is the planned replacement.
```

**Step 3: Verify byte-identical**

```bash
diff ~/projects/hapaxromana/docs/cross-project-boundary.md \
     ~/projects/hapax-containerization/docs/cross-project-boundary.md
```

Expected: no output

**Step 4: Commit in both repos**

```bash
cd ~/projects/hapax-containerization
git add docs/cross-project-boundary.md
git commit -m "docs: update boundary doc — infrastructure isolated, vault excised"

cd ~/projects/hapaxromana
git add docs/cross-project-boundary.md
git commit -m "docs: update boundary doc — infrastructure isolated, vault excised"
```

---

## Task 14: Update CLAUDE.md files

**Files:**
- Modify: `~/projects/hapax-containerization/CLAUDE.md`
- Modify: `~/projects/hapax-containerization/CLAUDE.md`

**Step 1: Update containerization CLAUDE.md**

In the main CLAUDE.md:

- Update the agent count in `system_check` description: "Health checks for the 3 core services" (was 4)
- Update the "Relationship to Wider Hapax System" section to note isolation is complete
- Remove any vault references

In `CLAUDE.md`:

- Update `system_check` description: "Health checks for 3 core services" (was 4)
- Remove vault references from agent descriptions or key files
- Update port references if any

**Step 2: Commit**

```bash
cd ~/projects/hapax-containerization
git add CLAUDE.md CLAUDE.md
git commit -m "docs: update CLAUDE.md files for resource isolation"
```

---

## Task 15: Run full verification

**Step 1: Run test suite**

```bash
cd ~/projects/hapax-containerization/ai-agents && uv run pytest tests/ -q
```

All tests must pass.

**Step 2: Verify no remaining vault imports from config**

```bash
cd ~/projects/hapax-containerization && grep -rn "VAULT_PATH\|WORK_VAULT\|PERSONAL_VAULT" ai-agents/  --include="*.py" | grep -v "test_\|__pycache__\|\.pyc"
```

Expected: no results (vault constants removed from config, all imports updated).

**Step 3: Verify port isolation in config defaults**

```bash
grep -n "localhost:4000\|localhost:6333\|localhost:3000\|localhost:5432" shared/config.py shared/langfuse_config.py shared/langfuse_client.py agents/system_check.py
```

Expected: no results (all updated to offset ports).

**Step 4: Verify docker-compose has no old names**

```bash
grep -n "container_name: [a-z]" llm-stack/docker-compose.yml | grep -v "mgmt-"
```

Expected: no results (all container names prefixed).
