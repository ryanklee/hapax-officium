# ai-agents/tests/test_simulation_models.py
"""Tests for simulation Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime

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
            created_at=datetime(2026, 3, 10, 14, 30, tzinfo=UTC),
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
