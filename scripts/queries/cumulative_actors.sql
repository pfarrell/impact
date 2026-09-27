-- New accounts per month: each actor is counted once, in the month they first
-- appear in GH Archive.
WITH actor_first_seen AS (
  SELECT
    actor.id AS actor_id,
    MIN(_TABLE_SUFFIX) AS first_seen_month
  FROM `githubarchive.month.*`
  -- Intentionally NOT bounded below by @start_suffix: deciding whether an
  -- actor is "new" in a month needs their full prior history, otherwise
  -- someone active before @start_suffix would be re-counted as new at the
  -- start of the range. Only actor.id is read, so the full scan is cheap.
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
-- Load-bearing: csv_store.with_running_cumulative builds cumulative_total by
-- summing rows in the order returned. Removing or changing this ORDER BY
-- would silently corrupt the running total.
ORDER BY year_month
