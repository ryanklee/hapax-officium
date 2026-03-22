"""Logos API routes for cycle mode switching."""

from __future__ import annotations

import asyncio
import shutil
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from shared.cycle_mode import MODE_FILE, CycleMode

router = APIRouter(prefix="/api", tags=["system"])

# Resolve hapax-mode script path
_SCRIPT = Path(__file__).parent.parent.parent.parent / "scripts" / "hapax-mode"


class CycleModeRequest(BaseModel):
    mode: CycleMode

    @field_validator("mode", mode="before")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("dev", "prod"):
            raise ValueError("mode must be 'dev' or 'prod'")
        return v


async def _run_hapax_mode(mode: str) -> tuple[int, str]:
    """Run hapax-mode script asynchronously."""
    script = shutil.which("hapax-mode") or str(_SCRIPT)
    proc = await asyncio.create_subprocess_exec(
        script,
        mode,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return proc.returncode or 0, stdout.decode()


@router.get("/cycle-mode")
async def get_cycle_mode():
    try:
        mode = CycleMode(MODE_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        mode = CycleMode.PROD

    try:
        mtime = MODE_FILE.stat().st_mtime
        switched_at = datetime.fromtimestamp(mtime, tz=UTC).isoformat()
    except FileNotFoundError:
        switched_at = None

    return {"mode": mode.value, "switched_at": switched_at}


@router.put("/cycle-mode")
async def put_cycle_mode(body: CycleModeRequest):
    returncode, output = await _run_hapax_mode(body.mode.value)
    if returncode != 0:
        import logging

        logging.getLogger("logos.api.cycle_mode").error(
            "hapax-mode failed (exit %d): %s", returncode, output
        )
        raise HTTPException(status_code=500, detail="Cycle mode switch failed")

    return await get_cycle_mode()
