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
        "year_month,push_count,commit_count,pr_opened_count,active_repo_count,active_actor_count\n"
        "202508,100,200,10,20,30\n"
    )
    (tmp_path / "cumulative_actors.csv").write_text(
        "year_month,new_actor_count,cumulative_total\n202508,50,1000\n"
    )
    (tmp_path / "monthly_language.csv").write_text("year_month,language,commit_count\n202508,Python,150\n")
    (tmp_path / "monthly_ai_topics.csv").write_text("year_month,ai_commit_count\n202508,40\n")
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
                    "commit_count": 9,
                    "pr_opened_count": 1,
                    "active_repo_count": 2,
                    "active_actor_count": 3,
                }
            ],
            bytes_billed=10,
        ),
        QueryResult(rows=[{"year_month": "202509", "new_actor_count": 7}], bytes_billed=20),
        QueryResult(rows=[{"year_month": "202509", "language": "Python", "commit_count": 6}], bytes_billed=30),
        QueryResult(rows=[{"year_month": "202509", "ai_commit_count": 2}], bytes_billed=40),
    ]
    fake_bq = FakeBigQueryClient(responses)

    total_bytes = run_refresh(fake_bq, data_dir=tmp_path, today=date(2026, 9, 26))

    assert total_bytes == 100
    assert fake_bq.calls[0] == {"start_suffix": "202509", "end_suffix": "202608"}

    volume_lines = (tmp_path / "monthly_volume.csv").read_text().strip().splitlines()
    assert volume_lines == [
        "year_month,push_count,commit_count,pr_opened_count,active_repo_count,active_actor_count",
        "202508,100,200,10,20,30",
        "202509,5,9,1,2,3",
    ]

    actors_lines = (tmp_path / "cumulative_actors.csv").read_text().strip().splitlines()
    assert actors_lines[-1] == "202509,7,1007"

    meta = json.loads((tmp_path / "_meta.json").read_text())
    assert meta == {"last_refreshed_month": "202608", "total_bytes_billed": 600}
