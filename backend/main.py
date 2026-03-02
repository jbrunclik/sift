import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """App lifespan: initialize DB, start scheduler."""
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("Starting Sift...")

    # Initialize database
    db = await init_db()
    await db.close()
    logger.info("Database initialized at %s", settings.database_path)

    # Start scheduler
    try:
        from apscheduler import AsyncScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        from backend.scheduler.cleanup import run_cleanup
        from backend.scheduler.worker import (
            extract_unextracted_articles,
            fetch_all_sources,
            score_unscored_articles,
            synthesize_profile,
        )

        scheduler = AsyncScheduler()
        await scheduler.__aenter__()
        await scheduler.add_schedule(
            fetch_all_sources,
            IntervalTrigger(minutes=30),
            id="fetch_all",
        )
        await scheduler.add_schedule(
            score_unscored_articles,
            IntervalTrigger(minutes=settings.scoring_interval_minutes),
            id="score_unscored",
        )
        await scheduler.add_schedule(
            extract_unextracted_articles,
            IntervalTrigger(minutes=settings.extraction_interval_minutes),
            id="extract",
        )
        await scheduler.add_schedule(
            run_cleanup,
            IntervalTrigger(hours=24),
            id="cleanup",
        )
        await scheduler.add_schedule(
            synthesize_profile,
            IntervalTrigger(hours=settings.profile_synthesis_interval_hours),
            id="synthesize_profile",
        )
        await scheduler.start_in_background()
        logger.info(
            "Scheduler started (fetch=30min, score=%dmin, extract=%dmin, "
            "synthesis=%dh, cleanup=daily)",
            settings.scoring_interval_minutes,
            settings.extraction_interval_minutes,
            settings.profile_synthesis_interval_hours,
        )
    except Exception:
        logger.exception("Scheduler failed to start — fetching will only work manually")

    yield

    # Shutdown
    with contextlib.suppress(Exception):
        await scheduler.__aexit__(None, None, None)
    logger.info("Sift stopped.")


def create_app() -> FastAPI:
    app = FastAPI(title="Sift", version="0.1.0", lifespan=lifespan)

    # CORS for dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    from backend.api.routes_articles import router as articles_router
    from backend.api.routes_feedback import router as feedback_router
    from backend.api.routes_health import router as health_router
    from backend.api.routes_onboarding import router as onboarding_router
    from backend.api.routes_preferences import router as preferences_router
    from backend.api.routes_sources import router as sources_router

    app.include_router(articles_router)
    app.include_router(sources_router)
    app.include_router(feedback_router)
    app.include_router(preferences_router)
    app.include_router(onboarding_router)
    app.include_router(health_router)

    # Serve frontend static files if built
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()
