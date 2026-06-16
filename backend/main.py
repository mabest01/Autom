import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logger.remove()
logger.add(
    sys.stdout,
    level="INFO",
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}",
)
logger.add(
    "logs/app.log",
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
)

from database import (
    init_db, get_jobs, get_job_by_id, get_stats,
    update_job_message, update_job_status, insert_job, delete_job,
)
from models import (
    JobResponse, JobUpdate, StatsResponse, ScrapeResponse,
    ApplyResponse, SessionStatusResponse,
)
from scheduler import start_scheduler, stop_scheduler
from scraper import run_scraper
from auto_apply import apply_to_job, apply_pending_jobs
from session_manager import get_session_status
from ai_generator import generate_message


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up")
    await init_db()
    for d in ("screenshots", "logs", "browser_data"):
        os.makedirs(d, exist_ok=True)
    start_scheduler()
    logger.info("Application startup complete")
    yield
    logger.info("Application shutting down")
    stop_scheduler()
    logger.info("Application shutdown complete")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="HelloWork Automation API",
    description="Automated job scraping and application system for HelloWork",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Background task helpers ───────────────────────────────────────────────────

async def _scrape_background():
    try:
        logger.info("Background scrape task started")
        result = await run_scraper()
        logger.info(f"Background scrape task finished: {result}")
    except Exception as exc:
        logger.error(f"Background scrape task error: {exc}")


async def _apply_background(job_id: int, job_url: str, cover_message: str):
    try:
        logger.info(f"Background apply task started for job_id={job_id}")
        result = await apply_to_job(job_id=job_id, job_url=job_url, cover_message=cover_message)
        logger.info(f"Background apply task finished for job_id={job_id}: {result}")
    except Exception as exc:
        logger.error(f"Background apply task error for job_id={job_id}: {exc}")


async def _regenerate_background(job_id: int, title: str, company: str, description: str):
    try:
        logger.info(f"Regenerating cover message for job_id={job_id}")
        message = await generate_message(
            job_title=title,
            company=company,
            job_description=description,
        )
        await update_job_message(job_id, message)
        logger.info(f"Cover message regenerated for job_id={job_id}")
    except Exception as exc:
        logger.error(f"Failed to regenerate message for job_id={job_id}: {exc}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "HelloWork Automation API", "version": "1.1.0"}


@app.get("/session/status", response_model=SessionStatusResponse)
async def session_status():
    """Current HelloWork browser session state."""
    return SessionStatusResponse(**get_session_status())


@app.get("/stats", response_model=StatsResponse)
async def get_statistics():
    try:
        stats = await get_stats()
        return StatsResponse(**stats)
    except Exception as exc:
        logger.error(f"Error fetching stats: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    status:   Optional[str] = Query(None, description="pending | applied | failed | skipped"),
    keyword:  Optional[str] = Query(None, description="Search in title, company, description"),
    date_from: Optional[str] = Query(None, description="ISO date e.g. 2024-01-01"),
):
    try:
        jobs = await get_jobs(status=status, keyword=keyword, date_from=date_from)
        return [JobResponse(**j) for j in jobs]
    except Exception as exc:
        logger.error(f"Error fetching jobs: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int):
    job = await get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobResponse(**job)


@app.delete("/jobs/{job_id}")
async def delete_job_endpoint(job_id: int):
    deleted = await delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"message": f"Job {job_id} deleted"}


@app.post("/scrape", response_model=dict)
async def trigger_scrape(background_tasks: BackgroundTasks):
    background_tasks.add_task(_scrape_background)
    logger.info("Scrape triggered via API")
    return {"message": "Scraping started in background", "status": "running"}


@app.post("/apply/{job_id}", response_model=ApplyResponse)
async def apply_to_specific_job(job_id: int, background_tasks: BackgroundTasks):
    job = await get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if job.get("status") == "applied":
        return ApplyResponse(success=False, message="Job already applied to")
    if not job.get("url"):
        raise HTTPException(status_code=400, detail="Job has no URL")

    background_tasks.add_task(
        _apply_background, job_id, job["url"], job.get("generated_message", "")
    )
    logger.info(f"Apply triggered for job_id={job_id}")
    return ApplyResponse(success=True, message=f"Application process started for job {job_id}")


@app.put("/jobs/{job_id}/message", response_model=dict)
async def update_job_cover_message(job_id: int, body: JobUpdate):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    job = await get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    await update_job_message(job_id, body.message)
    logger.info(f"Message updated for job_id={job_id}")
    return {"message": "Cover message updated", "job_id": job_id}


@app.post("/jobs/{job_id}/regenerate", response_model=dict)
async def regenerate_message(job_id: int, background_tasks: BackgroundTasks):
    """Re-generate the AI cover message for a job (runs in background)."""
    job = await get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    background_tasks.add_task(
        _regenerate_background,
        job_id,
        job.get("title", ""),
        job.get("company", ""),
        job.get("description", ""),
    )
    return {"message": f"Message regeneration started for job {job_id}", "job_id": job_id}


@app.post("/jobs/seed", response_model=JobResponse)
async def seed_job(body: dict):
    """
    Insert a test job and generate its cover message.
    Useful for testing the dashboard without HelloWork access.
    Required fields: title, company, url, description
    Optional: location, salary
    """
    required = ["title", "company", "url", "description"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {missing}")

    job_id = await insert_job(body)
    try:
        message = await generate_message(
            job_title=body["title"],
            company=body["company"],
            job_description=body["description"],
        )
        await update_job_message(job_id, message)
    except Exception as exc:
        logger.warning(f"Could not generate message for seeded job {job_id}: {exc}")

    job = await get_job_by_id(job_id)
    return JobResponse(**job)
