import re
from pathlib import Path

import pytest

QUERIES_DIR = Path(__file__).resolve().parent.parent / "scripts" / "queries"


def _strip_sql_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def test_monthly_volume_has_expected_params():
    sql = (QUERIES_DIR / "monthly_volume.sql").read_text()
    assert "@start_suffix" in sql and "@end_suffix" in sql
    assert "githubarchive.month.*" in sql


def test_cumulative_actors_has_expected_params():
    sql = (QUERIES_DIR / "cumulative_actors.sql").read_text()
    assert "@start_suffix" in sql and "@end_suffix" in sql


def test_monthly_language_ai_joins_github_repos_languages():
    sql = (QUERIES_DIR / "monthly_language_ai.sql").read_text()
    assert "@start_suffix" in sql and "@end_suffix" in sql
    assert "bigquery-public-data.github_repos.languages" in sql


def test_monthly_language_ai_matches_keywords_on_repo_name():
    sql = (QUERIES_DIR / "monthly_language_ai.sql").read_text()
    assert "@keyword_pattern" in sql
    assert "repo.name" in sql


def test_monthly_language_ai_matches_repo_segment_not_owner():
    sql = (QUERIES_DIR / "monthly_language_ai.sql").read_text()
    assert "REGEXP_EXTRACT(LOWER(a.repo_name), r'/(.+)$')" in sql
    assert "REGEXP_CONTAINS(LOWER(" not in sql


def test_language_and_ai_share_one_query():
    # Separate language and AI queries each scanned ~430 GB of the same
    # columns; merged, the backfill fits the 1 TiB/month sandbox free tier.
    assert not (QUERIES_DIR / "monthly_language.sql").exists()
    assert not (QUERIES_DIR / "monthly_ai_topics.sql").exists()


def test_cumulative_actors_keeps_load_bearing_order_by():
    sql = (QUERIES_DIR / "cumulative_actors.sql").read_text()
    assert sql.rstrip().endswith("ORDER BY year_month")


@pytest.mark.parametrize("name", ["monthly_volume", "monthly_language_ai", "cumulative_actors"])
def test_queries_never_read_payload_column(name):
    # GH Archive's payload column holds nearly all of the dataset's bytes:
    # reading it took the full backfill from ~1 TB to ~95 TB (~$540). Every
    # metric is built from type/repo/actor columns only.
    sql = (QUERIES_DIR / f"{name}.sql").read_text()
    assert "payload" not in _strip_sql_comments(sql)


def test_monthly_volume_selects_push_based_columns():
    sql = (QUERIES_DIR / "monthly_volume.sql").read_text()
    for col in ["push_count", "pr_event_count", "active_repo_count", "active_actor_count"]:
        assert f"AS {col}" in sql
    assert "commit_count" not in sql


def test_monthly_language_ai_counts_pushes():
    sql = (QUERIES_DIR / "monthly_language_ai.sql").read_text()
    assert "AS push_count" in sql
    assert "AS ai_push_count" in sql
