# naukri-assistant

> Automates two daily tasks on **your own** Naukri.com account:
> 1. **Profile Boost** – refreshes the "last updated" timestamp to stay visible to recruiters.
> 2. **Search + Auto-Apply** – searches for jobs matching your filters and applies to native Naukri listings.

Built with Python 3.11+, Playwright (Chromium), and SQLite.

---

## Table of Contents
- [Project Structure](#project-structure)
- [Setup](#setup)
- [First-Run Login Flow](#first-run-login-flow)
- [Configuration](#configuration)
- [Usage](#usage)
- [Scheduling](#scheduling)
- [Telegram Notifications](#telegram-notifications)
- [Dry-Run Mode](#dry-run-mode)
- [Known Limitations](#known-limitations)
- [Updating Selectors](#updating-selectors)

---

## Project Structure

```
naukri-assistant/
├── .env.example          ← copy to .env and fill in credentials
├── .gitignore
├── config.yaml           ← search filters and settings
├── answers.yaml          ← (optional) answers to questionnaires
├── requirements.txt
├── selectors.py          ← ALL Naukri UI selectors, centralized here
├── auth.py               ← login, session persistence
├── booster.py            ← Feature 1: profile refresh
├── applier.py            ← Feature 2: search + apply
├── db.py                 ← SQLite layer (applied_jobs, skipped_jobs, runs)
├── notifier.py           ← optional Telegram notifications
├── utils.py              ← shared helpers (delay, retry, URL builder)
├── main.py               ← CLI entry point
├── schedule_windows.py   ← install/remove Windows Task Scheduler tasks
└── debug/                ← screenshots saved on failure (auto-created)
```

---

## Setup

### 1. Prerequisites

- Python 3.11 or newer
- pip

### 2. Install dependencies

```bash
cd naukri-assistant
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure credentials

```bash
# Windows
copy .env.example .env
notepad .env

# macOS / Linux
cp .env.example .env
nano .env
```

Fill in:
```
NAUKRI_USER=your_email@example.com
NAUKRI_PASS=your_password
```

> ⚠ **Never commit `.env` to Git.** It is already in `.gitignore`.

### 4. Edit config.yaml

Open `config.yaml` and adjust:
- `keywords`, `locations`, `experience_years`
- `include_words`, `exclude_words`
- `max_applications_per_run`, `max_applications_per_day`

---

## First-Run Login Flow

The first run will open a **visible browser window** and log in using your credentials.

```bash
python main.py boost
```

1. The browser opens Naukri's login page.
2. If a **CAPTCHA or OTP** appears, the script pauses and prints:
   ```
   ======================================================================
     ⚠  CAPTCHA DETECTED
     Please solve it in the browser window, then press ENTER here.
   ======================================================================
   ```
3. Solve it manually in the browser → press **Enter** in the terminal.
4. After a successful login, the session is saved to `storage_state.json`.

**All subsequent runs reuse the saved session** – no login required unless the session expires (typically 30 days).

---

## Configuration

### `config.yaml`

| Key | Type | Description |
|-----|------|-------------|
| `headless` | bool | `false` (recommended) = visible browser; `true` = background |
| `keywords` | list | Job search terms |
| `locations` | list | City names (e.g. `Bangalore`, `Remote`) |
| `experience_years` | int | Your total years of experience |
| `min_salary_lpa` | int | Minimum salary filter (0 = off) |
| `posted_within_days` | int | Only jobs posted in the last N days |
| `include_words` | list | At least one must appear in the description |
| `exclude_words` | list | Any match → job is skipped |
| `exclude_companies` | list | Company names to skip |
| `max_applications_per_run` | int | Hard cap per execution |
| `max_applications_per_day` | int | Hard daily cap (across all runs, enforced from DB) |
| `delay_between_actions.min/max` | float | Random delay range in seconds (default 4–9) |

### `answers.yaml` (optional)

Map common questionnaire labels to your answers. Keys are **lowercased substrings** (first match wins):

```yaml
notice_period: "30"
current_ctc: "10"
expected_ctc: "15"
relocation: "Yes"
```

Delete or leave empty to skip all questionnaires.

---

## Usage

```bash
# Profile refresh only
python main.py boost

# Job search + apply
python main.py apply

# Both (boost first, then apply)
python main.py both

# Dry run – simulates everything, never clicks Apply or saves changes
python main.py apply --dry-run
python main.py boost --dry-run

# Re-upload resume.pdf during boost
python main.py boost --upload-resume

# Run headless (overrides config.yaml)
python main.py boost --headless

# Verbose debug logging
python main.py apply --debug
```

### Reports

After each `apply` run, a CSV is auto-exported to the project directory:
```
report_20251125_091500.csv
```

Columns: `status`, `job_id`, `title`, `company`, `location`, `url`, `timestamp`

---

## Scheduling

### Windows Task Scheduler

```bash
cd naukri-assistant

# Install tasks (runs at 09:00 and 09:15 daily)
python schedule_windows.py

# Verify
schtasks /query /tn naukri-boost
schtasks /query /tn naukri-apply

# Remove tasks
python schedule_windows.py remove
```

To customise the schedule times, edit `TASKS` in `schedule_windows.py`.

> **Note:** The tasks run as your current user. If you lock the screen, they still run. For headless mode, set `headless: true` in `config.yaml` or add `--headless` to the task command.

### cron (Linux / macOS / WSL)

```bash
crontab -e
```

Add:
```cron
# Profile boost at 09:00
0  9 * * * cd /path/to/naukri-assistant && /path/to/python main.py boost >> logs/boost.log 2>&1

# Auto-apply at 09:15
15 9 * * * cd /path/to/naukri-assistant && /path/to/python main.py apply >> logs/apply.log 2>&1
```

Find your Python path:
```bash
which python3
```

> **Important (cron):** Headless mode is required when no display is available. Set `headless: true` in `config.yaml` or install a virtual display (`Xvfb`).

---

## Telegram Notifications

1. Create a bot with [@BotFather](https://t.me/BotFather) → copy the token.
2. Send a message to your bot, then get your chat ID from:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Add to `.env`:
   ```
   TELEGRAM_TOKEN=123456:ABCDEF...
   TELEGRAM_CHAT_ID=987654321
   ```

Notifications fire on:
- ✅ Boost success (with last-updated timestamp)
- ❌ Boost failure (with error message)
- 📋 Apply run summary (applied count, skipped count, CSV path)

Leave both env vars blank to disable.

---

## Dry-Run Mode

`--dry-run` lets you safely test the full pipeline without side-effects:

| Action | Normal | Dry-run |
|--------|--------|---------|
| Navigate to pages | ✅ | ✅ |
| Filter jobs | ✅ | ✅ |
| Click Apply | ✅ | ❌ |
| Save headline | ✅ | ❌ |
| Write to DB | skipped/applied | "dry_run" skipped |
| Export CSV | ✅ | ✅ |

```bash
python main.py both --dry-run
```

---

## Known Limitations

| Limitation | Workaround |
|------------|------------|
| **Selector drift** | Naukri updates its frontend often. See [Updating Selectors](#updating-selectors) below. |
| **Captcha / OTP** | Script pauses and waits for manual resolution. Cannot be automated (by design). |
| **External-apply jobs** | Skipped automatically (can't apply without leaving Naukri). |
| **Login session expiry** | Re-runs the full login flow; delete `storage_state.json` to force a fresh login. |
| **Multi-step applications** | Only single-click "Apply" jobs are supported. Multi-step flows are skipped. |
| **Bot detection / IP blocks** | Run headful, keep delays high, avoid running too frequently. Use a residential IP if blocked. |
| **Questionnaire accuracy** | The questionnaire matcher uses substring matching; may miss unusual question phrasing. |
| **No parallel tabs** | Sequential processing only – intentionally, to avoid detection. |

---

## Updating Selectors

All selectors live in a single file: [`selectors.py`](./selectors.py).  
Selectors marked `# FRAGILE` are most likely to break after a Naukri front-end update.

### Quick update workflow

1. Open Chrome DevTools on the broken page (F12).
2. Use **Inspect Element** (Ctrl+Shift+C) to click the target element.
3. Right-click the element in the Elements panel → **Copy → Copy selector**.
4. Paste the new selector into `selectors.py` and update the comment.
5. Run `python main.py boost --dry-run` to verify.

### Using Playwright's codegen for verification

```bash
# Opens a browser and records selectors as you click
playwright codegen https://www.naukri.com/mnjuser/profile
```

This shows you the most robust locator (role / text / aria) that Playwright suggests.

### Resilience tips

- Prefer `page.get_by_role("button", name="Save")` over CSS selectors.
- Prefer `page.get_by_label("Email ID")` over `input[placeholder*='Email']`.
- Use `data-*` attributes when available (more stable than generated class names).
- Add `# FRAGILE` comments to any CSS-class-based selector so they're easy to audit.

---

## Security Notes

- Credentials are **only** read from `.env` (never hardcoded, never logged).
- `.env` and `storage_state.json` are in `.gitignore`.
- The script will never attempt to bypass captcha, OTP, or any bot-detection challenge.
- Applications are gated by both per-run and per-day hard caps stored in SQLite.

---

## License

MIT – for personal use on your own account only.  
Automating actions on third-party sites may violate their Terms of Service. Use responsibly.
