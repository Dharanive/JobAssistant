"""
schedule_windows.py – Register naukri-assistant in Windows Task Scheduler
==========================================================================
Run this script ONCE (from a PowerShell / CMD with normal user rights) to
create two scheduled tasks:

  naukri-boost  → runs `python main.py boost` every day at 09:00
  naukri-apply  → runs `python main.py apply` every day at 09:15

Requirements
------------
  • Python must be on PATH  (or edit PYTHON_EXE below).
  • The .env file must already be configured.
  • Run from the naukri-assistant/ directory.

Usage
-----
  cd naukri-assistant
  python schedule_windows.py          # install tasks
  python schedule_windows.py remove   # remove tasks
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PYTHON_EXE   = sys.executable          # full path to current Python
PROJECT_DIR  = str(Path(__file__).parent.resolve())
MAIN_PY      = str(Path(__file__).parent / "main.py")
LOG_DIR      = str(Path(__file__).parent / "logs")

TASKS = [
    {
        "name":    "naukri-boost",
        "args":    "boost",
        "time":    "09:00",
        "comment": "Naukri daily profile refresh",
    },
    {
        "name":    "naukri-apply",
        "args":    "apply",
        "time":    "09:15",
        "comment": "Naukri daily auto-apply",
    },
]


def _schtasks_create(task: dict) -> None:
    """Register one Windows scheduled task."""
    cmd = [
        "schtasks", "/create",
        "/tn", task["name"],
        "/tr", f'"{PYTHON_EXE}" "{MAIN_PY}" {task["args"]}',
        "/sc", "DAILY",
        "/st", task["time"],
        "/f",                 # overwrite if exists
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  ✅ Created task: {task['name']}  @ {task['time']} daily")
    else:
        print(f"  ❌ Failed to create {task['name']}:\n{result.stderr}")


def _schtasks_remove(task_name: str) -> None:
    """Delete a Windows scheduled task."""
    cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  🗑  Removed task: {task_name}")
    else:
        print(f"  ⚠  Could not remove {task_name}: {result.stderr.strip()}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "install"

    if mode == "remove":
        print("Removing scheduled tasks…")
        for t in TASKS:
            _schtasks_remove(t["name"])
    else:
        print(f"Installing scheduled tasks (Python: {PYTHON_EXE}) …")
        Path(LOG_DIR).mkdir(exist_ok=True)
        for t in TASKS:
            _schtasks_create(t)
        print("\nTo check tasks:   schtasks /query /tn naukri-boost")
        print("To remove tasks:  python schedule_windows.py remove")


if __name__ == "__main__":
    main()
