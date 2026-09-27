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

One-time full historical backfill. **This queries BigQuery for real and is
not cheap.** Three of the four queries read GH Archive's `payload` column,
which holds most of the dataset's bytes, and the tables aren't clustered by
event type, so a full 2015–present backfill is likely TB-scale: on the order
of **tens to low hundreds of dollars** at on-demand pricing, well past the
1 TiB/month free tier.

```
python -m scripts.backfill
```

Before querying anything, the backfill dry-runs all four queries (free),
prints the estimated GB scanned and approximate cost, and asks
`Proceed? [y/N]`. Read that estimate before answering. Answering anything
other than `y` exits without querying or writing.

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
