"""Incremental refresh: pulls only months after the last refreshed month and appends."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.bq_client import BigQueryClient
from scripts.config_loader import build_keyword_regex, load_ai_ml_keywords, load_milestones
from scripts.csv_store import append_rows, last_cumulative_value, with_running_cumulative
from scripts.meta_store import read_meta, write_meta
from scripts.month_range import latest_closed_month, next_month_suffix

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
QUERIES_DIR = Path(__file__).resolve().parent / "queries"

VOLUME_FIELDS = [
    "year_month", "push_count", "commit_count", "pr_opened_count",
    "active_repo_count", "active_actor_count",
]
ACTORS_FIELDS = ["year_month", "new_actor_count", "cumulative_total"]
LANGUAGE_FIELDS = ["year_month", "language", "commit_count"]
AI_TOPICS_FIELDS = ["year_month", "ai_commit_count"]


def run_refresh(bq: BigQueryClient, data_dir: Path = DATA_DIR, today: date | None = None) -> int:
    """Pulls only months after the last refreshed month and appends.

    Returns bytes billed this run, or 0 if already current.
    Raises RuntimeError if no prior backfill has been run.
    """
    meta = read_meta(data_dir / "_meta.json")
    last_month = meta["last_refreshed_month"]
    if last_month is None:
        raise RuntimeError("No prior backfill found -- run `python -m scripts.backfill` first.")

    end_suffix = latest_closed_month(today or date.today())
    if last_month >= end_suffix:
        return 0

    start_suffix = next_month_suffix(last_month)
    total_bytes_billed = 0

    volume_sql = (QUERIES_DIR / "monthly_volume.sql").read_text()
    result = bq.run_query(volume_sql, {"start_suffix": start_suffix, "end_suffix": end_suffix})
    append_rows(data_dir / "monthly_volume.csv", VOLUME_FIELDS, result.rows)
    total_bytes_billed += result.bytes_billed

    actors_sql = (QUERIES_DIR / "cumulative_actors.sql").read_text()
    result = bq.run_query(actors_sql, {"start_suffix": start_suffix, "end_suffix": end_suffix})
    starting_total = last_cumulative_value(data_dir / "cumulative_actors.csv", "cumulative_total")
    rows_with_cumulative = with_running_cumulative(
        result.rows, "new_actor_count", "cumulative_total", starting_total
    )
    append_rows(data_dir / "cumulative_actors.csv", ACTORS_FIELDS, rows_with_cumulative)
    total_bytes_billed += result.bytes_billed

    language_sql = (QUERIES_DIR / "monthly_language.sql").read_text()
    result = bq.run_query(language_sql, {"start_suffix": start_suffix, "end_suffix": end_suffix})
    append_rows(data_dir / "monthly_language.csv", LANGUAGE_FIELDS, result.rows)
    total_bytes_billed += result.bytes_billed

    keyword_pattern = build_keyword_regex(load_ai_ml_keywords())
    ai_topics_sql = (QUERIES_DIR / "monthly_ai_topics.sql").read_text()
    result = bq.run_query(
        ai_topics_sql,
        {"start_suffix": start_suffix, "end_suffix": end_suffix, "keyword_pattern": keyword_pattern},
    )
    append_rows(data_dir / "monthly_ai_topics.csv", AI_TOPICS_FIELDS, result.rows)
    total_bytes_billed += result.bytes_billed

    (data_dir / "milestones.json").write_text(json.dumps(load_milestones(), indent=2))

    write_meta(data_dir / "_meta.json", last_refreshed_month=end_suffix, additional_bytes_billed=total_bytes_billed)
    return total_bytes_billed


if __name__ == "__main__":
    run_refresh(BigQueryClient())
