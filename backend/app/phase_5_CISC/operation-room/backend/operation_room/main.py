"""
Operation Room — Case Initialization & Evidence Preservation
FastAPI backend entrypoint.

Heavy routes (LangGraph, extra ML, etc.) are loaded best-effort so the API can
start when optional dependencies are not installed.
"""

from contextlib import asynccontextmanager
import importlib
import logging
import sys
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from operation_room.config import settings
from operation_room.routes import bindings
from operation_room.routes import (
    cases,
    evidence,
    audit,
    timeline,
    anomaly,
    correlation,
    crud,
    network,
    depth,
    placeholder,
    evidence_binder,
    exfiltration,
)
from operation_room.mcp import create_mcp_router, get_server

_log = logging.getLogger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


mcp_server = get_server()


def _include_optional_route(module_basename: str) -> bool:
    """Import operation_room.routes.<name> and mount its .router; return True if loaded."""
    try:
        mod = importlib.import_module(f"operation_room.routes.{module_basename}")
        app.include_router(mod.router)
        _log.info("Operation Room router loaded: %s", module_basename)
        return True
    except Exception as e:
        _log.warning("Operation Room router skipped (%s): %s", module_basename, e)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure data directories exist and initialize services."""
    logger = logging.getLogger(__name__)

    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.CASES_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from operation_room.services.vector_store import get_vector_store

        get_vector_store()
        logger.info("Vector store initialized: %s", settings.VECTOR_STORE_PATH)
    except Exception as e:
        logger.warning("Vector store initialization skipped: %s", e)

    try:
        importlib.import_module("operation_room.mcp.tools")
        logger.info("MCP tools registered")
    except Exception as e:
        logger.warning("MCP tools registration skipped: %s", e)

    try:
        await mcp_server.start()
        logger.info("MCP server started")
    except Exception as e:
        logger.warning("MCP server startup skipped: %s", e)

    try:
        yield
    finally:
        try:
            await mcp_server.stop()
        except Exception:
            pass
        from operation_room.database import close_all_vaults

        close_all_vaults()


app = FastAPI(
    title="Operation Room — Case Initialization API",
    description=(
        "Forensic case management, evidence import with cryptographic hashing, "
        "and tamper‑evident chain‑of‑custody logging. Includes Multi-Agent Report Automation."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core routes (minimal dependency chain)
app.include_router(cases.router)
app.include_router(evidence.router)
app.include_router(audit.router)
app.include_router(timeline.router)
app.include_router(anomaly.router)
app.include_router(correlation.router)
app.include_router(crud.router)
app.include_router(network.router)
app.include_router(depth.router)
app.include_router(exfiltration.router)
app.include_router(bindings.router)
app.include_router(placeholder.router)
app.include_router(evidence_binder.router)

# Optional: LangGraph / LLM / heavy report pipelines — require extra pip packages
_OPTIONAL_ROUTES = (
    "studio_v4",
    "agents",
    "deep_research",
    "tools",
    "investigation",
    "workflow",
    "memory",
    "report_sections",
    "learning",
    "report_evidence",
    "report_generation",
)
_loaded_report_evidence = False
_loaded_report_generation = False
for _r in _OPTIONAL_ROUTES:
    ok = _include_optional_route(_r)
    if _r == "report_evidence" and ok:
        _loaded_report_evidence = True
    if _r == "report_generation" and ok:
        _loaded_report_generation = True

if _loaded_report_evidence:
    try:
        mod = importlib.import_module("operation_room.routes.report_evidence")
        app.include_router(mod.router, prefix="/api", include_in_schema=False)
    except Exception as e:
        _log.warning("report_evidence alias skipped: %s", e)
if _loaded_report_generation:
    try:
        mod = importlib.import_module("operation_room.routes.report_generation")
        app.include_router(mod.router, prefix="/api", include_in_schema=False)
    except Exception as e:
        _log.warning("report_generation alias skipped: %s", e)

app.include_router(create_mcp_router(mcp_server), prefix="/mcp")


@app.get("/api/health", tags=["System"])
def health_check():
    return {"status": "ok", "service": "operation-room-backend"}
