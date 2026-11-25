"""
auth.py – Login and session management for Naukri.com
======================================================
Strategy
---------
1. Try to load a saved browser storage state (cookies + localStorage).
2. Navigate to a protected page; if we land there successfully, session is valid.
3. If the session is expired or missing, do a fresh login and save the new state.
4. Captcha / OTP: detected by page-content inspection.  We pause and ask the user
   to solve it in the visible browser window, then wait for them to press Enter.

NEVER log or print credentials.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright

import naukri_selectors as SEL

logger = logging.getLogger(__name__)

STORAGE_STATE_PATH = Path(__file__).parent / "storage_state.json"
NAUKRI_HOME        = "https://www.naukri.com"
LOGIN_URL          = "https://www.naukri.com/nlogin/login"
PROFILE_URL        = "https://www.naukri.com/mnjuser/profile"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_context(playwright: Playwright, cfg: dict) -> BrowserContext:
    """
    Launch Chromium and return a BrowserContext, loading saved session if
    available.

    Args:
        playwright: Active Playwright instance.
        cfg:        Parsed config.yaml dict.

    Returns:
        BrowserContext ready to use.
    """
    launch_opts: dict = {
        "headless": cfg.get("headless", False),
        "slow_mo": cfg.get("slow_mo_ms", 0),
        "args": ["--disable-blink-features=AutomationControlled"],
    }

    browser: Browser = playwright.chromium.launch(**launch_opts)

    ctx_opts: dict = {
        "viewport": {"width": 1280, "height": 800},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "locale": "en-IN",
        "timezone_id": "Asia/Kolkata",
    }

    if STORAGE_STATE_PATH.exists():
        ctx_opts["storage_state"] = str(STORAGE_STATE_PATH)
        logger.info("Loaded saved session from %s", STORAGE_STATE_PATH)

    context: BrowserContext = browser.new_context(**ctx_opts)
    context.set_default_timeout(30_000)
    return context


def ensure_logged_in(context: BrowserContext) -> Page:
    """
    Return a Page that is confirmed logged-in to Naukri.

    Reuses the saved session if valid; otherwise performs a fresh login.
    Blocks on captcha / OTP until the user resolves it manually.

    Args:
        context: Active BrowserContext.

    Returns:
        Page object (at the profile URL after successful login).

    Raises:
        RuntimeError: If login fails after the user manually resolves a
                      captcha/OTP.
    """
    page = context.new_page()
    _dismiss_cookie_banner(page)

    if _session_valid(page):
        logger.info("Existing session is valid; skipping login.")
        return page

    logger.info("Session invalid or missing; performing fresh login.")
    _do_login(page, context)
    return page


def save_session(context: BrowserContext) -> None:
    """Persist storage state so the next run can skip login."""
    context.storage_state(path=str(STORAGE_STATE_PATH))
    logger.info("Session saved to %s", STORAGE_STATE_PATH)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _session_valid(page: Page) -> bool:
    """Navigate to profile; return True if we are still logged in."""
    try:
        page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=20_000)
        # If redirected to login, session is dead
        if "nlogin" in page.url or "login" in page.url:
            return False
        return True
    except Exception as exc:
        logger.debug("Session check error: %s", exc)
        return False


def _do_login(page: Page, context: BrowserContext) -> None:
    """
    Perform a full username/password login.

    Reads credentials from environment variables only.
    """
    user = os.environ.get("NAUKRI_USER", "")
    pwd  = os.environ.get("NAUKRI_PASS", "")

    if not user or not pwd:
        raise RuntimeError(
            "NAUKRI_USER and NAUKRI_PASS must be set in .env (or environment)."
        )

    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    _dismiss_cookie_banner(page)

    # Fill email
    email_input = (
        page.get_by_label(SEL.LOGIN_EMAIL_LABEL).first
        if page.get_by_label(SEL.LOGIN_EMAIL_LABEL).count()
        else page.locator(SEL.LOGIN_EMAIL_INPUT).first
    )
    email_input.fill(user)

    # Fill password
    page.locator(SEL.LOGIN_PASSWORD_INPUT).fill(pwd)

    # Submit – exact=True avoids matching "Use OTP to Login" as well
    page.get_by_role("button", name=SEL.LOGIN_SUBMIT_BTN, exact=True).click()

    # Wait and check for captcha / OTP before success
    _wait_and_check_verification(page)

    # Confirm we are logged in now
    page.wait_for_url(lambda url: "nlogin" not in url, timeout=30_000)

    if "nlogin" in page.url:
        raise RuntimeError("Login failed – still on login page after submission.")

    save_session(context)
    logger.info("Login successful.")


def _wait_and_check_verification(page: Page, timeout_ms: int = 15_000) -> None:
    """
    Poll page content for captcha / OTP indicators.
    If found, block and prompt the user to solve it manually.
    """
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        content = page.content().lower()

        for phrase in SEL.CAPTCHA_INDICATORS:
            if phrase in content:
                _pause_for_manual_resolution("CAPTCHA", page)
                return

        for phrase in SEL.OTP_INDICATORS:
            if phrase in content:
                _pause_for_manual_resolution("OTP / verification", page)
                return

        if "nlogin" not in page.url:
            return  # successfully navigated away

        time.sleep(0.5)


def _pause_for_manual_resolution(challenge_type: str, page: Page) -> None:  # noqa: ARG001
    """
    Halt automation and ask the user to solve the challenge in the browser.
    """
    banner = "=" * 70
    print(f"\n{banner}")
    print(f"  ⚠  {challenge_type.upper()} DETECTED")
    print("  Please solve it in the browser window, then press ENTER here.")
    print(banner)
    sys.stdin.readline()
    logger.info("User confirmed %s resolved; resuming automation.", challenge_type)


def _dismiss_cookie_banner(page: Page) -> None:
    """Click the cookie accept button if it appears (best-effort)."""
    try:
        btn = page.get_by_text(SEL.COOKIE_ACCEPT_BTN, exact=False)
        if btn.count():
            btn.first.click(timeout=3_000)
    except Exception:
        pass  # No banner – that's fine
