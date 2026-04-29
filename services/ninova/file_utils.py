import io
import logging
from pathlib import Path

from common.http_logging import http_request
from common.log_context import log_with_context

from .auth import login_to_ninova

logger = logging.getLogger("ninova")


def download_file(
    session, url, filename, chat_id=None, username=None, password=None, to_buffer=False
):
    """
    Ninova'dan dosya indirir.

    :param session: requests.Session nesnesi
    :param url: İndirilecek dosyanın URL'i
    :param filename: Dosya adı (varsayılan)
    :param chat_id: Kullanıcı ID
    :param username: Ninova kullanıcı adı
    :param password: Ninova şifresi
    :param to_buffer: True ise (BytesIO, filename) döner, değilse dosya yolu döner.
    :return: (BytesIO, filename) veya filepath veya None
    """
    try:
        response = http_request(
            logger,
            session,
            "GET",
            url,
            action="ninova_file_download",
            chat_id=str(chat_id) if chat_id else None,
            timeout=30,
            allow_redirects=False,
            stream=True,
        )
        if response.status_code == 302:
            if login_to_ninova(session, chat_id, username, password):
                response = http_request(
                    logger,
                    session,
                    "GET",
                    url,
                    action="ninova_file_download",
                    chat_id=str(chat_id) if chat_id else None,
                    timeout=30,
                    allow_redirects=False,
                    stream=True,
                )
            else:
                log_with_context(
                    logger,
                    "warning",
                    "File download failed after login retry",
                    chat_id=str(chat_id) if chat_id else None,
                    action="ninova_file_download",
                    error_stage="login",
                )
                return None

        if response.status_code == 200:
            cd = response.headers.get("Content-Disposition")
            if cd and "filename=" in cd:
                if 'filename="' in cd:
                    filename = cd.split('filename="')[1].split('"')[0]
                else:
                    filename = cd.split("filename=")[1].split(";")[0].strip()

            # Clean filename — remove only filesystem/path-unsafe chars, preserve Unicode (Turkish)
            filename = "".join(c for c in filename if c not in '<>:"/\\|?*\x00').strip()
            if not filename:
                filename = "document.bin"

            if to_buffer:
                buffer = io.BytesIO()
                for chunk in response.iter_content(chunk_size=8192):
                    buffer.write(chunk)
                buffer.seek(0)
                return buffer, filename
            filepath = Path.cwd() / filename
            with Path(filepath).open("wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return filepath

    except Exception as e:
        log_with_context(
            logger,
            "error",
            f"File download error: {e}",
            chat_id=str(chat_id) if chat_id else None,
            action="ninova_file_download",
            exc_info=True,
        )
    return None
