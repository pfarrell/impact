from unittest.mock import MagicMock

import pytest

from scripts.bq_client import BigQueryClient, max_bytes_billed_from_env


def test_run_query_returns_rows_and_bytes_billed():
    mock_row = MagicMock()
    mock_row.items.return_value = [("year_month", "201501"), ("commit_count", 42)]

    mock_job = MagicMock()
    mock_job.result.return_value = [mock_row]
    mock_job.total_bytes_billed = 12345

    mock_client = MagicMock()
    mock_client.query.return_value = mock_job

    bq = BigQueryClient(client=mock_client)
    result = bq.run_query("SELECT 1", {"start_suffix": "201501"})

    assert result.rows == [{"year_month": "201501", "commit_count": 42}]
    assert result.bytes_billed == 12345
    mock_client.query.assert_called_once()


def test_run_query_handles_missing_bytes_billed():
    mock_job = MagicMock()
    mock_job.result.return_value = []
    mock_job.total_bytes_billed = None

    mock_client = MagicMock()
    mock_client.query.return_value = mock_job

    bq = BigQueryClient(client=mock_client)
    result = bq.run_query("SELECT 1", {})

    assert result.rows == []
    assert result.bytes_billed == 0


def _mock_client_with_job(job):
    mock_client = MagicMock()
    mock_client.query.return_value = job
    return mock_client


def test_run_query_applies_maximum_bytes_billed_when_set():
    mock_job = MagicMock()
    mock_job.result.return_value = []
    mock_job.total_bytes_billed = 0
    mock_client = _mock_client_with_job(mock_job)

    bq = BigQueryClient(client=mock_client, maximum_bytes_billed=2_000_000)
    bq.run_query("SELECT 1", {"start_suffix": "201501"})

    job_config = mock_client.query.call_args.kwargs["job_config"]
    assert job_config.maximum_bytes_billed == 2_000_000


def test_run_query_leaves_maximum_bytes_billed_unset_by_default():
    mock_job = MagicMock()
    mock_job.result.return_value = []
    mock_job.total_bytes_billed = 0
    mock_client = _mock_client_with_job(mock_job)

    bq = BigQueryClient(client=mock_client)
    bq.run_query("SELECT 1", {})

    job_config = mock_client.query.call_args.kwargs["job_config"]
    assert job_config.maximum_bytes_billed is None


def test_estimate_bytes_uses_dry_run_and_returns_bytes_processed():
    mock_job = MagicMock()
    mock_job.total_bytes_processed = 987654321
    mock_client = _mock_client_with_job(mock_job)

    bq = BigQueryClient(client=mock_client, maximum_bytes_billed=5)
    result = bq.estimate_bytes("SELECT 1", {"start_suffix": "201501", "end_suffix": "201502"})

    assert result == 987654321
    mock_client.query.assert_called_once()
    job_config = mock_client.query.call_args.kwargs["job_config"]
    assert job_config.dry_run is True
    assert job_config.use_query_cache is False
    bound = {p.name: p.value for p in job_config.query_parameters}
    assert bound == {"start_suffix": "201501", "end_suffix": "201502"}
    mock_job.result.assert_not_called()


def test_estimate_bytes_handles_missing_bytes_processed():
    mock_job = MagicMock()
    mock_job.total_bytes_processed = None
    mock_client = _mock_client_with_job(mock_job)

    bq = BigQueryClient(client=mock_client)
    assert bq.estimate_bytes("SELECT 1", {}) == 0


def test_max_bytes_billed_from_env_defaults_to_2_tib():
    assert max_bytes_billed_from_env({}) == 2 * 1024**4


def test_max_bytes_billed_from_env_reads_override():
    assert max_bytes_billed_from_env({"BQ_MAX_BYTES_BILLED": "500000000000"}) == 500_000_000_000


@pytest.mark.parametrize("bad", ["lots", "0", "-5"])
def test_max_bytes_billed_from_env_rejects_invalid_values(bad):
    with pytest.raises(ValueError):
        max_bytes_billed_from_env({"BQ_MAX_BYTES_BILLED": bad})
