import json
from datetime import date
from pathlib import Path

from scripts.backfill import run_backfill
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
                    "commit_count": 20,
                    "pr_opened_count": 2,
                    "active_repo_count": 3,
                    "active_actor_count": 4,
                }
            ],
            bytes_billed=100,
        ),
        QueryResult(rows=[{"year_month": "201501", "new_actor_count": 4}], bytes_billed=50),
        QueryResult(rows=[{"year_month": "201501", "language": "Python", "commit_count": 15}], bytes_billed=75),
        QueryResult(rows=[{"year_month": "201501", "ai_commit_count": 5}], bytes_billed=25),
    ]


def test_run_backfill_writes_all_csvs_and_meta(tmp_path):
    fake_bq = FakeBigQueryClient(_canned_responses())

    total_bytes = run_backfill(fake_bq, data_dir=tmp_path, today=date(2015, 3, 1))

    assert total_bytes == 250
    assert (tmp_path / "monthly_volume.csv").read_text().strip().splitlines()[1] == "201501,10,20,2,3,4"
    assert (tmp_path / "cumulative_actors.csv").read_text().strip().splitlines()[1] == "201501,4,4"
    assert (tmp_path / "monthly_language.csv").exists()
    assert (tmp_path / "monthly_ai_topics.csv").exists()
    assert (tmp_path / "milestones.json").exists()

    meta = json.loads((tmp_path / "_meta.json").read_text())
    assert meta == {"last_refreshed_month": "201502", "total_bytes_billed": 250}


def test_run_backfill_queries_full_history_range(tmp_path):
    fake_bq = FakeBigQueryClient(_canned_responses())

    run_backfill(fake_bq, data_dir=tmp_path, today=date(2015, 3, 1))

    assert fake_bq.calls[0] == {"start_suffix": "201501", "end_suffix": "201502"}
    assert fake_bq.calls[1] == {"start_suffix": "201501", "end_suffix": "201502"}
    assert fake_bq.calls[2] == {"start_suffix": "201501", "end_suffix": "201502"}
    assert fake_bq.calls[3]["start_suffix"] == "201501"
    assert fake_bq.calls[3]["end_suffix"] == "201502"
    assert "keyword_pattern" in fake_bq.calls[3]
