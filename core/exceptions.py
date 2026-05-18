"""Custom exception hierarchy for the application."""

# migrated from: services/ninova/auth.py (LoginFailedError)


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


# --- Future names (Step 6 rename targets) ---


class NinovaError(Exception):
    """Base exception for all Ninova-related errors."""


class NinovaAuthError(NinovaError):
    """Authentication failure with typed error code. Replaces LoginFailedError in Step 6."""

    def __init__(
        self, error_type: str, message: str, username: str = "", chat_id: str = ""
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.username = username
        self.chat_id = chat_id


class NinovaScrapingError(NinovaError):
    """Scraping or parsing failure."""


class UserNotFoundError(NinovaError):
    """Requested user does not exist in storage."""


class StorageError(NinovaError):
    """Persistent storage read/write failure."""


class EncryptionError(NinovaError):
    """Fernet encryption or decryption failure."""
