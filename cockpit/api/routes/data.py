"""Data endpoints — serve cached management collector results.

All endpoints return the latest cached data from the background
refresh loop. Clients poll at 5-minute cadence.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from cockpit.api.cache import cache

router = APIRouter(prefix="/api", tags=["data"])


def _dict_factory(fields: list[tuple]) -> dict:
    """Custom dict factory for asdict() that handles Path objects."""
    return {k: str(v) if isinstance(v, Path) else v for k, v in fields}


def _to_dict(obj: Any) -> Any:
    """Convert a dataclass (or list of dataclasses) to a dict."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj, dict_factory=_dict_factory)
    return obj


def _response(data: Any) -> JSONResponse:
    """Return JSON response with X-Cache-Age header."""
    return JSONResponse(content=data, headers={"X-Cache-Age": str(cache.cache_age())})


def _freshness_response(data: Any, *, hot: bool = True) -> JSONResponse:
    """Return JSON response with _freshness metadata for synthesis artifacts."""
    from cockpit.api.cache import cache as _cache

    if hot:
        change_age = _cache.hot_change_age()
    else:
        hot_age = _cache.hot_change_age()
        warm_age = _cache.warm_change_age()
        if hot_age >= 0 and warm_age >= 0:
            change_age = min(hot_age, warm_age)
        elif hot_age >= 0:
            change_age = hot_age
        elif warm_age >= 0:
            change_age = warm_age
        else:
            change_age = -1

    freshness = {
        "data_change_age": change_age,
    }

    if isinstance(data, dict) and data is not None:
        data = {**data, "_freshness": freshness}
    elif data is not None:
        data = {"data": data, "_freshness": freshness}

    return JSONResponse(
        content=data,
        headers={"X-Cache-Age": str(_cache.cache_age())},
    )


# ── Management data ────────────────────────────────────────────────────


@router.get("/briefing")
async def get_briefing():
    return _freshness_response(cache.briefing, hot=True)


@router.get("/management")
async def get_management():
    return _response(_to_dict(cache.management))


@router.get("/nudges")
async def get_nudges():
    return _response(_to_dict(cache.nudges))


@router.get("/goals")
async def get_goals():
    return _response(_to_dict(cache.goals))


@router.get("/agents")
async def get_agents():
    return _response(_to_dict(cache.agents))


@router.get("/team/health")
async def get_team_health():
    return _response(_to_dict(cache.team_health))


# ── Tier 1 expansion ──────────────────────────────────────────────────


@router.get("/okrs")
async def get_okrs():
    return _response(_to_dict(cache.okrs))


@router.get("/smart-goals")
async def get_smart_goals():
    return _response(_to_dict(cache.smart_goals))


@router.get("/incidents")
async def get_incidents():
    return _response(_to_dict(cache.incidents))


@router.get("/postmortem-actions")
async def get_postmortem_actions():
    return _response(_to_dict(cache.postmortem_actions))


@router.get("/review-cycles")
async def get_review_cycles():
    return _response(_to_dict(cache.review_cycles))


@router.get("/status-reports")
async def get_status_reports():
    return _response(_to_dict(cache.status_reports))


@router.get("/status")
async def get_status():
    """Minimal system self-check."""
    return _response({"healthy": True})
