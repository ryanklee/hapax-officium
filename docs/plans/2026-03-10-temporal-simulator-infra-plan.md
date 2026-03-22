# Temporal Simulator Infrastructure — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation for the temporal simulator: mutable DATA_DIR config, ephemeral simulation directories, manifest schema, workflow semantics documentation, role matrix configuration, API context switching, and engine pause/resume.

**Architecture:** Refactor `DATA_DIR` from a module-level constant into a mutable config holder so the logos API can serve different data directories. Add simulation directory lifecycle management (create, seed, switch, cleanup). Document workflow semantics and role definitions in YAML files consumed by the existing context assembly pipeline.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, pytest, PyYAML

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `shared/config.py` | Modify | Add mutable `_Config` holder class with `data_dir` property and `set_data_dir()` |
| `shared/management_bridge.py` | Modify | Switch from `from shared.config import DATA_DIR` to `config.data_dir` |
| `shared/vault_writer.py` | Modify | Switch from `from shared.config import DATA_DIR` to `config.data_dir` |
| `logos/data/management.py` | Modify | Switch to `config.data_dir` |
| `logos/data/okrs.py` | Modify | Switch to `config.data_dir` |
| `logos/data/smart_goals.py` | Modify | Switch to `config.data_dir` |
| `logos/data/incidents.py` | Modify | Switch to `config.data_dir` |
| `logos/data/postmortem_actions.py` | Modify | Switch to `config.data_dir` |
| `logos/data/review_cycles.py` | Modify | Switch to `config.data_dir` |
| `logos/data/status_reports.py` | Modify | Switch to `config.data_dir` |
| `agents/status_update.py` | Modify | Switch to `config.data_dir` |
| `agents/ingest.py` | Modify | Switch to `config.data_dir` |
| `agents/drift_detector.py` | Modify | Switch to `config.data_dir` |
| `agents/review_prep.py` | Modify | Switch to `config.data_dir` |
| `logos/engine/__init__.py` | Modify | Add `pause()`/`resume()` methods |
| `logos/api/routes/engine.py` | Modify | Add `POST /api/engine/simulation-context` endpoint |
| `shared/simulation.py` | Create | Simulation directory lifecycle: create, seed, manifest, cleanup |
| `shared/simulation_models.py` | Create | Pydantic models: SimManifest, SimStatus |
| `config/role-matrix.yaml` | Create | Role definitions (EM only for v1) |
| `config/scenarios.yaml` | Create | Scenario modifier definitions |
| `docs/workflow-semantics.yaml` | Create | Workflow documentation consumed by context pipeline |
| `tests/test_simulation_infra.py` | Create | Tests for simulation directory lifecycle |
| `tests/test_config_mutable.py` | Create | Tests for mutable DATA_DIR config |
| `tests/test_simulation_context_api.py` | Create | Tests for API context switching |

---

## Chunk 1: Mutable DATA_DIR Config

### Task 1: Mutable Config Holder

**Files:**
- Modify: `shared/config.py:25-29`
- Create: `tests/test_config_mutable.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config_mutable.py
"""Tests for mutable DATA_DIR config holder."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from shared.config import config, DATA_DIR


class TestMutableConfig:
    def test_data_dir_returns_path(self):
        """config.data_dir returns a Path object."""
        assert isinstance(config.data_dir, Path)

    def test_data_dir_matches_module_constant(self):
        """config.data_dir matches the module-level DATA_DIR at import time."""
        # DATA_DIR is set at import time; config.data_dir is the live value
        # They should match initially
        assert config.data_dir == DATA_DIR

    def test_set_data_dir_changes_value(self, tmp_path: Path):
        """set_data_dir() changes what config.data_dir returns."""
        original = config.data_dir
        try:
            config.set_data_dir(tmp_path)
            assert config.data_dir == tmp_path
        finally:
            config.set_data_dir(original)

    def test_set_data_dir_does_not_change_module_constant(self, tmp_path: Path):
        """Changing config.data_dir does not affect the module-level DATA_DIR constant."""
        original = config.data_dir
        try:
            config.set_data_dir(tmp_path)
            # Module constant is frozen at import time
            assert DATA_DIR != tmp_path
        finally:
            config.set_data_dir(original)

    def test_reset_data_dir(self, tmp_path: Path):
        """reset_data_dir() restores the original value."""
        original = config.data_dir
        config.set_data_dir(tmp_path)
        config.reset_data_dir()
        assert config.data_dir == original

    def test_env_var_override(self, tmp_path: Path):
        """HAPAX_DATA_DIR env var is respected at init time."""
        with patch.dict("os.environ", {"HAPAX_DATA_DIR": str(tmp_path)}):
            from shared.config import _Config
            c = _Config()
            assert c.data_dir == tmp_path
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_config_mutable.py -v`
Expected: FAIL — `config` and `_Config` don't exist yet

- [ ] **Step 3: Implement the mutable config holder**

In `shared/config.py`, replace lines 25-29:

```python
# ── Canonical paths ─────────────────────────────────────────────────────────

PROFILES_DIR: Path = Path(__file__).resolve().parent.parent / "profiles"


class _Config:
    """Mutable configuration holder for paths that can change at runtime.

    Consumers that need dynamic DATA_DIR switching (API, collectors) should
    use ``config.data_dir`` instead of the module-level ``DATA_DIR`` constant.
    """

    def __init__(self) -> None:
        self._data_dir = Path(os.environ.get("HAPAX_DATA_DIR",
            str(Path(__file__).resolve().parent.parent / "data")))
        self._original_data_dir = self._data_dir

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    def set_data_dir(self, path: Path) -> None:
        self._data_dir = path

    def reset_data_dir(self) -> None:
        self._data_dir = self._original_data_dir


config = _Config()

# Backward-compatible constant — frozen at import time.
# New code should use config.data_dir for dynamic switching.
DATA_DIR: Path = config.data_dir
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_config_mutable.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All existing tests still pass (DATA_DIR constant unchanged)

- [ ] **Step 6: Commit**

```bash
git add shared/config.py tests/test_config_mutable.py
git commit -m "feat: add mutable _Config holder for dynamic DATA_DIR switching"
```

### Task 2: Migrate All DATA_DIR Consumers and Their Tests

This is the largest task — 13 production files and ~8 test files need updating. The approach: migrate tests first (TDD order), then production code.

**Production files to migrate (13):**
- `logos/data/management.py`
- `logos/data/okrs.py`
- `logos/data/smart_goals.py`
- `logos/data/incidents.py`
- `logos/data/postmortem_actions.py`
- `logos/data/review_cycles.py`
- `logos/data/status_reports.py`
- `shared/management_bridge.py`
- `shared/vault_writer.py`
- `agents/status_update.py`
- `agents/ingest.py`
- `agents/drift_detector.py`
- `agents/review_prep.py`

**Test files to migrate (~8, 60+ patch sites):**
- `tests/test_management_collector.py`
- `tests/test_management_bridge.py`
- `tests/test_vault_writer.py`
- `tests/test_ingest.py`
- `tests/test_status_update.py`
- `tests/test_postmortem_actions.py`
- `tests/test_review_cycles.py`
- `tests/test_integration_data_flow.py`
- (and any others found via `grep -r 'DATA_DIR' tests/`)

**Migration pattern for each production file:**

Change:
```python
from shared.config import DATA_DIR
```
to:
```python
from shared.config import config
```

Replace every `DATA_DIR` usage with `config.data_dir`.

**Migration pattern for each test file:**

Replace every occurrence of:
```python
with patch("cockpit.data.management.DATA_DIR", tmp_path):
```
or:
```python
with patch("shared.management_bridge.DATA_DIR", tmp_path):
```
with:
```python
from shared.config import config
# ...
original = config.data_dir
config.set_data_dir(tmp_path)
try:
    # test code
finally:
    config.set_data_dir(original)
```

For nested `with patch(...)` blocks that patch DATA_DIR in multiple modules simultaneously, the `config.set_data_dir()` approach is simpler — one call replaces all patches since all consumers now read from the same `config.data_dir`.

- [ ] **Step 1: Find all test files that patch DATA_DIR**

Run: `cd ai-agents && grep -rl 'DATA_DIR' tests/ | sort`
This identifies every test file that needs migration.

- [ ] **Step 2: Migrate test files (tests-first)**

For each test file found in Step 1, replace `patch("module.DATA_DIR", tmp_path)` with `config.set_data_dir(tmp_path)` in a try/finally. After migration, tests should FAIL because production code still imports `DATA_DIR` by name (so `config.set_data_dir` won't affect the frozen constant).

**Important:** Some tests may still pass even before production migration if they mock at a higher level. That's acceptable — the key is that the test pattern is correct for the new architecture.

- [ ] **Step 3: Migrate cockpit data collectors (7 files)**

In each file, change `from shared.config import DATA_DIR` to `from shared.config import config` and replace `DATA_DIR` → `config.data_dir`.

Files: `management.py`, `okrs.py`, `smart_goals.py`, `incidents.py`, `postmortem_actions.py`, `review_cycles.py`, `status_reports.py`

- [ ] **Step 4: Run collector tests**

Run: `cd ai-agents && uv run pytest tests/test_management_collector.py tests/test_okrs.py tests/test_smart_goals.py tests/test_incidents.py tests/test_postmortem_actions.py tests/test_review_cycles.py tests/test_status_reports.py -v`
Expected: All pass

- [ ] **Step 5: Migrate shared modules (2 files)**

`shared/management_bridge.py` (~10 DATA_DIR references) and `shared/vault_writer.py` (~11 references).

- [ ] **Step 6: Run shared module tests**

Run: `cd ai-agents && uv run pytest tests/test_management_bridge.py tests/test_vault_writer.py -v`
Expected: All pass

- [ ] **Step 7: Migrate agent modules (4 files)**

`agents/status_update.py`, `agents/ingest.py`, `agents/drift_detector.py`, `agents/review_prep.py`.

- [ ] **Step 8: Migrate engine modules (2 files)**

In `logos/engine/__init__.py` lines 37-40, change:
```python
if data_dir is None:
    from shared.config import DATA_DIR
    data_dir = DATA_DIR
```
to:
```python
if data_dir is None:
    from shared.config import config
    data_dir = config.data_dir
```

In `logos/engine/reactive_rules.py`, find and migrate any `from shared.config import DATA_DIR` usage (confirmed at line 55).

- [ ] **Step 9: Run full test suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: ALL tests pass — no regressions

- [ ] **Step 10: Commit**

```bash
git add logos/data/ shared/management_bridge.py \
       shared/vault_writer.py agents/ \
       logos/engine/ tests/
git commit -m "refactor: migrate all DATA_DIR consumers to config.data_dir"
```

---

## Chunk 2: Simulation Models and Directory Lifecycle

### Task 5: Simulation Pydantic Models

**Files:**
- Create: `shared/simulation_models.py`
- Create: `tests/test_simulation_models.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_simulation_models.py
"""Tests for simulation Pydantic models."""
from __future__ import annotations

from datetime import datetime, timezone

from shared.simulation_models import SimManifest, SimStatus


class TestSimManifest:
    def test_minimal_creation(self):
        """Manifest can be created with required fields only."""
        m = SimManifest(
            id="test-123",
            role="engineering-manager",
            window="30d",
            start_date="2026-02-08",
            end_date="2026-03-10",
            seed="demo-data/",
        )
        assert m.id == "test-123"
        assert m.status == SimStatus.PENDING
        assert m.ticks_completed == 0
        assert m.variant is None
        assert m.scenario is None

    def test_full_creation(self):
        """Manifest with all fields."""
        m = SimManifest(
            id="test-456",
            role="engineering-manager",
            variant="experienced-em",
            window="30d",
            start_date="2026-02-08",
            end_date="2026-03-10",
            scenario="pre-quarterly",
            audience="leadership",
            seed="demo-data/",
            ticks_total=22,
        )
        assert m.variant == "experienced-em"
        assert m.scenario == "pre-quarterly"
        assert m.audience == "leadership"
        assert m.ticks_total == 22

    def test_status_transitions(self):
        """Status enum has expected values."""
        assert SimStatus.PENDING == "pending"
        assert SimStatus.RUNNING == "running"
        assert SimStatus.COMPLETED == "completed"
        assert SimStatus.FAILED == "failed"

    def test_serialization_roundtrip(self):
        """Manifest can serialize to JSON and back."""
        m = SimManifest(
            id="test-789",
            role="engineering-manager",
            window="30d",
            start_date="2026-02-08",
            end_date="2026-03-10",
            seed="demo-data/",
            created_at=datetime(2026, 3, 10, 14, 30, tzinfo=timezone.utc),
        )
        json_str = m.model_dump_json(indent=2)
        m2 = SimManifest.model_validate_json(json_str)
        assert m2.id == m.id
        assert m2.created_at == m.created_at

    def test_yaml_roundtrip(self):
        """Manifest can serialize to YAML for .sim-manifest.yaml."""
        import yaml
        m = SimManifest(
            id="test-yaml",
            role="engineering-manager",
            window="7d",
            start_date="2026-03-01",
            end_date="2026-03-07",
            seed="demo-data/",
        )
        data = m.model_dump(mode="json")
        yaml_str = yaml.dump({"simulation": data}, default_flow_style=False)
        loaded = yaml.safe_load(yaml_str)
        m2 = SimManifest.model_validate(loaded["simulation"])
        assert m2.id == m.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_simulation_models.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement simulation models**

```python
# shared/simulation_models.py
"""Pydantic models for simulation manifests and configuration."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class SimStatus(StrEnum):
    """Simulation lifecycle status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SimManifest(BaseModel):
    """Metadata for a simulation run, persisted as .sim-manifest.yaml."""
    id: str
    role: str
    variant: str | None = None
    window: str
    start_date: str
    end_date: str
    scenario: str | None = None
    audience: str | None = None
    seed: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    ticks_completed: int = 0
    ticks_total: int = 0
    last_completed_tick: str | None = None
    checkpoints_run: int = 0
    status: SimStatus = SimStatus.PENDING
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_simulation_models.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add shared/simulation_models.py tests/test_simulation_models.py
git commit -m "feat: add Pydantic models for simulation manifests"
```

### Task 6: Simulation Directory Lifecycle

**Files:**
- Create: `shared/simulation.py`
- Create: `tests/test_simulation_infra.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_simulation_infra.py
"""Tests for simulation directory lifecycle."""
from __future__ import annotations

import yaml
from pathlib import Path

from shared.simulation import (
    create_simulation,
    seed_simulation,
    load_manifest,
    save_manifest,
    cleanup_simulation,
    list_simulations,
)
from shared.simulation_models import SimManifest, SimStatus


class TestCreateSimulation:
    def test_creates_directory_structure(self, tmp_path: Path):
        """create_simulation() creates the expected subdirectories."""
        sim_dir = create_simulation(
            base_dir=tmp_path,
            role="engineering-manager",
            window="7d",
            start_date="2026-03-01",
            end_date="2026-03-07",
            seed="demo-data/",
        )
        assert sim_dir.is_dir()
        assert (sim_dir / ".sim-manifest.yaml").is_file()

        # Check standard subdirectories exist
        for subdir in ("people", "coaching", "feedback", "meetings",
                       "okrs", "goals", "incidents", "postmortem-actions",
                       "review-cycles", "status-reports", "decisions", "references",
                       "inbox", "processed"):
            assert (sim_dir / subdir).is_dir()

    def test_manifest_written_correctly(self, tmp_path: Path):
        """Manifest file contains valid YAML with expected fields."""
        sim_dir = create_simulation(
            base_dir=tmp_path,
            role="engineering-manager",
            variant="experienced-em",
            window="30d",
            start_date="2026-02-08",
            end_date="2026-03-10",
            seed="demo-data/",
            audience="leadership",
        )
        manifest = load_manifest(sim_dir)
        assert manifest.role == "engineering-manager"
        assert manifest.variant == "experienced-em"
        assert manifest.status == SimStatus.PENDING
        assert manifest.audience == "leadership"

    def test_unique_directory_names(self, tmp_path: Path):
        """Two calls create distinct directories."""
        d1 = create_simulation(base_dir=tmp_path, role="em", window="7d",
                               start_date="2026-03-01", end_date="2026-03-07",
                               seed="demo-data/")
        d2 = create_simulation(base_dir=tmp_path, role="em", window="7d",
                               start_date="2026-03-01", end_date="2026-03-07",
                               seed="demo-data/")
        assert d1 != d2


class TestSeedSimulation:
    def test_copies_seed_files(self, tmp_path: Path):
        """seed_simulation() copies seed corpus into sim directory."""
        # Create a mock seed corpus
        seed_dir = tmp_path / "seed"
        (seed_dir / "people").mkdir(parents=True)
        (seed_dir / "people" / "alice.md").write_text("---\ntype: person\nname: Alice\n---\n")
        (seed_dir / "coaching").mkdir(parents=True)
        (seed_dir / "coaching" / "note.md").write_text("---\ntype: coaching\n---\n")

        sim_dir = tmp_path / "sim"
        sim_dir.mkdir()
        for subdir in ("people", "coaching"):
            (sim_dir / subdir).mkdir()

        seed_simulation(sim_dir, seed_dir)

        assert (sim_dir / "people" / "alice.md").is_file()
        assert (sim_dir / "coaching" / "note.md").is_file()

    def test_does_not_overwrite_existing(self, tmp_path: Path):
        """Existing files in sim_dir are not overwritten by seeding."""
        seed_dir = tmp_path / "seed"
        (seed_dir / "people").mkdir(parents=True)
        (seed_dir / "people" / "alice.md").write_text("seed content")

        sim_dir = tmp_path / "sim"
        (sim_dir / "people").mkdir(parents=True)
        (sim_dir / "people" / "alice.md").write_text("existing content")

        seed_simulation(sim_dir, seed_dir)
        assert (sim_dir / "people" / "alice.md").read_text() == "existing content"


class TestManifestIO:
    def test_save_and_load_roundtrip(self, tmp_path: Path):
        """Manifest can be saved and loaded."""
        manifest = SimManifest(
            id="test-io",
            role="engineering-manager",
            window="7d",
            start_date="2026-03-01",
            end_date="2026-03-07",
            seed="demo-data/",
        )
        save_manifest(tmp_path, manifest)
        loaded = load_manifest(tmp_path)
        assert loaded.id == manifest.id
        assert loaded.role == manifest.role

    def test_save_updates_existing(self, tmp_path: Path):
        """save_manifest overwrites existing manifest file."""
        m1 = SimManifest(id="v1", role="em", window="7d",
                         start_date="2026-03-01", end_date="2026-03-07",
                         seed="demo-data/")
        save_manifest(tmp_path, m1)

        m2 = m1.model_copy(update={"status": SimStatus.RUNNING, "ticks_completed": 5})
        save_manifest(tmp_path, m2)

        loaded = load_manifest(tmp_path)
        assert loaded.status == SimStatus.RUNNING
        assert loaded.ticks_completed == 5


class TestCleanup:
    def test_cleanup_removes_directory(self, tmp_path: Path):
        """cleanup_simulation() removes the simulation directory."""
        sim_dir = tmp_path / "sim-test"
        sim_dir.mkdir()
        (sim_dir / "people").mkdir()
        (sim_dir / "people" / "alice.md").write_text("content")
        (sim_dir / ".sim-manifest.yaml").write_text("simulation: {}")

        cleanup_simulation(sim_dir)
        assert not sim_dir.exists()

    def test_cleanup_refuses_non_simulation_dir(self, tmp_path: Path):
        """cleanup_simulation() raises if directory lacks .sim-manifest.yaml."""
        import pytest
        regular_dir = tmp_path / "not-a-sim"
        regular_dir.mkdir()

        with pytest.raises(ValueError, match="not a simulation directory"):
            cleanup_simulation(regular_dir)


class TestListSimulations:
    def test_lists_simulation_dirs(self, tmp_path: Path):
        """list_simulations() finds simulation directories by manifest presence."""
        # Create two simulation dirs
        for name in ("sim-aaa", "sim-bbb"):
            d = tmp_path / name
            d.mkdir()
            (d / ".sim-manifest.yaml").write_text(
                yaml.dump({"simulation": SimManifest(
                    id=name, role="em", window="7d",
                    start_date="2026-03-01", end_date="2026-03-07",
                    seed="demo-data/"
                ).model_dump(mode="json")}))

        # Create a non-simulation dir
        (tmp_path / "regular-dir").mkdir()

        sims = list_simulations(tmp_path)
        assert len(sims) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_simulation_infra.py -v`
Expected: FAIL — `shared.simulation` doesn't exist

- [ ] **Step 3: Implement simulation directory lifecycle**

```python
# shared/simulation.py
"""Simulation directory lifecycle — create, seed, manifest I/O, cleanup."""
from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

import yaml

from shared.simulation_models import SimManifest, SimStatus

_log = logging.getLogger(__name__)

# Standard subdirectories in a simulation DATA_DIR
_SUBDIRS = (
    "people", "coaching", "feedback", "meetings",
    "okrs", "goals", "incidents", "postmortem-actions",
    "review-cycles", "status-reports", "decisions", "references",
    "inbox", "processed",
)

_MANIFEST_FILE = ".sim-manifest.yaml"


def create_simulation(
    *,
    base_dir: Path,
    role: str,
    window: str,
    start_date: str,
    end_date: str,
    seed: str,
    variant: str | None = None,
    scenario: str | None = None,
    audience: str | None = None,
) -> Path:
    """Create a new simulation directory with manifest and subdirectories."""
    sim_id = f"sim-{uuid.uuid4().hex[:12]}"
    sim_dir = base_dir / sim_id
    sim_dir.mkdir(parents=True)

    for subdir in _SUBDIRS:
        (sim_dir / subdir).mkdir()

    manifest = SimManifest(
        id=sim_id,
        role=role,
        variant=variant,
        window=window,
        start_date=start_date,
        end_date=end_date,
        scenario=scenario,
        audience=audience,
        seed=seed,
    )
    save_manifest(sim_dir, manifest)

    _log.info("Created simulation %s at %s", sim_id, sim_dir)
    return sim_dir


def seed_simulation(sim_dir: Path, seed_dir: Path) -> None:
    """Copy seed corpus files into a simulation directory.

    Does not overwrite existing files in sim_dir.
    """
    if not seed_dir.is_dir():
        raise ValueError(f"Seed directory does not exist: {seed_dir}")

    for src_file in seed_dir.rglob("*"):
        if src_file.is_dir():
            continue
        rel = src_file.relative_to(seed_dir)
        dst = sim_dir / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst)

    _log.info("Seeded simulation from %s", seed_dir)


def save_manifest(sim_dir: Path, manifest: SimManifest) -> None:
    """Write manifest to .sim-manifest.yaml in the simulation directory."""
    path = sim_dir / _MANIFEST_FILE
    data = {"simulation": manifest.model_dump(mode="json")}
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")


def load_manifest(sim_dir: Path) -> SimManifest:
    """Load manifest from .sim-manifest.yaml."""
    path = sim_dir / _MANIFEST_FILE
    if not path.is_file():
        raise FileNotFoundError(f"No manifest at {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SimManifest.model_validate(data["simulation"])


def cleanup_simulation(sim_dir: Path) -> None:
    """Remove a simulation directory. Refuses if not a simulation dir."""
    if not (sim_dir / _MANIFEST_FILE).is_file():
        raise ValueError(f"{sim_dir} is not a simulation directory (no {_MANIFEST_FILE})")
    shutil.rmtree(sim_dir)
    _log.info("Cleaned up simulation at %s", sim_dir)


def list_simulations(base_dir: Path) -> list[SimManifest]:
    """List all simulation manifests in a base directory."""
    manifests = []
    if not base_dir.is_dir():
        return manifests
    for child in sorted(base_dir.iterdir()):
        if child.is_dir() and (child / _MANIFEST_FILE).is_file():
            try:
                manifests.append(load_manifest(child))
            except Exception:
                _log.warning("Failed to load manifest from %s", child)
    return manifests
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_simulation_infra.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Run full test suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add shared/simulation.py tests/test_simulation_infra.py
git commit -m "feat: add simulation directory lifecycle management"
```

---

## Chunk 3: Configuration Files and API Integration

### Task 7: Workflow Semantics YAML

**Files:**
- Create: `docs/workflow-semantics.yaml`

This is a documentation file consumed by the context assembly pipeline. No code changes needed — just creating the reference document.

- [ ] **Step 1: Create workflow-semantics.yaml**

```yaml
# docs/workflow-semantics.yaml
# Workflow semantics for the temporal simulator.
# Consumed by the demo and simulator agents via the context assembly pipeline.
# Kept current by the drift detector (weekly checks).

workflows:
  one_on_one:
    data_type: meeting
    subdirectory: meetings/
    frontmatter:
      type: meeting
      meeting-type: one-on-one
    triggers:
      - coaching_note
      - feedback
    cadence: "per-person, configurable (weekly/biweekly/monthly)"
    description: "Regular 1:1 meetings between manager and direct report"

  coaching_note:
    data_type: coaching
    subdirectory: coaching/
    frontmatter:
      type: coaching
    triggered_by: [one_on_one, incident]
    cadence: "event-driven, typically after significant 1:1s or incidents"
    description: "Coaching hypotheses and development observations"

  feedback:
    data_type: feedback
    subdirectory: feedback/
    frontmatter:
      type: feedback
    triggered_by: [one_on_one, review_cycle]
    cadence: "monthly or event-driven"
    description: "Feedback records (given/received, various categories)"

  okr_update:
    data_type: okr
    subdirectory: okrs/
    frontmatter:
      type: okr
    cadence: "quarterly definition, monthly check-in"
    description: "Objectives and key results tracking"

  goal:
    data_type: goal
    subdirectory: goals/
    frontmatter:
      type: goal
    cadence: "quarterly definition, monthly progress update"
    description: "Individual SMART development goals"

  incident:
    data_type: incident
    subdirectory: incidents/
    frontmatter:
      type: incident
    stochastic: true
    triggers: [postmortem_action, coaching_note]
    description: "Service incidents requiring management attention"

  postmortem_action:
    data_type: postmortem-action
    subdirectory: postmortem-actions/
    frontmatter:
      type: postmortem-action
    triggered_by: [incident]
    description: "Action items from incident postmortems"

  review_cycle:
    data_type: review-cycle
    subdirectory: review-cycles/
    frontmatter:
      type: review-cycle
    cadence: "semi-annual or annual"
    triggers: [feedback]
    description: "Performance review process tracking"

  status_report:
    data_type: status-report
    subdirectory: status-reports/
    frontmatter:
      type: status-report
    cadence: "weekly or biweekly"
    description: "Upward-facing status reports"

  decision:
    data_type: decision
    subdirectory: decisions/
    frontmatter:
      type: decision
    stochastic: true
    description: "Architectural and organizational decisions"
```

- [ ] **Step 2: Commit**

```bash
git add docs/workflow-semantics.yaml
git commit -m "docs: add workflow semantics for temporal simulator context pipeline"
```

### Task 8: Role Matrix and Scenarios YAML

**Files:**
- Create: `config/role-matrix.yaml`
- Create: `config/scenarios.yaml`

- [ ] **Step 1: Create config directory**

Run: `mkdir -p ai-agents/ config`

- [ ] **Step 2: Create role-matrix.yaml**

```yaml
# config/role-matrix.yaml
# Role definitions for the temporal simulator.
# Each role defines which workflows it uses and available variants.

roles:
  engineering-manager:
    description: "Engineering manager across experience levels"
    variants:
      new-em:
        description: "First 90 days as EM — learning, observing, building relationships"
        cadence_modifiers:
          one_on_one: 1.5      # more frequent initial 1:1s
          coaching_note: 0.5   # fewer coaching notes while learning
          decision: 0.3        # fewer decisions while observing
          feedback: 0.5        # cautious with feedback early on

      experienced-em:
        description: "Steady-state EM — full workflow usage"
        cadence_modifiers: {}  # baseline cadences from workflow-semantics

      senior-em:
        description: "Multi-team EM — delegation-heavy, strategic focus"
        cadence_modifiers:
          status_report: 2.0   # more reporting
          decision: 1.5        # more decisions
          one_on_one: 0.7      # some delegated to leads

    workflows:
      - one_on_one
      - coaching_note
      - feedback
      - okr_update
      - goal
      - incident
      - postmortem_action
      - review_cycle
      - status_report
      - decision
```

- [ ] **Step 3: Create scenarios.yaml**

```yaml
# config/scenarios.yaml
# Scenario modifiers for the temporal simulator.
# Scenarios adjust event generation probabilities and inject contextual events.

scenarios:
  pre-quarterly:
    description: "2 weeks before quarterly planning — increased OKR and planning activity"
    window_hint: 14d
    probability_overrides:
      okr_update: 3.0
      status_report: 2.0
      goal: 2.0
    inject_events:
      - workflow: one_on_one
        context: "quarterly planning prep"
        at: end

  post-incident:
    description: "Aftermath of a major incident — postmortem and recovery focus"
    inject_events:
      - workflow: incident
        severity: high
        at: start
    probability_overrides:
      postmortem_action: 5.0
      coaching_note: 2.0
      one_on_one: 1.3

  first-90-days:
    description: "New manager onboarding — observation and relationship building"
    window_hint: 90d
    probability_overrides:
      one_on_one: 1.5
      coaching_note: 0.5
      decision: 0.3
      feedback: 0.3
      status_report: 0.5

  review-season:
    description: "Performance review cycle in progress"
    window_hint: 30d
    inject_events:
      - workflow: review_cycle
        status: in-progress
        at: start
    probability_overrides:
      feedback: 3.0
      one_on_one: 1.3
      coaching_note: 1.5
```

- [ ] **Step 4: Commit**

```bash
git add config/
git commit -m "feat: add role matrix and scenario definitions for simulator"
```

### Task 9: Engine Pause/Resume for Simulation Context

**Files:**
- Modify: `logos/engine/__init__.py`
- Create: `tests/test_engine_pause.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_pause.py
"""Tests for engine pause/resume during simulation context switching."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cockpit.engine import ReactiveEngine


class TestEnginePause:
    async def test_pause_stops_watcher(self):
        """pause() stops the watcher but keeps engine instance alive."""
        engine = ReactiveEngine(data_dir=Path("/tmp/fake"), enabled=True)
        engine._watcher = MagicMock()
        engine._watcher.stop = AsyncMock()
        engine._scheduler = MagicMock()
        engine._scheduler.stop = AsyncMock()
        engine.running = True

        await engine.pause()

        engine._watcher.stop.assert_called_once()
        engine._scheduler.stop.assert_called_once()
        assert engine.running is False
        assert engine.paused is True

    async def test_resume_restarts_watcher(self):
        """resume() restarts the watcher."""
        engine = ReactiveEngine(data_dir=Path("/tmp/fake"), enabled=True)
        engine._watcher = MagicMock()
        engine._watcher.start = AsyncMock()
        engine._scheduler = MagicMock()
        engine._scheduler.start = AsyncMock()
        engine._delivery = MagicMock()
        engine._delivery.start_flush_loop = AsyncMock()
        engine.running = False
        engine.paused = True

        await engine.resume()

        engine._watcher.start.assert_called_once()
        engine._scheduler.start.assert_called_once()
        assert engine.running is True
        assert engine.paused is False

    async def test_pause_noop_when_not_running(self):
        """pause() is a no-op if engine not running."""
        engine = ReactiveEngine(data_dir=Path("/tmp/fake"), enabled=True)
        engine.running = False

        await engine.pause()
        assert engine.paused is False

    async def test_resume_noop_when_not_paused(self):
        """resume() is a no-op if engine not paused."""
        engine = ReactiveEngine(data_dir=Path("/tmp/fake"), enabled=True)
        engine.running = False
        engine.paused = False

        await engine.resume()
        assert engine.running is False

    async def test_status_includes_paused(self):
        """status() reports paused state."""
        engine = ReactiveEngine(data_dir=Path("/tmp/fake"), enabled=True)
        engine.running = False
        engine.paused = True

        status = engine.status()
        assert status["paused"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_engine_pause.py -v`
Expected: FAIL — `pause`, `resume`, `paused` don't exist

- [ ] **Step 3: Add pause/resume to ReactiveEngine**

In `logos/engine/__init__.py`, add to `__init__`:
```python
self.paused: bool = False
```

Add after the `stop()` method:

```python
async def pause(self) -> None:
    """Pause the engine (stop watcher/scheduler) without full shutdown.

    Used during simulation context switching to prevent the engine
    from reacting to the real DATA_DIR while the API serves simulation data.
    """
    if not self.running:
        return

    await self._watcher.stop()
    await self._scheduler.stop()
    self.running = False
    self.paused = True
    _log.info("ReactiveEngine paused")

async def resume(self) -> None:
    """Resume the engine after a pause."""
    if not self.paused:
        return

    await self._watcher.start()
    await self._delivery.start_flush_loop()
    await self._scheduler.start()
    self.running = True
    self.paused = False
    _log.info("ReactiveEngine resumed")
```

Update `status()` to include paused:
```python
def status(self) -> dict:
    return {
        "running": self.running,
        "paused": self.paused,
        "enabled": self._enabled,
        ...
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_engine_pause.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Run full test suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add logos/engine/__init__.py tests/test_engine_pause.py
git commit -m "feat: add engine pause/resume for simulation context switching"
```

### Task 10: API Simulation Context Endpoint

**Files:**
- Modify: `logos/api/routes/engine.py`
- Create: `tests/test_simulation_context_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_simulation_context_api.py
"""Tests for POST /api/engine/simulation-context endpoint."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from cockpit.api.routes.engine import router, set_engine


class TestSimulationContextEndpoint:
    def _make_client(self, engine=None):
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        if engine is not None:
            set_engine(engine)
        return TestClient(app)

    def test_activate_simulation_context(self, tmp_path: Path):
        """POST with sim_dir activates simulation context."""
        # Create a simulation directory with manifest
        sim_dir = tmp_path / "sim-test"
        sim_dir.mkdir()
        (sim_dir / ".sim-manifest.yaml").write_text(
            "simulation:\n  id: test\n  role: em\n  window: 7d\n"
            "  start_date: '2026-03-01'\n  end_date: '2026-03-07'\n"
            "  seed: demo-data/\n  status: completed\n"
        )

        engine = MagicMock()
        engine.pause = AsyncMock()
        client = self._make_client(engine)

        with patch("cockpit.api.routes.engine.config") as mock_config, \
             patch("cockpit.api.routes.engine.cache") as mock_cache:
            mock_cache.refresh = AsyncMock()
            response = client.post(
                "/api/engine/simulation-context",
                json={"sim_dir": str(sim_dir)},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_deactivate_simulation_context(self):
        """POST with null sim_dir deactivates simulation context."""
        engine = MagicMock()
        engine.resume = AsyncMock()
        client = self._make_client(engine)

        with patch("cockpit.api.routes.engine.config") as mock_config, \
             patch("cockpit.api.routes.engine.cache") as mock_cache:
            mock_cache.refresh = AsyncMock()
            response = client.post(
                "/api/engine/simulation-context",
                json={"sim_dir": None},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_rejects_nonexistent_directory(self):
        """POST with nonexistent sim_dir returns 400."""
        engine = MagicMock()
        client = self._make_client(engine)

        response = client.post(
            "/api/engine/simulation-context",
            json={"sim_dir": "/nonexistent/path"},
        )
        assert response.status_code == 400

    def test_rejects_non_simulation_directory(self, tmp_path: Path):
        """POST with directory lacking .sim-manifest.yaml returns 400."""
        regular_dir = tmp_path / "not-a-sim"
        regular_dir.mkdir()

        engine = MagicMock()
        client = self._make_client(engine)

        response = client.post(
            "/api/engine/simulation-context",
            json={"sim_dir": str(regular_dir)},
        )
        assert response.status_code == 400

    def test_engine_not_running_returns_error(self):
        """POST when engine is None returns error."""
        set_engine(None)
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/api/engine/simulation-context",
            json={"sim_dir": None},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "error"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_simulation_context_api.py -v`
Expected: FAIL — endpoint doesn't exist

- [ ] **Step 3: Implement the endpoint**

In `logos/api/routes/engine.py`, add at top (module-level imports so they are patchable in tests):

```python
from pydantic import BaseModel
from fastapi import HTTPException

from shared.config import config
from cockpit.api.cache import cache
```

Add the request model and endpoint:

```python
class SimulationContextRequest(BaseModel):
    sim_dir: str | None = None


@router.post("/simulation-context")
async def set_simulation_context(req: SimulationContextRequest) -> dict:
    """Switch the API to serve data from a simulation directory.

    Pass sim_dir=null to deactivate and return to the real DATA_DIR.
    """
    engine = _get_engine()
    if engine is None:
        return {"status": "error", "message": "Engine not running"}

    if req.sim_dir is None:
        # Deactivate simulation context
        config.reset_data_dir()
        await engine.resume()
        await cache.refresh()
        return {"status": "ok", "message": "Simulation context deactivated"}

    sim_path = Path(req.sim_dir)
    if not sim_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {req.sim_dir}")
    if not (sim_path / ".sim-manifest.yaml").is_file():
        raise HTTPException(status_code=400, detail=f"Not a simulation directory (no .sim-manifest.yaml)")

    # Activate simulation context
    await engine.pause()
    config.set_data_dir(sim_path)
    await cache.refresh()
    return {"status": "ok", "message": f"Simulation context activated: {sim_path.name}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_simulation_context_api.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Run full test suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add logos/api/routes/engine.py tests/test_simulation_context_api.py
git commit -m "feat: add POST /api/engine/simulation-context endpoint"
```

### Task 11: Workflow Semantics Validation Test

**Files:**
- Create: `tests/test_workflow_semantics.py`

A validation test ensuring bidirectional consistency between `workflow-semantics.yaml` and the `demo-data/` corpus.

- [ ] **Step 1: Write the test**

```python
# tests/test_workflow_semantics.py
"""Validate workflow-semantics.yaml against demo-data/ corpus."""
from __future__ import annotations

from pathlib import Path

import yaml


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKFLOW_SEMANTICS = _PROJECT_ROOT / "docs" / "workflow-semantics.yaml"
_DEMO_DATA = Path(__file__).resolve().parent.parent / "demo-data"


class TestWorkflowSemanticsConsistency:
    def test_semantics_file_exists(self):
        """workflow-semantics.yaml exists."""
        assert _WORKFLOW_SEMANTICS.is_file(), (
            f"Missing {_WORKFLOW_SEMANTICS}"
        )

    def test_all_demo_data_types_have_semantics(self):
        """Every document type in demo-data/ has a workflow-semantics entry."""
        semantics = yaml.safe_load(_WORKFLOW_SEMANTICS.read_text())
        defined_subdirs = {
            w["subdirectory"].rstrip("/")
            for w in semantics["workflows"].values()
        }

        # Subdirectories in demo-data that contain .md files with type: frontmatter
        data_subdirs = set()
        for md_file in _DEMO_DATA.rglob("*.md"):
            rel = md_file.relative_to(_DEMO_DATA)
            if len(rel.parts) >= 2:
                data_subdirs.add(rel.parts[0])

        # Exclude non-workflow directories
        non_workflow = {"references", "1on1-prep", "inbox", "processed",
                        "briefings", "status-updates", "review-prep"}
        data_subdirs -= non_workflow

        missing = data_subdirs - defined_subdirs
        assert not missing, (
            f"demo-data/ has document types not in workflow-semantics.yaml: {missing}"
        )

    def test_all_semantics_have_demo_data(self):
        """Every workflow-semantics entry has at least one example in demo-data/."""
        semantics = yaml.safe_load(_WORKFLOW_SEMANTICS.read_text())

        for name, workflow in semantics["workflows"].items():
            subdir = workflow["subdirectory"].rstrip("/")
            demo_dir = _DEMO_DATA / subdir
            md_files = list(demo_dir.glob("*.md")) if demo_dir.is_dir() else []
            assert len(md_files) > 0, (
                f"Workflow '{name}' (subdirectory: {subdir}) has no demo-data examples"
            )

    def test_role_matrix_exists(self):
        """role-matrix.yaml exists."""
        role_matrix = Path(__file__).resolve().parent.parent / "config" / "role-matrix.yaml"
        assert role_matrix.is_file()

    def test_role_matrix_workflows_match_semantics(self):
        """All workflows referenced in role-matrix.yaml exist in workflow-semantics.yaml."""
        semantics = yaml.safe_load(_WORKFLOW_SEMANTICS.read_text())
        role_matrix = yaml.safe_load(
            (Path(__file__).resolve().parent.parent / "config" / "role-matrix.yaml").read_text()
        )

        defined_workflows = set(semantics["workflows"].keys())

        for role_name, role_def in role_matrix["roles"].items():
            for wf in role_def.get("workflows", []):
                assert wf in defined_workflows, (
                    f"Role '{role_name}' references undefined workflow '{wf}'"
                )
```

- [ ] **Step 2: Run test**

Run: `cd ai-agents && uv run pytest tests/test_workflow_semantics.py -v`
Expected: PASS (all 5 tests — files were created in Tasks 7 and 8)

- [ ] **Step 3: Commit**

```bash
git add tests/test_workflow_semantics.py
git commit -m "test: add workflow semantics bidirectional consistency validation"
```

### Task 12: Final Integration Verification

- [ ] **Step 1: Run full test suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All tests pass (existing + new)

- [ ] **Step 2: Verify no import breakage**

Run: `cd ai-agents && uv run python -c "from shared.config import config, DATA_DIR; print(f'DATA_DIR: {DATA_DIR}'); print(f'config.data_dir: {config.data_dir}')"`
Expected: Both print the same path

Run: `cd ai-agents && uv run python -c "from shared.simulation import create_simulation; print('simulation module imports ok')"`
Expected: Prints "simulation module imports ok"

- [ ] **Step 3: Commit any final fixes**

Only if needed based on steps 1-2.
