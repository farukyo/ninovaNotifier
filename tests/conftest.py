"""Shared pytest fixtures for unit and integration tests."""

from __future__ import annotations

import pytest


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
