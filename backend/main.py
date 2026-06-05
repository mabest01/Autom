import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

load_dotenv()

# Configure loguru
os.makedirs("logs", exist_ok=True)
logger.remove()
logger.add(sys.stdout, level="INFO", colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}")
logger.add(
    "logs/app.log",
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
)

from database import init_db, get_jobs, get_stats, update_job_message
from models import JobResponse, JobUpdate, StatsResponse, ScrapeResponse, ApplyResponse, SessionStatusResponse
from scheduler import start_scheduler, stop_scheduler
from scraper import run_scraper
from auto_apply import apply_to_job, apply_pending_jobs
from session_manager import get_session_status


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    # Startup
    logger.info("Application starting up")
    await init_db()
    os.makedirs("screenshots", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("browser_data", exist_ok=True)
    start_scheduler()
    logger.info("Application startup complete")
    yield
    # Shutdown
    logger.info("Application shutting down")
    stop_scheduler()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="HelloWork Automation API",
    description="Automated job scraping and application system for HelloWork",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Background task wrappers
# ---------------------------------------------------------------------------

async def _scrape_background():
    """Background task: run the scraper."""
    try:
        logger.info("Background scrape task started")
        result = await run_scraper()
        logger.info(f"Background scrape task finished: {result}")
    except Exception as exc:
        logger.error(f"Background scrape task error: {exc}")


async def _apply_background(job_id: int, job_url: str, cover_message: str):
    """Background task: apply to a specific job."""
    try:
        logger.info(f"Background apply task started for job_id={job_id}")
        result = await apply_to_job(
            job_id=job_id,
            job_url=job_url,
            cover_message=cover_message,
        )
        logger.info(f"Background apply task finished for job_id={job_id}: {result}")
    except Exception as exc:
        logger.error(f"Background apply task error for job_id={job_id}: {exc}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "HelloWork Automation API"}


@app.get("/session/status", response_model=SessionStatusResponse)
async def session_status():
    """
    Return the current HelloWork session state:
    whether the bot is logged in, when it last checked/logged in,
    consecutive failure count, and block expiry if suspended.
    """
    return SessionStatusResponse(**get_session_status())


@app.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    status: str = Query(None, description="Filter by status: pending, applied, failed, skipped"),
    keyword: str = Query(None, description="Search keyword in title, company, description"),
    date_from: str = Query(None, description="ISO date string to filter from (e.g. 2024-01-01)"),
):
    """
    Retrieve jobs with optional filters.
    """
    try:
        jobs = await get_jobs(status=status, keyword=keyword, date_from=date_from)
        return [JobResponse(**job) for job in jobs]
    except Exception as exc:
        logger.error(f"Error fetching jobs: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve jobs: {str(exc)}")


@app.post("/scrape", response_model=dict)
async def trigger_scrape(background_tasks: BackgroundTasks):
    """
    Trigger the scraper in the background.
    Returns immediately with a confirmation message.
    """
    background_tasks.add_task(_scrape_background)
    logger.info("Scrape triggered via API")
    return {"message": "Scraping started in background", "status": "running"}


@app.post("/apply/{job_id}", response_model=ApplyResponse)
async def apply_to_specific_job(job_id: int, background_tasks: BackgroundTasks):
    """
    Trigger an application for a specific job in the background.
    """
    # Fetch the job to validate it exists and get URL/message
    try:
        jobs = await get_jobs()
        job = next((j for j in jobs if j["id"] == job_id), None)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch job: {str(exc)}")

    if not job:
        raise HTTPException(status_code=404, detail=f"Job with id={job_id} not found")

    if job.get("status") == "applied":
        return ApplyResponse(success=False, message="Job has already been applied to")

    job_url = job.get("url", "")
    if not job_url:
        raise HTTPException(status_code=400, detail="Job has no URL to apply to")

    cover_message = job.get("generated_message", "")
    background_tasks.add_task(_apply_background, job_id, job_url, cover_message)
    logger.info(f"Apply triggered for job_id={job_id} via API")
    return ApplyResponse(success=True, message=f"Application process started for job {job_id}")


@app.put("/jobs/{job_id}/message", response_model=dict)
async def update_job_cover_message(job_id: int, body: JobUpdate):
    """
    Update the generated cover message for a specific job.
    """
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        # Verify job exists
        jobs = await get_jobs()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job with id={job_id} not found")

        await update_job_message(job_id, body.message)
        logger.info(f"Updated message for job_id={job_id} via API")
        return {"message": "Cover message updated successfully", "job_id": job_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error updating job message: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to update message: {str(exc)}")


@app.get("/stats", response_model=StatsResponse)
async def get_statistics():
    """
    Get aggregated statistics about job applications.
    """
    try:
        stats = await get_stats()
        return StatsResponse(**stats)
    except Exception as exc:
        logger.error(f"Error fetching stats: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(exc)}")
