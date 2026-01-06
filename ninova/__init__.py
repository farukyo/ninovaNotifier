# Ninova modülü
from ninova.auth import LoginFailedError, login_to_ninova
from ninova.scraper import (
    get_announcements,
    get_announcement_detail,
    get_assignments,
    get_assignment_detail,
    get_grades,
    get_user_courses,
    get_class_files,
    get_all_files,
)
from ninova.file_utils import download_file
from ninova.scanner import check_for_updates

__all__ = [
    "LoginFailedError",
    "login_to_ninova",
    "get_announcements",
    "get_announcement_detail",
    "get_assignments",
    "get_assignment_detail",
    "get_grades",
    "get_user_courses",
    "download_file",
    "get_class_files",
    "get_all_files",
    "check_for_updates",
]
