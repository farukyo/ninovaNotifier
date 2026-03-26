# Ninova Notifier

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)
[![CI](https://github.com/farukyo/ninovaNotifier/actions/workflows/ci.yml/badge.svg)](https://github.com/farukyo/ninovaNotifier/actions)
[Turkish](README.md)

Ninova Notifier is a Telegram bot that tracks academic activity on ITU Ninova.
It regularly scans grades, assignments, announcements, and course files, then notifies users when something changes.

## What It Does

- Multi-user support: each user tracks their own Ninova account.
- Session-aware login flow: reduces unnecessary re-authentication.
- Update notifications: grade, assignment, file, and announcement changes.
- Course file access: browse and download files directly from Telegram.
- Admin statistics: runtime metrics and system overview from the admin panel.
- Extra modules: Arı24 news/events and SKS dining menu support.

## Tech Stack

- Python: 3.12+
- Bot framework: pytelegrambotapi
- HTTP/Scraping: requests, BeautifulSoup4
- Security: cryptography
- Data/utilities: sqlalchemy, numpy, scipy, matplotlib
- Package manager: uv
- Quality tooling: ruff, pytest, detect-secrets

## Quick Start

1. Install dependencies:

```bash
uv sync
```

2. Create environment file:

```bash
cp .env.example .env
```

PowerShell alternative:

```powershell
Copy-Item .env.example .env
```

3. Set at least these variables:

- TELEGRAM_TOKEN
- ADMIN_ID

4. Run the bot:

```bash
uv run main.py
```

## Developer Workflow

```bash
uv sync --dev
uv run ruff check .
uv run ruff format .
uv run pytest -v
```

## Release Flow

Version is not bumped on regular commits.
Releases are triggered manually from GitHub Actions.

- Workflow: .github/workflows/release.yml
- Inputs: patch/minor/major or an explicit version
- Output: pyproject.toml bump, git tag, GitHub Release

## Project Map

- Entry point: main.py
- Bot handlers: bot/handlers
- Services: services
- Shared utilities: common
- CI/CD workflows: .github/workflows

## License

This project is licensed under GPLv3. See LICENCE for details.
