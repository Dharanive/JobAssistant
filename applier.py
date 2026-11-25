"""
applier.py – Search + auto-apply engine for Naukri.com
=======================================================
Flow
----
  For each (keyword × location) pair in config.yaml:
    1. Build the search URL and load it.
    2. Scroll / paginate through job cards.
    3. Filter each card:
         • already in DB → skip
         • title/desc contains exclude_words → skip
         • title/desc lacks include_words → skip
         • "Apply on company site" button → skip
         • daily cap reached → stop entirely
    4. Open each surviving job in the same tab (sequential, never parallel).
    5. Click Apply (native Naukri jobs only).
    6. Handle questionnaires if answers.yaml is present; else skip.
    7. Record outcome in SQLite.
  Export CSV report at the end of each run.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional

import yaml
from playwright.sync_api import BrowserContext, Page

import db
import naukri_selectors as SEL
from utils import (
    build_search_url,
    extract_job_id,
    human_delay,
    screenshot_on_failure,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)

ANSWERS_PATH = Path(__file__).parent / "answers.yaml"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_apply(
    context: BrowserContext,
    page: Page,
    cfg: dict,
    *,
    dry_run: bool = False,
) -> dict:
    """
    Execute the full search-and-apply workflow.

    Args:
        context:  Active BrowserContext.
        page:     Page (already logged in).
        cfg:      Parsed config.yaml.
        dry_run:  If True, never click Apply.

    Returns:
        dict with keys: applied (int), skipped (int), csv_path (str).
    """
    answers  = _load_answers()
    keywords = cfg.get("keywords", [])
    locs     = cfg.get("locations", [])
    max_run  = int(cfg.get("max_applications_per_run", 15))
    max_day  = int(cfg.get("max_applications_per_day", 20))

    applied_count = 0
    skipped_count = 0
    stop = False

    for keyword in keywords:
        if stop:
            break
        for location in locs:
            if stop:
                break
            logger.info("Searching: %r in %r", keyword, location)
            url = build_search_url(keyword, location, cfg)

            try:
                n_applied, n_skipped, stop = _process_search_page(
                    page,
                    cfg,
                    search_url=url,
                    keyword=keyword,
                    location=location,
                    answers=answers,
                    dry_run=dry_run,
                    applied_so_far=applied_count,
                    max_run=max_run,
                    max_day=max_day,
                )
                applied_count += n_applied
                skipped_count += n_skipped
            except Exception as exc:
                logger.error("Error processing %r/%r: %s", keyword, location, exc)
                screenshot_on_failure(page, f"apply_{keyword}_{location}")

    csv_path = db.export_csv()
    return {
        "applied": applied_count,
        "skipped": skipped_count,
        "csv_path": str(csv_path),
    }


# ---------------------------------------------------------------------------
# Search results processing
# ---------------------------------------------------------------------------

def _process_search_page(
    page: Page,
    cfg: dict,
    *,
    search_url: str,
    keyword: str,
    location: str,
    answers: dict,
    dry_run: bool,
    applied_so_far: int,
    max_run: int,
    max_day: int,
) -> tuple[int, int, bool]:
    """
    Load a search URL and iterate over all pages of results.

    Returns:
        (n_applied, n_skipped, should_stop)
    """
    page.goto(search_url, wait_until="domcontentloaded")
    human_delay(cfg, factor=0.6)

    applied = 0
    skipped = 0
    page_num = 1
    stop = False

    while True:
        logger.info("Processing search results page %d", page_num)

        try:
            page.locator(SEL.JOB_CARD_CONTAINER).first.wait_for(
                state="visible", timeout=10_000
            )
        except Exception:
            pass

        job_cards = page.locator(SEL.JOB_CARD_CONTAINER).all()
        if not job_cards:
            logger.info("No job cards found on page %d – ending pagination.", page_num)
            break

        cards_data = [c for c in (_extract_card_info(card) for card in job_cards) if c]

        for card_info in cards_data:
            if stop or applied_so_far + applied >= max_run:
                stop = True
                break

            # Check daily cap (re-read from DB each time to be accurate)
            if db.applications_today() >= max_day:
                logger.warning("Daily cap of %d reached – stopping.", max_day)
                stop = True
                break

            job_id    = card_info["job_id"]
            title     = card_info["title"]
            company   = card_info["company"]
            job_url   = card_info["url"]
            loc_text  = card_info["location"]

            # ── Filter: already in DB ──
            if db.already_applied(job_id):
                skipped += 1
                db.record_skipped(job_id, title, company, job_url, "already_applied")
                continue

            # ── Filter: title-level keyword filters ──
            skip_reason = _check_title_filters(title, company, cfg)
            if skip_reason:
                skipped += 1
                db.record_skipped(job_id, title, company, job_url, skip_reason)
                logger.debug("Skipped %r (%s): %s", title, company, skip_reason)
                continue

            # ── Open job page and do deeper checks ──
            outcome = _handle_one_job(
                page, cfg,
                job_id=job_id,
                title=title,
                company=company,
                location=loc_text,
                url=job_url,
                answers=answers,
                dry_run=dry_run,
            )

            if outcome == "applied":
                applied += 1
                applied_so_far += 1
            else:
                skipped += 1

        if stop:
            break

        # ── Paginate ──
        next_btn = page.locator(SEL.NEXT_PAGE_BTN).first
        if (
            not next_btn.count()
            or not next_btn.is_visible()
            or next_btn.get_attribute("disabled") is not None
            or next_btn.get_attribute("aria-disabled") == "true"
        ):
            logger.info("No active next-page button – reached last page.")
            break

        next_btn.click()
        human_delay(cfg, factor=0.8)
        page_num += 1

    return applied, skipped, stop


# ---------------------------------------------------------------------------
# Job card extraction
# ---------------------------------------------------------------------------

def _extract_card_info(card) -> Optional[dict]:
    """
    Pull title, company, url, and job_id from a job card locator.
    Returns None if extraction fails.
    """
    try:
        title_el = card.locator(SEL.JOB_CARD_TITLE).first
        title    = title_el.inner_text(timeout=3_000).strip()

        company_el = card.locator(SEL.JOB_CARD_COMPANY).first
        company    = company_el.inner_text(timeout=3_000).strip() if company_el.count() else ""

        link_el    = card.locator(SEL.JOB_CARD_LINK).first
        url        = link_el.get_attribute("href") or ""

        loc_el     = card.locator(SEL.JOB_CARD_LOCATION).first
        location   = loc_el.inner_text(timeout=2_000).strip() if loc_el.count() else ""

        job_id     = card.get_attribute("data-job-id") or extract_job_id(url)

        return {"title": title, "company": company, "url": url, "location": location, "job_id": job_id}
    except Exception as exc:
        logger.debug("Could not extract card info: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Title-level filter (fast, no page navigation)
# ---------------------------------------------------------------------------

def _check_title_filters(title: str, company: str, cfg: dict) -> Optional[str]:
    """
    Return a skip reason string if the job should be skipped based on title/company,
    or None if it passes.
    """
    title_lower   = title.lower()
    company_lower = company.lower()

    for word in cfg.get("exclude_words", []):
        if word.lower() in title_lower:
            return f"exclude_word:{word}"

    for co in cfg.get("exclude_companies", []):
        if co.lower() in company_lower:
            return f"exclude_company:{co}"

    return None


# ---------------------------------------------------------------------------
# Individual job handling
# ---------------------------------------------------------------------------

def _handle_one_job(
    search_page: Page,
    cfg: dict,
    *,
    job_id: str,
    title: str,
    company: str,
    location: str,
    url: str,
    answers: dict,
    dry_run: bool,
) -> str:
    """
    Open the job URL in a new sequential tab, run deep filters, attempt to apply,
    and close the tab before returning.

    Returns:
        "applied" | "skipped:<reason>" | "error"
    """
    job_page = search_page.context.new_page()
    try:
        job_page.goto(url, wait_until="domcontentloaded")
        human_delay(cfg, factor=0.6)

        # ── Deep filters ──
        skip_reason = _deep_filter(job_page, cfg)
        if skip_reason:
            db.record_skipped(job_id, title, company, url, skip_reason)
            logger.info("Skipped %r: %s", title, skip_reason)
            return f"skipped:{skip_reason}"

        # ── Dry run ──
        if dry_run:
            logger.info("[DRY-RUN] Would apply to: %r @ %s", title, company)
            db.record_skipped(job_id, title, company, url, "dry_run")
            return "skipped:dry_run"

        # ── Click Apply ──
        success = _click_apply(job_page, cfg, answers=answers)
        if success:
            db.record_applied(job_id, title, company, location, url)
            logger.info("✅ Applied: %r @ %s", title, company)
            return "applied"
        else:
            db.record_skipped(job_id, title, company, url, "apply_failed")
            return "skipped:apply_failed"

    except Exception as exc:
        logger.error("Error on job %r: %s", title, exc)
        screenshot_on_failure(job_page, f"job_{job_id}")
        db.record_skipped(job_id, title, company, url, f"error:{exc}")
        return "error"
    finally:
        job_page.close()


def _deep_filter(page: Page, cfg: dict) -> Optional[str]:
    """
    Run filters that require the job detail page to be loaded.

    Returns a skip reason string, or None if the job passes all filters.
    """
    # Check for external apply buttons
    page_text = page.inner_text("body").lower()

    for phrase in SEL.EXTERNAL_APPLY_INDICATOR:
        if phrase.lower() in page_text:
            return "external_apply"

    # Check include_words against full description
    include = [w.lower() for w in cfg.get("include_words", [])]
    if include and not any(w in page_text for w in include):
        return "missing_include_words"

    # Check exclude_words against full description
    for word in cfg.get("exclude_words", []):
        if word.lower() in page_text:
            return f"exclude_word_in_desc:{word}"

    return None


def _click_apply(page: Page, cfg: dict, answers: dict) -> bool:
    """
    Click the Apply button and handle post-click overlays.

    Returns True if application confirmed successful, False otherwise.
    """
    # Locate Apply button
    apply_btn = None
    if page.locator(SEL.APPLY_BTN_PRIMARY).count():
        apply_btn = page.locator(SEL.APPLY_BTN_PRIMARY).first
    else:
        candidates = page.get_by_role("button", name=SEL.APPLY_BTN_TEXT_FALLBACK)
        if candidates.count():
            apply_btn = candidates.first

    if apply_btn is None or not apply_btn.is_visible():
        logger.warning("Apply button not found or not visible.")
        return False

    apply_btn.click()
    human_delay(cfg, factor=0.5)

    # ── Post-click state ──

    # Success without any overlay
    if _check_success(page):
        return True

    # Questionnaire overlay
    if page.locator(SEL.QUESTIONNAIRE_OVERLAY).count():
        return _handle_questionnaire(page, cfg, answers)

    # Chatbot overlay
    if page.locator(SEL.CHATBOT_CONTAINER).count():
        logger.info("Chatbot/questionnaire detected – skipping (no answers configured).")
        _dismiss_overlay(page)
        return False

    # Wait a moment and check again
    human_delay(cfg, factor=0.3)
    return _check_success(page)


def _check_success(page: Page) -> bool:
    """Return True if any success signal is visible in the page."""
    page_text = page.inner_text("body").lower()
    return any(sig.lower() in page_text for sig in SEL.APPLY_SUCCESS_SIGNALS)


def _dismiss_overlay(page: Page) -> None:
    """Try to close any open overlay/modal."""
    try:
        close = page.locator(SEL.QUESTIONNAIRE_CLOSE_BTN).first
        if close.count() and close.is_visible():
            close.click()
    except Exception:
        pass


def _handle_questionnaire(page: Page, cfg: dict, answers: dict) -> bool:
    """
    Attempt to fill a questionnaire overlay using answers.yaml mappings.

    If answers dict is empty, dismisses and returns False.

    Args:
        page:    Current page (overlay is visible).
        cfg:     Config dict.
        answers: Dict loaded from answers.yaml.

    Returns:
        True if successfully submitted, False if skipped.
    """
    if not answers:
        logger.info("Questionnaire detected but no answers.yaml – skipping.")
        _dismiss_overlay(page)
        return False

    overlay = page.locator(SEL.QUESTIONNAIRE_OVERLAY).first

    # Find all question labels + inputs within the overlay
    questions = overlay.locator("label").all()
    filled_any = False

    for q_label in questions:
        try:
            label_text = q_label.inner_text(timeout=2_000).strip().lower()
            matched_answer = _match_answer(label_text, answers)

            if matched_answer is None:
                continue

            # Find the associated input / textarea / select
            # Try: next sibling input, or input with same 'for' attribute
            q_input = overlay.locator("input, textarea, select").first  # crude fallback
            if q_input.count():
                tag = q_input.evaluate("el => el.tagName.toLowerCase()")
                if tag in ("input", "textarea"):
                    q_input.fill(str(matched_answer))
                elif tag == "select":
                    q_input.select_option(value=str(matched_answer))
                filled_any = True
                human_delay(cfg, factor=0.1)

        except Exception as exc:
            logger.debug("Questionnaire field error: %s", exc)

    if not filled_any:
        logger.info("Could not fill any questionnaire fields – skipping job.")
        _dismiss_overlay(page)
        return False

    # Submit the questionnaire
    try:
        submit = overlay.get_by_role("button", name="Submit").first
        if not submit.count():
            submit = overlay.locator("button[type='submit']").first
        if submit.count():
            submit.click()
            human_delay(cfg, factor=0.4)
            return _check_success(page)
    except Exception as exc:
        logger.warning("Questionnaire submit error: %s", exc)

    _dismiss_overlay(page)
    return False


def _match_answer(label_text: str, answers: dict) -> Optional[str]:
    """
    Return the best-matching answer for a question label, or None.

    Matching is substring-based (first match wins).
    """
    for key, value in answers.items():
        if key.lower() in label_text:
            return str(value)
    return None


# ---------------------------------------------------------------------------
# Answers loader
# ---------------------------------------------------------------------------

def _load_answers() -> dict:
    """Load answers.yaml if it exists; return empty dict otherwise."""
    if not ANSWERS_PATH.exists():
        return {}
    with open(ANSWERS_PATH, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    logger.info("Loaded %d answer mappings from answers.yaml", len(data))
    return data
