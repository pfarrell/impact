"""Append-only CSV storage helpers for pipeline output tables."""
from __future__ import annotations

import csv
from pathlib import Path


def append_rows(csv_path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    file_exists = csv_path.exists()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def overwrite_rows(csv_path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def last_cumulative_value(csv_path: Path, cumulative_field: str) -> int:
    if not csv_path.exists():
        return 0
    with csv_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return 0
    return int(rows[-1][cumulative_field])


def with_running_cumulative(
    rows: list[dict], count_field: str, cumulative_field: str, starting_total: int
) -> list[dict]:
    total = starting_total
    result = []
    for row in rows:
        total += int(row[count_field])
        result.append({**row, cumulative_field: total})
    return result
