"""
notifier.py – Optional Telegram notifications
==============================================
Silently skips if TELEGRAM_TOKEN or TELEGRAM_CHAT_ID is not set.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return bool(os.getenv("TELEGRAM_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def send(message: str) -> None:
    """
    Send a Telegram message.  No-op when credentials are absent.

    Args:
        message: Plain text to send (Markdown not used to avoid escaping issues).
    """
    if not _enabled():
        return

    try:
        import urllib.request, urllib.parse, json  # noqa: E401

        token   = os.environ["TELEGRAM_TOKEN"]
        chat_id = os.environ["TELEGRAM_CHAT_ID"]
        url     = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
        req     = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                logger.warning("Telegram returned HTTP %s", resp.status)
    except Exception as exc:  # pragma: no cover
        logger.warning("Telegram notification failed: %s", exc)


def notify_boost_success(last_updated: Optional[str] = None) -> None:
    msg = "✅ Naukri profile refreshed successfully."
    if last_updated:
        msg += f"\nLast updated: {last_updated}"
    send(msg)


def notify_boost_failure(error: str) -> None:
    send(f"❌ Naukri profile boost FAILED.\nError: {error}")


def notify_apply_summary(applied: int, skipped: int, csv_path: str) -> None:
    send(
        f"📋 Naukri auto-apply run complete.\n"
        f"Applied: {applied}  |  Skipped: {skipped}\n"
        f"Report: {csv_path}"
    )
