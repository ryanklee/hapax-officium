"""Engine endpoints — expose reactive engine status and configuration."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cockpit.api.cache import cache
from shared.config import config

router = APIRouter(prefix="/api/engine", tags=["engine"])

_engine_instance = None


def set_engine(engine: Any) -> None:
    """Set the module-level engine instance (called from app lifespan)."""
    global _engine_instance
    _engine_instance = engine


def _get_engine() -> Any | None:
    """Return the current engine instance, or None."""
    return _engine_instance


def _serialize_value(v: Any) -> Any:
    """Convert non-JSON-serializable values."""
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _serialize_item(item: Any) -> dict:
    """Convert a DeliveryItem dataclass to a JSON-safe dict."""
    raw = asdict(item)
    return {
        k: ([_serialize_value(x) for x in v] if isinstance(v, list) else _serialize_value(v))
        for k, v in raw.items()
    }


@router.get("/status")
async def engine_status() -> dict:
    """Return engine status summary."""
    engine = _get_engine()
    if engine is None:
        return {
            "running": False,
            "enabled": False,
            "rules_count": 0,
            "pending_delivery": 0,
        }
    return engine.status()


@router.get("/recent")
async def engine_recent() -> list[dict]:
    """Return recent delivery items."""
    engine = _get_engine()
    if engine is None:
        return []
    return [_serialize_item(item) for item in engine.recent_items()]


@router.get("/rules")
async def engine_rules() -> list[dict]:
    """Return registered rule descriptions."""
    engine = _get_engine()
    if engine is None:
        return []
    return engine.rule_descriptions()


@router.post("/synthesize")
async def engine_synthesize() -> dict:
    """Force immediate synthesis, bypassing quiet window."""
    engine = _get_engine()
    if engine is None:
        return {"status": "error", "message": "Engine not running"}
    await engine.force_synthesis()
    return {"status": "ok", "message": "Synthesis triggered"}


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
        config.reset_data_dir()
        await engine.resume()
        await cache.refresh()
        return {"status": "ok", "message": "Simulation context deactivated"}

    sim_path = Path(req.sim_dir)
    if not sim_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {req.sim_dir}")
    if not (sim_path / ".sim-manifest.yaml").is_file():
        raise HTTPException(
            status_code=400, detail="Not a simulation directory (no .sim-manifest.yaml)"
        )

    await engine.pause()
    config.set_data_dir(sim_path)
    await cache.refresh()
    return {"status": "ok", "message": f"Simulation context activated: {sim_path.name}"}
