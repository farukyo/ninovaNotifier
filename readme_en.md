# 🎓 Ninova Grade & Academic Tracking Bot

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)  [Türkçe Versiyon](README.md)

An academic assistant bot that monitors your grades, assignments, announcements, and course files on ITU Ninova in real-time and sends notifications via Telegram.

---

## ✨ Key Features

### 👥 User Management

- **Multi-User Support:** Multiple users can track their own academic data independently through a single bot instance.
- **Secure Authentication:** Your Ninova credentials are encrypted with AES-256 before being stored locally.
- **Session Management:** Caches user-based sessions to prevent unnecessary login traffic and avoid "too many requests" issues.

### 🔔 Smart Notification System

- **Instant Notifications:** Sends immediate alerts for new grades, announcements, assignments, or file updates.
- **Assignment Reminders:** Automatically sends "Last Call" notifications **24 hours** and **3 hours** before assignment deadlines.

### 📂 File and Content Access

- **Advanced File Explorer:** Supports complex and nested folder structures.
- **Direct Downloads:** Allows users to download course materials directly through Telegram.
- **Smart Search:** Enables keyword-based search within saved announcements.

### 🤖 Automation and Interface

- **Auto Course Discovery:** Automatically finds and adds all your courses from Ninova using the `otoders` command.
- **Interactive Menus:** Provides quick navigation with user-friendly Reply and Inline keyboards.
- **Rich Terminal UI:** Displays live statistics and progress bars for admins via a `rich`-powered dashboard.

---

## 🛠 Technical Stack

The project is built with a modular structure using modern Python practices:

- **Language:** Python 3.14+
- **Bot Framework:** `pytelegrambotapi` (Async-ready usage)
- **Scraping Engine:** `requests` & `BeautifulSoup4`
- **Security:** `cryptography` (Fernet)
- **UI/UX:** `rich` (Terminal Dashboard)
- **Package Manager:** `uv`

### Project Structure

```text
├── main.py              # Application entry point and Dashboard
├── bot/                 # Telegram bot logic
│   ├── handlers/        # Command and callback handlers
│   └── keyboards.py     # Keyboard interfaces
├── services/            # Core services
│   └── ninova/          # Ninova scraping and auth logic
├── common/              # Common configs and utilities
├── data/                # Data storage (JSON based)
└── logs/                # System logs
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
