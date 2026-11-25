"""
app.py – Web dashboard for naukri-assistant
=============================================
Flask server providing:
  • Dashboard with daily stats, run history, job tables
  • One-click Boost / Apply / Sync actions
  • Real-time log streaming via Server-Sent Events (SSE)
  • Config editor (read/write config.yaml)
  • Job history with CSV export

Usage:
  python app.py                  # starts on http://localhost:5000
  python app.py --port 8080      # custom port
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import queue
import sqlite3
import sys
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
)

# ── Project imports ─────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

import db

# ── Flask app ───────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.urandom(24)

# ── Shared state ────────────────────────────────────────────────────────────
# Queue-based log broadcasting for SSE
_log_queues: list[queue.Queue] = []
_log_lock = threading.Lock()

# Track running tasks
_running: dict[str, dict] = {}
_running_lock = threading.Lock()

CONFIG_PATH  = Path(__file__).parent / "config.yaml"
ANSWERS_PATH = Path(__file__).parent / "answers.yaml"
DB_PATH      = Path(__file__).parent / "naukri_assistant.db"


# ── Custom log handler that broadcasts to SSE clients ───────────────────────
class QueueLogHandler(logging.Handler):
    """Pushes log records to all connected SSE queues, filtering out internal HTTP logs."""

    def emit(self, record: logging.LogRecord) -> None:
        # Never broadcast internal HTTP server traffic to users
        msg_raw = record.getMessage()
        if record.name == "werkzeug" or "/api/" in msg_raw or "HTTP/1.1" in msg_raw:
            return

        msg = self.format(record)
        with _log_lock:
            dead: list[queue.Queue] = []
            for q in _log_queues:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                _log_queues.remove(q)


def _setup_queue_logging() -> None:
    handler = QueueLogHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    # Also add stdout so logs appear in terminal
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"))
        root.addHandler(sh)


_setup_queue_logging()
logger = logging.getLogger("app")


# ═══════════════════════════════════════════════════════════════════════════
# ROUTES — Pages
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    html_path = Path(__file__).parent / "templates" / "dashboard.html"
    return Response(html_path.read_text(encoding="utf-8"), mimetype="text/html")


@app.route("/dashboard")
def dashboard():
    html_path = Path(__file__).parent / "templates" / "dashboard.html"
    return Response(html_path.read_text(encoding="utf-8"), mimetype="text/html")


@app.route("/landing")
def landing():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return Response(html_path.read_text(encoding="utf-8"), mimetype="text/html")


@app.route("/api/connect", methods=["POST"])
def api_connect():
    """
    Accept Naukri credentials from the UI, persist them to .env,
    and attempt a session validation test.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password are required."}), 400

    env_path = Path(__file__).parent / ".env"

    # Read existing .env lines (keep any other vars)
    existing = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()

    existing["NAUKRI_USER"] = email
    existing["NAUKRI_PASS"] = password

    env_content = "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n"
    env_path.write_text(env_content, encoding="utf-8")

    # Clear cached Playwright session so the newly connected account logs in fresh
    storage_state = Path(__file__).parent / "storage_state.json"
    if storage_state.exists():
        try:
            storage_state.unlink()
            logger.info("Cleared previous storage_state.json for new account.")
        except OSError as exc:
            logger.warning("Could not remove storage_state.json: %s", exc)

    # Reload into current process environment
    os.environ["NAUKRI_USER"] = email
    os.environ["NAUKRI_PASS"] = password

    logger.info("Credentials updated via UI for user: %s", email[:5] + "***")
    return jsonify({"ok": True, "message": "Credentials saved and session reset."})


@app.route("/api/session-status")
def api_session_status():
    """Check if credentials are configured."""
    user = os.environ.get("NAUKRI_USER", "").strip()
    return jsonify({
        "configured": bool(user),
        "email": (user[:4] + "****@" + user.split("@")[-1]) if "@" in user else ""
    })


@app.route("/api/disconnect", methods=["POST"])
def api_disconnect():
    """Disconnect current account, clear credentials and browser storage state."""
    env_path = Path(__file__).parent / ".env"
    existing = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()

    existing.pop("NAUKRI_USER", None)
    existing.pop("NAUKRI_PASS", None)

    env_content = "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n"
    env_path.write_text(env_content, encoding="utf-8")

    os.environ.pop("NAUKRI_USER", None)
    os.environ.pop("NAUKRI_PASS", None)

    storage_state = Path(__file__).parent / "storage_state.json"
    if storage_state.exists():
        try:
            storage_state.unlink()
            logger.info("Removed storage_state.json on account disconnect.")
        except OSError as exc:
            logger.warning("Could not delete storage_state.json: %s", exc)

    logger.info("Account disconnected via dashboard.")
    return jsonify({"ok": True, "message": "Account disconnected successfully."})


# ═══════════════════════════════════════════════════════════════════════════
# ROUTES — API
# ═══════════════════════════════════════════════════════════════════════════

# ── Stats ──────────────────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    """Return dashboard statistics."""
    db.init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # Today's numbers
    applied_today = conn.execute(
        "SELECT COUNT(*) FROM applied_jobs WHERE applied_at LIKE ?", (f"{today}%",)
    ).fetchone()[0]
    skipped_today = conn.execute(
        "SELECT COUNT(*) FROM skipped_jobs WHERE skipped_at LIKE ?", (f"{today}%",)
    ).fetchone()[0]

    # All-time
    total_applied = conn.execute("SELECT COUNT(*) FROM applied_jobs").fetchone()[0]
    total_skipped = conn.execute("SELECT COUNT(*) FROM skipped_jobs").fetchone()[0]

    # Last 7 days chart data
    chart_labels = []
    chart_applied = []
    chart_skipped = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        chart_labels.append(d[-5:])  # MM-DD
        chart_applied.append(
            conn.execute("SELECT COUNT(*) FROM applied_jobs WHERE applied_at LIKE ?", (f"{d}%",)).fetchone()[0]
        )
        chart_skipped.append(
            conn.execute("SELECT COUNT(*) FROM skipped_jobs WHERE skipped_at LIKE ?", (f"{d}%",)).fetchone()[0]
        )

    # Recent runs
    runs = [
        dict(r) for r in conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT 10"
        ).fetchall()
    ]

    # Last boost time
    last_boost = conn.execute(
        "SELECT ended_at FROM runs WHERE mode='boost' AND status='ok' ORDER BY id DESC LIMIT 1"
    ).fetchone()

    conn.close()

    cfg = _load_config()
    max_day = int(cfg.get("max_applications_per_day", 20))

    return jsonify({
        "applied_today": applied_today,
        "skipped_today": skipped_today,
        "total_applied": total_applied,
        "total_skipped": total_skipped,
        "daily_cap": max_day,
        "daily_progress": min(100, int(applied_today / max_day * 100)) if max_day else 0,
        "chart": {"labels": chart_labels, "applied": chart_applied, "skipped": chart_skipped},
        "runs": runs,
        "last_boost": last_boost["ended_at"] if last_boost else None,
    })


# ── Job history ────────────────────────────────────────────────────────────

@app.route("/api/jobs")
def api_jobs():
    """Return applied and skipped jobs with optional filter."""
    db.init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    status_filter = request.args.get("status", "all")
    limit = int(request.args.get("limit", 50))

    rows = []
    if status_filter in ("all", "applied"):
        rows += [
            {**dict(r), "status": "applied", "reason": "", "timestamp": r["applied_at"]}
            for r in conn.execute(
                "SELECT * FROM applied_jobs ORDER BY applied_at DESC LIMIT ?", (limit,)
            ).fetchall()
        ]
    if status_filter in ("all", "skipped"):
        rows += [
            {**dict(r), "status": "skipped", "timestamp": r["skipped_at"]}
            for r in conn.execute(
                "SELECT * FROM skipped_jobs ORDER BY skipped_at DESC LIMIT ?", (limit,)
            ).fetchall()
        ]

    # Sort combined by timestamp desc
    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    conn.close()
    return jsonify(rows[:limit])


@app.route("/api/jobs/export")
def api_jobs_export():
    """Export job history as CSV download."""
    csv_path = db.export_csv()
    return send_file(str(csv_path), as_attachment=True, download_name=csv_path.name)


# ── Actions ────────────────────────────────────────────────────────────────

@app.route("/api/action/<mode>", methods=["POST"])
def api_action(mode: str):
    """
    Start a background action: boost, apply, sync, or both.
    Accepts JSON body: { "dry_run": bool }
    """
    if mode not in ("boost", "apply", "both", "sync"):
        return jsonify({"error": f"Unknown mode: {mode}"}), 400

    with _running_lock:
        if mode in _running and _running[mode].get("active"):
            return jsonify({"error": f"{mode} is already running"}), 409

    body = request.get_json(silent=True) or {}
    dry_run = body.get("dry_run", False)

    # Launch in background thread
    t = threading.Thread(
        target=_run_action, args=(mode, dry_run), daemon=True
    )
    with _running_lock:
        _running[mode] = {"active": True, "started": datetime.now().isoformat(), "dry_run": dry_run}
    t.start()

    return jsonify({"status": "started", "mode": mode, "dry_run": dry_run})


@app.route("/api/status")
def api_status():
    """Return which actions are currently running."""
    with _running_lock:
        return jsonify(_running)


# ── Config ─────────────────────────────────────────────────────────────────

@app.route("/api/config", methods=["GET"])
def api_config_get():
    return jsonify(_load_config())


@app.route("/api/config", methods=["POST"])
def api_config_save():
    """Save config.yaml from JSON body."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return jsonify({"status": "saved"})


@app.route("/api/answers", methods=["GET"])
def api_answers_get():
    if ANSWERS_PATH.exists():
        with open(ANSWERS_PATH, encoding="utf-8") as fh:
            return jsonify(yaml.safe_load(fh) or {})
    return jsonify({})


@app.route("/api/answers", methods=["POST"])
def api_answers_save():
    data = request.get_json()
    with open(ANSWERS_PATH, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return jsonify({"status": "saved"})


# ── SSE log stream ─────────────────────────────────────────────────────────

@app.route("/api/logs/stream")
def api_logs_stream():
    """Server-Sent Events endpoint for real-time log tailing."""
    def generate():
        q: queue.Queue = queue.Queue(maxsize=200)
        with _log_lock:
            _log_queues.append(q)
        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield f"data: {json.dumps({'log': msg})}\n\n"
                except queue.Empty:
                    yield f"data: {json.dumps({'heartbeat': True})}\n\n"
        except GeneratorExit:
            with _log_lock:
                if q in _log_queues:
                    _log_queues.remove(q)

    return Response(generate(), mimetype="text/event-stream")


# ═══════════════════════════════════════════════════════════════════════════
# Background action runner
# ═══════════════════════════════════════════════════════════════════════════

def _run_action(mode: str, dry_run: bool) -> None:
    """Execute an action in a background thread."""
    try:
        from playwright.sync_api import sync_playwright
        import auth
        from booster import run_boost
        from applier import run_apply
        from profile_reader import read_profile_and_sync_config
        import notifier

        db.init_db()
        cfg = _load_config()

        logger.info("▶ Starting %s (dry_run=%s) from dashboard…", mode.upper(), dry_run)

        with sync_playwright() as pw:
            context = auth.get_context(pw, cfg)
            try:
                page = auth.ensure_logged_in(context)

                if mode == "boost" or mode == "both":
                    run_id = db.run_start("boost")
                    result = run_boost(context, page, cfg, dry_run=dry_run)
                    if result["success"]:
                        db.run_end(run_id, 0, 0, "ok", result["message"])
                        notifier.notify_boost_success(result.get("last_updated"))
                        logger.info("✅ Boost done: %s", result["message"])
                    else:
                        db.run_end(run_id, 0, 0, "failed", result["message"])
                        notifier.notify_boost_failure(result["message"])
                        logger.error("❌ Boost failed: %s", result["message"])

                if mode == "apply" or mode == "both":
                    run_id = db.run_start("apply")
                    result = run_apply(context, page, cfg, dry_run=dry_run)
                    db.run_end(run_id, result["applied"], result["skipped"], "ok")
                    notifier.notify_apply_summary(result["applied"], result["skipped"], result["csv_path"])
                    logger.info("✅ Apply done: applied=%d skipped=%d", result["applied"], result["skipped"])

                if mode == "sync":
                    summary = read_profile_and_sync_config(page, cfg)
                    logger.info(
                        "✅ Sync done: %d skills extracted, config updated.",
                        len(summary["skills"]),
                    )

            finally:
                auth.save_session(context)
                context.browser.close()

    except Exception as exc:
        logger.error("❌ Action %s failed: %s", mode, exc)
    finally:
        with _running_lock:
            if mode in _running:
                _running[mode]["active"] = False
                _running[mode]["ended"] = datetime.now().isoformat()


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    return {}


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Naukri Assistant Dashboard")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    db.init_db()
    logger.info("Dashboard starting at http://%s:%d", args.host, args.port)

    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
