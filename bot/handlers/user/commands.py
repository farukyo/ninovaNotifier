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
    process_login_password,
    process_login_username,
    start_login_flow,
)
from .cafeteria_commands import (
    handle_cafeteria_refresh,
    send_cafeteria_menu,
)
from .course_commands import (
    auto_add_courses,
    interactive_menu,
)
from .general_commands import (
    handle_cancel_button,
    leave_system,
    process_search_term,
    search_announcements,
    send_help_button,
    send_welcome,
    show_academic_calendar,
    show_extra_menu,
    show_faq,
    show_status,
)
from .grade_commands import (
    kontrol_command_handler,
    list_assignments,
    list_grades,
    manual_check,
)
from .rehber_commands import handle_rehber_start

__all__ = [
    "auto_add_courses",
    "callback_pagination",
    "callback_subscribe",
    "callback_unsubscribe",
    "discover_events",
    "handle_cafeteria_refresh",
    "handle_cancel_button",
    "handle_rehber_start",
    "interactive_menu",
    "kontrol_command_handler",
    "leave_system",
    "list_assignments",
    "list_grades",
    "manual_check",
    "my_clubs",
    "process_login_password",
    "process_login_username",
    "process_search_term",
    "search_announcements",
    "send_cafeteria_menu",
    "send_help_button",
    "send_welcome",
    "show_academic_calendar",
    "show_ari24_menu",
    "show_extra_menu",
    "show_faq",
    "show_status",
    "start_login_flow",
    "subscribe_menu",
    "toggle_daily_bulletin",
]

# Loading rehber handlers
