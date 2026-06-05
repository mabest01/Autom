import asyncio
import os
import random
from typing import Optional
from urllib.parse import urlencode

from dotenv import load_dotenv
from loguru import logger
from playwright.async_api import async_playwright, Page, BrowserContext

from database import job_exists, insert_job, get_jobs, update_job_message
from ai_generator import generate_message
from session_manager import ensure_logged_in

load_dotenv()

HELLOWORK_BASE = "https://www.hellowork.com"
SEARCH_URL     = f"{HELLOWORK_BASE}/fr-fr/emploi/recherche.html"
BROWSER_DATA_DIR = os.path.abspath("./browser_data")


def _random_delay(min_s: float = 1.0, max_s: float = 3.0):
    return asyncio.sleep(random.uniform(min_s, max_s))


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




async def _extract_job_detail(page: Page, job_url: str) -> Optional[dict]:
    """Navigate to a job detail page and extract full description."""
    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
        await _random_delay(1, 2.5)

        # Extract description using multiple fallback selectors
        description = ""
        desc_selectors = [
            ".job-description",
            "[data-cy='job-description']",
            ".offer-description",
            "section.description",
            "div.tw-prose",
            "article .content",
            ".jobdescription",
            "[class*='description']",
            "main article",
        ]
        for sel in desc_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    description = await el.inner_text()
                    if description.strip():
                        break
            except Exception:
                continue

        # Check if "Postuler" apply button exists
        has_apply = False
        apply_selectors = [
            "button:has-text('Postuler')",
            "a:has-text('Postuler')",
            "[data-cy='apply-button']",
            ".apply-btn",
            "button.postuler",
        ]
        for sel in apply_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    has_apply = True
                    break
            except Exception:
                continue

        return {"description": description.strip(), "has_apply": has_apply}

    except Exception as exc:
        logger.warning(f"Failed to extract job detail from {job_url}: {exc}")
        return None


async def _extract_jobs_from_page(page: Page) -> list[dict]:
    """Extract job listings from the current search results page."""
    jobs = []

    # Multiple fallback selectors for job cards
    card_selectors = [
        "article[data-cy='jobCard']",
        "article.job-card",
        "div[data-cy='job-card']",
        "li.job-item",
        "article",
        ".job-result-item",
        "[class*='jobCard']",
    ]

    cards = []
    for sel in card_selectors:
        try:
            found = page.locator(sel)
            count = await found.count()
            if count > 0:
                logger.debug(f"Found {count} job cards with selector: {sel}")
                cards = found
                break
        except Exception:
            continue

    if not cards:
        logger.warning("No job cards found on the page")
        return jobs

    count = await cards.count()
    logger.info(f"Processing {count} job cards")

    for i in range(count):
        try:
            card = cards.nth(i)

            # Extract title
            title = ""
            title_selectors = ["h2", "h3", ".tw-typo-l", ".job-title", "[data-cy='job-title']", ".title"]
            for sel in title_selectors:
                try:
                    el = card.locator(sel).first
                    if await el.count() > 0:
                        title = (await el.inner_text()).strip()
                        if title:
                            break
                except Exception:
                    continue

            # Extract company
            company = ""
            company_selectors = [
                ".company-name",
                "[data-cy='company-name']",
                ".tw-typo-s",
                ".employer",
                "span.company",
                "[class*='company']",
            ]
            for sel in company_selectors:
                try:
                    el = card.locator(sel).first
                    if await el.count() > 0:
                        company = (await el.inner_text()).strip()
                        if company:
                            break
                except Exception:
                    continue

            # Extract location
            location = ""
            loc_selectors = [
                ".location",
                "[data-cy='location']",
                ".job-location",
                "[class*='location']",
                "span[class*='place']",
            ]
            for sel in loc_selectors:
                try:
                    el = card.locator(sel).first
                    if await el.count() > 0:
                        location = (await el.inner_text()).strip()
                        if location:
                            break
                except Exception:
                    continue

            # Extract salary
            salary = ""
            salary_selectors = [
                ".salary",
                "[data-cy='salary']",
                ".remuneration",
                "[class*='salary']",
                "[class*='remuneration']",
            ]
            for sel in salary_selectors:
                try:
                    el = card.locator(sel).first
                    if await el.count() > 0:
                        salary = (await el.inner_text()).strip()
                        if salary:
                            break
                except Exception:
                    continue

            # Extract URL
            job_url = ""
            url_selectors = ["a[href*='/emploi/']", "a[href*='/offre/']", "a.job-link", "a"]
            for sel in url_selectors:
                try:
                    el = card.locator(sel).first
                    if await el.count() > 0:
                        href = await el.get_attribute("href")
                        if href:
                            if href.startswith("http"):
                                job_url = href
                            else:
                                job_url = f"{HELLOWORK_BASE}{href}"
                            break
                except Exception:
                    continue

            if not job_url or not title:
                logger.debug(f"Skipping card {i}: missing title or URL")
                continue

            jobs.append(
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "salary": salary,
                    "url": job_url,
                    "description": "",
                }
            )

        except Exception as exc:
            logger.warning(f"Error extracting job card {i}: {exc}")
            continue

    return jobs


async def search_jobs(keywords: list, location: str) -> list[dict]:
    """Full search and extraction of job listings for given keywords."""
    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
    all_jobs = []
    seen_urls = set()

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

        # Ensure authenticated session (auto-reconnect with failure tracking)
        if not await ensure_logged_in(page, context):
            logger.error("Could not establish authenticated session — aborting scrape")
            await context.close()
            return []

        for keyword in keywords:
            logger.info(f"Searching for: '{keyword}' in '{location}'")
            keyword_jobs = []

            for page_num in range(1, 4):  # Up to 3 pages
                try:
                    params = {
                        "k": keyword,
                        "l": location,
                        "c": "Alternance",
                        "d": "1",  # Last 24h
                        "p": str(page_num),
                    }
                    search_full_url = f"{SEARCH_URL}?{urlencode(params)}"
                    logger.debug(f"Fetching page {page_num}: {search_full_url}")

                    await page.goto(search_full_url, wait_until="domcontentloaded", timeout=30000)
                    await _random_delay(1.5, 3)

                    # Check for no results
                    no_results = await page.locator(
                        "text=Aucun résultat, text=No results, .no-results, [class*='no-result']"
                    ).count()
                    if no_results > 0:
                        logger.info(f"No results on page {page_num} for keyword '{keyword}'")
                        break

                    page_jobs = await _extract_jobs_from_page(page)
                    if not page_jobs:
                        logger.info(f"No more jobs found on page {page_num} for '{keyword}'")
                        break

                    keyword_jobs.extend(page_jobs)
                    logger.info(f"Found {len(page_jobs)} jobs on page {page_num}")

                    await _random_delay(1, 2)

                except Exception as exc:
                    logger.error(f"Error fetching page {page_num} for '{keyword}': {exc}")
                    break

            # Fetch job details for unique URLs
            for job in keyword_jobs:
                if job["url"] in seen_urls:
                    continue
                seen_urls.add(job["url"])

                try:
                    detail = await _extract_job_detail(page, job["url"])
                    if detail:
                        job["description"] = detail.get("description", "")
                        job["has_apply"] = detail.get("has_apply", False)
                    all_jobs.append(job)
                except Exception as exc:
                    logger.warning(f"Error getting detail for {job['url']}: {exc}")
                    all_jobs.append(job)

                await _random_delay(1, 2.5)

        await context.close()

    return all_jobs


async def run_scraper() -> dict:
    """
    Main scraper entry point:
    - Reads keywords and location from environment
    - Searches for jobs, deduplicates, saves new ones to DB
    - Generates AI cover messages for new jobs
    Returns stats dict.
    """
    raw_keywords = os.getenv("SEARCH_KEYWORDS", "alternance data,alternance développeur")
    keywords = [k.strip() for k in raw_keywords.split(",") if k.strip()]
    location = os.getenv("SEARCH_LOCATION", "Île-de-France")

    logger.info(f"Starting scraper with keywords={keywords}, location={location}")

    jobs_found = 0
    jobs_new = 0

    try:
        jobs = await search_jobs(keywords, location)
        jobs_found = len(jobs)
        logger.info(f"Total jobs found: {jobs_found}")

        for job in jobs:
            try:
                if await job_exists(job["url"]):
                    logger.debug(f"Job already exists: {job['url']}")
                    continue

                job_id = await insert_job(job)
                jobs_new += 1

                # Generate AI cover message
                try:
                    message = await generate_message(
                        job_title=job.get("title", ""),
                        company=job.get("company", ""),
                        job_description=job.get("description", ""),
                    )
                    await update_job_message(job_id, message)
                except Exception as exc:
                    logger.error(f"Failed to generate message for job {job_id}: {exc}")

            except Exception as exc:
                logger.error(f"Error processing job {job.get('url', '')}: {exc}")

    except Exception as exc:
        logger.error(f"Scraper run failed: {exc}")
        return {"message": f"Scraper failed: {exc}", "jobs_found": 0, "jobs_new": 0}

    logger.info(f"Scraper complete: {jobs_found} found, {jobs_new} new")
    return {
        "message": "Scraper completed successfully",
        "jobs_found": jobs_found,
        "jobs_new": jobs_new,
    }
