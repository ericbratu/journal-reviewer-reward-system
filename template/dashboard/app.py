from __future__ import annotations

import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

from template.dashboard.service import SubnetStatsService, build_summary


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"

service = SubnetStatsService()


async def homepage(request):
    return FileResponse(INDEX_FILE)


async def subnet_stats(request):
    force_refresh = request.query_params.get("refresh") == "1"
    limit_param = request.query_params.get("limit")
    limit = int(limit_param) if limit_param and limit_param.isdigit() else None

    try:
        snapshot = service.get_snapshot(force_refresh=force_refresh)
        payload = snapshot.to_dict(limit=limit)
        payload["summary"] = build_summary(snapshot.entries)
        return JSONResponse(payload)
    except Exception as exc:
        return JSONResponse(
            {
                "error": str(exc),
                "command": service.command,
                "netuid": service.netuid,
                "network": service.network,
            },
            status_code=500,
        )


async def healthcheck(request):
    return JSONResponse(
        {
            "ok": True,
            "netuid": service.netuid,
            "network": service.network,
            "command": service.command,
            "cache_ttl": service.cache_ttl,
        }
    )


async def config(request):
    return JSONResponse(
        {
            "netuid": service.netuid,
            "network": service.network,
            "command": service.command,
            "cache_ttl": service.cache_ttl,
            "timeout_seconds": service.timeout_seconds,
            "title": os.getenv("SUBNET_DASHBOARD_TITLE", "Subnet Emissions Leaderboard"),
        }
    )


app = Starlette(
    debug=os.getenv("SUBNET_DASHBOARD_DEBUG", "false").lower() == "true",
    routes=[
        Route("/", homepage),
        Route("/api/subnet-stats", subnet_stats),
        Route("/api/config", config),
        Route("/health", healthcheck),
    ],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
