from pathlib import Path

QUERIES_DIR = Path(__file__).resolve().parent.parent / "scripts" / "queries"


def test_monthly_volume_has_expected_params():
    sql = (QUERIES_DIR / "monthly_volume.sql").read_text()
    assert "@start_suffix" in sql and "@end_suffix" in sql
    assert "githubarchive.month.*" in sql


def test_cumulative_actors_has_expected_params():
    sql = (QUERIES_DIR / "cumulative_actors.sql").read_text()
    assert "@start_suffix" in sql and "@end_suffix" in sql


def test_monthly_language_joins_github_repos_languages():
    sql = (QUERIES_DIR / "monthly_language.sql").read_text()
    assert "@start_suffix" in sql and "@end_suffix" in sql
    assert "bigquery-public-data.github_repos.languages" in sql


def test_monthly_ai_topics_matches_repo_name_not_github_repos():
    sql = (QUERIES_DIR / "monthly_ai_topics.sql").read_text()
    assert "@keyword_pattern" in sql
    assert "repo.name" in sql
    assert "github_repos" not in sql


def test_monthly_ai_topics_matches_repo_segment_not_owner():
    sql = (QUERIES_DIR / "monthly_ai_topics.sql").read_text()
    assert "REGEXP_EXTRACT(LOWER(repo.name), r'/(.+)$')" in sql
    assert "REGEXP_CONTAINS(LOWER(repo.name)" not in sql


def test_cumulative_actors_keeps_load_bearing_order_by():
    sql = (QUERIES_DIR / "cumulative_actors.sql").read_text()
    assert sql.rstrip().endswith("ORDER BY year_month")
