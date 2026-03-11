"""FastAPI application for the cockpit API.

Serves data from cockpit/data/ collectors over HTTP.
Designed to be consumed by the React SPA at cockpit-web/.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cockpit.api.cache import start_refresh_loop
from cockpit.api.sessions import agent_run_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_refresh_loop()
    from cockpit.engine import ReactiveEngine

    engine = ReactiveEngine(agent_run_manager=agent_run_manager)
    set_engine(engine)
    await engine.start()
    yield
    await engine.stop()
    await agent_run_manager.shutdown()


app = FastAPI(
    title="management-cockpit-api",
    description="Management cockpit API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:8050",  # Production (self-hosted SPA)
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8050",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

from cockpit.api.routes.agents import router as agents_router
from cockpit.api.routes.cycle_mode import router as cycle_mode_router
from cockpit.api.routes.data import router as data_router
from cockpit.api.routes.demos import router as demos_router
from cockpit.api.routes.engine import router as engine_router
from cockpit.api.routes.engine import set_engine
from cockpit.api.routes.nudges import router as nudges_router
from cockpit.api.routes.profile import router as profile_router
from cockpit.api.routes.scout import router as scout_router

app.include_router(data_router)
app.include_router(nudges_router)
app.include_router(agents_router)
app.include_router(profile_router)
app.include_router(demos_router)
app.include_router(engine_router)
app.include_router(cycle_mode_router)
app.include_router(scout_router)


@app.get("/")
async def root():
    return {"name": "cockpit-api", "version": "0.2.0"}


from pathlib import Path

SPA_DIR = Path(__file__).parent / "static"
if SPA_DIR.is_dir():
    from starlette.responses import FileResponse, JSONResponse
    from starlette.staticfiles import StaticFiles

    @app.get("/app/{path:path}")
    async def spa_catchall(path: str):
        index = SPA_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse({"error": "SPA not built"}, status_code=404)

    app.mount("/static", StaticFiles(directory=SPA_DIR), name="spa")
