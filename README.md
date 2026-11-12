# speedmeter

[![CI](https://github.com/begenFys/speedmeter/actions/workflows/ci.yml/badge.svg)](https://github.com/begenFys/speedmeter/actions/workflows/ci.yml)

English | [Русский](README.ru.md)

A command-line tool that measures download speed from your machine. Give it
the URL of a large file, such as an image; it makes several sequential
requests, waits for each response body in full and prints the average
request time, the amount downloaded and the speed.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+ (uv installs
Python if it is missing).

```bash
git clone https://github.com/begenFys/speedmeter.git
cd speedmeter
make install
make run URL=https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg
```

`make install` installs the dependencies, copies `.env.example` to `.env` and
sets up the pre-commit hooks.

Without make:

```bash
uv sync
cp .env.example .env
uv run speedmeter https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg
```

`uv run python -m speedmeter <url>` works too.

## Example output

The tool's messages are in Russian. A run of ten requests:

```
$ uv run speedmeter https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg
Замер: https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg, запросов: 10
   1/10  4.379 с  14.68 МБ
   2/10  1.797 с  14.68 МБ
   3/10  1.695 с  14.68 МБ
   4/10  1.834 с  14.68 МБ
   5/10  2.091 с  14.68 МБ
   6/10  2.517 с  14.68 МБ
   7/10  1.882 с  14.68 МБ
   8/10  1.880 с  14.68 МБ
   9/10  1.739 с  14.68 МБ
  10/10  1.982 с  14.68 МБ

Запросов:       10
Скачано:        146.79 МБ
Среднее время:  2.180 с (min 1.695, max 4.379)
Скорость:       6.73 МБ/с (53.9 Мбит/с)
```

The summary reads: requests, downloaded, average time, speed. The first
request is noticeably slower: it includes the TCP/TLS handshake and warming
up the CDN cache, which is why min and max are shown next to the average.

## Options

| Flag | Default | Meaning |
|---|---|---|
| `url` | required | http(s) URL of a large file |
| `-n`, `--count` | 10 | number of sequential requests |
| `-t`, `--timeout` | 30 | timeout of a single network operation, seconds |

Defaults can be set with environment variables or a `.env` file in the
working directory. Flags take precedence over the environment.

| Variable | Meaning |
|---|---|
| `SPEEDMETER_COUNT` | default number of requests |
| `SPEEDMETER_TIMEOUT` | default timeout, seconds |
| `SPEEDMETER_CONTACT_URL` | contact link added to the `User-Agent` |

`SPEEDMETER_CONTACT_URL` is needed for hosts such as Wikimedia, whose policy
answers requests without a contact link in the `User-Agent` with 403. A
ready value is in `.env.example`.

Exit codes: 0 on success, 1 if the measurement fails (timeout, network
error, non-2xx response), 2 on invalid arguments or settings.

## How it is measured

- **Speed** is total bytes divided by the total time of all requests, not
  the mean of per-request speeds, so slow requests get their proper weight.
- **Units.** Both megabytes per second and megabits per second are printed,
  as speedtest.net does. Multipliers are decimal: 1 MB = 1,000,000 bytes,
  1 Mbit = 1,000,000 bits.
- **Time** runs from sending the request to receiving the whole body,
  measured with `time.perf_counter()`.
- **Bytes** are what actually came from the socket (`num_bytes_downloaded`
  in httpx), not the `Content-Length` header.
- **Caching.** `Cache-Control: no-cache` is sent so proxies and CDNs do not
  serve a cached copy. The client itself caches nothing.
- **Compression** is disabled with `Accept-Encoding: identity`, so the bytes
  on the wire match the file size.
- **Connection** is reused between requests (keep-alive), so only the first
  request pays for the handshake. This is deliberate: the result is closer
  to the bandwidth of the link than to the cost of one cold request.
- **Timeout** applies to each network operation separately: connecting and
  waiting for the next chunk of data, as httpx does. A large file on a slow
  link is not cut off while data keeps arriving.
- **Errors.** The run stops at the first failed request. There are no
  retries; they would distort the result.
- **Small files.** If the average response is under 1 MB, a warning is
  printed: results on such sizes are noisy.

## Development

```bash
make            # list of commands
make check      # ruff, mypy, pytest
make test       # tests only, verbose
make format     # autoformat
```

The same checks run in pre-commit on commit and in GitHub Actions on Python
3.12 and 3.14.

```
src/speedmeter/
  cli.py        argument parsing, output, exit codes
  measure.py    HTTP requests and statistics
  settings.py   settings from the environment
tests/
  test_cli.py       CLI: arguments, output, exit codes
  test_measure.py   HTTP part via httpx.MockTransport and a fake clock
  test_stats.py     statistics
  test_settings.py  settings
```

The tests do not use the network.
