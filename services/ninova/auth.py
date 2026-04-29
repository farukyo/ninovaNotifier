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
from common.http_logging import http_request
from common.log_context import log_with_context

logger = logging.getLogger("ninova")

_LOGIN_LOCKS: dict[str, threading.Lock] = {}
_GLOBAL_LOCK = threading.Lock()


def get_user_lock(chat_id):
    with _GLOBAL_LOCK:
        if chat_id not in _LOGIN_LOCKS:
            _LOGIN_LOCKS[chat_id] = threading.Lock()
        return _LOGIN_LOCKS[chat_id]


class LoginFailedError(Exception):
    """
    Login hatası exception'ı.

    :param error_type: 'INVALID_CREDENTIALS', 'NETWORK_TIMEOUT', 'SESSION_ERROR', 'UNKNOWN'
    :param message: Hata mesajı
    :param username: Giriş yapmaya çalışan kullanıcı adı
    :param chat_id: Telegram chat ID
    """

    def __init__(self, error_type, message, username=None, chat_id=None):
        self.error_type = error_type
        self.message = message
        self.username = username
        self.chat_id = chat_id
        super().__init__(message)


def login_to_ninova(session, chat_id, username, password, quiet=False):
    """
    Belirli bir kullanıcı için Ninova'ya giriş yapar (exponential backoff retry ile).

    Oturum zaten aktifse tekrar giriş yapmaz. Başarısız giriş durumunda
    LoginFailedError fırlatır. Ağ hataları için retry mekanizması vardır.

    :param session: requests.Session nesnesi
    :param chat_id: Kullanıcının Telegram chat ID'si
    :param username: Ninova kullanıcı adı
    :param password: Ninova şifresi
    :param quiet: True ise sessiz mod (de hata fırlatırıyor)
    :return: Başarılıysa True, değilse LoginFailedError fırlatır
    :raises LoginFailedError: Giriş başarısız olursa
    """
    with get_user_lock(chat_id):
        if not username or not password:
            log_with_context(
                logger,
                "error",
                "Login failed: missing username or password",
                chat_id=str(chat_id),
                action="ninova_login",
            )
            raise LoginFailedError(
                "SESSION_ERROR",
                "Kullanıcı adı veya şifre eksik",
                username=username,
                chat_id=chat_id,
            )

        # Exponential backoff retry mekanizması
        for attempt in range(1, MAX_LOGIN_RETRIES + 1):
            try:
                # Önce halihazırda giriş yapılmış mı kontrol et
                try:
                    check_resp = http_request(
                        logger,
                        session,
                        "GET",
                        "https://ninova.itu.edu.tr/Kampus",
                        action="ninova_login_check",
                        chat_id=str(chat_id),
                        timeout=10,
                        allow_redirects=False,
                        retry_count=attempt - 1,
                    )
                    if check_resp.status_code == 200:
                        if not quiet:
                            logger.debug(f"[{chat_id}] Session already active, skipping login")
                        return True
                except Exception as e:
                    log_with_context(
                        logger,
                        "debug",
                        f"Session check failed (attempt {attempt}): {e}",
                        chat_id=str(chat_id),
                        action="ninova_login_check",
                        retry_count=attempt - 1,
                        error_stage="http",
                    )

                login_url = "https://ninova.itu.edu.tr/Login.aspx"
                resp = http_request(
                    logger,
                    session,
                    "GET",
                    login_url,
                    action="ninova_login_page",
                    chat_id=str(chat_id),
                    timeout=20,
                    allow_redirects=True,
                    retry_count=attempt - 1,
                )
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

                resp = http_request(
                    logger,
                    session,
                    "POST",
                    resp.url,
                    action="ninova_login_submit",
                    chat_id=str(chat_id),
                    data=data,
                    allow_redirects=True,
                    timeout=20,
                    retry_count=attempt - 1,
                )

                if "Hatalı" in resp.text or "Login.aspx" in resp.url:
                    log_with_context(
                        logger,
                        "warning",
                        f"Login failed: invalid credentials (attempt {attempt}/{MAX_LOGIN_RETRIES})",
                        chat_id=str(chat_id),
                        action="ninova_login",
                        retry_count=attempt - 1,
                    )
                    # Invalid credentials - don't retry
                    raise LoginFailedError(
                        "INVALID_CREDENTIALS",
                        "Ninova kullanıcı adı veya şifresi yanlış",
                        username=username,
                        chat_id=chat_id,
                    )

                if not quiet:
                    log_with_context(
                        logger,
                        "info",
                        "Login successful",
                        chat_id=str(chat_id),
                        action="ninova_login",
                        retry_count=attempt - 1,
                    )

                return True

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # Network error - retry with backoff
                if attempt < MAX_LOGIN_RETRIES:
                    backoff = min(RETRY_BACKOFF_BASE**attempt, RETRY_BACKOFF_MAX)
                    log_with_context(
                        logger,
                        "warning",
                        f"Network error (attempt {attempt}/{MAX_LOGIN_RETRIES}): {e}. Retrying in {backoff}s...",
                        chat_id=str(chat_id),
                        action="ninova_login",
                        retry_count=attempt - 1,
                        error_stage="http",
                    )
                    time.sleep(backoff)
                else:
                    log_with_context(
                        logger,
                        "error",
                        f"Login failed after {MAX_LOGIN_RETRIES} attempts: {e}",
                        chat_id=str(chat_id),
                        action="ninova_login",
                        retry_count=attempt - 1,
                        error_stage="http",
                    )
                    raise LoginFailedError(
                        "NETWORK_TIMEOUT",
                        f"{MAX_LOGIN_RETRIES} deneme sonucu başarısız: {str(e)[:100]}",
                        username=username,
                        chat_id=chat_id,
                    ) from e

            except LoginFailedError:
                raise

            except Exception as e:
                log_with_context(
                    logger,
                    "error",
                    f"Unexpected error during login: {e}",
                    chat_id=str(chat_id),
                    action="ninova_login",
                    exc_info=True,
                )
                raise LoginFailedError(
                    "UNKNOWN",
                    f"Bilinmeyen hata: {str(e)[:100]}",
                    username=username,
                    chat_id=chat_id,
                ) from e

        return False
