import aiosqlite
import os
from datetime import datetime, date
from loguru import logger

DATABASE_PATH = os.getenv("DATABASE_PATH", "jobs.db")


async def init_db():
    """Initialize database and create tables if they don't exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                salary TEXT,
                url TEXT UNIQUE NOT NULL,
                description TEXT,
                generated_message TEXT,
                status TEXT DEFAULT 'pending',
                applied_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                error_message TEXT,
                screenshot_path TEXT
            )
        """)
        await db.commit()
    logger.info("Database initialized successfully")


async def get_db():
    """Return an aiosqlite connection."""
    return aiosqlite.connect(DATABASE_PATH)


async def job_exists(url: str) -> bool:
    """Check if a job URL already exists in the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT 1 FROM jobs WHERE url = ?", (url,)) as cursor:
            row = await cursor.fetchone()
            return row is not None


async def insert_job(job_data: dict) -> int:
    """Insert a new job into the database and return its ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO jobs (title, company, location, salary, url, description, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                job_data.get("title", ""),
                job_data.get("company", ""),
                job_data.get("location", ""),
                job_data.get("salary", ""),
                job_data.get("url", ""),
                job_data.get("description", ""),
            ),
        )
        await db.commit()
        job_id = cursor.lastrowid
        logger.info(f"Inserted job ID={job_id}: {job_data.get('title')} at {job_data.get('company')}")
        return job_id


async def update_job_message(job_id: int, message: str):
    """Update the generated cover message for a job."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE jobs SET generated_message = ? WHERE id = ?",
            (message, job_id),
        )
        await db.commit()
    logger.debug(f"Updated message for job ID={job_id}")


async def update_job_status(
    job_id: int,
    status: str,
    error: str = None,
    screenshot: str = None,
):
    """Update the status of a job. Sets applied_at if status is 'applied'."""
    applied_at = datetime.utcnow().isoformat() if status == "applied" else None
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if applied_at:
            await db.execute(
                """
                UPDATE jobs
                SET status = ?, applied_at = ?, error_message = ?, screenshot_path = ?
                WHERE id = ?
                """,
                (status, applied_at, error, screenshot, job_id),
            )
        else:
            await db.execute(
                """
                UPDATE jobs
                SET status = ?, error_message = ?, screenshot_path = ?
                WHERE id = ?
                """,
                (status, error, screenshot, job_id),
            )
        await db.commit()
    logger.info(f"Updated job ID={job_id} status to '{status}'")


async def get_job_by_id(job_id: int) -> dict | None:
    """Fetch a single job by its primary key. Returns None if not found."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def delete_job(job_id: int) -> bool:
    """Delete a job by ID. Returns True if a row was deleted."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await db.commit()
        deleted = cursor.rowcount > 0
    if deleted:
        logger.info(f"Deleted job ID={job_id}")
    return deleted


async def get_jobs(
    status: str = None,
    keyword: str = None,
    date_from: str = None,
) -> list:
    """Retrieve jobs with optional filters."""
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)

    if keyword:
        query += " AND (title LIKE ? OR company LIKE ? OR description LIKE ?)"
        like_kw = f"%{keyword}%"
        params.extend([like_kw, like_kw, like_kw])

    if date_from:
        query += " AND created_at >= ?"
        params.append(date_from)

    query += " ORDER BY created_at DESC"

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_stats() -> dict:
    """Return aggregated statistics about the jobs."""
    today = date.today().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Total
        async with db.execute("SELECT COUNT(*) FROM jobs") as cur:
            total = (await cur.fetchone())[0]

        # Applied today
        async with db.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'applied' AND applied_at >= ?",
            (f"{today}T00:00:00",),
        ) as cur:
            applied_today = (await cur.fetchone())[0]

        # Pending
        async with db.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'pending'"
        ) as cur:
            pending = (await cur.fetchone())[0]

        # Failed
        async with db.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'failed'"
        ) as cur:
            failed = (await cur.fetchone())[0]

        # Applied total
        async with db.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'applied'"
        ) as cur:
            applied_total = (await cur.fetchone())[0]

    applied_plus_failed = applied_total + failed
    success_rate = round(applied_total / applied_plus_failed * 100, 1) if applied_plus_failed > 0 else 0.0

    return {
        "total": total,
        "applied_today": applied_today,
        "pending": pending,
        "failed": failed,
        "success_rate": success_rate,
    }
