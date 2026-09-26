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
