"""Тесты чистой математики: расчёт статистики по списку замеров."""

import pytest

from speedmeter.measure import Sample, compute_stats


def test_compute_stats_aggregates_samples() -> None:
    samples = [Sample(seconds=1.0, num_bytes=1_000_000), Sample(seconds=3.0, num_bytes=1_000_000)]

    stats = compute_stats(samples)

    assert stats.count == 2
    assert stats.total_bytes == 2_000_000
    assert stats.total_seconds == 4.0
    assert stats.avg_seconds == 2.0
    assert stats.min_seconds == 1.0
    assert stats.max_seconds == 3.0
    assert stats.avg_bytes == 1_000_000


def test_speed_is_total_bytes_over_total_time_not_mean_of_speeds() -> None:
    # 1 МБ за 1 с и 1 МБ за 3 с: среднее скоростей дало бы 0.667 МБ/с, честный расчёт даёт 0.5.
    samples = [Sample(seconds=1.0, num_bytes=1_000_000), Sample(seconds=3.0, num_bytes=1_000_000)]

    stats = compute_stats(samples)

    assert stats.bytes_per_second == 500_000
    assert stats.megabytes_per_second == 0.5
    assert stats.megabits_per_second == 4.0


def test_compute_stats_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="Нет результатов"):
        compute_stats([])


def test_compute_stats_rejects_zero_total_time() -> None:
    with pytest.raises(ValueError, match="положительным"):
        compute_stats([Sample(seconds=0.0, num_bytes=1)])
