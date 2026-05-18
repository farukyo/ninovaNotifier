"""Domain model dataclasses for SKS dining menu data.

Stub — will be populated in Step 7.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MealItem:
    name: str
    calories: str = ""


@dataclass
class MealMenu:
    meal_type: str
    date: str
    items: list[MealItem] = field(default_factory=list)
    html: str = ""
