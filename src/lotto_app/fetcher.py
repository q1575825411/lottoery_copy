from __future__ import annotations

import math
import logging
import re
import socket
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .constants import DEFAULT_HISTORY_URL, MAX_DRAWS, MAX_HISTORY_PAGES, RED_BALL_COUNT
from .state import LottoState

logger = logging.getLogger(__name__)
DEFAULT_FETCH_TIMEOUT = 30
DEFAULT_FETCH_RETRIES = 3
DEFAULT_FETCH_RETRY_DELAY = 1.0


@dataclass(frozen=True)
class DrawRecord:
    serial: str
    draw_date: str
    red: list[int]
    blue: int


def fetch_text(
    url: str,
    *,
    timeout: int = DEFAULT_FETCH_TIMEOUT,
    retries: int = DEFAULT_FETCH_RETRIES,
    retry_delay: float = DEFAULT_FETCH_RETRY_DELAY,
) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    last_error: Exception | None = None
    total_attempts = max(1, retries)
    for attempt in range(1, total_attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="ignore")
        except HTTPError:
            raise
        except (TimeoutError, socket.timeout, URLError) as exc:
            last_error = exc
            if attempt >= total_attempts:
                break
            logger.warning(
                "fetch attempt %s/%s failed for %s: %s; retrying in %.1fs",
                attempt,
                total_attempts,
                url,
                exc,
                retry_delay,
            )
            time.sleep(retry_delay)

    assert last_error is not None
    raise last_error


def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    return value.replace("&nbsp;", " ").strip()


def parse_history_rows(html: str) -> list[dict[str, object]]:
    table_match = re.search(r'<table class="table table-bordered table-history">.*?<tbody>(.*?)</tbody>', html, re.S)
    if not table_match:
        raise RuntimeError("unexpected history page format: missing result table")

    rows = []
    for row_html in re.findall(r"<tr>(.*?)</tr>", table_match.group(1), re.S):
        cells = re.findall(r"<td.*?>(.*?)</td>", row_html, re.S)
        if len(cells) < 4:
            continue

        serial = strip_tags(cells[0])
        draw_date = strip_tags(cells[1])
        red_values = re.findall(r'pellet-sm red">(\d{2})</span>', cells[3])
        blue_values = re.findall(r'pellet-sm blue">(\d{2})</span>', cells[3])
        if len(red_values) != RED_BALL_COUNT or len(blue_values) != 1:
            continue

        rows.append(
            {
                "serial": serial,
                "date": draw_date,
                "red": [int(ball) for ball in red_values],
                "blue": int(blue_values[0]),
            }
        )

    return rows


def load_history_records(base_url: str = DEFAULT_HISTORY_URL, draw_count: int | None = None) -> list[DrawRecord]:
    requested_draws = max(draw_count or 0, 0)
    estimated_pages = max(3, int(math.ceil(requested_draws / 30.0))) if requested_draws else MAX_HISTORY_PAGES
    parsed_rows: list[DrawRecord] = []
    seen_serials: set[str] = set()
    for page in range(1, estimated_pages + 1):
        try:
            logger.info("fetching history page %s", page)
            html = fetch_text(base_url.format(page=page))
        except HTTPError as exc:
            if exc.code == 404 and parsed_rows:
                logger.info("history page %s returned 404, treating it as the end of pagination", page)
                break
            raise RuntimeError("failed to fetch lottery data from %s: %s" % (base_url, exc)) from exc
        except (TimeoutError, socket.timeout, URLError) as exc:
            raise RuntimeError("failed to fetch lottery data from %s: %s" % (base_url, exc)) from exc

        page_rows = parse_history_rows(html)
        if not page_rows:
            break
        new_count = 0
        for row in page_rows:
            serial = row["serial"]
            if serial in seen_serials:
                continue
            seen_serials.add(serial)
            parsed_rows.append(
                DrawRecord(
                    serial=serial,
                    draw_date=row["date"],
                    red=list(row["red"]),
                    blue=row["blue"],
                )
            )
            new_count += 1
        logger.info("parsed %s new rows from page %s", new_count, page)
        if new_count == 0:
            break
        if requested_draws and len(parsed_rows) >= requested_draws:
            break

    return parsed_rows


def populate_state_from_records(state: LottoState, records: list[DrawRecord], draw_count: int) -> None:
    requested_draws = max(draw_count or MAX_DRAWS, MAX_DRAWS)
    state.reset()
    for row, item in enumerate(records[:requested_draws]):
        for col, ball in enumerate(item.red):
            state.red_balls[row][col] = ball
        state.blue_balls[row] = item.blue
        state.serials.append(item.serial)
        state.draw_dates.append(item.draw_date)


def load_history(state: LottoState, draw_count: int, base_url: str = DEFAULT_HISTORY_URL) -> None:
    parsed_rows = load_history_records(base_url=base_url, draw_count=draw_count)
    if len(parsed_rows) < MAX_DRAWS:
        raise RuntimeError("history page returned only %d draws; at least %d are required" % (len(parsed_rows), MAX_DRAWS))

    logger.info("loaded %s history rows", len(parsed_rows))
    populate_state_from_records(state, parsed_rows, draw_count)
