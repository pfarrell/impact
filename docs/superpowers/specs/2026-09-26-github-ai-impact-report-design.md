# GitHub AI Impact Report — Design

## Purpose

Build a shareable, refreshable data report exploring the impact of AI (LLMs,
coding assistants) on software development activity, using public GitHub
data as the evidence base. The report should establish a pre-LLM baseline
(GitHub activity before ~late 2022) and compare it against post-LLM activity,
with volume/velocity as the primary signal and language mix and AI/ML
framework adoption as supporting cuts. Geography is explicitly out of scope
(GitHub has no reliable geographic data — self-reported profile location
strings are too sparse and noisy to support a credible cut).

The deliverable is an interactive artifact (dashboard) first; a static
narrative write-up may follow once the underlying trends are clear, but is
not part of this build.

## Data sources

Two public BigQuery datasets, queried directly (no raw data downloaded or
stored locally):

- **`githubarchive.month.YYYYMM`** — one table per month, every public
  GitHub event since 2011 (pushes, PR opens, issues, stars, etc). Primary
  source for volume/velocity metrics.
- **`bigquery-public-data.github_repos`** — repo metadata (declared
  language, description, topics). Joined against event data by repo name
  for language breakdowns and AI/ML repo matching.

**Time range:** monthly grain, 2015-01 through the latest fully-closed
month at run time. 2015 was chosen as the baseline start because GH
Archive data quality and GitHub's own growth stabilize around this point;
this gives roughly 8 years of pre-ChatGPT baseline (through Nov 2022) and
several years of post-LLM data to compare against.

**Access:** Google Cloud project with BigQuery enabled, authenticated via
`gcloud auth application-default login` (personal use — no service account
key management). Every query restricts columns and event types to the
minimum needed and relies on monthly table partitioning to control bytes
scanned. Expected total cost for a full historical backfill: low
single-digit dollars, likely within BigQuery's 1TB/month free tier.
Ongoing refreshes (incremental, new months only) cost near-zero.

**Geography:** out of scope. GitHub's only location signal is a
free-text, self-reported profile field with no lat/long and heavy
non-response/noise — not reliable enough to support a claim in this report.

## Metrics & analytical approach

### The core framing problem

Raw GitHub activity counts (commits, PRs, pushes) have grown every year
since GitHub launched, independent of AI, simply because the platform has
more users every year. Plotting absolute counts alone cannot support a
credible "AI changed things" claim — any post-2022 increase could just be
continued organic platform growth. The report's metrics are designed to
separate these two effects.

### User-base baseline (denominator)

Two parallel series establish "how many developers were active," used to
normalize volume metrics:

- **Cumulative distinct actors ever seen** (derived): first-seen month per
  `actor_id` in GH Archive event data, accumulated into a running total.
  This is a lower-bound proxy for GitHub's active public developer base —
  it undercounts anyone who never appears in a public event (private-only
  users, lurkers), but is internally consistent and derived from the same
  pipeline as everything else.
- **GitHub's published user milestones** (reference, hand-maintained): a
  small table of dated headline figures GitHub itself has published (e.g.
  blog posts, Octoverse reports announcing "100 million developers," etc.),
  layered onto the same chart as annotated reference points so the derived
  proxy can be sanity-checked against GitHub's own numbers. These are
  external published figures, not derived from queried data, and are
  labeled as such in the report.

### Primary volume/velocity metrics (absolute, for scale/context)

- Monthly push count
- Monthly commit count (sum of push event `payload.size`)
- Monthly PRs opened
- Monthly active repos (distinct repos with a push in the month)
- Monthly active contributors (distinct actors with a push in the month)

### Productivity / normalized metrics (the actual "AI impact" signal)

- **Commits per active contributor per month** — isolates whether output
  per developer changed, independent of how many developers there are.
- **Commit volume normalized against cumulative user-base growth** — same
  goal via the cumulative-actors baseline instead of monthly active count.
- **Year-over-year % growth rate** for each primary metric, with the
  pre-2022 trend extrapolated forward as a dashed "expected" baseline, so
  any post-2022 deviation from expected trend is visible rather than
  asserted.

### Reference markers

Vertical annotations on all time series for key LLM/AI-assistant
milestones: GitHub Copilot GA (Jun 2022), ChatGPT release (Nov 2022),
GPT-4 (Mar 2023) — maintained in `config/milestones.yaml` alongside the
GitHub user-count milestones, so both annotation types share one
mechanism.

### Supporting cuts

- **Language mix**: monthly commit/push share by the top ~15 languages
  (by `github_repos` declared language), to show compositional shifts
  (e.g. Python's share) over the same timeline.
- **AI/ML & framework cut**: repos matched by name/description/topics
  against a maintained keyword list in `config/ai_ml_keywords.yaml`
  (e.g. pytorch, tensorflow, transformers/huggingface, langchain, openai,
  llama, jax, scikit-learn, ollama, plus coding-assistant tools like
  copilot, cursor). Tracked as its own volume and share-of-total trend,
  separate from the general language cut.

## Repository structure

```
ai_impact/
  config/
    ai_ml_keywords.yaml       # maintained list: frameworks, ML libs, coding-assistant tools
    milestones.yaml           # hand-maintained reference points (LLM milestones + GitHub user-count milestones)
  scripts/
    bq_client.py               # BigQuery auth (application-default credentials) + query runner
    queries/
      monthly_volume.sql       # pushes, commits, PRs, active repos, active actors
      cumulative_actors.sql    # first-seen actor_id -> running total
      monthly_language.sql     # commit share by language
      monthly_ai_topics.sql    # commit share by AI/ML-matched repos
    backfill.py                 # one-time: full 2015-01..latest-closed-month pull
    refresh.py                  # incremental: pulls only months after data/_meta.json's last month, appends
  data/
    monthly_volume.csv
    cumulative_actors.csv
    monthly_language.csv
    monthly_ai_topics.csv
    _meta.json                  # last refreshed month + query bytes billed, for cost tracking
  report/
    report.html                 # published as the interactive Artifact (references data/ files as published supporting files)
```

## Refresh workflow

- `backfill.py` runs once to populate full 2015–present history into `data/`.
- `refresh.py` is re-run manually (no automated schedule for this pass) to
  pull only months after `data/_meta.json`'s recorded last-refreshed
  month, appending to the existing CSVs. This keeps ongoing query cost
  near-zero regardless of how often it's re-run.
- `_meta.json` tracks the last successfully refreshed month and
  cumulative bytes billed, for cost visibility over time.

## Report / artifact delivery

- The published Artifact reads the small aggregate CSVs from `data/`,
  published alongside the HTML as supporting files — no BigQuery access
  is needed at view time, so the link is shareable with anyone.
- **Layout:** headline chart first (commit volume, absolute and
  normalized against user-base growth, with LLM milestone markers), then
  supporting sections: language mix shift, AI/ML framework share growth,
  cumulative user base with GitHub's published milestones overlaid.
- **Interactivity:** hover for exact values, toggle between
  absolute/normalized views, filter the language chart to top N.
- **Refresh cycle:** re-run `refresh.py` → CSVs update → re-publish the
  same Artifact URL with updated data files → link stays stable, content
  updates.
- A static/narrative write-up may follow once the data's findings are
  clear, but is explicitly not part of this build.

## Out of scope (this pass)

- Geographic breakdown (data quality — see above).
- Automated/scheduled refresh (cron) — refresh is manual for now.
- Static narrative report — artifact only, for now.
- Trend-extrapolation statistical modeling beyond a simple pre-2022 linear
  projection for the "expected baseline" dashed line.
