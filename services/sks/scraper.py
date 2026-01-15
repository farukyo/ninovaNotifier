import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from common.config import HEADERS

logger = logging.getLogger("ninova.sks")

# Direct source URLs for lunch and dinner
# Lunch: itu-ogle-yemegi-genel
# Dinner: itu-aksam-yemegi-genel
SKS_API_URL = (
    "https://bidb.itu.edu.tr/ExternalPages/sks/yemek-menu-v2/uzerinde-calisilan/yemek-menu.aspx"
)


def get_meal_menu(meal_type="lunch"):
    """
    Fetches the daily meal menu from ITU SKS direct endpoint.
    :param meal_type: "lunch" or "dinner"
    :return: Formatted HTML string or None if failed.
    """
    try:
        # Construct params
        tip = "itu-ogle-yemegi-genel" if meal_type == "lunch" else "itu-aksam-yemegi-genel"
        today_str = datetime.now().strftime("%d.%m.%Y")

        params = {"tip": tip, "value": today_str}

        response = requests.get(SKS_API_URL, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # The endpoint returns a direct HTML fragment with table rows
        menu_items = []

        # Look for the main menu table
        table = soup.find("table")
        if not table:
            return None

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                # Category is usually in the first cell
                category = cells[0].get_text(strip=True)

                # Meal names are in the second cell
                meal_cell = cells[1]
                # Look for the link that usually contains the meal name
                meal_tag = meal_cell.find("a", class_="js-nyro-modal") or meal_cell.find("a")

                if meal_tag:
                    # Remove icon tags to get clean text
                    for icon in meal_tag.find_all("i"):
                        icon.decompose()
                    meal = meal_tag.get_text(strip=True)
                else:
                    meal = meal_cell.get_text(strip=True)

                if category and meal and "Kalori" not in category:
                    menu_items.append(f"• <b>{category}:</b> {meal}")

        if not menu_items:
            return None

        meal_name = "Öğle Yemeği" if meal_type == "lunch" else "Akşam Yemeği"
        header = f"🍴 <b>{meal_name} Menüsü</b> ({today_str})"

        return header + "\n\n" + "\n".join(menu_items)

    except Exception as e:
        logger.error(f"Error fetching SKS menu: {e}")
        return None
