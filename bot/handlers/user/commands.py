"""
Kullanıcı komutları.

Bu modül geriye dönük uyumluluk için tüm kullanıcı komutlarını import eder.
Modüler yapı için her kategori ayrı dosyada tanımlıdır:
- auth_commands.py: Kullanıcı adı/şifre işlemleri
- course_commands.py: Ders yönetimi
- grade_commands.py: Not ve ödev listeleme
- general_commands.py: Genel komutlar (yardım, durum, arama vb.)
"""

# Import all command handlers from submodules to register them with the bot
from .ari24_commands import (
    callback_pagination,
    callback_subscribe,
    callback_unsubscribe,
    discover_events,
    my_clubs,
    show_ari24_menu,
    subscribe_menu,
    toggle_daily_bulletin,
)
from .auth_commands import (
    process_password,
    process_username,
    set_password,
    set_username,
)
from .cafeteria_commands import (
    handle_cafeteria_refresh,
    send_cafeteria_menu,
)
from .course_commands import (
    add_course,
    auto_add_courses,
    delete_course,
    interactive_menu,
    list_courses,
    user_otoders_command,
)
from .general_commands import (
    handle_cancel_button,
    leave_system,
    process_search_term,
    search_announcements,
    send_help_button,
    send_welcome,
    show_academic_calendar,
    show_faq,
    show_menu,
    show_status,
)
from .grade_commands import (
    kontrol_command_handler,
    list_assignments,
    list_grades,
    manual_check,
)

__all__ = [
    # Auth
    "set_username",
    "process_username",
    "set_password",
    "process_password",
    # Cafeteria
    "send_cafeteria_menu",
    "handle_cafeteria_refresh",
    # Course
    "interactive_menu",
    "user_otoders_command",
    "auto_add_courses",
    "add_course",
    "list_courses",
    "delete_course",
    # Grade
    "list_grades",
    "list_assignments",
    "kontrol_command_handler",
    "manual_check",
    # General
    "send_welcome",
    "handle_cancel_button",
    "send_help_button",
    "show_menu",
    "search_announcements",
    "process_search_term",
    "show_status",
    "leave_system",
    "show_academic_calendar",
    "show_faq",
    # Arı24
    "show_ari24_menu",
    "discover_events",
    "subscribe_menu",
    "callback_subscribe",
    "my_clubs",
    "callback_unsubscribe",
    "toggle_daily_bulletin",
    "callback_pagination",
]
