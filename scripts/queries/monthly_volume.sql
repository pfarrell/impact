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
