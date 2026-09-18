"""Интерфейс командной строки."""

import argparse
import sys
from collections.abc import Sequence
from typing import TextIO
from urllib.parse import urlparse

from pydantic import ValidationError

from speedmeter.measure import (
    SMALL_RESPONSE_BYTES,
    MeasurementError,
    Sample,
    Stats,
    compute_stats,
    iter_samples,
    make_client,
)
from speedmeter.settings import Settings


def http_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise argparse.ArgumentTypeError(f"ожидается http(s) URL, получено: {value!r}")
    return value


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"ожидается целое число, получено: {value!r}") from None
    if number < 1:
        raise argparse.ArgumentTypeError(f"ожидается число не меньше 1, получено: {number}")
    return number


def positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"ожидается число, получено: {value!r}") from None
    if number <= 0:
        raise argparse.ArgumentTypeError(f"ожидается положительное число, получено: {value}")
    return number


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="speedmeter",
        description="Замер скорости скачивания: несколько последовательных запросов к URL.",
    )
    parser.add_argument("url", type=http_url, help="адрес тяжёлого файла, например картинки")
    parser.add_argument(
        "-n",
        "--count",
        type=positive_int,
        default=settings.count,
        help="число последовательных запросов (по умолчанию %(default)s)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=positive_float,
        default=settings.timeout,
        help="таймаут одного запроса в секундах (по умолчанию %(default)s)",
    )
    return parser


def format_megabytes(num_bytes: float) -> str:
    return f"{num_bytes / 1_000_000:.2f} МБ"


def format_sample(index: int, count: int, sample: Sample) -> str:
    return f"  {index}/{count}  {sample.seconds:.3f} с  {format_megabytes(sample.num_bytes)}"


def format_stats(stats: Stats) -> str:
    rows = [
        ("Запросов", str(stats.count)),
        ("Скачано", format_megabytes(stats.total_bytes)),
        (
            "Среднее время",
            f"{stats.avg_seconds:.3f} с (min {stats.min_seconds:.3f}, max {stats.max_seconds:.3f})",
        ),
        (
            "Скорость",
            f"{stats.megabytes_per_second:.2f} МБ/с ({stats.megabits_per_second:.1f} Мбит/с)",
        ),
    ]
    width = max(len(label) for label, _ in rows) + 1  # +1 под двоеточие
    return "\n".join(f"{label + ':':<{width}}  {value}" for label, value in rows)


def run(url: str, count: int, timeout: float, user_agent: str, out: TextIO, err: TextIO) -> int:
    print(f"Замер: {url}, запросов: {count}", file=out, flush=True)
    samples: list[Sample] = []
    try:
        with make_client(timeout=timeout, user_agent=user_agent) as client:
            for index, sample in enumerate(iter_samples(client, url, count), start=1):
                samples.append(sample)
                print(format_sample(index, count, sample), file=out, flush=True)
    except MeasurementError as exc:
        print(f"Ошибка: {exc}", file=err)
        return 1

    stats = compute_stats(samples)
    print(file=out)
    print(format_stats(stats), file=out, flush=True)
    if stats.avg_bytes < SMALL_RESPONSE_BYTES:
        print(
            f"Внимание: средний размер ответа {format_megabytes(stats.avg_bytes)}."
            f" Для надёжного замера нужен файл от {format_megabytes(SMALL_RESPONSE_BYTES)}.",
            file=err,
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        settings = Settings()
    except ValidationError as exc:
        print(f"Ошибка в настройках окружения:\n{exc}", file=sys.stderr)
        return 2
    args = build_parser(settings).parse_args(argv)
    try:
        return run(
            args.url,
            args.count,
            args.timeout,
            user_agent=settings.user_agent,
            out=sys.stdout,
            err=sys.stderr,
        )
    except KeyboardInterrupt:
        print("Прервано", file=sys.stderr)
        return 130
