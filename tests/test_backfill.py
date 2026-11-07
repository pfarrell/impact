import json
from datetime import date
from pathlib import Path

import pytest

from scripts.backfill import (
    estimate_backfill_bytes,
    format_scan_estimate,
    free_tier_block_message,
    run_backfill,
)
from scripts.bq_client import QueryResult


class FakeBigQueryClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def run_query(self, sql, params):
        self.calls.append(params)
        return self._responses.pop(0)


def _canned_responses():
    return [
        QueryResult(
            rows=[
                {
                    "year_month": "201501",
                    "push_count": 10,
                    "pr_event_count": 2,
                    "active_repo_count": 3,
                    "active_actor_count": 4,
                }
            ],
            bytes_billed=100,
        ),
        QueryResult(rows=[{"year_month": "201501", "new_actor_count": 4}], bytes_billed=50),
        QueryResult(
            rows=[{"year_month": "201501", "language": "Python", "push_count": 15, "ai_push_count": 5}],
            bytes_billed=100,
        ),
    ]


def test_run_backfill_writes_all_csvs_and_meta(tmp_path):
    fake_bq = FakeBigQueryClient(_canned_responses())

    total_bytes = run_backfill(fake_bq, data_dir=tmp_path, today=date(2015, 3, 1))

    assert total_bytes == 250
    assert (tmp_path / "monthly_volume.csv").read_text().strip().splitlines() == [
        "year_month,push_count,pr_event_count,active_repo_count,active_actor_count",
        "201501,10,2,3,4",
    ]
    assert (tmp_path / "cumulative_actors.csv").read_text().strip().splitlines()[1] == "201501,4,4"
    assert (tmp_path / "monthly_language.csv").read_text().strip().splitlines() == [
        "year_month,language,push_count",
        "201501,Python,15",
    ]
    assert (tmp_path / "monthly_ai_topics.csv").read_text().strip().splitlines() == [
        "year_month,ai_push_count",
        "201501,5",
    ]
    assert (tmp_path / "milestones.json").exists()
    assert (tmp_path / "data_quality.json").exists()

    meta = json.loads((tmp_path / "_meta.json").read_text())
    assert meta == {"last_refreshed_month": "201502", "total_bytes_billed": 250}


def test_run_backfill_queries_full_history_range(tmp_path):
    fake_bq = FakeBigQueryClient(_canned_responses())

    run_backfill(fake_bq, data_dir=tmp_path, today=date(2015, 3, 1))

    assert fake_bq.calls[0] == {"start_suffix": "201501", "end_suffix": "201502"}
    # The actors query starts at GH Archive's earliest month so pre-2015 accounts
    # are counted in the running total (see ACTORS_START_SUFFIX in backfill.py).
    assert fake_bq.calls[1] == {"start_suffix": "201101", "end_suffix": "201502"}
    assert len(fake_bq.calls) == 3
    assert fake_bq.calls[2]["start_suffix"] == "201501"
    assert fake_bq.calls[2]["end_suffix"] == "201502"
    assert "keyword_pattern" in fake_bq.calls[2]


def test_run_backfill_counts_pre_2015_actors_in_cumulative_but_not_as_rows(tmp_path):
    responses = _canned_responses()
    responses[1] = QueryResult(
        rows=[
            {"year_month": "201103", "new_actor_count": 100},
            {"year_month": "201412", "new_actor_count": 900},
            {"year_month": "201501", "new_actor_count": 4},
            {"year_month": "201502", "new_actor_count": 6},
        ],
        bytes_billed=50,
    )
    fake_bq = FakeBigQueryClient(responses)

    run_backfill(fake_bq, data_dir=tmp_path, today=date(2015, 3, 1))

    lines = (tmp_path / "cumulative_actors.csv").read_text().strip().splitlines()
    assert lines == [
        "year_month,new_actor_count,cumulative_total",
        "201501,4,1004",
        "201502,6,1010",
    ]


class FailingOnNthCallClient(FakeBigQueryClient):
    def __init__(self, responses, fail_on_call):
        super().__init__(responses)
        self._fail_on_call = fail_on_call

    def run_query(self, sql, params):
        if len(self.calls) + 1 == self._fail_on_call:
            self.calls.append(params)
            raise RuntimeError("simulated BigQuery failure")
        return super().run_query(sql, params)


def _snapshot(directory: Path) -> dict[str, str]:
    return {p.name: p.read_text() for p in sorted(directory.iterdir())}


def test_run_backfill_failure_mid_run_leaves_existing_files_untouched(tmp_path):
    (tmp_path / "monthly_volume.csv").write_text("synthetic volume\n")
    (tmp_path / "cumulative_actors.csv").write_text("synthetic actors\n")
    (tmp_path / "monthly_language.csv").write_text("synthetic language\n")
    (tmp_path / "monthly_ai_topics.csv").write_text("synthetic ai\n")
    (tmp_path / "milestones.json").write_text("{}")
    (tmp_path / "_meta.json").write_text('{"last_refreshed_month": "201412", "total_bytes_billed": 7}')
    before = _snapshot(tmp_path)
    fake_bq = FailingOnNthCallClient(_canned_responses(), fail_on_call=3)

    with pytest.raises(RuntimeError, match="simulated"):
        run_backfill(fake_bq, data_dir=tmp_path, today=date(2015, 3, 1))

    assert len(fake_bq.calls) == 3
    assert _snapshot(tmp_path) == before


def test_run_backfill_failure_mid_run_creates_no_files(tmp_path):
    data_dir = tmp_path / "data"
    fake_bq = FailingOnNthCallClient(_canned_responses(), fail_on_call=3)

    with pytest.raises(RuntimeError, match="simulated"):
        run_backfill(fake_bq, data_dir=data_dir, today=date(2015, 3, 1))

    assert not data_dir.exists()


class FakeEstimatingClient:
    def __init__(self, bytes_per_query):
        self._bytes = list(bytes_per_query)
        self.calls = []

    def estimate_bytes(self, sql, params):
        self.calls.append(params)
        return self._bytes.pop(0)


def test_estimate_backfill_bytes_dry_runs_same_queries_as_backfill():
    fake_bq = FakeEstimatingClient([10, 20, 70])

    estimates = estimate_backfill_bytes(fake_bq, today=date(2015, 3, 1))

    assert [name for name, _ in estimates] == ["monthly_volume", "cumulative_actors", "monthly_language_ai"]
    assert sum(b for _, b in estimates) == 100
    assert fake_bq.calls[0] == {"start_suffix": "201501", "end_suffix": "201502"}
    assert fake_bq.calls[1] == {"start_suffix": "201101", "end_suffix": "201502"}
    assert "keyword_pattern" in fake_bq.calls[2]


def test_format_scan_estimate_reports_gb_and_dollars():
    text = format_scan_estimate(2 * 1024**4, query_count=4)

    assert "2,199.0 GB" in text
    assert "4 queries" in text
    assert "$12.50" in text


def test_free_tier_block_message_allows_scan_within_free_tier():
    assert free_tier_block_message(1024**4, environ={}) is None


def test_free_tier_block_message_blocks_scan_over_free_tier_without_billing():
    message = free_tier_block_message(1024**4 + 1, environ={})

    assert message is not None
    assert "BQ_BILLING_ENABLED=1" in message


def test_free_tier_block_message_allows_scan_over_free_tier_with_billing():
    assert free_tier_block_message(5 * 1024**4, environ={"BQ_BILLING_ENABLED": "1"}) is None
