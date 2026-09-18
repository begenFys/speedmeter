"""Ядро замера: N запросов к URL и расчёт статистики скачивания."""

import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass

import httpx

# Порог, ниже которого ответ считается слишком маленьким для надёжного замера.
SMALL_RESPONSE_BYTES = 1_000_000

# User-Agent сюда не входит: он приходит из настроек в make_client.
DEFAULT_HEADERS = {
    # Просим промежуточные прокси и CDN не отдавать закэшированную копию.
    "Cache-Control": "no-cache",
    # Отключаем сжатие, чтобы считать байты, реально прошедшие по сети.
    "Accept-Encoding": "identity",
}

Clock = Callable[[], float]


class MeasurementError(Exception):
    """Замер прерван: сетевая ошибка, таймаут или неуспешный HTTP-статус."""


@dataclass(frozen=True, slots=True)
class Sample:
    """Результат одного запроса: длительность и число скачанных байт."""

    seconds: float
    num_bytes: int


@dataclass(frozen=True, slots=True)
class Stats:
    """Итоговая статистика серии запросов."""

    count: int
    total_bytes: int
    total_seconds: float
    avg_seconds: float
    min_seconds: float
    max_seconds: float

    @property
    def avg_bytes(self) -> float:
        return self.total_bytes / self.count

    @property
    def bytes_per_second(self) -> float:
        return self.total_bytes / self.total_seconds

    @property
    def megabytes_per_second(self) -> float:
        return self.bytes_per_second / 1_000_000

    @property
    def megabits_per_second(self) -> float:
        return self.bytes_per_second * 8 / 1_000_000


def make_client(
    timeout: float, user_agent: str, transport: httpx.BaseTransport | None = None
) -> httpx.Client:
    """Создаёт HTTP-клиент с нужными заголовками. Соединение переиспользуется между запросами."""
    return httpx.Client(
        headers={**DEFAULT_HEADERS, "User-Agent": user_agent},
        timeout=timeout,
        follow_redirects=True,
        transport=transport,
    )


def fetch_once(client: httpx.Client, url: str, clock: Clock = time.perf_counter) -> Sample:
    """Скачивает URL целиком и возвращает время запроса и число байт, полученных по сети."""
    start = clock()
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        reason = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        raise MeasurementError(f"Не удалось выполнить запрос к {url} ({reason})") from exc
    elapsed = clock() - start

    if response.is_error:
        raise MeasurementError(f"Сервер вернул HTTP {response.status_code} для {url}")
    return Sample(seconds=elapsed, num_bytes=response.num_bytes_downloaded)


def iter_samples(
    client: httpx.Client, url: str, count: int, clock: Clock = time.perf_counter
) -> Iterator[Sample]:
    """Последовательно выполняет `count` запросов, отдавая результат каждого по мере готовности."""
    if count < 1:
        raise ValueError("Число запросов должно быть не меньше 1")
    for _ in range(count):
        yield fetch_once(client, url, clock)


def compute_stats(samples: Sequence[Sample]) -> Stats:
    """Считает итоговую статистику. Скорость равна сумме байт, делённой на сумму времени."""
    if not samples:
        raise ValueError("Нет результатов для расчёта статистики")
    durations = [sample.seconds for sample in samples]
    total_seconds = sum(durations)
    if total_seconds <= 0:
        raise ValueError("Суммарное время запросов должно быть положительным")
    return Stats(
        count=len(samples),
        total_bytes=sum(sample.num_bytes for sample in samples),
        total_seconds=total_seconds,
        avg_seconds=total_seconds / len(samples),
        min_seconds=min(durations),
        max_seconds=max(durations),
    )
