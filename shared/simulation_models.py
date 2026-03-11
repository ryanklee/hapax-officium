# ai-agents/shared/simulation_models.py
"""Pydantic models for simulation manifests and configuration."""

from __future__ import annotations

from datetime import UTC, datetime
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    ticks_completed: int = 0
    ticks_total: int = 0
    last_completed_tick: str | None = None
    checkpoints_run: int = 0
    status: SimStatus = SimStatus.PENDING
