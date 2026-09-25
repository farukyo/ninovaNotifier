# Ninova Notifier

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)
[![CI](https://github.com/farukyo/ninovaNotifier/actions/workflows/ci.yml/badge.svg)](https://github.com/farukyo/ninovaNotifier/actions)
[Turkish](README.md)

A Telegram bot that tracks academic changes on ITU Ninova. Get instant notifications for grade, assignment, announcement, and file updates.

## Features

- Notifications for grade, assignment, announcement, and file changes
- Browse and download course files directly from Telegram
- Multi-user support — each user tracks their own account
- SKS dining menu and Arı24 news/events integration
- Admin panel: system status and resource usage

## Setup

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
# 1. Install dependencies
uv sync

# 2. Create the environment file
cp secrets/.env.example secrets/.env

# 3. Edit secrets/.env (see the variables below)

# 4. Run the bot
uv run main.py
```

> Get your bot token from [@BotFather](https://t.me/BotFather) and your Telegram ID from [@userinfobot](https://t.me/userinfobot).

### Environment variables (`secrets/.env`)

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_TOKEN` | Yes | Bot token from BotFather (`TOKEN` is also accepted). The bot refuses to start without it. |
| `ADMIN_TELEGRAM_ID` | No | Admin user ID. Use a comma-separated list for several admins: `111,222`. The admin panel only works for these users in a **private chat**. |
| `ENCRYPTION_KEY` | No | Fernet key used to encrypt Ninova passwords. If unset, `secrets/.encryption_key` is generated automatically. |

> ⚠️ **Back up the encryption key.** If `ENCRYPTION_KEY` or `secrets/.encryption_key` is lost, stored Ninova passwords can't be decrypted and every user has to log in again.

The check interval (5 min) is currently the `CHECK_INTERVAL` constant in `core/config.py`, not an environment variable.

## Developer Setup

```bash
# Install with dev dependencies
uv sync --dev

# Install git hooks (ruff + secret scanning run on every commit)
uv run pre-commit install

# Lint and format
uv run ruff check .
uv run ruff format .

# Run the tests (no real token or Ninova access needed)
uv run pytest -q

# Run a single test file
uv run pytest tests/test_storage.py -v

# Secret scanning (same as CI)
uv run detect-secrets-hook --baseline .secrets.baseline $(git ls-files)
```

The `secrets/` and `data/` directories are in `.gitignore` — never commit them.

## Project Structure

```
main.py                 # Entry point: Telegram polling thread + periodic check loop
                        # (grade/assignment/file/announcement diffing and notifications)
bot/
  instance.py           # TeleBot instance and global exception handler
  handlers/user/        # User commands and callbacks
  handlers/admin/       # Admin panel (broadcast, backup, logs, course management)
  keyboards/            # Reply/inline keyboards
  callback_parsing.py   # callback_data parsing, download button tokens
core/
  config.py             # Environment variables, encryption, constants
  storage.py            # Locked, atomic reads/writes of users.json / ninova_data.json
  http_client.py        # Per-user requests.Session pool
  error_tracker.py      # Counts consecutive Ninova errors, notifies admins/users
  scheduler.py          # Bounded background task queue
  ttl_cache.py          # Short-lived cache for external service results
  logger.py             # JSON log files, token redaction
services/
  ninova/               # Login (auth.py) and scraping (scraper.py)
  sks/                  # Dining menu and announcements
  ari24/                # Arı24 news/events/clubs
  rehber/               # ITU directory search
  calendar/             # Academic calendar
tests/                  # pytest tests
```

Files created at runtime (all in `.gitignore`):

| File | Contents |
|---|---|
| `data/users.json` | Users, encrypted Ninova passwords, followed courses |
| `data/ninova_data.json` | Last saved state of each course (used to detect changes) |
| `data/error_tracker.json`, `data/file_cache.json`, `data/*_state.json` | Error counters, Telegram file cache, Arı24/SKS/bulletin state |
| `logs/app_YYYY-MM-DD.log` | Daily JSON-lines logs (kept for 30 days) |

## CI/CD and Deploy

> ⚠️ **Every push to `main` goes to production.** Try PRs locally first.

`.github/workflows/ci.yml`:

1. **Lint:** ruff check, ruff format and secret scanning.
2. **Test:** pytest on Python 3.12 and 3.14.
3. **Patch bump & lock sync** (only on push to `main`): bumps the patch version, updates `uv.lock`, pushes a `chore(release): vX.Y.Z [skip ci]` commit and tag to `main`, and creates a GitHub Release.
4. **Deploy** (only on push to `main`, `production` environment): connects to the VPS over SSH and runs these steps:
   - Backs up `data/` and `secrets/` to `~/ninova-backups/` (the last 20 backups are kept).
   - Runs `git pull --ff-only`, `uv sync` and `pm2 restart ninova-bot`.
   - If the bot is not online after 20 seconds, or keeps restarting, it rolls back to the previous commit and fails the job.

The deploy job reads the repository secrets `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` and `VPS_APP_PATH`. To require approval before each deploy: **Settings → Environments → production → Required reviewers**.

For a minor/major version: **Actions → Release → Run workflow** (`.github/workflows/release.yml`). It runs the tests and creates a tag plus a GitHub Release. It does not deploy.

If you merge while the server is offline, the deploy job fails. Once the server is back, run:

```bash
cd <app directory> && git pull --ff-only origin main && ~/.local/bin/uv sync && pm2 restart ninova-bot
```

## FAQ

**The bot won't start. What should I do?**
Check that `secrets/.env` exists and that `TELEGRAM_TOKEN` is correct. Error details are in the daily log file under `logs/` and in `pm2 logs ninova-bot`.

**How often are notifications sent?**
The check loop runs about every 5 minutes. To reduce load on Ninova, assignment detail pages are refreshed less often: every 30 minutes for open assignments and once a day for past-due ones. They are refreshed right away when the assignment list changes (for example, when you submit).

**Where is my Ninova password stored?**
Encrypted with Fernet in `data/users.json`. The key is read from the `ENCRYPTION_KEY` environment variable or `secrets/.encryption_key`.

**Can multiple users share the same bot?**
Yes. Each user connects their own Ninova account with "🔐 Giriş Yap" and is tracked independently.

**Anything to watch out for when running locally?**
Two bots can't run with the same token at the same time (Telegram rejects one of them). If the server bot is running, use a separate test bot from BotFather for local testing.

**I want to add a feature.**
Fork the repo, open a feature branch, write tests, and submit a PR. Code style is enforced by `ruff`.

## License

GPLv3. See [LICENCE](LICENCE) for details.
