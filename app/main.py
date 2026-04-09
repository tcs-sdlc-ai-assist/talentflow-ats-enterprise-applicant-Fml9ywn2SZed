import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.database import create_all_tables, dispose_engine
from app.routers import (
    applications,
    audit,
    auth_router,
    candidates,
    dashboard,
    interviews,
    jobs,
    landing,
)
from app.utils.bootstrap import ensure_admin_exists
from app.utils.seed_data import seed_all
from app.utils.template_helpers import register_template_helpers

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR.parent / "uploads"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting TalentFlow ATS application...")

    await create_all_tables()
    logger.info("Database tables ensured.")

    await ensure_admin_exists()
    logger.info("Admin user bootstrap complete.")

    try:
        results = await seed_all()
        logger.info(
            "Seed data complete: %d departments, %d skills created.",
            results.get("departments", 0),
            results.get("skills", 0),
        )
    except Exception:
        logger.exception("Failed to seed default data (non-fatal).")

    logger.info("TalentFlow ATS startup complete.")

    yield

    logger.info("Shutting down TalentFlow ATS application...")
    await dispose_engine()
    logger.info("TalentFlow ATS shutdown complete.")


app = FastAPI(
    title="TalentFlow ATS",
    description="Applicant Tracking System — A modern recruitment management platform",
    version="1.0.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
register_template_helpers(templates.env)

app.include_router(landing.router)
app.include_router(auth_router.router)
app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(applications.router)
app.include_router(interviews.router)
app.include_router(dashboard.router)
app.include_router(audit.router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info("Static files mounted from %s", STATIC_DIR)

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "TalentFlow ATS", "version": "1.0.0"}