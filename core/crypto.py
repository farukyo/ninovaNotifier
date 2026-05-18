"""Fernet symmetric encryption helpers for stored passwords.

migrated from: common/utils.py (encrypt_password, decrypt_password)
"""

# migrated from: common/utils.py
from __future__ import annotations

import logging

logger = logging.getLogger("ninova")


def encrypt_password(cipher_suite, password: str) -> str:
    """
    Şifreyi Fernet algoritması ile şifreler.

    :param cipher_suite: Fernet cipher instance
    :param password: Düz metin şifre
    :return: Şifrelenen şifre (string) veya boş string
    """
    if not password:
        return ""
    encrypted = cipher_suite.encrypt(password.encode())
    return encrypted.decode()


def decrypt_password(cipher_suite, encrypted_password: str) -> str | None:
    """
    Şifrelenen şifreyi çözer.

    :param cipher_suite: Fernet cipher instance
    :param encrypted_password: Şifrelenen şifre string'i
    :return: Düz metin şifre veya hata durumunda None
    """
    if not encrypted_password:
        return ""
    try:
        decrypted = cipher_suite.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception:
        logger.error("Şifre çözme başarısız! Şifreleme anahtarı değişmiş olabilir.")
        return None
