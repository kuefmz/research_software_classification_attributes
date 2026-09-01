"""Input/output helpers with atomic writes and consistent logging."""
from __future__ import annotations

import csv
import json
import logging
import os
import tempfile
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any


def configure_logging(level: int = logging.INFO) -> None:
    """Configure a concise root logger for script execution."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def atomic_write_text(path: Path, text: str) -> None:
    """Write text to ``path`` through a temporary file in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Yield dictionaries from a JSONL file, skipping blank lines."""
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on {path}:{line_number}") from exc


def write_jsonl(records: Iterable[Mapping[str, Any]], path: Path) -> int:
    """Atomically write records to JSONL and return the number of records."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        for record in records:
            tmp.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    os.replace(tmp_path, path)
    return count


def write_json(data: Any, path: Path) -> None:
    """Atomically write indented JSON."""
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def write_csv(records: Sequence[Mapping[str, Any]], path: Path, fieldnames: Sequence[str] | None = None) -> int:
    """Atomically write dictionaries to CSV, encoding nested values as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        field_set: list[str] = []
        for record in records:
            for key in record:
                if key not in field_set:
                    field_set.append(key)
        fieldnames = field_set

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        writer = csv.DictWriter(tmp, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({key: _csv_value(record.get(key)) for key in fieldnames})
    os.replace(tmp_path, path)
    return len(records)


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    """Read a CSV file with the standard library for dependency-light scripts."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def log_count_change(logger: logging.Logger, step: str, before: int, after: int) -> None:
    """Log before/after counts for a filtering or transformation step."""
    logger.info("%s: before=%s after=%s removed=%s", step, f"{before:,}", f"{after:,}", f"{before - after:,}")

