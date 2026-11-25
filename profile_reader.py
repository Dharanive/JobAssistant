"""
profile_reader.py – Scrape skills & designation from your Naukri profile
=========================================================================
Opens the Naukri profile page (must already be logged in) and extracts:
  • Key Skills  → used as both keywords AND include_words in config.yaml
  • Current designation / headline → used as an additional keyword
  • Experience (years) → written to experience_years in config.yaml

Then rewrites config.yaml in-place, preserving all other settings.

The scraper tries multiple selector strategies in order and falls back
gracefully – if a section can't be found, it keeps the existing value.

Usage (programmatic, called from main.py sync command):
    from profile_reader import read_profile_and_sync_config
    summary = read_profile_and_sync_config(page, cfg)
    print(summary)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import yaml
from playwright.sync_api import Page

import naukri_selectors as SEL
from utils import human_delay, screenshot_on_failure

logger = logging.getLogger(__name__)

PROFILE_URL  = "https://www.naukri.com/mnjuser/profile"
CONFIG_PATH  = Path(__file__).parent / "config.yaml"

# ---------------------------------------------------------------------------
# Common skill/tech stop-words to exclude from keywords
# (these appear in profile sections but are too generic to be useful queries)
# ---------------------------------------------------------------------------
_STOP_SKILLS = {
    "ms office", "microsoft office", "excel", "powerpoint", "word",
    "communication", "teamwork", "leadership", "management", "english",
    "hindi", "presentation", "analytical", "problem solving",
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def read_profile_and_sync_config(page: Page, cfg: dict) -> dict:
    """
    Navigate to the Naukri profile page, extract skills/designation/experience,
    and write them back into config.yaml.

    Args:
        page: Playwright Page (already logged in).
        cfg:  Currently loaded config dict (will be mutated and saved).

    Returns:
        dict with keys:
          skills (list[str]), designation (str|None),
          experience_years (int|None), config_path (str)
    """
    logger.info("Navigating to profile page to read skills…")
    if PROFILE_URL not in page.url:
        page.goto(PROFILE_URL, wait_until="domcontentloaded")
        human_delay(cfg, factor=0.5)

    try:
        page.locator(SEL.PROFILE_SKILL_CHIP).first.wait_for(
            state="visible", timeout=10_000
        )
    except Exception:
        pass

    result: dict = {
        "skills": [],
        "designation": None,
        "experience_years": None,
        "config_path": str(CONFIG_PATH),
    }

    # ── 1. Key Skills ──────────────────────────────────────────────────────
    skills = _extract_skills(page)
    result["skills"] = skills
    logger.info("Extracted %d skills: %s", len(skills), skills)

    # ── 2. Designation / headline ──────────────────────────────────────────
    designation = _extract_designation(page)
    result["designation"] = designation
    if designation:
        logger.info("Extracted designation: %r", designation)

    # ── 3. Experience ──────────────────────────────────────────────────────
    exp_years = _extract_experience(page)
    result["experience_years"] = exp_years
    if exp_years is not None:
        logger.info("Extracted experience: %d years", exp_years)

    # ── 4. Build keywords list ─────────────────────────────────────────────
    keywords = _build_keywords(skills, designation)
    logger.info("Will use keywords: %s", keywords)

    # ── 5. Rewrite config.yaml ─────────────────────────────────────────────
    _update_config(cfg, keywords=keywords, skills=skills, exp_years=exp_years)

    return result


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _extract_skills(page: Page) -> list[str]:
    """
    Try multiple selector strategies to pull Key Skills from the profile.
    Returns a deduplicated list of non-empty skill strings.
    """
    strategies = [
        SEL.PROFILE_SKILL_CHIP,       # span.chipText
        SEL.PROFILE_SKILL_CHIP_ALT,   # .skill-tags span
        # Text-based broad fallback: any element whose ancestor text says "Key Skills"
        "section:has(h2:has-text('Key Skills')) li",
        "div:has(h3:has-text('Key Skills')) span",
        # Naukri sometimes renders them as anchor tags
        "a.chip span",
        ".tags-container .tag-li span",
    ]

    for sel in strategies:
        try:
            els = page.locator(sel).all()
            if els:
                raw = [e.inner_text(timeout=2_000).strip() for e in els]
                cleaned = [s for s in raw if s and len(s) > 1]
                if cleaned:
                    logger.debug("Skills found via selector %r: %s", sel, cleaned)
                    return _dedupe(cleaned)
        except Exception as exc:
            logger.debug("Skill selector %r failed: %s", sel, exc)

    # Last resort: screenshot and warn
    logger.warning("Could not extract skills from profile page.")
    screenshot_on_failure(page, "profile_skills")
    return []


def _extract_designation(page: Page) -> Optional[str]:
    """Extract the current job title / designation from the profile summary."""
    strategies = [
        SEL.PROFILE_DESIGNATION,       # div.designation
        SEL.PROFILE_DESIGNATION_ALT,   # [class*='desig']
        SEL.PROFILE_HEADLINE,          # #lazyResumeHead .widgetCont
        "div.nameWrap + div",          # element right after name block
        ".profile-summary .title",
        SEL.PROFILE_HEADLINE_INPUT,    # textarea fallback
    ]

    for sel in strategies:
        try:
            el = page.locator(sel).first
            if el.count():
                tag = el.evaluate("e => e.tagName.toLowerCase()")
                text = (
                    el.input_value(timeout=2_000)
                    if tag in ("input", "textarea")
                    else el.inner_text(timeout=2_000)
                ).strip()
                if text and len(text) > 2:
                    # Truncate at first newline (headlines can be multi-line)
                    return text.splitlines()[0].strip()
        except Exception as exc:
            logger.debug("Designation selector %r failed: %s", sel, exc)

    return None


def _extract_experience(page: Page) -> Optional[int]:
    """
    Try to extract total experience in years.
    Naukri shows something like "3 Years 2 Months" or "3 Yrs 2 Mos".
    Returns the integer year part, or None if not found.
    """
    strategies = [
        SEL.PROFILE_EXPERIENCE,
        SEL.PROFILE_EXPERIENCE_ALT,
        "[class*='exp'] span",
        "div:has-text('Years') span",
    ]

    for sel in strategies:
        try:
            els = page.locator(sel).all()
            for el in els:
                text = el.inner_text(timeout=2_000).strip()
                m = re.search(r"(\d+)\s*(?:year|yr)", text, re.IGNORECASE)
                if m:
                    return int(m.group(1))
        except Exception as exc:
            logger.debug("Experience selector %r failed: %s", sel, exc)

    return None


# ---------------------------------------------------------------------------
# Keyword builder
# ---------------------------------------------------------------------------

def _build_keywords(skills: list[str], designation: Optional[str]) -> list[str]:
    """
    Construct a deduplicated keyword list suitable for Naukri search based on
    the user's headline and skills.
    """
    keywords: list[str] = []

    # 1. Extract distinct roles & key technologies from headline segments
    if designation:
        parts = re.split(r"[|•·\n]", designation)
        for part in parts:
            p = part.strip()
            # If it's a role or primary tech term
            if any(term in p.lower() for term in ["developer", "engineer", "frontend", "full stack", "fullstack", "react", "next", "ai"]):
                # Avoid long sentence fragments like "Building Scalable & High-Performance..."
                if not any(stop in p.lower() for stop in ["building", "scalable", "experience", "years", "exp"]):
                    clean = _normalise_keyword(p)
                    if clean and clean.lower() not in [k.lower() for k in keywords] and len(clean) < 30:
                        keywords.append(clean)
            if len(keywords) >= 4:
                break

    # 2. Add high-value skills as additional search queries
    for skill in skills:
        s_clean = _normalise_keyword(skill)
        if (
            s_clean
            and s_clean.lower() not in _STOP_SKILLS
            and len(s_clean) >= 3
            and s_clean.lower() not in [k.lower() for k in keywords]
        ):
            keywords.append(s_clean)
        if len(keywords) >= 6:
            break

    if not keywords:
        keywords = ["Frontend Developer", "React Developer", "Software Engineer"]

    return keywords


def _normalise_keyword(text: str) -> str:
    """Clean and title-case a keyword string."""
    # Remove trailing special chars, truncate at punctuation
    text = re.split(r"[|•·/\\]", text)[0].strip()
    text = re.sub(r"\s+", " ", text)
    return text.title() if text else ""


# ---------------------------------------------------------------------------
# Config writer
# ---------------------------------------------------------------------------

def _update_config(
    cfg: dict,
    keywords: list[str],
    skills: list[str],
    exp_years: Optional[int],
) -> None:
    """
    Rewrite config.yaml in-place, updating only the profile-derived fields.
    All other settings (delays, caps, headless, etc.) are preserved.
    """
    # Read raw YAML to preserve comments as much as possible
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            raw: dict = yaml.safe_load(fh) or {}
    else:
        raw = {}

    # Update derived fields
    raw["keywords"]       = keywords
    raw["locations"]      = ["Chennai"]          # fixed per user request
    raw["include_words"]  = [s.lower() for s in skills[:15] if len(s) >= 3]

    if exp_years is not None:
        raw["experience_years"] = exp_years

    # Preserve all other keys from currently-loaded cfg
    for key, val in cfg.items():
        if key not in ("keywords", "locations", "include_words", "experience_years"):
            raw.setdefault(key, val)

    # Write back
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        fh.write("# ── naukri-assistant / config.yaml  (auto-updated by sync)\n")
        fh.write("# Run `python main.py sync` to refresh from your Naukri profile.\n\n")
        yaml.dump(raw, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("config.yaml updated → keywords=%s  location=Chennai", keywords)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _dedupe(lst: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in lst:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out
