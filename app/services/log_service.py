from collections import deque
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
import logging
from pathlib import Path
import re
import threading
from typing import Any


SENSITIVE_PATTERNS = [
    re.compile(r"(password=)[^&\s]+", re.I),
    re.compile(r"(token=)[^&\s]+", re.I),
    re.compile(r"(authorization:?\s+)(?:bearer\s+)?[^&\s]+", re.I),
    re.compile(r"(cookie:?\s+).+", re.I),
]

_record_id = 0
_record_id_lock = threading.Lock()
_ring_handler: "RingBufferLogHandler | None" = None
_file_handler: RotatingFileHandler | None = None


def next_record_id() -> int:
    global _record_id
    with _record_id_lock:
        _record_id += 1
        return _record_id


def redact_log_message(value: str) -> str:
    redacted = value
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted


def record_timestamp(record: logging.LogRecord) -> str:
    return (
        datetime.fromtimestamp(record.created, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def log_record_to_entry(record: logging.LogRecord, message: str) -> dict[str, Any]:
    exception = None
    if record.exc_info:
        formatter = logging.Formatter()
        exception = redact_log_message(formatter.formatException(record.exc_info))

    return {
        "id": next_record_id(),
        "timestamp": record_timestamp(record),
        "level": record.levelname,
        "logger": record.name,
        "message": redact_log_message(message),
        "module": record.module,
        "function": record.funcName,
        "line": int(record.lineno),
        "exception": exception,
    }


class RingBufferLogHandler(logging.Handler):
    def __init__(self, capacity: int) -> None:
        super().__init__()
        self.records: deque[dict[str, Any]] = deque(maxlen=capacity)
        self.records_lock = threading.RLock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = log_record_to_entry(record, self.format(record))
        except Exception:
            self.handleError(record)
            return

        with self.records_lock:
            self.records.append(entry)

    def list_records(
        self,
        *,
        limit: int,
        level: str | None = None,
        logger_name: str | None = None,
        query: str | None = None,
        order: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        normalized_level = str(level or "").strip().upper()
        normalized_logger = str(logger_name or "").strip()
        normalized_query = str(query or "").strip().lower()

        with self.records_lock:
            records = list(self.records)

        if order == "desc":
            records.reverse()

        matched: list[dict[str, Any]] = []
        for record in records:
            if normalized_level and record["level"] != normalized_level:
                continue
            if normalized_logger and normalized_logger not in record["logger"]:
                continue
            if normalized_query:
                searchable = " ".join(
                    [
                        str(record["message"]),
                        str(record["logger"]),
                        str(record.get("exception") or ""),
                    ]
                ).lower()
                if normalized_query not in searchable:
                    continue
            matched.append(dict(record))

        return matched[:limit], len(matched)

    def total_available(self) -> int:
        with self.records_lock:
            return len(self.records)

    def clear_for_tests(self) -> None:
        with self.records_lock:
            self.records.clear()


def log_formatter() -> logging.Formatter:
    class RedactingFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            return redact_log_message(super().format(record))

    return RedactingFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")


def install_log_handlers(
    *,
    level: int,
    log_file_path: Path,
    buffer_size: int,
    max_bytes: int,
    backup_count: int,
) -> None:
    global _ring_handler, _file_handler

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = log_formatter()
    console_handlers = [
        handler
        for handler in root_logger.handlers
        if getattr(handler, "_training_log_console", False)
    ]
    if not console_handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        setattr(console_handler, "_training_log_console", True)
        root_logger.addHandler(console_handler)
    else:
        for handler in console_handlers:
            handler.setFormatter(formatter)
            handler.setLevel(level)

    if _ring_handler is None:
        _ring_handler = RingBufferLogHandler(buffer_size)
        _ring_handler.setFormatter(logging.Formatter("%(message)s"))
        _ring_handler.setLevel(level)
        setattr(_ring_handler, "_training_log_ring", True)
        root_logger.addHandler(_ring_handler)
    else:
        _ring_handler.setLevel(level)

    if _file_handler is None and backup_count >= 0:
        try:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            _file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
            )
            _file_handler.setFormatter(formatter)
            _file_handler.setLevel(level)
            setattr(_file_handler, "_training_log_file", True)
            root_logger.addHandler(_file_handler)
        except OSError:
            logging.getLogger("training_log").warning(
                "log.file.unavailable path=%s",
                log_file_path,
            )
    elif _file_handler is not None:
        _file_handler.setLevel(level)


def list_log_entries(
    *,
    limit: int,
    level: str | None = None,
    logger_name: str | None = None,
    query: str | None = None,
    order: str = "desc",
) -> dict[str, Any]:
    if _ring_handler is None:
        return {
            "limit": limit,
            "count": 0,
            "total_available": 0,
            "filtered_available": 0,
            "truncated": False,
            "entries": [],
        }

    entries, filtered_available = _ring_handler.list_records(
        limit=limit,
        level=level,
        logger_name=logger_name,
        query=query,
        order=order,
    )
    total_available = _ring_handler.total_available()
    return {
        "limit": limit,
        "count": len(entries),
        "total_available": total_available,
        "filtered_available": filtered_available,
        "truncated": len(entries) < filtered_available,
        "entries": entries,
    }


def clear_log_buffer_for_tests() -> None:
    if _ring_handler is not None:
        _ring_handler.clear_for_tests()
