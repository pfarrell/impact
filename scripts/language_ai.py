"""Splits the combined language/AI query result into the two output tables."""
from __future__ import annotations


def split_language_ai(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Returns (language_rows, ai_rows) from monthly_language_ai.sql rows.

    language_rows keep the query's order and drop ai_push_count. ai_rows hold
    one row per month (ai_push_count summed across languages), in month order,
    including months with zero matches.
    """
    language_rows = [
        {"year_month": r["year_month"], "language": r["language"], "push_count": r["push_count"]}
        for r in rows
    ]
    ai_by_month: dict[str, int] = {}
    for r in rows:
        ai_by_month[r["year_month"]] = ai_by_month.get(r["year_month"], 0) + int(r["ai_push_count"])
    ai_rows = [{"year_month": m, "ai_push_count": ai_by_month[m]} for m in sorted(ai_by_month)]
    return language_rows, ai_rows
