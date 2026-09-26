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
