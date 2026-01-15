import contextlib
import logging
import threading

from bs4 import BeautifulSoup
from plyer import notification

from common.config import console
from common.utils import send_telegram_message

logger = logging.getLogger("ninova")

_LOGIN_LOCKS = {}
_GLOBAL_LOCK = threading.Lock()


def get_user_lock(chat_id):
    with _GLOBAL_LOCK:
        if chat_id not in _LOGIN_LOCKS:
            _LOGIN_LOCKS[chat_id] = threading.Lock()
        return _LOGIN_LOCKS[chat_id]


class LoginFailedError(Exception):
    pass


def login_to_ninova(session, chat_id, username, password, quiet=False):
    """
    Belirli bir kullanıcı için Ninova'ya giriş yapar.

    Oturum zaten aktifse tekrar giriş yapmaz. Başarısız giriş durumunda
    kullanıcıya bildirim gönderir.

    :param session: requests.Session nesnesi
    :param chat_id: Kullanıcının Telegram chat ID'si
    :param username: Ninova kullanıcı adı
    :param password: Ninova şifresi
    :param quiet: True ise sessiz mod (bildirim gönderme)
    :return: Başarılıysa True, değilse False
    """
    with get_user_lock(chat_id):
        if not username or not password:
            console.print(f"[bold red]Hata ({chat_id}): Kullanıcı adı veya şifre eksik!")
            return False

        try:
            # Önce halihazırda giriş yapılmış mı kontrol et
            try:
                check_resp = session.get(
                    "https://ninova.itu.edu.tr/Kampus", timeout=5, allow_redirects=False
                )
                if check_resp.status_code == 200:
                    if not quiet:
                        console.print(f"[cyan]Oturum zaten aktif ({chat_id})[/cyan]")
                    return True
            except Exception:
                pass

            login_url = "https://ninova.itu.edu.tr/Login.aspx"
            resp = session.get(login_url, allow_redirects=True)
            soup = BeautifulSoup(resp.text, "html.parser")

            data = {}
            for hidden in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
                tag = soup.find("input", {"name": hidden})
                if tag:
                    data[hidden] = tag["value"]

            data.update(
                {
                    "ctl00$ContentPlaceHolder1$tbUserName": username,
                    "ctl00$ContentPlaceHolder1$tbPassword": password,
                    "ctl00$ContentPlaceHolder1$btnLogin": "Giriş",
                }
            )

            resp = session.post(resp.url, data=data, allow_redirects=True)

            if "Hatalı" in resp.text or "Login.aspx" in resp.url:
                console.print(
                    f"[bold red]Giriş başarısız ({chat_id}): Kullanıcı adı veya şifre hatalı olabilir."
                )
                return False

            if not quiet:
                msg = "🔑 <b>Yeni Oturum Açıldı</b>\n\nNinova oturumu başarıyla açıldı."
                console.print(f"[bold green]Giriş başarılı! ({chat_id})")
                send_telegram_message(chat_id, msg)

                with contextlib.suppress(Exception):
                    notification.notify(
                        title="Ninova Takip",
                        message=f"Oturum açıldı ({chat_id})",
                        app_name="Ninova Takip",
                        timeout=5,
                    )

            return True
        except Exception as e:
            console.print(f"[bold red]Giriş sırasında hata oluştu ({chat_id}): {e}")
            return False
