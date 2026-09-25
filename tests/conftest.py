"""Shared pytest fixtures for unit and integration tests."""

from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

# Uygulama modülleri import anında ortam değişkenlerini okuyor (bot.instance TeleBot'u,
# core.config Fernet anahtarını oluşturuyor). Testlerin gerçek token/anahtara ihtiyaç
# duymaması ve secrets/ altına dosya yazmaması için sahte değerler veriyoruz.
# load_dotenv mevcut ortam değişkenlerini ezmediğinden secrets/.env bunları değiştirmez.
os.environ["TELEGRAM_TOKEN"] = "123456:TEST-TOKEN"
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()


@pytest.fixture
def sample_course_url() -> str:
    return "https://ninova.itu.edu.tr/Sinif/12345"


@pytest.fixture
def sample_user_data() -> dict:
    return {
        "username": "test_user",
        "password": "",
        "urls": [],
    }
