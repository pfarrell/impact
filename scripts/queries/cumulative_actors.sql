WITH actor_first_seen AS (
  SELECT
    actor.id AS actor_id,
    MIN(_TABLE_SUFFIX) AS first_seen_month
  FROM `githubarchive.month.*`
  WHERE _TABLE_SUFFIX <= @end_suffix
    AND actor.id IS NOT NULL
  GROUP BY actor_id
)
SELECT
  first_seen_month AS year_month,
  COUNT(*) AS new_actor_count
FROM actor_first_seen
WHERE first_seen_month BETWEEN @start_suffix AND @end_suffix
GROUP BY year_month
ORDER BY year_month
