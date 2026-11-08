# GitHub AI Impact Report

Data pipeline + dashboard exploring AI's impact on coding activity, using
public GitHub data.

The report's main source is GitHub's own **Innovation Graph** (quarterly
public activity from 2020, bots excluded; free CSV, no BigQuery). GH Archive
via BigQuery is kept only for a comparison panel: it includes bots, and its
collection has broken down since mid-2025 (see "Why the Innovation Graph"
below).

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

## Innovation Graph (main source)

```
python -m scripts.innovation_graph
```

Downloads the release pinned in `config/innovation_graph.yaml` into
`data/innovation_graph/<release>/` (once; about 10 MB) and writes
`ig_quarterly.csv`, `ig_topics.csv`, `ig_languages.csv`, `ig_meta.json`,
the config JSON, and `gha_quarterly.csv` if `data/monthly_volume.csv`
exists. It costs nothing and doesn't touch BigQuery.

GitHub publishes a new release about a month after each quarter ends. To
pick it up, bump `release` in `config/innovation_graph.yaml` and re-run.

"Global" figures are sums over economies, leaving out the `EU` aggregate.
GitHub withholds an economy's figure when fewer than 100 developers did the
activity, so the totals run slightly low.

## Why the Innovation Graph

A cross-check in November 2026 found GH Archive can't support the
LLM-era question:

- 2020 to Q3 2023: GH Archive pushes track the Innovation Graph at about
  1.25×, so they agree on direction.
- Q4 2023 to Q1 2025: GH Archive rises to about 1.75× while the bot-free
  count runs below trend. GH Archive's "above trend" rise in this period was
  bot or automated activity.
- From mid-2025: GH Archive falls to 0.65× as the bot-free count doubles,
  because of GH Archive's own collection breakdown.

The Innovation Graph documents no change of method, and every earlier
quarter is identical across releases v1.0.5 (Jan 2025) to v1.0.12, so the
2025 rise was reported as it happened rather than restated.

## GH Archive pipeline (comparison only)

One-time full historical backfill. **This queries BigQuery for real.** The
queries read only the small `type`, `repo` and `actor` columns of GH Archive
and never the `payload` column, which holds nearly all of the dataset's
bytes. (Reading `payload` for commit counts priced the backfill at ~95 TB /
~$540, so the pipeline counts pushes instead of commits; a test enforces
that no query reads `payload`.) The language mix and AI/ML-repo series
share one query, so the whole backfill is ~830 GB: inside the 1 TiB/month
free tier, so it runs on a project without billing (the BigQuery sandbox).

```
python -m scripts.backfill
```

Before querying anything, the backfill dry-runs all three queries (free),
prints the estimated GB scanned and approximate cost, and asks
`Proceed? [y/N]`. Read that estimate before answering. Answering anything
other than `y` exits without querying or writing.

If the estimate is over the 1 TiB free tier, the backfill stops before the
prompt: without billing, the query that crosses the limit fails after the
earlier ones have used up the month's allowance. Real queries you've run in
the project earlier in the month count against the same 1 TiB (dry runs
don't). If billing is enabled and you accept the cost, override with
`BQ_BILLING_ENABLED=1 python -m scripts.backfill`.

Every real query is also capped server-side by `maximum_bytes_billed`, read
from `BQ_MAX_BYTES_BILLED` (bytes, per query; default 2 TiB). A query that
would bill more than the cap fails without being charged. If the dry run
warns that a query exceeds the cap and you accept the cost, raise it:

```
BQ_MAX_BYTES_BILLED=5000000000000 python -m scripts.backfill   # 5 TB per query
```

If any query fails, nothing under `data/` is written or changed.

To pull new months later (much cheaper — only queries months since the last
run, under the same `BQ_MAX_BYTES_BILLED` cap; a failed refresh leaves
`data/` untouched and can simply be re-run):

```
python -m scripts.refresh
```

Both write/update CSVs under `data/` and `data/_meta.json` (tracks the
last refreshed month and cumulative bytes billed).

## Data quality

GH Archive's own collection has gaps (checked from its daily event counts
in November 2026). `config/data_quality.yaml` records them, and the report
reads it as `data/data_quality.json`:

- `last_reliable_month`: months after this aren't shown (collection fell
  off from August 2026).
- `gap_months`: shown as breaks in the lines and left out of the trend fit
  and year-over-year comparisons.
- `source_breaks`: lasting collection changes (a ~30% step down in June
  2025), marked on the charts; growth rates aren't compared across them.

The CSVs under `data/` keep every month. After editing the config,
`python -m scripts.report_config` rewrites the JSON without querying.

Language mix was dropped from the report: `github_repos.languages` covers
too few repositories (79% of 2015 pushes and 99.9% of 2026 pushes have no
language). `monthly_language.csv` is still produced.
