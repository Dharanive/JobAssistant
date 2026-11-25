"""
utils.py – Shared helpers for naukri-assistant
===============================================
  • human_delay     – randomised wait to mimic human pacing
  • screenshot_on_failure – save a debug screenshot
  • retry_with_backoff    – generic retry decorator/wrapper
  • build_search_url      – construct Naukri search URL from config
  • extract_job_id        – pull stable job ID from a Naukri URL
"""

from __future__ import annotations

import logging
import random
import time
from pathlib import Path
from typing import Callable, Optional, TypeVar
from urllib.parse import quote_plus

from playwright.sync_api import Page

logger = logging.getLogger(__name__)

DEBUG_DIR = Path(__file__).parent / "debug"
DEBUG_DIR.mkdir(exist_ok=True)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Delay
# ---------------------------------------------------------------------------

def human_delay(cfg: dict, factor: float = 1.0) -> None:
    """
    Sleep for a random duration within [min, max] seconds scaled by factor.

    Args:
        cfg:    Config dict with delay_between_actions.min / .max.
        factor: Multiply the bounds (e.g. 0.5 for a shorter wait).
    """
    d = cfg.get("delay_between_actions", {})
    lo = d.get("min", 4) * factor
    hi = d.get("max", 9) * factor
    secs = random.uniform(lo, hi)
    logger.debug("Sleeping %.1fs", secs)
    time.sleep(secs)


# ---------------------------------------------------------------------------
# Screenshots
# ---------------------------------------------------------------------------

def screenshot_on_failure(page: Page, label: str = "error") -> None:
    """Save a full-page screenshot to ./debug/ with a timestamped filename."""
    try:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path  = DEBUG_DIR / f"{label}_{stamp}.png"
        page.screenshot(path=str(path), full_page=True)
        logger.error("Screenshot saved → %s", path)
    except Exception as exc:
        logger.warning("Could not save screenshot: %s", exc)


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------

def retry_with_backoff(
    fn: Callable[[], T],
    *,
    max_retries: int = 3,
    backoff_base: float = 5.0,
    on_failure: Optional[Callable[[Exception, int], None]] = None,
) -> T:
    """
    Call fn() up to max_retries times with linear backoff on exception.

    Args:
        fn:           Zero-argument callable to retry.
        max_retries:  Total attempts (1 = no retries).
        backoff_base: Sleep backoff_base * attempt seconds between tries.
        on_failure:   Optional callback(exc, attempt) called on each failure.

    Returns:
        Return value of fn() on success.

    Raises:
        Last exception if all attempts fail.
    """
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if on_failure:
                on_failure(exc, attempt)
            if attempt < max_retries:
                sleep_s = backoff_base * attempt
                logger.warning(
                    "Attempt %d/%d failed (%s). Retrying in %.0fs…",
                    attempt, max_retries, exc, sleep_s,
                )
                time.sleep(sleep_s)
            else:
                logger.error("All %d attempts failed.", max_retries)
    raise last_exc


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------

NAUKRI_SEARCH_BASE = "https://www.naukri.com/{keywords}-jobs"

_EXPERIENCE_MAP: dict[int, str] = {
    0: "0", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5",
    6: "6", 7: "7", 8: "8", 9: "9", 10: "10",
}

_DAYS_MAP: dict[int, str] = {1: "1", 3: "3", 7: "7", 15: "15", 30: "30"}


def build_search_url(keyword: str, location: str, cfg: dict) -> str:
    """
    Build a Naukri job search URL from keyword, location, and config.

    Naukri uses a mix of path segments and query params.
    This builds the most reliable URL form for filtering.

    Args:
        keyword:  Job keyword, e.g. "python developer".
        location: Location string, e.g. "Bangalore".
        cfg:      Parsed config.yaml dict.

    Returns:
        Full URL string.
    """
    kw_slug = keyword.strip().lower().replace(" ", "-")
    loc_slug = location.strip().lower().replace(" ", "-")

    exp: int   = int(cfg.get("experience_years", 0))
    days: int  = int(cfg.get("posted_within_days", 3))
    sal: float = float(cfg.get("min_salary_lpa", 0) or 0)

    # Base path
    path = f"https://www.naukri.com/{kw_slug}-jobs-in-{loc_slug}"

    params: list[str] = []

    # Experience (yearsOfExperience)
    exp_str = _EXPERIENCE_MAP.get(min(exp, 10), str(exp))
    params.append(f"experience={exp_str}")

    # Posted within
    days_str = _DAYS_MAP.get(days, "3")
    params.append(f"jobAge={days_str}")

    # Salary
    if sal > 0:
        params.append(f"salary={int(sal)}")

    # Keyword (redundant but Naukri's backend uses it)
    params.append(f"k={quote_plus(keyword)}")
    params.append(f"l={quote_plus(location)}")

    url = path + ("?" + "&".join(params) if params else "")
    logger.debug("Built search URL: %s", url)
    return url


def extract_job_id(url: str) -> str:
    """
    Extract a stable job identifier from a Naukri job URL.

    Naukri URLs follow the pattern:
      https://www.naukri.com/job-listings-<title>-<company>-<loc>-<jobid>
    or:
      https://www.naukri.com/job-listings-…?src=…&sid=<jobid>

    Returns the last path segment or query param as a fallback.
    """
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(url)

    # Try path-based ID (last numeric segment)
    segments = parsed.path.rstrip("/").split("-")
    for seg in reversed(segments):
        if seg.isdigit():
            return seg

    # Fallback: sid query param
    qs = parse_qs(parsed.query)
    if "sid" in qs:
        return qs["sid"][0]

    # Last resort: hash the URL
    return str(abs(hash(url)))[:12]
