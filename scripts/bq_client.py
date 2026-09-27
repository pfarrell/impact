"""Thin wrapper around google-cloud-bigquery for parameterized, cost-tracked queries."""
from __future__ import annotations

import os
from collections import namedtuple
from collections.abc import Mapping

from google.cloud import bigquery

QueryResult = namedtuple("QueryResult", ["rows", "bytes_billed"])

MAX_BYTES_BILLED_ENV = "BQ_MAX_BYTES_BILLED"
DEFAULT_MAX_BYTES_BILLED = 2 * 1024**4  # 2 TiB per query


def max_bytes_billed_from_env(environ: Mapping[str, str] | None = None) -> int:
    """Per-query billing cap from BQ_MAX_BYTES_BILLED (bytes), defaulting to 2 TiB."""
    env = os.environ if environ is None else environ
    raw = env.get(MAX_BYTES_BILLED_ENV, "").strip()
    if not raw:
        return DEFAULT_MAX_BYTES_BILLED
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{MAX_BYTES_BILLED_ENV} must be a positive integer byte count, got {raw!r}") from None
    if value <= 0:
        raise ValueError(f"{MAX_BYTES_BILLED_ENV} must be a positive integer byte count, got {raw!r}")
    return value


class BigQueryClient:
    def __init__(
        self,
        project: str | None = None,
        client: bigquery.Client | None = None,
        maximum_bytes_billed: int | None = None,
    ):
        self._client = client if client is not None else bigquery.Client(project=project)
        # Hard per-query ceiling enforced server-side by BigQuery: a query that
        # would bill more than this fails before running instead of charging.
        self._maximum_bytes_billed = maximum_bytes_billed

    @staticmethod
    def _query_parameters(params: dict[str, str]) -> list[bigquery.ScalarQueryParameter]:
        return [bigquery.ScalarQueryParameter(name, "STRING", value) for name, value in params.items()]

    def run_query(self, sql: str, params: dict[str, str]) -> QueryResult:
        job_config = bigquery.QueryJobConfig(query_parameters=self._query_parameters(params))
        if self._maximum_bytes_billed is not None:
            job_config.maximum_bytes_billed = self._maximum_bytes_billed
        job = self._client.query(sql, job_config=job_config)
        rows = [dict(row.items()) for row in job.result()]
        bytes_billed = job.total_bytes_billed or 0
        return QueryResult(rows=rows, bytes_billed=bytes_billed)

    def estimate_bytes(self, sql: str, params: dict[str, str]) -> int:
        """Dry-runs the query and returns the bytes it would process. Free; nothing executes."""
        job_config = bigquery.QueryJobConfig(
            query_parameters=self._query_parameters(params),
            dry_run=True,
            use_query_cache=False,
        )
        job = self._client.query(sql, job_config=job_config)
        return job.total_bytes_processed or 0
