"""Общие фикстуры."""

import pytest

from speedmeter.settings import Settings


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Тесты не должны зависеть от .env разработчика и его окружения."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in ("SPEEDMETER_COUNT", "SPEEDMETER_TIMEOUT", "SPEEDMETER_CONTACT_URL"):
        monkeypatch.delenv(name, raising=False)
