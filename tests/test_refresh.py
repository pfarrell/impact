import json
from datetime import date

import pytest

from scripts.bq_client import QueryResult
from scripts.meta_store import write_meta
from scripts.refresh import run_refresh


class FakeBigQueryClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def run_query(self, sql, params):
        self.calls.append(params)
        return self._responses.pop(0)


def _seed_existing_data(tmp_path):
    (tmp_path / "monthly_volume.csv").write_text(
        "year_month,push_count,pr_event_count,active_repo_count,active_actor_count\n"
        "202508,100,10,20,30\n"
    )
    (tmp_path / "cumulative_actors.csv").write_text(
        "year_month,new_actor_count,cumulative_total\n202508,50,1000\n"
    )
    (tmp_path / "monthly_language.csv").write_text("year_month,language,push_count\n202508,Python,150\n")
    (tmp_path / "monthly_ai_topics.csv").write_text("year_month,ai_push_count\n202508,40\n")
    write_meta(tmp_path / "_meta.json", last_refreshed_month="202508", additional_bytes_billed=500)


def test_run_refresh_raises_without_prior_backfill(tmp_path):
    fake_bq = FakeBigQueryClient([])

    with pytest.raises(RuntimeError):
        run_refresh(fake_bq, data_dir=tmp_path, today=date(2026, 9, 26))


def test_run_refresh_returns_zero_when_already_current(tmp_path):
    _seed_existing_data(tmp_path)
    fake_bq = FakeBigQueryClient([])

    result = run_refresh(fake_bq, data_dir=tmp_path, today=date(2025, 9, 15))

    assert result == 0
    assert fake_bq.calls == []


def test_run_refresh_appends_only_new_months(tmp_path):
    _seed_existing_data(tmp_path)
    responses = [
        QueryResult(
            rows=[
                {
                    "year_month": "202509",
                    "push_count": 5,
                    "pr_event_count": 1,
                    "active_repo_count": 2,
                    "active_actor_count": 3,
                }
            ],
            bytes_billed=10,
        ),
        QueryResult(rows=[{"year_month": "202509", "new_actor_count": 7}], bytes_billed=20),
        QueryResult(
            rows=[{"year_month": "202509", "language": "Python", "push_count": 6, "ai_push_count": 2}],
            bytes_billed=70,
        ),
    ]
    fake_bq = FakeBigQueryClient(responses)

    total_bytes = run_refresh(fake_bq, data_dir=tmp_path, today=date(2026, 9, 26))

    assert total_bytes == 100
    assert fake_bq.calls[0] == {"start_suffix": "202509", "end_suffix": "202608"}
    assert len(fake_bq.calls) == 3
    assert "keyword_pattern" in fake_bq.calls[2]

    assert (tmp_path / "monthly_language.csv").read_text().strip().splitlines()[-1] == "202509,Python,6"
    assert (tmp_path / "monthly_ai_topics.csv").read_text().strip().splitlines()[-1] == "202509,2"

    volume_lines = (tmp_path / "monthly_volume.csv").read_text().strip().splitlines()
    assert volume_lines == [
        "year_month,push_count,pr_event_count,active_repo_count,active_actor_count",
        "202508,100,10,20,30",
        "202509,5,1,2,3",
    ]

    actors_lines = (tmp_path / "cumulative_actors.csv").read_text().strip().splitlines()
    assert actors_lines[-1] == "202509,7,1007"

    meta = json.loads((tmp_path / "_meta.json").read_text())
    assert meta == {"last_refreshed_month": "202608", "total_bytes_billed": 600}


class FailingOnNthCallClient(FakeBigQueryClient):
    def __init__(self, responses, fail_on_call):
        super().__init__(responses)
        self._fail_on_call = fail_on_call

    def run_query(self, sql, params):
        if len(self.calls) + 1 == self._fail_on_call:
            self.calls.append(params)
            raise RuntimeError("simulated BigQuery failure")
        return super().run_query(sql, params)


def _snapshot(directory):
    return {p.name: p.read_text() for p in sorted(directory.iterdir())}


def test_run_refresh_failure_mid_run_leaves_existing_files_untouched(tmp_path):
    _seed_existing_data(tmp_path)
    (tmp_path / "milestones.json").write_text("{}")
    before = _snapshot(tmp_path)
    responses = [
        QueryResult(
            rows=[
                {
                    "year_month": "202509",
                    "push_count": 5,
                    "pr_event_count": 1,
                    "active_repo_count": 2,
                    "active_actor_count": 3,
                }
            ],
            bytes_billed=10,
        ),
        QueryResult(rows=[{"year_month": "202509", "new_actor_count": 7}], bytes_billed=20),
    ]
    fake_bq = FailingOnNthCallClient(responses, fail_on_call=3)

    with pytest.raises(RuntimeError, match="simulated"):
        run_refresh(fake_bq, data_dir=tmp_path, today=date(2026, 9, 26))

    assert len(fake_bq.calls) == 3
    assert _snapshot(tmp_path) == before
