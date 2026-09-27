"""One-time full historical backfill: 2015-01 through the latest fully-closed month."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.bq_client import BigQueryClient, max_bytes_billed_from_env
from scripts.config_loader import build_keyword_regex, load_ai_ml_keywords, load_milestones
from scripts.csv_store import overwrite_rows, with_running_cumulative
from scripts.meta_store import write_meta
from scripts.month_range import latest_closed_month

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
QUERIES_DIR = Path(__file__).resolve().parent / "queries"
START_SUFFIX = "201501"
# The cumulative-actors query alone starts at GH Archive's earliest monthly
# table (the archive begins Feb 2011), not START_SUFFIX. Its running total has
# to include everyone first seen before 2015, otherwise every pre-2015 account
# is permanently missing from the count and the series starts near zero. The
# extra months cost next to nothing: the query's first-seen CTE already scans
# all history up to end_suffix regardless of start_suffix. The pre-2015 rows
# are folded into the running total and then dropped before writing, so the
# CSV still covers 2015-01 onward like the other three tables.
ACTORS_START_SUFFIX = "201101"

# BigQuery on-demand list price per TiB scanned (first 1 TiB/month is free).
PRICE_PER_TIB_USD = 6.25

VOLUME_FIELDS = [
    "year_month", "push_count", "commit_count", "pr_opened_count",
    "active_repo_count", "active_actor_count",
]
ACTORS_FIELDS = ["year_month", "new_actor_count", "cumulative_total"]
LANGUAGE_FIELDS = ["year_month", "language", "commit_count"]
AI_TOPICS_FIELDS = ["year_month", "ai_commit_count"]


def _backfill_queries(end_suffix: str) -> list[tuple[str, str, dict[str, str]]]:
    """The (name, sql, params) for each backfill query, in execution order."""
    base = {"start_suffix": START_SUFFIX, "end_suffix": end_suffix}
    return [
        ("monthly_volume", (QUERIES_DIR / "monthly_volume.sql").read_text(), dict(base)),
        (
            "cumulative_actors",
            (QUERIES_DIR / "cumulative_actors.sql").read_text(),
            {"start_suffix": ACTORS_START_SUFFIX, "end_suffix": end_suffix},
        ),
        ("monthly_language", (QUERIES_DIR / "monthly_language.sql").read_text(), dict(base)),
        (
            "monthly_ai_topics",
            (QUERIES_DIR / "monthly_ai_topics.sql").read_text(),
            {**base, "keyword_pattern": build_keyword_regex(load_ai_ml_keywords())},
        ),
    ]


def run_backfill(bq: BigQueryClient, data_dir: Path = DATA_DIR, today: date | None = None) -> int:
    """Runs the full historical backfill. Returns total bytes billed across all queries.

    Every query runs before anything is written, so a failure at any query
    leaves the existing files in data_dir exactly as they were.
    """
    end_suffix = latest_closed_month(today or date.today())

    results = {name: bq.run_query(sql, params) for name, sql, params in _backfill_queries(end_suffix)}
    total_bytes_billed = sum(r.bytes_billed for r in results.values())

    actors_all_history = with_running_cumulative(
        results["cumulative_actors"].rows, "new_actor_count", "cumulative_total", starting_total=0
    )
    actors_rows = [r for r in actors_all_history if r["year_month"] >= START_SUFFIX]
    milestones = load_milestones()

    overwrite_rows(data_dir / "monthly_volume.csv", VOLUME_FIELDS, results["monthly_volume"].rows)
    overwrite_rows(data_dir / "cumulative_actors.csv", ACTORS_FIELDS, actors_rows)
    overwrite_rows(data_dir / "monthly_language.csv", LANGUAGE_FIELDS, results["monthly_language"].rows)
    overwrite_rows(data_dir / "monthly_ai_topics.csv", AI_TOPICS_FIELDS, results["monthly_ai_topics"].rows)
    (data_dir / "milestones.json").write_text(json.dumps(milestones, indent=2))

    write_meta(data_dir / "_meta.json", last_refreshed_month=end_suffix, additional_bytes_billed=total_bytes_billed)
    return total_bytes_billed


def estimate_backfill_bytes(bq: BigQueryClient, today: date | None = None) -> list[tuple[str, int]]:
    """Dry-runs each backfill query (free) and returns (name, bytes_processed) pairs."""
    end_suffix = latest_closed_month(today or date.today())
    return [(name, bq.estimate_bytes(sql, params)) for name, sql, params in _backfill_queries(end_suffix)]


def format_scan_estimate(total_bytes: int, query_count: int) -> str:
    gb = total_bytes / 1e9
    dollars = total_bytes / 1024**4 * PRICE_PER_TIB_USD
    return (
        f"Estimated scan: ~{gb:,.1f} GB across {query_count} queries "
        f"(~${dollars:,.2f} at ${PRICE_PER_TIB_USD:.2f}/TiB on-demand, before any free-tier credit)"
    )


def main() -> None:
    max_bytes = max_bytes_billed_from_env()
    bq = BigQueryClient(maximum_bytes_billed=max_bytes)

    estimates = estimate_backfill_bytes(bq)
    for name, nbytes in estimates:
        print(f"  {name}: ~{nbytes / 1e9:,.1f} GB")
    print(format_scan_estimate(sum(b for _, b in estimates), len(estimates)))
    print(f"Per-query cap (BQ_MAX_BYTES_BILLED): {max_bytes / 1e9:,.1f} GB")
    over_cap = [name for name, nbytes in estimates if nbytes > max_bytes]
    if over_cap:
        print(
            f"WARNING: {', '.join(over_cap)} would exceed the per-query cap and fail. "
            "Raise BQ_MAX_BYTES_BILLED if you accept the cost."
        )

    if input("Proceed? [y/N] ").strip().lower() not in ("y", "yes"):
        print("Aborted; nothing was queried or written.")
        return
    total = run_backfill(bq)
    print(f"Backfill complete. Bytes billed: {total / 1e9:,.1f} GB")


if __name__ == "__main__":
    main()
