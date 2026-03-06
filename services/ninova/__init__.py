# Ninova modülü
from .auth import LoginFailedError, login_to_ninova
from .file_utils import download_file
from .scraper import (
    get_all_files,
    get_announcement_detail,
    get_announcements,
    get_assignment_detail,
    get_assignments,
    get_class_files,
    get_class_info,
    get_grades,
    get_user_courses,
)

__all__ = [
    "LoginFailedError",
    "download_file",
    "get_all_files",
    "get_announcement_detail",
    "get_announcements",
    "get_assignment_detail",
    "get_assignments",
    "get_class_files",
    "get_class_info",
    "get_grades",
    "get_user_courses",
    "login_to_ninova",
]
