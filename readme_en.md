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

# 3. Edit secrets/.env
#    TELEGRAM_TOKEN=...
#    ADMIN_TELEGRAM_ID=...

# 4. Run the bot
uv run main.py
```

> Get your bot token from [@BotFather](https://t.me/BotFather) and your Telegram ID from [@userinfobot](https://t.me/userinfobot).

## Developer Setup

```bash
# Install with dev dependencies
uv sync --dev

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Run all tests
uv run pytest -v

# Run a single test file
uv run pytest tests/test_foo.py -v

# Secret scanning
uv run detect-secrets scan --baseline .secrets.baseline
```

Pre-commit hooks activate automatically on first setup. The `secrets/` and `data/` directories are in `.gitignore` — never commit them.

## Project Structure

```
main.py              # Entry point; polling + background loop
bot/
  handlers/          # Telegram command and callback handlers
  keyboards.py       # Inline keyboard templates
services/
  ninova/            # Ninova login and scraping
  sks/               # Dining menu
  ari24/             # News and events
common/
  config.py          # Environment variables and global settings
  session.py         # HTTP session pool
  cache_manager.py   # LRU + TTL cache
  background_tasks.py# Parallel user checking
```

## Release

Version bumps are not automatic on regular commits. Releases are triggered manually from GitHub Actions.

- Workflow: `.github/workflows/release.yml`
- Input: `patch` / `minor` / `major` or an explicit version number
- Output: `pyproject.toml` updated, git tag created, GitHub Release opened

## FAQ

**The bot won't start. What should I do?**
Check that `secrets/.env` exists and that `TELEGRAM_TOKEN` and `ADMIN_TELEGRAM_ID` are set correctly.

**How often are notifications sent?**
The default check interval is 5 minutes. Change it in seconds with the `CHECK_INTERVAL` environment variable.

**Where is my Ninova password stored?**
Passwords are stored in the `data/` directory using Fernet encryption. The key lives in `secrets/.encryption_key`.

**Can multiple users share the same bot?**
Yes. Each user connects their own Ninova account with `/start` and is tracked independently.

**I want to add a feature.**
Fork the repo, open a feature branch, write tests, and submit a PR. Code style is enforced by `ruff`.

## License

GPLv3. See [LICENCE](LICENCE) for details.
