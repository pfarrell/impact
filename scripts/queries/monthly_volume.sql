-- Reads only type, repo.id and actor.id. Never read `payload` here: it holds
-- nearly all of GH Archive's bytes, and reading it multiplied the backfill
-- cost ~100x. Pushes stand in for commits (payload.size), and all
-- PullRequestEvents (opened, closed, reopened, ...) stand in for PRs opened
-- (payload.action).
SELECT
  _TABLE_SUFFIX AS year_month,
  COUNTIF(type = 'PushEvent') AS push_count,
  COUNTIF(type = 'PullRequestEvent') AS pr_event_count,
  COUNT(DISTINCT IF(type = 'PushEvent', repo.id, NULL)) AS active_repo_count,
  COUNT(DISTINCT IF(type = 'PushEvent', actor.id, NULL)) AS active_actor_count
FROM `githubarchive.month.*`
WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
  AND type IN ('PushEvent', 'PullRequestEvent')
GROUP BY year_month
ORDER BY year_month
