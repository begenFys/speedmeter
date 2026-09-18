"""Тесты CLI: разбор аргументов, вывод и коды возврата. Сеть подменяется MockTransport."""

import io
from collections.abc import Callable

import httpx
import pytest

from speedmeter import cli
from speedmeter.measure import Stats
from speedmeter.settings import Settings

URL = "https://example.com/image.jpg"
USER_AGENT = "test-agent/1.0"
Handler = Callable[[httpx.Request], httpx.Response]


def response(status: int, body: bytes) -> httpx.Response:
    return httpx.Response(status, stream=httpx.ByteStream(body))


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Тесты не должны зависеть от .env разработчика и его окружения."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in ("SPEEDMETER_COUNT", "SPEEDMETER_TIMEOUT", "SPEEDMETER_CONTACT_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def mock_network(monkeypatch: pytest.MonkeyPatch) -> Callable[[Handler], None]:
    """Подменяет фабрику клиента так, чтобы запросы уходили в handler вместо сети."""

    def install(handler: Handler) -> None:
        def fake_make_client(timeout: float, user_agent: str) -> httpx.Client:
            return httpx.Client(transport=httpx.MockTransport(handler), timeout=timeout)

        monkeypatch.setattr(cli, "make_client", fake_make_client)

    return install


def parse_rows(text: str) -> dict[str, str]:
    """Разбирает строки вида «Метка:   значение» в словарь, не завися от выравнивания."""
    rows = (line.split(":", 1) for line in text.splitlines() if ":" in line)
    return {label.strip(): value.strip() for label, value in rows}


def run_cli(*argv: str) -> tuple[int, str, str]:
    args = cli.build_parser(Settings()).parse_args(argv)
    out, err = io.StringIO(), io.StringIO()
    code = cli.run(args.url, args.count, args.timeout, USER_AGENT, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_parser_defaults_come_from_settings(settings: Settings) -> None:
    args = cli.build_parser(settings).parse_args([URL])

    assert args.url == URL
    assert args.count == settings.count == 10
    assert args.timeout == settings.timeout == 30.0


def test_cli_flags_override_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEEDMETER_COUNT", "5")
    monkeypatch.setenv("SPEEDMETER_TIMEOUT", "7.5")

    from_env = cli.build_parser(Settings()).parse_args([URL])
    from_flags = cli.build_parser(Settings()).parse_args([URL, "-n", "2", "-t", "1"])

    assert (from_env.count, from_env.timeout) == (5, 7.5)
    assert (from_flags.count, from_flags.timeout) == (2, 1.0)


def test_main_reports_invalid_env_and_exits_with_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SPEEDMETER_COUNT", "0")

    assert cli.main([URL]) == 2
    assert "Ошибка в настройках окружения" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["ftp://example.com/file"],
        ["not-a-url"],
        [URL, "-n", "0"],
        [URL, "-n", "abc"],
        [URL, "-t", "0"],
        [URL, "-t", "fast"],
    ],
)
def test_parser_rejects_invalid_arguments(
    argv: list[str], settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.build_parser(settings).parse_args(argv)

    assert exc_info.value.code == 2
    assert "ожидается" in capsys.readouterr().err


def test_run_prints_progress_and_summary(mock_network: Callable[[Handler], None]) -> None:
    mock_network(lambda _: response(200, b"x" * 2_000_000))

    code, out, err = run_cli(URL, "-n", "3")

    assert code == 0
    assert err == ""
    assert f"Замер: {URL}, запросов: 3" in out
    assert "  1/3  " in out
    assert "  3/3  " in out
    rows = parse_rows(out)
    assert rows["Запросов"] == "3"
    assert rows["Скачано"] == "6.00 МБ"
    assert rows["Скорость"].endswith("Мбит/с)")


def test_run_reports_http_error_and_exits_with_1(
    mock_network: Callable[[Handler], None],
) -> None:
    mock_network(lambda _: response(500, b"boom"))

    code, out, err = run_cli(URL)

    assert code == 1
    assert "HTTP 500" in err
    assert "Скорость" not in out


def test_run_warns_when_response_is_small(mock_network: Callable[[Handler], None]) -> None:
    mock_network(lambda _: response(200, b"x" * 1000))

    code, _, err = run_cli(URL, "-n", "2")

    assert code == 0
    assert "Внимание" in err


def test_format_stats_shows_both_units() -> None:
    stats = Stats(
        count=2,
        total_bytes=2_000_000,
        total_seconds=4.0,
        avg_seconds=2.0,
        min_seconds=1.0,
        max_seconds=3.0,
    )

    rows = parse_rows(cli.format_stats(stats))

    assert rows["Запросов"] == "2"
    assert rows["Скачано"] == "2.00 МБ"
    assert rows["Среднее время"] == "2.000 с (min 1.000, max 3.000)"
    assert rows["Скорость"] == "0.50 МБ/с (4.0 Мбит/с)"


def test_help_exits_with_zero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0
