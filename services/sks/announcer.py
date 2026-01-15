import json
import logging
import os
import time
from datetime import datetime

from common.config import DATA_DIR, load_all_users
from common.utils import send_telegram_message
from services.sks.scraper import get_meal_menu

logger = logging.getLogger("ninova.sks")
STATE_FILE = os.path.join(DATA_DIR, "sks_state.json")


def load_sks_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_sks_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)


def check_and_announce_sks_menu():
    """
    Checks if it's time (11:00 or 16:30) and sends the meal menu announcement.
    Only sends once per day per slot.
    """
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    # Target slots
    LUNCH_TIME = "11:00"
    DINNER_TIME = "16:30"

    state = load_sks_state()

    # Check if we should send lunch menu
    # If time >= 11:00 and lunch not sent today
    if (
        current_time >= LUNCH_TIME
        and state.get(f"{today}_lunch") is not True
        and current_time < "15:00"
    ):
        announce(today, "lunch")
        state[f"{today}_lunch"] = True
        save_sks_state(state)

    # Check if we should send dinner menu
    # If time >= 16:30 and dinner not sent today
    elif (
        current_time >= DINNER_TIME
        and state.get(f"{today}_dinner") is not True
        and current_time < "21:00"
    ):
        announce(today, "dinner")
        state[f"{today}_dinner"] = True
        save_sks_state(state)


def announce(date_str, slot):
    """
    Fetches the menu and broadcasts it to all registered users.
    """
    logger.info(f"Triggering SKS announcement for {date_str} {slot}")
    menu_html = get_meal_menu(meal_type=slot)

    if not menu_html:
        logger.warning("Could not fetch SKS menu for announcement.")
        return

    users = load_all_users()
    if not users:
        return

    logger.info(f"Broadcasting SKS menu to {len(users)} users.")
    for chat_id in users.keys():
        try:
            send_telegram_message(chat_id, menu_html)
            time.sleep(0.5)  # Avoid hitting Telegram rate limits
        except Exception as e:
            logger.error(f"Failed to send SKS menu to {chat_id}: {e}")
