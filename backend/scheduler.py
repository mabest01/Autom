import asyncio
import os
from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

_scheduler: AsyncIOScheduler = None


async def _run_scraper_task():
    """Wrapper for the scraper task to handle exceptions gracefully."""
    try:
        from scraper import run_scraper
        logger.info("Scheduled scraper task starting")
        result = await run_scraper()
        logger.info(f"Scheduled scraper task completed: {result}")
    except Exception as exc:
        logger.error(f"Scheduled scraper task failed: {exc}")


async def _run_apply_task():
    """Wrapper for the auto-apply task to handle exceptions gracefully."""
    try:
        from auto_apply import apply_pending_jobs
        logger.info("Scheduled auto-apply task starting")
        await apply_pending_jobs()
        logger.info("Scheduled auto-apply task completed")
    except Exception as exc:
        logger.error(f"Scheduled auto-apply task failed: {exc}")


def start_scheduler():
    """Initialize and start the APScheduler with configured jobs."""
    global _scheduler

    scrape_interval_hours = int(os.getenv("SCRAPE_INTERVAL_HOURS", "6"))
    auto_apply = os.getenv("AUTO_APPLY", "true").lower() == "true"

    _scheduler = AsyncIOScheduler()

    # Schedule scraper job
    _scheduler.add_job(
        _run_scraper_task,
        trigger=IntervalTrigger(hours=scrape_interval_hours),
        id="scraper_job",
        name="HelloWork Scraper",
        replace_existing=True,
        misfire_grace_time=300,  # 5 minutes grace time
    )
    logger.info(f"Scheduled scraper every {scrape_interval_hours} hours")

    # Schedule auto-apply 30 minutes after each scraper run
    if auto_apply:
        apply_delay_seconds = scrape_interval_hours * 3600 + 1800  # interval + 30 min
        _scheduler.add_job(
            _run_apply_task,
            trigger=IntervalTrigger(seconds=apply_delay_seconds, start_date=None),
            id="apply_job",
            name="HelloWork Auto Apply",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info(f"Scheduled auto-apply every {apply_delay_seconds // 3600:.1f} hours (30 min after scrape)")
    else:
        logger.info("AUTO_APPLY is disabled; auto-apply not scheduled")

    _scheduler.start()
    logger.info("Scheduler started successfully")


def stop_scheduler():
    """Stop the scheduler if it is running."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    else:
        logger.info("Scheduler was not running")
