"""
Tests for application settings and configuration.

Source: app/config.py

NOTE: We test the global `settings` instance (created at import time from env vars
set in conftest.py) rather than creating new Settings() instances, because
pydantic-settings reads .env file from CWD which may contain extra vars.
"""

import pytest
import os
import tempfile

from app.config import Settings, settings


class TestGlobalSettings:
    """Tests for the global settings instance (created from conftest env vars)."""

    def test_admin_user_id_list(self):
        # conftest sets ADMIN_USER_IDS="28795547,999999"
        assert settings.admin_user_id_list == [28795547, 999999]

    def test_is_admin_true(self):
        assert settings.is_admin(28795547) is True

    def test_is_admin_false(self):
        assert settings.is_admin(12345) is False

    def test_is_admin_second_id(self):
        assert settings.is_admin(999999) is True

    def test_telegram_token(self):
        assert len(settings.telegram_token) > 10

    def test_environment_is_test(self):
        assert settings.environment == "test"


class TestSettingsCreation:
    """Tests for Settings construction in isolated env (no .env file)."""

    def test_single_admin_id(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # no .env here
        s = Settings(
            telegram_token="0000000000:AAHtest_token",
            telegram_api_id=123,
            telegram_api_hash="hash",
            admin_user_ids="28795547",
            database_url="sqlite:///:memory:",
            redis_url="redis://localhost/0",
        )
        assert s.admin_user_id_list == [28795547]

    def test_multiple_admin_ids(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        s = Settings(
            telegram_token="0000000000:AAHtest_token",
            telegram_api_id=123,
            telegram_api_hash="hash",
            admin_user_ids="28795547,132228544,56994156",
            database_url="sqlite:///:memory:",
            redis_url="redis://localhost/0",
        )
        assert s.admin_user_id_list == [28795547, 132228544, 56994156]

    def test_admin_ids_with_spaces(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        s = Settings(
            telegram_token="0000000000:AAHtest_token",
            telegram_api_id=123,
            telegram_api_hash="hash",
            admin_user_ids=" 28795547 , 132228544 ",
            database_url="sqlite:///:memory:",
            redis_url="redis://localhost/0",
        )
        assert s.admin_user_id_list == [28795547, 132228544]

    def test_empty_admin_ids_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(Exception):
            Settings(
                telegram_token="0000000000:AAHtest_token",
                telegram_api_id=123,
                telegram_api_hash="hash",
                admin_user_ids="",
                database_url="sqlite:///:memory:",
                redis_url="redis://localhost/0",
            )

    def test_short_token_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(Exception):
            Settings(
                telegram_token="short",
                telegram_api_id=123,
                telegram_api_hash="hash",
                admin_user_ids="28795547",
                database_url="sqlite:///:memory:",
                redis_url="redis://localhost/0",
            )
