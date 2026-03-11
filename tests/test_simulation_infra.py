# ai-agents/tests/test_simulation_infra.py
"""Tests for simulation directory lifecycle."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.simulation import (
    _SUBDIRS,
    _count_workdays,
    cleanup_simulation,
    create_simulation,
    list_simulations,
    load_manifest,
    save_manifest,
    seed_simulation,
)
from shared.simulation_models import SimManifest, SimStatus


class TestCreateSimulation:
    def test_creates_directory_structure(self, tmp_path: Path):
        """create_simulation() creates the expected subdirectories."""
        sim_dir, manifest = create_simulation(
            output=tmp_path,
            role="engineering-manager",
            window="7d",
            start_date="2026-03-02",
            end_date="2026-03-06",
            seed="demo-data/",
        )
        assert sim_dir.is_dir()
        assert (sim_dir / ".sim-manifest.yaml").is_file()

        for subdir in _SUBDIRS:
            assert (sim_dir / subdir).is_dir(), f"Missing subdir: {subdir}"

    def test_subdirs_match_data_dir_layout(self):
        """_SUBDIRS contains the correct 14 directories."""
        expected = {
            "people",
            "coaching",
            "feedback",
            "meetings",
            "okrs",
            "goals",
            "incidents",
            "postmortem-actions",
            "review-cycles",
            "status-reports",
            "decisions",
            "references",
            "1on1-prep",
            "briefings",
            "status-updates",
            "review-prep",
        }
        assert set(_SUBDIRS) == expected

    def test_returns_path_and_manifest(self, tmp_path: Path):
        """create_simulation() returns (Path, SimManifest) tuple."""
        result = create_simulation(
            output=tmp_path,
            role="engineering-manager",
            window="7d",
            start_date="2026-03-02",
            end_date="2026-03-06",
            seed="demo-data/",
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        sim_dir, manifest = result
        assert isinstance(sim_dir, Path)
        assert isinstance(manifest, SimManifest)
        assert manifest.role == "engineering-manager"

    def test_manifest_written_correctly(self, tmp_path: Path):
        """Manifest file contains valid YAML with expected fields."""
        sim_dir, manifest = create_simulation(
            output=tmp_path,
            role="engineering-manager",
            variant="experienced-em",
            window="30d",
            start_date="2026-02-08",
            end_date="2026-03-10",
            seed="demo-data/",
            audience="leadership",
        )
        loaded = load_manifest(sim_dir)
        assert loaded.role == "engineering-manager"
        assert loaded.variant == "experienced-em"
        assert loaded.status == SimStatus.PENDING
        assert loaded.audience == "leadership"

    def test_unique_directory_names(self, tmp_path: Path):
        """Two calls create distinct directories."""
        d1, _ = create_simulation(
            output=tmp_path,
            role="em",
            window="7d",
            start_date="2026-03-01",
            end_date="2026-03-07",
            seed="demo-data/",
        )
        d2, _ = create_simulation(
            output=tmp_path,
            role="em",
            window="7d",
            start_date="2026-03-01",
            end_date="2026-03-07",
            seed="demo-data/",
        )
        assert d1 != d2

    def test_default_output_is_tmp(self, tmp_path: Path):
        """Without output param, sim dir would be created under /tmp."""
        from shared.simulation import _DEFAULT_BASE_DIR

        assert Path("/tmp") == _DEFAULT_BASE_DIR

    def test_ticks_total_calculated(self, tmp_path: Path):
        """ticks_total is set to the number of workdays in the window."""
        # 2026-03-02 (Mon) to 2026-03-06 (Fri) = 5 workdays
        _, manifest = create_simulation(
            output=tmp_path,
            role="em",
            window="5d",
            start_date="2026-03-02",
            end_date="2026-03-06",
            seed="demo-data/",
        )
        assert manifest.ticks_total == 5

    def test_ticks_total_excludes_weekends(self, tmp_path: Path):
        """ticks_total excludes Saturday and Sunday."""
        # 2026-03-02 (Mon) to 2026-03-13 (Fri) = 10 workdays (2 weekends skipped)
        _, manifest = create_simulation(
            output=tmp_path,
            role="em",
            window="10d",
            start_date="2026-03-02",
            end_date="2026-03-13",
            seed="demo-data/",
        )
        assert manifest.ticks_total == 10


class TestCountWorkdays:
    def test_full_week(self):
        """Mon-Fri = 5 workdays."""
        from datetime import date

        assert _count_workdays(date(2026, 3, 2), date(2026, 3, 6)) == 5

    def test_includes_weekends(self):
        """Mon-Sun (7 days) = 5 workdays."""
        from datetime import date

        assert _count_workdays(date(2026, 3, 2), date(2026, 3, 8)) == 5

    def test_two_weeks(self):
        """Two full weeks = 10 workdays."""
        from datetime import date

        assert _count_workdays(date(2026, 3, 2), date(2026, 3, 13)) == 10

    def test_end_before_start(self):
        """Returns 0 if end < start."""
        from datetime import date

        assert _count_workdays(date(2026, 3, 10), date(2026, 3, 1)) == 0


class TestSeedSimulation:
    def test_copies_seed_files(self, tmp_path: Path):
        """seed_simulation() copies seed corpus into sim directory."""
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
        m1 = SimManifest(
            id="v1",
            role="em",
            window="7d",
            start_date="2026-03-01",
            end_date="2026-03-07",
            seed="demo-data/",
        )
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
        for name in ("sim-aaa", "sim-bbb"):
            d = tmp_path / name
            d.mkdir()
            (d / ".sim-manifest.yaml").write_text(
                yaml.dump(
                    {
                        "simulation": SimManifest(
                            id=name,
                            role="em",
                            window="7d",
                            start_date="2026-03-01",
                            end_date="2026-03-07",
                            seed="demo-data/",
                        ).model_dump(mode="json")
                    }
                )
            )

        (tmp_path / "regular-dir").mkdir()

        sims = list_simulations(tmp_path)
        assert len(sims) == 2
