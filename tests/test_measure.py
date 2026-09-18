"""Тесты HTTP-части: запросы выполняются через httpx.MockTransport, время подменяется."""

from collections.abc import Callable, Iterator

import httpx
import pytest

from speedmeter.measure import (
    MeasurementError,
    Sample,
    fetch_once,
    iter_samples,
    make_client,
)

URL = "https://example.com/image.jpg"
USER_AGENT = "test-agent/1.0"
Handler = Callable[[httpx.Request], httpx.Response]


def fake_clock(*ticks: float) -> Callable[[], float]:
    """Часы, возвращающие заранее заданные отметки времени."""
    it = iter(ticks)
    return lambda: next(it)


def response(status: int, body: bytes) -> httpx.Response:
    """Ответ с потоковым телом, как из реальной сети: иначе счётчик скачанных байт не сработает."""
    return httpx.Response(status, stream=httpx.ByteStream(body))


@pytest.fixture
def client_for() -> Iterator[Callable[[Handler], httpx.Client]]:
    clients: list[httpx.Client] = []

    def factory(handler: Handler) -> httpx.Client:
        transport = httpx.MockTransport(handler)
        client = make_client(timeout=1.0, user_agent=USER_AGENT, transport=transport)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


def test_fetch_once_returns_elapsed_time_and_downloaded_bytes(
    client_for: Callable[[Handler], httpx.Client],
) -> None:
    client = client_for(lambda _: response(200, b"x" * 1000))

    sample = fetch_once(client, URL, clock=fake_clock(10.0, 12.5))

    assert sample == Sample(seconds=2.5, num_bytes=1000)


def test_fetch_once_sends_no_cache_and_identity_headers(
    client_for: Callable[[Handler], httpx.Client],
) -> None:
    seen: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers)
        return response(200, b"ok")

    fetch_once(client_for(handler), URL)

    assert seen[0]["Cache-Control"] == "no-cache"
    assert seen[0]["Accept-Encoding"] == "identity"
    assert seen[0]["User-Agent"] == USER_AGENT


@pytest.mark.parametrize("status", [404, 500])
def test_fetch_once_raises_on_error_status(
    client_for: Callable[[Handler], httpx.Client], status: int
) -> None:
    client = client_for(lambda _: response(status, b"nope"))

    with pytest.raises(MeasurementError, match=str(status)):
        fetch_once(client, URL)


@pytest.mark.parametrize("exc", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow")])
def test_fetch_once_raises_on_transport_error(
    client_for: Callable[[Handler], httpx.Client], exc: httpx.HTTPError
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise exc

    with pytest.raises(MeasurementError, match=URL):
        fetch_once(client_for(handler), URL)


def test_iter_samples_makes_exactly_count_sequential_requests(
    client_for: Callable[[Handler], httpx.Client],
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(200, b"x" * 10)

    samples = list(iter_samples(client_for(handler), URL, count=3, clock=fake_clock(*range(6))))

    assert calls == 3
    assert samples == [Sample(1.0, 10)] * 3


def test_iter_samples_stops_at_first_failure(
    client_for: Callable[[Handler], httpx.Client],
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(200 if calls == 1 else 503, b"x")

    with pytest.raises(MeasurementError):
        list(iter_samples(client_for(handler), URL, count=5))

    assert calls == 2


def test_iter_samples_rejects_non_positive_count(
    client_for: Callable[[Handler], httpx.Client],
) -> None:
    client = client_for(lambda _: response(200, b"x"))

    with pytest.raises(ValueError, match="не меньше 1"):
        list(iter_samples(client, URL, count=0))
