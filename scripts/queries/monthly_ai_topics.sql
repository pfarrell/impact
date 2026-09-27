-- Matches only the repo-name segment (after the "/"), not the owner, so an
-- owner such as "claude" or "gpt-labs" doesn't pull in all of its repos.
-- @keyword_pattern comes from config_loader.build_keyword_regex and anchors
-- each keyword on token boundaries (so "jax" does not match "ajax").
SELECT
  _TABLE_SUFFIX AS year_month,
  SUM(CAST(JSON_EXTRACT_SCALAR(payload, '$.size') AS INT64)) AS ai_commit_count
FROM `githubarchive.month.*`
WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
  AND type = 'PushEvent'
  AND REGEXP_CONTAINS(REGEXP_EXTRACT(LOWER(repo.name), r'/(.+)$'), @keyword_pattern)
GROUP BY year_month
ORDER BY year_month
