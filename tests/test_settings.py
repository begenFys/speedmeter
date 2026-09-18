"""Тесты настроек: значения по умолчанию, переопределение через окружение, валидация."""

import pytest
from pydantic import ValidationError

from speedmeter.settings import Settings


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Тесты не должны зависеть от .env разработчика и его окружения."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in ("SPEEDMETER_COUNT", "SPEEDMETER_TIMEOUT", "SPEEDMETER_CONTACT_URL"):
        monkeypatch.delenv(name, raising=False)


def test_defaults() -> None:
    settings = Settings()

    assert settings.count == 10
    assert settings.timeout == 30.0
    assert settings.contact_url is None
    assert settings.user_agent == "speedmeter/0.1"


def test_values_come_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEEDMETER_COUNT", "3")
    monkeypatch.setenv("SPEEDMETER_TIMEOUT", "5")
    monkeypatch.setenv("SPEEDMETER_CONTACT_URL", "https://example.com/me")

    settings = Settings()

    assert settings.count == 3
    assert settings.timeout == 5.0
    assert settings.user_agent == "speedmeter/0.1 (https://example.com/me)"


@pytest.mark.parametrize(
    ("name", "value"), [("SPEEDMETER_COUNT", "0"), ("SPEEDMETER_TIMEOUT", "-1")]
)
def test_invalid_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings()
