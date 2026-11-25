"""Настройки из переменных окружения и файла .env. Флаги CLI имеют приоритет."""

from importlib.metadata import version

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "speedmeter"
APP_VERSION = version("speedmeter")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SPEEDMETER_", env_file=".env", extra="ignore")

    count: int = Field(default=10, ge=1, description="Число последовательных запросов")
    timeout: float = Field(default=30.0, gt=0, description="Таймаут сетевой операции, секунды")
    # Некоторые хосты (например, Wikimedia) без ссылки на автора в User-Agent отдают 403.
    contact_url: str | None = Field(default=None, description="Ссылка на автора для User-Agent")

    @property
    def user_agent(self) -> str:
        base = f"{APP_NAME}/{APP_VERSION}"
        return f"{base} ({self.contact_url})" if self.contact_url else base
