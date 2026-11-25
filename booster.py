"""
booster.py – Naukri profile refresh ("search booster")
========================================================
Strategy
---------
  1. Ensure we are logged in (delegates to auth.py).
  2. Navigate to the profile page.
  3. Read the current resume headline.
  4. Toggle a trailing period (add if missing, remove if present) → Naukri
     treats this as a profile update and refreshes the "last updated" stamp.
  5. Save the headline.
  6. Optionally re-upload resume.pdf from the path in .env / config.

Why headline toggling?
  Naukri's "profile completeness" tracker notices the edit and bumps the
  "last active" date that recruiters see, which improves search ranking.
  Editing the headline is the least intrusive change – it won't affect
  applications or recommendations.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import BrowserContext, Page

import naukri_selectors as SEL
from utils import human_delay, screenshot_on_failure, retry_with_backoff

logger = logging.getLogger(__name__)

PROFILE_URL = "https://www.naukri.com/mnjuser/profile"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_boost(
    context: BrowserContext,
    page: Page,
    cfg: dict,
    *,
    upload_resume: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Perform the profile boost.

    Args:
        context:        Active BrowserContext (already logged in).
        page:           Page object (may already be on profile URL).
        cfg:            Parsed config.yaml dict.
        upload_resume:  If True, re-upload the resume PDF.
        dry_run:        If True, navigate and read but do NOT save changes.

    Returns:
        dict with keys: success (bool), message (str), last_updated (str|None).
    """
    result: dict = {"success": False, "message": "", "last_updated": None}

    def _do() -> dict:
        return _boost(page, cfg, upload_resume=upload_resume, dry_run=dry_run)

    try:
        result = retry_with_backoff(
            _do,
            max_retries=cfg.get("max_retries", 3),
            backoff_base=cfg.get("retry_backoff_base_s", 5),
            on_failure=lambda e, _: screenshot_on_failure(page, "boost"),
        )
    except Exception as exc:
        result["message"] = str(exc)
        logger.error("Boost failed after retries: %s", exc)

    return result


# ---------------------------------------------------------------------------
# Internal logic
# ---------------------------------------------------------------------------

def _boost(
    page: Page,
    cfg: dict,
    *,
    upload_resume: bool,
    dry_run: bool,
) -> dict:
    """Core boost logic (single attempt)."""
    # Navigate to profile
    if PROFILE_URL not in page.url:
        page.goto(PROFILE_URL, wait_until="domcontentloaded")
        human_delay(cfg, factor=0.5)

    try:
        page.locator(SEL.PROFILE_HEADLINE_CONTAINER).first.wait_for(
            state="attached", timeout=10_000
        )
    except Exception:
        pass

    # Ensure headline section is scrolled into view
    head_sec = page.locator(SEL.PROFILE_HEADLINE_CONTAINER).first
    if head_sec.count():
        head_sec.scroll_into_view_if_needed()
        human_delay(cfg, factor=0.2)

    # Click edit button to reveal textarea if not already visible
    headline_loc = page.locator(SEL.RESUME_HEADLINE_FIELD).first
    if not headline_loc.is_visible():
        edit_btn = page.locator(SEL.RESUME_HEADLINE_EDIT_BTN).first
        if edit_btn.count():
            edit_btn.click()
            human_delay(cfg, factor=0.3)

    headline_loc.wait_for(state="visible", timeout=15_000)
    current_text: str = headline_loc.input_value() or ""

    # Toggle trailing period
    if current_text.endswith("."):
        new_text = current_text[:-1]
        action = "removed trailing period"
    else:
        new_text = current_text + "."
        action = "added trailing period"

    logger.info("Headline toggle: %s", action)
    logger.debug("Old headline: [redacted for log brevity]")

    if dry_run:
        logger.info("[DRY-RUN] Would save new headline (not saving).")
        # Cancel / dismiss modal so state is untouched
        cancel_btn = page.locator(SEL.RESUME_HEADLINE_CANCEL_BTN).first
        if cancel_btn.count() and cancel_btn.is_visible():
            cancel_btn.click()
        return {"success": True, "message": f"dry-run: {action}", "last_updated": None}

    # Clear and type new headline
    headline_loc.click()
    headline_loc.fill(new_text)
    human_delay(cfg, factor=0.3)

    # Save
    _click_save(page, cfg)

    # Read updated timestamp (best-effort)
    last_updated = _read_last_updated(page)

    # Optional resume upload
    if upload_resume:
        _upload_resume(page, cfg)

    return {
        "success": True,
        "message": f"Profile refreshed ({action})",
        "last_updated": last_updated,
    }


def _click_save(page: Page, cfg: dict) -> None:
    """Find and click the Save button near the headline section."""
    save_btn = page.locator(SEL.RESUME_HEADLINE_SAVE_BTN).filter(has_text="Save").first
    if save_btn.count() and save_btn.is_visible():
        save_btn.click()
    else:
        save_btns = page.get_by_role("button", name="Save")
        if save_btns.count() and save_btns.first.is_visible():
            save_btns.first.click()
        else:
            page.locator("button:has-text('Save')").first.click()

    human_delay(cfg, factor=0.5)
    logger.info("Save button clicked.")


def _read_last_updated(page: Page) -> Optional[str]:
    """
    Try to read the 'last updated' text from the profile page.
    Returns the text if found, None otherwise.
    """
    try:
        # Naukri typically shows something like "Last updated: 25 Nov '25"
        el = page.locator("text=Last updated").first
        if el.count():
            return el.inner_text(timeout=5_000).strip()
    except Exception:
        pass
    return None


def _upload_resume(page: Page, cfg: dict) -> None:
    """
    Re-upload resume PDF.  Skips if the file doesn't exist.
    """
    import os
    resume_path = os.environ.get("RESUME_PATH", "./resume.pdf")
    resolved = Path(resume_path).resolve()

    if not resolved.exists():
        logger.warning("Resume file not found at %s – skipping upload.", resolved)
        return

    logger.info("Uploading resume from %s", resolved)

    # Click the "Update Resume" button to reveal the file input
    update_btn = page.get_by_text(SEL.RESUME_UPLOAD_BTN, exact=False).first
    if not update_btn.count():
        logger.warning("Update Resume button not found – skipping upload.")
        return

    update_btn.click()
    human_delay(cfg, factor=0.4)

    file_input = page.locator(SEL.RESUME_FILE_INPUT).first
    file_input.set_input_files(str(resolved))
    human_delay(cfg, factor=0.5)

    logger.info("Resume uploaded successfully.")
