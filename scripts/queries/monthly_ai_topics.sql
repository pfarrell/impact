SELECT
  _TABLE_SUFFIX AS year_month,
  SUM(CAST(JSON_EXTRACT_SCALAR(payload, '$.size') AS INT64)) AS ai_commit_count
FROM `githubarchive.month.*`
WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
  AND type = 'PushEvent'
  AND REGEXP_CONTAINS(LOWER(repo.name), @keyword_pattern)
GROUP BY year_month
ORDER BY year_month
