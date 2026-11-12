import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.logging import logger
from app.db.base import Base
from app.db.session import SessionLocal, engine

_IS_VERCEL = bool(os.environ.get("VERCEL"))

new_app = FastAPI(title="Forensic AI Engine")

new_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables (on Vercel uses ephemeral SQLite under /tmp — see app.config).
Base.metadata.create_all(bind=engine)

# ── Core routers (always available) ─────────────────────────────────────────
from app.auth.router import router as auth_router
from app.ingestion.router import router as new_ingestion
from app.ledger.router import router as new_ledger
from app.phase2.router import router as phase2_router
from app.phase4.router import router as phase4_router

new_app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
new_app.include_router(new_ingestion, prefix="/api/ingestion", tags=["Ingestion"])
new_app.include_router(phase2_router, prefix="/api/phase2", tags=["Phase 2: Universal Translator"])
new_app.include_router(phase4_router, prefix="/api/phase4", tags=["Phase 4: Analytics Dataset"])
new_app.include_router(new_ledger, prefix="/api")

if not _IS_VERCEL:
    from app.dashboard.router import router as new_dashboard
    from app.detection.router import router as new_detection
    from app.features.router import router as new_features
    from app.ingestion.ws_router import router as ws_ingestion
    from app.reporting.router import router as new_reporting

    new_app.include_router(new_features, prefix="/api")
    new_app.include_router(new_detection, prefix="/api")
    new_app.include_router(new_dashboard, prefix="/api")
    new_app.include_router(new_reporting, prefix="/api")
    new_app.include_router(ws_ingestion, tags=["Secure WebSocket Ingestion"])

    _phase5_backend_root = Path(__file__).resolve().parent / "phase_5_CISC" / "operation-room" / "backend"
    if _phase5_backend_root.is_dir():
        _p5 = str(_phase5_backend_root)
        if _p5 not in sys.path:
            sys.path.insert(0, _p5)
        try:
            from operation_room.main import app as phase5_operation_room_app

            new_app.mount("/api/phase5", phase5_operation_room_app)
            logger.info("Phase 5 Operation Room mounted at /api/phase5")
        except Exception as _p5_exc:
            logger.warning(
                "Phase 5 Operation Room not mounted: {} — install: pip install -r app/phase_5_CISC/operation-room/backend/requirements.txt",
                _p5_exc,
            )

    try:
        from app.phase3.phase3_hot_and_cold_db.main import new_app as phase3_app  # type: ignore

        new_app.mount("/api/phase3", phase3_app)
    except Exception:
        @new_app.get("/api/phase3", include_in_schema=False)
        def _phase3_unavailable():
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "detail": "Phase 3 app could not be mounted (missing optional dependencies).",
                },
            )
else:
    @new_app.get("/api/phase3", include_in_schema=False)
    def _phase3_vercel_unavailable():
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "detail": "Phase 3 is not deployed on Vercel (use full backend for cold storage).",
            },
        )

    @new_app.api_route("/api/phase5", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    @new_app.api_route("/api/phase5/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def _phase5_vercel_unavailable(path: str = ""):
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "detail": "Phase 5 Operation Room is not deployed on Vercel (use full backend).",
            },
        )


@new_app.get("/")
def health():
    return {"status": "Forensic Engine Online", "vercel": _IS_VERCEL}


if not _IS_VERCEL:
    from app.ingestion.integrity import verify_hash_chain

    @new_app.on_event("startup")
    def startup_integrity_check():
        new_db = SessionLocal()
        try:
            new_result = verify_hash_chain(new_db)
            if hasattr(new_result, "get") and new_result.get("status") != "chain_valid":
                logger.warning(
                    f"Hash chain integrity check: {new_result.get('status', 'unknown')} "
                    f"(broken_at: {new_result.get('broken_at', 'N/A')})"
                )
                logger.info("Server continues - hash chain warnings are non-fatal in development")
            else:
                logger.info("Hash chain verified.")
        except Exception as new_e:
            logger.warning(f"Integrity check skipped: {new_e}")
        finally:
            new_db.close()

# Vercel FastAPI detection expects a top-level `app` (uvicorn still uses app.main:new_app).
app = new_app
