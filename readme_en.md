# 🎓 Ninova Grade & Academic Tracking Bot

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html) [![CI](https://github.com/farukyo/ninovaNotifier/actions/workflows/ci.yml/badge.svg)](https://github.com/farukyo/ninovaNotifier/actions) [Türkçe Versiyon](README.md)

An academic assistant bot that monitors your grades, assignments, announcements, and course files on ITU Ninova in real-time and sends notifications via Telegram.

---

## ✨ Key Features

### 👥 User Management

- **Multi-User Support:** Multiple users can track their own academic data independently through a single bot instance.
- **Secure Authentication:** Your Ninova credentials are encrypted with AES-256 before being stored locally.
- **Session Management:** Caches user-based sessions to prevent unnecessary login traffic and avoid "too many requests" issues.

### 📊 Advanced Grade Statistics

- **Class Analysis:** Automatically calculates class average and standard deviation for each course.
- **Data Coverage:** Indicates the percentage of data used for calculations to ensure accuracy.
- **📈 Performance Graph:** Visualizes your grades on a bell curve to show your position (Z-Score) relative to the class.

### 🔔 Smart Notification System

- **Instant Notifications:** Sends immediate alerts for new grades, announcements, assignments, or file updates.
- **Assignment Reminders:** Automatically sends "Last Call" notifications **24 hours** and **3 hours** before deadlines.

### 📂 File and Content Access

- **Advanced File Explorer:** Supports complex and nested folder structures.
- **Direct Downloads:** Allows users to download course materials directly via Telegram.

### 🐝 Arı24 Integration

- **📰 News:** Stay updated with ITU news. Automatically sends a notification to **all users** when a new article is published.
- **📅 Events:** Discover all club events on campus and view upcoming events.
- **🔔 Club Subscription:** Subscribe to specific clubs to receive notifications only for their events.
- **☀️ Daily Bulletin:** Receive a summary of today's and next week's events every morning at 08:00.

### 🔔 Smart Notification System

- **Instant Notifications:** Sends immediate alerts for new grades, announcements, assignments, or file updates.
- **Assignment Reminders:** Automatically sends "Last Call" notifications **24 hours** and **3 hours** before deadlines.
- **Arı24 Notifications:** Instant alerts for news and subscribed club events.

### 📂 File and Content Access

- **Advanced File Explorer:** Supports complex and nested folder structures.
- **Direct Downloads:** Allows users to download course materials directly via Telegram.

### 🍴 Dining Hall Menu Announcements

- **Automatic Announcements:** Automatically shares the ITU SKS dining hall menu every day at **11:00** (Lunch) and **16:30** (Dinner).
- **Dynamic Data Fetching:** Fetches menu data directly via ITU BIBD API for up-to-date and clean data.
- **Smart State Management:** Ensures announcements are sent only once per day per meal.
- **🔄 Instant Update:** Update the current meal menu with a single button via Telegram.

---

## 🛠 Technical Stack

- **Language:** Python 3.14+
- **Bot Framework:** `pytelegrambotapi`
- **Scraping Engine:** `requests` & `BeautifulSoup4`
- **Security:** `cryptography` (Fernet)
- **Testing:** `pytest` & `pytest-cov`
- **Package Manager:** `uv`
- **Linting:** `ruff`

### Project Structure

```text
├── main.py                          # Application entry point and Dashboard
├── bot/
│   ├── instance.py                  # Bot instance and global variables
│   ├── keyboards.py                 # Reply keyboards
│   ├── utils.py                     # Bot utilities
│   └── handlers/
│       ├── admin/                   # Admin commands and callbacks
│       │   ├── commands.py
│       │   ├── callbacks.py
│       │   ├── course_management.py
│       │   ├── course_functions.py  # Course management helpers
│       │   └── ...
│       └── user/                    # User commands and callbacks
│           ├── commands.py          # Main import file
│           ├── auth_commands.py     # Username/password
│           ├── course_commands.py   # Course management
│           ├── grade_commands.py    # Grade/assignment listing
│           ├── general_commands.py  # Help, status, search
│           ├── ari24_commands.py    # Arı24 integration
│           └── callbacks.py         # Inline callback handlers
├── services/
│   ├── ninova/                      # Ninova scraping services
│   │   ├── auth.py
│   │   ├── scraper.py
│   │   ├── scanner.py
│   │   └── file_utils.py
│   ├── sks/                         # Dining hall menu service
│   │   ├── scraper.py
│   │   └── announcer.py
│   ├── ari24/                       # Arı24 service
│   │   └── client.py
│   └── calendar/                    # Academic calendar
├── common/
│   ├── config.py                    # Configuration and constants
│   ├── cache.py                     # File caching
│   └── utils.py                     # General utilities
├── tests/                           # Unit and integration tests
└── .github/workflows/ci.yml         # GitHub Actions CI
```

---

## 🚀 Setup and Execution

### 1. Prerequisites

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) package manager

### 2. Install Dependencies

```bash
uv sync
```

### 3. Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Required variables:
- `TELEGRAM_TOKEN`: Your API token from BotFather
- `ADMIN_ID`: Your Telegram Chat ID for administrative tasks

### 4. Run the Bot

```bash
uv run main.py
```

---

## 🧑‍💻 Developer Guide

### Development Environment Setup

```bash
# Install dependencies including dev tools
uv sync --dev

# Enable pre-commit hooks
uv run pre-commit install
```

### Code Quality Tools

```bash
# Linting
uv run ruff check .

# Auto-fix issues
uv run ruff check . --fix

# Formatting
uv run ruff format .
```

### Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Coverage report
uv run pytest tests/ --cov=. --cov-report=html
```

### Pre-commit Hooks

The project has the following pre-commit hooks configured:

- **detect-secrets**: Secret detection (Token leaks etc.)
- **detect-private-key**: Private key detection

### Ruff Rules

Active lint rules (`pyproject.toml`):

| Code | Description |
|------|-------------|
| E, W | pycodestyle errors and warnings |
| F | pyflakes (unused imports, etc.) |
| I | isort (import sorting) |
| B | flake8-bugbear (common bug patterns) |
| C4 | flake8-comprehensions |
| UP | pyupgrade (Python modernization) |
| RET | flake8-return |
| ARG | flake8-unused-arguments |

### CI/CD

GitHub Actions automatically runs on every push and PR:
- Ruff lint check
- Ruff format check
- All pytest tests

---

## 🗺 Roadmap (TODO)

Planned future features and enhancements are tracked in the [TODO.md](TODO.md) file.

---

## 📄 License

This project is licensed under the GNU General Public License v3 (GPLv3). See the full license text in the `LICENCE` file.
