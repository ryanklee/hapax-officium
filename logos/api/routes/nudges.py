"""Nudge action endpoints — act on or dismiss nudges."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from logos.api.cache import cache

router = APIRouter(prefix="/api/nudges", tags=["nudges"])


class NudgeActionResponse(BaseModel):
    status: str
    source_id: str
    action: str


@router.post("/{source_id}/act")
async def act_on_nudge(source_id: str) -> NudgeActionResponse:
    """Record that the operator executed a nudge's suggested action."""
    return _record(source_id, "executed")


@router.post("/{source_id}/dismiss")
async def dismiss_nudge(source_id: str) -> NudgeActionResponse:
    """Record that the operator dismissed a nudge."""
    return _record(source_id, "dismissed")


def _record(source_id: str, action: str) -> NudgeActionResponse:
    """Find the nudge and record the action.

    Decision tracking was removed with the personal logos modules.
    This now validates the nudge exists and returns the response.
    """
    # Find matching nudge in cache
    nudge = None
    for n in cache.nudges or []:
        sid = n.source_id if hasattr(n, "source_id") else n.get("source_id", "")
        if sid == source_id:
            nudge = n
            break

    if nudge is None:
        raise HTTPException(status_code=404, detail=f"Nudge '{source_id}' not found")

    return NudgeActionResponse(status="ok", source_id=source_id, action=action)
