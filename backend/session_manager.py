import asyncio
import os
import random
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from typing import Optional

from dotenv import load_dotenv
from loguru import logger
from playwright.async_api import Page, BrowserContext

load_dotenv()

HELLOWORK_BASE = "https://www.hellowork.com"
DASHBOARD_URL  = f"{HELLOWORK_BASE}/fr-fr/compte/tableau-de-bord.html"
LOGIN_URL      = f"{HELLOWORK_BASE}/fr-fr/compte/connexion.html"
SESSION_FILE   = os.path.abspath("./session.json")

# ── Module-level singleton state (shared across all imports) ─────────────────
_logged_in:              bool            = False
_last_check:             Optional[str]   = None
_last_login:             Optional[str]   = None
_consecutive_failures:   int             = 0
_blocked_until:          Optional[str]   = None   # ISO-8601 timestamp


async def _delay(min_s: float = 1.0, max_s: float = 3.0) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))


def get_session_status() -> dict:
    """Return current session state for the /session/status endpoint."""
    return {
        "logged_in":            _logged_in,
        "last_check":           _last_check,
        "last_login":           _last_login,
        "consecutive_failures": _consecutive_failures,
        "blocked_until":        _blocked_until,
    }


async def _send_alert(subject: str, body: str) -> None:
    """Log an alert and optionally send an e-mail if SMTP is configured."""
    logger.error(f"ALERT — {subject}: {body}")

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    alert_to  = os.getenv("EMAIL_ALERT", "")

    if not all([smtp_host, smtp_user, smtp_pass, alert_to]):
        logger.info("SMTP not configured — alert logged only")
        return

    try:
        msg             = MIMEText(body, "plain", "utf-8")
        msg["Subject"]  = subject
        msg["From"]     = smtp_user
        msg["To"]       = alert_to

        with smtplib.SMTP(smtp_host, smtp_port) as srv:
            srv.starttls()
            srv.login(smtp_user, smtp_pass)
            srv.send_message(msg)
        logger.info(f"Alert e-mail sent to {alert_to}")
    except Exception as exc:
        logger.warning(f"Failed to send alert e-mail: {exc}")


# ── Login ────────────────────────────────────────────────────────────────────

async def login(page: Page) -> None:
    """Fill and submit the HelloWork login form."""
    email    = os.getenv("HELLOWORK_EMAIL", "")
    password = os.getenv("HELLOWORK_PASSWORD", "")

    if not email or not password:
        raise ValueError("HELLOWORK_EMAIL or HELLOWORK_PASSWORD not set in .env")

    logger.info("Navigating to HelloWork login page")
    await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
    await _delay(1, 2)

    # Accept cookie banner if present
    try:
        btn = page.locator(
            "button:has-text('Accepter'), button:has-text('Accept'), #didomi-notice-agree-button"
        )
        if await btn.count() > 0:
            await btn.first.click()
            await _delay(0.5, 1)
    except Exception:
        pass

    # Fill e-mail
    email_filled = False
    for sel in ['input[name="login"]', 'input[type="email"]',
                'input[id="login"]', 'input[placeholder*="mail"]']:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                await loc.fill(email)
                email_filled = True
                logger.debug(f"Email filled via {sel}")
                break
        except Exception:
            continue
    if not email_filled:
        raise RuntimeError("Email input not found on HelloWork login page")

    await _delay(0.3, 0.8)

    # Fill password
    pw_filled = False
    for sel in ['input[name="password"]', 'input[type="password"]', 'input[id="password"]']:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                await loc.fill(password)
                pw_filled = True
                logger.debug(f"Password filled via {sel}")
                break
        except Exception:
            continue
    if not pw_filled:
        raise RuntimeError("Password input not found on HelloWork login page")

    await _delay(0.5, 1)

    # Submit
    submitted = False
    for sel in ['button[type="submit"]', 'input[type="submit"]',
                'button:has-text("Connexion")', 'button:has-text("Se connecter")']:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                await loc.click()
                submitted = True
                logger.debug(f"Submit clicked via {sel}")
                break
        except Exception:
            continue
    if not submitted:
        raise RuntimeError("Submit button not found on HelloWork login page")

    await page.wait_for_load_state("networkidle", timeout=15_000)
    await _delay(1, 2)
    logger.info("Login form submitted")


# ── Session validation ────────────────────────────────────────────────────────

async def check_session(page: Page) -> bool:
    """
    Navigate to the account dashboard and determine whether the session is live.
    A redirect to the login page is definitive proof of an expired session.
    Updates module-level state and returns True/False.
    """
    global _logged_in, _last_check

    _last_check = datetime.now(timezone.utc).isoformat()

    try:
        logger.debug("Checking session via dashboard navigation")
        await page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(2)

        current_url = page.url

        if "connexion" in current_url or "login" in current_url:
            logger.info("Session invalid: redirected to login page")
            _logged_in = False
            return False

        # Positive indicators on the dashboard page
        for sel in [
            ".dashboard", "[data-cy='dashboard']",
            "text=Tableau de bord", "text=Mes candidatures",
            "[href*='/compte/profil']", "[href*='/profil/']",
            ".account-nav", "[data-testid='user-menu']",
        ]:
            try:
                if await page.locator(sel).count() > 0:
                    _logged_in = True
                    logger.debug("Session valid")
                    return True
            except Exception:
                continue

        # If still on an account-looking URL, assume valid
        if any(x in current_url for x in ["tableau-de-bord", "compte", "profil"]):
            _logged_in = True
            return True

        _logged_in = False
        return False

    except Exception as exc:
        logger.warning(f"Session check error: {exc}")
        _logged_in = False
        return False


# ── Auto-reconnect with failure tracking ─────────────────────────────────────

async def ensure_logged_in(page: Page, context: BrowserContext) -> bool:
    """
    Guarantee an authenticated session before any scrape or apply action.

    1. If the session is currently blocked (3 consecutive failures), return False
       until the 30-minute cooldown expires.
    2. Navigate to the dashboard to verify the session.
    3. If valid → reset failure counter, return True.
    4. If invalid → attempt re-login up to 3 times (5 s / 10 s back-off).
    5. After 3 consecutive failed logins:
       - Suspend auto-apply (return False)
       - Write alert to logs/app.log
       - Send e-mail alert if SMTP is configured
       - Block for 30 minutes before next attempt
    6. Save storageState to session.json after every successful login.
    """
    global _logged_in, _last_login, _consecutive_failures, _blocked_until

    # ── Block check ──────────────────────────────────────────────────────────
    if _blocked_until:
        blocked_dt = datetime.fromisoformat(_blocked_until)
        now        = datetime.now(timezone.utc)
        if now < blocked_dt:
            remaining = int((blocked_dt - now).total_seconds() / 60)
            logger.warning(
                f"Session blocked for ~{remaining} more min "
                f"({_consecutive_failures} consecutive login failures)."
            )
            return False
        # Block expired
        logger.info("Login block expired — resetting failure counter")
        _consecutive_failures = 0
        _blocked_until        = None

    # ── Session check ────────────────────────────────────────────────────────
    if await check_session(page):
        _consecutive_failures = 0
        return True

    # ── Re-login attempts ────────────────────────────────────────────────────
    logger.info("Session invalid — attempting re-login")
    for attempt in range(1, 4):
        try:
            logger.info(f"Login attempt {attempt}/3")
            await login(page)

            if await check_session(page):
                _last_login           = datetime.now(timezone.utc).isoformat()
                _consecutive_failures = 0
                _logged_in            = True

                # Persist storage state to session.json as a backup snapshot
                try:
                    await context.storage_state(path=SESSION_FILE)
                    logger.info(f"storageState saved to {SESSION_FILE}")
                except Exception as exc:
                    logger.warning(f"Could not save session.json: {exc}")

                logger.info("Re-login successful")
                return True
            else:
                logger.warning(f"Attempt {attempt}: form submitted but session still invalid")

        except Exception as exc:
            logger.error(f"Login attempt {attempt} raised: {exc}")

        if attempt < 3:
            await asyncio.sleep(5 * attempt)    # 5 s after attempt 1, 10 s after attempt 2

    # ── All 3 attempts failed ────────────────────────────────────────────────
    _consecutive_failures += 1
    _logged_in             = False
    logger.error(f"All login attempts failed (consecutive failures: {_consecutive_failures})")

    if _consecutive_failures >= 3:
        _blocked_until = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        unblock_at     = datetime.fromisoformat(_blocked_until).strftime("%Y-%m-%d %H:%M UTC")
        await _send_alert(
            subject="[HelloWork Bot] Login failed — auto-apply suspended",
            body=(
                f"The HelloWork automation bot failed to log in {_consecutive_failures} "
                f"consecutive times.\n\n"
                f"Auto-apply has been suspended for 30 minutes (until {unblock_at}).\n\n"
                f"Please check:\n"
                f"  • HELLOWORK_EMAIL and HELLOWORK_PASSWORD in your .env file\n"
                f"  • Whether HelloWork is showing a CAPTCHA or account lockout\n"
                f"  • Network connectivity from the server\n\n"
                f"The bot will automatically retry after {unblock_at}."
            ),
        )

    return False
