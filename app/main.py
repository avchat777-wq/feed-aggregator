"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import async_session
from app.api import auth, sources, objects, logs, mappings, dashboard, feed, notifications
from app.api import admin
from app.api.auth import ensure_admin_exists
from app.scheduler.scheduler import start_scheduler, scheduler
from app.services.avito_lookup import avito_lookup
from app.services.dev_id_mapping import dev_id_mapping

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting Feed Aggregator...")

    # Ensure admin user exists
    async with async_session() as session:
        await ensure_admin_exists(session)

    # Auto-load Avito developments lookup from disk (if file exists)
    avito_lookup.try_autoload()

    # Load development_id → jk_name manual mappings from DB
    async with async_session() as session:
        await dev_id_mapping.reload(session)

    # Start scheduler
    start_scheduler()
    logger.info("Application started successfully")

    yield

    # Shutdown
    scheduler.shutdown()
    logger.info("Application shut down")


app = FastAPI(
    title="Feed Aggregator — MIEL Barnaul",
    description="Aggregation of XML feeds and Excel tables from multiple developers "
                "into a unified CRM Intrum feed.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(sources.router)
app.include_router(objects.router)
app.include_router(logs.router)
app.include_router(mappings.router)
app.include_router(feed.router)
app.include_router(notifications.router)
app.include_router(admin.router)

# Serve static feed files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass  # Directory may not exist yet


@app.get("/")
async def root():
    return {
        "name": "Feed Aggregator",
        "version": "1.0.0",
        "feed_url": f"{settings.feed_base_url}/feed.xml",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
