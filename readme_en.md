# 🎓 Ninova Grade & Academic Tracking Bot

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)  [Türkçe Versiyon](README.md)

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

### 🔔 Smart Notification System

- **Instant Notifications:** Sends immediate alerts for new grades, announcements, assignments, or file updates.
- **Assignment Reminders:** Automatically sends "Last Call" notifications **24 hours** and **3 hours** before deadlines.

### 📂 File and Content Access

- **Advanced File Explorer:** Supports complex and nested folder structures.
- **Direct Downloads:** Allows users to download course materials directly via Telegram.

### 🤖 Automation and Developer Tools

- **Comprehensive Testing:** Over 90% test coverage using `pytest`.
- **Rich Terminal UI:** Displays live statistics and progress bars for admins via a dashboard.

---

## 🛠 Technical Stack

The project is built with a modular structure using modern Python practices:

- **Language:** Python 3.14+
- **Bot Framework:** `pytelegrambotapi` (Async-ready usage)
- **Scraping Engine:** `requests` & `BeautifulSoup4`
- **Security:** `cryptography` (Fernet)
- **Testing:** `pytest` & `pytest-cov`
- **Package Manager:** `uv`

### Project Structure

```text
├── main.py              # Application entry point and Dashboard
├── bot/                 # Telegram bot logic and handlers
├── services/            # Ninova scraping and authentication
├── common/              # Common utilities (encryption, cache, etc.)
├── scripts/             # Developer utilities (versioning script)
├── tests/               # Unit and integration tests
├── data/                # Data storage (JSON - ignored)
└── logs/                # System logs (ignored)
```

---

## 🚀 Setup and Execution

### 1. Prerequisites

You must have Python 3.14+ and [uv](https://github.com/astral-sh/uv) installed on your system.

### 2. Install Dependencies

```bash
uv sync
```

### 3. Configuration

Duplicate the `.env.example` file as `.env` and fill in the required information:

- `TELEGRAM_TOKEN`: Your API token from BotFather.
- `ADMIN_ID`: Your Telegram Chat ID for administrative tasks.

### 4. Run the Bot

To start the system:

```bash
uv run main.py
```

---

## 📄 License

This project is licensed under the GNU General Public License v3 (GPLv3). See the full license text in the `LICENCE` file.
