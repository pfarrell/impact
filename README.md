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
