"""Pure helpers for computing GH Archive monthly table suffixes and ranges."""
from __future__ import annotations

from datetime import date, timedelta


def month_suffix(year: int, month: int) -> str:
    return f"{year:04d}{month:02d}"


def latest_closed_month(today: date) -> str:
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - timedelta(days=1)
    return month_suffix(last_month_end.year, last_month_end.month)


def month_range(start_suffix: str, end_suffix: str) -> list[str]:
    start_year, start_month = int(start_suffix[:4]), int(start_suffix[4:])
    end_year, end_month = int(end_suffix[:4]), int(end_suffix[4:])
    months = []
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        months.append(month_suffix(year, month))
        month += 1
        if month == 13:
            month = 1
            year += 1
    return months


def next_month_suffix(suffix: str) -> str:
    year, month = int(suffix[:4]), int(suffix[4:])
    month += 1
    if month == 13:
        month = 1
        year += 1
    return month_suffix(year, month)
