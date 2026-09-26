# GitHub AI Impact Report (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a refreshable BigQuery-backed data pipeline over GH Archive + `github_repos`, and a D3-based interactive Artifact dashboard, showing GitHub coding-activity trends 2015-present with volume/velocity as the primary "AI impact" signal, normalized against user-base growth, plus language-mix and AI/ML-framework supporting cuts.

**Architecture:** Python scripts query BigQuery (application-default credentials) and write small aggregate CSVs to `data/`. `backfill.py` populates full history once; `refresh.py` appends only new months on later runs. A static `report.html`, published as a Claude Artifact with the `data/` files as supporting files, reads those CSVs client-side and renders the charts with D3 — no server, no BigQuery access needed at view time.

**Tech Stack:** Python 3.10+, `google-cloud-bigquery`, `pyyaml`, `pytest`; D3 (via Artifact-allowed CDN) for the report page, no build tooling.

**Spec:** `docs/superpowers/specs/2026-09-26-github-ai-impact-report-design.md`

## Global Constraints

- Time range: monthly grain, 2015-01 through the latest fully-closed month at run time. No geographic breakdown.
- Refresh is manual only for this pass — no cron/scheduling.
- BigQuery access via `gcloud auth application-default login`; every query is restricted to the minimum columns/event types and relies on `githubarchive.month.*` + `_TABLE_SUFFIX` partition filtering to control bytes scanned.
- The **AI/ML & framework cut matches `repo.name` directly from GH Archive event data** — it must NOT join against `bigquery-public-data.github_repos`, which is a stale, long-unrefreshed snapshot that would miss nearly all AI/ML repos created after ~2022.
- The **language-mix cut** may join against `bigquery-public-data.github_repos.languages`, but the report must display an explicit caveat that coverage degrades for repos created after the snapshot's cutoff.
- Deliverable for this pass is the interactive Artifact only — no static narrative report, no automated/scheduled refresh, no PyPI/npm/Stack Overflow cross-checks, no private-activity proxy (all documented as later phases in the spec).
- `report.html` must be built following the `dataviz` and `artifact-design` skills — load both before writing any chart code, choosing colors, or laying out the page.
- Running `backfill.py` or `refresh.py` for real requires the user's own authenticated GCP project (billing enabled) — a fresh subagent without that local auth context cannot execute the "run for real" steps; those are called out explicitly below as manual steps for the user (or an agent working in the user's authenticated shell).

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `README.md`
- Create: `.gitignore`
- Create: `pytest.ini`
- Create: `scripts/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)

**Interfaces:**
- Produces: a `scripts/` package importable as `scripts.<module>` from the repo root; a `tests/` directory pytest will discover.

- [ ] **Step 1: Create `requirements.txt`**

```
google-cloud-bigquery>=3.11
pyyaml>=6.0
pytest>=7.4
```

- [ ] **Step 2: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
```

- [ ] **Step 4: Create empty `scripts/__init__.py` and `tests/__init__.py`**

Both files are empty — they exist only to make `scripts` and `tests` importable packages.

- [ ] **Step 5: Create `README.md`**

```markdown
# GitHub AI Impact Report

Data pipeline + dashboard exploring AI's impact on coding activity, using
public GitHub data (GH Archive + `github_repos`) via BigQuery.

See `docs/superpowers/specs/2026-09-26-github-ai-impact-report-design.md`
for the full design.

## Setup

1. Install the Google Cloud CLI: https://cloud.google.com/sdk/docs/install
2. Create (or pick an existing) GCP project with billing enabled, then run:
   ```
   gcloud auth application-default login
   gcloud config set project <your-project-id>
   ```
3. Install Python dependencies:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Run the tests: `pytest`

## Running the pipeline

One-time full historical backfill (queries BigQuery for real — see the
design doc for expected cost, typically low single-digit dollars or free
tier):

```
python -m scripts.backfill
```

To pull new months later (cheap — only queries months since the last run):

```
python -m scripts.refresh
```

Both write/update CSVs under `data/` and `data/_meta.json` (tracks the
last refreshed month and cumulative bytes billed).
```

- [ ] **Step 6: Verify pytest runs (with nothing to collect yet)**

Run: `pytest`
Expected: `no tests ran` (exits 0, no collection errors)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt README.md .gitignore pytest.ini scripts/__init__.py tests/__init__.py
git commit -m "Add project scaffolding for GitHub AI impact pipeline

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Config files and loader

**Files:**
- Create: `config/ai_ml_keywords.yaml`
- Create: `config/milestones.yaml`
- Create: `scripts/config_loader.py`
- Test: `tests/test_config_loader.py`

**Interfaces:**
- Produces:
  - `load_ai_ml_keywords(path: Path = DEFAULT_KEYWORDS_PATH) -> list[str]`
  - `build_keyword_regex(keywords: list[str]) -> str`
  - `load_milestones(path: Path = DEFAULT_MILESTONES_PATH) -> dict` with keys `llm_milestones` and `github_user_milestones`
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Research and write `config/milestones.yaml`**

Use WebSearch to confirm these dates before writing the file (they're
widely reported, but verify rather than trust memory): GitHub Copilot's
technical preview announcement, GitHub Copilot's GA date, ChatGPT's
public release date, and GPT-4's release date. Then use WebSearch to
find at least 2 GitHub-published developer/user-count milestones (e.g.
GitHub's own blog posts or Octoverse reports announcing headline
figures like "100 million developers") beyond the one seeded below —
each entry must cite a source.

```yaml
llm_milestones:
  - date: "2021-06"
    label: "GitHub Copilot (technical preview)"
  - date: "2022-06"
    label: "GitHub Copilot GA"
  - date: "2022-11"
    label: "ChatGPT released"
  - date: "2023-03"
    label: "GPT-4 released"

github_user_milestones:
  # GitHub's own published headline figures. Reference points only --
  # NOT derived from queried data. Each entry must cite its source.
  - date: "2023-01"
    users_millions: 100
    source: "GitHub blog, January 2023 - 100 million developers"
  # Add at least 2 more researched via WebSearch, e.g. earlier Octoverse
  # report figures, each with its own "source" citation.
```

- [ ] **Step 2: Write `config/ai_ml_keywords.yaml`**

```yaml
# Matched (case-insensitive substring) against repo.name for the AI/ML
# & framework cut. Extend this list as new frameworks/tools emerge --
# it's read fresh on every backfill/refresh run.
keywords:
  - pytorch
  - tensorflow
  - keras
  - scikit-learn
  - jax
  - huggingface
  - transformers
  - langchain
  - llama
  - openai
  - anthropic
  - claude
  - gpt
  - llm
  - copilot
  - cursor-ai
  - ollama
  - stable-diffusion
  - diffusers
```

- [ ] **Step 3: Write the failing tests**

```python
# tests/test_config_loader.py
import pytest
import yaml

from scripts.config_loader import build_keyword_regex, load_ai_ml_keywords, load_milestones


def test_load_ai_ml_keywords_lowercases_and_returns_list(tmp_path):
    path = tmp_path / "keywords.yaml"
    path.write_text("keywords:\n  - PyTorch\n  - LangChain\n")

    result = load_ai_ml_keywords(path)

    assert result == ["pytorch", "langchain"]


def test_load_ai_ml_keywords_rejects_empty_list(tmp_path):
    path = tmp_path / "keywords.yaml"
    path.write_text("keywords: []\n")

    with pytest.raises(ValueError):
        load_ai_ml_keywords(path)


def test_build_keyword_regex_escapes_special_characters():
    result = build_keyword_regex(["pytorch", "c++"])

    assert result == r"(pytorch|c\+\+)"


def test_load_milestones_returns_both_sections(tmp_path):
    path = tmp_path / "milestones.yaml"
    path.write_text(
        "llm_milestones:\n"
        "  - date: '2022-11'\n"
        "    label: 'ChatGPT released'\n"
        "github_user_milestones:\n"
        "  - date: '2023-01'\n"
        "    users_millions: 100\n"
        "    source: 'GitHub blog'\n"
    )

    result = load_milestones(path)

    assert result["llm_milestones"][0]["label"] == "ChatGPT released"
    assert result["github_user_milestones"][0]["users_millions"] == 100


def test_load_milestones_rejects_missing_section(tmp_path):
    path = tmp_path / "milestones.yaml"
    path.write_text("llm_milestones:\n  - date: '2022-11'\n    label: 'x'\n")

    with pytest.raises(ValueError):
        load_milestones(path)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_config_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.config_loader'`

- [ ] **Step 5: Write `scripts/config_loader.py`**

```python
"""Loads and validates YAML config: AI/ML keyword list and milestone reference points."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

DEFAULT_KEYWORDS_PATH = Path(__file__).resolve().parent.parent / "config" / "ai_ml_keywords.yaml"
DEFAULT_MILESTONES_PATH = Path(__file__).resolve().parent.parent / "config" / "milestones.yaml"


def load_ai_ml_keywords(path: Path = DEFAULT_KEYWORDS_PATH) -> list[str]:
    data = yaml.safe_load(path.read_text())
    keywords = data.get("keywords") if data else None
    if not keywords or not isinstance(keywords, list):
        raise ValueError(f"{path}: expected a non-empty 'keywords' list")
    return [str(k).lower() for k in keywords]


def build_keyword_regex(keywords: list[str]) -> str:
    escaped = [re.escape(k) for k in keywords]
    return "(" + "|".join(escaped) + ")"


def load_milestones(path: Path = DEFAULT_MILESTONES_PATH) -> dict:
    data = yaml.safe_load(path.read_text()) or {}
    for key in ("llm_milestones", "github_user_milestones"):
        if key not in data or not isinstance(data[key], list) or not data[key]:
            raise ValueError(f"{path}: expected a non-empty '{key}' list")
    return data
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_config_loader.py -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Commit**

```bash
git add config/ai_ml_keywords.yaml config/milestones.yaml scripts/config_loader.py tests/test_config_loader.py
git commit -m "Add AI/ML keyword and milestone config with loader

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Month-range utilities

**Files:**
- Create: `scripts/month_range.py`
- Test: `tests/test_month_range.py`

**Interfaces:**
- Produces:
  - `month_suffix(year: int, month: int) -> str` (e.g. `"201501"`)
  - `latest_closed_month(today: date) -> str`
  - `month_range(start_suffix: str, end_suffix: str) -> list[str]` (inclusive)
  - `next_month_suffix(suffix: str) -> str`
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_month_range.py
from datetime import date

from scripts.month_range import latest_closed_month, month_range, month_suffix, next_month_suffix


def test_month_suffix_zero_pads_month():
    assert month_suffix(2015, 1) == "201501"
    assert month_suffix(2026, 11) == "202611"


def test_latest_closed_month_is_previous_month():
    assert latest_closed_month(date(2026, 9, 26)) == "202608"


def test_latest_closed_month_handles_january():
    assert latest_closed_month(date(2026, 1, 15)) == "202512"


def test_month_range_is_inclusive_and_spans_year_boundary():
    assert month_range("201511", "201602") == ["201511", "201512", "201601", "201602"]


def test_month_range_single_month():
    assert month_range("201501", "201501") == ["201501"]


def test_next_month_suffix_advances():
    assert next_month_suffix("201501") == "201502"


def test_next_month_suffix_wraps_year():
    assert next_month_suffix("201512") == "201601"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_month_range.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.month_range'`

- [ ] **Step 3: Write `scripts/month_range.py`**

```python
"""Pure helpers for computing GH Archive monthly table suffixes and ranges."""
from __future__ import annotations

from datetime import date, timedelta


def month_suffix(year: int, month: int) -> str:
    return f"{year:04d}{month:02d}"


def latest_closed_month(today: date) -> str:
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - timedelta(days=1)
    return month_suffix(last_month_end.year, last_month_end.month)


def month_range(start_suffix: str, end_suffix: str) -> list[str]:
    start_year, start_month = int(start_suffix[:4]), int(start_suffix[4:])
    end_year, end_month = int(end_suffix[:4]), int(end_suffix[4:])
    months = []
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        months.append(month_suffix(year, month))
        month += 1
        if month == 13:
            month = 1
            year += 1
    return months


def next_month_suffix(suffix: str) -> str:
    year, month = int(suffix[:4]), int(suffix[4:])
    month += 1
    if month == 13:
        month = 1
        year += 1
    return month_suffix(year, month)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_month_range.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/month_range.py tests/test_month_range.py
git commit -m "Add month-range utilities for GH Archive table suffixes

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: BigQuery client wrapper

**Files:**
- Create: `scripts/bq_client.py`
- Test: `tests/test_bq_client.py`

**Interfaces:**
- Produces:
  - `QueryResult = namedtuple("QueryResult", ["rows", "bytes_billed"])`
  - `class BigQueryClient: def __init__(self, project=None, client=None)`
  - `BigQueryClient.run_query(self, sql: str, params: dict[str, str]) -> QueryResult`
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bq_client.py
from unittest.mock import MagicMock

from scripts.bq_client import BigQueryClient


def test_run_query_returns_rows_and_bytes_billed():
    mock_row = MagicMock()
    mock_row.items.return_value = [("year_month", "201501"), ("commit_count", 42)]

    mock_job = MagicMock()
    mock_job.result.return_value = [mock_row]
    mock_job.total_bytes_billed = 12345

    mock_client = MagicMock()
    mock_client.query.return_value = mock_job

    bq = BigQueryClient(client=mock_client)
    result = bq.run_query("SELECT 1", {"start_suffix": "201501"})

    assert result.rows == [{"year_month": "201501", "commit_count": 42}]
    assert result.bytes_billed == 12345
    mock_client.query.assert_called_once()


def test_run_query_handles_missing_bytes_billed():
    mock_job = MagicMock()
    mock_job.result.return_value = []
    mock_job.total_bytes_billed = None

    mock_client = MagicMock()
    mock_client.query.return_value = mock_job

    bq = BigQueryClient(client=mock_client)
    result = bq.run_query("SELECT 1", {})

    assert result.rows == []
    assert result.bytes_billed == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_bq_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.bq_client'`

- [ ] **Step 3: Write `scripts/bq_client.py`**

```python
"""Thin wrapper around google-cloud-bigquery for parameterized, cost-tracked queries."""
from __future__ import annotations

from collections import namedtuple

from google.cloud import bigquery

QueryResult = namedtuple("QueryResult", ["rows", "bytes_billed"])


class BigQueryClient:
    def __init__(self, project: str | None = None, client: bigquery.Client | None = None):
        self._client = client if client is not None else bigquery.Client(project=project)

    def run_query(self, sql: str, params: dict[str, str]) -> QueryResult:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(name, "STRING", value)
                for name, value in params.items()
            ]
        )
        job = self._client.query(sql, job_config=job_config)
        rows = [dict(row.items()) for row in job.result()]
        bytes_billed = job.total_bytes_billed or 0
        return QueryResult(rows=rows, bytes_billed=bytes_billed)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_bq_client.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/bq_client.py tests/test_bq_client.py
git commit -m "Add BigQuery client wrapper with injectable client for testing

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: SQL query files

**Files:**
- Create: `scripts/queries/monthly_volume.sql`
- Create: `scripts/queries/cumulative_actors.sql`
- Create: `scripts/queries/monthly_language.sql`
- Create: `scripts/queries/monthly_ai_topics.sql`
- Test: `tests/test_queries.py`

**Interfaces:**
- Produces: four `.sql` files, each expecting named parameters `@start_suffix`/`@end_suffix` (and `@keyword_pattern` for `monthly_ai_topics.sql`), read as plain text by `backfill.py`/`refresh.py` and passed to `BigQueryClient.run_query`.
- Consumes: `BigQueryClient.run_query` (Task 4).

- [ ] **Step 1: Write `scripts/queries/monthly_volume.sql`**

```sql
SELECT
  _TABLE_SUFFIX AS year_month,
  COUNTIF(type = 'PushEvent') AS push_count,
  SUM(IF(type = 'PushEvent',
         CAST(JSON_EXTRACT_SCALAR(payload, '$.size') AS INT64),
         0)) AS commit_count,
  COUNTIF(type = 'PullRequestEvent'
          AND JSON_EXTRACT_SCALAR(payload, '$.action') = 'opened') AS pr_opened_count,
  COUNT(DISTINCT IF(type = 'PushEvent', repo.id, NULL)) AS active_repo_count,
  COUNT(DISTINCT IF(type = 'PushEvent', actor.id, NULL)) AS active_actor_count
FROM `githubarchive.month.*`
WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
  AND type IN ('PushEvent', 'PullRequestEvent')
GROUP BY year_month
ORDER BY year_month
```

- [ ] **Step 2: Write `scripts/queries/cumulative_actors.sql`**

Note: this scans `_TABLE_SUFFIX <= @end_suffix` (all history up to the
end of the requested range), not just the requested start/end window —
determining whether an actor is "new" in a given month requires knowing
whether they appeared in ANY earlier month. Only the output rows are
restricted to the requested range; both `backfill.py` and `refresh.py`
rely on this to produce correct incremental results while only writing
new rows.

```sql
WITH actor_first_seen AS (
  SELECT
    actor.id AS actor_id,
    MIN(_TABLE_SUFFIX) AS first_seen_month
  FROM `githubarchive.month.*`
  WHERE _TABLE_SUFFIX <= @end_suffix
    AND actor.id IS NOT NULL
  GROUP BY actor_id
)
SELECT
  first_seen_month AS year_month,
  COUNT(*) AS new_actor_count
FROM actor_first_seen
WHERE first_seen_month BETWEEN @start_suffix AND @end_suffix
GROUP BY year_month
ORDER BY year_month
```

- [ ] **Step 3: Write `scripts/queries/monthly_language.sql`**

```sql
WITH repo_primary_language AS (
  SELECT
    repo_name,
    (SELECT lang.name
     FROM UNNEST(language) AS lang
     ORDER BY lang.bytes DESC
     LIMIT 1) AS primary_language
  FROM `bigquery-public-data.github_repos.languages`
),
monthly_repo_activity AS (
  SELECT
    _TABLE_SUFFIX AS year_month,
    repo.name AS repo_name,
    SUM(CAST(JSON_EXTRACT_SCALAR(payload, '$.size') AS INT64)) AS commit_count
  FROM `githubarchive.month.*`
  WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
    AND type = 'PushEvent'
  GROUP BY year_month, repo_name
)
SELECT
  a.year_month,
  COALESCE(p.primary_language, 'Unknown') AS language,
  SUM(a.commit_count) AS commit_count
FROM monthly_repo_activity a
LEFT JOIN repo_primary_language p
  ON a.repo_name = p.repo_name
GROUP BY a.year_month, language
ORDER BY a.year_month, commit_count DESC
```

- [ ] **Step 4: Write `scripts/queries/monthly_ai_topics.sql`**

```sql
SELECT
  _TABLE_SUFFIX AS year_month,
  SUM(CAST(JSON_EXTRACT_SCALAR(payload, '$.size') AS INT64)) AS ai_commit_count
FROM `githubarchive.month.*`
WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
  AND type = 'PushEvent'
  AND REGEXP_CONTAINS(LOWER(repo.name), @keyword_pattern)
GROUP BY year_month
ORDER BY year_month
```

- [ ] **Step 5: Write and run a sanity test (not a substitute for real verification — see Step 6)**

```python
# tests/test_queries.py
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
```

Run: `pytest tests/test_queries.py -v`
Expected: PASS (4 tests) — this only guards against accidental edits to
parameter names/table references, it does NOT validate SQL correctness
or cost.

- [ ] **Step 6: Manual verification (requires the user's authenticated GCP project — not automatable in this session)**

Once `gcloud auth application-default login` has been run and a project
is set, dry-run each query with a narrow one-month range (e.g.
`start_suffix=202501`, `end_suffix=202501`) using the BigQuery console
or `bq query --dry_run` to confirm expected bytes-scanned before running
the real backfill. This is a manual step for the user — flag it rather
than assuming it's done.

- [ ] **Step 7: Commit**

```bash
git add scripts/queries/ tests/test_queries.py
git commit -m "Add GH Archive/github_repos SQL queries for pipeline metrics

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: CSV store helper

**Files:**
- Create: `scripts/csv_store.py`
- Test: `tests/test_csv_store.py`

**Interfaces:**
- Produces:
  - `append_rows(csv_path: Path, fieldnames: list[str], rows: list[dict]) -> None`
  - `overwrite_rows(csv_path: Path, fieldnames: list[str], rows: list[dict]) -> None`
  - `last_cumulative_value(csv_path: Path, cumulative_field: str) -> int`
  - `with_running_cumulative(rows: list[dict], count_field: str, cumulative_field: str, starting_total: int) -> list[dict]`
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_csv_store.py
from scripts.csv_store import (
    append_rows,
    last_cumulative_value,
    overwrite_rows,
    with_running_cumulative,
)


def test_append_rows_writes_header_once(tmp_path):
    path = tmp_path / "data.csv"
    append_rows(path, ["year_month", "count"], [{"year_month": "201501", "count": 5}])
    append_rows(path, ["year_month", "count"], [{"year_month": "201502", "count": 7}])

    lines = path.read_text().strip().splitlines()
    assert lines == ["year_month,count", "201501,5", "201502,7"]


def test_overwrite_rows_replaces_file_contents(tmp_path):
    path = tmp_path / "data.csv"
    append_rows(path, ["year_month", "count"], [{"year_month": "201501", "count": 5}])
    overwrite_rows(path, ["year_month", "count"], [{"year_month": "202601", "count": 99}])

    lines = path.read_text().strip().splitlines()
    assert lines == ["year_month,count", "202601,99"]


def test_last_cumulative_value_returns_zero_when_missing(tmp_path):
    assert last_cumulative_value(tmp_path / "missing.csv", "cumulative_total") == 0


def test_last_cumulative_value_reads_last_row(tmp_path):
    path = tmp_path / "data.csv"
    overwrite_rows(
        path,
        ["year_month", "cumulative_total"],
        [
            {"year_month": "201501", "cumulative_total": 10},
            {"year_month": "201502", "cumulative_total": 25},
        ],
    )

    assert last_cumulative_value(path, "cumulative_total") == 25


def test_with_running_cumulative_accumulates_from_starting_total():
    rows = [{"year_month": "201501", "new_actor_count": 5}, {"year_month": "201502", "new_actor_count": 3}]

    result = with_running_cumulative(rows, "new_actor_count", "cumulative_total", starting_total=10)

    assert result == [
        {"year_month": "201501", "new_actor_count": 5, "cumulative_total": 15},
        {"year_month": "201502", "new_actor_count": 3, "cumulative_total": 18},
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_csv_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.csv_store'`

- [ ] **Step 3: Write `scripts/csv_store.py`**

```python
"""Append-only CSV storage helpers for pipeline output tables."""
from __future__ import annotations

import csv
from pathlib import Path


def append_rows(csv_path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    file_exists = csv_path.exists()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def overwrite_rows(csv_path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def last_cumulative_value(csv_path: Path, cumulative_field: str) -> int:
    if not csv_path.exists():
        return 0
    with csv_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return 0
    return int(rows[-1][cumulative_field])


def with_running_cumulative(
    rows: list[dict], count_field: str, cumulative_field: str, starting_total: int
) -> list[dict]:
    total = starting_total
    result = []
    for row in rows:
        total += int(row[count_field])
        result.append({**row, cumulative_field: total})
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_csv_store.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/csv_store.py tests/test_csv_store.py
git commit -m "Add CSV store helper for append/overwrite/cumulative pipeline output

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: Meta (run-state) tracker

**Files:**
- Create: `scripts/meta_store.py`
- Test: `tests/test_meta_store.py`

**Interfaces:**
- Produces:
  - `read_meta(path: Path) -> dict` with keys `last_refreshed_month` (str | None) and `total_bytes_billed` (int)
  - `write_meta(path: Path, last_refreshed_month: str, additional_bytes_billed: int) -> None`
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_meta_store.py
from scripts.meta_store import read_meta, write_meta


def test_read_meta_returns_defaults_when_missing(tmp_path):
    meta = read_meta(tmp_path / "_meta.json")

    assert meta == {"last_refreshed_month": None, "total_bytes_billed": 0}


def test_write_meta_then_read_round_trips(tmp_path):
    path = tmp_path / "_meta.json"
    write_meta(path, last_refreshed_month="201501", additional_bytes_billed=100)

    meta = read_meta(path)

    assert meta == {"last_refreshed_month": "201501", "total_bytes_billed": 100}


def test_write_meta_accumulates_bytes_billed_across_calls(tmp_path):
    path = tmp_path / "_meta.json"
    write_meta(path, last_refreshed_month="201501", additional_bytes_billed=100)
    write_meta(path, last_refreshed_month="201502", additional_bytes_billed=50)

    meta = read_meta(path)

    assert meta == {"last_refreshed_month": "201502", "total_bytes_billed": 150}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_meta_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.meta_store'`

- [ ] **Step 3: Write `scripts/meta_store.py`**

```python
"""Tracks pipeline refresh state: last refreshed month and cumulative bytes billed."""
from __future__ import annotations

import json
from pathlib import Path


def read_meta(path: Path) -> dict:
    if not path.exists():
        return {"last_refreshed_month": None, "total_bytes_billed": 0}
    return json.loads(path.read_text())


def write_meta(path: Path, last_refreshed_month: str, additional_bytes_billed: int) -> None:
    meta = read_meta(path)
    meta["last_refreshed_month"] = last_refreshed_month
    meta["total_bytes_billed"] = meta.get("total_bytes_billed", 0) + additional_bytes_billed
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_meta_store.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/meta_store.py tests/test_meta_store.py
git commit -m "Add meta-store for tracking pipeline refresh state

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: `backfill.py` orchestration

**Files:**
- Create: `scripts/backfill.py`
- Test: `tests/test_backfill.py`

**Interfaces:**
- Consumes: `BigQueryClient` (Task 4, injectable via constructor), `load_ai_ml_keywords`/`build_keyword_regex`/`load_milestones` (Task 2), `overwrite_rows`/`with_running_cumulative` (Task 6), `write_meta` (Task 7), `latest_closed_month` (Task 3), the four `.sql` files (Task 5).
- Produces:
  - `run_backfill(bq: BigQueryClient, data_dir: Path = DATA_DIR, today: date | None = None) -> int` (returns total bytes billed)
  - CSV column contracts (relied on by Task 10's report page):
    - `monthly_volume.csv`: `year_month,push_count,commit_count,pr_opened_count,active_repo_count,active_actor_count`
    - `cumulative_actors.csv`: `year_month,new_actor_count,cumulative_total`
    - `monthly_language.csv`: `year_month,language,commit_count`
    - `monthly_ai_topics.csv`: `year_month,ai_commit_count`
  - `data/milestones.json` (raw dump of `load_milestones()`)
  - `data/_meta.json` (via `write_meta`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backfill.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_backfill.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.backfill'`

- [ ] **Step 3: Write `scripts/backfill.py`**

```python
"""One-time full historical backfill: 2015-01 through the latest fully-closed month."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.bq_client import BigQueryClient
from scripts.config_loader import build_keyword_regex, load_ai_ml_keywords, load_milestones
from scripts.csv_store import overwrite_rows, with_running_cumulative
from scripts.meta_store import write_meta
from scripts.month_range import latest_closed_month

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
QUERIES_DIR = Path(__file__).resolve().parent / "queries"
START_SUFFIX = "201501"

VOLUME_FIELDS = [
    "year_month", "push_count", "commit_count", "pr_opened_count",
    "active_repo_count", "active_actor_count",
]
ACTORS_FIELDS = ["year_month", "new_actor_count", "cumulative_total"]
LANGUAGE_FIELDS = ["year_month", "language", "commit_count"]
AI_TOPICS_FIELDS = ["year_month", "ai_commit_count"]


def run_backfill(bq: BigQueryClient, data_dir: Path = DATA_DIR, today: date | None = None) -> int:
    """Runs the full historical backfill. Returns total bytes billed across all queries."""
    end_suffix = latest_closed_month(today or date.today())
    total_bytes_billed = 0

    volume_sql = (QUERIES_DIR / "monthly_volume.sql").read_text()
    result = bq.run_query(volume_sql, {"start_suffix": START_SUFFIX, "end_suffix": end_suffix})
    overwrite_rows(data_dir / "monthly_volume.csv", VOLUME_FIELDS, result.rows)
    total_bytes_billed += result.bytes_billed

    actors_sql = (QUERIES_DIR / "cumulative_actors.sql").read_text()
    result = bq.run_query(actors_sql, {"start_suffix": START_SUFFIX, "end_suffix": end_suffix})
    rows_with_cumulative = with_running_cumulative(
        result.rows, "new_actor_count", "cumulative_total", starting_total=0
    )
    overwrite_rows(data_dir / "cumulative_actors.csv", ACTORS_FIELDS, rows_with_cumulative)
    total_bytes_billed += result.bytes_billed

    language_sql = (QUERIES_DIR / "monthly_language.sql").read_text()
    result = bq.run_query(language_sql, {"start_suffix": START_SUFFIX, "end_suffix": end_suffix})
    overwrite_rows(data_dir / "monthly_language.csv", LANGUAGE_FIELDS, result.rows)
    total_bytes_billed += result.bytes_billed

    keyword_pattern = build_keyword_regex(load_ai_ml_keywords())
    ai_topics_sql = (QUERIES_DIR / "monthly_ai_topics.sql").read_text()
    result = bq.run_query(
        ai_topics_sql,
        {"start_suffix": START_SUFFIX, "end_suffix": end_suffix, "keyword_pattern": keyword_pattern},
    )
    overwrite_rows(data_dir / "monthly_ai_topics.csv", AI_TOPICS_FIELDS, result.rows)
    total_bytes_billed += result.bytes_billed

    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "milestones.json").write_text(json.dumps(load_milestones(), indent=2))

    write_meta(data_dir / "_meta.json", last_refreshed_month=end_suffix, additional_bytes_billed=total_bytes_billed)
    return total_bytes_billed


if __name__ == "__main__":
    run_backfill(BigQueryClient())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_backfill.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/backfill.py tests/test_backfill.py
git commit -m "Add backfill orchestration for full historical data pull

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Manual step for the user — run the real backfill**

This requires the user's own authenticated GCP project (per Task 5 Step
6's `gcloud auth application-default login`) and cannot be executed by
an agent without that local credential context. Tell the user to run:

```
python -m scripts.backfill
```

and confirm `data/*.csv`, `data/milestones.json`, and `data/_meta.json`
were created with non-empty content before moving on to Task 10 (the
report needs real data to render against).

---

### Task 9: `refresh.py` orchestration

**Files:**
- Create: `scripts/refresh.py`
- Test: `tests/test_refresh.py`

**Interfaces:**
- Consumes: `BigQueryClient` (Task 4), `load_ai_ml_keywords`/`build_keyword_regex`/`load_milestones` (Task 2), `append_rows`/`last_cumulative_value`/`with_running_cumulative` (Task 6), `read_meta`/`write_meta` (Task 7), `latest_closed_month`/`next_month_suffix` (Task 3), the four `.sql` files (Task 5).
- Produces: `run_refresh(bq: BigQueryClient, data_dir: Path = DATA_DIR, today: date | None = None) -> int` (returns bytes billed this run, or `0` if already current). Appends to the same CSVs Task 8 creates, using the same column contracts.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_refresh.py
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
```

Note: `today=date(2026, 9, 26)` → `latest_closed_month` is `"202608"`
(per Task 3), which is the range end used above.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_refresh.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.refresh'`

- [ ] **Step 3: Write `scripts/refresh.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_refresh.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/refresh.py tests/test_refresh.py
git commit -m "Add incremental refresh orchestration

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 10: Report artifact (D3 dashboard)

**Files:**
- Create: `report/report.html`

**Interfaces:**
- Consumes: the CSV/JSON column contracts produced by Task 8/9:
  - `monthly_volume.csv`: `year_month,push_count,commit_count,pr_opened_count,active_repo_count,active_actor_count`
  - `cumulative_actors.csv`: `year_month,new_actor_count,cumulative_total`
  - `monthly_language.csv`: `year_month,language,commit_count`
  - `monthly_ai_topics.csv`: `year_month,ai_commit_count`
  - `milestones.json`: `{llm_milestones: [{date, label}], github_user_milestones: [{date, users_millions, source}]}`
- Produces: a published Claude Artifact (the deliverable for this phase).

- [ ] **Step 1: Load required skills before writing any chart code**

Load the `dataviz` skill (chart form, color palette, mark specs) and the
`artifact-design` skill (page contract: title, libraries, CDN
allowlist, theming, layout) via the `Skill` tool. Do not write
`report/report.html` before both are loaded.

- [ ] **Step 2: Confirm real data exists**

Verify `data/monthly_volume.csv`, `data/cumulative_actors.csv`,
`data/monthly_language.csv`, `data/monthly_ai_topics.csv`, and
`data/milestones.json` all exist and are non-empty (Task 8 Step 6 must
have been completed by the user first — this page has nothing to
render against until real backfill data exists).

- [ ] **Step 3: Build `report/report.html`**

Following the loaded skills' guidance, build a single-page D3 dashboard
with:

- **Headline chart**: monthly commit volume from `monthly_volume.csv`,
  with a toggle across four views (all derived client-side, no
  additional data files needed):
  - **Absolute**: `commit_count` per `year_month`.
  - **Per active contributor**: `commit_count / active_actor_count` per
    `year_month` — isolates output-per-developer from headcount growth.
  - **Normalized by user base**: `commit_count` divided by
    `cumulative_total` joined from `cumulative_actors.csv` on
    `year_month` — same goal via the cumulative-actors baseline.
  - **YoY growth rate**: year-over-year % change in `commit_count`,
    plotted alongside a dashed "expected" line: fit a simple linear
    trend to `commit_count` over months before `2022-11` (using months
    since series start as the x variable), extrapolate that same line
    forward through the rest of the series, and show it next to actual
    values so any post-2022 deviation from the pre-LLM trend is visible.
  Overlay vertical markers for each entry in `milestones.json`'s
  `llm_milestones` on every view (hover shows the `label`).
- **Language mix section**: stacked/streamgraph or multi-line view of
  `monthly_language.csv` commit share (commit_count divided by the sum
  of commit_count across all languages for that `year_month`), filterable
  to the top N languages by total commits. Must display an explicit,
  visible caveat that language coverage degrades for repos created after
  `bigquery-public-data.github_repos`'s snapshot date (see spec) — this
  is a report-content requirement, not optional footnote text.
  language chart to top N.
- **AI/ML framework section**: `monthly_ai_topics.csv` `ai_commit_count`
  plotted both as absolute volume and as a share of
  `monthly_volume.csv`'s `commit_count` for the same `year_month`. Must
  note this is a `repo.name` substring match against
  `config/ai_ml_keywords.yaml` (approximate, not exhaustive).
- **User-base section**: `cumulative_actors.csv`'s `cumulative_total`
  over time, with `milestones.json`'s `github_user_milestones` overlaid
  as annotated reference points (each showing its `source` on hover),
  visually distinguished from the derived line since they're
  externally-published figures, not derived data.
- All charts: hover tooltips showing exact values.
- Load D3 only from an Artifact-allowed CDN (cdnjs.cloudflare.com or
  cdn.jsdelivr.net/npm/), per `artifact-design`.

- [ ] **Step 4: Publish the artifact**

Use the `Artifact` tool to publish `report/report.html`, passing
`data/monthly_volume.csv`, `data/cumulative_actors.csv`,
`data/monthly_language.csv`, `data/monthly_ai_topics.csv`, and
`data/milestones.json` as supporting `files` so the page can fetch them
at their published paths.

- [ ] **Step 5: Manual browser verification**

Open the published artifact and confirm: all four sections render with
real data (not empty/placeholder states), milestone markers appear at
the correct dates, the absolute/normalized toggle changes the headline
chart, the language top-N filter works, hover tooltips show correct
values on each chart, and the language-mix staleness caveat and AI/ML
approximate-match note are visibly present (not just in a footnote
easy to miss).

- [ ] **Step 6: Commit**

```bash
git add report/report.html
git commit -m "Add D3 dashboard artifact for GitHub AI impact report

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

Note: `data/*.csv`/`data/*.json` are generated by the pipeline, not
hand-written — commit them alongside if the user wants the repo itself
to hold the current snapshot, or leave them untracked if they'd rather
treat `data/` as a local build artifact. Ask the user which they prefer
before adding `data/` to git.
