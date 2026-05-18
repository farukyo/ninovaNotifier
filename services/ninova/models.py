"""Domain model dataclasses for Ninova LMS data.

Stub — fields will be finalized in Step 7 (type annotations + dataclasses).
These replace the plain dicts used throughout scraper.py and main.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CourseGrade:
    name: str
    grade: str
    weight: str = ""
    date: str = ""


@dataclass
class Assignment:
    title: str
    start_date: str = ""
    end_date: str = ""
    is_submitted: bool | None = None


@dataclass
class Announcement:
    title: str
    url: str
    date: str = ""
    content: str = ""


@dataclass
class CourseFile:
    name: str
    url: str
    size: str = ""
    is_folder: bool = False


@dataclass
class CourseData:
    course_name: str
    url: str
    grades: dict[str, CourseGrade] = field(default_factory=dict)
    assignments: list[Assignment] = field(default_factory=list)
    announcements: list[Announcement] = field(default_factory=list)
    files: list[CourseFile] = field(default_factory=list)
