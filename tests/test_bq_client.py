from unittest.mock import MagicMock

from scripts.bq_client import BigQueryClient


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
