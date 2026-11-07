"""Incremental refresh: pulls only months after the last refreshed month and appends."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts.bq_client import BigQueryClient, max_bytes_billed_from_env
from scripts.config_loader import build_keyword_regex, load_ai_ml_keywords
from scripts.csv_store import append_rows, last_cumulative_value, with_running_cumulative
from scripts.language_ai import split_language_ai
from scripts.meta_store import read_meta, write_meta
from scripts.month_range import latest_closed_month, next_month_suffix
from scripts.report_config import write_report_config

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
QUERIES_DIR = Path(__file__).resolve().parent / "queries"

VOLUME_FIELDS = [
    "year_month", "push_count", "pr_event_count",
    "active_repo_count", "active_actor_count",
]
ACTORS_FIELDS = ["year_month", "new_actor_count", "cumulative_total"]
LANGUAGE_FIELDS = ["year_month", "language", "push_count"]
AI_TOPICS_FIELDS = ["year_month", "ai_push_count"]


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
    params = {"start_suffix": start_suffix, "end_suffix": end_suffix}
    keyword_pattern = build_keyword_regex(load_ai_ml_keywords())

    # Run every query before writing anything. If any query fails, no CSV has
    # been appended and _meta.json hasn't advanced, so the next run retries the
    # same months cleanly instead of appending duplicates (and double-counting
    # the cumulative actor total).
    volume = bq.run_query((QUERIES_DIR / "monthly_volume.sql").read_text(), params)
    actors = bq.run_query((QUERIES_DIR / "cumulative_actors.sql").read_text(), params)
    language_ai = bq.run_query(
        (QUERIES_DIR / "monthly_language_ai.sql").read_text(),
        {**params, "keyword_pattern": keyword_pattern},
    )
    total_bytes_billed = sum(r.bytes_billed for r in (volume, actors, language_ai))

    starting_total = last_cumulative_value(data_dir / "cumulative_actors.csv", "cumulative_total")
    actors_rows = with_running_cumulative(actors.rows, "new_actor_count", "cumulative_total", starting_total)
    language_rows, ai_rows = split_language_ai(language_ai.rows)

    append_rows(data_dir / "monthly_volume.csv", VOLUME_FIELDS, volume.rows)
    append_rows(data_dir / "cumulative_actors.csv", ACTORS_FIELDS, actors_rows)
    append_rows(data_dir / "monthly_language.csv", LANGUAGE_FIELDS, language_rows)
    append_rows(data_dir / "monthly_ai_topics.csv", AI_TOPICS_FIELDS, ai_rows)
    write_report_config(data_dir)

    write_meta(data_dir / "_meta.json", last_refreshed_month=end_suffix, additional_bytes_billed=total_bytes_billed)
    return total_bytes_billed


if __name__ == "__main__":
    # Refresh is incremental and normally cheap, so no estimate/confirm step,
    # but the per-query billing cap still applies (BQ_MAX_BYTES_BILLED).
    total = run_refresh(BigQueryClient(maximum_bytes_billed=max_bytes_billed_from_env()))
    print(f"Refresh complete. Bytes billed: {total / 1e9:,.1f} GB")
