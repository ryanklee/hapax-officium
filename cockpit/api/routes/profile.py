"""Profile endpoints — management self-awareness facts."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("cockpit.api.profile")

router = APIRouter(prefix="/api/profile", tags=["profile"])

MANAGEMENT_DIMENSIONS = frozenset(
    {
        "management_practice",
        "team_leadership",
        "decision_patterns",
        "communication_style",
        "attention_distribution",
        "self_awareness",
    }
)


@router.get("")
async def get_profile_summary():
    """List management self-awareness dimensions with fact counts."""
    import asyncio

    def _read():
        from agents.management_profiler import load_existing_profile

        profile = load_existing_profile()
        if not profile:
            return {"dimensions": [], "missing": sorted(MANAGEMENT_DIMENSIONS), "total_facts": 0}
        dims = []
        for dim in profile.dimensions:
            if dim.name in MANAGEMENT_DIMENSIONS:
                dims.append(
                    {"name": dim.name, "fact_count": len(dim.facts), "summary": dim.summary or ""}
                )
        missing = sorted(MANAGEMENT_DIMENSIONS - {d["name"] for d in dims})
        return {
            "dimensions": dims,
            "missing": missing,
            "total_facts": sum(d["fact_count"] for d in dims),
            "version": profile.version,
            "updated_at": profile.updated_at,
        }

    return await asyncio.to_thread(_read)


@router.get("/{dimension}")
async def get_dimension(dimension: str):
    """Get facts for one management dimension."""
    import asyncio

    if dimension not in MANAGEMENT_DIMENSIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown dimension '{dimension}'. Valid: {sorted(MANAGEMENT_DIMENSIONS)}",
        )

    def _read():
        from agents.management_profiler import load_existing_profile

        profile = load_existing_profile()
        if not profile:
            return None
        for dim in profile.dimensions:
            if dim.name == dimension:
                facts = []
                for f in dim.facts:
                    facts.append(
                        {
                            "key": f.key,
                            "value": f.value,
                            "confidence": f.confidence,
                            "source": f.source,
                        }
                    )
                return {"name": dim.name, "summary": dim.summary or "", "facts": facts}
        return None

    result = await asyncio.to_thread(_read)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Dimension '{dimension}' not found or no profile"
        )
    return result


class CorrectionRequest(BaseModel):
    dimension: str
    key: str
    value: str


@router.post("/correct")
async def correct_fact(req: CorrectionRequest):
    """Correct a management self-awareness fact."""
    import asyncio

    if req.dimension not in MANAGEMENT_DIMENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown dimension '{req.dimension}'. Valid: {sorted(MANAGEMENT_DIMENSIONS)}",
        )

    def _apply():
        from agents.management_profiler import apply_corrections

        if req.value.upper() == "DELETE":
            corrections = [{"dimension": req.dimension, "key": req.key, "value": None}]
        else:
            corrections = [{"dimension": req.dimension, "key": req.key, "value": req.value}]
        return apply_corrections(corrections)

    result = await asyncio.to_thread(_apply)
    return {"status": "ok", "result": result}
