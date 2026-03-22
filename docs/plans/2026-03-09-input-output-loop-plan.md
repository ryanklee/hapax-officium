# Input→Output Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace excised Obsidian vault dependency with a complete data input→output architecture. Every management input gets analyzed and all potentially useful outputs get generated.

**Architecture:** Structured markdown files in `data/` are the source of truth. Same frontmatter schema as the old vault. A document ingestion pipeline classifies and routes inputs. Watch folder provides automated processing; VS Code commands and CLI provide explicit invocation. Two new agents (status_update, review_prep) fill gaps in the EM workflow taxonomy.

**Tech Stack:** Python 3.12+ (uv), pydantic-ai, FastAPI, gray-matter (TypeScript), VS Code Extension API

**Repos:** `hapax-containerization` (tasks 1-10), `hapax-vscode` (tasks 11-14)

---

### Task 1: DATA_DIR Constant and Data Directory Structure

**Files:**
- Modify: `shared/config.py`
- Create: `data/.gitkeep`
- Create: `data/people/.gitkeep`
- Create: `data/meetings/.gitkeep`
- Create: `data/coaching/.gitkeep`
- Create: `data/feedback/.gitkeep`
- Create: `data/decisions/.gitkeep`
- Create: `data/inbox/.gitkeep`
- Create: `data/processed/.gitkeep`
- Create: `data/references/.gitkeep`
- Modify: `.gitignore`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

In `tests/test_config.py`, add:

```python
def test_data_dir_default():
    """DATA_DIR defaults to data/ relative to project root."""
    from shared.config import DATA_DIR
    assert DATA_DIR.name == "data"
    assert DATA_DIR.parent.name == "ai-agents" or DATA_DIR.exists()


def test_data_dir_env_override(monkeypatch):
    """DATA_DIR respects HAPAX_DATA_DIR env var."""
    import importlib
    monkeypatch.setenv("HAPAX_DATA_DIR", "/tmp/test-data")
    import shared.config as cfg
    importlib.reload(cfg)
    assert str(cfg.DATA_DIR) == "/tmp/test-data"
    monkeypatch.delenv("HAPAX_DATA_DIR")
    importlib.reload(cfg)
```

**Step 2: Run test to verify it fails**

Run: `cd ai-agents && uv run pytest tests/test_config.py::test_data_dir_default tests/test_config.py::test_data_dir_env_override -v`
Expected: FAIL with `ImportError` or `AttributeError` (DATA_DIR not defined)

**Step 3: Create data directory structure**

Create `data/` with 8 subdirectories, each containing `.gitkeep`.

Add to `.gitignore`:
```
# Management data (personal, never committed)
data/**/*.md
data/**/*.json
data/**/*.yaml
```

**Step 4: Add DATA_DIR to config.py**

After `PROFILES_DIR` (line 27), add:

```python
DATA_DIR: Path = Path(os.environ.get("HAPAX_DATA_DIR",
    str(Path(__file__).resolve().parent.parent / "data")))
```

**Step 5: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_config.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add shared/config.py data/ ai-agents/ .gitignore tests/test_config.py
git commit -m "feat: add DATA_DIR constant and data directory structure"
```

---

### Task 2: Rehydrate logos/data/management.py

This is the critical path — all management data flows through `collect_management_state()`.

**Files:**
- Modify: `logos/data/management.py`
- Test: `tests/test_management.py`

**Step 1: Write failing tests**

Replace the current stub tests in `tests/test_management.py` with tests that verify real data reading:

```python
"""Tests for cockpit.data.management — reads from DATA_DIR."""
from __future__ import annotations
import textwrap
from pathlib import Path
from unittest.mock import patch

from cockpit.data.management import (
    collect_management_state,
    ManagementSnapshot,
    PersonState,
    CoachingState,
    FeedbackState,
    _parse_frontmatter,
)


def _write_md(path: Path, frontmatter: str, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n{body}")


class TestParseFrontmatter:
    def test_valid_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        _write_md(f, "type: person\nname: Alice")
        meta, body = _parse_frontmatter(f)
        assert meta["type"] == "person"
        assert meta["name"] == "Alice"

    def test_no_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("Just some text")
        meta, body = _parse_frontmatter(f)
        assert meta == {}
        assert "Just some text" in body

    def test_missing_file(self, tmp_path):
        meta, body = _parse_frontmatter(tmp_path / "nope.md")
        assert meta == {}
        assert body == ""


class TestCollectPeople:
    def test_reads_person_files(self, tmp_path):
        _write_md(tmp_path / "people" / "alice.md", textwrap.dedent("""\
            type: person
            name: Alice
            status: active
            role: direct-report
            team: Platform
            cadence: weekly"""))
        with patch("cockpit.data.management.DATA_DIR", tmp_path):
            snap = collect_management_state()
        assert len(snap.people) == 1
        assert snap.people[0].name == "Alice"
        assert snap.people[0].team == "Platform"
        assert snap.active_people_count == 1

    def test_skips_inactive(self, tmp_path):
        _write_md(tmp_path / "people" / "bob.md", "type: person\nname: Bob\nstatus: departed")
        with patch("cockpit.data.management.DATA_DIR", tmp_path):
            snap = collect_management_state()
        assert snap.active_people_count == 0

    def test_empty_dir(self, tmp_path):
        (tmp_path / "people").mkdir()
        with patch("cockpit.data.management.DATA_DIR", tmp_path):
            snap = collect_management_state()
        assert snap.people == []


class TestCollectCoaching:
    def test_reads_coaching_files(self, tmp_path):
        _write_md(tmp_path / "coaching" / "alice-growth.md", textwrap.dedent("""\
            type: coaching
            person: Alice
            status: active
            check-in-by: 2026-03-15"""))
        (tmp_path / "people").mkdir()
        with patch("cockpit.data.management.DATA_DIR", tmp_path):
            snap = collect_management_state()
        assert len(snap.coaching) == 1
        assert snap.coaching[0].person == "Alice"


class TestCollectFeedback:
    def test_reads_feedback_files(self, tmp_path):
        _write_md(tmp_path / "feedback" / "alice-code-review.md", textwrap.dedent("""\
            type: feedback
            person: Alice
            direction: giving
            category: technical
            follow-up-by: 2026-03-20
            followed-up: false"""))
        (tmp_path / "people").mkdir()
        (tmp_path / "coaching").mkdir()
        with patch("cockpit.data.management.DATA_DIR", tmp_path):
            snap = collect_management_state()
        assert len(snap.feedback) == 1
        assert snap.feedback[0].person == "Alice"
        assert snap.feedback[0].direction == "giving"


class TestSnapshotAggregates:
    def test_computes_staleness_counts(self, tmp_path):
        _write_md(tmp_path / "people" / "alice.md", textwrap.dedent("""\
            type: person
            name: Alice
            status: active
            cadence: weekly
            last-1on1: 2026-02-01"""))
        _write_md(tmp_path / "coaching" / "alice-h.md", textwrap.dedent("""\
            type: coaching
            person: Alice
            status: active
            check-in-by: 2026-02-01"""))
        _write_md(tmp_path / "feedback" / "alice-fb.md", textwrap.dedent("""\
            type: feedback
            person: Alice
            direction: giving
            category: technical
            follow-up-by: 2026-02-01
            followed-up: false"""))
        with patch("cockpit.data.management.DATA_DIR", tmp_path):
            snap = collect_management_state()
        assert snap.stale_1on1_count >= 1
        assert snap.overdue_coaching_count >= 1
        assert snap.overdue_feedback_count >= 1


class TestDataclassSchema:
    def test_person_defaults(self):
        p = PersonState(name="Test")
        assert p.status == "active"
        assert p.stale_1on1 is False

    def test_management_snapshot_defaults(self):
        s = ManagementSnapshot()
        assert s.people == []
        assert s.active_people_count == 0
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_management.py -v`
Expected: FAIL (no `_parse_frontmatter` export, `collect_management_state` returns empty)

**Step 3: Implement the collector**

Rewrite `logos/data/management.py` to scan `DATA_DIR`:

```python
"""cockpit.data.management — Collect management state from data/ directory.

Reads structured markdown files with YAML frontmatter from DATA_DIR
subdirectories (people/, coaching/, feedback/, meetings/).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

from shared.config import DATA_DIR

_log = logging.getLogger(__name__)

# ── Frontmatter parsing ──────────────────────────────────────────────────────

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown file. Returns (metadata, body)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}, ""
    m = _FM_RE.match(raw)
    if not m:
        return {}, raw
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, raw
    return meta, m.group(2)


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class PersonState:
    name: str
    team: str = ""
    role: str = "direct-report"
    cadence: str = ""
    status: str = "active"
    cognitive_load: str = ""
    growth_vector: str = ""
    feedback_style: str = ""
    last_1on1: str = ""
    coaching_active: bool = False
    stale_1on1: bool = False
    days_since_1on1: int = 0
    file_path: str = ""
    career_goal_3y: str = ""
    current_gaps: str = ""
    current_focus: str = ""
    last_career_convo: str = ""
    team_type: str = ""
    interaction_mode: str = ""
    skill_level: str = ""
    will_signal: str = ""
    domains: list[str] = field(default_factory=list)
    relationship: str = ""


@dataclass
class CoachingState:
    title: str = ""
    person: str = ""
    status: str = "active"
    check_in_by: str = ""
    overdue: bool = False
    days_overdue: int = 0
    file_path: str = ""


@dataclass
class FeedbackState:
    title: str = ""
    person: str = ""
    direction: str = ""
    category: str = ""
    follow_up_by: str = ""
    followed_up: bool = False
    overdue: bool = False
    days_overdue: int = 0
    file_path: str = ""


@dataclass
class ManagementSnapshot:
    people: list[PersonState] = field(default_factory=list)
    coaching: list[CoachingState] = field(default_factory=list)
    feedback: list[FeedbackState] = field(default_factory=list)
    stale_1on1_count: int = 0
    overdue_coaching_count: int = 0
    overdue_feedback_count: int = 0
    high_load_count: int = 0
    active_people_count: int = 0


# ── Staleness computation ─────────────────────────────────────────────────────

_CADENCE_DAYS = {"weekly": 10, "biweekly": 17, "monthly": 35}


def _compute_1on1_staleness(person: PersonState) -> None:
    """Compute stale_1on1 and days_since_1on1 in-place."""
    if not person.last_1on1:
        return
    try:
        last = datetime.strptime(person.last_1on1, "%Y-%m-%d").date()
    except ValueError:
        return
    person.days_since_1on1 = (date.today() - last).days
    threshold = _CADENCE_DAYS.get(person.cadence, 14)
    person.stale_1on1 = person.days_since_1on1 > threshold


# ── Collectors ────────────────────────────────────────────────────────────────

def _collect_people() -> list[PersonState]:
    people_dir = DATA_DIR / "people"
    if not people_dir.is_dir():
        return []
    result = []
    for f in sorted(people_dir.glob("*.md")):
        meta, _ = _parse_frontmatter(f)
        if meta.get("type") != "person":
            continue
        p = PersonState(
            name=meta.get("name", f.stem.replace("-", " ").title()),
            team=str(meta.get("team", "")),
            role=str(meta.get("role", "direct-report")),
            cadence=str(meta.get("cadence", "")),
            status=str(meta.get("status", "active")),
            cognitive_load=str(meta.get("cognitive-load", "")),
            growth_vector=str(meta.get("growth-vector", "")),
            feedback_style=str(meta.get("feedback-style", "")),
            last_1on1=str(meta.get("last-1on1", "")),
            coaching_active=bool(meta.get("coaching-active", False)),
            file_path=str(f),
            career_goal_3y=str(meta.get("career-goal-3y", "")),
            current_gaps=str(meta.get("current-gaps", "")),
            current_focus=str(meta.get("current-focus", "")),
            last_career_convo=str(meta.get("last-career-convo", "")),
            team_type=str(meta.get("team-type", "")),
            interaction_mode=str(meta.get("interaction-mode", "")),
            skill_level=str(meta.get("skill-level", "")),
            will_signal=str(meta.get("will-signal", "")),
            domains=meta.get("domains", []) or [],
            relationship=str(meta.get("relationship", "")),
        )
        _compute_1on1_staleness(p)
        result.append(p)
    return result


def _collect_coaching() -> list[CoachingState]:
    coaching_dir = DATA_DIR / "coaching"
    if not coaching_dir.is_dir():
        return []
    result = []
    for f in sorted(coaching_dir.glob("*.md")):
        meta, _ = _parse_frontmatter(f)
        if meta.get("type") != "coaching":
            continue
        check_in = str(meta.get("check-in-by", ""))
        overdue = False
        days_overdue = 0
        if check_in:
            try:
                check_date = datetime.strptime(check_in, "%Y-%m-%d").date()
                days_overdue = (date.today() - check_date).days
                overdue = days_overdue > 0
            except ValueError:
                pass
        result.append(CoachingState(
            title=meta.get("title", f.stem.replace("-", " ").title()),
            person=str(meta.get("person", "")),
            status=str(meta.get("status", "active")),
            check_in_by=check_in,
            overdue=overdue,
            days_overdue=max(0, days_overdue),
            file_path=str(f),
        ))
    return result


def _collect_feedback() -> list[FeedbackState]:
    feedback_dir = DATA_DIR / "feedback"
    if not feedback_dir.is_dir():
        return []
    result = []
    for f in sorted(feedback_dir.glob("*.md")):
        meta, _ = _parse_frontmatter(f)
        if meta.get("type") != "feedback":
            continue
        follow_up = str(meta.get("follow-up-by", ""))
        followed_up = bool(meta.get("followed-up", False))
        overdue = False
        days_overdue = 0
        if follow_up and not followed_up:
            try:
                fu_date = datetime.strptime(follow_up, "%Y-%m-%d").date()
                days_overdue = (date.today() - fu_date).days
                overdue = days_overdue > 0
            except ValueError:
                pass
        result.append(FeedbackState(
            title=meta.get("title", f.stem.replace("-", " ").title()),
            person=str(meta.get("person", "")),
            direction=str(meta.get("direction", "")),
            category=str(meta.get("category", "")),
            follow_up_by=follow_up,
            followed_up=followed_up,
            overdue=overdue,
            days_overdue=max(0, days_overdue),
            file_path=str(f),
        ))
    return result


# ── Main entry point ──────────────────────────────────────────────────────────

def collect_management_state() -> ManagementSnapshot:
    """Scan DATA_DIR subdirectories and build a complete management snapshot."""
    people = _collect_people()
    coaching = _collect_coaching()
    feedback = _collect_feedback()

    active = [p for p in people if p.status == "active"]

    return ManagementSnapshot(
        people=people,
        coaching=coaching,
        feedback=feedback,
        stale_1on1_count=sum(1 for p in active if p.stale_1on1),
        overdue_coaching_count=sum(1 for c in coaching if c.overdue),
        overdue_feedback_count=sum(1 for f in feedback if f.overdue),
        high_load_count=sum(1 for p in active if p.cognitive_load in ("high", "critical")),
        active_people_count=len(active),
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_management.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All pass

**Step 6: Commit**

```bash
git add logos/data/management.py tests/test_management.py
git commit -m "feat: rehydrate management collector to read from DATA_DIR"
```

---

### Task 3: Rehydrate shared/management_bridge.py

**Files:**
- Modify: `shared/management_bridge.py`
- Test: `tests/test_management_bridge.py`

**Step 1: Write failing tests**

```python
"""Tests for shared.management_bridge — generates profile facts from DATA_DIR."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch

from shared.management_bridge import generate_facts, _make_fact, save_facts


def _write_md(path: Path, frontmatter: str, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n{body}")


class TestGenerateFacts:
    def test_people_facts(self, tmp_path):
        _write_md(tmp_path / "people" / "alice.md",
                  "type: person\nname: Alice\nstatus: active\nteam: Platform\nrole: senior")
        with patch("shared.management_bridge.DATA_DIR", tmp_path):
            facts = generate_facts()
        people_facts = [f for f in facts if f["dimension"] == "team_leadership"]
        assert len(people_facts) >= 1
        assert any("Alice" in f["text"] for f in people_facts)

    def test_coaching_facts(self, tmp_path):
        _write_md(tmp_path / "coaching" / "alice-growth.md",
                  "type: coaching\nperson: Alice\nstatus: active")
        (tmp_path / "people").mkdir(exist_ok=True)
        (tmp_path / "feedback").mkdir(exist_ok=True)
        (tmp_path / "meetings").mkdir(exist_ok=True)
        with patch("shared.management_bridge.DATA_DIR", tmp_path):
            facts = generate_facts()
        coaching_facts = [f for f in facts if f["dimension"] == "management_practice"]
        assert len(coaching_facts) >= 1

    def test_empty_dirs(self, tmp_path):
        for d in ("people", "coaching", "feedback", "meetings"):
            (tmp_path / d).mkdir()
        with patch("shared.management_bridge.DATA_DIR", tmp_path):
            facts = generate_facts()
        assert facts == []

    def test_returns_list_of_dicts(self, tmp_path):
        _write_md(tmp_path / "people" / "bob.md",
                  "type: person\nname: Bob\nstatus: active")
        with patch("shared.management_bridge.DATA_DIR", tmp_path):
            facts = generate_facts()
        for f in facts:
            assert "text" in f
            assert "dimension" in f
            assert "source" in f


class TestMakeFact:
    def test_fact_structure(self):
        f = _make_fact("test text", "team_leadership", "test_source")
        assert f["text"] == "test text"
        assert f["dimension"] == "team_leadership"
        assert f["source"] == "test_source"
        assert "timestamp" in f


class TestSaveFacts:
    def test_writes_json(self, tmp_path):
        with patch("shared.management_bridge.PROFILES_DIR", tmp_path):
            path = save_facts([{"text": "test", "dimension": "d", "source": "s"}])
        assert path.exists()
        import json
        data = json.loads(path.read_text())
        assert len(data) == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_management_bridge.py -v`
Expected: FAIL (`generate_facts` returns `[]` unconditionally)

**Step 3: Implement the bridge**

Rehydrate `shared/management_bridge.py`:

```python
"""management_bridge.py — Management data source bridge.

Reads structured markdown from DATA_DIR to generate profile-compatible
facts for the management profiler and other consumers.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from shared.config import DATA_DIR, PROFILES_DIR

_log = logging.getLogger(__name__)

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}, ""
    m = _FM_RE.match(raw)
    if not m:
        return {}, raw
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, raw
    return meta, m.group(2)


def _make_fact(text: str, dimension: str, source: str) -> dict:
    return {
        "text": text,
        "dimension": dimension,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _people_facts() -> list[dict]:
    people_dir = DATA_DIR / "people"
    if not people_dir.is_dir():
        return []
    facts = []
    for f in people_dir.glob("*.md"):
        meta, _ = _parse_frontmatter(f)
        if meta.get("type") != "person" or meta.get("status") != "active":
            continue
        name = meta.get("name", f.stem.replace("-", " ").title())
        team = meta.get("team", "")
        role = meta.get("role", "")
        if team:
            facts.append(_make_fact(
                f"{name} is on {team} team (role: {role})",
                "team_leadership", f"data/people/{f.name}"))
        cadence = meta.get("cadence", "")
        if cadence:
            facts.append(_make_fact(
                f"1:1 cadence with {name}: {cadence}",
                "management_practice", f"data/people/{f.name}"))
    return facts


def _coaching_facts() -> list[dict]:
    coaching_dir = DATA_DIR / "coaching"
    if not coaching_dir.is_dir():
        return []
    facts = []
    for f in coaching_dir.glob("*.md"):
        meta, body = _parse_frontmatter(f)
        if meta.get("type") != "coaching":
            continue
        person = meta.get("person", "")
        status = meta.get("status", "")
        title = meta.get("title", f.stem.replace("-", " ").title())
        facts.append(_make_fact(
            f"Coaching hypothesis for {person}: {title} (status: {status})",
            "management_practice", f"data/coaching/{f.name}"))
    return facts


def _feedback_facts() -> list[dict]:
    feedback_dir = DATA_DIR / "feedback"
    if not feedback_dir.is_dir():
        return []
    facts = []
    for f in feedback_dir.glob("*.md"):
        meta, _ = _parse_frontmatter(f)
        if meta.get("type") != "feedback":
            continue
        person = meta.get("person", "")
        direction = meta.get("direction", "")
        category = meta.get("category", "")
        facts.append(_make_fact(
            f"Feedback record ({direction}) for {person}: {category}",
            "management_practice", f"data/feedback/{f.name}"))
    return facts


def _meeting_facts() -> list[dict]:
    meetings_dir = DATA_DIR / "meetings"
    if not meetings_dir.is_dir():
        return []
    facts = []
    for f in sorted(meetings_dir.glob("*.md"), reverse=True)[:20]:
        meta, _ = _parse_frontmatter(f)
        if meta.get("type") != "meeting":
            continue
        title = meta.get("title", f.stem.replace("-", " ").title())
        meeting_date = meta.get("date", "")
        facts.append(_make_fact(
            f"Meeting: {title} ({meeting_date})",
            "attention_distribution", f"data/meetings/{f.name}"))
    return facts


def generate_facts(vault_path: Path | None = None) -> list[dict]:
    """Generate profile-compatible facts from DATA_DIR management data.

    The vault_path parameter is retained for API compatibility but ignored.
    All data is read from DATA_DIR.
    """
    all_facts = []
    all_facts.extend(_people_facts())
    all_facts.extend(_coaching_facts())
    all_facts.extend(_feedback_facts())
    all_facts.extend(_meeting_facts())
    if all_facts:
        _log.info("management_bridge: generated %d facts from %s", len(all_facts), DATA_DIR)
    else:
        _log.info("management_bridge: no management data found in %s", DATA_DIR)
    return all_facts


def save_facts(facts: list[dict]) -> Path:
    """Persist structured facts to profiles directory."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILES_DIR / "management-structured-facts.json"
    path.write_text(json.dumps(facts, indent=2))
    _log.info("Saved %d facts to %s", len(facts), path)
    return path
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_management_bridge.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/management_bridge.py tests/test_management_bridge.py
git commit -m "feat: rehydrate management_bridge to read facts from DATA_DIR"
```

---

### Task 4: Rehydrate shared/vault_writer.py

Rename to `data_writer.py` since it no longer writes to a vault.

**Files:**
- Modify: `shared/vault_writer.py`
- Test: `tests/test_vault_writer.py`

**Step 1: Write failing tests**

```python
"""Tests for shared.vault_writer — writes management data to DATA_DIR."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch

import yaml

from shared.vault_writer import (
    write_to_vault,
    write_briefing_to_vault,
    write_1on1_prep_to_vault,
    create_coaching_starter,
    create_fb_record_starter,
    create_decision_starter,
)


class TestWriteToVault:
    def test_creates_file_with_frontmatter(self, tmp_path):
        with patch("shared.vault_writer.DATA_DIR", tmp_path):
            result = write_to_vault("people", "alice.md", "# Alice",
                                    frontmatter={"type": "person", "name": "Alice"})
        assert result is not None
        assert result.exists()
        content = result.read_text()
        assert "---" in content
        assert "type: person" in content
        assert "# Alice" in content

    def test_creates_file_without_frontmatter(self, tmp_path):
        with patch("shared.vault_writer.DATA_DIR", tmp_path):
            result = write_to_vault("references", "article.md", "Some content")
        assert result is not None
        assert result.read_text() == "Some content"

    def test_creates_parent_dirs(self, tmp_path):
        with patch("shared.vault_writer.DATA_DIR", tmp_path):
            result = write_to_vault("people", "nested.md", "test")
        assert (tmp_path / "people" / "nested.md").exists()


class TestBriefing:
    def test_writes_briefing(self, tmp_path):
        with patch("shared.vault_writer.DATA_DIR", tmp_path):
            result = write_briefing_to_vault("# Morning Briefing\nAll clear.")
        assert result is not None
        assert "briefing" in str(result).lower() or "references" in str(result).lower()


class TestPrepWriter:
    def test_writes_prep_doc(self, tmp_path):
        with patch("shared.vault_writer.DATA_DIR", tmp_path):
            result = write_1on1_prep_to_vault("Alice", "# Prep for Alice")
        assert result is not None
        assert result.exists()


class TestCoachingStarter:
    def test_creates_coaching_file(self, tmp_path):
        with patch("shared.vault_writer.DATA_DIR", tmp_path):
            result = create_coaching_starter("Alice", "Shows strong ownership")
        assert result is not None
        content = result.read_text()
        assert "type: coaching" in content
        assert "Alice" in content


class TestFeedbackStarter:
    def test_creates_feedback_file(self, tmp_path):
        with patch("shared.vault_writer.DATA_DIR", tmp_path):
            result = create_fb_record_starter("Alice", "Great code review")
        assert result is not None
        content = result.read_text()
        assert "type: feedback" in content
        assert "Alice" in content


class TestDecisionStarter:
    def test_creates_decision_file(self, tmp_path):
        with patch("shared.vault_writer.DATA_DIR", tmp_path):
            result = create_decision_starter("Use Postgres", "Architecture meeting")
        assert result is not None
        content = result.read_text()
        assert "type: decision" in content
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_vault_writer.py -v`
Expected: FAIL (all functions return `None`)

**Step 3: Implement the writer**

```python
"""vault_writer.py — Write management data to DATA_DIR.

Retained name for import compatibility. All writes target DATA_DIR
subdirectories using structured markdown with YAML frontmatter.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import yaml

from shared.config import DATA_DIR

_log = logging.getLogger(__name__)


def _ensure_dir(subdir: str) -> Path:
    d = DATA_DIR / subdir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_md(path: Path, content: str, frontmatter: dict | None = None) -> Path:
    if frontmatter:
        fm = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).strip()
        path.write_text(f"---\n{fm}\n---\n{content}", encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")
    _log.info("Wrote %s", path)
    return path


def write_to_vault(
    folder: str, filename: str, content: str,
    frontmatter: dict | None = None,
) -> Path | None:
    """Write a markdown file to DATA_DIR/folder/filename."""
    d = _ensure_dir(folder)
    return _write_md(d / filename, content, frontmatter)


def write_briefing_to_vault(briefing_md: str) -> Path | None:
    today = date.today().isoformat()
    d = _ensure_dir("references")
    fm = {"type": "briefing", "date": today}
    return _write_md(d / f"briefing-{today}.md", briefing_md, fm)


def write_digest_to_vault(digest_md: str) -> Path | None:
    today = date.today().isoformat()
    d = _ensure_dir("references")
    fm = {"type": "digest", "date": today}
    return _write_md(d / f"digest-{today}.md", digest_md, fm)


def write_nudges_to_vault(nudges: list[dict]) -> Path | None:
    d = _ensure_dir("references")
    lines = ["# Active Nudges\n"]
    for n in nudges:
        lines.append(f"- [ ] **{n.get('title', 'Untitled')}** — {n.get('reason', '')}")
    fm = {"type": "nudges", "date": date.today().isoformat()}
    return _write_md(d / "nudges.md", "\n".join(lines), fm)


def write_goals_to_vault(goals: list[dict]) -> Path | None:
    d = _ensure_dir("references")
    lines = ["# Goals\n"]
    for g in goals:
        lines.append(f"## {g.get('name', 'Unnamed')}\n{g.get('description', '')}\n")
    fm = {"type": "goals", "date": date.today().isoformat()}
    return _write_md(d / "goals.md", "\n".join(lines), fm)


def write_1on1_prep_to_vault(person_name: str, prep_md: str) -> Path | None:
    today = date.today().isoformat()
    slug = person_name.lower().replace(" ", "-")
    d = _ensure_dir("meetings")
    fm = {"type": "meeting", "subtype": "prep", "person": person_name, "date": today}
    return _write_md(d / f"prep-{slug}-{today}.md", prep_md, fm)


def write_team_snapshot_to_vault(snapshot_md: str) -> Path | None:
    today = date.today().isoformat()
    d = _ensure_dir("references")
    fm = {"type": "team-snapshot", "date": today}
    return _write_md(d / f"team-snapshot-{today}.md", snapshot_md, fm)


def write_management_overview_to_vault(overview_md: str) -> Path | None:
    today = date.today().isoformat()
    d = _ensure_dir("references")
    fm = {"type": "overview", "date": today}
    return _write_md(d / f"overview-{today}.md", overview_md, fm)


def create_coaching_starter(person: str, observation: str) -> Path | None:
    today = date.today().isoformat()
    slug = person.lower().replace(" ", "-")
    d = _ensure_dir("coaching")
    fm = {
        "type": "coaching",
        "person": person,
        "status": "active",
        "date": today,
        "check-in-by": "",
    }
    body = f"# Coaching: {person}\n\n## Observation\n\n{observation}\n\n## Hypothesis\n\n\n\n## Plan\n\n"
    return _write_md(d / f"{slug}-{today}.md", body, fm)


def create_fb_record_starter(person: str, fb_moment: str) -> Path | None:
    today = date.today().isoformat()
    slug = person.lower().replace(" ", "-")
    d = _ensure_dir("feedback")
    fm = {
        "type": "feedback",
        "person": person,
        "direction": "giving",
        "category": "",
        "date": today,
        "follow-up-by": "",
        "followed-up": False,
    }
    body = f"# Feedback: {person}\n\n## Moment\n\n{fb_moment}\n\n## Context\n\n\n\n## Notes\n\n"
    return _write_md(d / f"{slug}-{today}.md", body, fm)


def create_decision_starter(decision_text: str, meeting_ref: str = "") -> Path | None:
    today = date.today().isoformat()
    slug = decision_text[:40].lower().replace(" ", "-").rstrip("-")
    d = _ensure_dir("decisions")
    fm = {
        "type": "decision",
        "date": today,
        "meeting": meeting_ref,
        "status": "decided",
    }
    body = f"# Decision\n\n{decision_text}\n\n## Context\n\n{meeting_ref}\n\n## Reasoning\n\n"
    return _write_md(d / f"{slug}-{today}.md", body, fm)


def write_bridge_prompt_to_vault(prompt_name: str, prompt_md: str) -> Path | None:
    d = _ensure_dir("references")
    fm = {"type": "prompt", "name": prompt_name, "date": date.today().isoformat()}
    return _write_md(d / f"prompt-{prompt_name}.md", prompt_md, fm)
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_vault_writer.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All pass

**Step 6: Commit**

```bash
git add shared/vault_writer.py tests/test_vault_writer.py
git commit -m "feat: rehydrate vault_writer to write management data to DATA_DIR"
```

---

### Task 5: Document Ingestion Agent — Classifier and Router

**Files:**
- Create: `agents/ingest.py`
- Test: `tests/test_ingest.py`

**Step 1: Write failing tests**

```python
"""Tests for agents.ingest — document classifier and router."""
from __future__ import annotations
import textwrap
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from agents.ingest import (
    classify_document,
    DocumentType,
    process_document,
    _detect_transcript,
    _detect_frontmatter_type,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestDetectTranscript:
    def test_vtt_extension(self, tmp_path):
        f = tmp_path / "meeting.vtt"
        f.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nHello")
        assert _detect_transcript(f) is True

    def test_srt_extension(self, tmp_path):
        f = tmp_path / "meeting.srt"
        f.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello")
        assert _detect_transcript(f) is True

    def test_md_with_speaker_turns(self, tmp_path):
        f = tmp_path / "meeting.md"
        f.write_text("Speaker 1: Hello\nSpeaker 2: Hi\nSpeaker 1: How are you")
        assert _detect_transcript(f) is True

    def test_normal_md(self, tmp_path):
        f = tmp_path / "notes.md"
        f.write_text("# My notes\nSome content here")
        assert _detect_transcript(f) is False


class TestDetectFrontmatterType:
    def test_person_type(self, tmp_path):
        f = tmp_path / "alice.md"
        _write(f, "---\ntype: person\nname: Alice\n---\n# Alice")
        assert _detect_frontmatter_type(f) == "person"

    def test_meeting_type(self, tmp_path):
        f = tmp_path / "standup.md"
        _write(f, "---\ntype: meeting\n---\n# Standup")
        assert _detect_frontmatter_type(f) == "meeting"

    def test_no_frontmatter(self, tmp_path):
        f = tmp_path / "notes.md"
        f.write_text("Just some notes")
        assert _detect_frontmatter_type(f) is None


class TestClassifyDocument:
    def test_transcript_by_extension(self, tmp_path):
        f = tmp_path / "meeting.vtt"
        f.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nHello")
        assert classify_document(f) == DocumentType.TRANSCRIPT

    def test_person_by_frontmatter(self, tmp_path):
        f = tmp_path / "alice.md"
        _write(f, "---\ntype: person\nname: Alice\n---\n")
        assert classify_document(f) == DocumentType.PERSON

    def test_feedback_by_frontmatter(self, tmp_path):
        f = tmp_path / "fb.md"
        _write(f, "---\ntype: feedback\nperson: Alice\n---\n")
        assert classify_document(f) == DocumentType.FEEDBACK

    def test_coaching_by_frontmatter(self, tmp_path):
        f = tmp_path / "ch.md"
        _write(f, "---\ntype: coaching\nperson: Alice\n---\n")
        assert classify_document(f) == DocumentType.COACHING

    def test_decision_by_frontmatter(self, tmp_path):
        f = tmp_path / "dec.md"
        _write(f, "---\ntype: decision\n---\n")
        assert classify_document(f) == DocumentType.DECISION

    def test_meeting_by_frontmatter(self, tmp_path):
        f = tmp_path / "m.md"
        _write(f, "---\ntype: meeting\n---\n")
        assert classify_document(f) == DocumentType.MEETING

    def test_unstructured_fallback(self, tmp_path):
        f = tmp_path / "random.md"
        f.write_text("Some random text without structure")
        assert classify_document(f) == DocumentType.UNSTRUCTURED


class TestProcessDocument:
    @pytest.mark.asyncio
    async def test_files_person_note(self, tmp_path):
        f = tmp_path / "inbox" / "alice.md"
        _write(f, "---\ntype: person\nname: Alice\nstatus: active\n---\n# Alice")
        data_dir = tmp_path / "data"
        (data_dir / "people").mkdir(parents=True)
        (data_dir / "processed").mkdir(parents=True)

        with patch("agents.ingest.DATA_DIR", data_dir):
            result = await process_document(f)
        assert result.success is True
        assert (data_dir / "people" / "alice.md").exists()

    @pytest.mark.asyncio
    async def test_files_feedback(self, tmp_path):
        f = tmp_path / "fb.md"
        _write(f, "---\ntype: feedback\nperson: Bob\ndirection: giving\n---\n# Feedback")
        data_dir = tmp_path / "data"
        (data_dir / "feedback").mkdir(parents=True)
        (data_dir / "processed").mkdir(parents=True)

        with patch("agents.ingest.DATA_DIR", data_dir):
            result = await process_document(f)
        assert result.success is True
        assert (data_dir / "feedback" / "fb.md").exists()
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_ingest.py -v`
Expected: FAIL (`agents.ingest` doesn't exist)

**Step 3: Implement the ingest agent**

Create `agents/ingest.py`:

```python
"""agents.ingest — Document classifier and router.

Classifies incoming documents and routes them to the appropriate DATA_DIR
subdirectory. Supports explicit invocation and watch-folder mode.

Usage:
    uv run python -m agents.ingest <file>                    # Classify and process
    uv run python -m agents.ingest --type transcript <file>  # Skip classification
    uv run python -m agents.ingest --watch                   # Watch data/inbox/
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

import yaml

from shared.config import DATA_DIR
from shared.notify import send_notification

_log = logging.getLogger(__name__)


class DocumentType(str, Enum):
    TRANSCRIPT = "transcript"
    MEETING = "meeting"
    PERSON = "person"
    COACHING = "coaching"
    FEEDBACK = "feedback"
    DECISION = "decision"
    REFERENCE = "reference"
    UNSTRUCTURED = "unstructured"


_TYPE_TO_DIR = {
    DocumentType.MEETING: "meetings",
    DocumentType.PERSON: "people",
    DocumentType.COACHING: "coaching",
    DocumentType.FEEDBACK: "feedback",
    DocumentType.DECISION: "decisions",
    DocumentType.REFERENCE: "references",
    DocumentType.UNSTRUCTURED: "references",
}

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)

# Speaker-turn patterns: "Name:", "Speaker 1:", "SPEAKER:", etc.
_SPEAKER_RE = re.compile(r"^(?:Speaker\s+\d+|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*:", re.MULTILINE)


@dataclass
class ProcessResult:
    success: bool
    doc_type: DocumentType
    destination: Path | None = None
    outputs: list[str] | None = None
    error: str | None = None


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}, ""
    m = _FM_RE.match(raw)
    if not m:
        return {}, raw
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, raw
    return meta, m.group(2)


def _detect_transcript(path: Path) -> bool:
    """Detect if file is a meeting transcript."""
    suffix = path.suffix.lower()
    if suffix in (".vtt", ".srt"):
        return True
    if suffix == ".md":
        try:
            text = path.read_text(encoding="utf-8")[:2000]
        except (OSError, UnicodeDecodeError):
            return False
        matches = _SPEAKER_RE.findall(text)
        return len(matches) >= 3
    return False


def _detect_frontmatter_type(path: Path) -> str | None:
    """Return the type field from frontmatter, or None."""
    meta, _ = _parse_frontmatter(path)
    return meta.get("type")


def classify_document(path: Path) -> DocumentType:
    """Classify a document by extension and content."""
    if _detect_transcript(path):
        return DocumentType.TRANSCRIPT

    fm_type = _detect_frontmatter_type(path)
    if fm_type:
        type_map = {
            "person": DocumentType.PERSON,
            "meeting": DocumentType.MEETING,
            "coaching": DocumentType.COACHING,
            "feedback": DocumentType.FEEDBACK,
            "decision": DocumentType.DECISION,
            "reference": DocumentType.REFERENCE,
        }
        return type_map.get(fm_type, DocumentType.UNSTRUCTURED)

    return DocumentType.UNSTRUCTURED


async def process_document(path: Path, doc_type: DocumentType | None = None) -> ProcessResult:
    """Process a single document: classify, route, generate outputs."""
    if doc_type is None:
        doc_type = classify_document(path)

    _log.info("Processing %s as %s", path.name, doc_type.value)

    if doc_type == DocumentType.TRANSCRIPT:
        return await _process_transcript(path)

    # For typed documents, copy to appropriate directory
    target_dir_name = _TYPE_TO_DIR.get(doc_type, "references")
    target_dir = DATA_DIR / target_dir_name
    target_dir.mkdir(parents=True, exist_ok=True)

    dest = target_dir / path.name
    shutil.copy2(path, dest)

    return ProcessResult(
        success=True,
        doc_type=doc_type,
        destination=dest,
        outputs=[f"Filed to {target_dir_name}/"],
    )


async def _process_transcript(path: Path) -> ProcessResult:
    """Process a meeting transcript — generate meeting note and starters.

    Full LLM-powered transcript processing will be implemented when the
    meeting_lifecycle agent is updated. For now, file to meetings/.
    """
    target_dir = DATA_DIR / "meetings"
    target_dir.mkdir(parents=True, exist_ok=True)

    # Convert .vtt/.srt to .md with meeting frontmatter
    stem = path.stem
    today = datetime.now().strftime("%Y-%m-%d")
    dest_name = f"{today}-{stem}.md" if not stem.startswith("20") else f"{stem}.md"
    dest = target_dir / dest_name

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return ProcessResult(success=False, doc_type=DocumentType.TRANSCRIPT, error=str(e))

    fm = {"type": "meeting", "date": today, "source": "transcript", "original": path.name}
    fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False).strip()
    dest.write_text(f"---\n{fm_str}\n---\n{content}", encoding="utf-8")

    return ProcessResult(
        success=True,
        doc_type=DocumentType.TRANSCRIPT,
        destination=dest,
        outputs=["Filed transcript to meetings/"],
    )


async def _watch_inbox(poll_interval: float = 30.0) -> None:
    """Watch DATA_DIR/inbox/ for new files, process them."""
    inbox = DATA_DIR / "inbox"
    processed_dir = DATA_DIR / "processed"
    inbox.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    _log.info("Watching %s (poll every %.0fs)", inbox, poll_interval)

    while True:
        for f in inbox.iterdir():
            if f.name.startswith(".") or f.name in seen:
                continue
            if f.is_file():
                seen.add(f.name)
                try:
                    result = await process_document(f)
                    # Move to processed
                    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                    dest = processed_dir / f"{ts}-{f.name}"
                    shutil.move(str(f), dest)
                    if result.success:
                        send_notification(
                            f"Ingested: {f.name}",
                            f"Type: {result.doc_type.value}. {', '.join(result.outputs or [])}",
                            tags=["inbox"],
                        )
                    else:
                        send_notification(
                            f"Ingest failed: {f.name}",
                            result.error or "Unknown error",
                            priority="high",
                            tags=["warning"],
                        )
                except Exception as exc:
                    _log.exception("Failed to process %s", f.name)
                    send_notification(
                        f"Ingest error: {f.name}",
                        str(exc)[:200],
                        priority="high",
                        tags=["warning"],
                    )
        await asyncio.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Document ingestion pipeline")
    parser.add_argument("file", nargs="?", help="File to process")
    parser.add_argument("--type", choices=[t.value for t in DocumentType],
                        help="Skip classification, use this type")
    parser.add_argument("--watch", action="store_true",
                        help="Watch data/inbox/ for new files")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.watch:
        asyncio.run(_watch_inbox())
    elif args.file:
        path = Path(args.file).resolve()
        if not path.exists():
            _log.error("File not found: %s", path)
            raise SystemExit(1)
        doc_type = DocumentType(args.type) if args.type else None
        result = asyncio.run(process_document(path, doc_type))
        if result.success:
            print(f"Processed: {result.doc_type.value} → {result.destination}")
            if result.outputs:
                for o in result.outputs:
                    print(f"  {o}")
        else:
            print(f"Failed: {result.error}")
            raise SystemExit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_ingest.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/ingest.py tests/test_ingest.py
git commit -m "feat: add document ingestion agent with classifier and router"
```

---

### Task 6: Status Update Agent

**Files:**
- Create: `agents/status_update.py`
- Test: `tests/test_status_update.py`

**Step 1: Write failing tests**

```python
"""Tests for agents.status_update — upward-facing status reports."""
from __future__ import annotations
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from agents.status_update import (
    StatusReport,
    _gather_week_context,
)


class TestGatherWeekContext:
    def test_returns_context_dict(self, tmp_path):
        for d in ("meetings", "coaching", "feedback", "people"):
            (tmp_path / d).mkdir(parents=True)
        with patch("agents.status_update.DATA_DIR", tmp_path):
            ctx = _gather_week_context(days=7)
        assert "meetings" in ctx
        assert "coaching" in ctx
        assert "feedback" in ctx
        assert isinstance(ctx["meetings"], list)

    def test_filters_by_date(self, tmp_path):
        (tmp_path / "meetings").mkdir()
        (tmp_path / "coaching").mkdir()
        (tmp_path / "feedback").mkdir()
        (tmp_path / "people").mkdir()
        # Write a meeting from today
        from datetime import date
        today = date.today().isoformat()
        f = tmp_path / "meetings" / f"{today}-standup.md"
        f.write_text(f"---\ntype: meeting\ndate: {today}\n---\n# Standup")
        with patch("agents.status_update.DATA_DIR", tmp_path):
            ctx = _gather_week_context(days=7)
        assert len(ctx["meetings"]) == 1


class TestStatusReport:
    def test_model_fields(self):
        r = StatusReport(
            headline="Good week",
            themes=["Shipped feature X"],
            risks=[],
            wins=["Feature X launched"],
            asks=[],
        )
        assert r.headline == "Good week"
        assert len(r.themes) == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_status_update.py -v`
Expected: FAIL

**Step 3: Implement**

Create `agents/status_update.py`:

```python
"""agents.status_update — Upward-facing status report generator.

Generates "Week in Review" style status reports (Lara Hogan pattern).
Consumes week's meetings, coaching activity, nudge state, team health.
Produces: headline, themes from 1:1s, risks/blockers, wins, asks.

Usage:
    uv run python -m agents.status_update           # Weekly
    uv run python -m agents.status_update --daily   # Daily
    uv run python -m agents.status_update --save    # Save to DATA_DIR
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from shared.config import DATA_DIR, get_model

_log = logging.getLogger(__name__)

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


class StatusReport(BaseModel):
    headline: str = Field(description="One-sentence summary of the period")
    themes: list[str] = Field(default_factory=list, description="Key themes from 1:1s and meetings")
    risks: list[str] = Field(default_factory=list, description="Risks and blockers")
    wins: list[str] = Field(default_factory=list, description="Wins and accomplishments")
    asks: list[str] = Field(default_factory=list, description="Asks / needs from leadership")


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}, ""
    m = _FM_RE.match(raw)
    if not m:
        return {}, raw
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, raw
    return meta, m.group(2)


def _gather_week_context(days: int = 7) -> dict:
    """Gather management data from the last N days."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    def _recent_files(subdir: str) -> list[dict]:
        d = DATA_DIR / subdir
        if not d.is_dir():
            return []
        results = []
        for f in d.glob("*.md"):
            meta, body = _parse_frontmatter(f)
            file_date = str(meta.get("date", ""))
            if file_date >= cutoff or not file_date:
                results.append({"meta": meta, "body": body[:1000], "file": f.name})
        return results

    return {
        "meetings": _recent_files("meetings"),
        "coaching": _recent_files("coaching"),
        "feedback": _recent_files("feedback"),
    }


async def generate_status(days: int = 7, save: bool = False) -> StatusReport:
    """Generate a status report for the last N days."""
    from pydantic_ai import Agent

    ctx = _gather_week_context(days)

    context_text = []
    for category, items in ctx.items():
        if items:
            context_text.append(f"## {category.title()} ({len(items)} items)")
            for item in items:
                title = item["meta"].get("title", item["file"])
                context_text.append(f"- {title}: {item['body'][:200]}")

    if not any(ctx.values()):
        _log.warning("No recent management data found for status report")
        return StatusReport(headline="No management data available for this period")

    agent = Agent(
        get_model("balanced"),
        output_type=StatusReport,
        system_prompt=(
            "You generate concise upward-facing status reports for an engineering manager. "
            "Focus on themes, patterns, and signals — not play-by-play. "
            "Headline should be a single sentence capturing the week's story. "
            "Risks should be actionable. Wins should be specific. "
            "Asks should be clear requests for leadership. "
            "Never generate feedback language about individual team members. "
            "Never suggest what to say to anyone."
        ),
    )

    period = "day" if days <= 1 else f"{days} days"
    result = await agent.run(
        f"Generate a status report for the last {period}.\n\n"
        + "\n".join(context_text)
    )
    report = result.output

    if save:
        _save_report(report, days)

    return report


def _save_report(report: StatusReport, days: int) -> Path:
    today = date.today().isoformat()
    period = "daily" if days <= 1 else "weekly"
    d = DATA_DIR / "references"
    d.mkdir(parents=True, exist_ok=True)

    lines = [f"# Status Update — {today}\n"]
    lines.append(f"**{report.headline}**\n")
    if report.themes:
        lines.append("## Themes")
        for t in report.themes:
            lines.append(f"- {t}")
    if report.wins:
        lines.append("\n## Wins")
        for w in report.wins:
            lines.append(f"- {w}")
    if report.risks:
        lines.append("\n## Risks")
        for r in report.risks:
            lines.append(f"- {r}")
    if report.asks:
        lines.append("\n## Asks")
        for a in report.asks:
            lines.append(f"- {a}")

    fm = {"type": "status-update", "date": today, "period": period}
    fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False).strip()
    path = d / f"status-{period}-{today}.md"
    path.write_text(f"---\n{fm_str}\n---\n" + "\n".join(lines), encoding="utf-8")
    _log.info("Saved status report to %s", path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate upward-facing status report")
    parser.add_argument("--daily", action="store_true", help="Daily report (1 day)")
    parser.add_argument("--save", action="store_true", help="Save to DATA_DIR/references/")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    days = 1 if args.daily else 7
    report = asyncio.run(generate_status(days=days, save=args.save))
    print(f"\n{report.headline}\n")
    if report.themes:
        print("Themes:")
        for t in report.themes:
            print(f"  - {t}")
    if report.wins:
        print("Wins:")
        for w in report.wins:
            print(f"  - {w}")
    if report.risks:
        print("Risks:")
        for r in report.risks:
            print(f"  - {r}")
    if report.asks:
        print("Asks:")
        for a in report.asks:
            print(f"  - {a}")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_status_update.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/status_update.py tests/test_status_update.py
git commit -m "feat: add status_update agent for upward-facing reports"
```

---

### Task 7: Review Prep Agent

**Files:**
- Create: `agents/review_prep.py`
- Test: `tests/test_review_prep.py`

**Step 1: Write failing tests**

```python
"""Tests for agents.review_prep — performance review evidence aggregation."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch

import pytest

from agents.review_prep import (
    ReviewEvidence,
    _gather_person_evidence,
)


def _write_md(path: Path, frontmatter: str, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n{body}")


class TestGatherPersonEvidence:
    def test_collects_meetings(self, tmp_path):
        _write_md(tmp_path / "meetings" / "m1.md",
                  "type: meeting\ndate: 2026-03-01\nattendees:\n  - Alice",
                  "Discussed project progress")
        _write_md(tmp_path / "people" / "alice.md",
                  "type: person\nname: Alice\nstatus: active")
        (tmp_path / "coaching").mkdir()
        (tmp_path / "feedback").mkdir()
        with patch("agents.review_prep.DATA_DIR", tmp_path):
            ev = _gather_person_evidence("Alice", months=6)
        assert len(ev["meetings"]) >= 1

    def test_collects_coaching(self, tmp_path):
        _write_md(tmp_path / "coaching" / "alice-growth.md",
                  "type: coaching\nperson: Alice\nstatus: active",
                  "Hypothesis: Strong ownership")
        (tmp_path / "meetings").mkdir()
        (tmp_path / "feedback").mkdir()
        (tmp_path / "people").mkdir()
        with patch("agents.review_prep.DATA_DIR", tmp_path):
            ev = _gather_person_evidence("Alice", months=6)
        assert len(ev["coaching"]) >= 1

    def test_collects_feedback(self, tmp_path):
        _write_md(tmp_path / "feedback" / "alice-review.md",
                  "type: feedback\nperson: Alice\ndirection: giving",
                  "Great code review")
        (tmp_path / "meetings").mkdir()
        (tmp_path / "coaching").mkdir()
        (tmp_path / "people").mkdir()
        with patch("agents.review_prep.DATA_DIR", tmp_path):
            ev = _gather_person_evidence("Alice", months=6)
        assert len(ev["feedback"]) >= 1

    def test_empty_for_unknown_person(self, tmp_path):
        for d in ("meetings", "coaching", "feedback", "people"):
            (tmp_path / d).mkdir()
        with patch("agents.review_prep.DATA_DIR", tmp_path):
            ev = _gather_person_evidence("Nobody", months=6)
        assert all(len(v) == 0 for v in ev.values())


class TestReviewEvidence:
    def test_model_fields(self):
        r = ReviewEvidence(
            person="Alice",
            period_months=6,
            contributions=["Led migration"],
            growth_trajectory=["Improved code review depth"],
            development_areas=["Public speaking"],
            evidence_citations=["2026-03-01 standup: Led discussion"],
        )
        assert r.person == "Alice"
        assert len(r.contributions) == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_review_prep.py -v`
Expected: FAIL

**Step 3: Implement**

Create `agents/review_prep.py`:

```python
"""agents.review_prep — Performance review evidence aggregation.

Consumes 3-12 months of meetings, coaching, feedback, and profile facts
for a specific person. Produces evidence aggregation: contributions summary,
growth trajectory, development areas, evidence citations.

Safety: Evidence aggregation only. Never generates evaluative language or
ratings. Per management_safety axiom.

Usage:
    uv run python -m agents.review_prep --person "Alice" --months 6
    uv run python -m agents.review_prep --person "Alice" --months 12 --save
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from datetime import date, timedelta
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from shared.config import DATA_DIR, get_model

_log = logging.getLogger(__name__)

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


class ReviewEvidence(BaseModel):
    person: str
    period_months: int
    contributions: list[str] = Field(default_factory=list,
        description="Factual contributions with dates/context")
    growth_trajectory: list[str] = Field(default_factory=list,
        description="Observable growth patterns with evidence")
    development_areas: list[str] = Field(default_factory=list,
        description="Areas with room for growth, evidence-based")
    evidence_citations: list[str] = Field(default_factory=list,
        description="Source citations (file, date, relevant excerpt)")


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}, ""
    m = _FM_RE.match(raw)
    if not m:
        return {}, raw
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, raw
    return meta, m.group(2)


def _gather_person_evidence(person: str, months: int = 6) -> dict[str, list[dict]]:
    """Gather all evidence for a person from the last N months."""
    cutoff = (date.today() - timedelta(days=months * 30)).isoformat()
    person_lower = person.lower()

    evidence: dict[str, list[dict]] = {"meetings": [], "coaching": [], "feedback": []}

    # Meetings mentioning person
    meetings_dir = DATA_DIR / "meetings"
    if meetings_dir.is_dir():
        for f in meetings_dir.glob("*.md"):
            meta, body = _parse_frontmatter(f)
            file_date = str(meta.get("date", ""))
            if file_date and file_date < cutoff:
                continue
            attendees = meta.get("attendees", []) or []
            attendees_lower = [a.lower() for a in attendees]
            if person_lower in attendees_lower or person_lower in body.lower():
                evidence["meetings"].append({
                    "file": f.name, "date": file_date,
                    "body": body[:500], "meta": meta,
                })

    # Coaching for person
    coaching_dir = DATA_DIR / "coaching"
    if coaching_dir.is_dir():
        for f in coaching_dir.glob("*.md"):
            meta, body = _parse_frontmatter(f)
            if str(meta.get("person", "")).lower() == person_lower:
                evidence["coaching"].append({
                    "file": f.name, "body": body[:500], "meta": meta,
                })

    # Feedback for person
    feedback_dir = DATA_DIR / "feedback"
    if feedback_dir.is_dir():
        for f in feedback_dir.glob("*.md"):
            meta, body = _parse_frontmatter(f)
            if str(meta.get("person", "")).lower() == person_lower:
                evidence["feedback"].append({
                    "file": f.name, "body": body[:500], "meta": meta,
                })

    return evidence


async def generate_review_evidence(person: str, months: int = 6,
                                    save: bool = False) -> ReviewEvidence:
    """Generate evidence aggregation for a person's review."""
    from pydantic_ai import Agent

    ev = _gather_person_evidence(person, months)
    total = sum(len(v) for v in ev.values())

    if total == 0:
        _log.warning("No evidence found for %s in last %d months", person, months)
        return ReviewEvidence(person=person, period_months=months)

    context_parts = []
    for category, items in ev.items():
        if items:
            context_parts.append(f"## {category.title()} ({len(items)} items)")
            for item in items:
                context_parts.append(
                    f"- [{item.get('date', 'undated')}] {item['file']}: "
                    f"{item['body'][:200]}"
                )

    agent = Agent(
        get_model("balanced"),
        output_type=ReviewEvidence,
        system_prompt=(
            "You aggregate evidence for performance reviews. "
            "Your output is STRICTLY factual — observable contributions, "
            "measurable growth, and cited evidence. "
            "NEVER generate evaluative language, ratings, scores, or rankings. "
            "NEVER generate feedback language or coaching recommendations. "
            "NEVER suggest what the manager should say or write. "
            "Every claim must cite a specific source (file, date). "
            "If evidence is thin, say so explicitly rather than inferring."
        ),
    )

    result = await agent.run(
        f"Aggregate review evidence for {person} over the last {months} months.\n\n"
        + "\n".join(context_parts)
    )
    report = result.output
    report.person = person
    report.period_months = months

    if save:
        _save_evidence(report)

    return report


def _save_evidence(report: ReviewEvidence) -> Path:
    today = date.today().isoformat()
    slug = report.person.lower().replace(" ", "-")
    d = DATA_DIR / "references"
    d.mkdir(parents=True, exist_ok=True)

    lines = [f"# Review Evidence: {report.person}\n"]
    lines.append(f"Period: {report.period_months} months ending {today}\n")
    if report.contributions:
        lines.append("## Contributions")
        for c in report.contributions:
            lines.append(f"- {c}")
    if report.growth_trajectory:
        lines.append("\n## Growth Trajectory")
        for g in report.growth_trajectory:
            lines.append(f"- {g}")
    if report.development_areas:
        lines.append("\n## Development Areas")
        for d_area in report.development_areas:
            lines.append(f"- {d_area}")
    if report.evidence_citations:
        lines.append("\n## Evidence Citations")
        for e in report.evidence_citations:
            lines.append(f"- {e}")

    fm = {"type": "review-evidence", "person": report.person,
          "date": today, "period_months": report.period_months}
    fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False).strip()
    path = d / f"review-{slug}-{today}.md"
    path.write_text(f"---\n{fm_str}\n---\n" + "\n".join(lines), encoding="utf-8")
    _log.info("Saved review evidence to %s", path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Performance review evidence aggregation")
    parser.add_argument("--person", required=True, help="Person name")
    parser.add_argument("--months", type=int, default=6, help="Lookback months (default: 6)")
    parser.add_argument("--save", action="store_true, help="Save to DATA_DIR/references/")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    report = asyncio.run(generate_review_evidence(args.person, args.months, args.save))
    print(f"\nReview Evidence: {report.person} ({report.period_months} months)\n")
    if report.contributions:
        print("Contributions:")
        for c in report.contributions:
            print(f"  - {c}")
    if report.growth_trajectory:
        print("Growth:")
        for g in report.growth_trajectory:
            print(f"  - {g}")
    if report.development_areas:
        print("Development Areas:")
        for d in report.development_areas:
            print(f"  - {d}")
    if report.evidence_citations:
        print("Evidence:")
        for e in report.evidence_citations:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_review_prep.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/review_prep.py tests/test_review_prep.py
git commit -m "feat: add review_prep agent for performance review evidence aggregation"
```

---

### Task 8: Update Agent Registry and System Check

**Files:**
- Modify: `logos/data/agents.py`
- Modify: `agents/system_check.py`
- Modify: `CLAUDE.md`

**Step 1: Read current agent registry**

Read `logos/data/agents.py` to understand the registry format.

**Step 2: Add new agents to registry**

Add `ingest`, `status_update`, and `review_prep` to the `AGENT_REGISTRY` list in `agents.py`, following the existing pattern.

**Step 3: Update CLAUDE.md agent table**

Add the 3 new agents to the agent table and update the "Available agents" line.

**Step 4: Run tests**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All pass

**Step 5: Commit**

```bash
git add logos/data/agents.py agents/system_check.py CLAUDE.md
git commit -m "feat: register ingest, status_update, review_prep agents"
```

---

### Task 9: Docker Volume Mount for Data Directory

**Files:**
- Modify: `llm-stack/docker-compose.yml`

**Step 1: Add data volume mount to management-cockpit service**

In the `management-cockpit` service, add a bind mount for the data directory:

```yaml
volumes:
  - mgmt_management_data:/data
  - ../axioms:/app/axioms:ro
  - ../projects/profiles:/app/profiles
  - ../projects/ai-agents/ data:/app/data          # NEW
  - ~/projects/hapaxromana:/app/hapaxromana:ro
```

Also set the `HAPAX_DATA_DIR` environment variable:

```yaml
environment:
  - HAPAX_DATA_DIR=/app/data
```

**Step 2: Verify compose file validity**

Run: `cd ~/projects/hapax-containerization/llm-stack && docker compose config --quiet`
Expected: No errors

**Step 3: Commit**

```bash
git add llm-stack/docker-compose.yml
git commit -m "feat: mount data directory into cockpit container"
```

---

### Task 10: Integration Test — End-to-End Data Flow

**Files:**
- Create: `tests/test_integration_data_flow.py`

**Step 1: Write integration test**

```python
"""Integration test: data files → management collector → nudges → API cache."""
from __future__ import annotations
import textwrap
from pathlib import Path
from unittest.mock import patch

from cockpit.data.management import collect_management_state
from cockpit.data.nudges import collect_nudges
from cockpit.data.team_health import collect_team_health
from shared.management_bridge import generate_facts
from shared.vault_writer import (
    create_coaching_starter,
    create_fb_record_starter,
    create_decision_starter,
    write_1on1_prep_to_vault,
)


def _write_md(path: Path, frontmatter: str, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n{body}")


def _setup_data(tmp_path: Path) -> None:
    """Create a minimal but complete data directory."""
    _write_md(tmp_path / "people" / "alice.md", textwrap.dedent("""\
        type: person
        name: Alice
        status: active
        team: Platform
        role: direct-report
        cadence: weekly
        last-1on1: 2026-02-01
        cognitive-load: high"""))
    _write_md(tmp_path / "people" / "bob.md", textwrap.dedent("""\
        type: person
        name: Bob
        status: active
        team: Platform
        role: direct-report
        cadence: biweekly"""))
    _write_md(tmp_path / "coaching" / "alice-ownership.md", textwrap.dedent("""\
        type: coaching
        person: Alice
        status: active
        check-in-by: 2026-02-15"""))
    _write_md(tmp_path / "feedback" / "bob-review.md", textwrap.dedent("""\
        type: feedback
        person: Bob
        direction: giving
        category: technical
        follow-up-by: 2026-02-20
        followed-up: false"""))
    for d in ("meetings", "decisions", "references", "inbox", "processed"):
        (tmp_path / d).mkdir(exist_ok=True)


class TestEndToEndDataFlow:
    def test_collector_reads_data(self, tmp_path):
        _setup_data(tmp_path)
        with patch("cockpit.data.management.DATA_DIR", tmp_path):
            snap = collect_management_state()
        assert snap.active_people_count == 2
        assert snap.stale_1on1_count >= 1  # Alice's 1:1 is stale
        assert snap.overdue_coaching_count >= 1
        assert snap.overdue_feedback_count >= 1
        assert snap.high_load_count >= 1  # Alice is high load

    def test_bridge_generates_facts(self, tmp_path):
        _setup_data(tmp_path)
        with patch("shared.management_bridge.DATA_DIR", tmp_path):
            facts = generate_facts()
        assert len(facts) >= 3  # At least people + coaching + feedback facts

    def test_nudges_from_data(self, tmp_path):
        _setup_data(tmp_path)
        with patch("cockpit.data.management.DATA_DIR", tmp_path):
            nudges = collect_nudges()
        assert len(nudges) >= 1  # Stale 1:1, overdue coaching, overdue feedback

    def test_team_health_from_data(self, tmp_path):
        _setup_data(tmp_path)
        with patch("cockpit.data.management.DATA_DIR", tmp_path):
            health = collect_team_health()
        assert health.total_people >= 2

    def test_writer_creates_files(self, tmp_path):
        _setup_data(tmp_path)
        with patch("shared.vault_writer.DATA_DIR", tmp_path):
            p1 = create_coaching_starter("Alice", "Strong ownership in incidents")
            p2 = create_fb_record_starter("Bob", "Excellent PR feedback")
            p3 = create_decision_starter("Adopt gRPC", "Architecture review")
            p4 = write_1on1_prep_to_vault("Alice", "# Prep\n- Check on project X")
        assert all(p.exists() for p in [p1, p2, p3, p4])
        # Now verify collector picks up the new files
        with patch("cockpit.data.management.DATA_DIR", tmp_path):
            snap = collect_management_state()
        assert len(snap.coaching) >= 2  # Original + new starter
        assert len(snap.feedback) >= 2  # Original + new starter
```

**Step 2: Run integration test**

Run: `cd ai-agents && uv run pytest tests/test_integration_data_flow.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All pass

**Step 4: Commit**

```bash
git add tests/test_integration_data_flow.py
git commit -m "test: add end-to-end integration test for data flow"
```

---

### Task 11: VS Code Extension — Update Paths and Configuration

**Repo:** `~/projects/vscode/`

**Files:**
- Modify: `package.json`
- Modify: `src/settings.ts`
- Modify: `src/vault.ts`
- Modify: `src/extension.ts`

**Step 1: Update configuration defaults**

In `package.json`, update settings:
- `hapax.litellmUrl` default: `"http://localhost:4000"` → `"http://localhost:4100"`
- `hapax.qdrantUrl` default: `"http://localhost:6333"` → `"http://localhost:6433"`
- `hapax.ollamaUrl` default: `"http://localhost:11434"` (keep — shared)
- Add new setting: `hapax.dataDir` with default `"data"`
- Add new setting: `hapax.inboxDir` with default `"data/inbox"`

**Step 2: Update activation event**

In `package.json`, change activation event from `workspaceContains:.hapax-vault` to also activate on `workspaceContains:ai-agents/ data`:

```json
"activationEvents": [
    "workspaceContains:.hapax-vault",
    "workspaceContains:ai-agents/ data"
]
```

**Step 3: Update vault.ts for data directory**

In `src/vault.ts`, update `isWorkVault()` to also detect `data/people/` as a valid workspace:

```typescript
export async function isWorkVault(): Promise<boolean> {
    const root = vaultRoot();
    if (!root) return false;
    // Legacy: check for 10-work/ (Obsidian vault)
    try {
        await vscode.workspace.fs.stat(vscode.Uri.joinPath(root, "10-work"));
        return true;
    } catch {}
    // New: check for data/ (containerization project)
    try {
        await vscode.workspace.fs.stat(vscode.Uri.joinPath(root, "ai-agents", "data"));
        return true;
    } catch {}
    return false;
}
```

**Step 4: Update extension.ts isWorkVault check**

Ensure the `isWork` variable in `extension.ts` uses the updated `isWorkVault()`.

**Step 5: Test manually**

Open hapax-containerization workspace in VS Code, verify commands appear in palette.

**Step 6: Commit**

```bash
cd ~/projects/hapax-vscode
git add package.json src/settings.ts src/vault.ts src/extension.ts
git commit -m "feat: update paths and config for hapax-containerization data dir"
```

---

### Task 12: VS Code Extension — Update Existing Management Commands

**Repo:** `~/projects/vscode/`

**Files:**
- Modify: `src/commands/prepare-1on1.ts`
- Modify: `src/commands/team-snapshot.ts`
- Modify: `src/commands/capture-decision.ts`
- Modify: `src/commands/profile.ts`
- Modify: `src/commands/nudges.ts`

**Step 1: Update prepare1on1**

In `prepare-1on1.ts`:
- Change file search from `10-work/people/` to `data/people/`
- Change meeting search from `10-work/` to `data/meetings/`
- Change coaching search from `10-work/coaching/` to `data/coaching/`

**Step 2: Update teamSnapshot**

In `team-snapshot.ts`:
- Change person note search from `10-work/people/` to `data/people/`

**Step 3: Update captureDecision**

In `capture-decision.ts`:
- Change vault fallback path from `10-work/decisions/` to `data/decisions/`

**Step 4: Update viewProfile**

In `profile.ts`:
- Change digest path from `~/projects/profiles/ryan-digest.json` to `~/projects/profiles/operator-digest.json`

**Step 5: Update viewNudges**

In `nudges.ts`:
- Change from opening `30-system/nudges.md` to fetching from logos API (`http://localhost:8051/api/nudges`)
- Render nudges as a webview panel or markdown document

**Step 6: Test commands manually**

Verify each command works in VS Code with the new paths.

**Step 7: Commit**

```bash
cd ~/projects/hapax-vscode
git add src/commands/
git commit -m "feat: update management commands for data dir paths"
```

---

### Task 13: VS Code Extension — New Document Processing Commands

**Repo:** `~/projects/vscode/`

**Files:**
- Create: `src/commands/process-document.ts`
- Create: `src/commands/new-person.ts`
- Create: `src/commands/new-coaching.ts`
- Create: `src/commands/new-feedback.ts`
- Modify: `package.json` (register commands)
- Modify: `src/extension.ts` (register handlers)

**Step 1: Create process-document command**

`Hapax: Process Document` — file picker → call logos API or ingest agent → show results:

```typescript
// src/commands/process-document.ts
export async function processDocument(context: vscode.ExtensionContext) {
    const fileUri = await vscode.window.showOpenDialog({
        canSelectMany: false,
        title: "Select document to process",
        filters: {
            "Documents": ["md", "vtt", "srt", "txt"],
        },
    });
    if (!fileUri?.[0]) return;
    // Call ingest endpoint or run CLI
    // Show result in output channel
}
```

**Step 2: Create guided creation commands**

Each command (new-person, new-coaching, new-feedback) uses VS Code input boxes to collect fields, then creates a frontmatter markdown file in the appropriate `data/` subdirectory:

```typescript
// src/commands/new-person.ts
export async function newPerson(context: vscode.ExtensionContext) {
    const name = await vscode.window.showInputBox({ prompt: "Person's full name" });
    if (!name) return;
    const team = await vscode.window.showInputBox({ prompt: "Team name" });
    const role = await vscode.window.showQuickPick(
        ["direct-report", "peer", "skip-level", "stakeholder"],
        { placeHolder: "Relationship" }
    );
    // Create markdown file with frontmatter
    // Open in editor
}
```

**Step 3: Register commands in package.json**

Add 4 new commands to `contributes.commands` and `contributes.menus`.

**Step 4: Register handlers in extension.ts**

Add `vscode.commands.registerCommand()` calls for each new command.

**Step 5: Test commands manually**

**Step 6: Commit**

```bash
cd ~/projects/hapax-vscode
git add src/commands/ package.json src/extension.ts
git commit -m "feat: add document processing and guided creation commands"
```

---

### Task 14: VS Code Extension — Briefing, Weekly Review, Status Update Commands

**Repo:** `~/projects/vscode/`

**Files:**
- Create: `src/commands/morning-briefing.ts`
- Create: `src/commands/weekly-review.ts`
- Create: `src/commands/status-update.ts`
- Modify: `package.json`
- Modify: `src/extension.ts`

**Step 1: Create briefing command**

`Hapax: Morning Briefing` — calls logos API `/api/agents/management_briefing/run` via SSE, streams result into a new editor tab:

```typescript
export async function morningBriefing(context: vscode.ExtensionContext) {
    const doc = await vscode.workspace.openTextDocument({
        content: "# Morning Briefing\n\nGenerating...",
        language: "markdown",
    });
    await vscode.window.showTextDocument(doc);
    // Stream from logos API SSE endpoint
    // Update document content as chunks arrive
}
```

**Step 2: Create weekly review command**

Similar pattern — calls `meeting_lifecycle --weekly-review`.

**Step 3: Create status update command**

Calls `status_update` agent, shows result in editor.

**Step 4: Register all commands**

**Step 5: Test manually**

**Step 6: Commit**

```bash
cd ~/projects/hapax-vscode
git add src/commands/ package.json src/extension.ts
git commit -m "feat: add briefing, weekly review, and status update commands"
```

---

### Task 15: Update Interview Engine for Data Directory

**Repo:** `~/projects/vscode/`

**Files:**
- Modify: `src/interview/engine.ts`
- Modify: `src/interview/knowledge-model.ts`
- Modify: `src/interview/vault-writer.ts`

**Step 1: Update knowledge model paths**

In `knowledge-model.ts`, update all requirement `check.path` values:
- `10-work/people/` → `data/people/`
- `10-work/references/` → `data/references/`

**Step 2: Update engine vault scanning**

In `engine.ts`, update `scanVaultSatisfaction()` to scan `data/` paths.

**Step 3: Update vault-writer output paths**

In `vault-writer.ts`:
- `createPersonNote()`: `10-work/people/` → `data/people/`
- `createReferenceDoc()`: `10-work/references/` → `data/references/`
- `updateFrontmatter()`: no path changes needed (operates on existing files)

**Step 4: Test interview flow manually**

**Step 5: Commit**

```bash
cd ~/projects/hapax-vscode
git add src/interview/
git commit -m "feat: update interview engine for data directory paths"
```

---

### Task 16: Update Chat Sidebar Context

**Repo:** `~/projects/vscode/`

**Files:**
- Modify: `src/chat-view.ts`

**Step 1: Update context file path**

Change vault context from `30-system/hapax-context.md` to `data/references/hapax-context.md` (or remove if not needed — the interview engine handles bootstrapping).

**Step 2: Update note type detection**

Ensure the note type prefix system works with `data/` paths instead of `10-work/` paths.

**Step 3: Test chat sidebar**

**Step 4: Commit**

```bash
cd ~/projects/hapax-vscode
git add src/chat-view.ts
git commit -m "feat: update chat sidebar for data directory context"
```

---

## Execution Notes

**Dependency order:** Tasks 1-10 (hapax-containerization) can be executed sequentially. Tasks 11-16 (hapax-vscode) depend on tasks 1-4 being complete (for path understanding) but can otherwise be executed independently.

**Critical path:** Task 1 → Task 2 → Task 3 → Task 4 → Task 10 (validates the core data flow). Everything else builds on this foundation.

**Cross-repo coordination:** Tasks 11-16 modify `~/projects/vscode/` which is a separate git repo. Feature branch there should reference this plan.

**Test strategy:** Tasks 1-7 each have dedicated test files. Task 10 provides end-to-end integration validation. Tasks 11-16 are manually tested (VS Code extension).

**Safety gates:** Review_prep agent (Task 7) and status_update agent (Task 6) must be reviewed against management_safety axiom: no evaluative language, no feedback drafting, evidence aggregation only.
