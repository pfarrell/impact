-- One scan for both the language mix and the AI/ML-repo series. Run as two
-- queries they each scanned ~430 GB of the same columns; merged, the full
-- backfill fits the 1 TiB/month BigQuery sandbox free tier.
-- language_ai.split_language_ai turns the rows into monthly_language.csv and
-- monthly_ai_topics.csv.
--
-- Counts pushes, not commits: reading `payload` would multiply the cost ~100x.
--
-- AI/ML match: only the repo-name segment (after the "/"), not the owner, so
-- an owner such as "claude" or "gpt-labs" doesn't pull in all of its repos.
-- @keyword_pattern comes from config_loader.build_keyword_regex and anchors
-- each keyword on token boundaries (so "jax" does not match "ajax").
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
    COUNT(*) AS push_count
  FROM `githubarchive.month.*`
  WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
    AND type = 'PushEvent'
  GROUP BY year_month, repo_name
)
SELECT
  a.year_month,
  COALESCE(p.primary_language, 'Unknown') AS language,
  SUM(a.push_count) AS push_count,
  SUM(IF(REGEXP_CONTAINS(REGEXP_EXTRACT(LOWER(a.repo_name), r'/(.+)$'), @keyword_pattern),
         a.push_count, 0)) AS ai_push_count
FROM monthly_repo_activity a
LEFT JOIN repo_primary_language p
  ON a.repo_name = p.repo_name
GROUP BY a.year_month, language
ORDER BY a.year_month, push_count DESC
