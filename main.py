"""
main.py – CLI entry point for naukri-assistant
===============================================
Usage
-----
  python main.py boost               # profile refresh only
  python main.py apply               # job search + apply
  python main.py both                # boost then apply
  python main.py sync                # read profile → auto-update config.yaml
  python main.py boost --dry-run     # simulate (no changes)
  python main.py apply --dry-run     # simulate (no Apply clicks)
  python main.py boost --upload-resume   # boost + re-upload resume.pdf

Flags
-----
  --dry-run          Don't make any writes / clicks that have side-effects
  --upload-resume    Re-upload the resume PDF during boost
  --headless         Override config.yaml: run without visible browser window
  --debug            Set log level to DEBUG
"""

from __future__ import annotations

import argparse
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

import auth
import db
import notifier
from booster import run_boost
from applier import run_apply
from profile_reader import read_profile_and_sync_config

# ── Load environment variables from .env  (never log credentials) ─────────
load_dotenv(Path(__file__).parent / ".env")

# ── Logging setup ─────────────────────────────────────────────────────────

def _setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    fmt   = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    logging.basicConfig(level=level, format=fmt, stream=sys.stdout)
    # Silence overly chatty libs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


logger = logging.getLogger("main")


# ── Config loader ─────────────────────────────────────────────────────────

def _load_config(headless_override: bool = False) -> dict:
    cfg_path = Path(__file__).parent / "config.yaml"
    if not cfg_path.exists():
        logger.error("config.yaml not found at %s", cfg_path)
        sys.exit(1)
    with open(cfg_path, encoding="utf-8") as fh:
        cfg: dict = yaml.safe_load(fh) or {}
    if headless_override:
        cfg["headless"] = True
    return cfg


# ── Mode handlers ─────────────────────────────────────────────────────────

def cmd_boost(args: argparse.Namespace, cfg: dict) -> int:
    """Run the profile booster.  Returns exit code."""
    run_id = db.run_start("boost")
    logger.info("▶ Starting BOOST run (dry_run=%s)", args.dry_run)

    with sync_playwright() as pw:
        context = auth.get_context(pw, cfg)
        try:
            page = auth.ensure_logged_in(context)
            result = run_boost(
                context, page, cfg,
                upload_resume=getattr(args, "upload_resume", False),
                dry_run=args.dry_run,
            )
        finally:
            auth.save_session(context)
            context.browser.close()

    if result["success"]:
        logger.info("✅ Boost successful: %s", result["message"])
        if result.get("last_updated"):
            logger.info("Last updated: %s", result["last_updated"])
        db.run_end(run_id, applied=0, skipped=0, status="ok", notes=result["message"])
        notifier.notify_boost_success(result.get("last_updated"))
        return 0
    else:
        logger.error("❌ Boost failed: %s", result["message"])
        db.run_end(run_id, applied=0, skipped=0, status="failed", notes=result["message"])
        notifier.notify_boost_failure(result["message"])
        return 1


def cmd_apply(args: argparse.Namespace, cfg: dict) -> int:
    """Run the auto-applier.  Returns exit code."""
    run_id = db.run_start("apply")
    logger.info("▶ Starting APPLY run (dry_run=%s)", args.dry_run)

    if args.dry_run:
        logger.info("[DRY-RUN] No real applications will be submitted.")

    with sync_playwright() as pw:
        context = auth.get_context(pw, cfg)
        try:
            page = auth.ensure_logged_in(context)
            result = run_apply(context, page, cfg, dry_run=args.dry_run)
        finally:
            auth.save_session(context)
            context.browser.close()

    applied = result["applied"]
    skipped = result["skipped"]
    csv_path = result["csv_path"]

    logger.info("✅ Apply run done – applied: %d | skipped: %d", applied, skipped)
    logger.info("Report: %s", csv_path)

    db.run_end(run_id, applied=applied, skipped=skipped, status="ok")
    notifier.notify_apply_summary(applied, skipped, csv_path)
    return 0


def cmd_both(args: argparse.Namespace, cfg: dict) -> int:
    """Run boost then apply."""
    ec = cmd_boost(args, cfg)
    if ec != 0:
        logger.warning("Boost failed; continuing to apply anyway.")
    return cmd_apply(args, cfg)


def cmd_sync(args: argparse.Namespace, cfg: dict) -> int:
    """
    Read Key Skills, designation and experience from your Naukri profile,
    then auto-update config.yaml with those as keywords + include_words.
    Location is always set to Chennai.
    """
    logger.info("▶ Starting SYNC – reading profile from Naukri…")

    with sync_playwright() as pw:
        context = auth.get_context(pw, cfg)
        try:
            page = auth.ensure_logged_in(context)
            summary = read_profile_and_sync_config(page, cfg)
        finally:
            auth.save_session(context)
            context.browser.close()

    if summary["skills"]:
        logger.info("✅ Sync complete!")
        logger.info("  Skills found  : %s", ", ".join(summary["skills"]))
        logger.info("  Designation   : %s", summary["designation"] or "(not found)")
        logger.info("  Experience    : %s", f"{summary['experience_years']} yrs" if summary["experience_years"] else "(not found)")
        logger.info("  Location set  : Chennai")
        logger.info("  config.yaml   : %s", summary["config_path"])
        print("\n✅ config.yaml updated. Run `python main.py apply --dry-run` to preview.\n")
    else:
        logger.warning("⚠  No skills could be extracted from the profile page.")
        logger.warning("   Check debug/ for a screenshot.  You can set keywords manually in config.yaml.")

    return 0


# ── Argument parsing ──────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="naukri-assistant",
        description="Automate Naukri.com profile refresh and job applications.",
    )
    parser.add_argument(
        "mode",
        choices=["boost", "apply", "both", "sync"],
        help=(
            "What to run: 'boost' (profile refresh), 'apply' (search+apply), "
            "'both', or 'sync' (read Naukri profile → update config.yaml)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate actions without making any real changes or applications.",
    )
    parser.add_argument(
        "--upload-resume",
        action="store_true",
        help="(boost mode) Re-upload resume.pdf in addition to refreshing the headline.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Override config.yaml and run the browser in headless mode.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    _setup_logging(debug=args.debug)
    cfg = _load_config(headless_override=args.headless)

    logger.info("naukri-assistant started at %s (mode=%s)", datetime.now().isoformat(), args.mode)

    db.init_db()

    dispatch = {
        "boost": cmd_boost,
        "apply": cmd_apply,
        "both":  cmd_both,
        "sync":  cmd_sync,
    }

    try:
        exit_code = dispatch[args.mode](args, cfg)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        exit_code = 130
    except Exception:
        logger.error("Unhandled exception:\n%s", traceback.format_exc())
        exit_code = 1

    logger.info("naukri-assistant finished (exit=%d)", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
