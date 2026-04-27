from __future__ import annotations

import hashlib
import json
import logging
import socket
from pathlib import Path
from urllib.error import HTTPError, URLError

from .constants import MAX_HISTORY_PAGES
from .fetcher import DrawRecord, fetch_text, load_history_records, parse_history_rows

logger = logging.getLogger(__name__)


def _record_to_dict(record: DrawRecord) -> dict[str, object]:
    return {
        "serial": record.serial,
        "draw_date": record.draw_date,
        "red": record.red,
        "blue": record.blue,
    }


def _record_from_dict(item: dict[str, object]) -> DrawRecord:
    return DrawRecord(
        serial=str(item["serial"]),
        draw_date=str(item["draw_date"]),
        red=[int(ball) for ball in item["red"]],
        blue=int(item["blue"]),
    )


def load_history_cache(path: Path, base_url: str) -> list[DrawRecord]:
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("base_url") != base_url:
        logger.info("history cache base URL changed, rebuilding cache")
        return []

    return [_record_from_dict(item) for item in payload.get("records", [])]


def save_history_cache(path: Path, base_url: str, records: list[DrawRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "base_url": base_url,
        "records": [_record_to_dict(record) for record in records],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_history_cache(base_url: str, cache_path: Path) -> tuple[list[DrawRecord], bool]:
    cached_records = load_history_cache(cache_path, base_url)
    if not cached_records:
        records = load_history_records(base_url)
        save_history_cache(cache_path, base_url, records)
        logger.info("history cache initialized at %s", cache_path)
        return records, True

    latest_serial = cached_records[0].serial
    seen_serials = {record.serial for record in cached_records}
    new_records: list[DrawRecord] = []

    for page in range(1, MAX_HISTORY_PAGES + 1):
        try:
            logger.info("fetching incremental history page %s", page)
            html = fetch_text(base_url.format(page=page))
        except HTTPError as exc:
            if exc.code == 404:
                logger.info("incremental history page %s returned 404, treating it as the end of pagination", page)
                break
            raise RuntimeError("failed to fetch lottery data from %s: %s" % (base_url, exc)) from exc
        except (TimeoutError, socket.timeout, URLError) as exc:
            raise RuntimeError("failed to fetch lottery data from %s: %s" % (base_url, exc)) from exc

        page_rows = parse_history_rows(html)
        if not page_rows:
            break

        reached_cached_head = False
        added_count = 0
        for row in page_rows:
            serial = row["serial"]
            if serial == latest_serial:
                reached_cached_head = True
                break
            if serial in seen_serials:
                continue
            seen_serials.add(serial)
            new_records.append(
                DrawRecord(
                    serial=serial,
                    draw_date=row["date"],
                    red=list(row["red"]),
                    blue=row["blue"],
                )
            )
            added_count += 1

        logger.info("parsed %s incremental rows from page %s", added_count, page)
        if reached_cached_head:
            break

    if not new_records:
        return cached_records, False

    merged_records = new_records + cached_records
    save_history_cache(cache_path, base_url, merged_records)
    logger.info("history cache updated with %s new rows", len(new_records))
    return merged_records, True


def compute_pipeline_signature(
    records: list[DrawRecord],
    *,
    base_url: str,
    rolling_min_train_draws: int,
    rolling_step: int,
    rule_parameters: dict[str, object] | None = None,
) -> str:
    payload = {
        "base_url": base_url,
        "rolling_min_train_draws": rolling_min_train_draws,
        "rolling_step": rolling_step,
        "rule_parameters": rule_parameters or {},
        "records": [_record_to_dict(record) for record in records],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def compute_workbook_signature(records: list[DrawRecord], *, draw_count: int, base_url: str) -> str:
    payload = {
        "base_url": base_url,
        "draw_count": draw_count,
        "records": [_record_to_dict(record) for record in records[:draw_count]],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def load_pipeline_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_pipeline_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
