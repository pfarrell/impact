"""Thin wrapper around google-cloud-bigquery for parameterized, cost-tracked queries."""
from __future__ import annotations

from collections import namedtuple

from google.cloud import bigquery

QueryResult = namedtuple("QueryResult", ["rows", "bytes_billed"])


class BigQueryClient:
    def __init__(self, project: str | None = None, client: bigquery.Client | None = None):
        self._client = client if client is not None else bigquery.Client(project=project)

    def run_query(self, sql: str, params: dict[str, str]) -> QueryResult:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(name, "STRING", value)
                for name, value in params.items()
            ]
        )
        job = self._client.query(sql, job_config=job_config)
        rows = [dict(row.items()) for row in job.result()]
        bytes_billed = job.total_bytes_billed or 0
        return QueryResult(rows=rows, bytes_billed=bytes_billed)
