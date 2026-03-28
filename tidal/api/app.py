"""FastAPI application for the Tidal control plane."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from tidal.api.errors import APIError
from tidal.api.routes.actions import router as actions_router
from tidal.api.routes.auctions import router as auctions_router
from tidal.api.routes.dashboard import router as dashboard_router
from tidal.api.routes.kick import router as kick_router
from tidal.api.routes.logs import router as logs_router
from tidal.api.services.action_audit import run_receipt_reconciler
from tidal.config import Settings, load_settings
from tidal.persistence.db import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or load_settings()
    database = Database(resolved_settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ANN202
        reconcile_task: asyncio.Task[None] | None = None
        if resolved_settings.rpc_url:
            reconcile_task = asyncio.create_task(run_receipt_reconciler(resolved_settings, database))
        try:
            yield
        finally:
            if reconcile_task is not None:
                reconcile_task.cancel()
                try:
                    await reconcile_task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(title="Tidal Control Plane", version="1.0.0", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.database = database

    if resolved_settings.tidal_api_cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved_settings.tidal_api_cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(APIError)
    async def handle_api_error(_request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "warnings": [], "data": None, "detail": exc.message},
        )

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {"status": "ok", "warnings": [], "data": {"ready": True}}

    prefix = "/api/v1/tidal"
    app.include_router(dashboard_router, prefix=prefix, tags=["dashboard"])
    app.include_router(logs_router, prefix=prefix, tags=["logs"])
    app.include_router(kick_router, prefix=prefix, tags=["kick"])
    app.include_router(auctions_router, prefix=prefix, tags=["auctions"])
    app.include_router(actions_router, prefix=prefix, tags=["actions"])
    return app


app = create_app()

