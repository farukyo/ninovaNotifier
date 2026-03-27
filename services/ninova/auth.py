import logging
import threading
import time

import requests
from bs4 import BeautifulSoup

from common.config import (
    MAX_LOGIN_RETRIES,
    RETRY_BACKOFF_BASE,
    RETRY_BACKOFF_MAX,
)

logger = logging.getLogger("ninova")

_LOGIN_LOCKS: dict[str, threading.Lock] = {}
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
    Belirli bir kullanıcı için Ninova'ya giriş yapar (exponential backoff retry ile).

    Oturum zaten aktifse tekrar giriş yapmaz. Başarısız giriş durumunda
    kullanıcıya bildirim gönderir. Ağ hataları için retry mekanizması vardır.

    :param session: requests.Session nesnesi
    :param chat_id: Kullanıcının Telegram chat ID'si
    :param username: Ninova kullanıcı adı
    :param password: Ninova şifresi
    :param quiet: True ise sessiz mod (bildirim gönderme)
    :return: Başarılıysa True, değilse False
    """
    with get_user_lock(chat_id):
        if not username or not password:
            logger.error(f"[{chat_id}] Login failed: missing username or password")
            return False

        # Exponential backoff retry mekanizması
        for attempt in range(1, MAX_LOGIN_RETRIES + 1):
            try:
                # Önce halihazırda giriş yapılmış mı kontrol et
                try:
                    check_resp = session.get(
                        "https://ninova.itu.edu.tr/Kampus", timeout=5, allow_redirects=False
                    )
                    if check_resp.status_code == 200:
                        if not quiet:
                            logger.debug(f"[{chat_id}] Session already active, skipping login")
                        return True
                except Exception as e:
                    logger.debug(f"[{chat_id}] Session check failed (attempt {attempt}): {e}")

                login_url = "https://ninova.itu.edu.tr/Login.aspx"
                resp = session.get(login_url, allow_redirects=True, timeout=15)
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

                resp = session.post(resp.url, data=data, allow_redirects=True, timeout=15)

                if "Hatalı" in resp.text or "Login.aspx" in resp.url:
                    logger.warning(
                        f"[{chat_id}] Login failed: invalid credentials (attempt {attempt}/{MAX_LOGIN_RETRIES})"
                    )
                    # Invalid credentials - don't retry
                    return False

                if not quiet:
                    logger.info(f"[{chat_id}] Login successful")

                return True

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # Network error - retry with backoff
                if attempt < MAX_LOGIN_RETRIES:
                    backoff = min(RETRY_BACKOFF_BASE**attempt, RETRY_BACKOFF_MAX)
                    logger.warning(
                        f"[{chat_id}] Network error (attempt {attempt}/{MAX_LOGIN_RETRIES}): {e}. "
                        f"Retrying in {backoff}s..."
                    )
                    time.sleep(backoff)
                else:
                    logger.error(
                        f"[{chat_id}] Login failed after {MAX_LOGIN_RETRIES} attempts: {e}"
                    )
                    return False

            except Exception as e:
                logger.exception(f"[{chat_id}] Unexpected error during login: {e}")
                return False

        return False
