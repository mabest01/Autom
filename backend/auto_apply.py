import asyncio
import os
import random
from datetime import datetime

from dotenv import load_dotenv
from loguru import logger
from playwright.async_api import async_playwright, Page, BrowserContext

from database import get_jobs, update_job_status

load_dotenv()

HELLOWORK_BASE = "https://www.hellowork.com"
BROWSER_DATA_DIR = os.path.abspath("./browser_data")
SCREENSHOTS_DIR = os.path.abspath("./screenshots")


def _get_user_agent() -> str:
    try:
        from fake_useragent import UserAgent
        ua = UserAgent()
        return ua.chrome
    except Exception:
        return (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )


async def _random_delay(min_s: float = 2.0, max_s: float = 5.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _take_screenshot(page: Page, job_id: int, suffix: str = "error") -> str:
    """Take a screenshot and return the path."""
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"job_{job_id}_{suffix}_{timestamp}.png"
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    try:
        await page.screenshot(path=filepath, full_page=True)
        logger.info(f"Screenshot saved: {filepath}")
    except Exception as exc:
        logger.warning(f"Failed to take screenshot: {exc}")
        return ""
    return filepath


async def apply_to_job(job_id: int, job_url: str, cover_message: str) -> dict:
    """
    Apply to a job using the existing browser session.
    Returns {'success': bool, 'message': str}
    """
    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    async with async_playwright() as pw:
        context: BrowserContext = await pw.chromium.launch_persistent_context(
            user_data_dir=BROWSER_DATA_DIR,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
            ],
            user_agent=_get_user_agent(),
            viewport={"width": 1280, "height": 800},
        )

        page = await context.new_page()

        try:
            # Navigate to job page
            logger.info(f"Navigating to job page for job_id={job_id}: {job_url}")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(2, 4)

            # Look for "Postuler" button with multiple strategies
            apply_button = None
            apply_selectors = [
                "button:has-text('Postuler')",
                "a:has-text('Postuler')",
                "[data-cy='apply-button']",
                "[data-testid='apply-button']",
                "button.postuler",
                ".apply-btn",
                "button[class*='apply']",
                "a[class*='apply']",
                "button:has-text('Je postule')",
                "button:has-text('Candidater')",
            ]

            for sel in apply_selectors:
                try:
                    locator = page.locator(sel).first
                    if await locator.count() > 0:
                        apply_button = locator
                        logger.debug(f"Found apply button with selector: {sel}")
                        break
                except Exception:
                    continue

            if apply_button is None:
                screenshot_path = await _take_screenshot(page, job_id, "no_apply_button")
                await update_job_status(
                    job_id,
                    "failed",
                    error="Apply button not found",
                    screenshot=screenshot_path,
                )
                await context.close()
                return {"success": False, "message": "Apply button not found on job page"}

            # Click apply button
            await apply_button.scroll_into_view_if_needed()
            await _random_delay(1, 2)
            await apply_button.click()
            logger.info(f"Clicked apply button for job_id={job_id}")

            # Wait for navigation or modal
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                await _random_delay(2, 3)

            await _random_delay(2, 4)

            # Look for cover message textarea
            message_selectors = [
                "textarea[name='message']",
                "textarea[name='cover_letter']",
                "textarea[placeholder*='message']",
                "textarea[placeholder*='lettre']",
                "textarea[placeholder*='motivation']",
                "textarea[id*='message']",
                "textarea[id*='cover']",
                "textarea",
                "[contenteditable='true']",
            ]

            message_filled = False
            if cover_message:
                for sel in message_selectors:
                    try:
                        locator = page.locator(sel).first
                        if await locator.count() > 0:
                            await locator.scroll_into_view_if_needed()
                            await locator.click()
                            await _random_delay(0.5, 1)
                            await locator.fill(cover_message)
                            message_filled = True
                            logger.info(f"Filled cover message for job_id={job_id} with selector: {sel}")
                            break
                    except Exception:
                        continue

                if not message_filled:
                    logger.warning(f"Could not find message textarea for job_id={job_id}, continuing without message")

            await _random_delay(1, 2)

            # Look for final submit/confirm button
            submit_selectors = [
                "button[type='submit']:has-text('Envoyer')",
                "button[type='submit']:has-text('Postuler')",
                "button[type='submit']:has-text('Confirmer')",
                "button[type='submit']:has-text('Valider')",
                "button:has-text('Envoyer ma candidature')",
                "button:has-text('Soumettre')",
                "button:has-text('Confirmer ma candidature')",
                "button[type='submit']",
                "input[type='submit']",
            ]

            submitted = False
            for sel in submit_selectors:
                try:
                    locator = page.locator(sel).first
                    if await locator.count() > 0:
                        await locator.scroll_into_view_if_needed()
                        await _random_delay(1, 2)
                        await locator.click()
                        submitted = True
                        logger.info(f"Clicked submit for job_id={job_id} with selector: {sel}")
                        break
                except Exception:
                    continue

            if not submitted:
                # If no submit button found after click (single-click apply), consider it applied
                logger.info(f"No explicit submit button found for job_id={job_id}, may be single-click apply")

            # Wait and check result
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                await _random_delay(2, 3)

            await _random_delay(2, 4)

            # Check for success indicators
            success_indicators = [
                "text=candidature envoyée",
                "text=Candidature envoyée",
                "text=candidature soumise",
                "text=Merci",
                "text=Félicitations",
                "[class*='success']",
                "[class*='confirmation']",
                "text=postulé",
                "text=Postulé",
            ]

            success = False
            for sel in success_indicators:
                try:
                    if await page.locator(sel).count() > 0:
                        success = True
                        logger.info(f"Success indicator found for job_id={job_id}: {sel}")
                        break
                except Exception:
                    continue

            # If we got this far without an error, consider it a tentative success
            # even if we couldn't confirm via DOM indicator
            if not success and submitted:
                success = True
                logger.info(f"Assuming success after submit for job_id={job_id}")

            screenshot_path = await _take_screenshot(page, job_id, "success" if success else "unknown")

            if success:
                await update_job_status(job_id, "applied", screenshot=screenshot_path)
                await context.close()
                return {"success": True, "message": "Application submitted successfully"}
            else:
                await update_job_status(
                    job_id,
                    "failed",
                    error="Could not confirm application submission",
                    screenshot=screenshot_path,
                )
                await context.close()
                return {"success": False, "message": "Could not confirm application submission"}

        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"Error applying to job {job_id}: {error_msg}")
            try:
                screenshot_path = await _take_screenshot(page, job_id, "error")
            except Exception:
                screenshot_path = ""
            await update_job_status(job_id, "failed", error=error_msg, screenshot=screenshot_path)
            await context.close()
            return {"success": False, "message": f"Error during application: {error_msg}"}


async def apply_pending_jobs():
    """
    Fetch all pending jobs that have a generated message and attempt to apply to them.
    Includes random delays between applications to avoid rate limiting.
    """
    logger.info("Starting batch apply for pending jobs")
    try:
        pending_jobs = await get_jobs(status="pending")
    except Exception as exc:
        logger.error(f"Failed to fetch pending jobs: {exc}")
        return

    if not pending_jobs:
        logger.info("No pending jobs to apply to")
        return

    logger.info(f"Found {len(pending_jobs)} pending jobs")
    applied = 0
    failed = 0

    for job in pending_jobs:
        job_id = job.get("id")
        job_url = job.get("url", "")
        cover_message = job.get("generated_message", "")

        if not job_url:
            logger.warning(f"Skipping job {job_id}: no URL")
            continue

        try:
            logger.info(f"Applying to job {job_id}: {job.get('title')} at {job.get('company')}")
            result = await apply_to_job(
                job_id=job_id,
                job_url=job_url,
                cover_message=cover_message,
            )

            if result.get("success"):
                applied += 1
                logger.info(f"Successfully applied to job {job_id}")
            else:
                failed += 1
                logger.warning(f"Failed to apply to job {job_id}: {result.get('message')}")

        except Exception as exc:
            failed += 1
            logger.error(f"Unexpected error applying to job {job_id}: {exc}")

        # Random delay between applications (8-20 seconds)
        await _random_delay(8, 20)

    logger.info(f"Batch apply complete: {applied} applied, {failed} failed out of {len(pending_jobs)} pending")
